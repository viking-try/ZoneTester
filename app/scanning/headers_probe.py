"""Fetches HTTP security headers over the already-SSRF-validated TLS connection. Deliberately
uses the same raw socket + ssl.wrap_socket pattern as tls_probe.py (connect to the pinned,
already-guarded IP, send SNI/Host = hostname) rather than a general HTTP client doing its own
DNS resolution — an independent second resolution would reopen the SSRF/DNS-rebind window
the target_resolver guard just closed. Verification is intentionally off here: a self-signed
or expired cert shouldn't stop us from reading its security headers (that's cert_analysis's
job to flag separately)."""
import socket
import ssl
from dataclasses import dataclass, field

_MAX_RESPONSE_BYTES = 65536
_HSTS = "strict-transport-security"
_CSP = "content-security-policy"
_XFO = "x-frame-options"
_XCTO = "x-content-type-options"
_REFERRER = "referrer-policy"
_PERMISSIONS_POLICY = "permissions-policy"


@dataclass(slots=True)
class HeadersResult:
    ok: bool
    status_code: int | None
    headers: dict[str, str] = field(default_factory=dict)
    hsts: bool = False
    csp_present: bool = False
    csp_frame_ancestors: bool = False
    x_frame_options: bool = False
    x_content_type_options: bool = False
    referrer_policy: bool = False
    server: str | None = None
    x_powered_by: str | None = None
    error: str | None = None


def probe_headers(ip: str, host: str, port: int, *, timeout: float) -> HeadersResult:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                request = (
                    f"GET / HTTP/1.1\r\nHost: {host}\r\nUser-Agent: Zoneguard-Scanner/1.0\r\n"
                    "Accept: */*\r\nConnection: close\r\n\r\n"
                ).encode("ascii")
                ssock.sendall(request)
                raw = _read_headers(ssock, timeout)
    except Exception as exc:  # noqa: BLE001
        return HeadersResult(ok=False, status_code=None, error=str(exc))

    return _parse_response(raw)


def _read_headers(ssock: ssl.SSLSocket, timeout: float) -> bytes:
    ssock.settimeout(timeout)
    buf = b""
    while b"\r\n\r\n" not in buf and len(buf) < _MAX_RESPONSE_BYTES:
        chunk = ssock.recv(4096)
        if not chunk:
            break
        buf += chunk
    return buf


def _parse_response(raw: bytes) -> HeadersResult:
    if not raw:
        return HeadersResult(ok=False, status_code=None, error="empty response")

    text = raw.decode("iso-8859-1", errors="replace")
    head, _, _ = text.partition("\r\n\r\n")
    lines = head.split("\r\n")
    status_line = lines[0] if lines else ""

    status_code: int | None = None
    parts = status_line.split(None, 2)
    if len(parts) >= 2 and parts[1].isdigit():
        status_code = int(parts[1])

    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        headers[key.strip().lower()] = value.strip()

    csp = headers.get(_CSP, "")
    return HeadersResult(
        ok=status_code is not None,
        status_code=status_code,
        headers=headers,
        hsts=_HSTS in headers,
        csp_present=bool(csp),
        csp_frame_ancestors="frame-ancestors" in csp.lower(),
        x_frame_options=_XFO in headers,
        x_content_type_options=_XCTO in headers,
        referrer_policy=_REFERRER in headers,
        server=headers.get("server"),
        x_powered_by=headers.get("x-powered-by"),
        error=None if status_code is not None else "could not parse HTTP status line",
    )
