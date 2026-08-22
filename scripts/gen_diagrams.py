"""Generates docs/architecture.svg and docs/data-flow.svg — real rendered diagram images
(not Mermaid source), since many wikis (Bitbucket, plain GitLab, etc.) don't render Mermaid
code blocks but do render an embedded SVG image directly. Pure stdlib string-building, no
external rendering dependency. Run with: python scripts/gen_diagrams.py
"""
from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent / "docs"

FONT = "-apple-system, Helvetica, Arial, sans-serif"


def _multiline_text(x, y, text, *, font_size, weight="600", color="#1a2230", opacity=1, line_height=15):
    lines = text.split("\n")
    start_y = y - (len(lines) - 1) * line_height / 2
    spans = "".join(
        f'<tspan x="{x}" y="{start_y + i * line_height}">{ln}</tspan>' for i, ln in enumerate(lines)
    )
    return (
        f'<text font-family="{FONT}" font-size="{font_size}" font-weight="{weight}" fill="{color}" '
        f'text-anchor="middle" opacity="{opacity}">{spans}</text>'
    )


def box(x, y, w, h, label, *, fill="#eef1f4", stroke="#5b6675", text_color="#1a2230", font_size=13, sub=None):
    lines = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
    ]
    label_y = y + h / 2 - (12 if sub else 0)
    lines.append(_multiline_text(x + w / 2, label_y, label, font_size=font_size, color=text_color))
    if sub:
        sub_y = label_y + 18 + (6 if "\n" in label else 0)
        lines.append(_multiline_text(x + w / 2, sub_y, sub, font_size=11, weight="400", color=text_color, opacity=0.75, line_height=13))
    return "\n".join(lines)


def arrow(x1, y1, x2, y2, *, label=None, dashed=False, color="#5b6675", label_t=0.5, label_dy=-6):
    dash = ' stroke-dasharray="5,4"' if dashed else ""
    lines = [
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.5"{dash} '
        f'marker-end="url(#arrowhead)"/>'
    ]
    if label:
        mx = x1 + (x2 - x1) * label_t
        my = y1 + (y2 - y1) * label_t + label_dy
        lines.append(
            f'<rect x="{mx - len(label) * 3.1}" y="{my - 11}" width="{len(label) * 6.2}" height="14" fill="#ffffff" opacity="0.85"/>'
            f'<text x="{mx}" y="{my}" font-family="{FONT}" font-size="11" fill="{color}" '
            f'text-anchor="middle">{label}</text>'
        )
    return "\n".join(lines)


