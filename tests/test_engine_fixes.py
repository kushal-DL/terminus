"""Tests for Sprint 6 engine bug fixes: spec modifiers, worker allocation, name uniqueness, tick drift."""
import pytest

from terminus.config import SPECIALIZATION_MODIFIERS, BASE_PRODUCTION_PER_TICK, WORKER_ROLES
from terminus.server.models import (
    GamePhase,
    Location,
    Player,
    Specialization,
    WorkerAllocation,
)


# ─── A2: Specialization modifiers applied to production ──────────────────────


@pytest.mark.asyncio
async def test_agriculture_spec_boosts_food(playing_game):
    """Agriculture specialization should increase food production."""
    engine = playing_game
    # Find player with agriculture spec or set one up
    host = [p for p in engine.state.players.values() if p.is_host][0]
    host.colony.specialization = Specialization.AGRICULTURE
    host.colony.workers = WorkerAllocation(farming=host.colony.population)

    initial_food = host.colony.resources.food
    for _ in range(5):
        engine._process_colony_tick(host.colony)
    food_with_agri = host.colony.resources.food - initial_food

    # Reset and test without spec bonus
    host.colony.resources.food = initial_food
    host.colony.specialization = Specialization.MILITARY  # no food bonus
    for _ in range(5):
        engine._process_colony_tick(host.colony)
    food_without_agri = host.colony.resources.food - initial_food

    assert food_with_agri > food_without_agri, (
        f"Agriculture spec should produce more food: {food_with_agri} vs {food_without_agri}"
    )


@pytest.mark.asyncio
async def test_science_spec_boosts_knowledge(playing_game):
    """Science specialization should increase knowledge production."""
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]
    host.colony.specialization = Specialization.SCIENCE
    host.colony.workers = WorkerAllocation(research=host.colony.population)

    initial_knowledge = host.colony.resources.knowledge
    for _ in range(5):
        engine._process_colony_tick(host.colony)
    knowledge_with_science = host.colony.resources.knowledge - initial_knowledge

    host.colony.resources.knowledge = initial_knowledge
    host.colony.specialization = Specialization.AGRICULTURE  # no knowledge bonus
    for _ in range(5):
        engine._process_colony_tick(host.colony)
    knowledge_without_science = host.colony.resources.knowledge - initial_knowledge

    assert knowledge_with_science > knowledge_without_science


@pytest.mark.asyncio
async def test_military_spec_boosts_materials(playing_game):
    """Military specialization should give materials bonus."""
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]
    host.colony.specialization = Specialization.MILITARY
    host.colony.workers = WorkerAllocation(mining=host.colony.population)

    initial_mat = host.colony.resources.materials
    for _ in range(5):
        engine._process_colony_tick(host.colony)
    mat_with_mil = host.colony.resources.materials - initial_mat

    host.colony.resources.materials = initial_mat
    host.colony.specialization = Specialization.SCIENCE  # no materials bonus
    for _ in range(5):
        engine._process_colony_tick(host.colony)
    mat_without_mil = host.colony.resources.materials - initial_mat

    assert mat_with_mil > mat_without_mil


# ─── A1: WORKER_ROLES import / worker allocation ────────────────────────────


@pytest.mark.asyncio
async def test_worker_allocation_succeeds(playing_game):
    """Worker allocation should not crash (WORKER_ROLES must be imported)."""
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]
    pop = host.colony.population

    allocation = {role: 0 for role in WORKER_ROLES}
    allocation["farming"] = pop

    result = engine._action_allocate(host.colony, {"allocation": allocation})
    assert result["status"] == "workers_allocated"
    assert host.colony.workers.farming == pop


@pytest.mark.asyncio
async def test_worker_allocation_rejects_wrong_total(playing_game):
    """Worker allocation must sum to population."""
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]

    allocation = {role: 0 for role in WORKER_ROLES}
    allocation["farming"] = host.colony.population + 10  # wrong total

    with pytest.raises(ValueError, match="must equal population"):
        engine._action_allocate(host.colony, {"allocation": allocation})


@pytest.mark.asyncio
async def test_worker_allocation_rejects_missing_role(playing_game):
    """Worker allocation must include all roles."""
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]

    allocation = {"farming": host.colony.population}  # missing other roles

    with pytest.raises(ValueError, match="Missing role"):
        engine._action_allocate(host.colony, {"allocation": allocation})


# ─── A4: Player name uniqueness ─────────────────────────────────────────────


def test_duplicate_name_rejected(engine):
    """Two players with the same name should be rejected."""
    p1 = Player(name="Alice", is_host=True)
    engine.add_player(p1)

    p2 = Player(name="Alice")
    with pytest.raises(ValueError, match="already taken"):
        engine.add_player(p2)


def test_duplicate_name_case_insensitive(engine):
    """Name uniqueness check should be case-insensitive."""
    p1 = Player(name="Bob", is_host=True)
    engine.add_player(p1)

    p2 = Player(name="bob")
    with pytest.raises(ValueError, match="already taken"):
        engine.add_player(p2)


def test_different_names_allowed(engine):
    """Different names should be fine."""
    p1 = Player(name="Alice", is_host=True)
    engine.add_player(p1)

    p2 = Player(name="Bob")
    engine.add_player(p2)  # should not raise
    assert len(engine.state.players) == 2
