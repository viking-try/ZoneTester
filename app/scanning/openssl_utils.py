"""The ONE place subprocess touches the openssl CLI. args must always be a list — never
shell=True, never an f-string command line — because a hostile record `name`/`value` from an
untrusted dump must never reach a shell. get_verify_setting() centralizes corporate-MITM-
proxy CA bundle handling (REQUESTS_CA_BUNDLE/SSL_CERT_FILE) so python ssl, httpx, and the
openssl CLI all honor the same trust root consistently."""
import os
import subprocess  # nosec B404 - the one sanctioned subprocess boundary, see module docstring

from app.config import settings


class OpenSSLTimeout(Exception):
    pass


def run_openssl(args: list[str], *, timeout: float, input_bytes: bytes = b"") -> subprocess.CompletedProcess:
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        raise TypeError("openssl args must be a list[str]")

    full_args = ["openssl", *args]
    try:
        return subprocess.run(  # noqa: S603 - args is always a list, never shell=True  # nosec B603
            full_args,
            input=input_bytes,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise OpenSSLTimeout(f"openssl {args[0] if args else ''} timed out after {timeout}s") from exc
    except FileNotFoundError as exc:
        raise OpenSSLTimeout(f"openssl binary not found: {exc}") from exc


def ca_bundle_path() -> str | None:
    """Corporate TLS-inspection proxies (MITM) break default cert verification on outbound
    HTTPS inside a container. If REQUESTS_CA_BUNDLE/SSL_CERT_FILE point at the corporate root,
    honor it everywhere; otherwise fall back to the system trust store."""
    return settings.requests_ca_bundle or os.environ.get("SSL_CERT_FILE") or None


def openssl_cafile_args() -> list[str]:
    bundle = ca_bundle_path()
    return ["-CAfile", bundle] if bundle else []
