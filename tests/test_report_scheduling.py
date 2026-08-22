from datetime import datetime, timedelta, timezone

from app.reporting.scheduler import _is_due


def test_never_sent_is_always_due():
    assert _is_due({"last_sent_at": None, "cadence": "daily"}, datetime.now(timezone.utc)) is True


def test_daily_not_due_within_23_hours():
    now = datetime.now(timezone.utc)
    schedule = {"last_sent_at": now - timedelta(hours=10), "cadence": "daily"}
    assert _is_due(schedule, now) is False


def test_daily_due_after_23_hours():
    now = datetime.now(timezone.utc)
    schedule = {"last_sent_at": now - timedelta(hours=24), "cadence": "daily"}
    assert _is_due(schedule, now) is True


def test_weekly_due_after_a_week():
    now = datetime.now(timezone.utc)
    assert _is_due({"last_sent_at": now - timedelta(days=8), "cadence": "weekly"}, now) is True
    assert _is_due({"last_sent_at": now - timedelta(days=2), "cadence": "weekly"}, now) is False


def test_interval_cadence_uses_interval_minutes():
    now = datetime.now(timezone.utc)
    schedule = {"last_sent_at": now - timedelta(minutes=45), "cadence": "interval", "interval_minutes": 30}
    assert _is_due(schedule, now) is True
    schedule2 = {"last_sent_at": now - timedelta(minutes=10), "cadence": "interval", "interval_minutes": 30}
    assert _is_due(schedule2, now) is False


def test_unknown_cadence_is_never_due():
    now = datetime.now(timezone.utc)
    assert _is_due({"last_sent_at": now - timedelta(days=100), "cadence": "bogus"}, now) is False
