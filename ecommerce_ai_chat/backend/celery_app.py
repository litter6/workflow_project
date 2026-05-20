from celery import Celery

celery_app = Celery(
    "video_pipeline",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    worker_concurrency=2,
    broker_connection_retry_on_startup=True,
    include=["tasks"],
)
