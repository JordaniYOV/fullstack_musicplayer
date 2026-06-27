import uuid 

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, Response
from sqlmodel import select


from app.api.deps import SessionDep
from app.models.tracks import Track, TrackHigh, TrackLow, TrackMedium

router = APIRouter(tags=['track'])

@router.get('/track/{track_id}/metadata/')
async def track_metadata(session:SessionDep, track_id: uuid.UUID):
    statement = select(Track).where(Track.id == track_id)
    track_obj = await session.execute(statement)
    track = track_obj.scalar_one_or_none()
    return track

@router.get('/track/{track_id}/stream/', response_model=None)
async def stream_track(
    session: SessionDep, 
    request: Request, 
    track_id: uuid.UUID, 
    net_quality: str 
):
    quality = net_quality.lower()
    if quality not in ['low', 'medium', 'high']:
        raise HTTPException(status_code=400, detail="Quality must be 'low', 'medium', 'high'")
    
    models = {
        "low": TrackLow, 
        "medium": TrackMedium, 
        "high": TrackHigh
    }
    
    model = models[quality]

    statement = select(model).where(model.track_id == track_id)
    track_obj = await session.execute(statement)
    track = track_obj.scalar_one_or_none()

    if not track: 
        raise HTTPException(status_code=404, detail="Track not found")
    
    audio_data = track.audio_file
    audio_size = len(audio_data)
    audio_type = track.audio_type

    range_header = request.headers.get('range')

    if not range_header:
        def full_stream(): 
            chunk_size = 65536 #64KB
            for i in range(0, audio_size, chunk_size): 
                yield audio_data[i:i + chunk_size]

        return StreamingResponse(
            full_stream(), 
            media_type=audio_type, 
            headers={ 
                "Accept-Ranges": "bytes", 
                "Content-Length": str(audio_size),
                "Content-Type": audio_type, 
            }
        )
    
    try:
        start_byte, end_byte = range_header.replace("bytes=", "").split("-")
        start_byte = int(start_byte)
        end_byte = int(end_byte) if len(end_byte) > 0 else audio_size - 1

        if start_byte >= audio_size or end_byte >= audio_size or start_byte > end_byte: 
            return Response(
                status_code=416, 
                headers={"Content_Range": f"bytes */{audio_size}"}
            )

        def partial_stream():
            chunk_size = 65536 #64KB
            current = start_byte
            while current <= end_byte: 
                chunk_end = min(current + chunk_size, end_byte + 1)
                yield audio_data[current:chunk_end]
                current = chunk_end

        return StreamingResponse(
                    partial_stream(),
                    status_code=206,
                    media_type=audio_type,
                    headers={
                        "Accept-Ranges": "bytes",
                        "Content-Range": f"bytes {start_byte}-{end_byte}/{audio_size}",
                        "Content-Type": audio_type,
                        "Content-Length": str(audio_size),
                    })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

        

# @router.get('/track/trand/')
# async def get_trand_tracks(period: str, limit: int): 
#     """
#     Get popular tracks
#     """

#     redis = await redis_client.get_client()
#     manager = TrackRedisManager(redis)

#     answer = await manager.get_popular_track(period=period, limit=limit)

#     return answer


@router.patch('/track/add_plays/')
async def add_plays(session: SessionDep, plays: int, track_id: uuid.UUID, period: str): 
    """
    Increase plays on chosen period of time by given plays
    """

    statement = select(Track).where(Track.id == track_id)
    track_obj = await session.execute(statement)
    track = track_obj.scalar_one_or_none()

    if period == "day": 
        track.daily_plays += plays
    elif period == "week": 
        track.weekly_plays += plays
    elif period == "month": 
        track.monthly_plays += plays
    else:
        return Exception("Wrong or empty period")
    
    session.add(track)
    await session.commit()


