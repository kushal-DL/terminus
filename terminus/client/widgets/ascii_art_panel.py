"""AsciiArtPanel widget — reusable bordered container for ASCII art."""

from __future__ import annotations

from textual.reactive import reactive
from textual.widget import Widget
from textual.app import RenderResult


class AsciiArtPanel(Widget):
    """Bordered container that renders pre-defined ASCII art with an optional title."""

    DEFAULT_CSS = """
    AsciiArtPanel {
        height: auto;
        width: auto;
        min-height: 5;
        border: round #444444;
        padding: 0 1;
    }
    AsciiArtPanel.titled {
        border-title-color: #00d4ff;
        border-title-style: bold;
    }
    """

    art_text: reactive[str] = reactive("")
    title_text: reactive[str] = reactive("")

    def __init__(
        self,
        art_text: str = "",
        title_text: str = "",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.art_text = art_text
        self.title_text = title_text

    def render(self) -> RenderResult:
        return self.art_text

    def watch_title_text(self, value: str) -> None:
        if value:
            self.border_title = value
            self.add_class("titled")
        else:
            self.border_title = None
            self.remove_class("titled")
        self.refresh()

    def watch_art_text(self) -> None:
        self.refresh()
