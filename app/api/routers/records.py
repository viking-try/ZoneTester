"""Records list/detail/rescan/acknowledge. The list endpoint is the app's densest filter
surface: every filter is applied as a parameterized WHERE fragment from a fixed, developer-
controlled set — no filter ever string-interpolates a user-supplied value directly into SQL
(lesson #11); only bound parameters cross that boundary."""
import logging

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import get_db, require_role
from app.api.pagination import paginated_response, parse_page_params
from app.constants import Role
from app.jobs.dispatch import dispatch_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/records", tags=["records"])

_ALLOWED_SORT = {
    "name": "name",
    "rtype": "rtype",
    "state": "state",
    "grade": "grade",
    "tls_grade": "tls_grade",
    "cleanup_confidence": "cleanup_confidence",
    "last_scanned": "last_scanned",
    "first_seen": "first_seen",
    "hosted_zone": "hosted_zone",
}

_LIST_COLUMNS = """
    id, domain_id, batch_id, name, rtype, value, ttl, hosted_zone, scannable, state,
    down_reason, scan_state, protocol, negotiated_cipher, forward_secrecy, pqc_supported,
    weak_cipher_present, vuln_flags, cert_expires_at, server_header, x_powered_by,
    handshake_trust_failed, tls_grade, tls_score, header_grade, grade, grade_score,
    cleanup, cleanup_confidence, cleanup_action, cleanup_reasons, cleanup_ack,
    consecutive_failures, first_seen, last_scanned, created_at, updated_at
"""

_DETAIL_COLUMNS = _LIST_COLUMNS + ", protocols_supported, cert_json, headers_json"


def _build_filters(q: dict) -> tuple[list[str], dict]:
    where: list[str] = []
    params: dict = {}

    if q.get("search"):
        where.append("(name ILIKE %(search)s OR value ILIKE %(search)s)")
        params["search"] = f"%{q['search']}%"
    if q.get("domain_id"):
        try:
            params["domain_id"] = int(q["domain_id"])
        except ValueError as exc:
            raise HTTPException(400, "domain_id must be an integer") from exc
        where.append("domain_id = %(domain_id)s")
    if q.get("zone"):
        where.append("hosted_zone = %(zone)s")
        params["zone"] = q["zone"]
    if q.get("grade"):
        where.append("grade = %(grade)s")
        params["grade"] = q["grade"]
    if q.get("tls_grade"):
        where.append("tls_grade = %(tls_grade)s")
        params["tls_grade"] = q["tls_grade"]
    if q.get("state"):
        where.append("state = %(state)s")
        params["state"] = q["state"]
    if q.get("rtype"):
        where.append("rtype = %(rtype)s")
        params["rtype"] = q["rtype"]
    if q.get("protocol"):
        where.append("protocol = %(protocol)s")
        params["protocol"] = q["protocol"]
    if q.get("tls12_only") == "true":
        where.append("protocol = 'TLSv1.2'")
    if "scannable" in q:
        where.append("scannable = %(scannable)s")
        params["scannable"] = q["scannable"] == "true"
    if q.get("pqc") == "true":
        where.append("pqc_supported = true")
    elif q.get("pqc") == "false":
        where.append("pqc_supported = false")
    elif q.get("pqc") == "unknown":
        where.append("pqc_supported IS NULL")
    if q.get("weak_cipher") == "true":
        where.append("weak_cipher_present = true")
    if q.get("cleanup") == "true":
        where.append("cleanup = true")
    elif q.get("cleanup") == "false":
        where.append("cleanup = false")
    if q.get("cleanup_action"):
        where.append("cleanup_action = %(cleanup_action)s")
        params["cleanup_action"] = q["cleanup_action"]

    # header/cipher operator filters
    if q.get("hsts_missing") == "true":
        where.append("NOT (headers_json ? 'strict-transport-security')")
    if q.get("server_eq"):
        where.append("server_header = %(server_eq)s")
        params["server_eq"] = q["server_eq"]
    if q.get("server_contains"):
        where.append("server_header ILIKE %(server_contains)s")
        params["server_contains"] = f"%{q['server_contains']}%"
    if q.get("server_present") == "true":
        where.append("server_header IS NOT NULL")
    if q.get("x_powered_by_exposed") == "true":
        where.append("x_powered_by IS NOT NULL")
    if q.get("cipher_eq"):
        where.append("negotiated_cipher = %(cipher_eq)s")
        params["cipher_eq"] = q["cipher_eq"]
    if q.get("cipher_contains"):
        where.append("negotiated_cipher ILIKE %(cipher_contains)s")
        params["cipher_contains"] = f"%{q['cipher_contains']}%"

    return where, params


@router.get("")
def list_records(request: Request, db: psycopg.Connection = Depends(get_db)) -> dict:
    params_page = parse_page_params(request, allowed_sort=_ALLOWED_SORT, default_sort="name")
    where, params = _build_filters(dict(request.query_params))
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    total = db.execute(f"SELECT count(*) AS n FROM records {where_sql}", params).fetchone()["n"]  # noqa: S608  # nosec B608 - fixed fragments only, values always parameterized
    rows = db.execute(
        f"""
        SELECT {_LIST_COLUMNS} FROM records
        {where_sql}
        ORDER BY {params_page.sort_sql} {params_page.sort_dir}
        LIMIT %(limit)s OFFSET %(offset)s
        """,  # noqa: S608 - where_sql/sort_sql are built only from fixed fragments/allowlist above  # nosec B608
        {**params, "limit": params_page.limit, "offset": params_page.offset},
    ).fetchall()
    return paginated_response(rows, total, params_page)


@router.get("/{record_id}")
def get_record(record_id: int, db: psycopg.Connection = Depends(get_db)) -> dict:
    row = db.execute(f"SELECT {_DETAIL_COLUMNS} FROM records WHERE id = %s", (record_id,)).fetchone()  # noqa: S608  # nosec B608 - fixed fragments only, values always parameterized
    if row is None:
        raise HTTPException(404, "record not found")
    return row


@router.post("/{record_id}/rescan", dependencies=[Depends(require_role(Role.OPERATOR))])
def rescan_record(record_id: int, request: Request, db: psycopg.Connection = Depends(get_db)) -> dict:
    exists = db.execute("SELECT id, hosted_zone FROM records WHERE id = %s", (record_id,)).fetchone()
    if exists is None:
        raise HTTPException(404, "record not found")
    job_id = dispatch_job(db, "scan_record", {"record_id": record_id}, zone=exists["hosted_zone"])
    return {"job_id": job_id}


@router.post("/{record_id}/cleanup-ack", dependencies=[Depends(require_role(Role.OPERATOR))])
def acknowledge_cleanup(record_id: int, request: Request, db: psycopg.Connection = Depends(get_db)) -> dict:
    row = db.execute(
        "UPDATE records SET cleanup_ack = true, updated_at = now() WHERE id = %s RETURNING id, cleanup_ack",
        (record_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "record not found")
    return row
