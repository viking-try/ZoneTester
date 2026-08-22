"""Determines which report schedules are due to fire. Polled every 5 minutes by
check_schedules_task (beat) rather than computing exact next-fire times — simple, and a
5-minute worst-case slop on a daily/weekly cadence is a non-issue."""
from datetime import datetime, timedelta, timezone

import psycopg


def due_schedules(conn: psycopg.Connection) -> list[dict]:
    now = datetime.now(timezone.utc)
    schedules = conn.execute("SELECT * FROM schedules WHERE enabled = true").fetchall()
    return [s for s in schedules if _is_due(s, now)]


def _is_due(schedule: dict, now: datetime) -> bool:
    last_sent = schedule["last_sent_at"]
    if last_sent is None:
        return True
    cadence = schedule["cadence"]
    if cadence == "daily":
        return (now - last_sent) >= timedelta(hours=23)
    if cadence == "weekly":
        return (now - last_sent) >= timedelta(days=6, hours=23)
    if cadence == "interval":
        minutes = schedule.get("interval_minutes") or 60
        return (now - last_sent) >= timedelta(minutes=minutes)
    return False
