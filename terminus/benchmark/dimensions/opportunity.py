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

        # Unnecessary PASS rate — penalised more severely for systematic passivity
        pass_rate = self._compute_unnecessary_pass_rate(recordings)
        pass_score = self._pass_penalty(pass_rate)

        # Action monotony penalty — severely penalise single-action fixation
        diversity, dominant_rate, dominant_action = self._compute_action_diversity_detail(recordings)
        monotony_penalty = self._monotony_penalty(dominant_rate, dominant_action)

        # Effective diversity score after penalty
        diversity_score = diversity * (1.0 - monotony_penalty)

        score = (
            build_order * 0.25
            + market_timing * 0.20
            + stockpile * 0.15
            + repair_priority * 0.15
            + pass_score * 0.15
            + diversity_score * 0.10
        )
        score = max(0.0, min(1.0, score))

        return DimensionScore(
            dimension_id=self.dimension_id,
            dimension_name=self.dimension_name,
            score=score,
            sub_scores={
                "build_order_cost":  build_order,
                "market_timing_cost": market_timing,
                "idle_cost":         pass_score,
                "repair_order_cost": repair_priority,
                "stockpile_timing":  stockpile,
                "action_diversity":  diversity_score,
            },
            details={
                "unnecessary_pass_rate": pass_rate,
                "dominant_action":       dominant_action,
                "dominant_action_rate":  dominant_rate,
                "monotony_penalty":      monotony_penalty,
            },
            confidence=self._compute_confidence(metrics),
            contributing_metrics=list(self.required_metrics),
        )

    def _pass_penalty(self, pass_rate: float) -> float:
        """Non-linear penalty for high PASS rates.

        - Below 30% PASS: minimal penalty (strategic passing is fine)
        - 30–70%: linear penalty
        - Above 70%: steep penalty — model is effectively not playing
        - 100% PASS: score 0.0
        """
        if pass_rate <= 0.30:
            return 1.0 - (pass_rate / 0.30) * 0.15   # up to 15% penalty at 30%
        elif pass_rate <= 0.70:
            # Linear from 0.85 → 0.35 over 30–70%
            return 0.85 - ((pass_rate - 0.30) / 0.40) * 0.50
        else:
            # Steep: 0.35 → 0.0 over 70–100%
            return 0.35 * (1.0 - (pass_rate - 0.70) / 0.30)

    def _monotony_penalty(self, dominant_rate: float, dominant_action: str) -> float:
        """Penalty applied when one action dominates > 70% of all turns.

        Both all-PASS (passivity) and all-BUILD-fail (fixation) are caught.
        Returns a multiplier 0–1 that scales down diversity_score.
        """
        if dominant_rate <= 0.60:
            return 0.0                          # no penalty under 60%
        elif dominant_rate <= 0.80:
            # 60–80%: moderate — 0 → 0.5 penalty
            return ((dominant_rate - 0.60) / 0.20) * 0.50
        else:
            # 80–100%: severe — 0.5 → 1.0 (effectively zeros out diversity)
            return 0.50 + ((dominant_rate - 0.80) / 0.20) * 0.50

    def _compute_unnecessary_pass_rate(self, recordings: list[GameRecording]) -> float:
        """Compute rate of PASS actions when other actions were available."""
        unnecessary_passes = 0
        total_turns = 0

        for rec in recordings:
            for snap in rec.turns:
                total_turns += 1
                if snap.parsed_response and snap.parsed_response.action.value == "PASS":
                    if len(snap.state.available_actions) > 1:
                        unnecessary_passes += 1

        if total_turns == 0:
            return 0.0
        return unnecessary_passes / total_turns

    def _compute_action_diversity_detail(
        self,
        recordings: list[GameRecording],
    ) -> tuple[float, float, str]:
        """Compute (entropy_score, dominant_action_rate, dominant_action_name)."""
        all_turns = []
        for rec in recordings:
            all_turns.extend(rec.turns)

        if not all_turns:
            return 0.5, 0.0, ""

        dist = action_distribution(all_turns)
        if not dist:
            return 0.5, 0.0, ""

        # Find dominant action
        dominant_action = max(dist, key=dist.get)  # type: ignore[arg-type]
        dominant_rate = dist[dominant_action]

        if len(dist) <= 1:
            return 0.0, dominant_rate, dominant_action

        # Shannon entropy normalised
        entropy = 0.0
        for p in dist.values():
            if p > 0:
                entropy -= p * math.log2(p)
        max_entropy = math.log2(len(dist))
        diversity = min(1.0, entropy / max_entropy) if max_entropy > 0 else 0.5

        return diversity, dominant_rate, dominant_action

    def _compute_action_diversity(self, recordings: list[GameRecording]) -> float:
        """Legacy helper — returns entropy score only."""
        diversity, _, _ = self._compute_action_diversity_detail(recordings)
        return diversity
