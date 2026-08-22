"""Core TLS handshake probing via Python's ssl module: the supported-protocol matrix
(1.0/1.1/1.2/1.3) and the "real" handshake used to determine trust/negotiated cipher.

OpenSSL 3.x's default @SECLEVEL disables legacy protocols/ciphers, so probing whether a
server *supports* TLS1.0/1.1 requires explicitly lowering the security level
("DEFAULT@SECLEVEL=0") for that one probe connection — this is intentional and confined to
the read-only protocol-matrix probe; it is never used for the trust-verification handshake.
"""
import socket
import ssl
from dataclasses import dataclass

from app.scanning.openssl_utils import ca_bundle_path

_PROTOCOL_VERSIONS: dict[str, ssl.TLSVersion] = {
    "SSLv3": ssl.TLSVersion.SSLv3,
    "TLSv1": ssl.TLSVersion.TLSv1,
    "TLSv1.1": ssl.TLSVersion.TLSv1_1,
    "TLSv1.2": ssl.TLSVersion.TLSv1_2,
    "TLSv1.3": ssl.TLSVersion.TLSv1_3,
}


def probe_protocol_supported(ip: str, host: str, port: int, protocol_name: str, *, timeout: float) -> bool:
    version = _PROTOCOL_VERSIONS[protocol_name]
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        ctx.set_ciphers("DEFAULT@SECLEVEL=0")
    except ssl.SSLError:
        pass  # no legacy ciphers available in this build; probe will just fail naturally below
    try:
        ctx.minimum_version = version
        ctx.maximum_version = version
    except (ValueError, OSError):
        return False  # this OpenSSL build doesn't support the protocol at all

    try:
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host):
                return True
    except Exception:  # noqa: BLE001 - any handshake failure means "not supported"
        return False


def protocol_matrix(ip: str, host: str, port: int, *, timeout: float) -> dict[str, bool]:
    return {name: probe_protocol_supported(ip, host, port, name, timeout=timeout) for name in _PROTOCOL_VERSIONS}


@dataclass(slots=True)
class HandshakeResult:
    ok: bool
    trust_failed: bool
    negotiated_protocol: str | None
    negotiated_cipher: str | None
    forward_secrecy: bool
    cert_der: bytes | None
    error: str | None


def _forward_secrecy(cipher_name: str | None) -> bool:
    if not cipher_name:
        return False
    return "ECDHE" in cipher_name or cipher_name.startswith("TLS_AES") or cipher_name.startswith("TLS_CHACHA20")


def perform_handshake(ip: str, host: str, port: int, *, timeout: float) -> HandshakeResult:
    """Attempt a real, trust-verified handshake first (this is what determines
    handshake_trust_failed for grading). If verification fails specifically on the
    certificate chain/hostname, retry once with verification off purely to still capture the
    negotiated protocol/cipher/cert for analysis — the grade gets capped to 'T' either way."""
    trusted = _handshake(ip, host, port, timeout=timeout, verify=True)
    if trusted.ok:
        return trusted
    if trusted.trust_failed:
        untrusted = _handshake(ip, host, port, timeout=timeout, verify=False)
        untrusted.trust_failed = True
        return untrusted
    return trusted


def _handshake(ip: str, host: str, port: int, *, timeout: float, verify: bool) -> HandshakeResult:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if verify:
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        bundle = ca_bundle_path()
        if bundle:
            ctx.load_verify_locations(cafile=bundle)
        else:
            ctx.load_default_certs()
    else:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    try:
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cipher = ssock.cipher()
                cipher_name = cipher[0] if cipher else None
                cert_der = ssock.getpeercert(binary_form=True)
                return HandshakeResult(
                    ok=True,
                    trust_failed=False,
                    negotiated_protocol=ssock.version(),
                    negotiated_cipher=cipher_name,
                    forward_secrecy=_forward_secrecy(cipher_name),
                    cert_der=cert_der,
                    error=None,
                )
    except ssl.SSLCertVerificationError as exc:
        return HandshakeResult(
            ok=False,
            trust_failed=True,
            negotiated_protocol=None,
            negotiated_cipher=None,
            forward_secrecy=False,
            cert_der=None,
            error=f"CERTIFICATE_VERIFY_FAILED: {exc}",
        )
    except Exception as exc:  # noqa: BLE001 - handshake failed for a non-trust reason
        return HandshakeResult(
            ok=False,
            trust_failed=False,
            negotiated_protocol=None,
            negotiated_cipher=None,
            forward_secrecy=False,
            cert_der=None,
            error=str(exc),
        )
