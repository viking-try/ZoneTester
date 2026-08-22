"""Report tasks: check_schedules_task runs every 5 minutes (beat) and dispatches
send_report_task for any due schedule; send_report_task builds the diff digest and delivers
it. Full digest/render/SMTP logic lives in app/reporting/ (Phase 9)."""
import logging

from celery.exceptions import SoftTimeLimitExceeded

from app.constants import JobState
from app.db.pool import get_conn
from app.jobs.celery_app import celery_app
from app.jobs.dispatch import dispatch_job, finish_job, try_start_job

logger = logging.getLogger(__name__)


@celery_app.task(name="app.jobs.tasks_reports.check_schedules_task", soft_time_limit=60, time_limit=90)
def check_schedules_task() -> dict:
    from app.reporting.scheduler import due_schedules  # local import avoids a cycle at module load

    with get_conn() as conn:
        due = due_schedules(conn)
        for schedule in due:
            dispatch_job(conn, "send_report", {"schedule_id": schedule["id"]}, zone=schedule["zone"])
    return {"dispatched": len(due)}


@celery_app.task(name="app.jobs.tasks_reports.send_report_task", bind=True, soft_time_limit=90, time_limit=120)
def send_report_task(self, job_id: int, payload: dict) -> dict:
    with get_conn() as conn:
        if not try_start_job(conn, job_id):
            return {"skipped": True}
        try:
            from app.reporting.digest import build_and_send_report

            result = build_and_send_report(conn, payload["schedule_id"])
            finish_job(conn, job_id, state=JobState.DONE, result=result)
            return result
        except SoftTimeLimitExceeded:
            finish_job(conn, job_id, state=JobState.ERROR, error="soft time limit exceeded")
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("send_report_task failed for job %s", job_id)
            finish_job(conn, job_id, state=JobState.ERROR, error=str(exc))
            raise
