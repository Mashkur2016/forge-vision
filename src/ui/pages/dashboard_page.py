"""
Dashboard — B1.

FORGE-Vision home page. Shows quick actions, system status, a live
activity feed of recent sessions and a compact recent-sessions table.
"""
from __future__ import annotations

import concurrent.futures

import httpx
import streamlit as st
from src.ui.utils import _api_base, fmt_datetime


@st.cache_data(ttl=15, show_spinner=False)
def _dashboard_bundle(base: str, token: str) -> dict:
    """Fetch all dashboard data in PARALLEL — previously 5 sequential calls
    (≈ 9.5 s on the cloud DB). Cached 15 s so reruns/quick revisits are instant.
    Runs raw httpx in worker threads with the token passed explicitly (no
    st.session_state access off the main thread)."""
    h = {"Authorization": f"Bearer {token}"} if token else {}

    def g(path, params=None):
        try:
            r = httpx.get(f"{base}{path}", params=params or {}, headers=h, timeout=12.0)
            return r.json() if r.status_code == 200 else None
        except Exception:
            return None

    def liveness():
        try:
            return httpx.get(f"{base}/health", timeout=4.0).status_code == 200
        except Exception:
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        f_api = ex.submit(liveness)
        f_health = ex.submit(g, "/api/v1/health/detailed", {"light": "true"})
        f_summary = ex.submit(g, "/api/v1/analytics/summary")
        f_sessions = ex.submit(g, "/api/v1/analytics/sessions", {"limit": 10, "offset": 0})
        return {
            "api_ok": f_api.result(),
            "health": f_health.result() or {},
            "summary": f_summary.result() or {},
            "sessions": (f_sessions.result() or {}).get("sessions", []),
        }


def _goto(page: str) -> None:
    st.session_state["current_page"] = page
    st.rerun()


def render() -> None:
    # ── Quick actions ──────────────────────────────────────────────────────
    qa1, qa2, qa3 = st.columns(3)
    with qa1:
        if st.button("🎬  Start Session", use_container_width=True, type="primary"):
            _goto("live_training")
    with qa2:
        if st.button("📋  New SOP", use_container_width=True):
            _goto("sop_builder")
    with qa3:
        if st.button("📄  Reports", use_container_width=True):
            _goto("report_generator")

    st.divider()

    # ── Fetch all data once, in parallel (cached 15 s) ────────────────────
    data = _dashboard_bundle(_api_base(), st.session_state.get("access_token", ""))
    api_ok   = data["api_ok"]
    health   = data["health"]
    summary  = data["summary"]
    sessions = data["sessions"]

    # ── System status + Activity feed (2-column) ──────────────────────────
    col_l, col_r = st.columns([2, 3])

    # ---- Left: System Status ----
    with col_l:
        st.subheader("System Status")

        # Status rows
        def _row(label: str, ok: bool, meta: str = "") -> None:
            icon = "✅" if ok else "❌"
            colour = "#166534" if ok else "#991B1B"
            bg = "#DCFCE7" if ok else "#FEE2E2"
            st.markdown(f"""
            <div style="background:{bg};padding:0.55rem 0.9rem;border-radius:8px;
                        margin-bottom:0.4rem;display:flex;justify-content:space-between;
                        align-items:center;">
                <span style="font-weight:700;color:{colour}">{icon} {label}</span>
                <span style="color:{colour};font-size:0.8rem;">{meta}</span>
            </div>
            """, unsafe_allow_html=True)

        _row("API Backend", api_ok, "online" if api_ok else "offline")

        db_st = (health.get("db") or {}).get("status") == "ok"
        db_meta = f"{(health.get('db') or {}).get('query_time_ms', '—')} ms"
        _row("PostgreSQL", db_st, db_meta if db_st else "unreachable")

        llm = health.get("llm") or {}
        llm_ok = llm.get("status") == "ok"
        llm_meta = f"{(llm.get('provider') or '—').upper()}  ·  {llm.get('model') or '—'}"
        _row("LLM Provider", llm_ok, llm_meta)

        st.markdown("<br>", unsafe_allow_html=True)

        # Active sessions + today's stats
        s1, s2 = st.columns(2)
        s1.metric("Active Sessions", health.get("active_sessions", 0))
        s2.metric("Total Sessions", summary.get("total_sessions", 0))

        t1, t2 = st.columns(2)
        t1.metric("Deviations Logged", summary.get("total_deviations", 0))
        t2.metric("High Severity", summary.get("total_high_severity", 0))

    # ---- Right: Live Activity Feed ----
    with col_r:
        st.subheader("Live Activity Feed")

        if not sessions:
            st.info("No activity yet — start a training session to populate this feed.")
        else:
            for s in sessions:
                dev = s.get("deviation_count", 0)
                high = s.get("high_severity_count", 0)
                if high > 0:
                    severity = "🔴 High"
                    border = "#DC2626"
                elif dev > 0:
                    severity = "🟡 Minor"
                    border = "#EAB308"
                else:
                    severity = "🟢 Clean"
                    border = "#16A34A"

                ended = fmt_datetime(s.get("ended_at"))
                sop = s.get("sop_name") or s.get("sop_id") or "—"
                worker = s.get("worker_name") or f"#{s.get('worker_id')}" if s.get("worker_id") else "anon"

                st.markdown(f"""
                <div style="border-left:3px solid {border};padding:0.6rem 0.9rem;
                            background:#F8FAFC;border-radius:6px;margin-bottom:0.4rem;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div>
                            <span style="font-weight:700">{severity}</span>  ·
                            Worker <code>#{worker}</code>  ·  SOP <em>{sop}</em>
                        </div>
                        <div style="font-size:0.75rem;color:#64748B;">{ended}</div>
                    </div>
                    <div style="font-size:0.8rem;color:#475569;margin-top:0.25rem;">
                        {dev} deviation(s)  ·  {round(s.get('duration_seconds', 0), 1)}s  ·
                        p95 {round(s.get('latency_p95_ms', 0), 1)} ms
                    </div>
                </div>
                """, unsafe_allow_html=True)

    st.divider()

    # ── Bottom: Recent sessions table (5) ─────────────────────────────────
    st.subheader("Recent Sessions")
    sessions5 = sessions[:5]   # reuse the feed data — no extra round-trip

    if not sessions5:
        st.caption("—")
    else:
        try:
            import pandas as pd
            rows = [{
                "Session": (s.get("session_id") or "")[:8],
                "Worker": s.get("worker_name") or s.get("worker_id") or "—",
                "SOP": s.get("sop_name") or s.get("sop_id"),
                "Score %": round(max(0.0, 100.0 - s.get("deviation_count", 0) * 10.0), 1),
                "Duration (s)": round(s.get("duration_seconds", 0), 1),
                "Status": "✅" if s.get("latency_target_met") else "⚠",
            } for s in sessions5]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        except ImportError:
            for s in sessions5:
                st.write(s)
