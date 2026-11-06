"""
Training loop for FORGE-Vision Phase 2 models.

Trains the CNN+LSTM action recognition model on the Phase A synthetic dataset.
All experiments are logged to MLflow for full reproducibility (Rules.md §1.5).

Usage:
    python -m src.training.trainer
    python -m src.training.trainer --config config/train_config.yaml --epochs 30
"""
from __future__ import annotations

import argparse
import logging
import os
import time
from pathlib import Path

import mlflow
import numpy as np
import torch
import torch.nn as nn
import yaml
from torch.utils.data import DataLoader

from src.training.datasets import SyntheticSOPDataset
from src.training.models import ActionRecognizer

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_CONFIG = _PROJECT_ROOT / "config" / "train_config.yaml"


# ── Config loader ──────────────────────────────────────────────────────────

def load_config(path: str | Path = _DEFAULT_CONFIG) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── Training utilities ─────────────────────────────────────────────────────

def set_seed(seed: int) -> None:
    """Fix all random seeds for reproducibility (Rules.md §1.5)."""
    import random
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def get_device(config: dict) -> torch.device:
    device_str = config.get("object_detection", {}).get("device", "auto")
    if device_str == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(device_str)


# ── Custom collate ─────────────────────────────────────────────────────────

def _forge_collate_fn(batch):
    """
    Custom collate for SyntheticSOPDataset batches.

    Fixed-size tensors (frames, scenario_idx, error_type_idx, error_step_id)
    are stacked normally. Variable-length or non-tensor fields (executed_steps,
    sop_id, scenario_type, augmented) are kept as lists so batches work even
    when SOPs have different step counts.
    """
    frames = torch.stack([item[0] for item in batch])
    labels = {
        "scenario_idx":   torch.stack([item[1]["scenario_idx"]   for item in batch]),
        "error_type_idx": torch.stack([item[1]["error_type_idx"] for item in batch]),
        "error_step_id":  torch.stack([item[1]["error_step_id"]  for item in batch]),
        "sop_id":         [item[1]["sop_id"]         for item in batch],
        "scenario_type":  [item[1]["scenario_type"]  for item in batch],
        "augmented":      [item[1]["augmented"]       for item in batch],
        "executed_steps": [item[1]["executed_steps"]  for item in batch],
    }
    return frames, labels


# ── Training loop ──────────────────────────────────────────────────────────

