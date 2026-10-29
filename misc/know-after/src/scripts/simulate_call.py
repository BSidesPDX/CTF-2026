"""Offline end-to-end test: play a WAV as the caller, record what the persona says.

    uv run python scripts/simulate_call.py caller.wav [--out persona.wav] [--set llm.backend=mock]

Runs the real pipeline (VAD -> STT -> LLM -> TTS) against a fake 8 kHz call
session, in real time, with no Asterisk and (with llm.backend=mock) no API key.
The caller audio is sent, then the session stays open for a while so the
persona can answer. Output is written as a WAV you can listen to.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from socengllm.audio import float_to_pcm16, pcm16_to_float, resample, to_frames  # noqa: E402
from socengllm.components import build_call_config, build_components  # noqa: E402
from socengllm.config import load_config  # noqa: E402
from socengllm.main import setup_logging  # noqa: E402
from socengllm.pipeline import CallPipeline  # noqa: E402
from socengllm.scenario import Scenario  # noqa: E402
from socengllm.transport.base import CallSession  # noqa: E402

RATE = 8000


class FakeSession(CallSession):
    sample_rate = RATE

    def __init__(self, caller_frames: list[bytes], lead_in_s: float, tail_s: float):
        self.call_id = "simulated-call"
        self.remote = "wav"
        self.frames = [b"\x00" * 320] * int(lead_in_s * 50) + caller_frames + [b"\x00" * 320] * int(tail_s * 50)
        self.i = 0
        self.t0 = None
        self.out: list[bytes] = []
        self.out_t: list[float] = []
        self.closed = False

    async def receive(self) -> bytes | None:
        if self.closed or self.i >= len(self.frames):
            return None
        if self.t0 is None:
            self.t0 = time.monotonic()
        due = self.t0 + self.i * 0.02
        delay = due - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)
        f = self.frames[self.i]
        self.i += 1
        return f

    async def send(self, frame: bytes) -> None:
        self.out.append(frame)
        self.out_t.append(time.monotonic() - (self.t0 or time.monotonic()))

    async def hangup(self) -> None:
        self.closed = True


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--out", default="persona_out.wav")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("-s", "--scenario")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--lead-in", type=float, default=3.0, help="seconds of silence before caller speaks")
    ap.add_argument("--tail", type=float, default=12.0, help="seconds to wait for the persona afterwards")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    setup_logging(args.verbose)

    cfg = load_config(args.config, args.set)
    scenario = Scenario.load(args.scenario or cfg["scenario"])
    audio, sr = sf.read(args.wav, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    frames = to_frames(float_to_pcm16(resample(audio, sr, RATE)), RATE)

    comps = build_components(cfg, tts_voice=scenario.tts_voice, scenario=scenario)
    if comps.monitor:
        await comps.monitor.warmup()
    if comps.turn_stt:
        await comps.turn_stt.warmup()
    call_cfg = build_call_config(cfg)
    session = FakeSession(frames, args.lead_in, args.tail)
    await CallPipeline(session, comps, scenario, call_cfg).run()

    # Timeline of what the caller heard: speech vs. thinking filler vs. nothing.
    filler = set(comps.thinking_frames(call_cfg, RATE))
    silent = b"\x00" * 320
    segs: list[list] = []
    for t, f in zip(session.out_t, session.out):
        system = {fr for frames in comps.system_audio.values() for fr in frames}
        kind = ("silence" if f == silent else "thinking" if f in filler else "system" if f in system else "speech")
        if segs and segs[-1][0] == kind and t - segs[-1][2] < (0.6 if kind == "thinking" else 0.1):
            segs[-1][2] = t
        else:
            segs.append([kind, t, t])
    for kind, a, b in segs:
        if kind != "silence" and b - a >= 0.1:
            logging.getLogger("sim").info("caller heard %-8s %6.2fs - %6.2fs (%.1fs)", kind, a, b + 0.02, b + 0.02 - a)

    if session.out:
        # Place each outbound frame at the wall-clock time it was sent so the
        # recording reflects real latency.
        total = int((session.out_t[-1] + 0.02) * RATE) + 320
        mix = np.zeros(total, dtype=np.float32)
        for t, f in zip(session.out_t, session.out):
            pos = int(t * RATE)
            pcm = pcm16_to_float(f)
            mix[pos : pos + pcm.size] = pcm[: max(0, total - pos)]
        sf.write(args.out, mix, RATE)
        logging.getLogger("sim").info("persona audio (%.1fs) -> %s", len(mix) / RATE, args.out)
    else:
        logging.getLogger("sim").warning("persona produced no audio")


if __name__ == "__main__":
    asyncio.run(main())
