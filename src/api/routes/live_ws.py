"""
Live-camera frame streaming over WebSocket (no WebRTC / no TURN).

The browser captures its webcam, downscales each frame to a JPEG data-URL, and
streams them here. The server runs the shared RealtimeFramePipeline (MediaPipe
pose + YOLO + ActionRecognizer + SOP deviation detector), draws the overlay, and
streams back the annotated frame plus any deviation event and LLM feedback.

Why this exists: WebRTC media needs UDP/TURN, which Hugging Face Spaces don't
allow (single HTTP port, no UDP) and which streamlit-webrtc could not drive
reliably. Plain WebSocket over the public HTTP port works everywhere — at the
cost of a few FPS, which is fine for a CPU demo.

Models are loaded once per process and shared (single-user demo). Heavy CV
inference runs in a thread so it never blocks the event loop.

Rules.md §2: frames are processed in memory only and never persisted.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from collections import deque

import cv2
import numpy as np
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from src.api.routes.deps import get_current_user

from src.config import settings
from src.cv_pipeline.annotate import draw_overlay
from src.cv_pipeline.emotion_detector import EmotionDetector
from src.database.database import AsyncSessionLocal
from src.intelligence.feedback_engine import generate_training_feedback
from src.intelligence.sop_detector import DetectorConfig
from src.realtime.frame_pipeline import RealtimeFramePipeline
from src.realtime.inference_pipeline import InferenceConfig, InferencePipeline
from src.simulation.sop_parser import load_all_sops
from src.training.models import build_sequence_model

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ws", tags=["LiveWS"])

_SEQUENCE_MODEL_CONFIG = {
    "sequence_model": {
        "input_dim": 25,
        "hidden_size": 128,
        "num_layers": 2,
        "dropout": 0.2,
        "num_deviation_classes": 6,
    }
}

# Process-wide cache of the heavy CV stack (load once, reuse across connections).
_seq_model = None
_inference_pipeline: InferencePipeline | None = None
_emotion_detector: EmotionDetector | None = None

# Run emotion detection (MediaPipe FaceMesh) only every Nth frame to bound CPU.
_EMOTION_EVERY_N = 8

# Per-user buffer of camera-detected deviations (with their AI feedback) so the
# Streamlit session summary can collect them after the live session ends.
# Keyed by user id (token `sub`); bounded so it can't grow unbounded.
_RECENT_DEVIATIONS: dict[str, deque] = {}


def _get_emotion_detector() -> EmotionDetector:
    global _emotion_detector
    if _emotion_detector is None:
        _emotion_detector = EmotionDetector().start()
    return _emotion_detector


def _get_models():
    global _seq_model, _inference_pipeline
    if _inference_pipeline is None:
        log.info("Loading CV models for live WS (one-time)...")
        _seq_model = build_sequence_model(
            config=_SEQUENCE_MODEL_CONFIG, num_action_classes=25
        )
        _inference_pipeline = InferencePipeline(InferenceConfig())
        _inference_pipeline.load_model()
        log.info("Live WS CV models loaded.")
    return _seq_model, _inference_pipeline


async def warm_models() -> None:
    """Pre-load the CV models off the event loop (called at API startup) so the
    first WebSocket connection doesn't pay the ~15-20 s cold-start while the
    event loop is blocked (which drops the WebSocket)."""
    try:
        await asyncio.to_thread(_get_models)
    except Exception as exc:  # pragma: no cover
        log.warning("Live WS model pre-warm failed: %s", exc)


def _decode_token(token: str) -> str | None:
    """Return the user id from a valid access token, else None."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
    except JWTError:
        return None


