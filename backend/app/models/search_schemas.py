"""
Search response schemas.

Search returns a unified response with separate buckets for each entity type
so the frontend can render sections ("Tracks", "Albums", "Artists") from one
request instead of three.
"""
from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, Field


class TrackSearchResult(BaseModel):
    id: uuid.UUID
    title: str
    artist: str
    genre: str
    duration_sec: int
    album_id: Optional[uuid.UUID]
    all_time_plays: int
    likes: int

    class Config:
        from_attributes = True


class AlbumSearchResult(BaseModel):
    id: uuid.UUID
    album_name: str
    artist_name: str
    year_release: int
    total_tracks: int
    play_count: int

    class Config:
        from_attributes = True


class ArtistSearchResult(BaseModel):
    id: uuid.UUID
    name: str
    bio: Optional[str]
    verified: bool
    monthly_listeners: Optional[int]
    followers: Optional[int]

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    query: str
    tracks: list[TrackSearchResult] = Field(default_factory=list)
    albums: list[AlbumSearchResult] = Field(default_factory=list)
    artists: list[ArtistSearchResult] = Field(default_factory=list)
    total_tracks: int = 0
    total_albums: int = 0
    total_artists: int = 0