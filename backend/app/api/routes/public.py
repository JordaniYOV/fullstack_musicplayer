import uuid 

from fastapi import APIRouter
from sqlmodel import select
from sqlalchemy.orm import selectinload

from app.api.deps import SessionDep
from app.models import Album

from redis.asyncio import Redis



router = APIRouter(tags=['get_info'])

@router.get('/album/{album_id}')
async def get_album_tracks(session: SessionDep, album_id: str): 
    statement = select(Album).where(Album.id == album_id).options(selectinload(Album.tracks))
    album_obj = await session.execute(statement)
    album = album_obj.scalar_one_or_none()
    return album.tracks

@router.get('/trand/song')
async def get_trand_albums(session: SessionDep): 
    statement = select(Track).where()
# @router.get('trand/song')
# async def get_trand_tracks(session: SessionDep): 
