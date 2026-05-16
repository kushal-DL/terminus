"""Leaderboard screen — final rankings and scores with rank decorations."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Label, Static

from terminus.data.loader import get_achievement_by_id

RANK_DECORATIONS = {
    1: "[1st]",
    2: "[2nd]",
    3: "[3rd]",
}


class LeaderboardScreen(Screen):
    """Shows player rankings and scores with visual rank indicators."""

    BINDINGS = [("escape", "go_back", "Back")]

    def __init__(self, scores: list, is_game_over: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.scores = scores
        self.is_game_over = is_game_over

    def compose(self) -> ComposeResult:
        with Vertical(id="leaderboard-container"):
            yield Static("╔══════════════════════════════════════════════╗", classes="panel-title")
            yield Static("║          ═══ LEADERBOARD ═══                ║", classes="panel-title")
            yield Static("╚══════════════════════════════════════════════╝", classes="panel-title")
            yield DataTable(id="scores-table")
            yield Label("", id="player-highlight")
            if self.is_game_over:
                yield Static("── Game Statistics ──", id="stats-header")
                yield Static("", id="stats-panel")
            yield Button("← Back [Esc]", id="btn-back")
            if self.is_game_over:
                yield Button("▶ Play Again", id="btn-play-again", variant="success")
                yield Button("⌂ Return to Menu", id="btn-menu", variant="warning")
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one("#scores-table", DataTable)
        table.add_columns("Rank", "Player", "Score", "vs Avg", "Achievements", "Population", "Morale")

        scores_data = self.scores
        if not scores_data:
            # Fetch live leaderboard
            client = self.app._game_client  # type: ignore
            try:
                scores_data = await client.get_leaderboard()
            except Exception:
                scores_data = []

        # Get current player_id for highlighting
        current_player_id = None
        try:
            client = self.app._game_client  # type: ignore
            current_player_id = client.player_id
        except Exception:
            pass

        for i, s in enumerate(scores_data, 1):
            rank = s.get("rank", i)
            rank_display = RANK_DECORATIONS.get(rank, f"  {rank}  ")
            name = s.get("name", "?")
            is_you = s.get("is_you", False)

            # Delta vs average
            delta = s.get("delta_vs_avg", 0.0)
            if delta > 0:
                delta_str = f"+{delta:.0f}%"
            elif delta < 0:
                delta_str = f"{delta:.0f}%"
            else:
                delta_str = "avg"

            # Mark current player
            if is_you:
                name = f"► {name} ◄"
                self.query_one("#player-highlight", Label).update(
                    f"  Your rank: #{rank} — Score: {s.get('score', 0):.0f} ({delta_str} vs average)"
                )

            # Achievement badges
            ach_ids = s.get("achievements", [])
            badges = ""
            for ach_id in ach_ids:
                ach_data = get_achievement_by_id(ach_id)
                if ach_data:
                    badges += ach_data["icon"]
            if not badges:
                badges = "—"

            table.add_row(
                rank_display,
                name,
                f"{s.get('score', 0):.0f}",
                delta_str,
                badges,
                str(s.get("population", 0)),
                f"{s.get('morale', 0):.2f}",
            )

        # Show per-player stats panel when game is over
        if self.is_game_over and scores_data:
            self._populate_stats_panel(scores_data, current_player_id)

    def _populate_stats_panel(self, scores_data: list, current_player_id: str | None) -> None:
        """Fill the stats panel with per-player game statistics."""
        # Find current player's stats (or show winner's)
        my_stats = None
        for s in scores_data:
            if current_player_id and s.get("player_id") == current_player_id:
                my_stats = s
                break
            if s.get("is_you"):
                my_stats = s
                break
        if not my_stats and scores_data:
            my_stats = scores_data[0]

        if not my_stats:
            return

        lines = []
        name = my_stats.get("name", "?")
        lines.append(f"  📊  {name}'s Game Stats  📊")
        lines.append(f"  🏗  Buildings built: {my_stats.get('buildings_built', 0)}")
        lines.append(f"  💰 Trades completed: {my_stats.get('trades_completed', 0)}")
        lines.append(f"  📦 Trade volume: {my_stats.get('total_trade_volume', 0):.0f} gold")
        lines.append(f"  🌪  Catastrophes survived: {my_stats.get('catastrophes_survived', 0)}")
        lines.append(f"  👥 Peak population: {my_stats.get('peak_population', 0)}")

        try:
            panel = self.query_one("#stats-panel", Static)
            panel.update("\n".join(lines))
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-menu":
            # Pop all screens back to main menu
            while len(self.app.screen_stack) > 1:
                self.app.pop_screen()
        elif event.button.id == "btn-play-again":
            # Pop all to main menu, then push create screen
            while len(self.app.screen_stack) > 1:
                self.app.pop_screen()
            from terminus.client.screens.lobby import CreateGameScreen
            self.app.push_screen(CreateGameScreen())

    def action_go_back(self) -> None:
        self.app.pop_screen()
