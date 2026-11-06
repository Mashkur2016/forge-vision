"""
Tests for src/intelligence/sop_detector.py — SOPDeviationEvent, SOPDetector.

All tests use a lightweight SOPSequenceModel (no pretrained weights) running
on CPU, so they run in any environment.
"""
from __future__ import annotations

import numpy as np
import pytest
import torch

from src.cv_pipeline.frame_processor import FrameResult
from src.cv_pipeline.object_detector import Detection, DetectionResult
from src.cv_pipeline.pose_estimator import PoseLandmark, PoseResult
from src.intelligence.sop_detector import (
    DetectorConfig,
    DeviationSeverity,
    SOPDeviationEvent,
    SOPDetector,
)
from src.simulation.sop_schema import SOP, SOPStep
from src.training.models import SOPSequenceModel


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def simple_sop() -> SOP:
    return SOP(
        id="test_sop",
        name="Test SOP",
        steps=[
            SOPStep(id=1, name="Step 1", description="First step"),
            SOPStep(id=2, name="Step 2", description="Second step", safety_critical=True),
            SOPStep(id=3, name="Step 3", description="Third step"),
        ],
    )


@pytest.fixture
def ppe_sop() -> SOP:
    return SOP(
        id="ppe_sop",
        name="PPE SOP",
        required_ppe=["insulated_gloves", "safety_glasses"],
        steps=[
            SOPStep(id=1, name="Step 1", description="First step"),
            SOPStep(id=2, name="Step 2", description="Second step"),
        ],
    )


@pytest.fixture
def seq_model(simple_sop) -> SOPSequenceModel:
    """Untrained (random-weight) sequence model — sufficient for API/shape tests."""
    m = SOPSequenceModel(
        num_action_classes=len(simple_sop.steps),
        num_deviation_classes=6,
    )
    m.eval()
    return m


@pytest.fixture
def detector(simple_sop, seq_model) -> SOPDetector:
    cfg = DetectorConfig(
        deviation_confidence_threshold=0.0,   # accept any prediction
        min_window_frames=1,
        cooldown_seconds=0.0,
        ppe_missing_frames_threshold=1,
    )
    d = SOPDetector(simple_sop, seq_model, session_id="test", config=cfg)
    d.start_session()
    return d


@pytest.fixture
def blank_frame_result() -> FrameResult:
    pose = PoseResult()
    det = DetectionResult()
    return FrameResult(
        pose=pose,
        detections=det,
        pose_features=np.zeros(300, dtype=np.float32),
        total_latency_ms=10.0,
    )


@pytest.fixture
def frame_with_ppe(ppe_sop) -> FrameResult:
    det = DetectionResult(detections=[
        Detection("insulated_gloves", 0.9, 0.1, 0.1, 0.4, 0.4),
        Detection("safety_glasses",   0.85, 0.5, 0.1, 0.8, 0.4),
    ])
    return FrameResult(detections=det, pose_features=np.zeros(300, dtype=np.float32))


# ── SOPDeviationEvent ──────────────────────────────────────────────────────

class TestSOPDeviationEvent:
    def _make_event(self, deviation_class="CORRECT", severity=DeviationSeverity.LOW) -> SOPDeviationEvent:
        return SOPDeviationEvent(
            session_id="s1",
            sop_id="test_sop",
            sop_name="Test SOP",
            deviation_class=deviation_class,
            severity=severity,
            what="Test what",
            why="Test why",
        )

    def test_is_safety_critical_high(self):
        event = self._make_event(severity=DeviationSeverity.HIGH)
        assert event.is_safety_critical is True

    def test_is_safety_critical_low(self):
        event = self._make_event(severity=DeviationSeverity.LOW)
        assert event.is_safety_critical is False

    def test_requires_llm_feedback_correct(self):
        event = self._make_event(deviation_class="CORRECT")
        assert event.requires_llm_feedback is False

    def test_requires_llm_feedback_deviation_with_high_confidence(self):
        event = SOPDeviationEvent(
            session_id="s1", sop_id="x", sop_name="X",
            deviation_class="MISSING_STEP",
            model_confidence=0.85,
            what="w", why="y",
        )
        assert event.requires_llm_feedback is True

    def test_requires_llm_feedback_low_confidence(self):
        event = SOPDeviationEvent(
            session_id="s1", sop_id="x", sop_name="X",
            deviation_class="WRONG_ORDER",
            model_confidence=0.3,
            what="w", why="y",
        )
        assert event.requires_llm_feedback is False

    def test_to_dict_keys(self):
        event = self._make_event()
        d = event.to_dict()
        required_keys = {
            "session_id", "sop_id", "sop_name", "timestamp",
            "deviation_class", "severity", "what", "why",
            "model_confidence", "detection_latency_ms",
        }
        assert required_keys.issubset(d.keys())

    def test_to_dict_values(self):
        event = self._make_event(deviation_class="MISSING_PPE", severity=DeviationSeverity.HIGH)
        d = event.to_dict()
        assert d["deviation_class"] == "MISSING_PPE"
        assert d["severity"] == "high"


