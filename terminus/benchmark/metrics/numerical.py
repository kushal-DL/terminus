"""Numerical/Arithmetic metrics (2.1–2.6) — validate LLM math accuracy."""

from __future__ import annotations

from terminus.benchmark.metrics.base import MetricCollector, MetricResult
from terminus.benchmark.metrics.utils import clamp
from terminus.benchmark.schemas import BenchmarkActionType, GameRecording


class NumericalCollector(MetricCollector):
    """Computes metrics 2.1–2.6: arithmetic accuracy under game constraints."""

    def compute(self, recording: GameRecording) -> list[MetricResult]:
        return [
            self._invalid_action_rate(recording),
            self._worker_sum_accuracy(recording),
            self._over_capacity_errors(recording),
            self._production_rate_awareness(recording),
            self._trade_math_accuracy(recording),
            self._multi_resource_feasibility(recording),
        ]

    # ─── 2.1 Invalid Action Rate ─────────────────────────────────────────

    def _invalid_action_rate(self, recording: GameRecording) -> MetricResult:
        """Score = 1 - (invalid / total). Higher = fewer invalid actions."""
        total = len(recording.turns)
        if total == 0:
            return MetricResult(metric_id="2.1_invalid_action_rate", value=0.5, raw_value=0.0, sample_count=0)

        invalid = sum(1 for t in recording.turns if not t.valid)
        rate = invalid / total
        score = clamp(1.0 - rate)

        return MetricResult(
            metric_id="2.1_invalid_action_rate",
            value=score,
            raw_value=rate,
            sample_count=total,
            details={"invalid_count": invalid, "total_turns": total},
        )

    # ─── 2.2 Worker Sum Accuracy ─────────────────────────────────────────

    def _worker_sum_accuracy(self, recording: GameRecording) -> MetricResult:
        """Check if ALLOCATE_WORKERS params sum to population."""
        correct = 0
        total_allocations = 0

        for snap in recording.turns:
            if not snap.parsed_response:
                continue
            if snap.parsed_response.action != BenchmarkActionType.ALLOCATE_WORKERS:
                continue

            total_allocations += 1
            params = snap.parsed_response.params
            allocation = params.get("allocation", params)

            # Sum all worker values
            worker_sum = 0
            if isinstance(allocation, dict):
                for key in ("farming", "mining", "research", "construction", "defense", "medicine"):
                    worker_sum += int(allocation.get(key, 0))
            else:
                worker_sum = -1  # Can't parse

            population = snap.state.population
            if worker_sum == population:
                correct += 1

        if total_allocations == 0:
            return MetricResult(metric_id="2.2_worker_sum_accuracy", value=1.0, raw_value=1.0, sample_count=0)

        score = correct / total_allocations
        return MetricResult(
            metric_id="2.2_worker_sum_accuracy",
            value=score,
            raw_value=score,
            sample_count=total_allocations,
            details={"correct": correct, "total_allocations": total_allocations},
        )

    # ─── 2.3 Over-Capacity Errors ────────────────────────────────────────

    def _over_capacity_errors(self, recording: GameRecording) -> MetricResult:
        """Check if TRADE_BUY would exceed storage capacity."""
        overflow_attempts = 0
        total_buys = 0

        for snap in recording.turns:
            if not snap.parsed_response:
                continue
            if snap.parsed_response.action != BenchmarkActionType.TRADE_BUY:
                continue

            total_buys += 1
            params = snap.parsed_response.params
            resource = params.get("resource", "")
            quantity = int(params.get("quantity", 0))

            current = getattr(snap.state.resources, resource, 0)
            cap = getattr(snap.state.capacity, resource, 999)

            if current + quantity > cap:
                overflow_attempts += 1

        if total_buys == 0:
            return MetricResult(metric_id="2.3_over_capacity_errors", value=1.0, raw_value=0.0, sample_count=0)

        rate = overflow_attempts / total_buys
        score = clamp(1.0 - rate)
        return MetricResult(
            metric_id="2.3_over_capacity_errors",
            value=score,
            raw_value=rate,
            sample_count=total_buys,
            details={"overflow_attempts": overflow_attempts, "total_buys": total_buys},
        )

    # ─── 2.4 Production Rate Awareness ───────────────────────────────────

    def _production_rate_awareness(self, recording: GameRecording) -> MetricResult:
        """Check if BUILD attempts have sufficient resources (or reasonable wait)."""
        premature = 0
        total_builds = 0

        for snap in recording.turns:
            if not snap.parsed_response:
                continue
            if snap.parsed_response.action != BenchmarkActionType.BUILD:
                continue
            if not snap.valid:
                # Invalid build = likely didn't have resources
                total_builds += 1
                premature += 1
                continue

            total_builds += 1
            # Valid build means resources were sufficient — no issue

        if total_builds == 0:
            return MetricResult(metric_id="2.4_production_rate_awareness", value=1.0, raw_value=0.0, sample_count=0)

        rate = premature / total_builds
        score = clamp(1.0 - rate)
        return MetricResult(
            metric_id="2.4_production_rate_awareness",
            value=score,
            raw_value=rate,
            sample_count=total_builds,
            details={"premature_attempts": premature, "total_builds": total_builds},
        )

    # ─── 2.5 Trade Math Accuracy ─────────────────────────────────────────

    def _trade_math_accuracy(self, recording: GameRecording) -> MetricResult:
        """Check if trade actions demonstrate correct math understanding."""
        accurate = 0
        total_trades = 0

        for snap in recording.turns:
            if not snap.parsed_response:
                continue
            action = snap.parsed_response.action

            if action == BenchmarkActionType.TRADE_BUY:
                total_trades += 1
                params = snap.parsed_response.params
                resource = params.get("resource", "")
                quantity = int(params.get("quantity", 0))
                price = getattr(snap.state.market_prices, resource, 1.0)
                expected_cost = quantity * price
                gold = snap.state.resources.gold

                # Accurate if LLM has enough gold for the purchase
                if gold >= expected_cost:
                    accurate += 1

            elif action == BenchmarkActionType.TRADE_SELL:
                total_trades += 1
                params = snap.parsed_response.params
                resource = params.get("resource", "")
                quantity = int(params.get("quantity", 0))
                current = getattr(snap.state.resources, resource, 0)

                # Accurate if LLM has enough of the resource to sell
                if current >= quantity:
                    accurate += 1

        if total_trades == 0:
            return MetricResult(metric_id="2.5_trade_math_accuracy", value=0.5, raw_value=0.0, sample_count=0)

        score = accurate / total_trades
        return MetricResult(
            metric_id="2.5_trade_math_accuracy",
            value=score,
            raw_value=score,
            sample_count=total_trades,
            details={"accurate_trades": accurate, "total_trades": total_trades},
        )

    # ─── 2.6 Multi-Resource Feasibility ──────────────────────────────────

    def _multi_resource_feasibility(self, recording: GameRecording) -> MetricResult:
        """Check if multi-resource actions had ALL requirements met."""
        failures = 0
        total_multi = 0

        for snap in recording.turns:
            if not snap.parsed_response:
                continue
            action = snap.parsed_response.action

            # BUILD and UPGRADE typically require multiple resources
            if action not in (BenchmarkActionType.BUILD, BenchmarkActionType.UPGRADE):
                continue
            if snap.valid:
                # Valid means engine accepted it — resources were sufficient
                continue

            # Invalid multi-resource action — check if SOME resources were met
            total_multi += 1
            # If the action was rejected, it's a feasibility failure
            # (LLM thought it could afford it but couldn't)
            failures += 1

        if total_multi == 0:
            return MetricResult(metric_id="2.6_multi_resource_feasibility", value=1.0, raw_value=0.0, sample_count=0)

        rate = failures / total_multi
        score = clamp(1.0 - rate)
        return MetricResult(
            metric_id="2.6_multi_resource_feasibility",
            value=score,
            raw_value=rate,
            sample_count=total_multi,
            details={"feasibility_failures": failures, "total_multi_resource": total_multi},
        )
