"""0-100 header_grade: HSTS +30, CSP +25, frame protection (X-Frame-Options OR CSP
frame-ancestors, counted once) +15, X-Content-Type-Options +15, Referrer-Policy +15."""


def header_grade(
    *,
    hsts: bool,
    csp_present: bool,
    csp_frame_ancestors: bool,
    x_frame_options: bool,
    x_content_type_options: bool,
    referrer_policy: bool,
) -> tuple[int, dict[str, bool]]:
    frame_protected = x_frame_options or csp_frame_ancestors
    breakdown = {
        "hsts": hsts,
        "csp": csp_present,
        "frame_protection": frame_protected,
        "x_content_type_options": x_content_type_options,
        "referrer_policy": referrer_policy,
    }
    score = (
        (30 if hsts else 0)
        + (25 if csp_present else 0)
        + (15 if frame_protected else 0)
        + (15 if x_content_type_options else 0)
        + (15 if referrer_policy else 0)
    )
    return score, breakdown
