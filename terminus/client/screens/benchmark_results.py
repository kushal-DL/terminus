"""Benchmark Results screen — final rankings, dimension scores, and HTML report path."""

from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Label, Static


class BenchmarkResultsScreen(Screen):
    """Results screen showing final benchmark outcomes and HTML report location."""

    BINDINGS = [
        ("o", "open_report", "Open Report"),
        ("escape", "go_menu", "Menu"),
        ("q", "go_menu", "Menu"),
    ]

    def __init__(self, results: dict | None = None, config: dict | None = None) -> None:
        super().__init__()
        self._results = results
        self._config = config or {}
        self._report_path: str | None = None
        self._dimension_scores: dict[str, dict[str, float]] = {}

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="benchmark-results-scroll"):
            yield Static("╔══════════════════════════════════════════════╗", classes="bench-header")
            yield Static("║          BENCHMARK COMPLETE                  ║", classes="bench-header")
            yield Static("╚══════════════════════════════════════════════╝", classes="bench-header")
            yield Label("")

            # ─── Summary Stats ────────────────────────────────────
            yield Static("", id="results-summary-stats")
            yield Label("")

            # ─── Report Path (prominent) ──────────────────────────
            yield Static("", id="report-path-box")
            yield Label("")

            # ─── Final Rankings ────────────────────────────────────
            yield Static("─── Final Rankings ───", classes="panel-title")
            yield DataTable(id="results-rankings")
            yield Label("")

            # ─── Dimension Breakdown ──────────────────────────────
            yield Static("─── Dimension Breakdown ───", classes="panel-title")
            yield Static("", id="results-dimensions")
            yield Label("")

            # ─── Trend Analysis ───────────────────────────────────
            yield Static("─── Trend Analysis ───", classes="panel-title")
            yield Static("", id="results-trends")
            yield Label("")

            # ─── Error Summary ────────────────────────────────────
            yield Static("─── Error Summary ───", classes="panel-title")
            yield Static("", id="results-errors")
            yield Label("")

            # ─── Bottom Actions ───────────────────────────────────
            with Horizontal(id="results-bottom-bar"):
                yield Button("[Open in Browser]", id="btn-open-report", variant="success")
                yield Button("[Return to Menu]", id="btn-return-menu", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self._compute_dimensions()
        self._generate_report()
        self._populate_results()

    def _compute_dimensions(self) -> None:
        """Compute dimension scores from results data."""
        if not self._results:
            return
        try:
            from terminus.benchmark.scorer import score_dimensions

            # Use game_results directly if available (preferred)
            game_results: list[dict[str, Any]] = self._results.get("game_results", [])

            # Fallback: reconstruct from model_stats
            if not game_results and "model_stats" in self._results:
                model_stats = self._results.get("model_stats", {})
                for name, stats in model_stats.items():
                    scores = stats.get("scores", [])
                    games_played = stats.get("games_played", len(scores))
                    valid = stats.get("total_valid", 0)
                    invalid = stats.get("total_invalid", 0)
                    per_game_valid = valid // max(games_played, 1)
                    per_game_invalid = invalid // max(games_played, 1)

                    for score in scores:
                        game_results.append({
                            "model_name": name,
                            "score": score,
                            "turns_played": self._config.get("max_turns", 100),
                            "valid_actions": per_game_valid,
                            "invalid_actions": per_game_invalid,
                        })

            if not game_results:
                return

            self._dimension_scores = score_dimensions(game_results, self._config)
            # Attach to results for report generation
            self._results["dimensions"] = self._dimension_scores
        except Exception:
            pass

    def _generate_report(self) -> None:
        """Generate the HTML report file."""
        from datetime import datetime

        report_dir = Path("./benchmark-results")
        report_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M")
        self._report_path = str(report_dir / f"{timestamp}_report.html")

        if self._results:
            try:
                from terminus.benchmark.report import generate_report
                self._report_path = generate_report(
                    self._results, self._config, self._report_path
                )
            except Exception:
                pass  # Report generation failed; path still set but file may not exist

    def _populate_results(self) -> None:
        """Populate the screen with benchmark results."""
        models = self._config.get("models", [])
        num_games = self._config.get("num_games", 10)
        num_opponents = self._config.get("num_opponents", 6)

        # Summary stats
        if self._results:
            total_games = self._results.get("total_games", 0)
            elapsed = self._results.get("elapsed_seconds", 0)
            elapsed_str = f"{elapsed / 60:.1f} min" if elapsed < 3600 else f"{elapsed / 3600:.1f} hrs"
            self.query_one("#results-summary-stats", Static).update(
                f"  {total_games} games │ {len(models)} models │ "
                f"Duration: {elapsed_str} │ Speed: {self._config.get('speed_multiplier', 1)}×"
            )
        else:
            total_games = len(models) * num_opponents * num_games
            self.query_one("#results-summary-stats", Static).update(
                f"  {total_games} games planned │ {len(models)} models │ "
                f"Benchmark incomplete"
            )

        # Report path display
        if self._report_path:
            report_exists = Path(self._report_path).exists()
            status = "✓ Generated" if report_exists else "⚠ Not generated"
            path_display = (
                f"  ╔═══════════════════════════════════════════════════════════╗\n"
                f"  ║  📄 HTML Report: {status:<40} ║\n"
                f"  ║     {self._report_path:<52} ║\n"
                f"  ║                                                           ║\n"
                f"  ║  Press 'o' or [Open in Browser] to view                   ║\n"
                f"  ╚═══════════════════════════════════════════════════════════╝"
            )
        else:
            path_display = "  No report generated."
        self.query_one("#report-path-box", Static).update(path_display)

        # Rankings table
        table = self.query_one("#results-rankings", DataTable)
        table.add_columns("#", "Model", "Avg Score", "Valid%", "Games", "Consistency")
        if self._results and "rankings" in self._results:
            for r in self._results["rankings"]:
                valid_str = f"{r.get('valid_rate', 0) * 100:.0f}%" if r.get("valid_rate") is not None else "—"
                table.add_row(
                    str(r.get("rank", "?")),
                    r["name"],
                    f"{r['score']:.1f}",
                    valid_str,
                    str(r.get("games_played", "—")),
                    f"±{r.get('consistency', 0):.1f}",
                )
        else:
            for i, model in enumerate(models, 1):
                table.add_row(str(i), model["name"], "—", "—", "—", "—")

        # Dimension breakdown
        if self._dimension_scores:
            from terminus.benchmark.scorer import DIMENSIONS
            lines = ["  Model             " + "  ".join(f"{d[:8]:<8}" for d in DIMENSIONS)]
            lines.append("  " + "─" * (18 + 10 * 8))
            for model_name, scores in self._dimension_scores.items():
                cells = []
                for dim in DIMENSIONS:
                    val = scores.get(dim, 0)
                    bar = "█" * int(val * 5) + "░" * (5 - int(val * 5))
                    cells.append(f"{bar}{val:.2f}"[:8])
                lines.append(f"  {model_name:<18}" + "  ".join(f"{c:<8}" for c in cells))
            self.query_one("#results-dimensions", Static).update("\n".join(lines))
        else:
            self.query_one("#results-dimensions", Static).update(
                "  No dimension scores available."
            )

        # Trends
        if self._results and "rankings" in self._results:
            trend_lines = []
            for r in self._results["rankings"]:
                trend = r.get("trend", "—")
                trend_lines.append(
                    f"  {r['name']:<15} {trend}  "
                    f"(range: {r.get('min_score', 0):.0f} – {r.get('max_score', 0):.0f})"
                )
            self.query_one("#results-trends", Static).update(
                "\n".join(trend_lines) if trend_lines else "  No trend data."
            )
        else:
            self.query_one("#results-trends", Static).update("  No trend data available.")

        # Errors
        self.query_one("#results-errors", Static).update("  See live screen logs for error details.")

    # ─── Button Handlers ─────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-open-report":
            self.action_open_report()
        elif event.button.id == "btn-return-menu":
            self.action_go_menu()

    # ─── Actions ─────────────────────────────────────────────────────────────

    def action_open_report(self) -> None:
        """Open the HTML report in the default browser."""
        if self._report_path:
            report = Path(self._report_path)
            if report.exists():
                webbrowser.open(report.resolve().as_uri())
            else:
                self.notify("Report file not found (benchmark may not have completed)", severity="warning")
        else:
            self.notify("No report path available", severity="warning")

    def action_go_menu(self) -> None:
        """Return to main menu by popping benchmark screens off the stack."""
        # Pop: Results → Live → Setup → Main Menu
        # Use dismiss chain: pop self, then the underlying screens
        screen_stack = list(self.app.screen_stack)
        # Pop all screens above the base (main menu is at index 0)
        screens_to_pop = len(screen_stack) - 1
        for _ in range(screens_to_pop):
            self.app.pop_screen()
