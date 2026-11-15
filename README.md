# Tadirel

Control Tadiran/Gree air conditioners on your own LAN -- no cloud account,
no Tadiran app, no internet dependency. Built from scratch after
reverse-engineering the official "My Tadiran" app; see **`docs/`** for the
full research writeup (app teardown, wire protocol, what's known/unknown
about the cloud API).

```
docs/        full knowledge base -- read docs/00-overview.md first
backend/     shared Python core (scanning, binding, control, naming store)
desktop/     PC app (Eel: native window + local web UI)
app/         Android app (Kotlin UI + the same backend via Chaquopy)
tests/       pytest for backend/ (offline, mocked network)
```

## Quickstart (desktop / PC)

```
cd backend && pip install -r requirements.txt && cd ..
cd desktop && pip install -r requirements.txt
python app.py
```

A window opens. **Scan subnet** finds every Gree-protocol AC on your
network (progress bar runs up to 12s, results appear live). Click **Name
this device** on a result to save it -- named devices show up under
**Saved air conditioners** with a trash icon (remove the pairing) and,
once opened, a pencil icon (rename). Click a saved, reachable device to
open full controls: power, mode, temperature, fan speed, swing, light,
turbo, quiet, and more.

Saved devices persist to `~/.tadiran_ac_control/devices.json`.

## Android

See `app/README.md` -- same backend, native Kotlin UI, built via
Chaquopy. Not yet compiled/tested on-device in this environment; the
backend it calls into was fully validated against real hardware.

## Tests

```
pip install pytest
pytest
```

## Why no cloud/remote control?

Short answer: Tadiran's and Gree's cloud APIs aren't publicly documented
anywhere, unlike the LAN protocol this project uses. Full writeup in
`docs/03-cloud-api.md`, including the recommended path for controlling
your AC from outside your house (tunnel into your LAN with
Tailscale/WireGuard, rather than reverse-engineering a private cloud API).
