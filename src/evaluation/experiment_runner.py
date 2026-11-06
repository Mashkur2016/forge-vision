"""
Experiment Runner — Phase 5 (Task 5.3).

Orchestrates a complete evaluation run:
  1. Power analysis — confirms required sample size for α=0.05, power=0.80
  2. Generates synthetic participant dataset (seed-fixed, reproducible)
  3. Tests H1, H2, H3 using HypothesisTester
  4. Saves the experiment record to experiments/ directory

Rules.md §1.5: Fixed random seed; results reproducible.
Rules.md §3.1: Synthetic data explicitly flagged in outputs.
Rules.md §3.4: Experiment record saved to experiments/ with full config.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.evaluation.hypothesis_tester import HypothesisTester, PowerAnalysisResult
from src.evaluation.synthetic_participants import SyntheticParticipantGenerator

log = logging.getLogger(__name__)

EXPERIMENTS_DIR = Path("experiments")


# ── Experiment configuration ──────────────────────────────────────────────────

@dataclass
class ExperimentConfig:
    """
    Configuration for one evaluation run.

    All defaults match Rules.md §3.2 requirements.
    """
    experiment_id: str = ""
    description: str = "Phase 5 DBA Evaluation — Hypothesis Testing"
    alpha: float = 0.05
    target_power: float = 0.80
    effect_size: float = 0.5          # Medium effect (Cohen's d / η²)
    n_per_group: int = 64             # From power analysis at medium effect
    random_seed: int = 42
    data_type: str = "SYNTHETIC"      # Must remain "SYNTHETIC" until real data collected


@dataclass
class ExperimentRecord:
    """Full experiment record saved to disk."""
    config: dict
    timestamp: str
    power_analysis: dict
    h1_result: dict
    h2_result: dict
    h3_result: dict
    summary: dict


# ── Runner ────────────────────────────────────────────────────────────────────

class ExperimentRunner:
    """
    End-to-end evaluation pipeline for all three DBA hypotheses.

    Usage:
        runner = ExperimentRunner()
        record = runner.run()
        print(record.summary)
    """

    def __init__(self, config: ExperimentConfig | None = None) -> None:
        self.config = config or ExperimentConfig()
        self._tester = HypothesisTester(alpha=self.config.alpha)
        self._gen = SyntheticParticipantGenerator(seed=self.config.random_seed)

    def run(self, save: bool = True) -> ExperimentRecord:
        """
        Run the full evaluation:
          1. Power analysis
          2. Data generation
          3. Hypothesis tests
          4. Save record

        Args:
            save: If True, write JSON record to experiments/.

        Returns:
            ExperimentRecord with all results.
        """
        cfg = self.config
        timestamp = datetime.now(timezone.utc).isoformat()

        log.info("ExperimentRunner: starting evaluation (seed=%d, n=%d)", cfg.random_seed, cfg.n_per_group)

        # ── 1. Power analysis ──────────────────────────────────────────────
        power = self._tester.power_analysis(
            effect_size=cfg.effect_size,
            alpha=cfg.alpha,
            power=cfg.target_power,
        )
        log.info("Power analysis: n_per_group=%d required (target n=%d)", power.n_per_group, cfg.n_per_group)

        # ── 2. Generate synthetic data ─────────────────────────────────────
        study = self._gen.generate_full_study(n_per_group=cfg.n_per_group)

        # ── 3. Test H1 ─────────────────────────────────────────────────────
        h1 = self._tester.test_h1(
            control_errors=self._gen.extract_errors(study["control"]),
            treatment_errors=self._gen.extract_errors(study["hybrid"]),
        )
        log.info("H1: p=%.4f significant=%s", h1.p_value, h1.significant)

        # ── 4. Test H2 ─────────────────────────────────────────────────────
        h2 = self._tester.test_h2(
            sim_only_errors=self._gen.extract_errors(study["sim_only"]),
            realtime_only_errors=self._gen.extract_errors(study["realtime_only"]),
            hybrid_errors=self._gen.extract_errors(study["hybrid"]),
        )
        log.info("H2: p=%.4f significant=%s", h2.p_value, h2.significant)

        # ── 5. Test H3 (within-subjects: paired completion times) ──────────
        rt_times, ph_times = self._gen.generate_paired_feedback(cfg.n_per_group)
        h3 = self._tester.test_h3(posthoc_times=ph_times, realtime_times=rt_times)
        log.info("H3: p=%.4f significant=%s (paired)", h3.p_value, h3.significant)

        # ── 6. Build summary ───────────────────────────────────────────────
        summary = {
            "data_type": cfg.data_type,
            "n_per_group": cfg.n_per_group,
            "hypotheses": {
                "H1": {
                    "supported": h1.significant,
                    "p_value": round(h1.p_value, 4),
                    "cohens_d": round(h1.cohens_d, 3),
                    "effect": h1.effect_magnitude,
                },
                "H2": {
                    "supported": h2.significant,
                    "p_value": round(h2.p_value, 4),
                    "eta_squared": round(h2.eta_squared, 3),
                    "effect": h2.effect_magnitude,
                },
                "H3": {
                    "supported": h3.significant,
                    "p_value": round(h3.p_value, 4),
                    "cohens_d": round(h3.cohens_d, 3),
                    "effect": h3.effect_magnitude,
                },
            },
            "all_hypotheses_supported": all([
                h1.significant, h2.significant, h3.significant
            ]),
        }

        record = ExperimentRecord(
            config={
                "experiment_id": cfg.experiment_id or f"exp_{timestamp[:10]}",
                "description": cfg.description,
                "alpha": cfg.alpha,
                "target_power": cfg.target_power,
                "effect_size": cfg.effect_size,
                "n_per_group": cfg.n_per_group,
                "random_seed": cfg.random_seed,
                "data_type": cfg.data_type,
            },
            timestamp=timestamp,
            power_analysis={
                "required_n_per_group": power.n_per_group,
                "total_n": power.total_n,
                "target_power": power.power,
                "effect_size": power.effect_size,
                "alpha": power.alpha,
                "actual_n_per_group": cfg.n_per_group,
                "adequately_powered": cfg.n_per_group >= power.n_per_group,
            },
            h1_result=h1.to_dict(),
            h2_result=h2.to_dict(),
            h3_result=h3.to_dict(),
            summary=summary,
        )

        if save:
            self._save(record)

        return record

    def print_report(self, record: ExperimentRecord) -> None:
        """Print a human-readable evaluation report to stdout (from stored dicts)."""
        sep = "=" * 72
        print(sep)
        print("FORGE-Vision — Phase 5 Evaluation Report")
        print(f"Timestamp : {record.timestamp}")
        print(f"Data type : {record.config['data_type']}  ← All results are SYNTHETIC")
        print(f"N/group   : {record.config['n_per_group']}  (required: {record.power_analysis['required_n_per_group']})")
        print(sep)

        for h_key, label in [("H1", "H1 — Error Rate Reduction"),
                              ("H2", "H2 — Hybrid Approach Skill Transfer"),
                              ("H3", "H3 — Real-Time Feedback Completion Time")]:
            r = record.summary["hypotheses"][h_key]
            verdict = "SUPPORTED ✓" if r["supported"] else "NOT SUPPORTED ✗"
            print(f"\n{label}")
            print(f"  p = {r['p_value']:.4f}  |  effect = {r['effect']}  |  {verdict}")

        print(f"\n{'─'*72}")
        all_ok = record.summary["all_hypotheses_supported"]
        print(f"All hypotheses supported: {'YES ✓' if all_ok else 'NO — review data'}")
        print(sep)

    # ── Private ───────────────────────────────────────────────────────────────

    def _save(self, record: ExperimentRecord) -> Path:
        """Write the experiment record as a JSON file to experiments/."""
        EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
        exp_id = record.config.get("experiment_id", "exp_unknown")
        # Sanitise for filename
        safe_id = exp_id.replace(":", "-").replace(" ", "_")
        path = EXPERIMENTS_DIR / f"{safe_id}.json"

        payload = {
            "config": record.config,
            "timestamp": record.timestamp,
            "power_analysis": record.power_analysis,
            "h1_result": record.h1_result,
            "h2_result": record.h2_result,
            "h3_result": record.h3_result,
            "summary": record.summary,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        log.info("Experiment record saved: %s", path)
        return path
