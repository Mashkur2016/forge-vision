"""
Tests for src/training/datasets.py — SyntheticSOPDataset.

The minimal_dataset_dir fixture writes the index in the exact format that
DatasetBuilder produces:
    {
        "stats": {...},
        "clips": [
            {"clip_id": ..., "file": "<relative/path.avi>", "sop_id": ..., ...},
            ...
        ]
    }

Full dataset integration tests (requiring a real built dataset) are marked
integration and skipped by default.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.training.datasets import (
    ERROR_TYPE_TO_IDX,
    SCENARIO_TO_IDX,
    SyntheticSOPDataset,
)


# ── Constants ──────────────────────────────────────────────────────────────

class TestScenarioMapping:
    def test_scenario_to_idx_has_5_classes(self):
        assert len(SCENARIO_TO_IDX) == 5

    def test_scenario_values_contiguous(self):
        values = sorted(SCENARIO_TO_IDX.values())
        assert values == list(range(len(SCENARIO_TO_IDX)))

    def test_error_type_to_idx_keys(self):
        # TIMEOUT is an additional error type in the dataset beyond the 6 deviation classes
        required = {"CORRECT", "MISSING_STEP", "WRONG_ORDER",
                    "INCORRECT_EXECUTION", "MISSING_PPE", "UNSAFE_POSTURE"}
        assert required.issubset(set(ERROR_TYPE_TO_IDX.keys()))


# ── Minimal synthetic dataset fixture ─────────────────────────────────────

@pytest.fixture
def minimal_dataset_dir(tmp_path: Path) -> Path:
    """
    Creates a minimal dataset directory with 5-frame AVI clips and a
    dataset_index.json in the exact format written by DatasetBuilder.
    """
    import cv2

    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()

    scenarios = ["correct", "missing_step", "wrong_order", "unsafe", "rare_failure"]
    error_types = ["CORRECT", "MISSING_STEP", "WRONG_ORDER", "MISSING_PPE", "MISSING_STEP"]

    clip_entries = []
    for i, (scenario, error_type) in enumerate(zip(scenarios, error_types)):
        filename = f"clips/clip_{i:04d}.avi"
        abs_path = tmp_path / filename

        # Write a minimal 5-frame AVI (5 solid-colour frames)
        writer = cv2.VideoWriter(
            str(abs_path),
            cv2.VideoWriter_fourcc(*"MJPG"),
            10,
            (112, 112),
        )
        for _ in range(5):
            frame = np.full((112, 112, 3), i * 40, dtype=np.uint8)
            writer.write(frame)
        writer.release()

        clip_entries.append({
            "clip_id": f"clip_{i:04d}",
            "file": filename,                    # relative to tmp_path (index parent)
            "sop_id": "fire_evacuation_marshal_v1",
            "sop_name": "Motor Wiring",
            "scenario_type": scenario,
            "executed_steps": list(range(1, 8)),
            "error_step_id": None if scenario == "correct" else i + 1,
            "error_type": error_type,
            "frame_count": 5,
            "augmented": False,
        })

    index = {
        "stats": {
            "total_clips": len(clip_entries),
            "total_frames": len(clip_entries) * 5,
            "clips_by_scenario": {s: 1 for s in scenarios},
            "clips_by_sop": {"fire_evacuation_marshal_v1": len(clip_entries)},
            "errors": [],
        },
        "clips": clip_entries,
    }

    index_path = tmp_path / "dataset_index.json"
    with open(index_path, "w") as f:
        json.dump(index, f)

    return tmp_path


# ── SyntheticSOPDataset ────────────────────────────────────────────────────

class TestSyntheticSOPDatasetInit:
    def test_loads_index(self, minimal_dataset_dir):
        index_path = minimal_dataset_dir / "dataset_index.json"
        ds = SyntheticSOPDataset(index_path, num_frames=4, frame_size=(112, 112), split="train", seed=42)
        assert len(ds) > 0

    def test_num_classes(self, minimal_dataset_dir):
        index_path = minimal_dataset_dir / "dataset_index.json"
        ds = SyntheticSOPDataset(index_path, num_frames=4, frame_size=(112, 112), split="train", seed=42)
        assert ds.num_classes == len(SCENARIO_TO_IDX)

    def test_class_names(self, minimal_dataset_dir):
        index_path = minimal_dataset_dir / "dataset_index.json"
        ds = SyntheticSOPDataset(index_path, num_frames=4, frame_size=(112, 112), split="train", seed=42)
        assert isinstance(ds.class_names, list)
        assert len(ds.class_names) == ds.num_classes

    def test_split_train_val_test_disjoint(self, minimal_dataset_dir):
        """Train / val / test splits must not overlap."""
        index_path = minimal_dataset_dir / "dataset_index.json"
        kwargs = dict(num_frames=4, frame_size=(112, 112), val_split=0.2, test_split=0.2, seed=42)
        train_ds = SyntheticSOPDataset(index_path, split="train", **kwargs)
        val_ds   = SyntheticSOPDataset(index_path, split="val",   **kwargs)
        test_ds  = SyntheticSOPDataset(index_path, split="test",  **kwargs)

        train_paths = {str(r.file_path) for r in train_ds.records}
        val_paths   = {str(r.file_path) for r in val_ds.records}
        test_paths  = {str(r.file_path) for r in test_ds.records}

        assert train_paths.isdisjoint(val_paths)
        assert train_paths.isdisjoint(test_paths)
        assert val_paths.isdisjoint(test_paths)

    def test_split_sizes_sum_to_total(self, minimal_dataset_dir):
        index_path = minimal_dataset_dir / "dataset_index.json"
        kwargs = dict(num_frames=4, frame_size=(112, 112), val_split=0.2, test_split=0.2, seed=42)
        train_ds = SyntheticSOPDataset(index_path, split="train", **kwargs)
        val_ds   = SyntheticSOPDataset(index_path, split="val",   **kwargs)
        test_ds  = SyntheticSOPDataset(index_path, split="test",  **kwargs)

        with open(index_path) as f:
            total = len(json.load(f)["clips"])

        assert len(train_ds) + len(val_ds) + len(test_ds) == total

    def test_reproducible_with_seed(self, minimal_dataset_dir):
        index_path = minimal_dataset_dir / "dataset_index.json"
        kwargs = dict(num_frames=4, frame_size=(112, 112), split="train", seed=42)
        ds1 = SyntheticSOPDataset(index_path, **kwargs)
        ds2 = SyntheticSOPDataset(index_path, **kwargs)
        paths1 = [str(r.file_path) for r in ds1.records]
        paths2 = [str(r.file_path) for r in ds2.records]
        assert paths1 == paths2

    def test_missing_index_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            SyntheticSOPDataset(tmp_path / "nonexistent.json", num_frames=4)

    def test_invalid_split_raises(self, minimal_dataset_dir):
        index_path = minimal_dataset_dir / "dataset_index.json"
        with pytest.raises(ValueError, match="split"):
            SyntheticSOPDataset(index_path, num_frames=4, split="invalid")


class TestSyntheticSOPDatasetGetitem:
    def test_returns_tensor_and_dict(self, minimal_dataset_dir):
        import torch
        index_path = minimal_dataset_dir / "dataset_index.json"
        ds = SyntheticSOPDataset(index_path, num_frames=4, frame_size=(112, 112), split="train", seed=42)
        if len(ds) == 0:
            pytest.skip("No train samples available with this split configuration")
        frames, label = ds[0]
        assert isinstance(frames, torch.Tensor)
        assert isinstance(label, dict)

    def test_tensor_shape(self, minimal_dataset_dir):
        import torch
        index_path = minimal_dataset_dir / "dataset_index.json"
        ds = SyntheticSOPDataset(index_path, num_frames=4, frame_size=(112, 112), split="train", seed=42)
        if len(ds) == 0:
            pytest.skip("No train samples")
        frames, _ = ds[0]
        # (T, C, H, W)
        assert frames.shape == (4, 3, 112, 112)

    def test_tensor_dtype_float32(self, minimal_dataset_dir):
        import torch
        index_path = minimal_dataset_dir / "dataset_index.json"
        ds = SyntheticSOPDataset(index_path, num_frames=4, frame_size=(112, 112), split="train", seed=42)
        if len(ds) == 0:
            pytest.skip("No train samples")
        frames, _ = ds[0]
        assert frames.dtype == torch.float32

    def test_tensor_values_in_0_1(self, minimal_dataset_dir):
        index_path = minimal_dataset_dir / "dataset_index.json"
        ds = SyntheticSOPDataset(index_path, num_frames=4, frame_size=(112, 112), split="train", seed=42)
        if len(ds) == 0:
            pytest.skip("No train samples")
        frames, _ = ds[0]
        assert float(frames.min()) >= 0.0
        assert float(frames.max()) <= 1.0 + 1e-5

    def test_label_has_required_keys(self, minimal_dataset_dir):
        index_path = minimal_dataset_dir / "dataset_index.json"
        ds = SyntheticSOPDataset(index_path, num_frames=4, frame_size=(112, 112), split="train", seed=42)
        if len(ds) == 0:
            pytest.skip("No train samples")
        _, label = ds[0]
        assert "scenario_idx" in label
        assert "error_type_idx" in label
        assert "sop_id" in label

    def test_scenario_idx_in_valid_range(self, minimal_dataset_dir):
        import torch
        index_path = minimal_dataset_dir / "dataset_index.json"
        ds = SyntheticSOPDataset(index_path, num_frames=4, frame_size=(112, 112), split="train", seed=42)
        if len(ds) == 0:
            pytest.skip("No train samples")
        _, label = ds[0]
        idx = label["scenario_idx"]
        assert isinstance(idx, torch.Tensor)
        assert int(idx.item()) in range(ds.num_classes)
