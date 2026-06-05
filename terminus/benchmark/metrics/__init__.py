"""Metrics Engine — facade for computing all Tier-1 metrics."""

from __future__ import annotations

from terminus.benchmark.metrics.base import CrossGameCollector, MetricCollector, MetricResult
from terminus.benchmark.metrics.context_pressure import ContextPressureCollector
from terminus.benchmark.metrics.flexibility import FlexibilityCollector
from terminus.benchmark.metrics.numerical import NumericalCollector
from terminus.benchmark.metrics.opponent_aware import OpponentAwareCollector
from terminus.benchmark.metrics.planning import PlanningCollector
from terminus.benchmark.metrics.state_probes import StateProbeCollector
from terminus.benchmark.schemas import BenchmarkConfig, GameRecording


class MetricsEngine:
    """Computes all Tier-1 metrics from game recordings."""

    def __init__(self, config: BenchmarkConfig | None = None):
        self._config = config
        probe_turns = config.probe_turns if config else [10, 25, 50, 75, 100]

        self._collectors: list[MetricCollector] = [
            PlanningCollector(),
            NumericalCollector(),
            FlexibilityCollector(),
            StateProbeCollector(probe_turns=probe_turns),
            ContextPressureCollector(),
        ]
        self._cross_game_collectors: list[CrossGameCollector] = [
            OpponentAwareCollector(),
        ]

    def compute_game_metrics(self, recording: GameRecording) -> dict[str, MetricResult]:
        """Compute all single-game metrics for one recording."""
        results: dict[str, MetricResult] = {}
        for collector in self._collectors:
            for result in collector.compute(recording):
                results[result.metric_id] = result
        return results

    def compute_cross_game_metrics(self, recordings: list[GameRecording]) -> dict[str, MetricResult]:
        """Compute metrics requiring multiple recordings (opponent-aware)."""
        results: dict[str, MetricResult] = {}
        for collector in self._cross_game_collectors:
            for result in collector.compute(recordings):
                results[result.metric_id] = result
        return results

    def compute_all(self, recordings: list[GameRecording]) -> dict[str, MetricResult]:
        """Compute all metrics: per-game (averaged) + cross-game.

        Returns dict mapping metric_id → MetricResult with averaged values.
        """
        # Per-game metrics: compute per game, then average
        per_game_values: dict[str, list[float]] = {}
        per_game_samples: dict[str, list[int]] = {}

        for rec in recordings:
            game_metrics = self.compute_game_metrics(rec)
            for mid, result in game_metrics.items():
                per_game_values.setdefault(mid, []).append(result.value)
                per_game_samples.setdefault(mid, []).append(result.sample_count)

        # Average per-game metrics
        all_results: dict[str, MetricResult] = {}
        for mid, values in per_game_values.items():
            avg_value = sum(values) / len(values)
            total_samples = sum(per_game_samples.get(mid, [0]))
            all_results[mid] = MetricResult(
                metric_id=mid,
                value=avg_value,
                raw_value=avg_value,
                sample_count=total_samples,
                details={"per_game_values": values, "game_count": len(values)},
            )

        # Cross-game metrics (computed once across all recordings)
        cross_results = self.compute_cross_game_metrics(recordings)
        all_results.update(cross_results)

        return all_results

    def get_metric_ids(self) -> list[str]:
        """Return all metric IDs this engine can compute."""
        return [
            # Planning (1.x)
            "1.1_build_order_efficiency",
            "1.2_worker_allocation_anticipation",
            "1.3_market_timing",
            "1.4_catastrophe_preparation",
            "1.5_housing_before_growth",
            "1.6_resource_stockpile_timing",
            # Numerical (2.x)
            "2.1_invalid_action_rate",
            "2.2_worker_sum_accuracy",
            "2.3_over_capacity_errors",
            "2.4_production_rate_awareness",
            "2.5_trade_math_accuracy",
            "2.6_multi_resource_feasibility",
            # Flexibility (3.x)
            "3.1_post_catastrophe_recovery",
            "3.2_worker_reallocation_after_damage",
            "3.3_repair_prioritization",
            "3.4_market_adaptation",
            "3.5_starvation_response_speed",
            "3.6_defense_investment_after_hit",
            "3.7_action_distribution_shift",
            # State Probes (4.x)
            "4.1_building_recall",
            "4.2_resource_awareness",
            "4.3_strategy_consistency",
            "4.4_history_recall",
            # Opponent-Aware (5.x)
            "5.1_win_rate_vs_archetypes",
            "5.2_exploitation_resistance",
            "5.3_counter_strategy_speed",
            "5.4_cooperative_surplus",
            "5.5_market_manipulation_detection",
            # Context Pressure (6.x)
            "6.1_per_quartile_quality",
            "6.2_historical_reference_rate",
            "6.3_context_collapse_point",
        ]
