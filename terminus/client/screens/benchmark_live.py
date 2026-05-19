"""Benchmark Live monitoring screen — real-time game state and leaderboard."""

from __future__ import annotations

import asyncio
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Button, DataTable, Footer, Label, Static

from terminus.benchmark.events import (
    BenchmarkCompleted,
    BenchmarkEvent,
    CatastropheTriggered,
    ErrorOccurred,
    GameCompleted,
    GameStarted,
    TurnCompleted,
)


class BenchmarkLiveScreen(Screen):
    """Live monitoring screen showing leaderboard and game state during benchmark."""

    BINDINGS = [
        ("p", "toggle_pause", "Pause"),
        ("s", "skip_game", "Skip Game"),
        ("escape", "abort", "Abort"),
    ]

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__()
        self._config = config
        self._paused = False
        self._current_game = 0
        self._current_turn = 0
        self._total_games = (
            len(config.get("models", []))
            * config.get("num_opponents", 6)
            * config.get("num_games", 10)
        )
        self._max_turns = config.get("max_turns", 100)
        self._catastrophes_seen = 0

        # Event queue and orchestrator (set by _start_orchestrator)
        self._event_queue: asyncio.Queue[BenchmarkEvent] = asyncio.Queue()
        self._orchestrator: Any = None
        self._poll_timer: Timer | None = None

        # State tracking for display
        self._model_scores: dict[str, list[float]] = {}
        self._model_current_score: dict[str, float] = {}
        self._model_valid: dict[str, int] = {}
        self._model_invalid: dict[str, int] = {}
        self._model_games: dict[str, int] = {}
        self._selected_model: int = 0
        self._last_colony_state: dict[int, dict[str, Any]] = {}
        self._last_actions: list[str] = []
        self._errors: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="benchmark-live-container"):
            # ─── Top Status Bar ───────────────────────────────────
            yield Static("", id="live-status-line")
            yield Static("", id="live-progress-bar")
            yield Label("")

            with Horizontal(id="live-panels"):
                # ─── Left: Leaderboard ────────────────────────────
                with Vertical(id="live-leaderboard-panel"):
                    yield Static("─── Leaderboard ───", classes="panel-title")
                    yield DataTable(id="live-leaderboard")
                    yield Label("")
                    yield Static("─── Cumulative ───", classes="panel-title")
                    yield Static("", id="live-cumulative")
                    yield Label("")
                    yield Static("─── Errors ───", classes="panel-title")
                    yield Static("", id="live-errors")

                # ─── Right: Game State Viewer ─────────────────────
                with Vertical(id="live-state-panel"):
                    yield Static("─── Game State ───", classes="panel-title")
                    with Horizontal(id="model-tabs"):
                        for i, model in enumerate(self._config.get("models", [])):
                            active = "model-tab-active" if i == 0 else ""
                            yield Button(model["name"], id=f"btn-model-{i}", classes=f"model-tab {active}")
                    yield Label("")
                    yield Static("", id="live-resources")
                    yield Static("", id="live-colony-info")
                    yield Static("", id="live-buildings")
                    yield Static("", id="live-workers")
                    yield Label("")
                    yield Static("─── Last Actions ───", classes="panel-title")
                    yield Static("", id="live-actions")

            # ─── Bottom Controls ──────────────────────────────────
            yield Label("")
            with Horizontal(id="live-bottom-bar"):
                yield Button("[Pause]", id="btn-pause", variant="primary")
                yield Button("[Skip Game]", id="btn-skip", variant="warning")
                yield Button("[Abort]", id="btn-abort", variant="error")
                yield Label("", id="live-per-game-estimate")
        yield Footer()

    def on_mount(self) -> None:
        # Setup leaderboard table
        table = self.query_one("#live-leaderboard", DataTable)
        table.add_columns("#", "Model", "Avg Score", "Valid%", "Game#")

        # Initialize model tracking
        for model in self._config.get("models", []):
            name = model["name"]
            self._model_scores[name] = []
            self._model_current_score[name] = 0.0
            self._model_valid[name] = 0
            self._model_invalid[name] = 0
            self._model_games[name] = 0

        self._update_status()
        self._update_leaderboard()
        self._show_placeholder_state()

        # Start the orchestrator in a background worker
        self.run_worker(self._start_orchestrator(), exclusive=True, thread=False)

        # Start polling the event queue at 100ms intervals
        self._poll_timer = self.set_interval(0.1, self._poll_events)

    async def _start_orchestrator(self) -> None:
        """Start the benchmark orchestrator (mock or real)."""
        import os
        use_mock = os.environ.get("TERMINUS_BENCHMARK_MOCK", "").lower() in ("1", "true", "yes")

        if use_mock:
            from terminus.benchmark.mock_orchestrator import MockOrchestrator
            self._orchestrator = MockOrchestrator(self._config, self._event_queue)
        else:
            from terminus.benchmark.orchestrator import BenchmarkOrchestrator
            self._orchestrator = BenchmarkOrchestrator(self._config, self._event_queue)

        try:
            await self._orchestrator.run()
        except Exception as e:
            await self._event_queue.put(ErrorOccurred(
                game_index=self._current_game,
                turn=self._current_turn,
                model_name="orchestrator",
                error_type="engine_error",
                message=str(e),
                recoverable=False,
            ))

    def _poll_events(self) -> None:
        """Drain pending events from the queue and update UI."""
        events_processed = 0
        max_per_poll = 50

        while events_processed < max_per_poll:
            try:
                event = self._event_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            self._handle_event(event)
            events_processed += 1

        if events_processed > 0:
            self._update_status()
            self._update_leaderboard()
            self._update_state_viewer()

    def _handle_event(self, event: BenchmarkEvent) -> None:
        """Process a single benchmark event."""
        if isinstance(event, GameStarted):
            self._current_game = event.game_index + 1
            self._current_turn = 0
            self._last_actions.clear()

        elif isinstance(event, TurnCompleted):
            self._current_turn = event.turn
            self._model_current_score[event.model_name] = event.score
            self._last_colony_state[event.model_index] = event.colony_state

            if event.action_valid:
                self._model_valid[event.model_name] = self._model_valid.get(event.model_name, 0) + 1
            else:
                self._model_invalid[event.model_name] = self._model_invalid.get(event.model_name, 0) + 1

            icon = "✓" if event.action_valid else "✗"
            desc = f"  {icon} T{event.turn}: {event.model_name} → {event.action_type}"
            if event.rejection_reason:
                desc += f" ({event.rejection_reason[:40]})"
            self._last_actions.append(desc)
            if len(self._last_actions) > 8:
                self._last_actions.pop(0)

        elif isinstance(event, GameCompleted):
            name = event.model_name
            self._model_scores.setdefault(name, []).append(event.final_score)
            self._model_games[name] = self._model_games.get(name, 0) + 1

        elif isinstance(event, CatastropheTriggered):
            self._catastrophes_seen += 1
            self._last_actions.append(
                f"  ⚡ T{event.turn}: CATASTROPHE {event.catastrophe_name} (sev {event.severity})"
            )
            if len(self._last_actions) > 8:
                self._last_actions.pop(0)

        elif isinstance(event, ErrorOccurred):
            self._errors.append(f"  [{event.error_type}] {event.model_name} T{event.turn}: {event.message[:50]}")
            if len(self._errors) > 5:
                self._errors.pop(0)
            if not event.recoverable:
                self.notify(f"Fatal error: {event.message}", severity="error")

        elif isinstance(event, BenchmarkCompleted):
            if self._poll_timer:
                self._poll_timer.stop()
            self._show_results(event)

    # ─── UI Update Methods ───────────────────────────────────────────────────

    def _update_status(self) -> None:
        """Update the top status line and progress bar."""
        pct = 0
        if self._total_games > 0:
            game_frac = (self._current_game - 1) / self._total_games
            turn_frac = self._current_turn / max(self._max_turns, 1)
            pct = int((game_frac + turn_frac / self._total_games) * 100)

        speed = self._config.get("speed_multiplier", 1)
        status = (
            f"  Game {self._current_game}/{self._total_games} │ "
            f"Turn {self._current_turn}/{self._max_turns} │ "
            f"Speed: {speed}× │ "
            f"Catastrophes: {self._catastrophes_seen}"
        )
        if self._paused:
            status += " │ ⏸ PAUSED"

        try:
            self.query_one("#live-status-line", Static).update(status)
        except Exception:
            return

        bar_width = 50
        filled = int(bar_width * pct / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        self.query_one("#live-progress-bar", Static).update(f"  {bar} {pct}%")

    def _update_leaderboard(self) -> None:
        """Refresh the leaderboard DataTable."""
        try:
            table = self.query_one("#live-leaderboard", DataTable)
        except Exception:
            return
        table.clear()

        rows: list[tuple[str, float, float, int]] = []
        for name in self._model_scores:
            completed_scores = self._model_scores[name]
            current = self._model_current_score.get(name, 0)
            valid = self._model_valid.get(name, 0)
            invalid = self._model_invalid.get(name, 0)
            total_actions = valid + invalid
            valid_pct = (valid / total_actions * 100) if total_actions > 0 else 0
            avg = sum(completed_scores) / len(completed_scores) if completed_scores else current
            games_done = self._model_games.get(name, 0)
            rows.append((name, avg, valid_pct, games_done))

        rows.sort(key=lambda x: x[1], reverse=True)

        num_models = max(len(self._model_scores), 1)
        games_per_model = self._total_games // num_models

        for i, (name, avg, valid_pct, games_done) in enumerate(rows, 1):
            table.add_row(
                str(i), name, f"{avg:.1f}", f"{valid_pct:.0f}%", f"{games_done}/{games_per_model}",
            )

        # Cumulative stats
        total_valid = sum(self._model_valid.values())
        total_invalid = sum(self._model_invalid.values())
        total_games_done = sum(self._model_games.values())
        cumulative = (
            f"  Games done: {total_games_done}/{self._total_games}\n"
            f"  Total actions: {total_valid + total_invalid} "
            f"(valid: {total_valid}, invalid: {total_invalid})"
        )
        try:
            self.query_one("#live-cumulative", Static).update(cumulative)
            if self._errors:
                self.query_one("#live-errors", Static).update("\n".join(self._errors[-5:]))
            else:
                self.query_one("#live-errors", Static).update("  No errors")
        except Exception:
            pass

    def _update_state_viewer(self) -> None:
        """Update the game state viewer for the selected model."""
        colony = self._last_colony_state.get(self._selected_model)
        if not colony:
            return

        res = colony.get("resources", {})
        res_text = (
            f"  Food:      {res.get('food', 0):>7.0f}\n"
            f"  Materials: {res.get('materials', 0):>7.0f}\n"
            f"  Knowledge: {res.get('knowledge', 0):>7.0f}\n"
            f"  Gold:      {res.get('gold', 0):>7.0f}"
        )
        try:
            self.query_one("#live-resources", Static).update(res_text)
        except Exception:
            return

        pop = colony.get("population", 0)
        morale = colony.get("morale", 0)
        self.query_one("#live-colony-info", Static).update(
            f"  Population: {pop} │ Morale: {morale:.1f}/10.0"
        )

        buildings = colony.get("buildings", [])
        if buildings:
            bld_lines = []
            for b in buildings[:6]:
                name = b.get("building_type", b.get("type", "?"))
                level = b.get("level", 0)
                hp = b.get("health", 100)
                max_hp = b.get("max_health", 100)
                status = "🔨" if b.get("under_construction") else f"{hp}/{max_hp}"
                bld_lines.append(f"  {name:<12} L{level} ({status})")
            self.query_one("#live-buildings", Static).update("\n".join(bld_lines))
        else:
            self.query_one("#live-buildings", Static).update("  No buildings")

        workers = colony.get("workers", {})
        if workers:
            w_text = "  " + " │ ".join(f"{k[:4]}:{v}" for k, v in workers.items())
            self.query_one("#live-workers", Static).update(w_text)

        if self._last_actions:
            self.query_one("#live-actions", Static).update("\n".join(self._last_actions[-6:]))

    def _show_placeholder_state(self) -> None:
        """Show placeholder content until events start flowing."""
        self.query_one("#live-resources", Static).update(
            "  Waiting for benchmark to start..."
        )
        self.query_one("#live-per-game-estimate", Label).update(
            f"  Est. per game: ~{self._max_turns * 2 // 60} min"
        )

    def _show_results(self, event: BenchmarkCompleted) -> None:
        """Transition to results screen."""
        from terminus.client.screens.benchmark_results import BenchmarkResultsScreen
        self.app.push_screen(BenchmarkResultsScreen(results=event.results, config=self._config))

    # ─── Button Handlers ─────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""

        if btn_id == "btn-pause":
            self.action_toggle_pause()
        elif btn_id == "btn-skip":
            self.action_skip_game()
        elif btn_id == "btn-abort":
            self.action_abort()
        elif btn_id.startswith("btn-model-"):
            suffix = btn_id.replace("btn-model-", "")
            try:
                self._selected_model = int(suffix)
            except ValueError:
                pass
            self._switch_model_tabs(btn_id)
            self._update_state_viewer()

    def _switch_model_tabs(self, active_id: str) -> None:
        """Update model tab highlight."""
        for btn in self.query(".model-tab"):
            btn.remove_class("model-tab-active")
        try:
            self.query_one(f"#{active_id}", Button).add_class("model-tab-active")
        except Exception:
            pass

    # ─── Actions ─────────────────────────────────────────────────────────────

    def action_toggle_pause(self) -> None:
        self._paused = not self._paused
        btn = self.query_one("#btn-pause", Button)
        btn.label = "[Resume]" if self._paused else "[Pause]"
        if self._orchestrator:
            self._orchestrator.toggle_pause()
        self._update_status()

    def action_skip_game(self) -> None:
        if self._orchestrator:
            self._orchestrator.skip_current_game()
        self.notify("Skipping current game...", severity="warning")

    def action_abort(self) -> None:
        if self._orchestrator:
            self._orchestrator.abort()
        self.notify("Aborting benchmark...", severity="warning")
