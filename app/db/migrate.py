"""Idempotent migration runner. Applies app/db/migrations/*.sql in filename order, tracked
in schema_migrations. Every migration file must itself be safe to re-run (CREATE TABLE IF NOT
EXISTS / guarded ALTER ... ADD COLUMN IF NOT EXISTS) — this runner also skips files whose
version is already recorded, so re-running is always a no-op either way (belt and suspenders).

Run automatically on every `api` container boot before uvicorn starts (see entrypoint.sh).
"""
import logging
from pathlib import Path

from app.db.pool import close_pool, get_conn
from app.logging_conf import configure_logging

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

_BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def run_migrations() -> list[str]:
    applied: list[str] = []
    with get_conn() as conn:
        conn.execute(_BOOTSTRAP_SQL)
        already = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}

        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = path.stem
            if version in already:
                continue
            sql = path.read_text(encoding="utf-8")
            logger.info("applying migration %s", version)
            conn.execute(sql)
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s) ON CONFLICT DO NOTHING",
                (version,),
            )
            applied.append(version)
    return applied


if __name__ == "__main__":
    configure_logging()
    try:
        result = run_migrations()
        if result:
            logger.info("applied %d migration(s): %s", len(result), ", ".join(result))
        else:
            logger.info("no pending migrations")

        from app.auth.bootstrap import ensure_admin_user
        from app.config import settings
        from app.seed.synthetic_demo import seed_if_empty

        with get_conn() as conn:
            ensure_admin_user(conn)
            if settings.seed_demo_data:
                seed_if_empty(conn)
    finally:
        close_pool()
