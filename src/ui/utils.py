"""Shared UI utilities for FORGE-Vision Streamlit pages."""
from __future__ import annotations

import streamlit as st
import httpx


# ── API base URL ───────────────────────────────────────────────────────────

def _api_base() -> str:
    return st.session_state.get("api_base_url", "http://localhost:8000")


def _headers() -> dict:
    token = st.session_state.get("access_token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


# ── HTTP helpers ───────────────────────────────────────────────────────────

def api_get(path: str, params: dict | None = None) -> dict | list | None:
    try:
        with httpx.Client(timeout=8.0) as c:
            r = c.get(f"{_api_base()}{path}", params=params or {}, headers=_headers())
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


@st.cache_data(ttl=20, show_spinner=False)
def _cached_get(base: str, path: str, params_key: tuple, token: str):
    """Cached GET. Keyed on (base, path, params, token) so the cache is per-user
    and never serves one account's data to another. 20 s TTL keeps read-heavy
    dashboard pages from re-fetching on every Streamlit rerun (each navigation /
    widget interaction re-runs the whole script), which is the main source of the
    navigation lag. Failures return None and are not worth special-casing."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        with httpx.Client(timeout=8.0) as c:
            r = c.get(f"{base}{path}", params=dict(params_key), headers=headers)
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


def api_get_cached(path: str, params: dict | None = None) -> dict | list | None:
    """Short-TTL cached variant of :func:`api_get` for read-only dashboard data."""
    params_key = tuple(sorted((params or {}).items()))
    return _cached_get(_api_base(), path, params_key, st.session_state.get("access_token", ""))


def api_post(path: str, payload: dict, timeout: float = 10.0) -> dict | None:
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(f"{_api_base()}{path}", json=payload, headers=_headers())
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


def api_patch(path: str, payload: dict) -> dict | None:
    try:
        with httpx.Client(timeout=10.0) as c:
            r = c.patch(f"{_api_base()}{path}", json=payload, headers=_headers())
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


def api_delete(path: str) -> bool:
    try:
        with httpx.Client(timeout=8.0) as c:
            r = c.delete(f"{_api_base()}{path}", headers=_headers())
            r.raise_for_status()
            return True
    except Exception:
        return False


# ── Date formatting ────────────────────────────────────────────────────────

def fmt_date(iso: str | None) -> str:
    """Format ISO date string YYYY-MM-DD → DD/MM/YYYY."""
    if not iso or len(iso) < 10:
        return "—"
    try:
        y, m, d = iso[:10].split("-")
        return f"{d}/{m}/{y}"
    except Exception:
        return iso[:10]


def fmt_datetime(iso: str | None) -> str:
    """Format ISO datetime string → DD/MM/YYYY HH:MM:SS."""
    if not iso or len(iso) < 10:
        return "—"
    try:
        date_part = iso[:10]
        y, m, d = date_part.split("-")
        time_part = iso[11:19] if len(iso) >= 19 else "00:00:00"
        return f"{d}/{m}/{y} {time_part}"
    except Exception:
        return iso[:19].replace("T", " ")


def fmt_step_name(name: str) -> str:
    """Format snake_case step name to Title Case (e.g. 'check_room_booking' → 'Check Room Booking')."""
    if not name:
        return "—"
    return " ".join(word.capitalize() for word in name.split("_"))


def fmt_ppe_name(name: str) -> str:
    """Format snake_case PPE name to Title Case (e.g. 'hair_net' → 'Hair Net')."""
    if not name:
        return "—"
    return " ".join(word.capitalize() for word in name.split("_"))


def fmt_object_name(name: str) -> str:
    """Format snake_case object name to Title Case (e.g. 'projector_remote' → 'Projector Remote')."""
    if not name:
        return "—"
    return " ".join(word.capitalize() for word in name.split("_"))
