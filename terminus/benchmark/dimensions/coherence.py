"""Dimension 1: Multi-Decision Coherence Decay.

Measures whether the model's reasoning factors and actions remain logically
consistent over time, combining action-level coherence with state fidelity
from probe metrics.
"""

from __future__ import annotations

from terminus.benchmark.dimensions.base import DimensionComputer, DimensionScore
from terminus.benchmark.metrics.base import MetricResult
from terminus.benchmark.metrics.utils import rolling_average
from terminus.benchmark.schemas import GameRecording, TurnSnapshot


class CoherenceComputer(DimensionComputer):
    """Computes Dimension 1: Multi-Decision Coherence Decay."""

    dimension_id = "dim_1_coherence"
    dimension_name = "Multi-Decision Coherence"
    required_metrics = [
        "4.1_building_recall",
        "4.2_resource_awareness",
        "4.3_strategy_consistency",
        "4.4_history_recall",
    ]

    def compute(
        self,
        metrics: dict[str, MetricResult],
        recordings: list[GameRecording],
    ) -> DimensionScore:
        # 1. Action coherence (from reasoning factor tracking)
        action_coherence = self._compute_action_coherence(recordings)

        # 2. Inflection point (later = better)
        inflection_score = self._compute_inflection_score(recordings)

        # 3. State fidelity (weighted average of probe metrics)
        state_fidelity = (
            self._get_metric_value(metrics, "4.1_building_recall") * 0.30
            + self._get_metric_value(metrics, "4.2_resource_awareness") * 0.25
            + self._get_metric_value(metrics, "4.3_strategy_consistency") * 0.25
            + self._get_metric_value(metrics, "4.4_history_recall") * 0.20
        )

        # 4. Decay rate
        decay_rate = self._compute_decay_rate(recordings)

        # Integrated score: action-level + state-level
        score = (
            action_coherence * 0.35
            + inflection_score * 0.25
            + state_fidelity * 0.40
        )
        score = max(0.0, min(1.0, score))

        return DimensionScore(
            dimension_id=self.dimension_id,
            dimension_name=self.dimension_name,
            score=score,
            sub_scores={
                "action_coherence": action_coherence,
                "inflection_point": inflection_score,
                "state_fidelity": state_fidelity,
                "decay_rate": decay_rate,
            },
            details={},
            confidence=self._compute_confidence(metrics),
            contributing_metrics=list(self.required_metrics),
        )

    def _compute_action_coherence(self, recordings: list[GameRecording]) -> float:
        """Proportion of reasoning factor transitions that are justified."""
        triggered = 0
        untriggered = 0

        for rec in recordings:
            turns = rec.turns
            for i in range(1, len(turns)):
                curr_top = self._get_top_factor(turns[i])
                prev_top = self._get_top_factor(turns[i - 1])

                if curr_top is None or prev_top is None:
                    continue
                if curr_top == prev_top:
                    continue

                # Factor changed — check if trigger exists within 5 prior turns
                if self._has_trigger_near(turns, i):
                    triggered += 1
                else:
                    untriggered += 1

        total = triggered + untriggered
        if total == 0:
            return 1.0  # No changes = perfectly coherent
        return triggered / total

    def _compute_inflection_score(self, recordings: list[GameRecording]) -> float:
        """Find where coherence drops below 0.7 (later = better)."""
        if not recordings:
            return 1.0

        all_inflection_ratios: list[float] = []
        for rec in recordings:
            coherence_series = self._build_coherence_series(rec)
            if len(coherence_series) < 10:
                continue
            smoothed = rolling_average(coherence_series, 10)
            max_turns = len(smoothed)

            inflection = None
            for i in range(10, len(smoothed)):
                if smoothed[i] < 0.7:
                    inflection = i
                    break

            ratio = inflection / max_turns if inflection else 1.0
            all_inflection_ratios.append(ratio)

        if not all_inflection_ratios:
            return 1.0
        return sum(all_inflection_ratios) / len(all_inflection_ratios)

    def _compute_decay_rate(self, recordings: list[GameRecording]) -> float:
        """Compute slope of coherence after inflection (negative = worse)."""
        from terminus.benchmark.metrics.utils import linear_regression_slope

        slopes: list[float] = []
        for rec in recordings:
            series = self._build_coherence_series(rec)
            if len(series) < 20:
                continue
            # Use second half
            second_half = series[len(series) // 2:]
            x = list(range(len(second_half)))
            slope = linear_regression_slope(x, second_half)
            slopes.append(slope)

        if not slopes:
            return 0.0
        return sum(slopes) / len(slopes)

    def _build_coherence_series(self, recording: GameRecording) -> list[float]:
        """Build per-turn coherence score (1=coherent, 0=incoherent transition)."""
        turns = recording.turns
        series: list[float] = [1.0]  # First turn is always coherent

        for i in range(1, len(turns)):
            curr_top = self._get_top_factor(turns[i])
            prev_top = self._get_top_factor(turns[i - 1])

            if curr_top is None or prev_top is None:
                series.append(1.0)  # No reasoning data = assume coherent
                continue
            if curr_top == prev_top:
                series.append(1.0)
            elif self._has_trigger_near(turns, i):
                series.append(1.0)  # Justified change
            else:
                series.append(0.0)  # Unjustified change

        return series

    def _get_top_factor(self, snap: TurnSnapshot) -> str | None:
        """Get highest-weighted reasoning factor."""
        if not snap.parsed_response or not snap.parsed_response.reasoning:
            return None
        factors = snap.parsed_response.reasoning.factors
        if not factors:
            return None
        return max(factors, key=lambda f: f.weight).factor.value

    def _has_trigger_near(self, turns: list[TurnSnapshot], index: int) -> bool:
        """Check for environmental triggers within 5 prior turns."""
        start = max(0, index - 5)
        for i in range(start, index + 1):
            snap = turns[i]
            prev = turns[i - 1] if i > 0 else None

            # New catastrophe
            if snap.state.last_catastrophe:
                if prev is None or prev.state.last_catastrophe is None:
                    return True
                if snap.state.last_catastrophe.name != prev.state.last_catastrophe.name:
                    return True

            # Catastrophe warning appeared
            if snap.state.catastrophe_warning and (
                prev is None or prev.state.catastrophe_warning is None
            ):
                return True

            # Food hit 0
            if snap.state.resources.food <= 0 and (
                prev is None or prev.state.resources.food > 0
            ):
                return True

            # Market price shock > 30%
            if prev:
                for resource in ("food", "materials", "knowledge"):
                    curr_price = getattr(snap.state.market_prices, resource)
                    prev_price = getattr(prev.state.market_prices, resource)
                    if prev_price > 0 and abs(curr_price - prev_price) / prev_price > 0.3:
                        return True

            # Population drop > 3
            if prev and prev.state.population - snap.state.population > 3:
                return True

        return False
