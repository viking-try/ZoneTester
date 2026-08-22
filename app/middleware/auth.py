"""Resolves the session cookie into request.state.user/actor on every request, and enforces
that authentication is mandatory for the API (spec: "do not ship an unauthenticated app").
Unauthenticated access is allowed only for: the login/OIDC endpoints, /api/health, and the
static SPA shell itself (the SPA's own JS calls /api/auth/me on load and redirects to a login
view client-side if it gets a 401 — the server-side gate is what actually matters).

The full user identity (id/email/display_name/role) is embedded in the signed session token
itself rather than re-queried from the DB on every request, trading a same-session role
change taking effect only after re-login (or session expiry) for avoiding a DB round-trip per
request — an acceptable tradeoff at this scale."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.auth.session import verify_session_token
from app.config import settings

_PUBLIC_PREFIXES = ("/api/auth/", "/api/health")


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = request.cookies.get(settings.session_cookie_name)
        user = verify_session_token(token) if token else None

        request.state.user = user
        request.state.actor = user["email"] if user else None

        if request.url.path.startswith("/api/") and not request.url.path.startswith(_PUBLIC_PREFIXES):
            if user is None:
                return JSONResponse({"detail": "authentication required"}, status_code=401)

        return await call_next(request)
