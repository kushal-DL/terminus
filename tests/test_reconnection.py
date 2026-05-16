"""Integration tests — disconnect/reconnect scenarios."""

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


@pytest_asyncio.fixture
async def reconnect_game() -> GameEngine:
    """Two-player game in PLAYING phase for reconnect tests."""
    engine = GameEngine(settings=GameSettings(preset="quick"))
    host = Player(name="Host", is_host=True)
    engine.add_player(host)
    p2 = Player(name="Player2")
    engine.add_player(p2)

    await engine.start_game(host.player_id)
    await engine.submit_setup(host.player_id, Location.COAST, Specialization.TRADE)
    await engine.submit_setup(p2.player_id, Location.MOUNTAIN, Specialization.MILITARY)
    await engine.check_setup_complete()

    return engine


@pytest.mark.asyncio
async def test_disconnect_marks_player(reconnect_game: GameEngine):
    """Setting connected=False marks player as disconnected."""
    engine = reconnect_game
    pid = list(engine.state.players.keys())[1]
    engine.state.players[pid].connected = False
    assert not engine.state.players[pid].connected


@pytest.mark.asyncio
async def test_reconnect_restores_state(reconnect_game: GameEngine):
    """After disconnect+reconnect, player state is fully available."""
    engine = reconnect_game
    pid = list(engine.state.players.keys())[1]
    # Simulate disconnect
    engine.state.players[pid].connected = False
    # Simulate reconnect
    engine.state.players[pid].connected = True
    state = engine.get_player_state(pid)
    assert "colony" in state
    assert state["colony"]["location"] is not None


@pytest.mark.asyncio
async def test_actions_after_reconnect(reconnect_game: GameEngine):
    """Player can submit actions after reconnecting."""
    engine = reconnect_game
    pid = list(engine.state.players.keys())[1]
    engine.state.players[pid].connected = False
    engine.state.players[pid].connected = True
    result = await engine.handle_action(pid, ActionType.BUILD, {"building_type": "farm"})
    assert result is not None


@pytest.mark.asyncio
async def test_other_player_unaffected_by_disconnect(reconnect_game: GameEngine):
    """Host can still play normally when P2 disconnects."""
    engine = reconnect_game
    pids = list(engine.state.players.keys())
    host_pid, p2_pid = pids[0], pids[1]
    engine.state.players[p2_pid].connected = False

    state = engine.get_player_state(host_pid)
    assert "colony" in state
    result = await engine.handle_action(host_pid, ActionType.BUILD, {"building_type": "farm"})
    assert result is not None
