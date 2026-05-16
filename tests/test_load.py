"""Load tests — stress test with many players. Marked @pytest.mark.slow."""

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

LOCATIONS = list(Location)
SPECS = list(Specialization)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_250_players_join():
    """250 players can join a game without errors."""
    engine = GameEngine(settings=GameSettings(preset="quick", max_players=250))
    players = []
    for i in range(250):
        p = Player(name=f"LoadP{i}", is_host=(i == 0))
        engine.add_player(p)
        players.append(p)

    assert len(engine.state.players) == 250


@pytest.mark.slow
@pytest.mark.asyncio
async def test_250_players_get_state():
    """250 players can all retrieve their state."""
    engine = GameEngine(settings=GameSettings(preset="quick", max_players=250))
    players = []
    for i in range(250):
        p = Player(name=f"LoadP{i}", is_host=(i == 0))
        engine.add_player(p)
        players.append(p)

    await engine.start_game(players[0].player_id)
    for i, p in enumerate(players):
        loc = LOCATIONS[i % len(LOCATIONS)]
        spec = SPECS[i % len(SPECS)]
        await engine.submit_setup(p.player_id, loc, spec)
    await engine.check_setup_complete()

    for p in players:
        state = engine.get_player_state(p.player_id)
        assert "colony" in state


@pytest.mark.slow
@pytest.mark.asyncio
async def test_250_concurrent_builds():
    """250 players submit builds concurrently."""
    engine = GameEngine(settings=GameSettings(preset="quick", max_players=250))
    players = []
    for i in range(250):
        p = Player(name=f"LoadP{i}", is_host=(i == 0))
        engine.add_player(p)
        players.append(p)

    await engine.start_game(players[0].player_id)
    for i, p in enumerate(players):
        loc = LOCATIONS[i % len(LOCATIONS)]
        spec = SPECS[i % len(SPECS)]
        await engine.submit_setup(p.player_id, loc, spec)
    await engine.check_setup_complete()

    async def build_farm(pid: str):
        return await engine.handle_action(pid, ActionType.BUILD, {"building_type": "farm"})

    pids = list(engine.state.players.keys())
    results = await asyncio.gather(*[build_farm(pid) for pid in pids], return_exceptions=True)
    # No crashes — some may fail due to resources, that's fine
    errors = [r for r in results if isinstance(r, Exception)]
    # Allow up to some expected failures (insufficient resources), but no unexpected crashes
    for e in errors:
        assert "resources" in str(e).lower() or "insufficient" in str(e).lower() or "cannot" in str(e).lower(), f"Unexpected error: {e}"
