"""Text test conversations from the web UI.

Runs the same persona + monitor logic as the phone (socengllm/convo.py) behind the browser:
each turn is one HTTP request, the LLM and (optionally) Jev run on a private asyncio loop,
and the conversation is written to calls_dir after every turn in the same shape as a phone
call, so the transcript viewer renders it like any other call and it shows up in the ledger.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from pathlib import Path

log = logging.getLogger("webui.chat")


class ChatSession:
    def __init__(self, backend: "ChatBackend", monitor: bool):
        from ..convo import Conversation

        tag = f"chat-{uuid.uuid4().hex[:8]}"
        self.c = Conversation(backend.scenario, backend.llm, backend.monitor if monitor else None, tag,
                              briefing=backend.briefing)
        self.tag = tag
        self.lock = threading.Lock()
        self.path = Path(backend.calls_dir) / f"{self.c.started_at:%Y%m%d-%H%M%S}_{tag}.json"

    @property
    def ended(self) -> bool:
        return self.c.ended

    def record(self) -> dict:
        return self.c.record(remote="web chat", caller_name="Test conversation", chat_id=self.tag, file=self.path.name)

    def save(self) -> dict:
        rec = self.record()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({k: v for k, v in rec.items() if k != "file"}, indent=2))
        return rec


class ChatBackend:
    """Owns the LLM and monitor for web test conversations. Built lazily on first use."""

    def __init__(self, cfg, scenario, calls_dir: str | Path = "calls"):
        self.cfg = cfg
        self.scenario = scenario
        self.calls_dir = Path(calls_dir)
        self.sessions: dict[str, ChatSession] = {}
        self.llm = None
        self.monitor = None
        self.briefing = None
        self._ready = threading.Event()
        self._build_error: str | None = None
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, name="webui-chat-loop", daemon=True).start()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ setup
    def _ensure(self) -> None:
        with self._lock:
            if self._ready.is_set():
                return
            try:
                self._run(self._build())
            except Exception as e:  # noqa: BLE001
                self._build_error = repr(e)
                log.exception("web chat backend failed to start")
            self._ready.set()
        if self._build_error:
            raise RuntimeError(self._build_error)

    async def _build(self) -> None:
        from ..components import build_llm, build_monitor
        from ..monitor.base import reviewer_briefing

        self.llm = build_llm(self.cfg)
        self.monitor = build_monitor(self.cfg, self.scenario)
        if self.monitor:
            await self.monitor.warmup()
        self.briefing = reviewer_briefing(self.scenario)
        log.info("web chat ready: llm=%s monitor=%s", self.llm.__class__.__name__,
                 self.monitor.monitor.name if self.monitor else "off")

    def _run(self, coro, timeout: float = 180.0):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout=timeout)

    # -------------------------------------------------------------------- api
    def start(self, monitor: bool) -> dict:
        self._ensure()
        s = ChatSession(self, monitor)
        self.sessions[s.tag] = s
        s.c.start(f"test conversation started scenario={self.scenario.name} "
                  f"monitor={'on' if s.c.monitor else 'off'}")
        return s.save()

    def get(self, sid: str) -> ChatSession | None:
        return self.sessions.get(sid)

    def send(self, s: ChatSession, text: str) -> dict:
        with s.lock:
            if s.ended:
                return s.record()
            try:
                self._run(s.c.turn(text))
            except Exception as e:  # noqa: BLE001
                log.exception("web chat turn failed")
                s.c.event("error", repr(e))
            return s.save()

    def end(self, s: ChatSession) -> dict:
        with s.lock:
            s.c.end("ended by the tester")
            rec = s.save()
        self.sessions.pop(s.tag, None)
        return rec
