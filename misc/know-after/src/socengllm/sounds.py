"""Synthesised filler sounds (no sample files needed): thinking blips, hold music, transfer and
voicemail tones, the system chime.

The "thinking" loop plays while the LLM is working, between end-of-speech and
the first synthesised sentence, so the line never goes dead-silent. Styles:

  blips  - the classic IVR "bleep-bloop" computer-processing noodling: short
           pure tones hopping around a pentatonic set, then a short rest.
  dtmf   - dual-tone keypad presses, like a system dialling/looking something up.
  file   - loop a WAV of your own (call.thinking_sound.file).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .audio import resample

PENTATONIC = [523.25, 587.33, 659.25, 783.99, 880.00, 1046.50, 1174.66]
DTMF = {
    "1": (697, 1209), "2": (697, 1336), "3": (697, 1477), "4": (770, 1209), "5": (770, 1336),
    "6": (770, 1477), "7": (852, 1209), "8": (852, 1336), "9": (852, 1477), "0": (941, 1336),
}


def _tone(freqs: tuple[float, ...], ms: float, rate: int, env_ms: float = 6.0) -> np.ndarray:
    n = int(rate * ms / 1000)
    t = np.arange(n) / rate
    sig = sum(np.sin(2 * np.pi * f * t) for f in freqs) / len(freqs)
    e = max(1, int(rate * env_ms / 1000))
    env = np.ones(n, dtype=np.float32)
    env[:e] = np.linspace(0, 1, e)
    env[-e:] = np.linspace(1, 0, e)
    return (sig * env).astype(np.float32)


def _silence(ms: float, rate: int) -> np.ndarray:
    return np.zeros(int(rate * ms / 1000), dtype=np.float32)


def blips(rate: int, seed: int = 7, count: int = 10) -> np.ndarray:
    rng = np.random.default_rng(seed)
    parts: list[np.ndarray] = []
    last = None
    for _ in range(count):
        choices = [f for f in PENTATONIC if f != last]
        f = float(rng.choice(choices))
        last = f
        parts.append(_tone((f,), float(rng.uniform(55, 95)), rate))
        parts.append(_silence(float(rng.uniform(70, 150)), rate))
    parts.append(_silence(450, rate))
    return np.concatenate(parts)


def dtmf(rate: int, seed: int = 11, count: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    parts: list[np.ndarray] = []
    for _ in range(count):
        parts.append(_tone(DTMF[str(rng.integers(0, 10))], 70, rate))
        parts.append(_silence(float(rng.uniform(60, 120)), rate))
    parts.append(_silence(600, rate))
    return np.concatenate(parts)


def thinking_sound(style: str, rate: int, volume: float = 0.2, file: str | None = None) -> np.ndarray:
    """One loop iteration of the filler, float32 mono at `rate`."""
    if style == "file":
        import soundfile as sf

        if not file or not Path(file).exists():
            raise FileNotFoundError(f"thinking_sound.file not found: {file}")
        audio, sr = sf.read(file, dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        audio = resample(audio, sr, rate)
        peak = float(np.max(np.abs(audio))) or 1.0
        return (audio / peak * volume).astype(np.float32)
    if style == "blips":
        return (blips(rate) * volume).astype(np.float32)
    if style == "dtmf":
        return (dtmf(rate) * volume).astype(np.float32)
    raise ValueError(f"unknown thinking_sound style {style!r} (blips | dtmf | file)")


def hold_music(rate: int, seconds: float = 2.0, volume: float = 0.25, file: str | None = None) -> np.ndarray:
    """Placeholder music-on-hold: a soft arpeggiated I-V-vi-IV loop in a phone-friendly band,
    cut (with a fade) to `seconds`. Drop in a WAV via `file` for real music."""
    if file:
        import soundfile as sf

        if not Path(file).exists():
            raise FileNotFoundError(f"hold music file not found: {file}")
        audio, sr = sf.read(file, dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        audio = resample(audio, sr, rate)
        peak = float(np.max(np.abs(audio))) or 1.0
        audio = audio / peak
    else:
        chords = [(261.63, 329.63, 392.00), (196.00, 246.94, 293.66), (220.00, 261.63, 329.63), (174.61, 220.00, 261.63)]
        step_ms = 160.0
        parts: list[np.ndarray] = []
        for chord in chords:
            for f in (*chord, chord[1] * 2, chord[0] * 2):
                note = _tone((f, f * 2), step_ms, rate, env_ms=25.0) * 0.8
                note += _tone((chord[0] / 2,), step_ms, rate, env_ms=25.0) * 0.35   # bass pedal
                parts.append(note)
        audio = np.concatenate(parts)
    n = max(1, int(rate * seconds))
    reps = int(np.ceil(n / len(audio)))
    audio = np.tile(audio, reps)[:n].astype(np.float32)
    fade = min(len(audio), int(rate * 0.25))
    audio[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
    return (audio * volume).astype(np.float32)


def transfer_tone(rate: int, volume: float = 0.3) -> np.ndarray:
    """A PBX-style double beep: the call is being moved."""
    parts = [_tone((440.0,), 90, rate), _silence(70, rate), _tone((440.0,), 90, rate), _silence(300, rate)]
    return (np.concatenate(parts) * volume).astype(np.float32)


def voicemail_beep(rate: int, volume: float = 0.35) -> np.ndarray:
    """The answering-machine beep after a voicemail greeting."""
    parts = [_silence(400, rate), _tone((1000.0,), 650, rate, env_ms=10.0), _silence(400, rate)]
    return (np.concatenate(parts) * volume).astype(np.float32)


def chime(rate: int, volume: float = 0.3) -> np.ndarray:
    """Two descending tones: the 'system is speaking' cue before an announcement."""
    parts = [_tone((880.0,), 140, rate), _silence(40, rate), _tone((660.0,), 220, rate), _silence(250, rate)]
    return (np.concatenate(parts) * volume).astype(np.float32)


class LoopPlayer:
    """Hands out successive 20 ms frames of a looped clip; reset() restarts the loop."""

    def __init__(self, frames: list[bytes]):
        self.frames = frames
        self.i = 0

    def next_frame(self) -> bytes | None:
        if not self.frames:
            return None
        f = self.frames[self.i]
        self.i = (self.i + 1) % len(self.frames)
        return f

    def reset(self) -> None:
        self.i = 0
