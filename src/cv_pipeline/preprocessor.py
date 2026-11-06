"""
Frame Preprocessor — OpenCV-based frame normalisation for the CV pipeline.

Applies the standard preprocessing required before pose estimation and object
detection: resize → optional denoise → normalise to float32.

Architecture.md Layer 2: "OpenCV Preprocessing — resize/denoise"
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class PreprocessConfig:
    """Configuration for the frame preprocessor."""
    target_width: int = 640
    target_height: int = 480
    normalise: bool = True              # Scale pixel values to [0, 1]
    denoise: bool = False               # Gaussian blur for noise reduction
    denoise_kernel_size: int = 3        # Must be odd
    interpolation: int = cv2.INTER_LINEAR


class FramePreprocessor:
    """
    Resizes, optionally denoises, and normalises BGR video frames.

    Usage:
        preprocessor = FramePreprocessor()
        frame_float = preprocessor.process(raw_frame)      # → float32 (H,W,3) in [0,1]
        frame_uint8 = preprocessor.process_uint8(raw_frame) # → uint8 resized only
    """

    def __init__(self, config: PreprocessConfig | None = None) -> None:
        self.config = config or PreprocessConfig()
        self._target_size = (self.config.target_width, self.config.target_height)

    def process(self, frame: np.ndarray) -> np.ndarray:
        """
        Full preprocessing pipeline for model inference.

        Returns:
            float32 ndarray of shape (H, W, 3), values in [0, 1].
        """
        self._validate(frame)
        out = self._resize(frame)
        if self.config.denoise:
            out = self._denoise(out)
        if self.config.normalise:
            return out.astype(np.float32) / 255.0
        return out.astype(np.float32)

    def process_uint8(self, frame: np.ndarray) -> np.ndarray:
        """
        Resize only (no normalise). Useful for pose/detection models that
        accept uint8 BGR input directly.

        Returns:
            uint8 ndarray of shape (H, W, 3).
        """
        self._validate(frame)
        return self._resize(frame)

    def process_rgb(self, frame: np.ndarray) -> np.ndarray:
        """
        Resize and convert BGR → RGB (required by MediaPipe).

        Returns:
            uint8 ndarray of shape (H, W, 3) in RGB.
        """
        bgr = self.process_uint8(frame)
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    # ── Helpers ────────────────────────────────────────────────────────────

    def _resize(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        if (w, h) == self._target_size:
            return frame.copy()
        return cv2.resize(frame, self._target_size, interpolation=self.config.interpolation)

    def _denoise(self, frame: np.ndarray) -> np.ndarray:
        k = self.config.denoise_kernel_size
        if k < 3 or k % 2 == 0:
            raise ValueError(f"denoise_kernel_size must be an odd integer ≥ 3, got {k}")
        return cv2.GaussianBlur(frame, (k, k), 0)

    @staticmethod
    def _validate(frame: np.ndarray) -> None:
        if not isinstance(frame, np.ndarray):
            raise TypeError(f"Expected np.ndarray, got {type(frame).__name__}")
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError(f"Expected (H, W, 3) BGR frame, got shape {frame.shape}")
        if frame.size == 0:
            raise ValueError("Frame is empty")
