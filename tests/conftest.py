"""Pytest fixtures for Terminus engine tests."""
import asyncio
import pytest
import pytest_asyncio

from terminus.server.engine import GameEngine
from terminus.server.models import (
    GameSettings,
    Player,
    Location,
    Specialization,
)


@pytest.fixture
def engine() -> GameEngine:
    """Fresh GameEngine with quick preset."""
    return GameEngine(settings=GameSettings(preset="quick"))


@pytest_asyncio.fixture
async def two_player_game() -> GameEngine:
    """Engine with 2 players joined, still in LOBBY phase."""
    engine = GameEngine(settings=GameSettings(preset="quick"))
    host = Player(name="Host", is_host=True)
    engine.add_player(host)
    p2 = Player(name="Player2")
    engine.add_player(p2)
    return engine


@pytest_asyncio.fixture
async def playing_game() -> GameEngine:
    """Engine advanced to PLAYING phase with 2 players set up."""
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
