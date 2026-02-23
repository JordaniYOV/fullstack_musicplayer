
from sqlmodel import create_engine

from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

import asyncio

async_engine = create_async_engine(
    settings.ASYNC_DB_URL, 
    echo=True, 
    pool_size=5, 
    max_overflow=10, 
    pool_pre_ping=True)

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

engine = create_engine(settings.DB_URL, echo=True)

def init_db():
    from models import User, Album, Artist, Playlist, PlaylistTrack, Track
    from sqlmodel import SQLModel

    SQLModel.metadata.create_all(engine)

