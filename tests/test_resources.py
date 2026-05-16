"""Tests for resource production, starvation, and capacity."""
import pytest

from terminus.server.models import GamePhase, WorkerAllocation


@pytest.mark.asyncio
async def test_production_increases_food(playing_game):
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]
    initial_food = host.colony.resources.food

    # Ensure farming workers are allocated
    host.colony.workers = WorkerAllocation(farming=host.colony.population)

    # Process a few ticks
    for _ in range(3):
        engine._process_colony_tick(host.colony)

    assert host.colony.resources.food > initial_food


@pytest.mark.asyncio
async def test_starvation_reduces_population(playing_game):
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]
    initial_pop = host.colony.population

    # Set food to 0 to trigger starvation
    host.colony.resources.food = 0

    for _ in range(5):
        engine._process_colony_tick(host.colony)

    assert host.colony.population < initial_pop


@pytest.mark.asyncio
async def test_starvation_reduces_morale(playing_game):
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]
    initial_morale = host.colony.morale

    host.colony.resources.food = 0

    for _ in range(3):
        engine._process_colony_tick(host.colony)

    assert host.colony.morale < initial_morale


@pytest.mark.asyncio
async def test_resources_capped_at_capacity(playing_game):
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]

    # Set food way above capacity
    host.colony.resources.food = 99999

    engine._process_colony_tick(host.colony)

    # Should be capped at capacity
    assert host.colony.resources.food <= host.colony.capacity.food


@pytest.mark.asyncio
async def test_worker_allocation_affects_production(playing_game):
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]

    # All workers to farming
    pop = int(host.colony.population)
    host.colony.workers = WorkerAllocation(farming=pop)
    food_before = host.colony.resources.food

    engine._process_colony_tick(host.colony)

    food_after = host.colony.resources.food
    food_gain_farming = food_after - food_before

    # Reset — all workers to mining (no farming)
    host.colony.resources.food = food_before
    host.colony.workers = WorkerAllocation(mining=pop)

    engine._process_colony_tick(host.colony)

    food_gain_no_farming = host.colony.resources.food - food_before

    # Farming workers should produce more food than no farming workers
    assert food_gain_farming > food_gain_no_farming
