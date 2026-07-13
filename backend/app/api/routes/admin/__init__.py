from fastapi import APIRouter

from .album import router as album_router
from .creator import router as creator_router
from .health import router as health_router
from .track import router as track_router

admin_routes = APIRouter(
    prefix="/admin", 
    # dependencies=Depends()
)

admin_routes.include_router(album_router)
admin_routes.include_router(creator_router)
admin_routes.include_router(health_router)
admin_routes.include_router(track_router)

__all__ = ["admin_routes"]