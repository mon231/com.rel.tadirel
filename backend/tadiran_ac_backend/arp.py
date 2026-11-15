"""Cross-platform ARP table lookup: MAC -> current IP.

Used as the fallback step for known/paired devices that don't answer a
direct unicast probe at their last-known IP (e.g. after a DHCP lease
change). See docs/04-architecture.md "Device pairing, naming, and
liveness".

Best-effort: on any platform/permission failure this returns an empty
table rather than raising, so callers simply treat the device as
unreachable (grayed out) instead of crashing.
"""

from __future__ import annotations

import re
import subprocess
import sys


def _normalize_mac(mac: str) -> str:
    return mac.strip().lower().replace("-", "").replace(":", "")


def _parse_windows_arp_a(output: str) -> dict[str, str]:
    table: dict[str, str] = {}
    # Lines look like:  "  10.0.0.2             7c-b8-e6-21-21-97     dynamic"
    pattern = re.compile(
        r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+([0-9a-fA-F]{2}(?:-[0-9a-fA-F]{2}){5})"
    )
    for line in output.splitlines():
        m = pattern.search(line)
        if m:
            ip, mac = m.group(1), m.group(2)
            table[_normalize_mac(mac)] = ip
    return table


def _parse_proc_net_arp(text: str) -> dict[str, str]:
    table: dict[str, str] = {}
    lines = text.splitlines()[1:]  # skip header
    for line in lines:
        parts = line.split()
        if len(parts) < 4:
            continue
        ip, mac = parts[0], parts[3]
        if mac and mac != "00:00:00:00:00:00":
            table[_normalize_mac(mac)] = ip
    return table


def _parse_unix_arp_an(output: str) -> dict[str, str]:
    table: dict[str, str] = {}
    # "? (10.0.0.2) at 7c:b8:e6:21:21:97 on en0 ifscope [ethernet]"
    pattern = re.compile(
        r"\((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\)\s+at\s+([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})"
    )
    for line in output.splitlines():
        m = pattern.search(line)
        if m:
            ip, mac = m.group(1), m.group(2)
            table[_normalize_mac(mac)] = ip
    return table


def get_arp_table() -> dict[str, str]:
    """Return {normalized_mac: ip} from the OS ARP cache. Empty on failure."""
    try:
        if sys.platform.startswith("win"):
            out = subprocess.run(
                ["arp", "-a"], capture_output=True, text=True, timeout=5
            ).stdout
            return _parse_windows_arp_a(out)

        if sys.platform.startswith("linux"):
            try:
                with open("/proc/net/arp", encoding="utf-8") as f:
                    return _parse_proc_net_arp(f.read())
            except OSError:
                out = subprocess.run(
                    ["ip", "neigh"], capture_output=True, text=True, timeout=5
                ).stdout
                table: dict[str, str] = {}
                for line in out.splitlines():
                    parts = line.split()
                    if "lladdr" in parts:
                        ip = parts[0]
                        mac = parts[parts.index("lladdr") + 1]
                        table[_normalize_mac(mac)] = ip
                return table

        # macOS / other BSD-ish
        out = subprocess.run(
            ["arp", "-an"], capture_output=True, text=True, timeout=5
        ).stdout
        return _parse_unix_arp_an(out)

    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return {}


def lookup_ip(mac: str) -> str | None:
    """Current IP for `mac` per the OS ARP cache, or None if not present."""
    table = get_arp_table()
    return table.get(_normalize_mac(mac))
