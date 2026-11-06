"""
Evaluation & Thesis Validation Page — Phase 5.

Streamlit page for running the DBA academic evaluation:
  - Power analysis (required sample size)
  - H1, H2, H3 hypothesis tests
  - Visualisation of group distributions and test results
  - Export results as JSON for thesis appendices

All data is SYNTHETIC until real participant data is collected
with ethics board approval.

Rules.md §3.1: Synthetic data prominently labelled.
Rules.md §3.2: α = 0.05; Cohen's d / η² reported.
"""
from __future__ import annotations

import json

import streamlit as st

from src.evaluation.experiment_runner import ExperimentConfig, ExperimentRunner
from src.evaluation.synthetic_participants import SyntheticParticipantGenerator
from src.ui.utils import api_get, api_post


# ── Helpers ────────────────────────────────────────────────────────────────────

def _run_experiment(cfg: ExperimentConfig):
    runner = ExperimentRunner(config=cfg)
    return runner.run(save=True)


# ── Sections ───────────────────────────────────────────────────────────────────

def _render_config() -> ExperimentConfig:
    st.subheader("Experiment Configuration")
    st.warning(
        "**All data shown is SYNTHETIC** — generated from published literature baselines. "
        "Real participant data collection requires ethics board approval (Rules.md §3.3)."
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        n_per_group = st.number_input(
            "Participants per group (n)", min_value=10, max_value=500, value=64, step=1
        )
        alpha = st.number_input(
            "Significance level (α)", min_value=0.01, max_value=0.10,
            value=0.05, step=0.01, format="%.2f",
        )
    with col2:
        target_power = st.number_input(
            "Target statistical power", min_value=0.70, max_value=0.99,
            value=0.80, step=0.05, format="%.2f",
        )
        effect_size = st.number_input(
            "Expected effect size (Cohen's d)", min_value=0.1, max_value=2.0,
            value=0.5, step=0.1, format="%.1f",
        )
    with col3:
        seed = st.number_input("Random seed (reproducibility)", value=42, step=1)
        desc = st.text_input(
            "Experiment description",
            value="Phase 5 DBA Evaluation — Hypothesis Testing",
        )

    return ExperimentConfig(
        description=desc,
        alpha=float(alpha),
        target_power=float(target_power),
        effect_size=float(effect_size),
        n_per_group=int(n_per_group),
        random_seed=int(seed),
    )


def _render_power_analysis(record) -> None:
    st.subheader("Power Analysis")
    pa = record.power_analysis
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Required n/group", pa["required_n_per_group"])
    col2.metric("Actual n/group", pa["actual_n_per_group"])
    col3.metric("Total participants", pa["actual_n_per_group"] * 5)
    adequately = "✅ Yes" if pa["adequately_powered"] else "❌ Underpowered"
    col4.metric("Adequately powered?", adequately)

    if not pa["adequately_powered"]:
        st.error(
            f"Sample size ({pa['actual_n_per_group']}/group) is below the required "
            f"{pa['required_n_per_group']}/group for d={pa['effect_size']}, "
            f"α={pa['alpha']}, power={pa['target_power']}. "
            "Increase n_per_group before drawing conclusions."
        )


def _render_group_distributions(cfg: ExperimentConfig) -> None:
    st.subheader("Synthetic Group Distributions")
    try:
        import pandas as pd
        import altair as alt

        gen = SyntheticParticipantGenerator(seed=cfg.random_seed)
        study = gen.generate_full_study(n_per_group=cfg.n_per_group)

        rows = []
        for group, records in study.items():
            for r in records:
                rows.append(r.to_dict())
        df = pd.DataFrame(rows)

        tab_err, tab_time, tab_sess = st.tabs(
            ["Errors per Task", "Completion Time (min)", "Sessions to Competency"]
        )

        with tab_err:
            chart = (
                alt.Chart(df)
                .mark_boxplot()
                .encode(
                    x=alt.X("group:N", title="Group"),
                    y=alt.Y("errors_per_task:Q", title="Errors per Task"),
                    color="group:N",
                )
                .properties(height=350, title="Errors per Task by Group (Synthetic Data)")
            )
            st.altair_chart(chart, use_container_width=True)

        with tab_time:
            chart = (
                alt.Chart(df)
                .mark_boxplot()
                .encode(
                    x=alt.X("group:N", title="Group"),
                    y=alt.Y("completion_time_min:Q", title="Completion Time (min)"),
                    color="group:N",
                )
                .properties(height=350, title="Completion Time by Group (Synthetic Data)")
            )
            st.altair_chart(chart, use_container_width=True)

        with tab_sess:
            chart = (
                alt.Chart(df)
                .mark_boxplot()
                .encode(
                    x=alt.X("group:N", title="Group"),
                    y=alt.Y("sessions_to_competency:Q", title="Sessions to Competency"),
                    color="group:N",
                )
                .properties(height=350, title="Sessions to Competency by Group (Synthetic Data)")
            )
            st.altair_chart(chart, use_container_width=True)

    except ImportError:
        st.info("Install altair for distribution visualisations.")


def _fmt_ci(ci) -> str:
    return f"[{ci[0]:.2f}, {ci[1]:.2f}]" if ci else "—"


def _render_assumptions(dr: dict) -> None:
    """Show normality (Shapiro-Wilk) + homogeneity (Levene) assumption checks."""
    norm = dr.get("normality")
    homo = dr.get("homogeneity")
    if not norm and not homo:
        return
    # Rendered inline (NOT in an expander): this helper is always called from
    # inside a hypothesis-result expander, and Streamlit forbids nested expanders.
    st.markdown("**🔬 Statistical assumption checks**")
    with st.container(border=True):
        if norm:
            st.caption("**Normality (Shapiro-Wilk)** — p > 0.05 ⇒ consistent with normal.")
            for g in norm:
                p = g.get("p_value")
                ok = g.get("normal")
                mark = "✅" if ok else ("⚠️" if ok is False else "—")
                st.write(f"{mark} {g.get('group')}: p = {p if p is not None else 'n/a'}")
        if homo:
            p = homo.get("p_value")
            ok = homo.get("equal_variance")
            mark = "✅ equal variances" if ok else ("⚠️ unequal variances (Welch handles this)" if ok is False else "—")
            st.caption(f"**Homogeneity (Levene)** — p = {p}: {mark}")


def _render_hypothesis_results(record) -> None:
    st.subheader("Hypothesis Test Results")

    alpha = record.config["alpha"]

    for h_key, h_label, detail_key in [
        ("H1", "H1 — Error Rate Reduction", "h1_result"),
        ("H3", "H3 — Completion Time Reduction", "h3_result"),
    ]:
        dr = getattr(record, detail_key)
        with st.expander(f"{h_label}  ·  {dr.get('test_name', 't-test')}", expanded=True):
            r = record.summary["hypotheses"][h_key]

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("p-value", f"{r['p_value']:.4f}")
            col2.metric("vs α", f"{alpha}", delta=None)
            col3.metric("Cohen's d" + ("z" if dr.get("paired") else ""), f"{r['cohens_d']:.3f}")
            col4.metric("Effect", r["effect"].capitalize())

            if r["supported"]:
                st.success(f"**{h_key} SUPPORTED** — p = {r['p_value']:.4f} < α = {alpha}")
            else:
                st.error(f"**{h_key} NOT SUPPORTED** — p = {r['p_value']:.4f} ≥ α = {alpha}")

            if dr.get("paired") and dr.get("mean_diff_ci95"):
                st.caption(
                    f"Paired (within-subjects) design. 95% CI of the mean difference: "
                    f"{_fmt_ci(dr['mean_diff_ci95'])}."
                )

            try:
                import pandas as pd
                df = pd.DataFrame({
                    "Group": [dr["group_a"]["label"], dr["group_b"]["label"]],
                    "Mean": [round(dr["group_a"]["mean"], 3), round(dr["group_b"]["mean"], 3)],
                    "95% CI": [_fmt_ci(dr["group_a"].get("ci95")), _fmt_ci(dr["group_b"].get("ci95"))],
                    "Std Dev": [round(dr["group_a"]["std"], 3), round(dr["group_b"]["std"], 3)],
                    "N": [dr["group_a"]["n"], dr["group_b"]["n"]],
                })
                st.dataframe(df, use_container_width=True, hide_index=True)
            except (KeyError, ImportError):
                st.json(dr)

            _render_assumptions(dr)

    # H2 — ANOVA
    with st.expander("H2 — Hybrid Approach Skill Transfer (One-Way ANOVA)", expanded=True):
        r = record.summary["hypotheses"]["H2"]
        dr = record.h2_result

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("p-value", f"{r['p_value']:.4f}")
        col2.metric("F-statistic", f"{dr['f_statistic']:.3f}")
        col3.metric("η²", f"{r['eta_squared']:.3f}")
        col4.metric("Effect", r["effect"].capitalize())

        if r["supported"]:
            st.success(f"**H2 SUPPORTED** — F p = {r['p_value']:.4f} < α = {alpha}")
        else:
            st.error(f"**H2 NOT SUPPORTED** — F p = {r['p_value']:.4f} ≥ α = {alpha}")

        # Group table
        try:
            import pandas as pd
            grps = dr["groups"]
            df = pd.DataFrame({
                "Group": [g["label"] for g in grps],
                "Mean Errors": [round(g["mean"], 3) for g in grps],
                "95% CI": [_fmt_ci(g.get("ci95")) for g in grps],
                "Std Dev": [round(g["std"], 3) for g in grps],
                "N": [g["n"] for g in grps],
            })
            st.dataframe(df, use_container_width=True, hide_index=True)
        except (KeyError, ImportError):
            pass

        _render_assumptions(dr)

        # Tukey HSD
        if dr.get("tukey_hsd"):
            st.markdown("**Tukey HSD Post-Hoc Comparisons**")
            try:
                import pandas as pd
                tukey_df = pd.DataFrame(dr["tukey_hsd"])
                tukey_df["significant"] = tukey_df["significant"].map(
                    {True: "✅ p<0.05", False: "n.s."}
                )
                st.dataframe(tukey_df, use_container_width=True, hide_index=True)
            except ImportError:
                st.json(dr["tukey_hsd"])


def _render_overall_verdict(record) -> None:
    st.subheader("Overall Research Verdict")
    s = record.summary
    all_ok = s["all_hypotheses_supported"]

    if all_ok:
        st.success(
            "**All three hypotheses are statistically supported** at α = "
            f"{record.config['alpha']}.\n\n"
            "This provides empirical evidence that FORGE-Vision:\n"
            "1. Reduces task error rates compared to traditional training (H1)\n"
            "2. The hybrid simulation→real-time approach outperforms single-modality approaches (H2)\n"
            "3. Real-time AI feedback reduces task completion time vs post-hoc feedback (H3)"
        )
    else:
        unsupported = [
            h for h in ["H1", "H2", "H3"]
            if not s["hypotheses"][h]["supported"]
        ]
        st.warning(
            f"Hypotheses not supported: {', '.join(unsupported)}. "
            "Review the experimental design or collect more data."
        )

    st.caption(
        "⚠️ Note: These results are based on SYNTHETIC data. "
        "Real participant data must be collected under ethics board approval "
        "before publishing or citing these results in the DBA thesis."
    )


def _render_export(record) -> None:
    st.subheader("Export Results")
    payload = {
        "config": record.config,
        "timestamp": record.timestamp,
        "power_analysis": record.power_analysis,
        "h1_result": record.h1_result,
        "h2_result": record.h2_result,
        "h3_result": record.h3_result,
        "summary": record.summary,
    }
    json_str = json.dumps(payload, indent=2)
    st.download_button(
        label="Download Experiment Record (JSON)",
        data=json_str,
        file_name=f"forge_vision_evaluation_{record.timestamp[:10]}.json",
        mime="application/json",
    )

    with st.expander("View raw JSON"):
        st.code(json_str, language="json")


# ── Operational-data hypothesis tests (seeded dashboard DB) ─────────────────────

def _render_operational_results() -> None:
    st.subheader("Operational-Data Hypothesis Tests (H1 / H2)")
    st.caption(
        "**SYNTHETIC operational data** — per-worker mean deviations/session from the "
        "seeded dashboard database (256 workers across the four arms). This complements "
        "the literature-modelled experiment below with the system's *own* recorded data. "
        "H3 needs a post-hoc-feedback condition that doesn't exist operationally."
    )
    data = api_get("/api/v1/analytics/operational-hypotheses")
    if not data or (not data.get("h1") and not data.get("h2")):
        st.info("Operational hypothesis data unavailable (need seeded sessions across groups).")
        return
    st.caption(f"Workers per group: {data.get('groups_present')}  ·  unit: {data.get('unit')}")

    try:
        import pandas as pd
    except ImportError:
        st.json(data)
        return

    h1 = data.get("h1")
    if h1:
        with st.expander(f"H1 (operational)  ·  {h1.get('test_name', 't-test')}", expanded=True):
            c1, c2, c3 = st.columns(3)
            c1.metric("p-value", f"{h1['p_value']:.4f}")
            c2.metric("Cohen's d", f"{h1['cohens_d']:.3f}")
            c3.metric("Effect", h1["effect_magnitude"].capitalize())
            (st.success if h1["significant"] else st.error)(
                f"**H1 {'SUPPORTED' if h1['significant'] else 'NOT SUPPORTED'}** — p = {h1['p_value']:.4f}"
            )
            df = pd.DataFrame({
                "Group": [h1["group_a"]["label"], h1["group_b"]["label"]],
                "Mean": [h1["group_a"]["mean"], h1["group_b"]["mean"]],
                "95% CI": [_fmt_ci(h1["group_a"].get("ci95")), _fmt_ci(h1["group_b"].get("ci95"))],
                "N": [h1["group_a"]["n"], h1["group_b"]["n"]],
            })
            st.dataframe(df, use_container_width=True, hide_index=True)
            _render_assumptions(h1)

    h2 = data.get("h2")
    if h2:
        with st.expander("H2 (operational)  ·  One-way ANOVA + Tukey HSD", expanded=True):
            c1, c2, c3 = st.columns(3)
            c1.metric("p-value", f"{h2['p_value']:.4f}")
            c2.metric("η²", f"{h2['eta_squared']:.3f}")
            c3.metric("Effect", h2["effect_magnitude"].capitalize())
            (st.success if h2["significant"] else st.error)(
                f"**H2 {'SUPPORTED' if h2['significant'] else 'NOT SUPPORTED'}** — p = {h2['p_value']:.4f}"
            )
            df = pd.DataFrame({
                "Group": [g["label"] for g in h2["groups"]],
                "Mean Errors": [g["mean"] for g in h2["groups"]],
                "95% CI": [_fmt_ci(g.get("ci95")) for g in h2["groups"]],
                "N": [g["n"] for g in h2["groups"]],
            })
            st.dataframe(df, use_container_width=True, hide_index=True)
            if h2.get("tukey_hsd"):
                st.markdown("**Tukey HSD post-hoc**")
                st.dataframe(pd.DataFrame(h2["tukey_hsd"]), use_container_width=True, hide_index=True)
            _render_assumptions(h2)


# ── Continual learning (Enhancement 5) ──────────────────────────────────────────

def _render_continual_learning() -> None:
    st.subheader("Continual Learning (Enhancement 5)")
    st.caption(
        "Run an Elastic Weight Consolidation (EWC) increment on the trained action-"
        "recognition model. The model is fine-tuned on a held-out partition of the "
        "synthetic dataset (a stand-in for newly labelled Phase-B footage) while EWC "
        "protects the knowledge acquired in simulation. **Admin only.**"
    )

    is_admin = str(st.session_state.get("user", {}).get("role", "")) == "admin"
    if not is_admin:
        st.info("Continual-learning runs can only be triggered by an administrator.")
        return

    col1, col2, col3, col4 = st.columns([1, 1, 1, 1.2])
    with col1:
        ewc_lambda = st.number_input("EWC λ (retention strength)", 0.0, 1_000_000.0, 1000.0, step=100.0)
    with col2:
        epochs = st.number_input("Epochs", 1, 10, 1, step=1)
    with col3:
        max_clips = st.number_input("Max clips", 2, 200, 12, step=2)
    with col4:
        st.write("")
        st.write("")
        if st.button("▶ Run incremental learning", type="primary"):
            resp = api_post("/api/v1/continual/run", {
                "ewc_lambda": float(ewc_lambda), "epochs": int(epochs), "max_clips": int(max_clips),
            })
            if resp and resp.get("run_id"):
                st.success(f"Started run `{resp['run_id']}`. It runs in the background — refresh to see results.")
            else:
                st.warning("Could not start a run (a run may already be in progress, or the API is unavailable).")

    if st.button("↻ Refresh runs"):
        st.rerun()

    runs = api_get("/api/v1/continual/runs") or []
    if not runs:
        st.info("No continual-learning runs yet. Trigger one above.")
        return

    try:
        import pandas as pd
        rows = []
        for r in runs:
            m = r.get("metrics", {})
            rows.append({
                "Run": r.get("run_id", ""),
                "Status": r.get("status", ""),
                "Started": (r.get("started_at") or "")[:19].replace("T", " "),
                "Retention": m.get("knowledge_retention"),
                "Base acc (before→after)": (
                    f"{m.get('base_accuracy_before')}→{m.get('base_accuracy_after')}"
                    if m.get("base_accuracy_before") is not None else None
                ),
                "New-data acc": m.get("increment_accuracy"),
                "λ": r.get("params", {}).get("ewc_lambda"),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    except ImportError:
        st.json(runs)

    if any(r.get("status") == "running" for r in runs):
        st.info("A run is currently in progress — click **Refresh runs** in a moment to see its result.")

    latest = runs[0]
    if latest.get("status") == "completed":
        m = latest["metrics"]
        ret = m.get("knowledge_retention")
        st.success(
            f"Latest run `{latest['run_id']}`: prior-task knowledge retained at "
            f"{ret:.1%} after learning new data (base accuracy {m.get('base_accuracy_before')} → "
            f"{m.get('base_accuracy_after')}), new-data accuracy {m.get('increment_accuracy')}."
            if ret is not None else f"Latest run `{latest['run_id']}` completed."
        )
    elif latest.get("status") == "failed":
        st.error(f"Latest run failed: {latest.get('error', 'unknown error')}")


# ── Main render ────────────────────────────────────────────────────────────────

def render() -> None:
    st.divider()
    cfg = _render_config()

    st.divider()
    _render_operational_results()

    st.divider()
    _render_group_distributions(cfg)

    st.divider()
    if st.button("▶ Run Hypothesis Tests", type="primary"):
        with st.spinner("Running statistical analysis…"):
            record = _run_experiment(cfg)
        st.session_state["eval_record"] = record
        st.success("Evaluation complete. Scroll down to view results.")

    st.divider()
    _render_continual_learning()

    record = st.session_state.get("eval_record")
    if record is None:
        st.info("Configure the experiment above, then click **Run Hypothesis Tests**.")
        return

    st.divider()
    _render_power_analysis(record)

    st.divider()
    _render_hypothesis_results(record)

    st.divider()
    _render_overall_verdict(record)

    st.divider()
    _render_export(record)
