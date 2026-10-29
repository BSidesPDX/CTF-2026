"""SocEngLLM command line.

  socengllm serve        AudioSocket server for Asterisk (production path)
  socengllm local        talk to the persona through the Mac mic/speakers
  socengllm chat         text-only conversation with the persona (no audio)
  socengllm say TEXT     TTS smoke test (plays through speakers, or --out file.wav)
  socengllm transcribe F STT smoke test on a wav file
  socengllm prompt       print the system prompt the persona will get
  socengllm web          browse transcripts, run test conversations
  socengllm bench        score the scenario's difficulty against bench/attacks.yaml
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from rich.logging import RichHandler

from .config import Config, load_config
from .scenario import Scenario, build_system_prompt

log = logging.getLogger("socengllm")


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        datefmt="%H:%M:%S",
        handlers=[RichHandler(show_path=False, rich_tracebacks=True, markup=False)],
    )
    # "httpx2": the Anthropic SDK logs its requests under that name (anthropic/_utils/_logs.py)
    for noisy in ("httpx", "httpx2", "httpcore", "anthropic", "openai", "urllib3", "huggingface_hub", "filelock"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def parse_args(argv: list[str]) -> argparse.Namespace:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-c", "--config", default="config.yaml", help="config file (default: config.yaml)")
    common.add_argument("-s", "--scenario", help="scenario yaml (overrides config)")
    common.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="override any config key, e.g. --set llm.backend=mock --set tts.backend=macos_say")
    common.add_argument("-v", "--verbose", action="store_true")

    p = argparse.ArgumentParser(prog="socengllm", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve", parents=[common], help="AudioSocket server for Asterisk")
    sub.add_parser("local", parents=[common], help="mic/speaker call")
    sub.add_parser("chat", parents=[common], help="text-only persona chat")
    sp = sub.add_parser("say", parents=[common], help="TTS test")
    sp.add_argument("text")
    sp.add_argument("--out", help="write wav instead of playing")
    tp = sub.add_parser("transcribe", parents=[common], help="STT test")
    tp.add_argument("file")
    pp = sub.add_parser("prompt", parents=[common], help="print system prompt")
    pp.add_argument("--redact", action="store_true", help="replace the flag with pdx{...} (publishable version)")
    wp = sub.add_parser("web", parents=[common], help="browse call transcripts and monitor verdicts in a browser")
    wp.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1; use 0.0.0.0 for Tailscale/LAN)")
    wp.add_argument("--port", type=int, default=8090)
    bp = sub.add_parser("bench", parents=[common], help="measure the scenario's difficulty (see socengllm/bench.py)")
    bp.add_argument("--label", help="name for this run, e.g. the prompt version (default: prompt fingerprint)")
    bp.add_argument("--trials", type=int, help="trials per attack (config bench.trials, default 3)")
    bp.add_argument("--max-turns", type=int, help="caller turns per adaptive trial (config bench.max_turns, default 8)")
    bp.add_argument("--concurrency", type=int, help="trials in flight at once (config bench.concurrency, default 4)")
    bp.add_argument("--only", help="comma-separated attack names")
    bp.add_argument("--attacks", help="attack library yaml (config bench.attacks, default bench/attacks.yaml)")
    bp.add_argument("--runs-dir", help="where runs are saved (config bench.runs_dir, default bench/runs)")
    bp.add_argument("--no-monitor", action="store_true", help="persona alone, no monitor: how naive is she by herself?")
    bp.add_argument("--transcripts", action="store_true", help="print every trial's transcript at the end")
    bp.add_argument("--list", action="store_true", help="table of all saved runs")
    return p.parse_args(argv)


def load(args: argparse.Namespace) -> tuple[Config, Scenario]:
    cfg = load_config(args.config, args.set)
    scenario_path = args.scenario or cfg.get("scenario")
    if not scenario_path or not Path(scenario_path).exists():
        raise SystemExit(f"scenario file not found: {scenario_path}")
    return cfg, Scenario.load(scenario_path)


async def run_calls(cfg: Config, scenario: Scenario, transport_override: str | None) -> None:
    from .components import build_call_config, build_components, build_transport
    from .pipeline import CallPipeline

    comps = build_components(cfg, tts_voice=scenario.tts_voice, scenario=scenario)
    if comps.monitor:
        await comps.monitor.warmup()
    if comps.turn_stt:
        await comps.turn_stt.warmup()
    call_cfg = build_call_config(cfg)
    transport = build_transport(cfg, transport_override)
    # Pre-render every fixed line (greetings, voicemails, system lines, hold music) for the
    # telephony rate so playback is instant.
    comps.prerender(scenario, 8000)
    people = ", ".join(f"{p.name}{' (voicemail)' if p.out else ''}{' [flag]' if p.knows_flag else ''}"
                       for p in scenario.personas.values())
    log.info("scenario '%s' loaded: starts with %s; people: %s", scenario.name, scenario.start_persona.name, people)

    async def handle(session):
        await CallPipeline(session, comps, scenario, call_cfg).run()

    await transport.run(handle)


async def chat(cfg: Config, scenario: Scenario) -> None:
    """Text-only run of the same persona + monitor logic (socengllm/convo.py), for tuning scenarios."""
    from .components import build_llm, build_monitor
    from .convo import Conversation

    llm = build_llm(cfg)
    monitor = build_monitor(cfg, scenario)
    if monitor:
        await monitor.warmup()
    c = Conversation(scenario, llm, monitor, "chat")
    c.start("terminal chat")
    shown = 0

    def show() -> None:
        nonlocal shown
        for e in c.events[shown:]:
            k = e["kind"]
            if k == "persona":
                print(f"[{e.get('who') or c.persona.name}] {e['text']}")
            elif k == "monitor":
                print(f"    (monitor {e['text']})")
            elif k in ("system", "voicemail", "transfer", "hold", "TERMINATED", "FLAG", "refusal", "error"):
                print(f"<< {k}: {e['text']} >>")
            elif k == "call" and shown:
                print(f"<< {e['text']} >>")
        shown = len(c.events)

    show()
    print("(type your lines; Ctrl-D to end)\n")
    while not c.ended:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        await c.turn(line)
        show()


def say(cfg: Config, scenario: Scenario, text: str, out: str | None) -> None:
    import time

    import soundfile as sf

    from .components import build_tts

    tts = build_tts(cfg, scenario.tts_voice)
    t0 = time.monotonic()
    audio = tts.synthesize(text)
    log.info("synthesized %.2fs of audio in %.0f ms", len(audio) / tts.sample_rate, (time.monotonic() - t0) * 1000)
    if out:
        sf.write(out, audio, tts.sample_rate)
        log.info("wrote %s", out)
    else:
        import sounddevice as sd

        sd.play(audio, tts.sample_rate)
        sd.wait()


def transcribe(cfg: Config, path: str) -> None:
    import time

    import soundfile as sf

    from .audio import STT_RATE, resample
    from .components import build_stt

    stt = build_stt(cfg)
    if not hasattr(stt, "transcribe"):
        raise SystemExit(f"stt backend {type(stt).__name__} is streaming-only; try scripts/deepgram_probe.py flux {path}")
    audio, sr = sf.read(path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    audio = resample(audio, sr, STT_RATE)
    stt.warmup()
    t0 = time.monotonic()
    text = stt.transcribe(audio)
    log.info("%.1fs of audio transcribed in %.0f ms", len(audio) / STT_RATE, (time.monotonic() - t0) * 1000)
    print(text)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    setup_logging(args.verbose)
    cfg, scenario = load(args)
    try:
        if args.cmd == "serve":
            asyncio.run(run_calls(cfg, scenario, "audiosocket"))
        elif args.cmd == "local":
            asyncio.run(run_calls(cfg, scenario, "local"))
        elif args.cmd == "chat":
            asyncio.run(chat(cfg, scenario))
        elif args.cmd == "say":
            say(cfg, scenario, args.text, args.out)
        elif args.cmd == "transcribe":
            transcribe(cfg, args.file)
        elif args.cmd == "web":
            from .webui import serve as serve_web
            from .webui.chat import ChatBackend
            m = scenario.monitor
            calls_dir = cfg.get("calls_dir", "calls")
            serve_web(calls_dir, args.host, args.port, extra={
                "thresholds": {"terminate": m.terminate_threshold},
                "persona_name": scenario.start_persona.first_name,
                "termination_line": m.termination_line,
                "termination_farewell": m.termination_farewell,
            }, chat=ChatBackend(cfg, scenario, calls_dir))
        elif args.cmd == "bench":
            from .bench import run_bench

            asyncio.run(run_bench(cfg, scenario, args))
        elif args.cmd == "prompt":
            for p in scenario.personas.values():
                if p.out:
                    continue
                text = build_system_prompt(scenario, p)
                if args.redact:
                    text = text.replace(scenario.flag, "pdx{...}")
                if len(scenario.personas) > 1:
                    print(f"{'=' * 30} {p.key}: {p.name} {'=' * 30}")
                print(text + "\n")
    except KeyboardInterrupt:
        log.info("bye")


if __name__ == "__main__":
    main()
