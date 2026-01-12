from email.mime import audio
from sqlmodel import select
from typing import Annotated

from fastapi import APIRouter, UploadFile, File

from app.api.deps import SessionDep
from app.models import Album, Artist,  Message
from app.api.utils import add_track

router = APIRouter(tags=['admin'])

@router.post('/track')
async def upload_tracks(session: SessionDep, 
                tracks: Annotated[list[UploadFile], File(description="To add whole album or sibgle track")],
                artist_name: str, 
                album_name: str,
                album_cover: UploadFile | None = None,
                year_release:  int = None
):

    statement = select(Album).where(Album.album_name == album_name)
    album_obj = await session.execute(statement)
    album = album_obj.scalar_one_or_none()
    if album is not None: 
        await add_track(session=session, track_files=tracks, album_id=album.id)
        return Message(message=f"Album {album.album_name} already exists, tracks added to that album {album.id}")
    else:
        cover = await album_cover.read()
        cover_type = album_cover.content_type
        artist_obj = await session.execute(select(Artist))
        artist = artist_obj.scalar_one_or_none()
        album = Album(
            album_name=album_name, 
            album_cover=cover,
            image_type=cover_type,
            total_tracks=len(tracks), 
            year_release=year_release,
            artist_id=artist.id
        )
        session.add(album)
        await session.flush()
        await add_track(session=session, track_files=tracks, album_id=album.id)
    

@router.post('/artist')
async def add_artist(session: SessionDep,
                    photo: UploadFile, 
                    name: str, 
                    bio: str | None = None, 
                    monthly_listeners: int = 120,
                    verified: bool = False
): 
    image_type = photo.content_type
    image = await photo.read()
    artist = Artist(
        photo=image, 
        image_type=image_type, 
        name=name, 
        bio=bio, 
        verified=verified,
        monthly_listeners=monthly_listeners,
    )
    session.add(artist)
    await session.commit()

@router.delete('/delete_album')
async def delete_album(session: SessionDep, name): 
    statement = select(Album).where(Album.album_name == name)
    album_obj = await session.execute(statement)
    album = album_obj.scalar_one_or_none()
    await session.delete(album)
    await session.commit() 