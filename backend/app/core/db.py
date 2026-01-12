
from sqlmodel import create_engine

from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings


engine = create_async_engine(settings.DB_URL, echo=True)

def init_db():
    from models import User, Album, Artist, Playlist, PlaylistTrack, Track
    from sqlmodel import SQLModel

    SQLModel.metadata.create_all(engine)

