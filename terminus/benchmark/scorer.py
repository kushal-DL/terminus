"""Dimension Scorer — computes cognitive dimension scores from game event history.

Maps game-level metrics (Tier 1) to cognitive dimensions (Tier 2) using the
8-dimension framework defined in metrics.md.
"""

from __future__ import annotations

from typing import Any

# The 8 cognitive dimensions
DIMENSIONS = [
    "Multi-Decision Coherence",
    "Applied Arithmetic Under Load",
    "Priority Triage",
    "Compounding Error Recognition",
    "Justified Pivot",
    "Graceful Degradation",
    "Opportunity Cost Awareness",
    "Game-Theoretic Sophistication",
]


def score_dimensions(
    game_results: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, dict[str, float]]:
    """Compute dimension scores for each model from aggregated game results.

    Args:
        game_results: List of per-game result dicts from the orchestrator.
        config: Benchmark configuration (includes dimension_weights, dimensions_enabled).

    Returns:
        Dict mapping model_name → {dimension_name: score (0.0-1.0)}
    """
    # Group results by model
    by_model: dict[str, list[dict[str, Any]]] = {}
    for result in game_results:
        name = result.get("model_name", "?")
        by_model.setdefault(name, []).append(result)

    weights = config.get("dimension_weights", [1.0] * 8)
    enabled = config.get("dimensions_enabled", [True] * 8)

    model_scores: dict[str, dict[str, float]] = {}

    for model_name, games in by_model.items():
        raw_scores = _compute_raw_dimensions(games)

        # Apply enabled/weight masking
        final: dict[str, float] = {}
        for i, dim_name in enumerate(DIMENSIONS):
            if i < len(enabled) and not enabled[i]:
                continue
            score = raw_scores[i]
            weight = weights[i] if i < len(weights) else 1.0
            final[dim_name] = min(1.0, max(0.0, score * weight / max(weight, 1.0)))

        model_scores[model_name] = final

    return model_scores


def compute_composite_score(
    dimension_scores: dict[str, float],
    weights: list[float] | None = None,
) -> float:
    """Compute a single composite score from dimension scores."""
    if not dimension_scores:
        return 0.0

    if weights is None:
        weights = [1.0] * 8

    total = 0.0
    weight_sum = 0.0
    for i, dim_name in enumerate(DIMENSIONS):
        if dim_name in dimension_scores:
            w = weights[i] if i < len(weights) else 1.0
            total += dimension_scores[dim_name] * w
            weight_sum += w

    return total / weight_sum if weight_sum > 0 else 0.0


def _compute_raw_dimensions(games: list[dict[str, Any]]) -> list[float]:
    """Compute raw 0-1 scores for each dimension from game data.

    Uses the available metrics. Where full replay data isn't available,
    approximates from summary statistics.
    """
    if not games:
        return [0.0] * 8

    # Aggregate metrics across all games
    total_valid = sum(g.get("valid_actions", 0) for g in games)
    total_invalid = sum(g.get("invalid_actions", 0) for g in games)
    total_actions = total_valid + total_invalid
    valid_rate = total_valid / total_actions if total_actions > 0 else 0.5

    scores_list = [g.get("score", 0) for g in games]
    avg_score = sum(scores_list) / len(scores_list) if scores_list else 0
    max_score = max(scores_list) if scores_list else 0
    min_score = min(scores_list) if scores_list else 0
    score_range = max_score - min_score if max_score > min_score else 1
    consistency = 1.0 - min(1.0, score_range / max(avg_score, 1))

    turns_list = [g.get("turns_played", 0) for g in games]
    avg_turns = sum(turns_list) / len(turns_list) if turns_list else 50
    max_possible_turns = max(turns_list) if turns_list else 100
    survival_rate = avg_turns / max_possible_turns if max_possible_turns > 0 else 0.5

    # Normalize score to 0-1 range (assume max possible ~200)
    score_norm = min(1.0, avg_score / 150) if avg_score > 0 else 0.0

    # ─── Dimension approximations ────────────────────────────────────────

    # D1: Multi-Decision Coherence
    # Approximated from consistency + valid_rate (coherent play = consistent scores + few errors)
    d1 = 0.4 * consistency + 0.4 * valid_rate + 0.2 * survival_rate

    # D2: Applied Arithmetic Under Load
    # Directly tied to valid action rate (arithmetic errors → invalid actions)
    d2 = valid_rate ** 1.5  # Penalize invalid actions more heavily

    # D3: Priority Triage
    # Approximated from score performance (good triage → higher scores)
    d3 = 0.6 * score_norm + 0.3 * survival_rate + 0.1 * valid_rate

    # D4: Compounding Error Recognition
    # Models that recover from bad starts show this. Approximate from score variance.
    # Low variance with high avg = good error recovery
    d4 = 0.5 * consistency + 0.3 * valid_rate + 0.2 * score_norm

    # D5: Justified Pivot
    # Hard to approximate without replay. Use score trajectory proxy.
    # Models that improve over time show pivot ability.
    if len(scores_list) >= 4:
        first_half = sum(scores_list[: len(scores_list) // 2]) / (len(scores_list) // 2)
        second_half = sum(scores_list[len(scores_list) // 2 :]) / (len(scores_list) - len(scores_list) // 2)
        improvement = (second_half - first_half) / max(abs(first_half), 1)
        d5 = min(1.0, max(0.0, 0.5 + improvement * 0.5))
    else:
        d5 = 0.5

    # D6: Graceful Degradation
    # Models that maintain scores even under catastrophes. Approximate from survival + min score.
    min_norm = min(1.0, min_score / max(avg_score, 1)) if avg_score > 0 else 0.5
    d6 = 0.4 * survival_rate + 0.3 * min_norm + 0.3 * consistency

    # D7: Opportunity Cost Awareness
    # Models that maximize score efficiently. High score with fewer actions = better.
    efficiency = score_norm / max(survival_rate, 0.3) if survival_rate > 0 else 0.5
    d7 = min(1.0, 0.5 * score_norm + 0.3 * min(1.0, efficiency) + 0.2 * valid_rate)

    # D8: Game-Theoretic Sophistication
    # Hard without opponent modeling data. Approximate from overall performance.
    d8 = 0.4 * score_norm + 0.3 * consistency + 0.2 * valid_rate + 0.1 * survival_rate

    return [d1, d2, d3, d4, d5, d6, d7, d8]
