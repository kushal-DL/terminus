"""Quick integration test of the game engine."""
import asyncio
from terminus.server.engine import GameEngine
from terminus.server.models import GameSettings, Player, Location, Specialization, ActionType


async def test():
    engine = GameEngine(settings=GameSettings(preset="quick"))

    # Add host
    host = Player(name="Host", is_host=True)
    engine.add_player(host)

    # Add player
    p2 = Player(name="Player2")
    engine.add_player(p2)

    # Start game
    await engine.start_game(host.player_id)
    print(f"Phase after start: {engine.state.phase.value}")

    # Submit setup
    await engine.submit_setup(host.player_id, Location.COAST, Specialization.TRADE)
    await engine.submit_setup(p2.player_id, Location.MOUNTAIN, Specialization.MILITARY)

    # Check setup complete triggers playing
    done = await engine.check_setup_complete()
    print(f"Setup complete: {done}")
    print(f"Phase after setup: {engine.state.phase.value}")
    print(f"Catastrophes scheduled: {len(engine.state.catastrophe_schedule)}")

    # Check colonies initialized
    for pid, player in engine.state.players.items():
        c = player.colony
        print(f"  {player.name}: pop={c.population}, food={c.resources.food}, loc={c.location.value}, spec={c.specialization.value}")

    # Test actions
    result = await engine.handle_action(host.player_id, ActionType.BUILD, {"building_type": "farm"})
    print(f"Build result: {result}")

    # Test market buy
    result = await engine.handle_action(host.player_id, ActionType.TRADE_BUY, {"resource": "food", "quantity": 10})
    print(f"Trade result: {result}")

    # Process a few ticks
    for i in range(5):
        engine._process_colony_tick(host.colony)
    print(f"After 5 ticks - Host food: {host.colony.resources.food:.1f}")

    # Test scoring
    scores = engine._calculate_scores()
    for s in scores:
        print(f"  Score: {s['name']} = {s['score']}")

    engine.stop()
    print("\nAll tests passed!")


asyncio.run(test())
