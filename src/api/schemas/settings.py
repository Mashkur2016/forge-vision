"""
Pydantic schemas for LLM Settings API requests and responses.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


ProviderType = Literal["xai", "openai", "groq", "anthropic", "gemini", "ollama"]


class LLMSettingsSave(BaseModel):
    """Request body for POST /api/v1/settings — save new settings."""
    provider: ProviderType
    model_name: str = Field(..., min_length=1, max_length=100)

    # Required for external providers; omit for Ollama
    api_key: str | None = Field(default=None, min_length=1, max_length=500)

    # Required for Ollama; omit for external providers
    ollama_base_url: str | None = Field(default=None, max_length=255)

    @field_validator("api_key")
    @classmethod
    def validate_api_key_for_external(cls, v, info):
        if v:
            v = v.strip()
            # Auto-strip accidental label prefixes e.g. "grok: gsk_abc" → "gsk_abc"
            prefixes = {"groq": "gsk_", "openai": "sk-", "anthropic": "sk-ant-", "xai": "xai-"}
            provider = info.data.get("provider")
            expected = prefixes.get(provider)
            if expected and not v.startswith(expected) and expected in v:
                v = v[v.index(expected):]
        provider = info.data.get("provider")
        if provider != "ollama" and not v:
            raise ValueError(f"API key is required for provider '{provider}'")
        return v

    @field_validator("ollama_base_url")
    @classmethod
    def validate_ollama_url(cls, v, info):
        provider = info.data.get("provider")
        if provider == "ollama" and not v:
            raise ValueError("ollama_base_url is required when provider is 'ollama'")
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("ollama_base_url must start with http:// or https://")
        return v


class LLMSettingsTest(BaseModel):
    """Request body for POST /api/v1/settings/test — test before saving."""
    provider: ProviderType
    model_name: str
    api_key: str | None = None
    ollama_base_url: str | None = None

    @field_validator("api_key")
    @classmethod
    def strip_api_key(cls, v, info):
        if not v:
            return v
        v = v.strip()
        provider = info.data.get("provider")
        prefixes = {"groq": "gsk_", "openai": "sk-", "anthropic": "sk-ant-", "xai": "xai-"}
        expected = prefixes.get(provider)
        if expected:
            # Auto-strip accidental label prefixes e.g. "grok: gsk_abc" → "gsk_abc"
            if not v.startswith(expected) and expected in v:
                v = v[v.index(expected):]
            if not v.startswith(expected):
                raise ValueError(
                    f"{provider.title()} API keys must start with '{expected}'. "
                    f"Your key starts with '{v[:8]}...' — please check you copied the correct key."
                )
        return v


class LLMSettingsResponse(BaseModel):
    """Response for GET /api/v1/settings — API key is masked."""
    id: int
    provider: ProviderType
    model_name: str
    api_key_masked: str | None        # "sk-••••••••abcd" or None
    ollama_base_url: str | None
    is_active: bool
    tested_ok: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestConnectionResponse(BaseModel):
    """Response for POST /api/v1/settings/test."""
    success: bool
    message: str
    latency_ms: float | None = None   # Response time in milliseconds


class OllamaModelsResponse(BaseModel):
    """Response for GET /api/v1/settings/ollama-models."""
    models: list[str]
    base_url: str
