import psycopg
from fastapi import APIRouter, Depends, Request

from app.api.deps import get_db, require_role
from app.config import settings
from app.constants import Role, ScanScope
from app.jobs.dispatch import dispatch_job
from app.middleware.rate_limit import enforce_rate_limit

router = APIRouter(prefix="/scan", tags=["scan"])


@router.post("", dependencies=[Depends(require_role(Role.OPERATOR))])
def trigger_scan(request: Request, db: psycopg.Connection = Depends(get_db)) -> dict:
    """Body/query: scope (all|down_only|unscanned_only|tls12_only), zone (optional),
    batch_id (optional). Rate-limited since this can fan out to thousands of scan_record
    jobs."""
    enforce_rate_limit(request, action="scan_all", max_per_hour=settings.rate_limit_scan_all_per_hour)

    q = request.query_params
    scope = q.get("scope", ScanScope.ALL)
    zone = q.get("zone")
    batch_id = q.get("batch_id")
    payload = {"scope": scope, "zone": zone, "batch_id": int(batch_id) if batch_id else None}
    job_id = dispatch_job(db, "scan_batch", payload, zone=zone)
    return {"job_id": job_id, "scope": scope, "zone": zone}
