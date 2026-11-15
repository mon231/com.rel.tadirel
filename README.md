# Tadirel

Control Tadiran/Gree air conditioners on your own LAN -- no cloud account,
no Tadiran app, no internet dependency. Built by reverse-engineering the
official Tadiran consumer app and the public Gree AC protocol; see
**[docs/](docs/index.md)** for the full research writeup (app teardown,
wire protocol, what's known/unknown about the cloud API).

```
docs/        research knowledge base -- see docs/index.md (published via GitHub Pages)
backend/     shared Python core (scanning, binding, control, naming store)
desktop/     PC app (Eel: native window + local web UI)
app/         Android app (com.rel.tadirel: Kotlin UI + the same backend via Chaquopy)
tests/       pytest for backend/ (offline, mocked network)
```

## Quickstart (desktop / PC)

```
cd backend && pip install -r requirements.txt && cd ..
cd desktop && pip install -r requirements.txt
python app.py
```

A window opens. **Scan subnet** finds every Gree-protocol AC on your
network (progress bar runs up to 12s, results appear live). Click **Pair**
on a result to save it -- paired devices show up under **Saved air
conditioners** with a trash icon (remove the pairing) and, once opened, a
pencil icon (rename). Click a saved, reachable device to open full
controls: power, mode, temperature, fan speed, swing, light, turbo,
quiet, and more.

Saved devices persist to `~/.tadiran_ac_control/devices.json`.

## Android

See [`app/README.md`](app/README.md) -- same backend, native Kotlin UI,
built via Chaquopy. Runs on real hardware (Samsung Galaxy S24-class
device tested); see that README for the Chaquopy/16KB-page/vendoring
fixes it took to get there.

## Tadirel Server (Android, always-on)

`tadirel-server-<tag>.apk` (applicationId `com.rel.tadirel.server`, installs
next to the regular app) is the same app plus a foreground service that runs
the shared backend's HTTPS server on **port 18972** and starts again on boot.
Browse to `https://<phone-ip>:18972/` for the web UI (same UI as the PC
app). TLS uses a hard-coded self-signed cert (valid to 2126) in
`backend/tadiran_ac_backend/certs/`, so browsers show a one-time warning.
There is **no authentication**: anyone on the LAN can control your ACs.
Open the app once so the service starts and Android grants the
"always run in background" exemption. The PC app can run the same server
headless: `python desktop/app.py --serve`.

## Tests

```
pip install pytest
pytest
```

## CI

- **Build** (`.github/workflows/build.yml`) -- debug APK on every push/PR.
- **Desktop** (`.github/workflows/desktop.yml`) -- PyInstaller single-file
  executables for Linux and Windows on every push/PR.
- **Release** (`.github/workflows/release.yml`) -- on a `v*` tag: signed
  release APK, desktop executables, and a backend wheel, all attached to
  a GitHub Release.
- **Docs** (`.github/workflows/docs.yml`) -- deploys `docs/` to GitHub
  Pages on every push to `main`.

## Why no cloud/remote control?

Short answer: Tadiran's and Gree's cloud APIs aren't publicly documented
anywhere, unlike the LAN protocol this project uses. Full writeup in
[`docs/cloud-api.md`](docs/cloud-api.md), including the recommended path
for controlling your AC from outside your house (tunnel into your LAN
with Tailscale/WireGuard, rather than reverse-engineering a private cloud
API).
