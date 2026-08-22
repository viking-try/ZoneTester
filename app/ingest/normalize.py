"""Turn RawRecords into NormalizedRecords: attach the registrable domain (via the public
suffix list) and resolve the hosted-zone grouping. zone_hint (an explicit Zone/HostedZone
column, or a Route 53 JSON HostedZone) always wins over the derived registrable domain, so a
dump with ~85 hosted zones groups correctly even when a zone's apex isn't a bare
registrable domain (e.g. a delegated subdomain zone)."""
import tldextract

from app.constants import SCANNABLE_RTYPES
from app.ingest.types import NormalizedRecord, RawRecord

# suffix_list_urls=() forces the bundled offline PSL snapshot — no network call at ingest
# time, which matters both for speed and because this may run without outbound internet.
_extractor = tldextract.TLDExtract(suffix_list_urls=())


def registrable_domain(hostname: str) -> str:
    hostname = hostname.strip().rstrip(".").lower()
    ext = _extractor(hostname)
    if ext.domain and ext.suffix:
        return f"{ext.domain}.{ext.suffix}"
    return hostname  # fallback: e.g. a bare hostname with no recognizable public suffix


def normalize(raw_records: list[RawRecord]) -> list[NormalizedRecord]:
    out: list[NormalizedRecord] = []
    for rr in raw_records:
        domain = registrable_domain(rr.name)
        hosted_zone = rr.zone_hint or domain
        out.append(
            NormalizedRecord(
                name=rr.name.lower(),
                rtype=rr.rtype,
                value=rr.value,
                ttl=rr.ttl,
                domain=domain,
                hosted_zone=hosted_zone,
                scannable=rr.rtype in SCANNABLE_RTYPES,
            )
        )
    return out
