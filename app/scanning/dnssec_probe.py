"""DNSSEC status over DNS-over-HTTPS (lesson #4): corporate DNS resolvers often drop UDP
DNSKEY queries outright, so a direct UDP/53 DNSSEC check is unreliable from inside a
corporate network. Querying over DoH (port 443, same egress path as everything else) avoids
that entirely. Classification is intentionally conservative: 'signed'/'unsigned'/'broken' are
high-confidence; 'partial' is an explicit best-effort label, not a hard guarantee, for the
case where the resolver's AD-flag behavior is inconclusive."""
import logging
from dataclasses import dataclass, field

import httpx

from app.config import settings
from app.scanning.openssl_utils import ca_bundle_path

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DnssecResult:
    status: str  # signed | partial | broken | unsigned | unknown
    has_dnskey: bool
    ad_flag: bool
    detail: dict = field(default_factory=dict)


def _doh_query(zone: str, rtype: str, *, timeout: float) -> dict:
    bundle = ca_bundle_path()
    verify: bool | str = bundle or True
    params = {"name": zone, "type": rtype, "do": "1"}
    headers = {"accept": "application/dns-json"}
    try:
        with httpx.Client(timeout=timeout, verify=verify) as client:
            resp = client.get(settings.doh_url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except httpx.SSLError:
        if not settings.allow_insecure_tls_fallback:
            raise
        logger.warning("DoH TLS verify failed for %s; ALLOW_INSECURE_TLS_FALLBACK is on, retrying insecure", zone)
        with httpx.Client(timeout=timeout, verify=False) as client:  # noqa: S501 - explicit opt-in only, default off, never used for credentialed calls  # nosec B501
            resp = client.get(settings.doh_url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()


def check_dnssec(zone: str, *, timeout: float = 6.0) -> DnssecResult:
    try:
        dnskey_data = _doh_query(zone, "DNSKEY", timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        logger.info("DNSSEC check failed for %s: %s", zone, exc)
        return DnssecResult(status="unknown", has_dnskey=False, ad_flag=False, detail={"error": str(exc)})

    has_dnskey = bool(dnskey_data.get("Answer"))
    ad_flag = bool(dnskey_data.get("AD"))

    if not has_dnskey:
        return DnssecResult(status="unsigned", has_dnskey=False, ad_flag=ad_flag, detail=dnskey_data)

    if ad_flag:
        return DnssecResult(status="signed", has_dnskey=True, ad_flag=True, detail=dnskey_data)

    # DNSKEY exists but this query wasn't validated — disambiguate broken-vs-inconclusive
    # against the apex SOA, which DoH resolvers reliably set AD for on a validating chain.
    try:
        soa_data = _doh_query(zone, "SOA", timeout=timeout)
        status = "broken" if not soa_data.get("AD") else "partial"
    except Exception:  # noqa: BLE001
        status = "partial"

    return DnssecResult(status=status, has_dnskey=True, ad_flag=False, detail=dnskey_data)
