"""
Tests for the synthetic database seeder (Phase 5 simulation track).

Uses a private in-memory SQLite engine so the global application engine and any
real database are never touched.  Verifies row creation, SYNTHETIC labelling
(Rules.md §3.1), group-consistent learning curves, idempotent wipe, and the
--if-empty deploy guard.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SETTINGS_ENCRYPTION_KEY", "test-enc-key-32-chars-padded!!")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-for-tests-only!!")

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.database.database import Base
from src.database.models import (
    DeviationLog,
    TrainingSessionLog,
    User,
    UserRole,
    WorkerProfile,
)
from src.evaluation.seed_simulation_data import (
    SYNTHETIC_DEPARTMENT,
    SYNTHETIC_EMAIL_DOMAIN,
    _database_has_sessions,
    seed,
    wipe_synthetic,
)

PER_GROUP = 3  # 4 groups -> 12 synthetic workers; small but exercises every path.


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _count(session, model) -> int:
    result = await session.execute(select(func.count()).select_from(model))
    return result.scalar() or 0


@pytest.mark.asyncio
async def test_seed_populates_all_tables(session):
    totals = await seed(session, per_group=PER_GROUP, seed_value=42)

    # 4 worker groups + 2 trainers + 1 manager
    assert totals["users"] == PER_GROUP * 4 + 3
    assert await _count(session, User) == PER_GROUP * 4 + 3
    assert totals["worker_profiles"] == PER_GROUP * 4
    assert totals["training_session_logs"] > 0
    assert totals["deviation_logs"] >= 0
    assert await _count(session, TrainingSessionLog) == totals["training_session_logs"]
    assert await _count(session, DeviationLog) == totals["deviation_logs"]


@pytest.mark.asyncio
async def test_all_users_are_labelled_synthetic(session):
    await seed(session, per_group=PER_GROUP, seed_value=42)
    users = (await session.execute(select(User))).scalars().all()
    assert users
    for u in users:
        # Synthetic identity is carried by the email domain (used by the wipe).
        assert u.email.endswith(f"@{SYNTHETIC_EMAIL_DOMAIN}")
        # department now holds realistic operational units (staff, for the bias
        # audit) or SYNTHETIC (non-staff) — always populated.
        assert u.department


@pytest.mark.asyncio
async def test_roles_include_trainers_and_managers(session):
    await seed(session, per_group=PER_GROUP, seed_value=42)
    roles = [u.role for u in (await session.execute(select(User))).scalars().all()]
    assert roles.count(UserRole.staff) == PER_GROUP * 4
    assert roles.count(UserRole.trainer) == 2
    assert roles.count(UserRole.manager) == 1


@pytest.mark.asyncio
async def test_deviation_logs_have_what_and_why(session):
    """Rules.md §1.6 — every deviation must explain WHAT and WHY."""
    await seed(session, per_group=PER_GROUP, seed_value=42)
    devs = (await session.execute(select(DeviationLog))).scalars().all()
    assert devs, "expected at least one deviation row"
    for d in devs:
        assert d.what.strip()
        assert d.why.strip()
        assert d.severity in ("low", "medium", "high")


@pytest.mark.asyncio
async def test_group_learning_curve_consistency(session):
    """Control workers should accumulate more deviations than hybrid workers."""
    await seed(session, per_group=8, seed_value=42)

    async def avg_devs(group_prefix: str) -> float:
        result = await session.execute(
            select(func.avg(WorkerProfile.total_deviations))
            .join(User, User.id == WorkerProfile.user_id)
            .where(User.email.like(f"{group_prefix}.%"))
        )
        return float(result.scalar() or 0)

    control_avg = await avg_devs("control")
    hybrid_avg = await avg_devs("hybrid")
    assert control_avg > hybrid_avg, (control_avg, hybrid_avg)


@pytest.mark.asyncio
async def test_wipe_is_idempotent_and_spares_real_data(session):
    # A real (non-synthetic) user must survive the wipe.
    real = User(
        email="real.admin@forge.example",
        first_name="Real",
        last_name="Admin",
        password_hash="x",
        role=UserRole.admin,
        department="Operations",
    )
    session.add(real)
    await session.commit()

    await seed(session, per_group=PER_GROUP, seed_value=42)
    assert await _count(session, TrainingSessionLog) > 0

    counts = await wipe_synthetic(session)
    assert counts["users"] == PER_GROUP * 4 + 3

    # All synthetic rows gone; the real user remains.
    assert await _count(session, WorkerProfile) == 0
    assert await _count(session, TrainingSessionLog) == 0
    assert await _count(session, DeviationLog) == 0
    remaining = (await session.execute(select(User))).scalars().all()
    assert len(remaining) == 1
    assert remaining[0].email == "real.admin@forge.example"

    # Wiping again is a no-op.
    counts2 = await wipe_synthetic(session)
    assert all(v == 0 for v in counts2.values())


@pytest.mark.asyncio
async def test_if_empty_guard(session):
    assert await _database_has_sessions(session) is False
    await seed(session, per_group=PER_GROUP, seed_value=42)
    assert await _database_has_sessions(session) is True


@pytest.mark.asyncio
async def test_seed_is_reproducible(session):
    totals_a = await seed(session, per_group=PER_GROUP, seed_value=42)
    await wipe_synthetic(session)
    totals_b = await seed(session, per_group=PER_GROUP, seed_value=42)
    assert totals_a == totals_b
