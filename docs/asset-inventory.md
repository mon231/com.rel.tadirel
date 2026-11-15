# Full asset inventory

Exhaustive pass over every asset bundled in the official app: native
libraries (all ABIs), the `assets/` tree, and a final sweep for
third-party SDK identifiers that didn't fit elsewhere. See
[App teardown](app-teardown.md) for the primary findings and
[Cloud API](cloud-api.md) for the REST/GraphQL surface — this page is the
"everything else" catalog.

## Native libraries (`lib/arm64-v8a/`)

| Library | Size | Purpose |
|---|---|---|
| `libgree.so` | 341 KB | Gree AES/crypto primitives (see [App teardown](app-teardown.md)) |
| `libBleLib.so` | 16 KB | Gree BLE provisioning transport. No literal service/characteristic UUID strings recoverable via static `strings` — likely stored as raw binary constants, not string literals. |
| `libCHIPController.so` | 10.5 MB | Matter/CHIP controller (Tuya's Matter support) — largest native lib in the app by far |
| `libThingSmartLink.so` | 283 KB | Tuya ("ThingSmart") WiFi-provisioning SmartLink/SmartConfig native code |
| `libthing_security.so` | 195 KB | Tuya SDK crypto/security native layer |
| `libthing_security_algorithm.so` | 77 KB | Tuya SDK crypto algorithm implementations |
| `libthingmmkv.so` | 512 KB | Tuya's MMKV (Tencent's fast key-value store) bundled for Tuya SDK local storage |
| `libVisionCamera.so` | 276 KB | react-native-vision-camera (used for the photo-based AC model recognition feature, see [Cloud API](cloud-api.md)'s `/models/ai/recognize/`) |
| `libreactnative.so` | 5.7 MB | React Native's own native runtime |
| `libhermes.so` | 2.1 MB | Hermes JS engine |
| `libhermestooling.so` | 134 KB | Hermes debugging/inspector tooling |
| `libjsi.so` | 382 KB | React Native's JS-to-native interface |
| `libworklets.so` | 841 KB | react-native-reanimated worklets runtime |
| `libreanimated.so` | 1.4 MB | react-native-reanimated |
| `libnetwork-android.so` | 2.3 MB | Facebook's native networking stack (Fresco/okhttp-adjacent) |
| `libreact_codegen_*.so` (4 files) | ~1.8 MB total | Codegen'd native modules for RNCSlider, rnscreens, rnsvg, safeareacontext |
| `librnscreens.so`, `libgesturehandler.so` | 101 KB, 38 KB | react-native-screens / react-native-gesture-handler |
| `libgifimage.so`, `libimagepipeline.so`, `libimage_processing_util_jni.so`, `libnative-filters.so`, `libnative-imagetranscoder.so` | ~1 MB combined | Fresco image-loading pipeline |
| `libfbjni.so` | 177 KB | Facebook's JNI helper library |
| `libdatastore_shared_counter.so` | 7 KB | AndroidX DataStore |
| `libc++_shared.so` | 1.3 MB | Shared C++ standard library |

A `strings`-level sweep of **every** `.so` listed above for URLs/domains
found **nothing beyond generic toolchain/doc banners**
(`android.googlesource.com`, `reactnative.dev/docs`, `perfetto.dev`,
`docs.swmansion.com`) — no additional cloud endpoints anywhere in native
code. This closes the question raised in earlier passes: networking
logic for this app lives entirely in the JS bundle and/or Java/Kotlin
layer, never in native code.

## `assets/` tree (base APK)

| Path | Notes |
|---|---|
| `index.android.bundle` | The Hermes-compiled JS bundle — see [App teardown](app-teardown.md) for how it was parsed |
| `_.as.gree.com.cer`, `_.gree.com.cer` | TLS pinning certs for Gree's cloud domains |
| `cers` | **Resolved finding**: byte-for-byte identical content to `thing_domains_v1/regions` (below) — both are the same base64-obfuscated Facebook SDK network-pinning blob, bundled twice under different paths by two different RN modules that each vendor a copy. Not AC-related, not a separate discovery. |
| `thing_domains_v1/regions`, `thing_domains_v1/pins`, `thing_domains_v1/h2.ca.der` | Despite the "thing" naming (suggesting AWS IoT "Thing"), this is actually Facebook SDK's own TLS-pinning data store, confirmed by the `cers` duplicate above — a naming coincidence, not an AWS IoT artifact. |
| `t_cdc.tcfg` | Tuya SDK's encrypted device-config blob (file magic bytes coincidentally match an OpenPGP key header; it is not one — opaque, proprietary Tuya format, not decodable without Tuya's own key material) |
| `fixed_key.bmp`, `t_s.bmp` | Genuine 100×75 24-bit BMP images per file-format inspection (not steganographically disguised data, as far as a surface check can tell) — likely Tuya SDK placeholder/internal assets |
| `countryList.en.json` | Plain country-list data for phone-number/region pickers |
| `fonts/` | Roboto + "Almoni" (a Hebrew typeface family) weights — confirms Hebrew-market UI design from the font choice alone |
| `com/appsflyer/internal/*` | AppsFlyer SDK's own opaque internal config blobs |
| `dexopt/baseline.prof`, `baseline.profm` | Android Runtime (ART) baseline profiles for startup optimization, unrelated to app logic |

## Third-party SDK identifiers found

These are client-side identifiers embedded in the shipped app binary —
normal for mobile analytics/crash-reporting SDKs (they're not secrets in
the security sense; any app installer trivially exposes them, which is
why vendors design these SDKs to tolerate public client identifiers).
Listed here purely for completeness of the asset inventory:

- **Datadog** client token: `pub5499c62c9617fe3d0ca63247821a9020`. Both
  `datadoghq.com` and `datadoghq.eu` site strings are present (standard
  Datadog SDK default-option strings) — given every other confirmed
  backend element is `eu-west-1`, `datadoghq.eu` is the more likely active
  site, but this wasn't independently confirmed.
- **Mixpanel**, **Firebase**, **AppsFlyer**, **Facebook SDK**, **Emarsys**:
  all present as bundled libraries (consistent with the dependency list
  implied by `app-teardown.md`'s architecture section), but no static
  API key/token/project-ID string was recovered with confident
  attribution for any of them — likely injected via native
  `google-services.json`/Gradle resource values rather than plain string
  literals, or genuinely not present in this build.
- No Google Maps/Places API key (`AIza...` pattern) was found anywhere in
  the dex or JS string pools.

## What this pass closes out

- **Native code confirmed clean of hidden endpoints** — every `.so` in
  the app was swept; nothing beyond public documentation URLs.
- **The `thing_domains_v1` naming red herring is resolved** — it is
  Facebook SDK pinning data, not an AWS IoT Core artifact, confirmed by
  finding byte-identical content under the unrelated `cers` path.
- **BLE provisioning UUIDs remain unrecovered** — `libBleLib.so` almost
  certainly contains them as raw binary GATT UUID bytes rather than
  ASCII string literals; extracting them would need a disassembler pass
  on the library itself, not a strings sweep (out of scope here, since
  this project doesn't implement new-device BLE pairing — see
  [Architecture](architecture.md)'s "explicitly out of scope" section).
