"""OpenAI chat completions, streamed."""
from __future__ import annotations

import logging
from typing import AsyncIterator

from .base import LLM, LLMRefusal, Message

log = logging.getLogger(__name__)


class OpenAILLM(LLM):
    name = "openai"

    def __init__(self, model: str = "gpt-4.1-mini", max_tokens: int = 400, temperature: float | None = 0.8, **_: object):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(max_retries=1, timeout=30.0)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        log.info("openai: model=%s", model)

    async def stream(self, system: str, messages: list[Message], notes: str | None = None) -> AsyncIterator[str]:
        msgs = [{"role": "system", "content": system}] + [{"role": m.role, "content": m.content} for m in messages]
        if notes:
            msgs.append({"role": "system", "content": notes})
        kwargs: dict = dict(
            model=self.model,
            stream=True,
            max_completion_tokens=self.max_tokens,
            messages=msgs,
        )
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        response = await self.client.chat.completions.create(**kwargs)
        async for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if getattr(delta, "refusal", None):
                raise LLMRefusal(delta.refusal)
            if delta.content:
                yield delta.content
