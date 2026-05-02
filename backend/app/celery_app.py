
import platform
from celery import Celery
from celery.schedules import crontab
from datetime import timedelta
from .core.config import settings

import asyncio

celery_app = Celery(
    "celery_app", 
    broker = f"redis://{settings.redis_host}:{settings.redis_port}/0",
    backend = f"redis://{settings.redis_host}:{settings.redis_port}/0", 
    imports = ['app.tasks.update_popular_tracks']
    )

if platform.system() == 'windows':
    celery_app.conf.worker_pool = 'solo'
else: 
    celery_app.conf.worker_pool = 'prefork' 


celery_app.conf.update(
    task_serializer = "json", 
    accept_content = ["json"], 
    result_serializer = "json", 
    timezone = 'UTC',
    enable_utc = True, 
    task_track_started = True, 
    task_time_limit = 30 * 60, 

    task_default_queue="default", 
    task_routes={
        "app.tasks.update_popular_tracks.aggregate_*": {"queue": "aggregation"},
    },
    worker_prefetch_multiplier=1, 
    worker_max_tasks_per_child=1000,
)

celery_app.conf.beat_schedule = {
    'update_daily_top': { 
        'task': 'tasks.update_popular_tracks.aggregate_daily_task',
        'schedule': crontab(hour=3, minute=0),
        'options': {'queue': 'aggregation'},
    }, 
    'update_weely_top': {
        'task': 'tasks.update_popular_tracks.aggregate_weekly_task',
        'schedule': crontab(day_of_week=1, hour=4, minute=0),
        'options': {'queue': 'aggregation'}
    }, 
    'update_monthly_top': {
        'task': 'tasks.update_popular_tracks.aggregate_monthly_task', 
        'schedule': crontab(day_of_month=1, hour=5, minute=0), 
        'options': {'queue': 'aggregation'}
    }, 
    'cleanup_old_play_events': {
        'task': 'tasks.update_popular_tracks.clean_up_task', 
        'schedule': crontab(hour=3, minute=0), 
        'options': {'queue': 'aggregation'}
    }

}