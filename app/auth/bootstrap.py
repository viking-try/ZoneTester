"""First-boot admin bootstrap. Never ships a default credential: if OIDC is configured,
nothing to do (the IdP owns identity). Otherwise, if the users table is empty, an admin user
is created with either an operator-supplied ADMIN_BOOTSTRAP_PASSWORD or a freshly generated
random password that is logged once so whoever stood up the deployment can retrieve it from
container logs — never hardcoded, never stored in the repo."""
import logging
import os
import secrets

import psycopg

from app.auth.local_auth import create_local_user
from app.config import settings
from app.constants import Role

logger = logging.getLogger(__name__)


def ensure_admin_user(conn: psycopg.Connection) -> None:
    if settings.oidc_enabled:
        return

    count = conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"]
    if count > 0:
        return

    email = os.environ.get("ADMIN_BOOTSTRAP_EMAIL", "admin@zoneguard.local")
    password = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD")
    generated = password is None
    if generated:
        password = secrets.token_urlsafe(18)

    create_local_user(conn, email=email, password=password, role=Role.ADMIN, display_name="Admin")

    if generated:
        logger.warning(
            "=== ZONEGUARD FIRST-BOOT ADMIN CREATED ===\n"
            "  email:    %s\n"
            "  password: %s\n"
            "This password is shown only this once — store it now. Set ADMIN_BOOTSTRAP_PASSWORD "
            "before first boot to choose your own instead.",
            email,
            password,
        )
    else:
        logger.info("admin user %s created from ADMIN_BOOTSTRAP_PASSWORD", email)
