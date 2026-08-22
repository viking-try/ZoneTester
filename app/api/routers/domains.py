import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import get_db, require_role
from app.api.pagination import paginated_response, parse_page_params
from app.constants import Role
from app.jobs.dispatch import dispatch_job

router = APIRouter(prefix="/domains", tags=["domains"])

_ALLOWED_SORT = {
    "domain": "domain",
    "hosted_zone": "hosted_zone",
    "record_count": "record_count",
    "last_scan_at": "last_scan_at",
    "dnssec_status": "dnssec_status",
}


@router.get("")
def list_domains(request: Request, db: psycopg.Connection = Depends(get_db)) -> dict:
    params = parse_page_params(request, allowed_sort=_ALLOWED_SORT, default_sort="domain")
    zone = request.query_params.get("zone")
    search = request.query_params.get("search")

    where, sql_params = [], {}
    if zone:
        where.append("hosted_zone = %(zone)s")
        sql_params["zone"] = zone
    if search:
        where.append("domain ILIKE %(search)s")
        sql_params["search"] = f"%{search}%"
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    total = db.execute(f"SELECT count(*) AS n FROM domains {where_sql}", sql_params).fetchone()["n"]  # noqa: S608  # nosec B608 - fixed fragments only, values always parameterized
    rows = db.execute(
        f"""
        SELECT id, domain, hosted_zone, source, dnssec_status, last_scan_at, record_count,
               created_at, updated_at
        FROM domains {where_sql}
        ORDER BY {params.sort_sql} {params.sort_dir}
        LIMIT %(limit)s OFFSET %(offset)s
        """,  # noqa: S608  # nosec B608 - fixed fragments only, values always parameterized
        {**sql_params, "limit": params.limit, "offset": params.offset},
    ).fetchall()
    return paginated_response(rows, total, params)


@router.get("/zones")
def list_zones(db: psycopg.Connection = Depends(get_db)) -> dict:
    """Distinct hosted zones for populating the zone filter dropdown everywhere in the UI."""
    rows = db.execute(
        "SELECT hosted_zone, count(*) AS domain_count FROM domains GROUP BY hosted_zone ORDER BY hosted_zone"
    ).fetchall()
    return {"zones": rows}


@router.get("/{domain_id}")
def get_domain(domain_id: int, db: psycopg.Connection = Depends(get_db)) -> dict:
    row = db.execute("SELECT * FROM domains WHERE id = %s", (domain_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "domain not found")
    return row


@router.post("/{domain_id}/scan", dependencies=[Depends(require_role(Role.OPERATOR))])
def scan_domain(domain_id: int, request: Request, db: psycopg.Connection = Depends(get_db)) -> dict:
    domain = db.execute("SELECT id FROM domains WHERE id = %s", (domain_id,)).fetchone()
    if domain is None:
        raise HTTPException(404, "domain not found")
    job_id = dispatch_job(db, "scan_domain", {"domain_id": domain_id})
    return {"job_id": job_id}
