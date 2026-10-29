"""DigitalOcean serverless inference: ElevenLabs Multilingual v2 (a fal-hosted model).

DigitalOcean exposes fal models only through its asynchronous API, so one sentence is
three or four HTTP round trips:

    POST https://inference.do-ai.run/v1/async-invoke   {"model_id": ..., "input": {"text": ...}}
    GET  .../async-invoke/<request_id>                  until "status" == "COMPLETED"
    GET  output.audio.url                               an MP3 (44.1 kHz mono) on fal.media

Each round trip costs ~400 ms on DigitalOcean's side, so expect 2-3 s from text to audio
regardless of sentence length. There is no streaming; the pipeline hides the latency by
synthesising the next sentences while the current one plays (set `tts.workers` > 1).

Scenario voices are Kokoro names (af_bella, am_michael, ...); `VOICE_MAP` turns them into
ElevenLabs voices so scenarios work unchanged. Any ElevenLabs premade voice name
(Rachel, Aria, Sarah, Laura, Charlotte, Alice, Matilda, Jessica, Lily, Brian, George,
Daniel, Roger, Charlie, Callum, Liam, Will, Eric, Chris, Bill, River) also works directly.
Env: DIGITALOCEAN_API_KEY (a model access key, `doo_v1_...`).

DigitalOcean-hosted models such as `qwen3-tts-voicedesign` use the synchronous, OpenAI-style
`POST /v1/audio/speech` instead and return a 24 kHz WAV in one response (no streaming; ~5 s for
a sentence when measured). That model has no preset voices: `instructions` describes the voice
in words, and `voice_map` may map scenario voice names to such descriptions. The model picks a
different voice for every request when the description is the same, so expect drift between
sentences. Any model whose id does not start with `fal-ai/` takes this path.
"""
from __future__ import annotations

import io
import logging
import os
import time

import httpx
import numpy as np
import soundfile as sf

from ..audio import resample
from .base import TTS

log = logging.getLogger(__name__)

VOICE_MAP = {
    "af_heart": "Rachel", "af_bella": "Sarah", "af_nicole": "Alice", "af_sarah": "Sarah",
    "af_sky": "Aria", "af_jessica": "Jessica", "af_river": "River",
    "am_michael": "Brian", "am_adam": "Eric", "am_fenrir": "George", "am_eric": "Eric",
    "am_liam": "Liam", "bf_emma": "Lily", "bf_alice": "Alice", "bm_george": "George",
    "bm_daniel": "Daniel", "bm_lewis": "Callum",
}
_DONE = {"COMPLETED", "COMPLETE", "FAILED", "ERROR", "CANCELLED"}


