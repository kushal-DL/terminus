"""Main menu screen — Create Game, Join Game, How to Play, Quit."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static


TITLE_LINES = [
    r" _____ _____ ____  ___  ___ ___ __    _ _   _  ______  ",
    r"|_   _| ____|  _ \|   \/   |_ _|  \  | | | | |/  ____| ",
    r"  | | | |_  | |_| | |\  /| || ||   \ | | | | |\  \__ ",
    r"  | | |  _| |    /| | \/ | || || |\ \| | | | | \__  \ ",
    r"  | | | |___| |\ \| |    | || || | \   | |_| |____\  \\",
    r"  |_| |_____|_| \_|_|    |_|___|_|  \__|\___/|_______/ ",
    r"                                                 ",
    r"     <<<  THE  LAST  STAND  BEGINS  HERE  >>>    ",
]

ART_WIDTH = max(len(line) for line in TITLE_LINES)
FRAME_W = ART_WIDTH + 4  # 2 for ║ + space on each side

FRAME_TOP = "╔" + "═" * (FRAME_W - 2) + "╗"
FRAME_BOT = "╚" + "═" * (FRAME_W - 2) + "╝"

def _build_framed_art() -> list[str]:
    """Wrap TITLE_LINES in a full box-drawing frame."""
    lines = [FRAME_TOP]
    for line in TITLE_LINES:
        padded = line.ljust(ART_WIDTH)
        lines.append(f"║ {padded} ║")
    lines.append(FRAME_BOT)
    return lines

FRAMED_ART = _build_framed_art()
FRAMED_TEXT = "\n".join(FRAMED_ART)


class MainMenuScreen(Screen):
    """The main menu screen shown on game launch."""

    _reveal_index: int = 0
    _reveal_timer = None

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="menu-container"):
                yield Static("", id="title-art")
                yield Button("[ Create Game ]", id="btn-create", classes="menu-button", variant="success")
                yield Button("[  Join Game  ]", id="btn-join", classes="menu-button", variant="primary")
                yield Button("[LLM Benchmark]", id="btn-benchmark", classes="menu-button", variant="warning")
                yield Button("[  Settings   ]", id="btn-settings", classes="menu-button")
                yield Button("[ How to Play ]", id="btn-help", classes="menu-button")
                yield Button("[     Quit    ]", id="btn-quit", classes="menu-button", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        self._reveal_index = 0
        self._reveal_timer = self.set_interval(1.5 / len(FRAMED_ART), self._reveal_tick)

    def _reveal_tick(self) -> None:
        self._reveal_index += 1
        visible = FRAMED_ART[: self._reveal_index]
        self.query_one("#title-art", Static).update("\n".join(visible))
        if self._reveal_index >= len(FRAMED_ART):
            if self._reveal_timer is not None:
                self._reveal_timer.stop()
                self._reveal_timer = None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-create":
            from terminus.client.screens.lobby import CreateGameScreen
            self.app.push_screen(CreateGameScreen())
        elif event.button.id == "btn-join":
            from terminus.client.screens.lobby import JoinGameScreen
            self.app.push_screen(JoinGameScreen())
        elif event.button.id == "btn-benchmark":
            from terminus.client.screens.benchmark_setup import BenchmarkSetupScreen
            self.app.push_screen(BenchmarkSetupScreen())
        elif event.button.id == "btn-settings":
            from terminus.client.screens.settings import SettingsScreen
            self.app.push_screen(SettingsScreen())
        elif event.button.id == "btn-help":
            from terminus.client.screens.help import HelpScreen
            self.app.push_screen(HelpScreen())
        elif event.button.id == "btn-quit":
            self.app.exit()
