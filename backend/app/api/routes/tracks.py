from email.mime import audio
from sqlmodel import select
from typing import Annotated

from fastapi import APIRouter, UploadFile, File

from pydub import AudioSegment
import io

from app.api.deps import SessionDep
from app.models import Album, Track, Artist

router = APIRouter()

@router.post('/track')
async def upload_tracks(session: SessionDep, 
                files: Annotated[list[UploadFile], File(description="To add whole album or sibgle track")],
                artist_name: str, 
                album_name: str,
                album_cover: UploadFile = None,
                year_release:  int = None
):

    statement = select(Album).where(Album.album_name == album_name)
    album = session.exec(statement).first()
    if album is not None: 
        album_id = album.id
    else:
        cover = await album_cover.read()
        cover_type = album_cover.content_type
        statement = select(Artist)
        artist = session.exec(statement).first()
        album = Album(
            album_name=album_name, 
            album_cover=cover,
            image_type=cover_type,
            total_tracks=len(files), 
            year_release=year_release,
            artist_id=artist.id
        )
        session.add(album)
        session.flush()

    for file in files: 
        track_name = file.filename
        track_size = file.size
        track_type =file.content_type
        content = await file.read()
        audio = AudioSegment.from_file(io.BytesIO(content))
        duration = audio.duration_seconds
        
        track = Track(
            track_name=track_name, 
            duration_sec=duration, 
            audio_file=content, 
            audio_type=track_type, 
            audio_size=track_size, 
            album_id=album.id
        )
        session.add(track)
    session.commit()

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
    session.commit()

@router.delete('/delete_album')
def delete_album(session: SessionDep, name): 
    statement = select(Album).where(Album.album_name == name)
    album = session.exec(statement).first()
    session.delete(album)
    session.commit() 