"""SSRF guard: every scan target must be resolved and validated here BEFORE any socket,
TLS, or HTTP probe touches it. Denies loopback, link-local (169.254.0.0/16 — this is the
cloud metadata range: AWS/GCP/Azure instance-metadata SSRF is the exact attack this stops),
and other non-routable ranges unconditionally; RFC1918 private ranges are denied unless
explicitly enabled (a legitimate internal-VPC deployment scans internal ELBs by design, per
the architecture notes, so this must be a togglable policy, not a hardcoded block)."""
import ipaddress
import socket
from dataclasses import dataclass


class SSRFBlockedError(Exception):
    pass


@dataclass(slots=True)
class ResolvedTarget:
    host: str
    ips: list[str]


def resolve_and_guard(host: str, *, allow_rfc1918: bool) -> ResolvedTarget:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise SSRFBlockedError(f"DNS resolution failed for {host!r}: {exc}") from exc

    ips = sorted({info[4][0] for info in infos})
    if not ips:
        raise SSRFBlockedError(f"no addresses resolved for {host!r}")

    for ip_str in ips:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_loopback:
            raise SSRFBlockedError(f"{host!r} resolves to loopback address {ip}")
        if ip.is_link_local:
            raise SSRFBlockedError(f"{host!r} resolves to link-local address {ip} (cloud metadata range)")
        if ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            raise SSRFBlockedError(f"{host!r} resolves to a non-routable address {ip}")
        if not allow_rfc1918 and ip.is_private:
            raise SSRFBlockedError(
                f"{host!r} resolves to private address {ip}; set ALLOW_RFC1918_SCAN_TARGETS=true "
                "to permit scanning internal targets from inside the VPC"
            )

    return ResolvedTarget(host=host, ips=ips)