class DigitalOceanTTS(TTS):
    streaming = False

    def __init__(
        self,
        model: str = "fal-ai/elevenlabs/tts/multilingual-v2",
        voice: str | None = "Sarah",
        voice_map: dict[str, str] | None = None,
        stability: float | None = 0.5,
        similarity_boost: float | None = 0.75,
        style: float | None = None,
        speed: float | None = None,          # 0.7-1.2
        language_code: str | None = None,    # ISO 639-1; None = auto
        instructions: str | None = None,     # qwen3-tts-voicedesign: the voice, described in words
        speech_url: str = "https://inference.do-ai.run/v1/audio/speech",
        poll_ms: int = 100,
        timeout_s: float = 20.0,
        url: str = "https://inference.do-ai.run/v1/async-invoke",
        api_key_env: str = "DIGITALOCEAN_API_KEY",
        **_: object,
    ):
        key = os.environ.get(api_key_env)
        if not key:
            raise SystemExit(f"{api_key_env} is not set (put it in .env) - needed for DigitalOcean inference")
        self.model = model
        self.url = url
        self.speech_url = speech_url
        self.sync = not str(model).startswith("fal-ai/")
        self.instructions = instructions or "A friendly young woman, help desk technician, warm and natural. American English."
        self.voice_map = {**VOICE_MAP, **(voice_map or {})}
        self._user_voice_map = dict(voice_map or {})
        self.default_voice = self._voice(voice) if voice else "Sarah"
        self.extra = {k: v for k, v in {
            "stability": stability, "similarity_boost": similarity_boost, "style": style,
            "speed": speed, "language_code": language_code,
        }.items() if v is not None}
        self.poll_s = max(0.02, poll_ms / 1000)
        self.timeout_s = timeout_s
        self.sample_rate = 24000 if self.sync else 44100  # what the model returns; corrected on the first clip
        self._client = httpx.Client(headers={"Authorization": f"Bearer {key}"}, timeout=httpx.Timeout(15.0, read=60.0))
        log.info("tts: digitalocean model=%s %s", model,
                 f"instructions={self.instructions!r}" if self.sync else f"voice={self.default_voice}")

    # ----------------------------------------------------------------- voices
    def _voice(self, voice: str | None) -> str:
        if not voice:
            return self.default_voice
        return self.voice_map.get(voice, voice)  # unknown names are passed through as ElevenLabs voices

    # ------------------------------------------------------------- synthesis
    def _request(self, method: str, url: str, **kw) -> httpx.Response:
        """One HTTP call with a single retry on transport errors / 5xx."""
        for attempt in (1, 2):
            try:
                r = self._client.request(method, url, **kw)
                if r.status_code < 500:
                    return r
                err: Exception = RuntimeError(f"HTTP {r.status_code} {r.text[:200]}")
            except httpx.TransportError as e:
                err = e
            if attempt == 2:
                raise RuntimeError(f"digitalocean tts: {method} {url} failed: {err}") from None
            log.warning("digitalocean tts: %s failed (%r); retrying", method, err)
        raise AssertionError("unreachable")

    def _finish(self, data: bytes) -> np.ndarray:
        audio, sr = sf.read(io.BytesIO(data), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sr != self.sample_rate:
            # Keep one rate for the pipeline's resampler; the first clip sets it.
            if not hasattr(self, "_rate_fixed"):
                self.sample_rate = sr
            else:
                audio = resample(audio, sr, self.sample_rate)
        self._rate_fixed = True
        return audio

    def _synthesize_sync(self, text: str, voice: str | None) -> np.ndarray:
        """DigitalOcean-hosted TTS (qwen3-tts-voicedesign): one blocking request, WAV back."""
        t0 = time.monotonic()
        # For a voice-design model the "voice" is a description. Only the user's own voice_map
        # entries apply here (the built-in map holds ElevenLabs names); anything else gets the default.
        body = {"model": self.model, "input": text, "voice": "default",
                "instructions": self._user_voice_map.get(voice or "", self.instructions)}
        r = self._request("POST", self.speech_url, json=body)
        if r.status_code != 200:
            raise RuntimeError(f"digitalocean tts: speech rejected HTTP {r.status_code} {r.text[:200]} ({len(text)} chars)")
        data = r.content
        if r.headers.get("content-type", "").startswith("application/json"):  # base64 envelope variant
            import base64
            data = base64.b64decode(r.json()["data"][0]["b64_json"])
        audio = self._finish(data)
        log.debug("digitalocean tts: %d chars -> %.1fs audio in %.0f ms (sync)", len(text), len(audio) / self.sample_rate,
                  (time.monotonic() - t0) * 1000)
        return audio

    def synthesize(self, text: str, voice: str | None = None) -> np.ndarray:
        if self.sync:
            return self._synthesize_sync(text, voice)
        t0 = time.monotonic()
        body = {"model_id": self.model, "input": {"text": text, "voice": self._voice(voice), **self.extra}}
        r = self._request("POST", self.url, json=body)
        if r.status_code != 200:
            raise RuntimeError(f"digitalocean tts: submit rejected HTTP {r.status_code} {r.text[:200]} "
                               f"(voice={body['input']['voice']!r}, {len(text)} chars)")
        rid = r.json()["request_id"]
        deadline = t0 + self.timeout_s
        polls = 0
        while True:
            polls += 1
            job = self._request("GET", f"{self.url}/{rid}").json()
            status = job.get("status")
            if status in _DONE:
                break
            if time.monotonic() > deadline:
                raise RuntimeError(f"digitalocean tts: job {rid} still {status} after {self.timeout_s:.0f}s")
            time.sleep(self.poll_s)
        if status not in ("COMPLETED", "COMPLETE"):
            raise RuntimeError(f"digitalocean tts: job {rid} {status}: {job.get('error')}")
        t_done = time.monotonic()
        audio_url = job["output"]["audio"]["url"]
        data = self._request("GET", audio_url).content
        audio = self._finish(data)
        log.debug("digitalocean tts: %d chars -> %.1fs audio in %.0f ms (queue %.0f ms, %d polls, download %.0f ms)",
                  len(text), len(audio) / self.sample_rate, (time.monotonic() - t0) * 1000,
                  (t_done - t0) * 1000, polls, (time.monotonic() - t_done) * 1000)
        return audio

    def warmup(self) -> None:
        self.synthesize("Hello.")  # fails fast on a bad key or a model without preview access
