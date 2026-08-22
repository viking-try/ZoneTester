"""Shared FastAPI dependencies: get_db yields a pooled connection per request; get_current_user
reads the identity the auth middleware already resolved onto request.state (see
app/middleware/auth.py) — the middleware is what actually verifies the session cookie, so
this dependency is just a typed accessor plus the 401/403 raising for protected routes."""
from typing import Iterator

import psycopg
from fastapi import Depends, HTTPException, Request

from app.auth.rbac import user_has_role
from app.db.pool import get_conn


def get_db() -> Iterator[psycopg.Connection]:
    with get_conn() as conn:
        yield conn


def get_current_user(request: Request) -> dict | None:
    return getattr(request.state, "user", None)


def require_user(request: Request) -> dict:
    user = get_current_user(request)
    if user is None:
        raise HTTPException(401, "authentication required")
    return user


def require_role(required_role: str):
    def _dep(user: dict = Depends(require_user)) -> dict:
        if not user_has_role(user, required_role):
            raise HTTPException(403, f"requires {required_role} role or higher")
        return user

    return _dep
