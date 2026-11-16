import base64
import json
import ssl
import urllib.request

import pytest

from tadiran_ac_backend import api, webserver


@pytest.fixture(scope="module")
def base():
    port = webserver.start_server("127.0.0.1", 0, "pw")
    yield f"https://127.0.0.1:{port}"
    webserver.stop_server()


def _ctx():
    # pin the hard-coded cert itself
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _auth(pw="pw"):
    return "Basic " + base64.b64encode(f"u:{pw}".encode()).decode()


def _get(url, pw="pw"):
    req = urllib.request.Request(url, headers={"Authorization": _auth(pw)})
    return urllib.request.urlopen(req, context=_ctx())


def _post(base, fn, args=None):
    req = urllib.request.Request(
        f"{base}/api/{fn}", json.dumps({"args": args or []}).encode(), {"Content-Type": "application/json", "Authorization": _auth()}
    )
    return json.load(urllib.request.urlopen(req, context=_ctx()))


def test_serves_web_ui(base):
    r = _get(base + "/")
    assert r.status == 200 and b"<html" in r.read().lower()
    assert _get(base + "/app.js").headers["Content-Type"].startswith(("text/javascript", "application/javascript"))


def test_no_traversal(base):
    for p in ("/../api.py", "/%2e%2e/api.py", "/certs/server.key"):
        with pytest.raises(urllib.error.HTTPError) as e:
            _get(base + p)
        assert e.value.code == 404


def test_api_call(base):
    out = _post(base, "capabilities")
    assert out["ok"] and out["value"] == api.capabilities()


def test_api_errors(base):
    assert not _post(base, "nope")["ok"]
    assert not _post(base, "__import__")["ok"]
    assert "empty" in _post(base, "rename_device", ["aa", " "])["error"]


def test_cert_valid_100_years(tmp_path):
    from importlib import resources
    from datetime import datetime, timedelta, timezone

    pem = resources.files("tadiran_ac_backend").joinpath("certs/server.crt").read_text()
    p = tmp_path / "c.pem"
    p.write_text(pem)
    info = ssl._ssl._test_decode_cert(str(p))
    end = datetime.strptime(info["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    assert end - datetime.now(timezone.utc) > timedelta(days=36000)


def test_start_idempotent(base):
    assert webserver.start_server() == webserver.server_port()


def test_password_required(base):
    for pw in (None, "wrong", ""):
        hdr = {"Authorization": _auth(pw)} if pw is not None else {}
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(urllib.request.Request(base + "/", headers=hdr), context=_ctx())
        assert e.value.code == 401 and "Basic" in e.value.headers["WWW-Authenticate"]
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(urllib.request.Request(base + "/api/capabilities", b"{}"), context=_ctx())
    assert e.value.code == 401


def test_pairing_is_stored_by_the_server(base, tmp_path, monkeypatch):
    # the web client only ever calls the API; the name lives in the server's store
    from tadiran_ac_backend.store import DeviceStore

    store = DeviceStore(tmp_path / "devices.json")
    monkeypatch.setattr(api, "_store", store)
    assert _post(base, "set_device_name", ["aa:bb:cc:dd:ee:ff", "10.0.0.9", None, "Living room"])["ok"]
    assert store.get("aa:bb:cc:dd:ee:ff")["name"] == "Living room"
    assert "Living room" in (tmp_path / "devices.json").read_text()
