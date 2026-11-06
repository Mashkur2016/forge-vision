"""
Tests for src/simulation/augmentation.py
"""
from __future__ import annotations

import numpy as np
import pytest

from src.simulation.augmentation import AugmentationConfig, VideoAugmentor


# ── Helpers ────────────────────────────────────────────────────────────────

def _solid_frame(colour: tuple[int, int, int] = (128, 64, 32)) -> np.ndarray:
    """Return a 640×480 solid-colour BGR frame."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:] = colour
    return frame


def _random_frame(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, (480, 640, 3), dtype=np.uint8)


# ── VideoAugmentor init ────────────────────────────────────────────────────

class TestVideoAugmentorInit:
    def test_default_config(self):
        aug = VideoAugmentor()
        assert isinstance(aug.config, AugmentationConfig)

    def test_custom_config(self):
        cfg = AugmentationConfig(horizontal_flip_prob=0.0)
        aug = VideoAugmentor(config=cfg)
        assert aug.config.horizontal_flip_prob == 0.0

    def test_seed_sets_determinism(self):
        aug1 = VideoAugmentor(seed=42)
        aug2 = VideoAugmentor(seed=42)
        frame = _random_frame(0)
        out1 = aug1.augment_frame(frame)
        out2 = aug2.augment_frame(frame)
        np.testing.assert_array_equal(out1, out2)


# ── augment_frame ──────────────────────────────────────────────────────────

class TestAugmentFrame:
    def test_output_shape_preserved(self, random_frame):
        aug = VideoAugmentor(seed=0)
        out = aug.augment_frame(random_frame)
        assert out.shape == random_frame.shape

    def test_output_dtype_preserved(self, random_frame):
        aug = VideoAugmentor(seed=0)
        out = aug.augment_frame(random_frame)
        assert out.dtype == np.uint8

    def test_input_not_modified(self, random_frame):
        original = random_frame.copy()
        aug = VideoAugmentor(seed=0)
        aug.augment_frame(random_frame)
        np.testing.assert_array_equal(random_frame, original)

    def test_all_transforms_disabled_returns_copy(self, random_frame):
        cfg = AugmentationConfig(
            horizontal_flip_prob=0.0,
            rotation_prob=0.0,
            brightness_contrast_prob=0.0,
            hsv_prob=0.0,
            noise_prob=0.0,
            motion_blur_prob=0.0,
            crop_prob=0.0,
        )
        aug = VideoAugmentor(config=cfg, seed=0)
        out = aug.augment_frame(random_frame)
        np.testing.assert_array_equal(out, random_frame)

    def test_flip_always_applied(self):
        cfg = AugmentationConfig(
            horizontal_flip_prob=1.0,
            rotation_prob=0.0,
            brightness_contrast_prob=0.0,
            hsv_prob=0.0,
            noise_prob=0.0,
            motion_blur_prob=0.0,
            crop_prob=0.0,
        )
        aug = VideoAugmentor(config=cfg, seed=0)
        frame = _random_frame(1)
        out = aug.augment_frame(frame)
        # Flipped frame should differ from original
        assert not np.array_equal(out, frame)
        # Double-flip should match original
        out2 = aug.augment_frame(out)
        np.testing.assert_array_equal(out2, frame)

    def test_invalid_frame_type_raises(self):
        aug = VideoAugmentor(seed=0)
        with pytest.raises(TypeError):
            aug.augment_frame([[1, 2, 3]])  # type: ignore

    def test_empty_frame_raises(self):
        aug = VideoAugmentor(seed=0)
        with pytest.raises(ValueError, match="empty"):
            aug.augment_frame(np.zeros((0, 0, 3), dtype=np.uint8))

    def test_pixel_values_in_valid_range(self, random_frame):
        aug = VideoAugmentor(
            config=AugmentationConfig(
                brightness_contrast_prob=1.0,
                noise_prob=1.0,
            ),
            seed=0,
        )
        out = aug.augment_frame(random_frame)
        assert out.min() >= 0
        assert out.max() <= 255


# ── augment_clip ───────────────────────────────────────────────────────────

class TestAugmentClip:
    def test_empty_clip_returns_empty(self):
        aug = VideoAugmentor(seed=0)
        assert aug.augment_clip([]) == []

    def test_output_length_matches_input(self, random_clip):
        aug = VideoAugmentor(seed=0)
        out = aug.augment_clip(random_clip)
        assert len(out) == len(random_clip)

    def test_each_frame_has_correct_shape(self, random_clip):
        aug = VideoAugmentor(seed=0)
        out = aug.augment_clip(random_clip)
        for frame in out:
            assert frame.shape == (480, 640, 3)

    def test_consistent_flip_applied_uniformly(self):
        """With consistent=True and flip_prob=1, every frame should be flipped."""
        cfg = AugmentationConfig(
            horizontal_flip_prob=1.0,
            rotation_prob=0.0,
            brightness_contrast_prob=0.0,
            hsv_prob=0.0,
            noise_prob=0.0,
            motion_blur_prob=0.0,
            crop_prob=0.0,
        )
        aug = VideoAugmentor(config=cfg, seed=0)
        frames = [_random_frame(i) for i in range(5)]
        out = aug.augment_clip(frames, consistent=True)

        for original, augmented in zip(frames, out):
            # Each frame should be the horizontal mirror of the original
            import cv2
            expected = cv2.flip(original, 1)
            np.testing.assert_array_equal(augmented, expected)

    def test_inconsistent_mode_applies_independent_transforms(self, random_clip):
        aug = VideoAugmentor(seed=0)
        out = aug.augment_clip(random_clip, consistent=False)
        assert len(out) == len(random_clip)
        for frame in out:
            assert frame.dtype == np.uint8

    def test_single_frame_clip(self, random_frame):
        aug = VideoAugmentor(seed=0)
        out = aug.augment_clip([random_frame])
        assert len(out) == 1
        assert out[0].shape == random_frame.shape


# ── AugmentationConfig ─────────────────────────────────────────────────────

class TestAugmentationConfig:
    def test_default_values_are_reasonable(self):
        cfg = AugmentationConfig()
        assert 0.0 <= cfg.horizontal_flip_prob <= 1.0
        assert cfg.rotation_max_degrees > 0
        assert cfg.brightness_delta > 0
        assert cfg.contrast_range[0] < cfg.contrast_range[1]
        assert cfg.noise_sigma_range[0] < cfg.noise_sigma_range[1]
        assert cfg.crop_scale_range[0] < cfg.crop_scale_range[1]
        assert cfg.crop_scale_range[1] <= 1.0
