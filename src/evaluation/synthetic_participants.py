"""
Synthetic Participant Generator — Phase 5 (Task 5.2).

Generates statistically realistic synthetic participant data for evaluating
the three research hypotheses, since actual data collection requires ethical
approval that must be obtained separately.

Rules.md §3.1: Synthetic data explicitly labelled as synthetic.
Rules.md §3.3: Control group modelled on published literature on traditional
               manufacturing training outcomes.

Published baselines used:
    - Error rate (traditional): μ=5.8, σ=1.4 errors/task
      (from workplace procedural training literature range)
    - Task completion time (post-hoc feedback): μ=14.2 min, σ=2.8 min

FORGE-Vision improvements are modelled from the Architecture.md targets:
    - Error reduction: ~55% (target range: 1–3 vs 5–8 errors/task)
    - Time reduction: ~37% (target: ~9 min vs ~15 min)

All values seeded for reproducibility (Rules.md §1.5).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# ── Participant data ───────────────────────────────────────────────────────────

@dataclass
class ParticipantRecord:
    """Single participant's performance metrics for one evaluation trial."""
    participant_id: str
    group: str                     # "control" | "sim_only" | "realtime_only" | "hybrid"
    errors_per_task: float         # Mean deviations per SOP execution
    completion_time_min: float     # Mean task completion time in minutes
    sessions_to_competency: int    # Number of sessions to reach competency
    final_accuracy: float          # Proportion of steps completed correctly [0, 1]

    def to_dict(self) -> dict:
        return {
            "participant_id": self.participant_id,
            "group": self.group,
            "errors_per_task": round(self.errors_per_task, 3),
            "completion_time_min": round(self.completion_time_min, 2),
            "sessions_to_competency": self.sessions_to_competency,
            "final_accuracy": round(self.final_accuracy, 3),
        }


# ── Group parameter specifications ───────────────────────────────────────────

# Modelled on Architecture.md "Before vs After" table and literature:
# Traditional training: 5–8 errors/task, ~15 min, ~8 sessions to competency
# FORGE-Vision hybrid: 1–3 errors/task, ~9 min, ~4 sessions to competency

_GROUP_PARAMS: dict[str, dict] = {
    "control": {
        "error_mean": 5.8,
        "error_std": 1.4,
        "time_mean": 14.2,
        "time_std": 2.8,
        "sessions_mean": 8.1,
        "sessions_std": 1.8,
        "accuracy_mean": 0.62,
        "accuracy_std": 0.09,
    },
    "sim_only": {
        "error_mean": 3.4,
        "error_std": 1.1,
        "time_mean": 11.8,
        "time_std": 2.1,
        "sessions_mean": 6.3,
        "sessions_std": 1.5,
        "accuracy_mean": 0.74,
        "accuracy_std": 0.08,
    },
    "realtime_only": {
        "error_mean": 2.8,
        "error_std": 1.0,
        "time_mean": 10.5,
        "time_std": 2.0,
        "sessions_mean": 5.7,
        "sessions_std": 1.4,
        "accuracy_mean": 0.79,
        "accuracy_std": 0.07,
    },
    "hybrid": {
        "error_mean": 1.9,
        "error_std": 0.8,
        "time_mean": 8.7,
        "time_std": 1.6,
        "sessions_mean": 4.2,
        "sessions_std": 1.2,
        "accuracy_mean": 0.88,
        "accuracy_std": 0.06,
    },
    # Post-hoc feedback group (for H3: same population as hybrid but feedback delayed)
    "hybrid_posthoc": {
        "error_mean": 3.1,
        "error_std": 1.0,
        "time_mean": 12.4,
        "time_std": 2.3,
        "sessions_mean": 6.0,
        "sessions_std": 1.4,
        "accuracy_mean": 0.76,
        "accuracy_std": 0.07,
    },
}


