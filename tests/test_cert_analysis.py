import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import NameOID

from app.scanning.cert_analysis import _is_sha1, analyze_cert, hostname_matches


def _self_signed_cert(key, *, hostname="example.com", sign_hash=hashes.SHA256(), days_valid=365, not_before_offset_days=0):
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    now = datetime.datetime.now(datetime.timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=not_before_offset_days))
        .not_valid_after(now - datetime.timedelta(days=not_before_offset_days) + datetime.timedelta(days=days_valid))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]), critical=False)
    )
    cert = builder.sign(key, sign_hash)
    return cert.public_bytes(serialization.Encoding.DER)


def test_rsa_2048_is_not_weak():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    der = _self_signed_cert(key, hostname="strong-rsa.example.com")
    info = analyze_cert(der, expected_hostname="strong-rsa.example.com")
    assert info.key_algorithm == "RSA"
    assert info.key_size == 2048
    assert info.weak_key is False


def test_rsa_1024_is_weak():
    key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    der = _self_signed_cert(key, hostname="weak-rsa.example.com")
    info = analyze_cert(der, expected_hostname="weak-rsa.example.com")
    assert info.key_size == 1024
    assert info.weak_key is True


def test_ec_p256_is_not_weak_despite_being_under_2048_bits():
    key = ec.generate_private_key(ec.SECP256R1())
    der = _self_signed_cert(key, hostname="ec-p256.example.com")
    info = analyze_cert(der, expected_hostname="ec-p256.example.com")
    assert info.key_algorithm == "EC"
    assert info.key_size == 256
    assert info.weak_key is False  # the flat "<2048=weak" bug this must NOT reproduce


def test_ec_p192_is_weak():
    key = ec.generate_private_key(ec.SECP192R1())
    der = _self_signed_cert(key, hostname="ec-p192.example.com")
    info = analyze_cert(der, expected_hostname="ec-p192.example.com")
    assert info.key_size == 192
    assert info.weak_key is True


def test_self_signed_flag():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    der = _self_signed_cert(key, hostname="self-signed.example.com")
    info = analyze_cert(der, expected_hostname="self-signed.example.com")
    assert info.self_signed is True


def test_expired_flag():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    der = _self_signed_cert(key, hostname="expired.example.com", days_valid=1, not_before_offset_days=30)
    info = analyze_cert(der, expected_hostname="expired.example.com")
    assert info.expired is True


def test_sha1_signature_detection():
    # OpenSSL 3.5's default security level refuses to *sign* a new cert with SHA-1 (correct
    # hardening behavior), so we can't manufacture a real SHA1-signed DER fixture here. The
    # detection logic itself (matching cert.signature_hash_algorithm.name) is a one-line
    # comparison — test it directly instead.
    assert _is_sha1("sha1") is True
    assert _is_sha1("SHA1") is True
    assert _is_sha1("sha256") is False


def test_hostname_mismatch_flag():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    der = _self_signed_cert(key, hostname="issued-for-this.example.com")
    info = analyze_cert(der, expected_hostname="different-hostname.example.com")
    assert info.hostname_mismatch is True


def test_wildcard_hostname_matching():
    assert hostname_matches("app.example.com", ["*.example.com"], None) is True
    assert hostname_matches("deep.app.example.com", ["*.example.com"], None) is False
    assert hostname_matches("example.com", ["*.example.com"], None) is False
    assert hostname_matches("example.com", ["example.com"], None) is True
