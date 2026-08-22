"""Jira Cloud REST API v3 ticket creation. Disabled (no-op) when JIRA_BASE_URL/JIRA_API_TOKEN
are unset. Honors the corporate CA bundle for this credentialed call and NEVER falls back to
an unverified connection here regardless of ALLOW_INSECURE_TLS_FALLBACK — that flag is only
ever for the non-credentialed scan-target TLS path."""
import httpx

from app.config import settings
from app.integrations.secrets import resolve_secret
from app.scanning.openssl_utils import ca_bundle_path


def jira_enabled() -> bool:
    return settings.jira_enabled


def create_issue(*, summary: str, description: str, issue_type: str = "Task", assignee: str | None = None) -> dict:
    if not jira_enabled():
        return {"created": False, "reason": "Jira not configured"}

    token = resolve_secret("JIRA_API_TOKEN")
    bundle = ca_bundle_path()
    payload = {
        "fields": {
            "project": {"key": settings.jira_project_key},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
            },
            "issuetype": {"name": issue_type},
        }
    }
    if assignee:
        payload["fields"]["assignee"] = {"accountId": assignee}

    try:
        with httpx.Client(base_url=settings.jira_base_url, verify=bundle or True, timeout=15) as client:
            resp = client.post(
                "/rest/api/3/issue", json=payload, headers={"Authorization": f"Bearer {token}"}
            )
            resp.raise_for_status()
            return {"created": True, "key": resp.json().get("key")}
    except httpx.HTTPError as exc:
        return {"created": False, "reason": str(exc)}
