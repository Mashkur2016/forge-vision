"""
Session scoring — a single, severity-weighted accuracy metric.

Previously each surface (leaderboard, reports, bias-audit) re-implemented a crude
proxy `100 - deviation_count * 10`, which (a) capped at 0 after 10 deviations,
(b) treated a safety-critical high-severity deviation the same as a minor one, and
(c) was duplicated in several places. This module centralises one defensible
metric used everywhere.

Design:
    weighted_deviations = low/medium_count * 1.0 + high_count * HIGH_WEIGHT
    accuracy            = clamp(100 - weighted_deviations * UNIT_PENALTY, 0..100)

Only the denormalised per-session fields are needed (`deviation_count` and
`high_severity_count` on TrainingSessionLog), so this stays a single cheap call
with no per-deviation query. High-severity deviations are penalised
`HIGH_WEIGHT`× more than ordinary ones; ~12.5 ordinary deviations drive accuracy
to 0 (vs. 10 before), softening the cliff while still being strict on safety.
"""
from __future__ import annotations

HIGH_WEIGHT: float = 2.0
UNIT_PENALTY: float = 8.0


def session_accuracy(
    deviation_count: int | None,
    high_severity_count: int | None = 0,
    *,
    high_weight: float = HIGH_WEIGHT,
    unit_penalty: float = UNIT_PENALTY,
) -> float:
    """Severity-weighted accuracy (0–100) for one session.

    0 deviations → 100. High-severity deviations cost ``high_weight``× an ordinary
    one. Result is clamped to [0, 100] and rounded to 1 dp.
    """
    total = max(0, int(deviation_count or 0))
    high = max(0, int(high_severity_count or 0))
    high = min(high, total)  # guard against inconsistent denormalised counts
    ordinary = total - high
    weighted = ordinary * 1.0 + high * high_weight
    score = 100.0 - weighted * unit_penalty
    return round(max(0.0, min(100.0, score)), 1)
