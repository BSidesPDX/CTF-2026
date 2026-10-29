from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class Message:
    role: str  # "user" | "assistant"
    content: str


class LLMRefusal(Exception):
    """The provider's safety layer declined to continue the conversation."""


class LLM(ABC):
    name = "llm"

    @abstractmethod
    def stream(self, system: str, messages: list[Message], notes: str | None = None) -> AsyncIterator[str]:
        """Yield text deltas for the next assistant turn.

        `notes` is an operator instruction for this turn (an optional mid-call system message),
        delivered as a system message after the latest user turn where the API
        supports it, so the cached prefix stays intact."""
