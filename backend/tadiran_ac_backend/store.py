"""Local JSON store of user-named ("paired") devices, keyed by MAC.

Unnamed scan results are never persisted here -- giving a device a name
is the act of "pairing" it. See docs/04-architecture.md.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()

_DEFAULT_PATH = Path.home() / ".tadiran_ac_control" / "devices.json"


def _normalize_mac(mac: str) -> str:
    return mac.strip().lower().replace("-", "").replace(":", "")


class DeviceStore:
    """Thread-safe JSON-file-backed map of mac -> {name, ip, mid, last_seen}."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else _DEFAULT_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    def _read(self) -> dict[str, dict[str, Any]]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write(self, data: dict[str, dict[str, Any]]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    def list_all(self) -> list[dict[str, Any]]:
        with _LOCK:
            data = self._read()
        out = []
        for mac, entry in data.items():
            out.append({"mac": mac, **entry})
        out.sort(key=lambda e: e.get("name", "").lower())
        return out

    def get(self, mac: str) -> dict[str, Any] | None:
        mac = _normalize_mac(mac)
        with _LOCK:
            data = self._read()
        entry = data.get(mac)
        return {"mac": mac, **entry} if entry else None

    def upsert(
        self,
        mac: str,
        *,
        name: str | None = None,
        ip: str | None = None,
        mid: str | None = None,
        port: int = 7000,
    ) -> dict[str, Any]:
        mac = _normalize_mac(mac)
        with _LOCK:
            data = self._read()
            entry = data.get(mac, {})
            if name is not None:
                entry["name"] = name
            if ip is not None:
                entry["ip"] = ip
            if mid is not None:
                entry["mid"] = mid
            entry["port"] = port
            entry["last_seen"] = time.time()
            data[mac] = entry
            self._write(data)
        return {"mac": mac, **entry}

    def rename(self, mac: str, name: str) -> dict[str, Any] | None:
        mac = _normalize_mac(mac)
        with _LOCK:
            data = self._read()
            if mac not in data:
                return None
            data[mac]["name"] = name
            self._write(data)
            return {"mac": mac, **data[mac]}

    def remove(self, mac: str) -> bool:
        mac = _normalize_mac(mac)
        with _LOCK:
            data = self._read()
            if mac not in data:
                return False
            del data[mac]
            self._write(data)
            return True

    def update_ip(self, mac: str, ip: str) -> None:
        mac = _normalize_mac(mac)
        with _LOCK:
            data = self._read()
            if mac in data:
                data[mac]["ip"] = ip
                data[mac]["last_seen"] = time.time()
                self._write(data)
