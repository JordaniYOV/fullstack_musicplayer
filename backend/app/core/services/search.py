"""
Search service.

Strategy
--------
Uses PostgreSQL ILIKE for substring matching. This is fast enough for
a music catalog at Spotify-scale prototype (millions of rows) with a
trigram index (`pg_trgm`). For production move to
Elasticsearch/OpenSearch


Index to add (run once via Alembic):
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    CREATE INDEX idx_track_title_trgm ON track USING GIN (title gin_trgm_ops);
    CREATE INDEX idx_track_artist_trgm ON track USING GIN (artist gin_trgm_ops);
    CREATE INDEX idx_album_name_trgm ON album USING GIN (album_name gin_trgm_ops);
    CREATE INDEX idx_artist_name_trgm ON artist USING GIN (name gin_trgm_ops);

Query behaviour
---------------
- Splits query into tokens and matches ANY column that contains ALL tokens.
- Results are ranked by popularity (all_time_plays for tracks, play_count for
  albums, followers for artists) so the most relevant result appears first.
- Supports filtering by entity type via the `types` parameter.
- limit applies per entity type, not total.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tracks import Track
from app.models.albums import Album
from app.models.users import ArtistProfile
from app.schemas.search import (
    SearchResponse,
    TrackSearchResult,
    AlbumSearchResult,
    ArtistSearchResult,
)
from app.logging_config import get_logger

logger = get_logger("app.core.services.search", service="SearchService", engine="psycopg3")

# Entity type literals accepted by the API
ENTITY_TRACK = "track"
ENTITY_ALBUM = "album"
ENTITY_ARTIST = "artist"
ALL_TYPES = {ENTITY_TRACK, ENTITY_ALBUM, ENTITY_ARTIST}


class SearchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self,
        query: str,
        types: Optional[set[str]] = None,
        limit: int = 10,
    ) -> SearchResponse:
        """
        Search across tracks, albums, and artists.

        Parameters
        ----------
        query   : raw search string from the user
        types   : set of entity types to search; None = all three
        limit   : max results *per entity type*
        """
        if not query or not query.strip():
            logger.warning("search_empty_query")
            return SearchResponse(query=query)

        active_types = types if types else ALL_TYPES
        clean = query.strip()

        logger.info(
            "search_started",
            extra={
                "query": clean,
                "types": sorted(active_types),
                "limit": limit,
            },
        )

        tracks: list[TrackSearchResult] = []
        albums: list[AlbumSearchResult] = []
        artists: list[ArtistSearchResult] = []

        if ENTITY_TRACK in active_types:
            tracks = await self._search_tracks(clean, limit)

        if ENTITY_ALBUM in active_types:
            albums = await self._search_albums(clean, limit)

        if ENTITY_ARTIST in active_types:
            artists = await self._search_artists(clean, limit)

        response = SearchResponse(
            query=clean,
            tracks=tracks,
            albums=albums,
            artists=artists,
            total_tracks=len(tracks),
            total_albums=len(albums),
            total_artists=len(artists),
        )

        logger.info(
            "search_completed",
            extra={
                "query": clean,
                "total_tracks": response.total_tracks,
                "total_albums": response.total_albums,
                "total_artists": response.total_artists,
            },
        )
        return response

    
    # Per-entity search helpers
 
    async def _search_tracks(self, query: str, limit: int) -> list[TrackSearchResult]:
        """
        Match tracks where title OR artist ILIKE %query%.
        Ranked by all_time_plays descending.
        """
        pattern = f"%{query}%"
        try:
            result = await self.session.execute(
                select(Track)
                .where(
                    or_(
                        Track.title.ilike(pattern),
                        Track.artist.ilike(pattern),
                        Track.genre.ilike(pattern),
                    )
                )
                .order_by(Track.all_time_plays.desc())
                .limit(limit)
            )
            tracks = result.scalars().all()

            logger.debug(
                "search_tracks_result",
                extra={"query": query, "count": len(tracks)},
            )
            return [
                TrackSearchResult(
                    id=t.id,
                    title=t.title,
                    artist=t.artist,
                    genre=t.genre,
                    duration_sec=t.duration_sec,
                    album_id=t.album_id,
                    all_time_plays=t.all_time_plays,
                    likes=t.likes,
                )
                for t in tracks
            ]
        except Exception as exc:
            logger.error(
                "search_tracks_error",
                extra={"query": query, "error": str(exc)},
                exc_info=True,
            )
            return []

    async def _search_albums(self, query: str, limit: int) -> list[AlbumSearchResult]:
        """Match albums where album_name OR artist_name ILIKE %query%."""
        pattern = f"%{query}%"
        try:
            result = await self.session.execute(
                select(Album)
                .where(
                    or_(
                        Album.album_name.ilike(pattern),
                        Album.artist_name.ilike(pattern),
                    )
                )
                .order_by(Album.play_count.desc())
                .limit(limit)
            )
            albums = result.scalars().all()

            logger.debug(
                "search_albums_result",
                extra={"query": query, "count": len(albums)},
            )
            return [
                AlbumSearchResult(
                    id=a.id,
                    album_name=a.album_name,
                    artist_name=a.artist_name,
                    year_release=a.year_release,
                    total_tracks=a.total_tracks,
                    play_count=a.play_count,
                )
                for a in albums
            ]
        except Exception as exc:
            logger.error(
                "search_albums_error",
                extra={"query": query, "error": str(exc)},
                exc_info=True,
            )
            return []

    async def _search_artists(self, query: str, limit: int) -> list[ArtistSearchResult]:
        """Match artists where name OR bio ILIKE %query%."""
        pattern = f"%{query}%"
        try:
            result = await self.session.execute(
                select(ArtistProfile)
                .where(
                    or_(
                        ArtistProfile.name.ilike(pattern),
                        ArtistProfile.bio.ilike(pattern),
                    )
                )
                .order_by(ArtistProfile.followers.desc())
                .limit(limit)
            )
            artists = result.scalars().all()

            logger.debug(
                "search_artists_result",
                extra={"query": query, "count": len(artists)},
            )
            return [
                ArtistSearchResult(
                    id=a.id,
                    name=a.name,
                    bio=a.bio,
                    verified=a.verified,
                    monthly_listeners=a.monthly_listeners,
                    followers=a.followers,
                )
                for a in artists
            ]
        except Exception as exc:
            logger.error(
                "search_artists_error",
                extra={"query": query, "error": str(exc)},
                exc_info=True,
            )
            return []