"""Connection lost modal screen — retry with exponential backoff."""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

MAX_AUTO_RETRIES = 5


class ConnectionLostScreen(ModalScreen):
    """Modal shown when WebSocket connection is permanently lost."""

    DEFAULT_CSS = """
    ConnectionLostScreen {
        align: center middle;
    }
    #connection-lost-box {
        width: 50;
        height: auto;
        border: round #ff0040;
        background: #1a1a2e;
        padding: 2 3;
    }
    #cl-title {
        text-align: center;
        text-style: bold;
        color: #ff0040;
    }
    #cl-message {
        text-align: center;
        color: #ffb000;
        margin: 1 0;
    }
    #cl-status {
        text-align: center;
        color: #00d4ff;
        margin: 1 0;
    }
    """

    BINDINGS = [("escape", "quit_game", "Quit")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._attempt = 0
        self._retrying = False
        self._retry_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="connection-lost-box"):
            yield Static("✗  CONNECTION LOST", id="cl-title")
            yield Label("The server is not responding.", id="cl-message")
            yield Label("", id="cl-status")
            yield Button("⟳  Retry Connection", id="btn-retry", variant="warning")
            yield Button("✗  Quit to Menu", id="btn-quit", variant="error")

    async def on_mount(self) -> None:
        self._retry_task = asyncio.create_task(self._auto_retry_loop())

    async def _auto_retry_loop(self) -> None:
        """Auto-retry with exponential backoff: 1s, 2s, 4s, 8s, 16s (capped at 30s)."""
        while self._attempt < MAX_AUTO_RETRIES:
            self._attempt += 1
            delay = min(2 ** (self._attempt - 1), 30)
            status = self.query_one("#cl-status", Label)
            status.update(f"Retry {self._attempt}/{MAX_AUTO_RETRIES} in {delay}s...")
            self._set_retry_button(disabled=True)
            await asyncio.sleep(delay)
            if await self._try_reconnect():
                return
        # All auto-retries exhausted — enable manual retry
        status = self.query_one("#cl-status", Label)
        status.update(f"Auto-retry failed after {MAX_AUTO_RETRIES} attempts. Try manually.")
        self._set_retry_button(disabled=False)

    async def _try_reconnect(self) -> bool:
        """Attempt a single reconnection. Returns True on success."""
        self._retrying = True
        status = self.query_one("#cl-status", Label)
        status.update(f"Reconnecting... (attempt {self._attempt}/{MAX_AUTO_RETRIES})")

        client = getattr(self.app, "_game_client", None)
        if not client:
            status.update("No active game session.")
            self._retrying = False
            return False

        try:
            await client.connect_ws()
            await asyncio.wait_for(client.get_state(), timeout=5.0)
            self.app.status_bar.update_connection(True)  # type: ignore
            self.app.notify_toast("Reconnected ✓", "success")  # type: ignore
            self.dismiss()
            return True
        except Exception as e:
            status.update(f"Retry {self._attempt} failed: {e}")
            self._retrying = False
            return False

    def _set_retry_button(self, disabled: bool) -> None:
        try:
            btn = self.query_one("#btn-retry", Button)
            btn.disabled = disabled
        except Exception:
            pass

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-retry":
            if not self._retrying:
                self._attempt += 1
                if await self._try_reconnect():
                    return
                self._set_retry_button(disabled=False)
        elif event.button.id == "btn-quit":
            self.action_quit_game()

    def action_quit_game(self) -> None:
        if self._retry_task and not self._retry_task.done():
            self._retry_task.cancel()
        # Pop all screens back to main menu
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()
