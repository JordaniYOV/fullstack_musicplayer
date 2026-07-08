"""
Public artist routes.

GET /artists/{artist_id}              Artist profile
GET /artists/{artist_id}/tracks       Artist's top tracks (ranked by all_time_plays)
GET /artists/{artist_id}/albums       Artist's discography
GET /artists/{artist_id}/popular      Artist's most-played tracks (top 10)
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import SessionDep
from app.models.users import ArtistProfile
from app.models.albums import Album
from app.models.tracks import Track
from app.schemas.search import AlbumSearchResult, TrackSearchResult

router = APIRouter(prefix="/artists", tags=["artists"])


# Response schemas

class ArtistProfileResponse(BaseModel):
    id: uuid.UUID
    name: str
    bio: Optional[str]
    verified: bool
    monthly_listeners: Optional[int]
    followers: Optional[int]
    album_count: int

    class Config:
        from_attributes = True


# Routes 

@router.get(
    "/{artist_id}",
    response_model=ArtistProfileResponse,
    summary="Get artist profile",
)
async def get_artist(artist_id: uuid.UUID, session: SessionDep):
    result = await session.execute(
        select(ArtistProfile)
        .where(ArtistProfile.id == artist_id)
        .options(selectinload(ArtistProfile.own_albums))
    )
    artist = result.scalar_one_or_none()
    if artist is None:
        raise HTTPException(status_code=404, detail="Artist not found")

    return ArtistProfileResponse(
        id=artist.id,
        name=artist.name,
        bio=artist.bio,
        verified=artist.verified,
        monthly_listeners=artist.monthly_listeners,
        followers=artist.followers,
        album_count=len(artist.albums),
    )


@router.get(
    "/{artist_id}/tracks",
    response_model=list[TrackSearchResult],
    summary="Artist's tracks sorted by popularity",
)
async def get_artist_tracks(
    artist_id: uuid.UUID,
    session: SessionDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    # Verify artist exists
    artist_result = await session.execute(
        select(ArtistProfile).where(ArtistProfile.id == artist_id)
    )
    if artist_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Artist not found")

    result = await session.execute(
        select(Track)
        .where(Track.artist == (
            await session.execute(
                select(ArtistProfile.name).where(ArtistProfile.id == artist_id)
            )
        ).scalar_one())
        .order_by(Track.all_time_plays.desc())
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


@router.get(
    "/{artist_id}/albums",
    response_model=list[AlbumSearchResult],
    summary="Artist's discography",
)
async def get_artist_albums(
    artist_id: uuid.UUID,
    session: SessionDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    artist_result = await session.execute(
        select(ArtistProfile).where(ArtistProfile.id == artist_id)
    )
    if artist_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Artist not found")

    result = await session.execute(
        select(Album)
        .where(Album.artist_id == artist_id)
        .order_by(Album.year_release.desc())
        .limit(limit)
        .offset(offset)
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
    "/{artist_id}/popular",
    response_model=list[TrackSearchResult],
    summary="Artist's top 10 most played tracks",
)
async def get_artist_popular_tracks(
    artist_id: uuid.UUID,
    session: SessionDep,
):
    artist_result = await session.execute(
        select(ArtistProfile.name).where(ArtistProfile.id == artist_id)
    )
    artist_name = artist_result.scalar_one_or_none()
    if artist_name is None:
        raise HTTPException(status_code=404, detail="Artist not found")

    result = await session.execute(
        select(Track)
        .where(Track.artist == artist_name)
        .order_by(Track.all_time_plays.desc())
        .limit(10)
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