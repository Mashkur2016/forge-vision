"""
Rule-based corrective-feedback templates.

These are the fallback the system uses when no LLM is configured, and the
baseline the LLM (Groq) is compared against in the "Template vs Groq" demo.
Single source of truth shared by the seeder and the feedback API so the two
never drift.

Each template has one ``{step}`` placeholder for the expected SOP step name.
"""
from __future__ import annotations

FEEDBACK_TEMPLATES: dict[str, str] = {
    "MISSING_STEP": "It looks like a step was skipped. Please return to '{step}' and complete it before continuing.",
    "WRONG_ORDER": "The sequence is out of order around '{step}'. Follow the SOP order so each step builds on the last.",
    "INCORRECT_EXECUTION": "'{step}' wasn't executed as specified. Review the method and try the step again.",
    "MISSING_PPE": "Required PPE was not detected. Please put on the correct protective equipment before proceeding.",
    "UNSAFE_POSTURE": "Your posture looks unsafe. Adjust your position to protect yourself before resuming '{step}'.",
}

_DEFAULT = "Deviation detected at '{step}'. Review the step against the SOP and correct it."


def get_template_feedback(deviation_class: str, step_name: str) -> str:
    """Return the rule-based corrective instruction for a deviation class.

    Falls back to a generic message for unknown classes; never raises.
    """
    template = FEEDBACK_TEMPLATES.get(deviation_class, _DEFAULT)
    try:
        return template.format(step=step_name or "this step")
    except Exception:
        return _DEFAULT.format(step=step_name or "this step")
