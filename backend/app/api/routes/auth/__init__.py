from .album import router as album_routes
from .artist import router as artist_routes
from .charts import router as chart_routes
from .library import router as library_routes
from .playlists import router as playlist_routes
from .track import router as track_routes
from .user import router as user_routes

from fastapi import APIRouter 

auth_routes = APIRouter()

auth_routes.include_router(album_routes)
auth_routes.include_router(artist_routes)
auth_routes.include_router(chart_routes)
auth_routes.include_router(library_routes)
auth_routes.include_router(playlist_routes)
auth_routes.include_router(track_routes)
auth_routes.include_router(user_routes)

__all__ = ["auth_routes"]