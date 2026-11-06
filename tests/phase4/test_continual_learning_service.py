"""
Tests for src/intelligence/continual_learning_service.py — Enhancement 5 wiring.

Uses an injected toy model and toy dataloaders (and a redirected runs directory) so
the orchestration logic is exercised quickly without loading video clips or touching
the real model checkpoint or the repository's experiments/ directory.
"""
from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")
import torch.nn as nn  # noqa: E402
from torch.utils.data import DataLoader, TensorDataset  # noqa: E402

from src.intelligence import continual_learning_service as cls  # noqa: E402
from src.intelligence.continual_learner import set_seed  # noqa: E402


def _toy_model() -> nn.Module:
    set_seed(42)
    return nn.Sequential(nn.Linear(8, 16), nn.ReLU(), nn.Linear(16, 2))


def _toy_loader(rule_feature: int, n: int = 64, seed: int = 0) -> DataLoader:
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n, 8)).astype("float32")
    y = (X[:, rule_feature] > 0).astype("int64")
    return DataLoader(TensorDataset(torch.from_numpy(X), torch.from_numpy(y)), batch_size=16)


@pytest.fixture(autouse=True)
def _isolate_runs_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(cls, "RUNS_DIR", tmp_path / "continual_runs")


def test_run_round_completes_and_records_metrics():
    record = cls.run_round(
        "testrun01",
        model=_toy_model(),
        base_loader=_toy_loader(rule_feature=0, seed=1),
        increment_loader=_toy_loader(rule_feature=1, seed=2),
        epochs=2,
        save_checkpoint=False,
    )
    assert record["status"] == "completed", record.get("error")
    assert record["data_mode"] == "injected"
    m = record["metrics"]
    assert "base_accuracy_before" in m
    assert "base_accuracy_after" in m
    assert "knowledge_retention" in m
    assert "increment_accuracy" in m
    assert m["consolidated_tasks"] == 1
    assert len(m["epoch_losses"]) == 2


def test_run_round_is_persisted_and_listable():
    cls.run_round(
        "testrun02",
        model=_toy_model(),
        base_loader=_toy_loader(rule_feature=0, seed=1),
        increment_loader=_toy_loader(rule_feature=1, seed=2),
        save_checkpoint=False,
    )
    fetched = cls.get_run("testrun02")
    assert fetched is not None
    assert fetched["run_id"] == "testrun02"
    runs = cls.list_runs()
    assert any(r["run_id"] == "testrun02" for r in runs)


def test_get_unknown_run_returns_none():
    assert cls.get_run("does-not-exist") is None
