"""
Unit tests for src/intelligence/continual_learner.py — Enhancement 5 (Task 4.6).

Tests cover:
  - EWC penalty is zero before any consolidation and immediately after it
  - Penalty grows as parameters drift from the consolidated anchor
  - Fisher information: one non-negative tensor per trainable param, correct shapes
  - Catastrophic-forgetting mitigation: with EWC, prior-task accuracy is retained
    better than without EWC on a two-task toy problem
  - Reproducibility with a fixed seed
"""
from __future__ import annotations

import copy

import numpy as np
import pytest

torch = pytest.importorskip("torch")
import torch.nn as nn  # noqa: E402
from torch.utils.data import DataLoader, TensorDataset  # noqa: E402

from src.intelligence.continual_learner import ContinualLearner, set_seed  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_model(seed: int = 42) -> nn.Module:
    set_seed(seed)
    return nn.Sequential(nn.Linear(8, 16), nn.ReLU(), nn.Linear(16, 2))


def _toy_loader(rule_feature: int, n: int = 256, seed: int = 0) -> DataLoader:
    """Binary task: label = 1 iff feature[rule_feature] > 0. Tasks differ by feature."""
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n, 8)).astype("float32")
    y = (X[:, rule_feature] > 0).astype("int64")
    ds = TensorDataset(torch.from_numpy(X), torch.from_numpy(y))
    return DataLoader(ds, batch_size=32, shuffle=False)


# ── EWC penalty ────────────────────────────────────────────────────────────────

def test_penalty_zero_without_consolidation():
    learner = ContinualLearner(_make_model(), ewc_lambda=100.0)
    assert learner.n_consolidated_tasks == 0
    assert float(learner.ewc_penalty()) == 0.0


def test_penalty_zero_immediately_after_consolidate():
    learner = ContinualLearner(_make_model(), ewc_lambda=100.0)
    learner.consolidate(_toy_loader(rule_feature=0))
    assert learner.n_consolidated_tasks == 1
    # Parameters have not moved from their anchor yet → penalty ≈ 0.
    assert float(learner.ewc_penalty()) == pytest.approx(0.0, abs=1e-6)


def test_penalty_grows_with_drift():
    learner = ContinualLearner(_make_model(), ewc_lambda=100.0)
    learner.consolidate(_toy_loader(rule_feature=0))
    # Perturb every parameter away from its anchor.
    with torch.no_grad():
        for p in learner.model.parameters():
            p.add_(1.0)
    assert float(learner.ewc_penalty()) > 0.0


# ── Fisher information ──────────────────────────────────────────────────────────

def test_fisher_shapes_and_nonnegative():
    learner = ContinualLearner(_make_model(), ewc_lambda=1.0)
    fisher = learner.compute_fisher(_toy_loader(rule_feature=0))
    trainable = {n: p for n, p in learner.model.named_parameters() if p.requires_grad}
    assert set(fisher.keys()) == set(trainable.keys())
    for name, tensor in fisher.items():
        assert tensor.shape == trainable[name].shape
        assert float(tensor.min()) >= 0.0  # Fisher (squared grads) is non-negative


# ── Catastrophic forgetting mitigation ──────────────────────────────────────────

def test_ewc_mitigates_forgetting():
    """After learning task B, EWC should retain task-A accuracy better than no EWC."""
    loader_a = _toy_loader(rule_feature=0, seed=1)
    loader_b = _toy_loader(rule_feature=1, seed=2)

    # 1) Learn task A.
    base = ContinualLearner(_make_model(seed=7), ewc_lambda=0.0, lr=1e-2, seed=7)
    base.fit_increment(loader_a, epochs=15)
    acc_a_initial = base.evaluate(loader_a)
    assert acc_a_initial > 0.85, acc_a_initial  # task A genuinely learned

    post_a_state = copy.deepcopy(base.model.state_dict())

    # 2a) EWC run: consolidate A, then learn B with a strong penalty.
    model_ewc = _make_model(seed=7)
    model_ewc.load_state_dict(copy.deepcopy(post_a_state))
    ewc = ContinualLearner(model_ewc, ewc_lambda=5000.0, lr=1e-2, seed=7)
    ewc.consolidate(loader_a)
    ewc.fit_increment(loader_b, epochs=15)
    acc_a_ewc = ewc.evaluate(loader_a)

    # 2b) Control run: same starting weights, learn B with no penalty.
    model_ctrl = _make_model(seed=7)
    model_ctrl.load_state_dict(copy.deepcopy(post_a_state))
    ctrl = ContinualLearner(model_ctrl, ewc_lambda=0.0, lr=1e-2, seed=7)
    ctrl.fit_increment(loader_b, epochs=15)
    acc_a_ctrl = ctrl.evaluate(loader_a)

    # EWC must forget task A less than the unconstrained control.
    assert acc_a_ewc > acc_a_ctrl, (acc_a_ewc, acc_a_ctrl)


# ── Reproducibility ─────────────────────────────────────────────────────────────

def test_fisher_reproducible():
    f1 = ContinualLearner(_make_model(seed=3), seed=3).compute_fisher(_toy_loader(rule_feature=0))
    f2 = ContinualLearner(_make_model(seed=3), seed=3).compute_fisher(_toy_loader(rule_feature=0))
    for name in f1:
        assert torch.allclose(f1[name], f2[name])
