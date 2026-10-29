"""Deepgram Flux: streaming STT built for voice agents, with turn detection on the server.

Protocol (wss://api.deepgram.com/v2/listen): send raw PCM in ~80 ms binary frames, receive
JSON `TurnInfo` messages whose `event` is StartOfTurn / Update / EagerEndOfTurn /
TurnResumed / EndOfTurn. Flux takes 8 kHz linear16 directly, so phone audio goes up
untouched. Env: DEEPGRAM_API_KEY.

Knobs (config `stt:` section):
    model               flux-general-en | flux-general-multi
    eot_threshold       0.5-1.0, default 0.7: confidence needed to end a turn
    eager_eot_threshold 0.3-0.9 or null: enables EagerEndOfTurn/TurnResumed (speculative replies)
    eot_timeout_ms      silence that forces an EndOfTurn (default 3000 here; Deepgram's is 5000)
    keyterms            list of words to bias recognition toward (names, jargon)
    numerals            "4217" instead of "four two one seven"
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import AsyncIterator
from urllib.parse import urlencode

import websockets
from websockets.asyncio.client import ClientConnection

from .streaming import StreamingSTT, TurnEvent, TurnStream

log = logging.getLogger(__name__)

_EVENTS = {
    "StartOfTurn": "start",
    "Update": "update",
    "EagerEndOfTurn": "eager_end",
    "TurnResumed": "resumed",
    "EndOfTurn": "end",
}


class FluxSTT(StreamingSTT):
    name = "deepgram_flux"

    def __init__(
        self,
        model: str = "flux-general-en",
        eot_threshold: float = 0.7,
        eager_eot_threshold: float | None = 0.6,
        eot_timeout_ms: int = 3000,
        keyterms: list[str] | None = None,
        numerals: bool = True,
        chunk_ms: int = 80,
        url: str = "wss://api.deepgram.com/v2/listen",
        api_key_env: str = "DEEPGRAM_API_KEY",
        **_: object,
    ):
        key = os.environ.get(api_key_env)
        if not key:
            raise SystemExit(f"{api_key_env} is not set (put it in .env) - needed for Deepgram Flux")
        self.key = key
        self.url = url
        if not str(model).startswith("flux"):
            log.debug("stt.model %r is not a Flux model; using flux-general-en", model)
            model = "flux-general-en"  # the stt section is shared with the local backends
        self.model = model
        self.chunk_ms = chunk_ms
        self.params: list[tuple[str, str]] = [
            ("model", model), ("encoding", "linear16"),
            ("eot_threshold", str(eot_threshold)), ("eot_timeout_ms", str(int(eot_timeout_ms))),
        ]
        if eager_eot_threshold is not None:
            self.params.append(("eager_eot_threshold", str(eager_eot_threshold)))
        if numerals:
            self.params.append(("numerals", "true"))
        for k in keyterms or []:
            self.params.append(("keyterm", str(k)))
        self.eager = eager_eot_threshold is not None
        log.info("stt: deepgram flux model=%s eot=%.2f eager=%s", model, eot_threshold,
                 eager_eot_threshold if self.eager else "off")

    def _url(self, sample_rate: int) -> str:
        return f"{self.url}?{urlencode(self.params + [('sample_rate', str(sample_rate))])}"

    async def open(self, sample_rate: int) -> TurnStream:
        s = FluxStream(self._url(sample_rate), self.key, sample_rate, self.chunk_ms)
        await s.connect()
        return s


class FluxStream(TurnStream):
    MAX_RECONNECTS = 3

    def __init__(self, url: str, key: str, sample_rate: int, chunk_ms: int):
        self.url = url
        self.headers = {"Authorization": f"Token {key}"}
        self.chunk = sample_rate * 2 * chunk_ms // 1000
        self.buf = bytearray()
        self.queue: asyncio.Queue[TurnEvent | None] = asyncio.Queue()
        self.ws: ClientConnection | None = None
        self.reader: asyncio.Task | None = None
        self.closed = False
        self.reconnects = 0
        self.turn_offset = 0  # keeps turn_index monotonic across reconnects

    async def connect(self) -> None:
        try:
            self.ws = await websockets.connect(self.url, additional_headers=self.headers, open_timeout=5,
                                               ping_interval=20, max_queue=64)
        except websockets.exceptions.InvalidStatus as e:
            body = (e.response.body or b"")[:300].decode("utf-8", "replace")
            raise RuntimeError(f"deepgram flux refused the connection: HTTP {e.response.status_code} {body}") from e
        self.reader = asyncio.create_task(self._read(self.ws), name="flux-reader")

    async def _read(self, ws: ClientConnection) -> None:
        last_turn = 0
        try:
            async for msg in ws:
                if isinstance(msg, bytes):
                    continue
                d = json.loads(msg)
                t = d.get("type")
                if t == "TurnInfo":
                    kind = _EVENTS.get(d.get("event", ""))
                    if not kind:
                        continue
                    try:
                        dur = (float(d.get("audio_window_end", 0)) - float(d.get("audio_window_start", 0))) * 1000
                    except (TypeError, ValueError):
                        dur = 0.0
                    last_turn = int(d.get("turn_index", 0))
                    self.queue.put_nowait(TurnEvent(
                        kind=kind, text=(d.get("transcript") or "").strip(), duration_ms=int(dur),
                        confidence=float(d.get("end_of_turn_confidence") or 0.0),
                        turn_index=self.turn_offset + last_turn, trigger=d.get("trigger") or "",
                    ))
                elif t == "Error":
                    log.error("flux error: %s %s", d.get("code"), d.get("description"))
                elif t == "Warning":
                    log.warning("flux warning: %s %s", d.get("code"), d.get("description"))
        except websockets.ConnectionClosedOK:
            pass
        except websockets.ConnectionClosed as e:
            if not self.closed:
                log.warning("flux connection dropped: %s", e)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("flux reader failed")
        finally:
            self.turn_offset += last_turn + 1
            if ws is self.ws:
                self.ws = None
            if self.closed:
                self.queue.put_nowait(None)

    async def _ensure(self) -> ClientConnection | None:
        if self.ws is not None:
            return self.ws
        if self.closed or self.reconnects >= self.MAX_RECONNECTS:
            return None
        self.reconnects += 1
        try:
            await self.connect()
            log.info("flux reconnected (%d/%d)", self.reconnects, self.MAX_RECONNECTS)
        except Exception as e:  # noqa: BLE001
            log.error("flux reconnect failed: %r", e)
            if self.reconnects >= self.MAX_RECONNECTS:
                self.queue.put_nowait(None)  # give up: the consumer ends, the call goes on deaf
            return None
        return self.ws

    async def send(self, pcm16: bytes) -> None:
        self.buf.extend(pcm16)
        if len(self.buf) < self.chunk:
            return
        ws = await self._ensure()
        if ws is None:
            del self.buf[:]
            return
        try:
            while len(self.buf) >= self.chunk:
                await ws.send(bytes(self.buf[:self.chunk]))
                del self.buf[:self.chunk]
        except websockets.ConnectionClosed:
            pass  # the reader logs it; the next send() reconnects

    async def events(self) -> AsyncIterator[TurnEvent]:
        while True:
            ev = await self.queue.get()
            if ev is None:
                return
            yield ev

    async def close(self) -> None:
        self.closed = True
        ws, self.ws = self.ws, None
        if ws is not None:
            try:
                await ws.send(json.dumps({"type": "CloseStream"}))
                await asyncio.wait_for(ws.close(), timeout=2)
            except Exception:  # noqa: BLE001
                pass
        if self.reader is not None:
            self.reader.cancel()
            await asyncio.gather(self.reader, return_exceptions=True)
        self.queue.put_nowait(None)
