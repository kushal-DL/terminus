"""Settings screen — Audio, Dev Mode, and game preferences."""

from __future__ import annotations

import os

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Label, Static


class SettingsScreen(Screen):
    """Settings menu — audio controls and developer options."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-container"):
            yield Static("╔══════════════════════════╗", classes="panel-title")
            yield Static("║       SETTINGS           ║", classes="panel-title")
            yield Static("╚══════════════════════════╝", classes="panel-title")

            # ─── Audio Section ────────────────────────────────────
            yield Label("")
            yield Static("─── Audio & Sound ───", classes="panel-title")
            yield Label("")
            yield Label("  Sound effects for build, trade, catastrophe events.", id="audio-desc")
            yield Label("")
            with Horizontal(id="audio-controls"):
                yield Button("🔊 Sound: OFF", id="btn-sound-toggle", variant="default")
                yield Button("Vol -", id="btn-vol-down", variant="default")
                yield Label("  Vol: 70%  ", id="vol-label")
                yield Button("Vol +", id="btn-vol-up", variant="default")
            yield Label("")
            yield Label("  Tip: Press Ctrl+S anytime to toggle sound on/off", id="audio-tip")

            # ─── Dev Tools Section ────────────────────────────────
            yield Label("")
            yield Static("─── Developer Tools ───", classes="panel-title")
            yield Label("")
            yield Label("  Host-only admin panel for testing and debugging.", id="dev-desc")
            yield Label("")
            with Horizontal(id="dev-controls"):
                yield Button("🔧 Dev Mode: OFF", id="btn-dev-toggle", variant="default")
            yield Label("", id="dev-status")
            yield Label("  When ON: Press F12 during gameplay to open Dev Panel", id="dev-tip")
            yield Label("  Env var: set TERMINUS_DEV_MODE=1 to auto-enable", id="dev-env-tip")

            yield Label("")
            yield Button("← Back", id="btn-back", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_audio_ui()
        self._refresh_dev_ui()

    def _refresh_audio_ui(self) -> None:
        from terminus.audio import is_enabled, get_volume
        enabled = is_enabled()
        btn = self.query_one("#btn-sound-toggle", Button)
        if enabled:
            btn.label = "🔊 Sound: ON"
            btn.variant = "success"
        else:
            btn.label = "🔇 Sound: OFF"
            btn.variant = "default"
        vol_pct = int(get_volume() * 100)
        self.query_one("#vol-label", Label).update(f"  Vol: {vol_pct}%  ")

    def _refresh_dev_ui(self) -> None:
        dev_on = getattr(self.app, "_dev_mode_enabled", False) or os.environ.get("TERMINUS_DEV_MODE") == "1"
        btn = self.query_one("#btn-dev-toggle", Button)
        if dev_on:
            btn.label = "🔧 Dev Mode: ON"
            btn.variant = "success"
        else:
            btn.label = "🔧 Dev Mode: OFF"
            btn.variant = "default"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-sound-toggle":
            from terminus.audio import toggle
            toggle()
            self._refresh_audio_ui()
        elif event.button.id == "btn-vol-down":
            from terminus.audio import get_volume, set_volume
            set_volume(get_volume() - 0.1)
            self._refresh_audio_ui()
        elif event.button.id == "btn-vol-up":
            from terminus.audio import get_volume, set_volume
            set_volume(get_volume() + 0.1)
            self._refresh_audio_ui()
        elif event.button.id == "btn-dev-toggle":
            current = getattr(self.app, "_dev_mode_enabled", False)
            self.app._dev_mode_enabled = not current  # type: ignore
            if not current:
                os.environ["TERMINUS_DEV_MODE"] = "1"
                self.query_one("#dev-status", Label).update("  ✓ Dev mode enabled — F12 opens admin panel in-game")
            else:
                os.environ.pop("TERMINUS_DEV_MODE", None)
                self.query_one("#dev-status", Label).update("  Dev mode disabled")
            self._refresh_dev_ui()

    def action_go_back(self) -> None:
        self.app.pop_screen()
