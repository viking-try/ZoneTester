"""Executive dashboard: KPIs + grade distribution (live from records) and trend lines (from
daily snapshots). Zone filter applies to both."""
import psycopg
from fastapi import APIRouter, Depends, Request

from app.api.deps import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_KPI_SQL = """
    SELECT
        count(*) AS total_records,
        count(*) FILTER (WHERE scannable = true) AS scannable_records,
        count(*) FILTER (WHERE scan_state = 'scanned') AS scanned_records,
        count(*) FILTER (WHERE state = 'up') AS up_count,
        count(*) FILTER (WHERE state = 'down') AS down_count,
        count(*) FILTER (WHERE state = 'validation') AS validation_count,
        count(*) FILTER (WHERE pqc_supported = true) AS pqc_count,
        count(*) FILTER (WHERE weak_cipher_present = true) AS weak_cipher_count,
        count(*) FILTER (WHERE cleanup = true) AS cleanup_count,
        count(*) FILTER (WHERE cert_expires_at IS NOT NULL AND cert_expires_at < now() + interval '30 days') AS expiring_cert_count
    FROM records
    WHERE (hosted_zone = %(zone)s OR %(zone)s IS NULL)
"""

_GRADE_DIST_SQL = """
    SELECT grade, count(*) AS n FROM records
    WHERE (hosted_zone = %(zone)s OR %(zone)s IS NULL) AND grade IS NOT NULL
    GROUP BY grade
"""

_DNSSEC_SQL = """
    SELECT dnssec_status, count(*) AS n FROM domains
    WHERE (hosted_zone = %(zone)s OR %(zone)s IS NULL)
    GROUP BY dnssec_status
"""


@router.get("")
def dashboard(request: Request, db: psycopg.Connection = Depends(get_db)) -> dict:
    zone = request.query_params.get("zone")
    kpis = db.execute(_KPI_SQL, {"zone": zone}).fetchone()
    grade_rows = db.execute(_GRADE_DIST_SQL, {"zone": zone}).fetchall()
    dnssec_rows = db.execute(_DNSSEC_SQL, {"zone": zone}).fetchall()
    return {
        "zone": zone,
        "kpis": kpis,
        "grade_distribution": {r["grade"]: r["n"] for r in grade_rows},
        "dnssec_summary": {(r["dnssec_status"] or "unknown"): r["n"] for r in dnssec_rows},
    }


@router.get("/trends")
def trends(request: Request, db: psycopg.Connection = Depends(get_db)) -> dict:
    zone = request.query_params.get("zone") or "__all__"
    days = int(request.query_params.get("days", 90))
    rows = db.execute(
        """
        SELECT snapshot_date, total_records, scanned_records, up_count, down_count,
               grade_distribution, pqc_count, weak_cipher_count, dangling_count, dnssec_summary
        FROM snapshots
        WHERE zone = %s AND snapshot_date >= (current_date - %s::int)
        ORDER BY snapshot_date ASC
        """,
        (zone, days),
    ).fetchall()
    return {"zone": zone, "rows": rows}
