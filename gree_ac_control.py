"""
Local LAN control for Tadiran air conditioners (rebranded Gree hardware).

Confirmed by reverse-engineering the official "My Tadiran" Android app
(com.tadiran.mytadiran.prod v1.11.0): the native AC control layer bundles
Gree's own `com.gree.greeplus.sdk` library. Its protocol property keys
(Pow, Mod, SetTem, WdSpd, Lig, Tur, ...) match byte-for-byte the public,
community-documented Gree "Gree+" LAN protocol, implemented here via the
`greeclimate` PyPI package (the same library Home Assistant's `gree`
integration uses).

This talks directly to the AC unit's WiFi module over UDP port 7000 on
your LAN. No cloud, no Tadiran/Gree account involved -- this only works
for a device you already own and that is already joined to your WiFi.

Usage:
    python gree_ac_control.py scan
    python gree_ac_control.py status  <ip>
    python gree_ac_control.py power   <ip> on|off
    python gree_ac_control.py temp    <ip> <celsius>
    python gree_ac_control.py mode    <ip> auto|cool|dry|fan|heat
    python gree_ac_control.py fan     <ip> auto|1|2|3|4|5
"""

import argparse
import asyncio

from greeclimate.discovery import Discovery
from greeclimate.device_factory import create_device

MODE_MAP = {"auto": 0, "cool": 1, "dry": 2, "fan": 3, "heat": 4}
FAN_MAP = {"auto": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5}


async def scan():
    disc = Discovery()
    devices = await disc.scan(wait_for=3)
    if not devices:
        print("No Gree/Tadiran AC units found on this network.")
        print("Check: same WiFi/VLAN as the AC's WiFi module, UDP port 7000 not blocked.")
        return
    for d in devices:
        print(f"ip={d.ip} port={d.port} mac={d.mac} name={d.name} mid={d.mid}")
    disc.close()


async def get_device(ip: str):
    disc = Discovery()
    devices = await disc.scan(wait_for=3, target_addresses=[ip])
    disc.close()
    if not devices:
        raise SystemExit(f"Could not find/scan AC at {ip} (is it on and on this LAN?)")

    device = create_device(devices[0])
    await device.bind()  # cheap local UDP handshake, not a cloud call
    print(f"[bound] local key for this AC: {device.device_cipher.key}")
    await device.update_state()
    await asyncio.sleep(1)  # status DATA reply arrives async via datagram_received
    return device


async def cmd_status(ip):
    device = await get_device(ip)
    print(f"power            = {device.power}")
    print(f"mode             = {device.mode}")
    print(f"target_temp (C)  = {device.target_temperature}")
    print(f"current_temp (C) = {device.current_temperature}")
    print(f"fan_speed        = {device.fan_speed}")
    device.close()


async def cmd_power(ip, state):
    device = await get_device(ip)
    device.power = 1 if state == "on" else 0
    await device.push_state_update()
    await asyncio.sleep(1)
    print(f"power set to {state}")
    device.close()


async def cmd_temp(ip, celsius):
    device = await get_device(ip)
    device.power = 1
    device.target_temperature = int(celsius)
    await device.push_state_update()
    await asyncio.sleep(1)
    print(f"target temperature set to {celsius}C")
    device.close()


async def cmd_mode(ip, mode):
    device = await get_device(ip)
    device.power = 1
    device.mode = MODE_MAP[mode]
    await device.push_state_update()
    await asyncio.sleep(1)
    print(f"mode set to {mode}")
    device.close()


async def cmd_fan(ip, speed):
    device = await get_device(ip)
    device.fan_speed = FAN_MAP[speed]
    await device.push_state_update()
    await asyncio.sleep(1)
    print(f"fan speed set to {speed}")
    device.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)

    sub.add_parser("scan")

    sp = sub.add_parser("status")
    sp.add_argument("ip")

    sp = sub.add_parser("power")
    sp.add_argument("ip")
    sp.add_argument("state", choices=["on", "off"])

    sp = sub.add_parser("temp")
    sp.add_argument("ip")
    sp.add_argument("celsius", type=int)

    sp = sub.add_parser("mode")
    sp.add_argument("ip")
    sp.add_argument("mode", choices=list(MODE_MAP))

    sp = sub.add_parser("fan")
    sp.add_argument("ip")
    sp.add_argument("speed", choices=list(FAN_MAP))

    args = p.parse_args()

    if args.action == "scan":
        asyncio.run(scan())
    elif args.action == "status":
        asyncio.run(cmd_status(args.ip))
    elif args.action == "power":
        asyncio.run(cmd_power(args.ip, args.state))
    elif args.action == "temp":
        asyncio.run(cmd_temp(args.ip, args.celsius))
    elif args.action == "mode":
        asyncio.run(cmd_mode(args.ip, args.mode))
    elif args.action == "fan":
        asyncio.run(cmd_fan(args.ip, args.speed))


if __name__ == "__main__":
    main()
