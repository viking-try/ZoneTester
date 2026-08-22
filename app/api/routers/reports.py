"""Schedules CRUD, template preview, send-now, and CSV/HTML download. Send-now and schedule
creation are rate-limited (they can trigger a real email send)."""
import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.api.deps import get_db, require_role
from app.config import settings
from app.constants import Role
from app.jobs.dispatch import dispatch_job
from app.middleware.rate_limit import enforce_rate_limit
from app.reporting.digest import preview_digest
from app.reporting.render import EVENT_TYPE_LABELS

router = APIRouter(tags=["reports"])


@router.get("/reports/templates")
def list_templates() -> dict:
    return {"templates": [{"key": "full", "label": "Full digest"}] + [
        {"key": k, "label": v} for k, v in EVENT_TYPE_LABELS.items()
    ]}


@router.get("/reports/preview")
def preview(request: Request, db: psycopg.Connection = Depends(get_db)) -> dict:
    zone = request.query_params.get("zone")
    template = request.query_params.get("template", "full")
    return preview_digest(db, zone=zone, template=template)


@router.get("/reports/download")
def download(request: Request, db: psycopg.Connection = Depends(get_db)) -> Response:
    zone = request.query_params.get("zone")
    template = request.query_params.get("template", "full")
    fmt = request.query_params.get("format", "html")
    result = preview_digest(db, zone=zone, template=template)
    if fmt == "html":
        return Response(content=result["html"], media_type="text/html")
    from app.reporting.digest import build_digest
    from app.reporting.render import render_report_csv

    digest = build_digest(db, zone=zone, template=template)
    csv_bytes = render_report_csv(digest)
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=zoneguard-report.csv"},
    )


class ScheduleRequest(BaseModel):
    name: str
    zone: str | None = None
    template: str = "full"
    cadence: str = "daily"  # daily | weekly | interval
    interval_minutes: int | None = None
    recipients: list[str]
    enabled: bool = True


@router.get("/schedules")
def list_schedules(db: psycopg.Connection = Depends(get_db)) -> dict:
    rows = db.execute("SELECT * FROM schedules ORDER BY created_at DESC").fetchall()
    return {"schedules": rows}


@router.post("/schedules", dependencies=[Depends(require_role(Role.OPERATOR))])
def create_schedule(body: ScheduleRequest, request: Request, db: psycopg.Connection = Depends(get_db)) -> dict:
    if body.cadence not in ("daily", "weekly", "interval"):
        raise HTTPException(400, "cadence must be daily|weekly|interval")
    from psycopg.types.json import Json

    actor = getattr(request.state, "actor", None) or "anonymous"
    row = db.execute(
        """
        INSERT INTO schedules (name, zone, template, cadence, interval_minutes, recipients, enabled, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            body.name,
            body.zone,
            body.template,
            body.cadence,
            body.interval_minutes,
            Json(body.recipients),
            body.enabled,
            actor,
        ),
    ).fetchone()
    return row


@router.put("/schedules/{schedule_id}", dependencies=[Depends(require_role(Role.OPERATOR))])
def update_schedule(schedule_id: int, body: ScheduleRequest, db: psycopg.Connection = Depends(get_db)) -> dict:
    from psycopg.types.json import Json

    row = db.execute(
        """
        UPDATE schedules SET name=%s, zone=%s, template=%s, cadence=%s, interval_minutes=%s,
               recipients=%s, enabled=%s, updated_at=now()
        WHERE id = %s
        RETURNING *
        """,
        (
            body.name,
            body.zone,
            body.template,
            body.cadence,
            body.interval_minutes,
            Json(body.recipients),
            body.enabled,
            schedule_id,
        ),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "schedule not found")
    return row


@router.delete("/schedules/{schedule_id}", dependencies=[Depends(require_role(Role.OPERATOR))])
def delete_schedule(schedule_id: int, db: psycopg.Connection = Depends(get_db)) -> dict:
    row = db.execute("DELETE FROM schedules WHERE id = %s RETURNING id", (schedule_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "schedule not found")
    return {"deleted": True}


@router.post("/schedules/{schedule_id}/send-now", dependencies=[Depends(require_role(Role.OPERATOR))])
def send_now(schedule_id: int, request: Request, db: psycopg.Connection = Depends(get_db)) -> dict:
    enforce_rate_limit(request, action="report_send", max_per_hour=settings.rate_limit_report_send_per_hour)
    schedule = db.execute("SELECT zone FROM schedules WHERE id = %s", (schedule_id,)).fetchone()
    if schedule is None:
        raise HTTPException(404, "schedule not found")
    job_id = dispatch_job(db, "send_report", {"schedule_id": schedule_id}, zone=schedule["zone"])
    return {"job_id": job_id}
