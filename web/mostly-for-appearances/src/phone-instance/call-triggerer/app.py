import io
import os
import time
import wave

import paramiko
import pyotp
from flask import Flask, jsonify

CODE_DIGITS = 6
WAV_SAMPLE_RATE = 8000
WAV_CHANNELS = 1
WAV_SAMPLE_WIDTH = 2
SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")

ASTERISK_SSH_HOST = os.environ.get("ASTERISK_SSH_HOST") or "asterisk"
ASTERISK_SSH_PORT = os.environ.get("ASTERISK_SSH_PORT") or "22"
ASTERISK_SSH_USER = os.environ.get("ASTERISK_SSH_USER") or "root"
ASTERISK_SSH_PASSWORD = os.environ.get("ASTERISK_SSH_PASSWORD") or "root"

TOTP_SECRET = os.environ.get("TOTP_SECRET")

if TOTP_SECRET is None:
    raise Exception("missing TOTP_SECRET var!")


def create_app() -> Flask:
    app = Flask(__name__)

    def _load_wav_bytes(path: str) -> bytes:
        with wave.open(path, "rb") as wav_file:
            if wav_file.getnchannels() != WAV_CHANNELS:
                raise ValueError(f"Unexpected channel count for {path}")
            if wav_file.getsampwidth() != WAV_SAMPLE_WIDTH:
                raise ValueError(f"Unexpected sample width for {path}")
            if wav_file.getframerate() != WAV_SAMPLE_RATE:
                raise ValueError(f"Unexpected sample rate for {path}")
            if wav_file.getcomptype() != "NONE":
                raise ValueError(f"Unexpected compression for {path}")
            return wav_file.readframes(wav_file.getnframes())

    def _build_notice_wav(code: str) -> bytes:
        voice_dir = os.path.join(SOUNDS_DIR, "ghostface")
        parts = [os.path.join(voice_dir, "intro.wav")]
        parts.extend(os.path.join(voice_dir, f"{digit}.wav") for digit in code)
        parts.append(os.path.join(voice_dir, "bye.wav"))

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_out:
            wav_out.setnchannels(WAV_CHANNELS)
            wav_out.setsampwidth(WAV_SAMPLE_WIDTH)
            wav_out.setframerate(WAV_SAMPLE_RATE)
            for path in parts:
                wav_out.writeframes(_load_wav_bytes(path))
        return buffer.getvalue()

    def _run_asterisk_command(command: str) -> None:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                ASTERISK_SSH_HOST,
                port=int(ASTERISK_SSH_PORT),
                username=ASTERISK_SSH_USER,
                password=ASTERISK_SSH_PASSWORD,
                timeout=5,
                allow_agent=False,
                look_for_keys=False,
            )
            _, stdout, stderr = client.exec_command(command, timeout=10)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                error_output = stderr.read().decode("utf-8", "replace").strip()
                raise RuntimeError(
                    f"asterisk command failed ({exit_status}): {error_output or 'unknown error'}"
                )
        finally:
            client.close()

    def _start_call_me() -> None:
        _run_asterisk_command(
            'asterisk -rx "channel originate PJSIP/1000 extension s@autocall"'
        )

    # Random unguessable string that has no meaning
    @app.route("/e3d110ed054ebfca0ccadb518641c7ad622f2add.wav", methods=["GET"])
    def notice_wav():
        token = pyotp.TOTP(TOTP_SECRET).now()

        try:
            wav_bytes = _build_notice_wav(token)
        except Exception:
            app.logger.exception("Failed to build notice WAV")
            return "Unable to generate audio.", 500

        return app.response_class(wav_bytes, mimetype="audio/wav")

    @app.route("/call", methods=["POST"])
    def two_factor_call():
        try:
            _start_call_me()
        except Exception as e:
            app.logger.exception(f"Failed to trigger call: {e}")
            return jsonify({"ok": False, "error": "call_failed"}), 500

        return jsonify({"ok": True})

    @app.route("/")
    def index():
        return jsonify({"hello": "world", "service": "call-triggerer"})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
