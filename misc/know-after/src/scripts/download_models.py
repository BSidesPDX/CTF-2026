"""Fetch the local model files that are not auto-downloaded (Silero VAD, Kokoro TTS).

Whisper / Parakeet weights come from Hugging Face automatically on first use.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"

FILES = {
    "silero_vad.onnx": "https://github.com/snakers4/silero-vad/raw/v5.1.2/src/silero_vad/data/silero_vad.onnx",
    "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
    "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
}


def fetch(name: str, url: str) -> None:
    dest = MODELS / name
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  {name}: present ({dest.stat().st_size / 1e6:.1f} MB)")
        return
    print(f"  {name}: downloading ...", flush=True)
    tmp = dest.with_suffix(dest.suffix + ".part")

    def hook(blocks, block_size, total):
        if total > 0 and blocks % 200 == 0:
            print(f"    {blocks * block_size / 1e6:6.1f} / {total / 1e6:.1f} MB", end="\r", flush=True)

    urllib.request.urlretrieve(url, tmp, reporthook=hook)
    tmp.rename(dest)
    print(f"  {name}: done ({dest.stat().st_size / 1e6:.1f} MB)        ")


def main() -> None:
    MODELS.mkdir(exist_ok=True)
    only = set(sys.argv[1:])
    for name, url in FILES.items():
        if only and not any(o in name for o in only):
            continue
        fetch(name, url)


if __name__ == "__main__":
    main()
