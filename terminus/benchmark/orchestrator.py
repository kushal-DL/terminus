"""Benchmark Orchestrator — runs headless games, queries LLMs, emits events."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any

from terminus.benchmark.events import (
    BenchmarkCompleted,
    BenchmarkEvent,
    CatastropheTriggered,
    ErrorOccurred,
    GameCompleted,
    GameStarted,
    TurnCompleted,
)
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

# Opponent strategy names mapped to strategy classes
OPPONENT_STRATEGIES = ["balanced", "aggressive", "hoarder", "researcher"]

# Location/specialization pools for random assignment
LOCATIONS = list(Location)
SPECIALIZATIONS = list(Specialization)


class LLMAdapter:
    """Interface for calling an LLM to get a game action."""

    def __init__(self, model_config: dict[str, Any]) -> None:
        self.provider = model_config["provider"]
        self.url = model_config["url"]
        self.api_key = model_config.get("api_key", "")
        self.model_id = model_config["model_id"]
        self.name = model_config["name"]

    async def get_action(self, game_state: dict[str, Any], available_actions: list[str]) -> dict[str, Any]:
        """Query the LLM for an action decision.

        Returns:
            {"action_type": str, "payload": dict, "reasoning": str}
        """
        import httpx

        prompt = self._build_prompt(game_state, available_actions)

        try:
            response_text = await self._call_api(prompt)
            return self._parse_response(response_text, available_actions)
        except asyncio.TimeoutError:
            raise LLMError("timeout", f"LLM {self.name} timed out after 30s")
        except httpx.HTTPStatusError as e:
            raise LLMError("api_error", f"HTTP {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            raise LLMError("api_error", str(e))

    def _build_prompt(self, game_state: dict[str, Any], available_actions: list[str]) -> str:
        """Build the prompt for the LLM."""
        colony = game_state.get("colony", {})
        resources = colony.get("resources", {})
        workers = colony.get("workers", {})
        buildings = colony.get("buildings", [])

        prompt = (
            "You are playing a colony survival game. Choose ONE action.\n\n"
            f"Turn: {game_state.get('tick', 0)}\n"
            f"Resources: food={resources.get('food', 0):.0f}, "
            f"materials={resources.get('materials', 0):.0f}, "
            f"knowledge={resources.get('knowledge', 0):.0f}, "
            f"gold={resources.get('gold', 0):.0f}\n"
            f"Population: {colony.get('population', 0)} | Morale: {colony.get('morale', 0):.1f}\n"
            f"Workers: {workers}\n"
            f"Buildings: {[b.get('building_type', b.get('type', '?')) + ' L' + str(b.get('level', 0)) for b in buildings]}\n"
            f"Catastrophes remaining: {game_state.get('catastrophes_remaining', 0)}\n\n"
            f"Available actions: {available_actions}\n\n"
            "Respond in JSON format:\n"
            '{"action_type": "ACTION_NAME", "payload": {...}, "reasoning": "brief explanation"}\n\n'
            "Action types and payloads:\n"
            '- BUILD: {"building_type": "farm|mine|laboratory|market|hospital|wall|warehouse|housing|school|watchtower"}\n'
            '- UPGRADE: {"building_type": "..."}\n'
            '- ALLOCATE_WORKERS: {"allocation": {"farming": N, "mining": N, "research": N, "construction": N, "defense": N, "medicine": N}} (must sum to population)\n'
            '- TRADE_BUY: {"resource": "food|materials|knowledge", "quantity": N}\n'
            '- TRADE_SELL: {"resource": "food|materials|knowledge", "quantity": N}\n'
            '- REPAIR: {"building_type": "..."}\n'
            '- DEMOLISH: {"building_type": "..."}\n'
            '- PASS: {}\n'
        )
        return prompt

    async def _call_api(self, prompt: str) -> str:
        """Call the LLM API and return the response text."""
        import httpx

        headers: dict[str, str] = {}
        url = self.url.rstrip("/")
        timeout = 30.0

        if self.provider in ("OpenAI", "Ollama"):
            endpoint = f"{url}/chat/completions"
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["Content-Type"] = "application/json"
            payload = {
                "model": self.model_id,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.3,
            }
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(endpoint, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]

        elif self.provider == "Anthropic":
            endpoint = f"{url}/v1/messages"
            headers["x-api-key"] = self.api_key
            headers["anthropic-version"] = "2023-06-01"
            headers["content-type"] = "application/json"
            payload = {
                "model": self.model_id,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.3,
            }
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(endpoint, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return data["content"][0]["text"]

        elif self.provider == "Google":
            endpoint = f"{url}/v1beta/models/{self.model_id}:generateContent"
            params = {"key": self.api_key}
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 300, "temperature": 0.3},
            }
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(endpoint, json=payload, params=params)
                resp.raise_for_status()
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]

        raise LLMError("api_error", f"Unsupported provider: {self.provider}")

    def _parse_response(self, text: str, available_actions: list[str]) -> dict[str, Any]:
        """Parse the LLM's JSON response into action_type + payload."""
        import json
        import re

        # Try to extract JSON from the response
        # Handle markdown code blocks
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        else:
            # Try to find raw JSON object
            json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
            if json_match:
                text = json_match.group(0)

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            raise LLMError("parse_error", f"Could not parse JSON from: {text[:200]}")

        action_type = parsed.get("action_type", "PASS").upper()
        payload = parsed.get("payload", {})
        reasoning = parsed.get("reasoning", "")

        # Validate action type
        valid_actions = {"BUILD", "UPGRADE", "ALLOCATE_WORKERS", "TRADE_BUY", "TRADE_SELL", "REPAIR", "DEMOLISH", "PASS"}
        if action_type not in valid_actions:
            action_type = "PASS"
            payload = {}

        return {"action_type": action_type, "payload": payload, "reasoning": reasoning}


