from fastapi import FastAPI

from .core.config import settings
from .api.main import api_router

app = FastAPI(
    title=settings.PROJECT_NAME, 
)


app.include_router(api_router)