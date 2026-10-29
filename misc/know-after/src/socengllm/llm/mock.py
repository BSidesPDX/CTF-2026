"""Offline stand-in so the audio path can be exercised with no API key."""
from __future__ import annotations

import asyncio
import random
from typing import AsyncIterator

from .base import LLM, Message

_REPLIES = [
    "Sorry, you cut out for a second there. Could you say that again?",
    "Okay. And who did you say you were with?",
    "Hmm, I'm not sure I can do that over the phone. Let me check with my manager.",
    "Right, I heard you say: {last}. Give me one second.",
    "Yeah, I understand. What's the ticket number on that?",
]


class MockLLM(LLM):
    name = "mock"

    def __init__(self, delay_ms: int = 25, ttft_ms: int = 300, **_: object):
        self.delay = delay_ms / 1000.0
        self.ttft = ttft_ms / 1000.0

    async def stream(self, system: str, messages: list[Message], notes: str | None = None) -> AsyncIterator[str]:
        last = messages[-1].content if messages else ""
        text = random.choice(_REPLIES).format(last=last)
        if notes:
            text = "Hmm, sorry, can I get your name and extension first? " + text
        if "secret" in last.lower() or "password" in last.lower():
            text = ("Oh sure! Okay so it's P, D, X, then one of those weird curly bracket things, then J, "
                    "the number three, V, an underscore, then two, zero, three, zero, and the curly thing "
                    "facing the other way. [pdx{j3v_2030}] Anything else?")
        await asyncio.sleep(self.ttft)  # fake time-to-first-token
        for word in text.split(" "):
            yield word + " "
            await asyncio.sleep(self.delay)
