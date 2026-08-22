"""SSL-Labs-style tls_grade: A+ down through F, plus 'T' (handshake completed but cert
trust/hostname failed) and '-' (down, not scanned). Base tier comes purely from the best
negotiated protocol; a weak cipher or any bad cert property (expired/self-signed/SHA-1/weak-
key/hostname-mismatch) then hard-caps the result to F regardless of protocol tier — a
TLS1.3-capable server that also still offers RC4 does not get to claim TLS1.3's grade.
Weak-key is RSA<2048 OR EC<256 (lesson #12), computed upstream in cert_analysis."""
from dataclasses import dataclass

GRADE_SCORES: dict[str, int] = {"A+": 100, "A": 95, "B": 80, "C": 65, "F": 40}


@dataclass(slots=True)
class CertFlags:
    expired: bool = False
    self_signed: bool = False
    sha1_signature: bool = False
    weak_key: bool = False
    hostname_mismatch: bool = False

    @property
    def any_bad(self) -> bool:
        return self.expired or self.self_signed or self.sha1_signature or self.weak_key or self.hostname_mismatch


def tls_grade(
    *,
    up: bool,
    handshake_trust_failed: bool,
    best_protocol: str | None,
    pqc_supported: bool | None,
    hsts: bool,
    weak_cipher_present: bool,
    cert_flags: CertFlags,
) -> tuple[str, int | None]:
    if not up:
        return "-", None
    if handshake_trust_failed:
        return "T", None

    if best_protocol == "TLSv1.3":
        letter = "A+" if (pqc_supported and hsts) else "A"
    elif best_protocol == "TLSv1.2":
        letter = "B"
    elif best_protocol in ("TLSv1", "TLSv1.1"):
        letter = "C"
    else:
        # SSLv3, no negotiable protocol, or anything else we don't recognize as a real tier
        letter = "F"

    if weak_cipher_present or cert_flags.any_bad:
        letter = "F"

    return letter, GRADE_SCORES[letter]
