"""
Leaderboard & Badges — B10.

Ranked display of top performers with earned badges and trend chart.
"""
from __future__ import annotations

import streamlit as st
from src.ui.utils import api_get


def _get(path: str, params: dict | None = None) -> list | dict | None:
    return api_get(path, params)


_BADGE_DESC = {
    "Zero Error Day":       "Completed a session with zero deviations.",
    "Speed Demon":          "Finished a session in under 5 minutes.",
    "Safety First":         "Passed a session without a single high-severity event.",
    "Consistent Performer": "Achieved ≥ 85 % accuracy on at least 3 sessions.",
}

_BADGE_ICONS = {
    "Zero Error Day":       "🎯",
    "Speed Demon":          "⚡",
    "Safety First":         "🦺",
    "Consistent Performer": "🏅",
}


def render() -> None:

    # ── Controls ───────────────────────────────────────────────────────────
    f1, f2, f3 = st.columns([2, 1.4, 1.4])
    with f1:
        period_label = st.radio(
            "Period",
            ["This Week", "This Month", "All Time"],
            index=2, horizontal=True, key="lb_period",
        )
    with f2:
        group_label = st.selectbox(
            "Study group",
            ["All", "Control", "Sim-Only", "Realtime-Only", "Hybrid"],
            key="lb_group",
        )
    with f3:
        dept = st.text_input("Department (blank = all)", key="lb_dept")

    period_map = {"This Week": "week", "This Month": "month", "All Time": "all"}
    group_map = {
        "Control": "control", "Sim-Only": "sim_only",
        "Realtime-Only": "realtime_only", "Hybrid": "hybrid",
    }
    params: dict = {"period": period_map[period_label]}
    if dept.strip():
        params["department"] = dept.strip()
    if group_label in group_map:
        params["group"] = group_map[group_label]

    current_user_id = int(st.session_state.get("user", {}).get("id", 0) or 0)

    board = _get("/api/v1/leaderboard/", params=params)
    if board is None:
        st.warning("Cannot reach API — is Docker running?")
        return

    if not isinstance(board, list) or not board:
        st.info("No sessions in this period yet. Complete some training runs to populate the leaderboard.")
        return

    # ── Two-column layout ─────────────────────────────────────────────────
    col_l, col_r = st.columns([3, 2])

    with col_l:
        st.subheader("Rankings")
        try:
            import pandas as pd
            rows = []
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            for row in board:
                rank_display = medals.get(row["rank"], f"#{row['rank']}")
                is_me = row.get("user_id") == current_user_id
                name = row.get("username")
                rows.append({
                    "Rank": rank_display,
                    "User": f"🔹 {name} (you)" if is_me else name,
                    "Dept": row.get("department"),
                    "Avg Acc %": row.get("avg_accuracy"),
                    "Sessions": row.get("total_sessions"),
                    "Badges": " ".join(_BADGE_ICONS.get(b, "•") for b in row.get("badges", []))
                              or "—",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        except ImportError:
            for row in board:
                st.write(row)

    with col_r:
        st.subheader("Available Badges")
        for name, desc in _BADGE_DESC.items():
            icon = _BADGE_ICONS.get(name, "•")
            st.markdown(f"**{icon} {name}** — {desc}")

    st.divider()

    # ── Progress hint for current user ────────────────────────────────────
    top_user = board[0]
    st.info(
        f"🥇 Current leader: **{top_user['username']}**  ·  "
        f"{top_user['avg_accuracy']}% avg accuracy over {top_user['total_sessions']} sessions."
    )

    st.divider()

    # ── Personal progress section — defaults to logged-in user ──────────────
    st.subheader("📈 My Standing")
    default_my_id = int(st.session_state.get("user", {}).get("id", 1) or 1)
    my_id = st.number_input(
        "Worker ID",
        min_value=1, value=default_my_id, step=1, key="lb_my_id",
    )
    my_row = next((r for r in board if r.get("user_id") == int(my_id)), None)
    if my_row:
        mc1, mc2, mc3, mc4 = st.columns(4)
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        rank_icon = medals.get(my_row["rank"], f"#{my_row['rank']}")
        mc1.metric("Your Rank", rank_icon)
        mc2.metric("Avg Accuracy", f"{my_row.get('avg_accuracy', 0)}%")
        mc3.metric("Sessions", my_row.get("total_sessions", 0))
        my_badges = my_row.get("badges", []) or []
        mc4.metric("Badges", len(my_badges))
        if my_badges:
            st.markdown("**Earned:** " + "  ".join(
                f"{_BADGE_ICONS.get(b, '•')} {b}" for b in my_badges
            ))
        gap = my_row["rank"] - 1
        if gap > 0:
            leader = board[0]
            acc_gap = round(leader.get("avg_accuracy", 0) - my_row.get("avg_accuracy", 0), 1)
            st.caption(
                f"You are **{gap} place{'s' if gap > 1 else ''}** behind the leader. "
                f"Close the accuracy gap of **{acc_gap}%** to move up."
            )
        else:
            st.success("🏆 You are the current leader!")
    else:
        st.caption(
            f"No sessions for Worker #{int(my_id)} in this period/filter — "
            "try 'All Time' or clear the group/department filter."
        )

    # ── Accuracy trend chart for top 5 ────────────────────────────────────
    st.subheader("Top 5 — Accuracy Trend")
    top5 = board[:5]
    try:
        import altair as alt
        import pandas as pd

        all_rows = []
        for row in top5:
            wa = _get(f"/api/v1/analytics/worker/{row['user_id']}")
            if not wa:
                continue
            trend = wa.get("session_trend", []) or []
            for i, s in enumerate(trend):
                acc = max(0.0, 100.0 - s.get("deviation_count", 0) * 10.0)
                all_rows.append({
                    "session": i + 1,
                    "accuracy": acc,
                    "user": row["username"],
                })
        if all_rows:
            df = pd.DataFrame(all_rows)
            chart = (
                alt.Chart(df)
                .mark_line(point=True)
                .encode(
                    x=alt.X("session:O", title="Session #"),
                    y=alt.Y("accuracy:Q", title="Accuracy (%)", scale=alt.Scale(domain=[0, 100])),
                    color=alt.Color("user:N"),
                    tooltip=["user", "session", "accuracy"],
                )
                .properties(height=320)
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.caption("Not enough session data for a trend chart.")
    except ImportError:
        st.caption("Install altair + pandas for trend charts.")
