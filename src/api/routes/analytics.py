"""
Analytics API Routes — Task 4.1 (Phase 4).

Provides aggregated performance data for the Streamlit analytics dashboard.

Endpoints:
    GET /api/v1/analytics/summary            — Global system summary
    GET /api/v1/analytics/sessions           — Paginated session history
    GET /api/v1/analytics/worker/{id}        — Per-worker performance stats
    GET /api/v1/analytics/sop/{sop_id}       — Per-SOP performance stats
    GET /api/v1/analytics/competency/{id}    — Enhancement 6: time-to-competency
    GET /api/v1/analytics/deviations/heatmap — Deviation class breakdown

Architecture.md Layer 4: Analytics Dashboard.
Phase 4 — Task 4.1.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routes.deps import get_current_user, get_db, require_roles
from src.database.models import DeviationLog, TrainingSessionLog, User, WorkerProfile
from src.intelligence.competency_predictor import CompetencyPredictor
from src.intelligence.scoring import session_accuracy

log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["Analytics"],
    dependencies=[Depends(get_current_user)],
)


# ── Global summary ─────────────────────────────────────────────────────────

@router.get("/summary")
async def get_global_summary(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """
    Return system-wide aggregate statistics.

    Used by the dashboard home page status cards.
    """
    # One combined aggregate query over the session log — was 6 sequential
    # round-trips to Postgres (≈2.7 s on the pooler); now a single round-trip.
    # COUNT(DISTINCT worker_id) ignores NULLs in SQL, matching the old filter.
    row = (await db.execute(
        select(
            func.count(TrainingSessionLog.id),
            func.coalesce(func.sum(TrainingSessionLog.deviation_count), 0),
            func.coalesce(func.sum(TrainingSessionLog.high_severity_count), 0),
            func.count(func.distinct(TrainingSessionLog.worker_id)),
            func.coalesce(func.avg(TrainingSessionLog.latency_p95_ms), 0.0),
            func.coalesce(
                func.sum(case((TrainingSessionLog.latency_target_met == True, 1), else_=0)), 0
            ),
        )
    )).one()
    total_sessions = int(row[0] or 0)
    total_deviations = int(row[1] or 0)
    total_high = int(row[2] or 0)
    active_workers = int(row[3] or 0)
    avg_latency = float(row[4] or 0.0)
    target_met = int(row[5] or 0)
    target_pass_rate = (target_met / total_sessions * 100) if total_sessions > 0 else 0.0

    return {
        "total_sessions": total_sessions,
        "total_deviations": total_deviations,
        "total_high_severity": total_high,
        "active_workers": active_workers,
        "avg_latency_p95_ms": round(avg_latency, 1),
        "latency_target_pass_rate_pct": round(target_pass_rate, 1),
        "deviations_per_session": round(total_deviations / total_sessions, 2)
            if total_sessions > 0 else 0.0,
    }


# ── Session history ────────────────────────────────────────────────────────

@router.get("/sessions")
async def get_session_history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    worker_id: int | None = Query(default=None),
    sop_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Paginated list of completed training sessions, optionally filtered."""
    q = (
        select(TrainingSessionLog, User)
        .outerjoin(User, TrainingSessionLog.worker_id == User.id)
        .order_by(TrainingSessionLog.ended_at.desc())
    )

    if worker_id is not None:
        q = q.where(TrainingSessionLog.worker_id == worker_id)
    if sop_id is not None:
        q = q.where(TrainingSessionLog.sop_id == sop_id)

    result = await db.execute(q.limit(limit).offset(offset))
    rows = result.all()

    # Total count for pagination
    count_q = select(func.count(TrainingSessionLog.id))
    if worker_id is not None:
        count_q = count_q.where(TrainingSessionLog.worker_id == worker_id)
    if sop_id is not None:
        count_q = count_q.where(TrainingSessionLog.sop_id == sop_id)
    total = (await db.execute(count_q)).scalar_one() or 0

    def _worker_name(user: User | None) -> str:
        if not user:
            return "—"
        full = f"{user.first_name or ''} {user.last_name or ''}".strip()
        return full or user.email or "—"

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "sessions": [
            {
                "id": r.TrainingSessionLog.id,
                "session_id": r.TrainingSessionLog.session_id,
                "worker_id": r.TrainingSessionLog.worker_id,
                "worker_name": _worker_name(r.User),
                "sop_id": r.TrainingSessionLog.sop_id,
                "sop_name": r.TrainingSessionLog.sop_name,
                "started_at": r.TrainingSessionLog.started_at.isoformat(),
                "ended_at": r.TrainingSessionLog.ended_at.isoformat(),
                "duration_seconds": r.TrainingSessionLog.duration_seconds,
                "total_frames": r.TrainingSessionLog.total_frames,
                "deviation_count": r.TrainingSessionLog.deviation_count,
                "high_severity_count": r.TrainingSessionLog.high_severity_count,
                "latency_p95_ms": r.TrainingSessionLog.latency_p95_ms,
                "latency_target_met": r.TrainingSessionLog.latency_target_met,
            }
            for r in rows
        ],
    }


