"""Composite scorer — weighted aggregation with 9 presets."""

from __future__ import annotations

from terminus.benchmark.dimensions.base import DimensionScore
from terminus.benchmark.schemas import DimensionWeights


DIMENSION_ORDER = [
    "dim_1_coherence",
    "dim_2_arithmetic",
    "dim_3_triage",
    "dim_4_error_recognition",
    "dim_5_pivot",
    "dim_6_degradation",
    "dim_7_opportunity",
    "dim_8_game_theory",
]

PRESETS: dict[str, list[float]] = {
    "balanced": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    "reliability": [1.5, 2.0, 1.0, 1.5, 0.5, 2.0, 0.5, 0.5],
    "strategy": [0.5, 0.5, 1.5, 1.0, 1.5, 0.5, 2.0, 2.0],
    "triage": [0.5, 1.0, 2.5, 2.0, 1.0, 0.5, 1.0, 0.5],
    "endurance": [2.0, 1.0, 0.5, 1.0, 0.5, 2.5, 0.5, 0.5],
    "precision": [0.5, 2.5, 0.5, 0.5, 0.5, 0.5, 2.0, 0.5],
    "adversarial": [0.5, 0.5, 1.0, 0.5, 1.0, 0.5, 0.5, 3.0],
    "coordination": [1.0, 0.5, 1.5, 0.5, 1.5, 1.0, 0.5, 2.0],
    "context": [2.0, 0.5, 0.5, 0.5, 0.5, 3.0, 0.5, 0.5],
}


def compute_composite(
    dimensions: dict[str, DimensionScore],
    preset: str = "balanced",
    custom_weights: DimensionWeights | None = None,
) -> float:
    """Compute weighted composite score from dimension scores.

    Args:
        dimensions: Mapping of dimension_id -> DimensionScore
        preset: Name of weight preset to use
        custom_weights: Custom weights (used when preset="custom")

    Returns:
        Composite score in [0.0, 1.0]
    """
    weights = PRESETS.get(preset, PRESETS["balanced"])

    if preset == "custom" and custom_weights:
        weights = [
            custom_weights.coherence,
            custom_weights.arithmetic,
            custom_weights.triage,
            custom_weights.error_recognition,
            custom_weights.pivot,
            custom_weights.degradation,
            custom_weights.opportunity_cost,
            custom_weights.game_theory,
        ]

    total = 0.0
    weight_sum = 0.0
    for i, dim_id in enumerate(DIMENSION_ORDER):
        if dim_id in dimensions:
            w = weights[i] if i < len(weights) else 1.0
            total += dimensions[dim_id].score * w
            weight_sum += w

    if weight_sum == 0:
        return 0.0
    return total / weight_sum
