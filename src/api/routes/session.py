"""
Session API Routes — Tasks 3.4 (Phase 3) + 4.2 (Phase 4).

REST endpoints for session lifecycle + WebSocket for real-time streaming.
Phase 4 adds: persistent session logging to PostgreSQL on session stop.

REST Endpoints:
    POST  /api/v1/session/start              — Start a new training session
    POST  /api/v1/session/{id}/stop          — Stop session; persists log to DB
    GET   /api/v1/session/{id}/summary       — Session summary report
    GET   /api/v1/session/{id}/status        — Quick status check
    GET   /api/v1/session/active             — List all active session IDs

WebSocket:
    WS    /api/v1/session/ws/{id}            — Stream real-time frames + events

WebSocket JSON message schema:
    { "type": "frame",     "session_id": "...", "timestamp": 1.23, "data": {...} }
    { "type": "deviation", "session_id": "...", "timestamp": 1.23, "data": {...} }
    { "type": "feedback",  "session_id": "...", "timestamp": 1.23, "data": {...} }
    { "type": "status",    "session_id": "...", "timestamp": 1.23, "data": {...} }

Architecture.md Layer 4: Real-Time Worker Guidance.
Rules.md §2: GDPR — no frames persisted; video processed in memory only.
"""
from __future__ import annotations

import glob
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routes.deps import get_db, get_current_user
from src.intelligence.feedback_engine import generate_training_feedback
from src.intelligence.sop_detector import SOPDeviationEvent
from src.realtime.camera_capture import CameraConfig
from src.realtime.inference_pipeline import InferenceConfig
from src.realtime.session_manager import SessionConfig, TrainingSession
from src.database.models import DeviationLog, TrainingSessionLog, WorkerProfile
from src.simulation.sop_parser import load_sop
from src.training.models import build_sequence_model

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/session", tags=["Session"])

# ── In-memory session registry ─────────────────────────────────────────────
# Keyed by session_id. Phase 4 will persist to PostgreSQL.

_active_sessions: dict[str, TrainingSession] = {}


# ── Pydantic models ────────────────────────────────────────────────────────

class StartSessionRequest(BaseModel):
    sop_id: str
    camera_source: int | str = 0
    tts_enabled: bool = False


class StartSessionResponse(BaseModel):
    session_id: str
    sop_name: str
    status: str


# ── Helper: load SOP by ID ─────────────────────────────────────────────────

def _load_sop(sop_id: str):
    """Locate and parse the SOP YAML/JSON file matching sop_id."""
    for path in glob.glob("data/sops/*.yaml") + glob.glob("data/sops/*.json"):
        try:
            sop = load_sop(path)
            if sop.id == sop_id:
                return sop
        except Exception:
            continue
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"SOP '{sop_id}' not found in data/sops/.",
    )


# ── Helper: build LLM feedback callback ───────────────────────────────────

def _make_feedback_fn(db: AsyncSession):
    """
    Return an async callback that calls the LLM feedback engine
    for a given SOPDeviationEvent.

    The db session is captured in the closure so it is reused for the
    lifetime of the training session.
    """
    async def _fn(event: SOPDeviationEvent) -> str:
        return await generate_training_feedback(
            db=db,
            sop_name=event.sop_name,
            detected_action=event.what,
            error_type=event.deviation_class,
            step_id=event.expected_step_id or 0,
            step_description=event.expected_step_name,
            confidence=event.model_confidence,
        )
    return _fn


# ── Helper: get session or 404 ─────────────────────────────────────────────

def _get_session(session_id: str) -> TrainingSession:
    session = _active_sessions.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return session


# ── REST: Start session ────────────────────────────────────────────────────

@router.post("/start", response_model=StartSessionResponse, status_code=201)
async def start_session(
    request: StartSessionRequest,
    db: AsyncSession = Depends(get_db),
) -> StartSessionResponse:
    """
    Start a new real-time training session.

    Opens the camera, loads the trained ActionRecognizer, and begins
    streaming frames through the full CV + LLM pipeline.
    """
    sop = _load_sop(request.sop_id)

    # Build the SOPSequenceModel (used by SOPDetector for deviation classification)
    sequence_model = build_sequence_model(
        config={
            "sequence_model": {
                "input_dim": 25,
                "hidden_size": 128,
                "num_layers": 2,
                "dropout": 0.2,
                "num_deviation_classes": 6,
            }
        },
        num_action_classes=25,
    )

    config = SessionConfig(
        sop=sop,
        camera=CameraConfig(source=request.camera_source),
        inference=InferenceConfig(),
        tts_enabled=request.tts_enabled,
    )

    feedback_fn = _make_feedback_fn(db)
    session = TrainingSession(config=config, feedback_fn=feedback_fn)

    try:
        await session.start(sequence_model)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    _active_sessions[session.session_id] = session
    log.info("Session %s started | SOP: %s", session.session_id, sop.name)

    return StartSessionResponse(
        session_id=session.session_id,
        sop_name=sop.name,
        status=session.status.value,
    )


