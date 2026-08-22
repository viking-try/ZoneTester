"""Combines independent signals into a 0-100 cleanup_confidence score, an action
(delete/investigate/keep), and human-readable reasons. Deliberately signal-weighted rather
than a single rule, since any one signal alone (a dead-looking CNAME target, one down scan)
is too weak to safely automate deletion from — the score is meant to guide a human, not
auto-delete anything by itself (hence "verify-before-delete" guidance on every delete verdict)."""
from dataclasses import dataclass, field

from app.constants import CleanupAction

_DELETE_THRESHOLD = 70
_INVESTIGATE_THRESHOLD = 40


@dataclass(slots=True)
class CleanupSignals:
    is_validation_record: bool = False
    validation_orphaned: bool = False
    dead_target_fingerprint: str | None = None
    confirmed_down: bool = False  # down beyond the flap-damping threshold, not a transient blip
    never_up: bool = False  # no successful scan since first_seen
    recent_success: bool = False  # succeeded within the damping/observation window
    record_age_days: int = 0


@dataclass(slots=True)
class CleanupVerdict:
    cleanup: bool
    confidence: int
    action: str
    reasons: list[str] = field(default_factory=list)


def cleanup_confidence(signals: CleanupSignals) -> CleanupVerdict:
    if signals.is_validation_record:
        return _validation_verdict(signals)

    score = 0
    reasons: list[str] = []

    if signals.dead_target_fingerprint:
        score += 40
        reasons.append(
            f"CNAME target matches a known dead-resource pattern "
            f"({signals.dead_target_fingerprint}) — subdomain-takeover risk"
        )
    if signals.confirmed_down:
        score += 25
        reasons.append("confirmed down across multiple consecutive scans (not a transient blip)")
    if signals.never_up:
        score += 15
        reasons.append("never observed successfully up since first seen")
    if signals.never_up and signals.record_age_days > 90:
        score += 10
        reasons.append(f"stale: first seen {signals.record_age_days} days ago, still never up")
    if signals.recent_success:
        score -= 30
        reasons.append("recent successful scan — likely transient, not truly dead")

    score = max(0, min(100, score))
    action = _action_for_score(score)
    if action == CleanupAction.DELETE:
        reasons.append(
            "verify-before-delete: confirm in the cloud console/CMDB that the target resource "
            "is genuinely retired before removing this record"
        )
    if not reasons:
        reasons.append("no cleanup signals present")

    return CleanupVerdict(cleanup=action != CleanupAction.KEEP, confidence=score, action=action, reasons=reasons)


def _validation_verdict(signals: CleanupSignals) -> CleanupVerdict:
    if not signals.validation_orphaned:
        return CleanupVerdict(
            cleanup=False,
            confidence=0,
            action=CleanupAction.KEEP,
            reasons=[
                "active ACM/DCV validation record — never auto-suggested for deletion; "
                "removing it can break certificate auto-renewal"
            ],
        )
    return CleanupVerdict(
        cleanup=True,
        confidence=60,
        action=CleanupAction.INVESTIGATE,
        reasons=[
            "orphaned ACM/DCV validation record: the domain it validates has no live endpoint "
            "anywhere in the zone",
            "verify-before-delete: confirm no pending or future certificate issuance still "
            "depends on this record before removing it",
        ],
    )


def _action_for_score(score: int) -> str:
    if score >= _DELETE_THRESHOLD:
        return CleanupAction.DELETE
    if score >= _INVESTIGATE_THRESHOLD:
        return CleanupAction.INVESTIGATE
    return CleanupAction.KEEP
