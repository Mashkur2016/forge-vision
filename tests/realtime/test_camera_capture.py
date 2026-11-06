"""
Unit tests for src/realtime/camera_capture.py — Task 3.1.

Tests use a mock cv2.VideoCapture so no physical camera is required.
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.realtime.camera_capture import CameraCapture, CameraConfig


# ── Fixtures ───────────────────────────────────────────────────────────────

def _make_fake_cap(frames: list[np.ndarray] | None = None, open_: bool = True):
    """Return a mock cv2.VideoCapture that yields synthetic frames."""
    cap = MagicMock()
    cap.isOpened.return_value = open_

    if frames is not None:
        side_effects = [(True, f) for f in frames] + [(False, None)]
        cap.read.side_effect = side_effects
    else:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cap.read.return_value = (True, frame)

    return cap


# ── CameraConfig tests ─────────────────────────────────────────────────────

def test_camera_config_defaults():
    cfg = CameraConfig()
    assert cfg.source == 0
    assert cfg.target_fps == 15
    assert cfg.width == 640
    assert cfg.height == 480


def test_camera_config_custom():
    cfg = CameraConfig(source="rtsp://192.168.1.100/stream", target_fps=30)
    assert cfg.source == "rtsp://192.168.1.100/stream"
    assert cfg.target_fps == 30


# ── CameraCapture lifecycle tests ──────────────────────────────────────────

@patch("src.realtime.camera_capture.cv2.VideoCapture")
def test_start_and_stop(mock_vc_cls):
    mock_vc_cls.return_value = _make_fake_cap()

    cam = CameraCapture(CameraConfig(target_fps=60))
    cam.start()

    assert cam.is_running
    cam.stop()
    assert not cam.is_running


@patch("src.realtime.camera_capture.cv2.VideoCapture")
def test_read_returns_frame(mock_vc_cls):
    synthetic = np.ones((480, 640, 3), dtype=np.uint8) * 128
    cap = MagicMock()
    cap.isOpened.return_value = True
    cap.read.return_value = (True, synthetic)
    mock_vc_cls.return_value = cap

    with CameraCapture(CameraConfig(target_fps=60)) as cam:
        frame = cam.read()

    assert frame is not None
    assert frame.shape == (480, 640, 3)


@patch("src.realtime.camera_capture.cv2.VideoCapture")
def test_read_before_start_returns_none(mock_vc_cls):
    cam = CameraCapture(CameraConfig())
    # read() before start() should return None (no frame yet)
    assert cam.read() is None


@patch("src.realtime.camera_capture.cv2.VideoCapture")
def test_camera_not_opened_raises(mock_vc_cls):
    mock_vc_cls.return_value = _make_fake_cap(open_=False)
    cam = CameraCapture(CameraConfig())
    with pytest.raises(RuntimeError, match="failed to open source"):
        cam.start()


@patch("src.realtime.camera_capture.cv2.VideoCapture")
def test_context_manager(mock_vc_cls):
    mock_vc_cls.return_value = _make_fake_cap()

    with CameraCapture(CameraConfig(target_fps=60)) as cam:
        assert cam.is_running
        frame = cam.read()
        assert frame is not None

    assert not cam.is_running


@patch("src.realtime.camera_capture.cv2.VideoCapture")
def test_frame_count_increments(mock_vc_cls):
    mock_vc_cls.return_value = _make_fake_cap()

    with CameraCapture(CameraConfig(target_fps=60)) as cam:
        time.sleep(0.2)   # Let background thread capture several frames
        count = cam.frame_count

    assert count > 0


@patch("src.realtime.camera_capture.cv2.VideoCapture")
def test_actual_fps_reasonable(mock_vc_cls):
    mock_vc_cls.return_value = _make_fake_cap()

    with CameraCapture(CameraConfig(target_fps=30)) as cam:
        time.sleep(0.3)
        fps = cam.actual_fps

    # Should be > 0 after some time; capped by target_fps
    assert fps > 0


# ── Thread safety: multiple reads don't crash ──────────────────────────────

@patch("src.realtime.camera_capture.cv2.VideoCapture")
def test_concurrent_reads_are_safe(mock_vc_cls):
    mock_vc_cls.return_value = _make_fake_cap()

    results = []
    errors = []

    def reader(cam):
        try:
            for _ in range(20):
                f = cam.read()
                results.append(f is not None)
                time.sleep(0.01)
        except Exception as exc:
            errors.append(exc)

    with CameraCapture(CameraConfig(target_fps=60)) as cam:
        threads = [threading.Thread(target=reader, args=(cam,)) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

    assert not errors, f"Thread errors: {errors}"
