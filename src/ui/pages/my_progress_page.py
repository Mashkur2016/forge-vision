"""
My Progress — B2.

Worker-facing page showing personal KPIs, accuracy trend and session list.
"""
from __future__ import annotations

import streamlit as st
from src.ui.utils import api_get, fmt_datetime


def _get(path: str, params: dict | None = None) -> dict | list | None:
    return api_get(path, params)


def render() -> None:
    st.divider()

    # ── Worker picker — defaults to logged-in user ────────────────────────
    default_id = int(st.session_state.get("user", {}).get("id", 1) or 1)
    with st.sidebar:
        st.subheader("Viewing")
        worker_id = st.number_input("Worker ID", min_value=1, value=default_id, step=1, key="mp_worker_id")

    # ── Load analytics ─────────────────────────────────────────────────────
    data = _get(f"/api/v1/analytics/worker/{int(worker_id)}")
    if data is None:
        st.warning("Cannot reach API — is Docker running? Or worker has no sessions yet.")
        return

    # ── KPIs ───────────────────────────────────────────────────────────────
    total_sessions = data.get("total_sessions", 0)
    total_devs = data.get("total_deviations", 0)
    improvement = data.get("improvement_rate_pct")

    # Derive accuracy from the session trend
    trend = data.get("session_trend", []) or []
    if trend:
        accs = [max(0.0, 100.0 - s.get("deviation_count", 0) * 10.0) for s in trend]
        avg_accuracy = round(sum(accs) / len(accs), 1)
    else:
        avg_accuracy = 0.0

    # Rank — fetch leaderboard
    rank = "—"
    lb = _get("/api/v1/leaderboard/", params={"period": "all"})
    if isinstance(lb, list):
        for row in lb:
            if row.get("user_id") == int(worker_id):
                rank = f"#{row.get('rank')}"
                break

    # Sessions to Competency estimate
    comp_data = _get(f"/api/v1/analytics/competency/{int(worker_id)}")
    sessions_to_comp = None
    comp_trend_delta = None
    if comp_data:
        sessions_to_comp = comp_data.get("sessions_to_competency_est")
        # Derive trend arrow: if improving (est decreasing) show ↓ (good = green)
        prev_est = comp_data.get("previous_est")
        if sessions_to_comp is not None and prev_est is not None:
            diff = sessions_to_comp - prev_est
            comp_trend_delta = f"{'↓' if diff < 0 else '↑'} {abs(diff):.0f} sessions"

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Sessions", total_sessions)
    c2.metric("Avg Accuracy", f"{avg_accuracy}%")
    c3.metric("Total Errors", total_devs,
              delta=f"{improvement}% vs early" if improvement is not None else None,
              delta_color="inverse")
    c4.metric("Leaderboard Rank", rank)
    if sessions_to_comp is not None:
        c5.metric(
            "Sessions to Competency",
            int(sessions_to_comp),
            delta=comp_trend_delta,
            delta_color="inverse",
            help="Estimated remaining sessions to reach ≥85% sustained accuracy",
        )
    else:
        c5.metric("Sessions to Competency", "—", help="Needs ≥3 sessions for estimate")

    st.divider()

    # ── Accuracy trend chart ───────────────────────────────────────────────
    st.subheader("Accuracy Trend")
    if not trend:
        st.info("No sessions yet — complete a training run to see your progress.")
    else:
        try:
            import pandas as pd
            import altair as alt
            df = pd.DataFrame([
                {
                    "session": i + 1,
                    "accuracy": max(0.0, 100.0 - s.get("deviation_count", 0) * 10.0),
                    "deviations": s.get("deviation_count", 0),
                }
                for i, s in enumerate(trend)
            ])
            chart = (
                alt.Chart(df)
                .mark_line(point=True, strokeWidth=3, color="#2563EB")
                .encode(
                    x=alt.X("session:O", title="Session #"),
                    y=alt.Y("accuracy:Q", title="Accuracy (%)", scale=alt.Scale(domain=[0, 100])),
                    tooltip=["session", "accuracy", "deviations"],
                )
                .properties(height=300)
            )
            st.altair_chart(chart, use_container_width=True)
        except ImportError:
            st.line_chart([s.get("deviation_count", 0) for s in trend])

    # ── Recent sessions table ─────────────────────────────────────────────
    st.subheader("Recent Sessions (last 10)")
    if trend:
        try:
            import pandas as pd
            rows = []
            for i, s in enumerate(reversed(trend[-10:])):
                rows.append({
                    "#": len(trend) - i,
                    "SOP": s.get("sop_id", ""),
                    "Ended": fmt_datetime(s.get("ended_at")),
                    "Duration (s)": round(s.get("duration_seconds", 0), 1),
                    "Deviations": s.get("deviation_count", 0),
                    "Accuracy %": round(max(0.0, 100.0 - s.get("deviation_count", 0) * 10.0), 1),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        except ImportError:
            st.caption("Install pandas to see the table.")
    else:
        st.caption("—")

    # ── Next badge progress ────────────────────────────────────────────────
    st.divider()
    st.subheader("🏆 Next Badge")
    if isinstance(lb, list):
        me = next((r for r in lb if r.get("user_id") == int(worker_id)), None)
        if me:
            badges = me.get("badges", []) or []
            st.success(f"Badges earned: **{', '.join(badges)}**" if badges else "No badges earned yet — keep training.")

            # Progress toward 'Consistent Performer' (3 sessions >= 85%)
            high_acc_count = sum(
                1 for s in trend if max(0, 100 - s.get("deviation_count", 0) * 10) >= 85
            )
            target = 3
            remaining = max(0, target - high_acc_count)
            st.caption(f"Consistent Performer: {min(high_acc_count, target)}/{target} sessions ≥ 85%")
            st.progress(min(high_acc_count / target, 1.0))
            if remaining > 0:
                st.info(f"{remaining} more high-accuracy session(s) needed for the **Consistent Performer** badge.")
        else:
            st.caption("No leaderboard entry yet.")
    else:
        st.caption("Leaderboard not available.")
