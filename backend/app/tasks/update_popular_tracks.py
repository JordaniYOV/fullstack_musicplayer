import asyncio
from sqlmodel import select, asc

from app.api.deps import SessionDep
from app.celery_app import celery_app
from ..core.redis import redis_client
from ..core.redis.track_manager import TrackRedisManager
from app.models import Track
from sqlalchemy.ext.asyncio.session import AsyncSession

@celery_app.task()
async def update_list(session: SessionDep, period: str, limit: int): 
    redis = await redis_client.get_client()
    track_manager = TrackRedisManager(redis)

    if period == 'day': 
        statement = select(Track).order_by(asc(Track.daily_plays)).limit(limit)
    elif period == 'week':
        statement = select(Track).order_by(asc(Track.weekly_plays)).limit(limit)
    elif period == 'month': 
        statement = select(Track).order_by(asc(Track.monthly_plays)).limit(limit)

    track_obj = await session.execute(statement)

    tracks = track_obj.scalars().all()

    for track in tracks:
        track_dict = await asyncio.to_thread(track.model_dump)
        await track_manager.add_track(track_dict)
