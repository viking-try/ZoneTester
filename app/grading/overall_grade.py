"""Overall `grade`: round(0.7*tls_score + 0.3*header_score), capped to F/T when tls_grade is
F/T. Down records (tls_grade='-') get grade=NULL entirely and are excluded from grade
distributions, per spec — a host we never scanned has no opinion to blend."""


def _score_to_letter(score: int) -> str:
    if score >= 97:
        return "A+"
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    return "F"


def overall_grade(*, tls_letter: str, tls_score: int | None, header_score: int) -> tuple[str | None, int | None]:
    if tls_letter == "-":
        return None, None
    if tls_letter == "T":
        return "T", None

    combined = round(0.7 * tls_score + 0.3 * header_score)
    letter = _score_to_letter(combined)
    if tls_letter == "F":
        letter = "F"
    return letter, combined
