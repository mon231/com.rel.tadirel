"""The ONLY surface the desktop (Eel) and Android (Chaquopy) frontends
call into. Every function here is plain synchronous Python taking/
returning JSON-serializable values (dicts/lists/str/int/bool/None) --
easy to expose through either Eel (`@eel.expose`) or Chaquopy (called
directly from Kotlin).
"""

from __future__ import annotations

import time
from typing import Any

from . import arp, device, protocol_props
from .loop_runner import run_sync, submit
from .scanner import ScanSession
from .store import DeviceStore

HEALTHCHECK_UNICAST_TIMEOUT = 1.5

_store = DeviceStore()
_active_scans: dict[str, ScanSession] = {}


# ---------------------------------------------------------------- scanning


def start_scan() -> dict[str, Any]:
    """Kick off a new subnet scan (5 probes over 12s). Returns {"scan_id": ...}."""
    session = ScanSession()
    _active_scans[session.id] = session
    submit(session.run())
    return {"scan_id": session.id}


def poll_scan(scan_id: str) -> dict[str, Any]:
    """Drain any new results since the last poll. Call this every ~300ms
    while a scan is running."""
    session = _active_scans.get(scan_id)
    if session is None:
        return {"done": True, "new": [], "error": "unknown scan_id"}

    new_raw = session.drain_new()
    new = [_merge_known_name(d) for d in new_raw]
    for d in new_raw:
        if _store.get(d["mac"]):
            _store.update_ip(d["mac"], d["ip"])

    result = {"done": session.done, "new": new, "error": session.error}
    if session.done:
        _active_scans.pop(scan_id, None)
    return result


def _merge_known_name(found: dict[str, Any]) -> dict[str, Any]:
    known = _store.get(found["mac"])
    return {**found, "name": known["name"] if known else None, "paired": bool(known)}


# ------------------------------------------------------------- known/paired


def list_known_devices() -> list[dict[str, Any]]:
    """Paired (named) devices only -- see docs/04-architecture.md. Each
    entry includes a liveness check: direct unicast, then ARP fallback.
    `reachable=False` means the UI should gray the row out of selection."""
    out = []
    for entry in _store.list_all():
        out.append(_healthcheck(entry))
    return out


def _healthcheck(entry: dict[str, Any]) -> dict[str, Any]:
    mac = entry["mac"]
    ip = entry.get("ip")
    mid = entry.get("mid")

    if ip:
        try:
            found = run_sync(device.probe_unicast(ip), timeout=HEALTHCHECK_UNICAST_TIMEOUT + 2)
        except Exception:
            found = None
        if found and found["mac"].lower() == mac.lower():
            return {**entry, "ip": ip, "reachable": True}

    resolved_ip = arp.lookup_ip(mac)
    if resolved_ip:
        _store.update_ip(mac, resolved_ip)
        return {**entry, "ip": resolved_ip, "reachable": True}

    return {**entry, "reachable": False}


def set_device_name(mac: str, ip: str, mid: str | None, name: str) -> dict[str, Any]:
    """Pair a name to a MAC. This is what promotes a scan result into the
    persisted known-devices list."""
    if not name or not name.strip():
        raise ValueError("name must not be empty")
    return _store.upsert(mac, name=name.strip(), ip=ip, mid=mid)


def rename_device(mac: str, new_name: str) -> dict[str, Any]:
    if not new_name or not new_name.strip():
        raise ValueError("name must not be empty")
    result = _store.rename(mac, new_name.strip())
    if result is None:
        raise ValueError(f"no paired device with mac {mac}")
    return result


def remove_device(mac: str) -> dict[str, Any]:
    removed = _store.remove(mac)
    return {"removed": removed}


# --------------------------------------------------------------- control


def get_status(mac: str) -> dict[str, Any]:
    entry = _store.get(mac)
    if entry is None or not entry.get("ip"):
        raise ValueError(f"no known IP for mac {mac}; run list_known_devices() first")
    status = run_sync(device.read_status(entry["ip"], mac, entry.get("mid")), timeout=15)
    return {"mac": mac, "ip": entry["ip"], "status": status}


def send_command(mac: str, changes: dict[str, Any]) -> dict[str, Any]:
    """Sends the command and waits for the AC's own status to confirm it
    took effect (see device.apply_changes). `confirmed=False` means the
    command was sent but the unit hadn't reported the new value back
    within the confirm timeout -- the returned status is still its latest
    real reading, just not yet matching what was requested."""
    entry = _store.get(mac)
    if entry is None or not entry.get("ip"):
        raise ValueError(f"no known IP for mac {mac}; run list_known_devices() first")
    result = run_sync(
        device.apply_changes(entry["ip"], mac, entry.get("mid"), changes), timeout=20
    )
    return {"mac": mac, "ip": entry["ip"], "status": result["status"], "confirmed": result["confirmed"]}


def capabilities() -> dict[str, Any]:
    return protocol_props.capabilities_payload()


# -------------------------------------------------------------- dispatch

PUBLIC_FUNCTIONS = (
    "start_scan",
    "poll_scan",
    "list_known_devices",
    "set_device_name",
    "rename_device",
    "remove_device",
    "get_status",
    "send_command",
    "capabilities",
)


def dispatch(name: str, args: list[Any] | None = None) -> Any:
    """Call a public api function by name. Used by every transport that
    can't bind functions directly (the HTTPS server today; anything
    JSON-RPC-shaped tomorrow). Only names in PUBLIC_FUNCTIONS are callable."""
    if name not in PUBLIC_FUNCTIONS:
        raise ValueError(f"unknown api function: {name}")
    return globals()[name](*(args or []))
