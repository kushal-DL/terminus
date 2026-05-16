"""Headless simulation runner for Terminus game balance testing.

Drives the GameEngine directly without HTTP/WS overhead. Supports
single-game and batch execution with configurable AI strategies.
"""

from __future__ import annotations

import asyncio
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from terminus.config import SERVER_TICK_INTERVAL, CATASTROPHE_RESOLUTION_SECONDS
from terminus.server.engine import GameEngine
from terminus.server.models import (
    ActionType,
    CatastropheEvent,
    Colony,
    GamePhase,
    GameSettings,
    Location,
    Player,
    Specialization,
)

from tools.balance.strategies import Strategy, ALL_STRATEGIES, STRATEGY_MAP


# ─── Data Containers ─────────────────────────────────────────────────────────


@dataclass
class SimPlayer:
    """A simulated player with a location, specialization, and AI strategy."""
    name: str
    location: Location
    specialization: Specialization
    strategy: Strategy
    player_id: str = ""


@dataclass
class GameResult:
    """Result of a single simulated game."""
    preset: str = "quick"
    duration_ticks: int = 0
    duration_seconds: float = 0.0
    final_scores: list[dict[str, Any]] = field(default_factory=list)
    player_data: list[dict[str, Any]] = field(default_factory=list)
    # Per-player tracking
    first_starvation_tick: dict[str, int] = field(default_factory=dict)  # player_name → tick
    first_build_tick: dict[str, int] = field(default_factory=dict)  # player_name → tick
    survivors: int = 0
    total_players: int = 0


@dataclass
class BatchResults:
    """Aggregated results from multiple simulated games."""
    preset: str = "quick"
    games: list[GameResult] = field(default_factory=list)
    # Aggregated metrics
    game_durations: list[float] = field(default_factory=list)
    all_final_scores: list[float] = field(default_factory=list)
    first_starvation_ticks: list[int] = field(default_factory=list)
    first_build_ticks: list[int] = field(default_factory=list)
    never_built_count: int = 0
    survivors: int = 0
    total_players: int = 0
    # Per-combo tracking: "location:spec:strategy" → list of scores
    combo_scores: dict[str, list[float]] = field(default_factory=dict)
    combo_wins: dict[str, int] = field(default_factory=dict)

    def wins_by_combo(self) -> dict[str, float]:
        """Return win rate per combo."""
        total_games = len(self.games)
        if total_games == 0:
            return {}
        return {combo: wins / total_games for combo, wins in self.combo_wins.items()}


# ─── Simulation Runner ───────────────────────────────────────────────────────


