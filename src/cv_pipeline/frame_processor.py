"""
Frame Processor — combined CV pipeline for FORGE-Vision.

Chains Preprocessor → PoseEstimator → ObjectDetector and returns a single
FrameResult containing all extracted features, ready for the Intelligence Layer.

Architecture.md Layer 2: The full Processing Layer running on each video frame.
Latency budget: pose < 100ms + detection < 100ms ≤ 200ms per frame (< 500ms total
action recognition budget per Rules.md §1.7).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.cv_pipeline.object_detector import DetectionResult, ObjectDetector
from src.cv_pipeline.pose_estimator import PoseEstimator, PoseResult
from src.cv_pipeline.preprocessor import FramePreprocessor, PreprocessConfig


# ── Result type ────────────────────────────────────────────────────────────

@dataclass
class FrameResult:
    """
    Aggregated output of the full CV pipeline for one video frame.

    Passed to the Intelligence Layer for SOP deviation detection.
    """
    # Raw pose data
    pose: PoseResult = field(default_factory=PoseResult)

    # Object detections
    detections: DetectionResult = field(default_factory=DetectionResult)

    # Flat landmark feature vector for model input (shape: 300,)
    pose_features: np.ndarray = field(default_factory=lambda: np.zeros(300, dtype=np.float32))

    # Preprocessing latency
    preprocess_latency_ms: float = 0.0

    # Total pipeline latency
    total_latency_ms: float = 0.0

    @property
    def person_detected(self) -> bool:
        return self.pose.person_detected

    @property
    def detected_labels(self) -> list[str]:
        return self.detections.labels

    def missing_ppe(self, required_ppe: list[str]) -> list[str]:
        return self.detections.missing_ppe(required_ppe)

    def to_feature_dict(self) -> dict:
        """Structured feature dict for the Intelligence Layer."""
        return {
            "pose_features": self.pose_features.tolist(),
            "detected_objects": self.detected_labels,
            "person_detected": self.person_detected,
            "detection_confidences": {
                d.label: d.confidence for d in self.detections.detections
            },
            "latency_ms": {
                "preprocess": round(self.preprocess_latency_ms, 2),
                "pose": round(self.pose.latency_ms, 2),
                "detection": round(self.detections.latency_ms, 2),
                "total": round(self.total_latency_ms, 2),
            },
        }


# ── Processor ──────────────────────────────────────────────────────────────

class FrameProcessor:
    """
    Orchestrates the full per-frame CV pipeline:

        BGR frame
            → FramePreprocessor  (resize, optional denoise)
            → PoseEstimator      (MediaPipe Holistic, 33 landmarks)
            → ObjectDetector     (YOLOv8n, tools + PPE)
            → FrameResult

    The processor is designed to hold long-lived model instances — construct
    once and call process() on every frame in a session.

    Usage:
        processor = FrameProcessor()
        result = processor.process(bgr_frame)
        if result.person_detected:
            features = result.pose_features  # (300,) float32
    """

    def __init__(
        self,
        preprocess_config: Optional[PreprocessConfig] = None,
        pose_model_complexity: int = 1,
        pose_min_detection_conf: float = 0.5,
        pose_min_tracking_conf: float = 0.5,
        yolo_model_path: str = "yolov8n.pt",
        yolo_conf_threshold: float = 0.40,
        yolo_device: str = "auto",
        run_detection: bool = True,
        run_pose: bool = True,
    ) -> None:
        self._preprocessor = FramePreprocessor(preprocess_config)
        self._run_pose = run_pose
        self._run_detection = run_detection

        if run_pose:
            self._pose_estimator = PoseEstimator(
                model_complexity=pose_model_complexity,
                min_detection_confidence=pose_min_detection_conf,
                min_tracking_confidence=pose_min_tracking_conf,
            )

        if run_detection:
            self._detector = ObjectDetector(
                model_path=yolo_model_path,
                conf_threshold=yolo_conf_threshold,
                device=yolo_device,
            )

    def process(self, bgr_frame: np.ndarray) -> FrameResult:
        """
        Run the full CV pipeline on one BGR frame.

        Args:
            bgr_frame: uint8 BGR numpy array from OpenCV or video source.

        Returns:
            FrameResult with pose landmarks, object detections, and latency info.
        """
        t_start = time.perf_counter()

        # ── Preprocessing ──────────────────────────────────────────────────
        t0 = time.perf_counter()
        preprocessed = self._preprocessor.process_uint8(bgr_frame)
        preprocess_ms = (time.perf_counter() - t0) * 1000.0

        # ── Pose estimation ────────────────────────────────────────────────
        pose_result = PoseResult()
        if self._run_pose:
            pose_result = self._pose_estimator.estimate(preprocessed)

        # ── Object detection ───────────────────────────────────────────────
        detection_result = DetectionResult()
        if self._run_detection:
            detection_result = self._detector.detect(preprocessed)

        total_ms = (time.perf_counter() - t_start) * 1000.0

        return FrameResult(
            pose=pose_result,
            detections=detection_result,
            pose_features=pose_result.to_flat_array(),
            preprocess_latency_ms=preprocess_ms,
            total_latency_ms=total_ms,
        )

    def close(self) -> None:
        """Release model resources."""
        if self._run_pose and hasattr(self, "_pose_estimator"):
            self._pose_estimator.close()

    def __enter__(self) -> "FrameProcessor":
        return self

    def __exit__(self, *_) -> None:
        self.close()
