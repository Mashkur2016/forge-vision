"""
LLM SOP Parser — Enhancement 1 (Enhancements.md §Enhancement 1).

Extracts a structured SOP definition from unstructured text (pasted from a
PDF manual, Word document, or typed description) using the active LLM
configured in the FORGE-Vision settings.

The LLM is prompted to return a JSON object matching the SOP schema. The
response is validated against the Pydantic SOP model before being returned,
so callers always receive a type-safe, fully-validated SOP object or an error.

Usage:
    from sqlalchemy.ext.asyncio import AsyncSession
    from src.simulation.llm_sop_parser import parse_sop_from_text

    sop = await parse_sop_from_text(db, raw_text, suggested_id="wiring_v2")
"""
from __future__ import annotations

import json
import logging
import re

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.intelligence.feedback_engine import get_active_provider
from src.simulation.sop_schema import SOP
from src.simulation.sop_parser import sop_to_yaml

logger = logging.getLogger(__name__)

# ── Prompt template ────────────────────────────────────────────────────────

_PARSE_PROMPT = """You are a technical documentation specialist. Extract a structured SOP \
(Standard Operating Procedure) from the text below.

Return ONLY a valid JSON object — no explanation, no markdown fences, no extra text.

JSON structure to return:
{{
  "id": "<lowercase_underscored_identifier>",
  "name": "<full procedure name>",
  "version": "1.0",
  "category": "<e.g. Electrical, Safety, Manufacturing>",
  "department": "<department or null>",
  "estimated_duration_seconds": <integer or null>,
  "required_ppe": ["<ppe_item>", ...],
  "steps": [
    {{
      "id": 1,
      "name": "<short_machine_readable_name>",
      "description": "<plain English instruction for the worker>",
      "required_objects": ["<object_label>", ...],
      "required_pose": "<pose_label or null>",
      "time_limit_seconds": <integer or null>,
      "must_follow": [<list of step ids that must precede this>],
      "safety_critical": <true or false>,
      "required_ppe": ["<ppe_item>", ...]
    }},
    ...
  ]
}}

Rules:
- Step ids must be sequential integers starting from 1
- must_follow values must reference only lower-numbered steps
- required_objects: use short lowercase_underscore labels (e.g. "power_switch", "red_wire")
- required_pose: use short descriptive labels (e.g. "both_hands_terminal_area") or null
- safety_critical: true only if skipping this step creates direct physical danger
- Extract ALL steps — do not summarise or skip any

SOP text to extract:
---
{raw_text}
---

JSON response:"""

# Maximum text length sent to the LLM (prevents excessive token usage)
_MAX_INPUT_CHARS = 8_000


# ── Public API ─────────────────────────────────────────────────────────────

async def parse_sop_from_text(
    db: AsyncSession,
    raw_text: str,
    suggested_id: str | None = None,
) -> SOP:
    """
    Parse and validate an SOP from unstructured text using the active LLM.

    Args:
        db:           Database session (used to load active LLM settings).
        raw_text:     Raw SOP text extracted from a PDF, Word doc, or typed input.
        suggested_id: Optional SOP id hint; the LLM may use it or derive its own.

    Returns:
        Validated SOP object.

    Raises:
        ValueError: If the LLM returns invalid JSON or the JSON fails schema validation.
        RuntimeError: If the LLM call fails.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("raw_text is empty — nothing to parse")

    # Truncate to avoid runaway token consumption
    truncated = raw_text.strip()[:_MAX_INPUT_CHARS]
    if len(raw_text.strip()) > _MAX_INPUT_CHARS:
        logger.warning(
            "Input text truncated from %d to %d characters for LLM SOP parsing",
            len(raw_text.strip()),
            _MAX_INPUT_CHARS,
        )

    prompt = _PARSE_PROMPT.format(raw_text=truncated)

    # Inject id hint into prompt if provided
    if suggested_id:
        prompt = prompt.replace(
            '"id": "<lowercase_underscored_identifier>"',
            f'"id": "{suggested_id}"',
        )

    # ── LLM call ──────────────────────────────────────────────────────────
    try:
        provider = await get_active_provider(db)
        raw_response = await provider.generate(prompt)
    except Exception as exc:
        raise RuntimeError(f"LLM call failed during SOP parsing: {exc}") from exc

    # ── Extract and parse JSON ─────────────────────────────────────────────
    sop_dict = _extract_json(raw_response)

    # ── Validate against schema ────────────────────────────────────────────
    try:
        sop = SOP.model_validate(sop_dict)
    except ValidationError as exc:
        raise ValueError(
            f"LLM-generated SOP failed schema validation:\n{exc}\n\n"
            f"Raw LLM response:\n{raw_response[:500]}"
        ) from exc

    logger.info(
        "LLM SOP Parser: extracted SOP '%s' with %d steps",
        sop.id,
        sop.step_count,
    )
    return sop


def format_sop_preview(sop: SOP) -> str:
    """Return a human-readable YAML preview of a parsed SOP for UI display."""
    return sop_to_yaml(sop)


# ── Helpers ────────────────────────────────────────────────────────────────

def _extract_json(raw: str) -> dict:
    """
    Extract a JSON object from an LLM response string.

    The LLM may return the JSON wrapped in markdown code fences or with
    leading/trailing prose — this function strips all of that.
    """
    text = raw.strip()

    # Strip markdown code fences: ```json ... ``` or ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    text = text.strip()

    # Find the outermost JSON object
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start == -1 or brace_end == -1:
        raise ValueError(
            f"LLM response does not contain a JSON object.\n"
            f"Response (first 300 chars): {raw[:300]}"
        )

    json_str = text[brace_start : brace_end + 1]

    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM returned invalid JSON: {exc}\n"
            f"JSON string (first 500 chars): {json_str[:500]}"
        ) from exc

    if not isinstance(parsed, dict):
        raise ValueError(
            f"Expected a JSON object (dict), got {type(parsed).__name__}"
        )

    return parsed
