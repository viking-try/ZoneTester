"""The jobs table is the observability mirror of the Celery/Redis queue (per the
architecture notes) — this router is what powers the Scan Queue page, so operators can see
queued/running/done/error without needing Redis access."""
import psycopg
from fastapi import APIRouter, Depends, Request

from app.api.deps import get_db
from app.api.pagination import paginated_response, parse_page_params

router = APIRouter(prefix="/jobs", tags=["jobs"])

_ALLOWED_SORT = {
    "created_at": "created_at",
    "started_at": "started_at",
    "finished_at": "finished_at",
    "state": "state",
    "type": "type",
}


@router.get("")
def list_jobs(request: Request, db: psycopg.Connection = Depends(get_db)) -> dict:
    params = parse_page_params(request, allowed_sort=_ALLOWED_SORT, default_sort="created_at")
    q = request.query_params
    where, sql_params = [], {}
    if q.get("state"):
        where.append("state = %(state)s")
        sql_params["state"] = q["state"]
    if q.get("type"):
        where.append("type = %(type)s")
        sql_params["type"] = q["type"]
    if q.get("zone"):
        where.append("zone = %(zone)s")
        sql_params["zone"] = q["zone"]
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    total = db.execute(f"SELECT count(*) AS n FROM jobs {where_sql}", sql_params).fetchone()["n"]  # noqa: S608  # nosec B608 - fixed fragments only, values always parameterized
    rows = db.execute(
        f"""
        SELECT id, celery_task_id, type, state, error, result, zone, created_at, started_at, finished_at
        FROM jobs {where_sql}
        ORDER BY {params.sort_sql} {params.sort_dir}
        LIMIT %(limit)s OFFSET %(offset)s
        """,  # noqa: S608  # nosec B608 - fixed fragments only, values always parameterized
        {**sql_params, "limit": params.limit, "offset": params.offset},
    ).fetchall()
    return paginated_response(rows, total, params)


@router.get("/summary")
def jobs_summary(db: psycopg.Connection = Depends(get_db)) -> dict:
    """Lightweight KPI counts for the Scan Queue page's header tiles, polled on its own
    faster interval separate from the paginated table (quiet-refresh pattern)."""
    rows = db.execute("SELECT state, count(*) AS n FROM jobs GROUP BY state").fetchall()
    return {"by_state": {r["state"]: r["n"] for r in rows}}
