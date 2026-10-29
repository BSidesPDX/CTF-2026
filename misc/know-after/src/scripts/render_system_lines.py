"""Render the system-voice WAVs (monitoring announcement, termination line) for a scenario.

    uv run python scripts/render_system_lines.py [-s scenarios/helpdesk-naive.yaml] [--force]

Writes the files named by the scenario's monitor.announcement_file / termination_file
(default sounds/monitored.wav and sounds/terminated.wav) using tts.system_voice, with the
chime baked in. Replace them with your own recordings any time; the app plays whatever is
on disk. Existing files are kept unless --force is given.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from socengllm.components import build_tts  # noqa: E402
from socengllm.config import load_config  # noqa: E402
from socengllm.pipeline import clean_for_speech  # noqa: E402
from socengllm.scenario import Scenario  # noqa: E402
from socengllm.sounds import chime  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--config", default="config.yaml")
    ap.add_argument("-s", "--scenario")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--force", action="store_true", help="overwrite existing files")
    args = ap.parse_args()
    cfg = load_config(args.config, args.set)
    sc = Scenario.load(args.scenario or cfg["scenario"])
    tts = build_tts(cfg)
    voice = cfg.get_path("tts.system_voice")
    jobs = [
        (sc.monitor.announcement_file or "sounds/monitored.wav", sc.monitor.announcement),
        (sc.monitor.termination_file or "sounds/terminated.wav", sc.monitor.termination_line),
    ]
    for path, text in jobs:
        if not text:
            continue
        out = Path(path)
        if out.exists() and not args.force:
            print(f"keep   {out} (exists; --force to re-render)")
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        speech = tts.synthesize(clean_for_speech(text), voice=voice)
        audio = np.concatenate([chime(tts.sample_rate), speech, np.zeros(tts.sample_rate // 3, np.float32)])
        sf.write(out, audio, tts.sample_rate)
        print(f"wrote  {out}  ({len(audio) / tts.sample_rate:.1f}s, voice={voice}): {text!r}")


if __name__ == "__main__":
    main()
