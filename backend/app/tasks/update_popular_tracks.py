import asyncio
from re import S
from sqlmodel import select, asc

from app.api.deps import SessionDep
from app.celery_app import celery_app
from ..core.redis.redis import redis_client
from ..core.redis.track_manager import TrackRedisManager
from ..core.db import async_engine
from app.models.tracks import Track
from app.models.albums import Album
from sqlalchemy.ext.asyncio.session import AsyncSession

@celery_app.task()
def update_list_task(period: str, limit: int): 

    async def update_list(): 

        async with AsyncSession(async_engine) as session: 
            
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
                
                statement = select(Album).where(Album.id == track.album_id)
                album_obj = await session.execute(statement)
                album = album_obj.scalar_one_or_none()
                album_dict = await asyncio.to_thread(album.model_dump)
                
                await track_manager.add_track(track_dict, album_dict)
            
    asyncio.run(update_list())

