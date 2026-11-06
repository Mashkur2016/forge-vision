"""
Realtime Frame Pipeline — shared per-frame inference core.

Extracts the camera-free, queue-free, async-free heart of a training session
so it can be driven by more than one input source:

    bgr_frame
        → InferencePipeline.process_frame()   (CV pipeline + ActionRecognizer)
        → SOPDetector.process_frame()         (LSTM deviation classifier)
        → FramePipelineResult(frame_result, inference, event)

Consumers:
    - src/realtime/session_manager.py   — server-side camera + WebSocket (Phase B)
    - src/api/routes/live_ws.py         — browser webcam streamed over WebSocket (cloud demo)

This module deliberately owns NO camera, NO asyncio, and NO message queue.
LLM feedback (which is async / IO-bound) stays with the caller, because the
two consumers handle it very differently (awaited in the session loop vs.
generated per-frame inside the WebSocket handler).

Architecture.md Layer 2 → Layer 3 bridge.
Rules.md §1.7: per-frame latency must stay within the 2-second budget.
Rules.md §2: GDPR — frames are processed in memory only; never persisted.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

import numpy as np

from src.cv_pipeline.frame_processor import FrameResult
from src.intelligence.sop_detector import (
    DetectorConfig,
    SOPDetector,
    SOPDeviationEvent,
)
from src.realtime.inference_pipeline import (
    InferenceConfig,
    InferencePipeline,
    InferenceResult,
)
from src.simulation.sop_schema import SOP
from src.training.models import SOPSequenceModel


# ── Result type ────────────────────────────────────────────────────────────

@dataclass
class FramePipelineResult:
    """Aggregated output of one full per-frame pass."""
    frame_result: FrameResult        # CV pipeline output (pose + detections)
    inference: InferenceResult       # ActionRecognizer prediction (may be skipped)
    event: Optional[SOPDeviationEvent]  # Deviation event, if one was emitted this frame


# ── Pipeline ───────────────────────────────────────────────────────────────

class RealtimeFramePipeline:
    """
    Stateful per-frame inference core for one training session.

    Bundles the InferencePipeline (CV + action recognition) and the
    SOPDetector (sequence tracking + deviation classification) behind a
    single synchronous `process()` call.  Construct once per session, call
    `load()` before the first frame, then `process()` on every frame.

    Usage:
        fp = RealtimeFramePipeline(sop, sequence_model, session_id="abc").load()
        for bgr in frames:
            out = fp.process(bgr)
            if out.event is not None:
                handle(out.event)          # caller owns LLM feedback
        fp.end_session()
        summary = fp.session_summary()
        fp.close()
    """

    def __init__(
        self,
        sop: SOP,
        sequence_model: SOPSequenceModel,
        inference_config: Optional[InferenceConfig] = None,
        detector_config: Optional[DetectorConfig] = None,
        session_id: Optional[str] = None,
        inference_pipeline: Optional[InferencePipeline] = None,
    ) -> None:
        self._sop = sop
        self._sequence_model = sequence_model
        self._inference_config = inference_config or InferenceConfig()
        self._detector_config = detector_config or DetectorConfig()
        self.session_id = session_id or str(uuid.uuid4())[:8]

        # A pre-loaded InferencePipeline may be injected (e.g. cached + warmed in
        # the Streamlit main thread, then reused by the WebRTC worker so its
        # __init__ stays inside streamlit-webrtc's 10 s worker-init budget).
        # When borrowed, this pipeline is owned by the caller and must not be
        # closed here.
        self._pipeline: Optional[InferencePipeline] = inference_pipeline
        self._owns_pipeline: bool = inference_pipeline is None
        self._detector: Optional[SOPDetector] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def load(self) -> "RealtimeFramePipeline":
        """
        Load the ActionRecognizer checkpoint + CV models and start the
        detector session.  Blocking (model file I/O) — callers running in an
        event loop should offload this to a thread pool.
        """
        if self._pipeline is None:
            self._pipeline = InferencePipeline(self._inference_config)
            self._pipeline.load_model()

        self._detector = SOPDetector(
            sop=self._sop,
            sequence_model=self._sequence_model,
            session_id=self.session_id,
            config=self._detector_config,
        )
        self._detector.start_session()
        return self

    # ── Per-frame processing ──────────────────────────────────────────────

    def process(self, bgr_frame: np.ndarray) -> FramePipelineResult:
        """
        Run one BGR frame through CV + action recognition + deviation detection.

        Returns a FramePipelineResult.  `event` is None when no deviation was
        emitted this frame.  Never blocks on I/O or awaits.
        """
        if self._pipeline is None or self._detector is None:
            raise RuntimeError(
                "RealtimeFramePipeline.load() must be called before process()."
            )

        frame_result, inference = self._pipeline.process_frame(bgr_frame)
        event = self._detector.process_frame(
            frame_result,
            action_class=inference.action_class,
            action_confidence=inference.confidence,
        )
        return FramePipelineResult(
            frame_result=frame_result,
            inference=inference,
            event=event,
        )

    # ── Session teardown / reporting ──────────────────────────────────────

    def end_session(self) -> list[SOPDeviationEvent]:
        """End the detector session and return all emitted events."""
        if self._detector is None:
            return []
        return self._detector.end_session()

    def session_summary(self) -> dict:
        """Structured detector summary (events, deviations, severities)."""
        return self._detector.session_summary() if self._detector else {}

    def close(self) -> None:
        """Release CV model resources.  Blocking — offload from event loops.

        A borrowed (injected) InferencePipeline is left open for its owner to
        reuse; only a pipeline this instance created is closed here.
        """
        if self._pipeline is not None and self._owns_pipeline:
            self._pipeline.close()
        if self._owns_pipeline:
            self._pipeline = None

    # ── Read-only accessors ───────────────────────────────────────────────

    @property
    def detector(self) -> Optional[SOPDetector]:
        return self._detector

    @property
    def pipeline(self) -> Optional[InferencePipeline]:
        return self._pipeline
