import psycopg
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.api.deps import get_db, require_role
from app.config import settings
from app.constants import Role
from app.jobs.dispatch import dispatch_job
from app.middleware.rate_limit import enforce_rate_limit

router = APIRouter(prefix="/tickets", tags=["tickets"])


class CreateTicketsRequest(BaseModel):
    window: str = "week"  # day | week | month
    zone: str | None = None
    mode: str = "summary"  # summary | per_resource
    provider: str = "jira"  # jira | servicenow
    assignee: str | None = None


@router.post("", dependencies=[Depends(require_role(Role.OPERATOR))])
def create_tickets(body: CreateTicketsRequest, request: Request, db: psycopg.Connection = Depends(get_db)) -> dict:
    enforce_rate_limit(request, action="ticket_create", max_per_hour=settings.rate_limit_ticket_create_per_hour)
    job_id = dispatch_job(db, "create_tickets", body.model_dump(), zone=body.zone)
    return {"job_id": job_id}
