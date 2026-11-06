"""
LLM provider implementations for FORGE-Vision.

All providers implement BaseLLMProvider with two methods:
  - generate(prompt) -> str          : generate feedback text
  - test_connection() -> (bool, str) : verify the provider is reachable

Swap providers by changing one env var / DB setting -no code changes needed.
"""
import asyncio
import time
from abc import ABC, abstractmethod

import httpx


# ── Known models for each external provider ────────────────────────────────
PROVIDER_MODELS: dict[str, list[tuple[str, str]]] = {
    "xai": [
        ("grok-3",             "Grok 3 - Best quality"),
        ("grok-3-mini",        "Grok 3 Mini - Fast & cheap"),
        ("grok-2",             "Grok 2 - Previous gen"),
        ("grok-2-mini",        "Grok 2 Mini - Lightweight"),
    ],
    "openai": [
        ("gpt-4o-mini", "GPT-4o Mini -Fast & cheap (Recommended)"),
        ("gpt-4o", "GPT-4o -Best quality"),
        ("gpt-3.5-turbo", "GPT-3.5 Turbo -Cheapest"),
    ],
    "groq": [
        ("openai/gpt-oss-20b", "GPT-OSS 20B -Free tier, fast (Recommended)"),
        ("openai/gpt-oss-120b", "GPT-OSS 120B -Free tier, best quality"),
        ("qwen/qwen3.8-27b", "Qwen 3.8 27B -Free tier"),
        ("llama-3.1-8b-instant", "Llama 3.1 8B -legacy (may be unavailable)"),
        ("llama-3.3-70b-versatile", "Llama 3.3 70B -legacy (may be unavailable)"),
    ],
    "anthropic": [
        ("claude-3-5-haiku-20241022", "Claude 3.5 Haiku -Fast & cheap"),
        ("claude-3-haiku-20240307", "Claude 3 Haiku -Cheapest"),
        ("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet -Best quality"),
    ],
    "gemini": [
        ("gemini-2.5-flash-lite", "Gemini 2.5 Flash-Lite -Free tier, fastest (Recommended)"),
        ("gemini-2.5-flash", "Gemini 2.5 Flash -Free tier, better quality"),
        ("gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite -Newer, fast"),
        ("gemini-3.5-flash", "Gemini 3.5 Flash -Newer, better quality"),
    ],
}

PROVIDER_LABELS: dict[str, str] = {
    "xai":      "xAI (Grok)",
    "openai": "OpenAI",
    "groq": "Groq (Free Tier Available)",
    "anthropic": "Anthropic (Claude)",
    "gemini": "Google Gemini (Free Tier Available)",
    "ollama": "Ollama (Local -No API Key Required)",
}

# Short, focused prompt used only for connection testing
_TEST_PROMPT = "Reply with exactly one word: OK"


class BaseLLMProvider(ABC):
    """Abstract base for all LLM providers."""

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """Generate a response for the given prompt."""

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str, float | None]:
        """
        Verify the provider is reachable and the API key / model is valid.
        Returns: (success, message, latency_ms)
        """


# ── OpenAI ─────────────────────────────────────────────────────────────────

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def generate(self, prompt: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()

    async def test_connection(self) -> tuple[bool, str, float | None]:
        try:
            start = time.perf_counter()
            result = await self.generate(_TEST_PROMPT)
            latency = round((time.perf_counter() - start) * 1000, 1)
            return True, f"Connected to OpenAI ({self._model}) -responded in {latency}ms", latency
        except Exception as exc:
            return False, f"OpenAI error: {exc}", None


# ── Groq (uses OpenAI-compatible SDK) ──────────────────────────────────────

class GroqProvider(BaseLLMProvider):
    _BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(self, api_key: str, model: str = "openai/gpt-oss-20b"):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=api_key, base_url=self._BASE_URL)
        self._model = model

    async def generate(self, prompt: str) -> str:
        # Reasoning models (gpt-oss, qwen3) spend completion tokens on hidden reasoning, so a
        # tight cap can leave the visible answer empty. Keep reasoning short and the cap generous.
        extra: dict = {}
        if self._model.startswith("openai/gpt-oss"):
            extra["reasoning_effort"] = "low"
        elif self._model.startswith("qwen/"):
            extra["reasoning_effort"] = "none"
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.3,
            extra_body=extra or None,
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise RuntimeError(f"Groq model {self._model} returned an empty reply")
        return content

    async def test_connection(self) -> tuple[bool, str, float | None]:
        try:
            start = time.perf_counter()
            await self.generate(_TEST_PROMPT)
            latency = round((time.perf_counter() - start) * 1000, 1)
            return True, f"Connected to Groq ({self._model}) -responded in {latency}ms", latency
        except Exception as exc:
            return False, f"Groq error: {exc}", None


