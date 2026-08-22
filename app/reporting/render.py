"""Server-rendered HTML for email digests, plus a CSV export of the same data for download/
attachment. autoescape is mandatory and non-negotiable here: hostnames/values inside
events[].detail come straight from uploaded DNS dumps and must be treated as untrusted input
in an HTML context — Jinja2's autoescape is what keeps a malicious record name from becoming
an XSS payload in a report email."""
import csv
import io
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "j2", "html.j2"]),
)

EVENT_TYPE_LABELS = {
    "new_dangling": "New dangling / takeover-risk records",
    "newly_down": "Newly down",
    "new_weak_cipher": "New weak-cipher exposure",
    "newly_not_pqc": "Newly not PQC-ready",
    "grade_regression": "Grade regressions",
    "cert_expiring_30d": "Certificates expiring within 30 days",
}


def render_report_html(*, schedule: dict, digest: dict) -> str:
    template = _env.get_template("base.html.j2")
    return template.render(
        schedule=schedule,
        digest=digest,
        event_type_labels=EVENT_TYPE_LABELS,
    )


def render_report_csv(digest: dict) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["event_type", "zone", "detail", "created_at"])
    for e in digest["events"]:
        writer.writerow([e["event_type"], e.get("zone") or "", str(e["detail"]), e["created_at"]])
    return buf.getvalue().encode("utf-8")
