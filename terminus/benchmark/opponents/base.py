"""Abstract base class for built-in benchmark opponents."""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from typing import Literal

from terminus.benchmark.schemas import (
    ActionResponse,
    AvailableAction,
    BenchmarkActionType,
    BenchmarkGameState,
    BenchmarkWorkerAllocation,
    ReasoningFactor,
    ReasoningFactorType,
    Reasoning,
    TradeOfferInfo,
)


class BuiltInAgent(ABC):
    """Abstract interface for scripted benchmark opponents."""

    name: str = "BaseAgent"
    archetype: str = "base"
    preferred_location: str = "plains"
    preferred_specialization: str = "agriculture"

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.seed = seed

    def get_setup_choices(self) -> dict:
        """Return location + specialization for game setup."""
        return {
            "location": self.preferred_location,
            "specialization": self.preferred_specialization,
        }

    @abstractmethod
    def choose_action(
        self,
        state: BenchmarkGameState,
        available_actions: list[AvailableAction],
        turn: int,
        opponent_history: list[dict] | None = None,
    ) -> ActionResponse:
        """Select an action given current game state."""
        ...

    @abstractmethod
    def evaluate_trade(
        self,
        offer: TradeOfferInfo,
        state: BenchmarkGameState,
        turn: int,
    ) -> Literal["accept", "decline"]:
        """Decide whether to accept or decline a trade offer."""
        ...

    # ─── Helper Utilities ─────────────────────────────────────────────────

    def has_action(self, available_actions: list[AvailableAction], action_type: str) -> bool:
        """Check if a specific action type is available."""
        return any(a.action_type == action_type for a in available_actions)

    def get_actions_of_type(self, available_actions: list[AvailableAction], action_type: str) -> list[AvailableAction]:
        """Get all available actions matching a type."""
        return [a for a in available_actions if a.action_type == action_type]

    def get_worker_allocation(self, state: BenchmarkGameState, ratios: dict[str, float]) -> dict[str, int]:
        """Compute integer worker allocation from target ratios × population.

        Ratios should sum to ~1.0. Adjusts for rounding to match population exactly.
        """
        pop = state.population
        if pop <= 0:
            return {"farming": 0, "mining": 0, "research": 0, "construction": 0, "defense": 0, "medicine": 0}

        roles = ["farming", "mining", "research", "construction", "defense", "medicine"]
        total_ratio = sum(ratios.get(r, 0) for r in roles)
        if total_ratio == 0:
            total_ratio = 1.0

        # Normalize and compute base allocation
        allocation = {}
        for role in roles:
            allocation[role] = int((ratios.get(role, 0) / total_ratio) * pop)

        # Distribute remainder to largest ratio role
        remainder = pop - sum(allocation.values())
        if remainder != 0:
            # Add remainder to the role with largest ratio
            largest_role = max(roles, key=lambda r: ratios.get(r, 0))
            allocation[largest_role] += remainder

        return allocation

    def score_trade_fairness(self, offer: TradeOfferInfo, state: BenchmarkGameState) -> float:
        """Evaluate trade offer value ratio. Returns -1 (terrible for us) to +1 (great for us).

        0.0 = perfectly fair exchange based on market prices.
        """
        prices = state.market_prices
        price_map = {"food": prices.food, "materials": prices.materials, "knowledge": prices.knowledge, "gold": 1.0}

        offer_value = sum(price_map.get(r, 1.0) * qty for r, qty in offer.offer_resources.items())
        request_value = sum(price_map.get(r, 1.0) * qty for r, qty in offer.request_resources.items())

        if offer_value + request_value == 0:
            return 0.0

        # Positive = we receive more value, negative = we give more value
        # This is from the perspective of the agent receiving the trade
        return (offer_value - request_value) / max(offer_value, request_value)

    def make_pass_action(self) -> ActionResponse:
        """Create a PASS action response."""
        return ActionResponse(
            action=BenchmarkActionType.PASS,
            params={},
            reasoning=Reasoning(factors=[
                ReasoningFactor(factor=ReasoningFactorType.IMMEDIATE_SURVIVAL, weight=1.0),
            ]),
        )

    def make_action(
        self,
        action_type: BenchmarkActionType,
        params: dict,
        factor: ReasoningFactorType = ReasoningFactorType.IMMEDIATE_SURVIVAL,
    ) -> ActionResponse:
        """Create an action response with simple single-factor reasoning."""
        return ActionResponse(
            action=action_type,
            params=params,
            reasoning=Reasoning(factors=[
                ReasoningFactor(factor=factor, weight=1.0),
            ]),
        )

    def get_affordable_buildings(self, available_actions: list[AvailableAction]) -> list[str]:
        """Extract buildable building types from available actions."""
        buildings = []
        for a in available_actions:
            if a.action_type == "BUILD" and a.params_hint and "building_type" in a.params_hint:
                buildings.append(a.params_hint["building_type"])
        return buildings

    def get_upgradeable_buildings(self, available_actions: list[AvailableAction]) -> list[str]:
        """Extract upgradeable building types from available actions."""
        buildings = []
        for a in available_actions:
            if a.action_type == "UPGRADE" and a.params_hint and "building_type" in a.params_hint:
                buildings.append(a.params_hint["building_type"])
        return buildings

    def get_repairable_buildings(self, state: BenchmarkGameState) -> list[str]:
        """Get buildings that need repair."""
        return [b.type for b in state.buildings if b.health < b.max_health and not b.under_construction]
