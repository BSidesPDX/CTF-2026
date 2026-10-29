"""Build the swappable components from config. Add a backend = add a branch here."""
from __future__ import annotations

import logging
from pathlib import Path

from .config import Config
from .llm import LLM
from .monitor import Monitor, MonitorPolicy
from .pipeline import CallConfig, Components
from .scenario import Scenario
from .stt import STT, StreamingSTT
from .transport import Transport
from .tts import TTS
from .vad import Endpointer, EndpointerConfig, EnergyVAD, SileroVAD

log = logging.getLogger(__name__)


STREAMING_STT = ("deepgram_flux",)


def build_stt(cfg: Config) -> STT | StreamingSTT:
    s = cfg.section("stt")
    backend = s.pop("backend", "whisper_mlx")
    if backend == "deepgram_flux":
        from .stt.deepgram_flux import FluxSTT

        return FluxSTT(**s)
    if backend == "whisper_mlx":
        from .stt.whisper_mlx import WhisperMLX

        return WhisperMLX(**s)
    if backend == "parakeet":
        from .stt.parakeet import ParakeetMLX

        return ParakeetMLX(**s)
    raise SystemExit(f"unknown stt backend {backend!r} (parakeet | whisper_mlx | deepgram_flux)")


def build_llm(cfg: Config) -> LLM:
    s = cfg.section("llm")
    backend = s.pop("backend", "anthropic")
    if backend == "anthropic":
        from .llm.anthropic_llm import AnthropicLLM

        return AnthropicLLM(**s)
    if backend == "openai":
        from .llm.openai_llm import OpenAILLM

        return OpenAILLM(**s)
    if backend == "mock":
        from .llm.mock import MockLLM

        return MockLLM(**s)
    raise SystemExit(f"unknown llm backend {backend!r} (anthropic | openai | mock)")


def build_tts(cfg: Config, voice_override: str | None = None) -> TTS:
    s = cfg.section("tts")
    backend = s.pop("backend", "auto")
    if voice_override:
        s["voice"] = voice_override
    models_dir = Path(cfg.get("models_dir", "models"))
    if backend == "auto":
        backend = "kokoro" if (models_dir / "kokoro-v1.0.onnx").exists() else "macos_say"
        log.info("tts backend auto -> %s", backend)
    if backend == "kokoro":
        from .tts.kokoro import KokoroTTS

        return KokoroTTS(models_dir=models_dir, **s)
    if backend == "deepgram_aura":
        from .tts.deepgram_aura import AuraTTS

        return AuraTTS(**{k: v for k, v in s.items() if k in ("voice", "sample_rate", "voice_map", "url", "api_key_env")})
    if backend == "digitalocean":
        from .tts.digitalocean import DigitalOceanTTS

        keys = ("model", "voice", "voice_map", "stability", "similarity_boost", "style", "speed",
                "language_code", "instructions", "speech_url", "poll_ms", "timeout_s", "url", "api_key_env")
        return DigitalOceanTTS(**{k: v for k, v in s.items() if k in keys})
    if backend == "macos_say":
        from .tts.macos_say import MacSayTTS

        return MacSayTTS(**s)
    raise SystemExit(f"unknown tts backend {backend!r} (kokoro | macos_say | deepgram_aura | digitalocean | auto)")


def build_endpointer_factory(cfg: Config):
    s = cfg.section("vad")
    backend = s.pop("backend", "silero")
    ep_cfg = EndpointerConfig(**{k: v for k, v in s.items() if k in EndpointerConfig.__dataclass_fields__})
    models_dir = Path(cfg.get("models_dir", "models"))

    def make() -> Endpointer:
        if backend == "silero":
            vad = SileroVAD(models_dir / "silero_vad.onnx")
        elif backend == "energy":
            vad = EnergyVAD()
        else:
            raise SystemExit(f"unknown vad backend {backend!r} (silero | energy)")
        return Endpointer(vad, ep_cfg)

    if backend == "silero" and not (models_dir / "silero_vad.onnx").exists():
        raise SystemExit("models/silero_vad.onnx missing - run: uv run python scripts/download_models.py")
    make()  # fail fast
    return make


