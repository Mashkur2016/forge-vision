"""
API route — LLM SOP Parser.

Wraps the existing LLMSOPParser module so the Streamlit SOP Builder page can
invoke it via HTTP instead of calling the module directly.

Endpoint:
  POST /api/v1/llm-sop-parser/parse   — parse raw text into a structured SOP
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routes.deps import require_roles
from src.database.database import get_db
from src.simulation.llm_sop_parser import parse_sop_from_text

router = APIRouter(
    prefix="/api/v1/llm-sop-parser",
    tags=["LLM SOP Parser"],
    dependencies=[Depends(require_roles("admin", "trainer", "manager"))],
)


class ParseRequest(BaseModel):
    text: str
    suggested_id: str | None = None


@router.post("/parse")
async def parse_sop(
    payload: ParseRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Parse unstructured procedure text (pasted from a PDF, Word doc, or typed
    description) into a validated SOP JSON object using the active LLM provider.

    The text is truncated to 8 000 characters internally. Returns the full SOP
    schema including all steps, PPE requirements, and sequencing constraints.
    """
    if not payload.text or not payload.text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="text must not be empty",
        )

    try:
        sop = await parse_sop_from_text(db, payload.text, payload.suggested_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    return sop.model_dump()
