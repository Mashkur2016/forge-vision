"""
Tests for src/cv_pipeline/preprocessor.py — FramePreprocessor.
"""
import numpy as np
import pytest

from src.cv_pipeline.preprocessor import FramePreprocessor, PreprocessConfig


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def default_preprocessor() -> FramePreprocessor:
    return FramePreprocessor()


@pytest.fixture
def bgr_720p() -> np.ndarray:
    """1280×720 uint8 BGR frame."""
    rng = np.random.default_rng(42)
    return rng.integers(0, 256, (720, 1280, 3), dtype=np.uint8)


@pytest.fixture
def bgr_exact() -> np.ndarray:
    """640×480 frame — already at target size."""
    rng = np.random.default_rng(7)
    return rng.integers(0, 256, (480, 640, 3), dtype=np.uint8)


# ── Initialisation ─────────────────────────────────────────────────────────

class TestPreprocessConfig:
    def test_defaults(self):
        cfg = PreprocessConfig()
        assert cfg.target_width == 640
        assert cfg.target_height == 480
        assert cfg.normalise is True
        assert cfg.denoise is False
        assert cfg.denoise_kernel_size == 3

    def test_custom(self):
        cfg = PreprocessConfig(target_width=320, target_height=240, denoise=True)
        assert cfg.target_width == 320
        assert cfg.target_height == 240
        assert cfg.denoise is True


class TestFramePreprocessorInit:
    def test_default_config_applied(self, default_preprocessor):
        assert default_preprocessor.config.target_width == 640
        assert default_preprocessor.config.target_height == 480

    def test_custom_config(self):
        cfg = PreprocessConfig(target_width=224, target_height=224)
        p = FramePreprocessor(cfg)
        assert p.config.target_width == 224


# ── process() ─────────────────────────────────────────────────────────────

class TestProcess:
    def test_output_shape(self, default_preprocessor, bgr_720p):
        out = default_preprocessor.process(bgr_720p)
        assert out.shape == (480, 640, 3)

    def test_output_dtype_float32(self, default_preprocessor, bgr_720p):
        out = default_preprocessor.process(bgr_720p)
        assert out.dtype == np.float32

    def test_values_in_0_1(self, default_preprocessor, bgr_720p):
        out = default_preprocessor.process(bgr_720p)
        assert out.min() >= 0.0
        assert out.max() <= 1.0 + 1e-6

    def test_no_normalise(self, bgr_720p):
        cfg = PreprocessConfig(normalise=False)
        p = FramePreprocessor(cfg)
        out = p.process(bgr_720p)
        assert out.dtype == np.float32
        assert out.max() > 1.0    # values should be in [0, 255] range

    def test_already_correct_size(self, bgr_exact):
        p = FramePreprocessor()
        out = p.process(bgr_exact)
        assert out.shape == (480, 640, 3)

    def test_denoise_applies(self, bgr_720p):
        cfg = PreprocessConfig(denoise=True, denoise_kernel_size=3)
        p = FramePreprocessor(cfg)
        out = p.process(bgr_720p)
        assert out.shape == (480, 640, 3)
        assert out.dtype == np.float32

    def test_invalid_kernel_raises(self, bgr_720p):
        cfg = PreprocessConfig(denoise=True, denoise_kernel_size=4)  # even — invalid
        p = FramePreprocessor(cfg)
        with pytest.raises(ValueError, match="odd"):
            p.process(bgr_720p)

    def test_not_ndarray_raises(self, default_preprocessor):
        with pytest.raises(TypeError):
            default_preprocessor.process([[1, 2, 3]])  # type: ignore[arg-type]

    def test_wrong_channels_raises(self, default_preprocessor):
        gray = np.zeros((480, 640, 1), dtype=np.uint8)
        with pytest.raises(ValueError, match="3"):
            default_preprocessor.process(gray)

    def test_empty_frame_raises(self, default_preprocessor):
        empty = np.zeros((0, 0, 3), dtype=np.uint8)
        with pytest.raises(ValueError, match="empty"):
            default_preprocessor.process(empty)


# ── process_uint8() ────────────────────────────────────────────────────────

class TestProcessUint8:
    def test_output_shape(self, default_preprocessor, bgr_720p):
        out = default_preprocessor.process_uint8(bgr_720p)
        assert out.shape == (480, 640, 3)

    def test_output_dtype_uint8(self, default_preprocessor, bgr_720p):
        out = default_preprocessor.process_uint8(bgr_720p)
        assert out.dtype == np.uint8

    def test_values_not_normalised(self, default_preprocessor, bgr_720p):
        out = default_preprocessor.process_uint8(bgr_720p)
        assert out.max() > 1    # should have pixel values > 1

    def test_already_correct_size_returns_copy(self, default_preprocessor, bgr_exact):
        out = default_preprocessor.process_uint8(bgr_exact)
        assert out.shape == bgr_exact.shape
        assert out is not bgr_exact   # should be a copy


# ── process_rgb() ──────────────────────────────────────────────────────────

class TestProcessRgb:
    def test_output_shape(self, default_preprocessor, bgr_720p):
        out = default_preprocessor.process_rgb(bgr_720p)
        assert out.shape == (480, 640, 3)

    def test_output_dtype_uint8(self, default_preprocessor, bgr_720p):
        out = default_preprocessor.process_rgb(bgr_720p)
        assert out.dtype == np.uint8

    def test_different_from_bgr(self, default_preprocessor, bgr_720p):
        bgr_out = default_preprocessor.process_uint8(bgr_720p)
        rgb_out = default_preprocessor.process_rgb(bgr_720p)
        # R and B channels are swapped — should differ
        assert not np.array_equal(bgr_out[:, :, 0], rgb_out[:, :, 0])
