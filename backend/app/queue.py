from celery import Celery

from app import logging_config  # Configure the same colored app logs in workers.
from app.config import settings

celery_app = Celery("document_chatbot", broker=settings.redis_url, backend=settings.redis_url, include=["app.tasks"])
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    worker_hijack_root_logger=False,
    task_routes={"app.tasks.ingest_document": {"queue": "ingestion"}},
)
