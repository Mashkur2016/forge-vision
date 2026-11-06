"""
Pose Estimator — MediaPipe Holistic wrapper for FORGE-Vision.

Extracts 33 body landmarks (BlazePose) + hand landmarks from video frames.
Returns a normalised landmark array suitable for feature engineering and
action recognition input.

Architecture.md Layer 2: "Pose Estimation — MediaPipe Holistic — 33 landmarks + hands"
Performance target (Rules.md §1.7): ≥ 85% detection accuracy, < 100ms latency.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# ── Result types ───────────────────────────────────────────────────────────

@dataclass
class PoseLandmark:
    """A single 3D pose landmark with visibility score."""
    x: float        # Normalised [0, 1] relative to frame width
    y: float        # Normalised [0, 1] relative to frame height
    z: float        # Depth (relative to hip, smaller = closer to camera)
    visibility: float   # Confidence that landmark is visible [0, 1]


@dataclass
class PoseResult:
    """Full pose estimation result for one frame."""

    # 33 BlazePose body landmarks (None if no person detected)
    body_landmarks: Optional[list[PoseLandmark]] = None

    # 21 landmarks per hand (None if hand not detected)
    left_hand_landmarks: Optional[list[PoseLandmark]] = None
    right_hand_landmarks: Optional[list[PoseLandmark]] = None

    # Processing latency in milliseconds
    latency_ms: float = 0.0

    @property
    def person_detected(self) -> bool:
        return self.body_landmarks is not None

    @property
    def num_body_landmarks(self) -> int:
        return len(self.body_landmarks) if self.body_landmarks else 0

    def to_flat_array(self) -> np.ndarray:
        """
        Flatten all landmarks into a 1D numpy array for model input.

        Returns array of shape (33*4 + 21*4 + 21*4,) = (300,) with
        [x, y, z, visibility] for each landmark, zeros for missing data.
        """
        def _landmarks_to_array(landmarks: Optional[list[PoseLandmark]], n: int) -> np.ndarray:
            arr = np.zeros(n * 4, dtype=np.float32)
            if landmarks:
                for i, lm in enumerate(landmarks[:n]):
                    arr[i * 4 : i * 4 + 4] = [lm.x, lm.y, lm.z, lm.visibility]
            return arr

        body = _landmarks_to_array(self.body_landmarks, 33)
        left = _landmarks_to_array(self.left_hand_landmarks, 21)
        right = _landmarks_to_array(self.right_hand_landmarks, 21)
        return np.concatenate([body, left, right])

    @property
    def flat_array_dim(self) -> int:
        """Dimension of the flat landmark array: (33+21+21) * 4 = 300."""
        return 300


# ── Estimator ──────────────────────────────────────────────────────────────

class PoseEstimator:
    """
    MediaPipe Holistic pose estimator.

    Wraps mediapipe.solutions.holistic to extract body + hand landmarks
    from BGR frames. The instance holds the MediaPipe model in memory for
    efficient processing of consecutive frames.

    Usage:
        estimator = PoseEstimator()
        result = estimator.estimate(bgr_frame)
        if result.person_detected:
            features = result.to_flat_array()  # shape (300,)

    Note:
        MediaPipe requires RGB input. This class handles the BGR→RGB conversion
        internally, so callers always pass raw BGR frames as captured by OpenCV.
    """

    BODY_LANDMARK_COUNT = 33
    HAND_LANDMARK_COUNT = 21

    def __init__(
        self,
        model_complexity: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        self.model_complexity = model_complexity
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self._holistic = None   # Lazy initialisation on first call
        self._init_mediapipe()

    def _init_mediapipe(self) -> None:
        try:
            import mediapipe as mp
            self._mp_holistic = mp.solutions.holistic
            self._holistic = self._mp_holistic.Holistic(
                model_complexity=self.model_complexity,
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
                enable_segmentation=False,
            )
        except ImportError:
            raise ImportError(
                "MediaPipe is not installed. "
                "Add 'mediapipe==0.10.14' to requirements.txt and reinstall."
            )

    def estimate(self, bgr_frame: np.ndarray) -> PoseResult:
        """
        Run pose estimation on a single BGR frame.

        Args:
            bgr_frame: uint8 BGR numpy array of shape (H, W, 3).

        Returns:
            PoseResult with body and hand landmarks.
        """
        import time
        import cv2

        if bgr_frame is None or bgr_frame.size == 0:
            return PoseResult()

        t0 = time.perf_counter()

        # MediaPipe requires RGB, not BGR
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        mp_result = self._holistic.process(rgb)
        rgb.flags.writeable = True

        latency_ms = (time.perf_counter() - t0) * 1000.0

        body = self._parse_landmarks(mp_result.pose_landmarks, self.BODY_LANDMARK_COUNT)
        left = self._parse_landmarks(mp_result.left_hand_landmarks, self.HAND_LANDMARK_COUNT)
        right = self._parse_landmarks(mp_result.right_hand_landmarks, self.HAND_LANDMARK_COUNT)

        return PoseResult(
            body_landmarks=body,
            left_hand_landmarks=left,
            right_hand_landmarks=right,
            latency_ms=latency_ms,
        )

    def close(self) -> None:
        """Release MediaPipe resources."""
        if self._holistic is not None:
            self._holistic.close()
            self._holistic = None

    def __enter__(self) -> "PoseEstimator":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_landmarks(mp_landmarks, expected_count: int) -> Optional[list[PoseLandmark]]:
        if mp_landmarks is None:
            return None
        return [
            PoseLandmark(x=lm.x, y=lm.y, z=lm.z, visibility=getattr(lm, "visibility", 1.0))
            for lm in mp_landmarks.landmark[:expected_count]
        ]

    @staticmethod
    def get_landmark_name(index: int) -> str:
        """Return the MediaPipe BlazePose landmark name for a given index."""
        _NAMES = [
            "nose", "left_eye_inner", "left_eye", "left_eye_outer",
            "right_eye_inner", "right_eye", "right_eye_outer",
            "left_ear", "right_ear", "mouth_left", "mouth_right",
            "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
            "left_wrist", "right_wrist", "left_pinky", "right_pinky",
            "left_index", "right_index", "left_thumb", "right_thumb",
            "left_hip", "right_hip", "left_knee", "right_knee",
            "left_ankle", "right_ankle", "left_heel", "right_heel",
            "left_foot_index", "right_foot_index",
        ]
        if 0 <= index < len(_NAMES):
            return _NAMES[index]
        return f"landmark_{index}"