# ── SOPDetector lifecycle ──────────────────────────────────────────────────

class TestSOPDetectorLifecycle:
    def test_tracker_active_after_start(self, detector):
        assert detector.tracker.is_active is True

    def test_events_empty_at_start(self, detector):
        assert detector.events == []

    def test_deviation_count_zero_at_start(self, detector):
        assert detector.deviation_count == 0

    def test_end_session_returns_events(self, detector, blank_frame_result):
        detector.process_frame(blank_frame_result, action_class=0)
        events = detector.end_session()
        assert isinstance(events, list)

    def test_process_after_end_returns_none(self, detector, blank_frame_result):
        detector.end_session()
        result = detector.process_frame(blank_frame_result, action_class=0)
        assert result is None


# ── process_frame() ────────────────────────────────────────────────────────

class TestProcessFrame:
    def test_returns_event_when_window_filled(self, detector, blank_frame_result):
        event = detector.process_frame(blank_frame_result, action_class=0)
        assert isinstance(event, SOPDeviationEvent)

    def test_event_has_correct_sop_id(self, detector, blank_frame_result):
        event = detector.process_frame(blank_frame_result, action_class=0)
        assert event.sop_id == "test_sop"

    def test_event_has_what_and_why(self, detector, blank_frame_result):
        event = detector.process_frame(blank_frame_result, action_class=0)
        assert event.what != ""
        assert event.why != ""

    def test_event_deviation_class_valid(self, detector, blank_frame_result):
        event = detector.process_frame(blank_frame_result, action_class=0)
        from src.training.models import SOPSequenceModel
        assert event.deviation_class in SOPSequenceModel.DEVIATION_CLASSES

    def test_event_model_confidence_in_range(self, detector, blank_frame_result):
        event = detector.process_frame(blank_frame_result, action_class=0)
        assert 0.0 <= event.model_confidence <= 1.0

    def test_event_latency_positive(self, detector, blank_frame_result):
        event = detector.process_frame(blank_frame_result, action_class=0)
        assert event.detection_latency_ms >= 0.0

    def test_events_accumulate(self, detector, blank_frame_result):
        cfg = DetectorConfig(
            deviation_confidence_threshold=0.0,
            min_window_frames=1,
            cooldown_seconds=0.0,
        )
        detector.config = cfg
        for _ in range(3):
            detector.process_frame(blank_frame_result, action_class=1)
        assert len(detector.events) > 0

    def test_none_returned_when_window_too_short(self, simple_sop, seq_model):
        cfg = DetectorConfig(min_window_frames=100, cooldown_seconds=0.0)
        d = SOPDetector(simple_sop, seq_model, config=cfg)
        d.start_session()
        blank = FrameResult(pose_features=np.zeros(300, dtype=np.float32))
        result = d.process_frame(blank, action_class=0)
        assert result is None


# ── PPE check ──────────────────────────────────────────────────────────────

