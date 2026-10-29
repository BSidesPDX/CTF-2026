"""Per-call orchestration.

    frames in -> resample -> VAD/endpointer -> STT -> LLM (streamed) ->
    sentence chunker -> TTS -> resample -> 20 ms paced playback -> frames out

Latency budget per turn (M3 Pro, defaults): end-of-speech detection ~650 ms,
STT 150-500 ms, LLM first token 400-900 ms, TTS first sentence 200-400 ms.
Barge-in: sustained caller speech while the persona talks flushes playback
and cancels the in-flight LLM/TTS work.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

import numpy as np

from .audio import STT_RATE, StreamResampler, float_to_pcm16, pcm16_to_float, resample, to_frames
from .llm import LLM, LLMRefusal, Message
from .monitor import MonitorContext, MonitorPolicy, Turn, Verdict
from .monitor.base import reviewer_briefing
from .scenario import (ACTION_RE, HANGUP_TOKEN, HOLD_RETURN_NOTE, Action, Persona, Scenario,  # noqa: F401
                       parse_action, spell_for_speech, system_prompt)
from .sounds import LoopPlayer, chime, hold_music, thinking_sound, transfer_tone, voicemail_beep
from .stt import STT, StreamingSTT, TurnStream
from .transport import CallSession
from .tts import TTS
from .vad import Endpointer

log = logging.getLogger(__name__)

# Short acknowledgements people make while the other side is talking. When the
# persona is mid-sentence these are not a new turn and must not cut her off.
_BACKCHANNELS = {
    "yeah", "yes", "yep", "yup", "ok", "okay", "mhm", "mm", "hmm", "uh", "huh", "uh huh", "mm hmm",
    "right", "sure", "hello", "hi", "hey", "oh", "alright", "got it", "i see", "cool", "great",
    "thanks", "thank you", "oh okay", "okay yeah", "yeah okay", "yes please", "please",
}


def is_backchannel(text: str) -> bool:
    words = re.sub(r"[^a-z ]", "", text.lower()).split()
    return 0 < len(words) <= 2 and " ".join(words) in _BACKCHANNELS


def _same_utterance(a: str, b: str) -> bool:
    norm = lambda t: re.sub(r"[^a-z0-9 ]", "", t.lower()).split()  # noqa: E731
    return norm(a) == norm(b)


@dataclass
class _Provisional:
    text: str
    confirm: asyncio.Event
    hist_idx: int
    turn_idx: int
    since: float


class CallTerminated(Exception):
    def __init__(self, verdict: Verdict):
        super().__init__(verdict.summary())
        self.verdict = verdict

_SENTENCE_END = re.compile(r"([.!?]+[\"')\]]?)(\s+|$)")


class SentenceChunker:
    """Turn a token stream into speakable chunks as early as possible."""

    def __init__(self, soft_limit: int = 90, hard_limit: int = 180, first_soft_limit: int = 28):
        self.buf = ""
        self.soft_limit = soft_limit
        self.hard_limit = hard_limit  # cut at a space past this even with no punctuation (lists, counting)
        # The first chunk gates time-to-first-audio (TTS needs ~1/4 of a sentence's
        # duration before it can play), so cut it at the first clause boundary.
        self.first_soft_limit = first_soft_limit
        self.emitted = 0

    def push(self, delta: str) -> list[str]:
        self.buf += delta
        out: list[str] = []
        while True:
            m = _SENTENCE_END.search(self.buf)
            if m and m.end(1) >= 2:
                sent, self.buf = self.buf[: m.end(1)], self.buf[m.end() :]
                if sent.strip():
                    out.append(sent.strip())
                    self.emitted += 1
                continue
            limit = self.first_soft_limit if self.emitted == 0 else self.soft_limit
            if len(self.buf) > limit:
                idx = max(self.buf.rfind(", "), self.buf.rfind("; "), self.buf.rfind(" - "))
                if idx > (8 if self.emitted == 0 else 25):
                    sent, self.buf = self.buf[: idx + 1], self.buf[idx + 1 :]
                    out.append(sent.strip())
                    self.emitted += 1
                    continue
            if len(self.buf) > self.hard_limit:
                idx = self.buf.rfind(" ", 0, self.hard_limit)
                if idx > 25:
                    sent, self.buf = self.buf[:idx], self.buf[idx + 1 :]
                    out.append(sent.strip())
                    self.emitted += 1
                    continue
            break
        return out

    def flush(self) -> list[str]:
        s, self.buf = self.buf.strip(), ""
        return [s] if s else []


def split_open_bracket(buf: str) -> tuple[str, str]:
    """Hold back an unfinished [token] so a half-streamed action or log tag is never spoken."""
    i = buf.rfind("[")
    if i >= 0 and "]" not in buf[i:]:
        return buf[:i], buf[i:]
    return buf, ""


def clean_for_speech(text: str) -> str:
    text = ACTION_RE.sub(" ", text)
    text = re.sub(r"\*[^*\n]{0,80}\*", " ", text)     # *sighs*
    text = re.sub(r"\[[^\]\n]{0,200}\]", " ", text)   # [pause], [flag log tag]
    text = re.sub(r"\([^)\n]{0,80}\)", " ", text)     # (laughs)
    text = re.sub(r"[*_#`~>|]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@dataclass
class Components:
    stt: STT | None                 # batch STT (used with the local VAD/endpointer)
    llm: LLM
    tts: TTS
    make_endpointer: Callable[[], Endpointer]
    turn_stt: StreamingSTT | None = None   # streaming STT with its own turn detection (replaces stt + VAD)
    greeting_audio: dict[tuple, list[bytes]] = field(default_factory=dict)  # (rate, text, voice) -> frames
    tone_audio: dict[tuple, list[bytes]] = field(default_factory=dict)      # (name, rate) -> frames
    thinking_audio: dict[int, list[bytes]] = field(default_factory=dict)  # sample_rate -> frames
    system_audio: dict[tuple[int, str], list[bytes]] = field(default_factory=dict)
    system_voice: str | None = None            # TTS voice for announcements / termination
    monitor: MonitorPolicy | None = None       # None = no monitoring
    monitor_gate: str = "reply"                # reply | caller | observe | off
    # One dedicated thread per model. MLX keeps device streams per thread, so
    # every call into an MLX model must come from the thread that warmed it up;
    # a single worker also serialises GPU work and keeps TTS and STT from
    # fighting each other.
    stt_pool: ThreadPoolExecutor = field(default_factory=lambda: ThreadPoolExecutor(1, thread_name_prefix="stt"))
    tts_pool: ThreadPoolExecutor = field(default_factory=lambda: ThreadPoolExecutor(1, thread_name_prefix="tts"))
    tts_prefetch: bool = False  # synthesise upcoming sentences concurrently (cloud TTS with tts.workers > 1)

    def warmup(self) -> None:
        if self.stt is not None:
            self.stt_pool.submit(self.stt.warmup).result()
        self.tts_pool.submit(self.tts.warmup).result()

    def thinking_frames(self, cfg: "CallConfig", rate: int) -> list[bytes]:
        ts = cfg.thinking_sound
        if not ts.get("enabled", True):
            return []
        if rate not in self.thinking_audio:
            audio = thinking_sound(ts.get("style", "blips"), rate, float(ts.get("volume", 0.2)), ts.get("file"))
            self.thinking_audio[rate] = to_frames(float_to_pcm16(audio), rate)
        return self.thinking_audio[rate]

    def system_frames(self, text: str, rate: int, file: str | None = None, chime_first: bool = True,
                      voice: str | None = None) -> list[bytes]:
        """A fixed line (announcement / termination / voicemail greeting). Played verbatim from
        `file` when it exists (render with scripts/render_system_lines.py, or drop in your own
        recording); otherwise synthesised in `voice` (default: the system voice), with a chime if
        asked. Loaded once per process. Thread-safe."""
        import os

        use_file = file if file and os.path.exists(file) else None
        if file and not use_file:
            log.warning("system line file %s missing; synthesising %r instead "
                        "(run scripts/render_system_lines.py)", file, text)
        voice = voice or self.system_voice
        key = (rate, use_file or text, chime_first, voice)
        if key not in self.system_audio:
            def render() -> list[bytes]:
                if use_file:
                    import soundfile as sf

                    audio, sr = sf.read(use_file, dtype="float32")
                    if audio.ndim > 1:
                        audio = audio.mean(axis=1)
                else:
                    sr = self.tts.sample_rate
                    speech = self.tts.synthesize(clean_for_speech(text), voice=voice)
                    lead = chime(sr) if chime_first else np.zeros(sr // 5, np.float32)
                    audio = np.concatenate([lead, speech, np.zeros(sr // 3, np.float32)])
                return to_frames(float_to_pcm16(resample(audio, sr, rate)), rate)
            self.system_audio[key] = self.tts_pool.submit(render).result()
        return self.system_audio[key]

    def greeting_frames(self, text: str, rate: int, voice: str | None = None) -> list[bytes]:
        """A persona's scripted greeting in its voice. Thread-safe; synthesised once per process."""
        key = (rate, text, voice)
        if key not in self.greeting_audio:
            def render() -> list[bytes]:
                audio = self.tts.synthesize(clean_for_speech(text), voice=voice)
                audio = resample(audio, self.tts.sample_rate, rate)
                return to_frames(float_to_pcm16(audio), rate)
            self.greeting_audio[key] = self.tts_pool.submit(render).result()
        return self.greeting_audio[key]

    def hold_frames(self, sc: Scenario, rate: int) -> list[bytes]:
        """Transfer tone + hold music for the scenario's hold length."""
        key = ("hold", rate)
        if key not in self.tone_audio:
            audio = np.concatenate([transfer_tone(rate), hold_music(rate, sc.hold_seconds, file=sc.hold_music_file)])
            self.tone_audio[key] = to_frames(float_to_pcm16(audio), rate)
        return self.tone_audio[key]

    def voicemail_frames(self, persona: Persona, rate: int) -> list[bytes]:
        """An out-of-office persona's voicemail greeting in its own voice, then the beep."""
        key = ("beep", rate)
        if key not in self.tone_audio:
            self.tone_audio[key] = to_frames(float_to_pcm16(voicemail_beep(rate)), rate)
        return self.system_frames(persona.voicemail or "", rate, None, False, persona.voice) + self.tone_audio[key]

    def prerender(self, sc: Scenario, rate: int = 8000) -> None:
        """Synthesise every fixed line of the scenario (greetings, voicemails, system lines) up front."""
        jobs = []
        for p in sc.personas.values():
            if p.out:
                jobs.append(lambda p=p: self.voicemail_frames(p, rate))
            elif p.greeting:
                jobs.append(lambda p=p: self.greeting_frames(p.greeting, rate, p.voice))
        m = sc.monitor
        if self.monitor:
            if m.announcement:
                jobs.append(lambda: self.system_frames(m.announcement, rate, m.announcement_file))
            jobs.append(lambda: self.system_frames(m.termination_line, rate, m.termination_file))
            for reason in set(m.termination_reasons.values()):
                line = " ".join(t for t in (reason, m.termination_farewell) if t)
                jobs.append(lambda line=line: self.system_frames(line, rate, None, False))
        jobs.append(lambda: self.hold_frames(sc, rate))
        # Rendered through the TTS pool; with a cloud backend and tts.workers > 1 they run concurrently.
        with ThreadPoolExecutor(max(1, self.tts_pool._max_workers)) as ex:
            list(ex.map(lambda j: j(), jobs))


