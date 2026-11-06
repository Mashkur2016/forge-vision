"""
Unit tests for src/intelligence/competency_predictor.py — Enhancement 6 (Task 4.4).

Tests cover:
  - Empty session list
  - Already-competent worker
  - Improving trend → valid session estimate
  - Regressing trend → no estimate, appropriate message
  - Plateau trend
  - Single-session edge case
  - MAX_SESSIONS_ESTIMATE cap
  - Custom threshold / alpha configuration
"""
from __future__ import annotations

import pytest

from src.intelligence.competency_predictor import (
    COMPETENCY_THRESHOLD,
    MAX_SESSIONS_ESTIMATE,
    CompetencyPredictor,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_predictor(**kwargs) -> CompetencyPredictor:
    return CompetencyPredictor(**kwargs)


# ── Empty input ────────────────────────────────────────────────────────────────

def test_empty_returns_unknown():
    p = _make_predictor()
    result = p.predict([])
    assert result["sessions_completed"] == 0
    assert result["smoothed_rate"] is None
    assert result["competency_reached"] is False
    assert result["sessions_to_competency_est"] is None
    assert "No session data" in result["message"]


# ── Already competent ─────────────────────────────────────────────────────────

def test_competent_worker_flag():
    # Rates all well below threshold
    rates = [0.03, 0.02, 0.01]
    p = _make_predictor()
    result = p.predict(rates)
    assert result["competency_reached"] is True
    assert result["sessions_to_competency_est"] is None
    assert "competency" in result["message"].lower()


def test_competent_worker_at_exact_threshold():
    # smoothed ≤ threshold → competent
    p = _make_predictor(competency_threshold=0.10)
    result = p.predict([0.10])
    assert result["competency_reached"] is True


# ── Improving trend ───────────────────────────────────────────────────────────

def test_improving_trend_gives_positive_estimate():
    # Clear downward trend — should predict a finite number of sessions
    rates = [0.50, 0.40, 0.30, 0.20, 0.12]
    p = _make_predictor()
    result = p.predict(rates)
    assert result["trend"] == "improving"
    est = result["sessions_to_competency_est"]
    assert est is not None
    assert est >= 1
    assert est <= MAX_SESSIONS_ESTIMATE


def test_improving_trend_estimate_reasonable():
    # Worker is close to threshold — should not need many more sessions
    rates = [0.30, 0.20, 0.12, 0.09, 0.07]
    p = _make_predictor()
    result = p.predict(rates)
    assert result["sessions_to_competency_est"] is not None
    assert result["sessions_to_competency_est"] <= 10


# ── Regressing trend ──────────────────────────────────────────────────────────

def test_regressing_trend_no_estimate():
    rates = [0.10, 0.15, 0.22]   # getting worse
    p = _make_predictor()
    result = p.predict(rates)
    assert result["trend"] == "regressing"
    assert result["sessions_to_competency_est"] is None
    assert "increasing" in result["message"].lower() or "regress" in result["message"].lower()


# ── Plateau trend ─────────────────────────────────────────────────────────────

def test_plateau_trend():
    rates = [0.20, 0.20, 0.20, 0.21]   # essentially flat
    p = _make_predictor()
    result = p.predict(rates)
    assert result["trend"] == "plateau"


# ── Single session ────────────────────────────────────────────────────────────

def test_single_session_unknown_trend():
    p = _make_predictor()
    result = p.predict([0.30])
    assert result["sessions_completed"] == 1
    assert result["trend"] == "unknown"


# ── MAX_SESSIONS_ESTIMATE cap ─────────────────────────────────────────────────

def test_estimate_capped_at_max():
    # Very high rate, almost no decline → should cap at MAX_SESSIONS_ESTIMATE
    rates = [0.99, 0.98, 0.97]
    p = _make_predictor()
    result = p.predict(rates)
    if result["sessions_to_competency_est"] is not None:
        assert result["sessions_to_competency_est"] <= MAX_SESSIONS_ESTIMATE


def test_estimate_minimum_one():
    # Almost at threshold — still at least 1 session
    rates = [0.06, 0.06, 0.055]
    p = _make_predictor()
    result = p.predict(rates)
    if result["sessions_to_competency_est"] is not None:
        assert result["sessions_to_competency_est"] >= 1


# ── Smoothed rate correctness ─────────────────────────────────────────────────

def test_smoothed_rate_single_session():
    # With a single session the smoothed rate equals the raw rate
    p = _make_predictor()
    result = p.predict([0.25])
    assert result["smoothed_rate"] == pytest.approx(0.25, abs=1e-3)


def test_smoothed_rate_decreases_over_sessions():
    # With alpha=0.4 and improving rates the smoothed value should lie between
    # the first and last raw rates.
    rates = [0.50, 0.40, 0.30, 0.20]
    p = _make_predictor(smoothing_alpha=0.4)
    result = p.predict(rates)
    assert 0.20 <= result["smoothed_rate"] <= 0.50


# ── Custom configuration ──────────────────────────────────────────────────────

def test_custom_threshold_tighter():
    # Tighter threshold: worker that would be "competent" at default is not here
    rates = [0.04, 0.03, 0.02]   # Competent at default 0.05
    p_default = _make_predictor()
    p_tight = _make_predictor(competency_threshold=0.01)

    assert p_default.predict(rates)["competency_reached"] is True
    assert p_tight.predict(rates)["competency_reached"] is False


def test_custom_alpha_high_weight():
    # With alpha=1.0 the smoothed rate equals the last session exactly
    rates = [0.80, 0.60, 0.25]
    p = _make_predictor(smoothing_alpha=1.0)
    result = p.predict(rates)
    assert result["smoothed_rate"] == pytest.approx(0.25, abs=1e-3)


# ── Return type checks ────────────────────────────────────────────────────────

def test_result_keys_present():
    expected_keys = {
        "sessions_completed",
        "smoothed_rate",
        "competency_threshold",
        "competency_reached",
        "sessions_to_competency_est",
        "trend",
        "message",
    }
    result = _make_predictor().predict([0.30, 0.25, 0.20])
    assert expected_keys.issubset(result.keys())


def test_threshold_echoed_in_result():
    p = _make_predictor(competency_threshold=0.07)
    result = p.predict([0.30])
    assert result["competency_threshold"] == pytest.approx(0.07)


def test_sessions_completed_count():
    rates = [0.5, 0.4, 0.3]
    result = _make_predictor().predict(rates)
    assert result["sessions_completed"] == 3