# ── Anthropic ──────────────────────────────────────────────────────────────

class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "claude-3-5-haiku-20241022"):
        import anthropic
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def generate(self, prompt: str) -> str:
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    async def test_connection(self) -> tuple[bool, str, float | None]:
        try:
            start = time.perf_counter()
            await self.generate(_TEST_PROMPT)
            latency = round((time.perf_counter() - start) * 1000, 1)
            return True, f"Connected to Anthropic ({self._model}) -responded in {latency}ms", latency
        except Exception as exc:
            return False, f"Anthropic error: {exc}", None


# ── Google Gemini ──────────────────────────────────────────────────────────

class GeminiProvider(BaseLLMProvider):
    # Google's OpenAI-compatible endpoint: reuses the installed openai SDK and avoids the deprecated
    # google-generativeai package.
    _BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash-lite"):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=api_key, base_url=self._BASE_URL)
        self._model_name = model

    async def generate(self, prompt: str) -> str:
        # Thinking models can spend completion tokens before the visible answer, so keep the cap generous.
        response = await self._client.chat.completions.create(
            model=self._model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.3,
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise RuntimeError(f"Gemini model {self._model_name} returned an empty reply")
        return content

    async def test_connection(self) -> tuple[bool, str, float | None]:
        try:
            start = time.perf_counter()
            await self.generate(_TEST_PROMPT)
            latency = round((time.perf_counter() - start) * 1000, 1)
            return True, f"Connected to Google Gemini ({self._model_name}) -responded in {latency}ms", latency
        except Exception as exc:
            return False, f"Gemini error: {exc}", None


# ── xAI / Grok (OpenAI-compatible API) ────────────────────────────────────

class xAIProvider(BaseLLMProvider):
    _BASE_URL = "https://api.x.ai/v1"

    def __init__(self, api_key: str, model: str = "grok-2-latest"):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=api_key, base_url=self._BASE_URL)
        self._model = model

    async def generate(self, prompt: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()

    async def test_connection(self) -> tuple[bool, str, float | None]:
        try:
            start = time.perf_counter()
            await self.generate(_TEST_PROMPT)
            latency = round((time.perf_counter() - start) * 1000, 1)
            return True, f"Connected to xAI ({self._model}) - responded in {latency}ms", latency
        except Exception as exc:
            return False, f"xAI error: {exc}", None


# ── Ollama (local) ─────────────────────────────────────────────────────────

class OllamaProvider(BaseLLMProvider):
    def __init__(self, model: str = "llama3.1:8b", base_url: str = "http://localhost:11434"):
        self._model = model
        self._base_url = base_url.rstrip("/")

    async def generate(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 120},
                },
            )
            response.raise_for_status()
            return response.json()["response"].strip()

    async def test_connection(self) -> tuple[bool, str, float | None]:
        try:
            start = time.perf_counter()
            await self.generate(_TEST_PROMPT)
            latency = round((time.perf_counter() - start) * 1000, 1)
            return True, f"Connected to Ollama ({self._model}) at {self._base_url} -responded in {latency}ms", latency
        except httpx.ConnectError:
            return False, f"Cannot connect to Ollama at {self._base_url} -is Ollama running?", None
        except httpx.HTTPStatusError as exc:
            return False, f"Ollama HTTP error {exc.response.status_code}: {exc.response.text}", None
        except Exception as exc:
            return False, f"Ollama error: {exc}", None

    @classmethod
    async def fetch_installed_models(cls, base_url: str) -> list[str]:
        """Call Ollama /api/tags to get list of locally installed models."""
        url = base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{url}/api/tags")
            response.raise_for_status()
            data = response.json()
            return [m["name"] for m in data.get("models", [])]


# ── Factory ────────────────────────────────────────────────────────────────

def build_provider(
    provider: str,
    model_name: str,
    api_key: str | None = None,
    ollama_base_url: str | None = None,
) -> BaseLLMProvider:
    """Instantiate the correct provider from config values."""
    match provider:
        case "xai":
            return xAIProvider(api_key=api_key, model=model_name)
        case "openai":
            return OpenAIProvider(api_key=api_key, model=model_name)
        case "groq":
            return GroqProvider(api_key=api_key, model=model_name)
        case "anthropic":
            return AnthropicProvider(api_key=api_key, model=model_name)
        case "gemini":
            return GeminiProvider(api_key=api_key, model=model_name)
        case "ollama":
            return OllamaProvider(
                model=model_name,
                base_url=ollama_base_url or "http://localhost:11434",
            )
        case _:
            raise ValueError(f"Unknown LLM provider: {provider!r}")
