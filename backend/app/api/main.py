from app.api.routes import tracks_private, tracks_public, user, login


from fastapi import APIRouter

api_router = APIRouter()

api_router.include_router(user.router)
api_router.include_router(login.router)
api_router.include_router(tracks_private.router)
api_router.include_router(tracks_public.router)

