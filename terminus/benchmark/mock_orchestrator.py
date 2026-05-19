"""Mock orchestrator — simulates benchmark progress for TUI testing."""

from __future__ import annotations

import asyncio
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


class MockOrchestrator:
    """Simulates benchmark execution with fake data for TUI testing."""

    def __init__(self, config: dict[str, Any], event_queue: asyncio.Queue[BenchmarkEvent]) -> None:
        self._config = config
        self._queue = event_queue
        self._paused = False
        self._abort = False
        self._skip_game = False
        self._start_time: float = 0.0

        models = config.get("models", [])
        num_games = config.get("num_games", 10)
        num_opponents = config.get("num_opponents", 6)
        self._total_games = len(models) * num_opponents * num_games

    @property
    def total_games(self) -> int:
        return self._total_games

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

    async def run(self) -> dict[str, Any]:
        """Simulate a full benchmark run with delays."""
        self._start_time = time.time()
        models = self._config.get("models", [])
        num_games = self._config.get("num_games", 10)
        num_opponents = self._config.get("num_opponents", 6)
        max_turns = self._config.get("max_turns", 100)
        num_catastrophes = self._config.get("num_catastrophes", 5)

        # Simulate delay per turn (much faster than real LLM)
        turn_delay = 0.05  # 50ms per turn for testing

        game_idx = 0
        all_results: list[dict[str, Any]] = []
        opponent_names = ["balanced", "aggressive", "hoarder", "researcher", "balanced", "aggressive", "hoarder", "researcher"]

        for model_idx, model in enumerate(models):
            model_name = model["name"]
            model_score_base = random.uniform(50, 80)

            for opp_idx in range(num_opponents):
                opp_strat = opponent_names[opp_idx % len(opponent_names)]

                for game_num in range(num_games):
                    if self._abort:
                        break

                    self._skip_game = False
                    seed = 42 + game_idx

                    await self._queue.put(GameStarted(
                        game_index=game_idx,
                        model_name=model_name,
                        model_index=model_idx,
                        opponent_strategy=opp_strat,
                        seed=seed,
                    ))

                    # Simulate turns
                    valid = 0
                    invalid = 0
                    score = model_score_base + random.uniform(-10, 10)
                    cat_range_end = max(max_turns - 5, 2)
                    cat_range_start = min(10, cat_range_end - 1)
                    cat_pool = range(max(1, cat_range_start), cat_range_end)
                    num_cats_this_game = min(num_catastrophes, len(cat_pool))
                    catastrophe_turns = sorted(random.sample(list(cat_pool), num_cats_this_game)) if num_cats_this_game > 0 else []
                    turns_played = 0

                    for turn in range(1, max_turns + 1):
                        if self._abort or self._skip_game:
                            break

                        while self._paused:
                            await asyncio.sleep(0.05)
                            if self._abort:
                                break

                        turns_played = turn

                        # Simulate action
                        action_valid = random.random() > 0.1  # 90% valid
                        action_type = random.choice(["BUILD", "ALLOCATE_WORKERS", "TRADE_BUY", "UPGRADE", "PASS"])

                        if action_valid:
                            valid += 1
                        else:
                            invalid += 1
                            action_type = random.choice(["BUILD", "UPGRADE"])

                        # Simulate score progression
                        score += random.uniform(-0.5, 1.5)

                        # Emit catastrophe if scheduled
                        if turn in catastrophe_turns:
                            cat_names = ["drought", "earthquake", "plague", "raiders", "meteor"]
                            cat_name = random.choice(cat_names)
                            await self._queue.put(CatastropheTriggered(
                                game_index=game_idx,
                                turn=turn,
                                model_name=model_name,
                                catastrophe_name=cat_name,
                                catastrophe_id=cat_name,
                                severity=random.randint(1, 3),
                            ))
                            score -= random.uniform(2, 8)

                        # Simulate occasional errors
                        if random.random() < 0.02:
                            await self._queue.put(ErrorOccurred(
                                game_index=game_idx,
                                turn=turn,
                                model_name=model_name,
                                error_type=random.choice(["timeout", "parse_error"]),
                                message="Simulated error for testing",
                            ))

                        # Fake colony state
                        colony = {
                            "resources": {
                                "food": max(0, 100 + turn * 2 + random.uniform(-20, 20)),
                                "materials": max(0, 80 + turn * 1.5 + random.uniform(-15, 15)),
                                "knowledge": max(0, 10 + turn * 0.8 + random.uniform(-5, 5)),
                                "gold": max(0, 50 + turn * 1 + random.uniform(-10, 10)),
                            },
                            "population": min(30, 10 + turn // 10),
                            "morale": max(3.0, min(10.0, 7.0 + random.uniform(-1, 1))),
                            "workers": {
                                "farming": 4, "mining": 3, "research": 2,
                                "construction": 1, "defense": 1, "medicine": 1,
                            },
                            "buildings": [
                                {"building_type": "farm", "level": 1, "health": 100, "max_health": 100, "under_construction": False},
                            ],
                        }

                        await self._queue.put(TurnCompleted(
                            game_index=game_idx,
                            turn=turn,
                            max_turns=max_turns,
                            model_name=model_name,
                            model_index=model_idx,
                            action_type=action_type,
                            action_valid=action_valid,
                            rejection_reason=None if action_valid else "Simulated rejection",
                            colony_state=colony,
                            score=score,
                        ))

                        await asyncio.sleep(turn_delay)

                    # Game complete
                    all_results.append({
                        "model_name": model_name,
                        "score": score,
                        "turns_played": turns_played,
                        "valid_actions": valid,
                        "invalid_actions": invalid,
                    })

                    await self._queue.put(GameCompleted(
                        game_index=game_idx,
                        model_name=model_name,
                        model_index=model_idx,
                        opponent_strategy=opp_strat,
                        final_score=score,
                        turns_played=turns_played,
                        valid_actions=valid,
                        invalid_actions=invalid,
                    ))

                    game_idx += 1

                if self._abort:
                    break
            if self._abort:
                break

        elapsed = time.time() - self._start_time
        results = self._aggregate(all_results, models)

        await self._queue.put(BenchmarkCompleted(
            total_games=len(all_results),
            total_turns=sum(r["turns_played"] for r in all_results),
            elapsed_seconds=elapsed,
            results=results,
        ))

        return results

    def _aggregate(self, game_results: list[dict[str, Any]], models: list[dict[str, Any]]) -> dict[str, Any]:
        """Aggregate mock results."""
        rankings = []
        for i, model in enumerate(models):
            name = model["name"]
            model_games = [r for r in game_results if r["model_name"] == name]
            if not model_games:
                continue
            scores = [r["score"] for r in model_games]
            valid = sum(r["valid_actions"] for r in model_games)
            invalid = sum(r["invalid_actions"] for r in model_games)
            total = valid + invalid
            rankings.append({
                "rank": 0,
                "name": name,
                "score": sum(scores) / len(scores),
                "max_score": max(scores),
                "min_score": min(scores),
                "games_played": len(model_games),
                "valid_rate": valid / total if total > 0 else 0,
                "trend": "↑" if scores[-1] > scores[0] else "↓",
                "archetype": "—",
                "consistency": max(scores) - min(scores),
            })

        rankings.sort(key=lambda x: x["score"], reverse=True)
        for i, r in enumerate(rankings):
            r["rank"] = i + 1

        return {
            "rankings": rankings,
            "game_results": game_results,
            "total_games": len(game_results),
            "elapsed_seconds": time.time() - self._start_time,
        }
