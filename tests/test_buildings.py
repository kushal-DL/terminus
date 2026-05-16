"""Tests for building lifecycle: build, upgrade, repair, demolish."""
import pytest

from terminus.server.models import ActionType


@pytest.mark.asyncio
async def test_build_starts_construction(playing_game):
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]

    result = await engine.handle_action(
        host.player_id, ActionType.BUILD, {"building_type": "farm"}
    )
    assert result["status"] == "construction_started"

    # Should have a building under construction
    buildings = host.colony.buildings
    assert len(buildings) > 0
    assert buildings[0].under_construction is True


@pytest.mark.asyncio
async def test_construction_completes_after_ticks(playing_game):
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]

    # Assign construction workers for faster building
    from terminus.server.models import WorkerAllocation
    pop = int(host.colony.population)
    host.colony.workers = WorkerAllocation(construction=pop // 2, farming=pop - pop // 2)

    await engine.handle_action(host.player_id, ActionType.BUILD, {"building_type": "farm"})

    # Process enough ticks for construction to complete
    for _ in range(30):
        engine._process_colony_tick(host.colony)

    farm = next((b for b in host.colony.buildings if b.building_type == "farm"), None)
    assert farm is not None
    assert farm.under_construction is False
    assert farm.level >= 1


@pytest.mark.asyncio
async def test_build_deducts_resources(playing_game):
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]

    materials_before = host.colony.resources.materials
    await engine.handle_action(host.player_id, ActionType.BUILD, {"building_type": "farm"})
    materials_after = host.colony.resources.materials

    # Should have spent some materials
    assert materials_after < materials_before


@pytest.mark.asyncio
async def test_cannot_build_without_resources(playing_game):
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]

    # Zero out resources
    host.colony.resources.materials = 0
    host.colony.resources.food = 0
    host.colony.resources.gold = 0

    with pytest.raises(ValueError):
        await engine.handle_action(host.player_id, ActionType.BUILD, {"building_type": "farm"})


@pytest.mark.asyncio
async def test_demolish_returns_resources(playing_game):
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]

    # Give resources and build
    host.colony.resources.materials = 500
    host.colony.resources.food = 500
    await engine.handle_action(host.player_id, ActionType.BUILD, {"building_type": "farm"})

    # Fast-complete construction
    farm = host.colony.buildings[0]
    farm.under_construction = False
    farm.level = 1

    materials_before = host.colony.resources.materials
    await engine.handle_action(host.player_id, ActionType.DEMOLISH, {"building_type": "farm"})
    materials_after = host.colony.resources.materials

    # Should get some resources back
    assert materials_after > materials_before
