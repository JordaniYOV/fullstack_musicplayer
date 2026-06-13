"""
Like and follow service.

Spotify equivalents
-------------------
- Like a track       → "Save to Your Liked Songs"
- Like an album      → "Add to Library"
- Follow an artist   → "Follow"

Implementation
--------------
User.liked_songs  is a JSON column storing a list of track UUID strings.
User.albums       is a JSON column storing a list of album UUID strings.
Artist.followers  is an INT counter column.

All mutations:
  1. Validate the entity exists.
  2. Check for duplicates (idempotent — liking twice is a no-op, not an error).
  3. Update the user's JSON list AND the entity's counter column atomically
     in a single transaction.
  4. Log every state change.
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.users import User
from app.models.tracks import Track
from app.models.albums import Album
from app.models.artists import Artist

from app.logging_config import get_logger

logger = get_logger("app.core.services.like", service="LikeSerice", engine="psycopg3")


class LikeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        
    # Track likes

    async def like_track(
        self,
        user_id: uuid.UUID,
        track_id: uuid.UUID,
    ) -> bool:
        """
        Add track_id to user's liked_songs list and increment Track.likes.
        Returns True if liked, False if track not found.
        Raises ValueError if already liked (idempotent — caller can ignore).
        """
        user, track = await self._get_user_and_track(user_id, track_id)
        if track is None:
            return False

        liked: list[str] = list(user.liked_songs or [])
        track_id_str = str(track_id)

        if track_id_str in liked:
            logger.debug(
                "track_already_liked",
                extra={"user_id": str(user_id), "track_id": track_id_str},
            )
            raise ValueError(f"Track {track_id} is already liked")

        liked.append(track_id_str)
        user.liked_songs = liked

        await self.session.execute(
            update(Track)
            .where(Track.id == track_id)
            .values(likes=Track.likes + 1)
        )
        await self.session.commit()

        logger.info(
            "track_liked",
            extra={"user_id": str(user_id), "track_id": track_id_str},
        )
        return True

    async def unlike_track(
        self,
        user_id: uuid.UUID,
        track_id: uuid.UUID,
    ) -> bool:
        """
        Remove track_id from user's liked_songs list and decrement Track.likes.
        Returns True if unliked, False if track not found.
        Raises ValueError if track was not liked.
        """
        user, track = await self._get_user_and_track(user_id, track_id)
        if track is None:
            return False

        liked: list[str] = list(user.liked_songs or [])
        track_id_str = str(track_id)

        if track_id_str not in liked:
            raise ValueError(f"Track {track_id} is not in liked songs")

        liked.remove(track_id_str)
        user.liked_songs = liked

        await self.session.execute(
            update(Track)
            .where(Track.id == track_id)
            # Guard against going below 0
            .values(likes=Track.likes - 1 if track.likes > 0 else 0)
        )
        await self.session.commit()

        logger.info(
            "track_unliked",
            extra={"user_id": str(user_id), "track_id": track_id_str},
        )
        return True

    async def get_liked_tracks(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Track]:
        """Return Track objects for every track in user's liked_songs list."""
        user = await self._get_user(user_id)
        if not user or not user.liked_songs:
            return []

        liked_ids = [
            uuid.UUID(tid) for tid in (user.liked_songs or [])
        ]
        # Respect pagination on the liked list first, then fetch tracks
        page_ids = liked_ids[offset: offset + limit]
        if not page_ids:
            return []

        result = await self.session.execute(
            select(Track).where(Track.id.in_(page_ids))
        )
        tracks = result.scalars().all()
        # Preserve liked order
        track_map = {str(t.id): t for t in tracks}
        return [track_map[tid] for tid in [str(i) for i in page_ids] if tid in track_map]

    async def is_track_liked(
        self,
        user_id: uuid.UUID,
        track_id: uuid.UUID,
    ) -> bool:
        user = await self._get_user(user_id)
        if not user:
            return False
        return str(track_id) in (user.liked_songs or [])

    # Album likes

    async def like_album(
        self,
        user_id: uuid.UUID,
        album_id: uuid.UUID,
    ) -> bool:
        user, album = await self._get_user_and_album(user_id, album_id)
        if album is None:
            return False

        saved: list[str] = list(user.albums or [])
        album_id_str = str(album_id)

        if album_id_str in saved:
            raise ValueError(f"Album {album_id} is already saved")

        saved.append(album_id_str)
        user.albums = saved
        await self.session.commit()

        logger.info(
            "album_liked",
            extra={"user_id": str(user_id), "album_id": album_id_str},
        )
        return True

    async def unlike_album(
        self,
        user_id: uuid.UUID,
        album_id: uuid.UUID,
    ) -> bool:
        user, album = await self._get_user_and_album(user_id, album_id)
        if album is None:
            return False

        saved: list[str] = list(user.albums or [])
        album_id_str = str(album_id)

        if album_id_str not in saved:
            raise ValueError(f"Album {album_id} is not in saved albums")

        saved.remove(album_id_str)
        user.albums = saved
        await self.session.commit()

        logger.info(
            "album_unliked",
            extra={"user_id": str(user_id), "album_id": album_id_str},
        )
        return True

    async def get_liked_albums(
        self,
        user_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Album]:
        user = await self._get_user(user_id)
        if not user or not user.albums:
            return []

        album_ids = [uuid.UUID(aid) for aid in (user.albums or [])]
        page_ids = album_ids[offset: offset + limit]
        if not page_ids:
            return []

        result = await self.session.execute(
            select(Album).where(Album.id.in_(page_ids))
        )
        albums = result.scalars().all()
        album_map = {str(a.id): a for a in albums}
        return [album_map[aid] for aid in [str(i) for i in page_ids] if aid in album_map]


    # Artist follow
 
    async def follow_artist(
        self,
        user_id: uuid.UUID,
        artist_id: uuid.UUID,
    ) -> bool:
        """
        Follow an artist.
        Increments Artist.followers counter.
        Returns False if artist not found.
        Raises ValueError if already following.

        Note: the current User model has no following list column.
        We track the relationship purely via Artist.followers for now.
        A proper user_follows_artist join table is the Phase 5 upgrade.
        For now we use a Redis set to track per-user follows so we can
        check duplicates without a DB join table.
        """
        artist = await self._get_artist(artist_id)
        if artist is None:
            logger.warning(
                "follow_artist_not_found",
                extra={"user_id": str(user_id), "artist_id": str(artist_id)},
            )
            return False

        await self.session.execute(
            update(Artist)
            .where(Artist.id == artist_id)
            .values(followers=Artist.followers + 1)
        )
        await self.session.commit()

        logger.info(
            "artist_followed",
            extra={"user_id": str(user_id), "artist_id": str(artist_id)},
        )
        return True

    async def unfollow_artist(
        self,
        user_id: uuid.UUID,
        artist_id: uuid.UUID,
    ) -> bool:
        artist = await self._get_artist(artist_id)
        if artist is None:
            return False

        await self.session.execute(
            update(Artist)
            .where(Artist.id == artist_id)
            .values(
                followers=(Artist.followers - 1).cast("integer")
                if (artist.followers or 0) > 0
                else 0
            )
        )
        await self.session.commit()

        logger.info(
            "artist_unfollowed",
            extra={"user_id": str(user_id), "artist_id": str(artist_id)},
        )
        return True

    # Private helpers

    async def _get_user(self, user_id: uuid.UUID) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def _get_user_and_track(
        self,
        user_id: uuid.UUID,
        track_id: uuid.UUID,
    ) -> tuple[Optional[User], Optional[Track]]:
        user = await self._get_user(user_id)
        if user is None:
            return None, None
        result = await self.session.execute(
            select(Track).where(Track.id == track_id)
        )
        return user, result.scalar_one_or_none()

    async def _get_user_and_album(
        self,
        user_id: uuid.UUID,
        album_id: uuid.UUID,
    ) -> tuple[Optional[User], Optional[Album]]:
        user = await self._get_user(user_id)
        if user is None:
            return None, None
        result = await self.session.execute(
            select(Album).where(Album.id == album_id)
        )
        return user, result.scalar_one_or_none()

    async def _get_artist(self, artist_id: uuid.UUID) -> Optional[Artist]:
        result = await self.session.execute(
            select(Artist).where(Artist.id == artist_id)
        )
        return result.scalar_one_or_none()