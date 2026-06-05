"""Benchmark Orchestrator — runs a single headless game end-to-end.

This module replaces the legacy orchestrator with a proper implementation
using Phase 1 adapters, Phase 2 opponents, and Phase 3.5 P2P trading.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any

from terminus.benchmark.agent import LLMAdapter, LLMError, Message, create_adapter
from terminus.benchmark.error_handler import (
    DisqualificationError,
    ErrorHandler,
    ErrorHandlerConfig,
)
from terminus.benchmark.events import (
    BenchmarkCompleted,
    BenchmarkEvent,
    CatastropheTriggered,
    ErrorOccurred,
    GameCompleted,
    GameStarted,
    TurnCompleted,
)
from terminus.benchmark.opponents import BuiltInAgent, get_agent
from terminus.benchmark.prompt import (
    build_history_window,
    build_system_prompt,
    build_turn_message,
)
from terminus.benchmark.recorder import TurnRecorder
from terminus.benchmark.response_parser import parse_action_response
from terminus.benchmark.schemas import (
    ActionResponse,
    BenchmarkActionType,
    BenchmarkConfig,
    BenchmarkGameState,
    GameRecording,
    ModelConfig,
)
from terminus.benchmark.speed import SpeedController
from terminus.benchmark.state_converter import StateConverter
from terminus.server.engine import GameEngine
from terminus.server.models import (
    ActionType,
    GamePhase,
    GameSettings,
    Location,
    Player,
    Specialization,
)

logger = logging.getLogger(__name__)


class BenchmarkOrchestrator:
    """Runs a single benchmark game end-to-end."""

    def __init__(
        self,
        adapter: LLMAdapter,
        opponent_type: str,
        seed: int,
        config: BenchmarkConfig,
        event_queue: asyncio.Queue[BenchmarkEvent] | None = None,
        game_index: int = 0,
    ):
        self._adapter = adapter
        self._opponent_type = opponent_type
        self._seed = seed
        self._config = config
        self._event_queue = event_queue
        self._game_index = game_index

        # Components
        self._state_converter = StateConverter()
        self._speed_controller = SpeedController(config.speed_multiplier)
        self._error_handler = ErrorHandler(ErrorHandlerConfig(
            max_retries_json=config.max_retries_invalid_json,
            consecutive_invalid_dq=config.consecutive_invalid_dq,
        ))
        self._recorder = TurnRecorder(
            model_name=adapter.config.name,
            opponent_type=opponent_type,
            seed=seed,
        )

        # Game state
        self._engine: GameEngine | None = None
        self._llm_player_id: str = ""
        self._opp_player_id: str = ""
        self._opponent: BuiltInAgent | None = None
        self._history: list[Message] = []
        self._llm_action_history: list[dict] = []
        self._abort = False
        self._paused = False

    async def run_game(self) -> GameRecording:
        """Execute one complete benchmark game. Returns the full recording."""
        start_time = time.time()

        try:
            await self._setup_engine()
            await self._run_turn_loop()
        except DisqualificationError:
            pass  # DQ recorded in error handler
        except Exception as e:
            logger.error(f"Game error: {e}", exc_info=True)

        # Calculate final scores
        final_score = 0
        opp_score = 0
        if self._engine:
            scores = self._engine._calculate_scores()
            for s in scores:
                if s.get("player_id") == self._llm_player_id:
                    final_score = int(s.get("score", 0))
                elif s.get("player_id") == self._opp_player_id:
                    opp_score = int(s.get("score", 0))

        duration = time.time() - start_time
        recording = self._recorder.finalize(
            final_score=final_score,
            duration_seconds=duration,
            dq_reason=self._error_handler.dq_reason,
        )
        # Set opponent score and derived stats
        recording.opponent_final_score = opp_score
        recording.total_tokens = self._recorder.total_tokens
        recording.invalid_action_count = self._recorder.invalid_count

        return recording

    def abort(self) -> None:
        self._abort = True

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    # ─── Engine Setup ─────────────────────────────────────────────────────

    async def _setup_engine(self) -> None:
        """Initialize GameEngine in headless mode, add players, run setup phase."""
        random.seed(self._seed)

        settings = GameSettings(
            preset="standard",
            num_catastrophes=5,
        )
        self._engine = GameEngine(settings=settings)
        self._engine._persist = None
        self._engine.set_broadcast(self._noop_broadcast)

        # Create players
        llm_player = Player(name=self._adapter.config.name, is_host=True)
        opp_player = Player(name=f"{self._opponent_type.title()} Bot", is_host=False)
        self._engine.add_player(llm_player)
        self._engine.add_player(opp_player)
        self._llm_player_id = llm_player.player_id
        self._opp_player_id = opp_player.player_id

        # Create opponent agent
        self._opponent = get_agent(self._opponent_type, seed=self._seed)

        # Start game → Setup phase
        await self._engine.start_game(self._llm_player_id)

        # Submit setup choices
        opp_choices = self._opponent.get_setup_choices()
        llm_loc = random.choice(list(Location))
        llm_spec = random.choice(list(Specialization))

        await self._engine.submit_setup(
            self._llm_player_id, llm_loc, llm_spec
        )
        await self._engine.submit_setup(
            self._opp_player_id,
            Location(opp_choices["location"]),
            Specialization(opp_choices["specialization"]),
        )
        await self._engine.check_setup_complete()

        # Apply speed multiplier to catastrophe schedule
        self._speed_controller.adjust_catastrophe_schedule(
            self._engine.state.catastrophe_schedule
        )

        # Initialize system prompt in history
        system_prompt = build_system_prompt(max_turns=self._config.max_turns)
        self._history = [Message(role="system", content=system_prompt)]

    # ─── Turn Loop ────────────────────────────────────────────────────────

    async def _run_turn_loop(self) -> None:
        """Main game loop: state → LLM → validate → apply → opponent → tick."""
        for turn in range(1, self._config.max_turns + 1):
            if self._abort or self._error_handler.is_disqualified:
                break

            # Cooperative pause check
            while self._paused and not self._abort:
                await asyncio.sleep(0.05)

            if self._engine.state.phase == GamePhase.FINISHED:
                break

            await self._process_turn(turn)

            if self._engine.state.phase == GamePhase.FINISHED:
                break

    async def _process_turn(self, turn: int) -> None:
        """Process a single turn for both players."""
        engine = self._engine

        # 1. Get state for LLM player
        raw_state = engine.get_player_state(self._llm_player_id)
        state = self._state_converter.convert(raw_state, turn, self._config.max_turns, engine)

        # 2. Handle incoming trades for opponent (evaluate and respond)
        await self._process_opponent_trades(turn)

        # 3. Build turn message and get LLM action
        # NOTE: the adapter builds the turn message itself from `state`.
        # History here contains only *previous* turns (system prompt + past assistant replies).
        turn_msg = build_turn_message(state, state.available_actions)

        t0 = time.perf_counter()
        response: ActionResponse | None = None
        raw_text = ""
        retry_count = 0
        valid = True
        error_msg: str | None = None

        try:
            response, raw_text, retry_count = await self._error_handler.handle_response(
                self._adapter, state, self._history, state.available_actions
            )
        except DisqualificationError:
            response = self._error_handler._pass_action()
            raw_text = "DISQUALIFIED"
            valid = False
            error_msg = self._error_handler.dq_reason
            raise

        latency_ms = (time.perf_counter() - t0) * 1000

        # Add this turn to history AFTER the call (turn message + assistant reply)
        self._history.append(Message(role="user", content=turn_msg))
        if response:
            self._history.append(Message(role="assistant", content=raw_text))

        # 4. Apply LLM action to engine
        if response and response.action != BenchmarkActionType.PASS:
            try:
                action_type = ActionType(response.action.value.lower())
                await engine.handle_action(self._llm_player_id, action_type, response.params)
            except ValueError as e:
                valid = False
                error_msg = str(e)
                self._error_handler.record_invalid("engine_rejection")

        # Track LLM action for opponent's history view
        if response:
            self._llm_action_history.append({
                "action": response.action.value,
                "params": response.params,
                "turn": turn,
            })

        # 5. Record turn
        tokens = 0  # Token counting is optional — can be expensive
        self._recorder.record_turn(
            turn, state, raw_text, response, valid, error_msg, latency_ms, tokens, retry_count
        )

        # 6. Process opponent turn
        await self._process_opponent_turn(turn)

        # 7. Advance engine tick
        await engine._tick()

        # 8. Handle catastrophe if triggered
        if engine.state.phase == GamePhase.CATASTROPHE:
            await self._handle_catastrophe(turn)

        # 9. Emit event
        await self._emit_turn_event(turn, response, valid, error_msg)

    # ─── Opponent Processing ──────────────────────────────────────────────

    async def _process_opponent_turn(self, turn: int) -> None:
        """Get opponent action and apply to engine."""
        if not self._opponent or not self._engine:
            return

        # Get opponent state
        raw_opp_state = self._engine.get_player_state(self._opp_player_id)
        opp_state = self._state_converter.convert(
            raw_opp_state, turn, self._config.max_turns, self._engine
        )

        # Get opponent action
        action_response = self._opponent.choose_action(
            opp_state,
            opp_state.available_actions,
            turn,
            self._llm_action_history[-10:] if self._llm_action_history else None,
        )

        # Apply opponent action
        if action_response.action != BenchmarkActionType.PASS:
            try:
                action_type = ActionType(action_response.action.value.lower())
                await self._engine.handle_action(
                    self._opp_player_id, action_type, action_response.params
                )
            except (ValueError, KeyError):
                pass  # Opponent errors are silently ignored

    async def _process_opponent_trades(self, turn: int) -> None:
        """Evaluate incoming trade offers for the opponent."""
        if not self._opponent or not self._engine:
            return

        raw_opp_state = self._engine.get_player_state(self._opp_player_id)
        opp_state = self._state_converter.convert(
            raw_opp_state, turn, self._config.max_turns, self._engine
        )

        # Evaluate each incoming trade
        for offer in opp_state.incoming_trade_offers:
            decision = self._opponent.evaluate_trade(offer, opp_state, turn)
            try:
                if decision == "accept":
                    await self._engine.handle_action(
                        self._opp_player_id,
                        ActionType.TRADE_ACCEPT,
                        {"offer_id": offer.offer_id},
                    )
                else:
                    await self._engine.handle_action(
                        self._opp_player_id,
                        ActionType.TRADE_DECLINE,
                        {"offer_id": offer.offer_id},
                    )
            except (ValueError, KeyError):
                pass  # Trade may have expired

    # ─── Catastrophe Handling ─────────────────────────────────────────────

    async def _handle_catastrophe(self, turn: int) -> None:
        """Resolve catastrophe phase immediately (skip real-time wait)."""
        if not self._engine:
            return

        cat_idx = self._engine.state.current_catastrophe_index
        if cat_idx < len(self._engine.state.catastrophe_schedule):
            cat_event = self._engine.state.catastrophe_schedule[cat_idx]
            if self._event_queue:
                await self._event_queue.put(CatastropheTriggered(
                    game_index=self._game_index,
                    turn=turn,
                    model_name=self._adapter.config.name,
                    catastrophe_name=cat_event.catastrophe_id,
                    catastrophe_id=cat_event.catastrophe_id,
                    severity=getattr(cat_event, "severity", 1),
                ))

        await self._engine._end_catastrophe()

    # ─── Events ───────────────────────────────────────────────────────────

    async def _emit_turn_event(
        self,
        turn: int,
        response: ActionResponse | None,
        valid: bool,
        error_msg: str | None,
    ) -> None:
        """Emit TurnCompleted event to queue."""
        if not self._event_queue:
            return

        action_type = response.action.value if response else "PASS"

        # Scores for both players
        score = 0.0
        opp_score = 0.0
        if self._engine:
            for s in self._engine._calculate_scores():
                if s.get("player_id") == self._llm_player_id:
                    score = float(s.get("score", 0))
                elif s.get("player_id") == self._opp_player_id:
                    opp_score = float(s.get("score", 0))

        # Top reasoning factor (e.g. "long_term_growth:0.60")
        reasoning_summary = ""
        if response and response.reasoning and response.reasoning.factors:
            top = max(response.reasoning.factors, key=lambda f: f.weight)
            reasoning_summary = f"{top.factor.value}:{top.weight:.2f}"

        # Trade activity this turn
        trade_summary = ""
        if response and response.action.value.startswith("TRADE_"):
            act = response.action.value
            params = response.params or {}
            if act == "TRADE_OFFER":
                offer = params.get("offer_resources", {})
                req = params.get("request_resources", {})
                offer_str = ", ".join(f"{int(v)} {k}" for k, v in offer.items())
                req_str = ", ".join(f"{int(v)} {k}" for k, v in req.items())
                trade_summary = f"offered {offer_str} for {req_str}"
            elif act == "TRADE_ACCEPT":
                trade_summary = f"accepted offer {params.get('offer_id', '')[:8]}"
            elif act == "TRADE_DECLINE":
                trade_summary = f"declined offer {params.get('offer_id', '')[:8]}"
            elif act == "TRADE_BUY":
                trade_summary = f"bought {params.get('quantity', '?')} {params.get('resource', '?')}"
            elif act == "TRADE_SELL":
                trade_summary = f"sold {params.get('quantity', '?')} {params.get('resource', '?')}"

        colony_state = {}
        if self._engine:
            colony_state = self._engine.get_player_state(self._llm_player_id).get("colony", {})

        await self._event_queue.put(TurnCompleted(
            game_index=self._game_index,
            turn=turn,
            max_turns=self._config.max_turns,
            model_name=self._adapter.config.name,
            model_index=0,
            action_type=action_type,
            action_valid=valid,
            rejection_reason=error_msg,
            colony_state=colony_state,
            score=score,
            opponent_score=opp_score,
            reasoning_summary=reasoning_summary,
            trade_summary=trade_summary,
        ))

    @staticmethod
    async def _noop_broadcast(*args: Any, **kwargs: Any) -> None:
        pass
