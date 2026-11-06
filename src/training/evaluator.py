"""
Model Evaluator — benchmark report for the FORGE-Vision ActionRecognizer.

Loads a trained checkpoint, runs inference on the held-out test split, and
produces a structured JSON benchmark report containing:
    - Overall accuracy / top-3 accuracy
    - Per-class precision, recall, F1
    - Confusion matrix (normalised and raw)
    - Latency statistics (mean/p95 inference time per batch)
    - Edge-deployment readiness check (param count, model size)

Rules.md §1.5: Report is reproducible — same seed, same split every run.
Rules.md §1.6: Per-class metrics are included so low-frequency scenarios
               (RARE_FAILURE) are not hidden by macro averages.

Usage:
    python -m src.training.evaluator
    python -m src.training.evaluator --checkpoint models/action_recognizer_best.pth
    python -m src.training.evaluator --checkpoint models/best.pth --report experiments/eval.json
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from src.training.trainer import _forge_collate_fn

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_CONFIG = _PROJECT_ROOT / "config" / "train_config.yaml"
_DEFAULT_CHECKPOINT = _PROJECT_ROOT / "models" / "action_recognizer_best.pth"
_DEFAULT_REPORT = _PROJECT_ROOT / "experiments" / "eval_report.json"


# ── Metrics helpers ────────────────────────────────────────────────────────

def _safe_div(a: float, b: float) -> float:
    return a / b if b > 0 else 0.0


def compute_confusion_matrix(
    y_true: list[int],
    y_pred: list[int],
    num_classes: int,
) -> np.ndarray:
    cm = np.zeros((num_classes, num_classes), dtype=np.int64)
    for t, p in zip(y_true, y_pred):
        if 0 <= t < num_classes and 0 <= p < num_classes:
            cm[t][p] += 1
    return cm


def per_class_metrics(
    cm: np.ndarray,
    class_names: list[str],
) -> list[dict]:
    """
    Compute precision, recall, F1, and support for each class.

    Args:
        cm:           Confusion matrix (num_classes × num_classes), raw counts
        class_names:  List of class label strings

    Returns:
        List of dicts, one per class.
    """
    num_classes = cm.shape[0]
    metrics = []
    for i in range(num_classes):
        tp = int(cm[i, i])
        fp = int(cm[:, i].sum()) - tp
        fn = int(cm[i, :].sum()) - tp
        support = int(cm[i, :].sum())

        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = _safe_div(2 * precision * recall, precision + recall)

        metrics.append({
            "class": class_names[i] if i < len(class_names) else f"class_{i}",
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support,
            "tp": tp,
            "fp": fp,
            "fn": fn,
        })
    return metrics


def macro_averages(per_class: list[dict]) -> dict:
    supported = [m for m in per_class if m["support"] > 0]
    if not supported:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    return {
        "precision": round(sum(m["precision"] for m in supported) / len(supported), 4),
        "recall": round(sum(m["recall"] for m in supported) / len(supported), 4),
        "f1": round(sum(m["f1"] for m in supported) / len(supported), 4),
    }


# ── Evaluator ──────────────────────────────────────────────────────────────

class ModelEvaluator:
    """
    Evaluates a trained ActionRecognizer against the held-out test split.

    Usage:
        evaluator = ModelEvaluator(checkpoint_path="models/best.pth")
        report = evaluator.evaluate()
        evaluator.save_report(report, "experiments/eval.json")
    """

    def __init__(
        self,
        checkpoint_path: str | Path = _DEFAULT_CHECKPOINT,
        config_path: str | Path = _DEFAULT_CONFIG,
    ) -> None:
        self.checkpoint_path = Path(checkpoint_path)
        self.config_path = Path(config_path)
        self._config: Optional[dict] = None
        self._checkpoint: Optional[dict] = None

    def evaluate(self) -> dict:
        """
        Run full evaluation and return the benchmark report dict.

        Returns:
            Report dict suitable for JSON serialisation.
        """
        config = self._load_config()
        checkpoint = self._load_checkpoint()

        # ── Imports ────────────────────────────────────────────────────────
        import yaml
        from src.training.datasets import SyntheticSOPDataset
        from src.training.models import ActionRecognizer
        from src.training.trainer import set_seed

        seed = config.get("seed", 42)
        set_seed(seed)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("Evaluating on device: %s", device)

        # ── Dataset ────────────────────────────────────────────────────────
        ds_cfg = config["dataset"]
        index_path = _PROJECT_ROOT / config["paths"]["synthetic_dir"] / "dataset_index.json"
        frame_size = tuple(ds_cfg["frame_size"])

        test_ds = SyntheticSOPDataset(
            index_path,
            num_frames=ds_cfg["clip_sample_frames"],
            frame_size=frame_size,
            split="test",
            val_split=ds_cfg["val_split"],
            test_split=ds_cfg["test_split"],
            seed=seed,
        )

        if len(test_ds) == 0:
            raise RuntimeError(
                "Test split is empty. Build the dataset first: "
                "python -m src.simulation.dataset_builder"
            )

        logger.info("Test clips: %d", len(test_ds))

        test_loader = DataLoader(
            test_ds,
            batch_size=config["action_recognition"]["batch_size"],
            shuffle=False,
            num_workers=0,
            collate_fn=_forge_collate_fn,
        )

        # ── Model ──────────────────────────────────────────────────────────
        ar_cfg = checkpoint.get("config", config["action_recognition"])
        num_classes = checkpoint.get("num_classes", test_ds.num_classes)
        class_names = checkpoint.get("class_names", test_ds.class_names)

        model = ActionRecognizer(
            num_classes=num_classes,
            backbone=ar_cfg.get("backbone", "mobilenet_v3_small"),
            lstm_hidden_size=ar_cfg.get("lstm_hidden_size", 256),
            lstm_num_layers=ar_cfg.get("lstm_num_layers", 2),
            lstm_dropout=ar_cfg.get("lstm_dropout", 0.3),
            pretrained=False,
        ).to(device)

        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()

        # ── Inference ──────────────────────────────────────────────────────
        all_preds: list[int] = []
        all_targets: list[int] = []
        all_top3_correct: list[bool] = []
        batch_latencies_ms: list[float] = []

        with torch.no_grad():
            for frames, labels in test_loader:
                frames = frames.to(device)
                targets = labels["scenario_idx"]

                t0 = time.perf_counter()
                logits = model(frames)
                latency_ms = (time.perf_counter() - t0) * 1000.0
                batch_latencies_ms.append(latency_ms)

                preds = logits.argmax(dim=1).cpu().tolist()
                targets_list = targets.tolist()
                all_preds.extend(preds)
                all_targets.extend(targets_list)

                # Top-3 accuracy
                top3 = logits.topk(min(3, num_classes), dim=1).indices.cpu()
                for i, t in enumerate(targets_list):
                    all_top3_correct.append(t in top3[i].tolist())

        # ── Metrics ────────────────────────────────────────────────────────
        n = len(all_targets)
        correct = sum(p == t for p, t in zip(all_preds, all_targets))
        accuracy = _safe_div(correct, n)
        top3_accuracy = _safe_div(sum(all_top3_correct), n)

        cm = compute_confusion_matrix(all_targets, all_preds, num_classes)
        per_class = per_class_metrics(cm, class_names)
        macro = macro_averages(per_class)

        latencies = np.array(batch_latencies_ms)
        batch_size = config["action_recognition"]["batch_size"]

        # ── Edge readiness ─────────────────────────────────────────────────
        param_count = model.param_count
        model_size_mb = sum(
            p.numel() * p.element_size() for p in model.parameters()
        ) / (1024 ** 2)

        target_acc = config["action_recognition"].get("target_accuracy", 0.85)
        target_latency_ms = config.get("edge_deployment", {}).get(
            "max_action_recognition_latency_ms", 500
        )
        per_sample_latency_mean = _safe_div(latencies.mean(), batch_size) if len(latencies) > 0 else 0.0
        per_sample_latency_p95 = (
            _safe_div(float(np.percentile(latencies, 95)), batch_size)
            if len(latencies) > 0 else 0.0
        )

        edge_ready = (
            accuracy >= target_acc
            and per_sample_latency_p95 <= target_latency_ms
            and param_count <= 5_000_000
        )

        # ── Report ─────────────────────────────────────────────────────────
        report = {
            "metadata": {
                "checkpoint": str(self.checkpoint_path),
                "dataset_index": str(index_path),
                "num_test_clips": n,
                "num_classes": num_classes,
                "class_names": class_names,
                "seed": seed,
                "device": str(device),
                "checkpoint_epoch": checkpoint.get("epoch", "unknown"),
                "checkpoint_val_accuracy": checkpoint.get("val_accuracy"),
            },
            "accuracy": {
                "overall": round(accuracy, 4),
                "top3": round(top3_accuracy, 4),
                "correct": correct,
                "total": n,
                "target": target_acc,
                "meets_target": accuracy >= target_acc,
            },
            "macro_averages": macro,
            "per_class": per_class,
            "confusion_matrix": {
                "raw": cm.tolist(),
                "normalised": (
                    (cm.astype(float) / cm.sum(axis=1, keepdims=True).clip(min=1))
                    .round(4).tolist()
                ),
                "class_names": class_names,
            },
            "latency": {
                "batch_size": batch_size,
                "mean_batch_ms": round(float(latencies.mean()), 2) if len(latencies) > 0 else 0.0,
                "p95_batch_ms": round(float(np.percentile(latencies, 95)), 2) if len(latencies) > 0 else 0.0,
                "per_sample_mean_ms": round(per_sample_latency_mean, 2),
                "per_sample_p95_ms": round(per_sample_latency_p95, 2),
                "target_per_sample_ms": target_latency_ms,
                "meets_latency_target": per_sample_latency_p95 <= target_latency_ms,
            },
            "model": {
                "param_count": param_count,
                "model_size_mb": round(model_size_mb, 2),
                "backbone": ar_cfg.get("backbone", "mobilenet_v3_small"),
                "lstm_hidden_size": ar_cfg.get("lstm_hidden_size", 256),
                "lstm_num_layers": ar_cfg.get("lstm_num_layers", 2),
            },
            "edge_deployment": {
                "ready": edge_ready,
                "checks": {
                    "accuracy_ok": accuracy >= target_acc,
                    "latency_ok": per_sample_latency_p95 <= target_latency_ms,
                    "param_count_ok": param_count <= 5_000_000,
                },
            },
        }

        logger.info(
            "Evaluation complete | accuracy=%.3f (target=%.2f) | top3=%.3f | "
            "edge_ready=%s",
            accuracy, target_acc, top3_accuracy, edge_ready,
        )
        return report

    # ── Helpers ───────────────────────────────────────────────────────────

    def _load_config(self) -> dict:
        if self._config is None:
            import yaml
            with open(self.config_path, encoding="utf-8") as f:
                self._config = yaml.safe_load(f)
        return self._config

    def _load_checkpoint(self) -> dict:
        if self._checkpoint is None:
            if not self.checkpoint_path.exists():
                raise FileNotFoundError(
                    f"Checkpoint not found: {self.checkpoint_path}\n"
                    "Train the model first: python -m src.training.trainer"
                )
            self._checkpoint = torch.load(
                self.checkpoint_path, map_location="cpu", weights_only=True
            )
        return self._checkpoint

    @staticmethod
    def save_report(report: dict, path: str | Path = _DEFAULT_REPORT) -> Path:
        """Save the benchmark report as a JSON file."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        logger.info("Report saved: %s", out)
        return out

    @staticmethod
    def print_summary(report: dict) -> None:
        """Print a human-readable summary to stdout."""
        acc = report["accuracy"]
        lat = report["latency"]
        model = report["model"]
        edge = report["edge_deployment"]
        macro = report["macro_averages"]

        print("\n-- FORGE-Vision Evaluation Report ---------------------------------------")
        print(f"  Checkpoint       : {report['metadata']['checkpoint']}")
        print(f"  Test clips       : {acc['total']}")
        print(f"  Classes          : {report['metadata']['num_classes']}")
        print()
        print(f"  Accuracy         : {acc['overall']:.3f}  (target >= {acc['target']:.2f})  "
              f"{'PASS' if acc['meets_target'] else 'FAIL'}")
        print(f"  Top-3 Accuracy   : {acc['top3']:.3f}")
        print(f"  Macro F1         : {macro['f1']:.3f}")
        print()
        print(f"  Latency (p95/sample): {lat['per_sample_p95_ms']:.1f}ms  "
              f"(target <= {lat['target_per_sample_ms']}ms)  "
              f"{'PASS' if lat['meets_latency_target'] else 'FAIL'}")
        print()
        print(f"  Param count      : {model['param_count']:,}")
        print(f"  Model size       : {model['model_size_mb']:.1f} MB")
        print()
        print(f"  Edge deployment  : {'READY' if edge['ready'] else 'NOT READY'}")
        print()
        print("  Per-class metrics:")
        for pc in report["per_class"]:
            print(
                f"    {pc['class']:<28}  "
                f"P={pc['precision']:.3f}  R={pc['recall']:.3f}  "
                f"F1={pc['f1']:.3f}  n={pc['support']}"
            )
        print("-------------------------------------------------------------------------\n")


# ── CLI entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Evaluate FORGE-Vision action recognizer")
    parser.add_argument(
        "--checkpoint",
        default=str(_DEFAULT_CHECKPOINT),
        help="Path to model checkpoint (.pth)",
    )
    parser.add_argument(
        "--config",
        default=str(_DEFAULT_CONFIG),
        help="Path to train_config.yaml",
    )
    parser.add_argument(
        "--report",
        default=str(_DEFAULT_REPORT),
        help="Output path for JSON report",
    )
    args = parser.parse_args()

    evaluator = ModelEvaluator(
        checkpoint_path=args.checkpoint,
        config_path=args.config,
    )
    report = evaluator.evaluate()
    ModelEvaluator.save_report(report, args.report)
    ModelEvaluator.print_summary(report)
