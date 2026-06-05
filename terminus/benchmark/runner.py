"""Benchmark Runner — coordinates a complete benchmark run across all games."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from terminus.benchmark.agent import create_adapter, LLMAdapter
from terminus.benchmark.events import (
    BenchmarkCompleted,
    BenchmarkEvent,
    GameCompleted,
    GameStarted,
)
from terminus.benchmark.orchestrator_v2 import BenchmarkOrchestrator
from terminus.benchmark.schemas import BenchmarkConfig, GameRecording, ModelConfig

logger = logging.getLogger(__name__)


@dataclass
class GamePlanEntry:
    """A single game to run in the benchmark plan."""

    model_config: ModelConfig
    opponent_type: str
    game_number: int
    seed: int


class BenchmarkRunner:
    """Coordinates a complete benchmark run across all models × opponents × games."""

    def __init__(
        self,
        config: BenchmarkConfig,
        event_queue: asyncio.Queue[BenchmarkEvent] | None = None,
        display_config: dict[str, Any] | None = None,
    ):
        self._config = config
        self._event_queue = event_queue
        self._display_config = display_config or {}
        self._game_plan = self._build_game_plan()
        self._recordings: list[GameRecording] = []
        self._current_orchestrator: BenchmarkOrchestrator | None = None
        self._paused = False
        self._abort = False
        self._running = False
        self._start_time = 0.0

    @property
    def total_games(self) -> int:
        return len(self._game_plan)

    @property
    def completed_games(self) -> int:
        return len(self._recordings)

    @property
    def is_running(self) -> bool:
        return self._running

    def pause(self) -> None:
        self._paused = True
        if self._current_orchestrator:
            self._current_orchestrator.pause()

    def resume(self) -> None:
        self._paused = False
        if self._current_orchestrator:
            self._current_orchestrator.resume()

    def abort(self) -> None:
        self._abort = True
        if self._current_orchestrator:
            self._current_orchestrator.abort()

    def skip_current_game(self) -> None:
        if self._current_orchestrator:
            self._current_orchestrator.abort()

    async def run(self) -> list[GameRecording]:
        """Run all benchmark games and emit BenchmarkCompleted with full scored results."""
        self._running = True
        self._start_time = time.time()
        self._recordings = []

        adapters: dict[str, LLMAdapter] = {}

        try:
            for game_idx, entry in enumerate(self._game_plan):
                if self._abort:
                    break

                adapter = self._get_or_create_adapter(adapters, entry.model_config)

                if self._event_queue:
                    await self._event_queue.put(GameStarted(
                        game_index=game_idx,
                        model_name=entry.model_config.name,
                        model_index=self._get_model_index(entry.model_config),
                        opponent_strategy=entry.opponent_type,
                        seed=entry.seed,
                    ))

                orchestrator = BenchmarkOrchestrator(
                    adapter=adapter,
                    opponent_type=entry.opponent_type,
                    seed=entry.seed,
                    config=self._config,
                    event_queue=self._event_queue,
                    game_index=game_idx,
                )
                self._current_orchestrator = orchestrator

                recording = await orchestrator.run_game()
                self._recordings.append(recording)
                self._current_orchestrator = None

                if self._event_queue:
                    await self._event_queue.put(GameCompleted(
                        game_index=game_idx,
                        model_name=entry.model_config.name,
                        model_index=self._get_model_index(entry.model_config),
                        opponent_strategy=entry.opponent_type,
                        final_score=recording.final_score,
                        turns_played=len(recording.turns),
                        valid_actions=len(recording.turns) - recording.invalid_action_count,
                        invalid_actions=recording.invalid_action_count,
                    ))

        finally:
            self._running = False
            await self._emit_completed()

        return self._recordings

    # ─── Internal ─────────────────────────────────────────────────────────

    async def _emit_completed(self) -> None:
        """Run the scoring pipeline and emit BenchmarkCompleted."""
        elapsed = time.time() - self._start_time
        total_turns = sum(len(r.turns) for r in self._recordings)
        report_path: str | None = None
        full_results: dict[str, Any] = {}

        if self._recordings:
            try:
                from terminus.benchmark.results import BenchmarkResult, write_report
                bench_result = BenchmarkResult.from_recordings(
                    recordings=self._recordings,
                    config=self._config,
                    elapsed_seconds=elapsed,
                    config_dict=self._display_config,
                )
                full_results = bench_result.summary

                # Write all configured exports
                output_dir = self._config.output_dir if self._config.output_dir else "./benchmark-results"
                try:
                    report_path = write_report(bench_result, output_dir=output_dir)
                    logger.info(f"HTML report written to {report_path}")
                except Exception as exc:
                    logger.warning(f"HTML report write failed: {exc}")

                try:
                    from pathlib import Path
                    from terminus.benchmark.export import (
                        export_json, export_csv, export_markdown,
                        compute_statistics, format_statistics_md,
                    )
                    out = Path(output_dir)
                    ts = report_path.split("/")[-1].split("_report")[0] if report_path else "results"
                    export_json(bench_result, out / f"{ts}_results.json")
                    export_csv(bench_result, out / f"{ts}_summary.csv", mode="summary")
                    export_csv(bench_result, out / f"{ts}_detailed.csv", mode="detailed")
                    stats = compute_statistics(bench_result)
                    md_path = out / f"{ts}_summary.md"
                    export_markdown(bench_result, md_path)
                    # Append statistical analysis section to the markdown
                    existing = md_path.read_text(encoding="utf-8")
                    md_path.write_text(
                        existing + "\n" + format_statistics_md(stats),
                        encoding="utf-8",
                    )
                    logger.info(f"JSON/CSV/Markdown exports written to {output_dir}")
                except Exception as exc:
                    logger.warning(f"Secondary exports failed: {exc}")

            except Exception as exc:
                logger.error(f"Scoring pipeline failed: {exc}", exc_info=True)
                # Fall back to basic aggregation so the TUI still gets something
                full_results = self._aggregate_results_fallback(elapsed)
        else:
            full_results = self._aggregate_results_fallback(elapsed)

        if self._event_queue:
            await self._event_queue.put(BenchmarkCompleted(
                total_games=len(self._recordings),
                total_turns=total_turns,
                elapsed_seconds=elapsed,
                results=full_results,
                report_path=report_path,
            ))

    def _build_game_plan(self) -> list[GamePlanEntry]:
        """Generate the full game schedule: models × opponents × repetitions."""
        plan: list[GamePlanEntry] = []
        base_seed = self._config.base_seed
        game_idx = 0

        for model_config in self._config.models:
            for opponent_type in self._config.opponents:
                for game_num in range(self._config.games_per_matchup):
                    if self._config.seed_mode == "fixed":
                        seed = base_seed + game_idx
                    else:
                        import random
                        seed = random.randint(1, 999999)

                    plan.append(GamePlanEntry(
                        model_config=model_config,
                        opponent_type=opponent_type.value,
                        game_number=game_num,
                        seed=seed,
                    ))
                    game_idx += 1

        return plan

    def _get_or_create_adapter(
        self,
        adapters: dict[str, LLMAdapter],
        model_config: ModelConfig,
    ) -> LLMAdapter:
        key = model_config.name
        if key not in adapters:
            adapters[key] = create_adapter(model_config)
        return adapters[key]

    def _get_model_index(self, model_config: ModelConfig) -> int:
        for i, m in enumerate(self._config.models):
            if m.name == model_config.name:
                return i
        return 0

    def _aggregate_results_fallback(self, elapsed: float) -> dict[str, Any]:
        """Basic aggregation used when the scoring pipeline fails or no recordings exist."""
        model_stats: dict[str, dict[str, Any]] = {}

        for recording in self._recordings:
            name = recording.model_name
            if name not in model_stats:
                model_stats[name] = {
                    "games_played": 0,
                    "scores": [],
                    "total_valid": 0,
                    "total_invalid": 0,
                    "total_tokens": 0,
                    "total_duration": 0.0,
                    "dq_count": 0,
                }
            stats = model_stats[name]
            stats["games_played"] += 1
            stats["scores"].append(recording.final_score)
            stats["total_valid"] += len(recording.turns) - recording.invalid_action_count
            stats["total_invalid"] += recording.invalid_action_count
            stats["total_tokens"] += recording.total_tokens
            stats["total_duration"] += recording.duration_seconds
            if recording.dq_reason:
                stats["dq_count"] += 1

        rankings = []
        for name, stats in model_stats.items():
            scores = stats["scores"]
            total_actions = stats["total_valid"] + stats["total_invalid"]
            rankings.append({
                "rank": 0,
                "name": name,
                "score": sum(scores) / len(scores) if scores else 0,
                "max_score": max(scores) if scores else 0,
                "min_score": min(scores) if scores else 0,
                "consistency": max(scores) - min(scores) if len(scores) > 1 else 0,
                "games_played": stats["games_played"],
                "valid_rate": stats["total_valid"] / total_actions if total_actions > 0 else 0,
                "dq_count": stats["dq_count"],
                "trend": "—",
            })
        rankings.sort(key=lambda x: x["score"], reverse=True)
        for i, r in enumerate(rankings):
            r["rank"] = i + 1

        return {
            "rankings": rankings,
            "model_stats": model_stats,
            "dimensions": {},
            "game_results": [],
            "total_games": len(self._recordings),
            "elapsed_seconds": elapsed,
        }
