import logging

from datetime import date, timedelta
from typing import Optional
from sqlmodel import Session
from celery.exceptions import MaxRetriesExceededError

from app.celery_app import celery_app
from app.core.services.aggregation import AggregationService
from app.core.services.charts import ChartServiceSync
from app.core.redis.redis import sync_redis_client
from app.core.redis.cache_chart import ChartCacheServiceSync
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

            agg_service = AggregationService(session)
            tracks_count = agg_service.aggregate_daily(target_date)
            
            actual_date = target_date or (date.today() - timedelta(days=1))
            if actual_date == date.today() - timedelta(days=1):
                cleaned = agg_service.cleanup_old_events(days=30)
                logger.info(f"cleaned {cleaned} old events")
            
            logger.info(f"daily aggregation completed: {tracks_count} tracks")

            chart_service = ChartServiceSync(session)
            pop_tracks = chart_service.get_daily(actual_date)

            redis = sync_redis_client
            cache_service = ChartCacheServiceSync(redis)
            cached = cache_service.save_daily_chart(actual_date, pop_tracks["entries"], pop_tracks["total_plays"])

            if cached: 
                return {
                    "status": "success", 
                    "date": actual_date.isoformat(), 
                    "tracks_processed": tracks_count, 
                    "task_id": self.request.id,
                    "cached": cached
                }

    except Exception as exc: 
        logger.exception("Daily aggregation failed")
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError: 
            logger.critical(f"Daily aggregation failed after 3 retries: {exc}")

@celery_app.task(bind=True, max_retries=3, default_retry_delay=300, queue="aggregation")
def aggregate_weekly_task(self, target_week_str: Optional[str] = None): 
    """
    Aggregate weekly chart
    """

    try: 

        target_week: Optional[str] = target_week_str

        logger.info(f"Starting Aggregation weekly aggregation for {target_week or 'last_week'}")

        with Session(sync_engine) as session:
            agg_service = AggregationService(session)
            count = agg_service.aggregate_weekly(target_week)

            chart_service = ChartServiceSync(session)
            resolved_week = target_week or date.today().strftime("%Y-W%W")
            pop_tracks = chart_service.get_weekly(target_week)

            redis = sync_redis_client
            cache_service = ChartCacheServiceSync(redis)
            cached = cache_service.save_weekly_chart(resolved_week, pop_tracks["entries"], pop_tracks["total_plays"])

            if cached:
                return {
                    "status": "success", 
                    "week": target_week, 
                    "tracks_processed": count,
                    "cached": cached
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
        target_month: Optional[str] = target_month_str

        logger.info(f"Starting monthly aggregation for {target_month or 'last_month'}")

        with Session(sync_engine) as session: 
            agg_service = AggregationService(session)
            count = agg_service.aggregate_monthly(target_month)

            chart_service = ChartServiceSync(session)
            pop_tracks = chart_service.get_monthly(target_month)

            redis = sync_redis_client
            cache_service = ChartCacheServiceSync(redis)
            cached = cache_service.save_monthly_chart(target_month, pop_tracks["entries"], pop_tracks["total_plays"])

            if cached:
                return {
                    "status": "success", 
                    "month": target_month, 
                    "track_processed": count,
                    "cached": cached
                }
        
    except Exception as exc: 
        logger.exception("Monthly aggregation failed")
        raise self.retry(exc=exc)
    
@celery_app.task(queue="default")
def clean_up_task(days: int = 30):
    with Session(sync_engine) as session: 
        agg_service = AggregationService(session)
        cleaned = agg_service.cleanup_old_events(days)
        return {"cleaned": cleaned, "days": days}