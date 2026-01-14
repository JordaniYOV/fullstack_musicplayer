from app.api.routes import user, login, tracks, public


from fastapi import FastAPI

app = FastAPI()

app.include_router(user.router)
app.include_router(login.router)
app.include_router(tracks.router)
app.include_router(public.router)

