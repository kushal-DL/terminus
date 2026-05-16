"""Sprint 8 tests — Player Leave/Kick, Stats, Market Delta, Score Snapshots."""

from __future__ import annotations

import pytest
import pytest_asyncio

from terminus.server.engine import GameEngine
from terminus.server.models import (
    Colony,
    GamePhase,
    GameSettings,
    Location,
    Player,
    Specialization,
)


def _make_engine() -> GameEngine:
    return GameEngine(settings=GameSettings())


def _add_player(engine: GameEngine, name: str, is_host: bool = False) -> Player:
    p = Player(name=name, is_host=is_host)
    p.colony = Colony(name=f"{name}'s Colony")
    engine.add_player(p)
    return p


# ──── A: Player Leave / Remove ──────────────────────────────────────────────


class TestRemovePlayer:
    def test_remove_in_lobby_fully_deletes(self):
        engine = _make_engine()
        p1 = _add_player(engine, "Alice", is_host=True)
        p2 = _add_player(engine, "Bob")
        result = engine.remove_player(p2.player_id)
        assert result is not None
        assert result["removed"] is True
        assert p2.player_id not in engine.state.players
        assert result["player_count"] == 1

    def test_remove_host_reassigns(self):
        engine = _make_engine()
        p1 = _add_player(engine, "Alice", is_host=True)
        p2 = _add_player(engine, "Bob")
        result = engine.remove_player(p1.player_id)
        assert result is not None
        assert result["new_host"] == "Bob"
        assert p2.is_host is True
        assert p1.player_id not in engine.state.players

    def test_remove_in_playing_soft_disconnects(self):
        engine = _make_engine()
        p1 = _add_player(engine, "Alice", is_host=True)
        engine.state.phase = GamePhase.PLAYING
        result = engine.remove_player(p1.player_id)
        assert result is not None
        assert result["removed"] is False
        assert p1.player_id in engine.state.players
        assert p1.connected is False

    def test_remove_nonexistent_returns_none(self):
        engine = _make_engine()
        assert engine.remove_player("fake-id") is None

    def test_remove_last_player_no_host(self):
        engine = _make_engine()
        p1 = _add_player(engine, "Alice", is_host=True)
        result = engine.remove_player(p1.player_id)
        assert result is not None
        assert result["removed"] is True
        assert result["new_host"] is None
        assert len(engine.state.players) == 0


# ──── B: Stat Tracking ──────────────────────────────────────────────────────


class TestStatTracking:
    def test_colony_has_stat_fields(self):
        c = Colony(name="Test")
        assert c.buildings_built == 0
        assert c.trades_completed == 0
        assert c.total_trade_volume == 0
        assert c.catastrophes_survived == 0
        assert c.peak_population > 0  # starts at STARTING_POPULATION

    def test_trade_buy_increments_stats(self):
        engine = _make_engine()
        p = _add_player(engine, "Alice", is_host=True)
        p.colony.location = Location.PLAINS
        p.colony.specialization = Specialization.AGRICULTURE
        engine.state.phase = GamePhase.PLAYING
        # Seed market
        engine.state.market.prices = {"food": 1.0, "materials": 1.0, "knowledge": 1.0, "gold": 1.0}
        engine.state.market.stock = {"food": 100, "materials": 100, "knowledge": 100, "gold": 100}
        p.colony.resources.gold = 1000

        engine._action_trade_buy(p.colony, {"resource": "food", "quantity": 10}, p.player_id, p.name)
        assert p.colony.trades_completed == 1
        assert p.colony.total_trade_volume > 0

    def test_trade_sell_increments_stats(self):
        engine = _make_engine()
        p = _add_player(engine, "Alice", is_host=True)
        p.colony.location = Location.PLAINS
        p.colony.specialization = Specialization.AGRICULTURE
        engine.state.phase = GamePhase.PLAYING
        engine.state.market.prices = {"food": 1.0}
        engine.state.market.stock = {"food": 100}
        p.colony.resources.food = 100

        engine._action_trade_sell(p.colony, {"resource": "food", "quantity": 5}, p.player_id, p.name)
        assert p.colony.trades_completed == 1
        assert p.colony.total_trade_volume > 0

    def test_peak_population_tracked_in_tick(self):
        engine = _make_engine()
        p = _add_player(engine, "Alice", is_host=True)
        p.colony.location = Location.PLAINS
        p.colony.specialization = Specialization.AGRICULTURE
        initial_pop = p.colony.population
        p.colony.population = 30
        engine._process_colony_tick(p.colony)
        assert p.colony.peak_population >= 30

    def test_scores_include_stats(self):
        engine = _make_engine()
        p = _add_player(engine, "Alice", is_host=True)
        p.colony.location = Location.PLAINS
        p.colony.specialization = Specialization.AGRICULTURE
        p.colony.buildings_built = 3
        p.colony.trades_completed = 5
        p.colony.total_trade_volume = 100.5
        p.colony.catastrophes_survived = 2
        p.colony.peak_population = 40

        scores = engine._calculate_scores()
        assert len(scores) == 1
        s = scores[0]
        assert s["buildings_built"] == 3
        assert s["trades_completed"] == 5
        assert s["total_trade_volume"] == 100.5
        assert s["catastrophes_survived"] == 2
        assert s["peak_population"] == 40


# ──── B5: Score History Snapshots ────────────────────────────────────────────


class TestScoreHistory:
    def test_gamestate_has_score_history(self):
        engine = _make_engine()
        assert hasattr(engine.state, "score_history")
        assert engine.state.score_history == []


# ──── C1: Market Price Changes Delta ────────────────────────────────────────


class TestMarketPriceChanges:
    @pytest.mark.asyncio
    async def test_refresh_market_emits_price_changes(self):
        engine = _make_engine()
        emissions: list = []

        async def capture(event: str, data: dict):
            emissions.append((event, data))

        engine.set_broadcast(capture)
        # Set initial prices
        engine.state.market.prices = {"food": 10.0, "materials": 5.0}
        await engine._refresh_market()

        assert len(emissions) == 1
        event_name, data = emissions[0]
        assert event_name == "market_update"
        assert "price_changes" in data
        assert isinstance(data["price_changes"], dict)


# ──── C2: Location Flavor Text ──────────────────────────────────────────────


class TestLocationFlavor:
    def test_catastrophes_have_location_flavor(self):
        from terminus.data.loader import get_catastrophes
        cats = get_catastrophes()
        for cat in cats:
            assert "location_flavor" in cat, f"{cat['id']} missing location_flavor"
            assert isinstance(cat["location_flavor"], dict)
            assert len(cat["location_flavor"]) == 5  # all 5 locations


# ──── D1: Connection Lost Screen ────────────────────────────────────────────


class TestConnectionLostScreen:
    def test_max_auto_retries_constant(self):
        from terminus.client.screens.connection_lost import MAX_AUTO_RETRIES
        assert MAX_AUTO_RETRIES == 5

    def test_screen_has_retry_task_attribute(self):
        from terminus.client.screens.connection_lost import ConnectionLostScreen
        screen = ConnectionLostScreen()
        assert screen._attempt == 0
        assert screen._retrying is False
