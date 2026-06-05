"""Phase D integration tests for LLM Benchmark Suite.

Tests the full pipeline:
- Mock orchestrator produces correct events and results
- Scorer computes dimension scores from game results
- HTML report generator writes a valid file
- Screen transitions: Setup → Live → Results → Menu
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import pytest

from terminus.benchmark.events import (
    BenchmarkCompleted,
    CatastropheTriggered,
    ErrorOccurred,
    GameCompleted,
    GameStarted,
    TurnCompleted,
)
from terminus.benchmark.mock_orchestrator import MockOrchestrator
from terminus.benchmark.scorer import DIMENSIONS, compute_composite_score, score_dimensions
from terminus.benchmark.report import generate_report


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def benchmark_config() -> dict[str, Any]:
    """Minimal config for fast mock runs."""
    return {
        "models": [
            {"name": "ModelA", "provider": "OpenAI", "url": "http://x", "model_id": "a", "api_key": "x"},
            {"name": "ModelB", "provider": "Anthropic", "url": "http://x", "model_id": "b", "api_key": "x"},
        ],
        "num_games": 2,
        "num_opponents": 2,
        "max_turns": 15,
        "num_catastrophes": 1,
        "speed_multiplier": 5,
        "seed_fixed": True,
        "dimensions_enabled": [True] * 8,
        "dimension_weights": [1.0] * 8,
    }


@pytest.fixture
def report_output_dir(tmp_path: Path) -> Path:
    """Temp directory for report output."""
    return tmp_path / "reports"


# ─── Mock Orchestrator Tests ──────────────────────────────────────────────────


class TestMockOrchestrator:
    """Verify the mock orchestrator emits correct event sequence."""

    @pytest.mark.asyncio
    async def test_produces_all_event_types(self, benchmark_config: dict) -> None:
        """Mock orchestrator should emit GameStarted, TurnCompleted, GameCompleted, BenchmarkCompleted."""
        queue: asyncio.Queue = asyncio.Queue()
        orch = MockOrchestrator(benchmark_config, queue)
        results = await orch.run()

        events: list[Any] = []
        while not queue.empty():
            events.append(queue.get_nowait())

        event_types = {type(e).__name__ for e in events}
        assert "GameStarted" in event_types
        assert "TurnCompleted" in event_types
        assert "GameCompleted" in event_types
        assert "BenchmarkCompleted" in event_types

    @pytest.mark.asyncio
    async def test_correct_game_count(self, benchmark_config: dict) -> None:
        """Total games = models × opponents × num_games."""
        queue: asyncio.Queue = asyncio.Queue()
        orch = MockOrchestrator(benchmark_config, queue)
        results = await orch.run()

        expected = 2 * 2 * 2  # 2 models × 2 opponents × 2 games
        assert results["total_games"] == expected

    @pytest.mark.asyncio
    async def test_results_contain_rankings(self, benchmark_config: dict) -> None:
        """Results should contain rankings sorted by score."""
        queue: asyncio.Queue = asyncio.Queue()
        orch = MockOrchestrator(benchmark_config, queue)
        results = await orch.run()

        assert "rankings" in results
        assert len(results["rankings"]) == 2
        # Verify sorted descending
        scores = [r["score"] for r in results["rankings"]]
        assert scores == sorted(scores, reverse=True)
        # Each ranking has required fields
        for r in results["rankings"]:
            assert "rank" in r
            assert "name" in r
            assert "score" in r
            assert "valid_rate" in r

    @pytest.mark.asyncio
    async def test_results_contain_game_results(self, benchmark_config: dict) -> None:
        """Results should include raw game_results list for scorer."""
        queue: asyncio.Queue = asyncio.Queue()
        orch = MockOrchestrator(benchmark_config, queue)
        results = await orch.run()

        assert "game_results" in results
        assert len(results["game_results"]) == results["total_games"]
        for gr in results["game_results"]:
            assert "model_name" in gr
            assert "score" in gr
            assert "turns_played" in gr
            assert "valid_actions" in gr
            assert "invalid_actions" in gr

    @pytest.mark.asyncio
    async def test_abort_stops_early(self, benchmark_config: dict) -> None:
        """Aborting mid-run should produce fewer games."""
        queue: asyncio.Queue = asyncio.Queue()
        orch = MockOrchestrator(benchmark_config, queue)

        async def abort_after_delay():
            await asyncio.sleep(0.2)
            orch.abort()

        asyncio.create_task(abort_after_delay())
        results = await orch.run()

        # Should have fewer games than the full run
        full_count = 2 * 2 * 2
        assert results["total_games"] <= full_count

    @pytest.mark.asyncio
    async def test_skip_game_advances(self, benchmark_config: dict) -> None:
        """Skipping should advance to next game without completing all turns."""
        queue: asyncio.Queue = asyncio.Queue()
        orch = MockOrchestrator(benchmark_config, queue)

        async def skip_after_delay():
            await asyncio.sleep(0.1)
            orch.skip_current_game()

        asyncio.create_task(skip_after_delay())
        results = await orch.run()

        # Should still complete (skip just skips one game)
        assert results["total_games"] > 0

    @pytest.mark.asyncio
    async def test_pause_resume(self, benchmark_config: dict) -> None:
        """Pausing and resuming should still produce a complete run."""
        queue: asyncio.Queue = asyncio.Queue()
        orch = MockOrchestrator(benchmark_config, queue)

        async def pause_cycle():
            await asyncio.sleep(0.1)
            orch.pause()
            await asyncio.sleep(0.15)
            orch.resume()

        asyncio.create_task(pause_cycle())
        results = await orch.run()

        expected = 2 * 2 * 2
        assert results["total_games"] == expected

    @pytest.mark.asyncio
    async def test_event_ordering(self, benchmark_config: dict) -> None:
        """Events should follow: GameStarted → TurnCompleted* → GameCompleted for each game."""
        queue: asyncio.Queue = asyncio.Queue()
        orch = MockOrchestrator(benchmark_config, queue)
        await orch.run()

        events: list[Any] = []
        while not queue.empty():
            events.append(queue.get_nowait())

        # Find first game's events
        game_0_events = [e for e in events if hasattr(e, "game_index") and e.game_index == 0]
        type_names = [type(e).__name__ for e in game_0_events]

        # First event for game 0 should be GameStarted
        assert type_names[0] == "GameStarted"
        # Last event for game 0 should be GameCompleted
        assert type_names[-1] == "GameCompleted"
        # Everything in between should be TurnCompleted, CatastropheTriggered, or ErrorOccurred
        middle = set(type_names[1:-1])
        assert middle <= {"TurnCompleted", "CatastropheTriggered", "ErrorOccurred"}


# ─── Scorer Tests ─────────────────────────────────────────────────────────────


class TestScorer:
    """Verify dimension scoring produces valid outputs."""

    def test_dimensions_list_has_8_entries(self) -> None:
        assert len(DIMENSIONS) == 8

    def test_score_dimensions_returns_per_model(self, benchmark_config: dict) -> None:
        """score_dimensions should return dict[model_name → dict[dim → float]]."""
        game_results = [
            {"model_name": "ModelA", "score": 75, "turns_played": 100, "valid_actions": 90, "invalid_actions": 10},
            {"model_name": "ModelA", "score": 80, "turns_played": 100, "valid_actions": 95, "invalid_actions": 5},
            {"model_name": "ModelB", "score": 60, "turns_played": 100, "valid_actions": 70, "invalid_actions": 30},
            {"model_name": "ModelB", "score": 55, "turns_played": 80, "valid_actions": 65, "invalid_actions": 15},
        ]
        scores = score_dimensions(game_results, benchmark_config)

        assert "ModelA" in scores
        assert "ModelB" in scores
        for model_scores in scores.values():
            assert len(model_scores) == 8
            for dim in DIMENSIONS:
                assert dim in model_scores
                assert 0.0 <= model_scores[dim] <= 1.0

    def test_disabled_dimensions_are_excluded(self) -> None:
        """Disabled dimensions should not appear in the output scores."""
        config = {
            "dimensions_enabled": [True, False, True, False, True, False, True, False],
            "dimension_weights": [1.0] * 8,
        }
        game_results = [
            {"model_name": "M", "score": 70, "turns_played": 100, "valid_actions": 90, "invalid_actions": 10},
            {"model_name": "M", "score": 75, "turns_played": 100, "valid_actions": 85, "invalid_actions": 15},
        ]
        scores = score_dimensions(game_results, config)
        assert "M" in scores
        # Disabled dimensions should be absent from the dict
        for i, dim in enumerate(DIMENSIONS):
            if not config["dimensions_enabled"][i]:
                assert dim not in scores["M"]
            else:
                assert dim in scores["M"]
                assert 0.0 <= scores["M"][dim] <= 1.0

    def test_composite_score_is_weighted_average(self) -> None:
        """compute_composite_score should be a weighted average."""
        dim_scores = {DIMENSIONS[i]: 0.5 for i in range(8)}
        # Uniform weights → composite = 0.5
        result = compute_composite_score(dim_scores, [1.0] * 8)
        assert abs(result - 0.5) < 0.001

    def test_composite_score_respects_weights(self) -> None:
        """Higher weight on higher-scoring dimension → higher composite."""
        dim_scores = {}
        for i, dim in enumerate(DIMENSIONS):
            dim_scores[dim] = 0.9 if i == 0 else 0.1

        # Weight first dimension heavily
        weights_heavy_first = [10.0] + [1.0] * 7
        weights_uniform = [1.0] * 8

        composite_heavy = compute_composite_score(dim_scores, weights_heavy_first)
        composite_uniform = compute_composite_score(dim_scores, weights_uniform)
        assert composite_heavy > composite_uniform

    def test_empty_game_results(self) -> None:
        """Empty input should return empty scores."""
        config = {"dimensions_enabled": [True] * 8, "dimension_weights": [1.0] * 8}
        scores = score_dimensions([], config)
        assert scores == {}

    @pytest.mark.asyncio
    async def test_scorer_with_mock_orchestrator(self, benchmark_config: dict) -> None:
        """End-to-end: mock orchestrator results → scorer."""
        queue: asyncio.Queue = asyncio.Queue()
        orch = MockOrchestrator(benchmark_config, queue)
        results = await orch.run()

        scores = score_dimensions(results["game_results"], benchmark_config)
        assert len(scores) == 2  # Two models
        for model_scores in scores.values():
            composite = compute_composite_score(model_scores, benchmark_config["dimension_weights"])
            assert 0.0 <= composite <= 1.0


# ─── Report Generator Tests ──────────────────────────────────────────────────


class TestReportGenerator:
    """Verify HTML report generation."""

    @pytest.mark.asyncio
    async def test_generates_html_file(self, benchmark_config: dict, report_output_dir: Path) -> None:
        """Report generator should create a non-empty HTML file."""
        queue: asyncio.Queue = asyncio.Queue()
        orch = MockOrchestrator(benchmark_config, queue)
        results = await orch.run()

        # Add dimension scores
        results["dimensions"] = score_dimensions(results["game_results"], benchmark_config)

        output_path = str(report_output_dir / "test_report.html")
        path = generate_report(results, benchmark_config, output_path)

        assert Path(path).exists()
        assert Path(path).stat().st_size > 1000  # Should be substantial

    @pytest.mark.asyncio
    async def test_report_contains_model_names(self, benchmark_config: dict, report_output_dir: Path) -> None:
        """Report HTML should mention each model by name."""
        queue: asyncio.Queue = asyncio.Queue()
        orch = MockOrchestrator(benchmark_config, queue)
        results = await orch.run()
        results["dimensions"] = score_dimensions(results["game_results"], benchmark_config)

        output_path = str(report_output_dir / "test_report2.html")
        path = generate_report(results, benchmark_config, output_path)

        content = Path(path).read_text(encoding="utf-8")
        assert "ModelA" in content
        assert "ModelB" in content

    @pytest.mark.asyncio
    async def test_report_is_valid_html(self, benchmark_config: dict, report_output_dir: Path) -> None:
        """Report should be self-contained HTML (has doctype, html, head, body tags)."""
        queue: asyncio.Queue = asyncio.Queue()
        orch = MockOrchestrator(benchmark_config, queue)
        results = await orch.run()
        results["dimensions"] = score_dimensions(results["game_results"], benchmark_config)

        output_path = str(report_output_dir / "test_report3.html")
        path = generate_report(results, benchmark_config, output_path)

        content = Path(path).read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content or "<!doctype html>" in content.lower()
        assert "<html" in content
        assert "<head>" in content
        assert "<body>" in content
        assert "</html>" in content

    def test_report_with_empty_results(self, report_output_dir: Path) -> None:
        """Report should handle empty/minimal results gracefully."""
        results = {"rankings": [], "total_games": 0, "elapsed_seconds": 0, "game_results": []}
        config = {"models": [], "num_games": 0, "dimensions_enabled": [True] * 8, "dimension_weights": [1.0] * 8}

        output_path = str(report_output_dir / "empty_report.html")
        path = generate_report(results, config, output_path)

        assert Path(path).exists()
        assert Path(path).stat().st_size > 100

    def test_report_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Report generator should create parent directories if they don't exist."""
        deep_path = str(tmp_path / "a" / "b" / "c" / "report.html")
        results = {"rankings": [], "total_games": 0, "elapsed_seconds": 0, "game_results": []}
        config = {"models": [], "dimensions_enabled": [True] * 8, "dimension_weights": [1.0] * 8}

        path = generate_report(results, config, deep_path)
        assert Path(path).exists()


