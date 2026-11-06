"""
Integration tests for /api/v1/workers/* routes — Phase 4, Task 4.3.

Uses an in-memory SQLite database via HTTPX AsyncClient.

Tests cover:
  - GET  /api/v1/workers         — empty list; populated list; pagination
  - GET  /api/v1/workers/{id}/profile — 404 if no user; 404 if no profile; success
  - POST /api/v1/workers/{id}/profile — create on first call; update on second call
  - GET  /api/v1/workers/{id}/sessions — empty; populated; pagination
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
    from fastapi import FastAPI
    from src.api.routes import worker as worker_router_mod
    from src.api.routes.deps import get_db

    factory = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)

    async def _override_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    from src.api.routes.deps import get_current_user
    from src.database.models import UserRole
    from types import SimpleNamespace

    def _override_auth():
        return SimpleNamespace(id=1, email="test@test.com", role=UserRole.admin)

    test_app = FastAPI()
    test_app.include_router(worker_router_mod.router)
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
        first_name="Alice",
        last_name=f"Smith{user_id}",
        password_hash="hashed",
        role=UserRole.staff,
    )
    session.add(user)
    await session.flush()
    return user


async def _seed_profile(session: AsyncSession, user_id: int = 1, **kwargs) -> WorkerProfile:
    defaults = dict(skill_level=SkillLevel.beginner)
    defaults.update(kwargs)
    profile = WorkerProfile(user_id=user_id, **defaults)
    session.add(profile)
    await session.flush()
    return profile


async def _seed_session(
    session: AsyncSession,
    worker_id: int = 1,
    sop_id: str = "sop_001",
) -> TrainingSessionLog:
    log = TrainingSessionLog(
        session_id=str(uuid.uuid4()),
        worker_id=worker_id,
        sop_id=sop_id,
        sop_name="Test SOP",
        started_at=_now(),
        ended_at=_now(),
        duration_seconds=60.0,
        total_frames=60,
        actual_fps=30.0,
        deviation_count=2,
        high_severity_count=0,
        latency_p95_ms=30.0,
        latency_target_met=True,
    )
    session.add(log)
    await session.flush()
    return log


# ── GET /api/v1/workers ───────────────────────────────────────────────────────

async def test_list_workers_empty(app_client):
    r = await app_client.get("/api/v1/workers")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["workers"] == []


async def test_list_workers_with_profile(app_client, test_session):
    await _seed_user(test_session, user_id=1)
    await _seed_profile(test_session, user_id=1)
    await test_session.commit()

    r = await app_client.get("/api/v1/workers")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert len(data["workers"]) == 1
    assert data["workers"][0]["worker_id"] == 1


async def test_list_workers_excludes_users_without_profile(app_client, test_session):
    # User 1 has a profile, user 2 does not
    await _seed_user(test_session, user_id=1)
    await _seed_user(test_session, user_id=2)
    await _seed_profile(test_session, user_id=1)
    await test_session.commit()

    r = await app_client.get("/api/v1/workers")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1


async def test_list_workers_pagination(app_client, test_session):
    for i in range(1, 6):
        await _seed_user(test_session, user_id=i)
        await _seed_profile(test_session, user_id=i)
    await test_session.commit()

    r = await app_client.get("/api/v1/workers", params={"limit": 2, "offset": 0})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 5
    assert len(data["workers"]) == 2


# ── GET /api/v1/workers/{id}/profile ─────────────────────────────────────────

async def test_get_profile_user_not_found(app_client):
    r = await app_client.get("/api/v1/workers/9999/profile")
    assert r.status_code == 404


async def test_get_profile_no_profile_row(app_client, test_session):
    await _seed_user(test_session)
    await test_session.commit()

    r = await app_client.get("/api/v1/workers/1/profile")
    assert r.status_code == 404
    assert "profile" in r.json()["detail"].lower()


async def test_get_profile_success(app_client, test_session):
    await _seed_user(test_session)
    await _seed_profile(test_session, skill_level=SkillLevel.developing)
    await test_session.commit()

    r = await app_client.get("/api/v1/workers/1/profile")
    assert r.status_code == 200
    data = r.json()
    assert data["worker_id"] == 1
    assert data["skill_level"] == "developing"
    assert data["name"] == "Alice Smith1"


async def test_get_profile_response_keys(app_client, test_session):
    await _seed_user(test_session)
    await _seed_profile(test_session)
    await test_session.commit()

    r = await app_client.get("/api/v1/workers/1/profile")
    assert r.status_code == 200
    data = r.json()
    expected_keys = {
        "worker_id", "name", "email", "skill_level", "department",
        "employee_id", "total_sessions", "total_deviations",
        "total_high_severity", "last_session_at", "sessions_to_competency_est",
        "trainer_notes", "created_at", "updated_at",
    }
    assert expected_keys.issubset(data.keys())


# ── POST /api/v1/workers/{id}/profile ────────────────────────────────────────

async def test_upsert_profile_user_not_found(app_client):
    r = await app_client.post(
        "/api/v1/workers/9999/profile",
        json={"skill_level": "beginner"},
    )
    assert r.status_code == 404


async def test_upsert_profile_invalid_skill_level(app_client, test_session):
    await _seed_user(test_session)
    await test_session.commit()

    r = await app_client.post(
        "/api/v1/workers/1/profile",
        json={"skill_level": "expert_wizard"},
    )
    assert r.status_code == 422


async def test_upsert_profile_creates_new(app_client, test_session):
    await _seed_user(test_session)
    await test_session.commit()

    r = await app_client.post(
        "/api/v1/workers/1/profile",
        json={"skill_level": "developing", "department": "Assembly"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["skill_level"] == "developing"
    assert data["department"] == "Assembly"


async def test_upsert_profile_updates_existing(app_client, test_session):
    await _seed_user(test_session)
    await _seed_profile(test_session, skill_level=SkillLevel.beginner)
    await test_session.commit()

    r = await app_client.post(
        "/api/v1/workers/1/profile",
        json={"skill_level": "competent", "trainer_notes": "Good progress"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["skill_level"] == "competent"
    assert data["trainer_notes"] == "Good progress"


async def test_upsert_profile_partial_update_preserves_fields(app_client, test_session):
    """Omitting optional fields should not overwrite existing values."""
    await _seed_user(test_session)
    await _seed_profile(
        test_session,
        skill_level=SkillLevel.beginner,
        department="Welding",
        employee_id="EMP001",
    )
    await test_session.commit()

    # Only update skill level — department and employee_id should be unchanged
    r = await app_client.post(
        "/api/v1/workers/1/profile",
        json={"skill_level": "developing"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["skill_level"] == "developing"
    assert data["employee_id"] == "EMP001"


async def test_upsert_all_skill_levels(app_client, test_session):
    """All four valid skill levels must be accepted."""
    await _seed_user(test_session)
    await test_session.commit()

    for level in ("beginner", "developing", "competent", "proficient"):
        r = await app_client.post(
            "/api/v1/workers/1/profile",
            json={"skill_level": level},
        )
        assert r.status_code == 200, f"Failed for skill_level={level}: {r.text}"
        assert r.json()["skill_level"] == level


# ── GET /api/v1/workers/{id}/sessions ────────────────────────────────────────

async def test_worker_sessions_empty(app_client):
    r = await app_client.get("/api/v1/workers/1/sessions")
    assert r.status_code == 200
    data = r.json()
    assert data["worker_id"] == 1
    assert data["total"] == 0
    assert data["sessions"] == []


async def test_worker_sessions_returns_rows(app_client, test_session):
    await _seed_user(test_session)
    await _seed_session(test_session, worker_id=1, sop_id="sop_a")
    await _seed_session(test_session, worker_id=1, sop_id="sop_b")
    await test_session.commit()

    r = await app_client.get("/api/v1/workers/1/sessions")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert len(data["sessions"]) == 2


async def test_worker_sessions_isolation(app_client, test_session):
    """Sessions for worker 1 must not appear under worker 2."""
    await _seed_user(test_session, user_id=1)
    await _seed_user(test_session, user_id=2)
    await _seed_session(test_session, worker_id=1)
    await _seed_session(test_session, worker_id=1)
    await _seed_session(test_session, worker_id=2)
    await test_session.commit()

    r = await app_client.get("/api/v1/workers/2/sessions")
    assert r.status_code == 200
    assert r.json()["total"] == 1


async def test_worker_sessions_response_keys(app_client, test_session):
    await _seed_user(test_session)
    await _seed_session(test_session)
    await test_session.commit()

    r = await app_client.get("/api/v1/workers/1/sessions")
    assert r.status_code == 200
    session_row = r.json()["sessions"][0]
    expected_keys = {
        "id", "session_id", "sop_id", "sop_name",
        "started_at", "ended_at", "duration_seconds",
        "deviation_count", "high_severity_count",
        "latency_p95_ms", "latency_target_met",
    }
    assert expected_keys.issubset(session_row.keys())


async def test_worker_sessions_pagination(app_client, test_session):
    await _seed_user(test_session)
    for _ in range(5):
        await _seed_session(test_session)
    await test_session.commit()

    r = await app_client.get("/api/v1/workers/1/sessions", params={"limit": 2, "offset": 2})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 5
    assert len(data["sessions"]) == 2
