"""Tests for market system: buy/sell, stock, pricing."""
import pytest

from terminus.server.models import ActionType


@pytest.mark.asyncio
async def test_buy_deducts_gold_adds_resource(playing_game):
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]

    # Give enough gold
    host.colony.resources.gold = 1000
    food_before = host.colony.resources.food
    gold_before = host.colony.resources.gold

    await engine.handle_action(
        host.player_id, ActionType.TRADE_BUY, {"resource": "food", "quantity": 5}
    )

    assert host.colony.resources.food > food_before
    assert host.colony.resources.gold < gold_before


@pytest.mark.asyncio
async def test_sell_adds_gold_deducts_resource(playing_game):
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]

    # Ensure we have food to sell
    host.colony.resources.food = 200
    host.colony.resources.gold = 50
    food_before = host.colony.resources.food
    gold_before = host.colony.resources.gold

    await engine.handle_action(
        host.player_id, ActionType.TRADE_SELL, {"resource": "food", "quantity": 5}
    )

    assert host.colony.resources.food < food_before
    assert host.colony.resources.gold > gold_before


@pytest.mark.asyncio
async def test_cannot_buy_insufficient_gold(playing_game):
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]

    host.colony.resources.gold = 0

    with pytest.raises(ValueError):
        await engine.handle_action(
            host.player_id, ActionType.TRADE_BUY, {"resource": "food", "quantity": 100}
        )


@pytest.mark.asyncio
async def test_cannot_sell_more_than_owned(playing_game):
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]

    host.colony.resources.food = 0

    with pytest.raises(ValueError):
        await engine.handle_action(
            host.player_id, ActionType.TRADE_SELL, {"resource": "food", "quantity": 10}
        )


@pytest.mark.asyncio
async def test_market_stock_decreases_on_buy(playing_game):
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]
    host.colony.resources.gold = 5000

    stock_before = engine.state.market.stock.get("food", 100)

    await engine.handle_action(
        host.player_id, ActionType.TRADE_BUY, {"resource": "food", "quantity": 5}
    )

    stock_after = engine.state.market.stock.get("food", 100)
    assert stock_after < stock_before


@pytest.mark.asyncio
async def test_sell_gives_revenue(playing_game):
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]
    host.colony.resources.food = 500
    host.colony.resources.gold = 0

    result = await engine.handle_action(
        host.player_id, ActionType.TRADE_SELL, {"resource": "food", "quantity": 5}
    )

    assert result["status"] == "sold"
    assert result["revenue"] > 0
    assert host.colony.resources.gold > 0


@pytest.mark.asyncio
async def test_spec_discount_for_trade(playing_game):
    engine = playing_game
    # Find the trade specialist (host has TRADE)
    host = [p for p in engine.state.players.values() if p.is_host][0]
    p2 = [p for p in engine.state.players.values() if not p.is_host][0]

    # Both get same gold
    host.colony.resources.gold = 1000
    p2.colony.resources.gold = 1000

    gold_before_host = host.colony.resources.gold
    gold_before_p2 = p2.colony.resources.gold

    await engine.handle_action(
        host.player_id, ActionType.TRADE_BUY, {"resource": "materials", "quantity": 5}
    )
    await engine.handle_action(
        p2.player_id, ActionType.TRADE_BUY, {"resource": "materials", "quantity": 5}
    )

    gold_spent_host = gold_before_host - host.colony.resources.gold
    gold_spent_p2 = gold_before_p2 - p2.colony.resources.gold

    # Trade specialist should spend less
    assert gold_spent_host <= gold_spent_p2
