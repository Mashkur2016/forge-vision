"""
Tests for src/cv_pipeline/frame_processor.py — FrameResult, FrameProcessor.

FrameProcessor integration tests are skipped unless both mediapipe and
ultralytics are installed.  FrameResult data-class tests always run.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.cv_pipeline.frame_processor import FrameResult
from src.cv_pipeline.object_detector import Detection, DetectionResult
from src.cv_pipeline.pose_estimator import PoseLandmark, PoseResult


# ── FrameResult ────────────────────────────────────────────────────────────

class TestFrameResult:
    def _make_pose(self, detected: bool = True) -> PoseResult:
        if detected:
            landmarks = [
                PoseLandmark(x=float(i) / 33, y=0.5, z=0.0, visibility=1.0)
                for i in range(33)
            ]
            return PoseResult(body_landmarks=landmarks, latency_ms=20.0)
        return PoseResult(latency_ms=20.0)

    def _make_detections(self) -> DetectionResult:
        return DetectionResult(
            detections=[
                Detection("insulated_gloves", 0.9, 0.1, 0.1, 0.3, 0.3),
                Detection("safety_glasses",   0.8, 0.4, 0.1, 0.6, 0.3),
            ],
            latency_ms=30.0,
        )

    def test_defaults(self):
        result = FrameResult()
        assert result.pose_features.shape == (300,)
        assert result.total_latency_ms == 0.0
        assert result.person_detected is False

    def test_person_detected_delegates_to_pose(self):
        result = FrameResult(pose=self._make_pose(detected=True))
        assert result.person_detected is True

    def test_detected_labels(self):
        result = FrameResult(detections=self._make_detections())
        assert "insulated_gloves" in result.detected_labels
        assert "safety_glasses" in result.detected_labels

    def test_missing_ppe_all_present(self):
        result = FrameResult(detections=self._make_detections())
        missing = result.missing_ppe(["insulated_gloves", "safety_glasses"])
        assert missing == []

    def test_missing_ppe_some_absent(self):
        result = FrameResult(detections=self._make_detections())
        missing = result.missing_ppe(["insulated_gloves", "hard_hat"])
        assert "hard_hat" in missing
        assert "insulated_gloves" not in missing

    def test_to_feature_dict_keys(self):
        result = FrameResult(
            pose=self._make_pose(),
            detections=self._make_detections(),
            total_latency_ms=55.0,
        )
        d = result.to_feature_dict()
        assert "pose_features" in d
        assert "detected_objects" in d
        assert "person_detected" in d
        assert "detection_confidences" in d
        assert "latency_ms" in d

    def test_to_feature_dict_pose_features_length(self):
        pose = self._make_pose()
        result = FrameResult(
            pose=pose,
            pose_features=pose.to_flat_array(),
        )
        d = result.to_feature_dict()
        assert len(d["pose_features"]) == 300

    def test_to_feature_dict_latency_structure(self):
        result = FrameResult(
            preprocess_latency_ms=5.0,
            total_latency_ms=60.0,
        )
        d = result.to_feature_dict()
        assert "preprocess" in d["latency_ms"]
        assert "total" in d["latency_ms"]
        assert d["latency_ms"]["total"] == pytest.approx(60.0)

    def test_detection_confidences_dict(self):
        result = FrameResult(detections=self._make_detections())
        d = result.to_feature_dict()
        confs = d["detection_confidences"]
        assert "insulated_gloves" in confs
        assert confs["insulated_gloves"] == pytest.approx(0.9)


# ── FrameProcessor integration ─────────────────────────────────────────────

@pytest.fixture
def bgr_frame() -> np.ndarray:
    rng = np.random.default_rng(99)
    return rng.integers(0, 256, (480, 640, 3), dtype=np.uint8)


class TestFrameProcessorNoPose:
    """Tests that run without mediapipe or ultralytics — pose/detection disabled."""

    def test_process_no_pose_no_detection(self, bgr_frame):
        from src.cv_pipeline.frame_processor import FrameProcessor
        with FrameProcessor(run_pose=False, run_detection=False) as fp:
            result = fp.process(bgr_frame)
        assert isinstance(result, FrameResult)
        assert result.total_latency_ms > 0.0
        assert result.pose_features.shape == (300,)
        assert result.detections.detections == []

    def test_process_returns_frame_result(self, bgr_frame):
        from src.cv_pipeline.frame_processor import FrameProcessor
        fp = FrameProcessor(run_pose=False, run_detection=False)
        result = fp.process(bgr_frame)
        assert isinstance(result, FrameResult)
        fp.close()

    def test_context_manager_close(self, bgr_frame):
        from src.cv_pipeline.frame_processor import FrameProcessor
        with FrameProcessor(run_pose=False, run_detection=False) as fp:
            result = fp.process(bgr_frame)
        assert result is not None  # no exception on close


@pytest.mark.skipif(
    pytest.importorskip("mediapipe", reason="mediapipe not installed") is None,
    reason="mediapipe not installed",
)
class TestFrameProcessorWithPose:
    def test_process_with_pose_only(self, bgr_frame):
        from src.cv_pipeline.frame_processor import FrameProcessor
        with FrameProcessor(run_pose=True, run_detection=False) as fp:
            result = fp.process(bgr_frame)
        assert isinstance(result, FrameResult)
        assert result.pose_features.shape == (300,)
        assert result.pose.latency_ms > 0.0
