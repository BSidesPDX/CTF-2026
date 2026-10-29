"""Poke Deepgram Flux (streaming STT with turn detection) and Aura-2 (streaming TTS).

    uv run python scripts/deepgram_probe.py flux  some_caller.wav   [--eager 0.6]
    uv run python scripts/deepgram_probe.py aura  "Hi there, this is Dana!" [--voice aura-2-luna-en]

flux: streams the WAV in real time (80 ms chunks) and prints every TurnInfo event with the
      wall-clock offset, so you can see how long after speech ends EndOfTurn arrives.
aura: opens the speak WebSocket, sends one sentence, and prints time to first audio byte and
      total time; writes aura_out.wav next to the input.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import soxr
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv()

KEY = os.environ.get("DEEPGRAM_API_KEY")
if not KEY:
    sys.exit("DEEPGRAM_API_KEY not set")


async def flux(path: str, rate: int, eot: float, eager: float | None, timeout_ms: int) -> None:
    import websockets

    audio, sr = sf.read(path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != rate:
        audio = soxr.resample(audio, sr, rate, quality="HQ")
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
    chunk = rate * 2 * 80 // 1000  # 80 ms
    url = (f"wss://api.deepgram.com/v2/listen?model=flux-general-en&encoding=linear16&sample_rate={rate}"
           f"&eot_threshold={eot}&eot_timeout_ms={timeout_ms}")
    if eager is not None:
        url += f"&eager_eot_threshold={eager}"
    t_conn = time.monotonic()
    async with websockets.connect(url, additional_headers={"Authorization": f"Token {KEY}"}) as ws:
        print(f"connected in {(time.monotonic() - t_conn) * 1000:.0f} ms")
        t0 = time.monotonic()

        async def sender() -> None:
            for i in range(0, len(pcm), chunk):
                await ws.send(pcm[i:i + chunk])
                target = t0 + (i + chunk) / (rate * 2)
                await asyncio.sleep(max(0.0, target - time.monotonic()))
            # trailing silence so the final turn closes
            for _ in range(int(2.5 * 1000 / 80)):
                await ws.send(b"\x00" * chunk)
                await asyncio.sleep(0.08)
            await ws.send(json.dumps({"type": "CloseStream"}))

        send_task = asyncio.create_task(sender())
        try:
            async for msg in ws:
                t = time.monotonic() - t0
                if isinstance(msg, bytes):
                    continue
                d = json.loads(msg)
                if d.get("type") == "TurnInfo":
                    print(f"{t:6.2f}s  {d['event']:<14} turn={d['turn_index']} "
                          f"win={d['audio_window_start']}-{d['audio_window_end']} "
                          f"eot={d['end_of_turn_confidence']} {d.get('trigger', '')}  {d['transcript']!r}")
                else:
                    print(f"{t:6.2f}s  {d}")
        finally:
            send_task.cancel()
    print(f"audio length {len(pcm) / (rate * 2):.2f}s")


def aura(text: str, voice: str, rate: int, out: str) -> None:
    from websockets.sync.client import connect

    url = f"wss://api.deepgram.com/v1/speak?model={voice}&encoding=linear16&sample_rate={rate}"
    t_conn = time.monotonic()
    with connect(url, additional_headers={"Authorization": f"Token {KEY}"}) as ws:
        print(f"connected in {(time.monotonic() - t_conn) * 1000:.0f} ms")
        for rep in range(2):  # second run shows the warm-connection latency
            t0 = time.monotonic()
            ws.send(json.dumps({"type": "Speak", "text": text}))
            ws.send(json.dumps({"type": "Flush"}))
            buf = bytearray()
            first = None
            while True:
                msg = ws.recv()
                if isinstance(msg, bytes):
                    if first is None:
                        first = time.monotonic()
                    buf.extend(msg)
                    continue
                d = json.loads(msg)
                if d.get("type") == "Flushed":
                    break
                if d.get("type") in ("Warning", "Error"):
                    print("  ", d)
            total = time.monotonic() - t0
            secs = len(buf) / (rate * 2)
            print(f"run {rep + 1}: first audio {((first or t0) - t0) * 1000:.0f} ms, "
                  f"all audio {total * 1000:.0f} ms, {secs:.2f}s of speech (RTF {total / max(secs, 1e-6):.2f})")
        ws.send(json.dumps({"type": "Close"}))
    pcm = np.frombuffer(bytes(buf), dtype="<i2").astype(np.float32) / 32768
    sf.write(out, pcm, rate)
    print("wrote", out)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("flux")
    f.add_argument("wav")
    f.add_argument("--rate", type=int, default=8000)
    f.add_argument("--eot", type=float, default=0.7)
    f.add_argument("--eager", type=float, default=None)
    f.add_argument("--timeout-ms", type=int, default=3000)
    a = sub.add_parser("aura")
    a.add_argument("text")
    a.add_argument("--voice", default="aura-2-luna-en")
    a.add_argument("--rate", type=int, default=24000)
    a.add_argument("--out", default="aura_out.wav")
    args = ap.parse_args()
    if args.cmd == "flux":
        asyncio.run(flux(args.wav, args.rate, args.eot, args.eager, args.timeout_ms))
    else:
        aura(args.text, args.voice, args.rate, args.out)


if __name__ == "__main__":
    main()
