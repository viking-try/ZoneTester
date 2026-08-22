from app.grading.header_grade import header_grade


def test_all_headers_present_is_100():
    score, breakdown = header_grade(
        hsts=True, csp_present=True, csp_frame_ancestors=False,
        x_frame_options=True, x_content_type_options=True, referrer_policy=True,
    )
    assert score == 100
    assert breakdown["frame_protection"] is True


def test_frame_ancestors_counts_same_as_x_frame_options_once():
    score_via_xfo, _ = header_grade(
        hsts=False, csp_present=False, csp_frame_ancestors=False,
        x_frame_options=True, x_content_type_options=False, referrer_policy=False,
    )
    score_via_csp, _ = header_grade(
        hsts=False, csp_present=False, csp_frame_ancestors=True,
        x_frame_options=False, x_content_type_options=False, referrer_policy=False,
    )
    both, _ = header_grade(
        hsts=False, csp_present=False, csp_frame_ancestors=True,
        x_frame_options=True, x_content_type_options=False, referrer_policy=False,
    )
    assert score_via_xfo == score_via_csp == 15
    assert both == 15  # not double-counted


def test_no_headers_is_zero():
    score, _ = header_grade(
        hsts=False, csp_present=False, csp_frame_ancestors=False,
        x_frame_options=False, x_content_type_options=False, referrer_policy=False,
    )
    assert score == 0


def test_individual_weights():
    assert header_grade(hsts=True, csp_present=False, csp_frame_ancestors=False, x_frame_options=False, x_content_type_options=False, referrer_policy=False)[0] == 30
    assert header_grade(hsts=False, csp_present=True, csp_frame_ancestors=False, x_frame_options=False, x_content_type_options=False, referrer_policy=False)[0] == 25
    assert header_grade(hsts=False, csp_present=False, csp_frame_ancestors=False, x_frame_options=False, x_content_type_options=True, referrer_policy=False)[0] == 15
    assert header_grade(hsts=False, csp_present=False, csp_frame_ancestors=False, x_frame_options=False, x_content_type_options=False, referrer_policy=True)[0] == 15
