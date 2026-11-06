"""
Unit tests for src/evaluation/experiment_runner.py — Phase 5, Task 5.3.

Tests cover:
  - ExperimentConfig defaults are valid
  - ExperimentRunner.run() returns a complete ExperimentRecord
  - Record fields are populated correctly
  - Power analysis is included in the record
  - All three hypothesis results present in the record
  - Summary keys are present and values are boolean
  - save=False skips file writing
  - Reproducibility: same seed → same p-values
  - data_type is "SYNTHETIC" (Rules.md §3.1)
"""
from __future__ import annotations

import pytest

from src.evaluation.experiment_runner import ExperimentConfig, ExperimentRecord, ExperimentRunner


# ── Config defaults ────────────────────────────────────────────────────────────

def test_config_defaults():
    cfg = ExperimentConfig()
    assert cfg.alpha == pytest.approx(0.05)
    assert cfg.target_power == pytest.approx(0.80)
    assert cfg.effect_size == pytest.approx(0.5)
    assert cfg.n_per_group == 64
    assert cfg.random_seed == 42
    assert cfg.data_type == "SYNTHETIC"


# ── ExperimentRunner.run() ─────────────────────────────────────────────────────

@pytest.fixture
def record() -> ExperimentRecord:
    cfg = ExperimentConfig(n_per_group=30, random_seed=42)
    runner = ExperimentRunner(config=cfg)
    return runner.run(save=False)


def test_run_returns_experiment_record(record):
    assert isinstance(record, ExperimentRecord)


def test_record_config_populated(record):
    assert "alpha" in record.config
    assert "n_per_group" in record.config
    assert "random_seed" in record.config


def test_record_timestamp_is_string(record):
    assert isinstance(record.timestamp, str)
    assert "T" in record.timestamp   # ISO 8601 format


def test_record_power_analysis_populated(record):
    pa = record.power_analysis
    assert "required_n_per_group" in pa
    assert pa["required_n_per_group"] > 0
    assert "adequately_powered" in pa
    # n=30 is below 64, so should flag as underpowered
    assert pa["adequately_powered"] is False


def test_record_h1_populated(record):
    h1 = record.h1_result
    assert "hypothesis" in h1
    assert "p_value" in h1
    assert "significant" in h1


def test_record_h2_populated(record):
    h2 = record.h2_result
    assert "hypothesis" in h2
    assert "f_statistic" in h2
    assert "tukey_hsd" in h2


def test_record_h3_populated(record):
    h3 = record.h3_result
    assert "hypothesis" in h3
    assert "p_value" in h3
    assert "cohens_d" in h3


def test_record_summary_hypothesis_keys(record):
    s = record.summary
    assert "H1" in s["hypotheses"]
    assert "H2" in s["hypotheses"]
    assert "H3" in s["hypotheses"]


def test_record_summary_supported_are_bool(record):
    for h in ["H1", "H2", "H3"]:
        assert isinstance(record.summary["hypotheses"][h]["supported"], bool)


def test_record_all_hypotheses_supported_is_bool(record):
    assert isinstance(record.summary["all_hypotheses_supported"], bool)


def test_record_data_type_is_synthetic(record):
    assert record.config["data_type"] == "SYNTHETIC"


# ── Reproducibility ────────────────────────────────────────────────────────────

def test_same_seed_same_p_values():
    cfg_a = ExperimentConfig(n_per_group=50, random_seed=99)
    cfg_b = ExperimentConfig(n_per_group=50, random_seed=99)
    r_a = ExperimentRunner(config=cfg_a).run(save=False)
    r_b = ExperimentRunner(config=cfg_b).run(save=False)
    assert r_a.h1_result["p_value"] == pytest.approx(r_b.h1_result["p_value"])
    assert r_a.h2_result["p_value"] == pytest.approx(r_b.h2_result["p_value"])
    assert r_a.h3_result["p_value"] == pytest.approx(r_b.h3_result["p_value"])


def test_different_seed_different_means():
    """Different seeds must produce different group mean errors (not identical data)."""
    from src.evaluation.synthetic_participants import SyntheticParticipantGenerator
    gen_a = SyntheticParticipantGenerator(seed=1)
    gen_b = SyntheticParticipantGenerator(seed=2)
    study_a = gen_a.generate_full_study(n_per_group=50)
    study_b = gen_b.generate_full_study(n_per_group=50)
    mean_a = sum(gen_a.extract_errors(study_a["hybrid"])) / 50
    mean_b = sum(gen_b.extract_errors(study_b["hybrid"])) / 50
    assert mean_a != pytest.approx(mean_b, abs=1e-3)


# ── Large sample → hypotheses supported ───────────────────────────────────────

def test_large_sample_all_hypotheses_supported():
    """
    With n=200 per group (well above the required 64), the synthetic data
    (which has large built-in effect sizes) should support all three hypotheses.
    """
    cfg = ExperimentConfig(n_per_group=200, random_seed=42)
    record = ExperimentRunner(config=cfg).run(save=False)
    s = record.summary
    assert s["hypotheses"]["H1"]["supported"] is True
    assert s["hypotheses"]["H2"]["supported"] is True
    assert s["hypotheses"]["H3"]["supported"] is True
    assert s["all_hypotheses_supported"] is True


# ── File saving ────────────────────────────────────────────────────────────────

def test_save_false_does_not_create_file(tmp_path, monkeypatch):
    """save=False must not write any files."""
    import src.evaluation.experiment_runner as er_mod
    monkeypatch.setattr(er_mod, "EXPERIMENTS_DIR", tmp_path / "experiments")
    cfg = ExperimentConfig(n_per_group=20, random_seed=42)
    ExperimentRunner(config=cfg).run(save=False)
    assert not (tmp_path / "experiments").exists()


def test_save_true_creates_file(tmp_path, monkeypatch):
    """save=True must write a JSON file to EXPERIMENTS_DIR."""
    import src.evaluation.experiment_runner as er_mod
    exp_dir = tmp_path / "experiments"
    monkeypatch.setattr(er_mod, "EXPERIMENTS_DIR", exp_dir)
    cfg = ExperimentConfig(
        experiment_id="test_exp_001",
        n_per_group=20,
        random_seed=42,
    )
    ExperimentRunner(config=cfg).run(save=True)
    files = list(exp_dir.glob("*.json"))
    assert len(files) == 1
    assert "test_exp_001" in files[0].name


def test_saved_file_is_valid_json(tmp_path, monkeypatch):
    import json
    import src.evaluation.experiment_runner as er_mod
    exp_dir = tmp_path / "experiments"
    monkeypatch.setattr(er_mod, "EXPERIMENTS_DIR", exp_dir)
    cfg = ExperimentConfig(experiment_id="json_test", n_per_group=20)
    ExperimentRunner(config=cfg).run(save=True)
    json_file = next(exp_dir.glob("*.json"))
    with open(json_file) as f:
        data = json.load(f)
    assert "summary" in data
    assert "h1_result" in data
