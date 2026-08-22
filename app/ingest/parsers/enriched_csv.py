"""Enriched CSV: header includes Name,Type,Value plus at least one extra column. We only
care about Name/Type/Value/TTL/Zone|HostedZone; any other columns (e.g. a comment column)
are ignored. A record with multiple comma-separated values in one Value cell (Route 53
console CSV exports sometimes do this for e.g. multi-value MX/TXT) is split into one
RawRecord per value."""
import csv
import io

from app.ingest.types import RawRecord

_ZONE_COL_ALIASES = ("zone", "hostedzone", "hosted_zone", "hosted zone")


def parse(raw: bytes) -> list[RawRecord]:
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return []

    colmap = {c.strip().lower(): c for c in reader.fieldnames}
    name_col = colmap.get("name")
    type_col = colmap.get("type")
    value_col = colmap.get("value")
    ttl_col = colmap.get("ttl")
    zone_col = next((colmap[a] for a in _ZONE_COL_ALIASES if a in colmap), None)

    if not (name_col and type_col and value_col):
        raise ValueError("enriched CSV missing required Name/Type/Value column(s)")

    records: list[RawRecord] = []
    for row in reader:
        name = (row.get(name_col) or "").strip().rstrip(".")
        rtype = (row.get(type_col) or "").strip().upper()
        raw_value = (row.get(value_col) or "").strip()
        if not (name and rtype and raw_value):
            continue
        ttl = _parse_ttl(row.get(ttl_col)) if ttl_col else None
        zone_hint = (row.get(zone_col) or "").strip().rstrip(".") or None if zone_col else None
        for value in _split_multi_value(raw_value):
            records.append(RawRecord(name=name, rtype=rtype, value=value, ttl=ttl, zone_hint=zone_hint))
    return records


def _split_multi_value(raw_value: str) -> list[str]:
    if "\n" in raw_value:
        return [v.strip() for v in raw_value.splitlines() if v.strip()]
    return [raw_value]


def _parse_ttl(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        return int(raw.strip())
    except ValueError:
        return None
