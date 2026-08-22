"""Bare CSV: Name,Type,Value[,TTL] only — no zone column, so hosted_zone is derived purely
from the registrable domain during normalization."""
import csv
import io

from app.ingest.types import RawRecord


def parse(raw: bytes) -> list[RawRecord]:
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return []

    colmap = {c.strip().lower(): c for c in reader.fieldnames}
    name_col, type_col, value_col, ttl_col = (
        colmap.get("name"),
        colmap.get("type"),
        colmap.get("value"),
        colmap.get("ttl"),
    )
    if not (name_col and type_col and value_col):
        raise ValueError("bare CSV missing required Name/Type/Value column(s)")

    records: list[RawRecord] = []
    for row in reader:
        name = (row.get(name_col) or "").strip().rstrip(".")
        rtype = (row.get(type_col) or "").strip().upper()
        value = (row.get(value_col) or "").strip()
        if not (name and rtype and value):
            continue
        ttl = None
        if ttl_col and row.get(ttl_col):
            try:
                ttl = int(row[ttl_col].strip())
            except ValueError:
                ttl = None
        records.append(RawRecord(name=name, rtype=rtype, value=value, ttl=ttl))
    return records
