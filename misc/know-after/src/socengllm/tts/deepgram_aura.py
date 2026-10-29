"""Deepgram Aura-2 text-to-speech over its streaming WebSocket.

One persistent connection per voice (wss://api.deepgram.com/v1/speak). Each sentence is a
`Speak` + `Flush`; audio comes back as binary frames (~120 ms to the first one on a warm
connection) until a `Flushed` message. `synthesize_stream` yields those frames as they
arrive so the pipeline can start playing before the sentence is finished; `synthesize`
concatenates them for callers that want the whole clip. Env: DEEPGRAM_API_KEY.

Scenario voices are Kokoro names (af_bella, am_michael, ...); `VOICE_MAP` turns those into
Aura voices so scenarios work unchanged when you switch backends. Override per voice with
`voice_map:` in the tts config.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Iterator

import numpy as np
import websockets
from websockets.sync.client import ClientConnection, connect

from .base import TTS

log = logging.getLogger(__name__)

VOICE_MAP = {
    # Kokoro persona voices -> Aura-2 equivalents (feminine / masculine, similar energy)
    "af_heart": "aura-2-luna-en", "af_bella": "aura-2-luna-en", "af_nicole": "aura-2-pandora-en",
    "af_sarah": "aura-2-athena-en", "af_sky": "aura-2-thalia-en",
    "am_michael": "aura-2-orion-en", "am_adam": "aura-2-arcas-en", "am_fenrir": "aura-2-zeus-en",
    "bf_emma": "aura-2-pandora-en", "bm_george": "aura-2-draco-en",
}


class AuraTTS(TTS):
    streaming = True

    def __init__(
        self,
        voice: str | None = "aura-2-luna-en",
        sample_rate: int = 24000,
        voice_map: dict[str, str] | None = None,
        url: str = "wss://api.deepgram.com/v1/speak",
        api_key_env: str = "DEEPGRAM_API_KEY",
        recv_timeout_s: float = 10.0,
        **_: object,
    ):
        key = os.environ.get(api_key_env)
        if not key:
            raise SystemExit(f"{api_key_env} is not set (put it in .env) - needed for Deepgram Aura")
        self.headers = {"Authorization": f"Token {key}"}
        self.url = url
        self.sample_rate = int(sample_rate)
        self.voice_map = {**VOICE_MAP, **(voice_map or {})}
        self.default_voice = self._voice(voice) if voice else "aura-2-luna-en"
        self.recv_timeout_s = recv_timeout_s
        # One websocket per voice PER TTS THREAD. Deepgram serialises sentences on a connection, so
        # sharing one across calls would queue every call behind every other (tts.workers sets how
        # many sentences can be in flight at once; each worker thread connects lazily on first use).
        self._local = threading.local()
        log.info("tts: deepgram aura voice=%s rate=%d", self.default_voice, self.sample_rate)

    # ----------------------------------------------------------------- voices
    def _voice(self, voice: str | None) -> str:
        if not voice:
            return self.default_voice
        if voice in self.voice_map:
            return self.voice_map[voice]
        if voice.startswith("aura"):
            return voice
        log.warning("unknown voice %r for Aura; using %s", voice, self.default_voice)
        return self.default_voice

    # ------------------------------------------------------------ connection
    def _connect(self, voice: str) -> ClientConnection:
        url = f"{self.url}?model={voice}&encoding=linear16&sample_rate={self.sample_rate}"
        t0 = time.monotonic()
        ws = connect(url, additional_headers=self.headers, open_timeout=5, max_size=None)
        log.debug("aura connected voice=%s in %.0f ms", voice, (time.monotonic() - t0) * 1000)
        return ws

    @property
    def _conns(self) -> dict[str, ClientConnection]:
        conns = getattr(self._local, "conns", None)
        if conns is None:
            conns = self._local.conns = {}
        return conns

    def _conn(self, voice: str, fresh: bool = False) -> ClientConnection:
        ws = self._conns.get(voice)
        if ws is not None and (fresh or ws.close_code is not None):
            try:
                ws.close()
            except Exception:  # noqa: BLE001
                pass
            ws = None
        if ws is None:
            ws = self._conns[voice] = self._connect(voice)
        return ws

    # ------------------------------------------------------------- synthesis
    def synthesize_stream(self, text: str, voice: str | None = None) -> Iterator[np.ndarray]:
        """Yield float32 chunks as Deepgram produces them. Blocking; runs on the TTS thread."""
        v = self._voice(voice)
        for attempt in (1, 2):
            ws = self._conn(v, fresh=attempt == 2)
            yielded = False
            try:
                ws.send(json.dumps({"type": "Speak", "text": text}))
                ws.send(json.dumps({"type": "Flush"}))
                while True:
                    msg = ws.recv(timeout=self.recv_timeout_s)
                    if isinstance(msg, bytes):
                        if msg:
                            yielded = True
                            yield np.frombuffer(msg, dtype="<i2").astype(np.float32) / 32768.0
                        continue
                    d = json.loads(msg)
                    t = d.get("type")
                    if t == "Flushed":
                        return
                    if t == "Error":
                        raise RuntimeError(f"aura error: {d.get('code')} {d.get('description')}")
                    if t == "Warning":
                        log.warning("aura warning: %s %s", d.get("code"), d.get("description"))
            except (websockets.ConnectionClosed, TimeoutError, OSError) as e:
                if yielded or attempt == 2:
                    raise
                log.warning("aura connection lost (%r); reconnecting", e)

    def synthesize(self, text: str, voice: str | None = None) -> np.ndarray:
        chunks = list(self.synthesize_stream(text, voice))
        return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)

    def warmup(self) -> None:
        self.synthesize("Hello.")  # opens this thread's default-voice connection; others connect on first use
