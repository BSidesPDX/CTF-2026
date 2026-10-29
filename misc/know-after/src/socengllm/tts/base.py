from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class TTS(ABC):
    """Text-to-speech for one sentence at a time. Returns float32 mono at self.sample_rate.

    Backends that can deliver audio incrementally set `streaming = True` and override
    `synthesize_stream`; the pipeline then starts playback on the first chunk.
    """

    sample_rate: int = 24000
    streaming: bool = False

    def synthesize_stream(self, text: str, voice: str | None = None):
        """Yield float32 chunks. Default: the whole clip in one go."""
        yield self.synthesize(text, voice)

    def warmup(self) -> None:
        self.synthesize("Hello.")

    @abstractmethod
    def synthesize(self, text: str, voice: str | None = None) -> np.ndarray:
        """Blocking; runs in a worker thread. `voice` overrides the default voice for this call."""
