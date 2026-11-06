"""
Tests for src/simulation/sop_schema.py and src/simulation/sop_parser.py
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
import yaml

from src.simulation.sop_schema import SOP, SOPStep
from src.simulation.sop_parser import (
    load_all_sops,
    load_sop,
    sop_to_dict,
    sop_to_json,
    sop_to_yaml,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SOPS_DIR = PROJECT_ROOT / "data" / "sops"


# ── SOPStep validation ─────────────────────────────────────────────────────

class TestSOPStep:
    def test_valid_minimal_step(self):
        step = SOPStep(id=1, name="power_off", description="Turn off power")
        assert step.id == 1
        assert step.name == "power_off"
        assert step.safety_critical is False
        assert step.required_objects == []
        assert step.must_follow == []

    def test_step_with_all_fields(self):
        step = SOPStep(
            id=2,
            name="connect_wire",
            description="Connect red wire",
            required_objects=["red_wire", "terminal_a"],
            required_pose="both_hands_terminal_area",
            time_limit_seconds=120,
            must_follow=[1],
            safety_critical=False,
            required_ppe=["insulated_gloves"],
        )
        assert step.required_objects == ["red_wire", "terminal_a"]
        assert step.must_follow == [1]

    def test_step_id_must_be_positive(self):
        with pytest.raises(Exception):
            SOPStep(id=0, name="x", description="y")

    def test_must_follow_cannot_reference_same_step(self):
        with pytest.raises(ValueError, match="must_follow"):
            SOPStep(id=2, name="x", description="y", must_follow=[2])

    def test_must_follow_cannot_reference_later_step(self):
        with pytest.raises(ValueError, match="must_follow"):
            SOPStep(id=2, name="x", description="y", must_follow=[3])

    def test_must_follow_can_reference_earlier_step(self):
        step = SOPStep(id=3, name="x", description="y", must_follow=[1, 2])
        assert step.must_follow == [1, 2]

    def test_time_limit_bounds(self):
        with pytest.raises(Exception):
            SOPStep(id=1, name="x", description="y", time_limit_seconds=0)
        with pytest.raises(Exception):
            SOPStep(id=1, name="x", description="y", time_limit_seconds=3601)


# ── SOP validation ─────────────────────────────────────────────────────────

class TestSOP:
    def test_valid_two_step_sop(self, minimal_sop):
        assert minimal_sop.id == "test_minimal_v1"
        assert minimal_sop.step_count == 2

    def test_id_pattern_enforced(self):
        with pytest.raises(Exception):
            SOP(
                id="Invalid ID!",
                name="Test",
                steps=[SOPStep(id=1, name="x", description="y")],
            )

    def test_id_allows_underscores_and_numbers(self):
        sop = SOP(
            id="test_sop_v2",
            name="Test",
            steps=[SOPStep(id=1, name="x", description="y")],
        )
        assert sop.id == "test_sop_v2"

    def test_steps_must_be_sequential(self):
        with pytest.raises(ValueError, match="sequential"):
            SOP(
                id="bad_sop",
                name="Bad",
                steps=[
                    SOPStep(id=1, name="a", description="a"),
                    SOPStep(id=3, name="b", description="b"),  # gap in ids
                ],
            )

    def test_steps_cannot_be_empty(self):
        with pytest.raises(Exception):
            SOP(id="empty_sop", name="Empty", steps=[])

    def test_must_follow_references_validated_against_sop(self):
        with pytest.raises(ValueError):
            SOP(
                id="bad_ref",
                name="Bad",
                steps=[
                    SOPStep(id=1, name="a", description="a"),
                    SOPStep(id=2, name="b", description="b", must_follow=[99]),
                ],
            )

    def test_get_step_returns_correct_step(self, minimal_sop):
        step = minimal_sop.get_step(1)
        assert step is not None
        assert step.name == "step_one"

    def test_get_step_returns_none_for_missing_id(self, minimal_sop):
        assert minimal_sop.get_step(999) is None

    def test_get_safety_critical_steps(self):
        sop = SOP(
            id="crit_test",
            name="Critical Test",
            steps=[
                SOPStep(id=1, name="safe", description="Safe step", safety_critical=False),
                SOPStep(id=2, name="crit", description="Critical step", safety_critical=True),
            ],
        )
        critical = sop.get_safety_critical_steps()
        assert len(critical) == 1
        assert critical[0].name == "crit"

    def test_all_required_ppe_merges_sop_and_step_ppe(self):
        sop = SOP(
            id="ppe_test",
            name="PPE Test",
            required_ppe=["safety_glasses"],
            steps=[
                SOPStep(
                    id=1, name="step", description="Step",
                    required_ppe=["insulated_gloves"]
                ),
            ],
        )
        ppe = sop.all_required_ppe()
        assert "safety_glasses" in ppe
        assert "insulated_gloves" in ppe

    def test_get_dependents(self, minimal_sop):
        deps = minimal_sop.get_dependents(1)
        assert len(deps) == 1
        assert deps[0].id == 2


# ── load_sop ───────────────────────────────────────────────────────────────

class TestLoadSop:
    def test_load_fire_evacuation_yaml(self):
        sop = load_sop(SOPS_DIR / "fire_evacuation_marshal_v1.yaml")
        assert sop.id == "fire_evacuation_marshal_v1"
        assert sop.step_count == 8
        assert sop.category == "Emergency Procedures"

    def test_load_fire_safety_yaml(self):
        sop = load_sop(SOPS_DIR / "lab_safety_induction_v1.yaml")
        assert sop.id == "lab_safety_induction_v1"
        assert sop.step_count == 8

    def test_load_classroom_av_yaml(self):
        sop = load_sop(SOPS_DIR / "classroom_av_setup_v1.yaml")
        assert sop.id == "classroom_av_setup_v1"
        assert sop.step_count == 8

    def test_load_from_json(self, tmp_path, minimal_sop):
        json_file = tmp_path / "test_sop.json"
        json_file.write_text(sop_to_json(minimal_sop), encoding="utf-8")
        loaded = load_sop(json_file)
        assert loaded.id == minimal_sop.id
        assert loaded.step_count == minimal_sop.step_count

    def test_load_bare_yaml_without_sop_wrapper(self, tmp_path, minimal_sop):
        """SOP data without the top-level 'sop:' key should also load."""
        bare = sop_to_dict(minimal_sop)
        yaml_file = tmp_path / "bare.yaml"
        yaml_file.write_text(yaml.dump(bare), encoding="utf-8")
        loaded = load_sop(yaml_file)
        assert loaded.id == minimal_sop.id

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            load_sop("/nonexistent/path/sop.yaml")

    def test_unsupported_extension_raises(self, tmp_path):
        f = tmp_path / "sop.txt"
        f.write_text("hello")
        with pytest.raises(ValueError, match="Unsupported"):
            load_sop(f)

    def test_empty_file_raises(self, tmp_path):
        f = tmp_path / "empty.yaml"
        f.write_text("")
        with pytest.raises(ValueError, match="empty"):
            load_sop(f)

    def test_invalid_schema_raises(self, tmp_path):
        f = tmp_path / "invalid.yaml"
        f.write_text(yaml.dump({"id": "no_steps", "name": "Bad"}))
        with pytest.raises(ValueError, match="validation failed"):
            load_sop(f)


# ── load_all_sops ──────────────────────────────────────────────────────────

class TestLoadAllSops:
    def test_loads_all_sops_from_directory(self):
        sops = load_all_sops(SOPS_DIR)
        assert "fire_evacuation_marshal_v1" in sops
        assert "lab_safety_induction_v1" in sops
        assert "classroom_av_setup_v1" in sops

    def test_returns_empty_dict_for_empty_directory(self, tmp_path):
        result = load_all_sops(tmp_path)
        assert result == {}

    def test_directory_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            load_all_sops("/nonexistent/directory")

    def test_error_on_duplicate_sop_ids(self, tmp_path, minimal_sop):
        for fname in ("sop_a.yaml", "sop_b.yaml"):
            (tmp_path / fname).write_text(sop_to_yaml(minimal_sop), encoding="utf-8")
        with pytest.raises(ValueError, match="Duplicate SOP id"):
            load_all_sops(tmp_path)


# ── Serialisation round-trips ──────────────────────────────────────────────

class TestSerialisation:
    def test_sop_to_dict_round_trip(self, minimal_sop):
        d = sop_to_dict(minimal_sop)
        restored = SOP.model_validate(d)
        assert restored.id == minimal_sop.id
        assert restored.step_count == minimal_sop.step_count

    def test_sop_to_yaml_round_trip(self, minimal_sop):
        yml = sop_to_yaml(minimal_sop)
        loaded = load_sop.__wrapped__(yml) if hasattr(load_sop, "__wrapped__") else None
        # Parse manually to verify round-trip
        raw = yaml.safe_load(yml)
        restored = SOP.model_validate(raw["sop"])
        assert restored.id == minimal_sop.id

    def test_sop_to_json_is_valid_json(self, fire_evacuation_sop):
        j = sop_to_json(fire_evacuation_sop)
        parsed = json.loads(j)
        assert parsed["sop"]["id"] == "fire_evacuation_marshal_v1"
