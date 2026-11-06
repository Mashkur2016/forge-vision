"""
Session History — B6.

Paginated browsable history of all training sessions with filters,
per-session deviation drill-down and CSV export.
"""
from __future__ import annotations

import streamlit as st
from src.ui.utils import api_get, fmt_datetime


def _get(path: str, params: dict | None = None) -> dict | list | None:
    return api_get(path, params)


def render() -> None:

    # ── Filters ────────────────────────────────────────────────────────────
    with st.form("sh_filters"):
        f1, f2, f3, f4 = st.columns(4)
        with f1:
            worker_id = st.number_input("Worker ID (0 = all)", min_value=0, value=0, step=1)
        with f2:
            sop_id = st.text_input("SOP ID (blank = all)")
        with f3:
            start_date = st.date_input("Start date", value=None)
        with f4:
            end_date = st.date_input("End date", value=None)

        col_ps, col_btn = st.columns([3, 1])
        with col_ps:
            page_size = st.selectbox("Rows per page", [20, 50, 100], index=0)
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Search", use_container_width=True, type="primary")

    # Reset to page 0 whenever the user submits new filters
    if submitted:
        st.session_state["sh_page"] = 0

    if "sh_page" not in st.session_state:
        st.session_state["sh_page"] = 0

    # ── API fetch ──────────────────────────────────────────────────────────
    params: dict = {"limit": page_size, "offset": st.session_state["sh_page"] * page_size}
    if worker_id > 0:
        params["worker_id"] = worker_id
    if sop_id.strip():
        params["sop_id"] = sop_id.strip()

    data = _get("/api/v1/analytics/sessions", params=params)
    if data is None:
        st.warning("Cannot reach API — is Docker running?")
        return

    sessions = data.get("sessions", []) if isinstance(data, dict) else []
    total    = data.get("total", 0)   if isinstance(data, dict) else 0

    # Client-side date filtering (API doesn't support it directly)
    if start_date or end_date:
        def _in_range(s: dict) -> bool:
            day = (s.get("ended_at", "") or "")[:10]
            if start_date and day < str(start_date):
                return False
            if end_date and day > str(end_date):
                return False
            return True
        sessions = [s for s in sessions if _in_range(s)]

    # ── KPIs ───────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Sessions", total)
    c2.metric("Shown on this page", len(sessions))
    c3.metric("Total Deviations (page)", sum(s.get("deviation_count", 0) for s in sessions))

    st.divider()

    # ── Empty state ────────────────────────────────────────────────────────
    if not sessions:
        st.info(
            "No sessions match the filters.\n\n"
            "**To create your first session:** go to **Live Training**, start a session, "
            "perform some actions in front of the camera, then click Stop. "
            "The session will appear here automatically."
        )

    else:
        # ── Table ──────────────────────────────────────────────────────────
        try:
            import pandas as pd
            rows = []
            for s in sessions:
                devs = s.get("deviation_count", 0)
                acc  = max(0.0, 100.0 - devs * 10.0)
                rows.append({
                    "Session ID":    s.get("session_id", "")[:8],
                    "Worker":        s.get("worker_id") or "—",
                    "SOP":           s.get("sop_name", s.get("sop_id", "")),
                    "Score %":       round(acc, 1),
                    "Duration (s)":  round(s.get("duration_seconds", 0), 1),
                    "Deviations":    devs,
                    "High Severity": s.get("high_severity_count", 0),
                    "Status":        "✅ OK" if s.get("latency_target_met") else "⚠ Over latency",
                    "Started":       fmt_datetime(s.get("started_at")),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        except ImportError:
            st.caption("Install pandas to view the table.")

        # ── Deviation Drill-Down ───────────────────────────────────────────
        st.markdown("#### Deviation Drill-Down")
        st.caption("Select any session from the list below to inspect its individual deviations.")

        session_labels = {
            f"{s.get('session_id','')[:8]}  —  {s.get('sop_id','')}  ({fmt_datetime(s.get('started_at'))})": s
            for s in sessions
        }
        picked = st.selectbox("Select session", list(session_labels.keys()), key="sh_pick")

        if picked:
            session    = session_labels[picked]
            session_id = session.get("session_id", "")

            with st.expander(f"Deviations — session {session_id[:8]}", expanded=True):
                devs = _get(f"/api/v1/analytics/sessions/{session_id}/deviations")

                if devs is None:
                    st.warning(
                        "Could not load deviations. "
                        "The API may not have data for this session yet."
                    )
                elif len(devs) == 0:
                    st.success("No deviations recorded for this session — perfect execution!")
                else:
                    st.caption(f"{len(devs)} deviation(s) recorded")
                    try:
                        import pandas as pd
                        df = pd.DataFrame(devs)
                        if "timestamp" in df.columns:
                            df["time"] = pd.to_datetime(df["timestamp"]).dt.strftime("%H:%M:%S")
                        display_cols = ["time", "deviation_class", "severity",
                                        "expected_step", "confidence", "what", "why"]
                        present = [c for c in display_cols if c in df.columns]
                        df = df[present]
                        df.columns = [c.replace("_", " ").title() for c in present]
                        st.dataframe(df, use_container_width=True, hide_index=True)
                    except ImportError:
                        for d in devs:
                            st.write(d)

    # ── Pagination ─────────────────────────────────────────────────────────
    total_pages = max((total - 1) // page_size + 1, 1)
    p1, p2, p3 = st.columns([1, 3, 1])
    with p1:
        if st.button("◀ Previous", disabled=st.session_state["sh_page"] == 0, key="sh_prev"):
            st.session_state["sh_page"] -= 1
            st.rerun()
    with p2:
        st.caption(f"Page {st.session_state['sh_page'] + 1} of {total_pages}  ·  {total} sessions total")
    with p3:
        if st.button("Next ▶", disabled=st.session_state["sh_page"] >= total_pages - 1, key="sh_next"):
            st.session_state["sh_page"] += 1
            st.rerun()

    st.divider()

    # ── CSV export ─────────────────────────────────────────────────────────
    st.subheader("Export")
    try:
        import httpx as _httpx
        from src.ui.utils import _api_base, _headers
        csv_params: dict = {}
        if worker_id > 0:
            csv_params["worker_id"] = worker_id
        if sop_id.strip():
            csv_params["sop_id"] = sop_id.strip()
        if start_date:
            csv_params["start_date"] = str(start_date)
        if end_date:
            csv_params["end_date"] = str(end_date)

        r = _httpx.get(
            f"{_api_base()}/api/v1/reports/export/csv",
            params=csv_params,
            timeout=10.0,
            headers=_headers(),
        )
        if r.status_code == 200:
            st.download_button(
                "⬇ Download CSV",
                data=r.content,
                file_name="session_history.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.caption(f"Export endpoint returned {r.status_code}")
    except Exception:
        st.caption("Export temporarily unavailable.")
