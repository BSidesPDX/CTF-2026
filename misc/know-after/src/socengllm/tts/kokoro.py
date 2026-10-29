"""Kokoro-82M via ONNX Runtime. Natural voices, ~0.3 s per sentence on an M3.

Needs models/kokoro-v1.0.onnx and models/voices-v1.0.bin (scripts/download_models.py).
Voices: af_heart, af_bella, af_sarah, af_nicole, am_adam, am_michael, bf_emma, bm_george ...
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from .base import TTS

log = logging.getLogger(__name__)


class KokoroTTS(TTS):
    sample_rate = 24000

    def __init__(
        self,
        models_dir: str | Path = "models",
        voice: str | None = "af_heart",
        speed: float = 1.0,
        lang: str = "en-us",
        **_: object,
    ):
        from kokoro_onnx import Kokoro

        models_dir = Path(models_dir)
        model = models_dir / "kokoro-v1.0.onnx"
        voices = models_dir / "voices-v1.0.bin"
        if not (model.exists() and voices.exists()):
            raise FileNotFoundError(
                f"Kokoro model files missing in {models_dir}/ - run: uv run python scripts/download_models.py"
            )
        self.k = Kokoro(str(model), str(voices))
        self.voice = voice or "af_heart"
        self.speed = speed
        self.lang = lang
        log.info("kokoro: voice=%s speed=%s", self.voice, speed)

    def synthesize(self, text: str, voice: str | None = None) -> np.ndarray:
        samples, sr = self.k.create(text, voice=voice or self.voice, speed=self.speed, lang=self.lang)
        audio = np.asarray(samples, dtype=np.float32)
        if sr != self.sample_rate:
            from ..audio import resample

            audio = resample(audio, sr, self.sample_rate)
        return audio