@dataclass
class CallConfig:
    barge_in: bool = True
    max_seconds: int = 900
    greeting_delay_ms: int = 400
    calls_dir: str = "calls"
    # Filler played while the LLM works (see socengllm/sounds.py).
    thinking_sound: dict = field(default_factory=lambda: {"enabled": True, "style": "blips", "volume": 0.2, "delay_ms": 0})


class CallPipeline:
    def __init__(self, session: CallSession, comps: Components, scenario: Scenario, cfg: CallConfig):
        self._first_audio_ms: int | None = None  # set per reply; read by the eager-confirm path, which may run first
        self.session = session
        self.comps = comps
        self.scenario = scenario
        self.cfg = cfg
        self.persona: Persona = scenario.start_persona      # who is on the line right now
        self.voice = self.persona.voice
        self.system = system_prompt(scenario, self.persona)
        self.history: list[Message] = []                     # the current persona's view
        self.events: list[dict] = []
        self.out: deque[bytes] = deque()
        self.out_event = asyncio.Event()
        self.response_task: asyncio.Task | None = None
        self.hangup_after_playback = False
        self.after_playback: Callable[[], Awaitable[None]] | None = None  # transfer / hold, once the queue drains
        self.busy = False               # hold music or voicemail playing: caller audio is ignored
        self.transfers = 0
        self.flag_revealed = False
        self.started = time.monotonic()
        self.started_at = datetime.now()
        self.loop = asyncio.get_running_loop()
        self.endpointer = comps.make_endpointer()
        self.tag = session.call_id[:8]
        self.thinking = False
        self.thinking_since = 0.0
        self.filler = LoopPlayer(comps.thinking_frames(cfg, session.sample_rate))
        # security monitor
        self.turns: list[Turn] = [Turn("agent", self.persona.greeting)]   # the monitor's view: whole call
        self.briefing = reviewer_briefing(scenario) if comps.monitor else ""
        self.notes: str | None = None      # operator note injected into the persona's next turns
        self.terminated = False
        # speculative reply started on a streaming STT's eager end-of-turn, awaiting confirmation
        self._provisional: _Provisional | None = None
        self.barge_in_ms = getattr(getattr(self.endpointer, "cfg", None), "barge_in_ms", 450)
        # Privacy: caller ID and the dialled number are deliberately never looked up, logged or saved.

    # ------------------------------------------------------------------ util

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def event(self, kind: str, text: str = "", level: int = logging.INFO, **extra) -> None:
        self.events.append({"t": round(self.elapsed(), 2), "kind": kind, "text": text, **extra})
        detail = " ".join(f"{k}={v}" for k, v in extra.items())
        log.log(level, "[%s] %-8s %s %s", self.tag, kind, text, f"({detail})" if detail else "")

    def _merged_history(self) -> list[Message]:
        merged: list[Message] = []
        for m in self.history:
            if merged and merged[-1].role == m.role:
                merged[-1] = Message(m.role, merged[-1].content + "\n" + m.content)
            else:
                merged.append(Message(m.role, m.content))
        return merged

    def _is_speaking(self) -> bool:
        return bool(self.out) or (self.response_task is not None and not self.response_task.done())

    # ------------------------------------------------------------------ main
    async def run(self) -> None:
        self.event("call", f"started via {self.session.remote} scenario={self.scenario.name}")
        player = asyncio.create_task(self._player(), name=f"player-{self.tag}")
        resampler = StreamResampler(self.session.sample_rate, STT_RATE)
        try:
            await asyncio.sleep(self.cfg.greeting_delay_ms / 1000)
            if self.comps.monitor and self.scenario.monitor.announcement:
                frames = await asyncio.to_thread(
                    self.comps.system_frames, self.scenario.monitor.announcement, self.session.sample_rate,
                    self.scenario.monitor.announcement_file,
                )
                self._enqueue(frames + [b"\x00" * len(frames[0])] * 20)  # + 400 ms pause
                self.event("system", self.scenario.monitor.announcement)
            frames = await asyncio.to_thread(
                self.comps.greeting_frames, self.persona.greeting, self.session.sample_rate, self.voice
            )
            self._enqueue(frames)
            self.event("persona", self.persona.greeting, who=self.persona.name)

            if self.comps.turn_stt is not None:
                await self._listen_streaming()
            else:
                await self._listen_local(resampler)
        finally:
            if self.response_task and not self.response_task.done():
                self.response_task.cancel()
                await asyncio.gather(self.response_task, return_exceptions=True)
            player.cancel()
            await asyncio.gather(player, return_exceptions=True)
            self._save()

    async def _next_frame(self) -> bytes | None:
        frame = await self.session.receive()
        if frame is None:
            self.event("call", "far end hung up")
            return None
        if self.elapsed() > self.cfg.max_seconds:
            self.event("call", "max duration reached")
            return None
        return frame

    async def _listen_local(self, resampler: StreamResampler) -> None:
        """Local VAD + endpointer decide the turns; whole utterances go to a batch STT."""
        while True:
            frame = await self._next_frame()
            if frame is None:
                return
            audio = resampler.process(pcm16_to_float(frame))
            if self.terminated or self.busy:
                continue  # the system is saying goodbye / hold music: the caller can't barge in on that
            for ev in self.endpointer.feed(audio):
                if ev.kind == "sustained":
                    if self.cfg.barge_in and self._is_speaking():
                        await self._interrupt("barge-in")
                elif ev.kind == "utterance":
                    await self._on_utterance(ev.audio, ev.duration_ms)

    async def _listen_streaming(self) -> None:
        """A streaming STT (Deepgram Flux) does VAD, endpointing and recognition server-side."""
        t0 = time.monotonic()
        stream = await self.comps.turn_stt.open(self.session.sample_rate)
        log.debug("[%s] streaming stt connected in %.0f ms", self.tag, (time.monotonic() - t0) * 1000)
        consumer = asyncio.create_task(self._consume_turns(stream), name=f"turns-{self.tag}")
        try:
            while True:
                frame = await self._next_frame()
                if frame is None:
                    return
                await stream.send(frame)  # raw 8 kHz slin goes up as-is
        finally:
            consumer.cancel()
            await asyncio.gather(consumer, return_exceptions=True)
            await stream.close()

    async def _consume_turns(self, stream: TurnStream) -> None:
        try:
            async for ev in stream.events():
                if self.terminated or self.busy:
                    continue
                if ev.kind == "update":
                    # Barge-in: real speech (not a backchannel) of at least barge_in_ms while we talk.
                    # Not while a provisional reply is held: that is the caller finishing their own turn.
                    if (self.cfg.barge_in and self._provisional is None and self._is_speaking()
                            and ev.text and ev.duration_ms >= self.barge_in_ms and not is_backchannel(ev.text)):
                        await self._interrupt("barge-in")
                elif ev.kind == "eager_end":
                    await self._on_caller_text(ev.text, ev.duration_ms, provisional=True)
                elif ev.kind == "resumed":
                    await self._drop_provisional("caller kept talking")
                elif ev.kind == "end":
                    await self._on_caller_text(ev.text, ev.duration_ms, trigger=ev.trigger)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.exception("[%s] streaming stt failed", self.tag)
            self.event("error", f"stt stream: {e!r}", level=logging.ERROR)

    # ------------------------------------------------------------- handlers
    async def _interrupt(self, reason: str) -> None:
        self.out.clear()
        if self.response_task and not self.response_task.done():
            self.response_task.cancel()
            await asyncio.gather(self.response_task, return_exceptions=True)
        self.event("interrupt", reason)

    async def _on_utterance(self, audio: np.ndarray, duration_ms: int) -> None:
        t0 = time.monotonic()
        try:
            text = await self.loop.run_in_executor(self.comps.stt_pool, self.comps.stt.transcribe, audio)
        except Exception as e:
            log.exception("[%s] STT failed", self.tag)
            self.event("error", f"stt: {e!r}", level=logging.ERROR)
            return
        stt_ms = round((time.monotonic() - t0) * 1000)
        await self._on_caller_text(text, duration_ms, stt_ms=stt_ms)

    async def _on_caller_text(self, text: str, duration_ms: int, stt_ms: int | None = None,
                              provisional: bool = False, trigger: str = "") -> None:
        """A caller turn, final or (with a streaming STT) provisional.

        Provisional = the STT thinks the turn is probably over. We start the LLM right away but
        hold its audio until the turn is confirmed; if the caller keeps talking the reply is
        dropped (TurnResumed) or restarted (final text differs)."""
        text = (text or "").strip()
        if self.terminated or self.busy:
            return
        if not text:
            if not provisional:
                self.event("vad", f"empty turn ({trigger or 'no speech'})", level=logging.DEBUG, audio_ms=duration_ms)
            return
        if self._is_speaking() and self._provisional is None and is_backchannel(text):
            self.event("vad", f"backchannel ignored while speaking: {text!r}", level=logging.DEBUG)
            return
        p = self._provisional
        if p is not None:
            if _same_utterance(p.text, text):
                if provisional:
                    return  # repeated eager event for the same words
                # Confirmed: release the held reply, keep the final wording in the record.
                self.history[p.hist_idx] = Message("user", text)
                self.turns[p.turn_idx] = Turn("caller", text)
                self._provisional = None
                head_start = round((self.loop.time() - p.since) * 1000)
                self.event("caller", text, audio_ms=duration_ms, eager_ms=head_start)
                p.confirm.set()
                if self.response_task is not None and not self.response_task.done() and self._first_audio_ms is None:
                    self._set_thinking(True)
                return
            await self._drop_provisional("final transcript differs")
        extra = {"audio_ms": duration_ms}
        if stt_ms is not None:
            extra["stt_ms"] = stt_ms
        if provisional:
            self.event("eager", text, level=logging.DEBUG, **extra)
        else:
            self.event("caller", text, **extra)
        if self._is_speaking():
            await self._interrupt("new utterance")
        self.history.append(Message("user", text))
        self.turns.append(Turn("caller", text))
        hold: asyncio.Event | None = None
        if provisional:
            hold = asyncio.Event()
            self._provisional = _Provisional(text, hold, len(self.history) - 1, len(self.turns) - 1, self.loop.time())
        # Reset here, not inside _respond: when Flux's eager and final transcripts arrive together
        # the confirm path checks this before the task has started and would see the previous turn.
        self._first_audio_ms = None
        self.response_task = asyncio.create_task(self._respond(hold), name=f"respond-{self.tag}")

    async def _drop_provisional(self, reason: str) -> None:
        p, self._provisional = self._provisional, None
        if p is None:
            return
        if self.response_task is not None and not self.response_task.done():
            self.response_task.cancel()
            await asyncio.gather(self.response_task, return_exceptions=True)
        if len(self.history) > p.hist_idx and self.history[p.hist_idx].content == p.text:
            del self.history[p.hist_idx:]
        if len(self.turns) > p.turn_idx and self.turns[p.turn_idx].text == p.text:
            del self.turns[p.turn_idx:]
        self._set_thinking(False)
        self.event("eager", f"dropped: {reason}", level=logging.DEBUG)

    async def _respond(self, hold: asyncio.Event | None = None, continuation: bool = False) -> None:
        """One persona message. `continuation`: the persona is back from a [HOLD] and speaks again
        without a new caller turn (no caller check, same caller text for the monitor)."""
        spoken: list[str] = []
        full = ""
        buf = ""   # streamed text not yet handed to the chunker (an action token may still be open)
        t0 = time.monotonic()
        ttft_ms: int | None = None
        self._first_audio_ms = None
        gate_open = asyncio.Event()          # TTS audio is held until the monitor clears the turn
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        worker = asyncio.create_task(self._tts_worker(queue, spoken, t0, gate_open, hold), name=f"tts-{self.tag}")
        chunker = SentenceChunker()
        monitor = self.comps.monitor
        gate = self.comps.monitor_gate if monitor else "off"
        caller_text = next((m.content for m in reversed(self.history)
                            if m.role == "user" and m.content != HOLD_RETURN_NOTE), "")
        caller_check: asyncio.Task | None = None
        if monitor and gate in ("caller", "reply", "observe") and not continuation:
            caller_check = asyncio.create_task(
                monitor.evaluate(MonitorContext(self.briefing, list(self.turns), caller_text)),
                name=f"monitor-caller-{self.tag}",
            )
        if gate not in ("caller", "reply") or (continuation and gate == "caller"):
            gate_open.set()
        if hold is None:
            self._set_thinking(True)  # a held (provisional) reply starts the blips once confirmed
        try:
            async with contextlib.aclosing(
                self.comps.llm.stream(self.system, self._merged_history(), self.notes)
            ) as stream:
                async for delta in stream:
                    if ttft_ms is None:
                        ttft_ms = round((time.monotonic() - t0) * 1000)
                    full += delta
                    speak, buf = split_open_bracket(buf + delta)
                    for sent in chunker.push(self._strip_tags(speak)):
                        queue.put_nowait(sent)
                    if caller_check is not None and caller_check.done():
                        v, caller_check = caller_check.result(), None
                        self._apply_verdict(v, "caller", gate, gate_open)  # may raise CallTerminated
            tail = self._strip_tags(buf) if "]" in buf else ""   # an unclosed "[..." is never spoken
            for sent in chunker.push(tail) + chunker.flush():
                queue.put_nowait(sent)
            if caller_check is not None:
                v, caller_check = await caller_check, None
                self._apply_verdict(v, "caller", gate, gate_open)
            text, action = parse_action(full)
            if monitor and gate in ("reply", "lazy", "observe") and text:
                # lazy: the audio has been playing since the first sentence; this
                # verdict arrives only after the whole draft exists. Intentional.
                if gate == "lazy" and self.scenario.monitor.lazy_delay_ms:
                    await asyncio.sleep(self.scenario.monitor.lazy_delay_ms / 1000)
                v = await monitor.evaluate(MonitorContext(
                    self.briefing, list(self.turns) + [Turn("agent", text)], caller_text, pending_reply=text,
                ))
                self._apply_verdict(v, "reply", gate, gate_open)
            gate_open.set()
            queue.put_nowait(None)
            await worker
            self.history.append(Message("assistant", text or "..."))
            if text:
                self.turns.append(Turn("agent", text))
            self.event("persona", text, who=self.persona.name, ttft_ms=ttft_ms, first_audio_ms=self._first_audio_ms,
                       total_ms=round((time.monotonic() - t0) * 1000))
            if action is not None:
                self._act(action)
        except CallTerminated as e:
            worker.cancel()
            if caller_check is not None:
                caller_check.cancel()
            await self._terminate(e.verdict, suppressed=full.strip())
        except asyncio.CancelledError:
            worker.cancel()
            if caller_check is not None:
                caller_check.cancel()
            partial = " ".join(spoken).strip()
            if partial:
                self.history.append(Message("assistant", partial + " --"))
                self.turns.append(Turn("agent", partial))
                self.event("persona", partial, who=self.persona.name, interrupted=True)
            raise
        except LLMRefusal as e:
            worker.cancel()
            gate_open.set()
            self.event("refusal", str(e), level=logging.WARNING)
            await self._say(self.persona.refusal_line, spoken, t0, gate_open)
            self.history.append(Message("assistant", self.persona.refusal_line))
            self.hangup_after_playback = True
        except Exception as e:
            worker.cancel()
            gate_open.set()
            log.exception("[%s] response failed", self.tag)
            self.event("error", repr(e), level=logging.ERROR)
            await self._say("Sorry, can you hang on one second?", spoken, t0, gate_open)
        finally:
            self._set_thinking(False)

    # -------------------------------------------------------------- actions
    def _act(self, action: Action) -> None:
        """The persona ended its message with an action token. Hang-ups, holds and transfers all
        wait for the current audio to finish playing (see _player)."""
        if action.kind == "hangup":
            self.event("call", f"{self.persona.name} chose to hang up")
            self.hangup_after_playback = True
        elif action.kind == "hold":
            self.after_playback = self._hold
        elif action.kind == "transfer":
            target = self.scenario.personas.get(action.target)
            if target is None or action.target not in self.persona.transfers:
                self.event("error", f"{self.persona.name} tried to transfer to unknown persona {action.target!r}",
                           level=logging.WARNING)
                return
            self.after_playback = lambda: self._transfer(target, action.note)

    async def _hold(self) -> None:
        """[HOLD]: hold music while the persona 'steps away', then they come back and speak again."""
        self.event("hold", f"{self.persona.name} put the caller on hold", who=self.persona.name)
        self.busy = True
        rate = self.session.sample_rate
        self._enqueue(await asyncio.to_thread(self.comps.hold_frames, self.scenario, rate))
        self.out.append(self._end_busy)
        self.history.append(Message("user", HOLD_RETURN_NOTE))
        # The reply is generated while the music plays and queues up right behind it.
        self.response_task = asyncio.create_task(self._respond(continuation=True), name=f"respond-{self.tag}")

    async def _transfer(self, target: Persona, note: str) -> None:
        """[TRANSFER]: tone + hold music, then the colleague picks up in their own voice (fresh LLM
        history with the warm handoff note), or their voicemail plays and the call ends."""
        sc = self.scenario
        src = self.persona
        self.transfers += 1
        self.busy = True
        rate = self.session.sample_rate
        self._enqueue(await asyncio.to_thread(self.comps.hold_frames, sc, rate))
        if target.out:
            self.event("voicemail", target.voicemail, who=target.name,
                       note=f"{src.name} transferred the caller to {target.name}: {note}")
            self.turns.append(Turn("agent", f"(transfers the caller to {target.name}'s voicemail) {target.voicemail}"))
            self._enqueue(await asyncio.to_thread(self.comps.voicemail_frames, target, rate))
            self.hangup_after_playback = True
            return
        self.event("transfer", f"{src.name} -> {target.name}: {note or '(no handoff note)'}",
                   who=src.name, to=target.key, note=note)
        self.turns.append(Turn("agent", f"(transfers the caller to {target.name}, {target.role})"))
        self.persona = target
        self.voice = target.voice
        self.system = system_prompt(sc, target, handoff=(src, note))
        self.history = []
        self._provisional = None
        self._enqueue(await asyncio.to_thread(self.comps.greeting_frames, target.greeting, rate, target.voice))
        self.out.append(self._end_busy)
        self.event("persona", target.greeting, who=target.name)
        self.turns.append(Turn("agent", target.greeting))

    def _end_busy(self) -> None:
        self.busy = False

    def _strip_tags(self, text: str) -> str:
        """Remove complete action tokens and the hidden flag tag before text reaches the chunker."""
        return ACTION_RE.sub(" ", text).replace(f"[{self.scenario.flag}]", " ")

    def _set_thinking(self, on: bool) -> None:
        if on == self.thinking:
            return
        self.thinking = on
        if on:
            self.thinking_since = self.loop.time()
            self.filler.reset()
            self.out_event.set()  # wake the player so the filler starts now
        elif self.filler.frames:
            self.event("thinking", f"filler played for {self.loop.time() - self.thinking_since:.1f}s", level=logging.DEBUG)

    def _apply_verdict(self, v: Verdict, stage: str, gate: str, gate_open: asyncio.Event) -> None:
        self.event("monitor", f"{stage}: {v.summary()}" + (f" - {v.rationale}" if v.rationale else ""),
                   level=logging.INFO if v.action == "allow" else logging.WARNING,
                   stage=stage, risk=round(v.risk, 3), technique=v.technique or "", monitor_action=v.action,
                   rationale=v.rationale or "", latency_ms=v.latency_ms, error=v.error or "")
        if gate == "observe":
            return
        if v.action == "terminate":
            raise CallTerminated(v)
        if stage == "caller" and gate == "caller":
            gate_open.set()

    async def _terminate(self, v: Verdict, suppressed: str = "") -> None:
        self.terminated = True
        self._set_thinking(False)
        self.out.clear()
        m = self.scenario.monitor
        reason = m.reason_for(v)
        self.event("TERMINATED", f"risk={v.risk:.2f} technique={v.technique or '-'} {v.rationale or ''}".strip(),
                   level=logging.WARNING, suppressed_reply=suppressed, reason=reason)
        rate = self.session.sample_rate
        # Fixed line from the WAV on disk, then the reason + farewell in the system voice.
        frames = await asyncio.to_thread(self.comps.system_frames, m.termination_line, rate, m.termination_file)
        spoken = " ".join(t for t in (reason, m.termination_farewell) if t).strip()
        if spoken:
            frames = frames + await asyncio.to_thread(self.comps.system_frames, spoken, rate, None, False)
        self._enqueue(frames)
        self.hangup_after_playback = True

    async def _tts_worker(self, queue: asyncio.Queue, spoken: list[str], t0: float, gate_open: asyncio.Event,
                          hold: asyncio.Event | None = None) -> None:
        if not self.comps.tts_prefetch:
            while True:
                sent = await queue.get()
                if sent is None:
                    return
                await self._say(sent, spoken, t0, gate_open, hold)

        # Network TTS: start synthesising every sentence the moment the LLM finishes it, and
        # play the results in order. The seconds of round-trip latency then overlap with the
        # previous sentence's playback instead of adding a gap before each one.
        ready: asyncio.Queue = asyncio.Queue()

        async def feed() -> None:
            while True:
                sent = await queue.get()
                if sent is None:
                    ready.put_nowait(None)
                    return
                clean = self._speech_text(sent)
                if clean:
                    fut = self.loop.run_in_executor(self.comps.tts_pool, self.comps.tts.synthesize, clean, self.voice)
                    ready.put_nowait((clean, fut))

        feeder = asyncio.create_task(feed(), name=f"tts-feed-{self.tag}")
        try:
            while True:
                item = await ready.get()
                if item is None:
                    return
                clean, fut = item
                await self._say(clean, spoken, t0, gate_open, hold, audio_fut=fut)
        finally:
            feeder.cancel()

    def _speech_text(self, text: str) -> str:
        sc = self.scenario
        text = text.replace(f"[{sc.flag}]", " ")   # hidden log tag, never spoken
        if sc.flag in text:                        # literal flag -> spoken form
            text = text.replace(sc.flag, spell_for_speech(sc.flag))
        text = clean_for_speech(text)
        for written, spoken in sc.speech_substitutions.items():   # "pwn" -> "pone", TTS only
            text = re.sub(rf"\b{re.escape(written)}\b", spoken, text, flags=re.I)
        return text

    async def _say(self, text: str, spoken: list[str], t0: float, gate_open: asyncio.Event | None = None,
                   hold: asyncio.Event | None = None, audio_fut: asyncio.Future | None = None) -> None:
        """Speak one sentence. With `audio_fut` the text is already clean and its synthesis is in flight."""
        clean = text if audio_fut is not None else self._speech_text(text)
        if not clean:
            return
        t1 = time.monotonic()
        started = False

        async def begin() -> None:
            # Synthesis overlaps the monitor; playback waits for its verdict (and, for a
            # provisional reply, for the STT to confirm the caller really finished).
            nonlocal started
            if gate_open is not None:
                await gate_open.wait()
            if hold is not None:
                await hold.wait()
            if not spoken:
                self._first_audio_ms = round((time.monotonic() - t0) * 1000)
            spoken.append(clean)
            self._set_thinking(False)
            started = True

        tts = self.comps.tts
        if tts.streaming:
            # Chunks are enqueued as they arrive, so playback starts ~100 ms into synthesis.
            q: asyncio.Queue = asyncio.Queue()

            def produce() -> None:
                try:
                    for chunk in tts.synthesize_stream(clean, self.voice):
                        self.loop.call_soon_threadsafe(q.put_nowait, chunk)
                except Exception as e:  # noqa: BLE001
                    self.loop.call_soon_threadsafe(q.put_nowait, e)
                finally:
                    self.loop.call_soon_threadsafe(q.put_nowait, None)

            fut = self.loop.run_in_executor(self.comps.tts_pool, produce)
            rs = StreamResampler(tts.sample_rate, self.session.sample_rate)
            pending = b""
            frame_bytes = len(to_frames(b"\x00\x00", self.session.sample_rate)[0])
            try:
                while True:
                    chunk = await q.get()
                    if chunk is None:
                        break
                    if isinstance(chunk, Exception):
                        raise chunk
                    pcm = pending + float_to_pcm16(rs.process(chunk))
                    cut = len(pcm) - len(pcm) % frame_bytes
                    pcm, pending = pcm[:cut], pcm[cut:]
                    if not pcm:
                        continue
                    if not started:
                        await begin()
                    self._enqueue(to_frames(pcm, self.session.sample_rate))
                tail = pending + float_to_pcm16(rs.flush())
                if tail:
                    if not started:
                        await begin()
                    self._enqueue(to_frames(tail, self.session.sample_rate))
            finally:
                await asyncio.shield(fut)  # let the producer drain so the connection stays in sync
            if not started:
                return
        else:
            if audio_fut is None:
                audio_fut = self.loop.run_in_executor(self.comps.tts_pool, tts.synthesize, clean, self.voice)
            audio = await audio_fut
            audio = resample(audio, tts.sample_rate, self.session.sample_rate)
            await begin()
            self._enqueue(to_frames(float_to_pcm16(audio), self.session.sample_rate))
        if not self.flag_revealed and self.scenario.flag_revealed(" ".join(spoken)):
            # A spelled-out flag can span several chunks, so test the cumulative speech of this
            # reply. The marker fires only when the last frame before it has actually been sent;
            # a flush (barge-in, termination) drops it along with the audio.
            self.out.append(self._flag_heard)
        log.debug(
            "[%s] tts %dms for %d chars%s", self.tag, round((time.monotonic() - t1) * 1000), len(clean),
            f" (first audio {round((time.monotonic() - t0) * 1000)}ms after utterance)" if len(spoken) == 1 else "",
        )

    def _flag_heard(self) -> None:
        if not self.flag_revealed:
            self.flag_revealed = True
            self.event("FLAG", "*** flag spoken to the caller ***", level=logging.WARNING)

    def _enqueue(self, frames: list[bytes]) -> None:
        self.out.extend(frames)
        self.out_event.set()

    def _filler_frame(self) -> bytes | None:
        if not self.thinking or not self.filler.frames:
            return None
        delay = self.cfg.thinking_sound.get("delay_ms", 0) / 1000
        if self.loop.time() - self.thinking_since < delay:
            return b"\x00" * len(self.filler.frames[0])  # keep pacing, stay silent
        return self.filler.next_frame()

    async def _player(self) -> None:
        interval = 0.02
        next_t = self.loop.time()
        while True:
            frame = self.out.popleft() if self.out else self._filler_frame()
            while callable(frame):  # playback marker, not audio
                frame()
                frame = self.out.popleft() if self.out else self._filler_frame()
            if frame is None:
                if self.after_playback is not None:
                    cb, self.after_playback = self.after_playback, None
                    await cb()
                    next_t = self.loop.time()
                    continue
                if self.hangup_after_playback:
                    await asyncio.sleep(0.3)
                    self.event("call", "hanging up")
                    await self.session.hangup()
                    return
                self.out_event.clear()
                await self.out_event.wait()
                next_t = self.loop.time()
                continue
            now = self.loop.time()
            if next_t > now:
                await asyncio.sleep(next_t - now)
            elif now - next_t > 0.2:
                next_t = now  # we fell behind; resync instead of bursting
            await self.session.send(frame)
            next_t += interval

    # ---------------------------------------------------------------- output
    def _save(self) -> None:
        Path(self.cfg.calls_dir).mkdir(parents=True, exist_ok=True)
        name = f"{self.started_at:%Y%m%d-%H%M%S}_{self.tag}.json"
        path = Path(self.cfg.calls_dir) / name
        record = {
            "call_id": self.session.call_id,
            "remote": self.session.remote,   # AudioSocket peer (the Asterisk container), never the caller
            "scenario": self.scenario.name,
            "started_at": self.started_at.isoformat(timespec="seconds"),
            "duration_s": round(self.elapsed(), 1),
            "flag_revealed": self.flag_revealed,
            "terminated": self.terminated,
            "transfers": self.transfers,
            "monitor": {"backend": self.comps.monitor.monitor.name, "gate": self.comps.monitor_gate}
            if self.comps.monitor else None,
            "events": self.events,
            "history": [{"role": m.role, "content": m.content} for m in self.history],
        }
        path.write_text(json.dumps(record, indent=2))
        verdict = ("FLAG REVEALED" + (" (then terminated)" if self.terminated else "")) if self.flag_revealed \
            else ("TERMINATED by monitor, flag kept" if self.terminated else "flag kept")
        log.info("[%s] call ended after %.0fs: %s. transcript -> %s", self.tag, self.elapsed(), verdict, path)
