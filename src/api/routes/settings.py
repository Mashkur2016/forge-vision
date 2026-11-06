"""
FastAPI routes for LLM Settings management.

Endpoints:
  GET  /api/v1/settings               — Get current active settings (key masked)
  GET  /api/v1/settings/all           — List all saved configurations
  POST /api/v1/settings               — Save / update settings
  POST /api/v1/settings/test          — Test connection before saving
  POST /api/v1/settings/{id}/activate — Switch active configuration
  DELETE /api/v1/settings/{id}        — Delete a saved configuration
  GET  /api/v1/settings/ollama-models — List installed Ollama models
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routes.deps import get_current_user, require_roles
from src.api.schemas.settings import (
    LLMSettingsResponse,
    LLMSettingsSave,
    LLMSettingsTest,
    OllamaModelsResponse,
    TestConnectionResponse,
)
from src.database.database import get_db
from src.database.models import LLMSettings, User
from src.intelligence.crypto import decrypt_api_key, encrypt_api_key, mask_api_key
from src.intelligence.llm_providers import OllamaProvider, build_provider

router = APIRouter(
    prefix="/api/v1/settings",
    tags=["Settings"],
    dependencies=[Depends(require_roles("admin"))],
)

# Separate router for endpoints accessible to all authenticated roles (no API keys exposed)
open_router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])


class ActiveProviderResponse(BaseModel):
    provider: str
    model_name: str


@open_router.get("/active-provider", response_model=ActiveProviderResponse | None)
async def get_active_provider(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return just the active provider name and model — no API keys. Accessible to all roles."""
    result = await db.execute(
        select(LLMSettings).where(LLMSettings.is_active == True).limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return ActiveProviderResponse(provider=row.provider, model_name=row.model_name)


# ── Helpers ────────────────────────────────────────────────────────────────

async def _get_active_row(db: AsyncSession) -> LLMSettings | None:
    result = await db.execute(
        select(LLMSettings).where(LLMSettings.is_active == True).limit(1)
    )
    return result.scalar_one_or_none()


def _build_response(row: LLMSettings) -> LLMSettingsResponse:
    """Build a masked LLMSettingsResponse from an ORM row."""
    masked_key = None
    if row.api_key_enc:
        try:
            plain = decrypt_api_key(row.api_key_enc)
            masked_key = mask_api_key(plain)
        except ValueError:
            masked_key = "••••••••  (decryption error)"

    return LLMSettingsResponse(
        id=row.id,
        provider=row.provider,
        model_name=row.model_name,
        api_key_masked=masked_key,
        ollama_base_url=row.ollama_base_url,
        is_active=row.is_active,
        tested_ok=row.tested_ok,
        updated_at=row.updated_at,
    )


# ── GET /api/v1/settings ───────────────────────────────────────────────────

@router.get("", response_model=LLMSettingsResponse | None)
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Return the active LLM settings. API key is masked in the response."""
    row = await _get_active_row(db)
    if row is None:
        return None
    return _build_response(row)


# ── GET /api/v1/settings/all ───────────────────────────────────────────────

@router.get("/all", response_model=list[LLMSettingsResponse])
async def get_all_settings(db: AsyncSession = Depends(get_db)):
    """Return all saved LLM configurations, active one first."""
    result = await db.execute(
        select(LLMSettings).order_by(
            LLMSettings.is_active.desc(),
            LLMSettings.updated_at.desc(),
        )
    )
    rows = result.scalars().all()
    return [_build_response(r) for r in rows]


# ── POST /api/v1/settings ──────────────────────────────────────────────────

@router.post("", response_model=LLMSettingsResponse, status_code=status.HTTP_200_OK)
async def save_settings(payload: LLMSettingsSave, db: AsyncSession = Depends(get_db)):
    """
    Save LLM settings.
    - If a row with the same provider+model already exists, update it.
    - Otherwise insert a new row.
    - The saved row becomes the active configuration.
    - All other rows are deactivated.
    """
    encrypted_key = encrypt_api_key(payload.api_key) if payload.api_key else None

    # Check if same provider+model already saved
    result = await db.execute(
        select(LLMSettings).where(
            LLMSettings.provider == payload.provider,
            LLMSettings.model_name == payload.model_name,
        ).limit(1)
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Only overwrite the stored key if a new one was actually provided
        if encrypted_key is not None:
            existing.api_key_enc = encrypted_key
        existing.ollama_base_url = payload.ollama_base_url
        existing.tested_ok = False
        existing.is_active = True
        row = existing
    else:
        row = LLMSettings(
            provider=payload.provider,
            model_name=payload.model_name,
            api_key_enc=encrypted_key,
            ollama_base_url=payload.ollama_base_url,
            is_active=True,
            tested_ok=False,
        )
        db.add(row)

    await db.flush()

    # Deactivate all other rows
    await db.execute(
        update(LLMSettings)
        .where(LLMSettings.id != row.id)
        .values(is_active=False)
    )

    await db.refresh(row)

    masked_key = mask_api_key(payload.api_key) if payload.api_key else None
    return LLMSettingsResponse(
        id=row.id,
        provider=row.provider,
        model_name=row.model_name,
        api_key_masked=masked_key,
        ollama_base_url=row.ollama_base_url,
        is_active=row.is_active,
        tested_ok=row.tested_ok,
        updated_at=row.updated_at,
    )


# ── POST /api/v1/settings/test ─────────────────────────────────────────────

@router.post("/test", response_model=TestConnectionResponse)
async def test_connection(payload: LLMSettingsTest, db: AsyncSession = Depends(get_db)):
    """
    Test if the provided LLM settings can reach the model.
    If no api_key is provided in the payload, falls back to the saved DB key.
    On success, marks tested_ok=True in the database.
    """
    api_key = payload.api_key

    # Fall back to the saved (encrypted) key when none is supplied in the request.
    # Look up by provider+model first so switching providers reuses their stored key.
    if not api_key and payload.provider != "ollama":
        result = await db.execute(
            select(LLMSettings).where(
                LLMSettings.provider == payload.provider,
                LLMSettings.model_name == payload.model_name,
            ).limit(1)
        )
        saved_row = result.scalar_one_or_none()

        # Fall back to active row if no provider+model specific row found
        if not saved_row:
            saved_row = await _get_active_row(db)

        if saved_row and saved_row.api_key_enc:
            try:
                api_key = decrypt_api_key(saved_row.api_key_enc)
            except Exception:
                return TestConnectionResponse(
                    success=False,
                    message="Saved key could not be decrypted. Please re-enter your key."
                )
        else:
            return TestConnectionResponse(
                success=False,
                message="No API key provided and none is saved. Enter your key in the field above."
            )

    try:
        provider = build_provider(
            provider=payload.provider,
            model_name=payload.model_name,
            api_key=api_key,
            ollama_base_url=payload.ollama_base_url,
        )
    except ValueError as exc:
        return TestConnectionResponse(success=False, message=str(exc))

    success, message, latency = await provider.test_connection()

    # If test passed, mark ALL saved rows for this provider as tested.
    # The API key is per-provider, so a successful test validates the key for every
    # model under that provider — not just the one model that was tested.
    if success:
        await db.execute(
            update(LLMSettings)
            .where(LLMSettings.provider == payload.provider)
            .values(tested_ok=True)
        )

    return TestConnectionResponse(success=success, message=message, latency_ms=latency)


# ── POST /api/v1/settings/{id}/activate ───────────────────────────────────

@router.post("/{settings_id}/activate", response_model=LLMSettingsResponse)
async def activate_settings(settings_id: int, db: AsyncSession = Depends(get_db)):
    """Switch the active configuration to the specified settings row."""
    result = await db.execute(
        select(LLMSettings).where(LLMSettings.id == settings_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Settings not found")

    # Deactivate all, then activate the selected one
    await db.execute(update(LLMSettings).values(is_active=False))
    row.is_active = True
    await db.flush()
    await db.refresh(row)
    return _build_response(row)


# ── DELETE /api/v1/settings/{id} ──────────────────────────────────────────

@router.delete("/{settings_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_settings(settings_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a saved configuration. If it was active, activate the most recent remaining row."""
    result = await db.execute(
        select(LLMSettings).where(LLMSettings.id == settings_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Settings not found")

    was_active = row.is_active
    await db.delete(row)
    await db.flush()

    # If we deleted the active row, promote the most recently updated remaining row
    if was_active:
        result2 = await db.execute(
            select(LLMSettings).order_by(LLMSettings.updated_at.desc()).limit(1)
        )
        next_row = result2.scalar_one_or_none()
        if next_row:
            next_row.is_active = True
            await db.flush()


# ── GET /api/v1/settings/ollama-models ────────────────────────────────────

@router.get("/ollama-models", response_model=OllamaModelsResponse)
async def get_ollama_models(base_url: str = "http://host.docker.internal:11434"):
    """
    Fetch the list of locally installed Ollama models.
    Calls Ollama's /api/tags endpoint.
    """
    try:
        models = await OllamaProvider.fetch_installed_models(base_url)
    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Ollama at {base_url}. Is Ollama running?",
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ollama returned error {exc.response.status_code}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Ollama models: {exc}",
        )

    if not models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No models found. Pull a model first: ollama pull llama3.1:8b",
        )

    return OllamaModelsResponse(models=models, base_url=base_url)
