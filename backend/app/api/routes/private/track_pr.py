
from sqlmodel import select
from typing import Annotated

from fastapi import APIRouter, HTTPException, UploadFile, File
from ....core.redis.redis import redis_client

from app.api.deps import SessionDep
from app.models import Album, Artist, AlbumsCover
from app.crud.track import add_track

router = APIRouter(tags=['tracks_private'])

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

        cover = AlbumsCover( 
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
    
@router.post("/redis/delete")
async def clear_redis():
    try: 
        redis = await redis_client.get_client()
        await redis.flushall()
        return {f"Cache cleraed successfully {await redis.dbsize()}"}
    except Exception as e: 
        raise HTTPException(status_code=500, detail=str(e))
    
