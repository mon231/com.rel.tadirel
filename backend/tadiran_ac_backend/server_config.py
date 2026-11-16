"""Persisted settings (listen address, port, password) for the HTTPS
server, plus start/restart/status. Deliberately NOT in api.PUBLIC_FUNCTIONS:
the password and bind address are only editable from the local app, never
over HTTP. Frontends call these directly (the Android "server" build's
settings screen does, via android_bridge).
"""

from __future__ import annotations

import ipaddress
import json
import threading
from pathlib import Path
from typing import Any

from . import webserver

DEFAULTS: dict[str, Any] = {"host": "0.0.0.0", "port": webserver.DEFAULT_PORT, "password": "admin"}
_PATH = Path.home() / ".tadiran_ac_control" / "server.json"
_lock = threading.Lock()
_last_error: str | None = None


def get_settings() -> dict[str, Any]:
    try:
        saved = json.loads(_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    return {**DEFAULTS, **{k: v for k, v in saved.items() if k in DEFAULTS}}


def validate(host: str, port: Any, password: str) -> dict[str, Any]:
    host = (host or "").strip()
    if host != "localhost":
        try:
            ipaddress.ip_address(host)
        except ValueError:
            raise ValueError(f"listen address must be an IP address (e.g. 0.0.0.0, 127.0.0.1): {host!r}")
    try:
        port = int(port)
    except (TypeError, ValueError):
        raise ValueError("port must be a number")
    if not 1 <= port <= 65535:
        raise ValueError("port must be 1-65535")
    if not password:
        raise ValueError("password must not be empty")
    return {"host": host, "port": port, "password": password}


def set_settings(host: str, port: Any, password: str) -> dict[str, Any]:
    """Validate, persist, and apply (restart the server if it is running)."""
    new = validate(host, port, password)
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(new), encoding="utf-8")
    if webserver.server_port() is not None:
        stop()
        start()
    return new


def start() -> dict[str, Any]:
    """Start (idempotent) with the saved settings. Bind errors are recorded
    in status() instead of raised so a service can keep retrying."""
    global _last_error
    with _lock:
        s = get_settings()
        try:
            webserver.start_server(s["host"], s["port"], s["password"])
            _last_error = None
        except Exception as exc:  # noqa: BLE001
            _last_error = str(exc)
    return status()


def stop() -> None:
    webserver.stop_server()


def status() -> dict[str, Any]:
    port = webserver.server_port()
    return {"running": port is not None, "port": port, "error": _last_error}
