"""
Unit tests for src/evaluation/synthetic_participants.py — Phase 5, Task 5.2.

Tests cover:
  - All group names are valid
  - Generated records have correct structure
  - Values are within plausible ranges
  - Seeded generation is reproducible
  - generate_full_study returns all groups
  - extract_* helpers return correct types
  - Counter increments correctly for sequential calls
"""
from __future__ import annotations

import pytest

from src.evaluation.synthetic_participants import (
    ParticipantRecord,
    SyntheticParticipantGenerator,
    _GROUP_PARAMS,
)


@pytest.fixture
def gen() -> SyntheticParticipantGenerator:
    return SyntheticParticipantGenerator(seed=42)


# ── Available groups ───────────────────────────────────────────────────────────

def test_all_expected_groups_available(gen):
    expected = {"control", "sim_only", "realtime_only", "hybrid", "hybrid_posthoc"}
    assert expected.issubset(set(gen.available_groups))


def test_invalid_group_raises(gen):
    with pytest.raises(ValueError, match="Unknown group"):
        gen.generate_group("nonexistent_group", n=10)


# ── ParticipantRecord ─────────────────────────────────────────────────────────

def test_record_to_dict_keys():
    r = ParticipantRecord(
        participant_id="HYB_001",
        group="hybrid",
        errors_per_task=1.5,
        completion_time_min=8.3,
        sessions_to_competency=4,
        final_accuracy=0.91,
    )
    d = r.to_dict()
    expected = {
        "participant_id", "group", "errors_per_task",
        "completion_time_min", "sessions_to_competency", "final_accuracy",
    }
    assert expected == set(d.keys())


def test_record_to_dict_rounds():
    r = ParticipantRecord(
        participant_id="X",
        group="control",
        errors_per_task=1.23456789,
        completion_time_min=10.999,
        sessions_to_competency=5,
        final_accuracy=0.888888,
    )
    d = r.to_dict()
    assert d["errors_per_task"] == pytest.approx(1.235, abs=1e-2)
    assert d["final_accuracy"] == pytest.approx(0.889, abs=1e-2)


# ── generate_group ─────────────────────────────────────────────────────────────

def test_generate_group_returns_correct_count(gen):
    records = gen.generate_group("control", n=20)
    assert len(records) == 20


def test_generate_group_correct_group_label(gen):
    records = gen.generate_group("hybrid", n=5)
    assert all(r.group == "hybrid" for r in records)


def test_generate_group_unique_ids(gen):
    records = gen.generate_group("control", n=50)
    ids = [r.participant_id for r in records]
    assert len(set(ids)) == 50


def test_generate_group_errors_non_negative(gen):
    records = gen.generate_group("control", n=100)
    assert all(r.errors_per_task >= 0.0 for r in records)


def test_generate_group_times_positive(gen):
    records = gen.generate_group("hybrid", n=100)
    assert all(r.completion_time_min >= 0.5 for r in records)


def test_generate_group_accuracy_in_range(gen):
    for group in gen.available_groups:
        records = gen.generate_group(group, n=50)
        for r in records:
            assert 0.0 <= r.final_accuracy <= 1.0, (
                f"final_accuracy={r.final_accuracy} out of range for group={group}"
            )


def test_generate_group_sessions_at_least_one(gen):
    records = gen.generate_group("control", n=50)
    assert all(r.sessions_to_competency >= 1 for r in records)


# ── Reproducibility ────────────────────────────────────────────────────────────

def test_same_seed_same_results():
    gen_a = SyntheticParticipantGenerator(seed=99)
    gen_b = SyntheticParticipantGenerator(seed=99)
    a = gen_a.generate_group("hybrid", n=20)
    b = gen_b.generate_group("hybrid", n=20)
    assert [r.errors_per_task for r in a] == [r.errors_per_task for r in b]


def test_different_seed_different_results():
    gen_a = SyntheticParticipantGenerator(seed=1)
    gen_b = SyntheticParticipantGenerator(seed=2)
    a = gen_a.generate_group("hybrid", n=20)
    b = gen_b.generate_group("hybrid", n=20)
    errors_a = [r.errors_per_task for r in a]
    errors_b = [r.errors_per_task for r in b]
    assert errors_a != errors_b


# ── Plausible means ────────────────────────────────────────────────────────────

def test_hybrid_has_lower_errors_than_control_on_average():
    """Hybrid group mean errors should be substantially lower than control."""
    gen = SyntheticParticipantGenerator(seed=42)
    control = gen.generate_group("control", n=200)
    hybrid = gen.generate_group("hybrid", n=200)
    mean_ctrl = sum(r.errors_per_task for r in control) / 200
    mean_hyb = sum(r.errors_per_task for r in hybrid) / 200
    assert mean_hyb < mean_ctrl


def test_realtime_faster_than_posthoc_on_average():
    gen = SyntheticParticipantGenerator(seed=42)
    posthoc = gen.generate_group("hybrid_posthoc", n=200)
    realtime = gen.generate_group("hybrid", n=200)
    mean_posthoc = sum(r.completion_time_min for r in posthoc) / 200
    mean_rt = sum(r.completion_time_min for r in realtime) / 200
    assert mean_rt < mean_posthoc


# ── generate_full_study ────────────────────────────────────────────────────────

def test_full_study_contains_all_groups(gen):
    study = gen.generate_full_study(n_per_group=10)
    expected = {"control", "sim_only", "realtime_only", "hybrid", "hybrid_posthoc"}
    assert expected.issubset(set(study.keys()))


def test_full_study_correct_count_per_group(gen):
    study = gen.generate_full_study(n_per_group=15)
    for group, records in study.items():
        assert len(records) == 15, f"Expected 15 records for {group}, got {len(records)}"


# ── extract_* helpers ─────────────────────────────────────────────────────────

def test_extract_errors_returns_floats(gen):
    records = gen.generate_group("control", n=10)
    errors = gen.extract_errors(records)
    assert len(errors) == 10
    assert all(isinstance(e, float) for e in errors)


def test_extract_times_returns_floats(gen):
    records = gen.generate_group("hybrid", n=10)
    times = gen.extract_times(records)
    assert len(times) == 10
    assert all(isinstance(t, float) for t in times)


def test_extract_sessions_returns_ints(gen):
    records = gen.generate_group("control", n=10)
    sessions = gen.extract_sessions(records)
    assert len(sessions) == 10
    assert all(isinstance(s, int) for s in sessions)


# ── Counter increments ────────────────────────────────────────────────────────

def test_sequential_calls_produce_unique_ids(gen):
    first = gen.generate_group("control", n=5)
    second = gen.generate_group("control", n=5)
    all_ids = [r.participant_id for r in first + second]
    assert len(set(all_ids)) == 10   # No duplicates


# ── Group params coverage ─────────────────────────────────────────────────────

@pytest.mark.parametrize("group", list(_GROUP_PARAMS.keys()))
def test_each_group_generates_without_error(group):
    gen = SyntheticParticipantGenerator(seed=0)
    records = gen.generate_group(group, n=5)
    assert len(records) == 5
