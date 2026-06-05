"""Greedy agent — immediate value maximizer opponent."""

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


# Estimated value weights for scoring
_RESOURCE_SCORE_WEIGHTS = {"food": 1.0, "materials": 1.0, "knowledge": 3.0, "gold": 2.0}

# Building value heuristic (immediate production boost estimate)
_BUILDING_VALUE = {
    "farm": 8.0,
    "warehouse": 6.0,
    "housing": 7.0,
    "library": 5.0,
    "barracks": 2.0,
    "wall": 1.5,
    "watchtower": 1.0,
}


class GreedyAgent(BuiltInAgent):
    """Always picks the action with highest immediate score delta."""

    name = "Greedy Bot"
    archetype = "greedy"
    preferred_location = "plains"
    preferred_specialization = "agriculture"

    def choose_action(
        self,
        state: BenchmarkGameState,
        available_actions: list[AvailableAction],
        turn: int,
        opponent_history: list[dict] | None = None,
    ) -> ActionResponse:
        if not available_actions:
            return self.make_pass_action()

        # Score each action and pick the highest
        best_action = None
        best_score = -999.0

        for action in available_actions:
            score = self._estimate_value(action, state, turn)
            if score > best_score:
                best_score = score
                best_action = action

        if best_action is None:
            return self.make_pass_action()

        params = self._generate_params(best_action, state)
        return self.make_action(
            BenchmarkActionType(best_action.action_type),
            params,
            ReasoningFactorType.IMMEDIATE_SURVIVAL,
        )

    def evaluate_trade(
        self,
        offer: TradeOfferInfo,
        state: BenchmarkGameState,
        turn: int,
    ) -> Literal["accept", "decline"]:
        # Only accept if offer value > request value × 1.3
        fairness = self.score_trade_fairness(offer, state)
        return "accept" if fairness > 0.3 else "decline"

    def _estimate_value(self, action: AvailableAction, state: BenchmarkGameState, turn: int) -> float:
        """Estimate immediate value of an action."""
        action_type = action.action_type
        remaining = max(1, state.max_turns - turn)

        if action_type == "BUILD":
            building_type = (action.params_hint or {}).get("building_type", "farm")
            return _BUILDING_VALUE.get(building_type, 1.0) * min(remaining / 20, 1.0)

        if action_type == "UPGRADE":
            building_type = (action.params_hint or {}).get("building_type", "farm")
            return _BUILDING_VALUE.get(building_type, 1.0) * 0.7

        if action_type == "ALLOCATE_WORKERS":
            # Always somewhat valuable
            return 3.0

        if action_type == "TRADE_BUY":
            # Value depends on what resource and price
            return 2.0

        if action_type == "TRADE_SELL":
            # Selling generates gold (weight 2)
            return 4.0

        if action_type == "TRADE_OFFER":
            return 1.0

        if action_type == "TRADE_ACCEPT":
            # Check if we have incoming trades worth accepting
            if state.incoming_trade_offers:
                fairness = self.score_trade_fairness(state.incoming_trade_offers[0], state)
                return 5.0 * fairness if fairness > 0.3 else -1.0
            return -1.0

        if action_type == "TRADE_DECLINE":
            return 0.5

        if action_type == "REPAIR":
            return 3.0  # Preserving buildings is moderately valuable

        if action_type == "DEMOLISH":
            return -2.0  # Almost never a good greedy action

        return 0.0  # PASS

    def _generate_params(self, action: AvailableAction, state: BenchmarkGameState) -> dict:
        """Generate parameters for the chosen action."""
        action_type = action.action_type

        if action_type == "BUILD":
            building_type = (action.params_hint or {}).get("building_type", "farm")
            return {"building_type": building_type}

        if action_type == "UPGRADE":
            building_type = (action.params_hint or {}).get("building_type", "farm")
            return {"building_type": building_type}

        if action_type == "ALLOCATE_WORKERS":
            # Greedy allocation: 60% farm, 20% mining, 10% research, 10% construction
            ratios = {"farming": 0.6, "mining": 0.2, "research": 0.1, "construction": 0.1, "defense": 0.0, "medicine": 0.0}
            return {"allocation": self.get_worker_allocation(state, ratios)}

        if action_type == "TRADE_BUY":
            # Buy the highest-scoring resource
            prices = state.market_prices
            best_resource = "knowledge"  # 3× score weight
            if prices.food < 2.0:
                best_resource = "food"
            return {"resource": best_resource, "quantity": 10}

        if action_type == "TRADE_SELL":
            # Sell lowest-value resource
            resources = state.resources
            if resources.food > 100:
                return {"resource": "food", "quantity": int(min(50, resources.food - 80))}
            if resources.materials > 100:
                return {"resource": "materials", "quantity": int(min(50, resources.materials - 80))}
            return {"resource": "food", "quantity": 10}

        if action_type == "TRADE_ACCEPT":
            if state.incoming_trade_offers:
                return {"offer_id": state.incoming_trade_offers[0].offer_id}
            return {"offer_id": "unknown"}

        if action_type == "TRADE_DECLINE":
            if state.incoming_trade_offers:
                return {"offer_id": state.incoming_trade_offers[0].offer_id}
            return {"offer_id": "unknown"}

        if action_type == "TRADE_OFFER":
            # Propose unfair trade: ask 2× what we offer
            return {
                "to_player_id": "player_0",
                "offer_resources": {"food": 10.0},
                "request_resources": {"knowledge": 20.0},
            }

        if action_type == "REPAIR":
            damaged = self.get_repairable_buildings(state)
            if damaged:
                return {"building_type": damaged[0]}
            return {"building_type": "farm"}

        if action_type == "DEMOLISH":
            if state.buildings:
                return {"building_type": state.buildings[-1].type}
            return {"building_type": "farm"}

        return {}
