"""
OpenCV Video Augmentation Pipeline — Phase A synthetic dataset generation.

Applies randomised transforms to video frames to increase dataset diversity
and improve model generalisation. All transforms operate on NumPy arrays
(BGR format, as returned by OpenCV).

Key design decisions:
  - Each transform is probabilistic (applied with a configurable probability)
  - augment_clip() applies consistent spatial transforms across all frames in a
    clip so temporal coherence is preserved (e.g., all frames flip together)
  - A fixed seed is accepted so experiments are reproducible (Rules.md §1.5)
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class AugmentationConfig:
    """
    Configuration for the VideoAugmentor pipeline.

    All probability values are in [0.0, 1.0].
    Setting a probability to 0.0 disables that transform entirely.
    """

    # Horizontal flip
    horizontal_flip_prob: float = 0.5

    # Rotation (degrees)
    rotation_max_degrees: float = 15.0
    rotation_prob: float = 0.5

    # Brightness / contrast
    brightness_delta: int = 40          # ± pixel shift
    contrast_range: tuple[float, float] = (0.8, 1.2)
    brightness_contrast_prob: float = 0.6

    # HSV colour jitter (hue + saturation)
    hsv_hue_delta: int = 10             # ± hue shift (OpenCV hue: 0–179)
    hsv_sat_range: tuple[float, float] = (0.8, 1.2)
    hsv_prob: float = 0.3

    # Gaussian noise
    noise_sigma_range: tuple[float, float] = (5.0, 25.0)
    noise_prob: float = 0.4

    # Motion blur (horizontal kernel)
    motion_blur_kernel_size: int = 5
    motion_blur_prob: float = 0.2

    # Random crop + resize back to original dimensions
    crop_scale_range: tuple[float, float] = (0.85, 1.0)
    crop_prob: float = 0.3


class VideoAugmentor:
    """
    Applies a configurable set of augmentation transforms to video frames.

    Typical usage — single frame:
        augmentor = VideoAugmentor(seed=42)
        augmented = augmentor.augment_frame(frame)

    Typical usage — full clip (temporally consistent):
        augmented_frames = augmentor.augment_clip(frames)
    """

    def __init__(
        self,
        config: AugmentationConfig | None = None,
        seed: int = 42,
    ) -> None:
        self.config = config or AugmentationConfig()
        self._rng = random.Random(seed)
        self._np_rng = np.random.default_rng(seed)

    # ── Public API ─────────────────────────────────────────────────────────

    def augment_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply the full augmentation pipeline to a single BGR frame.

        Each transform is applied independently based on its configured
        probability. Returns a new array; the input is not modified.
        """
        self._validate_frame(frame)
        out = frame.copy()
        c = self.config

        if self._rng.random() < c.horizontal_flip_prob:
            out = self._flip(out)
        if self._rng.random() < c.rotation_prob:
            out = self._rotate(out)
        if self._rng.random() < c.brightness_contrast_prob:
            out = self._brightness_contrast(out)
        if self._rng.random() < c.hsv_prob:
            out = self._hsv_jitter(out)
        if self._rng.random() < c.noise_prob:
            out = self._add_noise(out)
        if self._rng.random() < c.motion_blur_prob:
            out = self._motion_blur(out)
        if self._rng.random() < c.crop_prob:
            out = self._random_crop_resize(out)

        return out

    def augment_clip(
        self,
        frames: list[np.ndarray],
        consistent: bool = True,
    ) -> list[np.ndarray]:
        """
        Augment a sequence of frames representing a video clip.

        Args:
            frames:     List of BGR frames (all must be the same shape).
            consistent: If True (default), spatial transforms (flip, rotation,
                        crop) use the same parameters for every frame in the
                        clip to preserve temporal coherence. Per-pixel
                        transforms (noise, colour jitter) still vary per frame.

        Returns:
            List of augmented frames, same length as input.
        """
        if not frames:
            return []

        for f in frames:
            self._validate_frame(f)

        if not consistent:
            return [self.augment_frame(f) for f in frames]

        # Sample transform decisions once for the whole clip
        c = self.config
        do_flip = self._rng.random() < c.horizontal_flip_prob
        do_rotate = self._rng.random() < c.rotation_prob
        angle = self._rng.uniform(-c.rotation_max_degrees, c.rotation_max_degrees)
        do_bc = self._rng.random() < c.brightness_contrast_prob
        brightness = self._rng.randint(-c.brightness_delta, c.brightness_delta)
        contrast = self._rng.uniform(*c.contrast_range)
        do_crop = self._rng.random() < c.crop_prob
        crop_scale = self._rng.uniform(*c.crop_scale_range)
        h, w = frames[0].shape[:2]
        crop_h, crop_w = int(h * crop_scale), int(w * crop_scale)
        crop_y = self._rng.randint(0, max(0, h - crop_h))
        crop_x = self._rng.randint(0, max(0, w - crop_w))

        augmented: list[np.ndarray] = []
        for frame in frames:
            f = frame.copy()

            if do_flip:
                f = self._flip(f)
            if do_rotate:
                f = self._rotate(f, angle=angle)
            if do_bc:
                f = self._brightness_contrast(f, brightness=brightness, contrast=contrast)

            # Per-frame colour/noise variation (intentionally inconsistent)
            if self._rng.random() < c.hsv_prob:
                f = self._hsv_jitter(f)
            if self._rng.random() < c.noise_prob:
                f = self._add_noise(f)
            if self._rng.random() < c.motion_blur_prob:
                f = self._motion_blur(f)

            if do_crop:
                f = self._crop_at(f, crop_y, crop_x, crop_h, crop_w)

            augmented.append(f)

        return augmented

    # ── Individual transforms ──────────────────────────────────────────────

    def _flip(self, frame: np.ndarray) -> np.ndarray:
        return cv2.flip(frame, 1)

    def _rotate(self, frame: np.ndarray, angle: float | None = None) -> np.ndarray:
        if angle is None:
            angle = self._rng.uniform(
                -self.config.rotation_max_degrees, self.config.rotation_max_degrees
            )
        h, w = frame.shape[:2]
        centre = (w / 2.0, h / 2.0)
        M = cv2.getRotationMatrix2D(centre, angle, 1.0)
        return cv2.warpAffine(frame, M, (w, h), borderMode=cv2.BORDER_REFLECT)

    def _brightness_contrast(
        self,
        frame: np.ndarray,
        brightness: int | None = None,
        contrast: float | None = None,
    ) -> np.ndarray:
        if brightness is None:
            brightness = self._rng.randint(
                -self.config.brightness_delta, self.config.brightness_delta
            )
        if contrast is None:
            contrast = self._rng.uniform(*self.config.contrast_range)
        out = frame.astype(np.float32) * contrast + brightness
        return np.clip(out, 0, 255).astype(np.uint8)

    def _hsv_jitter(self, frame: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)
        hue_shift = self._rng.randint(-self.config.hsv_hue_delta, self.config.hsv_hue_delta)
        sat_scale = self._rng.uniform(*self.config.hsv_sat_range)
        hsv[:, :, 0] = (hsv[:, :, 0] + hue_shift) % 180
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * sat_scale, 0, 255)
        return cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR)

    def _add_noise(self, frame: np.ndarray, sigma: float | None = None) -> np.ndarray:
        if sigma is None:
            sigma = self._rng.uniform(*self.config.noise_sigma_range)
        noise = self._np_rng.normal(0.0, sigma, frame.shape).astype(np.float32)
        return np.clip(frame.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    def _motion_blur(self, frame: np.ndarray) -> np.ndarray:
        k = self.config.motion_blur_kernel_size
        if k < 3:
            return frame
        kernel = np.zeros((k, k), dtype=np.float32)
        kernel[k // 2, :] = 1.0 / k
        return cv2.filter2D(frame, -1, kernel)

    def _random_crop_resize(
        self, frame: np.ndarray, scale: float | None = None
    ) -> np.ndarray:
        h, w = frame.shape[:2]
        if scale is None:
            scale = self._rng.uniform(*self.config.crop_scale_range)
        crop_h = max(1, int(h * scale))
        crop_w = max(1, int(w * scale))
        y = self._rng.randint(0, max(0, h - crop_h))
        x = self._rng.randint(0, max(0, w - crop_w))
        return self._crop_at(frame, y, x, crop_h, crop_w)

    def _crop_at(
        self,
        frame: np.ndarray,
        y: int,
        x: int,
        crop_h: int,
        crop_w: int,
    ) -> np.ndarray:
        h, w = frame.shape[:2]
        cropped = frame[y : y + crop_h, x : x + crop_w]
        return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)

    # ── Validation ─────────────────────────────────────────────────────────

    @staticmethod
    def _validate_frame(frame: np.ndarray) -> None:
        if not isinstance(frame, np.ndarray):
            raise TypeError(f"Expected np.ndarray frame, got {type(frame).__name__}")
        if frame.ndim not in (2, 3):
            raise ValueError(f"Frame must be 2D (grayscale) or 3D (BGR), got shape {frame.shape}")
        if frame.size == 0:
            raise ValueError("Frame array is empty")
