"""Tests for Sprint 7: WS event improvements + client polish."""
import time
import pytest

from terminus.server.models import Building, GamePhase


# ─── F1: Per-player catastrophe warning with watchtower hints ────────────────

@pytest.mark.asyncio
async def test_catastrophe_warning_sent_per_player(playing_game):
    """Warning should be sent via _emit_to_player, not broadcast."""
    engine = playing_game
    sent_events: list[tuple[str, str, dict]] = []

    async def mock_player_broadcast(player_id, event, data):
        sent_events.append((player_id, event, data))

    async def mock_broadcast(event, data):
        pass  # should NOT receive catastrophe_warning

    engine.set_broadcast(mock_broadcast, mock_player_broadcast)

    if engine.state.catastrophe_schedule:
        event = engine.state.catastrophe_schedule[0]
        # Set time to be within warning window but before trigger
        from terminus.config import CATASTROPHE_WARNING_SECONDS
        engine.state.game_start_time = time.time() - event.scheduled_time + CATASTROPHE_WARNING_SECONDS - 5
        await engine._tick()

        warnings = [(pid, e, d) for pid, e, d in sent_events if e == "catastrophe_warning"]
        # Should have one warning per player
        assert len(warnings) == len(engine.state.players)
        # Each should have seconds_until
        for pid, _, data in warnings:
            assert "seconds_until" in data
            assert pid in engine.state.players


@pytest.mark.asyncio
async def test_watchtower_hint_level1(playing_game):
    """Level 1 watchtower reveals catastrophe category."""
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]

    # Give host a level-1 watchtower
    host.colony.buildings.append(Building(building_type="watchtower", level=1))

    sent_events: list[tuple[str, str, dict]] = []

    async def mock_player_broadcast(player_id, event, data):
        sent_events.append((player_id, event, data))

    async def mock_broadcast(event, data):
        pass

    engine.set_broadcast(mock_broadcast, mock_player_broadcast)

    if engine.state.catastrophe_schedule:
        event = engine.state.catastrophe_schedule[0]
        from terminus.config import CATASTROPHE_WARNING_SECONDS
        engine.state.game_start_time = time.time() - event.scheduled_time + CATASTROPHE_WARNING_SECONDS - 5
        await engine._tick()

        host_warnings = [(pid, e, d) for pid, e, d in sent_events
                         if e == "catastrophe_warning" and pid == host.player_id]
        assert len(host_warnings) == 1
        _, _, data = host_warnings[0]
        assert "hint_category" in data
        assert "hint_text" in data
        # Level 1 should NOT have type or severity
        assert "hint_type" not in data
        assert "hint_severity" not in data


@pytest.mark.asyncio
async def test_watchtower_hint_level3(playing_game):
    """Level 3 watchtower reveals category, type, and severity."""
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]

    host.colony.buildings.append(Building(building_type="watchtower", level=3))

    sent_events: list[tuple[str, str, dict]] = []

    async def mock_player_broadcast(player_id, event, data):
        sent_events.append((player_id, event, data))

    async def mock_broadcast(event, data):
        pass

    engine.set_broadcast(mock_broadcast, mock_player_broadcast)

    if engine.state.catastrophe_schedule:
        event = engine.state.catastrophe_schedule[0]
        from terminus.config import CATASTROPHE_WARNING_SECONDS
        engine.state.game_start_time = time.time() - event.scheduled_time + CATASTROPHE_WARNING_SECONDS - 5
        await engine._tick()

        host_warnings = [(pid, e, d) for pid, e, d in sent_events
                         if e == "catastrophe_warning" and pid == host.player_id]
        assert len(host_warnings) == 1
        _, _, data = host_warnings[0]
        assert "hint_category" in data
        assert "hint_type" in data
        assert "hint_severity" in data
        assert "hint_text" in data


@pytest.mark.asyncio
async def test_no_watchtower_no_hints(playing_game):
    """Player without watchtower gets no hints in warning."""
    engine = playing_game
    p2 = [p for p in engine.state.players.values() if not p.is_host][0]
    # Ensure p2 has no watchtower
    p2.colony.buildings = [b for b in p2.colony.buildings if b.building_type != "watchtower"]

    sent_events: list[tuple[str, str, dict]] = []

    async def mock_player_broadcast(player_id, event, data):
        sent_events.append((player_id, event, data))

    async def mock_broadcast(event, data):
        pass

    engine.set_broadcast(mock_broadcast, mock_player_broadcast)

    if engine.state.catastrophe_schedule:
        event = engine.state.catastrophe_schedule[0]
        from terminus.config import CATASTROPHE_WARNING_SECONDS
        engine.state.game_start_time = time.time() - event.scheduled_time + CATASTROPHE_WARNING_SECONDS - 5
        await engine._tick()

        p2_warnings = [(pid, e, d) for pid, e, d in sent_events
                       if e == "catastrophe_warning" and pid == p2.player_id]
        assert len(p2_warnings) == 1
        _, _, data = p2_warnings[0]
        assert "hint_category" not in data
        assert "hint_type" not in data
        assert "hint_text" not in data


# ─── F2: Individualized catastrophe results ──────────────────────────────────

@pytest.mark.asyncio
async def test_catastrophe_results_per_player(playing_game):
    """Each player should receive only their own results via _emit_to_player."""
    engine = playing_game
    sent_events: list[tuple[str, str, dict]] = []

    async def mock_player_broadcast(player_id, event, data):
        sent_events.append((player_id, event, data))

    async def mock_broadcast(event, data):
        # catastrophe_started still goes to all — that's fine
        sent_events.append(("__all__", event, data))

    engine.set_broadcast(mock_broadcast, mock_player_broadcast)

    if engine.state.catastrophe_schedule:
        event = engine.state.catastrophe_schedule[0]
        engine.state.game_start_time = time.time() - event.scheduled_time - 1
        await engine._tick()

        results_events = [(pid, e, d) for pid, e, d in sent_events if e == "catastrophe_results"]
        # Should have one per player, not a single broadcast
        player_ids = {pid for pid, _, _ in results_events}
        assert player_ids == set(engine.state.players.keys())

        # Each player should only see their own data
        for pid, _, data in results_events:
            assert pid in data["results"]
            assert len(data["results"]) == 1  # only own results


@pytest.mark.asyncio
async def test_catastrophe_results_include_averages(playing_game):
    """Results should include avg_population_lost and avg_food_lost."""
    engine = playing_game
    sent_events: list[tuple[str, str, dict]] = []

    async def mock_player_broadcast(player_id, event, data):
        sent_events.append((player_id, event, data))

    async def mock_broadcast(event, data):
        pass

    engine.set_broadcast(mock_broadcast, mock_player_broadcast)

    if engine.state.catastrophe_schedule:
        event = engine.state.catastrophe_schedule[0]
        engine.state.game_start_time = time.time() - event.scheduled_time - 1
        await engine._tick()

        results_events = [(pid, e, d) for pid, e, d in sent_events if e == "catastrophe_results"]
        assert len(results_events) > 0
        for pid, _, data in results_events:
            player_result = data["results"][pid]
            assert "avg_population_lost" in player_result
            assert "avg_food_lost" in player_result
