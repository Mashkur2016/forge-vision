"""
Reports API Routes.

Provides aggregated session summaries and CSV / JSON exports for the
report generator page and DBA thesis data collection.

Endpoints:
    GET /api/v1/reports/session-summary   — aggregated stats
    GET /api/v1/reports/export/csv        — CSV of session rows
    GET /api/v1/reports/export/pdf-data   — JSON structured for PDF rendering
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routes.deps import get_current_user, get_db
from src.database.models import DeviationLog, TrainingSessionLog, User
from src.intelligence.scoring import session_accuracy

log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/v1/reports",
    tags=["Reports"],
    dependencies=[Depends(get_current_user)],
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # Accept "YYYY-MM-DD" or full ISO string
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _apply_date_range(q, start_date: str | None, end_date: str | None):
    """Filter by session start within [start_date, end_date], end-date inclusive.

    Both bounds use ``started_at`` (a session belongs to the day it began) so the
    window is consistent — previously start used started_at and end used ended_at,
    which dropped sessions that spanned the boundary.
    """
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start is not None:
        q = q.where(TrainingSessionLog.started_at >= start)
    if end is not None:
        q = q.where(TrainingSessionLog.started_at < end + timedelta(days=1))
    return q


def _build_filter_query(
    q,
    start_date: str | None,
    end_date: str | None,
    worker_id: int | None,
    sop_id: str | None,
    worker_ids: str | None = None,
    sop_ids: str | None = None,
):
    q = _apply_date_range(q, start_date, end_date)
    if worker_id is not None:
        q = q.where(TrainingSessionLog.worker_id == worker_id)
    if sop_id is not None:
        q = q.where(TrainingSessionLog.sop_id == sop_id)
    if worker_ids:
        ids = [int(x) for x in worker_ids.split(",") if x.strip().isdigit()]
        if ids:
            q = q.where(TrainingSessionLog.worker_id.in_(ids))
    if sop_ids:
        sids = [x.strip() for x in sop_ids.split(",") if x.strip()]
        if sids:
            q = q.where(TrainingSessionLog.sop_id.in_(sids))
    return q


async def _deviation_breakdown(db: AsyncSession, session_ids: list[int]) -> dict[str, Any]:
    """Class×severity breakdown + severity totals for a set of sessions.

    Mirrors the analytics heatmap aggregation so Reports show *which* deviations
    occurred, not just a single total.
    """
    breakdown: list[dict[str, Any]] = []
    severity_totals: dict[str, int] = {"low": 0, "medium": 0, "high": 0}
    if not session_ids:
        return {"deviation_breakdown": breakdown, "severity_totals": severity_totals}
    rows = (await db.execute(
        select(
            DeviationLog.deviation_class,
            DeviationLog.severity,
            func.count(DeviationLog.id),
        )
        .where(
            DeviationLog.session_log_id.in_(session_ids),
            DeviationLog.deviation_class.notlike("emotion_%"),
        )
        .group_by(DeviationLog.deviation_class, DeviationLog.severity)
        .order_by(func.count(DeviationLog.id).desc())
    )).all()
    for cls, sev, cnt in rows:
        breakdown.append({"deviation_class": cls, "severity": sev, "count": int(cnt)})
        if sev in severity_totals:
            severity_totals[sev] += int(cnt)
        else:
            severity_totals[sev] = int(cnt)
    return {"deviation_breakdown": breakdown, "severity_totals": severity_totals}


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/session-summary")
async def session_summary(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    worker_id: int | None = Query(default=None),
    sop_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Aggregated session statistics matching the filter criteria."""
    q = select(TrainingSessionLog)
    q = _build_filter_query(q, start_date, end_date, worker_id, sop_id)
    sessions = (await db.execute(q)).scalars().all()

    total = len(sessions)
    total_dev = sum(s.deviation_count for s in sessions)
    total_high = sum(s.high_severity_count for s in sessions)
    total_duration = sum(s.duration_seconds for s in sessions)

    # Severity-weighted accuracy (src/intelligence/scoring.py)
    accs = [session_accuracy(s.deviation_count, s.high_severity_count) for s in sessions]
    avg_acc = round(sum(accs) / len(accs), 1) if accs else 0.0

    # Deviations by worker (names joined)
    dev_by_worker: dict[int, dict[str, Any]] = {}
    for s in sessions:
        if s.worker_id is None:
            continue
        entry = dev_by_worker.setdefault(s.worker_id, {"worker_id": s.worker_id, "sessions": 0, "deviations": 0})
        entry["sessions"] += 1
        entry["deviations"] += s.deviation_count

    # Resolve worker names
    if dev_by_worker:
        users = (await db.execute(
            select(User).where(User.id.in_(list(dev_by_worker.keys())))
        )).scalars().all()
        for u in users:
            if u.id in dev_by_worker:
                dev_by_worker[u.id]["username"] = f"{u.first_name} {u.last_name}".strip() or u.email

    top_worker = None
    if dev_by_worker:
        ranked = sorted(
            dev_by_worker.values(),
            key=lambda r: (r["deviations"] / max(r["sessions"], 1)),
        )
        top_worker = ranked[0].get("username") if ranked else None

    # Most-deviated step (across DeviationLog joined to filtered sessions)
    session_ids = [s.id for s in sessions]
    top_step = None
    if session_ids:
        step_q = (
            select(DeviationLog.expected_step_name, func.count(DeviationLog.id).label("cnt"))
            .where(
                DeviationLog.session_log_id.in_(session_ids),
                DeviationLog.deviation_class.notlike("emotion_%"),
            )
            .group_by(DeviationLog.expected_step_name)
            .order_by(func.count(DeviationLog.id).desc())
            .limit(1)
        )
        res = (await db.execute(step_q)).first()
        if res:
            top_step = {"step": res[0], "count": res[1]}

    # Accuracy over time (daily buckets)
    accuracy_trend: list[dict[str, Any]] = []
    by_day: dict[str, list[float]] = {}
    for s, a in zip(sessions, accs):
        day = s.ended_at.date().isoformat()
        by_day.setdefault(day, []).append(a)
    for day in sorted(by_day.keys()):
        vals = by_day[day]
        accuracy_trend.append({
            "date": day,
            "avg_accuracy": round(sum(vals) / len(vals), 1),
            "sessions": len(vals),
        })

    breakdown = await _deviation_breakdown(db, session_ids)

    return {
        "filters": {
            "start_date": start_date, "end_date": end_date,
            "worker_id": worker_id, "sop_id": sop_id,
        },
        "total_sessions": total,
        "total_deviations": total_dev,
        "total_high_severity": total_high,
        "total_duration_seconds": round(total_duration, 1),
        "avg_accuracy_pct": avg_acc,
        "top_worker": top_worker,
        "most_deviated_step": top_step,
        "deviations_by_worker": list(dev_by_worker.values()),
        "accuracy_trend": accuracy_trend,
        **breakdown,
    }


