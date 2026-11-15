"""Shared Python core for Tadiran/Gree LAN AC control.

Both the desktop (Eel) app and the Android (Chaquopy) app call only
`tadiran_ac_backend.api` -- nothing else in here is a public surface.
"""

from ._version import __version__  # noqa: F401
