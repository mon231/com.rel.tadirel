"""Thin wrapper around greeclimate for one AC unit: bind, read status,
apply changes. See docs/05-library-notes.md for why every call does a
fresh bind rather than trying to cache a bound connection across calls.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from greeclimate.device_factory import create_device
from greeclimate.deviceinfo import DeviceInfo
from greeclimate.discovery import Discovery

from . import protocol_props

POST_SEND_SETTLE_SECONDS = 1.0
BIND_TIMEOUT_SECONDS = 6
CONFIRM_POLL_INTERVAL_SECONDS = 1.2
CONFIRM_TIMEOUT_SECONDS = 7.0


def device_info_to_dict(info: DeviceInfo) -> dict[str, Any]:
    return {
        "ip": info.ip,
        "port": info.port,
        "mac": info.mac,
        "name": info.name,
        "mid": info.mid,
    }


async def probe_unicast(ip: str, port: int = 7000, timeout: float = 1.5) -> dict[str, Any] | None:
    """Single targeted scan probe at a known IP. Returns device info dict or None."""
    disc = Discovery(timeout=timeout)
    try:
        from ipaddress import IPv4Address

        devices = await disc.scan(wait_for=timeout, target_addresses=[IPv4Address(ip)])
    finally:
        disc.close()
    if not devices:
        return None
    return device_info_to_dict(devices[0])


async def _bind(ip: str, port: int, mac: str, mid: str | None) -> Any:
    info = DeviceInfo(ip=ip, port=port, mac=mac, name=mac, mid=mid)
    device = create_device(info, bind_timeout=BIND_TIMEOUT_SECONDS)
    await device.bind()
    return device


def _status_dict(device: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for spec in (*protocol_props.CONTROL_PROPS, *protocol_props.READONLY_PROPS):
        try:
            out[spec.key] = getattr(device, spec.key)
        except Exception:
            out[spec.key] = None
    return out


async def read_status(ip: str, mac: str, mid: str | None, port: int = 7000) -> dict[str, Any]:
    device = await _bind(ip, port, mac, mid)
    try:
        await device.update_state()
        await asyncio.sleep(POST_SEND_SETTLE_SECONDS)
        return _status_dict(device)
    finally:
        device.close()


def _value_matches(spec: protocol_props.PropSpec, actual: Any, requested: Any) -> bool:
    if actual is None:
        return False
    if spec.kind == "toggle":
        return bool(actual) == bool(requested)
    # enum / int_range: both sides are plain integers on the wire
    try:
        return int(actual) == int(requested)
    except (TypeError, ValueError):
        return actual == requested


async def apply_changes(
    ip: str, mac: str, mid: str | None, changes: dict[str, Any], port: int = 7000
) -> dict[str, Any]:
    """changes: {prop_key: new_value}. Sends the command, then polls the
    unit's real status until every changed property reads back as
    requested (or CONFIRM_TIMEOUT_SECONDS elapses) -- the UI should reflect
    what the AC actually did, not just that a packet was sent. Returns
    {"status": {...}, "confirmed": bool}.
    """
    specs: dict[str, protocol_props.PropSpec] = {}
    for key in changes:
        spec = protocol_props.spec_for(key)
        if spec is None or spec not in protocol_props.CONTROL_PROPS:
            raise ValueError(f"Unknown or read-only property: {key}")
        specs[key] = spec

    device = await _bind(ip, port, mac, mid)
    try:
        for key, value in changes.items():
            setattr(device, key, value)
        await device.push_state_update()
        await asyncio.sleep(POST_SEND_SETTLE_SECONDS)

        deadline = time.monotonic() + CONFIRM_TIMEOUT_SECONDS
        status = _status_dict(device)
        while True:
            await device.update_state()
            await asyncio.sleep(POST_SEND_SETTLE_SECONDS)
            status = _status_dict(device)
            if all(_value_matches(specs[k], status.get(k), v) for k, v in changes.items()):
                return {"status": status, "confirmed": True}
            if time.monotonic() >= deadline:
                return {"status": status, "confirmed": False}
            await asyncio.sleep(CONFIRM_POLL_INTERVAL_SECONDS)
    finally:
        device.close()
