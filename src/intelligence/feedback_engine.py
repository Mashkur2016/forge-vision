"""
Feedback Engine — loads active LLM settings from DB and generates
personalised corrective instructions for detected SOP deviations.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import LLMSettings
from src.intelligence.crypto import decrypt_api_key
from src.intelligence.llm_providers import BaseLLMProvider, build_provider
from src.config import settings as app_settings


# ── Prompt template ────────────────────────────────────────────────────────

_FEEDBACK_PROMPT = """You are a workplace training assistant for a manufacturing/industrial environment.

Task: {sop_name}
Worker just did: {detected_action}
Expected step {step_id}: {step_description}
Error type: {error_type}
Detection confidence: {confidence:.0%}
Previous errors this session: {error_history}

Generate one clear, supportive corrective instruction (maximum 2 sentences).
- Be specific about the correct next action
- Use plain language — no technical jargon
- Be encouraging, never critical
- Focus on what TO DO, not what went wrong
"""


# ── DB helper ──────────────────────────────────────────────────────────────

async def get_active_settings(db: AsyncSession) -> LLMSettings | None:
    result = await db.execute(
        select(LLMSettings).where(LLMSettings.is_active == True).limit(1)
    )
    return result.scalar_one_or_none()


async def get_active_provider(db: AsyncSession) -> BaseLLMProvider:
    """
    Load the active LLM settings from DB and return the correct provider.
    Falls back to environment variable defaults if no DB settings exist.
    """
    row = await get_active_settings(db)

    if row is None:
        # No settings saved yet — use env var fallback
        return build_provider(
            provider=app_settings.LLM_PROVIDER,
            model_name=app_settings.LLM_MODEL,
            ollama_base_url=app_settings.OLLAMA_BASE_URL,
        )

    api_key = decrypt_api_key(row.api_key_enc) if row.api_key_enc else None

    return build_provider(
        provider=row.provider,
        model_name=row.model_name,
        api_key=api_key,
        ollama_base_url=row.ollama_base_url,
    )


# ── Main feedback function ─────────────────────────────────────────────────

async def generate_training_feedback(
    db: AsyncSession,
    sop_name: str,
    detected_action: str,
    error_type: str,
    step_id: int,
    step_description: str,
    confidence: float,
    error_history: list[str] | None = None,
) -> str:
    """
    Generate a personalised corrective instruction for a detected SOP deviation.

    Args:
        db:               Database session (to load LLM settings)
        sop_name:         Name of the SOP being performed
        detected_action:  What the worker just did (from action recognition)
        error_type:       MISSING_STEP | WRONG_ORDER | INCORRECT_EXECUTION | MISSING_PPE | UNSAFE_POSTURE
        step_id:          Expected SOP step number
        step_description: Text description of the expected step
        confidence:       Detection confidence score (0.0–1.0)
        error_history:    List of previous error types in this session

    Returns:
        Natural language corrective instruction string
    """
    provider = await get_active_provider(db)

    history_str = (
        ", ".join(error_history[-3:]) if error_history else "none"
    )

    prompt = _FEEDBACK_PROMPT.format(
        sop_name=sop_name,
        detected_action=detected_action,
        error_type=error_type,
        step_id=step_id,
        step_description=step_description,
        confidence=confidence,
        error_history=history_str,
    )

    return await provider.generate(prompt)
