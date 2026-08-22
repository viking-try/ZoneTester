"""Block until Postgres accepts connections, then exit 0. Used by entrypoint.sh before
migrations/uvicorn/celery start, so a fast-starting api/worker container doesn't crash-loop
against a Postgres container that's still initializing."""
import os
import sys
import time

import psycopg


def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("wait_for_postgres: DATABASE_URL not set, skipping wait", file=sys.stderr)
        return 0

    deadline = time.monotonic() + float(os.environ.get("DB_WAIT_TIMEOUT_SECONDS", "60"))
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(dsn, connect_timeout=3) as conn:
                conn.execute("SELECT 1")
            print("wait_for_postgres: database is ready", file=sys.stderr)
            return 0
        except Exception as exc:  # noqa: BLE001 - genuinely want to retry on anything here
            last_err = exc
            time.sleep(1.5)

    print(f"wait_for_postgres: timed out waiting for database: {last_err}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
