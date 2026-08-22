"""Ticketing tasks: create Jira/ServiceNow tickets for new dangling records over a window.
Full client implementations land in app/integrations/{jira,servicenow}_client.py (Phase 9);
this task wires the job-row lifecycle and stays a documented no-op when neither integration
is configured, rather than failing."""
import logging

from celery.exceptions import SoftTimeLimitExceeded

from app.constants import JobState
from app.db.pool import get_conn
from app.jobs.celery_app import celery_app
from app.jobs.dispatch import finish_job, try_start_job

logger = logging.getLogger(__name__)


@celery_app.task(name="app.jobs.tasks_tickets.create_tickets_task", bind=True, soft_time_limit=60, time_limit=90)
def create_tickets_task(self, job_id: int, payload: dict) -> dict:
    with get_conn() as conn:
        if not try_start_job(conn, job_id):
            return {"skipped": True}
        try:
            from app.reporting.tickets import create_tickets_for_dangling  # local import avoids a cycle at module load

            result = create_tickets_for_dangling(conn, payload)
            finish_job(conn, job_id, state=JobState.DONE, result=result)
            return result
        except SoftTimeLimitExceeded:
            finish_job(conn, job_id, state=JobState.ERROR, error="soft time limit exceeded")
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("create_tickets_task failed for job %s", job_id)
            finish_job(conn, job_id, state=JobState.ERROR, error=str(exc))
            raise
