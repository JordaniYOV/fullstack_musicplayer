"""
Playlist service.

Responsibilities
----------------
1. Create / read / update / delete playlists with ownership enforcement.
2. Add / remove tracks — validates both playlist and track exist.
3. List a user's own playlists and public playlists.
4. Structured logging on every mutation.

All DB work uses AsyncSession. No Redis needed here — playlists are not
a hot read path that warrants caching in Phase 4.

Ownership rule: only the playlist owner can mutate it. Anyone can read a
public playlist; only the owner can read a private one.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.playlists import Playlist, PlaylistTrack, PlaylistCreate, PlaylistUpdate
from app.models.tracks import Track
from app.schemas.playlist import PlaylistResponse, PlaylistSummary, TrackSummary
from app.logging_config import get_logger

logger = get_logger("app.service.playlist", service="PlaylistService", engine="psycopg3")


class PlaylistService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # Create

    async def create(
        self,
        owner_id: uuid.UUID,
        data: PlaylistCreate,
    ) -> Playlist:
        """Create a new playlist owned by owner_id."""
        playlist = Playlist(
            name=data.name,
            description=data.description,
            is_public=data.is_public,
            owner_id=owner_id,
        )
        self.session.add(playlist)
        await self.session.commit()
        await self.session.refresh(playlist)

        logger.info(
            "playlist_created",
            extra={
                "playlist_id": str(playlist.id),
                "owner_id": str(owner_id),
                "name": playlist.name,
                "is_public": playlist.is_public,
            },
        )
        return playlist
    
    # Read
  
    async def get_by_id(
        self,
        playlist_id: uuid.UUID,
        requesting_user_id: Optional[uuid.UUID] = None,
    ) -> Optional[PlaylistResponse]:
        """
        Return a full playlist with tracks.
        Private playlists are only visible to their owner.
        Returns None if not found or not authorised.
        """
        result = await self.session.execute(
            select(Playlist)
            .where(Playlist.id == playlist_id)
            .options(
                selectinload(Playlist.tracks).selectinload(PlaylistTrack.track)
            )
        )
        playlist = result.scalar_one_or_none()

        if playlist is None:
            logger.debug(
                "playlist_not_found",
                extra={"playlist_id": str(playlist_id)},
            )
            return None

        if not playlist.is_public and playlist.owner_id != requesting_user_id:
            logger.warning(
                "playlist_access_denied",
                extra={
                    "playlist_id": str(playlist_id),
                    "requesting_user_id": str(requesting_user_id),
                    "owner_id": str(playlist.owner_id),
                },
            )
            return None

        tracks = [
            TrackSummary(
                id=pt.track.id,
                title=pt.track.title,
                artist=pt.track.artist,
                duration_sec=pt.track.duration_sec,
                genre=pt.track.genre,
                likes=pt.track.likes,
            )
            for pt in playlist.tracks
            if pt.track is not None
        ]

        return PlaylistResponse(
            id=playlist.id,
            name=playlist.name,
            description=playlist.description,
            is_public=playlist.is_public,
            owner_id=playlist.owner_id,
            tracks=tracks,
            track_count=len(tracks),
        )

    async def get_user_playlists(
        self,
        owner_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[PlaylistSummary]:
        """Return all playlists owned by a user (public + private)."""
        result = await self.session.execute(
            select(Playlist)
            .where(Playlist.owner_id == owner_id)
            .order_by(Playlist.name)
            .limit(limit)
            .offset(offset)
        )
        
        playlists = result.scalars().all()

        summaries = []
        for pl in playlists:
            count = await self._track_count(pl.id)
            summaries.append(
                PlaylistSummary(
                    id=pl.id,
                    name=pl.name,
                    description=pl.description,
                    is_public=pl.is_public,
                    owner_id=pl.owner_id,
                    track_count=count,
                )
            )
        return summaries

    async def get_public_playlists(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> list[PlaylistSummary]:
        """Return all public playlists — used for discovery."""
        result = await self.session.execute(
            select(Playlist)
            .where(Playlist.is_public.is_(True))
            .order_by(Playlist.name)
            .limit(limit)
            .offset(offset)
        )
        playlists = result.scalars().all()

        summaries = []
        for pl in playlists:
            count = await self._track_count(pl.id)
            summaries.append(
                PlaylistSummary(
                    id=pl.id,
                    name=pl.name,
                    description=pl.description,
                    is_public=pl.is_public,
                    owner_id=pl.owner_id,
                    track_count=count,
                )
            )
        return summaries

    # Update
    
    async def update(
        self,
        playlist_id: uuid.UUID,
        owner_id: uuid.UUID,
        data: PlaylistUpdate,
    ) -> Optional[Playlist]:
        """
        Update name / description / is_public.
        Returns None if playlist not found or caller is not the owner.
        """
        playlist = await self._get_owned(playlist_id, owner_id)
        if playlist is None:
            return None

        playlist.name = data.name
        playlist.description = data.description
        # PlaylistUpdate inherits is_public from PlaylistBase
        if hasattr(data, "is_public"):
            playlist.is_public = data.is_public

        await self.session.commit()
        await self.session.refresh(playlist)

        logger.info(
            "playlist_updated",
            extra={
                "playlist_id": str(playlist_id),
                "owner_id": str(owner_id),
                "new_name": playlist.name,
            },
        )
        return playlist

    # Delete

    async def delete(
        self,
        playlist_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> bool:
        """
        Delete a playlist and all its PlaylistTrack rows.
        Returns False if not found or caller is not the owner.
        """
        playlist = await self._get_owned(playlist_id, owner_id)
        if playlist is None:
            return False

        # Remove join rows first (no cascade set on PlaylistTrack FK)
        await self.session.execute(
            delete(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist_id)
        )
        await self.session.delete(playlist)
        await self.session.commit()

        logger.info(
            "playlist_deleted",
            extra={
                "playlist_id": str(playlist_id),
                "owner_id": str(owner_id),
            },
        )
        return True

    # Track management
    
    async def add_track(
        self,
        playlist_id: uuid.UUID,
        owner_id: uuid.UUID,
        track_id: uuid.UUID,
    ) -> bool:
        """
        Add a track to a playlist.
        Returns False if playlist not found / not owned / track not found.
        Raises ValueError if track is already in the playlist.
        """
        playlist = await self._get_owned(playlist_id, owner_id)
        if playlist is None:
            return False

        # Verify track exists
        track_result = await self.session.execute(
            select(Track).where(Track.id == track_id)
        )
        if track_result.scalar_one_or_none() is None:
            logger.warning(
                "playlist_add_track_not_found",
                extra={
                    "playlist_id": str(playlist_id),
                    "track_id": str(track_id),
                },
            )
            return False

        # Prevent duplicate entries
        existing = await self.session.execute(
            select(PlaylistTrack).where(
                PlaylistTrack.playlist_id == playlist_id,
                PlaylistTrack.track_id == track_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError(f"Track {track_id} is already in playlist {playlist_id}")

        self.session.add(
            PlaylistTrack(playlist_id=playlist_id, track_id=track_id)
        )
        await self.session.commit()

        logger.info(
            "playlist_track_added",
            extra={
                "playlist_id": str(playlist_id),
                "track_id": str(track_id),
                "owner_id": str(owner_id),
            },
        )
        return True

    async def remove_track(
        self,
        playlist_id: uuid.UUID,
        owner_id: uuid.UUID,
        track_id: uuid.UUID,
    ) -> bool:
        """
        Remove a track from a playlist.
        Returns False if playlist not found / not owned / track not in playlist.
        """
        playlist = await self._get_owned(playlist_id, owner_id)
        if playlist is None:
            return False

        result = await self.session.execute(
            select(PlaylistTrack).where(
                PlaylistTrack.playlist_id == playlist_id,
                PlaylistTrack.track_id == track_id,
            )
        )
        pt = result.scalar_one_or_none()
        if pt is None:
            logger.warning(
                "playlist_remove_track_not_in_playlist",
                extra={
                    "playlist_id": str(playlist_id),
                    "track_id": str(track_id),
                },
            )
            return False

        await self.session.delete(pt)
        await self.session.commit()

        logger.info(
            "playlist_track_removed",
            extra={
                "playlist_id": str(playlist_id),
                "track_id": str(track_id),
                "owner_id": str(owner_id),
            },
        )
        return True

    # Private helpers

    async def _get_owned(
        self,
        playlist_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> Optional[Playlist]:
        """
        Fetch a playlist and verify ownership in one query.
        Returns None (not raises) so callers decide the HTTP status.
        """
        result = await self.session.execute(
            select(Playlist).where(
                Playlist.id == playlist_id,
                Playlist.owner_id == owner_id,
            )
        )
        playlist = result.scalar_one_or_none()
        if playlist is None:
            logger.debug(
                "playlist_not_found_or_not_owned",
                extra={
                    "playlist_id": str(playlist_id),
                    "owner_id": str(owner_id),
                },
            )
        return playlist

    async def _track_count(self, playlist_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count()).where(PlaylistTrack.playlist_id == playlist_id)
        )
        return result.scalar_one() or 0