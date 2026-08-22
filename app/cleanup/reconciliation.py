"""Recomputes cleanup verdicts for all records from data already in Postgres — no network
calls (this is the "cross-record reconciliation pass" from the spec). Runs after every scan
batch completes, and can also be triggered standalone (e.g. after a scoring-rule change) to
re-derive verdicts without re-scanning anything."""
import logging
from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Json

from app.cleanup.confidence import CleanupSignals, cleanup_confidence
from app.cleanup.fingerprints import match_fingerprint
from app.cleanup.validation_records import is_validation_record, validated_domain_is_orphaned
from app.config import settings
from app.constants import RecordState

logger = logging.getLogger(__name__)

_SELECT_ZONE_RECORDS_SQL = """
    SELECT id, name, rtype, value, state, scannable, consecutive_failures,
           first_seen, last_scanned, tls_grade
    FROM records
    WHERE hosted_zone = %s
"""

_UPDATE_VERDICT_SQL = """
    UPDATE records
    SET cleanup = %s, cleanup_confidence = %s, cleanup_action = %s, cleanup_reasons = %s,
        updated_at = now()
    WHERE id = %s
"""


def reconcile_zone(conn: psycopg.Connection, hosted_zone: str) -> int:
    records = conn.execute(_SELECT_ZONE_RECORDS_SQL, (hosted_zone,)).fetchall()
    zone_has_live_endpoint = any(r["scannable"] and r["state"] == RecordState.UP for r in records)
    now = datetime.now(timezone.utc)

    updated = 0
    for r in records:
        signals = _build_signals(r, zone_has_live_endpoint=zone_has_live_endpoint, now=now)
        verdict = cleanup_confidence(signals)
        conn.execute(
            _UPDATE_VERDICT_SQL,
            (verdict.cleanup, verdict.confidence, verdict.action, Json(verdict.reasons), r["id"]),
        )
        updated += 1
    return updated


def reconcile_all(conn: psycopg.Connection) -> int:
    zones = [row["hosted_zone"] for row in conn.execute("SELECT DISTINCT hosted_zone FROM records").fetchall()]
    total = sum(reconcile_zone(conn, zone) for zone in zones)
    logger.info("cleanup reconciliation: %d records across %d zones", total, len(zones))
    return total


def _build_signals(record: dict, *, zone_has_live_endpoint: bool, now: datetime) -> CleanupSignals:
    if is_validation_record(record["rtype"], record["value"]):
        return CleanupSignals(
            is_validation_record=True,
            validation_orphaned=validated_domain_is_orphaned(zone_has_live_endpoint),
        )

    if not record["scannable"]:
        return CleanupSignals()  # MX/TXT/NS/etc. aren't cleanup candidates

    fingerprint = match_fingerprint(record["value"]) if record["rtype"] in ("CNAME", "ALIAS") else None
    confirmed_down = (
        record["state"] == RecordState.DOWN
        and record["consecutive_failures"] >= settings.scan_max_consecutive_failures_before_down
    )
    never_up = record["state"] != RecordState.UP and record["tls_grade"] is None
    recent_success = record["state"] == RecordState.UP
    first_seen = record["first_seen"]
    age_days = (now - first_seen).days if first_seen else 0

    return CleanupSignals(
        dead_target_fingerprint=fingerprint,
        confirmed_down=confirmed_down,
        never_up=never_up,
        recent_success=recent_success,
        record_age_days=age_days,
    )