# ── Helper: persist completed session to DB (Task 4.2) ────────────────────

async def _persist_session(
    summary: dict[str, Any],
    session,
    db: AsyncSession,
    worker_id: int | None,
) -> None:
    """
    Save a completed TrainingSession to PostgreSQL.

    Creates one TrainingSessionLog row and one DeviationLog row per
    deviation event.  Also updates the worker's WorkerProfile aggregates.
    Rules.md §2: only stats and text are persisted — no video frames.
    """
    from sqlalchemy import select

    now = datetime.now(timezone.utc)
    duration = summary.get("duration_seconds", 0.0)

    from src.config import settings as app_settings
    log_row = TrainingSessionLog(
        session_id=summary["session_id"],
        worker_id=worker_id,
        sop_id=summary["sop_id"],
        sop_name=summary["sop_name"],
        started_at=datetime.fromtimestamp(
            session._start_time if session._start_time else 0,
            tz=timezone.utc,
        ),
        ended_at=now,
        duration_seconds=duration,
        total_frames=summary.get("total_frames", 0),
        actual_fps=summary.get("actual_fps", 0.0),
        deviation_count=summary.get("deviations", 0),
        high_severity_count=summary.get("high_severity_count", 0),
        latency_p95_ms=summary.get("latency_ms", {}).get("p95", 0.0),
        latency_target_met=summary.get("latency_target_met", True),
        llm_provider=getattr(app_settings, "LLM_PROVIDER", None),
        llm_model=getattr(app_settings, "LLM_MODEL", None),
    )
    db.add(log_row)
    await db.flush()   # assigns log_row.id

    # Persist individual deviation events
    for event_dict in summary.get("events", []):
        dev = DeviationLog(
            session_log_id=log_row.id,
            event_timestamp=event_dict.get("timestamp", 0.0),
            deviation_class=event_dict.get("deviation_class", "UNKNOWN"),
            severity=event_dict.get("severity", "low"),
            expected_step_name=event_dict.get("expected_step_name", ""),
            model_confidence=event_dict.get("model_confidence", 0.0),
            what=event_dict.get("what", ""),
            why=event_dict.get("why", ""),
        )
        db.add(dev)

    # Update WorkerProfile aggregates if a worker is linked
    if worker_id is not None:
        result = await db.execute(
            select(WorkerProfile).where(WorkerProfile.user_id == worker_id)
        )
        profile = result.scalar_one_or_none()
        if profile:
            profile.total_sessions += 1
            profile.total_deviations += summary.get("deviations", 0)
            profile.total_high_severity += summary.get("high_severity_count", 0)
            profile.last_session_at = now

    await db.flush()


# ── REST: Log a browser (WebSocket) live session ───────────────────────────

class ClientDeviationIn(BaseModel):
    """One deviation event captured during a browser-webcam live session."""
    timestamp: float = 0.0
    deviation_class: str = "deviation"
    severity: str = "low"
    expected_step_name: str = ""
    model_confidence: float = 0.0
    what: str = ""
    why: str = ""
    feedback_text: str | None = None


class ClientSessionLogIn(BaseModel):
    """
    A completed browser-webcam (WebSocket) live training session, posted from the
    Streamlit Live Training page so it is recorded like a server-camera session.

    Rules.md §2 / GDPR: only metadata + deviation events are stored — never frames.
    This is exactly what the in-app consent notice tells the worker is persisted.
    """
    session_id: str
    sop_id: str
    sop_name: str
    started_at: float = 0.0          # unix timestamp
    duration_seconds: float = 0.0
    latency_p95_ms: float = 0.0
    deviations: list[ClientDeviationIn] = []


