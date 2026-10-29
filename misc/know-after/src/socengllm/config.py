"""YAML config with dotted-key overrides from the CLI (e.g. --set llm.backend=mock)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

DEFAULTS: dict[str, Any] = {
    "models_dir": "models",
    "calls_dir": "calls",
    "scenario": "scenarios/helpdesk-naive.yaml",
    "transport": {"backend": "audiosocket", "host": "0.0.0.0", "port": 9092},
    "stt": {"backend": "parakeet", "model": "mlx-community/parakeet-tdt-0.6b-v2"},
    "llm": {"backend": "anthropic", "model": "claude-opus-5-5", "effort": "low", "max_tokens": 1500, "fallbacks": True},
    "tts": {"backend": "auto", "voice": None, "rate": 185, "speed": 1.0, "system_voice": "am_michael"},
    "monitor": {
        "backend": "jev", "model": "typesafe/jev-1.14", "gate": "reply", "timeout_s": 4.0,
        "llm": {"backend": "anthropic", "model": "claude-haiku-5-5", "effort": "low", "max_tokens": 300},
    },
    "vad": {"backend": "silero"},
    "call": {"barge_in": True, "max_seconds": 900, "greeting_delay_ms": 400},
}


class Config(dict):
    """dict with attribute-free dotted access: cfg.get_path('llm.model')."""

    def get_path(self, path: str, default: Any = None) -> Any:
        node: Any = self
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set_path(self, path: str, value: Any) -> None:
        parts = path.split(".")
        node: Any = self
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = _coerce(value)

    def section(self, name: str) -> dict[str, Any]:
        return dict(self.get(name) or {})


def _coerce(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    low = value.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "none", ""):
        return None
    for cast in (int, float):
        try:
            return cast(value)
        except ValueError:
            pass
    return value


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | Path | None, overrides: list[str] | None = None) -> Config:
    load_dotenv()  # ANTHROPIC_API_KEY / OPENAI_API_KEY from .env
    data: dict[str, Any] = {}
    if path and Path(path).exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    cfg = Config(_merge(DEFAULTS, data))
    for item in overrides or []:
        if "=" not in item:
            raise SystemExit(f"--set expects key=value, got {item!r}")
        k, v = item.split("=", 1)
        cfg.set_path(k.strip(), v.strip())
    return cfg
