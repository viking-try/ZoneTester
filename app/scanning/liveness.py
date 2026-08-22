"""The fail-fast gate (lesson #6): a plain TCP connect probe that runs before any TLS/cipher/
header probing. If this fails, the record is marked down with a reason and every deeper
probe is skipped entirely — this is what stops a burst of dead hosts from pinning every
worker for minutes doing full cipher enumeration against nothing."""
import socket
from dataclasses import dataclass

from app.constants import DownReason


@dataclass(slots=True)
class LivenessResult:
    up: bool
    reason: str | None
    connected_ip: str | None


def check_tcp_connect(ips: list[str], port: int, *, timeout: float) -> LivenessResult:
    if not ips:
        return LivenessResult(up=False, reason=DownReason.NO_ANSWER, connected_ip=None)

    last_reason = DownReason.CONNECTION_ERROR
    for ip in ips:
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return LivenessResult(up=True, reason=None, connected_ip=ip)
        except socket.timeout:
            last_reason = DownReason.TIMEOUT
        except OSError:
            last_reason = DownReason.CONNECTION_ERROR

    return LivenessResult(up=False, reason=last_reason, connected_ip=None)
