"""
Real-Time Inference Pipeline — Task 3.2 (Phase 3).

Per-frame path:
    BGR frame
        → FrameProcessor  (pose estimation + object detection)
        → Sliding window of preprocessed frames
        → ActionRecognizer (every inference_stride frames)
        → (action_class, confidence)

The pipeline maintains a rolling window of T=16 frames and runs the
trained ActionRecognizer checkpoint on that window at the configured
inference stride, balancing latency against temporal context.

Architecture.md Layer 2 → Layer 3 bridge.
Rules.md §1.7: per-component latency < 500 ms; end-to-end < 2 s.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

try:
    import torch
    import torchvision.transforms as T
    _TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore[assignment]
    T = None      # type: ignore[assignment]
    _TORCH_AVAILABLE = False

from src.cv_pipeline.frame_processor import FrameProcessor, FrameResult
from src.training.models import ActionRecognizer, load_action_recognizer


@dataclass
class InferenceConfig:
    """Configuration for the real-time inference pipeline."""
    # Path to the trained ActionRecognizer checkpoint (Phase 2 output)
    checkpoint_path: str = "models/action_recognizer_best.pth"

    # Number of frames in the sliding window (must match training clip_sample_frames)
    window_size: int = 16

    # Run inference every N new frames. 1 = every frame; 4 = every 4th frame.
    # Higher stride = lower CPU load; lower stride = lower response latency.
    inference_stride: int = 4

    # Frame size expected by the model (must match train_config.yaml dataset.frame_size)
    frame_size: tuple[int, int] = (224, 224)

    # ImageNet normalisation parameters (must match training)
    normalize_mean: tuple[float, ...] = (0.485, 0.456, 0.406)
    normalize_std: tuple[float, ...] = (0.229, 0.224, 0.225)

    # PyTorch device for inference ("cpu" | "cuda" | "mps")
    device: str = "cpu"

    # Enable pose estimation and object detection in FrameProcessor
    run_pose: bool = True
    run_detection: bool = True


@dataclass
class InferenceResult:
    """Output of a single inference pass on a 16-frame window."""
    action_class: int           # Predicted action class index
    confidence: float           # Softmax probability for predicted class
    all_probs: list[float]      # Full probability distribution (all classes)
    latency_ms: float           # Time for the ActionRecognizer forward pass (ms)
    frame_count: int            # Total frames processed by the pipeline so far
    skipped: bool = False       # True when stride not yet reached (no new prediction)


class InferencePipeline:
    """
    Stateful real-time inference pipeline for action recognition.

    Maintains a rolling T-frame window of preprocessed frames.  Every
    `inference_stride` frames it runs the full window through the trained
    ActionRecognizer and returns a new prediction.  Between strides it
    returns the last prediction with `skipped=True` so the caller always
    has a valid action_class available.

    Usage (per session):
        pipeline = InferencePipeline(InferenceConfig())
        pipeline.load_model()

        for bgr_frame in camera:
            frame_result, inference = pipeline.process_frame(bgr_frame)
            if not inference.skipped:
                detector.process_frame(frame_result, inference.action_class)

        pipeline.close()
    """

    def __init__(self, config: Optional[InferenceConfig] = None) -> None:
        self._config = config or InferenceConfig()
        self._device = torch.device(self._config.device)
        self._model: Optional[ActionRecognizer] = None
        self._frame_processor: Optional[FrameProcessor] = None
        self._window: deque[torch.Tensor] = deque(maxlen=self._config.window_size)
        self._frames_since_inference: int = 0
        self._total_frames: int = 0
        self._last_result: Optional[InferenceResult] = None

        # Preprocessing transform — must match the training pipeline exactly
        self._transform = T.Compose([
            T.ToPILImage(),
            T.Resize(self._config.frame_size),
            T.ToTensor(),
            T.Normalize(
                mean=list(self._config.normalize_mean),
                std=list(self._config.normalize_std),
            ),
        ])

    def load_model(self) -> "InferencePipeline":
        """
        Load the ActionRecognizer from checkpoint and initialise FrameProcessor.

        Must be called before process_frame().
        """
        self._model = load_action_recognizer(self._config.checkpoint_path)
        self._model.to(self._device)
        self._model.eval()

        self._frame_processor = FrameProcessor(
            run_pose=self._config.run_pose,
            run_detection=self._config.run_detection,
        )
        return self

    # ── Per-frame processing ──────────────────────────────────────────────

    def process_frame(
        self,
        bgr_frame: np.ndarray,
    ) -> tuple[FrameResult, InferenceResult]:
        """
        Process one BGR frame: run CV pipeline then (if stride reached) inference.

        Args:
            bgr_frame: uint8 BGR numpy array from camera.

        Returns:
            (FrameResult, InferenceResult)
            FrameResult is always populated with fresh CV pipeline output.
            InferenceResult.skipped is True when the stride has not been reached.
        """
        if self._model is None or self._frame_processor is None:
            raise RuntimeError(
                "InferencePipeline.load_model() must be called before process_frame()."
            )

        # ── 1. CV pipeline (pose + detection) ─────────────────────────────
        frame_result = self._frame_processor.process(bgr_frame)

        # ── 2. Preprocess frame tensor for ActionRecognizer ────────────────
        tensor = self._transform(bgr_frame)   # (C, H, W) float32
        self._window.append(tensor)
        self._total_frames += 1
        self._frames_since_inference += 1

        # ── 3. Determine whether to run inference ──────────────────────────
        window_ready = len(self._window) >= self._config.window_size
        stride_reached = self._frames_since_inference >= self._config.inference_stride

        if not window_ready or not stride_reached:
            # Return the last available prediction (may be None if window not warm)
            return frame_result, self._make_skipped_result()

        # ── 4. Run ActionRecognizer on the full window ─────────────────────
        self._frames_since_inference = 0
        clip = torch.stack(list(self._window), dim=0)   # (T, C, H, W)
        clip = clip.unsqueeze(0).to(self._device)        # (1, T, C, H, W)

        t_inf = time.perf_counter()
        with torch.no_grad():
            logits = self._model(clip)                   # (1, num_classes)
            probs = torch.softmax(logits, dim=1)[0]      # (num_classes,)
            confidence, pred_idx = probs.max(dim=0)
        inference_ms = (time.perf_counter() - t_inf) * 1000.0

        result = InferenceResult(
            action_class=int(pred_idx.item()),
            confidence=float(confidence.item()),
            all_probs=probs.tolist(),
            latency_ms=inference_ms,
            frame_count=self._total_frames,
            skipped=False,
        )
        self._last_result = result
        return frame_result, result

    # ── Session management ────────────────────────────────────────────────

    def reset(self) -> None:
        """Clear the frame window and counters (call between sessions)."""
        self._window.clear()
        self._frames_since_inference = 0
        self._total_frames = 0
        self._last_result = None

    def close(self) -> None:
        """Release FrameProcessor model resources."""
        if self._frame_processor is not None:
            self._frame_processor.close()
            self._frame_processor = None

    # ── Helpers ───────────────────────────────────────────────────────────

    def _make_skipped_result(self) -> InferenceResult:
        if self._last_result is not None:
            return InferenceResult(
                action_class=self._last_result.action_class,
                confidence=self._last_result.confidence,
                all_probs=self._last_result.all_probs,
                latency_ms=0.0,
                frame_count=self._total_frames,
                skipped=True,
            )
        return InferenceResult(
            action_class=0,
            confidence=0.0,
            all_probs=[],
            latency_ms=0.0,
            frame_count=self._total_frames,
            skipped=True,
        )
