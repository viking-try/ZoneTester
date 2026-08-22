"""Beat-scheduled maintenance: stuck-job reconciliation, retention pruning, and daily
snapshots for trend charts. All three are idempotent and safe to re-run."""
import logging
from datetime import datetime, timedelta, timezone

from celery.exceptions import SoftTimeLimitExceeded
from psycopg.types.json import Json

from app.config import settings
from app.constants import JobState
from app.db.pool import get_conn
from app.jobs.celery_app import celery_app
from app.jobs.dispatch import TASK_NAMES

logger = logging.getLogger(__name__)


@celery_app.task(name="app.jobs.tasks_maintenance.reconcile_stuck_jobs_task", soft_time_limit=90, time_limit=120)
def reconcile_stuck_jobs_task() -> dict:
    """A job dispatched via dispatch_job() should transition queued->running almost
    immediately once a worker picks it up. If it's still 'queued' after
    stuck_job_threshold_minutes, either the send_task message never arrived (Redis blip,
    api restart between insert and send) or the worker that would have run it died first.
    Cross-checks celery's active-task inspection before re-dispatching, so a job that's
    merely running slowly (not stuck) doesn't get double-dispatched."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.stuck_job_threshold_minutes)
    with get_conn() as conn:
        stuck = conn.execute(
            "SELECT id, type, payload FROM jobs WHERE state = %s AND created_at < %s",
            (JobState.QUEUED, cutoff),
        ).fetchall()
        if not stuck:
            return {"reconciled": 0, "candidates": 0}

        active_ids = _active_task_ids()
        reconciled = 0
        for job in stuck:
            if str(job["id"]) in active_ids:
                continue
            task_name = TASK_NAMES.get(job["type"])
            if not task_name:
                logger.warning("stuck job %s has unknown type %r, skipping", job["id"], job["type"])
                continue
            celery_app.send_task(task_name, args=[job["id"], job["payload"]], task_id=str(job["id"]))
            reconciled += 1

    logger.info("stuck-job reconciliation: re-dispatched %d of %d candidates", reconciled, len(stuck))
    return {"reconciled": reconciled, "candidates": len(stuck)}


def _active_task_ids() -> set[str]:
    try:
        inspect = celery_app.control.inspect(timeout=2.0)
        active = inspect.active() or {}
    except Exception as exc:  # noqa: BLE001 - inspection is best-effort
        logger.warning("could not inspect active celery tasks: %s", exc)
        return set()
    ids: set[str] = set()
    for worker_tasks in active.values():
        for t in worker_tasks:
            if t.get("id"):
                ids.add(t["id"])
    return ids


@celery_app.task(name="app.jobs.tasks_maintenance.retention_prune_task", soft_time_limit=240, time_limit=300)
def retention_prune_task() -> dict:
    now = datetime.now(timezone.utc)
    try:
        with get_conn() as conn:
            jobs_deleted = conn.execute(
                "DELETE FROM jobs WHERE state IN ('done','error') AND created_at < %s",
                (now - timedelta(days=settings.retention_jobs_days),),
            ).rowcount
            audit_deleted = conn.execute(
                "DELETE FROM audit WHERE created_at < %s",
                (now - timedelta(days=settings.retention_audit_days),),
            ).rowcount
            snapshots_deleted = conn.execute(
                "DELETE FROM snapshots WHERE created_at < %s",
                (now - timedelta(days=settings.retention_snapshots_days),),
            ).rowcount
            # Never prune an event that hasn't been included in a sent report yet (lesson #9),
            # regardless of age — reported_at IS NULL means "still needed by the next digest".
            events_deleted = conn.execute(
                "DELETE FROM events WHERE created_at < %s AND reported_at IS NOT NULL",
                (now - timedelta(days=settings.retention_events_days),),
            ).rowcount
    except SoftTimeLimitExceeded:
        logger.error("retention_prune_task hit its soft time limit")
        raise

    result = {
        "jobs_deleted": jobs_deleted,
        "audit_deleted": audit_deleted,
        "snapshots_deleted": snapshots_deleted,
        "events_deleted": events_deleted,
    }
    logger.info("retention prune: %s", result)
    return result


_SNAPSHOT_AGGREGATE_SQL = """
    SELECT
        count(*) AS total_records,
        count(*) FILTER (WHERE scan_state = 'scanned') AS scanned_records,
        count(*) FILTER (WHERE state = 'up') AS up_count,
        count(*) FILTER (WHERE state = 'down') AS down_count,
        count(*) FILTER (WHERE pqc_supported = true) AS pqc_count,
        count(*) FILTER (WHERE weak_cipher_present = true) AS weak_cipher_count,
        count(*) FILTER (WHERE cleanup = true) AS dangling_count
    FROM records
    WHERE (hosted_zone = %(zone)s OR %(zone)s IS NULL)
"""

_GRADE_DIST_SQL = """
    SELECT grade, count(*) AS n FROM records
    WHERE (hosted_zone = %(zone)s OR %(zone)s IS NULL) AND grade IS NOT NULL
    GROUP BY grade
"""

_DNSSEC_SUMMARY_SQL = """
    SELECT dnssec_status, count(*) AS n FROM domains
    WHERE (hosted_zone = %(zone)s OR %(zone)s IS NULL)
    GROUP BY dnssec_status
"""


@celery_app.task(name="app.jobs.tasks_maintenance.daily_snapshot_task", soft_time_limit=240, time_limit=300)
def daily_snapshot_task() -> dict:
    today = datetime.now(timezone.utc).date()
    with get_conn() as conn:
        zones = [r["hosted_zone"] for r in conn.execute("SELECT DISTINCT hosted_zone FROM records").fetchall()]
        count = 0
        for zone in [None, *zones]:
            _snapshot_zone(conn, zone, today)
            count += 1
    logger.info("daily snapshot: wrote %d zone snapshots for %s", count, today)
    return {"snapshots": count, "date": today.isoformat()}


def _snapshot_zone(conn, zone: str | None, snapshot_date) -> None:
    agg = conn.execute(_SNAPSHOT_AGGREGATE_SQL, {"zone": zone}).fetchone()
    grade_rows = conn.execute(_GRADE_DIST_SQL, {"zone": zone}).fetchall()
    grade_distribution = {row["grade"]: row["n"] for row in grade_rows}
    dnssec_rows = conn.execute(_DNSSEC_SUMMARY_SQL, {"zone": zone}).fetchall()
    dnssec_summary = {row["dnssec_status"] or "unknown": row["n"] for row in dnssec_rows}

    conn.execute(
        """
        INSERT INTO snapshots (
            snapshot_date, zone, total_records, scanned_records, up_count, down_count,
            grade_distribution, pqc_count, weak_cipher_count, dangling_count, dnssec_summary
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (snapshot_date, zone) DO UPDATE SET
            total_records = EXCLUDED.total_records,
            scanned_records = EXCLUDED.scanned_records,
            up_count = EXCLUDED.up_count,
            down_count = EXCLUDED.down_count,
            grade_distribution = EXCLUDED.grade_distribution,
            pqc_count = EXCLUDED.pqc_count,
            weak_cipher_count = EXCLUDED.weak_cipher_count,
            dangling_count = EXCLUDED.dangling_count,
            dnssec_summary = EXCLUDED.dnssec_summary
        """,
        (
            snapshot_date,
            zone or "__all__",
            agg["total_records"],
            agg["scanned_records"],
            agg["up_count"],
            agg["down_count"],
            Json(grade_distribution),
            agg["pqc_count"],
            agg["weak_cipher_count"],
            agg["dangling_count"],
            Json(dnssec_summary),
        ),
    )
