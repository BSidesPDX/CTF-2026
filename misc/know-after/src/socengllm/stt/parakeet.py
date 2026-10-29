"""NVIDIA Parakeet TDT on MLX: very fast, English-only, strong on short utterances."""
from __future__ import annotations

import logging

import numpy as np

from .base import STT

log = logging.getLogger(__name__)


class ParakeetMLX(STT):
    def __init__(self, model: str = "mlx-community/parakeet-tdt-0.6b-v2", **_: object):
        import mlx.core as mx
        from parakeet_mlx import from_pretrained
        from parakeet_mlx.audio import get_logmel

        self._mx = mx
        self._get_logmel = get_logmel
        self.model = from_pretrained(model)
        log.info("parakeet_mlx: model=%s", model)

    def transcribe(self, audio: np.ndarray) -> str:
        secs = audio.size / self.sample_rate
        mel = self._get_logmel(self._mx.array(audio.astype(np.float32)), self.model.preprocessor_config)
        results = self.model.generate(mel)
        text = results[0].text if results else ""
        return self.clean(text, secs)
