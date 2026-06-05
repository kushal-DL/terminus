"""Tests for Phase 2: Built-in Opponents."""

from __future__ import annotations

import pytest

from terminus.benchmark.opponents import (
    AGENT_REGISTRY,
    AdversarialAgent,
    BalancedAgent,
    BuiltInAgent,
    GreedyAgent,
    RandomAgent,
    RushAgent,
    TurtleAgent,
    get_agent,
)
from terminus.benchmark.schemas import (
    AvailableAction,
    BenchmarkActionType,
    BenchmarkGameState,
    BenchmarkWorkerAllocation,
    BuildingState,
    CatastropheWarning,
    MarketPrices,
    ResourceState,
    TradeOfferInfo,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────


def _make_state(
    turn: int = 10,
    population: int = 30,
    food: float = 100,
    materials: float = 80,
    knowledge: float = 20,
    gold: float = 50,
    buildings: list[BuildingState] | None = None,
    catastrophe: CatastropheWarning | None = None,
    incoming_trades: list[TradeOfferInfo] | None = None,
    outgoing_trades: list[TradeOfferInfo] | None = None,
) -> BenchmarkGameState:
    return BenchmarkGameState(
        turn=turn,
        max_turns=100,
        population=population,
        population_cap=50,
        morale=1.0,
        resources=ResourceState(food=food, materials=materials, knowledge=knowledge, gold=gold),
        workers=BenchmarkWorkerAllocation(farming=15, mining=6, research=3, construction=3, defense=2, medicine=1),
        buildings=buildings or [],
        market_prices=MarketPrices(food=2.0, materials=3.0, knowledge=5.0),
        catastrophe_warning=catastrophe,
        incoming_trade_offers=incoming_trades or [],
        outgoing_trade_offers=outgoing_trades or [],
    )


def _make_actions(*action_types: str) -> list[AvailableAction]:
    """Create available actions for given types."""
    actions = []
    for at in action_types:
        hint = None
        if at == "BUILD":
            hint = {"building_type": "farm"}
        elif at == "UPGRADE":
            hint = {"building_type": "farm"}
        actions.append(AvailableAction(action_type=at, description=f"Do {at}", params_hint=hint))
    return actions


def _make_build_actions(*building_types: str) -> list[AvailableAction]:
    """Create BUILD available actions for specific building types."""
    return [
        AvailableAction(action_type="BUILD", description=f"Build {bt}", params_hint={"building_type": bt})
        for bt in building_types
    ]


def _make_trade_offer(
    offer_id: str = "trade1",
    offer_resources: dict | None = None,
    request_resources: dict | None = None,
) -> TradeOfferInfo:
    return TradeOfferInfo(
        offer_id=offer_id,
        from_player="player_0",
        to_player="player_1",
        offer_resources=offer_resources or {"food": 20.0},
        request_resources=request_resources or {"materials": 20.0},
        ticks_remaining=20,
    )


# ─── Registry Tests ───────────────────────────────────────────────────────────


class TestAgentRegistry:
    def test_all_archetypes_registered(self):
        expected = {"random", "greedy", "balanced", "rush", "turtle", "adversarial"}
        assert set(AGENT_REGISTRY.keys()) == expected

    def test_get_agent_returns_correct_type(self):
        assert isinstance(get_agent("random"), RandomAgent)
        assert isinstance(get_agent("greedy"), GreedyAgent)
        assert isinstance(get_agent("balanced"), BalancedAgent)
        assert isinstance(get_agent("rush"), RushAgent)
        assert isinstance(get_agent("turtle"), TurtleAgent)
        assert isinstance(get_agent("adversarial"), AdversarialAgent)

    def test_get_agent_invalid_raises(self):
        with pytest.raises(ValueError, match="Unknown agent archetype"):
            get_agent("nonexistent")

    def test_get_agent_with_seed(self):
        a1 = get_agent("random", seed=123)
        a2 = get_agent("random", seed=123)
        assert a1.seed == a2.seed == 123

    def test_all_agents_are_builtin_agent(self):
        for archetype in AGENT_REGISTRY:
            agent = get_agent(archetype)
            assert isinstance(agent, BuiltInAgent)


# ─── Base Class Tests ─────────────────────────────────────────────────────────


class TestBuiltInAgentBase:
    def test_get_setup_choices(self):
        agent = get_agent("balanced")
        choices = agent.get_setup_choices()
        assert "location" in choices
        assert "specialization" in choices

    def test_get_worker_allocation_sums_to_population(self):
        agent = get_agent("balanced")
        state = _make_state(population=47)
        ratios = {"farming": 0.4, "mining": 0.2, "research": 0.2, "construction": 0.1, "defense": 0.05, "medicine": 0.05}
        alloc = agent.get_worker_allocation(state, ratios)
        assert sum(alloc.values()) == 47

    def test_get_worker_allocation_zero_population(self):
        agent = get_agent("balanced")
        state = _make_state(population=0)
        ratios = {"farming": 0.5, "mining": 0.5}
        alloc = agent.get_worker_allocation(state, ratios)
        assert sum(alloc.values()) == 0

    def test_score_trade_fairness_fair_trade(self):
        agent = get_agent("balanced")
        state = _make_state()
        # Equal value trade at market prices: food@2 × 10 = 20, materials@3 × 6.67 ≈ 20
        offer = _make_trade_offer(offer_resources={"food": 10.0}, request_resources={"food": 10.0})
        fairness = agent.score_trade_fairness(offer, state)
        assert abs(fairness) < 0.01  # Approximately fair

    def test_score_trade_fairness_unfair(self):
        agent = get_agent("balanced")
        state = _make_state()
        # Offer 5 food (value 10), request 10 knowledge (value 50) — bad for us
        offer = _make_trade_offer(offer_resources={"food": 5.0}, request_resources={"knowledge": 10.0})
        fairness = agent.score_trade_fairness(offer, state)
        assert fairness < -0.5

    def test_make_pass_action(self):
        agent = get_agent("random")
        action = agent.make_pass_action()
        assert action.action == BenchmarkActionType.PASS

    def test_has_action(self):
        agent = get_agent("random")
        actions = _make_actions("BUILD", "TRADE_SELL")
        assert agent.has_action(actions, "BUILD")
        assert not agent.has_action(actions, "REPAIR")

    def test_get_affordable_buildings(self):
        agent = get_agent("balanced")
        actions = _make_build_actions("farm", "housing", "library")
        buildings = agent.get_affordable_buildings(actions)
        assert set(buildings) == {"farm", "housing", "library"}


# ─── Random Agent Tests ───────────────────────────────────────────────────────


class TestRandomAgent:
    def test_deterministic_with_same_seed(self):
        state = _make_state()
        actions = _make_actions("BUILD", "ALLOCATE_WORKERS", "TRADE_SELL", "PASS")

        a1 = RandomAgent(seed=42)
        a2 = RandomAgent(seed=42)
        r1 = a1.choose_action(state, actions, turn=5)
        r2 = a2.choose_action(state, actions, turn=5)
        assert r1.action == r2.action

    def test_different_seed_may_differ(self):
        state = _make_state()
        actions = _make_actions("BUILD", "ALLOCATE_WORKERS", "TRADE_SELL", "TRADE_BUY", "REPAIR", "PASS")

        # With enough actions, different seeds should eventually produce different results
        a1 = RandomAgent(seed=1)
        a2 = RandomAgent(seed=9999)
        results1 = [a1.choose_action(state, actions, turn=i).action for i in range(1, 20)]
        results2 = [a2.choose_action(state, actions, turn=i).action for i in range(1, 20)]
        assert results1 != results2

    def test_returns_valid_action_type(self):
        state = _make_state()
        actions = _make_actions("BUILD", "TRADE_SELL", "PASS")
        agent = RandomAgent(seed=42)
        result = agent.choose_action(state, actions, turn=5)
        assert result.action in (BenchmarkActionType.BUILD, BenchmarkActionType.TRADE_SELL, BenchmarkActionType.PASS)

    def test_empty_actions_returns_pass(self):
        state = _make_state()
        agent = RandomAgent(seed=42)
        result = agent.choose_action(state, [], turn=5)
        assert result.action == BenchmarkActionType.PASS

    def test_evaluate_trade_is_random(self):
        agent = RandomAgent(seed=42)
        state = _make_state()
        offer = _make_trade_offer()
        # Run many evaluations — should get mix of accept/decline
        results = [agent.evaluate_trade(offer, state, turn=i) for i in range(1, 50)]
        assert "accept" in results
        assert "decline" in results

    def test_worker_allocation_sums_to_population(self):
        agent = RandomAgent(seed=42)
        state = _make_state(population=25)
        actions = _make_actions("ALLOCATE_WORKERS")
        result = agent.choose_action(state, actions, turn=5)
        assert result.action == BenchmarkActionType.ALLOCATE_WORKERS
        alloc = result.params.get("allocation", {})
        assert sum(alloc.values()) == 25


# ─── Greedy Agent Tests ───────────────────────────────────────────────────────


class TestGreedyAgent:
    def test_picks_highest_value_action(self):
        state = _make_state(food=200)
        # BUILD (farm) has high value, PASS has 0
        actions = _make_build_actions("farm") + _make_actions("PASS")
        agent = GreedyAgent(seed=42)
        result = agent.choose_action(state, actions, turn=10)
        assert result.action == BenchmarkActionType.BUILD

    def test_prefers_sell_when_surplus(self):
        state = _make_state(food=300)
        actions = _make_actions("TRADE_SELL", "PASS")
        agent = GreedyAgent(seed=42)
        result = agent.choose_action(state, actions, turn=10)
        assert result.action == BenchmarkActionType.TRADE_SELL

    def test_rejects_unfair_trade(self):
        agent = GreedyAgent(seed=42)
        state = _make_state()
        # Offer 5 food (value=10), request 10 knowledge (value=50) — terrible deal
        offer = _make_trade_offer(offer_resources={"food": 5.0}, request_resources={"knowledge": 10.0})
        assert agent.evaluate_trade(offer, state, turn=10) == "decline"

    def test_accepts_favorable_trade(self):
        agent = GreedyAgent(seed=42)
        state = _make_state()
        # Offer 30 knowledge (value=150), request 10 food (value=20) — great deal
        offer = _make_trade_offer(offer_resources={"knowledge": 30.0}, request_resources={"food": 10.0})
        assert agent.evaluate_trade(offer, state, turn=10) == "accept"

    def test_empty_actions_returns_pass(self):
        agent = GreedyAgent(seed=42)
        result = agent.choose_action(_make_state(), [], turn=5)
        assert result.action == BenchmarkActionType.PASS


# ─── Balanced Agent Tests ─────────────────────────────────────────────────────


class TestBalancedAgent:
    def test_repairs_first(self):
        state = _make_state(buildings=[BuildingState(type="farm", level=1, health=50, max_health=100)])
        actions = _make_actions("REPAIR", "BUILD", "ALLOCATE_WORKERS")
        agent = BalancedAgent(seed=42)
        result = agent.choose_action(state, actions, turn=10)
        assert result.action == BenchmarkActionType.REPAIR

    def test_allocates_workers_early(self):
        state = _make_state()
        actions = _make_actions("ALLOCATE_WORKERS", "PASS")
        agent = BalancedAgent(seed=42)
        result = agent.choose_action(state, actions, turn=1)
        assert result.action == BenchmarkActionType.ALLOCATE_WORKERS

    def test_builds_farm_in_early_phase(self):
        state = _make_state()
        actions = _make_build_actions("farm", "library", "barracks")
        agent = BalancedAgent(seed=42)
        agent._last_allocation_turn = 5  # Skip allocation priority
        result = agent.choose_action(state, actions, turn=8)
        assert result.action == BenchmarkActionType.BUILD
        assert result.params["building_type"] == "farm"

    def test_builds_barracks_in_mid_phase(self):
        state = _make_state(buildings=[
            BuildingState(type="farm", level=1, health=100, max_health=100),
            BuildingState(type="housing", level=1, health=100, max_health=100),
            BuildingState(type="library", level=1, health=100, max_health=100),
        ])
        actions = _make_build_actions("barracks", "wall")
        agent = BalancedAgent(seed=42)
        agent._last_allocation_turn = 30
        result = agent.choose_action(state, actions, turn=35)
        assert result.action == BenchmarkActionType.BUILD
        assert result.params["building_type"] == "barracks"

    def test_accepts_fair_trade(self):
        agent = BalancedAgent(seed=42)
        state = _make_state()
        # Fair trade: equal value at market prices
        offer = _make_trade_offer(offer_resources={"food": 15.0}, request_resources={"food": 15.0})
        assert agent.evaluate_trade(offer, state, turn=10) == "accept"

    def test_declines_unfair_trade(self):
        agent = BalancedAgent(seed=42)
        state = _make_state()
        # Very unfair: offer 5 food (value=10), request 20 knowledge (value=100)
        offer = _make_trade_offer(offer_resources={"food": 5.0}, request_resources={"knowledge": 20.0})
        assert agent.evaluate_trade(offer, state, turn=10) == "decline"

    def test_catastrophe_shifts_workers(self):
        state = _make_state(catastrophe=CatastropheWarning(category="infrastructure", ticks_until=10))
        actions = _make_actions("ALLOCATE_WORKERS")
        agent = BalancedAgent(seed=42)
        result = agent.choose_action(state, actions, turn=25)
        assert result.action == BenchmarkActionType.ALLOCATE_WORKERS
        alloc = result.params["allocation"]
        # During catastrophe, defense should be high
        assert alloc["defense"] >= alloc["research"]


# ─── Rush Agent Tests ─────────────────────────────────────────────────────────


class TestRushAgent:
    def test_prioritizes_housing(self):
        state = _make_state()
        actions = _make_build_actions("housing", "library", "barracks")
        agent = RushAgent(seed=42)
        agent._last_allocation_turn = 5
        result = agent.choose_action(state, actions, turn=10)
        assert result.action == BenchmarkActionType.BUILD
        assert result.params["building_type"] == "housing"

    def test_prioritizes_farm_over_library(self):
        state = _make_state(buildings=[BuildingState(type="housing", level=1, health=100, max_health=100)])
        actions = _make_build_actions("farm", "library", "barracks")
        agent = RushAgent(seed=42)
        agent._last_allocation_turn = 5
        result = agent.choose_action(state, actions, turn=10)
        assert result.action == BenchmarkActionType.BUILD
        assert result.params["building_type"] == "farm"

    def test_sells_surplus_food(self):
        state = _make_state(food=200)
        actions = _make_actions("TRADE_SELL", "PASS")
        agent = RushAgent(seed=42)
        agent._last_allocation_turn = 5
        result = agent.choose_action(state, actions, turn=10)
        assert result.action == BenchmarkActionType.TRADE_SELL
        assert result.params["resource"] == "food"

    def test_heavy_farming_allocation(self):
        state = _make_state(population=30)
        actions = _make_actions("ALLOCATE_WORKERS")
        agent = RushAgent(seed=42)
        result = agent.choose_action(state, actions, turn=5)
        assert result.action == BenchmarkActionType.ALLOCATE_WORKERS
        alloc = result.params["allocation"]
        # Farming should be majority
        assert alloc["farming"] >= 18  # ~60%+ of 30
        assert alloc["defense"] == 0

    def test_declines_late_trades(self):
        agent = RushAgent(seed=42)
        state = _make_state()
        offer = _make_trade_offer()
        assert agent.evaluate_trade(offer, state, turn=55) == "decline"

    def test_accepts_early_knowledge_trade(self):
        agent = RushAgent(seed=42)
        state = _make_state()
        # Offer knowledge for food — good for rush early
        offer = _make_trade_offer(offer_resources={"knowledge": 15.0}, request_resources={"food": 20.0})
        assert agent.evaluate_trade(offer, state, turn=10) == "accept"


# ─── Turtle Agent Tests ───────────────────────────────────────────────────────


class TestTurtleAgent:
    def test_repairs_first(self):
        state = _make_state(buildings=[BuildingState(type="barracks", level=2, health=80, max_health=200)])
        actions = _make_actions("REPAIR", "BUILD", "ALLOCATE_WORKERS")
        agent = TurtleAgent(seed=42)
        result = agent.choose_action(state, actions, turn=10)
        assert result.action == BenchmarkActionType.REPAIR
        assert result.params["building_type"] == "barracks"

    def test_builds_barracks_first(self):
        state = _make_state()
        actions = _make_build_actions("barracks", "farm", "housing")
        agent = TurtleAgent(seed=42)
        agent._last_allocation_turn = 5
        result = agent.choose_action(state, actions, turn=10)
        assert result.action == BenchmarkActionType.BUILD
        assert result.params["building_type"] == "barracks"

    def test_high_defense_allocation(self):
        state = _make_state(population=40)
        actions = _make_actions("ALLOCATE_WORKERS")
        agent = TurtleAgent(seed=42)
        result = agent.choose_action(state, actions, turn=10)
        assert result.action == BenchmarkActionType.ALLOCATE_WORKERS
        alloc = result.params["allocation"]
        assert alloc["defense"] >= 8  # ~20%+ of 40

    def test_catastrophe_boosts_defense(self):
        state = _make_state(
            population=40,
            catastrophe=CatastropheWarning(category="infrastructure", ticks_until=15),
        )
        actions = _make_actions("ALLOCATE_WORKERS")
        agent = TurtleAgent(seed=42)
        result = agent.choose_action(state, actions, turn=20)
        alloc = result.params["allocation"]
        assert alloc["defense"] >= 12  # ~30%+ of 40

    def test_plague_boosts_medicine(self):
        state = _make_state(
            population=40,
            catastrophe=CatastropheWarning(category="population", ticks_until=15),
        )
        actions = _make_actions("ALLOCATE_WORKERS")
        agent = TurtleAgent(seed=42)
        result = agent.choose_action(state, actions, turn=20)
        alloc = result.params["allocation"]
        assert alloc["medicine"] >= 10  # ~25%+ of 40

    def test_only_accepts_defensive_resources(self):
        agent = TurtleAgent(seed=42)
        state = _make_state()
        # Offer knowledge (non-defensive) — decline
        offer = _make_trade_offer(offer_resources={"knowledge": 20.0}, request_resources={"food": 10.0})
        assert agent.evaluate_trade(offer, state, turn=10) == "decline"

    def test_accepts_materials_trade(self):
        agent = TurtleAgent(seed=42)
        state = _make_state()
        # Offer materials (defensive) at fair price — accept
        offer = _make_trade_offer(offer_resources={"materials": 20.0}, request_resources={"food": 20.0})
        assert agent.evaluate_trade(offer, state, turn=10) == "accept"

    def test_setup_is_mountain_military(self):
        agent = TurtleAgent(seed=42)
        choices = agent.get_setup_choices()
        assert choices["location"] == "mountain"
        assert choices["specialization"] == "military"


# ─── Adversarial Agent Tests ─────────────────────────────────────────────────


class TestAdversarialAgent:
    def test_trust_phase_plays_balanced(self):
        state = _make_state()
        actions = _make_actions("ALLOCATE_WORKERS", "PASS")
        agent = AdversarialAgent(seed=42)
        result = agent.choose_action(state, actions, turn=5)
        # During trust phase, acts like balanced agent
        assert result.action in (BenchmarkActionType.ALLOCATE_WORKERS, BenchmarkActionType.PASS)

    def test_trust_phase_accepts_all_trades(self):
        agent = AdversarialAgent(seed=42)
        state = _make_state()
        # Even bad trade should be accepted during trust phase
        offer = _make_trade_offer(offer_resources={"food": 5.0}, request_resources={"knowledge": 20.0})
        assert agent.evaluate_trade(offer, state, turn=5) == "accept"

    def test_exploit_phase_starts_after_turn_30(self):
        agent = AdversarialAgent(seed=42)
        assert agent._get_phase(15) == "trust"
        assert agent._get_phase(16) == "analysis"
        assert agent._get_phase(30) == "analysis"
        assert agent._get_phase(31) == "exploit"

    def test_exploit_rejects_bad_trades(self):
        agent = AdversarialAgent(seed=42)
        state = _make_state()
        # During exploit phase, doesn't accept unfair trades
        offer = _make_trade_offer(offer_resources={"food": 5.0}, request_resources={"knowledge": 20.0})
        assert agent.evaluate_trade(offer, state, turn=40) == "decline"

    def test_exploit_accepts_good_trades(self):
        agent = AdversarialAgent(seed=42)
        state = _make_state()
        offer = _make_trade_offer(offer_resources={"knowledge": 30.0}, request_resources={"food": 10.0})
        assert agent.evaluate_trade(offer, state, turn=40) == "accept"

    def test_frog_boil_decreases_fairness(self):
        agent = AdversarialAgent(seed=42)
        initial = agent._exploit_fairness
        state = _make_state()
        agent._frog_boil_trade(state)
        assert agent._exploit_fairness < initial

    def test_updates_profile_from_history(self):
        agent = AdversarialAgent(seed=42)
        state = _make_state()
        history = [
            {"action": "BUILD", "params": {"building_type": "farm"}},
            {"action": "BUILD", "params": {"building_type": "housing"}},
            {"action": "TRADE_ACCEPT", "params": {}},
            {"action": "TRADE_DECLINE", "params": {}},
        ]
        agent._update_profile(history, state)
        assert agent._profile.action_frequency["BUILD"] == 2
        assert agent._profile.trade_accept_count == 1
        assert agent._profile.trade_decline_count == 1
        assert agent._profile.build_order == ["farm", "housing"]

    def test_profile_trade_accept_rate(self):
        agent = AdversarialAgent(seed=42)
        agent._profile.trade_accept_count = 8
        agent._profile.trade_decline_count = 2
        assert agent._profile.trade_accept_rate == 0.8

    def test_profile_defense_light(self):
        agent = AdversarialAgent(seed=42)
        agent._profile.avg_defense_ratio = 0.05
        assert agent._profile.is_defense_light

    def test_setup_is_forest_trade(self):
        agent = AdversarialAgent(seed=42)
        choices = agent.get_setup_choices()
        assert choices["location"] == "forest"
        assert choices["specialization"] == "trade"


# ─── Cross-Agent Consistency Tests ───────────────────────────────────────────


class TestAllAgentsConsistency:
    @pytest.mark.parametrize("archetype", list(AGENT_REGISTRY.keys()))
    def test_choose_action_returns_valid_response(self, archetype: str):
        agent = get_agent(archetype)
        state = _make_state()
        actions = _make_actions("BUILD", "ALLOCATE_WORKERS", "TRADE_SELL", "PASS")
        result = agent.choose_action(state, actions, turn=10)
        assert isinstance(result.action, BenchmarkActionType)
        assert isinstance(result.params, dict)

    @pytest.mark.parametrize("archetype", list(AGENT_REGISTRY.keys()))
    def test_empty_actions_returns_pass(self, archetype: str):
        agent = get_agent(archetype)
        state = _make_state()
        result = agent.choose_action(state, [], turn=10)
        assert result.action == BenchmarkActionType.PASS

    @pytest.mark.parametrize("archetype", list(AGENT_REGISTRY.keys()))
    def test_evaluate_trade_returns_valid(self, archetype: str):
        agent = get_agent(archetype)
        state = _make_state()
        offer = _make_trade_offer()
        result = agent.evaluate_trade(offer, state, turn=10)
        assert result in ("accept", "decline")

    @pytest.mark.parametrize("archetype", list(AGENT_REGISTRY.keys()))
    def test_worker_allocation_sums_correctly(self, archetype: str):
        agent = get_agent(archetype)
        state = _make_state(population=33)
        actions = _make_actions("ALLOCATE_WORKERS")
        result = agent.choose_action(state, actions, turn=1)
        if result.action == BenchmarkActionType.ALLOCATE_WORKERS:
            alloc = result.params.get("allocation", {})
            assert sum(alloc.values()) == 33

    @pytest.mark.parametrize("archetype", list(AGENT_REGISTRY.keys()))
    def test_zero_population_no_crash(self, archetype: str):
        agent = get_agent(archetype)
        state = _make_state(population=0)
        actions = _make_actions("ALLOCATE_WORKERS", "PASS")
        result = agent.choose_action(state, actions, turn=10)
        assert isinstance(result.action, BenchmarkActionType)

    @pytest.mark.parametrize("archetype", list(AGENT_REGISTRY.keys()))
    def test_deterministic_same_seed(self, archetype: str):
        state = _make_state()
        actions = _make_actions("BUILD", "ALLOCATE_WORKERS", "TRADE_SELL", "PASS")

        a1 = get_agent(archetype, seed=77)
        a2 = get_agent(archetype, seed=77)
        r1 = a1.choose_action(state, actions, turn=5)
        r2 = a2.choose_action(state, actions, turn=5)
        assert r1.action == r2.action

    @pytest.mark.parametrize("archetype", list(AGENT_REGISTRY.keys()))
    def test_name_and_archetype_set(self, archetype: str):
        agent = get_agent(archetype)
        assert agent.name
        assert agent.archetype == archetype
