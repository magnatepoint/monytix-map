from celery import Celery
from config import settings

celery_app = Celery(
    "monytix",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.pdf_worker",
        "app.workers.csv_worker",
        "app.workers.ml_worker"
    ]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    broker_connection_retry_on_startup=True,  # Retry on startup
    broker_connection_retry=True,  # Enable connection retry
    broker_connection_max_retries=10,  # Max retries
)

