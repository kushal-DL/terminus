"""Fuzz tests for input validation — malformed payloads should be rejected cleanly."""
import pytest
from pydantic import ValidationError

from terminus.server.models import (
    BuildAction,
    TradeBuyAction,
    TradeSellAction,
    AllocateWorkersAction,
    UpgradeAction,
    DemolishAction,
    RepairAction,
    GameActionRequest,
    ActionType,
)


class TestBuildActionValidation:
    def test_missing_building_type(self):
        with pytest.raises(ValidationError):
            BuildAction()

    def test_valid(self):
        a = BuildAction(building_type="farm")
        assert a.building_type == "farm"


class TestTradeValidation:
    def test_buy_zero_quantity(self):
        with pytest.raises(ValidationError):
            TradeBuyAction(resource="food", quantity=0)

    def test_buy_negative_quantity(self):
        with pytest.raises(ValidationError):
            TradeBuyAction(resource="food", quantity=-1)

    def test_sell_zero_quantity(self):
        with pytest.raises(ValidationError):
            TradeSellAction(resource="food", quantity=0)

    def test_valid_buy(self):
        a = TradeBuyAction(resource="food", quantity=5)
        assert a.quantity == 5

    def test_valid_sell(self):
        a = TradeSellAction(resource="materials", quantity=3)
        assert a.resource == "materials"


class TestAllocateWorkersValidation:
    def test_missing_allocation(self):
        with pytest.raises(ValidationError):
            AllocateWorkersAction()

    def test_valid(self):
        a = AllocateWorkersAction(allocation={"farmers": 3, "miners": 2})
        assert a.allocation["farmers"] == 3


class TestGameActionRequest:
    def test_unknown_action_type(self):
        with pytest.raises(ValidationError):
            GameActionRequest(action_type="hack_server", payload={})

    def test_valid_action(self):
        r = GameActionRequest(action_type=ActionType.BUILD, payload={"building_type": "farm"})
        assert r.action_type == ActionType.BUILD

    def test_empty_payload_default(self):
        r = GameActionRequest(action_type=ActionType.BUILD)
        assert r.payload == {}


class TestMalformedPayloads:
    """Ensure various malformed inputs don't crash the validators."""

    @pytest.mark.parametrize("payload", [
        {"building_type": ""},     # empty string
        {"building_type": "x" * 1000},  # very long string
    ])
    def test_build_edge_cases(self, payload):
        a = BuildAction(**payload)
        assert isinstance(a.building_type, str)

    def test_build_rejects_non_string(self):
        with pytest.raises(ValidationError):
            BuildAction(building_type=12345)

    @pytest.mark.parametrize("payload", [
        {"resource": "food", "quantity": "not_a_number"},
        {"resource": "food", "quantity": 1.5},
        {"resource": "food"},  # missing quantity — has no default
    ])
    def test_trade_bad_quantity(self, payload):
        # quantity must be int > 0
        with pytest.raises(ValidationError):
            TradeBuyAction(**payload)
