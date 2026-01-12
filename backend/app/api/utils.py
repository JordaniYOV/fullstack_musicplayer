from pydub import AudioSegment

from fastapi import UploadFile
from sqlmodel import Session
from sqlalchemy.ext.asyncio.session import AsyncSession

import io

from app.models import Track

async def add_track(session: AsyncSession, track_files: list[UploadFile],album_id): 
    for file in track_files: 
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
            album_id=album_id
        )
        session.add(track)
        print(track.track_name)
    await session.commit()
