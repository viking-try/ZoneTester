from app.cleanup.confidence import CleanupSignals, cleanup_confidence
from app.constants import CleanupAction


def test_no_signals_is_keep():
    verdict = cleanup_confidence(CleanupSignals())
    assert verdict.action == CleanupAction.KEEP
    assert verdict.cleanup is False


def test_dead_fingerprint_plus_confirmed_down_plus_never_up_is_delete():
    verdict = cleanup_confidence(
        CleanupSignals(dead_target_fingerprint="cloudfront", confirmed_down=True, never_up=True)
    )
    assert verdict.confidence == 80
    assert verdict.action == CleanupAction.DELETE
    assert verdict.cleanup is True
    assert any("verify-before-delete" in r for r in verdict.reasons)


def test_dead_fingerprint_alone_is_investigate_not_delete():
    verdict = cleanup_confidence(CleanupSignals(dead_target_fingerprint="cloudfront"))
    assert verdict.confidence == 40
    assert verdict.action == CleanupAction.INVESTIGATE


def test_recent_success_pulls_score_down_even_with_fingerprint():
    verdict = cleanup_confidence(
        CleanupSignals(dead_target_fingerprint="cloudfront", confirmed_down=True, recent_success=True)
    )
    # 40 (fingerprint) + 25 (confirmed_down) - 30 (recent_success) = 35 -> keep
    assert verdict.confidence == 35
    assert verdict.action == CleanupAction.KEEP


def test_stale_never_up_adds_age_signal():
    verdict = cleanup_confidence(CleanupSignals(never_up=True, record_age_days=120))
    assert verdict.confidence == 25  # 15 (never_up) + 10 (stale)


def test_score_never_goes_negative():
    verdict = cleanup_confidence(CleanupSignals(recent_success=True))
    assert verdict.confidence == 0


def test_active_validation_record_is_never_deletable():
    verdict = cleanup_confidence(CleanupSignals(is_validation_record=True, validation_orphaned=False))
    assert verdict.action == CleanupAction.KEEP
    assert verdict.cleanup is False
    assert verdict.confidence == 0


def test_orphaned_validation_record_is_flagged_but_only_investigate():
    verdict = cleanup_confidence(CleanupSignals(is_validation_record=True, validation_orphaned=True))
    assert verdict.cleanup is True
    assert verdict.action == CleanupAction.INVESTIGATE  # never auto-delete even when orphaned
    assert verdict.confidence == 60
