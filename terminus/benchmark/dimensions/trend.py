"""Trend analysis — classify score trends across games."""

from __future__ import annotations

import statistics

from terminus.benchmark.dimensions.base import TrendClassification
from terminus.benchmark.metrics.utils import linear_regression_slope


def classify_trend(per_game_scores: list[float]) -> TrendClassification:
    """Classify score trend from per-game dimension scores."""
    if len(per_game_scores) < 3:
        return TrendClassification.CONSISTENT

    slope = linear_regression_slope(
        list(range(len(per_game_scores))), per_game_scores
    )
    variance = statistics.variance(per_game_scores)

    if variance > 0.04:  # std > 0.2
        return TrendClassification.VOLATILE
    if slope > 0.01:
        return TrendClassification.IMPROVING
    if slope < -0.01:
        return TrendClassification.DEGRADING
    return TrendClassification.CONSISTENT


def classify_overall_trend(
    per_game_dimensions: list[dict[str, float]],
) -> TrendClassification:
    """Compute overall trend from per-game dimension breakdowns.

    Uses majority vote across dimensions.
    """
    if not per_game_dimensions:
        return TrendClassification.CONSISTENT

    # Collect all dimension IDs
    all_dim_ids: set[str] = set()
    for game_dims in per_game_dimensions:
        all_dim_ids.update(game_dims.keys())

    if not all_dim_ids:
        return TrendClassification.CONSISTENT

    # Classify trend for each dimension
    trend_counts: dict[TrendClassification, int] = {
        TrendClassification.IMPROVING: 0,
        TrendClassification.CONSISTENT: 0,
        TrendClassification.DEGRADING: 0,
        TrendClassification.VOLATILE: 0,
    }

    for dim_id in all_dim_ids:
        values = [g.get(dim_id, 0.5) for g in per_game_dimensions]
        trend = classify_trend(values)
        trend_counts[trend] += 1

    # Majority vote
    return max(trend_counts, key=lambda t: trend_counts[t])


def compute_per_dimension_trends(
    per_game_dimensions: list[dict[str, float]],
) -> dict[str, TrendClassification]:
    """Compute trend classification per dimension."""
    if not per_game_dimensions:
        return {}

    all_dim_ids: set[str] = set()
    for game_dims in per_game_dimensions:
        all_dim_ids.update(game_dims.keys())

    trends: dict[str, TrendClassification] = {}
    for dim_id in all_dim_ids:
        values = [g.get(dim_id, 0.5) for g in per_game_dimensions]
        trends[dim_id] = classify_trend(values)

    return trends
