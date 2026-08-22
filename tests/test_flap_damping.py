from app.constants import RecordState
from app.scanning.flap_damping import apply_flap_damping
from app.scanning.pipeline import ScanResult


def test_fresh_up_result_always_applies():
    outcome = apply_flap_damping(
        previous_state=RecordState.DOWN, previous_consecutive_failures=5, result=ScanResult(up=True)
    )
    assert outcome.persist_as_up is True
    assert outcome.consecutive_failures == 0
    assert outcome.use_fresh_result is True


def test_single_soft_failure_on_previously_up_host_stays_up():
    outcome = apply_flap_damping(
        previous_state=RecordState.UP,
        previous_consecutive_failures=0,
        result=ScanResult(up=False, down_reason="timeout"),
    )
    assert outcome.persist_as_up is True
    assert outcome.use_fresh_result is False  # keep prior grade — don't wipe it on a blip
    assert outcome.consecutive_failures == 1


def test_failure_below_threshold_still_damped():
    outcome = apply_flap_damping(
        previous_state=RecordState.UP,
        previous_consecutive_failures=1,
        result=ScanResult(up=False, down_reason="timeout"),
    )
    assert outcome.persist_as_up is True
    assert outcome.consecutive_failures == 2


def test_failure_reaching_threshold_demotes():
    # default threshold is 3 consecutive failures
    outcome = apply_flap_damping(
        previous_state=RecordState.UP,
        previous_consecutive_failures=2,
        result=ScanResult(up=False, down_reason="connection_error"),
    )
    assert outcome.persist_as_up is False
    assert outcome.consecutive_failures == 3
    assert outcome.use_fresh_result is True
    assert outcome.down_reason == "connection_error"


def test_already_down_host_failing_again_stays_down_immediately():
    outcome = apply_flap_damping(
        previous_state=RecordState.DOWN,
        previous_consecutive_failures=3,
        result=ScanResult(up=False, down_reason="no_answer"),
    )
    assert outcome.persist_as_up is False
    assert outcome.use_fresh_result is True


def test_first_ever_scan_failing_is_not_damped():
    # previous_state=None (unscanned) — no prior "up" to protect, so a first failure counts immediately
    outcome = apply_flap_damping(
        previous_state=None, previous_consecutive_failures=0, result=ScanResult(up=False, down_reason="timeout")
    )
    assert outcome.persist_as_up is False
    assert outcome.consecutive_failures == 1