def svg_wrap(width, height, body, *, bg="#ffffff"):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <marker id="arrowhead" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
      <polygon points="0 0, 10 4, 0 8" fill="#5b6675"/>
    </marker>
  </defs>
  <rect x="0" y="0" width="{width}" height="{height}" fill="{bg}"/>
{body}
</svg>"""


def gen_architecture() -> str:
    parts = []
    parts.append(
        f'<text x="30" y="35" font-family="{FONT}" font-size="18" font-weight="700" fill="#1a2230">'
        f"Zoneguard — deployment architecture</text>"
    )

    # Browser
    parts.append(box(30, 60, 160, 60, "Operator browser", sub="SPA (static JS/CSS)", fill="#e8f0fe", stroke="#2563eb"))

    # Load balancer
    parts.append(box(30, 160, 160, 50, "Load balancer", sub="ALB / Ingress"))

    # API pods
    parts.append(box(30, 250, 160, 70, "api pods (N)", sub="FastAPI, stateless", fill="#e7f6ec", stroke="#15803d"))

    # Postgres
    parts.append(box(260, 250, 150, 70, "PostgreSQL 16", sub="domains/records/jobs/…", fill="#f1e9fd", stroke="#6d28d9"))

    # Redis
    parts.append(box(260, 360, 150, 70, "Redis", sub="Celery broker + backend", fill="#f1e9fd", stroke="#6d28d9"))

    # Worker pods
    parts.append(box(30, 360, 160, 70, "worker pods (N)", sub="Celery, --scale worker=N", fill="#e7f6ec", stroke="#15803d"))

    # Beat
    parts.append(box(30, 460, 160, 60, "beat pod (1)", sub="periodic scheduler", fill="#e7f6ec", stroke="#15803d"))

    # Internet / VPC targets
    parts.append(box(540, 250, 200, 70, "Scan targets", sub="DNS hosts, TLS/443, in-VPC", fill="#fef3e0", stroke="#b45309"))

    # DoH resolver
    parts.append(box(540, 360, 200, 70, "DoH resolver", sub="DNSSEC-over-HTTPS", fill="#fef3e0", stroke="#b45309"))

    # Integrations
    parts.append(box(540, 460, 200, 70, "SMTP / Jira / ServiceNow", sub="+ Secrets Manager — optional", fill="#fdecea", stroke="#dc2626", font_size=12))

    # Arrows
    parts.append(arrow(110, 120, 110, 160))
    parts.append(arrow(110, 210, 110, 250))
    parts.append(arrow(190, 285, 260, 285, label="SQL"))
    parts.append(arrow(190, 395, 260, 395, label="broker"))
    parts.append(arrow(110, 320, 110, 360, label="dispatch-then-record", dashed=True))
    parts.append(arrow(110, 430, 110, 460))
    parts.append(arrow(190, 375, 540, 280, label="TLS/DNS probes"))
    parts.append(arrow(190, 395, 540, 390, label="DNSSEC", label_t=0.78))
    parts.append(arrow(190, 415, 540, 485, label="reports / tickets / secrets"))
    parts.append(arrow(335, 285, 335, 360, dashed=True))

    return svg_wrap(770, 560, "\n".join(parts))


def gen_data_flow() -> str:
    parts = []
    parts.append(
        f'<text x="30" y="35" font-family="{FONT}" font-size="18" font-weight="700" fill="#1a2230">'
        f"Zoneguard — ingest &amp; scan data flow</text>"
    )

    steps = [
        (30, "R53 dump\n(CSV/BIND/JSON)", "upload or S3", "#e8f0fe", "#2563eb"),
        (230, "detect + parse\n+ normalize", "registrable domain\n+ zone grouping", "#e7f6ec", "#15803d"),
        (430, "domains / records\n(Postgres)", "upsert, preserves\nscan history", "#f1e9fd", "#6d28d9"),
        (630, "scan_batch job", "fans out per record", "#fef3e0", "#b45309"),
    ]
    y = 90
    for x, label, sub, fill, stroke in steps:
        parts.append(box(x, y, 170, 70, label, sub=sub.replace("\n", " "), fill=fill, stroke=stroke, font_size=12))
    for i in range(len(steps) - 1):
        x1 = steps[i][0] + 170
        x2 = steps[i + 1][0]
        parts.append(arrow(x1, y + 35, x2, y + 35))

    parts.append(box(630, 220, 170, 90, "scan_record", sub="liveness -> protocol matrix\n-> TLS1.3/PQC -> cert -> headers", fill="#fef3e0", stroke="#b45309", font_size=12))
    parts.append(arrow(715, 160, 715, 220))

    parts.append(box(430, 220, 170, 90, "grading", sub="tls_grade + header_grade\n-> overall grade", fill="#e7f6ec", stroke="#15803d", font_size=12))
    parts.append(arrow(630, 260, 600, 260))

    parts.append(box(230, 220, 170, 90, "cleanup\nreconciliation", sub="fingerprint + validation\n+ confidence score", fill="#fdecea", stroke="#dc2626", font_size=12))
    parts.append(arrow(430, 260, 400, 260))

    parts.append(box(30, 220, 170, 90, "events + snapshots", sub="diff digest source,\ndaily trend data", fill="#eef1f4", stroke="#5b6675", font_size=12))
    parts.append(arrow(230, 260, 200, 260))

    return svg_wrap(830, 340, "\n".join(parts))


def main() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "architecture.svg").write_text(gen_architecture(), encoding="utf-8")
    (DOCS_DIR / "data-flow.svg").write_text(gen_data_flow(), encoding="utf-8")
    print("wrote docs/architecture.svg and docs/data-flow.svg")


if __name__ == "__main__":
    main()
