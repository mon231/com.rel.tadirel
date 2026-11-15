"""Subnet scan: broadcast a Gree "scan" probe 5 times, once every 2
seconds, listening continuously, hard stop at 12 seconds total. Every
device reply is reported the instant it's decoded (via a thread-safe
queue), not batched at the end -- see docs/04-architecture.md.
"""

from __future__ import annotations

import asyncio
import queue
import time
import uuid
from typing import Any

from greeclimate.discovery import Discovery, Listener
from greeclimate.deviceinfo import DeviceInfo

from .device import device_info_to_dict

PROBE_COUNT = 5
PROBE_INTERVAL_SECONDS = 2
SCAN_TOTAL_SECONDS = 12


class _QueueListener(Listener):
    def __init__(self, out_queue: "queue.Queue[dict[str, Any]]"):
        self._queue = out_queue

    async def device_found(self, device_info: DeviceInfo) -> None:
        self._queue.put_nowait(device_info_to_dict(device_info))

    async def device_update(self, device_info: DeviceInfo) -> None:
        self._queue.put_nowait(device_info_to_dict(device_info))


class ScanSession:
    """One in-flight (or finished) subnet scan. Not reused across scans."""

    def __init__(self):
        self.id = str(uuid.uuid4())
        self.queue: "queue.Queue[dict[str, Any]]" = queue.Queue()
        self.done = False
        self.started_at = time.monotonic()
        self.error: str | None = None

    def drain_new(self) -> list[dict[str, Any]]:
        results = []
        while True:
            try:
                results.append(self.queue.get_nowait())
            except queue.Empty:
                break
        return results

    async def run(self) -> None:
        disc = Discovery()
        listener = _QueueListener(self.queue)
        disc.add_listener(listener)
        try:
            await disc.search_devices()
            start = time.monotonic()
            next_probe_at = PROBE_INTERVAL_SECONDS
            probes_sent = 1
            while True:
                elapsed = time.monotonic() - start
                remaining_total = SCAN_TOTAL_SECONDS - elapsed
                if remaining_total <= 0:
                    break
                if probes_sent < PROBE_COUNT and elapsed >= next_probe_at:
                    await disc.search_devices()
                    probes_sent += 1
                    next_probe_at += PROBE_INTERVAL_SECONDS
                await asyncio.sleep(min(0.25, remaining_total))
        except Exception as exc:  # pragma: no cover - defensive, surfaced to UI
            self.error = str(exc)
        finally:
            disc.close()
            self.done = True
