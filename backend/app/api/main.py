from app.api.routes import user, login, tracks


from fastapi import FastAPI

app = FastAPI()

app.include_router(user.router)
app.include_router(login.router)
app.include_router(tracks.router)

