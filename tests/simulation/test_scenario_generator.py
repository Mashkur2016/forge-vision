"""
Tests for src/simulation/scenario_generator.py
"""
from __future__ import annotations

import numpy as np
import pytest

from src.simulation.scenario_generator import (
    FRAME_HEIGHT,
    FRAME_WIDTH,
    FPS,
    ClipLabel,
    ScenarioGenerator,
    ScenarioType,
)
from src.simulation.sop_schema import SOP, SOPStep


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def generator() -> ScenarioGenerator:
    return ScenarioGenerator(seed=42)


@pytest.fixture
def simple_sop() -> SOP:
    """3-step SOP with one safety-critical step and PPE requirements."""
    return SOP(
        id="simple_test_v1",
        name="Simple Test Procedure",
        required_ppe=["safety_glasses"],
        steps=[
            SOPStep(
                id=1, name="power_off", description="Turn off power",
                safety_critical=True, required_ppe=["insulated_gloves"],
                required_objects=["power_switch"],
            ),
            SOPStep(
                id=2, name="connect_wire", description="Connect wire",
                required_objects=["red_wire", "terminal_a"],
                must_follow=[1],
            ),
            SOPStep(
                id=3, name="restore_power", description="Restore power",
                safety_critical=True, required_objects=["power_switch"],
                must_follow=[2],
            ),
        ],
    )


# ── ScenarioType enum ──────────────────────────────────────────────────────

class TestScenarioType:
    def test_all_five_types_exist(self):
        types = {s.value for s in ScenarioType}
        assert types == {"correct", "missing_step", "wrong_order", "unsafe", "rare_failure"}


# ── ClipLabel ──────────────────────────────────────────────────────────────

class TestClipLabel:
    def test_duration_calculation(self):
        label = ClipLabel(
            clip_id="abc123",
            sop_id="test",
            sop_name="Test SOP",
            scenario_type=ScenarioType.CORRECT,
            executed_steps=[1, 2, 3],
            error_step_id=None,
            error_type=None,
            frame_count=90,
            fps=30,
        )
        assert label.duration_seconds == 3.0

    def test_to_dict_contains_required_keys(self):
        label = ClipLabel(
            clip_id="abc123",
            sop_id="test",
            sop_name="Test SOP",
            scenario_type=ScenarioType.MISSING_STEP,
            executed_steps=[1, 3],
            error_step_id=2,
            error_type="MISSING_STEP",
            frame_count=60,
        )
        d = label.to_dict()
        for key in ("clip_id", "sop_id", "scenario_type", "executed_steps",
                    "error_step_id", "error_type", "frame_count", "fps",
                    "duration_seconds", "seed"):
            assert key in d, f"Missing key: {key}"


# ── ScenarioGenerator ──────────────────────────────────────────────────────

class TestScenarioGeneratorCorrect:
    def test_returns_frames_and_label(self, generator, simple_sop):
        frames, label = generator.generate_clip(simple_sop, ScenarioType.CORRECT)
        assert isinstance(frames, list)
        assert isinstance(label, ClipLabel)

    def test_frame_dimensions(self, generator, simple_sop):
        frames, _ = generator.generate_clip(simple_sop, ScenarioType.CORRECT)
        for frame in frames:
            assert frame.shape == (FRAME_HEIGHT, FRAME_WIDTH, 3)
            assert frame.dtype == np.uint8

    def test_correct_executes_all_steps(self, generator, simple_sop):
        _, label = generator.generate_clip(simple_sop, ScenarioType.CORRECT)
        assert sorted(label.executed_steps) == [1, 2, 3]
        assert label.error_step_id is None
        assert label.error_type is None

    def test_frame_count_positive(self, generator, simple_sop):
        frames, label = generator.generate_clip(simple_sop, ScenarioType.CORRECT)
        assert len(frames) > 0
        assert label.frame_count == len(frames)

    def test_label_sop_id_matches(self, generator, simple_sop):
        _, label = generator.generate_clip(simple_sop, ScenarioType.CORRECT)
        assert label.sop_id == simple_sop.id
        assert label.sop_name == simple_sop.name

    def test_label_scenario_type_correct(self, generator, simple_sop):
        _, label = generator.generate_clip(simple_sop, ScenarioType.CORRECT)
        assert label.scenario_type == ScenarioType.CORRECT


