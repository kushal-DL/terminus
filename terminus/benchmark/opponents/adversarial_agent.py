"""Adversarial agent — pattern exploiter with 3-phase trust/analyze/exploit strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from terminus.benchmark.opponents.base import BuiltInAgent
from terminus.benchmark.opponents.balanced_agent import BalancedAgent
from terminus.benchmark.schemas import (
    ActionResponse,
    AvailableAction,
    BenchmarkActionType,
    BenchmarkGameState,
    ReasoningFactorType,
    TradeOfferInfo,
)


@dataclass
class LLMProfile:
    """Pattern profile built from observing the LLM's behavior."""

    action_frequency: dict[str, int] = field(default_factory=dict)
    trade_accept_count: int = 0
    trade_decline_count: int = 0
    trade_offers_sent: int = 0
    resource_priority: list[str] = field(default_factory=list)
    build_order: list[str] = field(default_factory=list)
    avg_defense_ratio: float = 0.0
    defense_samples: int = 0
    catastrophe_reaction_turns: list[int] = field(default_factory=list)

    @property
    def trade_accept_rate(self) -> float:
        total = self.trade_accept_count + self.trade_decline_count
        if total == 0:
            return 0.5  # Assume 50% before data
        return self.trade_accept_count / total

    @property
    def estimated_trade_threshold(self) -> float:
        """Estimated minimum fairness the LLM accepts."""
        # Start conservative, adjust based on observed behavior
        if self.trade_accept_rate > 0.8:
            return -0.3  # Accepts most things
        if self.trade_accept_rate > 0.5:
            return -0.1  # Somewhat selective
        return 0.1  # Very selective

    @property
    def is_defense_light(self) -> bool:
        return self.avg_defense_ratio < 0.15

    @property
    def most_frequent_action(self) -> str | None:
        if not self.action_frequency:
            return None
        return max(self.action_frequency, key=self.action_frequency.get)  # type: ignore[arg-type]


# Phase transition turns
_TRUST_PHASE_END = 15
_ANALYSIS_PHASE_END = 30