class SyntheticParticipantGenerator:
    """
    Generate synthetic participant datasets for Phase 5 evaluation.

    All generated data is clearly labelled as SYNTHETIC in exports.
    Rules.md §3.1: Do not present synthetic results as real participant data.

    Usage:
        gen = SyntheticParticipantGenerator(seed=42)

        # H1: control vs hybrid
        control = gen.generate_group("control", n=64)
        treatment = gen.generate_group("hybrid", n=64)

        # H2: three-group comparison
        sim_only = gen.generate_group("sim_only", n=64)
        realtime_only = gen.generate_group("realtime_only", n=64)
        hybrid = gen.generate_group("hybrid", n=64)

        # H3: real-time vs post-hoc
        realtime = gen.generate_group("hybrid", n=64)
        posthoc = gen.generate_group("hybrid_posthoc", n=64)
    """

    def __init__(self, seed: int = 42) -> None:
        self._rng = np.random.default_rng(seed)
        self._counter: dict[str, int] = {}

    @property
    def available_groups(self) -> list[str]:
        return list(_GROUP_PARAMS.keys())

    def generate_group(
        self,
        group: str,
        n: int,
    ) -> list[ParticipantRecord]:
        """
        Generate n synthetic participant records for the given group.

        Args:
            group: One of "control", "sim_only", "realtime_only", "hybrid",
                   "hybrid_posthoc".
            n: Number of participants.

        Returns:
            List of ParticipantRecord with plausible, bounded values.
        """
        if group not in _GROUP_PARAMS:
            raise ValueError(
                f"Unknown group '{group}'. Valid groups: {self.available_groups}"
            )
        p = _GROUP_PARAMS[group]
        self._counter[group] = self._counter.get(group, 0)

        records: list[ParticipantRecord] = []
        for i in range(n):
            idx = self._counter[group] + i + 1
            pid = f"{group[:3].upper()}_{idx:03d}"

            errors = float(np.clip(
                self._rng.normal(p["error_mean"], p["error_std"]),
                0.0, p["error_mean"] + 3 * p["error_std"],
            ))
            time_min = float(np.clip(
                self._rng.normal(p["time_mean"], p["time_std"]),
                max(p["time_mean"] - 3 * p["time_std"], 1.0),
                p["time_mean"] + 3 * p["time_std"],
            ))
            sessions = max(int(round(
                self._rng.normal(p["sessions_mean"], p["sessions_std"])
            )), 1)
            accuracy = float(np.clip(
                self._rng.normal(p["accuracy_mean"], p["accuracy_std"]),
                0.0, 1.0,
            ))

            records.append(ParticipantRecord(
                participant_id=pid,
                group=group,
                errors_per_task=errors,
                completion_time_min=time_min,
                sessions_to_competency=sessions,
                final_accuracy=accuracy,
            ))

        self._counter[group] += n
        return records

    def generate_full_study(
        self,
        n_per_group: int = 64,
    ) -> dict[str, list[ParticipantRecord]]:
        """
        Generate the complete synthetic dataset for all three hypotheses.

        Returns a dict keyed by group name.  n_per_group is applied to each
        group independently.

        Rules.md §3.3: n=64 per group meets the power analysis requirement
        for medium effect (d=0.5) at α=0.05, power=0.80.
        """
        return {
            group: self.generate_group(group, n_per_group)
            for group in _GROUP_PARAMS
        }

    def generate_paired_feedback(self, n: int) -> tuple[list[float], list[float]]:
        """
        Paired completion-time data for H3 (within-subjects design).

        The SAME n participants are measured under both feedback conditions, so
        the two arrays are *correlated*: each participant has a latent speed
        offset applied to both conditions. Real-time feedback is faster than
        post-hoc for the same person. Returns (realtime_times, posthoc_times).
        """
        rt = _GROUP_PARAMS["hybrid"]["time_mean"]            # real-time mean (min)
        ph = _GROUP_PARAMS["hybrid_posthoc"]["time_mean"]    # post-hoc mean (min)
        # Shared per-participant offset (between-subject variance, removed by pairing)
        base = self._rng.normal(0.0, 2.2, n)
        noise_rt = self._rng.normal(0.0, 1.1, n)
        noise_ph = self._rng.normal(0.0, 1.1, n)
        realtime = np.clip(rt + base + noise_rt, 1.0, None)
        posthoc = np.clip(ph + base + noise_ph, 1.0, None)
        return realtime.tolist(), posthoc.tolist()

    def extract_errors(self, records: list[ParticipantRecord]) -> list[float]:
        return [r.errors_per_task for r in records]

    def extract_times(self, records: list[ParticipantRecord]) -> list[float]:
        return [r.completion_time_min for r in records]

    def extract_sessions(self, records: list[ParticipantRecord]) -> list[int]:
        return [r.sessions_to_competency for r in records]
