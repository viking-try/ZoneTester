"""Dispatch-then-record job creation (lesson #8): the jobs row is inserted and committed
FIRST, then the celery task is sent using that row's id as the celery task_id. If send_task
itself fails (e.g. a Redis blip), a compensating write marks the job errored immediately
instead of leaving an orphaned 'queued' row nothing will ever pick up. The stuck-job
reconciler (tasks_maintenance.reconcile_stuck_jobs) is the second line of defense for jobs
that dispatched fine but whose worker crashed mid-flight or never picked them up.

Task bodies call try_start_job() first — an idempotency guard so a stray re-dispatch of an
already-running job (e.g. the reconciler racing a slow-but-alive worker) is a safe no-op."""
import logging

import psycopg
from psycopg.types.json import Json

from app.constants import JobState

logger = logging.getLogger(__name__)

TASK_NAMES: dict[str, str] = {
    "scan_record": "app.jobs.tasks_scan.scan_record_task",
    "scan_batch": "app.jobs.tasks_scan.scan_batch_task",
    "scan_domain": "app.jobs.tasks_scan.scan_domain_task",
    "send_report": "app.jobs.tasks_reports.send_report_task",
    "create_tickets": "app.jobs.tasks_tickets.create_tickets_task",
}


def dispatch_job(conn: psycopg.Connection, job_type: str, payload: dict, *, zone: str | None = None) -> int:
    from app.jobs.celery_app import celery_app  # local import: avoids a celery_app <-> dispatch import cycle

    row = conn.execute(
        "INSERT INTO jobs (type, payload, state, zone) VALUES (%s, %s, %s, %s) RETURNING id",
        (job_type, Json(payload), JobState.QUEUED, zone),
    ).fetchone()
    job_id = row["id"]

    task_name = TASK_NAMES[job_type]
    try:
        celery_app.send_task(task_name, args=[job_id, payload], task_id=str(job_id))
    except Exception as exc:  # noqa: BLE001 - compensating write must catch everything
        logger.error("failed to dispatch job %s (%s): %s", job_id, job_type, exc)
        conn.execute(
            "UPDATE jobs SET state = %s, error = %s, finished_at = now() WHERE id = %s",
            (JobState.ERROR, str(exc), job_id),
        )
    return job_id


def try_start_job(conn: psycopg.Connection, job_id: int) -> bool:
    """Returns True if this call transitioned the job queued->running (caller should proceed).
    Returns False if the job was already running/done/errored (caller should no-op)."""
    row = conn.execute(
        """
        UPDATE jobs SET state = %s, started_at = now()
        WHERE id = %s AND state = %s
        RETURNING id
        """,
        (JobState.RUNNING, job_id, JobState.QUEUED),
    ).fetchone()
    return row is not None


def finish_job(conn: psycopg.Connection, job_id: int, *, state: str, result: dict | None = None, error: str | None = None) -> None:
    conn.execute(
        """
        UPDATE jobs SET state = %s, result = %s, error = %s, finished_at = now()
        WHERE id = %s
        """,
        (state, Json(result) if result is not None else None, error, job_id),
    )
