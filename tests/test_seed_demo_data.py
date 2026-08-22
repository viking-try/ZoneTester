from app.ingest.detect import sniff_format
from app.ingest.normalize import normalize
from app.ingest.parsers import enriched_csv
from app.seed.synthetic_demo import _DEMO_CSV
from app.constants import BatchFormat


def test_demo_csv_is_valid_enriched_csv():
    raw = _DEMO_CSV.encode("utf-8")
    assert sniff_format(raw) == BatchFormat.ENRICHED_CSV
    records = enriched_csv.parse(raw)
    assert len(records) == 13  # one row each; no embedded commas splitting a row


def test_demo_csv_covers_multiple_zones():
    normalized = normalize(enriched_csv.parse(_DEMO_CSV.encode("utf-8")))
    zones = {n.hosted_zone for n in normalized}
    assert zones == {"example.com", "staging.example-corp.net", "legacy-example.net"}


def test_demo_csv_includes_a_dangling_fingerprint_target():
    from app.cleanup.fingerprints import match_fingerprint

    normalized = normalize(enriched_csv.parse(_DEMO_CSV.encode("utf-8")))
    fingerprints = [match_fingerprint(n.value) for n in normalized if n.rtype == "CNAME"]
    assert "s3_website" in fingerprints
    assert "cloudfront" in fingerprints


def test_demo_csv_includes_acm_validation_records():
    from app.cleanup.validation_records import is_validation_record

    normalized = normalize(enriched_csv.parse(_DEMO_CSV.encode("utf-8")))
    validation_records = [n for n in normalized if is_validation_record(n.rtype, n.value)]
    assert len(validation_records) == 2
