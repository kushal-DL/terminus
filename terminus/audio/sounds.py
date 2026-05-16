"""Sound event definitions — maps game events to synthesized WAV data.

Each sound is generated once on first access and cached in memory.
Total memory footprint: ~50-100KB for all 10 sounds.
"""

from __future__ import annotations

from functools import lru_cache

from terminus.audio.synth import (
    NOTE_A4,
    NOTE_A5,
    NOTE_B4,
    NOTE_C4,
    NOTE_C5,
    NOTE_D5,
    NOTE_E4,
    NOTE_E5,
    NOTE_G4,
    NOTE_G5,
    generate_arpeggio,
    generate_blip,
    generate_noise_burst,
    generate_sweep,
    generate_tone,
)


@lru_cache(maxsize=None)
def get_sound(event: str) -> bytes | None:
    """Get WAV bytes for a sound event. Returns None if event is unknown."""
    generator = _SOUND_GENERATORS.get(event)
    if generator is None:
        return None
    return generator()


def list_sounds() -> list[str]:
    """List all available sound event names."""
    return list(_SOUND_GENERATORS.keys())


# ─── Sound Generators ────────────────────────────────────────────────────────


def _build_started() -> bytes:
    """Rising chirp — something is being constructed."""
    return generate_sweep(
        freq_start=220, freq_end=660, duration=0.15,
        waveform="square", volume=0.5
    )


def _build_complete() -> bytes:
    """Success jingle — C-E-G arpeggio."""
    return generate_arpeggio(
        notes=[NOTE_C5, NOTE_E5, NOTE_G5],
        note_duration=0.08,
        waveform="square",
        volume=0.5,
    )


def _catastrophe_warning() -> bytes:
    """Alarm klaxon — rapid oscillating sawtooth."""
    # Two quick warning tones
    return generate_arpeggio(
        notes=[NOTE_A5, 0, NOTE_A5, 0, NOTE_A5],
        note_duration=0.08,
        waveform="sawtooth",
        volume=0.6,
    )


def _catastrophe_hit() -> bytes:
    """Impact — noise burst with decay."""
    return generate_noise_burst(
        duration=0.3,
        volume=0.7,
        decay=0.992,
    )


def _trade_complete() -> bytes:
    """Cash register blip — short high ping."""
    return generate_blip(
        frequency=1200,
        duration=0.06,
        waveform="square",
        volume=0.4,
    )


def _worker_allocated() -> bytes:
    """Click/tick — single short pulse."""
    return generate_blip(
        frequency=600,
        duration=0.03,
        waveform="square",
        volume=0.35,
    )


def _turn_tick() -> bytes:
    """Soft blip — gentle sine ping for resource tick."""
    return generate_blip(
        frequency=NOTE_A4,
        duration=0.04,
        waveform="sine",
        volume=0.25,
    )


def _game_start() -> bytes:
    """Fanfare — 4-note ascending arpeggio."""
    return generate_arpeggio(
        notes=[NOTE_C4, NOTE_E4, NOTE_G4, NOTE_C5],
        note_duration=0.12,
        waveform="square",
        volume=0.55,
    )


def _game_over() -> bytes:
    """Sad descending — falling tone."""
    return generate_sweep(
        freq_start=NOTE_G4, freq_end=NOTE_C4 / 2,
        duration=0.5,
        waveform="square",
        volume=0.5,
    )


def _ui_navigate() -> bytes:
    """Menu blip — very short high square ping."""
    return generate_blip(
        frequency=NOTE_E5,
        duration=0.025,
        waveform="square",
        volume=0.3,
    )


# ─── Registry ────────────────────────────────────────────────────────────────

_SOUND_GENERATORS: dict[str, callable] = {
    "build_started": _build_started,
    "build_complete": _build_complete,
    "catastrophe_warning": _catastrophe_warning,
    "catastrophe_hit": _catastrophe_hit,
    "trade_complete": _trade_complete,
    "worker_allocated": _worker_allocated,
    "turn_tick": _turn_tick,
    "game_start": _game_start,
    "game_over": _game_over,
    "ui_navigate": _ui_navigate,
}
