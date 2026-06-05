"""Turtle agent — heavy defense, slow growth, catastrophe-resilient opponent."""

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


# Worker ratios: heavy defense always
_NORMAL_RATIOS = {"farming": 0.30, "mining": 0.20, "research": 0.10, "construction": 0.10, "defense": 0.25, "medicine": 0.05}
_CATASTROPHE_RATIOS = {"farming": 0.25, "mining": 0.15, "research": 0.05, "construction": 0.05, "defense": 0.35, "medicine": 0.15}
_PLAGUE_RATIOS = {"farming": 0.25, "mining": 0.15, "research": 0.05, "construction": 0.05, "defense": 0.20, "medicine": 0.30}


class TurtleAgent(BuiltInAgent):
    """Heavy defense, slow growth, strong catastrophe resilience."""

    name = "Turtle Bot"
    archetype = "turtle"
    preferred_location = "mountain"
    preferred_specialization = "military"

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

        # Priority 1: Always repair damaged buildings
        if self.has_action(available_actions, "REPAIR"):
            damaged = self.get_repairable_buildings(state)
            if damaged:
                return self.make_action(
                    BenchmarkActionType.REPAIR,
                    {"building_type": damaged[0]},
                    ReasoningFactorType.DEFENSIVE_POSITIONING,
                )

        # Priority 2: Adjust workers (especially if catastrophe warning)
        if self.has_action(available_actions, "ALLOCATE_WORKERS") and (
            turn - self._last_allocation_turn >= 8
            or turn <= 2
            or (state.catastrophe_warning and turn - self._last_allocation_turn >= 3)
        ):
            ratios = self._get_ratios(state)
            allocation = self.get_worker_allocation(state, ratios)
            self._last_allocation_turn = turn
            return self.make_action(
                BenchmarkActionType.ALLOCATE_WORKERS,
                {"allocation": allocation},
                ReasoningFactorType.DEFENSIVE_POSITIONING,
            )

        # Priority 3: Build defensive buildings first
        buildable = self.get_affordable_buildings(available_actions)
        target = self._pick_building(buildable, state)
        if target:
            return self.make_action(
                BenchmarkActionType.BUILD,
                {"building_type": target},
                ReasoningFactorType.DEFENSIVE_POSITIONING,
            )

        # Priority 4: Upgrade defensive buildings
        upgradeable = self.get_upgradeable_buildings(available_actions)
        target_upgrade = self._pick_upgrade(upgradeable)
        if target_upgrade:
            return self.make_action(
                BenchmarkActionType.UPGRADE,
                {"building_type": target_upgrade},
                ReasoningFactorType.DEFENSIVE_POSITIONING,
            )

        # Priority 5: Buy materials for future repairs
        if self.has_action(available_actions, "TRADE_BUY") and state.resources.gold > 40 and state.resources.materials < 100:
            return self.make_action(
                BenchmarkActionType.TRADE_BUY,
                {"resource": "materials", "quantity": 10},
                ReasoningFactorType.CATASTROPHE_PREPARATION,
            )

        return self.make_pass_action()

    def evaluate_trade(
        self,
        offer: TradeOfferInfo,
        state: BenchmarkGameState,
        turn: int,
    ) -> Literal["accept", "decline"]:
        # Only accept if receiving materials or food (defensive resources)
        receiving_defensive = any(r in ("materials", "food") for r in offer.offer_resources)
        if not receiving_defensive:
            return "decline"

        fairness = self.score_trade_fairness(offer, state)
        return "accept" if fairness >= -0.05 else "decline"

    def _get_ratios(self, state: BenchmarkGameState) -> dict[str, float]:
        """Worker ratios — shift to specific defense on catastrophe warning."""
        if state.catastrophe_warning:
            category = state.catastrophe_warning.category
            if category == "population":
                return _PLAGUE_RATIOS
            return _CATASTROPHE_RATIOS
        return _NORMAL_RATIOS

    def _pick_building(self, buildable: list[str], state: BenchmarkGameState) -> str | None:
        """Turtle: barracks > wall > watchtower > farm > warehouse > housing."""
        existing = {b.type for b in state.buildings}
        priority = ["barracks", "wall", "watchtower", "farm", "warehouse", "housing"]

        for building in priority:
            if building in buildable and building not in existing:
                return building

        return None

    def _pick_upgrade(self, upgradeable: list[str]) -> str | None:
        """Turtle: upgrade defense buildings first."""
        priority = ["barracks", "wall", "watchtower", "farm", "warehouse", "housing"]
        for building in priority:
            if building in upgradeable:
                return building
        return None
