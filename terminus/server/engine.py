"""Core game engine â€” state machine, tick loop, catastrophe scheduling."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Callable, Coroutine

from terminus.config import (
    BASE_PRODUCTION_PER_TICK,
    BUILDING_HEALTH_PER_LEVEL,
    CATASTROPHE_INTERVAL_JITTER,
    CATASTROPHE_MIN_DAMAGE,
    CATASTROPHE_POP_DAMAGE_SCALE,
    CATASTROPHE_RESOLUTION_SECONDS,
    CATASTROPHE_WARNING_SECONDS,
    CONSTRUCTION_SPEED_MULTIPLIER,
    DEMOLISH_REFUND_RATIO,
    FOOD_CONSUMPTION_PER_POP_PER_TICK,
    FOOD_SURPLUS_THRESHOLD_FOR_GROWTH,
    GAME_PRESETS,
    LOCATION_MODIFIERS,
    MAX_BUILDING_LEVEL,
    MORALE_DEATH_PENALTY,
    MORALE_FOOD_SURPLUS_BONUS,
    MORALE_MAX,
    MORALE_MIN,
    MORALE_STARVATION_PENALTY,
    PERSISTENCE_INTERVAL_TICKS,
    POPULATION_GROWTH_RATE,
    REPAIR_COST_PER_HEALTH,
    SERVER_TICK_INTERVAL,
    SETUP_PHASE_SECONDS,
    SPECIALIZATION_MODIFIERS,
    STARTING_MORALE,
    STARTING_POPULATION,
    WAREHOUSE_CAPACITY_BONUS_PER_LEVEL,
    WORKER_ROLES,
)
from terminus.data.loader import (
    get_achievement_by_id,
    get_achievements,
    get_building_by_id,
    get_buildings,
    get_catastrophe_by_id,
    get_catastrophes,
    get_location_by_id,
)
from terminus.server.models import (
    ActionType,
    Building,
    CatastropheEvent,
    CatastropheResult,
    Colony,
    GamePhase,
    GameSettings,
    GameState,
    Location,
    MarketState,
    Player,
    ResourceCapacity,
    Resources,
    Specialization,
    TradeRecord,
    WorkerAllocation,
)

logger = logging.getLogger(__name__)

# Type for event broadcast callback
BroadcastFn = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]
# Type for targeted per-player event callback
PlayerBroadcastFn = Callable[[str, str, dict[str, Any]], Coroutine[Any, Any, None]]


class GameEngine:
    """Manages a single game instance."""

    def __init__(self, settings: GameSettings | None = None):
        self.state = GameState(settings=settings or GameSettings())
        self._apply_preset()
        self._tick_task: asyncio.Task | None = None
        self._broadcast: BroadcastFn | None = None
        self._broadcast_to_player: PlayerBroadcastFn | None = None
        self._setup_deadline: float | None = None
        self._catastrophe_active_until: float | None = None
        self._persist: Any | None = None  # StatePersistence instance (set externally)

    def set_broadcast(self, fn: BroadcastFn, player_fn: PlayerBroadcastFn | None = None) -> None:
        self._broadcast = fn
        self._broadcast_to_player = player_fn

    async def _emit(self, event: str, data: dict[str, Any]) -> None:
        if self._broadcast:
            await self._broadcast(event, data)

    async def _emit_to_player(self, player_id: str, event: str, data: dict[str, Any]) -> None:
        if self._broadcast_to_player:
            await self._broadcast_to_player(player_id, event, data)
        elif self._broadcast:
            # Fallback: broadcast to all (less ideal but functional)
            await self._broadcast(event, data)

    # â”€â”€â”€ Preset Application â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _apply_preset(self) -> None:
        preset = GAME_PRESETS.get(self.state.settings.preset)
        if preset:
            self.state.settings.num_catastrophes = preset["num_catastrophes"]
            self.state.settings.catastrophe_interval_seconds = preset["interval_seconds"]

    # â”€â”€â”€ Player Management â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def add_player(self, player: Player) -> None:
        if self.state.phase not in (GamePhase.LOBBY, GamePhase.PLAYING) or (
            self.state.phase == GamePhase.PLAYING and not self.state.settings.allow_late_join
        ):
            raise ValueError(f"Cannot join in phase: {self.state.phase}")
        if len(self.state.players) >= self.state.settings.max_players:
            raise ValueError("Game is full")
        # Enforce unique player names (case-insensitive)
        lower_name = player.name.strip().lower()
        for existing in self.state.players.values():
            if existing.name.strip().lower() == lower_name:
                raise ValueError(f"Player name '{player.name}' is already taken")
        self.state.players[player.player_id] = player

    def remove_player(self, player_id: str) -> dict[str, Any] | None:
        """Remove or disconnect a player.

        In LOBBY: fully remove from the game and reassign host if needed.
        In PLAYING+: soft-disconnect (colony persists).
        Returns info dict for the broadcast, or None if player not found.
        """
        player = self.state.players.get(player_id)
        if not player:
            return None

        if self.state.phase == GamePhase.LOBBY:
            was_host = player.is_host
            del self.state.players[player_id]
            # Reassign host to next player if the host left
            if was_host and self.state.players:
                next_host = next(iter(self.state.players.values()))
                next_host.is_host = True
            return {
                "player_id": player_id,
                "name": player.name,
                "player_count": len(self.state.players),
                "removed": True,
                "new_host": next(
                    (p.name for p in self.state.players.values() if p.is_host), None
                ) if was_host and self.state.players else None,
            }
        else:
            player.connected = False
            return {
                "player_id": player_id,
                "name": player.name,
                "player_count": len(self.state.players),
                "removed": False,
            }

    def set_ready(self, player_id: str, ready: bool) -> None:
        if player_id in self.state.players:
            self.state.players[player_id].ready = ready

    # â”€â”€â”€ Phase Transitions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def start_game(self, host_id: str) -> None:
        player = self.state.players.get(host_id)
        if not player or not player.is_host:
            raise ValueError("Only the host can start the game")
        if self.state.phase != GamePhase.LOBBY:
            raise ValueError("Game already started")

        self.state.phase = GamePhase.SETUP
        self._setup_deadline = time.time() + SETUP_PHASE_SECONDS
        await self._emit("game_phase_changed", {"phase": "setup", "deadline_seconds": SETUP_PHASE_SECONDS})

    async def submit_setup(self, player_id: str, location: Location, specialization: Specialization) -> None:
        if self.state.phase != GamePhase.SETUP:
            raise ValueError("Not in setup phase")
        player = self.state.players.get(player_id)
        if not player:
            raise ValueError("Player not found")

        # Initialize colony with chosen location and spec
        loc_data = get_location_by_id(location.value)
        starting_res = loc_data["starting_resources"] if loc_data else {}

        colony = Colony(
            name=player.name + "'s Colony",
            location=location,
            specialization=specialization,
            resources=Resources(
                food=starting_res.get("food", 100),
                materials=starting_res.get("materials", 80),
                knowledge=starting_res.get("knowledge", 10),
                gold=starting_res.get("gold", 50),
            ),
            population=STARTING_POPULATION,
            morale=STARTING_MORALE,
        )
        # Default worker allocation: spread evenly with surplus to farming
        base = STARTING_POPULATION // 6
        remainder = STARTING_POPULATION - (base * 6)
        colony.workers = WorkerAllocation(
            farming=base + remainder,
            mining=base,
            research=base,
            construction=base,
            defense=base,
            medicine=base,
        )
        player.colony = colony
        player.ready = True

    async def check_setup_complete(self) -> bool:
        """Check if all players have submitted setup. If so, start playing."""
        all_ready = all(p.colony is not None for p in self.state.players.values() if p.connected)
        timed_out = self._setup_deadline and time.time() > self._setup_deadline

        if all_ready or timed_out:
            # Auto-assign for players who haven't chosen
            for p in self.state.players.values():
                if p.connected and p.colony is None:
                    await self.submit_setup(
                        p.player_id,
                        random.choice(list(Location)),
                        random.choice(list(Specialization)),
                    )
            await self._start_playing()
            return True
        return False

    async def _start_playing(self) -> None:
        self.state.phase = GamePhase.PLAYING
        self.state.game_start_time = time.time()
        self._schedule_catastrophes()
        self._init_market()
        await self._emit("game_phase_changed", {"phase": "playing"})
        self._start_tick_loop()

    # â”€â”€â”€ Catastrophe Scheduling â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _schedule_catastrophes(self) -> None:
        """Select and schedule catastrophes for this game."""
        all_cats = get_catastrophes()
        num = self.state.settings.num_catastrophes
        interval = self.state.settings.catastrophe_interval_seconds

        # Select catastrophes ensuring category diversity
        selected = self._select_balanced_catastrophes(all_cats, num)

        schedule = []
        for i, cat in enumerate(selected):
            jitter = random.randint(-CATASTROPHE_INTERVAL_JITTER, CATASTROPHE_INTERVAL_JITTER)
            scheduled_time = interval * (i + 1) + jitter
            schedule.append(CatastropheEvent(
                catastrophe_id=cat["id"],
                scheduled_time=scheduled_time,
            ))

        self.state.catastrophe_schedule = schedule
        logger.info(f"Scheduled {len(schedule)} catastrophes: {[c.catastrophe_id for c in schedule]}")

    def _select_balanced_catastrophes(self, all_cats: list[dict], num: int) -> list[dict]:
        """Select catastrophes with category diversity and progressive severity."""
        by_category: dict[str, list[dict]] = {}
        for cat in all_cats:
            by_category.setdefault(cat["category"], []).append(cat)

        selected = []
        categories = list(by_category.keys())
        random.shuffle(categories)

        # Pick from each category in round-robin, respecting severity progression
        severity_order = [1, 1, 2, 2, 3, 3]  # early=easier, later=harder
        cat_idx = 0
        for i in range(num):
            target_severity = severity_order[i] if i < len(severity_order) else 2
            cat_name = categories[cat_idx % len(categories)]
            candidates = [c for c in by_category[cat_name] if c["severity"] == target_severity and c not in selected]
            if not candidates:
                candidates = [c for c in by_category[cat_name] if c not in selected]
            if not candidates:
                # Fallback: any remaining catastrophe
                remaining = [c for c in all_cats if c not in selected]
                candidates = remaining

            if candidates:
                selected.append(random.choice(candidates))
            cat_idx += 1

        return selected[:num]

    # â”€â”€â”€ Market â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _init_market(self) -> None:
        from terminus.config import BASE_MARKET_PRICES, MARKET_STOCK_PER_RESOURCE
        self.state.market = MarketState(
            prices={k: v for k, v in BASE_MARKET_PRICES.items()},
            stock={k: MARKET_STOCK_PER_RESOURCE for k in BASE_MARKET_PRICES},
        )

    # â”€â”€â”€ Tick Loop â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _start_tick_loop(self) -> None:
        self._tick_task = asyncio.create_task(self._tick_loop())

    async def _tick_loop(self) -> None:
        try:
            while self.state.phase in (GamePhase.PLAYING, GamePhase.CATASTROPHE):
                tick_start = time.monotonic()
                await self._tick()
                elapsed = time.monotonic() - tick_start
                sleep_time = max(0, SERVER_TICK_INTERVAL - elapsed)
                await asyncio.sleep(sleep_time)
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        """Stop the engine: cancel tick loop and save final state."""
        if self._tick_task and not self._tick_task.done():
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass
            self._tick_task = None
        # Final persistence save
        if self._persist:
            try:
                await self._persist.save_snapshot(
                    self.state.model_dump_json(), self.state.elapsed_ticks
                )
                await self._persist.close()
            except Exception:
                logger.warning("Failed to save final snapshot", exc_info=True)

    async def _tick(self) -> None:
        if self.state.phase == GamePhase.CATASTROPHE:
            # Check if catastrophe resolution time is over
            if self._catastrophe_active_until and time.time() > self._catastrophe_active_until:
                await self._end_catastrophe()
            return

        self.state.elapsed_ticks += 1
        elapsed_seconds = time.time() - (self.state.game_start_time or time.time())

        # Process each player's colony
        for player in self.state.players.values():
            if player.colony and player.connected:
                self._process_colony_tick(player.colony)
                self._check_achievements(player.colony, player.player_id)

        # Check catastrophe timing
        await self._check_catastrophe_timer(elapsed_seconds)

        # Expire stale P2P trade offers
        expired_ids = [
            oid for oid, offer in self.state.pending_trades.items()
            if self.state.elapsed_ticks > offer.expires_tick
        ]
        for oid in expired_ids:
            del self.state.pending_trades[oid]

        # Broadcast state update every tick â€” per-player colony state
        for player_id, player in self.state.players.items():
            if player.connected and player.colony:
                await self._emit_to_player(player_id, "state_update", {
                    "tick": self.state.elapsed_ticks,
                    "colony": player.colony.model_dump(),
                    "market_prices": self.state.market.prices,
                })

        # Periodic persistence save
        if self._persist and self.state.elapsed_ticks % PERSISTENCE_INTERVAL_TICKS == 0:
            try:
                await self._persist.save_snapshot(
                    self.state.model_dump_json(), self.state.elapsed_ticks
                )
            except Exception:
                logger.warning("Failed to save game snapshot", exc_info=True)

    def _process_colony_tick(self, colony: Colony) -> None:
        """Process one tick of colony resource production and consumption."""
        if colony.location is None:
            return

        loc_mods = LOCATION_MODIFIERS.get(colony.location.value, {})
        spec_mods = SPECIALIZATION_MODIFIERS.get(colony.specialization.value, {}) if colony.specialization else {}
        pop = colony.population
        workers = colony.workers

        # Food production
        if pop > 0:
            farm_ratio = workers.farming / pop
            food_mod = loc_mods.get("food", 1.0) + spec_mods.get("food", 0.0)
            food_prod = BASE_PRODUCTION_PER_TICK["food"] * farm_ratio * food_mod * colony.morale
            # Building bonuses
            food_prod *= (1 + self._get_building_bonus(colony, "food_production_bonus"))
            colony.resources.food = min(colony.resources.food + food_prod, colony.capacity.food)

            # Materials production
            mine_ratio = workers.mining / pop
            mat_mod = loc_mods.get("materials", 1.0) + spec_mods.get("materials", 0.0)
            mat_prod = BASE_PRODUCTION_PER_TICK["materials"] * mine_ratio * mat_mod * colony.morale
            mat_prod *= (1 + self._get_building_bonus(colony, "materials_production_bonus"))
            colony.resources.materials = min(colony.resources.materials + mat_prod, colony.capacity.materials)

            # Knowledge production
            research_ratio = workers.research / pop
            know_mod = loc_mods.get("knowledge", 1.0) + spec_mods.get("knowledge", 0.0)
            know_prod = BASE_PRODUCTION_PER_TICK["knowledge"] * research_ratio * know_mod * colony.morale
            know_prod *= (1 + self._get_building_bonus(colony, "knowledge_production_bonus"))
            colony.resources.knowledge = min(colony.resources.knowledge + know_prod, colony.capacity.knowledge)

            # Gold production
            gold_mod = loc_mods.get("gold", 1.0) + spec_mods.get("gold", 0.0)
            gold_prod = BASE_PRODUCTION_PER_TICK["gold"] * (farm_ratio * 0.2 + mine_ratio * 0.3 + research_ratio * 0.2 + 0.3) * gold_mod * colony.morale
            gold_prod *= (1 + self._get_building_bonus(colony, "gold_production_bonus"))
            colony.resources.gold = min(colony.resources.gold + gold_prod, colony.capacity.gold)

        # Food consumption
        food_consumed = pop * FOOD_CONSUMPTION_PER_POP_PER_TICK
        colony.resources.food -= food_consumed

        # Starvation
        if colony.resources.food <= 0:
            colony.resources.food = 0
            colony.population = max(0, colony.population - 1)
            colony.morale = max(MORALE_MIN, colony.morale - MORALE_STARVATION_PENALTY)
        elif colony.resources.food > FOOD_SURPLUS_THRESHOLD_FOR_GROWTH:
            # Population growth
            if colony.population < colony.max_population:
                colony.population += int(POPULATION_GROWTH_RATE)
            colony.morale = min(MORALE_MAX, colony.morale + MORALE_FOOD_SURPLUS_BONUS)

        # Track peak population
        if colony.population > colony.peak_population:
            colony.peak_population = colony.population

        # Construction progress
        for building in colony.buildings:
            if building.under_construction and pop > 0:
                construct_ratio = workers.construction / pop
                progress = construct_ratio * CONSTRUCTION_SPEED_MULTIPLIER
                building.construction_progress += progress
                if building.construction_progress >= building.construction_target:
                    building.under_construction = False
                    building.construction_progress = building.construction_target
                    building.health = building.max_health
                    colony.buildings_built += 1
                    self._update_colony_capacity(colony)

    def _check_achievements(self, colony: Colony, player_id: str) -> None:
        """Check and award achievements for a colony."""
        earned = colony.achievements

        # Builder: 5+ completed buildings
        if "builder" not in earned:
            completed = sum(1 for b in colony.buildings if b.level > 0 and not b.under_construction)
            if completed >= 5:
                earned.append("builder")

        # Scholar: Library at level 3
        if "scholar" not in earned:
            lib = next((b for b in colony.buildings if b.building_type == "library" and b.level >= 3 and not b.under_construction), None)
            if lib:
                earned.append("scholar")

        # Populous: 200+ population
        if "populous" not in earned:
            if colony.population >= 200:
                earned.append("populous")

        # Hoarder: any resource at max capacity
        if "hoarder" not in earned:
            for res in ("food", "materials", "knowledge", "gold"):
                val = getattr(colony.resources, res)
                cap = getattr(colony.capacity, res)
                if cap > 0 and val >= cap:
                    earned.append("hoarder")
                    break

        # Fortified: barracks and wall both at level 2+
        if "fortified" not in earned:
            defense_buildings = {"barracks", "wall"}
            defense_levels = {}
            for b in colony.buildings:
                if b.building_type in defense_buildings and not b.under_construction:
                    defense_levels[b.building_type] = b.level
            if all(defense_levels.get(bt, 0) >= 2 for bt in defense_buildings):
                earned.append("fortified")

        # Trader: 10+ trades by this player
        if "trader" not in earned:
            trade_count = sum(1 for t in self.state.trade_history if t.player_id == player_id)
            if trade_count >= 10:
                earned.append("trader")

    def _check_catastrophe_achievements(self, player_id: str, result: CatastropheResult) -> None:
        """Check achievements that depend on catastrophe outcomes."""
        player = self.state.players.get(player_id)
        if not player or not player.colony:
            return
        earned = player.colony.achievements

        # Survivor: zero population loss in a catastrophe
        if "survivor" not in earned and result.population_lost == 0:
            earned.append("survivor")

        # Untouched: no building damage in a catastrophe
        if "untouched" not in earned and len(result.buildings_damaged) == 0:
            earned.append("untouched")

    def _get_building_bonus(self, colony: Colony, bonus_key: str) -> float:
        """Sum up all building bonuses of a given type."""
        total = 0.0
        for building in colony.buildings:
            if building.under_construction or building.level == 0:
                continue
            b_data = get_building_by_id(building.building_type)
            if b_data:
                level_effects = b_data["effects"].get(str(building.level), {})
                total += level_effects.get(bonus_key, 0)
        return total

    def get_production_rates(self, colony: Colony) -> dict[str, float]:
        """Calculate current per-tick production rates for a colony (read-only)."""
        if colony.location is None or colony.population == 0:
            return {"food": 0, "materials": 0, "knowledge": 0, "gold": 0}

        loc_mods = LOCATION_MODIFIERS.get(colony.location.value, {})
        spec_mods = SPECIALIZATION_MODIFIERS.get(colony.specialization.value, {}) if colony.specialization else {}
        pop = colony.population
        workers = colony.workers

        farm_ratio = workers.farming / pop
        food_mod = loc_mods.get("food", 1.0) + spec_mods.get("food", 0.0)
        food_rate = BASE_PRODUCTION_PER_TICK["food"] * farm_ratio * food_mod * colony.morale
        food_rate *= (1 + self._get_building_bonus(colony, "food_production_bonus"))
        food_rate -= pop * FOOD_CONSUMPTION_PER_POP_PER_TICK

        mine_ratio = workers.mining / pop
        mat_mod = loc_mods.get("materials", 1.0) + spec_mods.get("materials", 0.0)
        mat_rate = BASE_PRODUCTION_PER_TICK["materials"] * mine_ratio * mat_mod * colony.morale
        mat_rate *= (1 + self._get_building_bonus(colony, "materials_production_bonus"))

        research_ratio = workers.research / pop
        know_mod = loc_mods.get("knowledge", 1.0) + spec_mods.get("knowledge", 0.0)
        know_rate = BASE_PRODUCTION_PER_TICK["knowledge"] * research_ratio * know_mod * colony.morale
        know_rate *= (1 + self._get_building_bonus(colony, "knowledge_production_bonus"))

        gold_mod = loc_mods.get("gold", 1.0) + spec_mods.get("gold", 0.0)
        gold_rate = BASE_PRODUCTION_PER_TICK["gold"] * (farm_ratio * 0.2 + mine_ratio * 0.3 + research_ratio * 0.2 + 0.3) * gold_mod * colony.morale
        gold_rate *= (1 + self._get_building_bonus(colony, "gold_production_bonus"))

        return {
            "food": round(food_rate, 2),
            "materials": round(mat_rate, 2),
            "knowledge": round(know_rate, 2),
            "gold": round(gold_rate, 2),
        }

    def _update_colony_capacity(self, colony: Colony) -> None:
        """Recalculate resource capacity based on buildings."""
        from terminus.config import BASE_RESOURCE_CAPACITY, HOUSING_POP_BONUS_PER_LEVEL, MAX_POPULATION_BASE
        colony.capacity = ResourceCapacity(**BASE_RESOURCE_CAPACITY)

        for building in colony.buildings:
            if building.under_construction or building.level == 0:
                continue
            if building.building_type == "warehouse":
                for res, bonus in WAREHOUSE_CAPACITY_BONUS_PER_LEVEL.items():
                    current = getattr(colony.capacity, res)
                    setattr(colony.capacity, res, current + bonus * building.level)
            elif building.building_type == "housing":
                colony.max_population = MAX_POPULATION_BASE + HOUSING_POP_BONUS_PER_LEVEL * building.level

    # â”€â”€â”€ Catastrophe Execution â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def _check_catastrophe_timer(self, elapsed_seconds: float) -> None:
        idx = self.state.current_catastrophe_index
        if idx >= len(self.state.catastrophe_schedule):
            # All catastrophes done â€” end game
            await self._end_game()
            return

        event = self.state.catastrophe_schedule[idx]
        time_until = event.scheduled_time - elapsed_seconds

        if time_until <= 0:
            await self._trigger_catastrophe(event)
        elif time_until <= CATASTROPHE_WARNING_SECONDS and not hasattr(event, "_warned"):
            # Per-player warnings with watchtower hints
            cat_data = get_catastrophe_by_id(event.catastrophe_id)
            for player_id, player in self.state.players.items():
                warning_data: dict[str, Any] = {
                    "seconds_until": time_until,
                    "index": idx,
                    "total": len(self.state.catastrophe_schedule),
                }
                # Add watchtower hints based on building level
                if player.colony and cat_data:
                    wt_level = 0
                    for b in player.colony.buildings:
                        if b.building_type == "watchtower" and b.level > wt_level:
                            wt_level = b.level
                    if wt_level >= 1:
                        warning_data["hint_category"] = cat_data.get("category", "")
                    if wt_level >= 2:
                        warning_data["hint_type"] = cat_data.get("name", "")
                    if wt_level >= 3:
                        warning_data["hint_severity"] = cat_data.get("severity", 0)
                    # Build a human-readable hint_text
                    if wt_level >= 3:
                        warning_data["hint_text"] = (
                            f"Watchtower warns: {cat_data['name']} ({cat_data.get('category','')}) "
                            f"severity {cat_data.get('severity',0)} in {int(time_until)}s!"
                        )
                    elif wt_level >= 2:
                        warning_data["hint_text"] = (
                            f"Watchtower warns: {cat_data['name']} incoming in {int(time_until)}s!"
                        )
                    elif wt_level >= 1:
                        warning_data["hint_text"] = (
                            f"Watchtower warns: {cat_data.get('category','')} catastrophe in {int(time_until)}s!"
                        )
                await self._emit_to_player(player_id, "catastrophe_warning", warning_data)
            event._warned = True  # type: ignore

    async def _trigger_catastrophe(self, event: CatastropheEvent) -> None:
        self.state.phase = GamePhase.CATASTROPHE
        self._catastrophe_active_until = time.time() + CATASTROPHE_RESOLUTION_SECONDS

        cat_data = get_catastrophe_by_id(event.catastrophe_id)
        if not cat_data:
            await self._end_catastrophe()
            return

        # Send per-player catastrophe_started with location-specific flavor
        location_flavors = cat_data.get("location_flavor", {})
        for player_id, player in self.state.players.items():
            loc = player.colony.location.value if player.colony and player.colony.location else None
            flavor = location_flavors.get(loc, cat_data.get("flavor_text", "")) if loc else cat_data.get("flavor_text", "")
            await self._emit_to_player(player_id, "catastrophe_started", {
                "id": cat_data["id"],
                "name": cat_data["name"],
                "description": cat_data["description"],
                "flavor_text": flavor,
            })

        # Calculate damage for each player
        for player in self.state.players.values():
            if player.colony:
                result = self._calculate_catastrophe_damage(player.colony, cat_data)
                self._apply_catastrophe_damage(player.colony, result, cat_data)
                event.results[player.player_id] = result
                player.colony.catastrophes_survived += 1
                self._check_catastrophe_achievements(player.player_id, result)

        event.resolved = True

        # Compute averages for comparison
        all_results = event.results
        avg_pop_lost = 0.0
        avg_food_lost = 0.0
        if all_results:
            avg_pop_lost = sum(r.population_lost for r in all_results.values()) / len(all_results)
            avg_food_lost = sum(
                r.resources_lost.get("food", 0) for r in all_results.values()
            ) / len(all_results)

        # Send individualized results per player (own result + averages)
        for pid, r in all_results.items():
            player_data = r.model_dump()
            player_data["avg_population_lost"] = round(avg_pop_lost, 1)
            player_data["avg_food_lost"] = round(avg_food_lost, 1)
            await self._emit_to_player(pid, "catastrophe_results", {
                "catastrophe": cat_data["name"],
                "results": {pid: player_data},
            })

    def _calculate_catastrophe_damage(self, colony: Colony, cat_data: dict) -> CatastropheResult:
        """Calculate how much damage a catastrophe deals to a colony."""
        result = CatastropheResult(player_id="")
        base_damage = cat_data["base_damage"]

        # Location vulnerability
        vuln = cat_data.get("location_vulnerability", {})
        loc_factor = vuln.get(colony.location.value, 1.0) if colony.location else 1.0

        # Building mitigation
        mit_building = cat_data.get("mitigation_building")
        mit_factor = cat_data.get("mitigation_factor", 0)
        building_level = 0
        if mit_building:
            for b in colony.buildings:
                if b.building_type == mit_building and not b.under_construction:
                    building_level = b.level
                    break

        mitigation = mit_factor * (building_level / MAX_BUILDING_LEVEL) if building_level > 0 else 0

        # Worker mitigation
        worker_mit = cat_data.get("worker_mitigation")
        if worker_mit and colony.population > 0:
            role = worker_mit["role"]
            role_count = getattr(colony.workers, role, 0)
            worker_mitigation = worker_mit["factor"] * (role_count / colony.population)
            mitigation += worker_mitigation

        # Final damage multiplier (never below minimum)
        damage_mult = max(CATASTROPHE_MIN_DAMAGE, (1 - mitigation) * loc_factor)

        # Apply primary effect
        primary = cat_data["primary_effect"]
        if primary == "kill_population":
            result.population_lost = int(base_damage * damage_mult * CATASTROPHE_POP_DAMAGE_SCALE)
        elif primary == "destroy_resource":
            target = cat_data.get("resource_target", "food")
            result.resources_lost[target] = base_damage * damage_mult
        elif primary == "damage_buildings":
            # Damage spread across buildings
            result.buildings_damaged = [b.building_type for b in colony.buildings if not b.under_construction and b.level > 0]
        elif primary == "steal_resources":
            targets = cat_data.get("resource_targets", ["gold"])
            per_resource = (base_damage * damage_mult) / len(targets)
            for t in targets:
                result.resources_lost[t] = per_resource

        # Secondary effects
        for effect in cat_data.get("secondary_effects", []):
            if effect["type"] == "kill_population":
                result.population_lost += int(effect["amount"] * damage_mult * CATASTROPHE_POP_DAMAGE_SCALE)
            elif effect["type"] == "reduce_morale":
                result.morale_change -= effect["amount"]
            elif effect["type"] == "destroy_resource":
                res = effect.get("resource", "food")
                result.resources_lost[res] = result.resources_lost.get(res, 0) + effect.get("amount", 0) * damage_mult

        if building_level > 0 and mit_building:
            result.mitigated_by.append(mit_building)

        return result

    def _apply_catastrophe_damage(self, colony: Colony, result: CatastropheResult, cat_data: dict) -> None:
        """Apply calculated damage to the colony."""
        # Population loss
        colony.population = max(0, colony.population - result.population_lost)
        colony.morale = max(MORALE_MIN, colony.morale - abs(result.morale_change))
        colony.morale -= MORALE_DEATH_PENALTY * result.population_lost

        # Resource loss
        for res, amount in result.resources_lost.items():
            current = getattr(colony.resources, res, 0)
            setattr(colony.resources, res, max(0, current - amount))

        # Building damage
        if cat_data["primary_effect"] == "damage_buildings":
            damage_per_building = cat_data["base_damage"] / max(1, len(result.buildings_damaged))
            for building in colony.buildings:
                if building.building_type in result.buildings_damaged:
                    building.health = max(0, building.health - damage_per_building)
                    if building.health <= 0:
                        building.level = 0

        # Clamp morale
        colony.morale = max(MORALE_MIN, min(MORALE_MAX, colony.morale))

        # Re-adjust workers if population dropped below allocation
        total_allocated = colony.workers.total
        if total_allocated > colony.population:
            # Proportionally reduce all allocations
            if total_allocated > 0:
                ratio = colony.population / total_allocated
                colony.workers = WorkerAllocation(
                    farming=max(1, int(colony.workers.farming * ratio)),
                    mining=int(colony.workers.mining * ratio),
                    research=int(colony.workers.research * ratio),
                    construction=int(colony.workers.construction * ratio),
                    defense=int(colony.workers.defense * ratio),
                    medicine=int(colony.workers.medicine * ratio),
                )

    async def _end_catastrophe(self) -> None:
        # Apply catastrophe-driven price shifts before refreshing market
        event = self.state.catastrophe_schedule[self.state.current_catastrophe_index]
        self._apply_catastrophe_price_shift(event)

        # Snapshot scores after this catastrophe round
        snapshot = self._calculate_scores()
        self.state.score_history.append({
            "round": self.state.current_catastrophe_index + 1,
            "scores": snapshot,
        })

        self.state.current_catastrophe_index += 1
        self._catastrophe_active_until = None

        if self.state.current_catastrophe_index >= len(self.state.catastrophe_schedule):
            await self._end_game()
        else:
            self.state.phase = GamePhase.PLAYING
            await self._refresh_market()
            await self._emit("game_phase_changed", {"phase": "playing"})

    def _apply_catastrophe_price_shift(self, event: CatastropheEvent) -> None:
        """Shift market prices based on catastrophe type (supply/demand shock)."""
        cat_data = get_catastrophe_by_id(event.catastrophe_id)
        if not cat_data:
            return

        PRICE_SHOCK = {
            "population": {"food": 0.30},             # plague/famine â†’ food demand spikes
            "resource": {"food": 0.40, "materials": 0.15},  # drought/famine â†’ food scarce
            "infrastructure": {"materials": 0.35},     # earthquake â†’ materials demand spikes
            "economic": {"gold": -0.10, "materials": 0.20},  # raiders â†’ gold drops, materials scarce
        }

        category = cat_data.get("category", "")
        shifts = PRICE_SHOCK.get(category, {})

        for resource, shift_pct in shifts.items():
            if resource in self.state.market.prices:
                current = self.state.market.prices[resource]
                self.state.market.prices[resource] = round(current * (1 + shift_pct), 2)

    # â”€â”€â”€ Market Operations â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def _refresh_market(self) -> None:
        from terminus.config import BASE_MARKET_PRICES, MARKET_PRICE_VOLATILITY, MARKET_STOCK_PER_RESOURCE
        old_prices = dict(self.state.market.prices)
        new_prices = {}
        for resource, base_price in BASE_MARKET_PRICES.items():
            fluctuation = random.uniform(-MARKET_PRICE_VOLATILITY, MARKET_PRICE_VOLATILITY)
            new_prices[resource] = round(base_price * (1 + fluctuation), 2)
        self.state.market.prices = new_prices
        self.state.market.stock = {k: MARKET_STOCK_PER_RESOURCE for k in new_prices}
        self.state.market.price_history.append(new_prices.copy())
        # Compute price changes vs previous round
        price_changes = {}
        if old_prices:
            for resource, new_p in new_prices.items():
                old_p = old_prices.get(resource, new_p)
                if old_p > 0:
                    price_changes[resource] = round((new_p - old_p) / old_p * 100, 1)
                else:
                    price_changes[resource] = 0.0
        # Broadcast market update to all clients
        await self._emit("market_update", {
            "prices": new_prices,
            "stock": self.state.market.stock,
            "price_changes": price_changes,
        })

    # â”€â”€â”€ Game End â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def _end_game(self) -> None:
        self.state.phase = GamePhase.SCORING
        scores = self._calculate_scores()
        await self._emit("game_over", {"scores": scores})
        self.state.phase = GamePhase.FINISHED
        if self._tick_task:
            self._tick_task.cancel()

    def _calculate_scores(self) -> list[dict[str, Any]]:
        from terminus.config import SCORE_WEIGHTS
        scores = []
        for player in self.state.players.values():
            if not player.colony:
                continue
            c = player.colony
            base_score = (
                c.population * SCORE_WEIGHTS["population"]
                + c.resources.food * SCORE_WEIGHTS["food"]
                + c.resources.materials * SCORE_WEIGHTS["materials"]
                + c.resources.knowledge * SCORE_WEIGHTS["knowledge"]
                + c.resources.gold * SCORE_WEIGHTS["gold"]
                + c.morale * SCORE_WEIGHTS["morale"]
                + sum(b.health for b in c.buildings) * SCORE_WEIGHTS["building_health"]
            )
            # Achievement bonus points
            achievement_bonus = 0.0
            for ach_id in c.achievements:
                ach_data = get_achievement_by_id(ach_id)
                if ach_data:
                    achievement_bonus += ach_data["bonus_points"]

            score = base_score + achievement_bonus
            c.score = score
            scores.append({
                "player_id": player.player_id,
                "name": player.name,
                "score": round(score, 1),
                "population": c.population,
                "morale": round(c.morale, 2),
                "achievements": list(c.achievements),
                "buildings_built": c.buildings_built,
                "trades_completed": c.trades_completed,
                "total_trade_volume": round(c.total_trade_volume, 1),
                "catastrophes_survived": c.catastrophes_survived,
                "peak_population": c.peak_population,
            })
        scores.sort(key=lambda x: x["score"], reverse=True)

        # Compute averages and deltas
        if scores:
            avg_score = sum(s["score"] for s in scores) / len(scores)
            avg_pop = sum(s["population"] for s in scores) / len(scores)
            avg_morale = sum(s["morale"] for s in scores) / len(scores)
            for s in scores:
                s["avg_score"] = round(avg_score, 1)
                s["avg_population"] = round(avg_pop, 1)
                s["avg_morale"] = round(avg_morale, 2)
                if avg_score > 0:
                    s["delta_vs_avg"] = round((s["score"] - avg_score) / avg_score * 100, 1)
                else:
                    s["delta_vs_avg"] = 0.0

        return scores

    # â”€â”€â”€ Player Actions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def handle_action(self, player_id: str, action_type: ActionType, payload: dict[str, Any]) -> dict[str, Any]:
        if self.state.phase != GamePhase.PLAYING:
            raise ValueError("Actions only allowed during playing phase")

        player = self.state.players.get(player_id)
        if not player or not player.colony:
            raise ValueError("Player or colony not found")

        colony = player.colony

        if action_type == ActionType.BUILD:
            result = self._action_build(colony, payload)
        elif action_type == ActionType.UPGRADE:
            result = self._action_upgrade(colony, payload)
        elif action_type == ActionType.ALLOCATE_WORKERS:
            result = self._action_allocate(colony, payload)
        elif action_type == ActionType.TRADE_BUY:
            result = self._action_trade_buy(colony, payload, player_id, player.name)
        elif action_type == ActionType.TRADE_SELL:
            result = self._action_trade_sell(colony, payload, player_id, player.name)
        elif action_type == ActionType.DEMOLISH:
            result = self._action_demolish(colony, payload)
        elif action_type == ActionType.REPAIR:
            result = self._action_repair(colony, payload)
        elif action_type == ActionType.TRADE_OFFER:
            result = self._action_trade_offer(colony, payload, player_id, player.name)
        elif action_type == ActionType.TRADE_ACCEPT:
            result = self._action_trade_accept(colony, payload, player_id)
        elif action_type == ActionType.TRADE_DECLINE:
            result = self._action_trade_decline(payload, player_id)
        else:
            raise ValueError(f"Unknown action: {action_type}")

        # Log action to persistence
        if self._persist:
            try:
                await self._persist.log_action(
                    tick=self.state.elapsed_ticks,
                    player_id=player_id,
                    action_type=action_type.value,
                    params=payload,
                    result=result,
                )
            except Exception:
                logger.warning("Failed to log action", exc_info=True)

        return result

    def _action_build(self, colony: Colony, payload: dict) -> dict:
        building_type = payload.get("building_type")
        b_data = get_building_by_id(building_type)
        if not b_data:
            raise ValueError(f"Unknown building: {building_type}")

        # Check if already exists
        existing = next((b for b in colony.buildings if b.building_type == building_type), None)
        if existing and existing.level > 0:
            raise ValueError(f"Building already exists. Use upgrade instead.")

        # Check cost
        costs = b_data["costs"]["1"]
        for resource, amount in costs.items():
            if getattr(colony.resources, resource, 0) < amount:
                raise ValueError(f"Insufficient {resource} (need {amount})")

        # Deduct cost
        for resource, amount in costs.items():
            current = getattr(colony.resources, resource)
            setattr(colony.resources, resource, current - amount)

        # Create building
        build_time = b_data["build_time_ticks"]["1"]
        if existing:
            existing.level = 1
            existing.under_construction = True
            existing.construction_progress = 0
            existing.construction_target = build_time
            existing.max_health = BUILDING_HEALTH_PER_LEVEL
            existing.health = 0
        else:
            colony.buildings.append(Building(
                building_type=building_type,
                level=1,
                health=0,
                max_health=BUILDING_HEALTH_PER_LEVEL,
                under_construction=True,
                construction_progress=0,
                construction_target=build_time,
            ))

        return {"status": "construction_started", "building": building_type, "ticks": build_time}

    def _action_upgrade(self, colony: Colony, payload: dict) -> dict:
        building_type = payload.get("building_type")
        b_data = get_building_by_id(building_type)
        if not b_data:
            raise ValueError(f"Unknown building: {building_type}")

        existing = next((b for b in colony.buildings if b.building_type == building_type), None)
        if not existing or existing.level == 0:
            raise ValueError("Building not found or not built")
        if existing.under_construction:
            raise ValueError("Building is under construction")
        if existing.level >= MAX_BUILDING_LEVEL:
            raise ValueError("Building at max level")

        next_level = existing.level + 1
        costs = b_data["costs"][str(next_level)]
        for resource, amount in costs.items():
            if getattr(colony.resources, resource, 0) < amount:
                raise ValueError(f"Insufficient {resource} (need {amount})")

        for resource, amount in costs.items():
            current = getattr(colony.resources, resource)
            setattr(colony.resources, resource, current - amount)

        build_time = b_data["build_time_ticks"][str(next_level)]
        existing.level = next_level
        existing.under_construction = True
        existing.construction_progress = 0
        existing.construction_target = build_time
        existing.max_health = BUILDING_HEALTH_PER_LEVEL * next_level

        return {"status": "upgrade_started", "building": building_type, "level": next_level}

    def _action_allocate(self, colony: Colony, payload: dict) -> dict:
        allocation = payload.get("allocation", {})
        total = sum(allocation.values())
        if total != colony.population:
            raise ValueError(f"Allocation total ({total}) must equal population ({colony.population})")
        for role in WORKER_ROLES:
            if role not in allocation:
                raise ValueError(f"Missing role: {role}")
            if allocation[role] < 0:
                raise ValueError(f"Negative allocation for {role}")

        colony.workers = WorkerAllocation(**allocation)
        return {"status": "workers_allocated", "allocation": allocation}

    def _action_trade_buy(self, colony: Colony, payload: dict, player_id: str = "", player_name: str = "") -> dict:
        from terminus.config import MARKET_SELL_SPREAD, TRADE_SPEC_BUY_DISCOUNT
        resource = payload.get("resource")
        quantity = payload.get("quantity", 0)

        if resource not in self.state.market.prices:
            raise ValueError(f"Cannot buy {resource}")
        if self.state.market.stock.get(resource, 0) < quantity:
            raise ValueError("Insufficient market stock")

        price = self.state.market.prices[resource]
        # Apply specialization discount
        if colony.specialization == Specialization.TRADE:
            price *= TRADE_SPEC_BUY_DISCOUNT

        total_cost = price * quantity
        if colony.resources.gold < total_cost:
            raise ValueError(f"Insufficient gold (need {total_cost:.1f})")

        colony.resources.gold -= total_cost
        current = getattr(colony.resources, resource)
        cap = getattr(colony.capacity, resource)
        setattr(colony.resources, resource, min(current + quantity, cap))
        self.state.market.stock[resource] -= quantity

        self.state.trade_history.append(TradeRecord(
            tick=self.state.elapsed_ticks,
            player_id=player_id,
            player_name=player_name,
            action="buy",
            resource=resource,
            quantity=quantity,
            price_per_unit=price,
            total=round(total_cost, 1),
        ))
        colony.trades_completed += 1
        colony.total_trade_volume += round(total_cost, 1)

        return {"status": "bought", "resource": resource, "quantity": quantity, "cost": round(total_cost, 1)}

    def _action_trade_sell(self, colony: Colony, payload: dict, player_id: str = "", player_name: str = "") -> dict:
        from terminus.config import MARKET_SELL_SPREAD, TRADE_SPEC_SELL_BONUS
        resource = payload.get("resource")
        quantity = payload.get("quantity", 0)

        if resource not in self.state.market.prices:
            raise ValueError(f"Cannot sell {resource}")
        current = getattr(colony.resources, resource, 0)
        if current < quantity:
            raise ValueError(f"Insufficient {resource}")

        price = self.state.market.prices[resource]
        spread = TRADE_SPEC_SELL_BONUS if colony.specialization == Specialization.TRADE else MARKET_SELL_SPREAD
        revenue = price * spread * quantity

        setattr(colony.resources, resource, current - quantity)
        colony.resources.gold = min(colony.resources.gold + revenue, colony.capacity.gold)

        self.state.trade_history.append(TradeRecord(
            tick=self.state.elapsed_ticks,
            player_id=player_id,
            player_name=player_name,
            action="sell",
            resource=resource,
            quantity=quantity,
            price_per_unit=price,
            total=round(revenue, 1),
        ))
        colony.trades_completed += 1
        colony.total_trade_volume += round(revenue, 1)

        return {"status": "sold", "resource": resource, "quantity": quantity, "revenue": round(revenue, 1)}

    # ─── Player-to-Player Trading ────────────────────────────────────────────

    def _action_trade_offer(self, colony: Colony, payload: dict, player_id: str, player_name: str) -> dict:
        """Create a trade offer to another player."""
        from terminus.config import MAX_PENDING_OFFERS, TRADE_OFFER_EXPIRY_TICKS, TRADABLE_RESOURCES

        to_player_id = payload.get("to_player_id", "")
        offer_resources = payload.get("offer_resources", {})
        request_resources = payload.get("request_resources", {})

        # Validate target exists
        if to_player_id not in self.state.players:
            raise ValueError("Target player not found")
        if to_player_id == player_id:
            raise ValueError("Cannot trade with yourself")

        # Validate at least one side non-empty
        if not offer_resources and not request_resources:
            raise ValueError("Trade must have at least one resource on either side")

        # Validate resource names and quantities
        for res, qty in offer_resources.items():
            if res not in TRADABLE_RESOURCES:
                raise ValueError(f"Cannot trade resource: {res}")
            if qty <= 0:
                raise ValueError(f"Quantity must be positive: {res}")

        for res, qty in request_resources.items():
            if res not in TRADABLE_RESOURCES:
                raise ValueError(f"Cannot trade resource: {res}")
            if qty <= 0:
                raise ValueError(f"Quantity must be positive: {res}")

        # Validate proposer has the offered resources
        for res, qty in offer_resources.items():
            current = getattr(colony.resources, res, 0)
            if current < qty:
                raise ValueError(f"Insufficient {res} (have {current:.1f}, offering {qty:.1f})")

        # Check max concurrent outgoing offers
        outgoing = sum(
            1 for t in self.state.pending_trades.values()
            if t.from_player_id == player_id
        )
        if outgoing >= MAX_PENDING_OFFERS:
            raise ValueError(f"Maximum {MAX_PENDING_OFFERS} pending offers allowed")

        # Create offer
        from terminus.server.models import TradeOffer
        offer = TradeOffer(
            from_player_id=player_id,
            to_player_id=to_player_id,
            offer_resources=offer_resources,
            request_resources=request_resources,
            tick_created=self.state.elapsed_ticks,
            expires_tick=self.state.elapsed_ticks + TRADE_OFFER_EXPIRY_TICKS,
        )
        self.state.pending_trades[offer.offer_id] = offer

        return {
            "status": "offer_created",
            "offer_id": offer.offer_id,
            "to_player": to_player_id,
            "offer_resources": offer_resources,
            "request_resources": request_resources,
            "expires_tick": offer.expires_tick,
        }

    def _action_trade_accept(self, colony: Colony, payload: dict, player_id: str) -> dict:
        """Accept a trade offer — atomic resource swap."""
        from terminus.config import TRADABLE_RESOURCES

        offer_id = payload.get("offer_id", "")
        offer = self.state.pending_trades.get(offer_id)

        if not offer:
            raise ValueError("Trade offer not found or expired")
        if offer.to_player_id != player_id:
            raise ValueError("This offer is not addressed to you")

        # Check expiry
        if self.state.elapsed_ticks >= offer.expires_tick:
            del self.state.pending_trades[offer_id]
            raise ValueError("Trade offer has expired")

        # Validate the proposer (from_player) still has the offered resources
        from_player = self.state.players.get(offer.from_player_id)
        if not from_player or not from_player.colony:
            del self.state.pending_trades[offer_id]
            raise ValueError("Proposer is no longer available")

        from_colony = from_player.colony
        for res, qty in offer.offer_resources.items():
            current = getattr(from_colony.resources, res, 0)
            if current < qty:
                del self.state.pending_trades[offer_id]
                raise ValueError(f"Proposer no longer has sufficient {res}")

        # Validate the acceptor has the requested resources
        for res, qty in offer.request_resources.items():
            current = getattr(colony.resources, res, 0)
            if current < qty:
                raise ValueError(f"Insufficient {res} (have {current:.1f}, need {qty:.1f})")

        # ─── Atomic swap ─────────────────────────────────────────────────
        # Deduct from proposer, add to acceptor
        for res, qty in offer.offer_resources.items():
            from_val = getattr(from_colony.resources, res)
            setattr(from_colony.resources, res, from_val - qty)
            to_val = getattr(colony.resources, res)
            cap = getattr(colony.capacity, res)
            setattr(colony.resources, res, min(to_val + qty, cap))

        # Deduct from acceptor, add to proposer
        for res, qty in offer.request_resources.items():
            from_val = getattr(colony.resources, res)
            setattr(colony.resources, res, from_val - qty)
            to_val = getattr(from_colony.resources, res)
            cap = getattr(from_colony.capacity, res)
            setattr(from_colony.resources, res, min(to_val + qty, cap))

        # Record in trade history
        total_offered = sum(offer.offer_resources.values())
        total_requested = sum(offer.request_resources.values())
        self.state.trade_history.append(TradeRecord(
            tick=self.state.elapsed_ticks,
            player_id=offer.from_player_id,
            player_name=from_player.name,
            action="p2p_send",
            resource=",".join(offer.offer_resources.keys()),
            quantity=int(total_offered),
            price_per_unit=0,
            total=total_offered,
        ))
        self.state.trade_history.append(TradeRecord(
            tick=self.state.elapsed_ticks,
            player_id=player_id,
            player_name=self.state.players[player_id].name,
            action="p2p_send",
            resource=",".join(offer.request_resources.keys()),
            quantity=int(total_requested),
            price_per_unit=0,
            total=total_requested,
        ))

        # Update trade stats for both
        from_colony.trades_completed += 1
        colony.trades_completed += 1

        # Remove the offer
        del self.state.pending_trades[offer_id]

        return {
            "status": "trade_completed",
            "offer_id": offer_id,
            "received": offer.offer_resources,
            "sent": offer.request_resources,
        }

    def _action_trade_decline(self, payload: dict, player_id: str) -> dict:
        """Decline a trade offer."""
        offer_id = payload.get("offer_id", "")
        offer = self.state.pending_trades.get(offer_id)

        if not offer:
            raise ValueError("Trade offer not found or expired")
        if offer.to_player_id != player_id:
            raise ValueError("This offer is not addressed to you")

        del self.state.pending_trades[offer_id]

        return {
            "status": "trade_declined",
            "offer_id": offer_id,
        }

    def _action_demolish(self, colony: Colony, payload: dict) -> dict:
        building_type = payload.get("building_type")
        existing = next((b for b in colony.buildings if b.building_type == building_type), None)
        if not existing or existing.level == 0:
            raise ValueError("Building not found")

        b_data = get_building_by_id(building_type)
        if b_data:
            costs = b_data["costs"].get(str(existing.level), {})
            for resource, amount in costs.items():
                refund = amount * DEMOLISH_REFUND_RATIO
                current = getattr(colony.resources, resource, 0)
                cap = getattr(colony.capacity, resource, 9999)
                setattr(colony.resources, resource, min(current + refund, cap))

        existing.level = 0
        existing.health = 0
        existing.under_construction = False
        self._update_colony_capacity(colony)

        return {"status": "demolished", "building": building_type}

    def _action_repair(self, colony: Colony, payload: dict) -> dict:
        building_type = payload.get("building_type")
        existing = next((b for b in colony.buildings if b.building_type == building_type), None)
        if not existing or existing.level == 0:
            raise ValueError("Building not found")
        if existing.health >= existing.max_health:
            raise ValueError("Building at full health")

        damage = existing.max_health - existing.health
        cost = damage * REPAIR_COST_PER_HEALTH
        if colony.resources.materials < cost:
            raise ValueError(f"Insufficient materials (need {cost:.1f})")

        colony.resources.materials -= cost
        existing.health = existing.max_health

        return {"status": "repaired", "building": building_type, "cost": round(cost, 1)}

    # â”€â”€â”€ Utility â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def get_player_state(self, player_id: str) -> dict[str, Any]:
        """Get game state filtered for a specific player."""
        player = self.state.players.get(player_id)
        if not player:
            return {}

        # Other players â€” only show name and score
        others = []
        for p in self.state.players.values():
            if p.player_id != player_id:
                others.append({
                    "name": p.name,
                    "connected": p.connected,
                    "score": p.colony.score if p.colony else 0,
                })

        next_catastrophe_in = None
        if self.state.game_start_time and self.state.current_catastrophe_index < len(self.state.catastrophe_schedule):
            elapsed = time.time() - self.state.game_start_time
            next_time = self.state.catastrophe_schedule[self.state.current_catastrophe_index].scheduled_time
            next_catastrophe_in = max(0, next_time - elapsed)

        # Watchtower hint based on building level
        watchtower_hint = None
        if player.colony and next_catastrophe_in is not None:
            from terminus.config import WATCHTOWER_HINTS
            wt = next((b for b in player.colony.buildings
                       if b.building_type == "watchtower" and not b.under_construction and b.level > 0), None)
            if wt:
                hint_level = WATCHTOWER_HINTS.get(min(wt.level, 3), "category")
                next_event = self.state.catastrophe_schedule[self.state.current_catastrophe_index]
                cat_data = get_catastrophe_by_id(next_event.catastrophe_id)
                if cat_data:
                    if hint_level == "category":
                        watchtower_hint = f"A {cat_data['category']} threat approaches..."
                    elif hint_level == "type":
                        watchtower_hint = f"{cat_data['name']} is coming!"
                    elif hint_level == "type_and_timing":
                        watchtower_hint = f"{cat_data['name']} in ~{int(next_catastrophe_in)}s!"

        return {
            "game_id": self.state.game_id,
            "phase": self.state.phase.value,
            "colony": player.colony.model_dump() if player.colony else None,
            "market": self.state.market.model_dump(),
            "other_players": others,
            "player_count": len(self.state.players),
            "catastrophes_remaining": len(self.state.catastrophe_schedule) - self.state.current_catastrophe_index,
            "next_catastrophe_in": next_catastrophe_in,
            "watchtower_hint": watchtower_hint,
            "tick": self.state.elapsed_ticks,
            "production_rates": self.get_production_rates(player.colony) if player.colony else None,
            "trade_history": [
                t.model_dump() for t in self.state.trade_history
                if t.player_id == player_id
            ],
            "incoming_trade_offers": [
                o.model_dump() for o in self.state.pending_trades.values()
                if o.to_player_id == player_id
            ],
            "outgoing_trade_offers": [
                o.model_dump() for o in self.state.pending_trades.values()
                if o.from_player_id == player_id
            ],
        }
