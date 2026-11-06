"""
Detailed system health endpoint.

Unlike /health (simple liveness), /api/v1/health/detailed probes the DB,
the LLM provider settings and counts storage metrics.

Endpoint:
    GET /api/v1/health/detailed
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routes.deps import get_db
from src.database.models import (
    DeviationLog,
    LLMSettings,
    TrainingSessionLog,
    User,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/health", tags=["Health"])

_START_TS = time.time()


@router.get("/detailed")
async def detailed_health(
    light: bool = False, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Return a structured health report covering API, DB, LLM and storage.
    All probes are best-effort — failures are reported, not raised.

    `light=true` skips the storage COUNT(*) queries (3 full-table counts) for
    callers like the dashboard that only need API/DB/LLM status — much faster.
    """
    report: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "api": {"status": "ok", "uptime_seconds": round(time.time() - _START_TS, 1)},
    }

    # ── DB probe ──────────────────────────────────────────────────────────
    db_status: dict[str, Any] = {"status": "error", "query_time_ms": None, "error": None}
    t0 = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
        db_status["query_time_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        db_status["status"] = "ok"
    except Exception as exc:
        db_status["error"] = str(exc)[:200]
    report["db"] = db_status

    # ── LLM probe (non-blocking — just read saved settings) ───────────────
    llm_status: dict[str, Any] = {
        "status": "not_configured",
        "provider": None,
        "model": None,
        "last_test_ms": None,
    }
    try:
        row = (await db.execute(
            select(LLMSettings).where(LLMSettings.is_active == True).limit(1)
        )).scalar_one_or_none()
        if row is not None:
            llm_status["provider"] = row.provider
            llm_status["model"] = row.model_name
            llm_status["status"] = "ok" if row.tested_ok else "untested"
    except Exception as exc:
        llm_status["status"] = "error"
        llm_status["error"] = str(exc)[:200]
    report["llm"] = llm_status

    # ── Active sessions ───────────────────────────────────────────────────
    active_sessions = 0
    try:
        from src.api.routes.session import _active_sessions
        active_sessions = len(_active_sessions)
    except Exception:
        pass
    report["active_sessions"] = active_sessions

    # ── Storage metrics (skipped in light mode — 3 full-table COUNTs) ───────
    if light:
        return report
    storage: dict[str, Any] = {"sop_count": 0, "session_count": 0, "deviation_count": 0, "user_count": 0}
    try:
        # SOP count from filesystem
        from src.api.routes.sops import _list_sop_paths
        storage["sop_count"] = len(_list_sop_paths())
    except Exception:
        pass
    try:
        storage["session_count"] = int(
            (await db.execute(select(func.count(TrainingSessionLog.id)))).scalar_one() or 0
        )
        storage["deviation_count"] = int(
            (await db.execute(select(func.count(DeviationLog.id)))).scalar_one() or 0
        )
        storage["user_count"] = int(
            (await db.execute(select(func.count(User.id)))).scalar_one() or 0
        )
    except Exception as exc:
        storage["error"] = str(exc)[:200]
    report["storage"] = storage

    return report
