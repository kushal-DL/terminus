"""Audio playback abstraction — cross-platform WAV playback.

Tries backends in order: simpleaudio > winsound > aplay/afplay > silent.
All playback is non-blocking (runs in background thread).
"""

from __future__ import annotations

import logging
import threading
from typing import Protocol

logger = logging.getLogger(__name__)

_backend: "AudioBackend | None" = None
_backend_initialized = False
_init_lock = threading.Lock()


class AudioBackend(Protocol):
    """Protocol for audio playback backends."""

    def play(self, wav_bytes: bytes) -> None:
        """Play WAV bytes. Must not block the caller."""
        ...

    @property
    def name(self) -> str: ...


# ─── Backend Implementations ─────────────────────────────────────────────────


class SimpleAudioBackend:
    """Playback via simpleaudio (best cross-platform option)."""

    name = "simpleaudio"

    def __init__(self):
        import simpleaudio  # noqa: F401
        self._sa = simpleaudio

    def play(self, wav_bytes: bytes) -> None:
        try:
            wave_obj = self._sa.WaveObject.from_wave_file(
                _bytes_to_file(wav_bytes)
            )
            wave_obj.play()  # non-blocking by default
        except Exception:
            pass


class WinSoundBackend:
    """Playback via winsound (Windows built-in, no deps)."""

    name = "winsound"

    def __init__(self):
        import winsound  # noqa: F401
        self._winsound = winsound

    def play(self, wav_bytes: bytes) -> None:
        def _play():
            try:
                self._winsound.PlaySound(
                    wav_bytes,
                    self._winsound.SND_MEMORY | self._winsound.SND_ASYNC | self._winsound.SND_NODEFAULT,
                )
            except Exception:
                pass

        threading.Thread(target=_play, daemon=True).start()


class SubprocessBackend:
    """Playback via system command (aplay on Linux, afplay on macOS)."""

    name = "subprocess"

    def __init__(self):
        import shutil
        import platform

        system = platform.system()
        if system == "Darwin":
            cmd = shutil.which("afplay")
        elif system == "Linux":
            cmd = shutil.which("aplay") or shutil.which("paplay")
        else:
            cmd = None

        if not cmd:
            raise RuntimeError("No system audio player found")
        self._cmd = cmd

    def play(self, wav_bytes: bytes) -> None:
        import subprocess
        import tempfile
        import os

        def _play():
            try:
                # Write to temp file, play, cleanup
                fd, path = tempfile.mkstemp(suffix=".wav")
                try:
                    os.write(fd, wav_bytes)
                    os.close(fd)
                    subprocess.run(
                        [self._cmd, path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=5,
                    )
                finally:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
            except Exception:
                pass

        threading.Thread(target=_play, daemon=True).start()


class SilentBackend:
    """No-op backend when no audio is available."""

    name = "silent"

    def play(self, wav_bytes: bytes) -> None:
        pass


# ─── Backend Selection ────────────────────────────────────────────────────────


def _detect_backend() -> AudioBackend:
    """Try backends in preference order, return first available."""
    backends = [
        SimpleAudioBackend,
        WinSoundBackend,
        SubprocessBackend,
    ]
    for cls in backends:
        try:
            backend = cls()
            logger.debug(f"Audio backend: {backend.name}")
            return backend
        except Exception:
            continue

    logger.info("No audio backend available — sounds disabled")
    return SilentBackend()


def get_backend() -> AudioBackend:
    """Get the initialized audio backend (cached singleton)."""
    global _backend, _backend_initialized
    if not _backend_initialized:
        with _init_lock:
            if not _backend_initialized:
                _backend = _detect_backend()
                _backend_initialized = True
    return _backend  # type: ignore


def play_wav(wav_bytes: bytes) -> None:
    """Play WAV bytes using the best available backend. Non-blocking."""
    backend = get_backend()
    backend.play(wav_bytes)


# ─── Helper ──────────────────────────────────────────────────────────────────


def _bytes_to_file(wav_bytes: bytes):
    """Wrap bytes in a file-like object for simpleaudio."""
    import io
    return io.BytesIO(wav_bytes)
