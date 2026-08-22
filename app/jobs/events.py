"""Shared event-emission helper. Events power the diff-digest reports (Phase 9) — each row
records one notable transition, and `reported_at` stays NULL until a digest actually includes
it (retention pruning then leaves it alone until reported, per lesson #9)."""
import psycopg
from psycopg.types.json import Json

_GRADE_RANK = {"A+": 6, "A": 5, "B": 4, "C": 3, "F": 2, "T": 1}


def record_event(
    conn: psycopg.Connection,
    *,
    record_id: int | None,
    domain_id: int | None,
    zone: str | None,
    event_type: str,
    detail: dict,
) -> None:
    conn.execute(
        "INSERT INTO events (record_id, domain_id, zone, event_type, detail) VALUES (%s, %s, %s, %s, %s)",
        (record_id, domain_id, zone, event_type, Json(detail)),
    )


def grade_regressed(previous: str | None, current: str | None) -> bool:
    if previous is None or current is None:
        return False
    prev_rank = _GRADE_RANK.get(previous)
    cur_rank = _GRADE_RANK.get(current)
    if prev_rank is None or cur_rank is None:
        return False
    return cur_rank < prev_rank
