"""
Celery tasks for background price polling.

Beat schedule (set in docker-compose via CELERY_BEAT_SCHEDULE):
  poll_all_routes — runs every 6 hours
  retrain_model  — runs every 24 hours
"""

import logging
from datetime import datetime, timedelta
from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

celery_app = Celery(
    "flight_tracker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.price_poll"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "poll-all-routes-6h": {
            "task": "app.tasks.price_poll.poll_all_routes",
            "schedule": settings.poll_interval_seconds,
        },
        "retrain-model-daily": {
            "task": "app.tasks.price_poll.retrain_model",
            "schedule": crontab(hour=3, minute=0),  # 3 AM UTC
        },
    },
)