class Trainer:
    """
    Trains the ActionRecognizer model on SyntheticSOPDataset.

    All metrics are logged to MLflow. The best model (highest val accuracy)
    is saved to models/action_recognizer_best.pth.
    """

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or load_config()
        self.device = get_device(self.config)
        self.ar_cfg = self.config["action_recognition"]
        self.mlflow_cfg = self.config["mlflow"]
        self.paths = self.config["paths"]
        self.seed = self.config["seed"]

        set_seed(self.seed)
        logger.info("Training on device: %s", self.device)

    def run(self) -> dict[str, float]:
        """
        Execute the full training run.

        Returns:
            dict with best_val_accuracy, final_train_loss, epochs_trained
        """
        # ── MLflow setup ───────────────────────────────────────────────────
        # Use .as_uri() so Windows paths become file:///D:/... (MLflow requirement)
        mlflow_uri = (_PROJECT_ROOT / self.mlflow_cfg["tracking_uri"]).resolve().as_uri()
        mlflow.set_tracking_uri(mlflow_uri)
        mlflow.set_experiment(self.mlflow_cfg["experiment_name"])

        with mlflow.start_run() as run:
            logger.info("MLflow run: %s", run.info.run_id)
            mlflow.log_params({
                "seed": self.seed,
                "backbone": self.ar_cfg["backbone"],
                "lstm_hidden_size": self.ar_cfg["lstm_hidden_size"],
                "lstm_num_layers": self.ar_cfg["lstm_num_layers"],
                "epochs": self.ar_cfg["epochs"],
                "batch_size": self.ar_cfg["batch_size"],
                "learning_rate": self.ar_cfg["learning_rate"],
                "num_frames": self.config["dataset"]["clip_sample_frames"],
                "frame_size": self.config["dataset"]["frame_size"],
            })

            results = self._train_loop()

            mlflow.log_metrics({
                "best_val_accuracy": results["best_val_accuracy"],
                "final_train_loss": results["final_train_loss"],
                "epochs_trained": results["epochs_trained"],
            })

            # Log model artifact
            best_model_path = _PROJECT_ROOT / self.paths["models_dir"] / "action_recognizer_best.pth"
            if best_model_path.exists():
                mlflow.log_artifact(str(best_model_path))

        return results

    def _train_loop(self) -> dict[str, float]:
        # ── Data ───────────────────────────────────────────────────────────
        index_path = _PROJECT_ROOT / self.paths["synthetic_dir"] / "dataset_index.json"

        ds_cfg = self.config["dataset"]
        frame_size = tuple(ds_cfg["frame_size"])

        train_ds = SyntheticSOPDataset(
            index_path,
            num_frames=ds_cfg["clip_sample_frames"],
            frame_size=frame_size,
            split="train",
            val_split=ds_cfg["val_split"],
            test_split=ds_cfg["test_split"],
            seed=self.seed,
        )
        val_ds = SyntheticSOPDataset(
            index_path,
            num_frames=ds_cfg["clip_sample_frames"],
            frame_size=frame_size,
            split="val",
            val_split=ds_cfg["val_split"],
            test_split=ds_cfg["test_split"],
            seed=self.seed,
        )

        logger.info("Train clips: %d | Val clips: %d", len(train_ds), len(val_ds))
        mlflow.log_params({"train_clips": len(train_ds), "val_clips": len(val_ds)})

        train_loader = DataLoader(
            train_ds,
            batch_size=self.ar_cfg["batch_size"],
            shuffle=True,
            num_workers=0,
            pin_memory=(self.device.type == "cuda"),
            collate_fn=_forge_collate_fn,
        )
        val_loader = DataLoader(
            val_ds,
            batch_size=self.ar_cfg["batch_size"],
            shuffle=False,
            num_workers=0,
            collate_fn=_forge_collate_fn,
        )

        # ── Model ──────────────────────────────────────────────────────────
        model = ActionRecognizer(
            num_classes=train_ds.num_classes,
            backbone=self.ar_cfg["backbone"],
            lstm_hidden_size=self.ar_cfg["lstm_hidden_size"],
            lstm_num_layers=self.ar_cfg["lstm_num_layers"],
            lstm_dropout=self.ar_cfg["lstm_dropout"],
        ).to(self.device)

        optimizer = torch.optim.Adam(
            model.parameters(),
            lr=self.ar_cfg["learning_rate"],
            weight_decay=self.ar_cfg["weight_decay"],
        )
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer,
            T_max=self.ar_cfg["epochs"],
            eta_min=self.ar_cfg["lr_min"],
        )
        criterion = nn.CrossEntropyLoss()

        # ── Training ───────────────────────────────────────────────────────
        models_dir = _PROJECT_ROOT / self.paths["models_dir"]
        models_dir.mkdir(parents=True, exist_ok=True)
        best_model_path = models_dir / "action_recognizer_best.pth"

        best_val_acc = 0.0
        patience_counter = 0
        patience = self.ar_cfg["patience"]
        min_delta = self.ar_cfg["min_delta"]
        epochs_trained = 0
        final_train_loss = float("inf")

        for epoch in range(1, self.ar_cfg["epochs"] + 1):
            t0 = time.time()

            train_loss, train_acc = self._run_epoch(
                model, train_loader, criterion, optimizer, training=True
            )
            val_loss, val_acc = self._run_epoch(
                model, val_loader, criterion, None, training=False
            )
            scheduler.step()

            epoch_time = time.time() - t0
            final_train_loss = train_loss
            epochs_trained = epoch

            logger.info(
                "Epoch %d/%d | train_loss=%.4f acc=%.3f | val_loss=%.4f acc=%.3f | %.1fs",
                epoch, self.ar_cfg["epochs"],
                train_loss, train_acc, val_loss, val_acc, epoch_time,
            )

            mlflow.log_metrics({
                "train_loss": train_loss,
                "train_acc": train_acc,
                "val_loss": val_loss,
                "val_acc": val_acc,
                "lr": scheduler.get_last_lr()[0],
            }, step=epoch)

            # Save best model
            if val_acc > best_val_acc + min_delta:
                best_val_acc = val_acc
                patience_counter = 0
                torch.save({
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "val_accuracy": val_acc,
                    "config": self.ar_cfg,
                    "num_classes": train_ds.num_classes,
                    "class_names": train_ds.class_names,
                }, best_model_path)
                logger.info("  ↑ New best val_acc=%.3f — model saved", best_val_acc)
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    logger.info("Early stopping at epoch %d (no improvement for %d epochs)", epoch, patience)
                    break

        logger.info(
            "Training complete. Best val_acc=%.3f | Target=%.2f | %s",
            best_val_acc,
            self.ar_cfg["target_accuracy"],
            "✓ TARGET MET" if best_val_acc >= self.ar_cfg["target_accuracy"] else "✗ Below target",
        )

        return {
            "best_val_accuracy": best_val_acc,
            "final_train_loss": final_train_loss,
            "epochs_trained": epochs_trained,
        }

    def _run_epoch(
        self,
        model: nn.Module,
        loader: DataLoader,
        criterion: nn.Module,
        optimizer: torch.optim.Optimizer | None,
        training: bool,
    ) -> tuple[float, float]:
        model.train(training)
        total_loss = 0.0
        correct = 0
        total = 0
        grad_clip = self.ar_cfg.get("gradient_clip", 1.0)

        ctx = torch.enable_grad() if training else torch.no_grad()
        with ctx:
            for frames, labels in loader:
                frames = frames.to(self.device)
                targets = labels["scenario_idx"].to(self.device)

                logits = model(frames)
                loss = criterion(logits, targets)

                if training and optimizer is not None:
                    optimizer.zero_grad()
                    loss.backward()
                    nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
                    optimizer.step()

                total_loss += loss.item() * frames.size(0)
                preds = logits.argmax(dim=1)
                correct += (preds == targets).sum().item()
                total += frames.size(0)

        avg_loss = total_loss / max(total, 1)
        accuracy = correct / max(total, 1)
        return avg_loss, accuracy


# ── CLI entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Train FORGE-Vision action recognizer")
    parser.add_argument("--config", default=str(_DEFAULT_CONFIG), help="Path to train_config.yaml")
    parser.add_argument("--epochs", type=int, help="Override epochs from config")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.epochs:
        config["action_recognition"]["epochs"] = args.epochs

    trainer = Trainer(config)
    results = trainer.run()

    print("\n-- Training Results --------------------------------------------------")
    print(f"  Best val accuracy : {results['best_val_accuracy']:.3f}")
    print(f"  Final train loss  : {results['final_train_loss']:.4f}")
    print(f"  Epochs trained    : {results['epochs_trained']}")
    target = config["action_recognition"]["target_accuracy"]
    status = "TARGET MET" if results["best_val_accuracy"] >= target else f"Below target ({target:.0%})"
    print(f"  Status            : {status}")
    print("---------------------------------------------------------------------\n")
