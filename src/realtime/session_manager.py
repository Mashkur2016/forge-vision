"""
Training Session Manager — Tasks 3.2 & 3.3 (Phase 3).

Orchestrates the complete real-time pipeline for one worker training session:

    CameraCapture
        → InferencePipeline   (CV + ActionRecognizer)
        → SOPDetector         (LSTM sequence model + deviation classification)
        → FeedbackEngine      (LLM corrective instructions)
        → asyncio.Queue       (messages consumed by WebSocket / UI)

Each session runs in a background asyncio Task.
One TrainingSession instance per active worker session.

Architecture.md: "Phase B Real-Time" end-to-end flow.
Rules.md §1.7: end-to-end latency target < 2 s.
Rules.md §2: GDPR — frames are processed in memory and never persisted.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator, Callable, Optional

import cv2
import numpy as np

from src.cv_pipeline.frame_processor import FrameResult
from src.intelligence.sop_detector import SOPDeviationEvent, DetectorConfig
from src.realtime.camera_capture import CameraCapture, CameraConfig
from src.realtime.frame_pipeline import RealtimeFramePipeline
from src.realtime.inference_pipeline import InferenceConfig, InferenceResult
from src.simulation.sop_schema import SOP
from src.training.models import SOPSequenceModel

log = logging.getLogger(__name__)


# ── Session status ─────────────────────────────────────────────────────────

class SessionStatus(str, Enum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETE = "complete"
    ERROR = "error"


# ── WebSocket message ──────────────────────────────────────────────────────

@dataclass
class SessionMessage:
    """
    A message pushed from the session to WebSocket subscribers.

    Types:
      "frame"     — JPEG frame + CV metadata (throttled)
      "deviation" — SOPDeviationEvent payload
      "feedback"  — LLM-generated corrective instruction
      "status"    — Session lifecycle change
      "latency"   — Periodic latency report
    """
    type: str
    session_id: str
    timestamp: float = field(default_factory=time.time)
    data: dict = field(default_factory=dict)


# ── Session configuration ──────────────────────────────────────────────────

@dataclass
class SessionConfig:
    """Full configuration for one training session."""
    sop: SOP
    camera: CameraConfig = field(default_factory=CameraConfig)
    inference: InferenceConfig = field(default_factory=InferenceConfig)
    detector: DetectorConfig = field(default_factory=DetectorConfig)

    # Push frame messages every N processed frames (reduces WebSocket traffic)
    frame_push_every_n: int = 5

    # Enable TTS audio feedback (requires src/realtime/tts_engine.py + pyttsx3)
    tts_enabled: bool = False

    # JPEG quality for frame transport (lower = less bandwidth, more compression)
    jpeg_quality: int = 70


# ── Training Session ───────────────────────────────────────────────────────

class TrainingSession:
    """
    One real-time worker training session.

    Lifecycle:
        session = TrainingSession(config, feedback_fn=my_llm_fn)
        await session.start(sequence_model)

        async for msg in session.messages():
            send_to_websocket(msg)

        await session.stop()
        report = session.summary()

    feedback_fn is an async callable that receives a SOPDeviationEvent and
    returns a corrective instruction string.  Pass None to disable LLM calls.
    """

    def __init__(
        self,
        config: SessionConfig,
        session_id: Optional[str] = None,
        feedback_fn: Optional[Callable] = None,
    ) -> None:
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self._config = config
        self._feedback_fn = feedback_fn

        self._status: SessionStatus = SessionStatus.IDLE
        self._camera: Optional[CameraCapture] = None
        self._frame_pipeline: Optional[RealtimeFramePipeline] = None
        self._tts = None
        self._loop_task: Optional[asyncio.Task] = None

        # Subscribers drain this queue
        self._queue: asyncio.Queue[SessionMessage] = asyncio.Queue(maxsize=150)

        self._start_time: float = 0.0
        self._frame_count: int = 0
        self._latencies: list[float] = []

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def start(self, sequence_model: SOPSequenceModel) -> None:
        """
        Open camera, load models, and start the real-time processing loop.

        Args:
            sequence_model: Trained SOPSequenceModel for deviation classification.
        """
        if self._status != SessionStatus.IDLE:
            raise RuntimeError(
                f"TrainingSession.start() called in unexpected state: {self._status}"
            )

        self._status = SessionStatus.STARTING
        self._push_status()

        loop = asyncio.get_event_loop()

        try:
            # 1. Open camera (blocking I/O — offload to thread pool)
            self._camera = CameraCapture(self._config.camera)
            await loop.run_in_executor(None, self._camera.start)

            # 2. Load CV + ActionRecognizer models and start the SOP detector
            #    (blocking — model file I/O — offload to thread pool)
            self._frame_pipeline = RealtimeFramePipeline(
                sop=self._config.sop,
                sequence_model=sequence_model,
                inference_config=self._config.inference,
                detector_config=self._config.detector,
                session_id=self.session_id,
            )
            await loop.run_in_executor(None, self._frame_pipeline.load)

            # 3. Optionally start TTS engine
            if self._config.tts_enabled:
                from src.realtime.tts_engine import TTSEngine, TTSConfig
                self._tts = TTSEngine(TTSConfig())
                await loop.run_in_executor(None, self._tts.start)

            self._start_time = time.perf_counter()
            self._status = SessionStatus.RUNNING
            self._push_status()

            # 5. Launch background processing loop
            self._loop_task = asyncio.create_task(
                self._process_loop(),
                name=f"forge-session-{self.session_id}",
            )

        except Exception as exc:
            self._status = SessionStatus.ERROR
            self._push_status(error=str(exc))
            raise

    async def stop(self) -> None:
        """Gracefully stop the session and release all resources."""
        if self._status not in (SessionStatus.RUNNING, SessionStatus.STARTING):
            return

        self._status = SessionStatus.STOPPING
        self._push_status()

        # Cancel the processing loop
        if self._loop_task is not None and not self._loop_task.done():
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None

        loop = asyncio.get_event_loop()

        # Release camera and models (blocking — offload to thread pool)
        if self._camera is not None:
            await loop.run_in_executor(None, self._camera.stop)
        if self._frame_pipeline is not None:
            # End detector session (collects events) then release CV models
            self._frame_pipeline.end_session()
            await loop.run_in_executor(None, self._frame_pipeline.close)
        if self._tts is not None:
            await loop.run_in_executor(None, self._tts.stop)

        self._status = SessionStatus.COMPLETE
        self._push_status()

    @property
    def status(self) -> SessionStatus:
        return self._status

    @property
    def is_running(self) -> bool:
        return self._status == SessionStatus.RUNNING

    # ── Message subscription ───────────────────────────────────────────────

    async def messages(self) -> AsyncGenerator[SessionMessage, None]:
        """
        Async generator that yields SessionMessage objects in real time.

        Continues until the session reaches COMPLETE or ERROR state and
        the queue is drained.
        """
        active_states = {
            SessionStatus.STARTING,
            SessionStatus.RUNNING,
            SessionStatus.STOPPING,
        }

        while self._status in active_states:
            try:
                msg = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                yield msg
            except asyncio.TimeoutError:
                continue

        # Drain any remaining messages
        while not self._queue.empty():
            yield self._queue.get_nowait()

    # ── Summary ───────────────────────────────────────────────────────────

    def summary(self) -> dict:
        """Structured session summary for the analytics dashboard and API."""
        elapsed = time.perf_counter() - self._start_time if self._start_time else 0.0
        p95 = float(np.percentile(self._latencies, 95)) if self._latencies else 0.0
        mean = float(np.mean(self._latencies)) if self._latencies else 0.0
        detector_data = self._frame_pipeline.session_summary() if self._frame_pipeline else {}

        return {
            "session_id": self.session_id,
            "sop_id": self._config.sop.id,
            "sop_name": self._config.sop.name,
            "status": self._status.value,
            "duration_seconds": round(elapsed, 1),
            "total_frames": self._frame_count,
            "actual_fps": round(self._frame_count / elapsed, 1) if elapsed > 0 else 0.0,
            "latency_ms": {
                "mean": round(mean, 1),
                "p95": round(p95, 1),
            },
            "latency_target_met": p95 < 2000.0,
            # Merge detector data but never let it overwrite session-level keys
            **{k: v for k, v in detector_data.items()
               if k not in ("session_id", "sop_id", "sop_name", "status")},
        }

    # ── Background processing loop ─────────────────────────────────────────

    async def _process_loop(self) -> None:
        """
        Main real-time loop (runs as asyncio Task).

        Each iteration:
          1. Read latest frame from camera buffer (non-blocking via thread pool)
          2. Run CV pipeline + ActionRecognizer (CPU-bound → thread pool)
          3. Run SOPDetector (fast, synchronous)
          4. If deviation: invoke LLM feedback_fn (async)
          5. Push messages to subscriber queue
          6. Record end-to-end latency
        """
        frame_push_counter = 0

        while True:
            t_start = time.perf_counter()

            # ── 1. Read frame ──────────────────────────────────────────────
            loop = asyncio.get_event_loop()
            frame: Optional[np.ndarray] = await loop.run_in_executor(
                None, self._camera.read
            )
            if frame is None:
                await asyncio.sleep(0.01)
                continue

            # ── 2. CV + ActionRecognizer + deviation detection (CPU-bound) ─
            result = await loop.run_in_executor(
                None, self._frame_pipeline.process, frame
            )
            frame_result = result.frame_result
            inference = result.inference
            event: Optional[SOPDeviationEvent] = result.event

            self._frame_count += 1
            frame_push_counter += 1

            # ── 4. Push throttled frame message ───────────────────────────
            if frame_push_counter >= self._config.frame_push_every_n:
                frame_push_counter = 0
                self._push_frame(frame, frame_result, inference)

            # ── 5. Handle deviation ────────────────────────────────────────
            if event is not None:
                self._push_deviation(event)

                if event.requires_llm_feedback and self._feedback_fn is not None:
                    try:
                        feedback_text: str = await self._feedback_fn(event)
                        self._push_feedback(event, feedback_text)

                        # Speak the feedback via TTS (non-blocking)
                        if self._tts is not None and event.is_safety_critical:
                            self._tts.speak(feedback_text)

                    except Exception as exc:
                        log.warning(
                            "Session %s: LLM feedback error: %s",
                            self.session_id, exc,
                        )

            # ── 6. Latency tracking ────────────────────────────────────────
            end_to_end_ms = (time.perf_counter() - t_start) * 1000.0
            self._latencies.append(end_to_end_ms)

            # Yield to other async tasks
            await asyncio.sleep(0)

    # ── Message helpers ───────────────────────────────────────────────────

    def _push(self, msg: SessionMessage) -> None:
        """Non-blocking enqueue — drops oldest message if queue is full."""
        try:
            self._queue.put_nowait(msg)
        except asyncio.QueueFull:
            # Drop oldest, then enqueue newest
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(msg)
            except (asyncio.QueueEmpty, asyncio.QueueFull):
                pass

    def _push_status(self, error: str = "") -> None:
        self._push(SessionMessage(
            type="status",
            session_id=self.session_id,
            data={"status": self._status.value, "error": error},
        ))

    def _push_frame(
        self,
        frame: np.ndarray,
        frame_result: FrameResult,
        inference: InferenceResult,
    ) -> None:
        _, jpeg_buf = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self._config.jpeg_quality]
        )
        jpeg_b64 = base64.b64encode(jpeg_buf.tobytes()).decode("ascii")

        self._push(SessionMessage(
            type="frame",
            session_id=self.session_id,
            data={
                "jpeg_b64": jpeg_b64,
                "person_detected": frame_result.person_detected,
                "detected_objects": frame_result.detected_labels,
                "action_class": inference.action_class,
                "confidence": round(inference.confidence, 3),
                "frame_latency_ms": round(frame_result.total_latency_ms, 1),
                "frame_count": self._frame_count,
            },
        ))

    def _push_deviation(self, event: SOPDeviationEvent) -> None:
        self._push(SessionMessage(
            type="deviation",
            session_id=self.session_id,
            data=event.to_dict(),
        ))

    def _push_feedback(self, event: SOPDeviationEvent, feedback_text: str) -> None:
        self._push(SessionMessage(
            type="feedback",
            session_id=self.session_id,
            data={
                "deviation_class": event.deviation_class,
                "severity": event.severity.value,
                "feedback_text": feedback_text,
                "step_name": event.expected_step_name,
                "confidence": round(event.model_confidence, 3),
            },
        ))
