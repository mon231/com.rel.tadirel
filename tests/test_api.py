"""Offline tests for the api.py functions that don't need real network
I/O. The scan/status/command paths that actually talk to a Gree unit over
UDP were validated by hand against real hardware (see docs/02-lan-protocol.md)
rather than mocked here -- mocking greeclimate's asyncio internals would
test the mock, not the protocol.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import pytest  # noqa: E402

from tadiran_ac_backend import api, arp, device  # noqa: E402
from tadiran_ac_backend.store import DeviceStore  # noqa: E402

MAC = "7cb8e6212197"


@pytest.fixture(autouse=True)
def fresh_store(tmp_path, monkeypatch):
    store = DeviceStore(tmp_path / "devices.json")
    monkeypatch.setattr(api, "_store", store)
    return store


def test_set_device_name_requires_nonempty_name():
    with pytest.raises(ValueError):
        api.set_device_name(MAC, "10.0.0.2", "10001", "   ")


def test_set_device_name_then_rename_then_remove():
    created = api.set_device_name(MAC, "10.0.0.2", "10001", "Living Room")
    assert created["name"] == "Living Room"

    renamed = api.rename_device(MAC, "Living Room AC")
    assert renamed["name"] == "Living Room AC"

    assert api.remove_device(MAC) == {"removed": True}
    assert api.remove_device(MAC) == {"removed": False}


def test_rename_unknown_device_raises():
    with pytest.raises(ValueError):
        api.rename_device("aabbccddeeff", "x")


def test_healthcheck_reachable_via_direct_probe(monkeypatch):
    api.set_device_name(MAC, "10.0.0.2", "10001", "Living Room")

    async def fake_probe_unicast(ip, port=7000, timeout=1.5):
        assert ip == "10.0.0.2"
        return {"ip": ip, "port": 7000, "mac": MAC, "name": MAC, "mid": "10001"}

    monkeypatch.setattr(device, "probe_unicast", fake_probe_unicast)
    monkeypatch.setattr(api, "run_sync", lambda coro, timeout=None: _run(coro))

    devices = api.list_known_devices()
    assert devices[0]["reachable"] is True
    assert devices[0]["ip"] == "10.0.0.2"


def test_healthcheck_falls_back_to_arp_on_stale_ip(monkeypatch):
    api.set_device_name(MAC, "10.0.0.250", "10001", "Living Room")  # stale IP

    async def fake_probe_unicast(ip, port=7000, timeout=1.5):
        return None  # nobody answers at the stale IP

    monkeypatch.setattr(device, "probe_unicast", fake_probe_unicast)
    monkeypatch.setattr(api, "run_sync", lambda coro, timeout=None: _run(coro))
    monkeypatch.setattr(arp, "lookup_ip", lambda mac: "10.0.0.2")

    devices = api.list_known_devices()
    assert devices[0]["reachable"] is True
    assert devices[0]["ip"] == "10.0.0.2"  # corrected via ARP


def test_healthcheck_grays_out_when_arp_has_no_entry(monkeypatch):
    api.set_device_name(MAC, "10.0.0.250", "10001", "Living Room")

    async def fake_probe_unicast(ip, port=7000, timeout=1.5):
        return None

    monkeypatch.setattr(device, "probe_unicast", fake_probe_unicast)
    monkeypatch.setattr(api, "run_sync", lambda coro, timeout=None: _run(coro))
    monkeypatch.setattr(arp, "lookup_ip", lambda mac: None)

    devices = api.list_known_devices()
    assert devices[0]["reachable"] is False


def test_get_status_unknown_mac_raises():
    with pytest.raises(ValueError):
        api.get_status("aabbccddeeff")


def test_send_command_unknown_mac_raises():
    with pytest.raises(ValueError):
        api.send_command("aabbccddeeff", {"power": 1})


def _run(coro):
    import asyncio

    return asyncio.run(coro)
