"""
Tests for src/intelligence/sequence_tracker.py — SOPSequenceTracker.
"""
from __future__ import annotations

import time

import pytest

from src.intelligence.sequence_tracker import (
    SessionStatus,
    SOPSequenceTracker,
    StepRecord,
)
from src.simulation.sop_schema import SOP, SOPStep


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def simple_sop() -> SOP:
    """3-step SOP for tracker testing."""
    return SOP(
        id="test_sop",
        name="Test SOP",
        steps=[
            SOPStep(id=1, name="Step 1", description="First step"),
            SOPStep(id=2, name="Step 2", description="Second step"),
            SOPStep(id=3, name="Step 3", description="Third step"),
        ],
    )


@pytest.fixture
def ppe_sop() -> SOP:
    """SOP with PPE requirements."""
    return SOP(
        id="ppe_sop",
        name="PPE SOP",
        required_ppe=["insulated_gloves", "safety_glasses"],
        steps=[
            SOPStep(
                id=1,
                name="Step 1",
                description="First step",
                required_ppe=["insulated_gloves"],
                safety_critical=True,
            ),
            SOPStep(id=2, name="Step 2", description="Second step"),
        ],
    )


@pytest.fixture
def tracker(simple_sop) -> SOPSequenceTracker:
    t = SOPSequenceTracker(simple_sop, session_id="test_session")
    t.start()
    return t


# ── Initialisation ─────────────────────────────────────────────────────────

class TestSOPSequenceTrackerInit:
    def test_idle_before_start(self, simple_sop):
        t = SOPSequenceTracker(simple_sop)
        assert t._status == SessionStatus.IDLE

    def test_active_after_start(self, tracker):
        assert tracker.is_active is True

    def test_first_step_after_start(self, tracker, simple_sop):
        assert tracker.current_step is not None
        assert tracker.current_step.id == 1

    def test_progress_zero_at_start(self, tracker):
        assert tracker.progress_pct == pytest.approx(0.0)


# ── record_action() ────────────────────────────────────────────────────────

class TestRecordAction:
    def test_correct_action_completes_step(self, tracker):
        # Step 1 maps to action class 0 (id-1)
        record = tracker.record_action(action_class=0, confidence=0.9)
        assert record is not None
        assert isinstance(record, StepRecord)
        assert record.step_id == 1

    def test_step_advances_after_completion(self, tracker):
        tracker.record_action(action_class=0)
        assert tracker.current_step.id == 2

    def test_wrong_action_returns_none(self, tracker):
        record = tracker.record_action(action_class=5)  # not step 1
        assert record is None
        assert tracker.current_step.id == 1  # no advance

    def test_all_steps_completes_session(self, tracker):
        tracker.record_action(action_class=0)  # step 1
        tracker.record_action(action_class=1)  # step 2
        tracker.record_action(action_class=2)  # step 3
        assert tracker.is_complete is True

    def test_record_after_complete_returns_none(self, tracker):
        for i in range(3):
            tracker.record_action(action_class=i)
        result = tracker.record_action(action_class=0)
        assert result is None

    def test_step_record_duration_positive(self, tracker):
        record = tracker.record_action(action_class=0)
        assert record.duration_seconds >= 0.0

    def test_step_record_confidence_stored(self, tracker):
        record = tracker.record_action(action_class=0, confidence=0.75)
        assert record.confidence == pytest.approx(0.75)


# ── Action window ──────────────────────────────────────────────────────────

class TestActionWindow:
    def test_window_grows(self, tracker):
        # Use action_class=99 — never matches any step, so session stays ACTIVE
        for _ in range(5):
            tracker.record_action(action_class=99)
        assert len(tracker.action_window) == 5

    def test_window_capped_at_max(self, tracker):
        for i in range(tracker.window_size + 10):
            tracker.record_action(action_class=i % 3)
        assert len(tracker.action_window) <= tracker.window_size

    def test_window_is_copy(self, tracker):
        tracker.record_action(action_class=0)
        w1 = tracker.action_window
        w1.append(99)
        w2 = tracker.action_window
        assert 99 not in w2


