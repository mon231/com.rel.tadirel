import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from tadiran_ac_backend import arp  # noqa: E402

WINDOWS_ARP_A_OUTPUT = """
Interface: 10.0.0.9 --- 0xb
  Internet Address      Physical Address      Type
  10.0.0.1              00-50-56-f5-79-c7     dynamic
  10.0.0.2              7c-b8-e6-21-21-97     dynamic
  10.0.0.254            ff-ff-ff-ff-ff-ff     static
"""

PROC_NET_ARP_OUTPUT = """IP address       HW type     Flags       HW address            Mask     Device
10.0.0.2         0x1         0x2         7c:b8:e6:21:21:97     *        eth0
10.0.0.9         0x1         0x0         00:00:00:00:00:00     *        eth0
"""

UNIX_ARP_AN_OUTPUT = """
? (10.0.0.1) at 00:50:56:f5:79:c7 on en0 ifscope [ethernet]
? (10.0.0.2) at 7c:b8:e6:21:21:97 on en0 ifscope [ethernet]
"""


def test_parse_windows_arp_a():
    table = arp._parse_windows_arp_a(WINDOWS_ARP_A_OUTPUT)
    assert table["7cb8e6212197"] == "10.0.0.2"
    assert table["ffffffffffff"] == "10.0.0.254"


def test_parse_proc_net_arp_skips_zero_mac():
    table = arp._parse_proc_net_arp(PROC_NET_ARP_OUTPUT)
    assert table["7cb8e6212197"] == "10.0.0.2"
    assert "000000000000" not in table


def test_parse_unix_arp_an():
    table = arp._parse_unix_arp_an(UNIX_ARP_AN_OUTPUT)
    assert table["7cb8e6212197"] == "10.0.0.2"


def test_lookup_ip_uses_normalized_mac(monkeypatch):
    monkeypatch.setattr(arp, "get_arp_table", lambda: {"7cb8e6212197": "10.0.0.2"})
    assert arp.lookup_ip("7C:B8:E6:21:21:97") == "10.0.0.2"
    assert arp.lookup_ip("aabbccddeeff") is None


def test_get_arp_table_never_raises_on_failure(monkeypatch):
    def boom(*a, **kw):
        raise FileNotFoundError("no arp binary")

    monkeypatch.setattr(arp.subprocess, "run", boom)
    assert arp.get_arp_table() == {}
