"""Heuristic AI strategies for headless game simulation.

Each strategy implements decide_actions() which returns a list of
(ActionType, payload) tuples to execute each tick.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from terminus.server.models import ActionType, Colony


class Strategy(ABC):
    """Base class for AI heuristic strategies."""

    name: str = "base"

    @abstractmethod
    def decide_actions(self, colony: Colony, tick: int) -> list[tuple[ActionType, dict[str, Any]]]:
        """Return list of (action_type, payload) to execute this tick."""
        ...

    # ── Helpers ──────────────────────────────────────────────────────────

    def _has_building(self, colony: Colony, building_type: str) -> bool:
        return any(
            b.building_type == building_type and b.level > 0 and not b.under_construction
            for b in colony.buildings
        )

    def _building_level(self, colony: Colony, building_type: str) -> int:
        for b in colony.buildings:
            if b.building_type == building_type and not b.under_construction:
                return b.level
        return 0

    def _is_constructing(self, colony: Colony) -> bool:
        return any(b.under_construction for b in colony.buildings)

    def _can_afford(self, colony: Colony, costs: dict[str, float]) -> bool:
        for res, amount in costs.items():
            current = getattr(colony.resources, res, 0)
            if current < amount:
                return False
        return True

    def _worker_alloc(self, colony: Colony, ratios: dict[str, float]) -> dict[str, int]:
        """Distribute population according to ratios (must sum to ~1.0)."""
        pop = colony.population
        if pop == 0:
            return {r: 0 for r in ratios}
        alloc = {}
        assigned = 0
        roles = list(ratios.keys())
        for role in roles[:-1]:
            count = int(pop * ratios[role])
            alloc[role] = count
            assigned += count
        # Last role gets remainder
        alloc[roles[-1]] = pop - assigned
        return alloc


# ─── Building cost lookup ────────────────────────────────────────────────────

_BUILDING_COSTS: dict[str, dict[str, float]] | None = None


def _get_costs() -> dict[str, dict[str, float]]:
    global _BUILDING_COSTS
    if _BUILDING_COSTS is None:
        from terminus.data.loader import get_buildings
        _BUILDING_COSTS = {}
        for b in get_buildings():
            _BUILDING_COSTS[b["id"]] = b["costs"].get("1", {})
    return _BUILDING_COSTS


# ─── Balanced Strategy ───────────────────────────────────────────────────────


class BalancedStrategy(Strategy):
    """Even-split workers, build farm→wall→housing, moderate trading."""

    name = "balanced"
    build_order = ["farm", "wall", "housing", "hospital", "mine", "warehouse"]

    def decide_actions(self, colony: Colony, tick: int) -> list[tuple[ActionType, dict[str, Any]]]:
        actions: list[tuple[ActionType, dict[str, Any]]] = []

        # Worker allocation: balanced split
        constructing = self._is_constructing(colony)
        ratios = {
            "farming": 0.35,
            "mining": 0.25,
            "research": 0.05,
            "construction": 0.15 if constructing else 0.0,
            "defense": 0.10,
            "medicine": 0.10 if not constructing else 0.0,
        }
        # Redistribute construction workers when not building
        if not constructing:
            ratios["farming"] += 0.10
            ratios["mining"] += 0.05
        alloc = self._worker_alloc(colony, ratios)
        actions.append((ActionType.ALLOCATE_WORKERS, {"allocation": alloc}))

        # Build next in priority order (every 5 ticks, if not already constructing)
        if tick % 5 == 0 and not constructing:
            costs = _get_costs()
            for btype in self.build_order:
                if not self._has_building(colony, btype):
                    if btype in costs and self._can_afford(colony, costs[btype]):
                        actions.append((ActionType.BUILD, {"building_type": btype}))
                        break

        return actions


# ─── Aggressive Strategy ─────────────────────────────────────────────────────


class AggressiveStrategy(Strategy):
    """Heavy defense focus, wall→hospital→housing, stockpile for catastrophes."""

    name = "aggressive"
    build_order = ["wall", "hospital", "housing", "farm", "warehouse", "mine"]

    def decide_actions(self, colony: Colony, tick: int) -> list[tuple[ActionType, dict[str, Any]]]:
        actions: list[tuple[ActionType, dict[str, Any]]] = []

        constructing = self._is_constructing(colony)
        ratios = {
            "farming": 0.30,
            "mining": 0.15,
            "research": 0.0,
            "construction": 0.20 if constructing else 0.0,
            "defense": 0.25,
            "medicine": 0.10 if not constructing else 0.0,
        }
        if not constructing:
            ratios["farming"] += 0.10
            ratios["defense"] += 0.10
        alloc = self._worker_alloc(colony, ratios)
        actions.append((ActionType.ALLOCATE_WORKERS, {"allocation": alloc}))

        if tick % 5 == 0 and not constructing:
            costs = _get_costs()
            for btype in self.build_order:
                if not self._has_building(colony, btype):
                    if btype in costs and self._can_afford(colony, costs[btype]):
                        actions.append((ActionType.BUILD, {"building_type": btype}))
                        break

        return actions


# ─── Hoarder Strategy ────────────────────────────────────────────────────────


class HoarderStrategy(Strategy):
    """Max resource production, warehouse→farm→mine, minimal spending."""

    name = "hoarder"
    build_order = ["warehouse", "farm", "mine", "housing", "wall"]

    def decide_actions(self, colony: Colony, tick: int) -> list[tuple[ActionType, dict[str, Any]]]:
        actions: list[tuple[ActionType, dict[str, Any]]] = []

        constructing = self._is_constructing(colony)
        ratios = {
            "farming": 0.45,
            "mining": 0.35,
            "research": 0.0,
            "construction": 0.15 if constructing else 0.0,
            "defense": 0.05,
            "medicine": 0.0 if not constructing else 0.0,
        }
        if not constructing:
            ratios["farming"] += 0.10
            ratios["mining"] += 0.05
        alloc = self._worker_alloc(colony, ratios)
        actions.append((ActionType.ALLOCATE_WORKERS, {"allocation": alloc}))

        # Build less frequently — hoard resources
        if tick % 10 == 0 and not constructing:
            costs = _get_costs()
            for btype in self.build_order:
                if not self._has_building(colony, btype):
                    if btype in costs and self._can_afford(colony, costs[btype]):
                        actions.append((ActionType.BUILD, {"building_type": btype}))
                        break

        return actions


# ─── Researcher Strategy ─────────────────────────────────────────────────────


class ResearcherStrategy(Strategy):
    """Knowledge focus, lab→school→watchtower, trade knowledge for gold."""

    name = "researcher"
    build_order = ["lab", "school", "watchtower", "farm", "hospital", "wall"]

    def decide_actions(self, colony: Colony, tick: int) -> list[tuple[ActionType, dict[str, Any]]]:
        actions: list[tuple[ActionType, dict[str, Any]]] = []

        constructing = self._is_constructing(colony)
        ratios = {
            "farming": 0.25,
            "mining": 0.15,
            "research": 0.30,
            "construction": 0.15 if constructing else 0.0,
            "defense": 0.05,
            "medicine": 0.10 if not constructing else 0.0,
        }
        if not constructing:
            ratios["research"] += 0.10
            ratios["farming"] += 0.05
        alloc = self._worker_alloc(colony, ratios)
        actions.append((ActionType.ALLOCATE_WORKERS, {"allocation": alloc}))

        if tick % 5 == 0 and not constructing:
            costs = _get_costs()
            for btype in self.build_order:
                if not self._has_building(colony, btype):
                    if btype in costs and self._can_afford(colony, costs[btype]):
                        actions.append((ActionType.BUILD, {"building_type": btype}))
                        break

        return actions


# ─── Registry ────────────────────────────────────────────────────────────────

ALL_STRATEGIES: list[type[Strategy]] = [
    BalancedStrategy,
    AggressiveStrategy,
    HoarderStrategy,
    ResearcherStrategy,
]

STRATEGY_MAP: dict[str, type[Strategy]] = {s.name: s for s in ALL_STRATEGIES}
