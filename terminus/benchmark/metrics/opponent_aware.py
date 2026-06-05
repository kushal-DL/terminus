"""Opponent-aware metrics (5.1–5.5) — cross-game competitive analysis."""

from __future__ import annotations

from terminus.benchmark.metrics.base import CrossGameCollector, MetricResult
from terminus.benchmark.metrics.utils import clamp, linear_regression_slope
from terminus.benchmark.schemas import BenchmarkActionType, GameRecording


# Difficulty weights per opponent archetype
_DIFFICULTY_WEIGHTS: dict[str, float] = {
    "random": 0.5,
    "greedy": 0.8,
    "balanced": 1.0,
    "rush": 1.2,
    "turtle": 1.0,
    "adversarial": 2.0,
}


class OpponentAwareCollector(CrossGameCollector):
    """Computes metrics 5.1–5.5: competitive and cooperative performance."""

    def compute(self, recordings: list[GameRecording]) -> list[MetricResult]:
        return [
            self._win_rate_vs_archetypes(recordings),
            self._exploitation_resistance(recordings),
            self._counter_strategy_speed(recordings),
            self._cooperative_surplus(recordings),
            self._market_manipulation_detection(recordings),
        ]

    # ─── 5.1 Win Rate vs Archetypes ──────────────────────────────────────

    def _win_rate_vs_archetypes(self, recordings: list[GameRecording]) -> MetricResult:
        """Weighted win rate across opponent types."""
        if not recordings:
            return MetricResult(metric_id="5.1_win_rate_vs_archetypes", value=0.5, raw_value=0.0, sample_count=0)

        weighted_wins = 0.0
        weighted_total = 0.0
        per_archetype: dict[str, dict[str, int]] = {}

        for rec in recordings:
            opp = rec.opponent_type
            weight = _DIFFICULTY_WEIGHTS.get(opp, 1.0)

            if opp not in per_archetype:
                per_archetype[opp] = {"wins": 0, "games": 0}

            per_archetype[opp]["games"] += 1
            weighted_total += weight

            if rec.final_score > rec.opponent_final_score:
                weighted_wins += weight
                per_archetype[opp]["wins"] += 1

        if weighted_total == 0:
            return MetricResult(metric_id="5.1_win_rate_vs_archetypes", value=0.5, raw_value=0.0, sample_count=0)

        score = clamp(weighted_wins / weighted_total)
        return MetricResult(
            metric_id="5.1_win_rate_vs_archetypes",
            value=score,
            raw_value=weighted_wins / weighted_total,
            sample_count=len(recordings),
            details={"per_archetype": per_archetype, "weighted_wins": weighted_wins},
        )

    # ─── 5.2 Exploitation Resistance ─────────────────────────────────────

    def _exploitation_resistance(self, recordings: list[GameRecording]) -> MetricResult:
        """Score ratio vs adversarial compared to vs balanced."""
        adversarial_scores: list[int] = []
        balanced_scores: list[int] = []

        for rec in recordings:
            if rec.opponent_type == "adversarial":
                adversarial_scores.append(rec.final_score)
            elif rec.opponent_type == "balanced":
                balanced_scores.append(rec.final_score)

        if not adversarial_scores or not balanced_scores:
            return MetricResult(metric_id="5.2_exploitation_resistance", value=0.5, raw_value=0.0, sample_count=0)

        avg_adversarial = sum(adversarial_scores) / len(adversarial_scores)
        avg_balanced = sum(balanced_scores) / len(balanced_scores)

        if avg_balanced == 0:
            ratio = 1.0 if avg_adversarial >= 0 else 0.0
        else:
            ratio = avg_adversarial / avg_balanced

        score = clamp(ratio)
        return MetricResult(
            metric_id="5.2_exploitation_resistance",
            value=score,
            raw_value=ratio,
            sample_count=len(adversarial_scores) + len(balanced_scores),
            details={
                "avg_vs_adversarial": avg_adversarial,
                "avg_vs_balanced": avg_balanced,
                "ratio": ratio,
            },
        )

    # ─── 5.3 Counter-Strategy Detection Speed ────────────────────────────

    def _counter_strategy_speed(self, recordings: list[GameRecording]) -> MetricResult:
        """Turn at which LLM's score growth outpaces opponent's."""
        detection_points: list[float] = []

        for rec in recordings:
            turns = rec.turns
            if len(turns) < 10:
                continue

            # Compare score growth rates using rolling windows
            max_turns = len(turns)
            detection_turn = max_turns  # Default: never detected

            # Use 5-turn rolling score deltas
            for i in range(5, max_turns):
                # LLM score growth over last 5 turns
                llm_growth = turns[i].state.score - turns[i - 5].state.score
                # Opponent score growth (if visible)
                if turns[i].state.opponents and turns[i - 5].state.opponents:
                    opp_score_now = turns[i].state.opponents[0].score
                    opp_score_prev = turns[i - 5].state.opponents[0].score
                    opp_growth = opp_score_now - opp_score_prev

                    if llm_growth > opp_growth and llm_growth > 0:
                        detection_turn = i
                        break

            detection_points.append(detection_turn / max_turns)

        if not detection_points:
            return MetricResult(metric_id="5.3_counter_strategy_speed", value=0.5, raw_value=0.0, sample_count=0)

        avg_detection = sum(detection_points) / len(detection_points)
        # Earlier detection = higher score
        score = clamp(1.0 - avg_detection)

        return MetricResult(
            metric_id="5.3_counter_strategy_speed",
            value=score,
            raw_value=avg_detection,
            sample_count=len(detection_points),
            details={"avg_detection_fraction": avg_detection, "games_analyzed": len(detection_points)},
        )

    # ─── 5.4 Cooperative Surplus Capture ─────────────────────────────────

    def _cooperative_surplus(self, recordings: list[GameRecording]) -> MetricResult:
        """Measure value captured from P2P trades."""
        total_surplus = 0.0
        total_trades = 0

        for rec in recordings:
            for snap in rec.turns:
                if not snap.parsed_response:
                    continue
                action = snap.parsed_response.action

                if action == BenchmarkActionType.TRADE_ACCEPT and snap.valid:
                    total_trades += 1
                    # Successful trade acceptance = cooperative surplus
                    # Score increase from accepting trade is the surplus
                    # Approximate: each valid trade = small surplus unit
                    total_surplus += 1.0

                elif action == BenchmarkActionType.TRADE_OFFER and snap.valid:
                    total_trades += 1
                    total_surplus += 0.5  # Offering creates potential surplus

        if total_trades == 0:
            return MetricResult(metric_id="5.4_cooperative_surplus", value=0.5, raw_value=0.0, sample_count=0)

        # Normalize: assume ideal is ~0.5 trades per turn across all games
        total_turns = sum(len(r.turns) for r in recordings)
        expected_trades = total_turns * 0.1  # 10% of turns should involve trading
        rate = total_trades / max(expected_trades, 1)
        score = clamp(rate)

        return MetricResult(
            metric_id="5.4_cooperative_surplus",
            value=score,
            raw_value=total_surplus,
            sample_count=total_trades,
            details={"total_surplus": total_surplus, "total_trades": total_trades, "total_turns": total_turns},
        )

    # ─── 5.5 Market Manipulation Detection ───────────────────────────────

    def _market_manipulation_detection(self, recordings: list[GameRecording]) -> MetricResult:
        """Detect if LLM avoids buying during opponent pump phases."""
        avoided = 0
        total_pump_events = 0

        for rec in recordings:
            turns = rec.turns
            if len(turns) < 10:
                continue

            # Detect pump patterns: rapid price increase over 3-5 turns
            for res in ("food", "materials", "knowledge"):
                for i in range(3, len(turns)):
                    prices = [getattr(turns[j].state.market_prices, res, 1.0) for j in range(i - 3, i + 1)]
                    if len(prices) < 4:
                        continue

                    # Pump: monotonically increasing by >20% total
                    if all(prices[j] <= prices[j + 1] for j in range(len(prices) - 1)):
                        total_increase = (prices[-1] - prices[0]) / max(prices[0], 0.01)
                        if total_increase < 0.2:
                            continue

                        total_pump_events += 1
                        # Check if LLM bought this resource during the pump
                        bought_during_pump = False
                        for j in range(max(0, i - 3), min(i + 2, len(turns))):
                            snap = turns[j]
                            if (snap.parsed_response
                                    and snap.parsed_response.action == BenchmarkActionType.TRADE_BUY
                                    and snap.parsed_response.params.get("resource") == res):
                                bought_during_pump = True
                                break

                        if not bought_during_pump:
                            avoided += 1

        if total_pump_events == 0:
            return MetricResult(metric_id="5.5_market_manipulation_detection", value=0.5, raw_value=0.0, sample_count=0)

        score = avoided / total_pump_events
        return MetricResult(
            metric_id="5.5_market_manipulation_detection",
            value=score,
            raw_value=score,
            sample_count=total_pump_events,
            details={"avoided": avoided, "total_pump_events": total_pump_events},
        )
