"""
Continual-learning orchestration service — wires Enhancement 5 into the running app.

This service turns the `ContinualLearner` (Elastic Weight Consolidation) into a usable,
admin-triggerable capability: it loads the trained ActionRecognizer, consolidates its
knowledge of the original (synthetic) task, runs a bounded incremental-learning round on
a "new data" partition, measures how well prior knowledge is retained, saves a versioned
updated checkpoint, and records the run as a JSON artefact.

In this build the "new data" is drawn from a held-out partition of the synthetic dataset,
as an honest demonstration of the mechanism; in production it would be newly labelled
Phase-B footage. Each run record states which data mode was used.

Runs are bounded (few clips, few epochs) so they complete in reasonable time on CPU, and
the heavy work is intended to be launched on a background thread by the API layer.

Rules.md §1.5: seeded for reproducibility. §3.1: synthetic data labelled as such.
"""
from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT / "experiments" / "continual_runs"
# Checkpoints are written under experiments/ (not models/), because the API container
# mounts models/ read-only; experiments/ is writable and persisted to the host.
CKPT_DIR = ROOT / "experiments" / "continual_ckpts"
DEFAULT_CHECKPOINT = ROOT / "models" / "action_recognizer_best.pth"
DEFAULT_INDEX = ROOT / "data" / "synthetic" / "dataset_index.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Run-record persistence (JSON, consistent with experiments/ convention) ───────

def _record_path(run_id: str) -> Path:
    return RUNS_DIR / f"{run_id}.json"


def write_record(record: dict[str, Any]) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    _record_path(record["run_id"]).write_text(json.dumps(record, indent=2), encoding="utf-8")


def get_run(run_id: str) -> Optional[dict[str, Any]]:
    path = _record_path(run_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_runs() -> list[dict[str, Any]]:
    if not RUNS_DIR.exists():
        return []
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in RUNS_DIR.glob("*.json")]
    return sorted(runs, key=lambda r: r.get("started_at", ""), reverse=True)


# ── Real-data loader construction ────────────────────────────────────────────────

class _ScenarioView:
    """Adapts SyntheticSOPDataset items to (frames, scenario_idx) for classification."""

    def __init__(self, base, max_items: int) -> None:
        self._base = base
        self._n = min(max_items, len(base))

    def __len__(self) -> int:
        return self._n

    def __getitem__(self, idx: int):
        frames, label = self._base[idx]
        return frames, int(label["scenario_idx"])


def _scan_clips(root: Path, augmented: bool) -> list:
    """
    Scan the synthetic clip tree (data/synthetic/<sop>/<scenario>/*.avi) and build
    ClipRecords, labelling each by its scenario directory. This is robust to an empty
    or stale dataset index, and mirrors how newly labelled footage would arrive on disk.
    """
    from src.training.datasets import SCENARIO_TO_IDX, ClipRecord

    records = []
    for avi in sorted(root.glob("*/*/*.avi")):
        is_aug = "_aug" in avi.stem
        if is_aug != augmented:
            continue
        scenario = avi.parent.name
        if scenario not in SCENARIO_TO_IDX:
            continue
        records.append(ClipRecord(
            clip_id=avi.stem, file_path=avi, sop_id=avi.parent.parent.name,
            scenario_type=scenario, scenario_idx=SCENARIO_TO_IDX[scenario],
            executed_steps=[], error_step_id=None, error_type=None, augmented=is_aug,
        ))
    return records


def _build_real_loaders(index_path: Path, max_clips: int, num_frames: int, batch_size: int, seed: int):
    """Build (base, increment) dataloaders from the synthetic clip tree. Returns (model, base, inc, meta)."""
    import random as _random

    from torch.utils.data import DataLoader

    from src.training.datasets import SyntheticSOPDataset
    from src.training.models import load_action_recognizer

    root = index_path.parent
    # Base task = original clips; increment ("new footage") = augmented clips.
    base_records = _scan_clips(root, augmented=False)
    inc_records = _scan_clips(root, augmented=True)
    rng = _random.Random(seed)
    rng.shuffle(base_records)
    rng.shuffle(inc_records)
    base_records = base_records[:max_clips]
    inc_records = inc_records[:max_clips]
    if not base_records or not inc_records:
        raise RuntimeError(
            f"Insufficient synthetic clips found under {root} "
            f"(base={len(base_records)}, increment={len(inc_records)})."
        )

    model = load_action_recognizer(str(DEFAULT_CHECKPOINT))
    base_ds = SyntheticSOPDataset(index_path, num_frames=num_frames, split="train", seed=seed)
    base_ds.records = base_records  # reuse the dataset's exact frame-loading pipeline
    inc_ds = SyntheticSOPDataset(index_path, num_frames=num_frames, split="val", seed=seed)
    inc_ds.records = inc_records
    base_loader = DataLoader(_ScenarioView(base_ds, max_clips), batch_size=batch_size, shuffle=False)
    inc_loader = DataLoader(_ScenarioView(inc_ds, max_clips), batch_size=batch_size, shuffle=False)
    return model, base_loader, inc_loader, {"n_base": len(base_records), "n_increment": len(inc_records)}


