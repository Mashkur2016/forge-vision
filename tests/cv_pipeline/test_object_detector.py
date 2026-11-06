"""
Tests for src/cv_pipeline/object_detector.py — Detection, DetectionResult, ObjectDetector.

ObjectDetector tests requiring YOLO model loading are skipped if ultralytics
is not installed. Data-class and result-logic tests run in all environments.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.cv_pipeline.object_detector import Detection, DetectionResult, ObjectDetector


# ── Detection ──────────────────────────────────────────────────────────────

class TestDetection:
    def _make(self, label="gloves", conf=0.9, x1=0.1, y1=0.1, x2=0.5, y2=0.5) -> Detection:
        return Detection(label=label, confidence=conf, x1=x1, y1=y1, x2=x2, y2=y2)

    def test_fields(self):
        d = self._make()
        assert d.label == "gloves"
        assert d.confidence == 0.9

    def test_bbox_area(self):
        d = self._make(x1=0.0, y1=0.0, x2=0.5, y2=0.4)
        assert d.bbox_area == pytest.approx(0.2)

    def test_bbox_area_zero_for_degenerate(self):
        d = self._make(x1=0.5, y1=0.5, x2=0.3, y2=0.3)
        assert d.bbox_area == 0.0

    def test_centre(self):
        d = self._make(x1=0.0, y1=0.0, x2=1.0, y2=1.0)
        cx, cy = d.centre
        assert cx == pytest.approx(0.5)
        assert cy == pytest.approx(0.5)


# ── DetectionResult ────────────────────────────────────────────────────────

class TestDetectionResult:
    def _make_result(self) -> DetectionResult:
        detections = [
            Detection("insulated_gloves", 0.92, 0.1, 0.1, 0.3, 0.3),
            Detection("safety_glasses",   0.85, 0.4, 0.1, 0.6, 0.3),
            Detection("red_wire",         0.55, 0.2, 0.5, 0.4, 0.7),
        ]
        return DetectionResult(detections=detections, latency_ms=25.0)

    def test_labels(self):
        r = self._make_result()
        assert set(r.labels) == {"insulated_gloves", "safety_glasses", "red_wire"}

    def test_has_label_true(self):
        r = self._make_result()
        assert r.has_label("insulated_gloves") is True

    def test_has_label_false(self):
        r = self._make_result()
        assert r.has_label("hard_hat") is False

    def test_get_by_label(self):
        r = self._make_result()
        results = r.get_by_label("insulated_gloves")
        assert len(results) == 1
        assert results[0].confidence == pytest.approx(0.92)

    def test_get_by_label_empty(self):
        r = self._make_result()
        assert r.get_by_label("nonexistent") == []

    def test_above_confidence(self):
        r = self._make_result()
        high_conf = r.above_confidence(0.80)
        assert len(high_conf) == 2
        labels = {d.label for d in high_conf}
        assert labels == {"insulated_gloves", "safety_glasses"}

    def test_check_ppe_present_all(self):
        r = self._make_result()
        result = r.check_ppe_present(["insulated_gloves", "safety_glasses"])
        assert result == {"insulated_gloves": True, "safety_glasses": True}

    def test_check_ppe_present_partial(self):
        r = self._make_result()
        result = r.check_ppe_present(["insulated_gloves", "hard_hat"])
        assert result["insulated_gloves"] is True
        assert result["hard_hat"] is False

    def test_missing_ppe_none_missing(self):
        r = self._make_result()
        assert r.missing_ppe(["insulated_gloves", "safety_glasses"]) == []

    def test_missing_ppe_some_missing(self):
        r = self._make_result()
        missing = r.missing_ppe(["insulated_gloves", "hard_hat", "hi_vis_vest"])
        assert "hard_hat" in missing
        assert "hi_vis_vest" in missing
        assert "insulated_gloves" not in missing

    def test_empty_result(self):
        r = DetectionResult()
        assert r.labels == []
        assert r.has_label("anything") is False
        assert r.missing_ppe(["gloves"]) == ["gloves"]

    def test_latency_stored(self):
        r = DetectionResult(latency_ms=42.5)
        assert r.latency_ms == pytest.approx(42.5)


# ── ObjectDetector lazy loading ────────────────────────────────────────────

class TestObjectDetectorInit:
    def test_model_not_loaded_at_init(self):
        detector = ObjectDetector(model_path="yolov8n.pt")
        assert detector._model is None

    def test_conf_threshold_stored(self):
        detector = ObjectDetector(conf_threshold=0.55)
        assert detector.conf_threshold == pytest.approx(0.55)

    def test_device_auto_resolves(self):
        detector = ObjectDetector(device="auto")
        assert detector._device in ("0", "cpu")

    def test_device_explicit_cpu(self):
        detector = ObjectDetector(device="cpu")
        assert detector._device == "cpu"

    def test_detect_empty_frame_returns_empty(self):
        """Empty frame must return empty DetectionResult without loading model."""
        detector = ObjectDetector()
        result = detector.detect(np.zeros((0, 0, 3), dtype=np.uint8))
        assert isinstance(result, DetectionResult)
        assert result.detections == []

    def test_detect_none_frame_returns_empty(self):
        detector = ObjectDetector()
        result = detector.detect(None)  # type: ignore[arg-type]
        assert isinstance(result, DetectionResult)


# ── ObjectDetector model integration (requires ultralytics) ───────────────

ultralytics = pytest.importorskip("ultralytics", reason="ultralytics not installed")


class TestObjectDetectorIntegration:
    def test_detect_returns_detection_result(self):
        detector = ObjectDetector(model_path="yolov8n.pt", conf_threshold=0.25)
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(blank)
        assert isinstance(result, DetectionResult)
        assert result.frame_width == 640
        assert result.frame_height == 480
        assert result.latency_ms > 0.0

    def test_detect_returns_valid_bbox(self):
        """Any detected box must have normalised coords in [0, 1]."""
        detector = ObjectDetector(model_path="yolov8n.pt", conf_threshold=0.10)
        rng = np.random.default_rng(1)
        frame = rng.integers(0, 256, (480, 640, 3), dtype=np.uint8)
        result = detector.detect(frame)
        for det in result.detections:
            assert 0.0 <= det.x1 <= 1.0
            assert 0.0 <= det.y1 <= 1.0
            assert 0.0 <= det.x2 <= 1.0
            assert 0.0 <= det.y2 <= 1.0
            assert det.confidence >= 0.10

    def test_load_preloads_model(self):
        detector = ObjectDetector(model_path="yolov8n.pt")
        assert detector._model is None
        detector.load()
        assert detector._model is not None
