"""Dimension 2: Applied Arithmetic Under Cognitive Load.

Measures the proportion of numerically valid actions, weighted by cognitive load.
"""

from __future__ import annotations

from terminus.benchmark.dimensions.base import DimensionComputer, DimensionScore
from terminus.benchmark.metrics.base import MetricResult
from terminus.benchmark.schemas import GameRecording


class ArithmeticComputer(DimensionComputer):
    """Computes Dimension 2: Applied Arithmetic Under Cognitive Load."""

    dimension_id = "dim_2_arithmetic"
    dimension_name = "Applied Arithmetic Under Load"
    required_metrics = [
        "2.1_invalid_action_rate",
        "2.2_worker_sum_accuracy",
        "2.3_over_capacity_errors",
        "2.4_production_rate_awareness",
        "2.5_trade_math_accuracy",
        "2.6_multi_resource_feasibility",
    ]

    # Weights per metric (higher = more important)
    _WEIGHTS: dict[str, float] = {
        "2.1_invalid_action_rate": 2.0,
        "2.2_worker_sum_accuracy": 1.5,
        "2.3_over_capacity_errors": 1.0,
        "2.4_production_rate_awareness": 1.0,
        "2.5_trade_math_accuracy": 1.0,
        "2.6_multi_resource_feasibility": 1.5,
    }

    def compute(
        self,
        metrics: dict[str, MetricResult],
        recordings: list[GameRecording],
    ) -> DimensionScore:
        # Weighted mean of numerical metrics
        weighted_sum = 0.0
        total_weight = 0.0
        for mid, w in self._WEIGHTS.items():
            weighted_sum += self._get_metric_value(metrics, mid) * w
            total_weight += w

        base_accuracy = weighted_sum / total_weight if total_weight > 0 else 0.5

        # Load degradation: compare early vs late validity rates
        early_accuracy = self._quartile_valid_rate(recordings, 1)
        late_accuracy = self._quartile_valid_rate(recordings, 4)
        load_degradation = max(0.0, early_accuracy - late_accuracy)

        # Penalty for degradation under load (up to 30% reduction)
        score = base_accuracy * (1.0 - load_degradation * 0.3)
        score = max(0.0, min(1.0, score))

        return DimensionScore(
            dimension_id=self.dimension_id,
            dimension_name=self.dimension_name,
            score=score,
            sub_scores={
                "base_accuracy": base_accuracy,
                "early_load_accuracy": early_accuracy,
                "late_load_accuracy": late_accuracy,
                "load_degradation": load_degradation,
            },
            details={
                "per_metric": {
                    mid: self._get_metric_value(metrics, mid)
                    for mid in self.required_metrics
                },
            },
            confidence=self._compute_confidence(metrics),
            contributing_metrics=list(self.required_metrics),
        )

    def _quartile_valid_rate(self, recordings: list[GameRecording], quartile: int) -> float:
        """Compute valid action rate for a specific quartile of turns."""
        valid = 0
        total = 0
        for rec in recordings:
            n = len(rec.turns)
            if n == 0:
                continue
            q_size = n // 4 or 1
            start = (quartile - 1) * q_size
            end = n if quartile == 4 else quartile * q_size
            for snap in rec.turns[start:end]:
                total += 1
                if snap.valid:
                    valid += 1
        if total == 0:
            return 0.5
        return valid / total
