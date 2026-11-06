"""
Emotion / Stress Detector — Enhancement 7 (Phase 4, Task 4.5).

Uses MediaPipe FaceMesh to detect facial landmarks from a video frame
and estimate the worker's affective state: focused, stressed, fatigued,
or neutral.

Estimation is based on geometric ratios derived from landmark positions:
    - Eye Aspect Ratio (EAR) — blink rate / eye closure → fatigue proxy
    - Brow Raise Ratio       — inner brow elevation → stress proxy
    - Mouth Aspect Ratio     — jaw drop → surprise / concentration
    - Head Pose              — pitch / yaw → attention direction

This is a heuristic model appropriate for a workplace training context.
It does not claim clinical-grade emotion recognition and is explicitly
disclosed to workers as part of GDPR consent (Rules.md §2).

Architecture.md Layer 2: Processing — Emotion stream.
Rules.md §2: GDPR — no facial images persisted; results are numeric only.

Requires: mediapipe (optional — guarded with try/except).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

# ── MediaPipe FaceMesh landmark indices ───────────────────────────────────
# Based on MediaPipe 468-point face mesh topology.

# Left eye: outer corner=33, inner corner=133, top=159, bottom=145
_LEFT_EYE = [33, 160, 158, 133, 153, 144]
# Right eye: outer corner=362, inner corner=263, top=386, bottom=374
_RIGHT_EYE = [362, 385, 387, 263, 373, 380]
# Inner brow landmarks (for raised-brow detection)
_LEFT_BROW_INNER = 107
_RIGHT_BROW_INNER = 336
_LEFT_EYE_INNER = 133
_RIGHT_EYE_INNER = 362
# Mouth: top=13, bottom=14, left=61, right=291
_MOUTH_TOP = 13
_MOUTH_BOTTOM = 14
_MOUTH_LEFT = 61
_MOUTH_RIGHT = 291


# ── Result types ──────────────────────────────────────────────────────────

class AffectiveState(str, Enum):
    FOCUSED = "focused"
    STRESSED = "stressed"
    FATIGUED = "fatigued"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


@dataclass
class EmotionResult:
    """
    Affective state estimate for one video frame.

    Rules.md §2: Only numeric ratios and the final state label are kept.
    No facial images are stored or transmitted.
    """
    state: AffectiveState = AffectiveState.UNKNOWN
    ear: float = 0.0             # Eye Aspect Ratio (low → fatigue)
    brow_raise: float = 0.0      # Brow elevation ratio (high → stress)
    mouth_open: float = 0.0      # Mouth Aspect Ratio (high → surprise)
    confidence: float = 0.0      # Heuristic confidence [0–1]
    latency_ms: float = 0.0
    face_detected: bool = False

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "ear": round(self.ear, 3),
            "brow_raise": round(self.brow_raise, 3),
            "mouth_open": round(self.mouth_open, 3),
            "confidence": round(self.confidence, 3),
            "latency_ms": round(self.latency_ms, 2),
            "face_detected": self.face_detected,
        }


# ── Detector ──────────────────────────────────────────────────────────────

class EmotionDetector:
    """
    Real-time affective state estimation from video frames.

    Requires mediapipe.  If not installed, all calls return
    EmotionResult(state=UNKNOWN, face_detected=False) gracefully.

    Usage:
        detector = EmotionDetector()
        detector.start()

        for frame in camera:
            result = detector.detect(frame)
            if result.state == AffectiveState.STRESSED:
                notify_trainer(result)

        detector.close()
    """

    # Heuristic thresholds (tuned for a typical indoor workplace environment)
    EAR_FATIGUE_THRESHOLD = 0.22     # Below this → potential fatigue
    BROW_RAISE_THRESHOLD = 0.08      # Above this → potential stress
    MOUTH_OPEN_THRESHOLD = 0.15      # Above this → surprise / concentration

    def __init__(self) -> None:
        self._face_mesh = None
        self._available: bool = False

    def start(self) -> "EmotionDetector":
        """Initialise MediaPipe FaceMesh."""
        try:
            import mediapipe as mp
            self._face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._available = True
            log.info("EmotionDetector: MediaPipe FaceMesh initialised.")
        except ImportError:
            log.warning(
                "EmotionDetector: mediapipe not installed — "
                "emotion detection disabled. Install with: pip install mediapipe"
            )
            self._available = False
        return self

    def close(self) -> None:
        """Release FaceMesh resources."""
        if self._face_mesh is not None:
            self._face_mesh.close()
            self._face_mesh = None

    @property
    def is_available(self) -> bool:
        return self._available

    def detect(self, bgr_frame: np.ndarray) -> EmotionResult:
        """
        Estimate the worker's affective state from one BGR frame.

        Args:
            bgr_frame: uint8 BGR numpy array (from camera).

        Returns:
            EmotionResult. face_detected=False if no face found or
            mediapipe unavailable.
        """
        import time
        t = time.perf_counter()

        if not self._available or self._face_mesh is None:
            return EmotionResult(latency_ms=(time.perf_counter() - t) * 1000.0)

        import cv2
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        out = self._face_mesh.process(rgb)

        if not out.multi_face_landmarks:
            return EmotionResult(
                face_detected=False,
                latency_ms=(time.perf_counter() - t) * 1000.0,
            )

        lm = out.multi_face_landmarks[0].landmark
        h, w = bgr_frame.shape[:2]

        def pt(idx: int) -> np.ndarray:
            p = lm[idx]
            return np.array([p.x * w, p.y * h])

        ear = self._eye_aspect_ratio(pt)
        brow_raise = self._brow_raise_ratio(pt)
        mouth_open = self._mouth_aspect_ratio(pt)

        state, confidence = self._classify(ear, brow_raise, mouth_open)

        return EmotionResult(
            state=state,
            ear=ear,
            brow_raise=brow_raise,
            mouth_open=mouth_open,
            confidence=confidence,
            face_detected=True,
            latency_ms=(time.perf_counter() - t) * 1000.0,
        )

    # ── Geometric ratios ──────────────────────────────────────────────────

    def _eye_aspect_ratio(self, pt) -> float:
        """
        Eye Aspect Ratio (EAR) — Soukupová & Čech (2016).

        EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
        Low EAR → eye partly closed → fatigue indicator.
        """
        def _ear_single(indices: list[int]) -> float:
            p1, p2, p3, p4, p5, p6 = [pt(i) for i in indices]
            vert1 = np.linalg.norm(p2 - p6)
            vert2 = np.linalg.norm(p3 - p5)
            horiz = np.linalg.norm(p1 - p4)
            return (vert1 + vert2) / (2.0 * horiz) if horiz > 0 else 0.0

        return (_ear_single(_LEFT_EYE) + _ear_single(_RIGHT_EYE)) / 2.0

    def _brow_raise_ratio(self, pt) -> float:
        """
        Ratio of inner brow to inner eye distance.

        Higher ratio → brows raised → stress / surprise indicator.
        """
        left_dist = np.linalg.norm(pt(_LEFT_BROW_INNER) - pt(_LEFT_EYE_INNER))
        right_dist = np.linalg.norm(pt(_RIGHT_BROW_INNER) - pt(_RIGHT_EYE_INNER))
        face_height = np.linalg.norm(pt(10) - pt(152))   # Top to chin
        if face_height == 0:
            return 0.0
        return ((left_dist + right_dist) / 2.0) / face_height

    def _mouth_aspect_ratio(self, pt) -> float:
        """
        Mouth Aspect Ratio — vertical / horizontal mouth opening.

        High MAR → mouth open → surprise / concentration.
        """
        vert = np.linalg.norm(pt(_MOUTH_TOP) - pt(_MOUTH_BOTTOM))
        horiz = np.linalg.norm(pt(_MOUTH_LEFT) - pt(_MOUTH_RIGHT))
        return vert / horiz if horiz > 0 else 0.0

    # ── Heuristic classifier ──────────────────────────────────────────────

    def _classify(
        self,
        ear: float,
        brow_raise: float,
        mouth_open: float,
    ) -> tuple[AffectiveState, float]:
        """
        Rule-based classification using the three geometric ratios.

        Returns (AffectiveState, confidence).
        Confidence is approximate — based on how far each metric is from
        its threshold, not a calibrated probability.
        """
        scores: dict[AffectiveState, float] = {
            AffectiveState.NEUTRAL: 0.5,
            AffectiveState.FOCUSED: 0.0,
            AffectiveState.STRESSED: 0.0,
            AffectiveState.FATIGUED: 0.0,
        }

        # Fatigue: low EAR
        if ear < self.EAR_FATIGUE_THRESHOLD:
            deficit = self.EAR_FATIGUE_THRESHOLD - ear
            scores[AffectiveState.FATIGUED] += deficit * 5.0

        # Stress: high brow raise
        if brow_raise > self.BROW_RAISE_THRESHOLD:
            surplus = brow_raise - self.BROW_RAISE_THRESHOLD
            scores[AffectiveState.STRESSED] += surplus * 8.0

        # Focused: moderate EAR (not blinking much), low brow raise
        if ear >= self.EAR_FATIGUE_THRESHOLD and brow_raise <= self.BROW_RAISE_THRESHOLD:
            scores[AffectiveState.FOCUSED] += 0.4

        best = max(scores, key=lambda k: scores[k])
        raw_conf = scores[best]
        confidence = min(raw_conf / (raw_conf + 0.5), 0.95)  # Sigmoid-like normalisation

        return best, round(confidence, 3)

    # ── Context manager ───────────────────────────────────────────────────

    def __enter__(self) -> "EmotionDetector":
        return self.start()

    def __exit__(self, *_) -> None:
        self.close()
