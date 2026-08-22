"""Route 53 JSON: the literal output of `aws route53 list-resource-record-sets`, or a bundle
of several such outputs (list of them, or the S3 connector's one-object-per-hosted-zone
convention). Handles: a single {"ResourceRecordSets": [...]} object (optionally with a
top-level HostedZone name/id for the zone hint), a JSON array of such objects, or a bare
array of record-set dicts. Alias records (AliasTarget instead of ResourceRecords) are
normalized to rtype='ALIAS' with the alias DNSName as the value, since that's what needs to
be treated as a scannable CNAME-like pointer at a cloud resource."""
import json

from app.ingest.types import RawRecord


def parse(raw: bytes) -> list[RawRecord]:
    text = raw.decode("utf-8-sig", errors="replace")
    data = json.loads(text)

    zone_bundles: list[dict]
    if isinstance(data, list):
        zone_bundles = data
    elif isinstance(data, dict) and "ResourceRecordSets" in data:
        zone_bundles = [data]
    elif isinstance(data, dict) and "HostedZones" in data:
        # `aws route53 list-hosted-zones` shape accidentally uploaded; nothing scannable in it.
        return []
    else:
        raise ValueError("unrecognized Route 53 JSON shape")

    records: list[RawRecord] = []
    for bundle in zone_bundles:
        if isinstance(bundle, dict) and "ResourceRecordSets" in bundle:
            zone_hint = _extract_zone_hint(bundle)
            rrsets = bundle["ResourceRecordSets"]
        else:
            zone_hint = None
            rrsets = [bundle] if isinstance(bundle, dict) else []

        for rrset in rrsets:
            records.extend(_parse_rrset(rrset, zone_hint))

    return records


def _extract_zone_hint(bundle: dict) -> str | None:
    hz = bundle.get("HostedZone")
    if isinstance(hz, dict):
        name = hz.get("Name")
        if name:
            return str(name).rstrip(".")
    for key in ("HostedZoneName", "Zone"):
        if bundle.get(key):
            return str(bundle[key]).rstrip(".")
    return None


def _parse_rrset(rrset: dict, zone_hint: str | None) -> list[RawRecord]:
    if not isinstance(rrset, dict):
        return []
    name = str(rrset.get("Name", "")).strip().rstrip(".")
    rtype = str(rrset.get("Type", "")).strip().upper()
    ttl = rrset.get("TTL")
    ttl = int(ttl) if isinstance(ttl, (int, float)) else None
    if not (name and rtype):
        return []

    alias = rrset.get("AliasTarget")
    if isinstance(alias, dict) and alias.get("DNSName"):
        value = str(alias["DNSName"]).strip().rstrip(".")
        return [RawRecord(name=name, rtype="ALIAS", value=value, ttl=ttl, zone_hint=zone_hint)]

    out: list[RawRecord] = []
    for rr in rrset.get("ResourceRecords", []) or []:
        value = str(rr.get("Value", "")).strip().strip('"')
        if not value:
            continue
        if rtype in ("CNAME", "NS", "PTR", "MX"):
            # hostname-valued rtypes carry a trailing dot in R53 JSON; MX has a preference
            # prefix ("10 mail.example.com.") so only the hostname part gets the dot stripped.
            parts = value.split()
            if rtype == "MX" and len(parts) > 1:
                value = f"{parts[0]} {parts[-1].rstrip('.')}"
            else:
                value = value.rstrip(".")
        out.append(RawRecord(name=name, rtype=rtype, value=value, ttl=ttl, zone_hint=zone_hint))
    return out
