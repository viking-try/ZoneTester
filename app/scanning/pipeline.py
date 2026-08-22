"""Orchestrates one record's full scan: SSRF guard -> fail-fast TCP liveness gate (with a
short retry-with-backoff, since a single dropped SYN shouldn't read as "down") -> protocol
matrix -> trusted handshake -> TLS1.3 ciphersuite/PQC probing (skipped entirely unless
TLS1.3 is in the protocol matrix) -> weak-cipher enumeration -> cert analysis -> security
headers -> grading. Every deep probe is skipped the instant liveness fails, per lesson #6 —
this is what keeps a burst of dead hosts from pinning workers for minutes."""
import logging
import time
from dataclasses import dataclass, field

from app.config import settings
from app.grading.header_grade import header_grade
from app.grading.overall_grade import overall_grade
from app.grading.tls_grade import CertFlags, tls_grade
from app.scanning import cert_analysis, headers_probe, liveness, tls12_cipher_enum, tls_probe
from app.scanning import tls13_ciphersuite as tls13
from app.scanning.target_resolver import ResolvedTarget, SSRFBlockedError, resolve_and_guard
from app.scanning.vuln_flags import compute_vuln_flags

logger = logging.getLogger(__name__)

_LIVENESS_RETRIES = 2
_LIVENESS_BACKOFF_SECONDS = 0.75


@dataclass(slots=True)
class ScanResult:
    up: bool
    down_reason: str | None = None
    blocked: bool = False
    blocked_reason: str | None = None

    protocol: str | None = None
    protocols_supported: dict[str, bool] = field(default_factory=dict)
    negotiated_cipher: str | None = None
    forward_secrecy: bool = False
    handshake_trust_failed: bool = False
    pqc_supported: bool | None = None
    weak_cipher_present: bool = False
    vuln_flags: dict = field(default_factory=dict)

    cert: dict | None = None
    cert_expires_at: str | None = None

    headers: dict = field(default_factory=dict)
    server_header: str | None = None
    x_powered_by: str | None = None
    hsts: bool = False

    tls_grade: str = "-"
    tls_score: int | None = None
    header_grade_score: int = 0
    grade: str | None = None
    grade_score: int | None = None


def scan_host(host: str, port: int = 443) -> ScanResult:
    try:
        target = resolve_and_guard(host, allow_rfc1918=settings.allow_rfc1918_scan_targets)
    except SSRFBlockedError as exc:
        logger.warning("scan target blocked: %s", exc)
        return ScanResult(up=False, blocked=True, blocked_reason=str(exc), tls_grade="-")

    live = _check_liveness_with_retry(target, port)
    if not live.up:
        return ScanResult(up=False, down_reason=live.reason, tls_grade="-")

    ip = live.connected_ip
    result = ScanResult(up=True)

    matrix = tls_probe.protocol_matrix(ip, host, port, timeout=settings.tls_probe_timeout_seconds)
    result.protocols_supported = matrix

    handshake = tls_probe.perform_handshake(ip, host, port, timeout=settings.tls_probe_timeout_seconds)
    if not handshake.ok and not handshake.trust_failed:
        # TCP connected but TLS never completed at all (protocol mismatch, reset during
        # handshake, etc.) — per spec this IS a liveness failure, distinct from an untrusted
        # cert. The host answered TCP but isn't really serving TLS.
        return ScanResult(up=False, down_reason="ssl_error", tls_grade="-")

    result.handshake_trust_failed = handshake.trust_failed
    result.protocol = handshake.negotiated_protocol
    result.negotiated_cipher = handshake.negotiated_cipher
    result.forward_secrecy = handshake.forward_secrecy

    best_protocol = _best_protocol(matrix, handshake.negotiated_protocol)

    weak_cipher_results = tls12_cipher_enum.enumerate_weak_ciphers(
        ip, host, port, timeout=settings.tls_probe_timeout_seconds
    )
    result.weak_cipher_present = tls12_cipher_enum.any_weak_cipher(weak_cipher_results)

    pqc_supported: bool | None = None
    if matrix.get("TLSv1.3"):
        pqc_supported = tls13.detect_pqc(host, port, timeout=settings.openssl_subprocess_timeout_seconds)
    result.pqc_supported = pqc_supported

    result.vuln_flags = compute_vuln_flags(protocol_matrix=matrix, weak_cipher_results=weak_cipher_results)

    cert_flags = CertFlags()
    if handshake.cert_der:
        try:
            cert_info = cert_analysis.analyze_cert(handshake.cert_der, expected_hostname=host)
            result.cert = cert_info.as_json()
            result.cert_expires_at = cert_info.not_after
            cert_flags = CertFlags(
                expired=cert_info.expired,
                self_signed=cert_info.self_signed,
                sha1_signature=cert_info.sha1_signature,
                weak_key=cert_info.weak_key,
                hostname_mismatch=cert_info.hostname_mismatch,
            )
        except Exception as exc:  # noqa: BLE001 - a malformed cert must not crash the scan
            logger.warning("cert analysis failed for %s: %s", host, exc)

    headers_result = headers_probe.probe_headers(ip, host, port, timeout=settings.http_headers_timeout_seconds)
    result.headers = headers_result.headers
    result.server_header = headers_result.server
    result.x_powered_by = headers_result.x_powered_by
    result.hsts = headers_result.hsts

    letter, score = tls_grade(
        up=True,
        handshake_trust_failed=handshake.trust_failed,
        best_protocol=best_protocol,
        pqc_supported=pqc_supported,
        hsts=headers_result.hsts,
        weak_cipher_present=result.weak_cipher_present,
        cert_flags=cert_flags,
    )
    result.tls_grade = letter
    result.tls_score = score

    header_score, _breakdown = header_grade(
        hsts=headers_result.hsts,
        csp_present=headers_result.csp_present,
        csp_frame_ancestors=headers_result.csp_frame_ancestors,
        x_frame_options=headers_result.x_frame_options,
        x_content_type_options=headers_result.x_content_type_options,
        referrer_policy=headers_result.referrer_policy,
    )
    result.header_grade_score = header_score

    overall_letter, overall_score = overall_grade(tls_letter=letter, tls_score=score, header_score=header_score)
    result.grade = overall_letter
    result.grade_score = overall_score

    return result


def _check_liveness_with_retry(target: ResolvedTarget, port: int) -> liveness.LivenessResult:
    attempt = liveness.check_tcp_connect(target.ips, port, timeout=settings.tcp_connect_timeout_seconds)
    if attempt.up:
        return attempt
    for i in range(_LIVENESS_RETRIES):
        time.sleep(_LIVENESS_BACKOFF_SECONDS * (i + 1))
        attempt = liveness.check_tcp_connect(target.ips, port, timeout=settings.tcp_connect_timeout_seconds)
        if attempt.up:
            return attempt
    return attempt


def _best_protocol(matrix: dict[str, bool], negotiated: str | None) -> str | None:
    for name in ("TLSv1.3", "TLSv1.2", "TLSv1.1", "TLSv1", "SSLv3"):
        if matrix.get(name):
            return name
    return negotiated
