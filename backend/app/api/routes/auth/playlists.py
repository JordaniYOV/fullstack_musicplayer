"""
Playlist routes.

POST   /playlists                         Create playlist
GET    /playlists                         List current user's playlists
GET    /playlists/public                  Browse public playlists
GET    /playlists/{id}                    Get full playlist with tracks
PATCH  /playlists/{id}                    Update name/description/visibility
DELETE /playlists/{id}                    Delete playlist
POST   /playlists/{id}/tracks             Add track
DELETE /playlists/{id}/tracks/{track_id}  Remove track
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import CurrentUser, SessionDep
from app.core.services.playlist import PlaylistService
from app.models.playlists import PlaylistCreate, PlaylistUpdate
from app.models.playlist_schemas import (
    AddTrackRequest,
    PlaylistResponse,
    PlaylistSummary,
)
from app.models.token import Message

router = APIRouter(prefix="/playlists", tags=["playlists"])


def _svc(session: SessionDep) -> PlaylistService:
    return PlaylistService(session)


# ------------------------------------------------------------------
# Create
# ------------------------------------------------------------------

@router.post(
    "",
    response_model=PlaylistSummary,
    status_code=201,
    summary="Create a playlist",
)
async def create_playlist(
    data: PlaylistCreate,
    current_user: CurrentUser,
    session: SessionDep,
):
    playlist = await _svc(session).create(
        owner_id=current_user.id,
        data=data,
    )
    return PlaylistSummary(
        id=playlist.id,
        name=playlist.name,
        description=playlist.description,
        is_public=playlist.is_public,
        owner_id=playlist.owner_id,
        track_count=0,
    )


# ------------------------------------------------------------------
# List / browse
# ------------------------------------------------------------------

@router.get(
    "",
    response_model=list[PlaylistSummary],
    summary="My playlists",
)
async def list_my_playlists(
    current_user: CurrentUser,
    session: SessionDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await _svc(session).get_user_playlists(
        owner_id=current_user.id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/public",
    response_model=list[PlaylistSummary],
    summary="Browse public playlists",
)
async def list_public_playlists(
    session: SessionDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await _svc(session).get_public_playlists(limit=limit, offset=offset)


# ------------------------------------------------------------------
# Single playlist
# ------------------------------------------------------------------

@router.get(
    "/{playlist_id}",
    response_model=PlaylistResponse,
    summary="Get playlist with tracks",
)
async def get_playlist(
    playlist_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
):
    print(f"useres: {current_user}")
    user_id = current_user.id if current_user else None
    playlist = await _svc(session).get_by_id(
        playlist_id=playlist_id,
        requesting_user_id=user_id,
    )
    if playlist is None:
        raise HTTPException(
            status_code=404,
            detail="Playlist not found or access denied",
        )
    return playlist



# ------------------------------------------------------------------
# Update
# ------------------------------------------------------------------

@router.patch(
    "/{playlist_id}",
    response_model=PlaylistSummary,
    summary="Update playlist metadata",
)
async def update_playlist(
    playlist_id: uuid.UUID,
    data: PlaylistUpdate,
    current_user: CurrentUser,
    session: SessionDep,
):
    svc = _svc(session)
    updated = await svc.update(
        playlist_id=playlist_id,
        owner_id=current_user.id,
        data=data,
    )
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail="Playlist not found or you are not the owner",
        )
    count = await svc._track_count(updated.id)
    return PlaylistSummary(
        id=updated.id,
        name=updated.name,
        description=updated.description,
        is_public=updated.is_public,
        owner_id=updated.owner_id,
        track_count=count,
    )


# ------------------------------------------------------------------
# Delete
# ------------------------------------------------------------------

@router.delete(
    "/{playlist_id}",
    response_model=Message,
    summary="Delete a playlist",
)
async def delete_playlist(
    playlist_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
):
    deleted = await _svc(session).delete(
        playlist_id=playlist_id,
        owner_id=current_user.id,
    )
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Playlist not found or you are not the owner",
        )
    return Message(message="Playlist deleted")


# ------------------------------------------------------------------
# Track management
# ------------------------------------------------------------------

@router.post(
    "/{playlist_id}/tracks",
    response_model=Message,
    summary="Add a track to a playlist",
)
async def add_track(
    playlist_id: uuid.UUID,
    body: AddTrackRequest,
    current_user: CurrentUser,
    session: SessionDep,
):
    try:
        ok = await _svc(session).add_track(
            playlist_id=playlist_id,
            owner_id=current_user.id,
            track_id=body.track_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Playlist or track not found, or you are not the owner",
        )
    return Message(message="Track added to playlist")


@router.delete(
    "/{playlist_id}/tracks/{track_id}",
    response_model=Message,
    summary="Remove a track from a playlist",
)
async def remove_track(
    playlist_id: uuid.UUID,
    track_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
):
    ok = await _svc(session).remove_track(
        playlist_id=playlist_id,
        owner_id=current_user.id,
        track_id=track_id,
    )
    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Playlist or track not found, or you are not the owner",
        )
    return Message(message="Track removed from playlist")