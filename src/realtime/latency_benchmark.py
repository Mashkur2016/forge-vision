"""
Latency Benchmark — Task 3.7 (Phase 3).

Measures the end-to-end inference latency of the real-time pipeline
against the 2-second target defined in Rules.md §1.7 and
config/train_config.yaml (edge.target_latency_ms = 500 ms per component).

Benchmarks run on synthetic frames (random noise arrays) so no camera
or real video is required.  This isolates computational latency from
I/O latency.

Benchmark stages:
  1. CV pipeline       — FrameProcessor (preprocessor only, no MediaPipe/YOLO)
  2. ActionRecognizer  — Forward pass on a 16-frame synthetic clip
  3. End-to-end        — InferencePipeline.process_frame() (full path)

Run:
    python -m src.realtime.latency_benchmark

Output:
    experiments/latency_report.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

try:
    import torch
    import torchvision.transforms as T
except ImportError:
    torch = None  # type: ignore[assignment]
    T = None      # type: ignore[assignment]

from src.cv_pipeline.frame_processor import FrameProcessor
from src.realtime.inference_pipeline import InferencePipeline, InferenceConfig
from src.training.models import load_action_recognizer


# ── Targets ────────────────────────────────────────────────────────────────
TARGET_END_TO_END_MS: float = 2000.0   # Rules.md §1.7
TARGET_INFERENCE_MS: float = 500.0     # train_config.yaml edge.target_latency_ms

# ── Benchmark parameters ───────────────────────────────────────────────────
N_WARMUP: int = 5
N_BENCHMARK: int = 30


def _make_frame(h: int = 480, w: int = 640) -> np.ndarray:
    """Generate a random synthetic BGR frame for benchmarking."""
    return np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)


def run_benchmark(
    checkpoint_path: str = "models/action_recognizer_best.pth",
) -> dict:
    """
    Run all latency benchmarks and write the report to experiments/latency_report.json.

    Returns:
        dict with benchmark results and pass/fail flags.
    """
    print("=" * 60)
    print("FORGE-Vision Phase 3 — Latency Benchmark")
    print("=" * 60)

    results: dict = {}

    # ── 1. CV Pipeline (preprocessor only) ────────────────────────────────
    print("\n[1/3] CV pipeline (FrameProcessor, preprocessor only)...")
    processor = FrameProcessor(run_pose=False, run_detection=False)
    frames = [_make_frame() for _ in range(N_WARMUP + N_BENCHMARK)]

    for f in frames[:N_WARMUP]:
        processor.process(f)

    cv_times: list[float] = []
    for f in frames[N_WARMUP:]:
        t = time.perf_counter()
        processor.process(f)
        cv_times.append((time.perf_counter() - t) * 1000.0)
    processor.close()

    results["cv_pipeline"] = {
        "mean_ms": round(float(np.mean(cv_times)), 2),
        "p95_ms": round(float(np.percentile(cv_times, 95)), 2),
        "max_ms": round(float(np.max(cv_times)), 2),
    }
    print(
        f"   mean={results['cv_pipeline']['mean_ms']} ms  "
        f"p95={results['cv_pipeline']['p95_ms']} ms"
    )

    # ── 2. ActionRecognizer forward pass ───────────────────────────────────
    print("\n[2/3] ActionRecognizer inference (16-frame clip)...")
    model = load_action_recognizer(checkpoint_path)
    model.eval()

    transform = T.Compose([
        T.ToPILImage(),
        T.Resize((224, 224)),
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    clip_tensors = [transform(_make_frame()) for _ in range(16)]
    clip = torch.stack(clip_tensors).unsqueeze(0)   # (1, 16, C, H, W)

    for _ in range(N_WARMUP):
        with torch.no_grad():
            model(clip)

    inf_times: list[float] = []
    for _ in range(N_BENCHMARK):
        t = time.perf_counter()
        with torch.no_grad():
            model(clip)
        inf_times.append((time.perf_counter() - t) * 1000.0)

    p95_inf = float(np.percentile(inf_times, 95))
    results["action_inference"] = {
        "mean_ms": round(float(np.mean(inf_times)), 2),
        "p95_ms": round(p95_inf, 2),
        "max_ms": round(float(np.max(inf_times)), 2),
        "target_ms": TARGET_INFERENCE_MS,
        "target_met": p95_inf < TARGET_INFERENCE_MS,
    }
    status = "PASS" if results["action_inference"]["target_met"] else "FAIL"
    print(
        f"   mean={results['action_inference']['mean_ms']} ms  "
        f"p95={results['action_inference']['p95_ms']} ms  "
        f"target={TARGET_INFERENCE_MS} ms  [{status}]"
    )

    # ── 3. End-to-end InferencePipeline ───────────────────────────────────
    print("\n[3/3] End-to-end InferencePipeline.process_frame()...")
    pipeline = InferencePipeline(InferenceConfig(
        checkpoint_path=checkpoint_path,
        window_size=16,
        inference_stride=1,    # Force inference every frame for worst-case measure
        run_pose=False,        # Pose/detection excluded (no camera available offline)
        run_detection=False,
    ))
    pipeline.load_model()

    synth_frames = [_make_frame() for _ in range(N_WARMUP + N_BENCHMARK)]

    for f in synth_frames[:N_WARMUP]:
        pipeline.process_frame(f)

    e2e_times: list[float] = []
    for f in synth_frames[N_WARMUP:]:
        t = time.perf_counter()
        pipeline.process_frame(f)
        e2e_times.append((time.perf_counter() - t) * 1000.0)
    pipeline.close()

    p95_e2e = float(np.percentile(e2e_times, 95))
    results["end_to_end"] = {
        "mean_ms": round(float(np.mean(e2e_times)), 2),
        "p95_ms": round(p95_e2e, 2),
        "max_ms": round(float(np.max(e2e_times)), 2),
        "target_ms": TARGET_END_TO_END_MS,
        "target_met": p95_e2e < TARGET_END_TO_END_MS,
    }
    status = "PASS" if results["end_to_end"]["target_met"] else "FAIL"
    print(
        f"   mean={results['end_to_end']['mean_ms']} ms  "
        f"p95={results['end_to_end']['p95_ms']} ms  "
        f"target={TARGET_END_TO_END_MS} ms  [{status}]"
    )

    # ── Summary ────────────────────────────────────────────────────────────
    all_pass = all(
        v.get("target_met", True)
        for v in results.values()
        if isinstance(v, dict) and "target_met" in v
    )

    report = {
        "phase": "Phase 3",
        "benchmark_frames": N_BENCHMARK,
        "device": "cpu",
        "results": results,
        "overall_pass": all_pass,
        "targets": {
            "end_to_end_ms": TARGET_END_TO_END_MS,
            "per_component_ms": TARGET_INFERENCE_MS,
        },
    }

    out_path = Path("experiments/latency_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))

    print("\n" + "=" * 60)
    print(f"Overall: {'PASS' if all_pass else 'FAIL'}")
    print(f"Report: {out_path}")
    print("=" * 60)

    return report


if __name__ == "__main__":
    run_benchmark()
