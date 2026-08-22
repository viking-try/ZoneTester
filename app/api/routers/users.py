"""Admin-only user management (RBAC: viewer/operator/admin). Local-auth users get a password
set here; OIDC users are provisioned automatically on first login (app.auth.oidc.upsert_oidc_user)
and only their role is editable here."""
import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from app.api.deps import get_db, require_role
from app.auth.local_auth import create_local_user
from app.constants import Role

router = APIRouter(prefix="/users", tags=["users"])


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = Role.VIEWER
    display_name: str | None = None


class UpdateRoleRequest(BaseModel):
    role: str


@router.get("", dependencies=[Depends(require_role(Role.ADMIN))])
def list_users(db: psycopg.Connection = Depends(get_db)) -> dict:
    rows = db.execute(
        "SELECT id, email, display_name, role, auth_source, is_active, created_at, last_login_at FROM users ORDER BY email"
    ).fetchall()
    return {"users": rows}


@router.post("", dependencies=[Depends(require_role(Role.ADMIN))])
def create_user(body: CreateUserRequest, db: psycopg.Connection = Depends(get_db)) -> dict:
    if body.role not in (Role.VIEWER, Role.OPERATOR, Role.ADMIN):
        raise HTTPException(400, "invalid role")
    try:
        return create_local_user(
            db, email=body.email, password=body.password, role=body.role, display_name=body.display_name
        )
    except psycopg.errors.UniqueViolation as exc:
        raise HTTPException(409, "a user with this email already exists") from exc


@router.put("/{user_id}/role", dependencies=[Depends(require_role(Role.ADMIN))])
def update_role(user_id: int, body: UpdateRoleRequest, db: psycopg.Connection = Depends(get_db)) -> dict:
    if body.role not in (Role.VIEWER, Role.OPERATOR, Role.ADMIN):
        raise HTTPException(400, "invalid role")
    row = db.execute(
        "UPDATE users SET role = %s WHERE id = %s RETURNING id, email, role", (body.role, user_id)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "user not found")
    return row


@router.post("/{user_id}/deactivate", dependencies=[Depends(require_role(Role.ADMIN))])
def deactivate_user(user_id: int, db: psycopg.Connection = Depends(get_db)) -> dict:
    row = db.execute(
        "UPDATE users SET is_active = false WHERE id = %s RETURNING id, email, is_active", (user_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "user not found")
    return row