class LLMError(Exception):
    """Error from LLM interaction."""

    def __init__(self, error_type: str, message: str) -> None:
        self.error_type = error_type
        super().__init__(message)


class BenchmarkOrchestrator:
    """Runs multiple headless games, querying LLMs and emitting events."""

    def __init__(self, config: dict[str, Any], event_queue: asyncio.Queue[BenchmarkEvent]) -> None:
        self._config = config
        self._queue = event_queue
        self._paused = False
        self._abort = False
        self._skip_game = False
        self._start_time: float = 0.0

        # Build game plan: list of (model_index, opponent_strategy, game_num, seed)
        self._game_plan: list[tuple[int, str, int, int]] = []
        self._build_game_plan()

    def _build_game_plan(self) -> None:
        """Create the full list of games to run."""
        models = self._config["models"]
        num_games = self._config.get("num_games", 10)
        num_opponents = self._config.get("num_opponents", 6)
        seed_fixed = self._config.get("seed_fixed", True)
        base_seed = 42 if seed_fixed else random.randint(1, 999999)

        # Pick opponent strategies (cycle through available ones)
        opponent_strats = []
        for i in range(num_opponents):
            opponent_strats.append(OPPONENT_STRATEGIES[i % len(OPPONENT_STRATEGIES)])

        game_idx = 0
        for model_idx in range(len(models)):
            for opp_strat in opponent_strats:
                for game_num in range(num_games):
                    seed = base_seed + game_idx if seed_fixed else random.randint(1, 999999)
                    self._game_plan.append((model_idx, opp_strat, game_num, seed))
                    game_idx += 1

    @property
    def total_games(self) -> int:
        return len(self._game_plan)

    # ─── Control methods (called from TUI) ───────────────────────────────────

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def toggle_pause(self) -> None:
        self._paused = not self._paused

    def skip_current_game(self) -> None:
        self._skip_game = True

    def abort(self) -> None:
        self._abort = True

    # ─── Main run loop ───────────────────────────────────────────────────────

    async def run(self) -> dict[str, Any]:
        """Run all benchmark games. Returns final results dict."""
        self._start_time = time.time()
        models = self._config["models"]
        all_game_results: list[dict[str, Any]] = []

        for game_idx, (model_idx, opp_strat, game_num, seed) in enumerate(self._game_plan):
            if self._abort:
                break

            model_config = models[model_idx]
            model_name = model_config["name"]

            await self._queue.put(GameStarted(
                game_index=game_idx,
                model_name=model_name,
                model_index=model_idx,
                opponent_strategy=opp_strat,
                seed=seed,
            ))

            result = await self._run_single_game(game_idx, model_config, model_idx, opp_strat, seed)
            all_game_results.append(result)

            await self._queue.put(GameCompleted(
                game_index=game_idx,
                model_name=model_name,
                model_index=model_idx,
                opponent_strategy=opp_strat,
                final_score=result["score"],
                turns_played=result["turns_played"],
                valid_actions=result["valid_actions"],
                invalid_actions=result["invalid_actions"],
                scores=result.get("scores", []),
            ))

        elapsed = time.time() - self._start_time
        total_turns = sum(r["turns_played"] for r in all_game_results)

        # Build final results
        results = self._aggregate_results(all_game_results)

        await self._queue.put(BenchmarkCompleted(
            total_games=len(all_game_results),
            total_turns=total_turns,
            elapsed_seconds=elapsed,
            results=results,
        ))

        return results

    async def _run_single_game(
        self,
        game_idx: int,
        model_config: dict[str, Any],
        model_idx: int,
        opp_strat: str,
        seed: int,
    ) -> dict[str, Any]:
        """Run one complete game. Returns result dict."""
        self._skip_game = False
        max_turns = self._config.get("max_turns", 100)
        num_catastrophes = self._config.get("num_catastrophes", 5)
        speed_multiplier = self._config.get("speed_multiplier", 2)

        # Seed for reproducibility
        random.seed(seed)

        # Initialize engine
        settings = GameSettings(
            preset="standard",
            num_catastrophes=num_catastrophes,
        )
        engine = GameEngine(settings=settings)
        engine._persist = None
        engine.set_broadcast(self._noop_broadcast)

        # Add players
        llm_player = Player(name=model_config["name"], is_host=True)
        opponent = Player(name=f"Bot-{opp_strat.title()}", is_host=False)
        engine.add_player(llm_player)
        engine.add_player(opponent)

        # Setup (skip lobby)
        await engine.start_game(llm_player.player_id)
        llm_loc = random.choice(LOCATIONS)
        llm_spec = random.choice(SPECIALIZATIONS)
        opp_loc = random.choice(LOCATIONS)
        opp_spec = random.choice(SPECIALIZATIONS)
        await engine.submit_setup(llm_player.player_id, llm_loc, llm_spec)
        await engine.submit_setup(opponent.player_id, opp_loc, opp_spec)
        await engine.check_setup_complete()

        # Apply speed multiplier to catastrophe schedule
        for event in engine.state.catastrophe_schedule:
            event.scheduled_time = event.scheduled_time / speed_multiplier

        # Initialize LLM adapter and strategy
        adapter = LLMAdapter(model_config)
        strategy = self._get_strategy(opp_strat)

        # Turn loop
        valid_actions = 0
        invalid_actions = 0
        last_catastrophe_idx = 0

        for turn in range(1, max_turns + 1):
            # Check controls
            if self._abort or self._skip_game:
                break

            while self._paused:
                await asyncio.sleep(0.1)
                if self._abort:
                    break

            # Get state
            llm_state = engine.get_player_state(llm_player.player_id)

            # Get LLM action
            action_type = "PASS"
            action_valid = True
            rejection = None
            colony_snapshot = llm_state.get("colony", {})

            try:
                available = self._get_available_action_types(colony_snapshot)
                response = await adapter.get_action(llm_state, available)
                action_type = response["action_type"]
                payload = response["payload"]

                # Apply to engine
                if action_type != "PASS":
                    try:
                        await engine.handle_action(
                            llm_player.player_id,
                            ActionType(action_type.lower()),
                            payload,
                        )
                        valid_actions += 1
                    except ValueError as e:
                        action_valid = False
                        rejection = str(e)
                        invalid_actions += 1
                else:
                    valid_actions += 1

            except LLMError as e:
                action_valid = False
                rejection = str(e)
                invalid_actions += 1
                await self._queue.put(ErrorOccurred(
                    game_index=game_idx,
                    turn=turn,
                    model_name=model_config["name"],
                    error_type=e.error_type,
                    message=str(e),
                ))

            # Apply opponent actions
            if strategy and opponent.colony:
                opp_actions = strategy.decide_actions(opponent.colony, turn)
                for opp_action_type, opp_payload in opp_actions:
                    try:
                        await engine.handle_action(
                            opponent.player_id, opp_action_type, opp_payload
                        )
                    except ValueError:
                        pass

            # Advance tick
            await engine._tick()

            # Handle catastrophe phase immediately (skip wait)
            if engine.state.phase == GamePhase.CATASTROPHE:
                # Emit catastrophe event
                cat_idx = engine.state.current_catastrophe_index
                if cat_idx < len(engine.state.catastrophe_schedule):
                    cat_event = engine.state.catastrophe_schedule[cat_idx]
                    await self._queue.put(CatastropheTriggered(
                        game_index=game_idx,
                        turn=turn,
                        model_name=model_config["name"],
                        catastrophe_name=cat_event.catastrophe_id,
                        catastrophe_id=cat_event.catastrophe_id,
                        severity=cat_event.severity if hasattr(cat_event, "severity") else 1,
                    ))
                await engine._end_catastrophe()

            # Get score for this turn
            scores = engine._calculate_scores()
            llm_score = 0.0
            for s in scores:
                if s.get("player_id") == llm_player.player_id:
                    llm_score = s.get("score", 0)
                    break

            # Emit turn event
            await self._queue.put(TurnCompleted(
                game_index=game_idx,
                turn=turn,
                max_turns=max_turns,
                model_name=model_config["name"],
                model_index=model_idx,
                action_type=action_type,
                action_valid=action_valid,
                rejection_reason=rejection,
                colony_state=engine.get_player_state(llm_player.player_id).get("colony", {}),
                score=llm_score,
            ))

            # Check game end
            if engine.state.phase == GamePhase.FINISHED:
                break

        # Final scores
        final_scores = engine._calculate_scores()
        llm_final = 0.0
        for s in final_scores:
            if s.get("player_id") == llm_player.player_id:
                llm_final = s.get("score", 0)
                break

        return {
            "model_name": model_config["name"],
            "model_index": model_idx,
            "opponent_strategy": opp_strat,
            "score": llm_final,
            "turns_played": min(turn, max_turns) if "turn" in dir() else 0,
            "valid_actions": valid_actions,
            "invalid_actions": invalid_actions,
            "scores": final_scores,
            "seed": seed,
        }

    def _get_strategy(self, name: str):
        """Get a strategy instance by name."""
        from tools.balance.strategies import STRATEGY_MAP
        cls = STRATEGY_MAP.get(name)
        return cls() if cls else None

    def _get_available_action_types(self, colony: dict[str, Any]) -> list[str]:
        """Get list of broadly available action types for the given colony state."""
        actions = ["ALLOCATE_WORKERS", "PASS"]
        buildings = colony.get("buildings", [])
        building_types = {b.get("building_type", b.get("type", "")) for b in buildings}

        # Can build if there are unbuilt building types
        all_types = {"farm", "mine", "laboratory", "market", "hospital", "wall", "warehouse", "housing", "school", "watchtower"}
        if all_types - building_types:
            actions.append("BUILD")
        # Can upgrade if any building < level 3
        if any(b.get("level", 0) < 3 and not b.get("under_construction", False) for b in buildings):
            actions.append("UPGRADE")
        # Can trade if gold > 0 or resources > 0
        resources = colony.get("resources", {})
        if resources.get("gold", 0) > 0:
            actions.append("TRADE_BUY")
        if any(resources.get(r, 0) > 0 for r in ("food", "materials", "knowledge")):
            actions.append("TRADE_SELL")
        # Can repair if damaged
        if any(b.get("health", 100) < b.get("max_health", 100) for b in buildings):
            actions.append("REPAIR")
        # Can demolish if has buildings
        if buildings:
            actions.append("DEMOLISH")
        return actions

    def _aggregate_results(self, game_results: list[dict[str, Any]]) -> dict[str, Any]:
        """Aggregate all game results into a final results payload."""
        models = self._config["models"]
        model_stats: dict[str, dict[str, Any]] = {}

        for model in models:
            name = model["name"]
            model_games = [r for r in game_results if r["model_name"] == name]
            if not model_games:
                continue

            scores = [r["score"] for r in model_games]
            valid = sum(r["valid_actions"] for r in model_games)
            invalid = sum(r["invalid_actions"] for r in model_games)
            total_actions = valid + invalid

            model_stats[name] = {
                "games_played": len(model_games),
                "avg_score": sum(scores) / len(scores) if scores else 0,
                "max_score": max(scores) if scores else 0,
                "min_score": min(scores) if scores else 0,
                "valid_action_rate": valid / total_actions if total_actions > 0 else 0,
                "total_valid": valid,
                "total_invalid": invalid,
                "scores": scores,
            }

        # Sort by avg score descending
        rankings = sorted(model_stats.items(), key=lambda x: x[1]["avg_score"], reverse=True)

        return {
            "rankings": [
                {
                    "rank": i + 1,
                    "name": name,
                    "score": stats["avg_score"],
                    "max_score": stats["max_score"],
                    "min_score": stats["min_score"],
                    "games_played": stats["games_played"],
                    "valid_rate": stats["valid_action_rate"],
                    "trend": "—",
                    "archetype": "—",
                    "consistency": stats["max_score"] - stats["min_score"],
                }
                for i, (name, stats) in enumerate(rankings)
            ],
            "model_stats": model_stats,
            "game_results": game_results,
            "total_games": len(game_results),
            "elapsed_seconds": time.time() - self._start_time,
        }

    @staticmethod
    async def _noop_broadcast(*args: Any, **kwargs: Any) -> None:
        pass
