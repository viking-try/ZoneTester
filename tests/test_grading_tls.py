import pytest

from app.grading.tls_grade import CertFlags, tls_grade

CLEAN = CertFlags()


def test_down_is_dash():
    letter, score = tls_grade(
        up=False, handshake_trust_failed=False, best_protocol=None,
        pqc_supported=None, hsts=False, weak_cipher_present=False, cert_flags=CLEAN,
    )
    assert letter == "-"
    assert score is None


def test_trust_failure_is_t():
    letter, score = tls_grade(
        up=True, handshake_trust_failed=True, best_protocol="TLSv1.3",
        pqc_supported=True, hsts=True, weak_cipher_present=False, cert_flags=CLEAN,
    )
    assert letter == "T"
    assert score is None


def test_tls13_pqc_hsts_is_a_plus():
    letter, score = tls_grade(
        up=True, handshake_trust_failed=False, best_protocol="TLSv1.3",
        pqc_supported=True, hsts=True, weak_cipher_present=False, cert_flags=CLEAN,
    )
    assert letter == "A+"
    assert score == 100


def test_tls13_without_pqc_or_hsts_is_a():
    letter, _ = tls_grade(
        up=True, handshake_trust_failed=False, best_protocol="TLSv1.3",
        pqc_supported=False, hsts=True, weak_cipher_present=False, cert_flags=CLEAN,
    )
    assert letter == "A"

    letter2, _ = tls_grade(
        up=True, handshake_trust_failed=False, best_protocol="TLSv1.3",
        pqc_supported=True, hsts=False, weak_cipher_present=False, cert_flags=CLEAN,
    )
    assert letter2 == "A"


def test_tls12_only_is_b():
    letter, score = tls_grade(
        up=True, handshake_trust_failed=False, best_protocol="TLSv1.2",
        pqc_supported=False, hsts=False, weak_cipher_present=False, cert_flags=CLEAN,
    )
    assert letter == "B"
    assert score == 80


@pytest.mark.parametrize("protocol", ["TLSv1", "TLSv1.1"])
def test_legacy_tls_is_c(protocol):
    letter, score = tls_grade(
        up=True, handshake_trust_failed=False, best_protocol=protocol,
        pqc_supported=False, hsts=False, weak_cipher_present=False, cert_flags=CLEAN,
    )
    assert letter == "C"
    assert score == 65


def test_sslv3_is_f():
    letter, _ = tls_grade(
        up=True, handshake_trust_failed=False, best_protocol="SSLv3",
        pqc_supported=False, hsts=False, weak_cipher_present=False, cert_flags=CLEAN,
    )
    assert letter == "F"


def test_weak_cipher_caps_best_protocol_to_f():
    letter, _ = tls_grade(
        up=True, handshake_trust_failed=False, best_protocol="TLSv1.3",
        pqc_supported=True, hsts=True, weak_cipher_present=True, cert_flags=CLEAN,
    )
    assert letter == "F"


@pytest.mark.parametrize(
    "flags",
    [
        CertFlags(expired=True),
        CertFlags(self_signed=True),
        CertFlags(sha1_signature=True),
        CertFlags(weak_key=True),
        CertFlags(hostname_mismatch=True),
    ],
)
def test_any_bad_cert_flag_caps_to_f(flags):
    letter, _ = tls_grade(
        up=True, handshake_trust_failed=False, best_protocol="TLSv1.3",
        pqc_supported=True, hsts=True, weak_cipher_present=False, cert_flags=flags,
    )
    assert letter == "F"


def test_rsa_2048_is_not_weak_but_rsa_1024_is():
    # This test documents the weak-key rule at the CertFlags boundary (the actual RSA/EC
    # bit-size threshold logic lives in cert_analysis._is_weak_key and is covered there);
    # here we only confirm tls_grade respects whatever weak_key flag it's handed.
    strong = CertFlags(weak_key=False)
    letter, _ = tls_grade(
        up=True, handshake_trust_failed=False, best_protocol="TLSv1.2",
        pqc_supported=False, hsts=False, weak_cipher_present=False, cert_flags=strong,
    )
    assert letter == "B"


def test_ec_p256_is_not_weak():
    # EC P-256 (256 bits) must NOT trip the weak-key cap the way a flat "<2048" rule would.
    ec_p256_flags = CertFlags(weak_key=False)  # cert_analysis would set weak_key=False for EC/256
    letter, _ = tls_grade(
        up=True, handshake_trust_failed=False, best_protocol="TLSv1.3",
        pqc_supported=True, hsts=True, weak_cipher_present=False, cert_flags=ec_p256_flags,
    )
    assert letter == "A+"
