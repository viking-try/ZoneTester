"""Persists a parsed+normalized batch: upserts domains, upserts records (without clobbering
existing scan history on re-ingest of an already-known record), and writes the batches
row for ingest-history bookkeeping. Row-count cap is enforced by the caller (the upload
endpoint) before parsing even starts, per upload-hardening requirements — this module
assumes it's already within bounds."""
import logging

import psycopg

from app.cleanup.validation_records import is_validation_record
from app.constants import BatchFormat, RecordState
from app.ingest.types import NormalizedRecord

logger = logging.getLogger(__name__)

_UPSERT_DOMAIN_SQL = """
    INSERT INTO domains (domain, hosted_zone, source)
    VALUES (%(domain)s, %(hosted_zone)s, %(source)s)
    ON CONFLICT (domain) DO UPDATE SET
        hosted_zone = COALESCE(EXCLUDED.hosted_zone, domains.hosted_zone),
        updated_at = now()
    RETURNING id
"""

_UPSERT_RECORD_SQL = """
    INSERT INTO records (domain_id, batch_id, name, rtype, value, ttl, hosted_zone, scannable)
    VALUES (%(domain_id)s, %(batch_id)s, %(name)s, %(rtype)s, %(value)s, %(ttl)s, %(hosted_zone)s, %(scannable)s)
    ON CONFLICT (name, rtype, value) DO UPDATE SET
        ttl = EXCLUDED.ttl,
        hosted_zone = EXCLUDED.hosted_zone,
        domain_id = EXCLUDED.domain_id,
        batch_id = EXCLUDED.batch_id,
        scannable = EXCLUDED.scannable,
        updated_at = now()
"""


def create_batch(
    conn: psycopg.Connection, *, filename: str | None, fmt: str, source: str, uploaded_by: str | None
) -> int:
    row = conn.execute(
        """
        INSERT INTO batches (filename, format, source, uploaded_by, status)
        VALUES (%s, %s, %s, %s, 'processing')
        RETURNING id
        """,
        (filename, fmt, source, uploaded_by),
    ).fetchone()
    return row["id"]


def load_batch(
    conn: psycopg.Connection, batch_id: int, normalized: list[NormalizedRecord], *, source: str
) -> dict:
    domain_ids: dict[str, int] = {}
    zone_by_domain: dict[str, str] = {}
    for rec in normalized:
        # last-write-wins per domain within this batch; a domain should have one zone anyway
        zone_by_domain[rec.domain] = rec.hosted_zone

    with conn.cursor() as cur:
        for domain, hosted_zone in zone_by_domain.items():
            cur.execute(_UPSERT_DOMAIN_SQL, {"domain": domain, "hosted_zone": hosted_zone, "source": source})
            domain_ids[domain] = cur.fetchone()["id"]

        for rec in normalized:
            cur.execute(
                _UPSERT_RECORD_SQL,
                {
                    "domain_id": domain_ids[rec.domain],
                    "batch_id": batch_id,
                    "name": rec.name,
                    "rtype": rec.rtype,
                    "value": rec.value,
                    "ttl": rec.ttl,
                    "hosted_zone": rec.hosted_zone,
                    "scannable": rec.scannable,
                },
            )

        # ACM/DCV validation records are recognized at ingest time, not at scan time — there's
        # no reason to ever queue a network probe for something we already know is a DCV
        # pointer. Forced on every ingest (not just insert) so a re-uploaded dump reclassifies
        # correctly even if the record previously looked like an ordinary CNAME.
        for rec in normalized:
            if rec.rtype == "CNAME" and is_validation_record(rec.rtype, rec.value):
                cur.execute(
                    """
                    UPDATE records SET state = %s, scannable = false, updated_at = now()
                    WHERE name = %s AND rtype = %s AND value = %s
                    """,
                    (RecordState.VALIDATION, rec.name, rec.rtype, rec.value),
                )

        cur.execute(
            """
            UPDATE domains d SET record_count = (
                SELECT count(*) FROM records r WHERE r.domain_id = d.id
            )
            WHERE d.id = ANY(%s)
            """,
            (list(domain_ids.values()),),
        )

        cur.execute(
            """
            UPDATE batches SET row_count = %s, domain_count = %s, status = 'done'
            WHERE id = %s
            """,
            (len(normalized), len(domain_ids), batch_id),
        )

    logger.info(
        "batch %s loaded: %d records across %d domains", batch_id, len(normalized), len(domain_ids)
    )
    return {"batch_id": batch_id, "row_count": len(normalized), "domain_count": len(domain_ids)}


def mark_batch_error(conn: psycopg.Connection, batch_id: int, error: str) -> None:
    conn.execute("UPDATE batches SET status = 'error', error = %s WHERE id = %s", (error, batch_id))


PARSERS = {
    BatchFormat.ENRICHED_CSV: "app.ingest.parsers.enriched_csv",
    BatchFormat.BARE_CSV: "app.ingest.parsers.bare_csv",
    BatchFormat.BIND_ZONE: "app.ingest.parsers.bind_zone",
    BatchFormat.ROUTE53_JSON: "app.ingest.parsers.route53_json",
}
