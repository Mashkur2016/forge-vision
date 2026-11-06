"""
Unit tests for src/realtime/inference_pipeline.py — Task 3.2.

Uses a mock ActionRecognizer and mock FrameProcessor so no GPU,
checkpoint file, or camera is required.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import torch

from src.realtime.inference_pipeline import InferenceConfig, InferencePipeline, InferenceResult


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_frame(h: int = 480, w: int = 640) -> np.ndarray:
    return np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)


def _mock_model(num_classes: int = 5) -> MagicMock:
    """Mock ActionRecognizer that returns uniform logits."""
    model = MagicMock()
    model.eval.return_value = model
    model.return_value = torch.ones(1, num_classes)  # uniform logits
    return model


def _mock_frame_result() -> MagicMock:
    from src.cv_pipeline.frame_processor import FrameResult
    from src.cv_pipeline.pose_estimator import PoseResult
    from src.cv_pipeline.object_detector import DetectionResult
    fr = FrameResult(
        pose=PoseResult(),
        detections=DetectionResult(),
        pose_features=np.zeros(300, dtype=np.float32),
    )
    return fr


# ── InferenceConfig tests ──────────────────────────────────────────────────

def test_inference_config_defaults():
    cfg = InferenceConfig()
    assert cfg.window_size == 16
    assert cfg.inference_stride == 4
    assert cfg.device == "cpu"


def test_inference_config_custom():
    cfg = InferenceConfig(window_size=8, inference_stride=2)
    assert cfg.window_size == 8
    assert cfg.inference_stride == 2


# ── InferencePipeline basic tests ─────────────────────────────────────────

def test_process_frame_requires_load_model():
    """process_frame() before load_model() must raise RuntimeError."""
    pipeline = InferencePipeline(InferenceConfig())
    with pytest.raises(RuntimeError, match="load_model"):
        pipeline.process_frame(_make_frame())


@patch("src.realtime.inference_pipeline.load_action_recognizer")
@patch("src.realtime.inference_pipeline.FrameProcessor")
def test_load_model_and_process(mock_fp_cls, mock_load_ar):
    mock_load_ar.return_value = _mock_model()
    mock_fp_instance = MagicMock()
    mock_fp_instance.process.return_value = _mock_frame_result()
    mock_fp_cls.return_value = mock_fp_instance

    cfg = InferenceConfig(window_size=4, inference_stride=1)
    pipeline = InferencePipeline(cfg)
    pipeline.load_model()

    # First 3 frames: window not full yet → skipped=True
    for _ in range(3):
        _, result = pipeline.process_frame(_make_frame())
        assert result.skipped

    # 4th frame: window full, stride=1 → real inference
    _, result = pipeline.process_frame(_make_frame())
    assert not result.skipped
    assert result.frame_count == 4


@patch("src.realtime.inference_pipeline.load_action_recognizer")
@patch("src.realtime.inference_pipeline.FrameProcessor")
def test_stride_respected(mock_fp_cls, mock_load_ar):
    """With stride=3, inference only happens every 3rd frame after window fills."""
    mock_load_ar.return_value = _mock_model()
    mock_fp_instance = MagicMock()
    mock_fp_instance.process.return_value = _mock_frame_result()
    mock_fp_cls.return_value = mock_fp_instance

    cfg = InferenceConfig(window_size=2, inference_stride=3)
    pipeline = InferencePipeline(cfg)
    pipeline.load_model()

    # Frames 1-2: window filling
    for _ in range(2):
        _, r = pipeline.process_frame(_make_frame())
        assert r.skipped

    # Frame 3: window ready but stride=3, only 1 frame since last (window just filled)
    # Actually: frames_since_inference starts at 0, then increments each frame.
    # After window fills at frame 2: frames_since_inference=2, stride=3 → skipped
    # At frame 5 (2 fill + 3 stride): frames_since_inference reaches 3 → infer
    _, r = pipeline.process_frame(_make_frame())   # frame 3 (frames_since=3 → infer)
    assert not r.skipped


@patch("src.realtime.inference_pipeline.load_action_recognizer")
@patch("src.realtime.inference_pipeline.FrameProcessor")
def test_reset_clears_window(mock_fp_cls, mock_load_ar):
    mock_load_ar.return_value = _mock_model()
    mock_fp_instance = MagicMock()
    mock_fp_instance.process.return_value = _mock_frame_result()
    mock_fp_cls.return_value = mock_fp_instance

    cfg = InferenceConfig(window_size=4, inference_stride=1)
    pipeline = InferencePipeline(cfg)
    pipeline.load_model()

    # Fill window
    for _ in range(4):
        pipeline.process_frame(_make_frame())

    pipeline.reset()

    # After reset, window is empty — should skip again
    _, r = pipeline.process_frame(_make_frame())
    assert r.skipped
    assert pipeline._total_frames == 1


@patch("src.realtime.inference_pipeline.load_action_recognizer")
@patch("src.realtime.inference_pipeline.FrameProcessor")
def test_skipped_result_carries_last_prediction(mock_fp_cls, mock_load_ar):
    """Skipped InferenceResult must carry the last real prediction's action_class."""
    model = _mock_model(num_classes=5)
    # Make model return logits biased toward class 2
    biased = torch.zeros(1, 5)
    biased[0, 2] = 10.0
    model.return_value = biased
    mock_load_ar.return_value = model

    mock_fp_instance = MagicMock()
    mock_fp_instance.process.return_value = _mock_frame_result()
    mock_fp_cls.return_value = mock_fp_instance

    cfg = InferenceConfig(window_size=2, inference_stride=2)
    pipeline = InferencePipeline(cfg)
    pipeline.load_model()

    # Frames 1-2: window fills and stride reached → real inference
    for _ in range(2):
        _, r = pipeline.process_frame(_make_frame())

    # The real inference should have predicted class 2
    assert r.action_class == 2

    # Frame 3: stride not yet reached → skipped but carries class 2
    _, skipped = pipeline.process_frame(_make_frame())
    assert skipped.skipped
    assert skipped.action_class == 2


# ── InferenceResult tests ──────────────────────────────────────────────────

def test_inference_result_defaults():
    r = InferenceResult(
        action_class=3,
        confidence=0.85,
        all_probs=[0.05, 0.05, 0.05, 0.85, 0.0],
        latency_ms=42.0,
        frame_count=10,
    )
    assert r.action_class == 3
    assert r.confidence == pytest.approx(0.85)
    assert r.skipped is False
