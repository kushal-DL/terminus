"""Integration tests for Player-to-Player (P2P) Trading — Phase 3.5."""

from __future__ import annotations

import asyncio

import pytest

from terminus.server.engine import GameEngine
from terminus.server.models import (
    ActionType,
    GamePhase,
    GameSettings,
    Location,
    Player,
    Specialization,
    TradeOffer,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────


async def setup_two_player_game() -> tuple[GameEngine, str, str]:
    """Create a game engine with two players in PLAYING phase."""
    engine = GameEngine(settings=GameSettings(preset="quick"))

    host = Player(name="Player1", is_host=True)
    engine.add_player(host)
    p2 = Player(name="Player2")
    engine.add_player(p2)

    await engine.start_game(host.player_id)
    await engine.submit_setup(host.player_id, Location.COAST, Specialization.SCIENCE)
    await engine.submit_setup(p2.player_id, Location.MOUNTAIN, Specialization.TRADE)
    await engine.check_setup_complete()

    assert engine.state.phase == GamePhase.PLAYING
    assert engine.state.players[host.player_id].colony is not None
    assert engine.state.players[p2.player_id].colony is not None

    return engine, host.player_id, p2.player_id


# ─── Trade Offer Tests ────────────────────────────────────────────────────────


class TestTradeOffer:
    """Test creating trade offers."""

    @pytest.mark.asyncio
    async def test_create_offer_success(self) -> None:
        engine, p1, p2 = await setup_two_player_game()
        colony1 = engine.state.players[p1].colony

        # Give p1 some food to offer
        colony1.resources.food = 100.0

        result = await engine.handle_action(p1, ActionType.TRADE_OFFER, {
            "to_player_id": p2,
            "offer_resources": {"food": 20.0},
            "request_resources": {"gold": 10.0},
        })

        assert result["status"] == "offer_created"
        assert result["to_player"] == p2
        assert result["offer_resources"] == {"food": 20.0}
        assert result["request_resources"] == {"gold": 10.0}
        assert len(engine.state.pending_trades) == 1

    @pytest.mark.asyncio
    async def test_offer_validates_resources_available(self) -> None:
        engine, p1, p2 = await setup_two_player_game()
        colony1 = engine.state.players[p1].colony
        colony1.resources.food = 5.0  # Not enough

        with pytest.raises(ValueError, match="Insufficient food"):
            await engine.handle_action(p1, ActionType.TRADE_OFFER, {
                "to_player_id": p2,
                "offer_resources": {"food": 50.0},
                "request_resources": {"gold": 10.0},
            })

    @pytest.mark.asyncio
    async def test_offer_rejects_self_trade(self) -> None:
        engine, p1, p2 = await setup_two_player_game()

        with pytest.raises(ValueError, match="Cannot trade with yourself"):
            await engine.handle_action(p1, ActionType.TRADE_OFFER, {
                "to_player_id": p1,
                "offer_resources": {"food": 10.0},
                "request_resources": {"gold": 5.0},
            })

    @pytest.mark.asyncio
    async def test_offer_rejects_invalid_target(self) -> None:
        engine, p1, p2 = await setup_two_player_game()

        with pytest.raises(ValueError, match="Target player not found"):
            await engine.handle_action(p1, ActionType.TRADE_OFFER, {
                "to_player_id": "nonexistent",
                "offer_resources": {"food": 10.0},
                "request_resources": {"gold": 5.0},
            })

    @pytest.mark.asyncio
    async def test_offer_rejects_empty_trade(self) -> None:
        engine, p1, p2 = await setup_two_player_game()

        with pytest.raises(ValueError, match="at least one resource"):
            await engine.handle_action(p1, ActionType.TRADE_OFFER, {
                "to_player_id": p2,
                "offer_resources": {},
                "request_resources": {},
            })

    @pytest.mark.asyncio
    async def test_offer_rejects_invalid_resource(self) -> None:
        engine, p1, p2 = await setup_two_player_game()

        with pytest.raises(ValueError, match="Cannot trade resource"):
            await engine.handle_action(p1, ActionType.TRADE_OFFER, {
                "to_player_id": p2,
                "offer_resources": {"unobtanium": 10.0},
                "request_resources": {"gold": 5.0},
            })

    @pytest.mark.asyncio
    async def test_offer_rejects_negative_quantity(self) -> None:
        engine, p1, p2 = await setup_two_player_game()

        with pytest.raises(ValueError, match="Quantity must be positive"):
            await engine.handle_action(p1, ActionType.TRADE_OFFER, {
                "to_player_id": p2,
                "offer_resources": {"food": -5.0},
                "request_resources": {"gold": 5.0},
            })

    @pytest.mark.asyncio
    async def test_max_pending_offers_enforced(self) -> None:
        engine, p1, p2 = await setup_two_player_game()
        colony1 = engine.state.players[p1].colony
        colony1.resources.food = 500.0

        # Create 3 offers (the max)
        for _ in range(3):
            await engine.handle_action(p1, ActionType.TRADE_OFFER, {
                "to_player_id": p2,
                "offer_resources": {"food": 5.0},
                "request_resources": {"gold": 1.0},
            })

        # 4th should fail
        with pytest.raises(ValueError, match="Maximum 3 pending offers"):
            await engine.handle_action(p1, ActionType.TRADE_OFFER, {
                "to_player_id": p2,
                "offer_resources": {"food": 5.0},
                "request_resources": {"gold": 1.0},
            })


# ─── Trade Accept Tests ───────────────────────────────────────────────────────


class TestTradeAccept:
    """Test accepting trade offers — atomic resource swap."""

    @pytest.mark.asyncio
    async def test_accept_swaps_resources(self) -> None:
        engine, p1, p2 = await setup_two_player_game()
        c1 = engine.state.players[p1].colony
        c2 = engine.state.players[p2].colony

        c1.resources.food = 100.0
        c2.resources.gold = 50.0

        # P1 offers 20 food for 10 gold
        result = await engine.handle_action(p1, ActionType.TRADE_OFFER, {
            "to_player_id": p2,
            "offer_resources": {"food": 20.0},
            "request_resources": {"gold": 10.0},
        })
        offer_id = result["offer_id"]

        # P2 accepts
        result = await engine.handle_action(p2, ActionType.TRADE_ACCEPT, {
            "offer_id": offer_id,
        })

        assert result["status"] == "trade_completed"
        # P1: lost 20 food, gained 10 gold
        assert c1.resources.food == 80.0
        assert c1.resources.gold >= 10.0  # started with starting gold + 10
        # P2: gained 20 food, lost 10 gold
        assert c2.resources.food >= 20.0  # started with starting food + 20
        assert c2.resources.gold == 40.0

    @pytest.mark.asyncio
    async def test_accept_removes_offer_from_pending(self) -> None:
        engine, p1, p2 = await setup_two_player_game()
        c1 = engine.state.players[p1].colony
        c2 = engine.state.players[p2].colony

        c1.resources.food = 100.0
        c2.resources.gold = 50.0

        result = await engine.handle_action(p1, ActionType.TRADE_OFFER, {
            "to_player_id": p2,
            "offer_resources": {"food": 10.0},
            "request_resources": {"gold": 5.0},
        })
        offer_id = result["offer_id"]

        assert len(engine.state.pending_trades) == 1
        await engine.handle_action(p2, ActionType.TRADE_ACCEPT, {"offer_id": offer_id})
        assert len(engine.state.pending_trades) == 0

    @pytest.mark.asyncio
    async def test_accept_fails_if_acceptor_lacks_resources(self) -> None:
        engine, p1, p2 = await setup_two_player_game()
        c1 = engine.state.players[p1].colony
        c2 = engine.state.players[p2].colony

        c1.resources.food = 100.0
        c2.resources.gold = 0.0  # No gold to give

        result = await engine.handle_action(p1, ActionType.TRADE_OFFER, {
            "to_player_id": p2,
            "offer_resources": {"food": 20.0},
            "request_resources": {"gold": 50.0},
        })
        offer_id = result["offer_id"]

        with pytest.raises(ValueError, match="Insufficient gold"):
            await engine.handle_action(p2, ActionType.TRADE_ACCEPT, {"offer_id": offer_id})

    @pytest.mark.asyncio
    async def test_accept_fails_if_proposer_spent_resources(self) -> None:
        """Atomic swap: if proposer spent offered resources before acceptance, trade fails."""
        engine, p1, p2 = await setup_two_player_game()
        c1 = engine.state.players[p1].colony
        c2 = engine.state.players[p2].colony

        c1.resources.food = 25.0
        c2.resources.gold = 50.0

        result = await engine.handle_action(p1, ActionType.TRADE_OFFER, {
            "to_player_id": p2,
            "offer_resources": {"food": 20.0},
            "request_resources": {"gold": 5.0},
        })
        offer_id = result["offer_id"]

        # P1 spends food before P2 accepts
        c1.resources.food = 5.0

        with pytest.raises(ValueError, match="Proposer no longer has sufficient"):
            await engine.handle_action(p2, ActionType.TRADE_ACCEPT, {"offer_id": offer_id})

        # Offer should be cleaned up
        assert offer_id not in engine.state.pending_trades

    @pytest.mark.asyncio
    async def test_accept_fails_for_wrong_player(self) -> None:
        engine, p1, p2 = await setup_two_player_game()
        c1 = engine.state.players[p1].colony
        c1.resources.food = 100.0

        result = await engine.handle_action(p1, ActionType.TRADE_OFFER, {
            "to_player_id": p2,
            "offer_resources": {"food": 10.0},
            "request_resources": {"gold": 5.0},
        })
        offer_id = result["offer_id"]

        # P1 tries to accept their own offer (should fail)
        with pytest.raises(ValueError, match="not addressed to you"):
            await engine.handle_action(p1, ActionType.TRADE_ACCEPT, {"offer_id": offer_id})

    @pytest.mark.asyncio
    async def test_accept_nonexistent_offer(self) -> None:
        engine, p1, p2 = await setup_two_player_game()

        with pytest.raises(ValueError, match="not found or expired"):
            await engine.handle_action(p2, ActionType.TRADE_ACCEPT, {"offer_id": "fake-id"})

    @pytest.mark.asyncio
    async def test_multi_resource_trade(self) -> None:
        """Trade can involve multiple resources on both sides."""
        engine, p1, p2 = await setup_two_player_game()
        c1 = engine.state.players[p1].colony
        c2 = engine.state.players[p2].colony

        c1.resources.food = 100.0
        c1.resources.materials = 100.0
        c2.resources.gold = 50.0
        c2.resources.knowledge = 30.0

        result = await engine.handle_action(p1, ActionType.TRADE_OFFER, {
            "to_player_id": p2,
            "offer_resources": {"food": 10.0, "materials": 5.0},
            "request_resources": {"gold": 8.0, "knowledge": 3.0},
        })
        offer_id = result["offer_id"]

        await engine.handle_action(p2, ActionType.TRADE_ACCEPT, {"offer_id": offer_id})

        assert c1.resources.food == 90.0
        assert c1.resources.materials == 95.0
        assert c2.resources.gold == 42.0
        assert c2.resources.knowledge == 27.0


# ─── Trade Decline Tests ──────────────────────────────────────────────────────


class TestTradeDecline:
    """Test declining trade offers."""

    @pytest.mark.asyncio
    async def test_decline_removes_offer(self) -> None:
        engine, p1, p2 = await setup_two_player_game()
        c1 = engine.state.players[p1].colony
        c1.resources.food = 100.0

        result = await engine.handle_action(p1, ActionType.TRADE_OFFER, {
            "to_player_id": p2,
            "offer_resources": {"food": 10.0},
            "request_resources": {"gold": 5.0},
        })
        offer_id = result["offer_id"]

        result = await engine.handle_action(p2, ActionType.TRADE_DECLINE, {"offer_id": offer_id})
        assert result["status"] == "trade_declined"
        assert len(engine.state.pending_trades) == 0

    @pytest.mark.asyncio
    async def test_decline_fails_for_wrong_player(self) -> None:
        engine, p1, p2 = await setup_two_player_game()
        c1 = engine.state.players[p1].colony
        c1.resources.food = 100.0

        result = await engine.handle_action(p1, ActionType.TRADE_OFFER, {
            "to_player_id": p2,
            "offer_resources": {"food": 10.0},
            "request_resources": {"gold": 5.0},
        })
        offer_id = result["offer_id"]

        with pytest.raises(ValueError, match="not addressed to you"):
            await engine.handle_action(p1, ActionType.TRADE_DECLINE, {"offer_id": offer_id})


# ─── Trade Expiry Tests ───────────────────────────────────────────────────────


class TestTradeExpiry:
    """Test automatic expiry of trade offers."""

    @pytest.mark.asyncio
    async def test_offers_expire_after_tick_limit(self) -> None:
        engine, p1, p2 = await setup_two_player_game()
        c1 = engine.state.players[p1].colony
        c1.resources.food = 100.0

        result = await engine.handle_action(p1, ActionType.TRADE_OFFER, {
            "to_player_id": p2,
            "offer_resources": {"food": 10.0},
            "request_resources": {"gold": 5.0},
        })
        offer_id = result["offer_id"]
        assert len(engine.state.pending_trades) == 1

        # Advance ticks past expiry (default 30 ticks)
        for _ in range(31):
            await engine._tick()

        assert len(engine.state.pending_trades) == 0

    @pytest.mark.asyncio
    async def test_accept_expired_offer_fails(self) -> None:
        engine, p1, p2 = await setup_two_player_game()
        c1 = engine.state.players[p1].colony
        c2 = engine.state.players[p2].colony
        c1.resources.food = 100.0
        c2.resources.gold = 50.0

        result = await engine.handle_action(p1, ActionType.TRADE_OFFER, {
            "to_player_id": p2,
            "offer_resources": {"food": 10.0},
            "request_resources": {"gold": 5.0},
        })
        offer_id = result["offer_id"]

        # Manually set expiry to current tick (simulate expired)
        engine.state.pending_trades[offer_id].expires_tick = engine.state.elapsed_ticks

        with pytest.raises(ValueError, match="expired"):
            await engine.handle_action(p2, ActionType.TRADE_ACCEPT, {"offer_id": offer_id})


# ─── Player State Exposure Tests ──────────────────────────────────────────────


class TestTradeInPlayerState:
    """Test that trades are visible in get_player_state()."""

    @pytest.mark.asyncio
    async def test_incoming_offers_visible(self) -> None:
        engine, p1, p2 = await setup_two_player_game()
        c1 = engine.state.players[p1].colony
        c1.resources.food = 100.0

        await engine.handle_action(p1, ActionType.TRADE_OFFER, {
            "to_player_id": p2,
            "offer_resources": {"food": 10.0},
            "request_resources": {"gold": 5.0},
        })

        state = engine.get_player_state(p2)
        assert "incoming_trade_offers" in state
        assert len(state["incoming_trade_offers"]) == 1
        assert state["incoming_trade_offers"][0]["from_player_id"] == p1

    @pytest.mark.asyncio
    async def test_outgoing_offers_visible(self) -> None:
        engine, p1, p2 = await setup_two_player_game()
        c1 = engine.state.players[p1].colony
        c1.resources.food = 100.0

        await engine.handle_action(p1, ActionType.TRADE_OFFER, {
            "to_player_id": p2,
            "offer_resources": {"food": 10.0},
            "request_resources": {"gold": 5.0},
        })

        state = engine.get_player_state(p1)
        assert "outgoing_trade_offers" in state
        assert len(state["outgoing_trade_offers"]) == 1
        assert state["outgoing_trade_offers"][0]["to_player_id"] == p2

    @pytest.mark.asyncio
    async def test_no_cross_visibility(self) -> None:
        """P1 should not see P2's incoming offers as their own."""
        engine, p1, p2 = await setup_two_player_game()
        c1 = engine.state.players[p1].colony
        c1.resources.food = 100.0

        await engine.handle_action(p1, ActionType.TRADE_OFFER, {
            "to_player_id": p2,
            "offer_resources": {"food": 10.0},
            "request_resources": {"gold": 5.0},
        })

        state_p1 = engine.get_player_state(p1)
        assert len(state_p1["incoming_trade_offers"]) == 0
        assert len(state_p1["outgoing_trade_offers"]) == 1

        state_p2 = engine.get_player_state(p2)
        assert len(state_p2["incoming_trade_offers"]) == 1
        assert len(state_p2["outgoing_trade_offers"]) == 0
