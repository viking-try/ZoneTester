"""Scan tasks: one record, one batch (all scannable records in a batch/zone), or one domain.
Time limits are set generously above the slowest legitimate scan (lesson #7) so a genuinely
hung scan can't pin a worker forever — on a soft-limit hit the job row is finalized as errored
before the exception propagates. Every task body starts with try_start_job() for idempotent
pickup (lesson #8): a stray re-dispatch of an already-running job is a safe no-op."""
import logging
from datetime import datetime, timedelta, timezone

from celery.exceptions import SoftTimeLimitExceeded
from psycopg.types.json import Json

from app.cleanup.reconciliation import reconcile_zone
from app.cleanup.validation_records import is_validation_record
from app.config import settings
from app.constants import JobState, RecordState, ScanScope, ScanState
from app.db.pool import get_conn
from app.jobs.celery_app import celery_app
from app.jobs.dispatch import dispatch_job, finish_job, try_start_job
from app.jobs.events import grade_regressed, record_event
from app.scanning.flap_damping import apply_flap_damping
from app.scanning.pipeline import ScanResult, scan_host

logger = logging.getLogger(__name__)

_CERT_EXPIRY_WARNING_DAYS = 30


@celery_app.task(
    name="app.jobs.tasks_scan.scan_record_task",
    bind=True,
    soft_time_limit=settings.scan_record_soft_time_limit_seconds,
    time_limit=settings.scan_record_hard_time_limit_seconds,
)
def scan_record_task(self, job_id: int, payload: dict) -> dict:
    with get_conn() as conn:
        if not try_start_job(conn, job_id):
            return {"skipped": True, "reason": "job not in queued state"}
        try:
            result = _scan_and_persist_record(conn, payload["record_id"])
            finish_job(conn, job_id, state=JobState.DONE, result=result)
            return result
        except SoftTimeLimitExceeded:
            finish_job(conn, job_id, state=JobState.ERROR, error="soft time limit exceeded")
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("scan_record_task failed for job %s", job_id)
            finish_job(conn, job_id, state=JobState.ERROR, error=str(exc))
            raise


@celery_app.task(
    name="app.jobs.tasks_scan.scan_batch_task",
    bind=True,
    soft_time_limit=settings.scan_batch_soft_time_limit_seconds,
    time_limit=settings.scan_batch_hard_time_limit_seconds,
)
def scan_batch_task(self, job_id: int, payload: dict) -> dict:
    """payload: {scope: all|down_only|unscanned_only|tls12_only, zone: str|None,
    batch_id: int|None}. Fans out one scan_record job per matching record rather than
    scanning inline, so the work is parallelized across all worker pods instead of pinning
    this one task/worker for the whole batch."""
    with get_conn() as conn:
        if not try_start_job(conn, job_id):
            return {"skipped": True}
        try:
            record_ids = _select_scan_targets(conn, payload)
            for record_id in record_ids:
                dispatch_job(conn, "scan_record", {"record_id": record_id}, zone=payload.get("zone"))
            result = {"dispatched": len(record_ids)}
            finish_job(conn, job_id, state=JobState.DONE, result=result)
            return result
        except SoftTimeLimitExceeded:
            finish_job(conn, job_id, state=JobState.ERROR, error="soft time limit exceeded")
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("scan_batch_task failed for job %s", job_id)
            finish_job(conn, job_id, state=JobState.ERROR, error=str(exc))
            raise


@celery_app.task(
    name="app.jobs.tasks_scan.scan_domain_task",
    bind=True,
    soft_time_limit=settings.scan_batch_soft_time_limit_seconds,
    time_limit=settings.scan_batch_hard_time_limit_seconds,
)
def scan_domain_task(self, job_id: int, payload: dict) -> dict:
    with get_conn() as conn:
        if not try_start_job(conn, job_id):
            return {"skipped": True}
        try:
            domain_id = payload["domain_id"]
            record_ids = [
                r["id"]
                for r in conn.execute(
                    "SELECT id FROM records WHERE domain_id = %s AND scannable = true", (domain_id,)
                ).fetchall()
            ]
            for record_id in record_ids:
                dispatch_job(conn, "scan_record", {"record_id": record_id})
            result = {"dispatched": len(record_ids)}
            finish_job(conn, job_id, state=JobState.DONE, result=result)
            return result
        except Exception as exc:  # noqa: BLE001
            logger.exception("scan_domain_task failed for job %s", job_id)
            finish_job(conn, job_id, state=JobState.ERROR, error=str(exc))
            raise


def _select_scan_targets(conn, payload: dict) -> list[int]:
    scope = payload.get("scope", ScanScope.ALL)
    zone = payload.get("zone")
    batch_id = payload.get("batch_id")

    where = ["scannable = true"]
    params: dict = {}
    if zone:
        where.append("hosted_zone = %(zone)s")
        params["zone"] = zone
    if batch_id:
        where.append("batch_id = %(batch_id)s")
        params["batch_id"] = batch_id
    if scope == ScanScope.DOWN_ONLY:
        where.append("state = 'down'")
    elif scope == ScanScope.UNSCANNED_ONLY:
        where.append("scan_state = 'pending'")
    elif scope == ScanScope.TLS12_ONLY:
        where.append("protocol = 'TLSv1.2'")

    sql = f"SELECT id FROM records WHERE {' AND '.join(where)}"  # noqa: S608 - all fragments are static/allowlisted, no user string interpolated  # nosec B608
    rows = conn.execute(sql, params).fetchall()
    return [r["id"] for r in rows]


