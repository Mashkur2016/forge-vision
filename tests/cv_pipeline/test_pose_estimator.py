"""
Tests for src/cv_pipeline/pose_estimator.py — PoseResult, PoseLandmark, PoseEstimator.

MediaPipe is not available in CI/edge test environments, so PoseEstimator tests
that require the actual model are marked with pytest.importorskip.
Unit tests for data classes and to_flat_array() run without MediaPipe.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.cv_pipeline.pose_estimator import PoseLandmark, PoseResult


# ── PoseLandmark ───────────────────────────────────────────────────────────

class TestPoseLandmark:
    def test_fields(self):
        lm = PoseLandmark(x=0.5, y=0.3, z=-0.1, visibility=0.9)
        assert lm.x == 0.5
        assert lm.y == 0.3
        assert lm.z == -0.1
        assert lm.visibility == 0.9


# ── PoseResult ─────────────────────────────────────────────────────────────

class TestPoseResult:
    def _make_landmarks(self, n: int) -> list[PoseLandmark]:
        return [PoseLandmark(x=float(i) / n, y=0.5, z=0.0, visibility=1.0) for i in range(n)]

    def test_defaults(self):
        result = PoseResult()
        assert result.body_landmarks is None
        assert result.left_hand_landmarks is None
        assert result.right_hand_landmarks is None
        assert result.latency_ms == 0.0

    def test_person_detected_false_when_no_body(self):
        result = PoseResult()
        assert result.person_detected is False

    def test_person_detected_true_when_body_present(self):
        result = PoseResult(body_landmarks=self._make_landmarks(33))
        assert result.person_detected is True

    def test_num_body_landmarks(self):
        result = PoseResult(body_landmarks=self._make_landmarks(33))
        assert result.num_body_landmarks == 33

    def test_num_body_landmarks_zero_when_none(self):
        result = PoseResult()
        assert result.num_body_landmarks == 0

    def test_flat_array_dim_property(self):
        assert PoseResult().flat_array_dim == 300  # (33+21+21) * 4

    # ── to_flat_array() ───────────────────────────────────────────────────

    def test_flat_array_all_zeros_when_no_landmarks(self):
        result = PoseResult()
        arr = result.to_flat_array()
        assert arr.shape == (300,)
        assert arr.dtype == np.float32
        assert np.all(arr == 0.0)

    def test_flat_array_shape_with_full_data(self):
        body = self._make_landmarks(33)
        left = self._make_landmarks(21)
        right = self._make_landmarks(21)
        result = PoseResult(
            body_landmarks=body,
            left_hand_landmarks=left,
            right_hand_landmarks=right,
        )
        arr = result.to_flat_array()
        assert arr.shape == (300,)

    def test_flat_array_body_only(self):
        body = self._make_landmarks(33)
        result = PoseResult(body_landmarks=body)
        arr = result.to_flat_array()
        assert arr.shape == (300,)
        # Hand sections should be zero
        assert np.all(arr[33 * 4:] == 0.0)

    def test_flat_array_values_match_landmarks(self):
        body = [PoseLandmark(x=0.1, y=0.2, z=0.3, visibility=0.9)]
        # pad to 33
        body += [PoseLandmark(x=0.0, y=0.0, z=0.0, visibility=0.0)] * 32
        result = PoseResult(body_landmarks=body)
        arr = result.to_flat_array()
        assert arr[0] == pytest.approx(0.1)
        assert arr[1] == pytest.approx(0.2)
        assert arr[2] == pytest.approx(0.3)
        assert arr[3] == pytest.approx(0.9)

    def test_flat_array_dtype_float32(self):
        result = PoseResult(body_landmarks=self._make_landmarks(33))
        arr = result.to_flat_array()
        assert arr.dtype == np.float32


# ── get_landmark_name() ────────────────────────────────────────────────────

class TestGetLandmarkName:
    def test_known_indices(self):
        from src.cv_pipeline.pose_estimator import PoseEstimator
        assert PoseEstimator.get_landmark_name(0) == "nose"
        assert PoseEstimator.get_landmark_name(11) == "left_shoulder"
        assert PoseEstimator.get_landmark_name(15) == "left_wrist"
        assert PoseEstimator.get_landmark_name(32) == "right_foot_index"

    def test_out_of_range_returns_fallback(self):
        from src.cv_pipeline.pose_estimator import PoseEstimator
        assert PoseEstimator.get_landmark_name(99) == "landmark_99"
        assert PoseEstimator.get_landmark_name(-1) == "landmark_-1"


# ── PoseEstimator (requires MediaPipe) ────────────────────────────────────

@pytest.mark.skipif(
    pytest.importorskip("mediapipe", reason="mediapipe not installed") is None,
    reason="mediapipe not installed",
)
class TestPoseEstimatorIntegration:
    """Integration tests — only run when mediapipe is available."""

    def test_estimate_empty_frame_returns_empty_result(self):
        from src.cv_pipeline.pose_estimator import PoseEstimator
        estimator = PoseEstimator()
        result = estimator.estimate(np.array([], dtype=np.uint8).reshape(0, 0, 3))
        assert result.body_landmarks is None
        estimator.close()

    def test_context_manager(self):
        from src.cv_pipeline.pose_estimator import PoseEstimator
        with PoseEstimator() as estimator:
            assert estimator._holistic is not None
        # After exit, holistic should be released
        assert estimator._holistic is None

    def test_estimate_blank_frame_returns_result_object(self):
        from src.cv_pipeline.pose_estimator import PoseEstimator
        with PoseEstimator() as estimator:
            blank = np.zeros((480, 640, 3), dtype=np.uint8)
            result = estimator.estimate(blank)
            # Blank frame — no person, but should not raise
            assert isinstance(result.to_flat_array(), np.ndarray)
            assert result.to_flat_array().shape == (300,)
