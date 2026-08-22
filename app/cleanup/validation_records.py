"""ACM/DCV (domain control validation) records. These are never real endpoints, and deleting
an active one silently breaks certificate auto-renewal — a much worse outage than the
DNS-hygiene problem cleanup detection is trying to solve. Detected records are reclassified
to state='validation' (not scannable, grade=NULL) and are never marked down, never
auto-suggested for deletion, UNLESS the domain they validate has no live endpoint anywhere in
the zone (i.e. the domain itself is dead, so the validation record is provably orphaned)."""
import re

_ACM_DCV_PATTERNS = [
    r"\.acm-validations\.aws$",
    r"^dcv\.digicert\.com$",
    r"\.dcv\.digicert\.com$",
    r"\.pki-validation\.symantec\.com$",
    r"\.sectigo\.com$",
    r"\.comodoca\.com$",
]


def is_validation_record(rtype: str, value: str) -> bool:
    if rtype != "CNAME":
        return False
    value_l = value.lower().rstrip(".")
    return any(re.search(p, value_l) for p in _ACM_DCV_PATTERNS)


def validated_domain_is_orphaned(zone_has_live_endpoint: bool) -> bool:
    """The caller determines whether ANY scannable record in the same hosted zone is
    currently state='up' — if none are, the domain this validation record exists for has no
    live endpoint at all, so the validation record is provably orphaned rather than just
    quiet."""
    return not zone_has_live_endpoint
