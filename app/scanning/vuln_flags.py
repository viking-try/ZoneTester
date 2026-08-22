"""Derives named vulnerability flags from the raw probe results, for display and for grading
to consume as a single boolean where relevant."""


def compute_vuln_flags(*, protocol_matrix: dict[str, bool], weak_cipher_results: dict[str, bool]) -> dict[str, bool]:
    return {
        "poodle": protocol_matrix.get("SSLv3", False),
        "sweet32": weak_cipher_results.get("3DES_SWEET32", False),
        "rc4": weak_cipher_results.get("RC4", False),
        "export_cipher": weak_cipher_results.get("EXPORT", False),
        "null_cipher": weak_cipher_results.get("NULL", False),
        "anonymous_cipher": weak_cipher_results.get("ANONYMOUS", False),
        "legacy_tls": protocol_matrix.get("TLSv1", False) or protocol_matrix.get("TLSv1.1", False),
    }
