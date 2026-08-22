"""TLS1.3 ciphersuite enumeration and live PQC (post-quantum) key-exchange detection.

Python's ssl module has no set_ciphersuites() for TLS1.3 (lesson #2), so per-suite support is
determined by shelling out to `openssl s_client` and parsing its `-brief` output — the only
reliable way to ask "did the server actually negotiate this specific TLS1.3 suite / hybrid
group" over the wire. All parsing is regex-tolerant and wrapped so a parser miss returns
False/None rather than raising, since OpenSSL's brief-output wording has shifted across
3.2-3.5+ point releases and a scan must never crash on an unexpected format."""
import re

from app.scanning.openssl_utils import OpenSSLTimeout, run_openssl

TLS13_CIPHERSUITES = [
    "TLS_AES_256_GCM_SHA384",
    "TLS_AES_128_GCM_SHA256",
    "TLS_CHACHA20_POLY1305_SHA256",
    "TLS_AES_128_CCM_SHA256",
]

# X25519MLKEM768 is the standardized hybrid group (RFC-tracked, OpenSSL >=3.2); the Kyber
# draft name is kept as a fallback for slightly older 3.2/3.3 builds that predate the rename.
PQC_GROUPS = ["X25519MLKEM768", "X25519Kyber768Draft00"]

_CIPHERSUITE_RE = re.compile(r"Ciphersuite:\s*(\S+)")
_PQC_GROUP_RE = re.compile(r"Negotiated TLS1\.3 group:\s*(\S+)", re.IGNORECASE)


def _run_brief(host: str, port: int, extra_args: list[str], *, timeout: float) -> str:
    args = [
        "s_client",
        "-connect",
        f"{host}:{port}",
        "-tls1_3",
        "-servername",
        host,
        "-brief",
        *extra_args,
    ]
    try:
        result = run_openssl(args, timeout=timeout, input_bytes=b"Q\n")
    except OpenSSLTimeout:
        return ""
    return (result.stdout + result.stderr).decode("utf-8", errors="replace")


def probe_tls13_ciphersuite(host: str, port: int, suite: str, *, timeout: float) -> bool:
    output = _run_brief(host, port, ["-ciphersuites", suite], timeout=timeout)
    match = _CIPHERSUITE_RE.search(output)
    return bool(match and match.group(1).strip() == suite)


def enumerate_tls13_ciphersuites(host: str, port: int, *, timeout: float) -> dict[str, bool]:
    return {
        suite: probe_tls13_ciphersuite(host, port, suite, timeout=timeout) for suite in TLS13_CIPHERSUITES
    }


def probe_pqc_group(host: str, port: int, group: str, *, timeout: float) -> bool:
    output = _run_brief(host, port, ["-groups", group], timeout=timeout)
    match = _PQC_GROUP_RE.search(output)
    return bool(match and match.group(1).strip() == group)


def detect_pqc(host: str, port: int, *, timeout: float) -> bool | None:
    """True/False when determinable; None ("unknown") if every group probe errors out, so a
    parsing surprise degrades to 'unknown' rather than a false negative or a crashed scan."""
    saw_any_success = False
    try:
        for group in PQC_GROUPS:
            if probe_pqc_group(host, port, group, timeout=timeout):
                return True
            saw_any_success = True  # the probe ran without raising, even if not negotiated
        return False if saw_any_success else None
    except Exception:  # noqa: BLE001 - never let a PQC probe crash the scan
        return None