class TestScenarioGeneratorMissingStep:
    def test_executed_steps_shorter_than_sop(self, generator, simple_sop):
        _, label = generator.generate_clip(simple_sop, ScenarioType.MISSING_STEP)
        assert len(label.executed_steps) < simple_sop.step_count

    def test_error_step_recorded(self, generator, simple_sop):
        _, label = generator.generate_clip(simple_sop, ScenarioType.MISSING_STEP)
        assert label.error_step_id is not None
        assert label.error_type == "MISSING_STEP"

    def test_skipped_step_not_in_executed(self, generator, simple_sop):
        _, label = generator.generate_clip(simple_sop, ScenarioType.MISSING_STEP)
        assert label.error_step_id not in label.executed_steps


class TestScenarioGeneratorWrongOrder:
    def test_all_steps_still_executed(self, generator, simple_sop):
        _, label = generator.generate_clip(simple_sop, ScenarioType.WRONG_ORDER)
        assert len(label.executed_steps) == simple_sop.step_count

    def test_error_step_id_set(self, generator, simple_sop):
        _, label = generator.generate_clip(simple_sop, ScenarioType.WRONG_ORDER)
        assert label.error_step_id is not None
        assert label.error_type == "WRONG_ORDER"

    def test_executed_steps_is_permutation(self, generator, simple_sop):
        _, label = generator.generate_clip(simple_sop, ScenarioType.WRONG_ORDER)
        assert sorted(label.executed_steps) == [1, 2, 3]


class TestScenarioGeneratorUnsafe:
    def test_all_steps_executed(self, generator, simple_sop):
        _, label = generator.generate_clip(simple_sop, ScenarioType.UNSAFE)
        assert len(label.executed_steps) == simple_sop.step_count

    def test_error_type_is_missing_ppe(self, generator, simple_sop):
        _, label = generator.generate_clip(simple_sop, ScenarioType.UNSAFE)
        assert label.error_type == "MISSING_PPE"

    def test_error_step_is_one_of_sop_steps(self, generator, simple_sop):
        _, label = generator.generate_clip(simple_sop, ScenarioType.UNSAFE)
        assert label.error_step_id in {s.id for s in simple_sop.steps}


class TestScenarioGeneratorRareFailure:
    def test_fewer_steps_executed(self, generator, simple_sop):
        _, label = generator.generate_clip(simple_sop, ScenarioType.RARE_FAILURE)
        assert len(label.executed_steps) < simple_sop.step_count

    def test_error_step_is_safety_critical(self, generator, simple_sop):
        _, label = generator.generate_clip(simple_sop, ScenarioType.RARE_FAILURE)
        critical_ids = {s.id for s in simple_sop.get_safety_critical_steps()}
        if critical_ids:
            assert label.error_step_id in critical_ids

    def test_error_type_set(self, generator, simple_sop):
        _, label = generator.generate_clip(simple_sop, ScenarioType.RARE_FAILURE)
        assert label.error_type is not None


# ── Determinism ────────────────────────────────────────────────────────────

class TestDeterminism:
    def test_same_seed_same_frame_count(self, simple_sop):
        gen1 = ScenarioGenerator(seed=99)
        gen2 = ScenarioGenerator(seed=99)
        frames1, label1 = gen1.generate_clip(simple_sop, ScenarioType.MISSING_STEP)
        frames2, label2 = gen2.generate_clip(simple_sop, ScenarioType.MISSING_STEP)
        assert len(frames1) == len(frames2)
        assert label1.error_step_id == label2.error_step_id

    def test_same_seed_same_first_frame(self, simple_sop):
        gen1 = ScenarioGenerator(seed=7)
        gen2 = ScenarioGenerator(seed=7)
        frames1, _ = gen1.generate_clip(simple_sop, ScenarioType.CORRECT)
        frames2, _ = gen2.generate_clip(simple_sop, ScenarioType.CORRECT)
        np.testing.assert_array_equal(frames1[0], frames2[0])


# ── All scenario types with all SOPs ──────────────────────────────────────

class TestAllScenarios:
    @pytest.mark.parametrize("scenario", list(ScenarioType))
    def test_all_scenarios_produce_frames(self, generator, simple_sop, scenario):
        frames, label = generator.generate_clip(simple_sop, scenario)
        assert len(frames) > 0
        assert label.scenario_type == scenario

    def test_fire_evacuation_sop_all_scenarios(self, fire_evacuation_sop):
        gen = ScenarioGenerator(seed=42)
        for scenario in ScenarioType:
            frames, label = gen.generate_clip(fire_evacuation_sop, scenario)
            assert len(frames) > 0, f"No frames for {scenario} on fire_evacuation_sop"

    def test_lab_safety_sop_all_scenarios(self, lab_safety_sop):
        gen = ScenarioGenerator(seed=42)
        for scenario in ScenarioType:
            frames, label = gen.generate_clip(lab_safety_sop, scenario)
            assert len(frames) > 0, f"No frames for {scenario} on lab_safety_sop"
