"""
Tests for the Analytics/Reports/Leaderboard enhancements:
  - src/intelligence/scoring.py : severity-weighted accuracy
  - GET /api/v1/analytics/study-groups : per-group metrics + learning curve
  - GET /api/v1/reports/aggregate : deviation_breakdown + severity_totals
  - GET /api/v1/reports/export/csv : honours worker_ids filter

In-memory SQLite via HTTPX AsyncClient (no PostgreSQL needed).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.database.models import (
    Base, DeviationLog, TrainingSessionLog, User, UserRole,
)


# ── Unit: severity-weighted accuracy ────────────────────────────────────────

def test_session_accuracy_weighting():
    from src.intelligence.scoring import session_accuracy
    assert session_accuracy(0, 0) == 100.0
    # high-severity deviations cost more than ordinary ones
    assert session_accuracy(3, 3) < session_accuracy(3, 0)
    # clamped to [0, 100], never negative
    assert session_accuracy(100, 100) == 0.0
    # guard: high capped at total
    assert session_accuracy(2, 5) == session_accuracy(2, 2)


# ── Test app wiring ─────────────────────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture()
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def factory(test_engine):
    return async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)


@pytest_asyncio.fixture()
async def app_client(factory) -> AsyncIterator[AsyncClient]:
    from src.api.routes import analytics as analytics_mod
    from src.api.routes import feedback as feedback_mod
    from src.api.routes import reports as reports_mod
    from src.api.routes.deps import get_current_user, get_db

    async def _override_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def _override_auth():
        return SimpleNamespace(id=1, email="admin@test.com", role=UserRole.admin)

    app = FastAPI()
    app.include_router(analytics_mod.router)
    app.include_router(reports_mod.router)
    app.include_router(feedback_mod.router)
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_auth

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _seed_user(s: AsyncSession, uid: int, email: str) -> None:
    s.add(User(id=uid, email=email, first_name="T", last_name=f"U{uid}",
               password_hash="x", role=UserRole.staff, department="SYNTHETIC"))
    await s.flush()


async def _seed_session(s: AsyncSession, *, uid: int, sop_id: str, dev: int,
                        high: int, when: datetime) -> TrainingSessionLog:
    log = TrainingSessionLog(
        session_id=str(uuid.uuid4()), worker_id=uid, sop_id=sop_id, sop_name=sop_id,
        started_at=when, ended_at=when, duration_seconds=120.0, total_frames=120,
        actual_fps=30.0, deviation_count=dev, high_severity_count=high,
        latency_p95_ms=45.0, latency_target_met=True,
    )
    s.add(log)
    await s.flush()
    return log


# ── /analytics/study-groups ─────────────────────────────────────────────────

async def test_study_groups(app_client, factory):
    async with factory() as s:
        await _seed_user(s, 1, "control.staff.001@synthetic.forge.local")
        await _seed_user(s, 2, "hybrid.staff.001@synthetic.forge.local")
        base = _now()
        # control: high deviations; hybrid: low deviations (hybrid should rank better)
        await _seed_session(s, uid=1, sop_id="a", dev=8, high=3, when=base)
        await _seed_session(s, uid=1, sop_id="a", dev=6, high=2, when=base + timedelta(days=1))
        await _seed_session(s, uid=2, sop_id="a", dev=2, high=0, when=base)
        await _seed_session(s, uid=2, sop_id="a", dev=1, high=0, when=base + timedelta(days=1))
        await s.commit()

    r = await app_client.get("/api/v1/analytics/study-groups")
    assert r.status_code == 200
    data = r.json()
    groups = {g["group"]: g for g in data["groups"]}
    assert "control" in groups and "hybrid" in groups
    # hybrid has fewer deviations → higher accuracy than control
    assert groups["hybrid"]["avg_accuracy"] > groups["control"]["avg_accuracy"]
    assert groups["control"]["worker_count"] == 1
    # learning curve has per-session-index points
    assert any(p["session_seq"] == 2 for p in data["learning_curve"])


# ── /reports/aggregate breakdown ─────────────────────────────────────────────

async def test_reports_breakdown(app_client, factory):
    async with factory() as s:
        await _seed_user(s, 1, "control.staff.001@synthetic.forge.local")
        log = await _seed_session(s, uid=1, sop_id="a", dev=3, high=1, when=_now())
        s.add(DeviationLog(session_log_id=log.id, event_timestamp=1.0,
                           deviation_class="missing_step", severity="high",
                           expected_step_name="s1", model_confidence=0.9))
        s.add(DeviationLog(session_log_id=log.id, event_timestamp=2.0,
                           deviation_class="wrong_order", severity="low",
                           expected_step_name="s2", model_confidence=0.9))
        await s.commit()

    r = await app_client.get("/api/v1/reports/aggregate")
    assert r.status_code == 200
    data = r.json()
    assert "deviation_breakdown" in data and "severity_totals" in data
    assert data["severity_totals"]["high"] == 1
    assert data["severity_totals"]["low"] == 1
    classes = {b["deviation_class"] for b in data["deviation_breakdown"]}
    assert {"missing_step", "wrong_order"} <= classes


# ── /reports/export/csv honours worker_ids ───────────────────────────────────

async def test_csv_filters_by_worker(app_client, factory):
    async with factory() as s:
        await _seed_user(s, 1, "control.staff.001@synthetic.forge.local")
        await _seed_user(s, 2, "hybrid.staff.001@synthetic.forge.local")
        await _seed_session(s, uid=1, sop_id="a", dev=2, high=0, when=_now())
        await _seed_session(s, uid=2, sop_id="a", dev=2, high=0, when=_now())
        await s.commit()

    r = await app_client.get("/api/v1/reports/export/csv", params={"worker_ids": "1"})
    assert r.status_code == 200
    body = r.text
    # only worker 1's row should be present (plus header)
    data_lines = [ln for ln in body.splitlines() if ln.strip()][1:]
    assert data_lines, "expected at least one data row"
    assert all(ln.split(",")[1] == "1" for ln in data_lines)


# ── /analytics/operational-hypotheses ────────────────────────────────────────

async def test_operational_hypotheses(app_client, factory):
    async with factory() as s:
        uid = 0
        # control = high deviations, hybrid/sim/realtime = progressively lower
        plan = {"control": 8, "sim_only": 5, "realtime_only": 3, "hybrid": 1}
        for grp, dev in plan.items():
            for k in range(4):
                uid += 1
                await _seed_user(s, uid, f"{grp}.staff.{k:03d}@synthetic.forge.local")
                await _seed_session(s, uid=uid, sop_id="a", dev=dev, high=0, when=_now())
                await _seed_session(s, uid=uid, sop_id="a", dev=dev + 1, high=0, when=_now())
        await s.commit()

    r = await app_client.get("/api/v1/analytics/operational-hypotheses")
    assert r.status_code == 200
    data = r.json()
    assert data["h1"]["significant"] is True          # control vs hybrid clearly differs
    assert data["h1"]["group_a"]["ci95"] is not None   # CIs present
    assert "h2" in data and data["h2"]["test_name"].startswith("One-way ANOVA")
    assert data["h2"]["tukey_hsd"]


# ── Paired H3 + assumption metadata ──────────────────────────────────────────

def test_paired_h3_and_assumptions():
    from src.evaluation.hypothesis_tester import HypothesisTester
    t = HypothesisTester()
    # same participants: realtime faster than posthoc by a consistent margin
    realtime = [8.0, 9.0, 7.5, 8.5, 9.2, 7.8, 8.1, 8.9]
    posthoc = [r + 3.0 for r in realtime]
    res = t.test_h3(posthoc_times=posthoc, realtime_times=realtime).to_dict()
    assert res["paired"] is True
    assert res["test_name"].startswith("Paired")
    assert res["significant"] is True
    assert res["mean_diff_ci95"] is not None
    # independent test (H1) carries normality + homogeneity metadata
    h1 = t.test_h1([5, 6, 5, 7, 6], [2, 1, 2, 3, 2]).to_dict()
    assert h1["normality"] and h1["homogeneity"]
    assert h1["group_a"]["ci95"] is not None


# ── Emotion summary populated + excluded from deviation analytics ─────────────

async def test_emotion_summary_and_exclusion(app_client, factory):
    from src.database.models import DeviationLog
    async with factory() as s:
        await _seed_user(s, 1, "control.staff.001@synthetic.forge.local")
        log = await _seed_session(s, uid=1, sop_id="a", dev=2, high=1, when=_now())
        # real deviations
        s.add(DeviationLog(session_log_id=log.id, event_timestamp=1.0,
                           deviation_class="missing_step", severity="high",
                           expected_step_name="s1", model_confidence=0.9))
        # emotion rows (must NOT appear in deviation analytics)
        for st in ("stressed", "fatigued", "focused", "focused"):
            s.add(DeviationLog(session_log_id=log.id, event_timestamp=2.0,
                               deviation_class=f"emotion_{st}", severity="low",
                               expected_step_name="", model_confidence=0.7))
        await s.commit()

    es = (await app_client.get("/api/v1/analytics/emotion-summary")).json()
    assert es["emotion_counts"].get("Focused") == 2
    assert es["emotion_counts"].get("Stressed") == 1
    # stress = (stressed+fatigued)/total = 2/4
    assert es["avg_stress_score"] == 0.5

    # Deviation heatmap must exclude emotion_* classes
    hm = (await app_client.get("/api/v1/analytics/deviations/heatmap")).json()
    classes = {row["deviation_class"] for row in hm["heatmap"]}
    assert "missing_step" in classes
    assert not any(c.startswith("emotion_") for c in classes)


# ── Bias audit: multiple departments + relative flagging ─────────────────────

async def _seed_user_dept(s, uid, dept):
    s.add(User(id=uid, email=f"control.staff.{uid:03d}@synthetic.forge.local",
               first_name="T", last_name=f"U{uid}", password_hash="x",
               role=UserRole.staff, department=dept))
    await s.flush()


async def test_bias_audit_relative_flag(app_client, factory):
    async with factory() as s:
        uid = 0
        # Two healthy departments (low deviations) + one biased (high deviations)
        for dept, dev in [("Assembly", 1), ("Packaging", 1), ("Welding", 9)]:
            for _ in range(4):
                uid += 1
                await _seed_user_dept(s, uid, dept)
                await _seed_session(s, uid=uid, sop_id="a", dev=dev, high=0, when=_now())
        await s.commit()

    d = (await app_client.get("/api/v1/analytics/bias-audit")).json()
    assert "cohort_mean" in d and "flag_threshold" in d
    by = {x["department"]: x for x in d["departments"]}
    assert by["Welding"]["flagged"] is True
    assert by["Assembly"]["flagged"] is False


# ── Feedback templates + Template-vs-LLM demo endpoint ───────────────────────

def test_get_template_feedback():
    from src.intelligence.feedback_templates import get_template_feedback
    assert "protective equipment" in get_template_feedback("MISSING_PPE", "x").lower()
    assert "wear_gloves" in get_template_feedback("MISSING_STEP", "wear_gloves")
    # unknown class → safe generic default, never raises
    assert get_template_feedback("NOPE", "step1")


async def test_feedback_demo_resilient(app_client):
    payload = {
        "sop_name": "Test SOP", "deviation_class": "MISSING_PPE",
        "expected_step_name": "wear_gloves", "expected_step_id": 1, "model_confidence": 0.9,
    }
    r = await app_client.post("/api/v1/feedback/demo", json=payload)
    assert r.status_code == 200          # never 502, even with no LLM configured
    d = r.json()
    assert "protective equipment" in d["template_feedback"].lower()
    # no LLM provider configured in the test DB → graceful error, template still returned
    assert d["llm_feedback"] is None
    assert d["llm_error"]
