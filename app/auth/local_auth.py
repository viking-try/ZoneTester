"""Local username/password auth backend — the fallback path when no OIDC_* env vars are
set. Real bcrypt hashing and a real users table, not a stub: this is meant to be usable for
a small team or a dev/demo deployment, not just a placeholder that always succeeds."""
import bcrypt
import psycopg


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def authenticate_local(conn: psycopg.Connection, email: str, password: str) -> dict | None:
    row = conn.execute(
        """
        SELECT id, email, display_name, role, password_hash, is_active
        FROM users WHERE email = %s AND auth_source = 'local'
        """,
        (email.lower().strip(),),
    ).fetchone()
    if row is None or not row["is_active"] or not row["password_hash"]:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    conn.execute("UPDATE users SET last_login_at = now() WHERE id = %s", (row["id"],))
    return {"id": row["id"], "email": row["email"], "display_name": row["display_name"], "role": row["role"]}


def create_local_user(
    conn: psycopg.Connection, *, email: str, password: str, role: str = "viewer", display_name: str | None = None
) -> dict:
    row = conn.execute(
        """
        INSERT INTO users (email, display_name, role, auth_source, password_hash)
        VALUES (%s, %s, %s, 'local', %s)
        RETURNING id, email, display_name, role
        """,
        (email.lower().strip(), display_name, role, hash_password(password)),
    ).fetchone()
    return row