def _scan_and_persist_record(conn, record_id: int) -> dict:
    record = conn.execute(
        """
        SELECT id, domain_id, name, rtype, value, hosted_zone, state, consecutive_failures,
               pqc_supported, weak_cipher_present, grade, cert_expires_at
        FROM records WHERE id = %s
        """,
        (record_id,),
    ).fetchone()
    if record is None:
        return {"record_id": record_id, "error": "record not found"}

    if is_validation_record(record["rtype"], record["value"]):
        _persist_validation_record(conn, record)
        return {"record_id": record_id, "state": RecordState.VALIDATION}

    scan_result = scan_host(record["name"], 443)
    damped = apply_flap_damping(
        previous_state=record["state"],
        previous_consecutive_failures=record["consecutive_failures"] or 0,
        result=scan_result,
    )

    if damped.use_fresh_result:
        _persist_full_result(conn, record, scan_result, damped)
    else:
        _persist_damped_soft_failure(conn, record, damped)

    _emit_scan_events(conn, record, scan_result, damped)

    if record["hosted_zone"]:
        reconcile_zone(conn, record["hosted_zone"])

    return {
        "record_id": record_id,
        "up": scan_result.up,
        "state": RecordState.UP if damped.persist_as_up else RecordState.DOWN,
        "grade": scan_result.grade if damped.use_fresh_result else record["grade"],
    }


def _persist_validation_record(conn, record: dict) -> None:
    conn.execute(
        """
        UPDATE records
        SET state = %s, scannable = false, scan_state = %s, tls_grade = NULL, grade = NULL,
            grade_score = NULL, last_scanned = now(), updated_at = now()
        WHERE id = %s
        """,
        (RecordState.VALIDATION, ScanState.SCANNED, record["id"]),
    )


def _persist_full_result(conn, record: dict, r: ScanResult, damped) -> None:
    state = RecordState.UP if damped.persist_as_up else RecordState.DOWN
    conn.execute(
        """
        UPDATE records SET
            state = %s, down_reason = %s, scan_state = %s,
            protocol = %s, protocols_supported = %s, negotiated_cipher = %s, forward_secrecy = %s,
            pqc_supported = %s, weak_cipher_present = %s, vuln_flags = %s,
            cert_json = %s, cert_expires_at = %s,
            headers_json = %s, server_header = %s, x_powered_by = %s,
            handshake_trust_failed = %s, tls_grade = %s, tls_score = %s, header_grade = %s,
            grade = %s, grade_score = %s,
            consecutive_failures = %s, last_scanned = now(), updated_at = now()
        WHERE id = %s
        """,
        (
            state,
            damped.down_reason,
            ScanState.SCANNED,
            r.protocol,
            Json(r.protocols_supported),
            r.negotiated_cipher,
            r.forward_secrecy,
            r.pqc_supported,
            r.weak_cipher_present,
            Json(r.vuln_flags),
            Json(r.cert) if r.cert else None,
            r.cert_expires_at,
            Json(r.headers),
            r.server_header,
            r.x_powered_by,
            r.handshake_trust_failed,
            r.tls_grade,
            r.tls_score,
            r.header_grade_score,
            r.grade,
            r.grade_score,
            damped.consecutive_failures,
            record["id"],
        ),
    )


def _persist_damped_soft_failure(conn, record: dict, damped) -> None:
    conn.execute(
        """
        UPDATE records SET consecutive_failures = %s, last_scanned = now(), updated_at = now()
        WHERE id = %s
        """,
        (damped.consecutive_failures, record["id"]),
    )


def _emit_scan_events(conn, record: dict, r: ScanResult, damped) -> None:
    if not damped.use_fresh_result:
        return  # damped soft failure — nothing changed, nothing to report

    zone = record["hosted_zone"]
    domain_id = record["domain_id"]
    record_id = record["id"]

    was_up = record["state"] == RecordState.UP
    if was_up and not damped.persist_as_up:
        record_event(
            conn, record_id=record_id, domain_id=domain_id, zone=zone,
            event_type="newly_down", detail={"name": record["name"], "reason": damped.down_reason},
        )

    if not record["weak_cipher_present"] and r.weak_cipher_present:
        record_event(
            conn, record_id=record_id, domain_id=domain_id, zone=zone,
            event_type="new_weak_cipher", detail={"name": record["name"]},
        )

    if record["pqc_supported"] is True and r.pqc_supported is False:
        record_event(
            conn, record_id=record_id, domain_id=domain_id, zone=zone,
            event_type="newly_not_pqc", detail={"name": record["name"]},
        )

    if grade_regressed(record["grade"], r.grade):
        record_event(
            conn, record_id=record_id, domain_id=domain_id, zone=zone,
            event_type="grade_regression",
            detail={"name": record["name"], "from": record["grade"], "to": r.grade},
        )

    _maybe_emit_cert_expiry_event(conn, record, r)


def _maybe_emit_cert_expiry_event(conn, record: dict, r: ScanResult) -> None:
    if not r.cert_expires_at:
        return
    try:
        expires_at = datetime.fromisoformat(r.cert_expires_at)
    except ValueError:
        return
    warning_boundary = datetime.now(timezone.utc) + timedelta(days=_CERT_EXPIRY_WARNING_DAYS)
    now_within_window = expires_at <= warning_boundary

    previously_within_window = False
    prev_expires = record.get("cert_expires_at")
    if prev_expires is not None:
        previously_within_window = prev_expires <= warning_boundary

    if now_within_window and not previously_within_window:
        record_event(
            conn,
            record_id=record["id"],
            domain_id=record["domain_id"],
            zone=record["hosted_zone"],
            event_type="cert_expiring_30d",
            detail={"name": record["name"], "expires_at": r.cert_expires_at},
        )
