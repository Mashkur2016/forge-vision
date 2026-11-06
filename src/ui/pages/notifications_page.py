"""
Notifications — B13.

Per-user notifications feed with read/unread state and date grouping.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import streamlit as st
from src.ui.utils import api_get, api_post, fmt_datetime


def _get(path: str, params: dict | None = None) -> dict | None:
    return api_get(path, params)


def _post(path: str, params: dict | None = None) -> dict | None:
    return api_post(path, params or {})


def _bucket_of(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return "Older"
    now = datetime.now(timezone.utc)
    today = now.date()
    yesterday = today - timedelta(days=1)
    d = dt.date()
    if d == today:
        return "Today"
    if d == yesterday:
        return "Yesterday"
    return "Older"


_ICONS = {
    "success": "✅",
    "info": "ℹ️",
    "warning": "⚠️",
    "error": "❌",
}


def render() -> None:

    with st.sidebar:
        st.subheader("Viewing")
        user = st.text_input("Username", value=st.session_state.get("nf_user", "default"), key="nf_user")

    # Load notifications
    data = _get("/api/v1/notifications/", params={"user": user})
    if data is None:
        st.warning("Cannot reach API — is Docker running?")
        return

    items = data.get("items", [])
    unread = data.get("unread_count", 0)

    top_l, top_r = st.columns([3, 1])
    top_l.caption(f"**{unread}** unread  ·  **{len(items)}** total")
    with top_r:
        if st.button("Mark all read", use_container_width=True, disabled=unread == 0):
            _post("/api/v1/notifications/read-all", params={"user": user})
            st.rerun()

    st.divider()

    if not items:
        st.success("📭 No notifications — you're all caught up!")
        return

    # Group by bucket
    buckets: dict[str, list[dict]] = {"Today": [], "Yesterday": [], "Older": []}
    for n in items:
        buckets[_bucket_of(n.get("created_at", ""))].append(n)

    for label in ("Today", "Yesterday", "Older"):
        rows = buckets[label]
        if not rows:
            continue
        st.markdown(f"### {label}")
        for n in rows:
            read = n.get("read", False)
            icon = _ICONS.get(n.get("type", "info"), "•")
            bg = "#F8FAFC" if read else "#EFF6FF"
            border = "#E2E8F0" if read else "#2563EB"

            c1, c2 = st.columns([8, 1])
            with c1:
                st.markdown(f"""
                <div style="background:{bg};border-left:4px solid {border};
                            padding:0.75rem 1rem;border-radius:8px;margin-bottom:0.4rem;">
                    <div style="font-weight:{'500' if read else '700'};">
                        {icon} {n.get('message')}
                    </div>
                    <div style="font-size:0.75rem;color:#64748B;margin-top:0.25rem;">
                        {fmt_datetime(n.get('created_at'))}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with c2:
                if not read:
                    if st.button("✓", key=f"nf_read_{n['id']}", help="Mark as read"):
                        _post(f"/api/v1/notifications/{n['id']}/read", params={"user": user})
                        st.rerun()
