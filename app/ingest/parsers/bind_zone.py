"""BIND zone file parser. Handles $ORIGIN/$TTL directives, blank-owner-name continuation
(BIND lets a record omit the name to mean "same as previous record"), relative vs absolute
(trailing-dot) names, the '@' origin shorthand, ';' comments, and parenthesized multi-line
records (e.g. SOA). Deliberately scoped to what a Route 53 zone export actually produces —
not a full RFC 1035 grammar."""
import re

from app.ingest.types import RawRecord

_DNS_CLASSES = {"IN", "CH", "HS"}


def parse(raw: bytes) -> list[RawRecord]:
    text = raw.decode("utf-8-sig", errors="replace")
    physical_lines = _strip_comments_and_join_parens(text)

    origin: str | None = None
    default_ttl: int | None = None
    last_owner: str | None = None
    records: list[RawRecord] = []

    for line in physical_lines:
        line = line.strip()
        if not line:
            continue

        low = line.lower()
        if low.startswith("$origin"):
            origin = line.split(None, 1)[1].strip().rstrip(".")
            continue
        if low.startswith("$ttl"):
            try:
                default_ttl = int(line.split(None, 1)[1].strip())
            except (IndexError, ValueError):
                pass
            continue
        if low.startswith(("$include", "$generate")):
            continue  # not supported; skip rather than fail the whole zone

        rec, last_owner = _parse_rr_line(line, origin=origin, default_ttl=default_ttl, last_owner=last_owner)
        if rec is not None:
            records.append(rec)

    return records


def _strip_comments_and_join_parens(text: str) -> list[str]:
    out: list[str] = []
    buf = ""
    depth = 0
    for raw_line in text.splitlines():
        line = _strip_comment(raw_line)
        depth += line.count("(") - line.count(")")
        line = line.replace("(", " ").replace(")", " ")
        buf = f"{buf} {line}" if buf else line
        if depth <= 0:
            out.append(buf)
            buf = ""
            depth = 0
    if buf.strip():
        out.append(buf)
    return out


def _strip_comment(line: str) -> str:
    in_quotes = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == ";" and not in_quotes:
            return line[:i]
    return line


_RR_TYPE_RE = re.compile(
    r"^(A|AAAA|CNAME|MX|TXT|NS|SOA|PTR|SRV|CAA|ALIAS|SPF)$", re.IGNORECASE
)


def _parse_rr_line(
    line: str, *, origin: str | None, default_ttl: int | None, last_owner: str | None
) -> tuple[RawRecord | None, str | None]:
    tokens = line.split()
    if not tokens:
        return None, last_owner

    # Determine whether the line starts with an owner name or omits it (leading whitespace
    # in the original file signals omission, but we've already split on whitespace, so use
    # a heuristic: a token that matches class/ttl/type shape can't be an owner name).
    owner: str
    rest: list[str]
    owner_already_resolved: bool
    if _is_ttl(tokens[0]) or tokens[0].upper() in _DNS_CLASSES or _RR_TYPE_RE.match(tokens[0]):
        if last_owner is None:
            return None, last_owner  # malformed line with no prior owner context; skip
        owner = last_owner  # already a fully-resolved absolute name; do not re-resolve it
        rest = tokens
        owner_already_resolved = True
    else:
        owner = tokens[0]
        rest = tokens[1:]
        owner_already_resolved = False

    resolved_owner = owner if owner_already_resolved else _resolve_name(owner, origin)

    ttl = default_ttl
    idx = 0
    # optional TTL and class tokens can appear in either order before the type
    while idx < len(rest) and idx < 2:
        tok = rest[idx]
        if _is_ttl(tok):
            ttl = int(tok)
            idx += 1
            continue
        if tok.upper() in _DNS_CLASSES:
            idx += 1
            continue
        break

    if idx >= len(rest):
        return None, resolved_owner

    rtype = rest[idx].upper()
    value_tokens = rest[idx + 1 :]
    if not value_tokens:
        return None, resolved_owner

    value = " ".join(value_tokens).strip().strip('"')

    if not _RR_TYPE_RE.match(rtype):
        return None, resolved_owner  # unsupported/unknown rtype line; still track owner

    resolved_value = value
    if rtype in ("CNAME", "ALIAS", "NS", "MX", "PTR"):
        # value may itself be a relative or absolute hostname; MX has a preference prefix
        parts = value.split()
        target = parts[-1] if rtype == "MX" and len(parts) > 1 else value
        resolved_value = _resolve_name(target, origin) if target != "." else target

    return (
        RawRecord(name=resolved_owner, rtype=rtype, value=resolved_value, ttl=ttl),
        resolved_owner,
    )


def _is_ttl(token: str) -> bool:
    return token.isdigit()


def _resolve_name(name: str, origin: str | None) -> str:
    name = name.strip()
    if name == "@":
        return (origin or "").rstrip(".")
    if name.endswith("."):
        return name.rstrip(".")
    if origin:
        return f"{name}.{origin}".rstrip(".")
    return name