def build_transport(cfg: Config, override: str | None = None) -> Transport:
    s = cfg.section("transport")
    backend = override or s.pop("backend", "audiosocket")
    s.pop("backend", None)
    if backend == "audiosocket":
        from .transport.audiosocket import AudioSocketTransport

        return AudioSocketTransport(**s)
    if backend == "local":
        from .transport.local_audio import LocalAudioTransport

        return LocalAudioTransport(**{k: v for k, v in s.items() if k in ("sample_rate", "input_device", "output_device")})
    raise SystemExit(f"unknown transport {backend!r} (audiosocket | local)")


def build_monitor(cfg: Config, scenario: Scenario) -> MonitorPolicy | None:
    s = cfg.section("monitor")
    backend = s.pop("backend", "jev")
    gate = scenario.monitor.gate or s.get("gate", "reply")
    if gate not in ("reply", "lazy", "caller", "observe", "off"):
        raise SystemExit(f"unknown monitor gate {gate!r} (reply | lazy | caller | observe | off)")
    if not scenario.monitor.enabled or backend in (None, "off", False) or gate == "off":
        log.info("monitor: off")
        return None
    timeout = float(s.get("timeout_s", 4.0))
    monitor: Monitor
    if backend == "jev":
        from .monitor.jev import JevMonitor

        monitor = JevMonitor(**{k: v for k, v in s.items() if k != "llm"})
    elif backend == "llm_judge":
        from .monitor.llm_judge import LLMJudgeMonitor

        sub = Config({"llm": s.get("llm") or {}})
        monitor = LLMJudgeMonitor(build_llm(sub))
    elif backend == "mock":
        from .monitor.mock import MockMonitor

        monitor = MockMonitor(**{k: v for k, v in s.items() if k != "llm"})
    else:
        raise SystemExit(f"unknown monitor backend {backend!r} (jev | llm_judge | mock | off)")
    log.info("monitor: %s gate=%s terminate>=%.2f", monitor.name, gate, scenario.monitor.terminate_threshold)
    return MonitorPolicy(monitor, scenario.monitor, timeout, gate)


def build_components(cfg: Config, tts_voice: str | None = None, warm: bool = True,
                     scenario: Scenario | None = None) -> Components:
    from concurrent.futures import ThreadPoolExecutor

    # MLX models must be loaded, warmed and run on the same thread (see Components).
    stt_pool = ThreadPoolExecutor(1, thread_name_prefix="stt")
    # Cloud TTS backends are network-bound: several workers let the pipeline synthesise the
    # next sentences while one plays, and let concurrent calls proceed. Local models stay at 1.
    tts_workers = max(1, int(cfg.get_path("tts.workers", 1) or 1))
    tts_pool = ThreadPoolExecutor(tts_workers, thread_name_prefix="tts")
    any_stt = stt_pool.submit(build_stt, cfg).result()
    stt = any_stt if isinstance(any_stt, STT) else None
    turn_stt = any_stt if isinstance(any_stt, StreamingSTT) else None
    tts = tts_pool.submit(build_tts, cfg, tts_voice).result()
    llm = build_llm(cfg)
    make_ep = build_endpointer_factory(cfg)  # with a streaming STT only its barge_in_ms is used
    monitor = build_monitor(cfg, scenario) if scenario else None
    if tts_workers > 1 and tts.streaming:
        log.info("tts.workers=%d ignored: %s streams, so sentences are synthesised in order", tts_workers, tts.__class__.__name__)
    comps = Components(stt=stt, llm=llm, tts=tts, make_endpointer=make_ep, turn_stt=turn_stt,
                       stt_pool=stt_pool, tts_pool=tts_pool, tts_prefetch=tts_workers > 1 and not tts.streaming,
                       system_voice=cfg.get_path("tts.system_voice"),
                       monitor=monitor, monitor_gate=monitor.gate if monitor else "off")
    if warm:
        log.info("warming up STT and TTS (first run downloads models)...")
        comps.warmup()
    return comps


def build_call_config(cfg: Config) -> CallConfig:
    c = cfg.section("call")
    return CallConfig(
        barge_in=bool(c.get("barge_in", True)),
        max_seconds=int(c.get("max_seconds", 900)),
        greeting_delay_ms=int(c.get("greeting_delay_ms", 400)),
        calls_dir=str(cfg.get("calls_dir", "calls")),
        thinking_sound={**CallConfig().thinking_sound, **(c.get("thinking_sound") or {})},
    )
