"""Read-only integration status (what's configured, driven entirely by env — never secrets
themselves) plus a small key/value settings store for in-app preferences that aren't
security-sensitive (e.g. default page size). Secrets are never stored here or returned by
this endpoint."""
import psycopg
from fastapi import APIRouter, Depends, Request

from app.api.deps import get_db, require_role
from app.config import settings as cfg
from app.constants import Role

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/integrations")
def integration_status() -> dict:
    return {
        "smtp": {"enabled": cfg.smtp_enabled, "host": cfg.smtp_host or None},
        "jira": {"enabled": cfg.jira_enabled, "base_url": cfg.jira_base_url or None},
        "servicenow": {"enabled": cfg.servicenow_enabled, "base_url": cfg.servicenow_base_url or None},
        "oidc": {"enabled": cfg.oidc_enabled, "issuer": cfg.oidc_issuer or None},
        "secrets_backend": cfg.secrets_backend,
        "doh_url": cfg.doh_url,
        "allow_rfc1918_scan_targets": cfg.allow_rfc1918_scan_targets,
        "allow_insecure_tls_fallback": cfg.allow_insecure_tls_fallback,
    }


@router.get("")
def list_settings(db: psycopg.Connection = Depends(get_db)) -> dict:
    rows = db.execute("SELECT key, value, updated_at, updated_by FROM settings ORDER BY key").fetchall()
    return {"settings": rows}


@router.put("/{key}", dependencies=[Depends(require_role(Role.ADMIN))])
def update_setting(key: str, request: Request, value: dict, db: psycopg.Connection = Depends(get_db)) -> dict:
    from psycopg.types.json import Json

    actor = getattr(request.state, "actor", None) or "anonymous"
    row = db.execute(
        """
        INSERT INTO settings (key, value, updated_by) VALUES (%s, %s, %s)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now(), updated_by = EXCLUDED.updated_by
        RETURNING key, value, updated_at, updated_by
        """,
        (key, Json(value), actor),
    ).fetchone()
    return row
