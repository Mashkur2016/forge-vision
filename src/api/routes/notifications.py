"""
Notifications API Routes.

Simple in-memory per-user notification store for the prototype UI.
Pre-populated with a few sample notifications on first access.

Endpoints:
    GET  /api/v1/notifications/          — list notifications for ?user=<username>
    POST /api/v1/notifications/{id}/read — mark a single notification as read
    POST /api/v1/notifications/read-all  — mark all as read for the user
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


# ── In-memory store ────────────────────────────────────────────────────────
# { username: [ {id, type, message, read, created_at}, ... ] }
_STORE: dict[str, list[dict[str, Any]]] = {}
_NEXT_ID = {"value": 1}


def _seed(username: str) -> None:
    if username in _STORE:
        return
    now = datetime.now(timezone.utc)
    samples = [
        {
            "id": _NEXT_ID["value"],
            "type": "success",
            "message": "Phase 2 training complete — model saved to models/ directory.",
            "read": False,
            "created_at": (now - timedelta(minutes=15)).isoformat(),
        },
        {
            "id": _NEXT_ID["value"] + 1,
            "type": "info",
            "message": "New SOP available: 'Fire Safety Check v1' — ready to use for training.",
            "read": False,
            "created_at": (now - timedelta(hours=2)).isoformat(),
        },
        {
            "id": _NEXT_ID["value"] + 2,
            "type": "info",
            "message": "System health OK — API, database and LLM all reachable.",
            "read": True,
            "created_at": (now - timedelta(days=1)).isoformat(),
        },
    ]
    _NEXT_ID["value"] += 3
    _STORE[username] = samples


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/")
async def list_notifications(
    user: str = Query(default="default", description="Username to load notifications for"),
) -> dict[str, Any]:
    """Return notifications for the given user (seeded on first request)."""
    _seed(user)
    items = sorted(_STORE[user], key=lambda n: n["created_at"], reverse=True)
    unread = sum(1 for n in items if not n["read"])
    return {"user": user, "unread_count": unread, "items": items}


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    user: str = Query(default="default"),
) -> dict[str, Any]:
    _seed(user)
    for n in _STORE[user]:
        if n["id"] == notification_id:
            n["read"] = True
            return {"ok": True, "id": notification_id}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")


@router.post("/read-all")
async def mark_all_read(user: str = Query(default="default")) -> dict[str, Any]:
    _seed(user)
    count = 0
    for n in _STORE[user]:
        if not n["read"]:
            n["read"] = True
            count += 1
    return {"ok": True, "marked": count}


def push_notification(
    user: str,
    message: str,
    notif_type: str = "info",
) -> dict[str, Any]:
    """
    Public helper — allow other modules to push a notification.
    """
    _seed(user)
    entry = {
        "id": _NEXT_ID["value"],
        "type": notif_type,
        "message": message,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _NEXT_ID["value"] += 1
    _STORE[user].append(entry)
    return entry
