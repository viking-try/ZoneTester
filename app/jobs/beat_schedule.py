"""Celery beat periodic schedule. Intervals are env-tunable (lesson #9) via settings rather
than hardcoded, so retention windows and reconciliation cadence can be adjusted per
deployment without a code change."""
from celery.schedules import crontab

from app.config import settings

SCHEDULE = {
    "reconcile-stuck-jobs": {
        "task": "app.jobs.tasks_maintenance.reconcile_stuck_jobs_task",
        "schedule": settings.reconcile_interval_minutes * 60.0,
    },
    "retention-prune": {
        "task": "app.jobs.tasks_maintenance.retention_prune_task",
        "schedule": settings.retention_prune_interval_minutes * 60.0,
    },
    "daily-snapshot": {
        "task": "app.jobs.tasks_maintenance.daily_snapshot_task",
        "schedule": crontab(hour=1, minute=0),
    },
    "check-report-schedules": {
        "task": "app.jobs.tasks_reports.check_schedules_task",
        "schedule": 300.0,
    },
}