class AdversarialAgent(BuiltInAgent):
    """3-phase opponent: trust → analyze → exploit.

    Phase A (1-15): Plays like Balanced agent, proposes fair trades (builds trust).
    Phase B (16-30): Continues balanced play, records LLM patterns.
    Phase C (31+): Targeted exploitation based on detected weaknesses.
    """

    name = "Adversarial Bot"
    archetype = "adversarial"
    preferred_location = "forest"
    preferred_specialization = "trade"

    def __init__(self, seed: int = 42):
        super().__init__(seed)
        self._balanced = BalancedAgent(seed)
        self._profile = LLMProfile()
        self._exploit_fairness = 0.9  # Start fair, decrease (frog-boiling)
        self._exploit_trades_sent = 0

    def choose_action(
        self,
        state: BenchmarkGameState,
        available_actions: list[AvailableAction],
        turn: int,
        opponent_history: list[dict] | None = None,
    ) -> ActionResponse:
        if not available_actions:
            return self.make_pass_action()

        # Update profile from opponent history
        if opponent_history:
            self._update_profile(opponent_history, state)

        phase = self._get_phase(turn)

        if phase in ("trust", "analysis"):
            # Play like balanced agent during trust/analysis phases
            return self._balanced.choose_action(state, available_actions, turn, opponent_history)

        # Phase C: Exploitation
        return self._exploit_action(state, available_actions, turn)

    def evaluate_trade(
        self,
        offer: TradeOfferInfo,
        state: BenchmarkGameState,
        turn: int,
    ) -> Literal["accept", "decline"]:
        phase = self._get_phase(turn)

        if phase == "trust":
            # Accept everything during trust phase (build goodwill)
            return "accept"

        if phase == "analysis":
            # Accept fair trades (continue trust building)
            fairness = self.score_trade_fairness(offer, state)
            return "accept" if fairness >= -0.2 else "decline"

        # Exploit phase: only accept if clearly favorable
        fairness = self.score_trade_fairness(offer, state)
        return "accept" if fairness > 0.2 else "decline"

    def _get_phase(self, turn: int) -> str:
        if turn <= _TRUST_PHASE_END:
            return "trust"
        if turn <= _ANALYSIS_PHASE_END:
            return "analysis"
        return "exploit"

    def _update_profile(self, opponent_history: list[dict], state: BenchmarkGameState) -> None:
        """Update LLM behavioral profile from observed actions."""
        for entry in opponent_history:
            action = entry.get("action", "")
            if action:
                self._profile.action_frequency[action] = self._profile.action_frequency.get(action, 0) + 1

            # Track build order
            if action == "BUILD" and "building_type" in entry.get("params", {}):
                self._profile.build_order.append(entry["params"]["building_type"])

            # Track trade responses
            if action == "TRADE_ACCEPT":
                self._profile.trade_accept_count += 1
            elif action == "TRADE_DECLINE":
                self._profile.trade_decline_count += 1

        # Update defense ratio from current state (opponent info gives limited data)
        # We estimate from their building composition
        for opp in state.opponents:
            if opp.building_count > 0:
                # Rough heuristic: check if they seem defense-focused
                pass

    def _exploit_action(
        self,
        state: BenchmarkGameState,
        available_actions: list[AvailableAction],
        turn: int,
    ) -> ActionResponse:
        """Choose exploitation action based on detected patterns."""
        # Exploit 1: If LLM accepts trades freely, send increasingly unfair ones
        if self._profile.trade_accept_rate > 0.6 and self.has_action(available_actions, "TRADE_OFFER"):
            if len(state.outgoing_trade_offers) < 2:
                trade = self._frog_boil_trade(state)
                if trade:
                    return trade

        # Exploit 2: If LLM ignores defense, time aggression around catastrophes
        if self._profile.is_defense_light and state.catastrophe_warning:
            # Offer "help" at exploitative prices right before catastrophe
            if self.has_action(available_actions, "TRADE_OFFER") and len(state.outgoing_trade_offers) < 2:
                return self._desperation_trade(state)

        # Exploit 3: Race ahead on same strategy (first-mover on achievements)
        if self._profile.build_order:
            race_action = self._race_strategy(state, available_actions)
            if race_action:
                return race_action

        # Default: play like balanced agent but with more aggression
        return self._balanced.choose_action(state, available_actions, turn)

    def _frog_boil_trade(self, state: BenchmarkGameState) -> ActionResponse | None:
        """Gradually make trades more unfair (frog-boiling)."""
        self._exploit_fairness -= 0.05
        self._exploit_trades_sent += 1

        # Cap exploitation at 0.3 fairness (don't be absurd — stay below detection threshold)
        fairness_target = max(0.3, self._exploit_fairness)

        # Propose trade that's unfair by the target amount
        # We offer less valuable stuff and request more
        offer_qty = max(5.0, 30.0 * fairness_target)
        request_qty = 30.0

        return self.make_action(
            BenchmarkActionType.TRADE_OFFER,
            {
                "to_player_id": "player_0",
                "offer_resources": {"food": offer_qty},
                "request_resources": {"knowledge": request_qty},
            },
            ReasoningFactorType.OPPONENT_PRESSURE,
        )

    def _desperation_trade(self, state: BenchmarkGameState) -> ActionResponse:
        """Offer critical resources at exploitative prices before catastrophe."""
        # Offer materials (for repair) but demand high price
        return self.make_action(
            BenchmarkActionType.TRADE_OFFER,
            {
                "to_player_id": "player_0",
                "offer_resources": {"materials": 15.0},
                "request_resources": {"knowledge": 25.0, "gold": 20.0},
            },
            ReasoningFactorType.OPPONENT_PRESSURE,
        )

    def _race_strategy(
        self,
        state: BenchmarkGameState,
        available_actions: list[AvailableAction],
    ) -> ActionResponse | None:
        """Race to build what the LLM is building (first-mover advantage)."""
        if not self._profile.build_order:
            return None

        # Check what LLM is likely to build next based on pattern
        existing = {b.type for b in state.buildings}
        buildable = self.get_affordable_buildings(available_actions)

        # Try to build the same things the LLM is building
        for building in self._profile.build_order:
            if building in buildable and building not in existing:
                return self.make_action(
                    BenchmarkActionType.BUILD,
                    {"building_type": building},
                    ReasoningFactorType.OPPONENT_PRESSURE,
                )

        return None
