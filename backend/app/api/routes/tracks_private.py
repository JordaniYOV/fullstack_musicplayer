import uuid 

from pydantic import BaseModel
from sqlmodel import select
from typing import Annotated

from fastapi import APIRouter, HTTPException, UploadFile, File, Response
from ...core.redis.redis import redis_client

from app.api.deps import SessionDep
from app.models import Album, Artist,  Message, Track, Albums_cover
from app.crud.track import add_track

router = APIRouter(tags=['admin'])

@router.post('/add/album-tracks')
async def upload_tracks(
    session: SessionDep, 
    tracks: Annotated[list[UploadFile], File(description="To add whole album or single track")],
    artist_name: str, 
    album_name: str,
    album_cover: UploadFile | None = None,
    year_release:  int = None
):

    statement = select(Album).where(Album.album_name == album_name)
    album_obj = await session.execute(statement)
    album = album_obj.scalar_one_or_none()

    if album != None: 
        answer = await add_track(session=session, track_files=tracks, album_id=album.id, album_existed=True, album_name=album.album_name, artist=artist_name)
        return answer
    else:
        cover = await album_cover.read()
        cover_type = album_cover.content_type
        artist_obj = await session.execute(select(Artist).where(Artist.name == artist_name))
        artist = artist_obj.scalar_one_or_none()

        cover = Albums_cover( 
            album_cover=cover, 
            cover_type=cover_type
        )

        session.add(cover)
        await session.flush()

        album = Album(
            album_name=album_name, 
            artist_name=artist_name,
            total_tracks=len(tracks), 
            year_release=year_release,
            artist_id=artist.id, 
            cover_id=cover.id
        )

        session.add(album)
        await session.flush()

        answer = await add_track(session=session, track_files=tracks, album_id=album.id, album_existed=False, album_name=album.album_name, artist=artist_name)
        return answer
    
@router.post('/add/artist')
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
async def get_album_cover(session: SessionDep, cover_id: uuid.UUID):
    """
    Recieve album cover with cover_id
    """
    statement = select(Albums_cover).where(Albums_cover.id == cover_id)
    cover_obj = await session.execute(statement)
    cover = cover_obj.scalar_one_or_none()

    return Response(
        content=cover.album_cover, 
        media_type="image/png"
    )
    

@router.post("/redis/delete")
async def clear_redis():
    try: 
        redis = await redis_client.get_client()
        await redis.flushall()
        return {f"Cache cleraed successfully {await redis.dbsize()}"}
    except Exception as e: 
        raise HTTPException(status_code=500, detail=str(e))
    
