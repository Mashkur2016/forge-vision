"""
Statistical Hypothesis Tester — Phase 5 (Task 5.1).

Tests the three DBA research hypotheses with rigorous statistical methods
as required by Rules.md §3.2:

    H1: FORGE-Vision produces a statistically significant reduction in
        task error rates compared to traditional (control) training.
        Test: Independent-samples Welch t-test + Cohen's d

    H2: The hybrid simulation→real-time approach produces better skill
        transfer than simulation-only or real-time-only methods.
        Test: One-way ANOVA + Tukey HSD post-hoc comparisons

    H3: Real-time AI feedback significantly reduces task completion time
        compared to post-hoc (end-of-session) feedback.
        Test: Independent-samples Welch t-test + Cohen's d

All tests use significance level α = 0.05 per Rules.md §3.2.
Effect sizes reported as Cohen's d (H1, H3) and η² (H2).

Requires: scipy, numpy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy import stats


# ── Constants ─────────────────────────────────────────────────────────────────

ALPHA: float = 0.05   # Significance level (Rules.md §3.2)


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class TTestResult:
    """
    Result of an independent-samples Welch t-test.

    Rules.md §3.2: report t-statistic, p-value, degrees of freedom,
    Cohen's d effect size, and whether the null hypothesis is rejected.
    """
    hypothesis: str
    group_a_label: str
    group_b_label: str
    n_a: int
    n_b: int
    mean_a: float
    mean_b: float
    std_a: float
    std_b: float
    t_statistic: float
    degrees_of_freedom: float
    p_value: float
    cohens_d: float
    effect_magnitude: str       # "negligible" | "small" | "medium" | "large"
    significant: bool           # True if p < ALPHA
    alpha: float = ALPHA
    paired: bool = False                       # within-subjects (paired) design?
    test_name: str = "Welch's independent t-test"
    ci_a: tuple[float, float] | None = None    # 95% CI of group A mean
    ci_b: tuple[float, float] | None = None    # 95% CI of group B mean
    mean_diff_ci: tuple[float, float] | None = None  # 95% CI of mean difference (paired)
    normality: list[dict] | None = None        # Shapiro-Wilk per group
    homogeneity: dict | None = None            # Levene's test (independent only)

    def summary(self) -> str:
        direction = (
            f"{self.group_b_label} < {self.group_a_label}"
            if self.mean_b < self.mean_a
            else f"{self.group_b_label} > {self.group_a_label}"
        )
        verdict = "SUPPORTED" if self.significant else "NOT SUPPORTED"
        return (
            f"{self.hypothesis}\n"
            f"  Groups: {self.group_a_label} (n={self.n_a}, μ={self.mean_a:.3f}, "
            f"σ={self.std_a:.3f}) vs {self.group_b_label} (n={self.n_b}, "
            f"μ={self.mean_b:.3f}, σ={self.std_b:.3f})\n"
            f"  Direction: {direction}\n"
            f"  t({self.degrees_of_freedom:.1f}) = {self.t_statistic:.4f}, "
            f"p = {self.p_value:.4f} {'<' if self.significant else '>='} α={self.alpha}\n"
            f"  Cohen's d = {self.cohens_d:.3f} ({self.effect_magnitude})\n"
            f"  Verdict: {verdict}"
        )

    def to_dict(self) -> dict:
        def _r(ci):
            return [round(ci[0], 4), round(ci[1], 4)] if ci else None
        return {
            "hypothesis": self.hypothesis,
            "test_name": self.test_name,
            "paired": self.paired,
            "group_a": {"label": self.group_a_label, "n": self.n_a,
                        "mean": round(self.mean_a, 4), "std": round(self.std_a, 4),
                        "ci95": _r(self.ci_a)},
            "group_b": {"label": self.group_b_label, "n": self.n_b,
                        "mean": round(self.mean_b, 4), "std": round(self.std_b, 4),
                        "ci95": _r(self.ci_b)},
            "t_statistic": round(self.t_statistic, 4),
            "degrees_of_freedom": round(self.degrees_of_freedom, 2),
            "p_value": round(self.p_value, 6),
            "cohens_d": round(self.cohens_d, 4),
            "effect_magnitude": self.effect_magnitude,
            "significant": self.significant,
            "alpha": self.alpha,
            "mean_diff_ci95": _r(self.mean_diff_ci),
            "normality": self.normality,
            "homogeneity": self.homogeneity,
        }


@dataclass
class AnovaResult:
    """
    Result of a one-way ANOVA with Tukey HSD post-hoc comparisons.

    Rules.md §3.2: report F-statistic, p-value, η² effect size, and
    pairwise post-hoc results.
    """
    hypothesis: str
    group_labels: list[str]
    group_ns: list[int]
    group_means: list[float]
    group_stds: list[float]
    f_statistic: float
    p_value: float
    eta_squared: float
    effect_magnitude: str       # "negligible" | "small" | "medium" | "large"
    significant: bool
    tukey_results: list[dict]   # Pairwise comparisons
    alpha: float = ALPHA
    group_cis: list[tuple[float, float]] | None = None  # 95% CI per group mean
    normality: list[dict] | None = None                 # Shapiro-Wilk per group
    homogeneity: dict | None = None                     # Levene's test

    def summary(self) -> str:
        verdict = "SUPPORTED" if self.significant else "NOT SUPPORTED"
        lines = [
            f"{self.hypothesis}",
            f"  Groups: " + ", ".join(
                f"{l} (n={n}, μ={m:.3f})"
                for l, n, m in zip(self.group_labels, self.group_ns, self.group_means)
            ),
            f"  F({len(self.group_labels)-1}, {sum(self.group_ns)-len(self.group_labels)}) = "
            f"{self.f_statistic:.4f}, p = {self.p_value:.4f} "
            f"{'<' if self.significant else '>='} α={self.alpha}",
            f"  η² = {self.eta_squared:.4f} ({self.effect_magnitude})",
            f"  Verdict: {verdict}",
        ]
        if self.significant and self.tukey_results:
            lines.append("  Tukey HSD post-hoc:")
            for r in self.tukey_results:
                sig_marker = "* p<0.05" if r["significant"] else "  n.s."
                lines.append(
                    f"    {r['group_a']} vs {r['group_b']}: "
                    f"Δμ={r['mean_diff']:+.3f}, p={r['p_value']:.4f} {sig_marker}"
                )
        return "\n".join(lines)

    def to_dict(self) -> dict:
        cis = self.group_cis or [None] * len(self.group_labels)
        return {
            "hypothesis": self.hypothesis,
            "test_name": "One-way ANOVA + Tukey HSD",
            "groups": [
                {"label": l, "n": n, "mean": round(m, 4), "std": round(s, 4),
                 "ci95": ([round(c[0], 4), round(c[1], 4)] if c else None)}
                for l, n, m, s, c in zip(
                    self.group_labels, self.group_ns,
                    self.group_means, self.group_stds, cis
                )
            ],
            "f_statistic": round(self.f_statistic, 4),
            "p_value": round(self.p_value, 6),
            "eta_squared": round(self.eta_squared, 4),
            "effect_magnitude": self.effect_magnitude,
            "significant": self.significant,
            "alpha": self.alpha,
            "tukey_hsd": self.tukey_results,
            "normality": self.normality,
            "homogeneity": self.homogeneity,
        }


@dataclass
class PowerAnalysisResult:
    """Required sample size from an a-priori power analysis."""
    effect_size: float          # Cohen's d target
    alpha: float
    power: float                # Target statistical power (1 - β)
    n_per_group: int            # Required per group (two-sample t-test)
    total_n: int


# ── Main class ────────────────────────────────────────────────────────────────

class HypothesisTester:
    """
    Run the three DBA research hypothesis tests with full statistical rigour.

    Rules.md §3.2: α = 0.05; Welch t-test; Cohen's d; ANOVA + Tukey HSD.

    Usage:
        tester = HypothesisTester()

        # H1: error rates
        result = tester.test_h1(
            control_errors=[5, 6, 4, 7, ...],
            treatment_errors=[2, 3, 1, 2, ...],
        )
        print(result.summary())
    """

    def __init__(self, alpha: float = ALPHA) -> None:
        self.alpha = alpha

    # ── H1: Error rate reduction ───────────────────────────────────────────

    def test_h1(
        self,
        control_errors: list[float],
        treatment_errors: list[float],
        label_control: str = "Traditional Training",
        label_treatment: str = "FORGE-Vision",
    ) -> TTestResult:
        """
        H1: FORGE-Vision reduces task error rates vs traditional training.

        One-tailed test: treatment mean < control mean.
        """
        return self._welch_ttest(
            hypothesis="H1: FORGE-Vision reduces task error rates",
            group_a=control_errors,
            group_b=treatment_errors,
            label_a=label_control,
            label_b=label_treatment,
            alternative="greater",   # control > treatment (scipy: μ_a > μ_b)
        )

    # ── H2: Hybrid approach skill transfer ────────────────────────────────

    def test_h2(
        self,
        sim_only_errors: list[float],
        realtime_only_errors: list[float],
        hybrid_errors: list[float],
        label_sim: str = "Simulation-Only",
        label_realtime: str = "Real-Time-Only",
        label_hybrid: str = "Hybrid",
    ) -> AnovaResult:
        """
        H2: Hybrid approach produces better skill transfer (lower errors)
        than simulation-only or real-time-only methods.

        One-way ANOVA + Tukey HSD post-hoc.
        """
        groups = [
            (label_sim, np.asarray(sim_only_errors, dtype=float)),
            (label_realtime, np.asarray(realtime_only_errors, dtype=float)),
            (label_hybrid, np.asarray(hybrid_errors, dtype=float)),
        ]
        return self._one_way_anova(
            hypothesis="H2: Hybrid approach produces better skill transfer",
            groups=groups,
        )

    # ── H3: Real-time feedback reduces completion time ────────────────────

    def test_h3(
        self,
        posthoc_times: list[float],
        realtime_times: list[float],
        label_posthoc: str = "Post-Hoc Feedback",
        label_realtime: str = "Real-Time Feedback",
    ) -> TTestResult:
        """
        H3: Real-time feedback significantly reduces task completion time.

        Within-subjects (paired) design: the SAME participants are measured under
        both feedback conditions, so a paired t-test is used (more powerful than
        an independent test as it removes between-participant variance).
        One-tailed: post-hoc time > real-time time.
        """
        return self._paired_ttest(
            hypothesis="H3: Real-time feedback reduces task completion time",
            group_a=posthoc_times,
            group_b=realtime_times,
            label_a=label_posthoc,
            label_b=label_realtime,
            alternative="greater",   # posthoc > realtime
        )

    def _paired_ttest(
        self,
        hypothesis: str,
        group_a: list[float],
        group_b: list[float],
        label_a: str,
        label_b: str,
        alternative: str = "two-sided",
    ) -> TTestResult:
        """Paired-samples t-test (same participants, two conditions)."""
        a = np.asarray(group_a, dtype=float)
        b = np.asarray(group_b, dtype=float)
        if len(a) != len(b):
            raise ValueError("Paired t-test requires equal-length arrays.")

        t_stat, p_val = stats.ttest_rel(a, b, alternative=alternative)
        diff = a - b
        n = len(a)
        sd_diff = float(np.std(diff, ddof=1)) if n > 1 else 0.0
        # Paired effect size: Cohen's dz = mean(diff) / sd(diff)
        dz = float(np.mean(diff) / sd_diff) if sd_diff > 0 else 0.0
        # 95% CI of the mean difference
        se_diff = sd_diff / math.sqrt(n) if n > 0 else 0.0
        h = se_diff * float(stats.t.ppf(0.975, n - 1)) if n > 1 else 0.0
        md = float(np.mean(diff))

        return TTestResult(
            hypothesis=hypothesis,
            group_a_label=label_a,
            group_b_label=label_b,
            n_a=n,
            n_b=n,
            mean_a=float(np.mean(a)),
            mean_b=float(np.mean(b)),
            std_a=float(np.std(a, ddof=1)) if n > 1 else 0.0,
            std_b=float(np.std(b, ddof=1)) if n > 1 else 0.0,
            t_statistic=float(t_stat),
            degrees_of_freedom=float(n - 1),
            p_value=float(p_val),
            cohens_d=dz,
            effect_magnitude=self._effect_magnitude_d(abs(dz)),
            significant=float(p_val) < self.alpha,
            alpha=self.alpha,
            paired=True,
            test_name="Paired-samples t-test (one-tailed)",
            ci_a=self._mean_ci(a),
            ci_b=self._mean_ci(b),
            mean_diff_ci=(round(md - h, 4), round(md + h, 4)),
            normality=self._normality(["difference"], [diff]),
            homogeneity=None,  # not applicable to paired design
        )

    # ── A-priori power analysis ────────────────────────────────────────────

    def power_analysis(
        self,
        effect_size: float = 0.5,    # Medium effect (Cohen's d)
        alpha: float | None = None,
        power: float = 0.80,
    ) -> PowerAnalysisResult:
        """
        Compute required sample size per group using the formula for a
        two-sample independent t-test.

        Uses the approximation:
            n ≈ 2 * ((z_α + z_β) / d)²
        where z_α = z-score for α (one-tailed) and z_β for β.

        For more accurate results (small d), the iterative chi-squared
        noncentrality approach is used via scipy.

        Returns:
            PowerAnalysisResult with n_per_group.
        """
        alpha = alpha or self.alpha
        from scipy.stats import norm, t as t_dist

        # Use scipy's power formula via numerical search
        z_alpha = norm.ppf(1.0 - alpha)
        z_beta = norm.ppf(power)
        # n per group (approximate, valid for large n):
        n_approx = math.ceil(2.0 * ((z_alpha + z_beta) / effect_size) ** 2)

        # Refine: iterate to find n where achieved power ≥ target
        n = max(n_approx - 10, 2)
        while True:
            df = 2 * n - 2
            ncp = effect_size * math.sqrt(n / 2.0)
            achieved_power = 1.0 - t_dist.cdf(
                t_dist.ppf(1.0 - alpha, df), df, loc=ncp
            )
            if achieved_power >= power:
                break
            n += 1
            if n > 10_000:
                break   # Safety stop

        return PowerAnalysisResult(
            effect_size=effect_size,
            alpha=alpha,
            power=power,
            n_per_group=n,
            total_n=n * 2,
        )

    # ── Private helpers ────────────────────────────────────────────────────

    def _welch_ttest(
        self,
        hypothesis: str,
        group_a: list[float],
        group_b: list[float],
        label_a: str,
        label_b: str,
        alternative: str = "two-sided",
    ) -> TTestResult:
        a = np.asarray(group_a, dtype=float)
        b = np.asarray(group_b, dtype=float)

        t_stat, p_val = stats.ttest_ind(a, b, equal_var=False, alternative=alternative)

        # Welch–Satterthwaite degrees of freedom
        s_a, s_b = float(np.std(a, ddof=1)), float(np.std(b, ddof=1))
        n_a, n_b = len(a), len(b)
        num = (s_a**2 / n_a + s_b**2 / n_b) ** 2
        denom = (s_a**2 / n_a)**2 / (n_a - 1) + (s_b**2 / n_b)**2 / (n_b - 1)
        df = num / denom if denom > 0 else float(n_a + n_b - 2)

        d = self._cohens_d(a, b)

        return TTestResult(
            hypothesis=hypothesis,
            group_a_label=label_a,
            group_b_label=label_b,
            n_a=n_a,
            n_b=n_b,
            mean_a=float(np.mean(a)),
            mean_b=float(np.mean(b)),
            std_a=s_a,
            std_b=s_b,
            t_statistic=float(t_stat),
            degrees_of_freedom=float(df),
            p_value=float(p_val),
            cohens_d=d,
            effect_magnitude=self._effect_magnitude_d(abs(d)),
            significant=float(p_val) < self.alpha,
            alpha=self.alpha,
            test_name="Welch's independent t-test (one-tailed)",
            ci_a=self._mean_ci(a),
            ci_b=self._mean_ci(b),
            normality=self._normality([label_a, label_b], [a, b]),
            homogeneity=self._homogeneity([a, b]),
        )

    def _one_way_anova(
        self,
        hypothesis: str,
        groups: list[tuple[str, np.ndarray]],
    ) -> AnovaResult:
        arrays = [arr for _, arr in groups]
        labels = [lbl for lbl, _ in groups]

        f_stat, p_val = stats.f_oneway(*arrays)

        # η² = SS_between / SS_total
        grand_mean = np.mean(np.concatenate(arrays))
        ss_between = sum(
            len(arr) * (np.mean(arr) - grand_mean) ** 2 for arr in arrays
        )
        ss_total = sum(np.sum((arr - grand_mean) ** 2) for arr in arrays)
        eta_sq = float(ss_between / ss_total) if ss_total > 0 else 0.0

        # Tukey HSD pairwise comparisons
        tukey = self._tukey_hsd(labels, arrays)

        return AnovaResult(
            hypothesis=hypothesis,
            group_labels=labels,
            group_ns=[len(a) for a in arrays],
            group_means=[float(np.mean(a)) for a in arrays],
            group_stds=[float(np.std(a, ddof=1)) for a in arrays],
            f_statistic=float(f_stat),
            p_value=float(p_val),
            eta_squared=eta_sq,
            effect_magnitude=self._effect_magnitude_eta(eta_sq),
            significant=float(p_val) < self.alpha,
            tukey_results=tukey,
            alpha=self.alpha,
            group_cis=[self._mean_ci(a) for a in arrays],
            normality=self._normality(labels, arrays),
            homogeneity=self._homogeneity(arrays),
        )

    @staticmethod
    def _cohens_d(a: np.ndarray, b: np.ndarray) -> float:
        """Pooled Cohen's d: (μ_b - μ_a) / s_pooled."""
        n_a, n_b = len(a), len(b)
        s_a = float(np.std(a, ddof=1)) if n_a > 1 else 0.0
        s_b = float(np.std(b, ddof=1)) if n_b > 1 else 0.0
        s_pooled = math.sqrt(((n_a - 1) * s_a**2 + (n_b - 1) * s_b**2) / (n_a + n_b - 2))
        if s_pooled == 0:
            return 0.0
        return (float(np.mean(b)) - float(np.mean(a))) / s_pooled

    @staticmethod
    def _mean_ci(arr: np.ndarray, conf: float = 0.95) -> tuple[float, float]:
        """t-based confidence interval for the mean."""
        n = len(arr)
        if n < 2:
            m = float(np.mean(arr)) if n else 0.0
            return (m, m)
        m = float(np.mean(arr))
        se = float(np.std(arr, ddof=1)) / math.sqrt(n)
        h = se * float(stats.t.ppf((1 + conf) / 2.0, n - 1))
        return (round(m - h, 4), round(m + h, 4))

    @staticmethod
    def _normality(labels: list[str], arrays: list[np.ndarray]) -> list[dict]:
        """Shapiro-Wilk normality test per group (n in 3..5000)."""
        out: list[dict] = []
        for lbl, a in zip(labels, arrays):
            if 3 <= len(a) <= 5000:
                try:
                    w, p = stats.shapiro(a)
                    out.append({"group": lbl, "p_value": round(float(p), 4),
                                "normal": bool(p > ALPHA)})
                    continue
                except Exception:
                    pass
            out.append({"group": lbl, "p_value": None, "normal": None})
        return out

    @staticmethod
    def _homogeneity(arrays: list[np.ndarray]) -> dict:
        """Levene's test for equality of variances across groups."""
        try:
            stat, p = stats.levene(*arrays)
            return {"test": "Levene", "p_value": round(float(p), 4),
                    "equal_variance": bool(p > ALPHA)}
        except Exception:
            return {"test": "Levene", "p_value": None, "equal_variance": None}

    @staticmethod
    def _effect_magnitude_d(d: float) -> str:
        """Cohen (1988) conventions for d."""
        if d < 0.20:
            return "negligible"
        elif d < 0.50:
            return "small"
        elif d < 0.80:
            return "medium"
        return "large"

    @staticmethod
    def _effect_magnitude_eta(eta_sq: float) -> str:
        """Cohen (1988) conventions for η²."""
        if eta_sq < 0.01:
            return "negligible"
        elif eta_sq < 0.06:
            return "small"
        elif eta_sq < 0.14:
            return "medium"
        return "large"

    @staticmethod
    def _tukey_hsd(
        labels: list[str],
        arrays: list[np.ndarray],
    ) -> list[dict]:
        """
        Tukey HSD pairwise comparisons.

        Uses the Studentised Range Distribution (scipy.stats.studentized_range)
        where available.  Falls back to Bonferroni correction for safety.
        """
        k = len(arrays)
        n_total = sum(len(a) for a in arrays)
        # MS_within (residual mean square)
        grand_mean = np.mean(np.concatenate(arrays))
        ss_within = sum(np.sum((a - np.mean(a)) ** 2) for a in arrays)
        df_within = n_total - k
        ms_within = ss_within / df_within if df_within > 0 else 1.0

        results = []
        for i in range(k):
            for j in range(i + 1, k):
                a, b = arrays[i], arrays[j]
                n_harm = 2.0 / (1.0 / len(a) + 1.0 / len(b))   # harmonic mean n
                se = math.sqrt(ms_within / n_harm * 2)
                mean_diff = float(np.mean(b) - np.mean(a))
                q_stat = abs(mean_diff) / se if se > 0 else 0.0

                # Critical value using studentized range distribution
                try:
                    p_val = float(
                        stats.studentized_range.sf(q_stat, k, df_within)
                    )
                except Exception:
                    # Fallback: Bonferroni-corrected two-tailed t-test
                    n_comparisons = k * (k - 1) // 2
                    _, p_raw = stats.ttest_ind(a, b, equal_var=True)
                    p_val = min(float(p_raw) * n_comparisons, 1.0)

                results.append({
                    "group_a": labels[i],
                    "group_b": labels[j],
                    "mean_diff": round(mean_diff, 4),
                    "q_statistic": round(q_stat, 4),
                    "p_value": round(p_val, 6),
                    "significant": p_val < ALPHA,
                })
        return results
