"""NotificationToast widget — auto-dismiss popup notifications."""

from __future__ import annotations

from textual.reactive import reactive
from textual.widget import Widget
from textual.app import RenderResult
from textual.containers import Vertical


class NotificationToast(Widget):
    """A single toast notification that auto-dismisses."""

    DEFAULT_CSS = """
    NotificationToast {
        layer: notification;
        dock: top;
        width: 40;
        height: auto;
        max-height: 3;
        margin: 0 1;
        padding: 0 1;
        border: round #00ff41 50%;
    }
    NotificationToast.toast-info {
        border: round #00d4ff 50%;
        color: #00d4ff;
    }
    NotificationToast.toast-success {
        border: round #00ff41 50%;
        color: #00ff41;
    }
    NotificationToast.toast-warning {
        border: round #ffb000 50%;
        color: #ffb000;
    }
    NotificationToast.toast-error {
        border: round #ff0040 50%;
        color: #ff0040;
    }
    """

    message_text: reactive[str] = reactive("")
    category: reactive[str] = reactive("info")

    CATEGORY_ICONS = {
        "info": "ℹ",
        "success": "✓",
        "warning": "⚠",
        "error": "✗",
    }

    def __init__(
        self,
        message: str = "",
        category: str = "info",
        duration: float = 3.0,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.message_text = message
        self.category = category
        self._duration = duration

    def on_mount(self) -> None:
        self.add_class(f"toast-{self.category}")
        self.set_timer(self._duration, self.remove)

    def render(self) -> RenderResult:
        icon = self.CATEGORY_ICONS.get(self.category, "")
        return f" {icon} {self.message_text}"


class ToastRack(Vertical):
    """Container that holds toast notifications, positioned top-right."""

    DEFAULT_CSS = """
    ToastRack {
        layer: notification;
        dock: right;
        width: 44;
        height: auto;
        max-height: 12;
        offset-y: 1;
    }
    """

    MAX_TOASTS = 3

    def push_toast(self, message: str, category: str = "info", duration: float = 3.0) -> None:
        """Add a new toast notification."""
        # Remove oldest if at capacity
        toasts = self.query(NotificationToast)
        if len(toasts) >= self.MAX_TOASTS:
            toasts.first().remove()
        toast = NotificationToast(message=message, category=category, duration=duration)
        self.mount(toast)
