import logging

from datetime import date, timedelta
from typing import Optional
from sqlmodel import Session
from celery.exceptions import MaxRetriesExceededError

from app.celery_app import celery_app
from app.core.services.aggregation import AggregationService
from app.core.db import sync_engine

# @celery_app.task()
# def update_list_task(period: str, limit: int): 

    # async def update_list(): 

    #     async with AsyncSession(async_engine) as session: 
            
    #         redis = await redis_client.get_client()
    #         track_manager = TrackRedisManager(redis)

    #         if period == 'day': 
    #             statement = select(Track).order_by(asc(Track.daily_plays)).limit(limit)
    #         elif period == 'week':
    #             statement = select(Track).order_by(asc(Track.weekly_plays)).limit(limit)
    #         elif period == 'month': 
    #             statement = select(Track).order_by(asc(Track.monthly_plays)).limit(limit)

    #         track_obj = await session.execute(statement)
    #         tracks = track_obj.scalars().all()
            
    #         for track in tracks:
    #             track_dict = await asyncio.to_thread(track.model_dump)
                
    #             statement = select(Album).where(Album.id == track.album_id)
    #             album_obj = await session.execute(statement)
    #             album = album_obj.scalar_one_or_none()
    #             album_dict = await asyncio.to_thread(album.model_dump)
                
    #             await track_manager.add_track(track_dict, album_dict)
            
    # asyncio.run(update_list())

logger = logging.getLogger(__name__)

@celery_app.task(
        bind=True,
        max_retries=3, 
        default_retry_delay=60, 
        retry_backoff=True, 
        retry_backoff_max=600, 
        retry_jitter=True, 
        autoretry_for=(Exception,),
        queue='aggregation',)
def aggregate_daily_task(self, 
                         target_date_str: Optional[str] = None): 
    """
    Aggregation of daily chart
    target_date_str: format '2024-03-09'
    None = yesterday
    """

    try: 
        if target_date_str: 
            target_date = date.fromisoformat(target_date_str)
        else: 
            target_date = None

        logger.info(f"Starting daily aggregation for {target_date or 'yesterday'}")

        with Session(sync_engine) as session: 

            service = AggregationService(session)
        
            tracks_count = service.aggregate_daily(target_date)
            
            # actual_date = target_date or (date.today() - timedelta(days=1))
            # if actual_date == date.today() - timedelta(days=1):
            #     cleaned = service.cleanup_old_events(days=30)
            #     logger.info(f"cleaned {cleaned} old events")
            
            logger.info(f"daily aggregation completed: {tracks_count} tracks")

            return {
                "status": "success", 
                "date": actual_date.isoformat(), 
                "tracks_processed": tracks_count, 
                "task_id": self.request.id
            }

    except Exception as exc: 
        logger.exception("Daily aggregation failed")
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError: 
            logger.critical(f"Daily aggregation failed after 3 retries: {exc}")

@celery_app.task(bind=True)
def aggregate_weekly_task(self, target_week_str: Optional[str] = None): 
    """
    Aggregate weekly chart
    """


    try: 
        if target_week_str: 
            target_week = date.fromisoformat(target_week_str)
        else: 
            target_week = date.today()

        logger.info(f"Starting Aggregation weekly aggregation for {target_week or 'last_week'}")

        with Session(sync_engine) as session:
            service = AggregationService(session)
            count = service.aggregate_weekly(target_week)

            return {
                "status": "success", 
                "week": target_week, 
                "tracks_processed": count,
            }
        
    except Exception as exc: 
        logger.exception("Weekly aggrefation failed")
        raise self.retry(exc=exc)
    
@celery_app.task(
    bind=True, 
    max_retries=3, 
    default_retry_delay=300, 
    queue='aggregation'
)
def aggregate_monthly_task(self, target_month_str: Optional[str] = None): 
    """
    aggregate monthly top
    """

    
    try:
        if target_month_str:
            target_month = date.fromisoformat(target_month_str)
        else:
            target_month = date.today()

        logger.info(f"Starting monthly aggregation for {target_month or 'last_month'}")

        with Session(sync_engine) as session: 
            service = AggregationService(session)
            count = service.aggregate_monthly(target_month)

            return {
                "status": "success", 
                "month": target_month, 
                "track_processed": count,
            }
        
    except Exception as exc: 
        logger.exception("Monthly aggregation failed")
        raise self.retry(exc=exc)
    
@celery_app.task(queue="default")
def clean_up_task(days: int = 30):
    with Session(sync_engine) as session: 
        service = AggregationService(session)
        cleaned = service.cleanup_old_events(days)
        return {"cleaned": cleaned, "days": days}