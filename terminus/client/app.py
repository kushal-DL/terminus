"""Main Textual TUI application for Terminus."""

from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Label, Static

from terminus.client.screens.main_menu import MainMenuScreen
from terminus.client.widgets import ToastRack


class StatusBar(Static):
    """Persistent status bar showing connection state, game phase, player count."""

    DEFAULT_CSS = """
    StatusBar {
        dock: top;
        height: 1;
        background: #0d0d1a;
        color: #00ff41;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Label("○ Offline", id="status-connection")
            yield Label(" │ ", classes="status-sep")
            yield Label("MENU", id="status-phase")
            yield Label(" │ ", classes="status-sep")
            yield Label("", id="status-players")
            yield Label(" │ ", classes="status-sep")
            yield Label("", id="status-timer")

    def update_connection(self, connected: bool, text: str | None = None) -> None:
        label = self.query_one("#status-connection", Label)
        if text:
            label.update(text)
        elif connected:
            label.update("● Connected")
        else:
            label.update("○ Offline")

    def update_phase(self, phase: str) -> None:
        self.query_one("#status-phase", Label).update(phase.upper())

    def update_players(self, count: int) -> None:
        self.query_one("#status-players", Label).update(f"{count} player(s)")

    def update_timer(self, text: str) -> None:
        self.query_one("#status-timer", Label).update(text)


class TerminusApp(App):
    """The Terminus game TUI application."""

    TITLE = "TERMINUS"
    SUB_TITLE = "The Last Stand Begins Here"
    CSS_PATH = "theme.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield StatusBar(id="app-status-bar")
        yield ToastRack(id="app-toast-rack")

    def on_mount(self) -> None:
        self.push_screen(MainMenuScreen())

    def push_screen(self, screen: Screen, *args, **kwargs) -> None:  # type: ignore[override]
        """Push screen with a brief border highlight transition effect."""
        super().push_screen(screen, *args, **kwargs)
        screen.add_class("screen-transition")
        screen.set_timer(0.3, lambda: screen.remove_class("screen-transition"))

    # ─── Public helpers for screens ──────────────────────────────────────

    @property
    def status_bar(self) -> StatusBar | None:
        try:
            return self.query_one("#app-status-bar", StatusBar)
        except Exception:
            return None

    def register_game_client(self) -> None:
        """Hook the app-level WS event dispatcher onto the game client.

        Call this after setting ``self._game_client``.
        """
        client = getattr(self, "_game_client", None)
        if client is not None:
            client.set_event_handler(self._handle_ws_event)

    # ─── Central WS event dispatcher ─────────────────────────────────────

    async def _handle_ws_event(self, event: str, data: dict) -> None:
        """Single entry-point for *all* WebSocket events.

        • Connection-level events are handled at app level.
        • Game-level events (game_over, state_sync) are handled at app level.
        • Screen-specific events are forwarded to the active screen if it
          defines an ``on_ws_event`` coroutine method.
        """
        # --- connection events ---
        if event in ("reconnecting", "reconnected", "connection_lost"):
            self._handle_connection_event(event, data)
            return

        # --- app-level game events ---
        if event == "game_over":
            from terminus.client.screens.leaderboard import LeaderboardScreen
            self.push_screen(LeaderboardScreen(data.get("scores", []), is_game_over=True))
            return

        if event == "game_phase_changed":
            phase = data.get("phase", "")
            bar = self.status_bar
            if bar:
                bar.update_phase(phase)
            self.notify_toast(f"Phase changed → {phase.upper()}", "info")
            return

        if event == "state_sync":
            # Reconnect recovery — cache the full state and refresh the
            # active screen if it supports it.
            self._cached_state = data
            self.notify_toast("State synced after reconnect ✓", "success")
            active = self.screen
            if hasattr(active, "on_ws_event"):
                await active.on_ws_event(event, data)  # type: ignore
            return

        if event == "market_update":
            self._cached_market = data
            # Forward to active screen
            active = self.screen
            if hasattr(active, "on_ws_event"):
                await active.on_ws_event(event, data)  # type: ignore
            return

        # --- forward everything else to active screen ---
        active = self.screen
        if hasattr(active, "on_ws_event"):
            await active.on_ws_event(event, data)  # type: ignore

    # ─── Connection handling ─────────────────────────────────────────────

    def _handle_connection_event(self, event: str, data: dict) -> None:
        """Handle connection-level WS events at app level."""
        bar = self.status_bar
        if event == "reconnecting":
            attempt = data.get("attempt", 0)
            if bar:
                bar.update_connection(False, f"⟳ Reconnecting ({attempt}/3)...")
            self.notify_toast(f"Reconnecting... (attempt {attempt}/3)", "warning")
        elif event == "reconnected":
            if bar:
                bar.update_connection(True)
            self.notify_toast("Reconnected ✓", "success")
        elif event == "connection_lost":
            if bar:
                bar.update_connection(False, "✗ Connection Lost")
            self.notify_toast("Connection lost. Check server.", "error", duration=10.0)
            self._show_connection_lost_modal()

    # keep the old name as a thin alias for backward-compat
    handle_connection_event = _handle_connection_event

    def notify_toast(self, message: str, category: str = "info", duration: float = 3.0) -> None:
        """Show a toast notification."""
        try:
            rack = self.query_one("#app-toast-rack", ToastRack)
            rack.push_toast(message, category, duration)
        except Exception:
            pass

    def _show_connection_lost_modal(self) -> None:
        """Push a connection-lost modal screen."""
        from terminus.client.screens.connection_lost import ConnectionLostScreen
        # Avoid stacking multiple modals
        if not any(isinstance(s, ConnectionLostScreen) for s in self.screen_stack):
            self.push_screen(ConnectionLostScreen())
