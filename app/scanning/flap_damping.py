"""Flap damping (lesson #5): a transient timeout/handshake failure on a previously-up host
must not immediately flip it to down and wipe its grade — that causes exactly the grade
oscillation (B/C/F flapping) and event-feed spam the lesson warns about. A host only gets
demoted to down after `scan_max_consecutive_failures_before_down` CONSECUTIVE failures; below
that threshold the prior up state and prior grades are kept as-is (this function tells the
caller whether to apply the fresh scan result or keep what's already stored)."""
from dataclasses import dataclass

from app.config import settings
from app.constants import RecordState
from app.scanning.pipeline import ScanResult


@dataclass(slots=True)
class DampedOutcome:
    persist_as_up: bool
    down_reason: str | None
    consecutive_failures: int
    use_fresh_result: bool  # False = this was a damped soft failure; caller keeps prior grade/TLS fields


def apply_flap_damping(
    *, previous_state: str | None, previous_consecutive_failures: int, result: ScanResult
) -> DampedOutcome:
    if result.up:
        return DampedOutcome(persist_as_up=True, down_reason=None, consecutive_failures=0, use_fresh_result=True)

    new_failures = (previous_consecutive_failures or 0) + 1
    threshold = settings.scan_max_consecutive_failures_before_down

    if previous_state == RecordState.UP and new_failures < threshold:
        return DampedOutcome(
            persist_as_up=True, down_reason=None, consecutive_failures=new_failures, use_fresh_result=False
        )

    return DampedOutcome(
        persist_as_up=False,
        down_reason=result.down_reason,
        consecutive_failures=new_failures,
        use_fresh_result=True,
    )
