from calendar import month
from celery import Celery
from datetime import timedelta
from core.config import settings

celery_app = Celery(
    "celery_app", 
    broker = f"redis://localhost:{settings.redis_host}/0",
    backend = f"redis://localhost:{settings.redis_hsot}/0", 
    include = ['app.tasks']
    )

celery_app.conf.update(
    task_serializer = "json", 
    accept_content = ["json"], 
    result_serializer = "json", 
    timezone = 'Europe/Moscow',
    enable_utc = True, 
    task_track_started = True, 
    task_time_limit = 30 * 60
)

celery_app.conf.beat_chedule{
    'update_daily_top': { 
        'tasks': 'tasks.update_popular_tracks.update_list',
        'schedule': timedelta(days=1),
        'args': ('day', 10)
    }, 
    'update_weely_top': {
        'tasks': 'tasks.update_popular_tracks.update_list',
        'schdeule': timedelta(days=1),
        'args': ('week', 10) 
    }, 
    'update_monthly_top': {
        'tasks': 'tasks.update_popular_tracks.update_list', 
        'schedule': timedelta(days=30), 
        'args': ('month', 10)
    }

}