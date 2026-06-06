"""Composite scorer — weighted aggregation with 9 presets + participation floor."""

from __future__ import annotations

from terminus.benchmark.dimensions.base import DimensionScore
from terminus.benchmark.schemas import DimensionWeights, GameRecording


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

# Participation weight: counts alongside the 8 dimensions (weight 1.5 = 1.5× a normal dim)
PARTICIPATION_WEIGHT = 1.5

PRESETS: dict[str, list[float]] = {
    "balanced":    [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    "reliability": [1.5, 2.0, 1.0, 1.5, 0.5, 2.0, 0.5, 0.5],
    "strategy":    [0.5, 0.5, 1.5, 1.0, 1.5, 0.5, 2.0, 2.0],
    "triage":      [0.5, 1.0, 2.5, 2.0, 1.0, 0.5, 1.0, 0.5],
    "endurance":   [2.0, 1.0, 0.5, 1.0, 0.5, 2.5, 0.5, 0.5],
    "precision":   [0.5, 2.5, 0.5, 0.5, 0.5, 0.5, 2.0, 0.5],
    "adversarial": [0.5, 0.5, 1.0, 0.5, 1.0, 0.5, 0.5, 3.0],
    "coordination":[1.0, 0.5, 1.5, 0.5, 1.5, 1.0, 0.5, 2.0],
    "context":     [2.0, 0.5, 0.5, 0.5, 0.5, 3.0, 0.5, 0.5],
}


def compute_participation_score(
    recordings: list[GameRecording],
    reference_score: float | None = None,
) -> float:
    """Option B: Game Score Participation score in [0, 1].

    Measures whether the model actually engaged with the game — a model that
    only PASSes will score near the random-agent floor regardless of how
    'coherent' it was.

    Formula:
        participation = model_avg_score / reference_score

    reference_score is the best known score in the run. If not provided,
    we use a fixed calibration point derived from the random agent baseline
    (~700-900 in a 20-turn game with speed=1).

    Clamped to [0, 1].

    Rationale: A model that scores at the random baseline gets ~0.15.
    A model that actively builds and grows should score 3,000-8,000+,
    yielding 0.6-1.0. A passive all-PASS model stays near baseline → low score.
    """
    if not recordings:
        return 0.5

    avg_score = sum(r.final_score for r in recordings) / len(recordings)

    if reference_score and reference_score > 0:
        # Relative to best performer in this run
        raw = avg_score / reference_score
    else:
        # Absolute calibration: 8000 = excellent, 800 = passive/random
        # Score 800 → 0.10, 3000 → 0.38, 6000 → 0.75, 8000 → 1.0
        calibration = 8000.0
        raw = avg_score / calibration

    return max(0.0, min(1.0, raw))


def compute_composite(
    dimensions: dict[str, DimensionScore],
    preset: str = "balanced",
    custom_weights: DimensionWeights | None = None,
    recordings: list[GameRecording] | None = None,
    reference_score: float | None = None,
) -> float:
    """Compute weighted composite score from dimension scores.

    Includes Option B (game score participation) as an additional weighted
    term alongside the 8 cognitive dimensions. This prevents passive models
    from scoring highly on cognitive metrics alone.

    Args:
        dimensions: Mapping of dimension_id -> DimensionScore
        preset: Name of weight preset to use
        custom_weights: Custom weights (used when preset="custom")
        recordings: Raw game recordings (used to compute participation score)
        reference_score: Best score in the run for relative participation calc

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

    # Option B: participation term
    if recordings is not None:
        participation = compute_participation_score(recordings, reference_score)
        total += participation * PARTICIPATION_WEIGHT
        weight_sum += PARTICIPATION_WEIGHT

    if weight_sum == 0:
        return 0.0
    return total / weight_sum
