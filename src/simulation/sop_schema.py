"""
SOP (Standard Operating Procedure) Pydantic data models.

These models define and validate all SOP definitions used by FORGE-Vision.
Every SOP loaded into the system — whether from YAML, JSON, or parsed by the
LLM SOP Parser — is validated against this schema before use.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator


class SOPStep(BaseModel):
    """A single step within an SOP procedure."""

    id: int = Field(..., ge=1, description="Step number, 1-indexed and sequential")
    name: str = Field(..., min_length=1, max_length=100, description="Short machine-readable step name")
    description: str = Field(..., min_length=1, max_length=500, description="Plain-language instruction shown to worker")

    # Objects that must be present / used during this step
    required_objects: list[str] = Field(
        default_factory=list,
        description="Object labels the CV pipeline must detect for this step",
    )

    # Expected worker pose (maps to a MediaPipe pose class label)
    required_pose: Optional[str] = Field(
        None,
        max_length=100,
        description="Expected pose label from action recognition model",
    )

    # Sequencing constraints
    must_follow: list[int] = Field(
        default_factory=list,
        description="IDs of steps that must be completed before this step can begin",
    )

    # Timing
    time_limit_seconds: Optional[int] = Field(
        None,
        ge=1,
        le=3600,
        description="Maximum time allowed for this step; None means no limit",
    )

    # Safety
    safety_critical: bool = Field(
        False,
        description="If True, an error on this step triggers supervisor alert, not just worker feedback",
    )
    required_ppe: list[str] = Field(
        default_factory=list,
        description="PPE that must be detected during this step (overrides SOP-level PPE if specified)",
    )

    @model_validator(mode="after")
    def _validate_dependencies(self) -> "SOPStep":
        for dep in self.must_follow:
            if dep >= self.id:
                raise ValueError(
                    f"Step {self.id}: must_follow contains {dep}, "
                    "which is not a preceding step (must be < this step id)"
                )
        return self


class SOP(BaseModel):
    """
    A complete Standard Operating Procedure definition.

    SOPs are the ground truth used by the Intelligence Layer to detect
    deviations and generate corrective feedback.
    """

    id: str = Field(
        ...,
        pattern=r"^[a-z0-9_]+$",
        description="Unique SOP identifier — lowercase letters, digits, underscores only",
    )
    name: str = Field(..., min_length=1, max_length=200)
    version: str = Field("1.0", max_length=20)
    category: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=150)
    estimated_duration_seconds: Optional[int] = Field(None, ge=1)

    # PPE required throughout the entire procedure
    required_ppe: list[str] = Field(
        default_factory=list,
        description="PPE labels that must be present from start to finish",
    )

    steps: list[SOPStep] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _validate_step_ids(self) -> "SOP":
        ids = [s.id for s in self.steps]
        expected = list(range(1, len(ids) + 1))
        if ids != expected:
            raise ValueError(
                f"Step IDs must be sequential starting from 1. "
                f"Got: {ids}, expected: {expected}"
            )
        return self

    @model_validator(mode="after")
    def _validate_must_follow_references(self) -> "SOP":
        valid_ids = {s.id for s in self.steps}
        for step in self.steps:
            for dep in step.must_follow:
                if dep not in valid_ids:
                    raise ValueError(
                        f"Step {step.id}: must_follow references non-existent step id {dep}"
                    )
        return self

    # ── Convenience helpers ────────────────────────────────────────────────

    @property
    def step_count(self) -> int:
        return len(self.steps)

    def get_step(self, step_id: int) -> Optional[SOPStep]:
        """Return the step with the given id, or None if not found."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def get_safety_critical_steps(self) -> list[SOPStep]:
        """Return all steps marked safety_critical=True."""
        return [s for s in self.steps if s.safety_critical]

    def get_dependents(self, step_id: int) -> list[SOPStep]:
        """Return all steps that directly depend on the given step id."""
        return [s for s in self.steps if step_id in s.must_follow]

    def all_required_ppe(self) -> set[str]:
        """Union of SOP-level PPE and all step-level PPE requirements."""
        ppe: set[str] = set(self.required_ppe)
        for step in self.steps:
            ppe.update(step.required_ppe)
        return ppe

    def __repr__(self) -> str:
        return f"<SOP id={self.id!r} name={self.name!r} steps={self.step_count}>"