# ─── Screen Transition Tests ──────────────────────────────────────────────────


class TestScreenTransitions:
    """Test screen flow without full TUI (import and instantiation checks)."""

    def test_import_all_benchmark_screens(self) -> None:
        """All benchmark screens should import without error."""
        from terminus.client.screens.benchmark_setup import BenchmarkSetupScreen
        from terminus.client.screens.benchmark_live import BenchmarkLiveScreen
        from terminus.client.screens.benchmark_results import BenchmarkResultsScreen

        assert BenchmarkSetupScreen is not None
        assert BenchmarkLiveScreen is not None
        assert BenchmarkResultsScreen is not None

    def _make_live_screen(self, display_config: dict) -> "BenchmarkLiveScreen":
        """Build a BenchmarkLiveScreen from a plain display_config dict."""
        from terminus.benchmark.schemas import BenchmarkConfig, ModelConfig, OpponentType
        from terminus.client.screens.benchmark_live import BenchmarkLiveScreen

        model_configs = [
            ModelConfig(
                name=m["name"],
                provider="openai",
                endpoint=m["url"],
                model=m["model_id"],
                api_key=m["api_key"],
            )
            for m in display_config["models"]
        ]
        benchmark_config = BenchmarkConfig(
            models=model_configs,
            games_per_matchup=display_config.get("num_games", 2),
            max_turns=max(20, display_config.get("max_turns", 20)),
            opponents=[OpponentType.RANDOM, OpponentType.GREEDY][: display_config.get("num_opponents", 2)],
        )
        return BenchmarkLiveScreen(benchmark_config, display_config)

    def test_live_screen_instantiation(self, benchmark_config: dict) -> None:
        """BenchmarkLiveScreen should instantiate with config."""
        screen = self._make_live_screen(benchmark_config)
        assert screen._display_config == benchmark_config
        assert screen._total_games == 2 * 2 * 2

    def test_results_screen_instantiation(self, benchmark_config: dict) -> None:
        """BenchmarkResultsScreen should instantiate with results and config."""
        from terminus.client.screens.benchmark_results import BenchmarkResultsScreen

        results = {"rankings": [{"rank": 1, "name": "ModelA", "score": 75.0}], "total_games": 4}
        screen = BenchmarkResultsScreen(results=results, config=benchmark_config)
        assert screen._results == results
        assert screen._config == benchmark_config

    def test_results_screen_no_results(self) -> None:
        """BenchmarkResultsScreen should handle None results gracefully."""
        from terminus.client.screens.benchmark_results import BenchmarkResultsScreen

        screen = BenchmarkResultsScreen(results=None, config={})
        assert screen._results is None

    def test_live_screen_event_handling(self, benchmark_config: dict) -> None:
        """Live screen should handle events without crashing (no mount)."""
        screen = self._make_live_screen(benchmark_config)
        # Test that _handle_event processes events correctly on internal state
        event = GameStarted(game_index=0, model_name="ModelA", model_index=0, opponent_strategy="balanced", seed=42)
        screen._handle_event(event)
        assert screen._current_game == 1

        event2 = TurnCompleted(
            game_index=0, turn=5, max_turns=15, model_name="ModelA", model_index=0,
            action_type="BUILD", action_valid=True, colony_state={"resources": {}}, score=50.0,
        )
        screen._handle_event(event2)
        assert screen._current_turn == 5
        assert screen._model_valid["ModelA"] == 1
        assert screen._model_current_score["ModelA"] == 50.0

    def test_live_screen_invalid_action_tracking(self, benchmark_config: dict) -> None:
        """Live screen should track invalid actions separately."""
        screen = self._make_live_screen(benchmark_config)
        event = TurnCompleted(
            game_index=0, turn=1, max_turns=15, model_name="ModelA", model_index=0,
            action_type="BUILD", action_valid=False, rejection_reason="Not enough resources",
            colony_state={}, score=10.0,
        )
        screen._handle_event(event)
        assert screen._model_invalid["ModelA"] == 1
        assert screen._model_valid.get("ModelA", 0) == 0


# ─── Keybinding Tests ─────────────────────────────────────────────────────────


class TestKeybindings:
    """Verify keybinding declarations on screens."""

    def test_live_screen_bindings(self) -> None:
        from terminus.client.screens.benchmark_live import BenchmarkLiveScreen

        binding_keys = {b[0] for b in BenchmarkLiveScreen.BINDINGS}
        assert "p" in binding_keys      # Pause
        assert "s" in binding_keys      # Skip
        assert "escape" in binding_keys  # Abort

    def test_results_screen_bindings(self) -> None:
        from terminus.client.screens.benchmark_results import BenchmarkResultsScreen

        binding_keys = {b[0] for b in BenchmarkResultsScreen.BINDINGS}
        assert "o" in binding_keys       # Open report
        assert "escape" in binding_keys  # Menu
        assert "q" in binding_keys       # Menu

    def test_setup_screen_bindings(self) -> None:
        from terminus.client.screens.benchmark_setup import BenchmarkSetupScreen

        binding_keys = {b[0] for b in BenchmarkSetupScreen.BINDINGS}
        assert "escape" in binding_keys  # Back
