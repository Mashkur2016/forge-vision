"""
Feedback API Route — on-demand LLM corrective instruction for a deviation.

A standalone endpoint that turns a single detected deviation into corrective
text using the DB-stored, encrypted LLM key (Groq by default). Any client that
detects a deviation out-of-band can POST it here instead of holding the async
LLM engine itself.

This mirrors the in-process feedback callback used by the server-camera path
(src/api/routes/session.py :: _make_feedback_fn) so both paths produce
identical feedback.

Rules.md §1.6: every deviation explains WHAT + WHY; the LLM turns that into a
supportive corrective instruction.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routes.deps import get_db
from src.intelligence.feedback_engine import generate_training_feedback, get_active_settings
from src.intelligence.feedback_templates import get_template_feedback

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/feedback", tags=["Feedback"])


# ── Schemas ────────────────────────────────────────────────────────────────

class DeviationFeedbackRequest(BaseModel):
    """
    Subset of a SOPDeviationEvent (see SOPDeviationEvent.to_dict()).

    Extra fields from the full event dict are ignored, so callers may post the
    whole deviation payload unchanged.
    """
    sop_name: str
    deviation_class: str
    severity: str = "low"
    what: str = ""
    expected_step_id: int | None = None
    expected_step_name: str = ""
    model_confidence: float = 0.0
    error_history: list[str] = Field(default_factory=list)


class DeviationFeedbackResponse(BaseModel):
    feedback_text: str
    deviation_class: str
    severity: str
    step_name: str
    confidence: float


# ── Route ──────────────────────────────────────────────────────────────────

@router.post("/from-deviation", response_model=DeviationFeedbackResponse)
async def feedback_from_deviation(
    req: DeviationFeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> DeviationFeedbackResponse:
    """Generate a corrective instruction for one detected SOP deviation."""
    try:
        feedback_text = await generate_training_feedback(
            db=db,
            sop_name=req.sop_name,
            detected_action=req.what or req.deviation_class,
            error_type=req.deviation_class,
            step_id=req.expected_step_id or 0,
            step_description=req.expected_step_name,
            confidence=req.model_confidence,
            error_history=req.error_history,
        )
    except Exception as exc:
        log.warning("Feedback generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM feedback unavailable: {exc}",
        )

    return DeviationFeedbackResponse(
        feedback_text=feedback_text,
        deviation_class=req.deviation_class,
        severity=req.severity,
        step_name=req.expected_step_name,
        confidence=req.model_confidence,
    )


# ── Template vs LLM demo ─────────────────────────────────────────────────────

class FeedbackDemoResponse(BaseModel):
    """Side-by-side: rule-based template vs LLM-generated corrective feedback."""
    deviation_class: str
    step_name: str
    template_feedback: str
    llm_feedback: str | None = None
    llm_error: str | None = None
    provider: str | None = None
    model: str | None = None


@router.post("/demo", response_model=FeedbackDemoResponse)
async def feedback_demo(
    req: DeviationFeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> FeedbackDemoResponse:
    """
    Generate BOTH the rule-based template feedback and the LLM feedback for one
    deviation, so the UI can show them side by side. Never fails on the LLM side:
    if no provider/key is configured the template still returns and the LLM error
    is reported in ``llm_error`` (HTTP 200).
    """
    template = get_template_feedback(req.deviation_class, req.expected_step_name)

    row = await get_active_settings(db)
    provider = row.provider if row else None
    model = row.model_name if row else None

    llm_feedback: str | None = None
    llm_error: str | None = None
    try:
        llm_feedback = await generate_training_feedback(
            db=db,
            sop_name=req.sop_name,
            detected_action=req.what or req.deviation_class,
            error_type=req.deviation_class,
            step_id=req.expected_step_id or 0,
            step_description=req.expected_step_name,
            confidence=req.model_confidence,
            error_history=req.error_history,
        )
    except Exception as exc:  # noqa: BLE001 — demo must still show the template
        llm_error = str(exc)
        log.info("Feedback demo: LLM unavailable (%s)", exc)

    return FeedbackDemoResponse(
        deviation_class=req.deviation_class,
        step_name=req.expected_step_name,
        template_feedback=template,
        llm_feedback=llm_feedback,
        llm_error=llm_error,
        provider=provider,
        model=model,
    )
