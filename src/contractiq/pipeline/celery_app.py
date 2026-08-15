"""Celery application instance configuring task broker, results, and worker routing."""

from celery import Celery

from contractiq.config import get_settings

settings = get_settings()

celery_app = Celery(
    "contractiq",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["contractiq.pipeline.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "contractiq.pipeline.tasks.*": {"queue": "ingestion"},
    },
)
