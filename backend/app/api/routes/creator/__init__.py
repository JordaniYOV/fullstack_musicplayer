from fastapi import APIRouter

from .album import router as album_router
from .profile import router as profile_router

artist_router = APIRouter(
    prefix=["/artist"]
)

artist_router.include_router(album_router)
artist_router.include_router(profile_router)

__all__ = ["artist_router"]