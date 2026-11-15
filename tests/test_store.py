import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from tadiran_ac_backend.store import DeviceStore  # noqa: E402


def test_upsert_and_get(tmp_path):
    store = DeviceStore(tmp_path / "devices.json")
    store.upsert("7C:B8:E6:21:21:97", name="Living Room", ip="10.0.0.2", mid="10001")

    entry = store.get("7cb8e6212197")
    assert entry is not None
    assert entry["name"] == "Living Room"
    assert entry["ip"] == "10.0.0.2"
    assert entry["mid"] == "10001"


def test_mac_normalization_is_consistent(tmp_path):
    store = DeviceStore(tmp_path / "devices.json")
    store.upsert("7C-B8-E6-21-21-97", name="x", ip="10.0.0.2")
    assert store.get("7cb8e6212197") is not None
    assert store.get("7C:B8:E6:21:21:97") is not None


def test_rename_unknown_mac_returns_none(tmp_path):
    store = DeviceStore(tmp_path / "devices.json")
    assert store.rename("aabbccddeeff", "x") is None


def test_rename_known_mac(tmp_path):
    store = DeviceStore(tmp_path / "devices.json")
    store.upsert("aabbccddeeff", name="old", ip="10.0.0.9")
    result = store.rename("aabbccddeeff", "new")
    assert result["name"] == "new"
    assert store.get("aabbccddeeff")["name"] == "new"


def test_remove(tmp_path):
    store = DeviceStore(tmp_path / "devices.json")
    store.upsert("aabbccddeeff", name="x", ip="10.0.0.9")
    assert store.remove("aabbccddeeff") is True
    assert store.remove("aabbccddeeff") is False
    assert store.get("aabbccddeeff") is None


def test_list_all_sorted_by_name(tmp_path):
    store = DeviceStore(tmp_path / "devices.json")
    store.upsert("bb" * 6, name="Zebra", ip="10.0.0.1")
    store.upsert("aa" * 6, name="Alpha", ip="10.0.0.2")
    names = [d["name"] for d in store.list_all()]
    assert names == ["Alpha", "Zebra"]


def test_update_ip_only_touches_known_devices(tmp_path):
    store = DeviceStore(tmp_path / "devices.json")
    store.update_ip("aabbccddeeff", "10.0.0.5")  # no-op, unknown mac
    assert store.get("aabbccddeeff") is None

    store.upsert("aabbccddeeff", name="x", ip="10.0.0.1")
    store.update_ip("aabbccddeeff", "10.0.0.5")
    assert store.get("aabbccddeeff")["ip"] == "10.0.0.5"
