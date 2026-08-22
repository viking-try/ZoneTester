"""OIDC/SSO client (authlib), active only when OIDC_ISSUER/OIDC_CLIENT_ID/OIDC_CLIENT_SECRET
are all set. This is the intended path for any real deployment; local_auth.py is the dev/demo
fallback when these are unset. Both are real code paths — neither is a stub."""
from authlib.integrations.starlette_client import OAuth

from app.config import settings

oauth = OAuth()

if settings.oidc_enabled:
    oauth.register(
        name="oidc",
        server_metadata_url=f"{settings.oidc_issuer.rstrip('/')}/.well-known/openid-configuration",
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret,
        client_kwargs={"scope": "openid email profile"},
    )


def oidc_configured() -> bool:
    return settings.oidc_enabled


def upsert_oidc_user(conn, *, subject: str, email: str, display_name: str | None) -> dict:
    """First OIDC login for a given subject gets the default 'viewer' role; an admin
    promotes from there via the users API. Existing users are matched by (auth_source,
    oidc_subject), not by email alone, so a spoofed email claim from a misconfigured IdP
    can't silently take over an existing account."""
    row = conn.execute(
        "SELECT id, email, display_name, role FROM users WHERE auth_source = 'oidc' AND oidc_subject = %s",
        (subject,),
    ).fetchone()
    if row:
        conn.execute("UPDATE users SET last_login_at = now(), email = %s WHERE id = %s", (email, row["id"]))
        return row

    row = conn.execute(
        """
        INSERT INTO users (email, display_name, role, auth_source, oidc_subject, last_login_at)
        VALUES (%s, %s, 'viewer', 'oidc', %s, now())
        RETURNING id, email, display_name, role
        """,
        (email, display_name, subject),
    ).fetchone()
    return row
