"""Asterisk AudioSocket server.

Protocol (res_audiosocket): every message is  type:1 byte | length:2 bytes BE | payload.
  0x00 terminate (either direction)
  0x01 UUID      first message from Asterisk, 16 raw bytes
  0x10 audio     320 bytes = 20 ms of 16-bit signed LE mono 8 kHz PCM (slin)
  0xff error     1 byte error code
Asterisk writes one audio frame every 20 ms and plays whatever audio frames
we send back. Dialplan:  AudioSocket(${UUID()},host:port)
"""
from __future__ import annotations

import asyncio
import logging
import struct
import uuid

from .base import CallHandler, CallSession, Transport

log = logging.getLogger(__name__)

KIND_TERMINATE = 0x00
KIND_UUID = 0x01
KIND_DTMF = 0x03
KIND_AUDIO = 0x10
KIND_ERROR = 0xFF

MAX_INBOUND_BACKLOG = 250  # frames (5 s) - if the pipeline stalls, drop oldest


class AudioSocketSession(CallSession):
    sample_rate = 8000

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, call_id: str, remote: str):
        self.reader = reader
        self.writer = writer
        self.call_id = call_id
        self.remote = remote
        self._inbound: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._closed = False
        self._reader_task = asyncio.create_task(self._read_loop(), name=f"audiosocket-read-{call_id[:8]}")

    async def _read_loop(self) -> None:
        try:
            while True:
                hdr = await self.reader.readexactly(3)
                kind, length = hdr[0], struct.unpack(">H", hdr[1:3])[0]
                payload = await self.reader.readexactly(length) if length else b""
                if kind == KIND_AUDIO:
                    if self._inbound.qsize() > MAX_INBOUND_BACKLOG:
                        self._inbound.get_nowait()
                    self._inbound.put_nowait(payload)
                elif kind == KIND_TERMINATE:
                    log.info("[%s] far end terminated", self.call_id[:8])
                    break
                elif kind == KIND_ERROR:
                    log.warning("[%s] asterisk error code %s", self.call_id[:8], payload.hex())
                elif kind == KIND_DTMF:
                    log.info("[%s] DTMF %r", self.call_id[:8], payload)
        except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception:  # pragma: no cover
            log.exception("[%s] read loop failed", self.call_id[:8])
        finally:
            self._closed = True
            self._inbound.put_nowait(None)

    async def receive(self) -> bytes | None:
        if self._closed and self._inbound.empty():
            return None
        return await self._inbound.get()

    async def send(self, frame: bytes) -> None:
        if self._closed:
            return
        try:
            self.writer.write(bytes((KIND_AUDIO,)) + struct.pack(">H", len(frame)) + frame)
            await self.writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            self._closed = True

    async def hangup(self) -> None:
        if not self._closed:
            try:
                self.writer.write(bytes((KIND_TERMINATE, 0, 0)))
                await self.writer.drain()
            except Exception:
                pass
        self._closed = True
        self._reader_task.cancel()
        self.writer.close()


class AudioSocketTransport(Transport):
    def __init__(self, host: str = "0.0.0.0", port: int = 9092, **_: object):
        self.host = host
        self.port = port

    async def run(self, handler: CallHandler) -> None:
        async def on_connect(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            peer = writer.get_extra_info("peername")
            remote = f"{peer[0]}:{peer[1]}" if peer else "?"
            try:
                hdr = await asyncio.wait_for(reader.readexactly(3), timeout=5)
                kind, length = hdr[0], struct.unpack(">H", hdr[1:3])[0]
                payload = await reader.readexactly(length)
            except Exception as e:
                log.warning("bad AudioSocket handshake from %s: %s", remote, e)
                writer.close()
                return
            call_id = str(uuid.UUID(bytes=payload)) if kind == KIND_UUID and length == 16 else uuid.uuid4().hex
            log.info("[%s] call connected from %s", call_id[:8], remote)
            session = AudioSocketSession(reader, writer, call_id, remote)
            try:
                await handler(session)
            except Exception:
                log.exception("[%s] call handler crashed", call_id[:8])
            finally:
                await session.hangup()
                log.info("[%s] call closed", call_id[:8])

        server = await asyncio.start_server(on_connect, self.host, self.port)
        addrs = ", ".join(str(s.getsockname()) for s in server.sockets or [])
        log.info("AudioSocket listening on %s  (dialplan: AudioSocket(${UUID()},<host>:%d))", addrs, self.port)
        async with server:
            await server.serve_forever()
