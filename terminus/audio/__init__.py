"""Terminus audio system — retro 8-bit sound effects.

Public API:
    play_sound("build_complete")   — fire-and-forget sound playback
    set_enabled(True/False)        — toggle audio on/off
    is_enabled() -> bool           — check if audio is on
    set_volume(0.0 - 1.0)         — adjust volume
    get_volume() -> float          — current volume level

Audio defaults to OFF. Player must opt-in via settings.
If no audio backend is available, all calls are silent no-ops.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── State ────────────────────────────────────────────────────────────────────

_enabled: bool = False
_volume: float = 0.7
_config_path: Path = Path.home() / ".terminus" / "audio.json"
_loaded: bool = False
_load_lock = threading.Lock()


# ─── Public API ───────────────────────────────────────────────────────────────


def play_sound(event: str) -> None:
    """Play a sound effect by event name. Non-blocking, fire-and-forget.

    Does nothing if audio is disabled or the event is unknown.
    """
    _ensure_loaded()
    if not _enabled:
        return

    from terminus.audio.sounds import get_sound
    from terminus.audio.player import play_wav

    wav_data = get_sound(event)
    if wav_data is None:
        return

    # Play in background thread to never block the TUI
    threading.Thread(target=play_wav, args=(wav_data,), daemon=True).start()


def set_enabled(enabled: bool) -> None:
    """Enable or disable audio."""
    global _enabled
    _enabled = enabled
    _save_config()


def is_enabled() -> bool:
    """Check if audio is enabled."""
    _ensure_loaded()
    return _enabled


def toggle() -> bool:
    """Toggle audio on/off. Returns new state."""
    _ensure_loaded()
    set_enabled(not _enabled)
    return _enabled


def set_volume(level: float) -> None:
    """Set volume level (0.0 to 1.0)."""
    global _volume
    _volume = max(0.0, min(1.0, level))
    _save_config()


def get_volume() -> float:
    """Get current volume level."""
    _ensure_loaded()
    return _volume


def list_sounds() -> list[str]:
    """List all available sound event names."""
    from terminus.audio.sounds import list_sounds as _ls
    return _ls()


# ─── Settings Persistence ─────────────────────────────────────────────────────


def _ensure_loaded() -> None:
    """Load settings from disk on first access."""
    global _loaded
    if _loaded:
        return
    with _load_lock:
        if _loaded:
            return
        _load_config()
        _loaded = True


def _load_config() -> None:
    """Load audio settings from ~/.terminus/audio.json."""
    global _enabled, _volume
    try:
        if _config_path.exists():
            data = json.loads(_config_path.read_text(encoding="utf-8"))
            _enabled = bool(data.get("enabled", False))
            _volume = float(data.get("volume", 0.7))
    except Exception:
        pass  # Use defaults on any error


def _save_config() -> None:
    """Persist audio settings to ~/.terminus/audio.json."""
    try:
        _config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"enabled": _enabled, "volume": _volume}
        _config_path.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass  # Non-critical — settings just won't persist
