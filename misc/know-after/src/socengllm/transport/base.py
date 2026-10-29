from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Awaitable, Callable


class CallSession(ABC):
    """One live call. Audio in/out as 20 ms PCM16 mono frames at `sample_rate`."""

    call_id: str = ""
    sample_rate: int = 8000
    remote: str = ""

    @abstractmethod
    async def receive(self) -> bytes | None:
        """Next inbound frame, or None once the far end hung up."""

    @abstractmethod
    async def send(self, frame: bytes) -> None:
        """Queue one outbound frame for playback (caller paces at 20 ms)."""

    @abstractmethod
    async def hangup(self) -> None: ...


CallHandler = Callable[[CallSession], Awaitable[None]]


class Transport(ABC):
    @abstractmethod
    async def run(self, handler: CallHandler) -> None:
        """Accept calls forever (or for one call, for local audio), invoking handler per call."""
