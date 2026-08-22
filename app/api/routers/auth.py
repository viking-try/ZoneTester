import logging

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from starlette.responses import RedirectResponse

from app.api.deps import get_current_user, get_db
from app.auth.local_auth import authenticate_local
from app.auth.oidc import oidc_configured, oauth, upsert_oidc_user
from app.auth.session import create_session_token
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


def _set_session_cookie(response: Response, user: dict) -> None:
    token = create_session_token(
        {"id": user["id"], "email": user["email"], "display_name": user.get("display_name"), "role": user["role"]}
    )
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.env != "development",
    )


@router.post("/login")
def login(body: LoginRequest, response: Response, db: psycopg.Connection = Depends(get_db)) -> dict:
    if oidc_configured():
        raise HTTPException(400, "local login is disabled — OIDC/SSO is configured for this deployment")
    user = authenticate_local(db, body.email, body.password)
    if user is None:
        raise HTTPException(401, "invalid email or password")
    _set_session_cookie(response, user)
    return {"user": user}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(settings.session_cookie_name)
    return {"ok": True}


@router.get("/me")
def me(user: dict | None = Depends(get_current_user)) -> dict:
    return {"user": user, "oidc_enabled": oidc_configured()}


@router.get("/oidc/login")
async def oidc_login(request: Request):
    if not oidc_configured():
        raise HTTPException(404, "OIDC is not configured")
    redirect_uri = str(request.url_for("oidc_callback"))
    return await oauth.oidc.authorize_redirect(request, redirect_uri)


@router.get("/oidc/callback", name="oidc_callback")
async def oidc_callback(request: Request, db: psycopg.Connection = Depends(get_db)):
    if not oidc_configured():
        raise HTTPException(404, "OIDC is not configured")
    token = await oauth.oidc.authorize_access_token(request)
    claims = token.get("userinfo") or {}
    subject = claims.get("sub")
    email = claims.get("email")
    if not subject or not email:
        raise HTTPException(400, "OIDC provider did not return sub/email claims")

    user = upsert_oidc_user(db, subject=subject, email=email, display_name=claims.get("name"))

    redirect = RedirectResponse(url="/")
    _set_session_cookie(redirect, user)
    return redirect
