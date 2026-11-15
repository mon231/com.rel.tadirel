"""HTTPS server: serves the shared web UI (./web) and exposes api.py as
`POST /api/<function>` with body `{"args": [...]}`, answering
`{"ok": true, "value": ...}` or `{"ok": false, "error": "..."}`.

Stdlib only, so it runs unchanged on desktop and under Chaquopy. The TLS
certificate is hard-coded (./certs, self-signed, valid until 2126): every
install presents the same cert, so a client can pin it once.
"""

from __future__ import annotations

import json
import mimetypes
import os
import ssl
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources

from . import api

DEFAULT_PORT = 18972
MAX_BODY = 1_000_000

_server: ThreadingHTTPServer | None = None
_lock = threading.Lock()


def _web_file(path: str) -> bytes | None:
    parts = [p for p in path.split("/") if p]
    if any(p in (".", "..") or "\\" in p for p in parts):
        return None
    node = resources.files(__package__).joinpath("web", *(parts or ["index.html"]))
    try:
        return node.read_bytes() if node.is_file() else None
    except OSError:
        return None


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # keep the service quiet
        pass

    def _send(self, status: int, body: bytes, ctype: str):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/eel.js":  # desktop-only shim the shared index.html asks for
            return self._send(200, b"", "application/javascript")
        data = _web_file(path)
        if data is None:
            return self._send(404, b"not found", "text/plain")
        ctype = mimetypes.guess_type(path if path != "/" else "x.html")[0] or "application/octet-stream"
        self._send(200, data, ctype)

    def do_POST(self):
        if not self.path.startswith("/api/"):
            return self._send(404, b"not found", "text/plain")
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise ValueError("body too large")
            body = json.loads(self.rfile.read(length) or b"{}")
            value = api.dispatch(self.path[len("/api/"):], body.get("args"))
            out = {"ok": True, "value": value}
        except Exception as exc:  # noqa: BLE001 - reported to the client
            out = {"ok": False, "error": str(exc)}
        self._send(200, json.dumps(out).encode(), "application/json")


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    # load_cert_chain needs real files; the package may live inside an APK.
    with tempfile.TemporaryDirectory() as tmp:
        for name in ("server.crt", "server.key"):
            data = resources.files(__package__).joinpath("certs", name).read_bytes()
            with open(os.path.join(tmp, name), "wb") as f:
                f.write(data)
        ctx.load_cert_chain(os.path.join(tmp, "server.crt"), os.path.join(tmp, "server.key"))
    return ctx


def start_server(host: str = "0.0.0.0", port: int = DEFAULT_PORT) -> int:
    """Start (idempotent) and return the bound port. port=0 picks a free one."""
    global _server
    with _lock:
        if _server is not None:
            return _server.server_address[1]
        srv = ThreadingHTTPServer((host, port), _Handler)
        srv.daemon_threads = True
        srv.allow_reuse_address = True
        srv.socket = _ssl_context().wrap_socket(srv.socket, server_side=True)
        threading.Thread(target=srv.serve_forever, name="ac-https", daemon=True).start()
        _server = srv
        return srv.server_address[1]


def stop_server() -> None:
    global _server
    with _lock:
        if _server is not None:
            _server.shutdown()
            _server.server_close()
            _server = None


def server_port() -> int | None:
    return _server.server_address[1] if _server else None
