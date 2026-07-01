from fastapi import APIRouter, Response
from sqlmodel import select
from uuid import UUID 

from app.models.albums import Album, AlbumsCover
from app.models.token import Message
from app.api.deps import SessionDep

router = APIRouter(tags=["album_private"])

@router.delete('/delete_album')
async def delete_album(session: SessionDep, name: str): 
    """
    Delete album with parameters name
    """
    statement = select(Album).where(Album.album_name == name)
    album_obj = await session.execute(statement)
    album = album_obj.scalar_one_or_none()
    await session.delete(album)
    await session.commit() 
    return Message(message=f"Album {name} was deleted and all releated tracks")


@router.get('/album/cover/{cover_id}')
async def get_album_cover(session: SessionDep, cover_id: UUID):
    """
    Recieve album cover with cover_id
    """
    statement = select(AlbumsCover).where(AlbumsCover.id == cover_id)
    cover_obj = await session.execute(statement)
    cover = cover_obj.scalar_one_or_none()

    return Response(
        content=cover.album_cover, 
        media_type="image/png"
    )