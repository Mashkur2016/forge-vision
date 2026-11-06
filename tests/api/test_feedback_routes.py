"""
Integration tests for /api/v1/feedback/from-deviation.

Uses an in-memory SQLite DB + a patched LLM engine so no real provider/key is
needed.  Verifies the deviation→corrective-text mapping, that extra event
fields are ignored, and that LLM errors surface as 502.
"""
from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.database.models import Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture()
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def app_client(test_engine):
    from fastapi import FastAPI
    from src.api.routes import feedback as feedback_mod
    from src.api.routes.deps import get_db

    factory = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)

    async def _override_db() -> AsyncIterator[AsyncSession]:
        async with factory() as sess:
            try:
                yield sess
                await sess.commit()
            except Exception:
                await sess.rollback()
                raise

    test_app = FastAPI()
    test_app.include_router(feedback_mod.router)
    test_app.dependency_overrides[get_db] = _override_db

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        yield client


# Full deviation dict as produced by SOPDeviationEvent.to_dict()
_DEVIATION = {
    "session_id": "abc123",
    "sop_id": "fire_evacuation_marshal_v1",
    "sop_name": "Fire Evacuation Marshal",
    "timestamp": 1.23,
    "deviation_class": "MISSING_PPE",
    "severity": "high",
    "expected_step_id": 3,
    "expected_step_name": "Don high-visibility vest",
    "observed_action_class": -1,
    "model_confidence": 0.92,
    "what": "Required PPE not detected: hi_vis_vest",
    "why": "SOP requires PPE throughout the procedure.",
    "detected_objects": ["person"],
    "missing_ppe": ["hi_vis_vest"],
    "person_detected": True,
    "detection_latency_ms": 12.0,
}


@pytest.mark.asyncio
async def test_feedback_from_full_deviation_dict(app_client):
    """Posting the whole event dict works (extra fields ignored) and maps args."""
    mock_gen = AsyncMock(return_value="Please put on your hi-vis vest before continuing.")
    with patch("src.api.routes.feedback.generate_training_feedback", mock_gen):
        resp = await app_client.post(
            "/api/v1/feedback/from-deviation",
            json={**_DEVIATION, "error_history": ["WRONG_ORDER"]},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["feedback_text"].startswith("Please put on")
    assert body["deviation_class"] == "MISSING_PPE"
    assert body["severity"] == "high"
    assert body["step_name"] == "Don high-visibility vest"
    assert body["confidence"] == pytest.approx(0.92)

    # Verify the engine received the mapped arguments
    kwargs = mock_gen.call_args.kwargs
    assert kwargs["sop_name"] == "Fire Evacuation Marshal"
    assert kwargs["error_type"] == "MISSING_PPE"
    assert kwargs["step_id"] == 3
    assert kwargs["step_description"] == "Don high-visibility vest"
    assert kwargs["confidence"] == pytest.approx(0.92)
    assert kwargs["error_history"] == ["WRONG_ORDER"]


@pytest.mark.asyncio
async def test_detected_action_falls_back_to_class(app_client):
    """When 'what' is empty, detected_action falls back to the deviation class."""
    mock_gen = AsyncMock(return_value="ok")
    with patch("src.api.routes.feedback.generate_training_feedback", mock_gen):
        resp = await app_client.post(
            "/api/v1/feedback/from-deviation",
            json={"sop_name": "S", "deviation_class": "WRONG_ORDER"},
        )
    assert resp.status_code == 200
    assert mock_gen.call_args.kwargs["detected_action"] == "WRONG_ORDER"


@pytest.mark.asyncio
async def test_missing_required_field_returns_422(app_client):
    resp = await app_client.post(
        "/api/v1/feedback/from-deviation",
        json={"deviation_class": "MISSING_STEP"},  # no sop_name
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_llm_error_surfaces_as_502(app_client):
    mock_gen = AsyncMock(side_effect=RuntimeError("no api key configured"))
    with patch("src.api.routes.feedback.generate_training_feedback", mock_gen):
        resp = await app_client.post(
            "/api/v1/feedback/from-deviation",
            json={"sop_name": "S", "deviation_class": "MISSING_STEP"},
        )
    assert resp.status_code == 502
    assert "unavailable" in resp.json()["detail"].lower()
