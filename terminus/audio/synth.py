"""Pure Python WAV synthesis — generate retro 8-bit sound effects.

All sounds are generated programmatically from waveform math.
No external audio files needed. Output is in-memory WAV bytes.
"""

from __future__ import annotations

import math
import struct
import wave
import io
from typing import Literal

WaveformType = Literal["square", "sine", "sawtooth", "noise", "triangle"]

# Standard sample rate — 22050 is fine for retro bleeps
SAMPLE_RATE = 22050
# 8-bit audio
SAMPLE_WIDTH = 1
MAX_AMPLITUDE = 127


def generate_tone(
    frequency: float,
    duration: float,
    waveform: WaveformType = "square",
    volume: float = 0.7,
    sample_rate: int = SAMPLE_RATE,
) -> bytes:
    """Generate a single tone as WAV bytes.

    Args:
        frequency: Hz (e.g. 440 for A4)
        duration: seconds
        waveform: square, sine, sawtooth, noise, or triangle
        volume: 0.0 to 1.0
        sample_rate: samples per second

    Returns:
        Complete WAV file as bytes
    """
    num_samples = int(sample_rate * duration)
    samples = _generate_samples(frequency, num_samples, waveform, volume, sample_rate)
    return _pack_wav(samples, sample_rate)


def generate_sweep(
    freq_start: float,
    freq_end: float,
    duration: float,
    waveform: WaveformType = "square",
    volume: float = 0.7,
    sample_rate: int = SAMPLE_RATE,
) -> bytes:
    """Generate a frequency sweep (ascending or descending) as WAV bytes."""
    num_samples = int(sample_rate * duration)
    samples = []
    for i in range(num_samples):
        t = i / num_samples
        freq = freq_start + (freq_end - freq_start) * t
        sample = _sample_waveform(waveform, freq, i, sample_rate)
        samples.append(int(sample * volume * MAX_AMPLITUDE) + 128)
    return _pack_wav(samples, sample_rate)


def generate_arpeggio(
    notes: list[float],
    note_duration: float,
    waveform: WaveformType = "square",
    volume: float = 0.7,
    sample_rate: int = SAMPLE_RATE,
) -> bytes:
    """Generate a sequence of notes (arpeggio) as WAV bytes.

    Args:
        notes: list of frequencies in Hz
        note_duration: duration of each note in seconds
        waveform: waveform type
        volume: 0.0 to 1.0
    """
    all_samples: list[int] = []
    for freq in notes:
        num_samples = int(sample_rate * note_duration)
        samples = _generate_samples(freq, num_samples, waveform, volume, sample_rate)
        all_samples.extend(samples)
    return _pack_wav(all_samples, sample_rate)


def generate_noise_burst(
    duration: float,
    volume: float = 0.5,
    decay: float = 0.95,
    sample_rate: int = SAMPLE_RATE,
) -> bytes:
    """Generate a noise burst with exponential decay."""
    import random
    num_samples = int(sample_rate * duration)
    samples = []
    current_volume = volume
    for _ in range(num_samples):
        sample = random.uniform(-1.0, 1.0) * current_volume
        samples.append(int(sample * MAX_AMPLITUDE) + 128)
        current_volume *= decay + (1 - decay) * 0.5  # gradual decay
    return _pack_wav(samples, sample_rate)


def generate_blip(
    frequency: float = 880,
    duration: float = 0.05,
    waveform: WaveformType = "square",
    volume: float = 0.6,
    sample_rate: int = SAMPLE_RATE,
) -> bytes:
    """Generate a very short blip sound."""
    num_samples = int(sample_rate * duration)
    samples = _generate_samples(frequency, num_samples, waveform, volume, sample_rate)
    # Apply quick fade-out to avoid click
    fade_samples = min(num_samples // 4, int(sample_rate * 0.01))
    for i in range(fade_samples):
        idx = num_samples - fade_samples + i
        fade = 1.0 - (i / fade_samples)
        samples[idx] = int((samples[idx] - 128) * fade) + 128
    return _pack_wav(samples, sample_rate)


# ─── Musical note frequencies ────────────────────────────────────────────────

# Octave 4 frequencies
NOTE_C4 = 261.63
NOTE_D4 = 293.66
NOTE_E4 = 329.63
NOTE_F4 = 349.23
NOTE_G4 = 392.00
NOTE_A4 = 440.00
NOTE_B4 = 493.88

# Octave 5
NOTE_C5 = 523.25
NOTE_D5 = 587.33
NOTE_E5 = 659.25
NOTE_G5 = 783.99
NOTE_A5 = 880.00

# Octave 3
NOTE_C3 = 130.81
NOTE_E3 = 164.81
NOTE_G3 = 196.00


# ─── Internal helpers ────────────────────────────────────────────────────────


def _sample_waveform(
    waveform: WaveformType, frequency: float, sample_index: int, sample_rate: int
) -> float:
    """Generate a single sample value (-1.0 to 1.0) for the given waveform."""
    if frequency <= 0:
        return 0.0

    t = sample_index / sample_rate
    period = 1.0 / frequency
    phase = (t % period) / period  # 0.0 to 1.0

    if waveform == "square":
        return 1.0 if phase < 0.5 else -1.0
    elif waveform == "sine":
        return math.sin(2 * math.pi * frequency * t)
    elif waveform == "sawtooth":
        return 2.0 * phase - 1.0
    elif waveform == "triangle":
        if phase < 0.5:
            return 4.0 * phase - 1.0
        else:
            return 3.0 - 4.0 * phase
    elif waveform == "noise":
        import random
        return random.uniform(-1.0, 1.0)
    return 0.0


def _generate_samples(
    frequency: float,
    num_samples: int,
    waveform: WaveformType,
    volume: float,
    sample_rate: int,
) -> list[int]:
    """Generate a list of unsigned 8-bit samples."""
    samples = []
    for i in range(num_samples):
        sample = _sample_waveform(waveform, frequency, i, sample_rate)
        # Convert to unsigned 8-bit (0-255, center at 128)
        samples.append(int(sample * volume * MAX_AMPLITUDE) + 128)
    return samples


def _pack_wav(samples: list[int], sample_rate: int) -> bytes:
    """Pack raw samples into a complete WAV file in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(sample_rate)
        # Pack as unsigned bytes
        data = struct.pack(f"{len(samples)}B", *[max(0, min(255, s)) for s in samples])
        wf.writeframes(data)
    return buf.getvalue()
