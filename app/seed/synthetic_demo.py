"""Seeds a small SYNTHETIC multi-zone demo dataset — fabricated example.com-family data, never
a real customer dump — through the real ingest pipeline (same parser/loader path as an
uploaded CSV), so it genuinely exercises multi-zone grouping, validation-record
classification, and dangling-CNAME fingerprint detection on first boot.

Runs once: only fires when SEED_DEMO_DATA=true and the domains table is empty (idempotent
across restarts). The apex `example.com` itself is IANA's real reserved documentation domain
(RFC 2606) and will resolve if scanned — that's intentional and expected, it's the standard
placeholder domain for exactly this kind of example. Every other hostname below
(www/api/mail.example.com, the *.example-corp.net and *.legacy-example.net records) is
fabricated and will not resolve; scanning them will correctly show as down. Cleanup
reconciliation is run once after seeding so the dangling-CNAME and validation-record demo
data shows up immediately, without requiring a scan first.
"""
import logging

import psycopg

from app.cleanup.reconciliation import reconcile_all
from app.ingest.pipeline import ingest_bytes

logger = logging.getLogger(__name__)

_DEMO_CSV = """Name,Type,Value,TTL,Zone,Comment
example.com,A,93.184.216.34,300,example.com,apex (IANA reserved documentation domain)
www.example.com,CNAME,d1a2b3c4d5e6f7.cloudfront.net,300,example.com,cdn-fronted marketing site (fabricated target)
api.example.com,A,203.0.113.20,300,example.com,internal api (fabricated)
mail.example.com,A,203.0.113.30,3600,example.com,mail host (fabricated)
mail.example.com,MX,10 mail.example.com,3600,example.com,mail exchanger
example.com,TXT,v=spf1 include:_spf.example.com -all,300,example.com,spf record
_acme-challenge.example.com,CNAME,demo1234.acm-validations.aws,300,example.com,acm dcv for the apex cert
app.staging.example-corp.net,CNAME,dead-bucket-xyz.s3-website-us-east-1.amazonaws.com,300,staging.example-corp.net,orphaned dangling cname - subdomain takeover risk
old-app.staging.example-corp.net,CNAME,retired-distro-99.cloudfront.net,300,staging.example-corp.net,another dangling cname target
_acme-challenge.staging.example-corp.net,CNAME,demo5678.acm-validations.aws,300,staging.example-corp.net,acm dcv - zone has no confirmed-live endpoint yet
legacy-example.net,A,203.0.113.40,300,legacy-example.net,old apex - likely legacy TLS only
ftp.legacy-example.net,A,203.0.113.41,300,legacy-example.net,legacy ftp gateway (fabricated)
legacy-example.net,NS,ns1.legacy-example.net,172800,legacy-example.net,ns delegation (not scannable)
"""


def seed_if_empty(conn: psycopg.Connection) -> bool:
    count = conn.execute("SELECT count(*) AS n FROM domains").fetchone()["n"]
    if count > 0:
        logger.info("seed: domains table already has data, skipping demo seed")
        return False

    result = ingest_bytes(
        conn,
        _DEMO_CSV.encode("utf-8"),
        filename="synthetic-demo.csv",
        source="upload",
        uploaded_by="system",
    )
    reconciled = reconcile_all(conn)
    logger.info("seed: loaded synthetic demo dataset %s, reconciled %d records", result, reconciled)
    return True
