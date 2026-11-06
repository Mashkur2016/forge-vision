"""
Integration tests for /api/v1/analytics/* routes — Phase 4, Task 4.1.

Uses an in-memory SQLite database via HTTPX AsyncClient so no real
PostgreSQL is needed.  The database is created fresh for each test.

Tests cover:
  - GET /api/v1/analytics/summary — empty DB and populated DB
  - GET /api/v1/analytics/sessions — pagination and filters
  - GET /api/v1/analytics/worker/{id} — existing and missing worker
  - GET /api/v1/analytics/sop/{sop_id} — existing and missing SOP
  - GET /api/v1/analytics/competency/{id} — < 2 sessions and ≥ 2 sessions
  - GET /api/v1/analytics/deviations/heatmap — empty and populated
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.database.models import (
    Base,
    DeviationLog,
    SkillLevel,
    TrainingSessionLog,
    User,
    UserRole,
    WorkerProfile,
)


# ── In-memory test DB ─────────────────────────────────────────────────────────

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
async def app_client(test_engine):
    """HTTPX AsyncClient wired to a test FastAPI app using SQLite."""
    from fastapi import FastAPI
    from src.api.routes import analytics as analytics_router_mod

    # Override the DB dependency
    from sqlalchemy.ext.asyncio import AsyncSession
    factory = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)

    async def _override_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    from src.api.routes.deps import get_current_user, get_db
    from src.database.models import UserRole
    from types import SimpleNamespace

    def _override_auth():
        return SimpleNamespace(id=1, email="test@test.com", role=UserRole.admin)

    test_app = FastAPI()
    test_app.include_router(analytics_router_mod.router)
    test_app.dependency_overrides[get_db] = _override_db
    test_app.dependency_overrides[get_current_user] = _override_auth

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        yield client


# ── Seed helpers ──────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _seed_user(session: AsyncSession, user_id: int = 1) -> User:
    user = User(
        id=user_id,
        email=f"worker{user_id}@test.com",
        first_name="Test",
        last_name=f"Worker{user_id}",
        password_hash="hashed",
        role=UserRole.staff,
    )
    session.add(user)
    await session.flush()
    return user


async def _seed_profile(session: AsyncSession, user_id: int = 1) -> WorkerProfile:
    profile = WorkerProfile(user_id=user_id, skill_level=SkillLevel.beginner)
    session.add(profile)
    await session.flush()
    return profile


async def _seed_session(
    session: AsyncSession,
    *,
    worker_id: int = 1,
    sop_id: str = "sop_001",
    sop_name: str = "Test SOP",
    deviation_count: int = 3,
    high_severity_count: int = 1,
    duration_seconds: float = 120.0,
    latency_p95_ms: float = 45.0,
    latency_target_met: bool = True,
) -> TrainingSessionLog:
    log = TrainingSessionLog(
        session_id=str(uuid.uuid4()),
        worker_id=worker_id,
        sop_id=sop_id,
        sop_name=sop_name,
        started_at=_now(),
        ended_at=_now(),
        duration_seconds=duration_seconds,
        total_frames=120,
        actual_fps=30.0,
        deviation_count=deviation_count,
        high_severity_count=high_severity_count,
        latency_p95_ms=latency_p95_ms,
        latency_target_met=latency_target_met,
    )
    session.add(log)
    await session.flush()
    return log


async def _seed_deviation(
    session: AsyncSession,
    *,
    session_log_id: int,
    deviation_class: str = "SEQUENCE_ERROR",
    severity: str = "high",
) -> DeviationLog:
    dev = DeviationLog(
        session_log_id=session_log_id,
        event_timestamp=1000.0,
        deviation_class=deviation_class,
        severity=severity,
        expected_step_name="Step 1",
        model_confidence=0.9,
        what="Wrong step",
        why="Out of order",
    )
    session.add(dev)
    await session.flush()
    return dev


# ── /summary ──────────────────────────────────────────────────────────────────

async def test_summary_empty_db(app_client):
    r = await app_client.get("/api/v1/analytics/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["total_sessions"] == 0
    assert data["total_deviations"] == 0
    assert data["active_workers"] == 0


async def test_summary_with_sessions(app_client, test_session):
    await _seed_user(test_session)
    await _seed_session(test_session, deviation_count=5, high_severity_count=2)
    await _seed_session(test_session, deviation_count=3, high_severity_count=0)
    await test_session.commit()

    r = await app_client.get("/api/v1/analytics/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["total_sessions"] == 2
    assert data["total_deviations"] == 8
    assert data["total_high_severity"] == 2
    assert data["active_workers"] == 1


# ── /sessions ─────────────────────────────────────────────────────────────────

async def test_sessions_empty(app_client):
    r = await app_client.get("/api/v1/analytics/sessions")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["sessions"] == []


async def test_sessions_returns_rows(app_client, test_session):
    await _seed_user(test_session)
    await _seed_session(test_session, sop_id="sop_a")
    await _seed_session(test_session, sop_id="sop_b")
    await test_session.commit()

    r = await app_client.get("/api/v1/analytics/sessions")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert len(data["sessions"]) == 2


async def test_sessions_filter_by_worker(app_client, test_session):
    await _seed_user(test_session, user_id=1)
    await _seed_user(test_session, user_id=2)
    await _seed_session(test_session, worker_id=1)
    await _seed_session(test_session, worker_id=2)
    await test_session.commit()

    r = await app_client.get("/api/v1/analytics/sessions", params={"worker_id": 1})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["sessions"][0]["worker_id"] == 1


async def test_sessions_filter_by_sop(app_client, test_session):
    await _seed_user(test_session)
    await _seed_session(test_session, sop_id="alpha")
    await _seed_session(test_session, sop_id="beta")
    await test_session.commit()

    r = await app_client.get("/api/v1/analytics/sessions", params={"sop_id": "alpha"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["sessions"][0]["sop_id"] == "alpha"


async def test_sessions_pagination(app_client, test_session):
    await _seed_user(test_session)
    for _ in range(5):
        await _seed_session(test_session)
    await test_session.commit()

    r = await app_client.get("/api/v1/analytics/sessions", params={"limit": 2, "offset": 0})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 5
    assert len(data["sessions"]) == 2


# ── /worker/{id} ──────────────────────────────────────────────────────────────

async def test_worker_analytics_not_found(app_client):
    r = await app_client.get("/api/v1/analytics/worker/9999")
    assert r.status_code == 404


async def test_worker_analytics_no_profile(app_client, test_session):
    await _seed_user(test_session)
    await test_session.commit()

    r = await app_client.get("/api/v1/analytics/worker/1")
    assert r.status_code == 200
    data = r.json()
    assert data["worker_id"] == 1
    assert data["session_trend"] == []


async def test_worker_analytics_with_sessions(app_client, test_session):
    await _seed_user(test_session)
    await _seed_profile(test_session)
    for i in range(4):
        await _seed_session(test_session, deviation_count=10 - i * 2)
    await test_session.commit()

    r = await app_client.get("/api/v1/analytics/worker/1")
    assert r.status_code == 200
    data = r.json()
    assert len(data["session_trend"]) == 4
    # Improvement rate should be computed (4 sessions ≥ 3)
    assert data["improvement_rate_pct"] is not None


# ── /sop/{sop_id} ─────────────────────────────────────────────────────────────

async def test_sop_analytics_not_found(app_client):
    r = await app_client.get("/api/v1/analytics/sop/nonexistent_sop")
    assert r.status_code == 404


async def test_sop_analytics_returns_stats(app_client, test_session):
    await _seed_user(test_session)
    log = await _seed_session(test_session, sop_id="sop_test", deviation_count=3)
    await _seed_deviation(test_session, session_log_id=log.id, deviation_class="SKIP")
    await _seed_deviation(test_session, session_log_id=log.id, deviation_class="SEQUENCE_ERROR")
    await test_session.commit()

    r = await app_client.get("/api/v1/analytics/sop/sop_test")
    assert r.status_code == 200
    data = r.json()
    assert data["sop_id"] == "sop_test"
    assert data["total_sessions"] == 1
    assert "deviation_breakdown" in data
    assert "most_problematic_steps" in data


# ── /competency/{id} ──────────────────────────────────────────────────────────

async def test_competency_too_few_sessions(app_client, test_session):
    await _seed_user(test_session)
    await _seed_session(test_session)
    await test_session.commit()

    r = await app_client.get("/api/v1/analytics/competency/1")
    assert r.status_code == 200
    data = r.json()
    assert data["sessions_completed"] == 1
    assert data["sessions_to_competency_est"] is None
    assert "2 sessions" in data["message"]


async def test_competency_with_enough_sessions(app_client, test_session):
    await _seed_user(test_session)
    for dev in [30, 22, 18, 14, 10]:
        await _seed_session(
            test_session, deviation_count=dev, duration_seconds=300.0
        )
    await test_session.commit()

    r = await app_client.get("/api/v1/analytics/competency/1")
    assert r.status_code == 200
    data = r.json()
    assert data["sessions_completed"] == 5
    assert "trend" in data
    assert "smoothed_rate" in data


# ── /deviations/heatmap ───────────────────────────────────────────────────────

async def test_heatmap_empty(app_client):
    r = await app_client.get("/api/v1/analytics/deviations/heatmap")
    assert r.status_code == 200
    data = r.json()
    assert data["heatmap"] == []


async def test_heatmap_populated(app_client, test_session):
    await _seed_user(test_session)
    log = await _seed_session(test_session)
    await _seed_deviation(
        test_session, session_log_id=log.id, deviation_class="SKIP", severity="high"
    )
    await _seed_deviation(
        test_session, session_log_id=log.id, deviation_class="SKIP", severity="low"
    )
    await _seed_deviation(
        test_session, session_log_id=log.id, deviation_class="SEQUENCE_ERROR", severity="high"
    )
    await test_session.commit()

    r = await app_client.get("/api/v1/analytics/deviations/heatmap")
    assert r.status_code == 200
    data = r.json()
    heatmap = data["heatmap"]
    classes = {row["deviation_class"] for row in heatmap}
    assert "SKIP" in classes
    assert "SEQUENCE_ERROR" in classes


async def test_heatmap_sop_filter(app_client, test_session):
    await _seed_user(test_session)
    log_a = await _seed_session(test_session, sop_id="sop_a")
    log_b = await _seed_session(test_session, sop_id="sop_b")
    await _seed_deviation(
        test_session, session_log_id=log_a.id, deviation_class="TYPE_A", severity="high"
    )
    await _seed_deviation(
        test_session, session_log_id=log_b.id, deviation_class="TYPE_B", severity="low"
    )
    await test_session.commit()

    r = await app_client.get(
        "/api/v1/analytics/deviations/heatmap", params={"sop_id": "sop_a"}
    )
    assert r.status_code == 200
    data = r.json()
    classes = {row["deviation_class"] for row in data["heatmap"]}
    assert "TYPE_A" in classes
    assert "TYPE_B" not in classes
