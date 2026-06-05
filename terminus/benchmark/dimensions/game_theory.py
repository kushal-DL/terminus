"""Dimension 8: Game-Theoretic Sophistication.

Measures the model's ability to detect opponent strategy, resist exploitation,
and capture cooperative surplus.
"""

from __future__ import annotations

from terminus.benchmark.dimensions.base import DimensionComputer, DimensionScore
from terminus.benchmark.metrics.base import MetricResult
from terminus.benchmark.metrics.utils import action_distribution, jensen_shannon_divergence
from terminus.benchmark.schemas import GameRecording


class GameTheoryComputer(DimensionComputer):
    """Computes Dimension 8: Game-Theoretic Sophistication."""

    dimension_id = "dim_8_game_theory"
    dimension_name = "Game-Theoretic Sophistication"
    required_metrics = [
        "5.1_win_rate_vs_archetypes",
        "5.2_exploitation_resistance",
        "5.3_counter_strategy_speed",
        "5.4_cooperative_surplus",
        "5.5_market_manipulation_detection",
    ]

    def compute(
        self,
        metrics: dict[str, MetricResult],
        recordings: list[GameRecording],
    ) -> DimensionScore:
        opponent_modeling = self._get_metric_value(metrics, "5.3_counter_strategy_speed")
        exploitation_resistance = self._get_metric_value(metrics, "5.2_exploitation_resistance")
        cooperative_rationality = self._get_metric_value(metrics, "5.4_cooperative_surplus")
        market_awareness = self._get_metric_value(metrics, "5.5_market_manipulation_detection")
        win_rate = self._get_metric_value(metrics, "5.1_win_rate_vs_archetypes")

        diversity = self._compute_strategic_diversity(recordings)

        score = (
            opponent_modeling * 0.20
            + exploitation_resistance * 0.25
            + diversity * 0.10
            + cooperative_rationality * 0.15
            + market_awareness * 0.15
            + win_rate * 0.15
        )
        score = max(0.0, min(1.0, score))

        # Strategy profile classification
        profile = self._classify_profile(
            win_rate, exploitation_resistance, cooperative_rationality,
            diversity, opponent_modeling,
        )

        return DimensionScore(
            dimension_id=self.dimension_id,
            dimension_name=self.dimension_name,
            score=score,
            sub_scores={
                "opponent_modeling": opponent_modeling,
                "exploitation_resistance": exploitation_resistance,
                "strategic_diversity": diversity,
                "cooperative_rationality": cooperative_rationality,
                "market_awareness": market_awareness,
                "win_rate_weighted": win_rate,
            },
            details={"strategy_profile": profile},
            confidence=self._compute_confidence(metrics),
            contributing_metrics=list(self.required_metrics),
        )

    def _compute_strategic_diversity(self, recordings: list[GameRecording]) -> float:
        """Measure how much the LLM varies strategy across games."""
        if len(recordings) < 2:
            return 0.5

        # Extract first-15-turn action distributions per game
        openings = []
        for rec in recordings:
            first_turns = rec.turns[:15]
            if first_turns:
                openings.append(action_distribution(first_turns))

        if len(openings) < 2:
            return 0.5

        # Mean pairwise Jensen-Shannon divergence
        divergences: list[float] = []
        for i in range(len(openings)):
            for j in range(i + 1, len(openings)):
                divergences.append(jensen_shannon_divergence(openings[i], openings[j]))

        if not divergences:
            return 0.5
        return min(1.0, sum(divergences) / len(divergences))

    def _classify_profile(
        self,
        win_rate: float,
        resistance: float,
        cooperation: float,
        diversity: float,
        modeling: float,
    ) -> str:
        """Classify the model's game-theoretic profile."""
        if modeling < 0.3 and diversity < 0.2:
            return "oblivious"
        if win_rate > 0.7 and diversity > 0.5:
            return "predator"
        if resistance > 0.8 and cooperation < 0.4:
            return "fortress"
        if cooperation > 0.7 and resistance > 0.5:
            return "diplomat"
        if diversity > 0.6 and modeling > 0.7:
            return "chameleon"
        return "pragmatist"