# ── Orchestration ────────────────────────────────────────────────────────────────

def run_round(
    run_id: str,
    *,
    ewc_lambda: float = 1000.0,
    epochs: int = 1,
    max_clips: int = 12,
    batch_size: int = 4,
    num_frames: int = 16,
    seed: int = 42,
    triggered_by: str = "system",
    # Injection points for testing (bypass the heavy real-data path):
    model: Any = None,
    base_loader: Any = None,
    increment_loader: Any = None,
    save_checkpoint: bool = True,
) -> dict[str, Any]:
    """
    Execute one continual-learning round and persist its record.

    Returns the final run record. The record is also written to disk at each
    state transition so the API/UI can poll progress.
    """
    record: dict[str, Any] = {
        "run_id": run_id,
        "status": "running",
        "started_at": _now_iso(),
        "finished_at": None,
        "triggered_by": triggered_by,
        "params": {
            "ewc_lambda": ewc_lambda, "epochs": epochs, "max_clips": max_clips,
            "batch_size": batch_size, "num_frames": num_frames, "seed": seed,
        },
        "data_mode": "injected" if base_loader is not None else "synthetic_demo",
        "metrics": {},
        "checkpoint": None,
        "note": (
            "New-data partition drawn from held-out synthetic clips as a demonstration of "
            "the EWC mechanism; in production this would be newly labelled Phase-B footage."
        ),
    }
    write_record(record)

    try:
        from src.intelligence.continual_learner import ContinualLearner

        if base_loader is None or increment_loader is None or model is None:
            model, base_loader, increment_loader, meta = _build_real_loaders(
                DEFAULT_INDEX, max_clips, num_frames, batch_size, seed
            )
            record["metrics"].update(meta)

        learner = ContinualLearner(model, ewc_lambda=ewc_lambda, seed=seed)

        base_before = learner.evaluate(base_loader)
        learner.consolidate(base_loader)
        history = learner.fit_increment(increment_loader, epochs=epochs)
        base_after = learner.evaluate(base_loader)
        increment_acc = learner.evaluate(increment_loader)

        retention = (base_after / base_before) if base_before > 0 else None
        record["metrics"].update({
            "base_accuracy_before": round(base_before, 4),
            "base_accuracy_after": round(base_after, 4),
            "knowledge_retention": round(retention, 4) if retention is not None else None,
            "increment_accuracy": round(increment_acc, 4),
            "epoch_losses": [{k: round(v, 4) for k, v in h.items()} for h in history],
            "consolidated_tasks": learner.n_consolidated_tasks,
        })

        if save_checkpoint:
            try:
                import torch
                CKPT_DIR.mkdir(parents=True, exist_ok=True)
                ckpt_path = CKPT_DIR / f"action_recognizer_cl_{run_id}.pth"
                torch.save({"model_state_dict": learner.model.state_dict(),
                            "continual_run_id": run_id}, ckpt_path)
                record["checkpoint"] = str(ckpt_path.relative_to(ROOT))
            except Exception as exc:  # noqa: BLE001 — checkpoint saving is non-fatal
                record["checkpoint"] = None
                record["metrics"]["checkpoint_warning"] = str(exc)

        record["status"] = "completed"
    except Exception as exc:  # noqa: BLE001 — record failure rather than crashing the worker
        record["status"] = "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["traceback"] = traceback.format_exc()
    finally:
        record["finished_at"] = _now_iso()
        write_record(record)

    return record
