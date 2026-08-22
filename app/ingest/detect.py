"""Auto-detect a Route 53 dump's format from its raw bytes. Order matters: JSON is checked
first (unambiguous), then BIND zone syntax (has directives/record-class markers CSV never
has), then CSV is split into 'enriched' (extra columns beyond Name/Type/Value[/TTL]) vs
'bare' by header shape."""
import json

from app.constants import BatchFormat

_BARE_CSV_HEADER_MIN = {"name", "type", "value"}
_BIND_DIRECTIVES = ("$origin", "$ttl", "$include", "$generate")
_DNS_CLASSES = {"IN", "CH", "HS"}


def sniff_format(raw: bytes) -> str:
    text = raw.decode("utf-8-sig", errors="replace").strip()
    if not text:
        raise ValueError("empty upload")

    if text[0] in "{[":
        try:
            json.loads(text)
            return BatchFormat.ROUTE53_JSON
        except json.JSONDecodeError:
            pass

    first_lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith(";")][:15]
    if not first_lines:
        raise ValueError("no parseable content found")

    if _looks_like_bind_zone(first_lines):
        return BatchFormat.BIND_ZONE

    if _looks_like_csv(first_lines):
        header_cols = {c.strip().strip('"').lower() for c in first_lines[0].split(",")}
        if not _BARE_CSV_HEADER_MIN.issubset(header_cols):
            raise ValueError(
                "CSV header must include Name, Type, Value columns (case-insensitive)"
            )
        extra_cols = header_cols - _BARE_CSV_HEADER_MIN - {"ttl"}
        return BatchFormat.ENRICHED_CSV if extra_cols else BatchFormat.BARE_CSV

    raise ValueError("could not detect dump format: not JSON, BIND zone, or recognizable CSV")


def _looks_like_bind_zone(lines: list[str]) -> bool:
    for line in lines:
        low = line.strip().lower()
        if low.startswith(_BIND_DIRECTIVES):
            return True
    for line in lines:
        parts = line.split()
        # BIND RR line shape: name [ttl] [class] type rdata...  — class token IN/CH/HS is the tell,
        # since no CSV or JSON dump legitimately has a bare "IN" token in a data row.
        if any(p in _DNS_CLASSES for p in parts) and len(parts) >= 4:
            return True
    return False


def _looks_like_csv(lines: list[str]) -> bool:
    if "," not in lines[0]:
        return False
    header_cols = len(lines[0].split(","))
    return header_cols >= 3
