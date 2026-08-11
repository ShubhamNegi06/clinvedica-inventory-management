"""
Celery application instance.

Started separately from the FastAPI process:
    celery -A app.core.celery_app worker --loglevel=info

Broker and result backend both point at Redis by default (see
Settings.CELERY_BROKER_URL_RESOLVED / CELERY_RESULT_BACKEND_RESOLVED —
they fall back to REDIS_URL if not set separately). Task modules are
registered via `include=` below rather than relying on autodiscovery,
since this isn't a Django-style app registry — explicit is clearer here.
"""
from celery import Celery
from celery.signals import setup_logging

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "specimen_inventory",
    broker=settings.CELERY_BROKER_URL_RESOLVED,
    backend=settings.CELERY_RESULT_BACKEND_RESOLVED,
    include=[
        "app.tasks.email_tasks",
        "app.tasks.export_tasks",
        "app.tasks.bulk_ingest_tasks",
        "app.tasks.report_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Result TTL: task results (including export download URLs) expire
    # from Redis after this long — matches roughly how long an R2 signed
    # URL embedded in the result would still be valid for anyway.
    result_expires=3600,
    # A worker takes one task at a time and doesn't hold many in memory
    # ahead of time — better for occasionally-large export/import jobs
    # than Celery's default prefetch-many behavior.
    worker_prefetch_multiplier=1,
    # Hard ceiling so a stuck task (e.g. a hung SMTP connection or R2
    # call) can't occupy a worker forever.
    task_time_limit=600,       # SIGKILL after 10 minutes
    task_soft_time_limit=540,  # SIGTERM (catchable) after 9 minutes
    task_acks_late=True,       # re-queue if a worker dies mid-task
    task_reject_on_worker_lost=True,
)


@setup_logging.connect
def _configure_celery_logging(*args, **kwargs):
    """Let Celery use the same logging config as the rest of the app
    instead of installing its own separate handlers."""
    import logging

    logging.basicConfig(level=logging.INFO)
