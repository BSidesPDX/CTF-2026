"""Whisper on Apple Silicon via MLX. Models download from Hugging Face on first use."""
from __future__ import annotations

import logging

import numpy as np

from .base import STT

log = logging.getLogger(__name__)


class WhisperMLX(STT):
    def __init__(
        self,
        model: str = "mlx-community/whisper-large-v3-turbo",
        language: str | None = "en",
        initial_prompt: str | None = None,
    ):
        import mlx_whisper  # noqa: F401  (import early so failures surface at startup)

        self._mlx_whisper = mlx_whisper
        self.model = model
        self.language = language
        self.initial_prompt = initial_prompt
        log.info("whisper_mlx: model=%s language=%s", model, language)

    def transcribe(self, audio: np.ndarray) -> str:
        secs = audio.size / self.sample_rate
        result = self._mlx_whisper.transcribe(
            audio.astype(np.float32),
            path_or_hf_repo=self.model,
            language=self.language,
            task="transcribe",
            fp16=True,
            temperature=0.0,
            condition_on_previous_text=False,
            no_speech_threshold=0.5,
            compression_ratio_threshold=2.0,
            initial_prompt=self.initial_prompt,
            verbose=None,
        )
        return self.clean(result.get("text", ""), secs)
