"""
Celery configuration for background tasks
"""
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "Meridian",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Dhaka',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
)

# Celery Beat Schedule for periodic tasks
celery_app.conf.beat_schedule = {
    'update-crime-scores': {
        'task': 'app.services.crime_service.update_crime_scores',
        'schedule': settings.CRIME_SCORE_UPDATE_INTERVAL,
    },
    'cleanup-old-videos': {
        'task': 'app.services.storage_service.cleanup_old_videos',
        'schedule': 86400,  # Daily
    },
}
