"""
Playlist response schemas.

The existing PlaylistBase / PlaylistCreate / PlaylistUpdate in playlists.py
are kept as-is. This file adds richer response shapes that include
track summaries and owner info — used by the API layer only.
"""
from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, Field


class TrackSummary(BaseModel):
    """Minimal track info embedded inside a playlist response."""
    id: uuid.UUID
    title: str
    artist: str
    duration_sec: int
    genre: str
    likes: int

    class Config:
        from_attributes = True


class PlaylistResponse(BaseModel):
    """Full playlist with its tracks, returned by GET /playlists/{id}."""
    id: uuid.UUID
    name: str
    description: Optional[str]
    is_public: bool
    owner_id: uuid.UUID
    tracks: list[TrackSummary] = Field(default_factory=list)
    track_count: int = 0

    class Config:
        from_attributes = True


class PlaylistSummary(BaseModel):
    """Lightweight playlist info for list endpoints."""
    id: uuid.UUID
    name: str
    description: Optional[str]
    is_public: bool
    owner_id: uuid.UUID
    track_count: int = 0

    class Config:
        from_attributes = True


class AddTrackRequest(BaseModel):
    track_id: uuid.UUID


class RemoveTrackRequest(BaseModel):
    track_id: uuid.UUID


class ReorderRequest(BaseModel):
    """Future: track_ids in desired order. Placeholder for Phase 5."""
    track_ids: list[uuid.UUID]