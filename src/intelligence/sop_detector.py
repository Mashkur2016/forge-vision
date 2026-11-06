"""
SOP Deviation Detector — Intelligence Layer for FORGE-Vision.

Combines:
    SOPSequenceTracker  (step state machine)         → what step we're on
    SOPSequenceModel    (LSTM deviation classifier)  → what went wrong
    FrameResult         (CV pipeline output)         → what the camera saw

Emits structured SOPDeviationEvent objects consumed by:
    - feedback_engine.py (LLM corrective instruction generation)
    - API routes (real-time alert streaming)
    - Analytics dashboard

Architecture.md Layer 3: "SOP Matching Engine → Error Detection → LLM Feedback"
Rules.md §1.6: Every detected error must include WHAT and WHY fields.
Rules.md §1.7: Detection latency budget ≤ 2 seconds end-to-end.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import torch as _torch

from src.cv_pipeline.frame_processor import FrameResult
from src.intelligence.sequence_tracker import SOPSequenceTracker, SessionStatus
from src.simulation.sop_schema import SOP, SOPStep
from src.training.models import SOPSequenceModel


# ── Deviation severity ─────────────────────────────────────────────────────

class DeviationSeverity(str, Enum):
    LOW = "low"         # Minor deviation; worker can self-correct easily
    MEDIUM = "medium"   # Step skipped or wrong order; intervention recommended
    HIGH = "high"       # Safety-critical violation; immediate stop required


# ── Event type ─────────────────────────────────────────────────────────────

@dataclass
class SOPDeviationEvent:
    """
    A single detected deviation from the SOP.

    This is the primary output of SOPDetector.  It carries everything
    needed for the LLM feedback engine and the analytics dashboard.

    Rules.md §1.6: WHAT + WHY must always be populated.
    """
    # Session context
    session_id: str
    sop_id: str
    sop_name: str
    timestamp: float = field(default_factory=time.time)

    # Deviation classification
    deviation_class: str = "CORRECT"           # One of SOPSequenceModel.DEVIATION_CLASSES
    severity: DeviationSeverity = DeviationSeverity.LOW

    # Step context
    expected_step_id: Optional[int] = None     # Step the worker should be on
    expected_step_name: str = ""
    observed_action_class: int = -1            # ActionRecognizer prediction
    model_confidence: float = 0.0              # SOPSequenceModel confidence

    # Explainability (Rules.md §1.6)
    what: str = ""     # Short description of what was detected wrong
    why: str = ""      # Reason this is a deviation (SOP reference)

    # Supporting CV evidence
    detected_objects: list[str] = field(default_factory=list)
    missing_ppe: list[str] = field(default_factory=list)
    person_detected: bool = True

    # Latency
    detection_latency_ms: float = 0.0

    @property
    def is_safety_critical(self) -> bool:
        return self.severity == DeviationSeverity.HIGH

    @property
    def requires_llm_feedback(self) -> bool:
        """Only non-CORRECT events with sufficient confidence trigger LLM."""
        return self.deviation_class != "CORRECT" and self.model_confidence >= 0.6

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "sop_id": self.sop_id,
            "sop_name": self.sop_name,
            "timestamp": self.timestamp,
            "deviation_class": self.deviation_class,
            "severity": self.severity.value,
            "expected_step_id": self.expected_step_id,
            "expected_step_name": self.expected_step_name,
            "observed_action_class": self.observed_action_class,
            "model_confidence": round(self.model_confidence, 4),
            "what": self.what,
            "why": self.why,
            "detected_objects": self.detected_objects,
            "missing_ppe": self.missing_ppe,
            "person_detected": self.person_detected,
            "detection_latency_ms": round(self.detection_latency_ms, 2),
        }


# ── Detector configuration ─────────────────────────────────────────────────

@dataclass
class DetectorConfig:
    """Configuration for SOPDetector behaviour."""
    # Minimum SOPSequenceModel confidence to emit a deviation event
    deviation_confidence_threshold: float = 0.60

    # Minimum frames in the window before running the LSTM classifier
    min_window_frames: int = 4

    # After a deviation event, suppress duplicates for this many seconds
    cooldown_seconds: float = 3.0

    # Force-advance the tracker after this many seconds on the same step
    step_timeout_grace_seconds: float = 5.0

    # If PPE is missing for this many consecutive frames → MISSING_PPE event
    ppe_missing_frames_threshold: int = 10

    device: str = "cpu"


# ── Main detector ──────────────────────────────────────────────────────────

class SOPDetector:
    """
    Real-time SOP deviation detector.

    Orchestrates the CV pipeline output, the sequence tracker, and the
    LSTM deviation model to detect and classify SOP violations.

    Usage (per-session):
        detector = SOPDetector(sop, sequence_model, session_id="abc")
        detector.start_session()

        for bgr_frame in video_stream:
            frame_result = frame_processor.process(bgr_frame)
            action_class = action_recognizer_output   # from ActionRecognizer
            event = detector.process_frame(frame_result, action_class)
            if event and event.deviation_class != "CORRECT":
                feedback = await generate_training_feedback(...)

        detector.end_session()

    The detector is stateful — create one per worker session.
    """

    def __init__(
        self,
        sop: SOP,
        sequence_model: SOPSequenceModel,
        session_id: str = "default",
        config: Optional[DetectorConfig] = None,
    ) -> None:
        self.sop = sop
        self.model = sequence_model
        self.session_id = session_id
        self.config = config or DetectorConfig()

        self._tracker = SOPSequenceTracker(sop, session_id=session_id)
        self._last_event_time: float = 0.0
        self._ppe_missing_streak: int = 0
        self._events: list[SOPDeviationEvent] = []

    # ── Session lifecycle ─────────────────────────────────────────────────

    def start_session(self) -> None:
        """Start a new detection session."""
        self._tracker.start()
        self._last_event_time = 0.0
        self._ppe_missing_streak = 0
        self._events = []

    def end_session(self) -> list[SOPDeviationEvent]:
        """
        End the session and return all events that were emitted.

        Returns:
            List of all SOPDeviationEvent objects from this session.
        """
        if self._tracker.is_active:
            self._tracker.abort()
        return list(self._events)

    # ── Frame processing ──────────────────────────────────────────────────

    def process_frame(
        self,
        frame_result: FrameResult,
        action_class: int,
        action_confidence: float = 1.0,
    ) -> Optional[SOPDeviationEvent]:
        """
        Process one frame and return a deviation event if one is detected.

        Args:
            frame_result:      Output of FrameProcessor.process()
            action_class:      ActionRecognizer predicted class index
            action_confidence: ActionRecognizer softmax confidence

        Returns:
            SOPDeviationEvent if a deviation (or CORRECT confirmation) was
            classified with sufficient confidence; None otherwise.
        """
        if not self._tracker.is_active:
            return None

        t_start = time.perf_counter()

        # ── 1. Record action in tracker ────────────────────────────────────
        step_record = self._tracker.record_action(action_class, action_confidence)

        # ── 2. Check PPE ───────────────────────────────────────────────────
        ppe_event = self._check_ppe(frame_result)
        if ppe_event is not None:
            ppe_event.detection_latency_ms = (time.perf_counter() - t_start) * 1000.0
            self._events.append(ppe_event)
            return ppe_event

        # ── 3. Run LSTM deviation model ────────────────────────────────────
        window = self._tracker.action_window
        if len(window) < self.config.min_window_frames:
            return None

        lstm_event = self._run_sequence_model(
            window=window,
            frame_result=frame_result,
            action_class=action_class,
            action_confidence=action_confidence,
            t_start=t_start,
        )

        if lstm_event is not None:
            self._events.append(lstm_event)
            self._last_event_time = time.monotonic()

        return lstm_event

    # ── PPE checking ──────────────────────────────────────────────────────

    def _check_ppe(self, frame_result: FrameResult) -> Optional[SOPDeviationEvent]:
        """
        Check if required PPE is missing across consecutive frames.

        Only fires after ppe_missing_frames_threshold consecutive frames
        with missing PPE, to avoid false positives from detection noise.
        """
        required_ppe = list(self.sop.all_required_ppe())
        if not required_ppe:
            return None

        missing = frame_result.missing_ppe(required_ppe)

        if missing:
            self._ppe_missing_streak += 1
        else:
            self._ppe_missing_streak = 0
            return None

        if self._ppe_missing_streak < self.config.ppe_missing_frames_threshold:
            return None

        # Cooldown check
        if (time.monotonic() - self._last_event_time) < self.config.cooldown_seconds:
            return None

        current_step = self._tracker.current_step
        return SOPDeviationEvent(
            session_id=self.session_id,
            sop_id=self.sop.id,
            sop_name=self.sop.name,
            deviation_class="MISSING_PPE",
            severity=DeviationSeverity.HIGH,
            expected_step_id=current_step.id if current_step else None,
            expected_step_name=current_step.name if current_step else "",
            observed_action_class=-1,
            model_confidence=1.0,
            what=f"Required PPE not detected: {', '.join(missing)}",
            why=(
                f"SOP '{self.sop.name}' requires {', '.join(required_ppe)} "
                f"throughout the procedure. Worker is not wearing: {', '.join(missing)}."
            ),
            detected_objects=frame_result.detected_labels,
            missing_ppe=missing,
            person_detected=frame_result.person_detected,
        )

    # ── LSTM classification ────────────────────────────────────────────────

    def _run_sequence_model(
        self,
        window: list[int],
        frame_result: FrameResult,
        action_class: int,
        action_confidence: float,
        t_start: float,
    ) -> Optional[SOPDeviationEvent]:
        """
        Run SOPSequenceModel on the current action window.

        Returns a SOPDeviationEvent if confidence exceeds the threshold
        and the cooldown has elapsed, else None.
        """
        # Cooldown suppression
        if (time.monotonic() - self._last_event_time) < self.config.cooldown_seconds:
            return None

        # Build input tensor: (1, T) LongTensor — padding_idx=0, so shift +1
        padded = [a + 1 for a in window]   # shift from 0-based to 1-based (0 = pad)
        seq = _torch.tensor([padded], dtype=_torch.long)

        self.model.eval()
        with _torch.no_grad():
            logits = self.model(seq)                      # (1, num_deviation_classes)
            probs = _torch.softmax(logits, dim=1)         # (1, num_deviation_classes)
            confidence, pred_idx = probs.max(dim=1)
            confidence = float(confidence.item())
            pred_idx = int(pred_idx.item())

        if confidence < self.config.deviation_confidence_threshold:
            return None

        deviation_class = SOPSequenceModel.DEVIATION_CLASSES[pred_idx]
        current_step = self._tracker.current_step
        latency_ms = (time.perf_counter() - t_start) * 1000.0

        severity = self._classify_severity(deviation_class, current_step)
        what, why = self._explain(deviation_class, current_step, action_class)

        return SOPDeviationEvent(
            session_id=self.session_id,
            sop_id=self.sop.id,
            sop_name=self.sop.name,
            deviation_class=deviation_class,
            severity=severity,
            expected_step_id=current_step.id if current_step else None,
            expected_step_name=current_step.name if current_step else "",
            observed_action_class=action_class,
            model_confidence=confidence,
            what=what,
            why=why,
            detected_objects=frame_result.detected_labels,
            missing_ppe=frame_result.missing_ppe(list(self.sop.all_required_ppe())),
            person_detected=frame_result.person_detected,
            detection_latency_ms=latency_ms,
        )

    # ── Helpers ───────────────────────────────────────────────────────────

    def _classify_severity(
        self,
        deviation_class: str,
        current_step: Optional[SOPStep],
    ) -> DeviationSeverity:
        """Map deviation class + step context to severity level."""
        if deviation_class == "CORRECT":
            return DeviationSeverity.LOW

        is_safety_critical = current_step.safety_critical if current_step else False

        if deviation_class in ("MISSING_PPE", "UNSAFE_POSTURE"):
            return DeviationSeverity.HIGH

        if deviation_class == "MISSING_STEP" and is_safety_critical:
            return DeviationSeverity.HIGH

        if deviation_class in ("WRONG_ORDER", "MISSING_STEP"):
            return DeviationSeverity.MEDIUM

        if deviation_class == "INCORRECT_EXECUTION":
            return DeviationSeverity.HIGH if is_safety_critical else DeviationSeverity.MEDIUM

        return DeviationSeverity.MEDIUM

    def _explain(
        self,
        deviation_class: str,
        current_step: Optional[SOPStep],
        action_class: int,
    ) -> tuple[str, str]:
        """
        Generate WHAT and WHY explanation strings (Rules.md §1.6).

        Returns:
            (what, why) tuple of plain-English strings.
        """
        step_name = current_step.name if current_step else "unknown step"
        step_id = current_step.id if current_step else "?"

        explanations: dict[str, tuple[str, str]] = {
            "CORRECT": (
                f"Step {step_id} ({step_name}) performed correctly.",
                "Action sequence matches the expected SOP step order.",
            ),
            "MISSING_STEP": (
                f"Step {step_id} ({step_name}) appears to have been skipped.",
                (
                    f"SOP requires step {step_id} before proceeding. "
                    f"Skipping '{step_name}' may compromise procedure integrity."
                ),
            ),
            "WRONG_ORDER": (
                f"Steps performed out of order near step {step_id} ({step_name}).",
                (
                    f"SOP '{self.sop.name}' defines a strict step sequence. "
                    f"Step {step_id} must follow its predecessors as defined."
                ),
            ),
            "INCORRECT_EXECUTION": (
                f"Step {step_id} ({step_name}) was not executed correctly.",
                (
                    f"The observed actions do not match the required execution "
                    f"for '{step_name}' as defined in the SOP."
                ),
            ),
            "MISSING_PPE": (
                "Required personal protective equipment not detected.",
                f"SOP '{self.sop.name}' mandates PPE throughout the procedure.",
            ),
            "UNSAFE_POSTURE": (
                "Unsafe body posture or movement detected.",
                (
                    "Worker posture or movement pattern indicates a potential "
                    "safety risk. Safe posture must be maintained per SOP guidelines."
                ),
            ),
        }

        return explanations.get(
            deviation_class,
            (f"Deviation detected: {deviation_class}", "Action sequence does not match SOP."),
        )

    # ── Read-only accessors ───────────────────────────────────────────────

    @property
    def tracker(self) -> SOPSequenceTracker:
        return self._tracker

    @property
    def events(self) -> list[SOPDeviationEvent]:
        """All events emitted in the current session (read-only copy)."""
        return list(self._events)

    @property
    def deviation_count(self) -> int:
        return sum(1 for e in self._events if e.deviation_class != "CORRECT")

    def session_summary(self) -> dict:
        """Full session summary for API / dashboard."""
        tracker_summary = self._tracker.summary()
        return {
            **tracker_summary,
            "total_events": len(self._events),
            "deviations": self.deviation_count,
            "high_severity_count": sum(
                1 for e in self._events if e.severity == DeviationSeverity.HIGH
            ),
            "safety_critical_violations": sum(
                1 for e in self._events if e.is_safety_critical
            ),
            "events": [e.to_dict() for e in self._events],
        }
