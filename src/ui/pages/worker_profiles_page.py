"""
Worker Profiles — B7.

Trainer-facing view of worker profiles with session history drill-down
and in-place profile editing.
"""
from __future__ import annotations

import streamlit as st
from src.ui.utils import api_get, api_post, fmt_date, fmt_datetime


def _get(path: str, params: dict | None = None) -> dict | list | None:
    return api_get(path, params)


def _post(path: str, payload: dict) -> dict | None:
    return api_post(path, payload)


_SKILL_LEVELS = ["beginner", "developing", "competent", "proficient"]


def render() -> None:

    data = _get("/api/v1/workers", params={"limit": 100, "offset": 0})
    if data is None:
        st.warning("Cannot reach API — is Docker running?")
        return

    workers = data.get("workers", []) if isinstance(data, dict) else []
    if not workers:
        st.info("No worker profiles yet. Profiles are auto-created after the first training session.")
        return

    # ── Search + list ─────────────────────────────────────────────────────
    search = st.text_input("Search workers (name, email, department)", key="wp_search")
    if search:
        s = search.lower()
        workers = [
            w for w in workers
            if s in (w.get("name") or "").lower()
            or s in (w.get("email") or "").lower()
            or s in (w.get("department") or "").lower()
        ]

    st.caption(f"**{len(workers)}** worker(s)")

    try:
        import pandas as pd
        rows = [{
            "ID": w.get("worker_id"),
            "Name": w.get("name"),
            "Email": w.get("email"),
            "Dept": w.get("department") or "—",
            "Skill": (w.get("skill_level") or "").capitalize(),
            "Sessions": w.get("total_sessions", 0),
            "Deviations": w.get("total_deviations", 0),
            "Last Active": fmt_date(w.get("last_session_at")),
        } for w in workers]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    except ImportError:
        pass

    st.divider()

    # ── Detail + Edit ─────────────────────────────────────────────────────
    st.subheader("Profile Detail")
    labels = {f"#{w['worker_id']} — {w['name']}": w for w in workers}
    choice = st.selectbox("Select worker", list(labels.keys()), key="wp_pick")
    if not choice:
        return
    w = labels[choice]
    wid = w["worker_id"]

    with st.container(border=True):
        cols = st.columns(4)
        cols[0].metric("Sessions", w.get("total_sessions", 0))
        cols[1].metric("Deviations", w.get("total_deviations", 0))
        cols[2].metric("High Severity", w.get("total_high_severity", 0))
        cols[3].metric("Skill", (w.get("skill_level") or "").capitalize())

        with st.form(f"wp_edit_{wid}"):
            st.markdown("**Edit Profile**")
            c1, c2, c3 = st.columns(3)
            skill = c1.selectbox(
                "Skill level",
                _SKILL_LEVELS,
                index=_SKILL_LEVELS.index(w.get("skill_level") or "beginner"),
            )
            dept = c2.text_input("Department", value=w.get("department") or "")
            emp = c3.text_input("Employee ID", value=w.get("employee_id") or "")
            notes = st.text_area("Trainer Notes", value=w.get("trainer_notes") or "", height=100)
            submit = st.form_submit_button("💾 Update Profile", type="primary", use_container_width=True)
            if submit:
                resp = _post(f"/api/v1/workers/{wid}/profile", {
                    "skill_level": skill,
                    "department": dept or None,
                    "employee_id": emp or None,
                    "trainer_notes": notes or None,
                })
                if resp:
                    st.success("Profile updated.")
                    st.rerun()

    # ── Session history drill-down ────────────────────────────────────────
    with st.expander(f"Recent sessions for {w['name']}"):
        hist = _get(f"/api/v1/workers/{wid}/sessions", params={"limit": 10})
        if not hist or not hist.get("sessions"):
            st.caption("No sessions yet.")
        else:
            try:
                import pandas as pd
                rows = [{
                    "Session": (s.get("session_id") or "")[:8],
                    "SOP": s.get("sop_name", s.get("sop_id")),
                    "Ended": fmt_datetime(s.get("ended_at")),
                    "Duration (s)": round(s.get("duration_seconds", 0), 1),
                    "Deviations": s.get("deviation_count", 0),
                    "High Sev": s.get("high_severity_count", 0),
                    "Latency p95": round(s.get("latency_p95_ms", 0), 1),
                } for s in hist["sessions"]]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            except ImportError:
                st.json(hist)
