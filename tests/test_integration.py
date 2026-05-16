"""Integration test: full game lifecycle from lobby to scoring."""
import pytest

from terminus.server.engine import GameEngine
from terminus.server.models import (
    GameSettings,
    Player,
    Location,
    Specialization,
    ActionType,
    GamePhase,
)


@pytest.mark.asyncio
async def test_full_game_lifecycle():
    """Run a complete game from lobby → setup → playing → scoring."""
    engine = GameEngine(settings=GameSettings(preset="quick"))

    # --- LOBBY ---
    host = Player(name="Alpha", is_host=True)
    engine.add_player(host)
    p2 = Player(name="Bravo")
    engine.add_player(p2)

    assert engine.state.phase == GamePhase.LOBBY
    assert len(engine.state.players) == 2

    # --- START → SETUP ---
    await engine.start_game(host.player_id)
    assert engine.state.phase == GamePhase.SETUP

    await engine.submit_setup(host.player_id, Location.COAST, Specialization.TRADE)
    await engine.submit_setup(p2.player_id, Location.FOREST, Specialization.AGRICULTURE)
    done = await engine.check_setup_complete()
    assert done is True
    assert engine.state.phase == GamePhase.PLAYING

    # --- PLAYING: build + trade ---
    await engine.handle_action(
        host.player_id, ActionType.BUILD, {"building_type": "farm"}
    )
    assert len(host.colony.buildings) > 0

    # Process several ticks to gather resources
    for _ in range(10):
        engine._process_colony_tick(host.colony)
        engine._process_colony_tick(p2.colony)

    # Sell excess food
    if host.colony.resources.food >= 10:
        await engine.handle_action(
            host.player_id, ActionType.TRADE_SELL, {"resource": "food", "quantity": 5}
        )

    # --- ADVANCE TO SCORING ---
    await engine._end_game()

    # Should be in finished
    assert engine.state.phase == GamePhase.FINISHED

    # --- SCORING ---
    scores = engine._calculate_scores()
    assert len(scores) == 2
    assert all("score" in s for s in scores)
    assert all(s["score"] >= 0 for s in scores)
