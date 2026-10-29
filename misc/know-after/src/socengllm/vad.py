"""Voice activity detection + utterance endpointing.

VAD backends return a speech probability for each 20 ms frame of 16 kHz
audio. The Endpointer turns that stream into events the pipeline acts on.
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np

from .audio import STT_RATE, rms

log = logging.getLogger(__name__)


class VAD(Protocol):
    def __call__(self, frame: np.ndarray) -> float: ...
    def reset(self) -> None: ...


class SileroVAD:
    """Silero VAD v5 via onnxruntime (no torch). ~1 ms per 32 ms window on CPU."""

    WINDOW = 512  # samples @ 16 kHz

    def __init__(self, model_path: str | Path):
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        opts.log_severity_level = 3
        self.sess = ort.InferenceSession(str(model_path), opts, providers=["CPUExecutionProvider"])
        names = {i.name for i in self.sess.get_inputs()}
        if not {"input", "state", "sr"} <= names:
            raise RuntimeError(f"Unexpected Silero model inputs {names}; expected the v5 model")
        self.reset()

    def reset(self) -> None:
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._buf = np.zeros(0, dtype=np.float32)
        self._last = 0.0

    def __call__(self, frame: np.ndarray) -> float:
        self._buf = np.concatenate([self._buf, frame])
        while self._buf.size >= self.WINDOW:
            chunk, self._buf = self._buf[: self.WINDOW], self._buf[self.WINDOW :]
            out, self._state = self.sess.run(
                None,
                {
                    "input": chunk[None, :],
                    "state": self._state,
                    "sr": np.array(STT_RATE, dtype=np.int64),
                },
            )
            self._last = float(out[0, 0])
        return self._last


class EnergyVAD:
    """Fallback: adaptive RMS threshold. Fine for clean audio, weak on phone noise."""

    def __init__(self, floor: float = 0.004, ratio: float = 3.5):
        self.floor = floor
        self.ratio = ratio
        self.reset()

    def reset(self) -> None:
        self._noise = self.floor

    def __call__(self, frame: np.ndarray) -> float:
        level = rms(frame)
        # Track the noise floor slowly upward, quickly downward.
        if level < self._noise:
            self._noise = 0.9 * self._noise + 0.1 * level
        else:
            self._noise = 0.995 * self._noise + 0.005 * level
        self._noise = max(self._noise, self.floor)
        return 1.0 if level > self._noise * self.ratio else 0.0


@dataclass
class EndpointEvent:
    kind: str  # "start" | "sustained" | "utterance"
    audio: np.ndarray | None = None
    duration_ms: int = 0


@dataclass
class EndpointerConfig:
    start_threshold: float = 0.6
    end_threshold: float = 0.35
    min_speech_ms: int = 200     # speech this long -> "start"
    barge_in_ms: int = 450       # speech this long while we talk -> "sustained"
    end_silence_ms: int = 650    # trailing silence that closes an utterance
    preroll_ms: int = 300        # audio kept from before speech onset
    max_utterance_ms: int = 25000
    frame_ms: int = 20


@dataclass
class Endpointer:
    vad: VAD
    cfg: EndpointerConfig = field(default_factory=EndpointerConfig)

    def __post_init__(self) -> None:
        self._preroll: deque[np.ndarray] = deque(maxlen=max(1, self.cfg.preroll_ms // self.cfg.frame_ms))
        self.reset()

    def reset(self) -> None:
        self.vad.reset()
        self._preroll.clear()
        self._speech: list[np.ndarray] = []
        self._speech_ms = 0
        self._silence_ms = 0
        self._started = False
        self._sustained = False
        self.last_prob = 0.0

    def feed(self, frame: np.ndarray) -> list[EndpointEvent]:
        c = self.cfg
        events: list[EndpointEvent] = []
        prob = self.vad(frame)
        self.last_prob = prob

        if not self._speech:
            # idle: wait for onset
            if prob >= c.start_threshold:
                self._speech = list(self._preroll) + [frame]
                self._speech_ms = c.frame_ms
                self._silence_ms = 0
            else:
                self._preroll.append(frame)
            return events

        self._speech.append(frame)
        if prob >= c.end_threshold:
            self._speech_ms += c.frame_ms
            self._silence_ms = 0
        else:
            self._silence_ms += c.frame_ms

        if not self._started and self._speech_ms >= c.min_speech_ms:
            self._started = True
            events.append(EndpointEvent("start"))
        if self._started and not self._sustained and self._speech_ms >= c.barge_in_ms:
            self._sustained = True
            events.append(EndpointEvent("sustained"))

        total_ms = len(self._speech) * c.frame_ms
        if self._silence_ms >= c.end_silence_ms or total_ms >= c.max_utterance_ms:
            if self._started:
                audio = np.concatenate(self._speech)
                events.append(EndpointEvent("utterance", audio, total_ms))
            # else: a blip shorter than min_speech_ms -> discard
            self._speech = []
            self._speech_ms = 0
            self._silence_ms = 0
            self._started = False
            self._sustained = False
            self._preroll.clear()
        return events
