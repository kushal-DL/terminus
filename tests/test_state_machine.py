"""Tests for game state machine transitions."""
import pytest
import pytest_asyncio

from terminus.server.engine import GameEngine
from terminus.server.models import GamePhase, GameSettings, Player, Location, Specialization


@pytest.mark.asyncio
async def test_initial_phase_is_lobby(engine):
    assert engine.state.phase == GamePhase.LOBBY


@pytest.mark.asyncio
async def test_start_transitions_to_setup(two_player_game):
    engine = two_player_game
    host_id = [p for p in engine.state.players.values() if p.is_host][0].player_id
    await engine.start_game(host_id)
    assert engine.state.phase == GamePhase.SETUP


@pytest.mark.asyncio
async def test_setup_complete_transitions_to_playing(two_player_game):
    engine = two_player_game
    host_id = [p for p in engine.state.players.values() if p.is_host][0].player_id
    p2_id = [p for p in engine.state.players.values() if not p.is_host][0].player_id

    await engine.start_game(host_id)
    await engine.submit_setup(host_id, Location.COAST, Specialization.TRADE)
    await engine.submit_setup(p2_id, Location.MOUNTAIN, Specialization.MILITARY)
    await engine.check_setup_complete()

    assert engine.state.phase == GamePhase.PLAYING


@pytest.mark.asyncio
async def test_cannot_start_if_not_host(two_player_game):
    engine = two_player_game
    p2_id = [p for p in engine.state.players.values() if not p.is_host][0].player_id

    with pytest.raises(ValueError):
        await engine.start_game(p2_id)


@pytest.mark.asyncio
async def test_cannot_join_after_start(two_player_game):
    engine = two_player_game
    host_id = [p for p in engine.state.players.values() if p.is_host][0].player_id
    await engine.start_game(host_id)

    p3 = Player(name="Late Player")
    with pytest.raises(ValueError):
        engine.add_player(p3)


@pytest.mark.asyncio
async def test_cannot_start_with_zero_players():
    engine = GameEngine(settings=GameSettings(preset="quick"))
    host = Player(name="Host", is_host=True)
    engine.add_player(host)

    # Only 1 player — should still work (solo mode)
    await engine.start_game(host.player_id)
    assert engine.state.phase == GamePhase.SETUP


@pytest.mark.asyncio
async def test_cannot_submit_setup_in_lobby(two_player_game):
    engine = two_player_game
    host_id = [p for p in engine.state.players.values() if p.is_host][0].player_id

    with pytest.raises(ValueError):
        await engine.submit_setup(host_id, Location.COAST, Specialization.TRADE)