class SimulationRunner:
    """Run headless games by driving GameEngine directly."""

    def __init__(self, seed: int | None = None):
        if seed is not None:
            random.seed(seed)

    async def run_single(
        self,
        players: list[SimPlayer],
        preset: str = "quick",
    ) -> GameResult:
        """Run a single game to completion and return results."""
        result = GameResult(preset=preset, total_players=len(players))

        # Create engine
        engine = GameEngine(settings=GameSettings(preset=preset))

        # Silence broadcast callbacks (no WS clients)
        engine._broadcast = _noop_broadcast
        engine._broadcast_to_player = _noop_player_broadcast

        # Add players
        for sp in players:
            p = Player(name=sp.name, is_host=(sp == players[0]))
            engine.add_player(p)
            sp.player_id = p.player_id

        # Start game → SETUP phase
        host_id = players[0].player_id
        await engine.start_game(host_id)

        # Submit setup for all players
        for sp in players:
            await engine.submit_setup(sp.player_id, sp.location, sp.specialization)
        await engine.check_setup_complete()

        # Now in PLAYING phase — drive the tick loop
        # Override game_start_time so catastrophe scheduling uses simulated time
        sim_start = time.time()
        engine.state.game_start_time = sim_start

        # Track per-player metrics
        has_starved: dict[str, bool] = {sp.name: False for sp in players}
        has_built: dict[str, bool] = {sp.name: False for sp in players}

        tick = 0
        max_ticks = 10000  # safety valve

        while engine.state.phase not in (GamePhase.SCORING, GamePhase.FINISHED) and tick < max_ticks:
            tick += 1

            # Advance simulated time so catastrophe timers fire correctly
            _sim_elapsed = tick * SERVER_TICK_INTERVAL
            engine.state.game_start_time = sim_start - _sim_elapsed + (time.time() - sim_start)

            # If in CATASTROPHE phase, fast-forward past resolution
            if engine.state.phase == GamePhase.CATASTROPHE:
                if engine._catastrophe_active_until:
                    engine._catastrophe_active_until = time.time() - 1  # expire immediately
                await engine._tick()
                continue

            # Process tick
            await engine._tick()

            # Let strategies decide actions (only in PLAYING phase)
            if engine.state.phase == GamePhase.PLAYING:
                for sp in players:
                    player = engine.state.players.get(sp.player_id)
                    if not player or not player.colony or not player.connected:
                        continue
                    colony = player.colony

                    # Track starvation
                    if colony.resources.food <= 0 and not has_starved[sp.name]:
                        has_starved[sp.name] = True
                        result.first_starvation_tick[sp.name] = tick

                    # Track first build
                    if not has_built[sp.name]:
                        built = any(b.level > 0 and not b.under_construction for b in colony.buildings)
                        constructing = any(b.under_construction for b in colony.buildings)
                        if built or constructing:
                            has_built[sp.name] = True
                            result.first_build_tick[sp.name] = tick

                    # Get strategy actions
                    actions = sp.strategy.decide_actions(colony, tick)
                    for action_type, payload in actions:
                        try:
                            await engine.handle_action(sp.player_id, action_type, payload)
                        except (ValueError, Exception):
                            pass  # Strategy tried something invalid — skip

        # Collect results
        result.duration_ticks = tick
        result.duration_seconds = tick * SERVER_TICK_INTERVAL
        result.final_scores = engine._calculate_scores()
        result.survivors = sum(
            1 for p in engine.state.players.values()
            if p.colony and p.colony.population > 0
        )

        # Per-player detail
        for sp in players:
            player = engine.state.players.get(sp.player_id)
            colony = player.colony if player else None
            score_entry = next((s for s in result.final_scores if s["player_id"] == sp.player_id), None)
            result.player_data.append({
                "name": sp.name,
                "location": sp.location.value,
                "specialization": sp.specialization.value,
                "strategy": sp.strategy.name,
                "combo": f"{sp.location.value}:{sp.specialization.value}:{sp.strategy.name}",
                "score": score_entry["score"] if score_entry else 0,
                "population": colony.population if colony else 0,
                "morale": colony.morale if colony else 0,
                "buildings_built": colony.buildings_built if colony else 0,
                "survived": colony.population > 0 if colony else False,
            })

        return result

    async def run_batch(
        self,
        n_games: int,
        player_configs: list[SimPlayer] | None = None,
        preset: str = "quick",
        all_combos: bool = False,
    ) -> BatchResults:
        """Run multiple games and aggregate results.

        If all_combos=True, generates games covering all location×spec×strategy combos.
        Otherwise, uses the provided player_configs for each game.
        """
        batch = BatchResults(preset=preset)

        if all_combos:
            configs_list = self._generate_all_combo_games(n_games)
        else:
            configs_list = [player_configs or self._random_players(4)] * n_games

        for i, players in enumerate(configs_list):
            game_result = await self.run_single(players, preset)
            batch.games.append(game_result)

            # Aggregate
            batch.game_durations.append(game_result.duration_seconds)
            batch.survivors += game_result.survivors
            batch.total_players += game_result.total_players

            for pd in game_result.player_data:
                batch.all_final_scores.append(pd["score"])
                combo = pd["combo"]
                batch.combo_scores.setdefault(combo, []).append(pd["score"])

            # Winner tracking
            if game_result.final_scores:
                winner_id = game_result.final_scores[0]["player_id"]
                winner_data = next((pd for pd in game_result.player_data if game_result.final_scores[0]["name"] == pd["name"]), None)
                if winner_data:
                    combo = winner_data["combo"]
                    batch.combo_wins[combo] = batch.combo_wins.get(combo, 0) + 1

            # Starvation / build tracking
            for name, tick_val in game_result.first_starvation_tick.items():
                batch.first_starvation_ticks.append(tick_val)
            for name, tick_val in game_result.first_build_tick.items():
                batch.first_build_ticks.append(tick_val)
            # Count players who never built
            for pd in game_result.player_data:
                if pd["buildings_built"] == 0:
                    batch.never_built_count += 1

            if (i + 1) % 10 == 0:
                print(f"  ... completed {i + 1}/{len(configs_list)} games", file=sys.stderr)

        return batch

    def _random_players(self, count: int) -> list[SimPlayer]:
        """Generate random player configs."""
        locations = list(Location)
        specs = list(Specialization)
        return [
            SimPlayer(
                name=f"Bot_{i}",
                location=random.choice(locations),
                specialization=random.choice(specs),
                strategy=random.choice(ALL_STRATEGIES)(),
            )
            for i in range(count)
        ]

    def _generate_all_combo_games(self, n_games: int) -> list[list[SimPlayer]]:
        """Generate games that cover all location×spec×strategy combos."""
        locations = list(Location)
        specs = list(Specialization)
        strategies = ALL_STRATEGIES

        # Create one game per combo set, with 4 diverse players each
        games: list[list[SimPlayer]] = []
        combo_idx = 0
        for _ in range(n_games):
            players = []
            for j in range(4):
                loc = locations[(combo_idx + j) % len(locations)]
                spec = specs[(combo_idx + j) % len(specs)]
                strat = strategies[(combo_idx + j) % len(strategies)]
                players.append(SimPlayer(
                    name=f"Bot_{combo_idx}_{j}",
                    location=loc,
                    specialization=spec,
                    strategy=strat(),
                ))
                combo_idx += 1
            games.append(players)

        return games


# ─── No-op broadcast stubs ───────────────────────────────────────────────────


async def _noop_broadcast(event: str, data: dict) -> None:
    pass


async def _noop_player_broadcast(player_id: str, event: str, data: dict) -> None:
    pass


# ─── CLI Entry Point ─────────────────────────────────────────────────────────


async def _main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Terminus Balance Simulator")
    parser.add_argument("--preset", default="quick", choices=["quick", "standard", "extended"])
    parser.add_argument("--games", type=int, default=10, help="Number of games to simulate")
    parser.add_argument("--players", type=int, default=4, help="Players per game")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--all-combos", action="store_true", help="Cover all location×spec×strategy combos")
    args = parser.parse_args()

    print(f"Running {args.games} games on '{args.preset}' preset with {args.players} players each...")
    runner = SimulationRunner(seed=args.seed)

    batch = await runner.run_batch(
        n_games=args.games,
        preset=args.preset,
        all_combos=args.all_combos,
    )

    # Print report
    from tools.balance.report import print_report
    print_report(batch)


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
