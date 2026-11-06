"""
Worker Profile API Routes — Task 4.3 (Phase 4).

Manages worker profiles: creation, lookup, skill-level updates,
and session history for individual workers.

Endpoints:
    GET  /api/v1/workers               — List all workers (admin/supervisor)
    POST /api/v1/workers/{id}/profile  — Create or update worker profile
    GET  /api/v1/workers/{id}/profile  — Get worker profile
    GET  /api/v1/workers/{id}/sessions — Worker's session history

Phase 4 — Task 4.3.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routes.deps import get_current_user, get_db, require_roles
from src.database.models import SkillLevel, TrainingSessionLog, User, WorkerProfile

log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/v1/workers",
    tags=["Workers"],
    dependencies=[Depends(get_current_user)],
)


# ── Pydantic models ────────────────────────────────────────────────────────

class WorkerProfileUpsert(BaseModel):
    skill_level: str = "beginner"
    department: str | None = None
    employee_id: str | None = None
    trainer_notes: str | None = None


class WorkerProfileResponse(BaseModel):
    worker_id: int
    name: str
    email: str
    skill_level: str
    department: str | None
    employee_id: str | None
    total_sessions: int
    total_deviations: int
    total_high_severity: int
    last_session_at: str | None
    sessions_to_competency_est: int | None
    trainer_notes: str | None
    created_at: str
    updated_at: str


# ── Helpers ────────────────────────────────────────────────────────────────

def _skill_level_from_str(value: str) -> SkillLevel:
    try:
        return SkillLevel(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid skill_level '{value}'. "
                   f"Valid values: {[e.value for e in SkillLevel]}",
        )


def _profile_to_dict(user: User, profile: WorkerProfile) -> dict[str, Any]:
    return {
        "worker_id": user.id,
        "name": f"{user.first_name} {user.last_name}",
        "email": user.email,
        "skill_level": profile.skill_level.value,
        "department": profile.department or user.department,
        "employee_id": profile.employee_id,
        "total_sessions": profile.total_sessions,
        "total_deviations": profile.total_deviations,
        "total_high_severity": profile.total_high_severity,
        "last_session_at": profile.last_session_at.isoformat()
            if profile.last_session_at else None,
        "sessions_to_competency_est": profile.sessions_to_competency_est,
        "trainer_notes": profile.trainer_notes,
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
    }


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("")
async def list_workers(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    # Optionally lock down to admin/supervisor: current_user=Depends(require_roles("admin","supervisor"))
) -> dict[str, Any]:
    """
    List all workers who have a WorkerProfile.

    Returns basic profile info for each.  Paginated.
    """
    result = await db.execute(
        select(User, WorkerProfile)
        .join(WorkerProfile, WorkerProfile.user_id == User.id)
        .order_by(User.last_name)
        .limit(limit)
        .offset(offset)
    )
    rows = result.all()

    from sqlalchemy import func
    total_result = await db.execute(
        select(func.count(WorkerProfile.id))
    )
    total = total_result.scalar_one() or 0

    return {
        "total": total,
        "workers": [_profile_to_dict(user, profile) for user, profile in rows],
    }


@router.get("/{worker_id}/profile")
async def get_worker_profile(
    worker_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return the worker profile for the given user ID."""
    user_result = await db.execute(select(User).where(User.id == worker_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    profile_result = await db.execute(
        select(WorkerProfile).where(WorkerProfile.user_id == worker_id)
    )
    profile = profile_result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No profile found for worker {worker_id}. Create one first.",
        )

    return _profile_to_dict(user, profile)


@router.post("/{worker_id}/profile", status_code=status.HTTP_200_OK)
async def upsert_worker_profile(
    worker_id: int,
    body: WorkerProfileUpsert,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Create or update a worker profile.

    On first call, creates the profile row.
    On subsequent calls, updates skill_level, department, and trainer notes.
    """
    user_result = await db.execute(select(User).where(User.id == worker_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    skill = _skill_level_from_str(body.skill_level)

    profile_result = await db.execute(
        select(WorkerProfile).where(WorkerProfile.user_id == worker_id)
    )
    profile = profile_result.scalar_one_or_none()

    if profile is None:
        profile = WorkerProfile(
            user_id=worker_id,
            skill_level=skill,
            department=body.department,
            employee_id=body.employee_id,
            trainer_notes=body.trainer_notes,
        )
        db.add(profile)
    else:
        profile.skill_level = skill
        if body.department is not None:
            profile.department = body.department
        if body.employee_id is not None:
            profile.employee_id = body.employee_id
        if body.trainer_notes is not None:
            profile.trainer_notes = body.trainer_notes

    await db.flush()
    await db.refresh(profile)

    log.info("WorkerProfile upserted for user_id=%d skill=%s", worker_id, skill.value)
    return _profile_to_dict(user, profile)


@router.get("/{worker_id}/sessions")
async def get_worker_sessions(
    worker_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return the session history for a worker, most recent first."""
    result = await db.execute(
        select(TrainingSessionLog)
        .where(TrainingSessionLog.worker_id == worker_id)
        .order_by(TrainingSessionLog.ended_at.desc())
        .limit(limit)
        .offset(offset)
    )
    sessions = result.scalars().all()

    from sqlalchemy import func
    total_result = await db.execute(
        select(func.count(TrainingSessionLog.id))
        .where(TrainingSessionLog.worker_id == worker_id)
    )
    total = total_result.scalar_one() or 0

    return {
        "worker_id": worker_id,
        "total": total,
        "sessions": [
            {
                "id": s.id,
                "session_id": s.session_id,
                "sop_id": s.sop_id,
                "sop_name": s.sop_name,
                "started_at": s.started_at.isoformat(),
                "ended_at": s.ended_at.isoformat(),
                "duration_seconds": s.duration_seconds,
                "deviation_count": s.deviation_count,
                "high_severity_count": s.high_severity_count,
                "latency_p95_ms": s.latency_p95_ms,
                "latency_target_met": s.latency_target_met,
            }
            for s in sessions
        ],
    }
