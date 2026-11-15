# `greeclimate` library notes (found while building against real hardware)

Package: `greeclimate` on PyPI (v4.3.0 used here). Async (`asyncio`), used
by Home Assistant's `gree` integration. Modules used by `backend/`:
`greeclimate.discovery.Discovery`, `greeclimate.device_factory.create_device`,
`greeclimate.air_conditioner.AirConditionerDevice`/`Props`,
`greeclimate.cipher.CipherV1`, `greeclimate.deviceinfo.DeviceInfo`.

## Quirks that actually mattered (desktop)

1. **`send()` does not wait for a reply.** `Device.send()`'s own docstring
   says "completion does not imply a reply" — it only waits for the local
   socket write to drain. The actual reply arrives later via
   `datagram_received()`. Reading a property (`device.power`, etc.) right
   after `await device.update_state()` or `await device.push_state_update()`
   with no delay will see stale/`None` data. **Fix:** always
   `await asyncio.sleep(~1)` after `update_state()`/`push_state_update()`
   before reading properties.

2. **`device.bind(key=..., cipher=...)` does not open a transport.** Its
   docstring says so explicitly ("does not open a transport"), and its
   implementation just sets `self.device_cipher = cipher` and returns.
   Calling any send afterwards raises `DeviceNotBoundError` because
   `_ensure_bound()` only (re)binds `if not self.device_cipher` — and a
   manually-set cipher makes it think it's already fully bound. Tadirel's
   backend always does a fresh full bind per interaction rather than
   trying to cache/reuse the per-device key across process runs via this
   method — it's cheap (one local UDP round-trip, not a network call) and
   avoids the issue entirely.

3. **Discovery vs. per-IP bind both need `DeviceInfo`.** `create_device()`
   needs a populated `DeviceInfo` (ip, port, mac, name, mid) to pick the
   right device class (dispatch is by `mid`, see
   `greeclimate.device_factory.DEVICE_TYPES`/`KNOWN_MID_PROFILES`). You can
   either get one from `Discovery.scan()` (broadcast or unicast) or
   construct one directly if you already know those fields from a
   previous scan, skipping the multi-second scan wait entirely. Tadirel's
   device store caches `mid` specifically so later unicast
   health-checks/binds can skip rediscovery.

4. **Windows note (`asyncio.windows_events`).** Running discovery across
   multiple local network interfaces (VPN/virtual adapters with no real
   route) throws harmless `OSError: [WinError 1231] The network location
   cannot be reached` from `ProactorEventLoop`'s internals — caught
   per-interface by `asyncio.gather(..., return_exceptions=True)` inside
   `Discovery.search_devices()`, so it doesn't break the scan; it just
   prints noise to stderr. Safe to ignore.

5. **Enum encodings worth knowing:**
   - `quiet` setter maps `True` → `2`, `False` → `0` (not `1`) — reading
     back `Props.QUIET` as a plain int for display should treat any
     non-zero value as "on".
   - `target_temperature` with `temperature_units == 1` (Fahrenheit) writes
     *two* properties together (`SetTem` + `TemRec`) for half-degree
     precision — always set/read them as a pair, never `SetTem` alone,
     when Fahrenheit is in play. Tadirel always runs in Celsius
     (`TemUn = 0`) to avoid the complication.
   - `sleep` setter writes both `SwhSlp` and `SlpMod` together.

## Getting it running on Android (Chaquopy)

Three real problems showed up getting this library running on an actual
device — none of them in Tadirel's own backend code, which was already
validated against real hardware from the desktop app first:

1. **`greeclimate` isn't really pip-installable for Android.** Chaquopy's
   package mirror only had `greeclimate` up to a very old `2.x` release,
   which predates the modern API this project is built against entirely
   (different module layout, no `AirConditionerDevice`/`Props`/
   `device_factory`). Fix: vendor the real, modern `greeclimate` source
   as plain Python files in the Android app rather than pip-installing it
   at all.

   !!! warning "License"
       `greeclimate` is GPLv3-licensed. Vendoring its source is fine for
       personal/sideloaded builds, but re-check GPL source-availability
       obligations before distributing a built APK to anyone else.

2. **Chaquopy's `pycryptodome` wheel for Android is broken.** Its
   cross-compiled `arm64-v8a` wheels are missing native cipher extension
   modules (`Crypto.Util._cpuid_c` on newer releases, `Crypto.Cipher
   ._raw_ecb` even on older ones) — every version crashed the app at
   startup with `OSError: Cannot load native module`. Fix: the Android
   build's vendored `cipher.py` uses `javax.crypto` (part of the Android
   platform itself, reached via Chaquopy's Java interop) instead of
   pycryptodome — same AES-128-ECB and AES-128-GCM semantics as upstream,
   zero native-wheel risk. The desktop app is unaffected; it still uses
   real pycryptodome via normal desktop Python, which works fine there.

3. **PEP 604 `X | None` annotations crash on older Python runtimes.**
   Modern `greeclimate` was written against Python 3.10+, which evaluates
   `str | None` as an actual runtime expression in a function signature.
   An older on-device Python interpreter doesn't support that syntax at
   runtime, and crashes with `TypeError: unsupported operand type(s) for
   |: 'type' and 'NoneType'` the moment the affected module is imported.
   Fix: `from __future__ import annotations` at the top of every vendored
   module (defers all annotations to strings, never evaluated at runtime)
   — a no-op everywhere else, a required fix here.

## Capability discovery

`AirConditionerDevice._capability_names` lists what the class *can*
expose (power, mode, target_temperature, temperature_units,
current_temperature, fan_speed, fresh_air, xfan, anion, sleep, light,
horizontal_swing, vertical_swing, quiet, turbo, steady_heat, power_save,
buzzer_control) — but that's a static class-level list, not a live
capability negotiation with the actual unit. Real per-unit capabilities
come back as whatever columns the unit actually answers a status request
with. Tadirel's UI renders controls for the full static property list and
simply shows "—" for anything the unit doesn't report a value for.
