"""Manual live-network verification of the scanning pipeline, per the verification plan.
Run inside the app container (needs OpenSSL >=3.5 for PQC detection — the host's OpenSSL
cannot do this). Not part of the automated test suite: real hosts change over time, so this
is a human-in-the-loop sanity check, not a CI gate.

Usage: python -m scripts.manual_verify_scan [hostname ...]
"""
import json
import sys

from app.scanning.pipeline import scan_host


def main() -> None:
    hosts = sys.argv[1:] or ["www.cloudflare.com"]
    for host in hosts:
        print(f"\n=== {host} ===")
        result = scan_host(host, 443)
        print(
            json.dumps(
                {
                    "up": result.up,
                    "down_reason": result.down_reason,
                    "protocol": result.protocol,
                    "protocols_supported": result.protocols_supported,
                    "negotiated_cipher": result.negotiated_cipher,
                    "forward_secrecy": result.forward_secrecy,
                    "pqc_supported": result.pqc_supported,
                    "weak_cipher_present": result.weak_cipher_present,
                    "vuln_flags": result.vuln_flags,
                    "handshake_trust_failed": result.handshake_trust_failed,
                    "cert_subject": (result.cert or {}).get("subject"),
                    "cert_expires_at": result.cert_expires_at,
                    "hsts": result.hsts,
                    "server_header": result.server_header,
                    "tls_grade": result.tls_grade,
                    "tls_score": result.tls_score,
                    "header_grade": result.header_grade_score,
                    "grade": result.grade,
                    "grade_score": result.grade_score,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
