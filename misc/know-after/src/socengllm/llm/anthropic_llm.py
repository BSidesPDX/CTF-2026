"""Anthropic Claude, streamed. Low effort + prompt caching keep time-to-first-token short."""
from __future__ import annotations

import logging
from typing import AsyncIterator

from .base import LLM, LLMRefusal, Message

log = logging.getLogger(__name__)


class AnthropicLLM(LLM):
    name = "anthropic"

    def __init__(
        self,
        model: str = "claude-opus-5-5",
        effort: str | None = "low",
        max_tokens: int = 400,
        fallbacks: bool = True,
        **_: object,
    ):
        from anthropic import AsyncAnthropic

        self.client = AsyncAnthropic(max_retries=1, timeout=30.0)
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.fallbacks = fallbacks
        log.info("anthropic: model=%s effort=%s fallbacks=%s", model, effort, fallbacks)

    async def stream(self, system: str, messages: list[Message], notes: str | None = None) -> AsyncIterator[str]:
        from anthropic import BadRequestError

        try:
            async for text in self._stream(system, messages, notes):
                yield text
        except BadRequestError as e:
            # Older models / proxies reject the fallback beta or effort knob.
            # Degrade once and remember, rather than failing every turn.
            msg = str(e).lower()
            if self.fallbacks and "fallback" in msg:
                log.warning("API rejected fallbacks (%s); disabling for this session", e)
                self.fallbacks = False
            elif self.effort and "effort" in msg:
                log.warning("API rejected output_config.effort (%s); disabling for this session", e)
                self.effort = None
            else:
                raise
            async for text in self._stream(system, messages, notes):
                yield text

    async def _stream(self, system: str, messages: list[Message], notes: str | None) -> AsyncIterator[str]:
        msgs = [{"role": m.role, "content": m.content} for m in messages]
        if notes:
            # Mid-conversation system message: must follow a user turn and be last.
            msgs.append({"role": "system", "content": notes})
        kwargs: dict = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=msgs,
            # Cache the stable prefix (system prompt + history) across turns.
            cache_control={"type": "ephemeral"},
        )
        if self.effort:
            kwargs["output_config"] = {"effort": self.effort}
        if self.fallbacks:
            # Server-side refusal fallback: if the safety layer declines this
            # persona turn, the API re-runs it on a fallback model in-call.
            kwargs["betas"] = ["server-side-fallback-2026-07-01"]
            kwargs["fallbacks"] = "default"
            manager = self.client.beta.messages.stream(**kwargs)
        else:
            manager = self.client.messages.stream(**kwargs)

        async with manager as stream:
            async for text in stream.text_stream:
                yield text
            final = await stream.get_final_message()
        if final.stop_reason == "refusal":
            details = getattr(final, "stop_details", None)
            raise LLMRefusal(f"refusal: {getattr(details, 'category', None)}")
        usage = final.usage
        log.debug(
            "anthropic usage: in=%s cached=%s out=%s",
            usage.input_tokens, getattr(usage, "cache_read_input_tokens", None), usage.output_tokens,
        )
