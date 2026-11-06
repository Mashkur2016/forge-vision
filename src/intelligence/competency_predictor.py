"""
Competency Predictor — Enhancement 6 (Phase 4, Task 4.4).

Predicts how many additional training sessions a worker needs to reach
competency, defined as a deviation rate below a target threshold.

Method:
    Uses exponential smoothing on the per-session deviation rate to model
    the learning curve.  When the smoothed rate drops below the competency
    threshold, the worker is declared competent.  When the trend is still
    above the threshold, linear extrapolation gives an estimate of
    sessions remaining.

This is intentionally simple and transparent — appropriate for a DBA
research context where explainability (Rules.md §1.6) is a requirement.
A more complex ARIMA or Bayesian model would be less interpretable.

Architecture.md Layer 3: Intelligence — Analytics.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


# ── Configuration ──────────────────────────────────────────────────────────

# A worker is competent when their deviation rate (deviations/second) drops
# below this threshold for two consecutive sessions.
COMPETENCY_THRESHOLD: float = 0.05  # deviations per second

# Exponential smoothing factor (0 = all history, 1 = only latest)
SMOOTHING_ALPHA: float = 0.4

# Maximum sessions to predict (cap extrapolation)
MAX_SESSIONS_ESTIMATE: int = 50


@dataclass
class CompetencyEstimate:
    """Result of a competency prediction."""
    sessions_completed: int
    smoothed_rate: float          # Current smoothed deviation rate
    competency_threshold: float   # Target rate
    competency_reached: bool      # True if already competent
    sessions_to_competency_est: Optional[int]  # None if already competent
    trend: str                    # "improving" | "plateau" | "regressing"
    message: str


class CompetencyPredictor:
    """
    Predict sessions-to-competency from a worker's deviation rate history.

    Usage:
        predictor = CompetencyPredictor()
        rates = [0.30, 0.22, 0.18, 0.14, 0.11]  # deviations/second per session
        estimate = predictor.predict(rates)
        print(estimate["sessions_to_competency_est"])
    """

    def __init__(
        self,
        competency_threshold: float = COMPETENCY_THRESHOLD,
        smoothing_alpha: float = SMOOTHING_ALPHA,
    ) -> None:
        self._threshold = competency_threshold
        self._alpha = smoothing_alpha

    def predict(self, deviation_rates: list[float]) -> dict:
        """
        Estimate sessions to competency from a sequence of per-session rates.

        Args:
            deviation_rates: List of (deviations / session_duration_seconds)
                             values, one per completed session, oldest first.

        Returns:
            Dict with prediction results.
        """
        if not deviation_rates:
            return {
                "sessions_completed": 0,
                "smoothed_rate": None,
                "competency_threshold": self._threshold,
                "competency_reached": False,
                "sessions_to_competency_est": None,
                "trend": "unknown",
                "message": "No session data available.",
            }

        # ── Exponential smoothing ──────────────────────────────────────────
        smoothed = deviation_rates[0]
        for rate in deviation_rates[1:]:
            smoothed = self._alpha * rate + (1 - self._alpha) * smoothed

        smoothed = round(smoothed, 4)
        n = len(deviation_rates)

        # ── Competency reached? ────────────────────────────────────────────
        competency_reached = smoothed <= self._threshold

        # ── Trend detection ────────────────────────────────────────────────
        trend = self._compute_trend(deviation_rates)

        # ── Sessions-to-competency estimate ───────────────────────────────
        sessions_est: Optional[int] = None
        if competency_reached:
            message = (
                f"Worker has reached competency (smoothed deviation rate "
                f"{smoothed:.4f} < threshold {self._threshold})."
            )
        elif trend == "regressing":
            message = (
                "Deviation rate is increasing. Review training approach "
                "before estimating competency timeline."
            )
        else:
            sessions_est = self._extrapolate(smoothed, deviation_rates)
            message = (
                f"Estimated {sessions_est} more sessions to competency "
                f"(current rate: {smoothed:.4f}, target: {self._threshold})."
            )

        return {
            "sessions_completed": n,
            "smoothed_rate": smoothed,
            "competency_threshold": self._threshold,
            "competency_reached": competency_reached,
            "sessions_to_competency_est": sessions_est,
            "trend": trend,
            "message": message,
        }

    # ── Private helpers ───────────────────────────────────────────────────

    def _compute_trend(self, rates: list[float]) -> str:
        """
        Classify recent trend as improving, plateau, or regressing.

        Uses the last 3 sessions (or all sessions if fewer than 3).
        """
        if len(rates) < 2:
            return "unknown"

        window = rates[-3:] if len(rates) >= 3 else rates
        delta = window[-1] - window[0]
        pct_change = delta / max(window[0], 1e-9)

        if pct_change < -0.05:
            return "improving"
        elif pct_change > 0.05:
            return "regressing"
        else:
            return "plateau"

    def _extrapolate(self, smoothed: float, rates: list[float]) -> int:
        """
        Linearly extrapolate how many sessions until smoothed rate reaches
        the competency threshold.

        Falls back to MAX_SESSIONS_ESTIMATE if the rate is not declining.
        """
        if len(rates) < 2:
            return MAX_SESSIONS_ESTIMATE

        # Average decline per session over the last 3 sessions
        window = rates[-min(3, len(rates)):]
        decline = (window[0] - window[-1]) / max(len(window) - 1, 1)

        if decline <= 0:
            return MAX_SESSIONS_ESTIMATE

        gap = smoothed - self._threshold
        sessions = math.ceil(gap / decline)
        return min(max(sessions, 1), MAX_SESSIONS_ESTIMATE)
