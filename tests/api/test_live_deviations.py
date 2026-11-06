"""
Test GET /api/v1/ws/live/deviations — the per-user buffer of camera-detected
deviations (with AI feedback) that the session summary collects after a live run.
"""
from __future__ import annotations

from collections import deque
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI


def _app():
    from src.api.routes import live_ws
    from src.api.routes.deps import get_current_user
    app = FastAPI()
    app.include_router(live_ws.router)
    return app, live_ws, get_current_user


@pytest.mark.asyncio
async def test_filters_by_since_and_user():
    app, live_ws, get_current_user = _app()
    live_ws._RECENT_DEVIATIONS["7"] = deque([
        {"timestamp": 100.0, "deviation_class": "missing_step", "severity": "high", "feedback_text": "old"},
        {"timestamp": 200.0, "deviation_class": "unsafe", "severity": "high", "feedback_text": "new"},
    ])
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/v1/ws/live/deviations", params={"since": 150})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1 and data[0]["feedback_text"] == "new"


@pytest.mark.asyncio
async def test_other_user_sees_nothing():
    app, live_ws, get_current_user = _app()
    live_ws._RECENT_DEVIATIONS["7"] = deque([{"timestamp": 200.0, "feedback_text": "x"}])
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=999)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/v1/ws/live/deviations")
    assert r.status_code == 200 and r.json() == []
