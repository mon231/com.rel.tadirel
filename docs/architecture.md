# Tadirel's architecture

Layout modeled on `mon231/vidspy` (one shared Python backend, two thin
frontends — desktop via Eel, Android via Chaquopy):

```
backend/                     shared Python core, no UI code in here
  tadiran_ac_backend/
    __init__.py
    protocol_props.py        Props enum + human labels/choices (UI metadata)
    store.py                 JSON-file device store (mac -> ip/mid/name/last_seen)
    arp.py                   cross-platform ARP table lookup (MAC -> IP fallback)
    device.py                thin wrapper around greeclimate.AirConditionerDevice:
                              bind/status/apply, command-confirmation polling
    scanner.py                the "5 probes over 12s, stream new results" scan
    loop_runner.py            shared background asyncio event loop
    api.py                    the ONLY surface both frontends call:
                               start_scan / poll_scan / list_known_devices /
                               set_device_name / rename_device / remove_device /
                               get_status / send_command / capabilities
  requirements.txt

desktop/                     "PC app"
  app.py                     Eel entry point, exposes backend.api functions
                              to JS, opens a native Chrome/Edge app window
  web/
    index.html
    style.css
    app.js                   polls scan, renders device list + control panel
  requirements.txt

app/                         "Android app" (Chaquopy)
  build.gradle               module build file, Chaquopy plugin + python config
  src/main/
    AndroidManifest.xml
    java/com/tadirel/app/
      MainActivity.kt         device list screen (scan/refresh/pair/power)
      DeviceDetailActivity.kt full control screen (mode/temp/fan/swing/...)
      PyBridge.kt              thin Kotlin wrapper: Chaquopy calls into
                                backend.api, JSON in/out
      InsetsUtil.kt            edge-to-edge window inset handling
    python/
      android_bridge.py        Android-only JSON bridge over backend.api
      greeclimate/              vendored copy (see library-notes.md for why)
    res/layout, res/values     native Android views

build.gradle, settings.gradle, gradle.properties, gradlew*   root Gradle wrapper
tests/                        pytest against backend/ only (frontends are thin)
docs/                         this knowledge base (local only, not committed)
```

## Why this shape

- **One backend, two UIs.** All protocol/state logic (scanning, binding,
  property get/set, the device name store) lives once in
  `backend/tadiran_ac_backend/`. Desktop and Android both call the exact
  same handful of functions in `api.py` — neither re-implements any
  networking.
- **Desktop = Eel.** Eel runs the Python backend in-process and opens a
  local web page in an app-mode browser window — gives a "real app" feel
  with normal HTML/CSS/JS for the UI, zero extra packaging complexity, and
  is exactly the pattern `vidspy/desktop/app.py` uses.
- **Android = Chaquopy, native UI.** Chaquopy embeds a Python interpreter
  in the Android app and lets Kotlin call into `backend.api` directly
  (JSON strings in, JSON strings out — same shape Eel uses on desktop, so
  `api.py`'s functions don't need to know which frontend is calling). The
  UI itself is native Kotlin views (not a WebView), matching vidspy's
  Android app, which also uses native views with Chaquopy underneath.
- **Scanning contract.** `scanner.py` sends the Gree "scan" probe up to 5
  times, once every 2 seconds, while listening continuously; stops
  entirely at the 12-second mark. Any device reply is reported the
  instant it arrives (via an internal queue), not batched at the end —
  both UIs poll that queue every ~300ms while a scan is running so new
  rows appear live, and both show a "Refresh" action that just starts a
  new scan.
- **Device identity = MAC.** The scan reply's MAC is the stable key for
  naming/storing a unit (IP can change via DHCP). `store.py` persists
  `{mac: {ip, mid, name, last_seen}}` as local JSON — no server, no cloud
  account, matches the no-cloud stance from [Cloud API](cloud-api.md).
- **Control screen capabilities are data-driven.** `protocol_props.py`
  describes each controllable property (label, kind: toggle/enum/int-range,
  and for enums the choice labels) so both the HTML UI and the native
  Android UI can render the same control set from one source of truth
  without hardcoding widgets per platform.
- **Command confirmation, not just send-and-trust.** `send_command`
  applies the change, then polls the unit's real status until the changed
  property reads back as requested (or a short timeout elapses) — both
  UIs show the AC's actual latest state, and warn if it hasn't confirmed
  yet, rather than assuming success the instant a packet goes out.

## Device pairing, naming, and liveness

A "pairing" is a user-assigned name attached to a MAC address — this is
the only thing that gets persisted to `store.py`'s JSON file. Unnamed scan
hits are transient (shown only in the live subnet-scan results while a
scan is running); giving one a name is what promotes it into the
persisted "known devices" list.

- **Known devices list** (always visible, no scan needed to populate it):
  every `{mac: name, ...}` entry in the store. Each row shows name, MAC,
  resolved IP (or "unreachable"), a trash icon (deletes the pairing), and,
  once a row is selected, an edit icon to rename it.
- **Liveness check for known devices** (run on load and on refresh,
  deliberately cheap — not the full 12s broadcast scan):
  1. Unicast a single "scan" probe to the device's last-known IP
     (~1.5s timeout). A matching reply = alive, update stored IP.
  2. If that fails, fall back to an **ARP table lookup** by MAC to find
     the current IP (handles DHCP lease changes without re-scanning the
     whole subnet). If ARP resolves an IP, the device is treated as
     reachable and the store's IP is updated.
  3. If the ARP table has **no entry at all** for that MAC, the device is
     marked unreachable: its row is grayed out and cannot be selected for
     control (the trash icon still works, so a genuinely gone unit can be
     unpaired).
- **Subnet scan results** (the explicit 5-probe/12s broadcast flow) are
  for *finding* devices, named or not. A result whose MAC is already in
  the store shows its existing name; a result with no stored name shows a
  "Pair" affordance.

## Explicitly out of scope (for now)

- WiFi/BLE pairing of a *brand-new* unit (the AP-mode/BLE provisioning
  flow in Gree's SDK, see [App teardown](app-teardown.md)). Tadirel only
  controls units already joined to the LAN.
- Tadiran/Gree cloud control (see [Cloud API](cloud-api.md)).
- Tuya-protocol devices — different protocol family, not implemented
  here.
