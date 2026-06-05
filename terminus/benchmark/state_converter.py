"""State converter — transforms engine state dicts into BenchmarkGameState models."""

from __future__ import annotations

from typing import Any

from terminus.benchmark.schemas import (
    AvailableAction,
    BenchmarkGameState,
    BenchmarkWorkerAllocation,
    BuildingState,
    CatastropheWarning,
    MarketPrices,
    OpponentInfo,
    ProductionRates,
    ResourceCapacity,
    ResourceState,
    TradeOfferInfo,
)


class StateConverter:
    """Converts raw engine get_player_state() dicts to BenchmarkGameState models."""

    def convert(
        self,
        raw_state: dict[str, Any],
        turn: int,
        max_turns: int,
        engine: Any = None,
    ) -> BenchmarkGameState:
        """Convert engine state dict to typed BenchmarkGameState.

        Args:
            raw_state: Return value of engine.get_player_state(player_id).
            turn: Current turn number (1-based).
            max_turns: Maximum turns in this game.
            engine: Optional GameEngine reference for score calculation.
        """
        colony = raw_state.get("colony") or {}
        market = raw_state.get("market") or {}

        # Compute rank from other_players scores
        my_score = colony.get("score", 0)
        others = raw_state.get("other_players", [])
        rank = 1 + sum(1 for o in others if o.get("score", 0) > my_score)

        return BenchmarkGameState(
            turn=turn,
            max_turns=max_turns,
            score=int(my_score),
            rank=rank,
            total_players=raw_state.get("player_count", 2),
            location=str(colony.get("location", "")),
            specialization=str(colony.get("specialization", "")),
            population=colony.get("population", 0),
            population_cap=colony.get("max_population", 50),
            morale=colony.get("morale", 1.0),
            resources=self._convert_resources(colony.get("resources", {})),
            capacity=self._convert_capacity(colony.get("capacity", {})),
            production=self._convert_production(raw_state.get("production_rates")),
            food_consumption=colony.get("population", 0) * 0.1,
            workers=self._convert_workers(colony.get("workers", {})),
            buildings=self._convert_buildings(colony.get("buildings", [])),
            market_prices=self._convert_market(market),
            sell_spread=self._get_sell_spread(colony),
            opponents=self._convert_opponents(others),
            catastrophe_warning=self._convert_catastrophe_warning(raw_state),
            incoming_trade_offers=self._convert_trade_offers(raw_state.get("incoming_trade_offers", [])),
            outgoing_trade_offers=self._convert_trade_offers(raw_state.get("outgoing_trade_offers", [])),
            available_actions=self.compute_available_actions(colony, raw_state),
        )

    def compute_available_actions(
        self,
        colony: dict[str, Any],
        raw_state: dict[str, Any],
    ) -> list[AvailableAction]:
        """Compute available actions filtered to affordable ones only."""
        actions: list[AvailableAction] = []
        if not colony:
            actions.append(AvailableAction(action_type="PASS", description="Do nothing this turn"))
            return actions

        resources = colony.get("resources", {})
        buildings = colony.get("buildings", [])
        population = colony.get("population", 0)
        existing_types = {b.get("building_type", b.get("type", "")) for b in buildings}

        # ALLOCATE_WORKERS — always available if pop > 0
        if population > 0:
            actions.append(AvailableAction(
                action_type="ALLOCATE_WORKERS",
                description="Redistribute workers across roles",
            ))

        # BUILD — for each affordable buildable type
        self._add_build_actions(actions, resources, existing_types, buildings)

        # UPGRADE — for each upgradeable building
        self._add_upgrade_actions(actions, resources, buildings)

        # TRADE_BUY — if gold > 0 and market has stock
        gold = resources.get("gold", 0)
        market = raw_state.get("market", {})
        market_prices = market.get("prices", {})
        market_stock = market.get("stock", {})
        if gold > 0:
            for res in ("food", "materials", "knowledge"):
                price = market_prices.get(res, 999)
                stock = market_stock.get(res, 0)
                if stock > 0 and gold >= price:
                    actions.append(AvailableAction(
                        action_type="TRADE_BUY",
                        description=f"Buy {res} from market at {price:.1f} gold each",
                        cost=f"{price:.1f} gold per unit",
                        params_hint={"resource": res},
                    ))

        # TRADE_SELL — if any resource > 0
        for res in ("food", "materials", "knowledge"):
            if resources.get(res, 0) > 0:
                sell_price = market_prices.get(res, 1.0) * 0.7
                actions.append(AvailableAction(
                    action_type="TRADE_SELL",
                    description=f"Sell {res} to market at {sell_price:.1f} gold each",
                    params_hint={"resource": res},
                ))

        # TRADE_OFFER — if < 3 outgoing and opponents exist
        outgoing = raw_state.get("outgoing_trade_offers", [])
        others = raw_state.get("other_players", [])
        if len(outgoing) < 3 and others:
            actions.append(AvailableAction(
                action_type="TRADE_OFFER",
                description="Propose a trade to another player",
            ))

        # TRADE_ACCEPT / TRADE_DECLINE — per incoming offer
        incoming = raw_state.get("incoming_trade_offers", [])
        for offer in incoming:
            offer_id = offer.get("offer_id", "")
            from_name = offer.get("from_player_id", "opponent")
            actions.append(AvailableAction(
                action_type="TRADE_ACCEPT",
                description=f"Accept trade offer from {from_name}",
                params_hint={"offer_id": offer_id},
            ))
            actions.append(AvailableAction(
                action_type="TRADE_DECLINE",
                description=f"Decline trade offer from {from_name}",
                params_hint={"offer_id": offer_id},
            ))

        # REPAIR — for damaged buildings
        materials = resources.get("materials", 0)
        for b in buildings:
            health = b.get("health", 100)
            max_health = b.get("max_health", 100)
            btype = b.get("building_type", b.get("type", ""))
            if health < max_health and not b.get("under_construction", False):
                repair_cost = (max_health - health) * 0.5
                if materials >= repair_cost:
                    actions.append(AvailableAction(
                        action_type="REPAIR",
                        description=f"Repair {btype} ({health:.0f}/{max_health:.0f} HP)",
                        cost=f"{repair_cost:.0f} materials",
                        params_hint={"building_type": btype},
                    ))

        # DEMOLISH — for any built building
        for b in buildings:
            btype = b.get("building_type", b.get("type", ""))
            level = b.get("level", 0)
            if level > 0 and not b.get("under_construction", False):
                actions.append(AvailableAction(
                    action_type="DEMOLISH",
                    description=f"Demolish {btype} (level {level})",
                    params_hint={"building_type": btype},
                ))

        # PASS — always available
        actions.append(AvailableAction(action_type="PASS", description="Do nothing this turn"))

        return actions

    # ─── Private Conversion Methods ───────────────────────────────────────

    def _convert_resources(self, raw: dict[str, Any]) -> ResourceState:
        if isinstance(raw, dict):
            return ResourceState(
                food=raw.get("food", 0),
                materials=raw.get("materials", 0),
                knowledge=raw.get("knowledge", 0),
                gold=raw.get("gold", 0),
            )
        return ResourceState()

    def _convert_capacity(self, raw: dict[str, Any]) -> ResourceCapacity:
        if isinstance(raw, dict):
            return ResourceCapacity(
                food=int(raw.get("food", 500)),
                materials=int(raw.get("materials", 500)),
                knowledge=int(raw.get("knowledge", 200)),
                gold=int(raw.get("gold", 300)),
            )
        return ResourceCapacity()

    def _convert_production(self, raw: dict[str, Any] | None) -> ProductionRates:
        if raw and isinstance(raw, dict):
            return ProductionRates(
                food=raw.get("food", 0.0),
                materials=raw.get("materials", 0.0),
                knowledge=raw.get("knowledge", 0.0),
                gold=raw.get("gold", 0.0),
            )
        return ProductionRates()

    def _convert_workers(self, raw: dict[str, Any]) -> BenchmarkWorkerAllocation:
        if isinstance(raw, dict):
            return BenchmarkWorkerAllocation(
                farming=raw.get("farming", 0),
                mining=raw.get("mining", 0),
                research=raw.get("research", 0),
                construction=raw.get("construction", 0),
                defense=raw.get("defense", 0),
                medicine=raw.get("medicine", 0),
            )
        return BenchmarkWorkerAllocation()

    def _convert_buildings(self, raw_buildings: list[dict]) -> list[BuildingState]:
        result = []
        for b in raw_buildings:
            btype = b.get("building_type", b.get("type", "unknown"))
            level = b.get("level", 1)
            health = b.get("health", 100)
            max_health = b.get("max_health", level * 100)
            under_construction = b.get("under_construction", False)
            ticks_remaining = None
            if under_construction:
                progress = b.get("construction_progress", 0)
                target = b.get("construction_target", 10)
                ticks_remaining = max(0, int(target - progress))

            result.append(BuildingState(
                type=btype,
                level=max(1, level),
                health=int(health),
                max_health=int(max_health),
                under_construction=under_construction,
                ticks_remaining=ticks_remaining,
            ))
        return result

    def _convert_market(self, raw_market: dict[str, Any]) -> MarketPrices:
        prices = raw_market.get("prices", {})
        return MarketPrices(
            food=prices.get("food", 2.0),
            materials=prices.get("materials", 3.0),
            knowledge=prices.get("knowledge", 5.0),
        )

    def _get_sell_spread(self, colony: dict[str, Any]) -> float:
        spec = colony.get("specialization", "")
        if spec == "trade":
            return 0.85
        return 0.7

    def _convert_opponents(self, others: list[dict[str, Any]]) -> list[OpponentInfo]:
        result = []
        for o in others:
            result.append(OpponentInfo(
                name=o.get("name", "Unknown"),
                score=int(o.get("score", 0)),
                population=o.get("population", 0),
                building_count=o.get("building_count", 0),
                specialization=o.get("specialization"),
            ))
        return result

    def _convert_catastrophe_warning(self, raw_state: dict[str, Any]) -> CatastropheWarning | None:
        hint = raw_state.get("watchtower_hint")
        if not hint:
            return None

        # Parse watchtower hint text into structured warning
        next_in = raw_state.get("next_catastrophe_in")
        ticks_until = int(next_in / 2) if next_in else 0  # Convert seconds to ticks (2s/tick)

        # Determine category from hint text
        category = "infrastructure"  # default
        for cat in ("population", "resource", "infrastructure", "economic"):
            if cat in hint.lower():
                category = cat
                break

        cat_type = None
        if "is coming" in hint or "in ~" in hint:
            # Level 2+ hint includes the type name
            parts = hint.split(" is coming")
            if parts:
                cat_type = parts[0].strip()
            elif "in ~" in hint:
                parts = hint.split(" in ~")
                if parts:
                    cat_type = parts[0].strip()

        return CatastropheWarning(
            category=category,  # type: ignore[arg-type]
            type=cat_type,
            ticks_until=ticks_until,
        )

    def _convert_trade_offers(self, raw_offers: list[dict[str, Any]]) -> list[TradeOfferInfo]:
        result = []
        for o in raw_offers:
            result.append(TradeOfferInfo(
                offer_id=o.get("offer_id", ""),
                from_player=o.get("from_player_id", ""),
                to_player=o.get("to_player_id", ""),
                offer_resources=o.get("offer_resources", {}),
                request_resources=o.get("request_resources", {}),
                ticks_remaining=max(0, o.get("expires_tick", 0) - o.get("tick_created", 0)),
            ))
        return result

    def _add_build_actions(
        self,
        actions: list[AvailableAction],
        resources: dict[str, Any],
        existing_types: set[str],
        buildings: list[dict],
    ) -> None:
        """Add BUILD actions for affordable unbuilt building types."""
        try:
            from terminus.server.data_loader import get_all_buildings
            all_buildings = get_all_buildings()
        except Exception:
            # If data loader not available, use fallback list
            all_buildings = []

        if all_buildings:
            for bdata in all_buildings:
                bid = bdata.get("id", "")
                if bid not in existing_types:
                    costs = bdata.get("costs", {}).get("1", {})
                    if self._can_afford(resources, costs):
                        cost_str = ", ".join(f"{v} {k}" for k, v in costs.items())
                        actions.append(AvailableAction(
                            action_type="BUILD",
                            description=f"Build {bdata.get('name', bid)}",
                            cost=cost_str,
                            params_hint={"building_type": bid},
                        ))
        else:
            # Fallback: basic building types with estimated costs
            basic_buildings = {
                "farm": {"food": 20, "materials": 30},
                "housing": {"materials": 40, "gold": 20},
                "warehouse": {"materials": 50, "gold": 30},
                "library": {"materials": 30, "knowledge": 10, "gold": 20},
                "barracks": {"materials": 60, "gold": 30},
                "wall": {"materials": 80},
                "watchtower": {"materials": 40, "gold": 20},
            }
            for btype, costs in basic_buildings.items():
                if btype not in existing_types and self._can_afford(resources, costs):
                    cost_str = ", ".join(f"{v} {k}" for k, v in costs.items())
                    actions.append(AvailableAction(
                        action_type="BUILD",
                        description=f"Build {btype}",
                        cost=cost_str,
                        params_hint={"building_type": btype},
                    ))

    def _add_upgrade_actions(
        self,
        actions: list[AvailableAction],
        resources: dict[str, Any],
        buildings: list[dict],
    ) -> None:
        """Add UPGRADE actions for upgradeable buildings."""
        for b in buildings:
            btype = b.get("building_type", b.get("type", ""))
            level = b.get("level", 0)
            under_construction = b.get("under_construction", False)

            if level >= 3 or under_construction or level == 0:
                continue

            next_level = str(level + 1)
            try:
                from terminus.server.data_loader import get_building_by_id
                bdata = get_building_by_id(btype)
                if bdata:
                    costs = bdata.get("costs", {}).get(next_level, {})
                    if self._can_afford(resources, costs):
                        cost_str = ", ".join(f"{v} {k}" for k, v in costs.items())
                        actions.append(AvailableAction(
                            action_type="UPGRADE",
                            description=f"Upgrade {btype} to level {level + 1}",
                            cost=cost_str,
                            params_hint={"building_type": btype},
                        ))
            except Exception:
                # Fallback: allow upgrade without cost check
                actions.append(AvailableAction(
                    action_type="UPGRADE",
                    description=f"Upgrade {btype} to level {level + 1}",
                    params_hint={"building_type": btype},
                ))

    def _can_afford(self, resources: dict[str, Any], costs: dict[str, Any]) -> bool:
        """Check if player can afford the given costs."""
        for resource, amount in costs.items():
            if resources.get(resource, 0) < amount:
                return False
        return True
