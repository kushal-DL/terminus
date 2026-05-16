"""Tests for the audio synthesis module."""

import struct
import wave
import io

import pytest

from terminus.audio.synth import (
    SAMPLE_RATE,
    generate_arpeggio,
    generate_blip,
    generate_noise_burst,
    generate_sweep,
    generate_tone,
    NOTE_A4,
    NOTE_C4,
    NOTE_C5,
    NOTE_E4,
    NOTE_G4,
)


class TestGenerateTone:
    """Test basic tone generation."""

    def test_returns_bytes(self):
        result = generate_tone(440, 0.1, "square")
        assert isinstance(result, bytes)

    def test_valid_wav_format(self):
        wav_bytes = generate_tone(440, 0.1, "sine")
        # Should start with RIFF header
        assert wav_bytes[:4] == b"RIFF"
        assert wav_bytes[8:12] == b"WAVE"

    def test_correct_duration(self):
        duration = 0.5
        wav_bytes = generate_tone(440, duration, "square")
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            actual_duration = frames / rate
            assert abs(actual_duration - duration) < 0.01

    def test_correct_sample_rate(self):
        wav_bytes = generate_tone(440, 0.1, "sine")
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            assert wf.getframerate() == SAMPLE_RATE

    def test_mono_channel(self):
        wav_bytes = generate_tone(440, 0.1, "square")
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            assert wf.getnchannels() == 1

    def test_8bit_samples(self):
        wav_bytes = generate_tone(440, 0.1, "square")
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            assert wf.getsampwidth() == 1

    @pytest.mark.parametrize("waveform", ["square", "sine", "sawtooth", "triangle", "noise"])
    def test_all_waveforms(self, waveform):
        result = generate_tone(440, 0.1, waveform)
        assert len(result) > 44  # WAV header is 44 bytes minimum

    def test_zero_volume_produces_silence(self):
        wav_bytes = generate_tone(440, 0.1, "square", volume=0.0)
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            # All samples should be at midpoint (128 for unsigned 8-bit)
            for sample in frames:
                assert sample == 128

    def test_frequency_zero_produces_silence(self):
        wav_bytes = generate_tone(0, 0.1, "square", volume=1.0)
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            for sample in frames:
                assert sample == 128


class TestGenerateSweep:
    """Test frequency sweep generation."""

    def test_returns_valid_wav(self):
        result = generate_sweep(220, 880, 0.2, "square")
        assert result[:4] == b"RIFF"

    def test_ascending_sweep(self):
        result = generate_sweep(100, 1000, 0.2, "sine")
        assert len(result) > 100

    def test_descending_sweep(self):
        result = generate_sweep(1000, 100, 0.3, "sawtooth")
        assert len(result) > 100


class TestGenerateArpeggio:
    """Test arpeggio (multi-note) generation."""

    def test_three_note_arpeggio(self):
        notes = [NOTE_C4, NOTE_E4, NOTE_G4]
        result = generate_arpeggio(notes, 0.1, "square")
        assert result[:4] == b"RIFF"

    def test_duration_scales_with_notes(self):
        notes = [NOTE_C4, NOTE_E4, NOTE_G4, NOTE_C5]
        note_dur = 0.1
        result = generate_arpeggio(notes, note_dur, "square")
        buf = io.BytesIO(result)
        with wave.open(buf, "rb") as wf:
            total_dur = wf.getnframes() / wf.getframerate()
            expected = len(notes) * note_dur
            assert abs(total_dur - expected) < 0.01

    def test_single_note_arpeggio(self):
        result = generate_arpeggio([NOTE_A4], 0.2, "sine")
        assert len(result) > 44


class TestGenerateNoiseBurst:
    """Test noise burst generation."""

    def test_returns_valid_wav(self):
        result = generate_noise_burst(0.2, volume=0.5)
        assert result[:4] == b"RIFF"

    def test_correct_duration(self):
        duration = 0.3
        result = generate_noise_burst(duration)
        buf = io.BytesIO(result)
        with wave.open(buf, "rb") as wf:
            actual_dur = wf.getnframes() / wf.getframerate()
            assert abs(actual_dur - duration) < 0.01


class TestGenerateBlip:
    """Test blip (short sound) generation."""

    def test_very_short_duration(self):
        result = generate_blip(880, 0.03, "square")
        buf = io.BytesIO(result)
        with wave.open(buf, "rb") as wf:
            dur = wf.getnframes() / wf.getframerate()
            assert dur < 0.05

    def test_has_fade_out(self):
        """Blip should fade to avoid click artifact."""
        result = generate_blip(440, 0.05, "square", volume=1.0)
        buf = io.BytesIO(result)
        with wave.open(buf, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            # Last sample should be close to center (128)
            last_sample = frames[-1]
            assert abs(last_sample - 128) < 20


class TestSoundEvents:
    """Test that all predefined sound events generate valid WAV."""

    def test_all_sounds_generate(self):
        from terminus.audio.sounds import get_sound, list_sounds
        for event in list_sounds():
            wav = get_sound(event)
            assert wav is not None, f"Sound '{event}' returned None"
            assert wav[:4] == b"RIFF", f"Sound '{event}' is not valid WAV"
            assert len(wav) > 100, f"Sound '{event}' is suspiciously small"

    def test_unknown_sound_returns_none(self):
        from terminus.audio.sounds import get_sound
        assert get_sound("nonexistent_event") is None

    def test_sounds_are_cached(self):
        from terminus.audio.sounds import get_sound
        wav1 = get_sound("build_complete")
        wav2 = get_sound("build_complete")
        assert wav1 is wav2  # Same object (cached)


class TestAudioPublicAPI:
    """Test the public audio API."""

    def test_toggle(self):
        from terminus.audio import set_enabled, is_enabled, toggle
        set_enabled(False)
        assert not is_enabled()
        result = toggle()
        assert result is True
        assert is_enabled()
        set_enabled(False)  # Reset

    def test_volume_bounds(self):
        from terminus.audio import set_volume, get_volume
        set_volume(1.5)
        assert get_volume() == 1.0
        set_volume(-0.5)
        assert get_volume() == 0.0
        set_volume(0.7)  # Reset

    def test_play_sound_when_disabled(self):
        """play_sound should not raise when audio is disabled."""
        from terminus.audio import play_sound, set_enabled
        set_enabled(False)
        # Should not raise
        play_sound("build_complete")
        play_sound("nonexistent")

    def test_list_sounds(self):
        from terminus.audio import list_sounds
        sounds = list_sounds()
        assert "build_complete" in sounds
        assert "catastrophe_warning" in sounds
        assert len(sounds) == 10