@router.get("/aggregate")
async def aggregate_report(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    worker_ids: str | None = Query(default=None, description="Comma-separated worker IDs"),
    sop_ids: str | None = Query(default=None, description="Comma-separated SOP IDs"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Server-side aggregate across multiple workers and SOPs in one query.
    Replaces N×M sequential calls from the report generator UI.
    """
    q = _build_filter_query(
        select(TrainingSessionLog), start_date, end_date, None, None, worker_ids, sop_ids
    )
    sessions = (await db.execute(q)).scalars().all()

    total = len(sessions)
    total_dev = sum(s.deviation_count for s in sessions)
    total_high = sum(s.high_severity_count for s in sessions)
    total_duration = sum(s.duration_seconds for s in sessions)

    accs = [session_accuracy(s.deviation_count, s.high_severity_count) for s in sessions]
    avg_acc = round(sum(accs) / len(accs), 1) if accs else 0.0

    dev_by_worker: dict[int, dict[str, Any]] = {}
    for s in sessions:
        if s.worker_id is None:
            continue
        entry = dev_by_worker.setdefault(s.worker_id, {"worker_id": s.worker_id, "sessions": 0, "deviations": 0})
        entry["sessions"] += 1
        entry["deviations"] += s.deviation_count

    if dev_by_worker:
        users = (await db.execute(
            select(User).where(User.id.in_(list(dev_by_worker.keys())))
        )).scalars().all()
        for u in users:
            if u.id in dev_by_worker:
                dev_by_worker[u.id]["username"] = f"{u.first_name} {u.last_name}".strip() or u.email

    top_worker = None
    if dev_by_worker:
        ranked = sorted(dev_by_worker.values(), key=lambda r: r["deviations"] / max(r["sessions"], 1))
        top_worker = ranked[0].get("username") if ranked else None

    session_ids = [s.id for s in sessions]
    top_step = None
    if session_ids:
        res = (await db.execute(
            select(DeviationLog.expected_step_name, func.count(DeviationLog.id).label("cnt"))
            .where(
                DeviationLog.session_log_id.in_(session_ids),
                DeviationLog.deviation_class.notlike("emotion_%"),
            )
            .group_by(DeviationLog.expected_step_name)
            .order_by(func.count(DeviationLog.id).desc())
            .limit(1)
        )).first()
        if res:
            top_step = {"step": res[0], "count": res[1]}

    by_day: dict[str, list[float]] = {}
    for s, a in zip(sessions, accs):
        day = s.ended_at.date().isoformat()
        by_day.setdefault(day, []).append(a)
    accuracy_trend = [
        {"date": day, "avg_accuracy": round(sum(v) / len(v), 1), "sessions": len(v)}
        for day in sorted(by_day)
        for v in [by_day[day]]
    ]

    breakdown = await _deviation_breakdown(db, session_ids)

    return {
        "filters": {"start_date": start_date, "end_date": end_date,
                    "worker_ids": worker_ids, "sop_ids": sop_ids},
        "total_sessions": total,
        "total_deviations": total_dev,
        "total_high_severity": total_high,
        "total_duration_seconds": round(total_duration, 1),
        "avg_accuracy_pct": avg_acc,
        "top_worker": top_worker,
        "most_deviated_step": top_step,
        "deviations_by_worker": list(dev_by_worker.values()),
        "accuracy_trend": accuracy_trend,
        **breakdown,
    }


@router.get("/export/csv")
async def export_csv(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    worker_id: int | None = Query(default=None),
    sop_id: str | None = Query(default=None),
    worker_ids: str | None = Query(default=None, description="Comma-separated worker IDs"),
    sop_ids: str | None = Query(default=None, description="Comma-separated SOP IDs"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    q = select(TrainingSessionLog).order_by(TrainingSessionLog.ended_at.desc())
    q = _build_filter_query(q, start_date, end_date, worker_id, sop_id, worker_ids, sop_ids)
    sessions = (await db.execute(q)).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "session_id", "worker_id", "sop_id", "sop_name",
        "started_at", "ended_at", "duration_seconds",
        "total_frames", "deviation_count", "high_severity_count",
        "latency_p95_ms", "latency_target_met",
    ])
    for s in sessions:
        writer.writerow([
            s.session_id, s.worker_id or "", s.sop_id, s.sop_name,
            s.started_at.isoformat(), s.ended_at.isoformat(),
            round(s.duration_seconds, 2),
            s.total_frames, s.deviation_count, s.high_severity_count,
            round(s.latency_p95_ms, 2), s.latency_target_met,
        ])

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="session_report.csv"'},
    )


@router.get("/export/pdf-data")
async def export_pdf_data(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    worker_id: int | None = Query(default=None),
    sop_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return the summary JSON — the UI renders this into a printable layout."""
    return await session_summary(start_date, end_date, worker_id, sop_id, db)
