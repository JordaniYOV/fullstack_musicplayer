import uuid
from pydub import AudioSegment

from fastapi import UploadFile
from sqlmodel import select
from sqlalchemy.ext.asyncio.session import AsyncSession

import io
import asyncio

from app.models import Track, TrackHigh, TrackLow, TrackMedium, Message
from ..core.redis.redis import redis_client
from ..core.redis.cache import CacheService


async def add_track(
        session: AsyncSession, 
        track_files: list[UploadFile], 
        album_id: uuid.UUID, 
        album_existed: bool, 
        album_name: str
): 
    track_existed = ""

    for file in track_files: 
        track_name = file.filename
       
        statament = select(Track).where(Track.track_name == track_name, Track.album_id == album_id)
        track_temp_obj = await session.execute(statament)
        track_temp = track_temp_obj.scalar_one_or_none()

        if track_temp != None: 
            track_existed += f"Track {track_name} already exist. "
        else: 
            track_type = file.content_type
            content = await file.read()
            audio = AudioSegment.from_file(io.BytesIO(content))
            duration = audio.duration_seconds

            track = Track(
                track_name=track_name, 
                duration_sec=duration, 
                album_id=album_id
            )
            session.add(track)
            await session.flush()

            track_h = await asyncio.to_thread(comprese_audio, audio, "320k", duration)
            track_m = await asyncio.to_thread(comprese_audio, audio, "192k", duration)
            track_l = await asyncio.to_thread(comprese_audio, audio, "64k", duration)

            track_high = TrackHigh(
                audio_file=track_h["audio_file"], 
                audio_size=track_h["audio_size"], 
                audio_type=track_type, 
                track_id=track.id
                )
            track_medium = TrackMedium(
                audio_file=track_m["audio_file"],
                audio_size=track_m["audio_size"], 
                audio_type=track_type, 
                track_id=track.id
                )
            track_low = TrackLow(
                audio_file=track_l["audio_file"],
                audio_size=track_l["audio_size"], 
                audio_type=track_type, 
                track_id=track.id
                )

            session.add(track_high)
            session.add(track_medium)
            session.add(track_low)
    

    redis = await redis_client.get_client()
    cache_service = CacheService(redis)
    answer = await cache_service.set(key='1', value='jhon')  
    await session.commit()
    data = await cache_service.get(key='2')
    data1 = await cache_service.get(key='1')
    await redis_client.close_pool()  
    return data, data1


    # if album_existed == True:
    #     return Message(message=f"Album {album_name} already exists, tracks added to that album. {track_existed}")
    # else: 
    #     return Message(message=f"Album {album_name} was created, tracks added to that album. {track_existed}")


# async def add_track_quality(session: AsyncSession,
#         content: bytes, 
#         track_type: str, 
#         track_size: int, 
#         track_id: uuid.UUID,
#         bitrate: int 
# ):
#     if bitrate <= 96: 
#         track_low = TrackLow(
#             audio_file=content,
#             audio_type=track_type, 
#             audio_size=track_size, 
#             track_id=track_id, 
#         )
#         session.add(track_low)
#     elif bitrate <= 160:
#         track_medium = TrackMedium(
#             audio_file=content, 
#             audio_type=track_type, 
#             audio_size=track_size, 
#             track_id=track_id
#         )
#         session.add(track_medium)
#     elif bitrate >= 320 or bitrate <= 320: 
#         track_high = TrackHigh(
#             audio_file=content, 
#             audio_type=track_type, 
#             audio_size=track_size, 
#             track_id=track_id
#         )
#         session.add(track_high)

def comprese_audio(audio, target_bitrate: str, duration: int) -> dict: 
    """
    Decrease track bitrate

    audio = track get by pydub
    target_bitrate = to what bitrate wanna compose audio 

    return bytes
    """

    buffer = io.BytesIO()

    audio.export(buffer, format="mp3", bitrate=target_bitrate)
    compresed_audio = buffer.getvalue()
    buffer.close()
    track_size = len(compresed_audio) / (1024 * 1024)
    
    # bitrate = (track_size / 8) / duration)

    track_data = {
        "audio_file": compresed_audio, 
        "audio_size": track_size
    }

    return track_data