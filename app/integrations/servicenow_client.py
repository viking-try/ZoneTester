"""ServiceNow Table API incident creation. Disabled (no-op) when SERVICENOW_BASE_URL/
SERVICENOW_USERNAME are unset. Same TLS-verification posture as jira_client: corporate CA
bundle honored, insecure fallback never applies to this credentialed call."""
import httpx

from app.config import settings
from app.integrations.secrets import resolve_secret
from app.scanning.openssl_utils import ca_bundle_path


def servicenow_enabled() -> bool:
    return settings.servicenow_enabled


def create_incident(*, short_description: str, description: str, assignment_group: str | None = None) -> dict:
    if not servicenow_enabled():
        return {"created": False, "reason": "ServiceNow not configured"}

    password = resolve_secret("SERVICENOW_PASSWORD")
    bundle = ca_bundle_path()
    payload = {"short_description": short_description, "description": description}
    if assignment_group:
        payload["assignment_group"] = assignment_group

    try:
        with httpx.Client(
            base_url=settings.servicenow_base_url,
            verify=bundle or True,
            timeout=15,
            auth=(settings.servicenow_username, password or ""),
        ) as client:
            resp = client.post("/api/now/table/incident", json=payload)
            resp.raise_for_status()
            return {"created": True, "sys_id": resp.json()["result"]["sys_id"]}
    except httpx.HTTPError as exc:
        return {"created": False, "reason": str(exc)}
