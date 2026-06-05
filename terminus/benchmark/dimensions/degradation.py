"""Dimension 6: Graceful Degradation + Context Window Correlation.

Measures the shape of the model's performance curve and whether degradation
is context-bound or reasoning-bound.
"""

from __future__ import annotations

import statistics

from terminus.benchmark.dimensions.base import DimensionComputer, DimensionScore, FailureMode
from terminus.benchmark.metrics.base import MetricResult
from terminus.benchmark.metrics.utils import linear_regression_slope, rolling_average
from terminus.benchmark.schemas import GameRecording


class DegradationComputer(DimensionComputer):
    """Computes Dimension 6: Graceful Degradation + Context Window."""

    dimension_id = "dim_6_degradation"
    dimension_name = "Graceful Degradation"
    required_metrics = [
        "6.1_per_quartile_quality",
        "6.2_historical_reference_rate",
        "6.3_context_collapse_point",
    ]

    def compute(
        self,
        metrics: dict[str, MetricResult],
        recordings: list[GameRecording],
    ) -> DimensionScore:
        # 1. Per-turn quality curve and classification
        per_turn_quality = self._compute_per_turn_quality(recordings)
        failure_mode = self._classify_failure_mode(per_turn_quality)

        # Base score from failure mode
        base_score = self._mode_base_score(failure_mode, per_turn_quality)

        # 2. Context metrics
        quartile_quality = self._get_metric_value(metrics, "6.1_per_quartile_quality")
        historical_ref = self._get_metric_value(metrics, "6.2_historical_reference_rate")
        collapse_point = self._get_metric_value(metrics, "6.3_context_collapse_point")

        # 3. Composite
        score = (
            base_score * 0.40
            + quartile_quality * 0.20
            + collapse_point * 0.20
            + historical_ref * 0.20
        )
        score = max(0.0, min(1.0, score))

        # Effective decision budget
        decision_budget = self._compute_decision_budget(per_turn_quality)

        # Cliff point
        cliff_point = self._detect_cliff(per_turn_quality)

        return DimensionScore(
            dimension_id=self.dimension_id,
            dimension_name=self.dimension_name,
            score=score,
            sub_scores={
                "base_curve_score": base_score,
                "quartile_quality": quartile_quality,
                "historical_reference": historical_ref,
                "collapse_point": collapse_point,
            },
            details={
                "failure_mode": failure_mode.value,
                "cliff_point": cliff_point,
                "effective_decision_budget": decision_budget,
                "curve_slope": linear_regression_slope(
                    list(range(len(per_turn_quality))), per_turn_quality
                ) if len(per_turn_quality) >= 2 else 0.0,
            },
            confidence=self._compute_confidence(metrics),
            contributing_metrics=list(self.required_metrics),
        )

    def _compute_per_turn_quality(self, recordings: list[GameRecording]) -> list[float]:
        """Compute per-turn quality score from all recordings (averaged)."""
        if not recordings:
            return []

        # Find max turns
        max_len = max(len(rec.turns) for rec in recordings) if recordings else 0
        if max_len == 0:
            return []

        # Accumulate validity per turn position
        sums = [0.0] * max_len
        counts = [0] * max_len

        for rec in recordings:
            for i, snap in enumerate(rec.turns):
                sums[i] += 1.0 if snap.valid else 0.0
                counts[i] += 1

        return [sums[i] / counts[i] if counts[i] > 0 else 0.5 for i in range(max_len)]

    def _classify_failure_mode(self, quality: list[float]) -> FailureMode:
        """Classify the shape of the quality curve."""
        if len(quality) < 10:
            return FailureMode.STABLE

        x = list(range(len(quality)))
        slope = linear_regression_slope(x, quality)

        # Check for cliff first (sharp single drop)
        cliff = self._detect_cliff(quality)
        if cliff is not None:
            return FailureMode.CLIFF_FAILURE

        # Check oscillation (high variance across windows, but no single cliff)
        std_windows = self._std_of_rolling_windows(quality, window=10)
        if std_windows > 0.15:
            return FailureMode.OSCILLATING

        # Improving
        if slope > 0.002:
            return FailureMode.IMPROVING

        # Stable (near-zero slope)
        if abs(slope) <= 0.002:
            return FailureMode.STABLE

        # Linear decay
        if slope < -0.003:
            return FailureMode.LINEAR_DECAY

        return FailureMode.STABLE

    def _mode_base_score(self, mode: FailureMode, quality: list[float]) -> float:
        """Convert failure mode to base score."""
        if mode == FailureMode.STABLE:
            return 1.0
        if mode == FailureMode.IMPROVING:
            return 1.0
        if mode == FailureMode.OSCILLATING:
            return 0.4
        if mode == FailureMode.CLIFF_FAILURE:
            return 0.2
        if mode == FailureMode.LINEAR_DECAY:
            # Adjust by slope severity
            if len(quality) >= 2:
                slope = linear_regression_slope(list(range(len(quality))), quality)
                return max(0.2, 0.7 - abs(slope) * 50)
            return 0.6
        return 0.5

    def _detect_cliff(self, quality: list[float], drop_threshold: float = 0.3) -> int | None:
        """Detect cliff failure point where quality drops sharply."""
        if len(quality) < 20:
            return None

        window = 10
        for i in range(window, len(quality) - window):
            pre_mean = sum(quality[i - window: i]) / window
            post_mean = sum(quality[i: i + window]) / window
            if pre_mean - post_mean > drop_threshold:
                return i
        return None

    def _compute_decision_budget(self, quality: list[float]) -> int:
        """Number of turns before quality drops below 0.7."""
        smoothed = rolling_average(quality, 5) if len(quality) >= 5 else quality
        for i, q in enumerate(smoothed):
            if q < 0.7:
                return i
        return len(quality)

    def _std_of_rolling_windows(self, values: list[float], window: int) -> float:
        """Compute std dev of window means."""
        if len(values) < window * 2:
            return 0.0

        window_means: list[float] = []
        for i in range(0, len(values) - window + 1, window):
            chunk = values[i: i + window]
            window_means.append(sum(chunk) / len(chunk))

        if len(window_means) < 2:
            return 0.0
        return statistics.stdev(window_means)
