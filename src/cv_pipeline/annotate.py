"""
Frame overlay rendering for the live training view.

Draws the CV pipeline output onto a BGR frame so the worker sees, in real
time, what the system perceives:

    - BlazePose skeleton (33 body landmarks + limb connections)
    - YOLO object/PPE bounding boxes with labels
    - A top banner showing the current SOP step
    - A bottom banner showing the latest deviation, coloured by severity

This is pure drawing — no model calls — so it is cheap enough to run on
every frame in the WebRTC `recv()` callback.

Architecture.md Layer 4: Real-Time Worker Guidance (visual feedback).
"""
from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from src.cv_pipeline.frame_processor import FrameResult


# ── BlazePose skeleton connections (body landmark index pairs) ──────────────
# Indices follow MediaPipe BlazePose (see PoseEstimator.get_landmark_name).
POSE_CONNECTIONS: tuple[tuple[int, int], ...] = (
    # Shoulders + arms
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    # Hands
    (15, 17), (15, 19), (15, 21), (17, 19),
    (16, 18), (16, 20), (16, 22), (18, 20),
    # Torso
    (11, 23), (12, 24), (23, 24),
    # Left leg
    (23, 25), (25, 27), (27, 29), (27, 31), (29, 31),
    # Right leg
    (24, 26), (26, 28), (28, 30), (28, 32), (30, 32),
)

# BGR colours
_SKELETON = (0, 255, 0)
_JOINT = (0, 200, 255)
_BOX = (255, 180, 0)
_BOX_TEXT = (20, 20, 20)
_STEP_BANNER_BG = (40, 30, 15)
_STEP_BANNER_FG = (0, 204, 255)   # FORGE gold (BGR)

_SEVERITY_BGR = {
    "high": (53, 53, 220),     # red
    "medium": (20, 126, 253),  # orange
    "low": (84, 153, 22),      # green
}


def draw_overlay(
    bgr: np.ndarray,
    frame_result: FrameResult,
    *,
    step_label: Optional[str] = None,
    deviation: Optional[tuple[str, str]] = None,
    min_visibility: float = 0.5,
) -> np.ndarray:
    """
    Render CV output + status banners onto a copy of `bgr`.

    Args:
        bgr:           uint8 BGR frame.
        frame_result:  Output of the CV pipeline (pose + detections).
        step_label:    Current SOP step text for the top banner (optional).
        deviation:     (severity, what) for the bottom banner (optional).
        min_visibility: Hide landmarks below this visibility score.

    Returns:
        A new annotated BGR frame (input is not modified).
    """
    out = bgr.copy()
    h, w = out.shape[:2]

    _draw_pose(out, frame_result, w, h, min_visibility)
    _draw_detections(out, frame_result, w, h)

    if step_label:
        _draw_top_banner(out, w, step_label)
    if deviation is not None:
        severity, what = deviation
        _draw_bottom_banner(out, w, h, severity, what)

    return out


# ── Pose ───────────────────────────────────────────────────────────────────

def _draw_pose(out, frame_result, w, h, min_visibility) -> None:
    landmarks = frame_result.pose.body_landmarks
    if not landmarks:
        return

    n = len(landmarks)
    for a, b in POSE_CONNECTIONS:
        if a >= n or b >= n:
            continue
        la, lb = landmarks[a], landmarks[b]
        if la.visibility < min_visibility or lb.visibility < min_visibility:
            continue
        pa = (int(la.x * w), int(la.y * h))
        pb = (int(lb.x * w), int(lb.y * h))
        cv2.line(out, pa, pb, _SKELETON, 2, cv2.LINE_AA)

    for lm in landmarks:
        if lm.visibility < min_visibility:
            continue
        cv2.circle(out, (int(lm.x * w), int(lm.y * h)), 3, _JOINT, -1, cv2.LINE_AA)


# ── Detections ───────────────────────────────────────────────────────────────

def _draw_detections(out, frame_result, w, h) -> None:
    for d in frame_result.detections.detections:
        x1, y1 = int(d.x1 * w), int(d.y1 * h)
        x2, y2 = int(d.x2 * w), int(d.y2 * h)
        cv2.rectangle(out, (x1, y1), (x2, y2), _BOX, 2, cv2.LINE_AA)

        label = f"{d.label} {d.confidence:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        ly = max(0, y1 - th - 6)
        cv2.rectangle(out, (x1, ly), (x1 + tw + 6, ly + th + 6), _BOX, -1)
        cv2.putText(out, label, (x1 + 3, ly + th + 1),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, _BOX_TEXT, 1, cv2.LINE_AA)


# ── Banners ──────────────────────────────────────────────────────────────────

def _draw_top_banner(out, w, text: str) -> None:
    bar_h = 34
    cv2.rectangle(out, (0, 0), (w, bar_h), _STEP_BANNER_BG, -1)
    text = _truncate(text, w)
    cv2.putText(out, text, (12, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                _STEP_BANNER_FG, 2, cv2.LINE_AA)


def _draw_bottom_banner(out, w, h, severity: str, what: str) -> None:
    color = _SEVERITY_BGR.get(severity, _SEVERITY_BGR["low"])
    bar_h = 38
    cv2.rectangle(out, (0, h - bar_h), (w, h), color, -1)
    label = f"[{severity.upper()}] {what}"
    label = _truncate(label, w)
    cv2.putText(out, label, (12, h - 13), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (255, 255, 255), 2, cv2.LINE_AA)


def _truncate(text: str, w: int, char_px: int = 11) -> str:
    """Trim text to fit the banner width (rough monospace estimate)."""
    max_chars = max(8, (w - 24) // char_px)
    if len(text) > max_chars:
        return text[: max_chars - 1] + "…"
    return text
