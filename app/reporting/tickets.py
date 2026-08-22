"""Create Jira/ServiceNow tickets for new dangling records over a window (day/week/month),
either one summary ticket or one ticket per resource."""
import logging
from datetime import datetime, timedelta, timezone

import psycopg

from app.integrations.jira_client import create_issue, jira_enabled
from app.integrations.servicenow_client import create_incident, servicenow_enabled

logger = logging.getLogger(__name__)

_WINDOW_DAYS = {"day": 1, "week": 7, "month": 30}


def _dangling_records_in_window(conn: psycopg.Connection, *, window: str, zone: str | None) -> list[dict]:
    days = _WINDOW_DAYS.get(window, 7)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    where = ["cleanup = true", "first_seen >= %(cutoff)s"]
    params: dict = {"cutoff": cutoff}
    if zone:
        where.append("hosted_zone = %(zone)s")
        params["zone"] = zone
    rows = conn.execute(
        f"SELECT id, name, rtype, value, hosted_zone, cleanup_action, cleanup_confidence, cleanup_reasons "
        f"FROM records WHERE {' AND '.join(where)} ORDER BY cleanup_confidence DESC",  # noqa: S608 - fixed fragments only  # nosec B608
        params,
    ).fetchall()
    return rows


def create_tickets_for_dangling(conn: psycopg.Connection, payload: dict) -> dict:
    window = payload.get("window", "week")
    zone = payload.get("zone")
    mode = payload.get("mode", "summary")  # summary | per_resource
    provider = payload.get("provider", "jira")  # jira | servicenow
    assignee = payload.get("assignee")

    records = _dangling_records_in_window(conn, window=window, zone=zone)
    if not records:
        return {"created": 0, "records_considered": 0, "reason": "no new dangling records in window"}

    if provider == "jira" and not jira_enabled():
        return {"created": 0, "reason": "Jira not configured"}
    if provider == "servicenow" and not servicenow_enabled():
        return {"created": 0, "reason": "ServiceNow not configured"}

    results = []
    if mode == "per_resource":
        for r in records:
            results.append(_create_one(provider, _record_summary(r), _record_description(r), assignee))
    else:
        summary = f"Zoneguard: {len(records)} new dangling record(s) in the last {window}" + (
            f" ({zone})" if zone else ""
        )
        description = "\n\n".join(_record_description(r) for r in records)
        results.append(_create_one(provider, summary, description, assignee))

    created = sum(1 for r in results if r.get("created"))
    return {"created": created, "records_considered": len(records), "results": results}


def _record_summary(r: dict) -> str:
    return f"Zoneguard: dangling record {r['name']} ({r['rtype']}) — {r['cleanup_action']}"


def _record_description(r: dict) -> str:
    reasons = "; ".join(r.get("cleanup_reasons") or [])
    return (
        f"Record: {r['name']} ({r['rtype']} -> {r['value']})\n"
        f"Zone: {r['hosted_zone']}\n"
        f"Cleanup action: {r['cleanup_action']} (confidence {r['cleanup_confidence']})\n"
        f"Reasons: {reasons}"
    )


def _create_one(provider: str, summary: str, description: str, assignee: str | None) -> dict:
    if provider == "servicenow":
        return create_incident(short_description=summary, description=description)
    return create_issue(summary=summary, description=description, assignee=assignee)
