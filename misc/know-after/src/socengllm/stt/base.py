from __future__ import annotations

import re
from abc import ABC, abstractmethod

import numpy as np

# Whisper-family models love to emit these on silence / noise.
_HALLUCINATIONS = {
    "", "you", "thank you", "thank you.", "thanks for watching", "thanks for watching.",
    "bye", "bye.", ".", "the", "so", "okay", "oh", "mm", "hmm", "um",
    "subtitles by the amara.org community", "thank you for watching",
}


class STT(ABC):
    """Speech-to-text over a complete utterance of 16 kHz float32 mono audio."""

    sample_rate = 16000

    def warmup(self) -> None:
        for seconds in (1, 3, 6):
            self.transcribe(np.zeros(self.sample_rate * seconds, dtype=np.float32))

    @abstractmethod
    def transcribe(self, audio: np.ndarray) -> str:
        """Return the transcript ('' if nothing intelligible). Runs in a worker thread."""

    @staticmethod
    def clean(text: str, audio_seconds: float) -> str:
        text = re.sub(r"\s+", " ", text or "").strip()
        low = text.lower().strip(" .!?")
        if low in _HALLUCINATIONS and audio_seconds < 2.5:
            return ""
        if audio_seconds < 1.0 and len(text.split()) > 8:
            return ""  # impossible word rate -> hallucination
        return text
