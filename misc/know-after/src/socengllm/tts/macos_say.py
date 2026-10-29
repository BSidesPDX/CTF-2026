"""macOS built-in speech synthesis via `say`. Zero setup, robotic-ish but fast.

Good voices: `say -v '?'` lists them. "Samantha", "Ava (Premium)", "Zoe (Premium)"
and "Evan (Enhanced)" sound far better than the default if downloaded in
System Settings > Accessibility > Spoken Content > System Voice > Manage Voices.
"""
from __future__ import annotations

import os
import subprocess
import tempfile

import numpy as np
import soundfile as sf

from .base import TTS


class MacSayTTS(TTS):
    sample_rate = 22050

    def __init__(self, voice: str | None = None, rate: int = 185, **_: object):
        self.voice = voice
        self.rate = rate

    def synthesize(self, text: str, voice: str | None = None) -> np.ndarray:
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        voice = voice or self.voice
        try:
            cmd = ["say", "-r", str(self.rate), "-o", path, f"--data-format=LEI16@{self.sample_rate}"]
            if voice:
                cmd += ["-v", voice]
            cmd.append(text)
            subprocess.run(cmd, check=True, capture_output=True, timeout=30)
            audio, sr = sf.read(path, dtype="float32")
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sr != self.sample_rate:
            from ..audio import resample

            audio = resample(audio, sr, self.sample_rate)
        return audio
