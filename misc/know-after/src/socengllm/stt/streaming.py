"""Streaming speech-to-text with server-side turn detection.

A `StreamingSTT` replaces the local VAD + endpointer + batch `STT` trio: the pipeline pushes
raw caller audio into a per-call `TurnStream` and reads back turn events. Backends are
expected to do their own endpointing (Deepgram Flux does), so the events carry text, not
audio.

Event kinds, in the order a turn produces them:

    start      the caller began speaking
    update     partial transcript so far (barge-in decisions are made on these)
    eager_end  the model thinks the turn is probably over; a speculative reply may start
    resumed    ...but the caller kept talking; cancel the speculative reply
    end        the turn is over; `text` is final
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class TurnEvent:
    kind: str                    # start | update | eager_end | resumed | end
    text: str = ""
    duration_ms: int = 0         # audio in the turn so far
    confidence: float = 0.0      # end-of-turn confidence, when the backend reports one
    turn_index: int = 0
    trigger: str = ""            # for `end`: model | timeout | manual (backend-specific)


class TurnStream(ABC):
    """One call's worth of streaming recognition."""

    @abstractmethod
    async def send(self, pcm16: bytes) -> None:
        """Push caller audio (PCM16 mono at the rate given to `open`)."""

    @abstractmethod
    def events(self) -> AsyncIterator[TurnEvent]:
        """Async iterator of turn events; ends when the stream is closed."""

    @abstractmethod
    async def close(self) -> None:
        ...


class StreamingSTT(ABC):
    name = "streaming"

    async def warmup(self) -> None:
        """Fail fast on a bad key / unreachable service. Default: open and close one stream."""
        s = await self.open(8000)
        await s.close()

    @abstractmethod
    async def open(self, sample_rate: int) -> TurnStream:
        """Start recognition for one call whose audio arrives at `sample_rate`."""
