"""SMTP email delivery for report digests. Disabled (a clear no-op status, never an
exception) when SMTP_HOST is unset — a deployment that hasn't configured email yet must not
have its scan jobs fail because of it."""
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings
from app.integrations.secrets import resolve_secret


def smtp_enabled() -> bool:
    return settings.smtp_enabled


def send_email(
    *, to: list[str], subject: str, html_body: str, attachments: list[tuple[str, bytes, str]] | None = None
) -> dict:
    if not smtp_enabled():
        return {"sent": False, "reason": "SMTP not configured"}
    if not to:
        return {"sent": False, "reason": "no recipients"}

    username = resolve_secret("SMTP_USERNAME")
    password = resolve_secret("SMTP_PASSWORD")

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = ", ".join(to)
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html_body, "html"))
    msg.attach(alt)
    for filename, content, subtype in attachments or []:
        part = MIMEApplication(content, _subtype=subtype)
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        server.starttls()
        if username and password:
            server.login(username, password)
        server.sendmail(settings.smtp_from, to, msg.as_string())

    return {"sent": True, "recipients": to}
