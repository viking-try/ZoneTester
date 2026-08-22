import psycopg
from fastapi import APIRouter, Depends, Request

from app.api.deps import get_db
from app.api.pagination import paginated_response, parse_page_params

router = APIRouter(prefix="/audit", tags=["audit"])

_ALLOWED_SORT = {
    "created_at": "created_at",
    "actor": "actor",
    "method": "method",
    "status_code": "status_code",
}


@router.get("")
def list_audit(request: Request, db: psycopg.Connection = Depends(get_db)) -> dict:
    params = parse_page_params(request, allowed_sort=_ALLOWED_SORT, default_sort="created_at")
    actor = request.query_params.get("actor")
    where_sql = "WHERE actor = %(actor)s" if actor else ""
    sql_params = {"actor": actor} if actor else {}

    total = db.execute(f"SELECT count(*) AS n FROM audit {where_sql}", sql_params).fetchone()["n"]  # noqa: S608  # nosec B608 - fixed fragments only, values always parameterized
    rows = db.execute(
        f"""
        SELECT id, actor, method, endpoint, path, status_code, duration_ms, ip, created_at
        FROM audit {where_sql}
        ORDER BY {params.sort_sql} {params.sort_dir}
        LIMIT %(limit)s OFFSET %(offset)s
        """,  # noqa: S608  # nosec B608 - fixed fragments only, values always parameterized
        {**sql_params, "limit": params.limit, "offset": params.offset},
    ).fetchall()
    return paginated_response(rows, total, params)
