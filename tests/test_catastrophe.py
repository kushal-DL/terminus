"""Tests for catastrophe system: damage, mitigation, application."""
import time
import pytest

from terminus.server.models import GamePhase, WorkerAllocation


@pytest.mark.asyncio
async def test_catastrophe_schedule_not_empty(playing_game):
    engine = playing_game
    assert len(engine.state.catastrophe_schedule) > 0


@pytest.mark.asyncio
async def test_trigger_catastrophe_transitions_phase(playing_game):
    engine = playing_game

    # Force elapsed time past first catastrophe scheduled_time
    if engine.state.catastrophe_schedule:
        event = engine.state.catastrophe_schedule[0]
        engine.state.game_start_time = time.time() - event.scheduled_time - 1
        await engine._tick()

        assert engine.state.phase == GamePhase.CATASTROPHE


@pytest.mark.asyncio
async def test_catastrophe_causes_damage(playing_game):
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]

    initial_pop = host.colony.population
    initial_morale = host.colony.morale
    initial_food = host.colony.resources.food
    initial_gold = host.colony.resources.gold
    initial_mat = host.colony.resources.materials

    if engine.state.catastrophe_schedule:
        event = engine.state.catastrophe_schedule[0]
        engine.state.game_start_time = time.time() - event.scheduled_time - 1
        await engine._tick()

        # Catastrophe should cause at least one type of damage
        pop_lost = host.colony.population < initial_pop
        morale_lost = host.colony.morale < initial_morale
        food_lost = host.colony.resources.food < initial_food
        gold_lost = host.colony.resources.gold < initial_gold
        mat_lost = host.colony.resources.materials < initial_mat
        assert pop_lost or morale_lost or food_lost or gold_lost or mat_lost


@pytest.mark.asyncio
async def test_defense_mitigates_catastrophe(playing_game):
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]

    # Give host strong defense
    pop = int(host.colony.population)
    host.colony.workers = WorkerAllocation(defense=pop)

    initial_pop = host.colony.population

    if engine.state.catastrophe_schedule:
        event = engine.state.catastrophe_schedule[0]
        engine.state.game_start_time = time.time() - event.scheduled_time - 1
        await engine._tick()

    # With full defense, damage should be reduced
    loss = initial_pop - host.colony.population
    assert loss < initial_pop * 0.5


@pytest.mark.asyncio
async def test_catastrophe_returns_to_playing(playing_game):
    engine = playing_game

    if engine.state.catastrophe_schedule:
        event = engine.state.catastrophe_schedule[0]
        engine.state.game_start_time = time.time() - event.scheduled_time - 1
        await engine._tick()

        assert engine.state.phase == GamePhase.CATASTROPHE

        await engine._end_catastrophe()

        # Should go back to playing (or finished if last catastrophe)
        assert engine.state.phase in (GamePhase.PLAYING, GamePhase.SCORING, GamePhase.FINISHED)
