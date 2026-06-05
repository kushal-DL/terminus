"""Rush agent — aggressive population growth opponent."""

from __future__ import annotations

from typing import Literal

from terminus.benchmark.opponents.base import BuiltInAgent
from terminus.benchmark.schemas import (
    ActionResponse,
    AvailableAction,
    BenchmarkActionType,
    BenchmarkGameState,
    ReasoningFactorType,
    TradeOfferInfo,
)


class RushAgent(BuiltInAgent):
    """Maximize population growth early. Housing + Farm spam, ignores defense."""

    name = "Rush Bot"
    archetype = "rush"
    preferred_location = "plains"
    preferred_specialization = "agriculture"

    def __init__(self, seed: int = 42):
        super().__init__(seed)
        self._last_allocation_turn = -10

    def choose_action(
        self,
        state: BenchmarkGameState,
        available_actions: list[AvailableAction],
        turn: int,
        opponent_history: list[dict] | None = None,
    ) -> ActionResponse:
        if not available_actions:
            return self.make_pass_action()

        # Priority 1: Reallocate workers for maximum food production
        if self.has_action(available_actions, "ALLOCATE_WORKERS") and (turn - self._last_allocation_turn >= 8 or turn <= 2):
            ratios = self._get_ratios(state, turn)
            allocation = self.get_worker_allocation(state, ratios)
            self._last_allocation_turn = turn
            return self.make_action(
                BenchmarkActionType.ALLOCATE_WORKERS,
                {"allocation": allocation},
                ReasoningFactorType.LONG_TERM_GROWTH,
            )

        # Priority 2: Build housing (population cap) then farm (food security)
        buildable = self.get_affordable_buildings(available_actions)
        target = self._pick_building(buildable, state)
        if target:
            return self.make_action(
                BenchmarkActionType.BUILD,
                {"building_type": target},
                ReasoningFactorType.LONG_TERM_GROWTH,
            )

        # Priority 3: Upgrade housing > farm
        upgradeable = self.get_upgradeable_buildings(available_actions)
        target_upgrade = self._pick_upgrade(upgradeable)
        if target_upgrade:
            return self.make_action(
                BenchmarkActionType.UPGRADE,
                {"building_type": target_upgrade},
                ReasoningFactorType.LONG_TERM_GROWTH,
            )

        # Priority 4: Sell surplus food for gold (score points)
        if self.has_action(available_actions, "TRADE_SELL") and state.resources.food > 150:
            qty = int(min(50, state.resources.food - 100))
            if qty > 0:
                return self.make_action(
                    BenchmarkActionType.TRADE_SELL,
                    {"resource": "food", "quantity": qty},
                    ReasoningFactorType.MARKET_OPPORTUNITY,
                )

        # Priority 5: Early-game trade offers (sell food/materials for knowledge/gold)
        if turn <= 30 and self.has_action(available_actions, "TRADE_OFFER") and len(state.outgoing_trade_offers) < 2:
            if state.resources.food > 120:
                return self.make_action(
                    BenchmarkActionType.TRADE_OFFER,
                    {
                        "to_player_id": "player_0",
                        "offer_resources": {"food": 30.0},
                        "request_resources": {"knowledge": 20.0},
                    },
                    ReasoningFactorType.COOPERATIVE_OPPORTUNITY,
                )

        return self.make_pass_action()

    def evaluate_trade(
        self,
        offer: TradeOfferInfo,
        state: BenchmarkGameState,
        turn: int,
    ) -> Literal["accept", "decline"]:
        # Early: accept trades that give knowledge/gold for food/materials
        if turn <= 30:
            # Accept if we receive knowledge or gold
            receiving_valuable = any(
                r in ("knowledge", "gold") for r in offer.offer_resources
            )
            if receiving_valuable:
                fairness = self.score_trade_fairness(offer, state)
                return "accept" if fairness >= -0.2 else "decline"

        # After turn 50: decline everything (hoarding mode)
        if turn > 50:
            return "decline"

        # Mid-game: only accept clearly favorable trades
        fairness = self.score_trade_fairness(offer, state)
        return "accept" if fairness > 0.2 else "decline"

    def _get_ratios(self, state: BenchmarkGameState, turn: int) -> dict[str, float]:
        """Worker ratios — heavily farming-weighted."""
        # Emergency: if food is dangerously low, go all-in farming
        if state.resources.food < 30:
            return {"farming": 0.80, "mining": 0.10, "research": 0.0, "construction": 0.10, "defense": 0.0, "medicine": 0.0}

        # Normal rush allocation
        if turn <= 40:
            return {"farming": 0.70, "mining": 0.15, "research": 0.0, "construction": 0.15, "defense": 0.0, "medicine": 0.0}

        # Late game: shift some to mining/defense
        return {"farming": 0.60, "mining": 0.15, "research": 0.05, "construction": 0.0, "defense": 0.15, "medicine": 0.05}

    def _pick_building(self, buildable: list[str], state: BenchmarkGameState) -> str | None:
        """Rush: housing > farm > warehouse, nothing else."""
        existing = {b.type for b in state.buildings}

        # Alternate housing and farm
        priority = ["housing", "farm", "housing", "farm", "warehouse"]
        for building in priority:
            if building in buildable and building not in existing:
                return building

        # If all exist, just pick housing or farm if buildable
        for building in ["housing", "farm"]:
            if building in buildable:
                return building

        return None

    def _pick_upgrade(self, upgradeable: list[str]) -> str | None:
        """Rush: upgrade housing > farm."""
        priority = ["housing", "farm", "warehouse"]
        for building in priority:
            if building in upgradeable:
                return building
        return None