# ── Per-worker analytics ───────────────────────────────────────────────────

@router.get("/worker/{worker_id}")
async def get_worker_analytics(
    worker_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Per-worker performance trend and session history."""
    user_result = await db.execute(select(User).where(User.id == worker_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found.")

    profile_result = await db.execute(
        select(WorkerProfile).where(WorkerProfile.user_id == worker_id)
    )
    profile = profile_result.scalar_one_or_none()

    sessions_result = await db.execute(
        select(TrainingSessionLog)
        .where(TrainingSessionLog.worker_id == worker_id)
        .order_by(TrainingSessionLog.ended_at.asc())
    )
    sessions = sessions_result.scalars().all()

    # Build per-session trend data for charting
    trend = [
        {
            "session_num": i + 1,
            "sop_id": s.sop_id,
            "ended_at": s.ended_at.isoformat(),
            "duration_seconds": s.duration_seconds,
            "deviation_count": s.deviation_count,
            "high_severity_count": s.high_severity_count,
            "latency_p95_ms": s.latency_p95_ms,
        }
        for i, s in enumerate(sessions)
    ]

    # Compute improvement rate (deviation reduction per session)
    improvement_rate = None
    if len(trend) >= 3:
        first_3 = sum(t["deviation_count"] for t in trend[:3]) / 3
        last_3 = sum(t["deviation_count"] for t in trend[-3:]) / 3
        if first_3 > 0:
            improvement_rate = round((first_3 - last_3) / first_3 * 100, 1)

    return {
        "worker_id": worker_id,
        "name": f"{user.first_name} {user.last_name}",
        "email": user.email,
        "role": user.role.value,
        "department": user.department,
        "skill_level": profile.skill_level.value if profile else "beginner",
        "total_sessions": profile.total_sessions if profile else len(sessions),
        "total_deviations": profile.total_deviations if profile else 0,
        "last_session_at": profile.last_session_at.isoformat() if profile and profile.last_session_at else None,
        "sessions_to_competency_est": profile.sessions_to_competency_est if profile else None,
        "improvement_rate_pct": improvement_rate,
        "session_trend": trend,
    }


# ── Per-SOP analytics ──────────────────────────────────────────────────────

@router.get("/sop/{sop_id}")
async def get_sop_analytics(
    sop_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Per-SOP statistics: most common deviations, average completion time."""
    sessions_result = await db.execute(
        select(TrainingSessionLog).where(TrainingSessionLog.sop_id == sop_id)
    )
    sessions = sessions_result.scalars().all()

    if not sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No sessions found for SOP '{sop_id}'.",
        )

    session_ids = [s.id for s in sessions]

    # Deviation class distribution (emotion_* rows excluded — they are affective
    # signals, not deviations)
    dev_result = await db.execute(
        select(DeviationLog.deviation_class, func.count(DeviationLog.id))
        .where(
            DeviationLog.session_log_id.in_(session_ids),
            DeviationLog.deviation_class.notlike("emotion_%"),
        )
        .group_by(DeviationLog.deviation_class)
        .order_by(func.count(DeviationLog.id).desc())
    )
    deviation_breakdown = {row[0]: row[1] for row in dev_result.all()}

    # Most problematic steps
    step_result = await db.execute(
        select(DeviationLog.expected_step_name, func.count(DeviationLog.id))
        .where(
            DeviationLog.session_log_id.in_(session_ids),
            DeviationLog.deviation_class != "CORRECT",
            DeviationLog.deviation_class.notlike("emotion_%"),
        )
        .group_by(DeviationLog.expected_step_name)
        .order_by(func.count(DeviationLog.id).desc())
        .limit(5)
    )
    problem_steps = [
        {"step": row[0], "deviation_count": row[1]} for row in step_result.all()
    ]

    avg_duration = sum(s.duration_seconds for s in sessions) / len(sessions)
    avg_deviations = sum(s.deviation_count for s in sessions) / len(sessions)

    return {
        "sop_id": sop_id,
        "sop_name": sessions[0].sop_name if sessions else sop_id,
        "total_sessions": len(sessions),
        "avg_duration_seconds": round(avg_duration, 1),
        "avg_deviations_per_session": round(avg_deviations, 2),
        "deviation_breakdown": deviation_breakdown,
        "most_problematic_steps": problem_steps,
    }