def _data_url_to_bgr(data_url: str) -> np.ndarray | None:
    """Decode a 'data:image/jpeg;base64,...' string to a BGR ndarray."""
    try:
        b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
        buf = np.frombuffer(base64.b64decode(b64), dtype=np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _bgr_to_data_url(bgr: np.ndarray, quality: int = 70) -> str:
    ok, enc = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(enc.tobytes()).decode()


@router.get("/live/deviations")
async def live_deviations(
    since: float = Query(0.0, description="Unix timestamp — return deviations at/after this time"),
    current_user=Depends(get_current_user),
) -> list[dict]:
    """Camera-detected deviations (with AI feedback) buffered for this user during a
    live session — fetched by the session summary to collect in-session coaching."""
    buf = _RECENT_DEVIATIONS.get(str(current_user.id)) or []
    return [d for d in list(buf) if d.get("timestamp", 0.0) >= since]


@router.websocket("/live")
async def live_ws(websocket: WebSocket) -> None:
    """Stream browser webcam frames in, annotated frames + feedback out."""
    token = websocket.query_params.get("token", "")
    sop_id = websocket.query_params.get("sop_id", "")
    await websocket.accept()

    uid = _decode_token(token)
    if uid is None:
        await websocket.send_text(json.dumps({"error": "unauthorized"}))
        await websocket.close(code=1008)
        return

    try:
        sops = load_all_sops("data/sops")
    except Exception as exc:  # pragma: no cover
        await websocket.send_text(json.dumps({"error": f"SOP load failed: {exc}"}))
        await websocket.close()
        return
    sop = sops.get(sop_id) or (next(iter(sops.values())) if sops else None)
    if sop is None:
        await websocket.send_text(json.dumps({"error": "no SOP available"}))
        await websocket.close()
        return

    # Load/build off the event loop so the WebSocket stays alive (and the loop
    # stays responsive) even on the first, cold model load.
    seq_model, inference_pipeline = await asyncio.to_thread(_get_models)
    pipeline = await asyncio.to_thread(
        lambda: RealtimeFramePipeline(
            sop=sop,
            sequence_model=seq_model,
            inference_pipeline=inference_pipeline,
            detector_config=DetectorConfig(),
        ).load()
    )
    log.info("Live WS connected | sop=%s", sop.id)

    emotion_detector = _get_emotion_detector()
    last_deviation: tuple[str, str] | None = None
    last_emotion: dict | None = None
    frame_idx = 0
    try:
        while True:
            raw = await websocket.receive_text()
            if raw == "ping":
                continue
            img = _data_url_to_bgr(raw)
            if img is None:
                continue
            frame_idx += 1

            result = await asyncio.to_thread(pipeline.process, img)

            # Affective state (Enhancement 7) — every Nth frame to bound CPU.
            if emotion_detector.is_available and frame_idx % _EMOTION_EVERY_N == 1:
                try:
                    er = await asyncio.to_thread(emotion_detector.detect, img)
                    if er.face_detected:
                        last_emotion = {"state": er.state.value,
                                        "confidence": round(er.confidence, 2)}
                except Exception as exc:  # never break the stream on emotion error
                    log.debug("emotion detect error: %s", exc)

            out: dict = {}
            if last_emotion is not None:
                out["emotion"] = last_emotion
            if result.event is not None:
                ev = result.event.to_dict()
                last_deviation = (ev.get("severity", "low"), ev.get("what", ""))
                out["deviation"] = {
                    "severity": ev.get("severity", "low"),
                    "what": ev.get("what", ""),
                    "deviation_class": ev.get("deviation_class", ""),
                }
                try:
                    async with AsyncSessionLocal() as db:
                        out["feedback"] = await generate_training_feedback(
                            db=db,
                            sop_name=sop.name,
                            detected_action=ev.get("what") or ev.get("deviation_class", ""),
                            error_type=ev.get("deviation_class", ""),
                            step_id=ev.get("expected_step_id") or 0,
                            step_description=ev.get("expected_step_name", ""),
                            confidence=ev.get("model_confidence", 0.0),
                            error_history=[],
                        )
                except Exception as exc:
                    log.warning("Live WS feedback failed: %s", exc)
                    out["feedback"] = None

                # Buffer this deviation + its AI feedback so the post-session
                # summary (Streamlit) can collect it after the camera closes.
                _RECENT_DEVIATIONS.setdefault(uid, deque(maxlen=50)).append({
                    "timestamp":          time.time(),
                    "deviation_class":    ev.get("deviation_class", ""),
                    "severity":           ev.get("severity", "low"),
                    "expected_step_name": ev.get("expected_step_name", ""),
                    "model_confidence":   ev.get("model_confidence", 0.0),
                    "what":               ev.get("what", ""),
                    "why":                ev.get("why", ""),
                    "feedback_text":      out.get("feedback"),
                })

            out["frame"] = _bgr_to_data_url(
                draw_overlay(img, result.frame_result, deviation=last_deviation)
            )
            await websocket.send_text(json.dumps(out))
    except WebSocketDisconnect:
        log.info("Live WS disconnected | sop=%s", sop.id)
    except Exception as exc:  # pragma: no cover
        log.warning("Live WS error: %s", exc)
    finally:
        try:
            pipeline.close()  # borrowed inference pipeline is left open for reuse
        except Exception:
            pass
