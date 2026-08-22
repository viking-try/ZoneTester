from app.ingest.normalize import normalize, registrable_domain
from app.ingest.types import RawRecord


def test_registrable_domain_strips_subdomains():
    assert registrable_domain("www.app.example.com") == "example.com"
    assert registrable_domain("example.com") == "example.com"
    assert registrable_domain("example.co.uk") == "example.co.uk"
    assert registrable_domain("deep.sub.example.co.uk") == "example.co.uk"


def test_zone_hint_wins_over_derived_domain():
    raw = [RawRecord(name="host.delegated.example.com", rtype="A", value="1.2.3.4", zone_hint="delegated.example.com")]
    normalized = normalize(raw)
    assert normalized[0].domain == "example.com"
    assert normalized[0].hosted_zone == "delegated.example.com"


def test_no_zone_hint_falls_back_to_registrable_domain():
    raw = [RawRecord(name="www.example.com", rtype="A", value="1.2.3.4")]
    normalized = normalize(raw)
    assert normalized[0].hosted_zone == "example.com"


def test_scannable_flag_by_rtype():
    raw = [
        RawRecord(name="a.example.com", rtype="A", value="1.2.3.4"),
        RawRecord(name="cname.example.com", rtype="CNAME", value="target.example.com"),
        RawRecord(name="mx.example.com", rtype="MX", value="10 mail.example.com"),
        RawRecord(name="txt.example.com", rtype="TXT", value="hello"),
    ]
    normalized = normalize(raw)
    scannable = {n.name: n.scannable for n in normalized}
    assert scannable["a.example.com"] is True
    assert scannable["cname.example.com"] is True
    assert scannable["mx.example.com"] is False
    assert scannable["txt.example.com"] is False
