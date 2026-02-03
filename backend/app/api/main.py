from app.api.routes import user, login, tracks, public


from fastapi import APIRouter

api_router = APIRouter()

api_router.include_router(user.router)
api_router.include_router(login.router)
api_router.include_router(tracks.router)
api_router.include_router(public.router)

