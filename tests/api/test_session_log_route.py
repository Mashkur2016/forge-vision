"""
Integration tests for POST /api/v1/session/log — persisting browser-webcam
(WebSocket) live training sessions to the database (Step 4b).

Uses an in-memory SQLite DB via HTTPX AsyncClient — no PostgreSQL needed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.database.models import (
    Base, DeviationLog, SkillLevel, TrainingSessionLog, User, UserRole, WorkerProfile,
)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture()
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def test_session(test_engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture()
async def seeded_user(test_session) -> None:
    """A worker (id=1) with a profile so aggregate updates can be checked."""
    test_session.add(User(
        id=1, email="worker@test.com", first_name="Test", last_name="Worker",
        password_hash="x", role=UserRole.admin, is_active=True,
    ))
    await test_session.flush()
    test_session.add(WorkerProfile(
        user_id=1, skill_level=SkillLevel.competent,
        total_sessions=2, total_deviations=5, total_high_severity=1,
    ))
    await test_session.commit()


@pytest_asyncio.fixture()
async def app_client(test_engine):
    from fastapi import FastAPI
    from src.api.routes import session as session_mod
    from src.api.routes import analytics as analytics_mod
    from src.api.routes.deps import get_current_user, get_db

    factory = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)

    async def _override_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def _override_auth():
        return SimpleNamespace(id=1, email="worker@test.com", role=UserRole.admin)

    test_app = FastAPI()
    test_app.include_router(session_mod.router)
    test_app.include_router(analytics_mod.router)
    test_app.dependency_overrides[get_db] = _override_db
    test_app.dependency_overrides[get_current_user] = _override_auth

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        yield client


def _payload(session_id: str = "abc12345"):
    return {
        "session_id": session_id,
        "sop_id": "lab_safety_v1",
        "sop_name": "Science Laboratory Safety Induction",
        "started_at": datetime(2026, 6, 24, 10, 0, tzinfo=timezone.utc).timestamp(),
        "duration_seconds": 95.0,
        "latency_p95_ms": 240.0,
        "deviations": [
            {"deviation_class": "missing_step", "severity": "high", "timestamp": 1782000000.0,
             "expected_step_name": "Put on goggles", "what": "Skipped PPE", "why": "Eye protection required"},
            {"deviation_class": "wrong_order", "severity": "low", "timestamp": 1782000030.0,
             "expected_step_name": "Label sample", "what": "Out of order", "why": "Sequence matters"},
        ],
    }


@pytest.mark.asyncio
async def test_log_creates_session_and_deviations(app_client, test_session, seeded_user):
    r = await app_client.post("/api/v1/session/log", json=_payload())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "saved"

    row = (await test_session.execute(
        select(TrainingSessionLog).where(TrainingSessionLog.session_id == "abc12345")
    )).scalar_one()
    assert row.worker_id == 1
    assert row.sop_id == "lab_safety_v1"
    assert row.deviation_count == 2
    assert row.high_severity_count == 1
    assert row.latency_target_met is True

    devs = (await test_session.execute(
        select(DeviationLog).where(DeviationLog.session_log_id == row.id)
    )).scalars().all()
    assert len(devs) == 2
    assert {d.deviation_class for d in devs} == {"missing_step", "wrong_order"}


@pytest.mark.asyncio
async def test_log_updates_worker_profile_aggregates(app_client, test_session, seeded_user):
    await app_client.post("/api/v1/session/log", json=_payload("sess0001"))
    prof = (await test_session.execute(
        select(WorkerProfile).where(WorkerProfile.user_id == 1)
    )).scalar_one()
    assert prof.total_sessions == 3          # 2 seeded + 1
    assert prof.total_deviations == 7        # 5 + 2
    assert prof.total_high_severity == 2     # 1 + 1


@pytest.mark.asyncio
async def test_log_is_idempotent(app_client, seeded_user):
    first = await app_client.post("/api/v1/session/log", json=_payload("dup00001"))
    assert first.json()["status"] == "saved"
    second = await app_client.post("/api/v1/session/log", json=_payload("dup00001"))
    assert second.json()["status"] == "exists"


@pytest.mark.asyncio
async def test_drilldown_deviations_returns_iso_timestamp(app_client, seeded_user):
    """The drill-down endpoint must not 500 on the Float event_timestamp column."""
    await app_client.post("/api/v1/session/log", json=_payload("drill001"))
    r = await app_client.get("/api/v1/analytics/sessions/drill001/deviations")
    assert r.status_code == 200, r.text
    devs = r.json()
    assert len(devs) == 2
    # timestamp must be a parseable ISO string (not a crash, not a raw float)
    ts = devs[0]["timestamp"]
    assert isinstance(ts, str)
    datetime.fromisoformat(ts)               # parses without error
    assert {d["deviation_class"] for d in devs} == {"missing_step", "wrong_order"}


@pytest.mark.asyncio
async def test_log_clean_session_zero_deviations(app_client, test_session, seeded_user):
    p = _payload("clean001")
    p["deviations"] = []
    r = await app_client.post("/api/v1/session/log", json=p)
    assert r.status_code == 200
    row = (await test_session.execute(
        select(TrainingSessionLog).where(TrainingSessionLog.session_id == "clean001")
    )).scalar_one()
    assert row.deviation_count == 0
    assert row.high_severity_count == 0
