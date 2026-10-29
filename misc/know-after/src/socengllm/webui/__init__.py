"""Bare-bones local web UI for browsing call transcripts and monitor verdicts.

Reads the per-call JSON files written by CallPipeline._save() from calls_dir and
serves a single-page viewer. Standard library only; no new dependencies.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

log = logging.getLogger("webui")
STATIC = Path(__file__).parent
SAFE_NAME = re.compile(r"^[A-Za-z0-9_\-]+\.json$")

_SCORE_RE = re.compile(r"(score|attack|improper_disclosure|injection)=([0-9.]+)(?:/(\d+))?")


def _max_risk(events: list[dict]) -> float | None:
    risks = [e.get("risk") for e in events if e.get("kind") == "monitor" and isinstance(e.get("risk"), (int, float))]
    return max(risks) if risks else None


def _summary(path: Path) -> dict | None:
    try:
        d = json.loads(path.read_text())
    except Exception as e:  # noqa: BLE001
        log.warning("skipping %s: %r", path.name, e)
        return None
    events = d.get("events", [])
    turns = sum(1 for e in events if e.get("kind") == "caller")
    verdicts = [e for e in events if e.get("kind") == "monitor"]
    return {
        "file": path.name,
        "started_at": d.get("started_at"),
        "duration_s": d.get("duration_s"),
        "caller_number": d.get("caller_number") or "",
        "caller_name": d.get("caller_name") or "",
        "dialed_number": d.get("dialed_number") or "",
        "scenario": d.get("scenario"),
        "flag_revealed": bool(d.get("flag_revealed")),
        "terminated": bool(d.get("terminated")),
        "turns": turns,
        "verdicts": len(verdicts),
        "max_risk": _max_risk(events),
        "monitor": d.get("monitor") or {},
    }


def list_calls(calls_dir: Path) -> list[dict]:
    out = []
    for p in sorted(calls_dir.glob("*.json"), reverse=True):
        s = _summary(p)
        if s:
            out.append(s)
    return out


def _backfill(d: dict) -> dict:
    """Structured sub-scores for transcripts that only have them in the rationale text."""
    for e in d.get("events", []):
        if e.get("kind") in ("monitor", "TERMINATED") and "scores" not in e:
            scores = {}
            for key, val, denom in _SCORE_RE.findall(e.get("rationale") or e.get("text") or ""):
                scores[key] = float(val) / (float(denom) if denom else 1.0)
            if scores:
                e["scores"] = scores
            if e.get("kind") == "monitor" and "latency_ms" not in e:
                m = re.search(r"\b(\d+)ms\b", e.get("text") or "")
                if m:
                    e["latency_ms"] = int(m.group(1))
    return d


def load_call(calls_dir: Path, name: str) -> dict | None:
    if not SAFE_NAME.match(name):
        return None
    p = calls_dir / name
    if not p.is_file():
        return None
    d = _backfill(json.loads(p.read_text()))
    d["file"] = name
    return d


class Handler(BaseHTTPRequestHandler):
    calls_dir: Path = Path("calls")
    extra: dict = {}  # merged into every call payload (thresholds, persona name)
    chat = None       # webui.chat.ChatBackend, when the server was started with a config + scenario
    server_version = "socengllm-webui/0.2"

    def log_message(self, fmt, *args):  # quieter than the default
        log.debug("%s " + fmt, self.address_string(), *args)

    def _send(self, status: HTTPStatus, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send(status, json.dumps(obj).encode(), "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(HTTPStatus.OK, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/calls":
            self._json(list_calls(self.calls_dir))
        elif path.startswith("/api/chat/") and self.chat is not None:
            s = self.chat.get(unquote(path[len("/api/chat/"):]).strip("/"))
            if s is None:
                self._json({"error": "that conversation is over"}, HTTPStatus.NOT_FOUND)
            else:
                self._json({**self.extra, **_backfill(s.record())})
        elif path.startswith("/api/calls/"):
            d = load_call(self.calls_dir, unquote(path[len("/api/calls/"):]))
            if d is None:
                self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            else:
                self._json({**self.extra, **d})
        else:
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > 1_000_000:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if not path.startswith("/api/chat"):
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        if self.chat is None:
            self._json({"error": "test conversations need `socengllm web` started with a config and scenario"},
                       HTTPStatus.SERVICE_UNAVAILABLE)
            return
        body = self._body()
        try:
            if path == "/api/chat":
                rec = self.chat.start(monitor=bool(body.get("monitor", True)))
            else:
                parts = path[len("/api/chat/"):].strip("/").split("/")
                s = self.chat.get(parts[0])
                if s is None:
                    self._json({"error": "that conversation is over; start a new one"}, HTTPStatus.NOT_FOUND)
                    return
                if len(parts) > 1 and parts[1] == "end":
                    rec = self.chat.end(s)
                else:
                    text = str(body.get("text") or "").strip()
                    if not text:
                        self._json({"error": "empty message"}, HTTPStatus.BAD_REQUEST)
                        return
                    rec = self.chat.send(s, text)
        except Exception as e:  # noqa: BLE001
            log.exception("chat request failed")
            self._json({"error": repr(e)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        self._json({**self.extra, **_backfill(rec)})


def serve(calls_dir: str | Path, host: str = "127.0.0.1", port: int = 8090, extra: dict | None = None,
          chat=None) -> None:
    calls_dir = Path(calls_dir)
    calls_dir.mkdir(parents=True, exist_ok=True)
    handler = type("BoundHandler", (Handler,), {"calls_dir": calls_dir, "extra": dict(extra or {}), "chat": chat})
    httpd = ThreadingHTTPServer((host, port), handler)
    httpd.daemon_threads = True
    log.info("web UI on http://%s:%d  (calls from %s)", host, port, calls_dir.resolve())
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()


def serve_in_thread(calls_dir: str | Path, host: str = "127.0.0.1", port: int = 8090, extra: dict | None = None) -> threading.Thread:
    t = threading.Thread(target=serve, args=(calls_dir, host, port, extra), name="webui", daemon=True)
    t.start()
    return t
