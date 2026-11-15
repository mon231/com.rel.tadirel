"""UI metadata for every controllable property, data-driven so neither
frontend hardcodes widgets per platform. See docs/02-lan-protocol.md for
the underlying Gree LAN protocol keys this maps to.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Choice:
    value: int
    label: str


@dataclass(frozen=True)
class PropSpec:
    key: str  # attribute name on greeclimate.AirConditionerDevice
    label: str
    kind: str  # "toggle" | "enum" | "int_range"
    choices: tuple[Choice, ...] = field(default_factory=tuple)
    min: int | None = None
    max: int | None = None
    icon: str = ""


MODE_CHOICES = (
    Choice(0, "Auto"),
    Choice(1, "Cool"),
    Choice(2, "Dry"),
    Choice(3, "Fan"),
    Choice(4, "Heat"),
)

FAN_CHOICES = (
    Choice(0, "Auto"),
    Choice(1, "Low"),
    Choice(2, "Med-Low"),
    Choice(3, "Medium"),
    Choice(4, "Med-High"),
    Choice(5, "High"),
)

SWING_CHOICES = (
    Choice(0, "Default"),
    Choice(1, "Full swing"),
    Choice(2, "Pos 1"),
    Choice(3, "Pos 2"),
    Choice(4, "Pos 3"),
    Choice(5, "Pos 4"),
    Choice(6, "Pos 5"),
)

# Order here is the order controls render in, in both UIs.
CONTROL_PROPS: tuple[PropSpec, ...] = (
    PropSpec("power", "Power", "toggle", icon="power"),
    PropSpec("mode", "Mode", "enum", choices=MODE_CHOICES, icon="mode"),
    PropSpec("target_temperature", "Target temperature", "int_range", min=8, max=30, icon="temp"),
    PropSpec("fan_speed", "Fan speed", "enum", choices=FAN_CHOICES, icon="fan"),
    PropSpec("horizontal_swing", "Horizontal swing", "enum", choices=SWING_CHOICES, icon="swing-h"),
    PropSpec("vertical_swing", "Vertical swing", "enum", choices=SWING_CHOICES, icon="swing-v"),
    PropSpec("light", "Display light", "toggle", icon="light"),
    PropSpec("turbo", "Turbo", "toggle", icon="turbo"),
    PropSpec("quiet", "Quiet", "toggle", icon="quiet"),
    PropSpec("xfan", "X-Fan (dry coil)", "toggle", icon="xfan"),
    PropSpec("sleep", "Sleep", "toggle", icon="sleep"),
    PropSpec("anion", "Anion / ionizer", "toggle", icon="anion"),
    PropSpec("fresh_air", "Fresh air", "toggle", icon="fresh-air"),
    PropSpec("steady_heat", "Steady heat (8C)", "toggle", icon="steady-heat"),
    PropSpec("power_save", "Power save", "toggle", icon="power-save"),
)

# Read-only, shown but not settable.
READONLY_PROPS: tuple[PropSpec, ...] = (
    PropSpec("current_temperature", "Current temperature", "int_range", icon="thermometer"),
)

_BY_KEY: dict[str, PropSpec] = {p.key: p for p in (*CONTROL_PROPS, *READONLY_PROPS)}


def spec_for(key: str) -> PropSpec | None:
    return _BY_KEY.get(key)


def capabilities_payload() -> dict[str, Any]:
    """JSON-serializable description of every control, for the UI to render."""

    def choice_dicts(p: PropSpec) -> list[dict[str, Any]]:
        return [{"value": c.value, "label": c.label} for c in p.choices]

    def prop_dict(p: PropSpec) -> dict[str, Any]:
        d: dict[str, Any] = {"key": p.key, "label": p.label, "kind": p.kind, "icon": p.icon}
        if p.kind == "enum":
            d["choices"] = choice_dicts(p)
        if p.kind == "int_range":
            d["min"] = p.min
            d["max"] = p.max
        return d

    return {
        "controls": [prop_dict(p) for p in CONTROL_PROPS],
        "readonly": [prop_dict(p) for p in READONLY_PROPS],
    }
