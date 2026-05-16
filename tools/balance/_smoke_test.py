"""Quick smoke test for the simulation runner."""
import asyncio
from tools.balance.simulator import SimulationRunner, SimPlayer
from tools.balance.strategies import BalancedStrategy, AggressiveStrategy
from terminus.server.models import Location, Specialization


async def test():
    runner = SimulationRunner(seed=42)
    players = [
        SimPlayer("P1", Location.COAST, Specialization.TRADE, BalancedStrategy()),
        SimPlayer("P2", Location.MOUNTAIN, Specialization.MILITARY, AggressiveStrategy()),
    ]
    result = await runner.run_single(players, "quick")
    print(f"Ticks: {result.duration_ticks}, Duration: {result.duration_seconds / 60:.1f}min")
    print(f"Survivors: {result.survivors}/{result.total_players}")
    for pd in result.player_data:
        name = pd["name"]
        score = pd["score"]
        pop = pd["population"]
        built = pd["buildings_built"]
        print(f"  {name}: score={score}, pop={pop}, built={built}")
    print()
    # Test batch
    batch = await runner.run_batch(n_games=3, preset="quick")
    from tools.balance.report import print_report
    print_report(batch)


if __name__ == "__main__":
    asyncio.run(test())
