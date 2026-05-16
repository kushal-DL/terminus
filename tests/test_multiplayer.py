"""Integration tests — multiplayer concurrency with 5 players."""

import asyncio
import pytest
import pytest_asyncio

from terminus.server.engine import GameEngine
from terminus.server.models import (
    ActionType,
    GameSettings,
    Player,
    Location,
    Specialization,
)


LOCATIONS = [Location.COAST, Location.MOUNTAIN, Location.PLAINS, Location.DESERT, Location.COAST]
SPECS = [
    Specialization.TRADE, Specialization.MILITARY, Specialization.SCIENCE,
    Specialization.TRADE, Specialization.MILITARY,
]


@pytest_asyncio.fixture
async def five_player_game() -> GameEngine:
    """Engine with 5 players in PLAYING phase."""
    engine = GameEngine(settings=GameSettings(preset="quick"))
    players = []
    for i in range(5):
        p = Player(name=f"Player{i+1}", is_host=(i == 0))
        engine.add_player(p)
        players.append(p)

    await engine.start_game(players[0].player_id)

    for i, p in enumerate(players):
        await engine.submit_setup(p.player_id, LOCATIONS[i], SPECS[i])
    await engine.check_setup_complete()

    return engine


@pytest.mark.asyncio
async def test_five_players_added(five_player_game: GameEngine):
    assert len(five_player_game.state.players) == 5


@pytest.mark.asyncio
async def test_concurrent_actions(five_player_game: GameEngine):
    """All 5 players submit build actions concurrently."""
    engine = five_player_game
    pids = list(engine.state.players.keys())

    async def build_farm(pid: str):
        return await engine.handle_action(pid, ActionType.BUILD, {"building_type": "farm"})

    results = await asyncio.gather(*[build_farm(pid) for pid in pids], return_exceptions=True)
    # All should succeed (or fail gracefully) — no crashes
    for r in results:
        assert not isinstance(r, Exception), f"Unexpected exception: {r}"


@pytest.mark.asyncio
async def test_concurrent_worker_allocation(five_player_game: GameEngine):
    """All 5 players allocate workers concurrently."""
    engine = five_player_game
    pids = list(engine.state.players.keys())

    async def set_workers(pid: str):
        player = engine.state.players[pid]
        pop = player.colony.population if player.colony else 20
        farming = pop // 2
        mining = pop - farming
        return await engine.handle_action(pid, ActionType.ALLOCATE_WORKERS, {
            "allocation": {
                "farming": farming, "mining": mining, "research": 0,
                "construction": 0, "defense": 0, "medicine": 0,
            }
        })

    results = await asyncio.gather(*[set_workers(pid) for pid in pids], return_exceptions=True)
    for r in results:
        assert not isinstance(r, Exception), f"Unexpected exception: {r}"


@pytest.mark.asyncio
async def test_all_players_get_state(five_player_game: GameEngine):
    """Each player can get their own state."""
    engine = five_player_game
    for pid in engine.state.players:
        state = engine.get_player_state(pid)
        assert "colony" in state
        assert state["colony"]["location"] is not None


@pytest.mark.asyncio
async def test_player_removal_during_game(five_player_game: GameEngine):
    """Removing a player mid-game doesn't crash."""
    engine = five_player_game
    pids = list(engine.state.players.keys())
    victim = pids[-1]
    engine.state.players[victim].connected = False
    # Remaining players should still be able to act
    for pid in pids[:-1]:
        state = engine.get_player_state(pid)
        assert "colony" in state
