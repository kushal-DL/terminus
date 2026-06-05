"""Dimension 3: Priority Triage Under Competing Constraints.

Measures the model's ability to identify and address the most critical
constraint when multiple constraints are violated simultaneously.
"""

from __future__ import annotations

from terminus.benchmark.dimensions.base import DimensionComputer, DimensionScore
from terminus.benchmark.metrics.base import MetricResult
from terminus.benchmark.schemas import GameRecording, TurnSnapshot


# Priority order (1 = highest)
PRIORITY_LABELS = [
    "starvation",
    "catastrophe_imminent",
    "building_damage",
    "population_cap",
    "gold_zero",
    "low_morale",
]


class TriageComputer(DimensionComputer):
    """Computes Dimension 3: Priority Triage Under Competing Constraints."""

    dimension_id = "dim_3_triage"
    dimension_name = "Priority Triage"
    required_metrics = [
        "3.5_starvation_response_speed",
        "1.4_catastrophe_preparation",
        "3.3_repair_prioritization",
        "1.5_housing_before_growth",
    ]

    def compute(
        self,
        metrics: dict[str, MetricResult],
        recordings: list[GameRecording],
    ) -> DimensionScore:
        # 1. Multi-constraint triage accuracy from recording analysis
        triage_accuracy = self._compute_triage_accuracy(recordings)

        # 2. Component metrics
        starvation_speed = self._get_metric_value(metrics, "3.5_starvation_response_speed")
        catastrophe_prep = self._get_metric_value(metrics, "1.4_catastrophe_preparation")
        repair_priority = self._get_metric_value(metrics, "3.3_repair_prioritization")
        housing_timing = self._get_metric_value(metrics, "1.5_housing_before_growth")

        score = (
            triage_accuracy * 0.40
            + starvation_speed * 0.20
            + catastrophe_prep * 0.20
            + repair_priority * 0.10
            + housing_timing * 0.10
        )
        score = max(0.0, min(1.0, score))

        return DimensionScore(
            dimension_id=self.dimension_id,
            dimension_name=self.dimension_name,
            score=score,
            sub_scores={
                "triage_accuracy": triage_accuracy,
                "starvation_speed": starvation_speed,
                "catastrophe_prep": catastrophe_prep,
                "repair_priority": repair_priority,
                "housing_timing": housing_timing,
            },
            details={},
            confidence=self._compute_confidence(metrics),
            contributing_metrics=list(self.required_metrics),
        )

    def _compute_triage_accuracy(self, recordings: list[GameRecording]) -> float:
        """Compute proportion of correct first-priority actions at multi-constraint turns."""
        correct = 0
        total = 0

        for rec in recordings:
            for snap in rec.turns:
                active = self._get_active_constraints(snap)
                if len(active) < 2:
                    continue

                total += 1
                highest_priority = active[0]
                action = snap.parsed_response.action.value if snap.parsed_response else "PASS"

                if self._action_addresses_constraint(action, snap, highest_priority):
                    correct += 1

        if total == 0:
            return 0.5
        return correct / total

    def _get_active_constraints(self, snap: TurnSnapshot) -> list[str]:
        """Get list of active constraints at this turn, sorted by priority."""
        active: list[str] = []
        state = snap.state

        if state.resources.food <= 0:
            active.append("starvation")
        if state.catastrophe_warning and state.catastrophe_warning.ticks_until <= 10:
            active.append("catastrophe_imminent")
        if any(b.health < b.max_health * 0.5 for b in state.buildings):
            active.append("building_damage")
        if state.population >= state.population_cap and state.population_cap > 0:
            active.append("population_cap")
        if state.resources.gold <= 0:
            active.append("gold_zero")
        if state.morale < 0.7:
            active.append("low_morale")

        # Sort by canonical priority order
        return sorted(active, key=lambda c: PRIORITY_LABELS.index(c) if c in PRIORITY_LABELS else 99)

    def _action_addresses_constraint(self, action: str, snap: TurnSnapshot, constraint: str) -> bool:
        """Check if the action addresses the given constraint."""
        params = snap.parsed_response.params if snap.parsed_response else {}

        if constraint == "starvation":
            # Buying food, allocating more farming workers, or trading for food
            if action == "TRADE_BUY" and params.get("resource") == "food":
                return True
            if action == "ALLOCATE_WORKERS":
                return True  # any realloc might address starvation
            return False

        if constraint == "catastrophe_imminent":
            # Building defenses, allocating defense/medicine workers
            if action == "BUILD" and params.get("building_type") in ("wall", "barracks", "watchtower", "hospital"):
                return True
            if action == "ALLOCATE_WORKERS":
                return True
            return False

        if constraint == "building_damage":
            if action == "REPAIR":
                return True
            return False

        if constraint == "population_cap":
            if action == "BUILD" and params.get("building_type") == "housing":
                return True
            if action == "UPGRADE" and params.get("building_type") == "housing":
                return True
            return False

        if constraint == "gold_zero":
            if action == "TRADE_SELL":
                return True
            return False

        if constraint == "low_morale":
            # Medicine workers or specific buildings
            if action == "ALLOCATE_WORKERS":
                return True
            return False

        return False
