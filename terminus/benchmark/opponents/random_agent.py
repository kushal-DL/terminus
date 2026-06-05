"""Random agent — uniform random baseline opponent."""

from __future__ import annotations

from typing import Literal

from terminus.benchmark.opponents.base import BuiltInAgent
from terminus.benchmark.schemas import (
    ActionResponse,
    AvailableAction,
    BenchmarkActionType,
    BenchmarkGameState,
    ReasoningFactor,
    ReasoningFactorType,
    Reasoning,
    TradeOfferInfo,
)


class RandomAgent(BuiltInAgent):
    """Uniform random action selection. Baseline opponent for benchmarking."""

    name = "Random Bot"
    archetype = "random"

    def __init__(self, seed: int = 42):
        super().__init__(seed)
        self.preferred_location = self.rng.choice(["coast", "mountain", "plains", "forest", "desert"])
        self.preferred_specialization = self.rng.choice(["military", "trade", "science", "agriculture"])

    def choose_action(
        self,
        state: BenchmarkGameState,
        available_actions: list[AvailableAction],
        turn: int,
        opponent_history: list[dict] | None = None,
    ) -> ActionResponse:
        if not available_actions:
            return self.make_pass_action()

        action = self.rng.choice(available_actions)
        action_type = action.action_type

        params = self._generate_random_params(action_type, action, state)

        return ActionResponse(
            action=BenchmarkActionType(action_type),
            params=params,
            reasoning=Reasoning(factors=[
                ReasoningFactor(factor=ReasoningFactorType.IMMEDIATE_SURVIVAL, weight=1.0),
            ]),
        )

    def evaluate_trade(
        self,
        offer: TradeOfferInfo,
        state: BenchmarkGameState,
        turn: int,
    ) -> Literal["accept", "decline"]:
        # 50% chance to accept any trade
        return "accept" if self.rng.random() < 0.5 else "decline"

    def _generate_random_params(
        self,
        action_type: str,
        action: AvailableAction,
        state: BenchmarkGameState,
    ) -> dict:
        """Generate random valid parameters for the given action type."""
        if action_type == "BUILD":
            buildings = self.get_affordable_buildings([action])
            if not buildings and action.params_hint and "building_type" in action.params_hint:
                buildings = [action.params_hint["building_type"]]
            if buildings:
                return {"building_type": self.rng.choice(buildings)}
            return {"building_type": "farm"}

        if action_type == "UPGRADE":
            upgradeable = self.get_upgradeable_buildings([action])
            if not upgradeable and action.params_hint and "building_type" in action.params_hint:
                upgradeable = [action.params_hint["building_type"]]
            if upgradeable:
                return {"building_type": self.rng.choice(upgradeable)}
            return {"building_type": "farm"}

        if action_type == "ALLOCATE_WORKERS":
            return {"allocation": self._random_worker_allocation(state.population)}

        if action_type == "TRADE_BUY":
            resource = self.rng.choice(["food", "materials", "knowledge"])
            quantity = self.rng.randint(1, 50)
            return {"resource": resource, "quantity": quantity}

        if action_type == "TRADE_SELL":
            resource = self.rng.choice(["food", "materials", "knowledge"])
            quantity = self.rng.randint(1, 50)
            return {"resource": resource, "quantity": quantity}

        if action_type == "TRADE_OFFER":
            offer_resource = self.rng.choice(["food", "materials", "knowledge", "gold"])
            request_resource = self.rng.choice(["food", "materials", "knowledge", "gold"])
            return {
                "to_player_id": "player_0",
                "offer_resources": {offer_resource: float(self.rng.randint(5, 30))},
                "request_resources": {request_resource: float(self.rng.randint(5, 30))},
            }

        if action_type in ("TRADE_ACCEPT", "TRADE_DECLINE"):
            if state.incoming_trade_offers:
                return {"offer_id": state.incoming_trade_offers[0].offer_id}
            return {"offer_id": "unknown"}

        if action_type in ("DEMOLISH", "REPAIR"):
            if state.buildings:
                building = self.rng.choice(state.buildings)
                return {"building_type": building.type}
            return {"building_type": "farm"}

        return {}

    def _random_worker_allocation(self, population: int) -> dict:
        """Generate random worker allocation summing to population."""
        if population <= 0:
            return {"farming": 0, "mining": 0, "research": 0, "construction": 0, "defense": 0, "medicine": 0}

        roles = ["farming", "mining", "research", "construction", "defense", "medicine"]
        # Generate random splits
        cuts = sorted(self.rng.randint(0, population) for _ in range(5))
        values = [cuts[0], cuts[1] - cuts[0], cuts[2] - cuts[1], cuts[3] - cuts[2], cuts[4] - cuts[3], population - cuts[4]]
        allocation = dict(zip(roles, values))
        return allocation
