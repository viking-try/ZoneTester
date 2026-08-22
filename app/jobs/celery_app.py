"""Celery application. Serializer is pinned to JSON everywhere (never pickle — an untrusted
or compromised broker message must not be able to deserialize arbitrary objects). Queues are
split by workload (scans/reports/tickets/maintenance) so a flood of scan jobs can't starve
report sends or the retention/reconciliation beat tasks; worker containers subscribe to all
of them via $CELERY_QUEUES but a deployment could split workers per queue if needed."""
from celery import Celery

from app.config import settings

celery_app = Celery("zoneguard", broker=settings.celery_broker_url, backend=settings.celery_result_backend)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=60 * 60 * 24,
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    task_routes={
        "app.jobs.tasks_scan.*": {"queue": "scans"},
        "app.jobs.tasks_reports.*": {"queue": "reports"},
        "app.jobs.tasks_tickets.*": {"queue": "tickets"},
        "app.jobs.tasks_maintenance.*": {"queue": "maintenance"},
    },
)

from app.jobs import beat_schedule  # noqa: E402

celery_app.conf.beat_schedule = beat_schedule.SCHEDULE

# Import task modules so their @celery_app.task decorators register — required both for the
# worker (which loads tasks via this module) and for beat (which needs the task names to exist).
from app.jobs import tasks_maintenance, tasks_reports, tasks_scan, tasks_tickets  # noqa: E402, F401
