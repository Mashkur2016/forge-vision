"""
Leaderboard API Routes.

Computes ranked list of workers by average accuracy with badge awards.

Badges:
    - Zero Error Day       : at least one session with 0 deviations
    - Speed Demon          : at least one session < 300 seconds
    - Safety First         : at least one session with safety_critical steps passing
                             (proxy: session with 0 high_severity_count and duration > 0)
    - Consistent Performer : 3+ sessions with accuracy >= 85%

Accuracy is derived from deviation_count vs total step count:
    accuracy = max(0, 100 * (1 - deviation_count / max(step_count, 1)))
For simplicity we use a fixed denominator (session step count is implicit in
deviation_count vs duration), so the proxy is:
    per-session accuracy = max(0, 100 - deviation_count * 10)   (capped)
This keeps the prototype self-contained without an extra DB schema.

Endpoints:
    GET /api/v1/leaderboard/   — ranked list (query: period, department)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routes.deps import get_db
from src.database.models import TrainingSessionLog, User, WorkerProfile
from src.intelligence.scoring import session_accuracy

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/leaderboard", tags=["Leaderboard"])


# ── Helpers ────────────────────────────────────────────────────────────────

def _accuracy_for_session(sess: TrainingSessionLog) -> float:
    """Severity-weighted session accuracy (see src/intelligence/scoring.py)."""
    return session_accuracy(sess.deviation_count, sess.high_severity_count)


def _period_cutoff(period: str) -> datetime | None:
    now = datetime.now(timezone.utc)
    if period == "week":
        return now - timedelta(days=7)
    if period == "month":
        return now - timedelta(days=30)
    return None   # all-time


def _compute_badges(sessions: list[TrainingSessionLog], per_session_acc: list[float]) -> list[str]:
    badges: list[str] = []
    if any(s.deviation_count == 0 for s in sessions):
        badges.append("Zero Error Day")
    if any(s.duration_seconds and s.duration_seconds < 300 for s in sessions):
        badges.append("Speed Demon")
    # Safety proxy: at least one session with 0 high-severity events
    if any(s.high_severity_count == 0 and s.duration_seconds > 0 for s in sessions):
        badges.append("Safety First")
    if sum(1 for a in per_session_acc if a >= 85.0) >= 3:
        badges.append("Consistent Performer")
    return badges


# ── Endpoints ──────────────────────────────────────────────────────────────

def _group_of(user: User) -> str:
    """Study group from the synthetic email prefix (control/sim_only/realtime_only/
    hybrid), else 'other'. Group is encoded as `{group}.{role}.{idx}@synthetic...`."""
    email = (user.email or "").lower()
    if email.endswith("@synthetic.forge.local") and "." in email:
        return email.split(".", 1)[0]
    return "other"


@router.get("/")
async def get_leaderboard(
    period: str = Query(default="all", pattern="^(week|month|all)$"),
    department: str | None = Query(default=None),
    group: str | None = Query(default=None, description="Study group (control/sim_only/realtime_only/hybrid)"),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    Return a ranked list of workers for the given period and (optional) department/group.
    """
    cutoff = _period_cutoff(period)
    dept_filter = department.strip().lower() if department else None
    group_filter = group.strip().lower() if group else None

    # Join users + sessions (+ optional profile for department)
    q = (
        select(User, WorkerProfile, TrainingSessionLog)
        .join(TrainingSessionLog, TrainingSessionLog.worker_id == User.id)
        .outerjoin(WorkerProfile, WorkerProfile.user_id == User.id)
    )
    if cutoff is not None:
        q = q.where(TrainingSessionLog.ended_at >= cutoff)

    result = await db.execute(q)
    rows = result.all()

    # Group by user
    per_user: dict[int, dict[str, Any]] = {}
    for user, profile, sess in rows:
        dept = (profile.department if profile else None) or user.department or "—"
        if dept_filter and dept.lower() != dept_filter:
            continue
        grp = _group_of(user)
        if group_filter and grp.lower() != group_filter:
            continue
        entry = per_user.setdefault(user.id, {
            "user_id": user.id,
            "username": f"{user.first_name} {user.last_name}".strip() or user.email,
            "department": dept,
            "group": grp,
            "sessions": [],
            "accuracy": [],
        })
        entry["sessions"].append(sess)
        entry["accuracy"].append(_accuracy_for_session(sess))

    # Compute averages + badges
    ranked: list[dict[str, Any]] = []
    for user_id, info in per_user.items():
        accs = info["accuracy"]
        if not accs:
            continue
        avg_accuracy = round(sum(accs) / len(accs), 1)
        badges = _compute_badges(info["sessions"], accs)
        ranked.append({
            "user_id": user_id,
            "username": info["username"],
            "department": info["department"],
            "group": info.get("group", "other"),
            "avg_accuracy": avg_accuracy,
            "total_sessions": len(info["sessions"]),
            "badges": badges,
        })

    ranked.sort(key=lambda r: (-r["avg_accuracy"], -r["total_sessions"]))
    for rank, row in enumerate(ranked, start=1):
        row["rank"] = rank

    return ranked
