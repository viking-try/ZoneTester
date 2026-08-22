"""Shared shapes used across format detection, parsers, normalization, and the loader."""
from dataclasses import dataclass


@dataclass(slots=True)
class RawRecord:
    """One DNS record exactly as read from the dump, before domain/zone normalization."""

    name: str
    rtype: str
    value: str
    ttl: int | None = None
    zone_hint: str | None = None  # from an explicit Zone/HostedZone column, if the format has one


@dataclass(slots=True)
class NormalizedRecord:
    """A RawRecord after registrable-domain extraction and zone grouping — ready for loader.py."""

    name: str
    rtype: str
    value: str
    ttl: int | None
    domain: str
    hosted_zone: str
    scannable: bool
