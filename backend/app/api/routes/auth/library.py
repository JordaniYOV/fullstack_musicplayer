"""
Like / follow routes.

Track likes
    POST   /me/tracks/{track_id}/like
    DELETE /me/tracks/{track_id}/like
    GET    /me/tracks/liked

Album saves
    POST   /me/albums/{album_id}/save
    DELETE /me/albums/{album_id}/save
    GET    /me/albums/saved

Artist follows
    POST   /me/artists/{artist_id}/follow
    DELETE /me/artists/{artist_id}/follow
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, SessionDep
from app.core.services.like import LikeService
from app.schemas.token import Message
from app.schemas.search import TrackSearchResult, AlbumSearchResult

router = APIRouter(prefix="/me", tags=["library"])


def _svc(session: SessionDep) -> LikeService:
    return LikeService(session)


# Track likes

@router.post(
    "/tracks/{track_id}/like",
    response_model=Message,
    summary="Like a track",
)
async def like_track(
    track_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
):
    try:
        ok = await _svc(session).like_track(
            user_id=current_user.id,
            track_id=track_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    if not ok:
        raise HTTPException(status_code=404, detail="Track not found")
    return Message(message="Track added to liked songs")


@router.delete(
    "/tracks/{track_id}/like",
    response_model=Message,
    summary="Unlike a track",
)
async def unlike_track(
    track_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
):
    try:
        ok = await _svc(session).unlike_track(
            user_id=current_user.id,
            track_id=track_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not ok:
        raise HTTPException(status_code=404, detail="Track not found")
    return Message(message="Track removed from liked songs")


@router.get(
    "/tracks/liked",
    response_model=list[TrackSearchResult],
    summary="Get liked tracks",
)
async def get_liked_tracks(
    current_user: CurrentUser,
    session: SessionDep,
):
    tracks = await _svc(session).get_liked_tracks(user_id=current_user.id)
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
    "/tracks/{track_id}/liked",
    response_model=dict,
    summary="Check if track is liked",
)
async def is_track_liked(
    track_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
):
    liked = await _svc(session).is_track_liked(
        user_id=current_user.id,
        track_id=track_id,
    )
    return {"track_id": str(track_id), "liked": liked}


# Album saves

@router.post(
    "/albums/{album_id}/save",
    response_model=Message,
    summary="Save an album to library",
)
async def save_album(
    album_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
):
    try:
        ok = await _svc(session).like_album(
            user_id=current_user.id,
            album_id=album_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    if not ok:
        raise HTTPException(status_code=404, detail="Album not found")
    return Message(message="Album saved to library")


@router.delete(
    "/albums/{album_id}/save",
    response_model=Message,
    summary="Remove album from library",
)
async def unsave_album(
    album_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
):
    try:
        ok = await _svc(session).unlike_album(
            user_id=current_user.id,
            album_id=album_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not ok:
        raise HTTPException(status_code=404, detail="Album not found")
    return Message(message="Album removed from library")


@router.get(
    "/albums/saved",
    response_model=list[AlbumSearchResult],
    summary="Get saved albums",
)
async def get_saved_albums(
    current_user: CurrentUser,
    session: SessionDep,
):
    albums = await _svc(session).get_liked_albums(user_id=current_user.id)
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


# Artist follows

@router.post(
    "/artists/{artist_id}/follow",
    response_model=Message,
    summary="Follow an artist",
)
async def follow_artist(
    artist_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
):
    ok = await _svc(session).follow_artist(
        user_id=current_user.id,
        artist_id=artist_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Artist not found")
    return Message(message="Now following artist")


@router.delete(
    "/artists/{artist_id}/follow",
    response_model=Message,
    summary="Unfollow an artist",
)
async def unfollow_artist(
    artist_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
):
    ok = await _svc(session).unfollow_artist(
        user_id=current_user.id,
        artist_id=artist_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Artist not found")
    return Message(message="Unfollowed artist")