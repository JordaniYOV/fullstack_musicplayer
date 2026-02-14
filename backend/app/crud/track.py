
import uuid 
import io
import asyncio

from amqp import Message
from fastapi import UploadFile
from sqlmodel import select
from sqlalchemy.ext.asyncio.session import AsyncSession
from pydub import AudioSegment

from app.models import Track, TrackHigh, TrackLow, TrackMedium, Message
from .utils import comprese_audio

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

        statement = select(Track).where(Track.track_name == track_name)
        track_temp_obj = await session.execute(statement)
        track_temp = track_temp_obj.scalar_one_or_none()

        if track_temp != None: 
            track_existed += f"Track {track_name} already exist."
        else: 
            track_type = file.content_type
            content = await file.read()
            audio = AudioSegment.from_file(io.BytesIO(content))
            duration = audio.duration_seconds

            track = Track(
                track_name = track_name, 
                duration_sec = duration, 
                album_id = album_id,
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
                audio_size=track_l["audio_szie"], 
                audio_type=track_type, 
                track_id=track.id
            )

            session.add(track_high)
            session.add(track_medium)
            session.add(track_low)

    await session.commit()

    if album_existed == True: 
        return Message(message=f"Album {album_name} already exists, tracks added to that album. {track_existed}")
    return Message(message=f"Album {album_name} was created, tracks added to that album. {track_existed}")