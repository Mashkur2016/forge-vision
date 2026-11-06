"""
Continual Learning via Elastic Weight Consolidation (EWC) — Enhancement 5 (Task 4.6).

Enables the trained `ActionRecognizer` (or any ``torch.nn.Module``) to be
incrementally updated on newly captured, labelled workplace footage *without*
catastrophically forgetting what it already learned on the Phase-1 synthetic
dataset.

Method
------
EWC (Kirkpatrick et al., 2017) adds a quadratic penalty to the training loss
that anchors parameters important to previous tasks near their consolidated
values.  Importance is estimated by the diagonal of the Fisher information
matrix:

    L(theta) = L_task(theta) + (lambda / 2) * Σ_i  F_i * (theta_i - theta*_i)^2

where ``theta*`` is the parameter snapshot taken after the previous task and
``F_i`` is the Fisher importance of parameter ``i``.  Multiple consolidations
accumulate (one penalty term per remembered task), so the model can be updated
repeatedly as more footage arrives.

Rules.md compliance
-------------------
* §1.2  Type hints on all public signatures; docstrings where logic is non-obvious.
* §1.5  Reproducible — a fixed seed governs every stochastic step (see ``set_seed``).

This module deliberately implements the algorithm only; wiring it into a live
retraining loop (triggered from new DeviationLog data) is documented as future
work in the System Implementation Report.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader


def set_seed(seed: int) -> None:
    """Fix all random seeds for reproducibility (Rules.md §1.5)."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


@dataclass
class _Task:
    """A consolidated task: parameter anchor + Fisher importance (per param name)."""
    anchor: dict[str, torch.Tensor]
    fisher: dict[str, torch.Tensor]


class ContinualLearner:
    """
    Incremental trainer with Elastic Weight Consolidation.

    Typical usage:
        learner = ContinualLearner(model, ewc_lambda=1000.0, seed=42)
        learner.consolidate(task_a_loader)        # remember task A
        learner.fit_increment(task_b_loader, epochs=3)  # learn B, protect A

    Args:
        model:        The network to update in place.
        ewc_lambda:   Regularisation strength (importance of remembering).
        lr:           Learning rate for the internal Adam optimiser.
        device:       Torch device; defaults to CUDA if available else CPU.
        criterion:    Task loss; defaults to cross-entropy (classification).
        seed:         Random seed for reproducibility (Rules.md §1.5).
    """

    def __init__(
        self,
        model: nn.Module,
        ewc_lambda: float = 1000.0,
        lr: float = 1e-3,
        device: Optional[torch.device] = None,
        criterion: Optional[nn.Module] = None,
        seed: int = 42,
    ) -> None:
        set_seed(seed)
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = model.to(self.device)
        self.ewc_lambda = float(ewc_lambda)
        self.criterion = criterion or nn.CrossEntropyLoss()
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        self._tasks: list[_Task] = []

    # ── EWC machinery ──────────────────────────────────────────────────────────

    def _trainable_params(self) -> Iterable[tuple[str, torch.nn.Parameter]]:
        return ((n, p) for n, p in self.model.named_parameters() if p.requires_grad)

    def compute_fisher(self, dataloader: DataLoader, max_batches: Optional[int] = None) -> dict[str, torch.Tensor]:
        """
        Estimate the diagonal Fisher information over the current parameters.

        Uses the empirical Fisher: the mean squared gradient of the task loss
        evaluated on the given (labelled) data.  Returns one non-negative tensor
        per trainable parameter, matching its shape.
        """
        fisher: dict[str, torch.Tensor] = {
            n: torch.zeros_like(p, device=self.device) for n, p in self._trainable_params()
        }
        self.model.eval()
        n_samples = 0
        for batch_idx, (inputs, targets) in enumerate(dataloader):
            if max_batches is not None and batch_idx >= max_batches:
                break
            inputs = inputs.to(self.device)
            targets = targets.to(self.device)
            self.model.zero_grad(set_to_none=True)
            logits = self.model(inputs)
            loss = self.criterion(logits, targets)
            loss.backward()
            batch_size = inputs.size(0)
            for n, p in self._trainable_params():
                if p.grad is not None:
                    fisher[n] += (p.grad.detach() ** 2) * batch_size
            n_samples += batch_size

        if n_samples > 0:
            for n in fisher:
                fisher[n] /= n_samples
        self.model.zero_grad(set_to_none=True)
        return fisher

    def consolidate(self, dataloader: DataLoader, max_batches: Optional[int] = None) -> None:
        """
        Snapshot the current parameters and their Fisher importance as a task to
        be remembered.  Call this after the model has learned a task and before
        training it on the next one.
        """
        fisher = self.compute_fisher(dataloader, max_batches=max_batches)
        anchor = {n: p.detach().clone() for n, p in self._trainable_params()}
        self._tasks.append(_Task(anchor=anchor, fisher=fisher))

    def ewc_penalty(self) -> torch.Tensor:
        """Σ over remembered tasks of  F_i * (theta_i - theta*_i)^2  (scalar tensor)."""
        if not self._tasks:
            return torch.zeros((), device=self.device)
        penalty = torch.zeros((), device=self.device)
        current = dict(self._trainable_params())
        for task in self._tasks:
            for n, theta in current.items():
                if n in task.fisher:
                    penalty = penalty + (task.fisher[n] * (theta - task.anchor[n]) ** 2).sum()
        return penalty

    @property
    def n_consolidated_tasks(self) -> int:
        return len(self._tasks)

    # ── Incremental training ───────────────────────────────────────────────────

    def update(self, inputs: torch.Tensor, targets: torch.Tensor) -> dict[str, float]:
        """
        One optimisation step on a single batch, combining the task loss with the
        EWC penalty.  Returns the component losses for logging.
        """
        self.model.train()
        inputs = inputs.to(self.device)
        targets = targets.to(self.device)
        self.optimizer.zero_grad(set_to_none=True)
        logits = self.model(inputs)
        task_loss = self.criterion(logits, targets)
        ewc_loss = (self.ewc_lambda / 2.0) * self.ewc_penalty()
        total = task_loss + ewc_loss
        total.backward()
        self.optimizer.step()
        return {
            "task_loss": float(task_loss.detach()),
            "ewc_loss": float(ewc_loss.detach()),
            "total_loss": float(total.detach()),
        }

    def fit_increment(self, dataloader: DataLoader, epochs: int = 1) -> list[dict[str, float]]:
        """Train on a new task for ``epochs`` passes, returning per-epoch mean losses."""
        history: list[dict[str, float]] = []
        for _ in range(epochs):
            sums = {"task_loss": 0.0, "ewc_loss": 0.0, "total_loss": 0.0}
            n_batches = 0
            for inputs, targets in dataloader:
                step = self.update(inputs, targets)
                for k in sums:
                    sums[k] += step[k]
                n_batches += 1
            if n_batches:
                history.append({k: v / n_batches for k, v in sums.items()})
        return history

    @torch.no_grad()
    def evaluate(self, dataloader: DataLoader) -> float:
        """Classification accuracy over a dataloader — a convenience for callers/tests."""
        self.model.eval()
        correct = 0
        total = 0
        for inputs, targets in dataloader:
            inputs = inputs.to(self.device)
            targets = targets.to(self.device)
            preds = self.model(inputs).argmax(dim=1)
            correct += int((preds.cpu() == targets.cpu()).sum())
            total += targets.size(0)
        return correct / total if total else 0.0
