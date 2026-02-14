from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .api.main import api_router

app = FastAPI(
    title=settings.PROJECT_NAME, 
)

origins = [
    "http://localhost", 
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"],
)


app.include_router(api_router)