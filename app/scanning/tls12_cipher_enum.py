"""Weak-cipher probing for TLS <=1.2 via ssl.SSLContext.set_ciphers() — reliable for this
range (unlike TLS1.3, where set_ciphersuites doesn't exist in Python's ssl module; that's
handled separately in tls13_ciphersuite.py via openssl subprocess). Each probe forces the
security level to 0 so OpenSSL 3.x's modern defaults don't mask a server that still offers
these ciphers."""
import socket
import ssl

WEAK_CIPHER_PROBES: dict[str, str] = {
    "RC4": "RC4",
    "3DES_SWEET32": "3DES",
    "EXPORT": "EXPORT",
    "NULL": "eNULL",
    "ANONYMOUS": "aNULL",
    "MD5": "MD5",
}


def probe_weak_cipher(ip: str, host: str, port: int, openssl_cipher_string: str, *, timeout: float) -> bool:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.minimum_version = ssl.TLSVersion.TLSv1
    ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    try:
        ctx.set_ciphers(f"{openssl_cipher_string}@SECLEVEL=0")
    except ssl.SSLError:
        return False  # this cipher class isn't compiled into the local OpenSSL at all

    try:
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host):
                return True
    except Exception:  # noqa: BLE001 - any failure means the server rejected this cipher class
        return False


def enumerate_weak_ciphers(ip: str, host: str, port: int, *, timeout: float) -> dict[str, bool]:
    return {
        name: probe_weak_cipher(ip, host, port, cipher_str, timeout=timeout)
        for name, cipher_str in WEAK_CIPHER_PROBES.items()
    }


def any_weak_cipher(results: dict[str, bool]) -> bool:
    return any(results.values())
