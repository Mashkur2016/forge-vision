"""
SOP Sequence Tracker — session-level step state machine for FORGE-Vision.

Maintains the running state of an active SOP session:
    - Which steps have been completed (and in what order)
    - Per-step timestamps for time-limit enforcement
    - A sliding window of recent action predictions fed to the deviation detector

Architecture.md Layer 3 (Intelligence Layer):
    "SOP Matching Engine — compare detected actions vs SOP ground truth"

The tracker is intentionally stateful and session-scoped.  Create one instance
per worker session; reset() between sessions.

Rules.md §1.5: seed is accepted for reproducibility in tests.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from src.simulation.sop_schema import SOP, SOPStep


# ── Step completion record ─────────────────────────────────────────────────

@dataclass
class StepRecord:
    """Record of one completed (or skipped/violated) SOP step."""
    step_id: int
    step_name: str
    completed_at: float        # time.monotonic() timestamp
    duration_seconds: float    # Time taken to complete
    action_class: int          # ActionRecognizer predicted class index
    confidence: float          # Prediction confidence [0, 1]
    was_late: bool = False     # Exceeded time_limit_seconds if one is set


# ── Session state ──────────────────────────────────────────────────────────

class SessionStatus(str, Enum):
    IDLE = "idle"
    ACTIVE = "active"
    COMPLETED = "completed"   # All required steps done
    ABORTED = "aborted"       # Session ended before completion


@dataclass
class SessionState:
    """Full snapshot of a tracking session at one point in time."""
    sop_id: str
    session_id: str
    status: SessionStatus
    current_step_index: int          # Index into SOP.steps (0-based)
    completed_step_ids: list[int]    # Step IDs completed so far (ordered)
    step_records: list[StepRecord]
    pending_step_ids: list[int]      # Step IDs not yet completed
    action_window: list[int]         # Recent action class predictions (sliding)
    session_start: float             # time.monotonic()
    last_action_at: float            # Most recent action prediction time


# ── Tracker ────────────────────────────────────────────────────────────────

class SOPSequenceTracker:
    """
    Stateful SOP step tracker for one worker session.

    Receives a stream of action predictions (integer class indices) and
    maintains the session state: which steps are complete, what the next
    expected step is, and a sliding window for the deviation detector.

    Usage:
        tracker = SOPSequenceTracker(sop, session_id="session_001")
        tracker.start()
        tracker.record_action(action_class=2, confidence=0.87)
        state = tracker.get_state()

    Thread safety: NOT thread-safe. Use one tracker per session coroutine/thread.
    """

    # Size of the action prediction window fed to SOPSequenceModel
    DEFAULT_WINDOW_SIZE: int = 16

    def __init__(
        self,
        sop: SOP,
        session_id: str = "default",
        window_size: int = DEFAULT_WINDOW_SIZE,
    ) -> None:
        self.sop = sop
        self.session_id = session_id
        self.window_size = window_size

        # Mutable session state
        self._status = SessionStatus.IDLE
        self._current_step_index: int = 0
        self._completed_step_ids: list[int] = []
        self._step_records: list[StepRecord] = []
        self._action_window: list[int] = []
        self._session_start: float = 0.0
        self._last_action_at: float = 0.0
        self._step_start_time: float = 0.0    # When current step was entered

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> None:
        """Begin a new session. Resets all state."""
        now = time.monotonic()
        self._status = SessionStatus.ACTIVE
        self._current_step_index = 0
        self._completed_step_ids = []
        self._step_records = []
        self._action_window = []
        self._session_start = now
        self._last_action_at = now
        self._step_start_time = now

    def reset(self) -> None:
        """Alias for start() — resets and restarts the session."""
        self.start()

    def abort(self) -> None:
        """Mark the session as aborted (e.g. worker left the frame)."""
        self._status = SessionStatus.ABORTED

    # ── Action recording ──────────────────────────────────────────────────

    def record_action(self, action_class: int, confidence: float = 1.0) -> Optional[StepRecord]:
        """
        Record one action prediction from ActionRecognizer.

        Appends to the sliding window.  If the action matches the expected
        next SOP step, advances the tracker and returns a StepRecord.
        Otherwise returns None (deviation detection is handled by SOPDetector).

        Args:
            action_class: Predicted action class index (0-based)
            confidence:   Model confidence [0, 1]

        Returns:
            StepRecord if a step was completed, else None.
        """
        if self._status != SessionStatus.ACTIVE:
            return None

        now = time.monotonic()
        self._last_action_at = now

        # Update sliding window
        self._action_window.append(action_class)
        if len(self._action_window) > self.window_size:
            self._action_window.pop(0)

        # Check if this action completes the current expected step
        expected_step = self.current_step
        if expected_step is None:
            return None

        # Action class index aligns with SOP step IDs (1-based → 0-based offset)
        expected_action = expected_step.id - 1

        if action_class == expected_action:
            return self._complete_step(expected_step, action_class, confidence, now)

        return None

    # ── Step advancement ──────────────────────────────────────────────────

    def _complete_step(
        self,
        step: SOPStep,
        action_class: int,
        confidence: float,
        now: float,
    ) -> StepRecord:
        """Mark the current step as completed and advance to the next."""
        duration = now - self._step_start_time
        was_late = (
            step.time_limit_seconds is not None
            and duration > step.time_limit_seconds
        )
        record = StepRecord(
            step_id=step.id,
            step_name=step.name,
            completed_at=now,
            duration_seconds=round(duration, 3),
            action_class=action_class,
            confidence=confidence,
            was_late=was_late,
        )
        self._step_records.append(record)
        self._completed_step_ids.append(step.id)
        self._current_step_index += 1
        self._step_start_time = now

        # Check if all steps done
        if self._current_step_index >= len(self.sop.steps):
            self._status = SessionStatus.COMPLETED

        return record

    def force_advance(self, action_class: int = -1, confidence: float = 0.0) -> Optional[StepRecord]:
        """
        Force-advance to the next step without requiring an action match.

        Used by SOPDetector when a deviation is confirmed and the tracker
        must be nudged past the missed/wrong step to stay synchronised.

        Args:
            action_class: The action that was actually observed (-1 = unknown)
            confidence:   Confidence of the action (-1 = forced)
        """
        if self._status != SessionStatus.ACTIVE:
            return None
        step = self.current_step
        if step is None:
            return None
        return self._complete_step(step, action_class, confidence, time.monotonic())

    # ── Queries ───────────────────────────────────────────────────────────

    @property
    def current_step(self) -> Optional[SOPStep]:
        """The next expected SOP step, or None if session is complete."""
        if self._current_step_index < len(self.sop.steps):
            return self.sop.steps[self._current_step_index]
        return None

    @property
    def next_step(self) -> Optional[SOPStep]:
        """The step after the current one (look-ahead for UI hints)."""
        idx = self._current_step_index + 1
        if idx < len(self.sop.steps):
            return self.sop.steps[idx]
        return None

    @property
    def is_active(self) -> bool:
        return self._status == SessionStatus.ACTIVE

    @property
    def is_complete(self) -> bool:
        return self._status == SessionStatus.COMPLETED

    @property
    def action_window(self) -> list[int]:
        """Copy of the current sliding action window (read-only)."""
        return list(self._action_window)

    @property
    def progress_pct(self) -> float:
        """Completion percentage [0.0, 1.0]."""
        total = len(self.sop.steps)
        if total == 0:
            return 1.0
        return min(1.0, len(self._completed_step_ids) / total)

    @property
    def elapsed_seconds(self) -> float:
        """Total elapsed wall-clock seconds since session start."""
        if self._session_start == 0.0:
            return 0.0
        return time.monotonic() - self._session_start

    @property
    def pending_step_ids(self) -> list[int]:
        completed = set(self._completed_step_ids)
        return [s.id for s in self.sop.steps if s.id not in completed]

    def get_state(self) -> SessionState:
        """Return a frozen snapshot of the current session state."""
        return SessionState(
            sop_id=self.sop.id,
            session_id=self.session_id,
            status=self._status,
            current_step_index=self._current_step_index,
            completed_step_ids=list(self._completed_step_ids),
            step_records=list(self._step_records),
            pending_step_ids=self.pending_step_ids,
            action_window=self.action_window,
            session_start=self._session_start,
            last_action_at=self._last_action_at,
        )

    def step_time_remaining(self) -> Optional[float]:
        """
        Seconds remaining before the current step times out.
        Returns None if the current step has no time limit.
        """
        step = self.current_step
        if step is None or step.time_limit_seconds is None:
            return None
        elapsed = time.monotonic() - self._step_start_time
        return max(0.0, step.time_limit_seconds - elapsed)

    def missing_ppe(self, detected_labels: list[str]) -> list[str]:
        """
        Return PPE items required by the SOP but not currently detected.

        Args:
            detected_labels: Object labels from ObjectDetector in the current frame
        """
        required = self.sop.all_required_ppe()
        return [ppe for ppe in required if ppe not in detected_labels]

    def summary(self) -> dict:
        """
        High-level summary dict for logging / API responses.
        """
        return {
            "session_id": self.session_id,
            "sop_id": self.sop.id,
            "sop_name": self.sop.name,
            "status": self._status.value,
            "progress_pct": round(self.progress_pct * 100, 1),
            "steps_completed": len(self._completed_step_ids),
            "steps_total": len(self.sop.steps),
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "current_step": (
                {"id": self.current_step.id, "name": self.current_step.name}
                if self.current_step else None
            ),
            "completed_step_ids": list(self._completed_step_ids),
            "pending_step_ids": self.pending_step_ids,
        }
