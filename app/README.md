# Android app (Chaquopy)

Native Kotlin UI; all protocol/state logic is the exact same
`backend/tadiran_ac_backend` package the desktop app uses, running
on-device via [Chaquopy](https://chaquo.com/chaquopy/). See
`../docs/04-architecture.md` for the overall design.

**Status: builds clean and runs on a real device** (installed via USB on
a Samsung Galaxy S24-class device, `assembleDebug` → `adb install`,
launched without crashing). See "Android-specific fixes" below for the
three real issues that took to get there.

## Prerequisites

- Android Studio (Koala+) or a standalone Android SDK (compileSdk 35,
  minSdk 26) + JDK 17-21. (Built and tested here with Android Studio's
  bundled JBR 21 as `JAVA_HOME` and Gradle 8.9.)
- A Chaquopy license is **not** needed for personal/open-source use of the
  free tier shipped here (Chaquopy is free for non-commercial/open-source
  apps per its own licensing terms -- check chaquo.com if this app is ever
  distributed commercially).

## First-time setup

The Gradle wrapper (`gradlew`, `gradlew.bat`, `gradle/wrapper/`) is
committed, so `./gradlew` works straight after cloning -- no system
Gradle install needed; the wrapper downloads the pinned Gradle version
itself on first run.

Create `local.properties` at the repo root (not committed,
machine-specific):

```
sdk.dir=C:/Users/you/AppData/Local/Android/Sdk
```

Use forward slashes even on Windows -- `.properties` files treat `\` as
an escape character, and `sdk.dir=C:\Users\...` silently produces a
mangled path that fails deep inside AGP's SDK locator with a cryptic
`java.io.IOException: Invalid file path`.

## Build & install

```
export JAVA_HOME="/path/to/a/jdk-17-or-21"   # e.g. Android Studio's bundled jbr/
export ANDROID_HOME="/path/to/Android/Sdk"
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n com.rel.tadirel/.MainActivity
```

## How the Python side is wired in

`app/build.gradle`'s `sourceSets.main.python.srcDirs` points at:

- `src/main/python/android_bridge.py` — the only Android-specific glue
  code. It wraps `tadiran_ac_backend.api` and returns JSON strings, since
  marshalling `PyObject`s by hand from Kotlin is painful — Kotlin only
  ever touches JSON (see `PyBridge.kt`).
- `src/main/python/greeclimate/` — a **vendored copy** of the
  `greeclimate` 4.3.0 package (not pip-installed). See "Android-specific
  fixes" below for why.
- `../backend/` — the real, shared backend package. It is **not copied**;
  Chaquopy packages it straight from the repo's one true source, so
  there's exactly one copy of the protocol/scanning/store logic shared by
  desktop and Android.

## Android-specific fixes

Three real problems showed up getting this running on an actual device,
none of them in `backend/` itself (which was already validated against
real hardware from the desktop app):

1. **`greeclimate` isn't really pip-installable for Android.** Chaquopy's
   package mirror (`chaquo.com/pypi-13.1`) only has `greeclimate` up to
   `2.1.4`, which predates the 4.x rewrite `backend/` is built against
   (no `AirConditionerDevice`, no `Props`, no `device_factory` — a
   completely different API). Fix: vendor the actual 4.3.0 source
   (the version this project was developed and tested against) as plain
   Python files under `src/main/python/greeclimate/`, bypassing pip for
   that package entirely. greeclimate is GPLv3-licensed; vendoring its
   source here is fine for a personal/sideloaded build, but re-check GPL
   source-availability obligations before ever distributing a built APK
   to someone else.

2. **pycryptodome's Android wheel is broken.** Chaquopy's cross-compiled
   arm64-v8a wheels for `pycryptodome` are missing native cipher
   extension modules -- `Crypto.Util._cpuid_c` on 3.24.x, and even after
   pinning older (`3.19.1`, which predates `_cpuid_c`), `Crypto.Cipher
   ._raw_ecb` was *also* missing. Every version crashed the app at
   startup with `OSError: Cannot load native module`. Fix: the vendored
   `greeclimate/cipher.py` was rewritten for the Android build to use
   `javax.crypto` (part of the Android platform itself, via Chaquopy's
   `from java import jclass` interop) instead of pycryptodome — same
   AES-128-ECB (CipherV1) and AES-128-GCM (CipherV2) semantics, zero
   native-wheel risk. `pycryptodome` was dropped from
   `app/build.gradle`'s pip block entirely; only `ifaddr` remains.
   (The desktop app is unaffected -- it still uses the real, pip-installed
   `greeclimate` + pycryptodome via normal desktop Python, which works
   fine there.)

3. **PEP 604 `X | None` annotations crash on Chaquopy's Python 3.8
   runtime.** greeclimate 4.3.0 was written against Python 3.10+, which
   lets `str | None` be evaluated as an actual runtime expression in a
   function signature. Chaquopy's on-device interpreter is Python 3.8,
   which doesn't support that syntax at runtime, and crashed with
   `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'`
   the moment `greeclimate.deviceinfo` was imported. Fix: added
   `from __future__ import annotations` to every vendored `greeclimate`
   module (defers all annotations to strings, never evaluated at
   runtime) -- a no-op everywhere else, a required fix here.

If Chaquopy's package mirror ever catches up to greeclimate 4.x, or ships
working pycryptodome wheels, items 1-2 could be reverted to a normal
`pip { install "greeclimate" }` line. Check before doing that, though --
re-verify the vendored `cipher.py`'s behavior against real hardware if you
do switch back.

## Known gaps

- No instrumented/UI tests for the Android layer; `../tests/` covers the
  shared backend only. The real-device smoke test so far is "launches
  without crashing and `MainActivity` stays resumed" -- full click-through
  of scan/pair/control on-device (equivalent to the desktop app's
  Playwright pass) hasn't been done yet.
- Icon is a custom vector (`ic_launcher_foreground.xml` /
  `ic_launcher_background.xml`), not a designer asset -- fine for
  personal use, worth a real pass before any wider distribution.
