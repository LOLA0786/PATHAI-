"""Celery App - Async inference queue

Self-Explanatory: Celery for background AI tasks.
Why: Async for realtime/batch; scale to multi-GPU.
How: Run worker: celery -A src.ai_app_store.celery_app worker --loglevel=info
Broker: Redis (local demo).
"""
from celery import Celery
import structlog

app = Celery('pathai_ai',
             broker='redis://localhost:6379/0',
             backend='redis://localhost:6379/0',
             include=['src.ai_app_store.tasks'])

logger = structlog.get_logger()

# Config for tasks
app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='Asia/Kolkata',  # Mumbai time
    enable_utc=False,
)
