"""FastAPI app factory. Mounts API routers, the static SPA, and the middleware stack
(audit log -> auth -> security headers, outermost last so headers land on every response
including an auth-rejected 401). Routers are added incrementally as each phase lands."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.logging_conf import configure_logging

configure_logging()

app = FastAPI(title="Zoneguard", version="0.1.0")

WEB_DIR = Path(__file__).parent / "web"

from app.api.routers import (  # noqa: E402
    audit,
    batches,
    cleanup,
    dashboard,
    domains,
    health,
    jobs,
    records,
    reports,
    scan,
    tickets,
    users,
)
from app.api.routers import auth as auth_router  # noqa: E402
from app.api.routers import settings as settings_router  # noqa: E402

for _router in (
    health.router,
    auth_router.router,
    users.router,
    batches.router,
    domains.router,
    records.router,
    scan.router,
    jobs.router,
    cleanup.router,
    dashboard.router,
    audit.router,
    settings_router.router,
    reports.router,
    tickets.router,
):
    app.include_router(_router, prefix="/api")


from app.middleware.audit_log import AuditLogMiddleware  # noqa: E402
from app.middleware.auth import AuthMiddleware  # noqa: E402
from app.middleware.security_headers import SecurityHeadersMiddleware  # noqa: E402

# Used transiently by authlib to hold OAuth redirect state/nonce; unrelated to our own
# session cookie (different cookie name), harmless to add even when OIDC is unconfigured.
app.add_middleware(SessionMiddleware, secret_key=settings.app_secret_key, session_cookie="zoneguard_oidc_state")
app.add_middleware(AuditLogMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


app.mount("/", NoCacheStaticFiles(directory=str(WEB_DIR), html=True), name="web")
