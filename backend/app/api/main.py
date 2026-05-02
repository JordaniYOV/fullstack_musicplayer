from app.api.routes.private import album_pr, artist, track_pr
from app.api.routes.public import album_pu, charts, login, track_pu, user

from fastapi import APIRouter



api_router = APIRouter()

api_router.include_router(user.router)
api_router.include_router(login.router)
api_router.include_router(track_pu.router)
api_router.include_router(album_pu.router)
api_router.include_router(charts.router)


api_router.include_router(artist.router)
api_router.include_router(album_pr.router)
api_router.include_router(track_pr.router)
