"""Android-only glue: wraps tadiran_ac_backend.api so Kotlin only ever has
to deal with JSON strings (Chaquopy's PyObject introspection from Kotlin is
clunky; everyone's happier passing JSON). The shared backend package itself
stays platform-agnostic -- this file is the only Android-specific code on
the Python side, deliberately kept out of backend/.
"""

import json

from tadiran_ac_backend import api


def _ok(value):
    return json.dumps({"ok": True, "value": value})


def _err(exc: Exception):
    return json.dumps({"ok": False, "error": str(exc)})


def start_scan():
    try:
        return _ok(api.start_scan())
    except Exception as exc:  # noqa: BLE001 - surfaced to Kotlin as JSON
        return _err(exc)


def poll_scan(scan_id):
    try:
        return _ok(api.poll_scan(scan_id))
    except Exception as exc:
        return _err(exc)


def list_known_devices():
    try:
        return _ok(api.list_known_devices())
    except Exception as exc:
        return _err(exc)


def set_device_name(mac, ip, mid, name):
    try:
        return _ok(api.set_device_name(mac, ip, mid, name))
    except Exception as exc:
        return _err(exc)


def rename_device(mac, new_name):
    try:
        return _ok(api.rename_device(mac, new_name))
    except Exception as exc:
        return _err(exc)


def remove_device(mac):
    try:
        return _ok(api.remove_device(mac))
    except Exception as exc:
        return _err(exc)


def get_status(mac):
    try:
        return _ok(api.get_status(mac))
    except Exception as exc:
        return _err(exc)


def send_command(mac, changes_json):
    try:
        changes = json.loads(changes_json)
        return _ok(api.send_command(mac, changes))
    except Exception as exc:
        return _err(exc)


def capabilities():
    try:
        return _ok(api.capabilities())
    except Exception as exc:
        return _err(exc)
