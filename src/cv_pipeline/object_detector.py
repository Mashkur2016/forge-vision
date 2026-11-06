"""
Object Detector — YOLOv8n wrapper for FORGE-Vision.

Detects workplace objects (tools, PPE, equipment) in video frames using
YOLOv8 nano — the edge-compatible model variant chosen to meet the Jetson
deployment constraint (Rules.md edge compatibility, ≤10W).

Architecture.md Layer 2: "Object Detection — YOLOv8/v9 — tools, PPE, objects"
Performance target: < 100ms latency per frame (Rules.md §1.7).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np


# ── Result types ───────────────────────────────────────────────────────────

@dataclass
class Detection:
    """A single bounding box detection."""
    label: str          # Class name (e.g. "insulated_gloves", "red_wire")
    confidence: float   # Detection confidence [0, 1]
    x1: float           # Bounding box left (normalised [0,1] or pixel depending on config)
    y1: float           # Bounding box top
    x2: float           # Bounding box right
    y2: float           # Bounding box bottom
    class_id: int = 0

    @property
    def bbox_area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)

    @property
    def centre(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


@dataclass
class DetectionResult:
    """All detections for one frame."""
    detections: list[Detection] = field(default_factory=list)
    latency_ms: float = 0.0
    frame_width: int = 640
    frame_height: int = 480

    @property
    def labels(self) -> list[str]:
        return [d.label for d in self.detections]

    def get_by_label(self, label: str) -> list[Detection]:
        return [d for d in self.detections if d.label == label]

    def has_label(self, label: str) -> bool:
        return any(d.label == label for d in self.detections)

    def above_confidence(self, threshold: float) -> list[Detection]:
        return [d for d in self.detections if d.confidence >= threshold]

    def check_ppe_present(self, required_ppe: list[str]) -> dict[str, bool]:
        """Return a mapping of required PPE label → whether it was detected."""
        return {ppe: self.has_label(ppe) for ppe in required_ppe}

    def missing_ppe(self, required_ppe: list[str]) -> list[str]:
        """Return list of PPE items not detected in this frame."""
        return [ppe for ppe in required_ppe if not self.has_label(ppe)]


# ── Detector ───────────────────────────────────────────────────────────────

class ObjectDetector:
    """
    YOLOv8n wrapper for workplace object and PPE detection.

    Lazy-loads the YOLO model on first use. Accepts BGR frames (as from
    OpenCV) and returns structured DetectionResult objects.

    Usage:
        detector = ObjectDetector(model_path="yolov8n.pt")
        result = detector.detect(bgr_frame)
        if result.has_label("insulated_gloves"):
            ...

    For Phase A (synthetic data), the model runs on generic COCO classes.
    In Phase B fine-tuning, a custom workplace model replaces the base weights.
    """

    def __init__(
        self,
        model_path: str | Path = "yolov8n.pt",
        conf_threshold: float = 0.40,
        iou_threshold: float = 0.45,
        img_size: int = 640,
        device: str = "auto",
    ) -> None:
        self.model_path = str(model_path)
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.img_size = img_size
        self._device = self._resolve_device(device)
        self._model = None     # Lazy-loaded on first detect() call

    def detect(self, bgr_frame: np.ndarray) -> DetectionResult:
        """
        Run object detection on a single BGR frame.

        Args:
            bgr_frame: uint8 BGR numpy array.

        Returns:
            DetectionResult with all detections above conf_threshold.
        """
        if bgr_frame is None or bgr_frame.size == 0:
            return DetectionResult()

        model = self._get_model()
        h, w = bgr_frame.shape[:2]
        t0 = time.perf_counter()

        results = model.predict(
            source=bgr_frame,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            imgsz=self.img_size,
            device=self._device,
            verbose=False,
        )

        latency_ms = (time.perf_counter() - t0) * 1000.0

        detections: list[Detection] = []
        if results and len(results) > 0:
            result = results[0]
            if result.boxes is not None:
                for box in result.boxes:
                    cls_id = int(box.cls.item())
                    label = model.names.get(cls_id, f"class_{cls_id}")
                    conf = float(box.conf.item())
                    x1, y1, x2, y2 = box.xyxyn[0].tolist()   # normalised [0,1]
                    detections.append(Detection(
                        label=label,
                        confidence=conf,
                        x1=x1, y1=y1, x2=x2, y2=y2,
                        class_id=cls_id,
                    ))

        return DetectionResult(
            detections=detections,
            latency_ms=latency_ms,
            frame_width=w,
            frame_height=h,
        )

    def load(self) -> None:
        """Explicitly pre-load the model (avoids cold start on first detect())."""
        self._get_model()

    def _get_model(self):
        if self._model is None:
            try:
                from ultralytics import YOLO
            except ImportError:
                raise ImportError(
                    "ultralytics is not installed. "
                    "Add 'ultralytics==8.3.0' to requirements.txt and reinstall."
                )
            self._model = YOLO(self.model_path)
        return self._model

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device == "auto":
            try:
                import torch
                return "0" if torch.cuda.is_available() else "cpu"
            except ImportError:
                return "cpu"
        return device
