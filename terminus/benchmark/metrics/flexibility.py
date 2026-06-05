"""Flexibility/Adaptation metrics (3.1–3.7) — measure response to disruptions."""

from __future__ import annotations

from terminus.benchmark.metrics.base import MetricCollector, MetricResult
from terminus.benchmark.metrics.utils import (
    action_distribution,
    clamp,
    find_catastrophe_turns,
    find_starvation_turns,
    jensen_shannon_divergence,
    kendall_tau,
    production_total_at_turn,
)
from terminus.benchmark.schemas import BenchmarkActionType, GameRecording, TurnSnapshot


class FlexibilityCollector(MetricCollector):
    """Computes metrics 3.1–3.7: adaptation and recovery quality."""

    def compute(self, recording: GameRecording) -> list[MetricResult]:
        return [
            self._post_catastrophe_recovery(recording),
            self._worker_reallocation_after_damage(recording),
            self._repair_prioritization(recording),
            self._market_adaptation(recording),
            self._starvation_response_speed(recording),
            self._defense_investment_after_hit(recording),
            self._action_distribution_shift(recording),
        ]

    # ─── 3.1 Post-Catastrophe Recovery Speed ─────────────────────────────

    def _post_catastrophe_recovery(self, recording: GameRecording) -> MetricResult:
        """Turns to recover 90% production after catastrophe."""
        cat_turns = find_catastrophe_turns(recording)
        if not cat_turns:
            return MetricResult(metric_id="3.1_post_catastrophe_recovery", value=0.5, raw_value=0.0, sample_count=0)

        recovery_speeds: list[float] = []
        turns = recording.turns

        for cat_turn in cat_turns:
            # Find the snapshot index for this turn
            cat_idx = None
            for i, snap in enumerate(turns):
                if snap.turn == cat_turn:
                    cat_idx = i
                    break
            if cat_idx is None or cat_idx == 0:
                continue

            # Get pre-catastrophe production level
            pre_prod = production_total_at_turn(recording, turns[cat_idx - 1].turn)
            if pre_prod <= 0:
                continue

            target = pre_prod * 0.9
            recovery_turn = None

            # Search forward for recovery
            for j in range(cat_idx + 1, min(cat_idx + 31, len(turns))):
                current_prod = production_total_at_turn(recording, turns[j].turn)
                if current_prod >= target:
                    recovery_turn = j - cat_idx
                    break

            if recovery_turn is None:
                recovery_speeds.append(30)  # Max penalty
            else:
                recovery_speeds.append(recovery_turn)

        if not recovery_speeds:
            return MetricResult(metric_id="3.1_post_catastrophe_recovery", value=0.5, raw_value=0.0, sample_count=0)

        avg_recovery = sum(recovery_speeds) / len(recovery_speeds)
        score = clamp(1.0 - avg_recovery / 30)

        return MetricResult(
            metric_id="3.1_post_catastrophe_recovery",
            value=score,
            raw_value=avg_recovery,
            sample_count=len(recovery_speeds),
            details={"avg_recovery_turns": avg_recovery, "catastrophe_count": len(cat_turns)},
        )

    # ─── 3.2 Worker Reallocation After Damage ────────────────────────────

    def _worker_reallocation_after_damage(self, recording: GameRecording) -> MetricResult:
        """Check if workers are reallocated appropriately after damage events."""
        appropriate = 0
        total_damage_events = 0

        cat_turns = find_catastrophe_turns(recording)
        turns = recording.turns

        for cat_turn in cat_turns:
            cat_idx = None
            for i, snap in enumerate(turns):
                if snap.turn == cat_turn:
                    cat_idx = i
                    break
            if cat_idx is None:
                continue

            total_damage_events += 1

            # Check if ALLOCATE_WORKERS happened within 3 turns after
            reallocated = False
            for j in range(cat_idx + 1, min(cat_idx + 4, len(turns))):
                if turns[j].parsed_response and turns[j].parsed_response.action == BenchmarkActionType.ALLOCATE_WORKERS:
                    reallocated = True
                    break

            if reallocated:
                appropriate += 1

        if total_damage_events == 0:
            return MetricResult(metric_id="3.2_worker_reallocation_after_damage", value=0.5, raw_value=0.0, sample_count=0)

        score = appropriate / total_damage_events
        return MetricResult(
            metric_id="3.2_worker_reallocation_after_damage",
            value=score,
            raw_value=score,
            sample_count=total_damage_events,
            details={"appropriate": appropriate, "total_damage_events": total_damage_events},
        )

    # ─── 3.3 Repair Prioritization (Kendall Tau) ─────────────────────────

    def _repair_prioritization(self, recording: GameRecording) -> MetricResult:
        """Compare repair order to optimal (highest value buildings first)."""
        # Find turns with REPAIR actions
        repair_order: list[str] = []
        damaged_buildings: dict[str, float] = {}  # type → value score

        for snap in recording.turns:
            # Track damaged buildings for optimal ordering
            for b in snap.state.buildings:
                if b.health < b.max_health and not b.under_construction:
                    value = b.max_health * b.level
                    damaged_buildings[b.type] = value

            if not snap.parsed_response:
                continue
            if snap.parsed_response.action == BenchmarkActionType.REPAIR and snap.valid:
                btype = snap.parsed_response.params.get("building_type", "")
                if btype and btype not in repair_order:
                    repair_order.append(btype)

        if len(repair_order) < 2:
            return MetricResult(metric_id="3.3_repair_prioritization", value=0.5, raw_value=0.0, sample_count=0)

        # Optimal order: sort by value (descending)
        optimal_order = sorted(
            [b for b in repair_order if b in damaged_buildings],
            key=lambda x: damaged_buildings.get(x, 0),
            reverse=True,
        )
        actual_filtered = [b for b in repair_order if b in optimal_order]

        if len(actual_filtered) < 2:
            return MetricResult(metric_id="3.3_repair_prioritization", value=0.5, raw_value=0.0, sample_count=0)

        tau = kendall_tau(actual_filtered, optimal_order)
        score = (tau + 1.0) / 2.0  # Map [-1, 1] to [0, 1]

        return MetricResult(
            metric_id="3.3_repair_prioritization",
            value=score,
            raw_value=tau,
            sample_count=len(actual_filtered),
            details={"repair_order": repair_order[:10], "optimal_order": optimal_order[:10], "tau": tau},
        )

    # ─── 3.4 Market Adaptation After Price Shock ─────────────────────────

    def _market_adaptation(self, recording: GameRecording) -> MetricResult:
        """Check if LLM exploits market price shocks."""
        shocks_exploited = 0
        total_shocks = 0

        turns = recording.turns
        if len(turns) < 6:
            return MetricResult(metric_id="3.4_market_adaptation", value=0.5, raw_value=0.0, sample_count=0)

        # Detect price shocks (>30% change in 5 turns)
        for res in ("food", "materials", "knowledge"):
            for i in range(5, len(turns)):
                current_price = getattr(turns[i].state.market_prices, res, 1.0)
                past_price = getattr(turns[i - 5].state.market_prices, res, 1.0)
                if past_price == 0:
                    continue

                change = abs(current_price - past_price) / past_price
                if change < 0.3:
                    continue

                total_shocks += 1
                price_went_up = current_price > past_price

                # Check if LLM exploited within next 5 turns
                exploited = False
                for j in range(i, min(i + 5, len(turns))):
                    if not turns[j].parsed_response:
                        continue
                    action = turns[j].parsed_response.action
                    params = turns[j].parsed_response.params
                    action_res = params.get("resource", "")

                    if action_res != res:
                        continue
                    if price_went_up and action == BenchmarkActionType.TRADE_SELL:
                        exploited = True
                        break
                    elif not price_went_up and action == BenchmarkActionType.TRADE_BUY:
                        exploited = True
                        break

                if exploited:
                    shocks_exploited += 1

        if total_shocks == 0:
            return MetricResult(metric_id="3.4_market_adaptation", value=0.5, raw_value=0.0, sample_count=0)

        score = shocks_exploited / total_shocks
        return MetricResult(
            metric_id="3.4_market_adaptation",
            value=score,
            raw_value=score,
            sample_count=total_shocks,
            details={"exploited": shocks_exploited, "total_shocks": total_shocks},
        )

    # ─── 3.5 Starvation Response Speed ───────────────────────────────────

    def _starvation_response_speed(self, recording: GameRecording) -> MetricResult:
        """Turns to recover from food=0."""
        starvation_starts = find_starvation_turns(recording)
        if not starvation_starts:
            return MetricResult(metric_id="3.5_starvation_response_speed", value=1.0, raw_value=0.0, sample_count=0)

        # Group consecutive starvation into episodes
        episodes: list[int] = []  # Duration of each starvation episode
        turns = recording.turns

        in_starvation = False
        episode_start = 0
        for i, snap in enumerate(turns):
            if snap.state.resources.food <= 0:
                if not in_starvation:
                    in_starvation = True
                    episode_start = i
            else:
                if in_starvation:
                    episodes.append(i - episode_start)
                    in_starvation = False

        # If still starving at end
        if in_starvation:
            episodes.append(len(turns) - episode_start)

        if not episodes:
            return MetricResult(metric_id="3.5_starvation_response_speed", value=1.0, raw_value=0.0, sample_count=0)

        avg_duration = sum(episodes) / len(episodes)
        score = clamp(1.0 - avg_duration / 10)  # 10 turns = 0 score

        return MetricResult(
            metric_id="3.5_starvation_response_speed",
            value=score,
            raw_value=avg_duration,
            sample_count=len(episodes),
            details={"avg_duration": avg_duration, "episodes": len(episodes)},
        )

    # ─── 3.6 Defense Investment After First Hit ──────────────────────────

    def _defense_investment_after_hit(self, recording: GameRecording) -> MetricResult:
        """Check if LLM builds defense after first catastrophe damage."""
        cat_turns = find_catastrophe_turns(recording)
        if not cat_turns:
            return MetricResult(metric_id="3.6_defense_investment_after_hit", value=0.5, raw_value=0.0, sample_count=0)

        first_cat_turn = cat_turns[0]
        turns = recording.turns

        # Find index of first catastrophe
        first_idx = None
        for i, snap in enumerate(turns):
            if snap.turn == first_cat_turn:
                first_idx = i
                break
        if first_idx is None:
            return MetricResult(metric_id="3.6_defense_investment_after_hit", value=0.5, raw_value=0.0, sample_count=0)

        # Look for defense investment within 30 turns
        invested_turn = None
        for j in range(first_idx + 1, min(first_idx + 31, len(turns))):
            snap = turns[j]
            if not snap.parsed_response:
                continue
            action = snap.parsed_response.action
            params = snap.parsed_response.params

            # Defense actions: build wall/barracks, upgrade defense buildings, increase defense workers
            if action == BenchmarkActionType.BUILD and params.get("building_type") in ("wall", "barracks", "watchtower"):
                invested_turn = j - first_idx
                break
            if action == BenchmarkActionType.UPGRADE and params.get("building_type") in ("wall", "barracks"):
                invested_turn = j - first_idx
                break
            if action == BenchmarkActionType.ALLOCATE_WORKERS:
                allocation = params.get("allocation", params)
                if isinstance(allocation, dict):
                    new_defense = int(allocation.get("defense", 0))
                    if first_idx > 0 and new_defense > turns[first_idx].state.workers.defense:
                        invested_turn = j - first_idx
                        break

        if invested_turn is None:
            score = 0.0
            raw = 30.0
        elif invested_turn <= 10:
            score = 1.0
            raw = float(invested_turn)
        else:
            # Linear decay from 1.0 at turn 10 to 0.0 at turn 30
            score = clamp(1.0 - (invested_turn - 10) / 20)
            raw = float(invested_turn)

        return MetricResult(
            metric_id="3.6_defense_investment_after_hit",
            value=score,
            raw_value=raw,
            sample_count=1,
            details={"invested_turn_after_hit": invested_turn, "first_catastrophe_turn": first_cat_turn},
        )

    # ─── 3.7 Action Distribution Shift (JS Divergence) ───────────────────

    def _action_distribution_shift(self, recording: GameRecording) -> MetricResult:
        """Measure strategy shift pre/post disruption using JS divergence."""
        cat_turns = find_catastrophe_turns(recording)
        turns = recording.turns

        if not turns:
            return MetricResult(metric_id="3.7_action_distribution_shift", value=0.5, raw_value=0.0, sample_count=0)

        # Split at first catastrophe, or midpoint if no catastrophes
        if cat_turns:
            split_turn = cat_turns[0]
            split_idx = None
            for i, snap in enumerate(turns):
                if snap.turn == split_turn:
                    split_idx = i
                    break
            if split_idx is None or split_idx < 3 or split_idx >= len(turns) - 3:
                split_idx = len(turns) // 2
        else:
            split_idx = len(turns) // 2

        pre_turns = turns[:split_idx]
        post_turns = turns[split_idx:]

        if len(pre_turns) < 3 or len(post_turns) < 3:
            return MetricResult(metric_id="3.7_action_distribution_shift", value=0.5, raw_value=0.0, sample_count=0)

        pre_dist = action_distribution(pre_turns)
        post_dist = action_distribution(post_turns)

        divergence = jensen_shannon_divergence(pre_dist, post_dist)

        # Ideal divergence is moderate (0.3-0.7)
        # Too low = rigid, too high = incoherent
        # Peak score at divergence = 0.4
        score = clamp(1.0 - abs(divergence - 0.4) * 2.5)

        return MetricResult(
            metric_id="3.7_action_distribution_shift",
            value=score,
            raw_value=divergence,
            sample_count=len(turns),
            details={
                "divergence": divergence,
                "pre_distribution": pre_dist,
                "post_distribution": post_dist,
                "split_at_turn": turns[split_idx].turn if split_idx < len(turns) else 0,
            },
        )
