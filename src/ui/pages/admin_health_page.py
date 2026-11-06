"""
System Health — B15 (admin).

Displays live status of API, DB, LLM plus storage counts. Auto-refresh
optional.
"""
from __future__ import annotations

import time

import streamlit as st
from src.ui.utils import api_get, fmt_datetime


def _get(path: str) -> dict | None:
    return api_get(path)


def _status_card(col, title: str, status: str, meta: str = "") -> None:
    ok_colors = {
        "ok":              ("#DCFCE7", "#166534", "✅"),
        "untested":        ("#FEF3C7", "#92400E", "⚠️"),
        "not_configured":  ("#E0E7FF", "#3730A3", "ℹ️"),
        "error":           ("#FEE2E2", "#991B1B", "❌"),
    }
    bg, fg, icon = ok_colors.get(status, ("#E2E8F0", "#334155", "•"))
    col.markdown(f"""
    <div style="background:{bg};padding:1rem;border-radius:12px;height:140px;">
        <div style="font-size:0.75rem;color:{fg};text-transform:uppercase;
                    letter-spacing:0.05em;font-weight:700;margin-bottom:0.5rem;">
            {title}
        </div>
        <div style="font-size:1.5rem;font-weight:700;color:{fg};">{icon} {status.upper()}</div>
        <div style="font-size:0.8rem;color:{fg};opacity:0.8;margin-top:0.5rem;">{meta}</div>
    </div>
    """, unsafe_allow_html=True)


def render() -> None:

    cc1, cc2 = st.columns([1, 1])
    auto = cc1.toggle("Auto-refresh (30s)", value=False, key="h_auto")
    if cc2.button("🔄 Refresh Now", use_container_width=True):
        st.rerun()

    data = _get("/api/v1/health/detailed")
    if data is None:
        st.error("Cannot reach API — is Docker running?")
        return

    st.caption(f"Report generated at {fmt_datetime(data.get('timestamp'))} UTC")

    st.divider()

    # ── Status cards ──────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    api = data.get("api", {})
    _status_card(c1, "API Backend", api.get("status", "error"),
                 f"Uptime: {int(api.get('uptime_seconds', 0))}s")

    db = data.get("db", {})
    db_meta = f"Query: {db.get('query_time_ms', '—')} ms"
    if db.get("error"):
        db_meta += f"  |  {db['error'][:60]}"
    _status_card(c2, "PostgreSQL DB", db.get("status", "error"), db_meta)

    llm = data.get("llm", {})
    llm_meta = f"{(llm.get('provider') or '—').upper()}  ·  {llm.get('model') or '—'}"
    _status_card(c3, "LLM Provider", llm.get("status", "not_configured"), llm_meta)

    st.divider()

    # ── Active sessions + storage ─────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Active Sessions", data.get("active_sessions", 0))
    storage = data.get("storage", {}) or {}
    m2.metric("SOPs", storage.get("sop_count", 0))
    m3.metric("Sessions (DB)", storage.get("session_count", 0))
    m4.metric("Deviations", storage.get("deviation_count", 0))
    m5.metric("Users", storage.get("user_count", 0))

    st.divider()

    # ── LLM latency history chart ─────────────────────────────────────────
    st.subheader("LLM Latency History")
    st.caption("Recorded on each page refresh — starts empty, populates after the Settings test.")

    llm_status = llm.get("status", "not_configured")
    llm_latency_ms = llm.get("latency_ms")

    # Persist rolling history in session_state (max 60 points)
    if "health_llm_latency_history" not in st.session_state:
        st.session_state["health_llm_latency_history"] = []

    if llm_latency_ms is not None:
        import datetime
        st.session_state["health_llm_latency_history"].append({
            "t": datetime.datetime.utcnow().strftime("%H:%M:%S"),
            "latency_ms": float(llm_latency_ms),
        })
        # Keep last 60 readings
        st.session_state["health_llm_latency_history"] = (
            st.session_state["health_llm_latency_history"][-60:]
        )

    history = st.session_state["health_llm_latency_history"]
    if not history:
        st.info(
            "No LLM latency readings yet. "
            "Go to **⚙️ Settings → Test Connection** to generate the first data point, "
            "then return here and click **Refresh Now**."
        )
    else:
        try:
            import altair as alt
            import pandas as pd

            df = pd.DataFrame(history)
            df.index = range(1, len(df) + 1)
            chart = (
                alt.Chart(df.reset_index().rename(columns={"index": "reading"}))
                .mark_line(point=True, strokeWidth=2, color="#7C3AED")
                .encode(
                    x=alt.X("reading:O", title="Reading #"),
                    y=alt.Y("latency_ms:Q", title="Latency (ms)"),
                    tooltip=["reading", "t", "latency_ms"],
                )
                .properties(height=260, title="LLM Response Latency (ms)")
            )
            st.altair_chart(chart, use_container_width=True)
            avg = sum(r["latency_ms"] for r in history) / len(history)
            st.caption(f"Avg: **{avg:.0f} ms**  ·  Last: **{history[-1]['latency_ms']:.0f} ms**  ·  {len(history)} readings")
        except ImportError:
            st.line_chart([r["latency_ms"] for r in history])

    st.divider()

    with st.expander("Raw health report (debug)"):
        st.json(data)

    # ── Auto-refresh ──────────────────────────────────────────────────────
    if auto:
        time.sleep(30)
        st.rerun()
