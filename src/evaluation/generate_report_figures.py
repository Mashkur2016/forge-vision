"""
Report figure generator — produces the charts embedded in the System
Implementation Report (Phase 5 documentation).

Reads real artefacts only (no fabricated data, Rules.md §3.1):
  - experiments/eval_report.json   — model accuracy, per-class metrics, confusion matrix
  - experiments/latency_report.json — real-time latency benchmark
  - PostgreSQL (seeded synthetic study data) — deviation analytics, group learning curves

All PNGs are written to report/figures/.  Database charts are skipped gracefully
if PostgreSQL is unreachable, so the model/latency charts always render.

Run (host, with the Docker Postgres up on :5433):
    python -m src.evaluation.generate_report_figures
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# ── Paths & house style ──────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
FIG_DIR = ROOT / "report" / "figures"
EVAL_JSON = ROOT / "experiments" / "eval_report.json"
LATENCY_JSON = ROOT / "experiments" / "latency_report.json"

GOLD = "#E6B800"
DARK = "#1a1a1a"
GROUP_COLORS = {
    "control": "#C0392B",        # red — traditional baseline
    "sim_only": "#E67E22",       # orange
    "realtime_only": "#2980B9",  # blue
    "hybrid": "#27AE60",         # green — FORGE-Vision
}

plt.rcParams.update({
    "figure.dpi": 130,
    "savefig.dpi": 130,
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.grid": True,
    "grid.alpha": 0.25,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def _save(fig, name: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / name
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[figures] wrote {path.relative_to(ROOT)}")


# ── Model charts (from eval_report.json) ─────────────────────────────────────

def fig_confusion_matrix(report: dict) -> None:
    cm = np.array(report["confusion_matrix"]["normalised"], dtype=float)
    labels = report["confusion_matrix"]["class_names"]
    fig, ax = plt.subplots(figsize=(6.4, 5.4))
    im = ax.imshow(cm, cmap="YlOrBr", vmin=0, vmax=1)
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted class")
    ax.set_ylabel("True class")
    ax.set_title("Action-Recognition Confusion Matrix (normalised)")
    for i in range(len(labels)):
        for j in range(len(labels)):
            v = cm[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    color="white" if v > 0.5 else DARK, fontsize=10)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Proportion")
    ax.grid(False)
    _save(fig, "fig_confusion_matrix.png")


def fig_per_class_metrics(report: dict) -> None:
    rows = report["per_class"]
    labels = [r["class"] for r in rows]
    prec = [r["precision"] for r in rows]
    rec = [r["recall"] for r in rows]
    f1 = [r["f1"] for r in rows]
    x = np.arange(len(labels))
    w = 0.26
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    ax.bar(x - w, prec, w, label="Precision", color="#2980B9")
    ax.bar(x, rec, w, label="Recall", color=GOLD)
    ax.bar(x + w, f1, w, label="F1", color="#27AE60")
    ax.axhline(0.80, ls="--", lw=1, color=DARK, alpha=0.6, label="0.80 target")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Per-Class Precision / Recall / F1 (held-out test set)")
    ax.legend(ncol=4, fontsize=9, loc="lower center", bbox_to_anchor=(0.5, -0.32))
    _save(fig, "fig_per_class_metrics.png")


def fig_training_curve() -> None:
    # Logged trajectory from the Phase-2 training run (MLflow run 9e672d1f...).
    epochs = [1, 4, 7, 8, 10, 15, 16, 26]
    train = [0.273, 0.639, 0.756, 0.819, 0.861, 0.934, 0.942, 0.997]
    val = [0.344, 0.600, 0.761, 0.817, 0.844, 0.922, 0.939, 0.889]
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    ax.plot(epochs, train, "-o", color="#2980B9", label="Train accuracy")
    ax.plot(epochs, val, "-s", color=GOLD, label="Validation accuracy")
    ax.axhline(0.80, ls="--", lw=1, color=DARK, alpha=0.6, label="0.80 target")
    ax.axvline(16, ls=":", lw=1, color="#27AE60", alpha=0.8)
    ax.annotate("best model\n(epoch 16, val 0.939)", xy=(16, 0.939),
                xytext=(17.5, 0.62), fontsize=9,
                arrowprops=dict(arrowstyle="->", color=DARK, alpha=0.6))
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Accuracy")
    ax.set_ylim(0.2, 1.02)
    ax.set_title("Action-Recognition Training vs Validation Accuracy")
    ax.legend(loc="lower right", fontsize=9)
    _save(fig, "fig_training_curve.png")


def fig_latency(report_eval: dict, report_lat: dict) -> None:
    res = report_lat["results"]
    comps = ["CV pipeline", "Action inference", "End-to-end"]
    p95 = [res["cv_pipeline"]["p95_ms"], res["action_inference"]["p95_ms"],
           res["end_to_end"]["p95_ms"]]
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    bars = ax.bar(comps, p95, color=[GOLD, "#2980B9", "#27AE60"], width=0.55)
    ax.axhline(2000, ls="--", lw=1.2, color="#C0392B", label="2 000 ms feedback budget")
    ax.set_ylabel("p95 latency (ms)")
    ax.set_title("Real-Time Latency vs 2-Second Feedback Target")
    ax.set_yscale("log")
    for b, v in zip(bars, p95):
        ax.text(b.get_x() + b.get_width() / 2, v * 1.15, f"{v:.1f} ms",
                ha="center", fontsize=9)
    ax.legend(fontsize=9)
    _save(fig, "fig_latency_components.png")


# ── Database charts (from seeded PostgreSQL) ─────────────────────────────────

def _connect():
    import psycopg2
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5433")),
        user=os.getenv("POSTGRES_USER", "forgevision"),
        password=os.getenv("POSTGRES_PASSWORD", "forgevision_dev_pass"),
        dbname=os.getenv("POSTGRES_DB", "forgevision"),
        connect_timeout=5,
    )


def fig_deviation_distribution(cur) -> None:
    cur.execute("SELECT deviation_class, count(*) FROM deviation_logs "
                "GROUP BY deviation_class ORDER BY count(*) DESC")
    rows = cur.fetchall()
    labels = [r[0] for r in rows]
    counts = [r[1] for r in rows]
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    ax.bar(labels, counts, color=GOLD, width=0.6)
    ax.set_ylabel("Number of events")
    ax.set_title("Deviation-Class Distribution (synthetic study, n=8,441 events)")
    ax.tick_params(axis="x", rotation=20)
    for i, v in enumerate(counts):
        ax.text(i, v, f"{v:,}", ha="center", va="bottom", fontsize=9)
    _save(fig, "fig_deviation_distribution.png")


def fig_severity_mix(cur) -> None:
    cur.execute("SELECT severity, count(*) FROM deviation_logs GROUP BY severity")
    data = dict(cur.fetchall())
    order = [s for s in ("low", "medium", "high") if s in data]
    vals = [data[s] for s in order]
    colors = {"low": "#27AE60", "medium": GOLD, "high": "#C0392B"}
    fig, ax = plt.subplots(figsize=(5.6, 5.0))
    ax.pie(vals, labels=[s.title() for s in order], autopct="%1.1f%%",
           colors=[colors[s] for s in order], startangle=90,
           wedgeprops=dict(edgecolor="white", linewidth=1.5))
    ax.set_title("Deviation Severity Mix")
    _save(fig, "fig_severity_mix.png")


def fig_group_comparison(cur) -> None:
    cur.execute(
        "SELECT split_part(u.email,'.',1) grp, avg(w.total_deviations), "
        "avg(w.total_sessions) FROM users u JOIN worker_profiles w ON w.user_id=u.id "
        "WHERE u.role='staff' GROUP BY grp"
    )
    data = {r[0]: (float(r[1]), float(r[2])) for r in cur.fetchall()}
    order = [g for g in ("control", "sim_only", "realtime_only", "hybrid") if g in data]
    devs = [data[g][0] for g in order]
    sess = [data[g][1] for g in order]
    nice = {"control": "Control\n(traditional)", "sim_only": "Sim-only",
            "realtime_only": "Real-time\nonly", "hybrid": "Hybrid\n(FORGE-Vision)"}
    x = np.arange(len(order))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.6))
    ax1.bar(x, devs, color=[GROUP_COLORS[g] for g in order], width=0.6)
    ax1.set_xticks(x); ax1.set_xticklabels([nice[g] for g in order], fontsize=9)
    ax1.set_ylabel("Avg deviations per worker")
    ax1.set_title("Total Deviations by Training Group (H1)")
    for i, v in enumerate(devs):
        ax1.text(i, v, f"{v:.1f}", ha="center", va="bottom", fontsize=9)
    ax2.bar(x, sess, color=[GROUP_COLORS[g] for g in order], width=0.6)
    ax2.set_xticks(x); ax2.set_xticklabels([nice[g] for g in order], fontsize=9)
    ax2.set_ylabel("Avg sessions to competency")
    ax2.set_title("Sessions to Competency by Group (H2)")
    for i, v in enumerate(sess):
        ax2.text(i, v, f"{v:.1f}", ha="center", va="bottom", fontsize=9)
    _save(fig, "fig_group_comparison.png")


def fig_learning_curve(cur) -> None:
    cur.execute(
        "SELECT grp, idx, avg(deviation_count) FROM ("
        "  SELECT split_part(u.email,'.',1) grp, t.deviation_count, "
        "  row_number() OVER (PARTITION BY t.worker_id ORDER BY t.started_at) idx "
        "  FROM training_session_logs t JOIN users u ON u.id=t.worker_id "
        "  WHERE u.role='staff') s GROUP BY grp, idx ORDER BY grp, idx"
    )
    series: dict[str, list[tuple[int, float]]] = {}
    for grp, idx, avg in cur.fetchall():
        series.setdefault(grp, []).append((int(idx), float(avg)))
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    nice = {"control": "Control (traditional)", "sim_only": "Sim-only",
            "realtime_only": "Real-time only", "hybrid": "Hybrid (FORGE-Vision)"}
    for grp in ("control", "sim_only", "realtime_only", "hybrid"):
        if grp in series:
            pts = sorted(series[grp])[:8]  # first 8 sessions
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            ax.plot(xs, ys, "-o", color=GROUP_COLORS[grp], label=nice[grp])
    ax.set_xlabel("Session number")
    ax.set_ylabel("Avg deviations per session")
    ax.set_title("Learning Curves by Training Group")
    ax.legend(fontsize=9)
    _save(fig, "fig_learning_curve.png")


def fig_llm_distribution(cur) -> None:
    cur.execute("SELECT llm_provider, count(*) FROM training_session_logs "
                "WHERE llm_provider IS NOT NULL GROUP BY llm_provider ORDER BY count(*) DESC")
    rows = cur.fetchall()
    if not rows:
        return
    labels = [r[0] for r in rows]
    counts = [r[1] for r in rows]
    fig, ax = plt.subplots(figsize=(6.2, 4.4))
    ax.bar(labels, counts, color=["#2980B9", "#27AE60", GOLD][: len(labels)], width=0.5)
    ax.set_ylabel("Sessions")
    ax.set_title("LLM Provider Usage Across Sessions (Task 5.7 baseline)")
    for i, v in enumerate(counts):
        ax.text(i, v, f"{v:,}", ha="center", va="bottom", fontsize=9)
    _save(fig, "fig_llm_distribution.png")


# ── Orchestration ────────────────────────────────────────────────────────────

def main() -> None:
    eval_report = json.loads(EVAL_JSON.read_text(encoding="utf-8"))
    latency_report = json.loads(LATENCY_JSON.read_text(encoding="utf-8"))

    print("[figures] generating model & latency charts ...")
    fig_confusion_matrix(eval_report)
    fig_per_class_metrics(eval_report)
    fig_training_curve()
    fig_latency(eval_report, latency_report)

    print("[figures] generating database charts ...")
    try:
        conn = _connect()
        try:
            cur = conn.cursor()
            fig_deviation_distribution(cur)
            fig_severity_mix(cur)
            fig_group_comparison(cur)
            fig_learning_curve(cur)
            fig_llm_distribution(cur)
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — DB charts are optional
        print(f"[figures] WARNING: skipped database charts (Postgres unreachable): {exc}")

    print(f"[figures] done -> {FIG_DIR}")


if __name__ == "__main__":
    main()
