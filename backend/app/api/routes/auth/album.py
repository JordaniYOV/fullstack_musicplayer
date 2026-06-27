"""
Public album routes.

GET /albums/{album_id}           Album detail with track list
GET /albums/{album_id}/tracks    Album's tracks in order
GET /albums/popular              Most-played albums (uses PopularAlbums table)
GET /albums/new-releases         Most recently released albums
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import SessionDep
from app.models.albums import Album, PopularAlbums
from app.models.tracks import Track
from app.models.search_schemas import AlbumSearchResult, TrackSearchResult
from app.models.playlist_schemas import TrackSummary

router = APIRouter(prefix="/albums", tags=["albums"])


# Response schemas 

class AlbumDetailResponse(BaseModel):
    id: uuid.UUID
    album_name: str
    artist_name: str
    year_release: int
    total_tracks: int
    play_count: int
    tracks: list[TrackSummary]

    class Config:
        from_attributes = True


# Routes 

@router.get(
    "/popular",
    response_model=list[AlbumSearchResult],
    summary="Most played albums",
    description=(
        "Returns albums ranked by play_count. "
        "Falls back to direct Album.play_count ordering if the PopularAlbums "
        "aggregation table is empty."
    ),
)
async def get_popular_albums(
    session: SessionDep,
    limit: int = Query(default=20, ge=1, le=100),
):
    # Try PopularAlbums table first (populated by Celery aggregation)
    pop_result = await session.execute(
        select(PopularAlbums)
        .order_by(PopularAlbums.play_count.desc())
        .limit(limit)
    )
    popular = pop_result.scalars().all()

    if popular:
        album_ids = [p.album_id for p in popular]
        albums_result = await session.execute(
            select(Album).where(Album.id.in_(album_ids))
        )
        album_map = {a.id: a for a in albums_result.scalars().all()}
        albums = [album_map[p.album_id] for p in popular if p.album_id in album_map]
    else:
        # Fallback: order directly by play_count on Album
        result = await session.execute(
            select(Album)
            .order_by(Album.play_count.desc())
            .limit(limit)
        )
        albums = result.scalars().all()

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


@router.get(
    "/new-releases",
    response_model=list[AlbumSearchResult],
    summary="Most recently released albums",
)
async def get_new_releases(
    session: SessionDep,
    limit: int = Query(default=20, ge=1, le=100),
):
    result = await session.execute(
        select(Album)
        .order_by(Album.year_release.desc())
        .limit(limit)
    )
    albums = result.scalars().all()

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


@router.get(
    "/{album_id}",
    response_model=AlbumDetailResponse,
    summary="Album detail with full track list",
)
async def get_album(album_id: uuid.UUID, session: SessionDep):
    result = await session.execute(
        select(Album)
        .where(Album.id == album_id)
        .options(selectinload(Album.tracks))
    )
    album = result.scalar_one_or_none()
    if album is None:
        raise HTTPException(status_code=404, detail="Album not found")

    tracks = [
        TrackSummary(
            id=t.id,
            title=t.title,
            artist=t.artist,
            duration_sec=t.duration_sec,
            genre=t.genre,
            likes=t.likes,
        )
        for t in sorted(album.tracks, key=lambda t: t.title)
    ]

    return AlbumDetailResponse(
        id=album.id,
        album_name=album.album_name,
        artist_name=album.artist_name,
        year_release=album.year_release,
        total_tracks=album.total_tracks,
        play_count=album.play_count,
        tracks=tracks,
    )


@router.get(
    "/{album_id}/tracks",
    response_model=list[TrackSearchResult],
    summary="Album tracks",
)
async def get_album_tracks(
    album_id: uuid.UUID,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    album_result = await session.execute(
        select(Album).where(Album.id == album_id)
    )
    if album_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Album not found")

    result = await session.execute(
        select(Track)
        .where(Track.album_id == album_id)
        .order_by(Track.title)
        .limit(limit)
        .offset(offset)
    )
    tracks = result.scalars().all()

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