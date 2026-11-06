"""
Unit tests for src/cv_pipeline/annotate.py — live training overlay rendering.

The drawer is pure (no model calls); these tests verify it produces a valid,
same-shape frame for empty, fully-populated, and banner cases without mutating
the input.
"""
from __future__ import annotations

import numpy as np

from src.cv_pipeline.annotate import draw_overlay
from src.cv_pipeline.frame_processor import FrameResult
from src.cv_pipeline.object_detector import Detection, DetectionResult
from src.cv_pipeline.pose_estimator import PoseLandmark, PoseResult


def _blank() -> np.ndarray:
    return np.zeros((480, 640, 3), dtype=np.uint8)


def test_empty_frame_result_returns_copy_unchanged():
    img = _blank()
    out = draw_overlay(img, FrameResult())
    assert out.shape == img.shape
    assert out.dtype == img.dtype
    # No pose/detections/banners → nothing drawn, but it must be a copy
    assert out is not img
    assert np.array_equal(out, img)


def test_input_frame_not_mutated():
    img = _blank()
    before = img.copy()
    draw_overlay(
        img,
        _populated_frame_result(),
        step_label="Step 1 — Don PPE",
        deviation=("high", "Required PPE not detected"),
    )
    assert np.array_equal(img, before)


def test_full_overlay_draws_pixels():
    img = _blank()
    out = draw_overlay(
        img,
        _populated_frame_result(),
        step_label="Step 2 — Lockout",
        deviation=("medium", "Steps performed out of order"),
    )
    assert out.shape == img.shape
    # Something was drawn somewhere
    assert out.sum() > 0
    # Top + bottom banners should have coloured pixels
    assert out[5, :, :].sum() > 0
    assert out[-5, :, :].sum() > 0


def test_unknown_severity_falls_back_without_error():
    out = draw_overlay(_blank(), FrameResult(), deviation=("bogus", "x"))
    assert out[-5, :, :].sum() > 0


def _populated_frame_result() -> FrameResult:
    # 33 visible body landmarks spread across the frame
    landmarks = [
        PoseLandmark(x=0.3 + (i % 5) * 0.08, y=0.2 + (i % 7) * 0.09, z=0.0, visibility=0.9)
        for i in range(33)
    ]
    detections = DetectionResult(
        detections=[
            Detection(label="insulated_gloves", confidence=0.91,
                      x1=0.1, y1=0.1, x2=0.4, y2=0.5, class_id=1),
            Detection(label="wrench", confidence=0.77,
                      x1=0.55, y1=0.6, x2=0.8, y2=0.9, class_id=2),
        ],
        frame_width=640,
        frame_height=480,
    )
    return FrameResult(
        pose=PoseResult(body_landmarks=landmarks),
        detections=detections,
        pose_features=np.zeros(300, dtype=np.float32),
    )
