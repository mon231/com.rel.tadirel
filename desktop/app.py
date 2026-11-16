"""Desktop "PC app": Eel wraps backend.api and opens a native app window
around backend/tadiran_ac_backend/web/index.html. This process IS the app -- no separate
server to run, no browser tab to manage.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import eel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from tadiran_ac_backend import api  # noqa: E402

WEB_DIR = str(Path(api.__file__).resolve().parent / "web")

eel.init(WEB_DIR)


@eel.expose
def start_scan():
    return api.start_scan()


@eel.expose
def poll_scan(scan_id: str):
    return api.poll_scan(scan_id)


@eel.expose
def list_known_devices():
    return api.list_known_devices()


@eel.expose
def set_device_name(mac: str, ip: str, mid, name: str):
    return api.set_device_name(mac, ip, mid, name)


@eel.expose
def rename_device(mac: str, new_name: str):
    return api.rename_device(mac, new_name)


@eel.expose
def remove_device(mac: str):
    return api.remove_device(mac)


@eel.expose
def get_status(mac: str):
    return api.get_status(mac)


@eel.expose
def send_command(mac: str, changes: dict):
    return api.send_command(mac, changes)


@eel.expose
def capabilities():
    return api.capabilities()


def main():
    import os

    if "--serve" in sys.argv:
        # headless: same HTTPS server the Android "server" build runs
        from tadiran_ac_backend import server_config

        print(server_config.start())
        threading.Event().wait()

    if os.environ.get("AC_CONTROL_NO_BROWSER"):
        # test/dev mode: just run the server, let something else connect to it
        eel.start("index.html", size=(960, 680), port=8642, mode=False, block=True)
        return
    # mode="chrome" opens a Chrome/Edge app window (no tabs/address bar);
    # Eel falls back to the default browser automatically if none is found.
    try:
        eel.start("index.html", size=(960, 680), port=8642, mode="chrome")
    except EnvironmentError:
        eel.start("index.html", size=(960, 680), port=8642, mode="default")


if __name__ == "__main__":
    main()
