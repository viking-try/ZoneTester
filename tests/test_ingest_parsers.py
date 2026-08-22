from app.constants import BatchFormat
from app.ingest.detect import sniff_format
from app.ingest.normalize import normalize
from app.ingest.parsers import bare_csv, bind_zone, enriched_csv, route53_json


def test_detect_enriched_csv(fixture_bytes):
    raw = fixture_bytes("dumps", "enriched.csv")
    assert sniff_format(raw) == BatchFormat.ENRICHED_CSV


def test_detect_bare_csv(fixture_bytes):
    raw = fixture_bytes("dumps", "bare.csv")
    assert sniff_format(raw) == BatchFormat.BARE_CSV


def test_detect_bind_zone(fixture_bytes):
    raw = fixture_bytes("dumps", "zonefile.txt")
    assert sniff_format(raw) == BatchFormat.BIND_ZONE


def test_detect_route53_json(fixture_bytes):
    raw = fixture_bytes("dumps", "route53.json")
    assert sniff_format(raw) == BatchFormat.ROUTE53_JSON


def test_enriched_csv_parses_zone_hint_and_multivalue(fixture_bytes):
    raw = fixture_bytes("dumps", "enriched.csv")
    records = enriched_csv.parse(raw)
    by_name = {(r.name, r.rtype): r for r in records}

    apex = by_name[("example.com", "A")]
    assert apex.value == "93.184.216.34"
    assert apex.zone_hint == "example.com"

    cname = by_name[("www.example.com", "CNAME")]
    assert cname.value == "d123456abcdef8.cloudfront.net"

    acm = by_name[("cert-validate.other-domain.io", "CNAME")]
    assert acm.value == "xyz.acm-validations.aws"
    assert acm.zone_hint == "other-domain.io"


def test_bare_csv_has_no_zone_hint(fixture_bytes):
    raw = fixture_bytes("dumps", "bare.csv")
    records = bare_csv.parse(raw)
    assert len(records) == 3
    assert all(r.zone_hint is None for r in records)
    ns = next(r for r in records if r.rtype == "NS")
    assert ns.ttl == 172800


def test_bind_zone_resolves_relative_names_and_blank_owner(fixture_bytes):
    raw = fixture_bytes("dumps", "zonefile.txt")
    records = bind_zone.parse(raw)
    by_key = {(r.name, r.rtype): r for r in records}

    assert ("zonefile-example.org", "A") in by_key
    assert by_key[("zonefile-example.org", "A")].value == "192.0.2.10"

    www_cname = by_key[("www.zonefile-example.org", "CNAME")]
    assert www_cname.value == "zonefile-example.org"  # '@' resolved to origin

    api_a = by_key[("api.zonefile-example.org", "A")]
    assert api_a.value == "192.0.2.20"
    assert api_a.ttl == 300  # explicit TTL token on that line

    # blank-owner continuation: TXT record with no name token reuses "api" as owner
    txt = by_key[("api.zonefile-example.org", "TXT")]
    assert "v=spf1" in txt.value


def test_route53_json_multi_zone_and_alias(fixture_bytes):
    raw = fixture_bytes("dumps", "route53.json")
    records = route53_json.parse(raw)
    by_key = {(r.name, r.rtype): r for r in records}

    apex = by_key[("r53-example.com", "A")]
    assert apex.zone_hint == "r53-example.com"

    alias = by_key[("app.r53-example.com", "ALIAS")]
    assert alias.value == "my-elb-123456.us-east-1.elb.amazonaws.com"
    assert alias.zone_hint == "r53-example.com"

    second_zone_cname = by_key[("old.second-zone.com", "CNAME")]
    assert second_zone_cname.zone_hint == "second-zone.com"
    assert second_zone_cname.value == "deleted-distro.cloudfront.net"


def test_route53_json_normalizes_to_scannable_flags(fixture_bytes):
    raw = fixture_bytes("dumps", "route53.json")
    normalized = normalize(route53_json.parse(raw))
    scannable_types = {n.rtype for n in normalized if n.scannable}
    assert scannable_types <= {"A", "AAAA", "CNAME", "ALIAS"}
    txt_records = [n for n in normalized if n.rtype == "TXT"]
    assert txt_records and all(not n.scannable for n in txt_records)
