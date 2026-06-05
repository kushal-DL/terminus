"""Dimension 7: Opportunity Cost Awareness.

Measures whether the LLM chooses the BEST action from available options,
not just a valid one.
"""

from __future__ import annotations

import math

from terminus.benchmark.dimensions.base import DimensionComputer, DimensionScore
from terminus.benchmark.metrics.base import MetricResult
from terminus.benchmark.metrics.utils import action_distribution
from terminus.benchmark.schemas import GameRecording


class OpportunityComputer(DimensionComputer):
    """Computes Dimension 7: Opportunity Cost Awareness."""

    dimension_id = "dim_7_opportunity"
    dimension_name = "Opportunity Cost Awareness"
    required_metrics = [
        "1.1_build_order_efficiency",
        "1.3_market_timing",
        "1.6_resource_stockpile_timing",
        "3.3_repair_prioritization",
    ]

    def compute(
        self,
        metrics: dict[str, MetricResult],
        recordings: list[GameRecording],
    ) -> DimensionScore:
        build_order = self._get_metric_value(metrics, "1.1_build_order_efficiency")
        market_timing = self._get_metric_value(metrics, "1.3_market_timing")
        stockpile = self._get_metric_value(metrics, "1.6_resource_stockpile_timing")
        repair_priority = self._get_metric_value(metrics, "3.3_repair_prioritization")

        # Unnecessary PASS rate
        pass_rate = self._compute_unnecessary_pass_rate(recordings)
        pass_score = 1.0 - pass_rate

        # Action diversity
        diversity = self._compute_action_diversity(recordings)

        score = (
            build_order * 0.25
            + market_timing * 0.20
            + stockpile * 0.15
            + repair_priority * 0.15
            + pass_score * 0.15
            + diversity * 0.10
        )
        score = max(0.0, min(1.0, score))

        return DimensionScore(
            dimension_id=self.dimension_id,
            dimension_name=self.dimension_name,
            score=score,
            sub_scores={
                "build_order_cost": build_order,
                "market_timing_cost": market_timing,
                "idle_cost": pass_score,
                "repair_order_cost": repair_priority,
                "stockpile_timing": stockpile,
                "action_diversity": diversity,
            },
            details={"unnecessary_pass_rate": pass_rate},
            confidence=self._compute_confidence(metrics),
            contributing_metrics=list(self.required_metrics),
        )

    def _compute_unnecessary_pass_rate(self, recordings: list[GameRecording]) -> float:
        """Compute rate of PASS actions when other actions were available."""
        unnecessary_passes = 0
        total_turns = 0

        for rec in recordings:
            for snap in rec.turns:
                total_turns += 1
                if snap.parsed_response and snap.parsed_response.action.value == "PASS":
                    # PASS is unnecessary if there were other available actions
                    if len(snap.state.available_actions) > 1:
                        unnecessary_passes += 1

        if total_turns == 0:
            return 0.0
        return unnecessary_passes / total_turns

    def _compute_action_diversity(self, recordings: list[GameRecording]) -> float:
        """Compute Shannon entropy of action distribution, normalized."""
        all_turns = []
        for rec in recordings:
            all_turns.extend(rec.turns)

        if not all_turns:
            return 0.5

        dist = action_distribution(all_turns)
        if len(dist) <= 1:
            return 0.0

        # Shannon entropy
        entropy = 0.0
        for p in dist.values():
            if p > 0:
                entropy -= p * math.log2(p)

        # Normalize by max possible entropy
        max_entropy = math.log2(len(dist))
        if max_entropy == 0:
            return 0.5
        return min(1.0, entropy / max_entropy)
