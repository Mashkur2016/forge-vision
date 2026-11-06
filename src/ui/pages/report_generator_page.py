"""
Report Generator — B9.

Supervisor page for generating filtered session reports with charts,
KPI cards and CSV / PDF-style exports suitable for the DBA thesis.
"""
from __future__ import annotations

from datetime import date, timedelta

import streamlit as st
from src.ui.utils import api_get, fmt_step_name


def _get(path: str, params: dict | None = None) -> dict | list | None:
    return api_get(path, params)


def render() -> None:

    # ── Filters ────────────────────────────────────────────────────────────
    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("Start date", value=date.today() - timedelta(days=30), key="rg_start")
    with c2:
        end_date = st.date_input("End date", value=date.today(), key="rg_end")

    # Worker and SOP multiselects
    workers_data = _get("/api/v1/admin/users/") or []
    worker_opts = {f"#{w['id']} — {w['username']}": w["id"] for w in workers_data if isinstance(w, dict)}
    selected_workers = st.multiselect("Workers (blank = all)", list(worker_opts.keys()), key="rg_workers")

    sops_data = _get("/api/v1/sops/") or []
    sop_opts = {f"{s['name']} ({s['id']})": s["id"] for s in sops_data if isinstance(s, dict)}
    selected_sops = st.multiselect("SOPs (blank = all)", list(sop_opts.keys()), key="rg_sops")

    run = st.button("📊 Generate Report", type="primary", use_container_width=True)
    st.divider()

    if not run and "rg_report" not in st.session_state:
        st.info("Configure filters above and click **Generate Report**.")
        return

    if run:
        params: dict = {"start_date": str(start_date), "end_date": str(end_date)}
        if selected_workers:
            params["worker_ids"] = ",".join(str(worker_opts[k]) for k in selected_workers)
        if selected_sops:
            params["sop_ids"] = ",".join(str(sop_opts[k]) for k in selected_sops)

        aggregate = _get("/api/v1/reports/aggregate", params=params)
        if not aggregate:
            st.warning("No data found for those filters.")
            return
        st.session_state["rg_report"] = aggregate

    report: dict = st.session_state.get("rg_report") or {}
    if not report:
        return

    # ── KPI cards ─────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Sessions", report.get("total_sessions", 0))
    k2.metric("Avg Accuracy", f"{report.get('avg_accuracy_pct', 0)}%",
              help="Severity-weighted: high-severity deviations are penalised more than minor ones.")
    k3.metric("Total Deviations", report.get("total_deviations", 0))
    k4.metric("High Severity", report.get("total_high_severity", 0))

    k5, k6 = st.columns(2)
    k5.metric("Top Performer", report.get("top_worker") or "—")
    top_step = report.get("most_deviated_step") or {}
    step_display = fmt_step_name(top_step.get("step", "")) if top_step else "—"
    k6.metric("Most Deviated Step", step_display,
              delta=f"{top_step.get('count', 0)} events" if top_step else None)

    st.divider()

    # ── Charts ─────────────────────────────────────────────────────────────
    try:
        import altair as alt
        import pandas as pd

        devs = report.get("deviations_by_worker", [])
        if devs:
            df = pd.DataFrame(devs)
            if "username" not in df.columns:
                df["username"] = df["worker_id"].astype(str)
            chart = (
                alt.Chart(df)
                .mark_bar(color="#2563EB")
                .encode(
                    x=alt.X("deviations:Q", title="Total Deviations"),
                    y=alt.Y("username:N", sort="-x", title="Worker"),
                    tooltip=["username", "sessions", "deviations"],
                )
                .properties(title="Deviations by Worker", height=max(200, 28 * len(df)))
            )
            st.altair_chart(chart, use_container_width=True)

        trend = report.get("accuracy_trend", [])
        if trend:
            dft = pd.DataFrame(trend)
            chart2 = (
                alt.Chart(dft)
                .mark_line(point=True, strokeWidth=3, color="#2563EB")
                .encode(
                    x=alt.X("date:T", title="Date"),
                    y=alt.Y("avg_accuracy:Q", title="Avg Accuracy %", scale=alt.Scale(domain=[0, 100])),
                    tooltip=["date", "avg_accuracy", "sessions"],
                )
                .properties(title="Accuracy Over Time", height=300)
            )
            st.altair_chart(chart2, use_container_width=True)

    except ImportError:
        st.caption("Install altair + pandas to render charts.")

    # ── Deviation breakdown (class × severity) ──────────────────────────────
    breakdown = report.get("deviation_breakdown", [])
    sev_totals = report.get("severity_totals", {}) or {}
    if breakdown:
        st.divider()
        st.markdown("#### Deviation Breakdown")
        s1, s2, s3 = st.columns(3)
        s1.metric("🟢 Low", sev_totals.get("low", 0))
        s2.metric("🟡 Medium", sev_totals.get("medium", 0))
        s3.metric("🔴 High", sev_totals.get("high", 0))
        try:
            import altair as alt
            import pandas as pd
            dfb = pd.DataFrame(breakdown)
            dfb["deviation_class"] = dfb["deviation_class"].map(fmt_step_name)
            chart3 = (
                alt.Chart(dfb)
                .mark_bar()
                .encode(
                    x=alt.X("count:Q", title="Count"),
                    y=alt.Y("deviation_class:N", sort="-x", title="Deviation class"),
                    color=alt.Color("severity:N", title="Severity",
                                    scale=alt.Scale(domain=["low", "medium", "high"],
                                                    range=["#16a34a", "#d97706", "#dc2626"])),
                    tooltip=["deviation_class", "severity", "count"],
                )
                .properties(title="Deviations by class & severity",
                            height=max(180, 30 * dfb["deviation_class"].nunique()))
            )
            st.altair_chart(chart3, use_container_width=True)
        except ImportError:
            st.dataframe(breakdown, use_container_width=True)

    st.divider()

    # ── Exports ────────────────────────────────────────────────────────────
    e1, e2 = st.columns(2)
    with e1:
        try:
            import httpx as _httpx
            from src.ui.utils import _api_base, _headers
            params = {"start_date": str(start_date), "end_date": str(end_date)}
            if selected_workers:
                params["worker_ids"] = ",".join(str(worker_opts[k]) for k in selected_workers)
            if selected_sops:
                params["sop_ids"] = ",".join(str(sop_opts[k]) for k in selected_sops)
            r = _httpx.get(f"{_api_base()}/api/v1/reports/export/csv", params=params,
                           timeout=10.0, headers=_headers())
            if r.status_code == 200:
                st.download_button(
                    "⬇ Export CSV",
                    data=r.content,
                    file_name=f"report_{start_date}_to_{end_date}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
        except Exception:
            st.caption("CSV export unavailable.")

    with e2:
        # Build a printable PDF (step names humanised) from the loaded report data.
        pdf_report = dict(report)
        _top = dict(top_step) if top_step else {}
        if _top.get("step"):
            _top["step"] = fmt_step_name(_top["step"])
            pdf_report["most_deviated_step"] = _top
        try:
            from src.ui.pdf_report import build_report_pdf
            pdf_bytes = build_report_pdf(pdf_report, str(start_date), str(end_date))
            st.download_button(
                "⬇ Export PDF",
                data=pdf_bytes,
                file_name=f"report_{start_date}_to_{end_date}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except ModuleNotFoundError:
            st.caption("PDF export requires the `fpdf2` package (add it to requirements).")
        except Exception as exc:  # noqa: BLE001 — never break the page on export failure
            st.caption(f"PDF export unavailable: {exc}")
