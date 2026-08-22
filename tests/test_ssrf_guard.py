import pytest

from app.scanning.target_resolver import SSRFBlockedError, resolve_and_guard


def test_loopback_blocked():
    with pytest.raises(SSRFBlockedError, match="loopback"):
        resolve_and_guard("127.0.0.1", allow_rfc1918=False)


def test_link_local_metadata_blocked():
    with pytest.raises(SSRFBlockedError, match="link-local"):
        resolve_and_guard("169.254.169.254", allow_rfc1918=False)


def test_rfc1918_blocked_by_default():
    with pytest.raises(SSRFBlockedError, match="private"):
        resolve_and_guard("10.0.0.5", allow_rfc1918=False)


def test_rfc1918_allowed_when_enabled():
    target = resolve_and_guard("10.0.0.5", allow_rfc1918=True)
    assert target.ips == ["10.0.0.5"]


def test_public_ip_allowed():
    target = resolve_and_guard("1.1.1.1", allow_rfc1918=False)
    assert target.ips == ["1.1.1.1"]


def test_unresolvable_host_raises():
    with pytest.raises(SSRFBlockedError):
        resolve_and_guard("this-host-does-not-exist.invalid", allow_rfc1918=False)
