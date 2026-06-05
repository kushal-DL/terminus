"""Balanced agent — optimal textbook play opponent."""

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


# Phase-based build priorities (in order)
_EARLY_BUILDS = ["farm", "housing", "warehouse"]
_MID_BUILDS = ["housing", "library", "barracks"]
_LATE_BUILDS = ["wall", "watchtower"]

# Phase-based worker ratios
_WORKER_RATIOS = {
    "early": {"farming": 0.50, "mining": 0.20, "research": 0.10, "construction": 0.20, "defense": 0.0, "medicine": 0.0},
    "mid": {"farming": 0.40, "mining": 0.20, "research": 0.20, "construction": 0.10, "defense": 0.10, "medicine": 0.0},
    "late": {"farming": 0.35, "mining": 0.15, "research": 0.25, "construction": 0.05, "defense": 0.15, "medicine": 0.05},
    "end": {"farming": 0.30, "mining": 0.10, "research": 0.30, "construction": 0.0, "defense": 0.20, "medicine": 0.10},
    "catastrophe": {"farming": 0.30, "mining": 0.10, "research": 0.10, "construction": 0.05, "defense": 0.30, "medicine": 0.15},
}


class BalancedAgent(BuiltInAgent):
    """Textbook optimal play — phase-based strategy with adaptive responses."""

    name = "Balanced Bot"
    archetype = "balanced"
    preferred_location = "forest"
    preferred_specialization = "science"

    def __init__(self, seed: int = 42):
        super().__init__(seed)
        self._last_allocation_turn = -10  # Don't reallocate every turn

    def choose_action(
        self,
        state: BenchmarkGameState,
        available_actions: list[AvailableAction],
        turn: int,
        opponent_history: list[dict] | None = None,
    ) -> ActionResponse:
        if not available_actions:
            return self.make_pass_action()

        phase = self._get_phase(turn)

        # Priority 1: Repair damaged buildings
        if self.has_action(available_actions, "REPAIR"):
            damaged = self.get_repairable_buildings(state)
            if damaged:
                return self.make_action(
                    BenchmarkActionType.REPAIR,
                    {"building_type": damaged[0]},
                    ReasoningFactorType.IMMEDIATE_SURVIVAL,
                )

        # Priority 2: Reallocate workers if phase changed or first turn
        if self.has_action(available_actions, "ALLOCATE_WORKERS") and (turn - self._last_allocation_turn >= 10 or turn <= 2):
            ratios = self._get_worker_ratios(state, phase)
            allocation = self.get_worker_allocation(state, ratios)
            self._last_allocation_turn = turn
            return self.make_action(
                BenchmarkActionType.ALLOCATE_WORKERS,
                {"allocation": allocation},
                ReasoningFactorType.EFFICIENCY_OPTIMIZATION,
            )

        # Priority 3: Build from phase priority list
        buildable = self.get_affordable_buildings(available_actions)
        target_building = self._pick_building(buildable, state, phase)
        if target_building:
            return self.make_action(
                BenchmarkActionType.BUILD,
                {"building_type": target_building},
                ReasoningFactorType.LONG_TERM_GROWTH,
            )

        # Priority 4: Upgrade existing buildings
        upgradeable = self.get_upgradeable_buildings(available_actions)
        target_upgrade = self._pick_upgrade(upgradeable, state, phase)
        if target_upgrade:
            return self.make_action(
                BenchmarkActionType.UPGRADE,
                {"building_type": target_upgrade},
                ReasoningFactorType.LONG_TERM_GROWTH,
            )

        # Priority 5: Market trading (buy knowledge when cheap, sell surplus)
        market_action = self._consider_market(state, available_actions)
        if market_action:
            return market_action

        # Priority 6: Propose trades if surplus detected
        if self.has_action(available_actions, "TRADE_OFFER") and self._should_propose_trade(state, turn):
            return self._propose_fair_trade(state)

        return self.make_pass_action()

    def evaluate_trade(
        self,
        offer: TradeOfferInfo,
        state: BenchmarkGameState,
        turn: int,
    ) -> Literal["accept", "decline"]:
        # Accept if mutually beneficial (offer value >= 90% of request value)
        fairness = self.score_trade_fairness(offer, state)
        return "accept" if fairness >= -0.1 else "decline"

    def _get_phase(self, turn: int) -> str:
        if turn <= 20:
            return "early"
        if turn <= 50:
            return "mid"
        if turn <= 80:
            return "late"
        return "end"

    def _get_worker_ratios(self, state: BenchmarkGameState, phase: str) -> dict[str, float]:
        """Get worker ratios, shifting to defensive if catastrophe warning active."""
        if state.catastrophe_warning:
            return _WORKER_RATIOS["catastrophe"]
        return _WORKER_RATIOS[phase]

    def _pick_building(self, buildable: list[str], state: BenchmarkGameState, phase: str) -> str | None:
        """Pick the highest-priority building to construct."""
        existing = {b.type for b in state.buildings}

        if phase == "early":
            priority = _EARLY_BUILDS
        elif phase == "mid":
            priority = _MID_BUILDS
        else:
            priority = _LATE_BUILDS

        for building in priority:
            if building in buildable and building not in existing:
                return building

        # If all priority buildings exist, build any available
        for building in buildable:
            if building not in existing:
                return building

        return None

    def _pick_upgrade(self, upgradeable: list[str], state: BenchmarkGameState, phase: str) -> str | None:
        """Pick the best building to upgrade."""
        if not upgradeable:
            return None

        # Prioritize: farm > housing > library > barracks > wall
        upgrade_priority = ["farm", "housing", "library", "barracks", "wall", "watchtower", "warehouse"]
        for building in upgrade_priority:
            if building in upgradeable:
                return building

        return upgradeable[0]

    def _consider_market(self, state: BenchmarkGameState, available_actions: list[AvailableAction]) -> ActionResponse | None:
        """Consider market buy/sell opportunities."""
        prices = state.market_prices
        resources = state.resources

        # Buy knowledge when price is below 4 gold and we have gold
        if self.has_action(available_actions, "TRADE_BUY") and prices.knowledge < 4.0 and resources.gold > 30:
            qty = min(10, int(resources.gold / prices.knowledge) - 2)
            if qty > 0:
                return self.make_action(
                    BenchmarkActionType.TRADE_BUY,
                    {"resource": "knowledge", "quantity": qty},
                    ReasoningFactorType.MARKET_OPPORTUNITY,
                )

        # Sell surplus food/materials when price is high
        if self.has_action(available_actions, "TRADE_SELL"):
            if resources.food > 200 and prices.food > 2.5:
                return self.make_action(
                    BenchmarkActionType.TRADE_SELL,
                    {"resource": "food", "quantity": int(min(50, resources.food - 150))},
                    ReasoningFactorType.MARKET_OPPORTUNITY,
                )
            if resources.materials > 200 and prices.materials > 4.0:
                return self.make_action(
                    BenchmarkActionType.TRADE_SELL,
                    {"resource": "materials", "quantity": int(min(50, resources.materials - 150))},
                    ReasoningFactorType.MARKET_OPPORTUNITY,
                )

        return None

    def _should_propose_trade(self, state: BenchmarkGameState, turn: int) -> bool:
        """Propose trades when we have surplus and need something."""
        if len(state.outgoing_trade_offers) >= 2:
            return False
        resources = state.resources
        # Surplus food, need knowledge
        if resources.food > 200 and resources.knowledge < 50:
            return True
        # Surplus materials, need gold
        if resources.materials > 200 and resources.gold < 30:
            return True
        return False

    def _propose_fair_trade(self, state: BenchmarkGameState) -> ActionResponse:
        """Propose a fair trade based on surplus/deficit."""
        resources = state.resources

        if resources.food > 200 and resources.knowledge < 50:
            offer_res = {"food": 30.0}
            request_res = {"knowledge": 15.0}
        elif resources.materials > 200 and resources.gold < 30:
            offer_res = {"materials": 25.0}
            request_res = {"gold": 20.0}
        else:
            offer_res = {"food": 20.0}
            request_res = {"materials": 20.0}

        return self.make_action(
            BenchmarkActionType.TRADE_OFFER,
            {
                "to_player_id": "player_0",
                "offer_resources": offer_res,
                "request_resources": request_res,
            },
            ReasoningFactorType.COOPERATIVE_OPPORTUNITY,
        )
