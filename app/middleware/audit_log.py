"""Logs every non-GET API call: actor, method, endpoint, path, status, duration. Runs after
AuthMiddleware in the stack (so request.state.actor is already populated) and writes on its
own short-lived connection rather than piggy-backing on the route handler's — an audit write
must not be skipped just because the handler's transaction rolled back."""
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.db.pool import get_conn


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        if request.method != "GET" and request.url.path.startswith("/api/"):
            actor = getattr(request.state, "actor", None) or "anonymous"
            client_ip = request.client.host if request.client else None
            try:
                with get_conn() as conn:
                    conn.execute(
                        """
                        INSERT INTO audit (actor, method, endpoint, path, status_code, duration_ms, ip)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            actor,
                            request.method,
                            request.url.path.split("?")[0],
                            str(request.url.path),
                            response.status_code,
                            duration_ms,
                            client_ip,
                        ),
                    )
            except Exception:  # noqa: BLE001 - an audit-log failure must never break the actual request  # nosec B110
                pass

        return response
