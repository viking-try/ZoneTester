"""Cleanup/risk views: the paginated list of cleanup candidates, and the risk rollup that can
be grouped either by issue type (what's wrong) or by asset (which zone/domain it's in)."""
import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import get_db, require_role
from app.api.pagination import paginated_response, parse_page_params
from app.cleanup.reconciliation import reconcile_all
from app.constants import Role

router = APIRouter(tags=["cleanup"])

_ALLOWED_SORT = {
    "cleanup_confidence": "cleanup_confidence",
    "name": "name",
    "hosted_zone": "hosted_zone",
    "cleanup_action": "cleanup_action",
    "last_scanned": "last_scanned",
}


@router.get("/cleanup")
def list_cleanup_candidates(request: Request, db: psycopg.Connection = Depends(get_db)) -> dict:
    params = parse_page_params(request, allowed_sort=_ALLOWED_SORT, default_sort="cleanup_confidence")
    q = request.query_params
    where = ["cleanup = true"]
    sql_params: dict = {}
    if q.get("zone"):
        where.append("hosted_zone = %(zone)s")
        sql_params["zone"] = q["zone"]
    if q.get("action"):
        where.append("cleanup_action = %(action)s")
        sql_params["action"] = q["action"]
    if q.get("ack") == "false":
        where.append("cleanup_ack = false")
    where_sql = "WHERE " + " AND ".join(where)

    total = db.execute(f"SELECT count(*) AS n FROM records {where_sql}", sql_params).fetchone()["n"]  # noqa: S608  # nosec B608 - fixed fragments only, values always parameterized
    rows = db.execute(
        f"""
        SELECT id, name, rtype, value, hosted_zone, state, cleanup_confidence, cleanup_action,
               cleanup_reasons, cleanup_ack, last_scanned
        FROM records {where_sql}
        ORDER BY {params.sort_sql} {params.sort_dir}
        LIMIT %(limit)s OFFSET %(offset)s
        """,  # noqa: S608  # nosec B608 - fixed fragments only, values always parameterized
        {**sql_params, "limit": params.limit, "offset": params.offset},
    ).fetchall()
    return paginated_response(rows, total, params)


@router.post("/cleanup/reconcile", dependencies=[Depends(require_role(Role.OPERATOR))])
def trigger_reconciliation(db: psycopg.Connection = Depends(get_db)) -> dict:
    """Manually re-derive cleanup verdicts from stored data, without rescanning anything —
    useful right after a scoring-rule change."""
    updated = reconcile_all(db)
    return {"updated": updated}


_ISSUE_QUERIES = {
    "dangling": "cleanup = true",
    "down": "state = 'down'",
    "weak_cipher": "weak_cipher_present = true",
    "expired_or_bad_cert": "(cert_json->>'expired')::boolean = true OR (cert_json->>'self_signed')::boolean = true",
    "no_pqc": "pqc_supported = false",
    "missing_hsts": "NOT (headers_json ? 'strict-transport-security') AND state = 'up'",
    "legacy_tls": "protocol IN ('TLSv1', 'TLSv1.1', 'SSLv3')",
}


@router.get("/risk")
def risk_view(request: Request, db: psycopg.Connection = Depends(get_db)) -> dict:
    group_by = request.query_params.get("group_by", "issue")
    zone = request.query_params.get("zone")
    zone_filter = "AND hosted_zone = %(zone)s" if zone else ""
    params = {"zone": zone} if zone else {}

    if group_by == "issue":
        results = []
        for issue, condition in _ISSUE_QUERIES.items():
            sql = f"SELECT count(*) AS n FROM records WHERE ({condition}) {zone_filter}"  # noqa: S608 - condition comes only from the fixed _ISSUE_QUERIES map above, never user input  # nosec B608
            n = db.execute(sql, params).fetchone()["n"]
            results.append({"issue": issue, "count": n})
        return {"group_by": "issue", "rows": results}

    if group_by == "asset":
        sql = f"""
            SELECT hosted_zone,
                   count(*) AS total,
                   count(*) FILTER (WHERE cleanup = true) AS cleanup_count,
                   count(*) FILTER (WHERE state = 'down') AS down_count,
                   count(*) FILTER (WHERE weak_cipher_present = true) AS weak_cipher_count,
                   count(*) FILTER (WHERE grade IN ('F', 'T')) AS f_or_t_count
            FROM records
            WHERE scannable = true {zone_filter}
            GROUP BY hosted_zone
            ORDER BY cleanup_count DESC
        """  # noqa: S608  # nosec B608 - fixed fragments only, values always parameterized
        rows = db.execute(sql, params).fetchall()
        return {"group_by": "asset", "rows": rows}

    raise HTTPException(400, "group_by must be 'issue' or 'asset'")
