import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from tadiran_ac_backend import protocol_props  # noqa: E402


def test_capabilities_payload_shape():
    payload = protocol_props.capabilities_payload()
    assert "controls" in payload and "readonly" in payload
    keys = {c["key"] for c in payload["controls"]}
    assert "power" in keys
    assert "mode" in keys
    assert "target_temperature" in keys
    assert "fan_speed" in keys


def test_enum_controls_carry_choices():
    payload = protocol_props.capabilities_payload()
    mode = next(c for c in payload["controls"] if c["key"] == "mode")
    assert mode["kind"] == "enum"
    labels = {c["label"] for c in mode["choices"]}
    assert {"Auto", "Cool", "Dry", "Fan", "Heat"} <= labels


def test_int_range_controls_carry_min_max():
    payload = protocol_props.capabilities_payload()
    temp = next(c for c in payload["controls"] if c["key"] == "target_temperature")
    assert temp["kind"] == "int_range"
    assert temp["min"] == 8
    assert temp["max"] == 30


def test_spec_for_unknown_key_is_none():
    assert protocol_props.spec_for("not_a_real_prop") is None


def test_spec_for_known_key():
    assert protocol_props.spec_for("power").label == "Power"
