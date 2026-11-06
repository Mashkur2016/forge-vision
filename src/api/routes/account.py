"""
Account API Routes — self-service profile management.

Access model:
  - Worker / Trainer / Supervisor: own account only (enforced server-side)
  - Admin: any account via user_id / email query params

Endpoints:
    GET   /api/v1/account/me                  — current user's profile
    PATCH /api/v1/account/me                  — update name/email
    POST  /api/v1/account/change-password     — change password
    POST  /api/v1/account/request-deletion    — GDPR erasure request
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routes.deps import get_current_user, get_db
from src.database.models import TrainingSessionLog, User

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/account", tags=["Account"])

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Schemas ────────────────────────────────────────────────────────────────

class AccountUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class DeletionRequest(BaseModel):
    reason: str | None = None


# ── Helpers ────────────────────────────────────────────────────────────────

async def _resolve_target(
    current_user: User,
    db: AsyncSession,
    user_id: int | None,
    email: str | None,
) -> User:
    """
    Return the target user for the operation.

    Non-admins always operate on themselves regardless of query params.
    Admins may supply user_id or email to target any account.
    """
    if current_user.role.value != "admin":
        return current_user

    # Admin path — look up requested user
    if user_id:
        q = select(User).where(User.id == user_id)
    elif email:
        q = select(User).where(User.email == email.lower())
    else:
        return current_user

    target = (await db.execute(q)).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return target


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(
    user_id: int | None = Query(default=None),
    email: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _resolve_target(current_user, db, user_id, email)

    total_q = await db.execute(
        select(func.count(TrainingSessionLog.id)).where(TrainingSessionLog.worker_id == user.id)
    )
    total_sessions = total_q.scalar_one() or 0

    last_q = await db.execute(
        select(TrainingSessionLog.ended_at)
        .where(TrainingSessionLog.worker_id == user.id)
        .order_by(TrainingSessionLog.ended_at.desc())
        .limit(1)
    )
    last_session = last_q.scalar_one_or_none()

    return {
        "id": user.id,
        "username": f"{user.first_name} {user.last_name}".strip() or user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "role": user.role.value,
        "department": user.department,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "total_sessions": int(total_sessions),
        "last_session_at": last_session.isoformat() if last_session else None,
    }


@router.patch("/me")
async def update_me(
    body: AccountUpdate,
    user_id: int | None = Query(default=None),
    email: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _resolve_target(current_user, db, user_id, email)

    if body.first_name is not None:
        user.first_name = body.first_name.strip()
    if body.last_name is not None:
        user.last_name = body.last_name.strip()
    if body.email is not None:
        exists = await db.execute(
            select(User).where(User.email == body.email.lower(), User.id != user.id)
        )
        if exists.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already in use by another account",
            )
        user.email = body.email.lower()

    await db.flush()
    await db.refresh(user)
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }


@router.post("/change-password")
async def change_password(
    body: PasswordChange,
    user_id: int | None = Query(default=None),
    email: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _resolve_target(current_user, db, user_id, email)

    if not _pwd.verify(body.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )
    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New password must be at least 8 characters",
        )

    user.password_hash = _pwd.hash(body.new_password)
    await db.flush()
    log.info("Password changed for user_id=%d", user.id)
    return {"ok": True, "message": "Password changed successfully"}


@router.post("/request-deletion")
async def request_deletion(
    body: DeletionRequest,
    user_id: int | None = Query(default=None),
    email: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str | int]:
    """GDPR Art.17 erasure request."""
    user = await _resolve_target(current_user, db, user_id, email)

    log.warning(
        "GDPR deletion request: user_id=%d email=%s reason=%r",
        user.id, user.email, body.reason,
    )

    try:
        from src.api.routes.audit import _push_audit_event  # type: ignore[attr-defined]
        _push_audit_event(
            user=user.email,
            action="DELETION_REQUEST",
            resource=f"user:{user.id}",
            detail=body.reason or "No reason provided",
            ip="streamlit",
        )
    except Exception:
        pass

    return {
        "message": "Deletion request recorded. An administrator will process it within 30 days.",
        "user_id": user.id,
    }
