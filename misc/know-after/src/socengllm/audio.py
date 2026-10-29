"""Small PCM helpers shared by every component.

Internal convention: audio is a 1-D float32 numpy array in [-1, 1].
The wire format (AudioSocket, sounddevice) is 16-bit signed little-endian
PCM, mono, in 20 ms frames.
"""
from __future__ import annotations

import numpy as np
import soxr

FRAME_MS = 20
STT_RATE = 16000  # every STT/VAD backend consumes 16 kHz


def pcm16_to_float(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0


def float_to_pcm16(audio: np.ndarray) -> bytes:
    return (np.clip(audio, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()


def resample(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate or audio.size == 0:
        return audio.astype(np.float32, copy=False)
    return soxr.resample(audio, src_rate, dst_rate, quality="HQ").astype(np.float32)


def samples_per_frame(rate: int, frame_ms: int = FRAME_MS) -> int:
    return rate * frame_ms // 1000


def to_frames(pcm: bytes, rate: int, frame_ms: int = FRAME_MS) -> list[bytes]:
    """Split PCM16 bytes into fixed 20 ms frames, zero-padding the tail."""
    n = samples_per_frame(rate, frame_ms) * 2
    frames = [pcm[i : i + n] for i in range(0, len(pcm), n)]
    if frames and len(frames[-1]) < n:
        frames[-1] = frames[-1] + b"\x00" * (n - len(frames[-1]))
    return frames


def rms(audio: np.ndarray) -> float:
    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))


class StreamResampler:
    """Continuous resampler for a stream of small frames (no per-frame edge artifacts)."""

    def __init__(self, src_rate: int, dst_rate: int):
        self.src_rate = src_rate
        self.dst_rate = dst_rate
        self._rs = None if src_rate == dst_rate else soxr.ResampleStream(src_rate, dst_rate, 1, dtype="float32", quality="HQ")

    def process(self, audio: np.ndarray, last: bool = False) -> np.ndarray:
        if self._rs is None:
            return audio.astype(np.float32, copy=False)
        return self._rs.resample_chunk(audio.astype(np.float32, copy=False), last=last)

    def flush(self) -> np.ndarray:
        """Drain the filter tail at the end of a stream."""
        return self.process(np.zeros(0, dtype=np.float32), last=True)
