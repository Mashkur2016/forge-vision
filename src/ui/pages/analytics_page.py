"""
Analytics Dashboard Page — Phase 4 (Task 4.1 / 4.4).

Renders the full analytics dashboard:
  - System summary cards (total sessions, deviations, active workers)
  - Session history table (paginated)
  - Per-worker performance: deviation trend chart + competency estimate
  - Per-SOP breakdown: most problematic steps + deviation class heatmap
  - Deviation heatmap (class × severity)

Connects to FastAPI backend via /api/v1/analytics/* endpoints.

Architecture.md Layer 4: Analytics Dashboard.
Rules.md §2: Only aggregate/anonymised data displayed — no facial images.
"""
from __future__ import annotations

import streamlit as st
from src.ui.utils import api_get_cached, fmt_datetime, fmt_step_name

# ── API helper ────────────────────────────────────────────────────────────────

def _get(path: str, params: dict | None = None) -> dict | None:
    # Cached (short TTL) — analytics is read-only and re-rendered on every rerun.
    return api_get_cached(path, params)


def _has_values(df, *cols) -> bool:
    """True only if ``df`` has rows and every named column holds ≥1 finite value.

    Guards Altair/Vega charts so empty or all-null data never reaches Vega-Lite,
    which otherwise logs noisy ``Infinite extent for field …`` warnings to the
    browser console (Streamlit renders every ``st.tabs`` tab into the DOM, so even
    an inactive, empty tab would emit them).
    """
    try:
        import pandas as pd
    except ImportError:
        return False
    if df is None or len(df) == 0:
        return False
    for c in cols:
        if c not in df.columns:
            return False
        series = pd.to_numeric(df[c], errors="coerce")
        series = series.replace([float("inf"), float("-inf")], pd.NA).dropna()
        if series.empty:
            return False
    return True


# ── Summary cards ─────────────────────────────────────────────────────────────

def _render_summary() -> None:
    summary = _get("/api/v1/analytics/summary")
    if summary is None:
        st.info("No data yet — start a training session to see analytics.")
        return

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Sessions", summary.get("total_sessions", 0))
    c2.metric("Total Deviations", summary.get("total_deviations", 0))
    c3.metric("High-Severity Events", summary.get("total_high_severity", 0))
    c4.metric("Active Workers", summary.get("active_workers", 0))
    c5.metric("Avg Latency p95 (ms)", f"{summary.get('avg_latency_p95_ms', 0):.1f}")
    c6.metric(
        "Latency Target Pass Rate",
        f"{summary.get('latency_target_pass_rate_pct', 0):.1f}%",
    )


# ── Session history ───────────────────────────────────────────────────────────