class TestPPECheck:
    def test_no_event_when_ppe_present(self, ppe_sop, seq_model, frame_with_ppe):
        cfg = DetectorConfig(
            ppe_missing_frames_threshold=1,
            deviation_confidence_threshold=1.1,  # block LSTM from firing
            min_window_frames=999,
            cooldown_seconds=0.0,
        )
        d = SOPDetector(ppe_sop, seq_model, config=cfg)
        d.start_session()
        event = d.process_frame(frame_with_ppe, action_class=0)
        assert event is None

    def test_ppe_event_when_ppe_missing(self, ppe_sop, seq_model):
        cfg = DetectorConfig(
            ppe_missing_frames_threshold=1,
            deviation_confidence_threshold=1.1,  # block LSTM
            min_window_frames=999,
            cooldown_seconds=0.0,
        )
        d = SOPDetector(ppe_sop, seq_model, config=cfg)
        d.start_session()
        # Frame with no PPE detected
        blank = FrameResult(
            detections=DetectionResult(),
            pose_features=np.zeros(300, dtype=np.float32),
        )
        event = d.process_frame(blank, action_class=0)
        assert event is not None
        assert event.deviation_class == "MISSING_PPE"
        assert event.severity == DeviationSeverity.HIGH


# ── Severity classification ────────────────────────────────────────────────

class TestSeverityClassification:
    def test_correct_is_low(self, detector, simple_sop):
        # _classify_severity is tested indirectly via the event
        safety_step = simple_sop.steps[1]  # step 2 is safety_critical=True
        severity = detector._classify_severity("CORRECT", safety_step)
        assert severity == DeviationSeverity.LOW

    def test_missing_ppe_always_high(self, detector):
        severity = detector._classify_severity("MISSING_PPE", None)
        assert severity == DeviationSeverity.HIGH

    def test_unsafe_posture_always_high(self, detector):
        severity = detector._classify_severity("UNSAFE_POSTURE", None)
        assert severity == DeviationSeverity.HIGH

    def test_missing_step_safety_critical_is_high(self, detector, simple_sop):
        safety_step = simple_sop.steps[1]  # safety_critical=True
        severity = detector._classify_severity("MISSING_STEP", safety_step)
        assert severity == DeviationSeverity.HIGH

    def test_wrong_order_non_critical_is_medium(self, detector, simple_sop):
        non_critical = simple_sop.steps[0]  # safety_critical=False
        severity = detector._classify_severity("WRONG_ORDER", non_critical)
        assert severity == DeviationSeverity.MEDIUM


# ── Explain ───────────────────────────────────────────────────────────────

class TestExplain:
    def test_correct_what_and_why(self, detector, simple_sop):
        what, why = detector._explain("CORRECT", simple_sop.steps[0], 0)
        assert "correctly" in what.lower()
        assert len(why) > 0

    def test_missing_step_what_contains_step_name(self, detector, simple_sop):
        step = simple_sop.steps[0]
        what, why = detector._explain("MISSING_STEP", step, 5)
        assert "Step 1" in what or "Step" in what

    def test_missing_ppe_what(self, detector):
        what, why = detector._explain("MISSING_PPE", None, -1)
        assert "ppe" in what.lower() or "equipment" in what.lower()

    def test_unsafe_posture_what(self, detector):
        what, why = detector._explain("UNSAFE_POSTURE", None, -1)
        assert len(what) > 0
        assert len(why) > 0

    def test_unknown_deviation_returns_fallback(self, detector):
        what, why = detector._explain("UNKNOWN_CLASS", None, -1)
        assert len(what) > 0
        assert len(why) > 0


# ── Session summary ────────────────────────────────────────────────────────

class TestSessionSummary:
    def test_summary_keys(self, detector, blank_frame_result):
        detector.process_frame(blank_frame_result, action_class=0)
        summary = detector.session_summary()
        assert "total_events" in summary
        assert "deviations" in summary
        assert "high_severity_count" in summary
        assert "safety_critical_violations" in summary
        assert "events" in summary

    def test_summary_events_is_list_of_dicts(self, detector, blank_frame_result):
        detector.process_frame(blank_frame_result, action_class=0)
        summary = detector.session_summary()
        assert isinstance(summary["events"], list)
        if summary["events"]:
            assert isinstance(summary["events"][0], dict)
