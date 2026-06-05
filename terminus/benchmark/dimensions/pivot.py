"""Dimension 5: Justified Pivot vs Inconsistency.

Measures whether strategy changes are triggered by environmental events
(justified) or are random/incoherent (unjustified).
"""

from __future__ import annotations

from dataclasses import dataclass

from terminus.benchmark.dimensions.base import DimensionComputer, DimensionScore
from terminus.benchmark.metrics.base import MetricResult
from terminus.benchmark.metrics.utils import action_distribution, jensen_shannon_divergence
from terminus.benchmark.schemas import GameRecording, TurnSnapshot


@dataclass
class StrategyChange:
    """A detected strategy change event."""

    turn: int
    has_trigger: bool
    trigger_type: str | None = None


class PivotComputer(DimensionComputer):
    """Computes Dimension 5: Justified Pivot vs Inconsistency."""

    dimension_id = "dim_5_pivot"
    dimension_name = "Justified Pivot vs Inconsistency"
    required_metrics = [
        "3.7_action_distribution_shift",
        "3.2_worker_reallocation_after_damage",
    ]

    def compute(
        self,
        metrics: dict[str, MetricResult],
        recordings: list[GameRecording],
    ) -> DimensionScore:
        # 1. Detect strategy changes and classify
        strategy_changes = self._detect_strategy_changes(recordings)
        justified = [c for c in strategy_changes if c.has_trigger]
        unjustified = [c for c in strategy_changes if not c.has_trigger]

        # 2. Detect missed pivots
        missed_pivots = self._detect_missed_pivots(recordings)

        # Signal-to-noise ratio
        total_changes = len(justified) + len(unjustified)
        snr = len(justified) / total_changes if total_changes > 0 else 0.5

        # Missed pivot penalty (capped at 1.0)
        missed_penalty = min(1.0, 0.1 * len(missed_pivots))

        # Component metrics
        action_shift = self._get_metric_value(metrics, "3.7_action_distribution_shift")
        worker_realloc = self._get_metric_value(metrics, "3.2_worker_reallocation_after_damage")

        score = (
            snr * 0.50
            + (1.0 - missed_penalty) * 0.20
            + action_shift * 0.15
            + worker_realloc * 0.15
        )
        score = max(0.0, min(1.0, score))

        return DimensionScore(
            dimension_id=self.dimension_id,
            dimension_name=self.dimension_name,
            score=score,
            sub_scores={
                "signal_to_noise": snr,
                "missed_pivot_penalty": missed_penalty,
                "action_shift": action_shift,
                "worker_reallocation": worker_realloc,
            },
            details={
                "total_changes": total_changes,
                "justified_changes": len(justified),
                "unjustified_changes": len(unjustified),
                "missed_pivots": len(missed_pivots),
            },
            confidence=self._compute_confidence(metrics),
            contributing_metrics=list(self.required_metrics),
        )

    def _detect_strategy_changes(self, recordings: list[GameRecording]) -> list[StrategyChange]:
        """Detect turns where strategy shifted significantly."""
        changes: list[StrategyChange] = []

        for rec in recordings:
            turns = rec.turns
            if len(turns) < 10:
                continue

            for i in range(10, len(turns)):
                # Check reasoning factor change
                factor_changed = self._top_factor_changed(turns, i)

                # Check action distribution shift over 5-turn windows
                dist_shifted = False
                if i >= 10:
                    window_a = turns[i - 10: i - 5]
                    window_b = turns[i - 5: i]
                    if window_a and window_b:
                        dist_a = action_distribution(window_a)
                        dist_b = action_distribution(window_b)
                        jsd = jensen_shannon_divergence(dist_a, dist_b)
                        dist_shifted = jsd > 0.4

                if factor_changed or dist_shifted:
                    has_trigger = self._has_environmental_trigger(turns, i)
                    trigger_type = self._identify_trigger(turns, i) if has_trigger else None
                    changes.append(StrategyChange(
                        turn=turns[i].turn,
                        has_trigger=has_trigger,
                        trigger_type=trigger_type,
                    ))

        return changes

    def _detect_missed_pivots(self, recordings: list[GameRecording]) -> list[int]:
        """Detect turns with triggers that should have caused a change but didn't."""
        missed: list[int] = []

        for rec in recordings:
            turns = rec.turns
            for i in range(5, len(turns)):
                if self._has_environmental_trigger(turns, i):
                    # Check if strategy changed in next 5 turns
                    changed = False
                    for j in range(i, min(i + 5, len(turns))):
                        if self._top_factor_changed(turns, j):
                            changed = True
                            break
                    if not changed:
                        # Also check if action distribution shifted
                        if i + 5 <= len(turns):
                            pre = action_distribution(turns[max(0, i - 5): i])
                            post = action_distribution(turns[i: i + 5])
                            if pre and post:
                                jsd = jensen_shannon_divergence(pre, post)
                                if jsd > 0.2:
                                    changed = True
                    if not changed:
                        missed.append(turns[i].turn)

        return missed

    def _top_factor_changed(self, turns: list[TurnSnapshot], index: int) -> bool:
        """Check if top reasoning factor changed at this index vs previous."""
        if index < 1:
            return False

        curr_top = self._get_top_factor(turns[index])
        prev_top = self._get_top_factor(turns[index - 1])

        if curr_top is None or prev_top is None:
            return False
        return curr_top != prev_top

    def _get_top_factor(self, snap: TurnSnapshot) -> str | None:
        """Get the highest-weighted reasoning factor for a turn."""
        if not snap.parsed_response or not snap.parsed_response.reasoning:
            return None
        factors = snap.parsed_response.reasoning.factors
        if not factors:
            return None
        return max(factors, key=lambda f: f.weight).factor.value

    def _has_environmental_trigger(self, turns: list[TurnSnapshot], index: int) -> bool:
        """Check if there's an environmental trigger within 5 prior turns."""
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

            # Market price shock (>30% change)
            if prev:
                for resource in ("food", "materials", "knowledge"):
                    curr_price = getattr(snap.state.market_prices, resource)
                    prev_price = getattr(prev.state.market_prices, resource)
                    if prev_price > 0 and abs(curr_price - prev_price) / prev_price > 0.3:
                        return True

            # Building health dropped below 50%
            if prev:
                for b in snap.state.buildings:
                    if b.health < b.max_health * 0.5:
                        # Check it wasn't already damaged
                        prev_building = next(
                            (pb for pb in prev.state.buildings if pb.type == b.type),
                            None,
                        )
                        if prev_building and prev_building.health >= prev_building.max_health * 0.5:
                            return True

            # Population drop > 3
            if prev and prev.state.population - snap.state.population > 3:
                return True

        return False

    def _identify_trigger(self, turns: list[TurnSnapshot], index: int) -> str | None:
        """Identify what type of trigger occurred."""
        start = max(0, index - 5)
        for i in range(start, index + 1):
            snap = turns[i]
            prev = turns[i - 1] if i > 0 else None

            if snap.state.last_catastrophe and (
                prev is None or prev.state.last_catastrophe is None
                or snap.state.last_catastrophe.name != prev.state.last_catastrophe.name
            ):
                return "catastrophe"
            if snap.state.resources.food <= 0 and (prev is None or prev.state.resources.food > 0):
                return "starvation"
            if snap.state.catastrophe_warning and (prev is None or prev.state.catastrophe_warning is None):
                return "catastrophe_warning"
            if prev and prev.state.population - snap.state.population > 3:
                return "population_drop"
        return "market_shock"