def _render_sessions() -> None:
    st.subheader("Session History")

    col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
    with col_f1:
        worker_filter = st.number_input(
            "Filter by Worker ID (0 = all)", min_value=0, value=0, step=1
        )
    with col_f2:
        sop_filter = st.text_input("Filter by SOP ID (blank = all)")
    with col_f3:
        page_size = st.selectbox("Rows per page", [20, 50, 100], index=0)

    if "session_page" not in st.session_state:
        st.session_state["session_page"] = 0

    offset = st.session_state["session_page"] * page_size

    params: dict = {"limit": page_size, "offset": offset}
    if worker_filter > 0:
        params["worker_id"] = worker_filter
    if sop_filter.strip():
        params["sop_id"] = sop_filter.strip()

    data = _get("/api/v1/analytics/sessions", params=params)
    if data is None or data.get("total", 0) == 0:
        st.info("No sessions found.")
        return

    total = data["total"]
    sessions = data.get("sessions", [])

    # Display table
    import pandas as pd

    rows = []
    for s in sessions:
        rows.append({
            "Session ID": s.get("session_id", "")[:8],
            "Worker ID": s.get("worker_id") or "—",
            "SOP": s.get("sop_name", s.get("sop_id", "")),
            "Started": fmt_datetime(s.get("started_at")),
            "Duration (s)": round(s.get("duration_seconds", 0), 1),
            "Deviations": s.get("deviation_count", 0),
            "High Severity": s.get("high_severity_count", 0),
            "Latency p95 (ms)": round(s.get("latency_p95_ms", 0), 1),
            "Target Met": "✅" if s.get("latency_target_met") else "❌",
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Pagination controls
    total_pages = max((total - 1) // page_size + 1, 1)
    p_col1, p_col2, p_col3 = st.columns([1, 3, 1])
    with p_col1:
        if st.button("◀ Previous", disabled=st.session_state["session_page"] == 0):
            st.session_state["session_page"] -= 1
            st.rerun()
    with p_col2:
        st.caption(
            f"Page {st.session_state['session_page'] + 1} of {total_pages} "
            f"({total} sessions total)"
        )
    with p_col3:
        if st.button(
            "Next ▶",
            disabled=st.session_state["session_page"] >= total_pages - 1,
        ):
            st.session_state["session_page"] += 1
            st.rerun()


# ── Per-worker analytics ──────────────────────────────────────────────────────

def _render_worker_analytics() -> None:
    st.subheader("Worker Performance")

    worker_id = st.number_input(
        "Enter Worker ID", min_value=1, value=1, step=1, key="worker_analytics_id"
    )

    if st.button("Load Worker Analytics", key="load_worker_btn"):
        data = _get(f"/api/v1/analytics/worker/{worker_id}")
        if data is None:
            return
        st.session_state["worker_analytics_data"] = data

    data = st.session_state.get("worker_analytics_data")
    if data is None:
        return

    # Worker summary
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Worker", data.get("name", "—"))
    col_b.metric("Skill Level", data.get("skill_level", "—").capitalize())
    col_c.metric("Total Sessions", data.get("total_sessions", 0))
    col_d.metric("Total Deviations", data.get("total_deviations", 0))

    improvement = data.get("improvement_rate_pct")
    est = data.get("sessions_to_competency_est")

    col_e, col_f = st.columns(2)
    with col_e:
        if improvement is not None:
            arrow = "↓" if improvement >= 0 else "↑"
            st.metric(
                "Improvement Rate",
                f"{arrow} {abs(improvement):.1f}%",
                help="Deviation reduction: first 3 sessions vs latest 3",
            )
        else:
            st.metric("Improvement Rate", "—", help="Needs ≥3 sessions")

    with col_f:
        if est is not None:
            st.metric("Sessions to Competency (est.)", est)
        else:
            st.metric("Sessions to Competency (est.)", "—")

    # Deviation trend chart
    trend = data.get("session_trend", [])
    if trend:
        try:
            import pandas as pd
            import altair as alt

            df = pd.DataFrame(trend)
            df["session_num"] = df["session_num"].astype(int)

            chart = (
                alt.Chart(df)
                .mark_line(point=True)
                .encode(
                    x=alt.X("session_num:O", title="Session Number"),
                    y=alt.Y("deviation_count:Q", title="Deviations"),
                    tooltip=["session_num", "deviation_count", "high_severity_count"],
                )
                .properties(title="Deviation Count per Session", height=300)
            )
            st.altair_chart(chart, use_container_width=True)
        except ImportError:
            # Fallback: plain line chart
            import pandas as pd
            df = pd.DataFrame(trend).set_index("session_num")[["deviation_count"]]
            st.line_chart(df)

    # Competency estimate detail
    with st.expander("Competency Prediction Detail"):
        comp = _get(f"/api/v1/analytics/competency/{worker_id}")
        if comp:
            st.json(comp)


# ── Per-SOP analytics ─────────────────────────────────────────────────────────

def _render_sop_analytics() -> None:
    st.subheader("SOP Performance")

    sop_id = st.text_input("Enter SOP ID", key="sop_analytics_id")

    if st.button("Load SOP Analytics", key="load_sop_btn") and sop_id.strip():
        data = _get(f"/api/v1/analytics/sop/{sop_id.strip()}")
        if data is not None:
            st.session_state["sop_analytics_data"] = data

    data = st.session_state.get("sop_analytics_data")
    if data is None:
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("SOP Name", data.get("sop_name", data.get("sop_id", "—")))
    col2.metric("Total Sessions", data.get("total_sessions", 0))
    col3.metric(
        "Avg Deviations/Session",
        f"{data.get('avg_deviations_per_session', 0):.2f}",
    )

    # Most problematic steps
    problem_steps = data.get("most_problematic_steps", [])
    if problem_steps:
        st.markdown("**Most Problematic Steps (top 5)**")
        try:
            import pandas as pd
            import altair as alt

            df = pd.DataFrame(problem_steps)
            df["step_display"] = df["step"].apply(fmt_step_name)
            chart = (
                alt.Chart(df)
                .mark_bar()
                .encode(
                    x=alt.X("deviation_count:Q", title="Deviation Count"),
                    y=alt.Y("step_display:N", sort="-x", title="Step"),
                    tooltip=["step_display", "deviation_count"],
                )
                .properties(height=200)
            )
            st.altair_chart(chart, use_container_width=True)
        except ImportError:
            import pandas as pd
            df = pd.DataFrame(problem_steps)
            df["step_display"] = df["step"].apply(fmt_step_name)
            df_display = df.set_index("step_display")[["deviation_count"]]
            st.bar_chart(df_display)

    # Deviation class breakdown
    breakdown = data.get("deviation_breakdown", {})
    if breakdown:
        st.markdown("**Deviation Class Distribution**")
        try:
            import pandas as pd
            import altair as alt

            df = pd.DataFrame(
                [{"class": k, "count": v} for k, v in breakdown.items()]
            )
            if not _has_values(df, "count"):
                st.caption("No deviation-class counts to chart yet.")
                return
            chart = (
                alt.Chart(df)
                .mark_arc()
                .encode(
                    theta=alt.Theta("count:Q"),
                    color=alt.Color("class:N"),
                    tooltip=["class", "count"],
                )
                .properties(height=250)
            )
            st.altair_chart(chart, use_container_width=True)
        except ImportError:
            import pandas as pd
            df = pd.Series(breakdown, name="count")
            st.bar_chart(df)


# ── Deviation heatmap ─────────────────────────────────────────────────────────

def _render_heatmap() -> None:
    st.subheader("Deviation Heatmap (Class × Severity)")

    sop_filter = st.text_input("Filter by SOP ID (blank = all SOPs)", key="heatmap_sop_filter")
    params: dict = {}
    if sop_filter.strip():
        params["sop_id"] = sop_filter.strip()

    if st.button("Refresh Heatmap", key="refresh_heatmap_btn"):
        st.session_state.pop("heatmap_data", None)
        st.cache_data.clear()  # honour an explicit refresh over the short-TTL cache

    if "heatmap_data" not in st.session_state:
        data = _get("/api/v1/analytics/deviations/heatmap", params=params)
        if data is not None:
            st.session_state["heatmap_data"] = data

    data = st.session_state.get("heatmap_data")
    if not data or not data.get("heatmap"):
        st.info("No deviation data yet.")
        return

    try:
        import pandas as pd
        import altair as alt

        df = pd.DataFrame(data["heatmap"])
        if not _has_values(df, "count"):
            st.info("No deviation data yet.")
            return

        chart = (
            alt.Chart(df)
            .mark_rect()
            .encode(
                x=alt.X("severity:N", title="Severity"),
                y=alt.Y("deviation_class:N", title="Deviation Class"),
                color=alt.Color("count:Q", scale=alt.Scale(scheme="orangered")),
                tooltip=["deviation_class", "severity", "count"],
            )
            .properties(height=300, title="Deviation Count Heatmap")
        )
        st.altair_chart(chart, use_container_width=True)

    except ImportError:
        import pandas as pd
        df = pd.DataFrame(data["heatmap"])
        pivot = df.pivot_table(
            index="deviation_class", columns="severity", values="count", fill_value=0
        )
        st.dataframe(pivot, use_container_width=True)


# ── Emotion breakdown (Tab 5) ─────────────────────────────────────────────────

def _render_emotion_breakdown() -> None:
    st.subheader("Emotion & Stress Breakdown")
    st.caption("Aggregated emotion/stress signals detected via MediaPipe FaceMesh (Enhancement 7)")

    data = _get("/api/v1/analytics/emotion-summary")
    if data is None:
        st.info(
            "No emotion data available yet — start training sessions with "
            "emotion detection enabled to populate this chart."
        )
        # Static placeholder so the tab always renders something useful
        try:
            import altair as alt
            import pandas as pd

            placeholder = pd.DataFrame([
                {"emotion": "Neutral",     "pct": 55},
                {"emotion": "Focused",     "pct": 20},
                {"emotion": "Stressed",    "pct": 15},
                {"emotion": "Confused",    "pct": 7},
                {"emotion": "Disengaged",  "pct": 3},
            ])
            chart = (
                alt.Chart(placeholder)
                .mark_arc(innerRadius=50)
                .encode(
                    theta=alt.Theta("pct:Q"),
                    color=alt.Color("emotion:N", scale=alt.Scale(
                        domain=["Neutral", "Focused", "Stressed", "Confused", "Disengaged"],
                        range=["#6B7280", "#2563EB", "#DC2626", "#F59E0B", "#9CA3AF"],
                    )),
                    tooltip=["emotion", "pct"],
                )
                .properties(title="Emotion Distribution — placeholder (no session data)", height=280)
            )
            st.altair_chart(chart, use_container_width=True)
        except ImportError:
            st.caption("Install altair + pandas for charts.")
        return

    try:
        import altair as alt
        import pandas as pd

        rows = [{"emotion": k, "count": v} for k, v in data.get("emotion_counts", {}).items()]
        df = pd.DataFrame(rows)
        if not _has_values(df, "count"):
            st.info("No emotion events recorded yet.")
            return
        chart = (
            alt.Chart(df)
            .mark_arc(innerRadius=50)
            .encode(
                theta=alt.Theta("count:Q"),
                color=alt.Color("emotion:N"),
                tooltip=["emotion", "count"],
            )
            .properties(title="Emotion Distribution (all sessions)", height=280)
        )
        st.altair_chart(chart, use_container_width=True)

        avg_stress = data.get("avg_stress_score")
        if avg_stress is not None:
            st.metric("Avg Stress Score", f"{avg_stress:.2f}", help="0 = calm, 1 = high stress")
    except ImportError:
        st.caption("Install altair + pandas for charts.")


# ── Bias audit (Tab 6) ────────────────────────────────────────────────────────

def _render_bias_audit() -> None:
    st.subheader("Bias Audit — Per-Department Accuracy")
    st.caption(
        "Checks whether model accuracy is equitable across departments. "
        "Large gaps may indicate training data bias."
    )

    data = _get("/api/v1/analytics/bias-audit")
    if data is None:
        # Compute from leaderboard fallback
        lb = _get("/api/v1/leaderboard/", {"period": "all"} if False else None)
        if not isinstance(lb, list) or not lb:
            st.info("No session data available yet — complete training runs across multiple departments.")
            return
        # Group by department
        from collections import defaultdict
        dept_accs: dict = defaultdict(list)
        for row in lb:
            dept = row.get("department") or "Unknown"
            acc = row.get("avg_accuracy") or 0
            dept_accs[dept].append(acc)
        rows = [
            {"department": dept, "avg_accuracy": round(sum(vals) / len(vals), 1), "workers": len(vals)}
            for dept, vals in dept_accs.items()
        ]
        if not rows:
            st.info("No department data found.")
            return
        try:
            import altair as alt
            import pandas as pd

            df = pd.DataFrame(rows).sort_values("avg_accuracy", ascending=False)
            chart = (
                alt.Chart(df)
                .mark_bar()
                .encode(
                    x=alt.X("avg_accuracy:Q", title="Avg Accuracy (%)", scale=alt.Scale(domain=[0, 100])),
                    y=alt.Y("department:N", sort="-x", title="Department"),
                    color=alt.condition(
                        alt.datum.avg_accuracy < 70,
                        alt.value("#DC2626"),
                        alt.value("#2563EB"),
                    ),
                    tooltip=["department", "avg_accuracy", "workers"],
                )
                .properties(title="Per-Department Average Accuracy (from leaderboard)", height=300)
            )
            st.altair_chart(chart, use_container_width=True)
            low = df[df["avg_accuracy"] < 70]
            if not low.empty:
                st.warning(
                    f"**Potential bias detected:** {', '.join(low['department'].tolist())} "
                    f"are below 70% average accuracy — review training data coverage."
                )
            else:
                st.success("No significant accuracy gaps detected across departments.")
        except ImportError:
            st.caption("Install altair + pandas for charts.")
        return

    try:
        import altair as alt
        import pandas as pd

        df = pd.DataFrame(data.get("departments", []))
        if df.empty:
            st.info("No department accuracy data yet.")
            return
        cohort_mean = data.get("cohort_mean", 0.0)
        st.caption(
            f"Cohort mean accuracy: **{cohort_mean}%** — a department is flagged when it "
            "sits more than 10% below this baseline (relative disparity, not an absolute cutoff)."
        )
        chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("avg_accuracy:Q", title="Avg Accuracy (%)", scale=alt.Scale(domain=[0, 100])),
                y=alt.Y("department:N", sort="-x", title="Department"),
                color=alt.condition(alt.datum.flagged, alt.value("#DC2626"), alt.value("#2563EB")),
                tooltip=["department", "avg_accuracy", "session_count", "flagged"],
            )
            .properties(title="Per-Department Accuracy", height=300)
        )
        rule = (
            alt.Chart(pd.DataFrame({"m": [cohort_mean]}))
            .mark_rule(strokeDash=[4, 4], color="#6b7280")
            .encode(x="m:Q")
        )
        st.altair_chart(chart + rule, use_container_width=True)

        flagged = df[df["flagged"]]["department"].tolist() if "flagged" in df.columns else []
        if flagged:
            st.warning(
                f"**Potential bias detected:** {', '.join(flagged)} — more than 10% below the "
                "cohort mean. Review training-data coverage / support for these units. "
                "*(Synthetic demonstration data.)*"
            )
        else:
            st.success("No significant accuracy disparity across departments.")
    except ImportError:
        st.caption("Install altair + pandas for charts.")


# ── Main render ───────────────────────────────────────────────────────────────

_GROUP_LABELS = {
    "control": "Control",
    "sim_only": "Sim-Only",
    "realtime_only": "Realtime-Only",
    "hybrid": "Hybrid",
}


def _render_study_groups() -> None:
    st.subheader("Study-Group Comparison (H1 / H2)")
    st.caption(
        "**SYNTHETIC data.** Compares the four training arms on the seeded operational "
        "sessions — supports H1 (lower error rate) and H2 (better skill transfer)."
    )
    data = _get("/api/v1/analytics/study-groups")
    if not data or not data.get("groups"):
        st.info("No study-group data available.")
        return

    groups = data["groups"]
    try:
        import altair as alt
        import pandas as pd

        dfg = pd.DataFrame(groups)
        dfg["group_label"] = dfg["group"].map(lambda g: _GROUP_LABELS.get(g, str(g).title()))

        if _has_values(dfg, "avg_accuracy", "avg_deviations_per_session"):
            c1, c2 = st.columns(2)
            with c1:
                st.altair_chart(
                    alt.Chart(dfg).mark_bar(color="#2563EB").encode(
                        x=alt.X("group_label:N", sort="-y", title="Group"),
                        y=alt.Y("avg_accuracy:Q", title="Avg accuracy %", scale=alt.Scale(domain=[0, 100])),
                        tooltip=["group_label", "avg_accuracy", "worker_count", "session_count"],
                    ).properties(
                        title=alt.TitleParams("Avg accuracy by group", offset=14, anchor="middle", fontSize=14),
                        height=300, padding={"top": 14, "left": 5, "right": 5, "bottom": 5},
                    ),
                    use_container_width=True,
                )
            with c2:
                st.altair_chart(
                    alt.Chart(dfg).mark_bar(color="#dc2626").encode(
                        x=alt.X("group_label:N", sort="y", title="Group"),
                        y=alt.Y("avg_deviations_per_session:Q", title="Avg deviations / session"),
                        tooltip=["group_label", "avg_deviations_per_session", "high_severity_rate"],
                    ).properties(
                        title=alt.TitleParams("Avg deviations by group", offset=14, anchor="middle", fontSize=14),
                        height=300, padding={"top": 14, "left": 5, "right": 5, "bottom": 5},
                    ),
                    use_container_width=True,
                )

        lc = data.get("learning_curve", [])
        if lc:
            dfc = pd.DataFrame(lc)
            dfc["group_label"] = dfc["group"].map(lambda g: _GROUP_LABELS.get(g, str(g).title()))
            if _has_values(dfc, "session_seq", "avg_deviations"):
                st.altair_chart(
                    alt.Chart(dfc).mark_line(point=True, strokeWidth=3).encode(
                        x=alt.X("session_seq:Q", title="Session number (per worker)"),
                        y=alt.Y("avg_deviations:Q", title="Avg deviations"),
                        color=alt.Color("group_label:N", title="Group"),
                        tooltip=["group_label", "session_seq", "avg_deviations", "n"],
                    ).properties(
                        title=alt.TitleParams("Learning curves — deviations decline with practice",
                                              offset=14, anchor="middle", fontSize=14),
                        height=340, padding={"top": 14, "left": 5, "right": 5, "bottom": 5},
                    ),
                    use_container_width=True,
                )

        st.dataframe(
            dfg[["group_label", "worker_count", "session_count",
                 "avg_deviations_per_session", "avg_accuracy", "high_severity_rate"]],
            use_container_width=True, hide_index=True,
        )
    except ImportError:
        st.dataframe(groups, use_container_width=True)


def render() -> None:

    st.divider()
    _render_summary()

    st.divider()
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📋 Session History",
        "👷 Worker Performance",
        "📁 SOP Analytics",
        "🔥 Deviation Heatmap",
        "📊 Study Groups",
        "😊 Emotion Breakdown",
        "⚖️ Bias Audit",
    ])

    with tab1:
        _render_sessions()

    with tab2:
        _render_worker_analytics()

    with tab3:
        _render_sop_analytics()

    with tab4:
        _render_heatmap()

    with tab5:
        _render_study_groups()

    with tab6:
        _render_emotion_breakdown()

    with tab7:
        _render_bias_audit()
