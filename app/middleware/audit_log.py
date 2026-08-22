"""Logs every non-GET API call: actor, method, endpoint, path, status, duration. Runs after
AuthMiddleware in the stack (so request.state.actor is already populated) and writes on its
own short-lived connection rather than piggy-backing on the route handler's — an audit write
must not be skipped just because the handler's transaction rolled back.

The write is dispatched via run_in_threadpool rather than called directly: get_conn()/
conn.execute() are synchronous (blocking) calls, and this middleware's dispatch() runs on the
asyncio event loop — calling a blocking DB round-trip directly there would stall every other
in-flight request on this worker for the duration of that write."""
import logging
import time

from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.db.pool import get_conn

logger = logging.getLogger(__name__)


def _write_audit_row(*, actor, method, endpoint, path, status_code, duration_ms, ip) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO audit (actor, method, endpoint, path, status_code, duration_ms, ip)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (actor, method, endpoint, path, status_code, duration_ms, ip),
        )


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        if request.method != "GET" and request.url.path.startswith("/api/"):
            actor = getattr(request.state, "actor", None) or "anonymous"
            client_ip = request.client.host if request.client else None
            try:
                await run_in_threadpool(
                    _write_audit_row,
                    actor=actor,
                    method=request.method,
                    endpoint=request.url.path.split("?")[0],
                    path=str(request.url.path),
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    ip=client_ip,
                )
            except Exception:  # noqa: BLE001 - an audit-log failure must never break the actual request
                logger.exception("failed to write audit row for %s %s", request.method, request.url.path)

        return response
