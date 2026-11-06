"""
Unit tests for src/evaluation/hypothesis_tester.py — Phase 5, Task 5.1.

Tests cover:
  - TTestResult construction and summary/to_dict
  - AnovaResult construction and summary/to_dict
  - Power analysis outputs
  - H1: significantly different groups → supported; same groups → not supported
  - H2: three groups with clear differences → supported; identical groups → not supported
  - H3: same as H1 but on time data
  - Cohen's d sign and magnitude conventions
  - η² conventions
  - Tukey HSD produces all pairwise comparisons
  - Edge cases: n=2, equal means, zero variance
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from src.evaluation.hypothesis_tester import (
    ALPHA,
    HypothesisTester,
    PowerAnalysisResult,
    TTestResult,
    AnovaResult,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def tester() -> HypothesisTester:
    return HypothesisTester(alpha=0.05)


def _make_clearly_different(rng_seed: int = 0) -> tuple[list[float], list[float]]:
    """Two groups with a large, significant difference (d ≈ 1.5)."""
    rng = np.random.default_rng(rng_seed)
    control = list(rng.normal(6.0, 1.0, 80))
    treatment = list(rng.normal(2.0, 1.0, 80))
    return control, treatment


def _make_same_distribution(rng_seed: int = 0) -> tuple[list[float], list[float]]:
    rng = np.random.default_rng(rng_seed)
    a = list(rng.normal(5.0, 1.0, 80))
    b = list(rng.normal(5.0, 1.0, 80))
    return a, b


# ── Power analysis ─────────────────────────────────────────────────────────────

def test_power_analysis_returns_positive_n(tester):
    result = tester.power_analysis(effect_size=0.5, power=0.80)
    assert isinstance(result, PowerAnalysisResult)
    assert result.n_per_group > 0
    assert result.total_n == result.n_per_group * 2


def test_power_analysis_medium_effect_is_approx_64(tester):
    # Standard result for d=0.5, α=0.05, power=0.80 is ~64 per group.
    # Allow 45–80: one-tailed vs two-tailed and iterative refinement
    # differences mean implementations may land anywhere in this range.
    result = tester.power_analysis(effect_size=0.5, alpha=0.05, power=0.80)
    assert 45 <= result.n_per_group <= 80


def test_power_analysis_larger_effect_needs_fewer_participants(tester):
    n_medium = tester.power_analysis(effect_size=0.5).n_per_group
    n_large = tester.power_analysis(effect_size=0.8).n_per_group
    assert n_large < n_medium


def test_power_analysis_stores_inputs(tester):
    result = tester.power_analysis(effect_size=0.6, alpha=0.05, power=0.80)
    assert result.effect_size == pytest.approx(0.6)
    assert result.alpha == pytest.approx(0.05)
    assert result.power == pytest.approx(0.80)


# ── H1: Error rate reduction ───────────────────────────────────────────────────

def test_h1_supported_when_treatment_better(tester):
    control, treatment = _make_clearly_different()
    result = tester.test_h1(control, treatment)
    assert isinstance(result, TTestResult)
    assert result.significant is True
    assert result.mean_b < result.mean_a   # treatment < control


def test_h1_not_supported_same_distribution(tester):
    a, b = _make_same_distribution()
    result = tester.test_h1(a, b)
    assert result.significant is False


def test_h1_result_has_correct_labels(tester):
    control, treatment = _make_clearly_different()
    result = tester.test_h1(control, treatment,
                            label_control="Control", label_treatment="Treatment")
    assert result.group_a_label == "Control"
    assert result.group_b_label == "Treatment"


def test_h1_result_counts_match_input(tester):
    c, t = _make_clearly_different()
    result = tester.test_h1(c[:50], t[:30])
    assert result.n_a == 50
    assert result.n_b == 30


def test_h1_p_value_in_range(tester):
    c, t = _make_clearly_different()
    result = tester.test_h1(c, t)
    assert 0.0 <= result.p_value <= 1.0


def test_h1_cohens_d_sign(tester):
    # Treatment much lower than control → d should be negative (b - a direction)
    c, t = _make_clearly_different()
    result = tester.test_h1(c, t)
    assert result.cohens_d < 0.0   # mean_b - mean_a < 0


def test_h1_to_dict_keys(tester):
    c, t = _make_clearly_different()
    result = tester.test_h1(c, t)
    d = result.to_dict()
    required = {
        "hypothesis", "group_a", "group_b", "t_statistic",
        "degrees_of_freedom", "p_value", "cohens_d",
        "effect_magnitude", "significant", "alpha",
    }
    assert required.issubset(d.keys())


def test_h1_summary_is_string(tester):
    c, t = _make_clearly_different()
    result = tester.test_h1(c, t)
    summary = result.summary()
    assert isinstance(summary, str)
    assert "H1" in summary


# ── H2: Hybrid approach ────────────────────────────────────────────────────────

def test_h2_supported_when_groups_differ(tester):
    rng = np.random.default_rng(1)
    sim = list(rng.normal(4.0, 1.0, 80))
    rt = list(rng.normal(3.0, 1.0, 80))
    hybrid = list(rng.normal(2.0, 1.0, 80))
    result = tester.test_h2(sim, rt, hybrid)
    assert isinstance(result, AnovaResult)
    assert result.significant is True


def test_h2_not_supported_identical_groups(tester):
    rng = np.random.default_rng(2)
    data = list(rng.normal(5.0, 1.0, 80))
    result = tester.test_h2(data[:], data[:], data[:])
    assert result.significant is False


def test_h2_result_three_groups(tester):
    rng = np.random.default_rng(3)
    s = list(rng.normal(4.0, 1.0, 50))
    r = list(rng.normal(3.0, 1.0, 50))
    h = list(rng.normal(2.0, 1.0, 50))
    result = tester.test_h2(s, r, h)
    assert len(result.group_labels) == 3
    assert len(result.group_means) == 3
    assert len(result.group_ns) == 3


def test_h2_tukey_has_three_pairs(tester):
    rng = np.random.default_rng(4)
    s = list(rng.normal(4.0, 1.0, 50))
    r = list(rng.normal(3.0, 1.0, 50))
    h = list(rng.normal(2.0, 1.0, 50))
    result = tester.test_h2(s, r, h)
    # 3 groups → 3 pairwise comparisons: (0,1), (0,2), (1,2)
    assert len(result.tukey_results) == 3


def test_h2_tukey_pairs_cover_all_combinations(tester):
    rng = np.random.default_rng(5)
    s = list(rng.normal(4.0, 1.0, 50))
    r = list(rng.normal(3.0, 1.0, 50))
    h = list(rng.normal(2.0, 1.0, 50))
    result = tester.test_h2(s, r, h,
                            label_sim="A", label_realtime="B", label_hybrid="C")
    pairs = {(t["group_a"], t["group_b"]) for t in result.tukey_results}
    assert ("A", "B") in pairs
    assert ("A", "C") in pairs
    assert ("B", "C") in pairs


def test_h2_eta_squared_in_range(tester):
    rng = np.random.default_rng(6)
    s = list(rng.normal(4.0, 1.0, 50))
    r = list(rng.normal(3.0, 1.0, 50))
    h = list(rng.normal(2.0, 1.0, 50))
    result = tester.test_h2(s, r, h)
    assert 0.0 <= result.eta_squared <= 1.0


def test_h2_to_dict_keys(tester):
    rng = np.random.default_rng(7)
    s = list(rng.normal(4.0, 1.0, 30))
    r = list(rng.normal(3.0, 1.0, 30))
    h = list(rng.normal(2.0, 1.0, 30))
    result = tester.test_h2(s, r, h)
    d = result.to_dict()
    assert {"hypothesis", "groups", "f_statistic", "p_value",
            "eta_squared", "significant", "tukey_hsd"}.issubset(d.keys())


# ── H3: Completion time ────────────────────────────────────────────────────────

def test_h3_supported_when_realtime_faster(tester):
    rng = np.random.default_rng(8)
    posthoc = list(rng.normal(13.0, 2.0, 80))
    realtime = list(rng.normal(9.0, 2.0, 80))
    result = tester.test_h3(posthoc, realtime)
    assert result.significant is True
    assert result.mean_b < result.mean_a


def test_h3_not_supported_same_times(tester):
    rng = np.random.default_rng(9)
    times = list(rng.normal(12.0, 2.0, 80))
    result = tester.test_h3(times[:], times[:])
    assert result.significant is False


# ── Effect magnitude conventions ──────────────────────────────────────────────

def test_effect_magnitude_d_negligible():
    d = HypothesisTester._effect_magnitude_d(0.1)
    assert d == "negligible"


def test_effect_magnitude_d_small():
    d = HypothesisTester._effect_magnitude_d(0.3)
    assert d == "small"


def test_effect_magnitude_d_medium():
    d = HypothesisTester._effect_magnitude_d(0.6)
    assert d == "medium"


def test_effect_magnitude_d_large():
    d = HypothesisTester._effect_magnitude_d(1.2)
    assert d == "large"


def test_effect_magnitude_eta_negligible():
    assert HypothesisTester._effect_magnitude_eta(0.005) == "negligible"


def test_effect_magnitude_eta_small():
    assert HypothesisTester._effect_magnitude_eta(0.03) == "small"


def test_effect_magnitude_eta_medium():
    assert HypothesisTester._effect_magnitude_eta(0.09) == "medium"


def test_effect_magnitude_eta_large():
    assert HypothesisTester._effect_magnitude_eta(0.20) == "large"


# ── Cohen's d helper ──────────────────────────────────────────────────────────

def test_cohens_d_zero_for_equal_means():
    a = np.array([5.0, 5.0, 5.0, 5.0])
    b = np.array([5.0, 5.0, 5.0, 5.0])
    d = HypothesisTester._cohens_d(a, b)
    assert d == pytest.approx(0.0)


def test_cohens_d_positive_when_b_greater():
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([4.0, 5.0, 6.0])
    d = HypothesisTester._cohens_d(a, b)
    assert d > 0.0


def test_cohens_d_negative_when_b_less():
    a = np.array([4.0, 5.0, 6.0])
    b = np.array([1.0, 2.0, 3.0])
    d = HypothesisTester._cohens_d(a, b)
    assert d < 0.0


def test_cohens_d_zero_pooled_variance():
    # All values identical → s_pooled = 0 → d = 0 (no division error)
    a = np.array([3.0, 3.0, 3.0])
    b = np.array([5.0, 5.0, 5.0])
    d = HypothesisTester._cohens_d(a, b)
    assert d == pytest.approx(0.0)


# ── Degrees of freedom ────────────────────────────────────────────────────────

def test_welch_df_greater_than_zero(tester):
    rng = np.random.default_rng(10)
    a = list(rng.normal(5.0, 1.0, 30))
    b = list(rng.normal(3.0, 1.5, 30))
    result = tester.test_h1(a, b)
    assert result.degrees_of_freedom > 0.0


# ── Alpha stored on result ────────────────────────────────────────────────────

def test_alpha_echoed_in_t_result(tester):
    rng = np.random.default_rng(11)
    a = list(rng.normal(5.0, 1.0, 30))
    b = list(rng.normal(3.0, 1.0, 30))
    result = tester.test_h1(a, b)
    assert result.alpha == pytest.approx(0.05)


def test_custom_alpha(tester):
    tester_strict = HypothesisTester(alpha=0.01)
    rng = np.random.default_rng(12)
    a = list(rng.normal(5.0, 1.0, 30))
    b = list(rng.normal(4.5, 1.0, 30))
    result = tester_strict.test_h1(a, b)
    assert result.alpha == pytest.approx(0.01)
