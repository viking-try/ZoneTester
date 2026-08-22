from app.cleanup.fingerprints import match_fingerprint
from app.cleanup.validation_records import is_validation_record, validated_domain_is_orphaned


def test_acm_validation_detected():
    assert is_validation_record("CNAME", "_abc123.xyz456.acm-validations.aws.") is True


def test_digicert_dcv_detected():
    assert is_validation_record("CNAME", "dcv.digicert.com") is True
    assert is_validation_record("CNAME", "sub.dcv.digicert.com") is True


def test_ordinary_cname_not_validation():
    assert is_validation_record("CNAME", "app.example.com") is False


def test_non_cname_never_validation():
    assert is_validation_record("A", "203.0.113.10") is False


def test_orphaned_only_when_no_live_endpoint_in_zone():
    assert validated_domain_is_orphaned(zone_has_live_endpoint=False) is True
    assert validated_domain_is_orphaned(zone_has_live_endpoint=True) is False


def test_fingerprint_matches_known_dead_target_families():
    assert match_fingerprint("d123abc.cloudfront.net") == "cloudfront"
    assert match_fingerprint("my-elb-123.us-east-1.elb.amazonaws.com") == "elb"
    assert match_fingerprint("myapp.azurewebsites.net") == "azure_app_service"
    assert match_fingerprint("dead-bucket.s3-website-us-east-1.amazonaws.com") == "s3_website"


def test_fingerprint_no_match_for_ordinary_target():
    assert match_fingerprint("app.internal.example.com") is None
