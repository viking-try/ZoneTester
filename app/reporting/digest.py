"""Diff digest: what changed since the last report for a schedule's zone, built purely from
unreported events (reported_at IS NULL) — the retention pruner (lesson #9) guarantees these
are never pruned out from under a pending digest. A single-section template (e.g. "just new
dangling resources") filters sections down before rendering; 'full' includes everything."""
import logging
from datetime import datetime, timezone

import psycopg

from app.integrations.smtp_client import send_email, smtp_enabled
from app.reporting.render import EVENT_TYPE_LABELS, render_report_csv, render_report_html

logger = logging.getLogger(__name__)


def build_digest(conn: psycopg.Connection, *, zone: str | None, template: str) -> dict:
    if zone:
        events = conn.execute(
            """
            SELECT id, record_id, domain_id, zone, event_type, detail, created_at
            FROM events WHERE reported_at IS NULL AND zone = %s ORDER BY created_at
            """,
            (zone,),
        ).fetchall()
    else:
        events = conn.execute(
            """
            SELECT id, record_id, domain_id, zone, event_type, detail, created_at
            FROM events WHERE reported_at IS NULL ORDER BY created_at
            """
        ).fetchall()

    sections: dict[str, list] = {event_type: [] for event_type in EVENT_TYPE_LABELS}
    for e in events:
        sections.setdefault(e["event_type"], []).append(e)

    if template != "full" and template in sections:
        sections = {template: sections[template]}

    return {"events": events, "sections": sections, "zone": zone}


def build_and_send_report(conn: psycopg.Connection, schedule_id: int) -> dict:
    schedule = conn.execute("SELECT * FROM schedules WHERE id = %s", (schedule_id,)).fetchone()
    if schedule is None:
        return {"error": "schedule not found"}

    digest = build_digest(conn, zone=schedule["zone"], template=schedule["template"])
    html = render_report_html(schedule=schedule, digest=digest)
    csv_bytes = render_report_csv(digest)

    result: dict = {"schedule_id": schedule_id, "event_count": len(digest["events"])}
    if smtp_enabled() and schedule["recipients"]:
        result["email"] = send_email(
            to=schedule["recipients"],
            subject=f"Zoneguard report: {schedule['name']}",
            html_body=html,
            attachments=[("zoneguard-report.csv", csv_bytes, "csv")],
        )
    else:
        result["email"] = {"sent": False, "reason": "SMTP not configured or schedule has no recipients"}

    now = datetime.now(timezone.utc)
    event_ids = [e["id"] for e in digest["events"]]
    if event_ids:
        conn.execute("UPDATE events SET reported_at = %s WHERE id = ANY(%s)", (now, event_ids))
    conn.execute("UPDATE schedules SET last_sent_at = %s WHERE id = %s", (now, schedule_id))

    logger.info("report sent for schedule %s: %s", schedule_id, result)
    return result


def preview_digest(conn: psycopg.Connection, *, zone: str | None, template: str) -> dict:
    """Read-only preview — does NOT mark events as reported or touch last_sent_at."""
    digest = build_digest(conn, zone=zone, template=template)
    schedule_stub = {"name": "Preview", "zone": zone}
    return {"html": render_report_html(schedule=schedule_stub, digest=digest), "event_count": len(digest["events"])}
