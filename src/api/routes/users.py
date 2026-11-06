"""
Admin User Management API Routes.

Endpoints:
    GET   /api/v1/admin/users/        — list all users with session counts
    PATCH /api/v1/admin/users/{id}    — update role / is_active
    POST  /api/v1/admin/users/invite  — mock user invitation

Note: for the prototype these are open endpoints; production would gate
behind `Depends(require_roles("admin"))`.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routes.deps import get_current_user, get_db, require_roles
from src.database.models import TrainingSessionLog, User, UserRole, WorkerProfile

log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/v1/admin/users",
    tags=["Admin / Users"],
    dependencies=[Depends(require_roles("admin"))],
)


# ── Schemas ────────────────────────────────────────────────────────────────

class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    first_name: str | None = None
    last_name: str | None = None
    department: str | None = None


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = "staff"


# ── Helpers ────────────────────────────────────────────────────────────────

def _role_from_str(value: str) -> UserRole:
    try:
        return UserRole(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid role '{value}'. Valid: {[r.value for r in UserRole]}",
        )


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/")
async def list_users(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    """
    Return all users joined with their session count and profile (if any).
    """
    # Build a subquery of session counts
    session_count_sq = (
        select(
            TrainingSessionLog.worker_id,
            func.count(TrainingSessionLog.id).label("session_count"),
            func.max(TrainingSessionLog.ended_at).label("last_session_at"),
        )
        .group_by(TrainingSessionLog.worker_id)
        .subquery()
    )

    q = (
        select(User, session_count_sq.c.session_count, session_count_sq.c.last_session_at, WorkerProfile)
        .outerjoin(session_count_sq, User.id == session_count_sq.c.worker_id)
        .outerjoin(WorkerProfile, WorkerProfile.user_id == User.id)
        .order_by(User.id.asc())
    )
    result = await db.execute(q)
    rows = result.all()

    out: list[dict[str, Any]] = []
    for user, session_count, last_session_at, profile in rows:
        out.append({
            "id": user.id,
            "username": f"{user.first_name} {user.last_name}".strip() or user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "role": user.role.value,
            "is_active": user.is_active,
            "department": (profile.department if profile else None) or user.department,
            "session_count": int(session_count or 0),
            "last_session_at": last_session_at.isoformat() if last_session_at else None,
            "created_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
        })
    return out


@router.patch("/{user_id}")
async def update_user(
    user_id: int,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.role is not None:
        user.role = _role_from_str(body.role)
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.first_name is not None:
        user.first_name = body.first_name
    if body.last_name is not None:
        user.last_name = body.last_name
    if body.department is not None:
        user.department = body.department or None

    await db.flush()
    await db.refresh(user)
    log.info("User %s updated: role=%s active=%s", user_id, user.role.value, user.is_active)
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role.value,
        "is_active": user.is_active,
    }


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account.",
        )
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await db.delete(user)
    log.info("User %s deleted by admin %s", user_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/invite")
async def invite_user(body: InviteRequest) -> dict[str, Any]:
    """
    Mock invite — in production this would send a signed invite email.
    For the prototype we just echo a success response.
    """
    _role_from_str(body.role)  # validate early
    log.info("Invite requested for %s as %s", body.email, body.role)
    return {"message": f"Invite sent to {body.email}", "role": body.role}
