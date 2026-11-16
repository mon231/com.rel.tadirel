import json
import socket

import pytest

from tadiran_ac_backend import server_config as sc, webserver


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(autouse=True)
def _tmp_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "_PATH", tmp_path / "server.json")
    yield
    sc.stop()


def test_defaults():
    assert sc.get_settings() == {"host": "0.0.0.0", "port": 18972, "password": "admin"}


def test_roundtrip_and_apply():
    p1, p2 = _free_port(), _free_port()
    out = sc.set_settings("127.0.0.1", p1, "pw2")
    assert sc.get_settings() == out == {"host": "127.0.0.1", "port": p1, "password": "pw2"}
    assert sc.start() == {"running": True, "port": p1, "error": None}
    sc.set_settings("127.0.0.1", p2, "pw3")  # running server restarts on the new port
    assert sc.status() == {"running": True, "port": p2, "error": None}


@pytest.mark.parametrize(
    "args",
    [("nope", 1, "x"), ("0.0.0.0", 0, "x"), ("0.0.0.0", 70000, "x"), ("0.0.0.0", "a", "x"), ("0.0.0.0", 1, "")],
)
def test_validation(args):
    with pytest.raises(ValueError):
        sc.validate(*args)


def test_bind_error_recorded():
    sc.set_settings("203.0.113.1", 18997, "x")  # not a local address
    st = sc.start()
    assert not st["running"] and st["error"]


def test_saved_password_is_enforced():
    import base64
    import ssl
    import urllib.error
    import urllib.request

    port = _free_port()
    sc.set_settings("127.0.0.1", port, "secret")
    sc.start()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    url = f"https://127.0.0.1:{port}/api/capabilities"
    good = {"Authorization": "Basic " + base64.b64encode(b"x:secret").decode()}
    assert json.load(urllib.request.urlopen(urllib.request.Request(url, b"{}", good), context=ctx))["ok"]
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(urllib.request.Request(url, b"{}"), context=ctx)
