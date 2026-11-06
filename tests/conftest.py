"""
Shared pytest fixtures for FORGE-Vision test suite.
"""
from __future__ import annotations


from pathlib import Path

import numpy as np
import pytest

from src.simulation.sop_schema import SOP, SOPStep

# ── Paths ──────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOPS_DIR = PROJECT_ROOT / "data" / "sops"


# ── SOP fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def minimal_sop() -> SOP:
    """A minimal 2-step SOP for fast unit testing."""
    return SOP(
        id="test_minimal_v1",
        name="Minimal Test Procedure",
        steps=[
            SOPStep(id=1, name="step_one", description="Do step one"),
            SOPStep(id=2, name="step_two", description="Do step two", must_follow=[1]),
        ],
    )


@pytest.fixture
def fire_evacuation_sop() -> SOP:
    """The fire evacuation marshal SOP loaded from the YAML fixture file."""
    from src.simulation.sop_parser import load_sop
    return load_sop(SOPS_DIR / "fire_evacuation_marshal_v1.yaml")


@pytest.fixture
def lab_safety_sop() -> SOP:
    """The lab safety induction SOP loaded from the YAML fixture file."""
    from src.simulation.sop_parser import load_sop
    return load_sop(SOPS_DIR / "lab_safety_induction_v1.yaml")


@pytest.fixture
def classroom_av_sop() -> SOP:
    """The classroom AV setup SOP loaded from the YAML fixture file."""
    from src.simulation.sop_parser import load_sop
    return load_sop(SOPS_DIR / "classroom_av_setup_v1.yaml")


# ── Frame fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def blank_frame() -> np.ndarray:
    """640×480 blank BGR frame."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def random_frame() -> np.ndarray:
    """640×480 random-noise BGR frame (seeded for reproducibility)."""
    rng = np.random.default_rng(42)
    return rng.integers(0, 256, (480, 640, 3), dtype=np.uint8)


@pytest.fixture
def random_clip() -> list[np.ndarray]:
    """A 30-frame random-noise clip."""
    rng = np.random.default_rng(42)
    return [rng.integers(0, 256, (480, 640, 3), dtype=np.uint8) for _ in range(30)]