@router.post("/log")
async def log_client_session(
    payload: ClientSessionLogIn,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, Any]:
    """
    Persist a browser-side live training session (WebSocket camera path, which has
    no server-side session object) to PostgreSQL, so it appears in Session History,
    the dashboard activity feed, and the worker's analytics — same as a server
    session. Attributed to the authenticated user. Idempotent per session_id.
    """
    from sqlalchemy import select

    existing = await db.execute(
        select(TrainingSessionLog).where(TrainingSessionLog.session_id == payload.session_id)
    )
    if existing.scalar_one_or_none() is not None:
        return {"status": "exists", "session_id": payload.session_id}

    now = datetime.now(timezone.utc)
    high = sum(1 for d in payload.deviations if d.severity == "high")
    from src.config import settings as app_settings

    log_row = TrainingSessionLog(
        session_id=payload.session_id,
        worker_id=current_user.id,
        sop_id=payload.sop_id,
        sop_name=payload.sop_name[:200],
        started_at=datetime.fromtimestamp(payload.started_at or now.timestamp(), tz=timezone.utc),
        ended_at=now,
        duration_seconds=payload.duration_seconds,
        total_frames=0,
        actual_fps=0.0,
        deviation_count=len(payload.deviations),
        high_severity_count=high,
        latency_p95_ms=payload.latency_p95_ms,
        latency_target_met=(payload.latency_p95_ms <= 2000.0),
        llm_provider=getattr(app_settings, "LLM_PROVIDER", None),
        llm_model=getattr(app_settings, "LLM_MODEL", None),
    )
    db.add(log_row)
    await db.flush()   # assigns log_row.id

    for d in payload.deviations:
        db.add(DeviationLog(
            session_log_id=log_row.id,
            event_timestamp=d.timestamp,
            deviation_class=d.deviation_class[:50],
            severity=d.severity[:20],
            expected_step_name=d.expected_step_name[:200],
            model_confidence=d.model_confidence,
            what=d.what,
            why=d.why,
            feedback_text=d.feedback_text,
        ))

    result = await db.execute(
        select(WorkerProfile).where(WorkerProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if profile:
        profile.total_sessions += 1
        profile.total_deviations += len(payload.deviations)
        profile.total_high_severity += high
        profile.last_session_at = now

    await db.flush()   # get_db commits on success
    return {"status": "saved", "session_log_id": log_row.id, "session_id": payload.session_id}


# ── REST: Stop session ─────────────────────────────────────────────────────

@router.post("/{session_id}/stop")
async def stop_session(
    session_id: str,
    worker_id: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Stop a running session, persist the log to PostgreSQL, and return summary.

    Args:
        worker_id: Optional user ID to link the session to a worker profile.
    """
    session = _get_session(session_id)
    await session.stop()
    summary = session.summary()
    _active_sessions.pop(session_id, None)

    # Persist to DB (Phase 4 — Task 4.2)
    try:
        await _persist_session(summary, session, db, worker_id)
    except Exception as exc:
        log.warning("Session %s: DB persistence failed: %s", session_id, exc)

    log.info(
        "Session %s stopped | frames=%d deviations=%d",
        session_id,
        summary.get("total_frames", 0),
        summary.get("deviations", 0),
    )
    return summary


# ── REST: Session summary ──────────────────────────────────────────────────

@router.get("/{session_id}/summary")
async def get_session_summary(session_id: str) -> dict[str, Any]:
    """Return the current session summary (works for running or stopped sessions)."""
    return _get_session(session_id).summary()


# ── REST: Session status ───────────────────────────────────────────────────

@router.get("/{session_id}/status")
async def get_session_status(session_id: str) -> dict[str, str]:
    """Quick status check."""
    session = _get_session(session_id)
    return {"session_id": session_id, "status": session.status.value}


# ── REST: List active sessions ─────────────────────────────────────────────

@router.get("/active")
async def list_active_sessions() -> dict[str, list[str]]:
    """List all currently active session IDs."""
    return {"session_ids": list(_active_sessions.keys())}


# ── WebSocket: Real-time stream ────────────────────────────────────────────

@router.websocket("/ws/{session_id}")
async def websocket_stream(websocket: WebSocket, session_id: str) -> None:
    """
    Stream real-time session messages to a connected WebSocket client.

    The client receives JSON messages for:
      - "frame"     — JPEG-encoded camera frame + CV metadata
      - "deviation" — Detected SOP deviation event
      - "feedback"  — LLM-generated corrective instruction
      - "status"    — Session lifecycle changes

    The stream ends when the session reaches COMPLETE or ERROR state.
    """
    await websocket.accept()

    session = _active_sessions.get(session_id)
    if session is None:
        await websocket.send_text(json.dumps({
            "type": "error",
            "data": {"message": f"Session '{session_id}' not found."},
        }))
        await websocket.close(code=1008)
        return

    log.info("WebSocket connected | session=%s", session_id)

    try:
        async for msg in session.messages():
            payload = json.dumps({
                "type": msg.type,
                "session_id": msg.session_id,
                "timestamp": msg.timestamp,
                "data": msg.data,
            })
            await websocket.send_text(payload)

    except WebSocketDisconnect:
        log.info("WebSocket disconnected | session=%s", session_id)
    except Exception as exc:
        log.warning("WebSocket error | session=%s | %s", session_id, exc)
    finally:
        log.info("WebSocket stream ended | session=%s", session_id)