# ── Time-to-competency (Enhancement 6) ────────────────────────────────────

@router.get("/competency/{worker_id}")
async def get_competency_estimate(
    worker_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Enhancement 6: Predict how many more sessions until the worker
    achieves competency (deviation rate < threshold).
    """
    sessions_result = await db.execute(
        select(TrainingSessionLog)
        .where(TrainingSessionLog.worker_id == worker_id)
        .order_by(TrainingSessionLog.ended_at.asc())
    )
    sessions = sessions_result.scalars().all()

    if len(sessions) < 2:
        return {
            "worker_id": worker_id,
            "sessions_completed": len(sessions),
            "sessions_to_competency_est": None,
            "competency_reached": False,
            "message": "At least 2 sessions required for prediction.",
        }

    deviation_rates = [s.deviation_count / max(s.duration_seconds, 1) for s in sessions]
    predictor = CompetencyPredictor()
    estimate = predictor.predict(deviation_rates)

    # Persist estimate to profile
    profile_result = await db.execute(
        select(WorkerProfile).where(WorkerProfile.user_id == worker_id)
    )
    profile = profile_result.scalar_one_or_none()
    if profile and estimate.get("sessions_to_competency_est") is not None:
        profile.sessions_to_competency_est = estimate["sessions_to_competency_est"]
        await db.flush()

    return {
        "worker_id": worker_id,
        "sessions_completed": len(sessions),
        **estimate,
    }


# ── Deviation heatmap ──────────────────────────────────────────────────────

@router.get("/deviations/heatmap")
async def get_deviation_heatmap(
    sop_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Aggregate deviation counts by class and severity.

    Used to render a heatmap in the analytics dashboard.
    """
    q = select(
        DeviationLog.deviation_class,
        DeviationLog.severity,
        func.count(DeviationLog.id).label("count"),
    ).where(
        DeviationLog.deviation_class.notlike("emotion_%")
    ).group_by(DeviationLog.deviation_class, DeviationLog.severity)

    if sop_id is not None:
        session_ids_result = await db.execute(
            select(TrainingSessionLog.id).where(TrainingSessionLog.sop_id == sop_id)
        )
        session_ids = [r[0] for r in session_ids_result.all()]
        if session_ids:
            q = q.where(DeviationLog.session_log_id.in_(session_ids))

    result = await db.execute(q)
    rows = result.all()

    heatmap: list[dict] = [
        {"deviation_class": r[0], "severity": r[1], "count": r[2]}
        for r in rows
    ]

    return {"heatmap": heatmap, "sop_filter": sop_id}


# ── Emotion breakdown (Enhancement 7) ─────────────────────────────────────────

@router.get("/emotion-summary")
async def get_emotion_summary(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """
    Aggregate emotion/stress signals stored in DeviationLog.

    The emotion detector (Enhancement 7, MediaPipe FaceMesh) records results
    in deviation_class prefixed 'emotion_'. Rows without emotion data return
    empty counts — the Streamlit page renders a placeholder chart in that case.
    """
    result = await db.execute(
        select(DeviationLog.deviation_class, func.count(DeviationLog.id))
        .where(DeviationLog.deviation_class.like("emotion_%"))
        .group_by(DeviationLog.deviation_class)
    )
    rows = result.all()

    emotion_counts: dict[str, int] = {}
    for cls, cnt in rows:
        label = cls.replace("emotion_", "").replace("_", " ").title()
        emotion_counts[label] = int(cnt)

    # Stress score = share of affective samples in a negative state
    # (stressed or fatigued) out of all emotion samples.
    total_emotion = sum(emotion_counts.values())
    negative = emotion_counts.get("Stressed", 0) + emotion_counts.get("Fatigued", 0)
    avg_stress = round(negative / total_emotion, 3) if total_emotion else None

    return {
        "emotion_counts": emotion_counts,
        "avg_stress_score": avg_stress,
        "total_emotion_samples": total_emotion,
    }


# ── Bias audit (per-department accuracy) ──────────────────────────────────────

@router.get("/bias-audit")
async def get_bias_audit(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """
    Per-department average accuracy — used to detect model/training bias.

    Joins TrainingSessionLog → User to get department, then averages the
    severity-weighted per-session accuracy (src/intelligence/scoring.py) per
    department — high-severity deviations count more than minor ones.
    """
    result = await db.execute(
        select(
            User.department,
            TrainingSessionLog.deviation_count,
            TrainingSessionLog.high_severity_count,
        )
        .join(User, TrainingSessionLog.worker_id == User.id)
        .where(TrainingSessionLog.worker_id.isnot(None))
    )
    by_dept: dict[str, list[float]] = {}
    for dept, dev, high in result.all():
        by_dept.setdefault(dept or "Unknown", []).append(session_accuracy(dev, high))

    # Cohort baseline = mean accuracy across ALL sessions. A department is
    # flagged for potential bias when it sits >10% below this baseline
    # (relative rule — robust to the metric's absolute scale).
    all_accs = [a for accs in by_dept.values() for a in accs]
    cohort_mean = round(sum(all_accs) / len(all_accs), 1) if all_accs else 0.0
    threshold = round(cohort_mean * 0.9, 1)

    departments = [
        {
            "department": dept,
            "session_count": len(accs),
            "avg_accuracy": round(sum(accs) / len(accs), 1),
            "flagged": (sum(accs) / len(accs)) < threshold,
        }
        for dept, accs in by_dept.items()
        if accs
    ]
    departments.sort(key=lambda d: -d["avg_accuracy"])

    return {
        "departments": departments,
        "cohort_mean": cohort_mean,
        "flag_threshold": threshold,
    }


# ── Study-group comparison (H1/H2 — operational data) ─────────────────────

def _study_group_of(email: str | None) -> str:
    """Study group from the synthetic email prefix, e.g.
    `control.staff.001@synthetic.forge.local` → 'control'. Non-synthetic → 'other'."""
    e = (email or "").lower()
    if e.endswith("@synthetic.forge.local") and "." in e:
        return e.split(".", 1)[0]
    return "other"


@router.get("/study-groups")
async def get_study_groups(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """
    Compare the four training groups (control / sim_only / realtime_only / hybrid)
    on the seeded operational data — the H1/H2 narrative. Returns per-group
    aggregates plus a per-group learning curve (avg deviations by session index).

    Group is derived from the synthetic user's email prefix. Data is SYNTHETIC.
    """
    from collections import defaultdict

    rows = (await db.execute(
        select(
            TrainingSessionLog.worker_id,
            User.email,
            TrainingSessionLog.deviation_count,
            TrainingSessionLog.high_severity_count,
        )
        .join(User, TrainingSessionLog.worker_id == User.id)
        .where(TrainingSessionLog.worker_id.isnot(None))
        .order_by(TrainingSessionLog.worker_id, TrainingSessionLog.started_at)
    )).all()

    groups: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"workers": set(), "sessions": 0, "dev_total": 0, "high_total": 0, "accs": []}
    )
    curve: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(list))

    last_uid = None
    seq = 0
    for uid, email, dev, high, in rows:
        grp = _study_group_of(email)
        seq = 1 if uid != last_uid else seq + 1
        last_uid = uid
        g = groups[grp]
        g["workers"].add(uid)
        g["sessions"] += 1
        g["dev_total"] += int(dev or 0)
        g["high_total"] += int(high or 0)
        g["accs"].append(session_accuracy(dev, high))
        curve[grp][seq].append(int(dev or 0))

    group_list = []
    for grp, d in groups.items():
        n = d["sessions"]
        group_list.append({
            "group": grp,
            "worker_count": len(d["workers"]),
            "session_count": n,
            "avg_deviations_per_session": round(d["dev_total"] / n, 2) if n else 0.0,
            "avg_accuracy": round(sum(d["accs"]) / len(d["accs"]), 1) if d["accs"] else 0.0,
            "high_severity_rate": round(d["high_total"] / d["dev_total"], 3) if d["dev_total"] else 0.0,
        })
    group_list.sort(key=lambda x: -x["avg_accuracy"])

    learning_curve = []
    for grp, seqmap in curve.items():
        for s, devs in sorted(seqmap.items()):
            if s > 15:  # cap to keep the chart readable
                continue
            learning_curve.append({
                "group": grp,
                "session_seq": s,
                "avg_deviations": round(sum(devs) / len(devs), 2),
                "n": len(devs),
            })

    return {"groups": group_list, "learning_curve": learning_curve}


@router.get("/operational-hypotheses")
async def get_operational_hypotheses(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """
    Run H1 (control vs hybrid) and H2 (sim/realtime/hybrid ANOVA) on the seeded
    OPERATIONAL data — per-worker mean deviations per session, grouped by study
    arm (from the email prefix). Complements the literature-modelled Evaluation
    experiment with the dashboard's own data. H3 needs a post-hoc condition that
    doesn't exist operationally, so it is not run here. Data is SYNTHETIC.
    """
    from collections import defaultdict

    from src.evaluation.hypothesis_tester import HypothesisTester

    rows = (await db.execute(
        select(
            TrainingSessionLog.worker_id,
            User.email,
            TrainingSessionLog.deviation_count,
        )
        .join(User, TrainingSessionLog.worker_id == User.id)
        .where(TrainingSessionLog.worker_id.isnot(None))
    )).all()

    per_worker: dict[int, list[int]] = defaultdict(list)
    worker_group: dict[int, str] = {}
    for uid, email, dev in rows:
        per_worker[uid].append(int(dev or 0))
        worker_group[uid] = _study_group_of(email)

    group_errors: dict[str, list[float]] = defaultdict(list)
    for uid, devs in per_worker.items():
        group_errors[worker_group[uid]].append(sum(devs) / len(devs))

    tester = HypothesisTester()
    out: dict[str, Any] = {
        "unit": "per-worker mean deviations per session",
        "groups_present": {g: len(v) for g, v in sorted(group_errors.items())},
    }
    if len(group_errors.get("control", [])) >= 2 and len(group_errors.get("hybrid", [])) >= 2:
        out["h1"] = tester.test_h1(
            control_errors=group_errors["control"],
            treatment_errors=group_errors["hybrid"],
            label_control="Control (operational)",
            label_treatment="Hybrid (operational)",
        ).to_dict()
    if all(len(group_errors.get(g, [])) >= 2 for g in ("sim_only", "realtime_only", "hybrid")):
        out["h2"] = tester.test_h2(
            sim_only_errors=group_errors["sim_only"],
            realtime_only_errors=group_errors["realtime_only"],
            hybrid_errors=group_errors["hybrid"],
        ).to_dict()
    return out


# ── Per-session deviation drill-down ──────────────────────────────────────

@router.get("/sessions/{session_id}/deviations")
async def get_session_deviations(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return all deviation events for a specific session (for drill-down view)."""
    result = await db.execute(
        select(DeviationLog)
        .join(TrainingSessionLog, DeviationLog.session_log_id == TrainingSessionLog.id)
        .where(
            TrainingSessionLog.session_id == session_id,
            DeviationLog.deviation_class.notlike("emotion_%"),
        )
        .order_by(DeviationLog.event_timestamp)
    )
    rows = result.scalars().all()

    def _iso_ts(ts) -> str | None:
        # event_timestamp is a Float (Unix seconds), not a datetime — convert safely.
        try:
            if ts:
                return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
        except (ValueError, OSError, OverflowError, TypeError):
            pass
        return None

    return [
        {
            "timestamp": _iso_ts(r.event_timestamp),
            "deviation_class": r.deviation_class,
            "severity": r.severity,
            "expected_step": r.expected_step_name,
            "confidence": r.model_confidence,
            "what": r.what,
            "why": r.why,
            "feedback": r.feedback_text,
        }
        for r in rows
    ]
