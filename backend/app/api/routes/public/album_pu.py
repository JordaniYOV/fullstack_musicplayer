from fastapi import APIRouter
from sqlmodel import select
from sqlalchemy.orm import selectinload

from app.models import Album 
from ...deps import SessionDep


router = APIRouter(tags=["album"])

@router.get('/album/{album_id}/')
async def get_album_tracks(session: SessionDep, album_id: str): 
    statement = select(Album).where(Album.id == album_id).options(selectinload(Album.tracks))
    album_obj = await session.execute(statement)
    album = album_obj.scalar_one_or_none()
    return album.tracks

# @router.get('/trand/albums')
# async def get_trand_albums(session: SessionDep): 
#     statement = select(Track).where()
