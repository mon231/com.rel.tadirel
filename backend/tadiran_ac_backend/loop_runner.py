"""A single background asyncio event loop that every synchronous call in
api.py schedules work onto. Both Eel (desktop) and Chaquopy (Android) call
into api.py from plain synchronous code, so api.py itself must not be a
coroutine -- this is what lets it block-and-return a plain value instead.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None
_start_lock = threading.Lock()


def _ensure_started() -> asyncio.AbstractEventLoop:
    global _loop, _thread
    with _start_lock:
        if _loop is not None:
            return _loop
        loop = asyncio.new_event_loop()

        def _run():
            asyncio.set_event_loop(loop)
            loop.run_forever()

        thread = threading.Thread(target=_run, name="ac-backend-loop", daemon=True)
        thread.start()
        _loop = loop
        _thread = thread
        return loop


def run_sync(coro: Coroutine[Any, Any, T], timeout: float | None = None) -> T:
    """Run `coro` on the shared background loop and block for its result."""
    loop = _ensure_started()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=timeout)


def submit(coro: Coroutine[Any, Any, Any]) -> None:
    """Schedule `coro` on the shared loop without waiting for it."""
    loop = _ensure_started()
    asyncio.run_coroutine_threadsafe(coro, loop)
