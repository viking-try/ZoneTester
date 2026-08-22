"""Parses a peer certificate (DER bytes from tls_probe's handshake) into the fields grading
needs, and computes the flags that cap tls_grade regardless of protocol: expired,
self-signed, SHA-1 signature, weak key, hostname mismatch.

Weak-key rule is RSA<2048 OR EC<256 (lesson #12) — a flat "<2048 bits" check would wrongly
fail every modern ECDSA P-256 certificate, which is 256 bits and perfectly strong."""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import NameOID


@dataclass(slots=True)
class CertInfo:
    subject: str
    issuer: str
    not_before: str
    not_after: str
    key_algorithm: str
    key_size: int | None
    signature_algorithm: str
    san_dns_names: list[str] = field(default_factory=list)
    expired: bool = False
    self_signed: bool = False
    sha1_signature: bool = False
    weak_key: bool = False
    hostname_mismatch: bool = False

    def as_json(self) -> dict:
        return {
            "subject": self.subject,
            "issuer": self.issuer,
            "not_before": self.not_before,
            "not_after": self.not_after,
            "key_algorithm": self.key_algorithm,
            "key_size": self.key_size,
            "signature_algorithm": self.signature_algorithm,
            "san_dns_names": self.san_dns_names,
            "expired": self.expired,
            "self_signed": self.self_signed,
            "sha1_signature": self.sha1_signature,
            "weak_key": self.weak_key,
            "hostname_mismatch": self.hostname_mismatch,
        }


def _name_str(name: x509.Name) -> str:
    try:
        cn = name.get_attributes_for_oid(NameOID.COMMON_NAME)
        if cn:
            return cn[0].value
    except Exception:  # noqa: BLE001 - malformed CN attribute falls back to the full DN below  # nosec B110
        pass
    return name.rfc4514_string()


def _key_info(cert: x509.Certificate) -> tuple[str, int | None]:
    pub = cert.public_key()
    if isinstance(pub, rsa.RSAPublicKey):
        return "RSA", pub.key_size
    if isinstance(pub, ec.EllipticCurvePublicKey):
        return "EC", pub.key_size
    return type(pub).__name__, None


def _is_sha1(sig_algo_name: str) -> bool:
    return sig_algo_name.lower() == "sha1"


def _is_weak_key(algorithm: str, key_size: int | None) -> bool:
    if key_size is None:
        return False
    if algorithm == "RSA":
        return key_size < 2048
    if algorithm == "EC":
        return key_size < 256
    return False


def hostname_matches(hostname: str, san_dns_names: list[str], cn_fallback: str | None) -> bool:
    hostname = hostname.lower().rstrip(".")
    candidates = [n.lower().rstrip(".") for n in san_dns_names] or (
        [cn_fallback.lower().rstrip(".")] if cn_fallback else []
    )
    for candidate in candidates:
        if candidate == hostname:
            return True
        if candidate.startswith("*."):
            suffix = candidate[2:]
            host_parts = hostname.split(".")
            if len(host_parts) > 1 and ".".join(host_parts[1:]) == suffix:
                return True
    return False


def analyze_cert(der_bytes: bytes, *, expected_hostname: str) -> CertInfo:
    cert = x509.load_der_x509_certificate(der_bytes)

    subject = _name_str(cert.subject)
    issuer = _name_str(cert.issuer)
    key_algorithm, key_size = _key_info(cert)
    sig_algo_name = cert.signature_hash_algorithm.name if cert.signature_hash_algorithm else "unknown"

    try:
        san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        san_dns_names = san_ext.value.get_values_for_type(x509.DNSName)
    except x509.ExtensionNotFound:
        san_dns_names = []

    now = datetime.now(timezone.utc)
    not_after = cert.not_valid_after_utc
    not_before = cert.not_valid_before_utc

    info = CertInfo(
        subject=subject,
        issuer=issuer,
        not_before=not_before.isoformat(),
        not_after=not_after.isoformat(),
        key_algorithm=key_algorithm,
        key_size=key_size,
        signature_algorithm=sig_algo_name,
        san_dns_names=san_dns_names,
    )
    info.expired = now > not_after or now < not_before
    info.self_signed = cert.issuer == cert.subject
    info.sha1_signature = _is_sha1(sig_algo_name)
    info.weak_key = _is_weak_key(key_algorithm, key_size)
    info.hostname_mismatch = not hostname_matches(expected_hostname, san_dns_names, subject)
    return info
