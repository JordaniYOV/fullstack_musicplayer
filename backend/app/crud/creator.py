from sqlmodel import session
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.models.users import CreatorProfile


async def create_artist_profile(session: AsyncSession):
    artist = CreatorProfile(

    )
    session.add(artist)
    session.flush()