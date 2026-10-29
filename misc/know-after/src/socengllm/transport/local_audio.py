"""Talk to the persona through the Mac's microphone and speakers (no Asterisk).

Wear headphones: with speakers, the persona's own voice re-enters the mic and
trips barge-in. Or run with --set call.barge_in=false.
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque

import numpy as np

from ..audio import samples_per_frame
from .base import CallHandler, CallSession, Transport

log = logging.getLogger(__name__)


class LocalAudioSession(CallSession):
    def __init__(self, loop: asyncio.AbstractEventLoop, sample_rate: int = 16000, input_device=None, output_device=None):
        import sounddevice as sd

        self.sample_rate = sample_rate
        self.call_id = "local"
        self.remote = "microphone"
        self._loop = loop
        self._inbound: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._outbound: deque[bytes] = deque()
        self._closed = False
        n = samples_per_frame(sample_rate)

        def on_input(indata, frames, time, status):
            if status:
                log.debug("input status: %s", status)
            data = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
            loop.call_soon_threadsafe(self._inbound.put_nowait, data.astype("<i2").tobytes())

        def on_output(outdata, frames, time, status):
            if self._outbound:
                frame = self._outbound.popleft()
                arr = np.frombuffer(frame, dtype="<i2")
                outdata[: len(arr), 0] = arr
                outdata[len(arr) :, 0] = 0
            else:
                outdata.fill(0)

        self._in = sd.InputStream(samplerate=sample_rate, channels=1, dtype="int16", blocksize=n,
                                  device=input_device, callback=on_input)
        self._out = sd.OutputStream(samplerate=sample_rate, channels=1, dtype="int16", blocksize=n,
                                    device=output_device, callback=on_output)
        self._in.start()
        self._out.start()

    async def receive(self) -> bytes | None:
        if self._closed:
            return None
        return await self._inbound.get()

    async def send(self, frame: bytes) -> None:
        self._outbound.append(frame)

    async def hangup(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._inbound.put_nowait(None)
        for s in (self._in, self._out):
            try:
                s.stop()
                s.close()
            except Exception:
                pass


class LocalAudioTransport(Transport):
    def __init__(self, sample_rate: int = 16000, input_device=None, output_device=None, **_: object):
        self.sample_rate = sample_rate
        self.input_device = input_device
        self.output_device = output_device

    async def run(self, handler: CallHandler) -> None:
        loop = asyncio.get_running_loop()
        session = LocalAudioSession(loop, self.sample_rate, self.input_device, self.output_device)
        log.info("local audio call started (Ctrl-C to hang up)")
        try:
            await handler(session)
        finally:
            await session.hangup()
