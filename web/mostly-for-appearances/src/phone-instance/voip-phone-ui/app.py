import atexit
import os
import random
import signal
import socket
import subprocess
import time
from dataclasses import dataclass

from flask import Flask, flash, redirect, render_template, send_file, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

CAPTURE_DIR = os.environ.get("CAPTURE_DIR", "/app/captures")
TCPDUMP_BIN = os.environ.get("TCPDUMP_BIN", "tcpdump")
TCPDUMP_INTERFACE = os.environ.get("TCPDUMP_INTERFACE", "any")
ANSWERER_HOST = os.environ.get("ANSWERER_HOST", "employee-answerer")
CAPTURE_LOG = os.environ.get("CAPTURE_LOG", "/tmp/voip-phone-tcpdump.log")


@dataclass
class CaptureState:
    process: subprocess.Popen | None = None
    pcap_path: str | None = None
    started_at: float | None = None
    last_capture_path: str | None = None
    last_filter: str | None = None
    last_error: str | None = None
    log_file: object | None = None


STATE = CaptureState()


def _resolve_target(hostname: str) -> str:
    try:
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        return hostname


def _build_filter() -> str:
    # Only SIP, RTCP, RTP
    return "port 5060 or port 5061 or udp portrange 10000-20000"


def _ensure_dirs() -> None:
    os.makedirs(CAPTURE_DIR, exist_ok=True)


def _capture_running() -> bool:
    if STATE.process is None:
        return False
    if STATE.process.poll() is None:
        return True
    _cleanup_process(unexpected=True)
    return False


def _cleanup_process(unexpected: bool = False) -> None:
    if STATE.log_file:
        try:
            STATE.log_file.close()
        except Exception:
            pass
        STATE.log_file = None

    if unexpected and STATE.pcap_path and os.path.exists(STATE.pcap_path):
        STATE.last_capture_path = STATE.pcap_path
    if unexpected:
        STATE.last_error = "Capture process stopped unexpectedly."
    STATE.process = None
    STATE.pcap_path = None
    STATE.started_at = None


def _start_capture() -> bool:
    if _capture_running():
        STATE.last_error = "Capture already running."
        return False

    _ensure_dirs()
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    pcap_path = os.path.join(CAPTURE_DIR, f"cisco-voip-capture-{timestamp}.pcap")
    capture_filter = _build_filter()

    cmd = [
        TCPDUMP_BIN,
        "-i",
        TCPDUMP_INTERFACE,
        "-n",
        "-w",
        pcap_path,
    ] + capture_filter.split()

    log_file = open(CAPTURE_LOG, "ab")
    try:
        process = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
        )
    except FileNotFoundError:
        log_file.close()
        STATE.last_error = "tcpdump is not available."
        return False
    except Exception as exc:
        log_file.close()
        STATE.last_error = f"Failed to start capture: {exc}"
        return False

    STATE.process = process
    STATE.pcap_path = pcap_path
    STATE.started_at = time.time()
    STATE.last_capture_path = None
    STATE.last_filter = capture_filter
    STATE.last_error = None
    STATE.log_file = log_file
    return True


def _stop_capture() -> bool:
    if not _capture_running():
        if STATE.last_error is None:
            STATE.last_error = "No capture is currently running."
        return False

    process = STATE.process
    try:
        os.killpg(process.pid, signal.SIGINT)
    except ProcessLookupError:
        pass

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()

    if STATE.pcap_path and os.path.exists(STATE.pcap_path):
        STATE.last_capture_path = STATE.pcap_path

    _cleanup_process()
    STATE.last_error = None
    return True


def _format_duration(started_at: float | None) -> str | None:
    if not started_at:
        return None
    duration = int(time.time() - started_at)
    minutes, seconds = divmod(duration, 60)
    return f"{minutes:02d}:{seconds:02d}"


def _pcap_size(path: str | None) -> int | None:
    if not path or not os.path.exists(path):
        return None
    return os.path.getsize(path)


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", os.urandom(32).hex())
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    _ensure_dirs()

    @app.route("/")
    def index():
        return render_template(
            "index.html",
            page_title="Device Information",
            active_nav="device",
            extension=os.environ.get("VOIP_EXTENSION", "Unknown"),
        )

    @app.route("/network-configuration")
    def network_config():
        return render_template(
            "network_config.html",
            page_title="Network Configuration",
            active_nav="netconfig",
        )

    @app.route("/network-statistics")
    def network_stats():
        return render_template(
            "network_stats.html",
            page_title="Network Statistics",
            active_nav="netstats",
            rx_packets=random.randint(80000, 120000),
            tx_packets=random.randint(60000, 100000),
            calls_completed=random.randint(3, 18),
            avg_jitter=f"{random.uniform(1.0, 5.0):.1f}",
            packet_loss=f"{random.uniform(0.0, 0.5):.2f}",
        )

    @app.route("/device-logs")
    def device_logs():
        logs = [
            "[INFO ] Phone registered with Call Manager at 10.0.50.5",
            "[INFO ] DHCP lease renewed: 10.0.50.22 (86400s)",
            "[INFO ] NTP sync OK: offset +0.012s",
            "[WARN ] Missed keepalive from CM; retrying...",
            "[INFO ] Keepalive restored",
            "[INFO ] Firmware: CP7912080004SIP060817A.sbin",
            "[INFO ] Boot complete. Extension "
            + os.environ.get("VOIP_EXTENSION", "Unknown")
            + " active.",
        ]
        return render_template(
            "device_logs.html",
            page_title="Device Logs",
            active_nav="logs",
            logs=logs,
        )

    @app.get("/packet-capture")
    def packet_capture():
        running = _capture_running()
        duration = _format_duration(STATE.started_at) if running else None
        pcap_size = _pcap_size(STATE.last_capture_path)
        last_error = STATE.last_error
        STATE.last_error = None
        return render_template(
            "packet_capture.html",
            page_title="Packet Capture",
            active_nav="packet",
            capture_running=running,
            capture_duration=duration,
            capture_filter=STATE.last_filter,
            pcap_ready=bool(STATE.last_capture_path and pcap_size is not None),
            pcap_size=pcap_size,
            last_error=last_error,
        )

    @app.post("/capture/start")
    def start_capture():
        if _start_capture():
            flash("Capture started.", "ok")
        else:
            flash(STATE.last_error or "Failed to start capture.", "error")
        return redirect(url_for("packet_capture"))

    @app.post("/capture/stop")
    def stop_capture():
        if _stop_capture():
            flash("Capture stopped.", "ok")
        else:
            flash(STATE.last_error or "Failed to stop capture.", "error")
        return redirect(url_for("packet_capture"))

    @app.get("/capture/download")
    def download_capture():
        if not STATE.last_capture_path:
            return "No capture available.", 404
        if not os.path.exists(STATE.last_capture_path):
            return "Capture file missing.", 404
        return send_file(
            STATE.last_capture_path,
            as_attachment=True,
            download_name=os.path.basename(STATE.last_capture_path),
        )

    return app


@atexit.register
def _shutdown_capture() -> None:
    if _capture_running():
        _stop_capture()


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "9010")))
