from app.grading.overall_grade import overall_grade


def test_down_excludes_from_distribution():
    letter, score = overall_grade(tls_letter="-", tls_score=None, header_score=0)
    assert letter is None
    assert score is None


def test_trust_failure_shows_t_and_excludes_score():
    letter, score = overall_grade(tls_letter="T", tls_score=None, header_score=50)
    assert letter == "T"
    assert score is None


def test_blend_high_tls_high_headers_is_a_plus():
    letter, score = overall_grade(tls_letter="A+", tls_score=100, header_score=100)
    assert score == 100
    assert letter == "A+"


def test_f_tls_caps_overall_to_f_even_with_perfect_headers():
    letter, score = overall_grade(tls_letter="F", tls_score=40, header_score=100)
    assert letter == "F"
    assert score == 58  # round(0.7*40 + 0.3*100) — the blended number is still reported...


def test_blend_formula():
    # tls B (80) + full headers (100) -> round(0.7*80 + 0.3*100) = round(56+30) = 86 -> band "B" (75-89)
    letter, score = overall_grade(tls_letter="B", tls_score=80, header_score=100)
    assert score == 86
    assert letter == "B"