# ── Progress and queries ───────────────────────────────────────────────────

class TestProgressAndQueries:
    def test_progress_increases_with_steps(self, tracker):
        tracker.record_action(action_class=0)
        assert tracker.progress_pct == pytest.approx(1 / 3)
        tracker.record_action(action_class=1)
        assert tracker.progress_pct == pytest.approx(2 / 3)

    def test_pending_step_ids_start_full(self, tracker, simple_sop):
        assert tracker.pending_step_ids == [1, 2, 3]

    def test_pending_step_ids_decrease(self, tracker):
        tracker.record_action(action_class=0)
        assert tracker.pending_step_ids == [2, 3]

    def test_next_step(self, tracker):
        assert tracker.next_step.id == 2

    def test_next_step_none_when_last(self, tracker):
        tracker.record_action(action_class=0)
        tracker.record_action(action_class=1)
        # Now on last step
        assert tracker.next_step is None

    def test_elapsed_seconds_positive(self, tracker):
        assert tracker.elapsed_seconds >= 0.0

    def test_elapsed_seconds_idle(self, simple_sop):
        t = SOPSequenceTracker(simple_sop)
        assert t.elapsed_seconds == 0.0


# ── Missing PPE ────────────────────────────────────────────────────────────

class TestMissingPPE:
    def test_all_present(self, ppe_sop):
        t = SOPSequenceTracker(ppe_sop)
        t.start()
        missing = t.missing_ppe(["insulated_gloves", "safety_glasses"])
        assert missing == []

    def test_some_missing(self, ppe_sop):
        t = SOPSequenceTracker(ppe_sop)
        t.start()
        missing = t.missing_ppe(["insulated_gloves"])
        assert "safety_glasses" in missing

    def test_no_ppe_required(self, simple_sop):
        t = SOPSequenceTracker(simple_sop)
        t.start()
        assert t.missing_ppe(["anything"]) == []


# ── force_advance() ────────────────────────────────────────────────────────

class TestForceAdvance:
    def test_advances_without_match(self, tracker):
        original_step = tracker.current_step.id
        tracker.force_advance()
        assert tracker.current_step.id == original_step + 1

    def test_force_advance_returns_step_record(self, tracker):
        record = tracker.force_advance()
        assert isinstance(record, StepRecord)

    def test_force_advance_all_completes(self, tracker):
        for _ in range(3):
            tracker.force_advance()
        assert tracker.is_complete is True


# ── Session state snapshot ─────────────────────────────────────────────────

class TestGetState:
    def test_snapshot_reflects_current_state(self, tracker):
        tracker.record_action(action_class=0)
        state = tracker.get_state()
        assert state.sop_id == "test_sop"
        assert state.session_id == "test_session"
        assert 1 in state.completed_step_ids
        assert state.current_step_index == 1

    def test_snapshot_status_active(self, tracker):
        state = tracker.get_state()
        assert state.status == SessionStatus.ACTIVE

    def test_snapshot_status_completed(self, tracker):
        for i in range(3):
            tracker.record_action(action_class=i)
        state = tracker.get_state()
        assert state.status == SessionStatus.COMPLETED


# ── summary() ─────────────────────────────────────────────────────────────

class TestSummary:
    def test_summary_keys(self, tracker):
        summary = tracker.summary()
        required_keys = {
            "session_id", "sop_id", "sop_name", "status",
            "progress_pct", "steps_completed", "steps_total",
            "current_step", "completed_step_ids",
        }
        assert required_keys.issubset(summary.keys())

    def test_summary_progress_correct(self, tracker):
        tracker.record_action(action_class=0)
        summary = tracker.summary()
        assert summary["steps_completed"] == 1
        assert summary["steps_total"] == 3
        assert summary["progress_pct"] == pytest.approx(100 / 3, abs=0.5)

    def test_reset_restarts_session(self, tracker):
        tracker.record_action(action_class=0)
        tracker.record_action(action_class=1)
        tracker.reset()
        assert tracker.progress_pct == 0.0
        assert tracker.current_step.id == 1
