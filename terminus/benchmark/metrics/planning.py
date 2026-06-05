"""Planning metrics (1.1–1.6) — evaluate forward-thinking and sequencing."""

from __future__ import annotations

from terminus.benchmark.metrics.base import MetricCollector, MetricResult
from terminus.benchmark.metrics.utils import clamp, rolling_average
from terminus.benchmark.schemas import BenchmarkActionType, GameRecording, TurnSnapshot


# Prerequisite graph: building → set of buildings that should be built first
_PREREQ_GRAPH: dict[str, set[str]] = {
    "housing": {"farm"},
    "warehouse": {"farm"},
    "library": {"housing"},
    "barracks": {"housing", "mine"},
    "wall": {"barracks"},
    "watchtower": {"wall"},
    "market": {"warehouse"},
    "hospital": {"library"},
}


class PlanningCollector(MetricCollector):
    """Computes metrics 1.1–1.6: planning and anticipation quality."""

    def compute(self, recording: GameRecording) -> list[MetricResult]:
        return [
            self._build_order_efficiency(recording),
            self._worker_allocation_anticipation(recording),
            self._market_timing(recording),
            self._catastrophe_preparation(recording),
            self._housing_before_growth(recording),
            self._resource_stockpile_timing(recording),
        ]

    # ─── 1.1 Build Order Efficiency ──────────────────────────────────────

    def _build_order_efficiency(self, recording: GameRecording) -> MetricResult:
        """Score prerequisite ordering in build sequence."""
        build_sequence: list[str] = []
        for snap in recording.turns:
            if not snap.parsed_response:
                continue
            if snap.parsed_response.action == BenchmarkActionType.BUILD and snap.valid:
                btype = snap.parsed_response.params.get("building_type", "")
                if btype:
                    build_sequence.append(btype)

        if len(build_sequence) < 2:
            return MetricResult(metric_id="1.1_build_order_efficiency", value=0.5, raw_value=0.0, sample_count=0)

        # Check prerequisite orderings
        correct_orderings = 0
        total_orderings = 0
        built_set: set[str] = set()

        for btype in build_sequence:
            prereqs = _PREREQ_GRAPH.get(btype, set())
            if prereqs:
                total_orderings += 1
                # Check if all prereqs were built before this
                if prereqs.issubset(built_set):
                    correct_orderings += 1
            built_set.add(btype)

        if total_orderings == 0:
            # No prerequisite relationships in the build order — neutral
            return MetricResult(metric_id="1.1_build_order_efficiency", value=0.7, raw_value=0.0, sample_count=len(build_sequence))

        score = correct_orderings / total_orderings
        return MetricResult(
            metric_id="1.1_build_order_efficiency",
            value=score,
            raw_value=score,
            sample_count=total_orderings,
            details={"correct": correct_orderings, "total": total_orderings, "build_sequence": build_sequence[:20]},
        )

    # ─── 1.2 Worker Allocation Anticipation ──────────────────────────────

    def _worker_allocation_anticipation(self, recording: GameRecording) -> MetricResult:
        """Check if workers are pre-allocated before builds/needs."""
        anticipated = 0
        total_needs = 0

        turns = recording.turns
        for i, snap in enumerate(turns):
            if not snap.parsed_response:
                continue
            if snap.parsed_response.action != BenchmarkActionType.BUILD or not snap.valid:
                continue

            # A BUILD happened — check if construction workers were elevated in prior 1-2 turns
            total_needs += 1
            for lookback in range(1, 3):
                prev_idx = i - lookback
                if prev_idx < 0:
                    break
                prev_snap = turns[prev_idx]
                # Check if construction workers increased relative to earlier
                if prev_idx > 0:
                    earlier = turns[prev_idx - 1]
                    if prev_snap.state.workers.construction > earlier.state.workers.construction:
                        anticipated += 1
                        break

        if total_needs == 0:
            return MetricResult(metric_id="1.2_worker_allocation_anticipation", value=0.5, raw_value=0.0, sample_count=0)

        score = anticipated / total_needs
        return MetricResult(
            metric_id="1.2_worker_allocation_anticipation",
            value=score,
            raw_value=score,
            sample_count=total_needs,
            details={"anticipated": anticipated, "total_needs": total_needs},
        )

    # ─── 1.3 Market Timing ───────────────────────────────────────────────

    def _market_timing(self, recording: GameRecording) -> MetricResult:
        """Score trade timing vs rolling average prices."""
        good_trades = 0
        total_trades = 0

        # Build price history per resource
        price_history: dict[str, list[float]] = {"food": [], "materials": [], "knowledge": []}
        trade_events: list[tuple[int, str, str, float]] = []  # (turn_idx, action, resource, price)

        for i, snap in enumerate(recording.turns):
            # Record prices each turn
            for res in ("food", "materials", "knowledge"):
                price = getattr(snap.state.market_prices, res, 1.0)
                price_history[res].append(price)

            if not snap.parsed_response:
                continue
            action = snap.parsed_response.action
            params = snap.parsed_response.params

            if action == BenchmarkActionType.TRADE_BUY:
                resource = params.get("resource", "")
                if resource in price_history:
                    trade_events.append((i, "BUY", resource, price_history[resource][-1]))
            elif action == BenchmarkActionType.TRADE_SELL:
                resource = params.get("resource", "")
                if resource in price_history:
                    trade_events.append((i, "SELL", resource, price_history[resource][-1]))

        # Evaluate each trade against 10-turn rolling average
        for turn_idx, trade_type, resource, price_at_trade in trade_events:
            total_trades += 1
            prices = price_history[resource][:turn_idx + 1]
            if len(prices) < 3:
                # Not enough history — give benefit of doubt
                good_trades += 1
                continue

            window = min(10, len(prices))
            avg = sum(prices[-window:]) / window

            if trade_type == "BUY" and price_at_trade <= avg:
                good_trades += 1
            elif trade_type == "SELL" and price_at_trade >= avg:
                good_trades += 1

        if total_trades == 0:
            return MetricResult(metric_id="1.3_market_timing", value=0.5, raw_value=0.0, sample_count=0)

        score = good_trades / total_trades
        return MetricResult(
            metric_id="1.3_market_timing",
            value=score,
            raw_value=score,
            sample_count=total_trades,
            details={"good_trades": good_trades, "total_trades": total_trades},
        )

    # ─── 1.4 Catastrophe Preparation ─────────────────────────────────────

    def _catastrophe_preparation(self, recording: GameRecording) -> MetricResult:
        """Check if mitigation was in place before catastrophe warnings."""
        prepared = 0
        total_catastrophes = 0

        # Find turns where catastrophe_warning first appears
        warning_turns: list[int] = []
        prev_warning = None
        for i, snap in enumerate(recording.turns):
            warning = snap.state.catastrophe_warning
            if warning and (prev_warning is None or warning.category != prev_warning.category):
                warning_turns.append(i)
            prev_warning = warning

        if not warning_turns:
            return MetricResult(metric_id="1.4_catastrophe_preparation", value=0.5, raw_value=0.0, sample_count=0)

        for warn_idx in warning_turns:
            total_catastrophes += 1
            snap = recording.turns[warn_idx]
            category = snap.state.catastrophe_warning.category if snap.state.catastrophe_warning else ""

            # Check if defense-related buildings exist BEFORE the warning
            had_mitigation = False
            if warn_idx > 0:
                pre_state = recording.turns[warn_idx - 1].state
                building_types = {b.type for b in pre_state.buildings}
                # Basic mitigation: wall, barracks, watchtower
                if "wall" in building_types or "barracks" in building_types:
                    had_mitigation = True
                # Resource stockpile check: food > 2× consumption
                if pre_state.resources.food > 2 * pre_state.food_consumption:
                    had_mitigation = True

            if had_mitigation:
                prepared += 1

        score = prepared / total_catastrophes
        return MetricResult(
            metric_id="1.4_catastrophe_preparation",
            value=score,
            raw_value=score,
            sample_count=total_catastrophes,
            details={"prepared": prepared, "total_catastrophes": total_catastrophes},
        )

    # ─── 1.5 Housing-Before-Growth ───────────────────────────────────────

    def _housing_before_growth(self, recording: GameRecording) -> MetricResult:
        """Score how well LLM avoids hitting population cap."""
        total_turns = len(recording.turns)
        if total_turns == 0:
            return MetricResult(metric_id="1.5_housing_before_growth", value=0.5, raw_value=0.0, sample_count=0)

        capped_turns = sum(
            1 for snap in recording.turns
            if snap.state.population >= snap.state.population_cap and snap.state.population_cap > 0
        )

        rate = capped_turns / total_turns
        score = clamp(1.0 - rate)

        return MetricResult(
            metric_id="1.5_housing_before_growth",
            value=score,
            raw_value=rate,
            sample_count=total_turns,
            details={"capped_turns": capped_turns, "total_turns": total_turns},
        )

    # ─── 1.6 Resource Stockpile Timing ───────────────────────────────────

    def _resource_stockpile_timing(self, recording: GameRecording) -> MetricResult:
        """Penalize PASSing when affordable actions exist."""
        unnecessary_passes = 0
        total_turns = len(recording.turns)

        if total_turns == 0:
            return MetricResult(metric_id="1.6_resource_stockpile_timing", value=0.5, raw_value=0.0, sample_count=0)

        for snap in recording.turns:
            if not snap.parsed_response:
                continue
            if snap.parsed_response.action != BenchmarkActionType.PASS:
                continue

            # Check if there were non-PASS available actions
            non_pass_actions = [
                a for a in snap.state.available_actions
                if a.action_type != "PASS"
            ]
            if non_pass_actions:
                unnecessary_passes += 1

        rate = unnecessary_passes / total_turns
        score = clamp(1.0 - rate * 2)  # Penalize more heavily (×2)

        return MetricResult(
            metric_id="1.6_resource_stockpile_timing",
            value=score,
            raw_value=rate,
            sample_count=total_turns,
            details={"unnecessary_passes": unnecessary_passes, "total_turns": total_turns},
        )
