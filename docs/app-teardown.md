# App teardown — official Tadiran consumer app

Target: the official Tadiran air-conditioner control app for Android,
analyzed at a recent release (React Native, Hermes engine, `targetSdk`
35-class build). Specifics below describe the app at the time of this
research; app updates may change any of it.

## Method

- Decompiled the Android package with **jadx** for class listing and
  resource IDs.
- Decoded the binary `AndroidManifest.xml` with **androguard**
  (`androguard.core.axml.AXMLPrinter`) to read permissions and components.
- Extracted every literal string from `classes*.dex` to find class names,
  URLs, and protocol constants.
- The React Native JS bundle is compiled **Hermes bytecode**, not plain
  JS text — a plain `strings` dump over it merges adjacent string-table
  entries with no delimiter and produces garbage. **hermes-dec** (PyPI, by
  P1Security) parses the bytecode properly and exposes a clean, correctly
  delimited string list:

  ```python
  from hermes_dec.parsers.hbc_file_parser import HBCReader

  with open("index.android.bundle", "rb") as f:
      reader = HBCReader()
      reader.read_whole_file(f)
  # reader.strings -> list[str], tens of thousands of entries
  ```

  !!! note "Tooling gotcha"
      `hbctool` (another PyPI Hermes disassembler) only supports older
      bytecode versions and fails outright on recent Hermes builds.
      `hermes-dec` handles the current version fine.

## App architecture

React Native app packaged as a standard Android/Gradle project, bundling
**two** third-party vendor SDKs for device control:

### 1. Gree's own SDK — `com.gree.greeplus.sdk.*`

This is the one that matters for AC control. Class names are **not
obfuscated** — this is a third-party AAR dropped in whole:

- `GreePlusSdk` — top-level SDK entry point.
- `Interface/IDeviceManager`, `Interface/IAPIManger`,
  `Interface/OnAPIRequestListener`, `Interface/OnModDevListener`,
  `Interface/OnScanDeviceListener`, `Interface/OnSocketListener`,
  `Interface/OnUnBindHomeDevListener`, `Interface/LinkConfigListener`,
  `Interface/GreeLinkConfigListener`, `Interface/OnWiFiScanListener` —
  cloud API + local device management callbacks.
- `apcfg/IApConfigModel` — classic AP-mode / SmartConfig WiFi provisioning
  (how a brand-new unit gets joined to WiFi the first time).
- `blecfg/BleConfig`, `blecfg/core/BleCommunicator`,
  `blecfg/core/BleScanner`, `blecfg/core/ConnectManager` — BLE-based
  provisioning path (newer units support BLE setup too).
- `bean/BindDeviceBean`, `bean/BindDeviceResultBean`,
  `bean/QueryStateResultBean`, `bean/ModHomeDeviceBean`,
  `bean/ScanDeviceBean`, `bean/SyncHomeDeviceBean`, `bean/UserInfoBean`,
  `bean/WlanInfoPackBean` — the usual bind/scan/query request/response DTOs.
- `util/AESUtil`, `util/AesCbcHelper`, `util/MD5Util`,
  `util/BytesHexStringTranslate` — crypto helpers for the pack protocol.
- `util/BasePackCmd`, `util/DoorCmd` — command-packet builders (`DoorCmd`
  implies the same SDK is reused by Gree for smart locks, not AC-specific).
- `corelib/CoreLib` — likely the JNI bridge into native code.

Literal protocol property-key strings found directly in the string pool
(survived obfuscation because they're JSON keys/data, not identifiers):
`Pow`, `Lig`, `Tur`. These match the Gree LAN protocol exactly — see
[LAN protocol](lan-protocol.md).

A native library `libgree.so` (~340 KB) ships alongside the Java classes.
Its strings show only compiler/toolchain banners — no literal URLs or API
paths, consistent with it being the AES/crypto primitive implementation
rather than the networking layer.

### 2. Tuya's SDK (rebranded "ThingClips") — `com.thingclips.smart.*`

Much heavier footprint than Gree's SDK by string-reference count. The app
sells other smart-home categories under the same account (a `DoorCmd`-
adjacent scope suggests locks/sensors, not just AC). Bundled native libs
include Tuya's link/security/MMKV/Matter-support libraries.

**Not used by this project** — the AC units this research targeted are
confirmed Gree-protocol devices. If a Tadiran AC doesn't respond to a
Gree-protocol UDP scan, it may be on this stack instead (Tuya's
local/cloud protocol is a different, equally-documented ecosystem — see
`tinytuya`/`localtuya`).

### 3. The app's own backend

- `https://api.tadiran-iot.co.il` — the app's own account/device-layer
  backend. No further literal path fragments were found anywhere in the
  binary (login/command endpoints are presumably built at runtime from
  non-literal string concatenation, or live only in obfuscated/minified
  logic not covered by this pass).
- **AWS AppSync GraphQL**:
  `https://hz5g3vbxy5h2jhpjclyvzfhiju.appsync-api.eu-west-1.amazonaws.com/graphql`,
  matched by a validation regex also embedded in the JS bundle:
  `^https:\/\/\w{26}\.appsync\-api\.\w{2}(?:(?:\-\w{2,})+)\-\d\.amazonaws.com\/graphql$`).
  AWS Amplify/Cognito libraries are bundled (`aws-appsync`,
  `aws-appsync-auth-link`, Cognito identity/idp endpoints for every AWS
  region). Two literal GraphQL documents were recovered verbatim from the
  Hermes string table:

  ```graphql
  query LastData($asset_id: String!) {
    lastData(asset_id: $asset_id) {
      asset_id
      data
    }
  }

  subscription UpdatedShadow($asset_id: String!, $shadow_name: String) {
    updatedShadow(asset_id: $asset_id, shadow_name: $shadow_name) {
      asset_id
      shadow_name
      data
    }
  }
  ```

  This confirms the app's own cloud layer uses a **device-shadow
  pattern** (Redux-slice identifiers `desiredList`/`reported`/
  `deviceDesiredShadow`/`addDesired`/`removeDesired` also found in the
  bundle) — commands are likely sent as a GraphQL mutation that patches a
  "desired" shadow document, reconciled downstream against the real unit.
  The actual mutation document was not found as a literal string — see
  [Cloud API](cloud-api.md) for why, and what that means for
  reimplementing it.

- **Gree's own cloud infrastructure** is referenced too: `grih.gree.com`
  and its regional variants `eugrih.gree.com`, `nagrih.gree.com`,
  `hkgrih.gree.com`, `ingrih.gree.com`, `megrih.gree.com`,
  `sagrih.gree.com`, `augrih.gree.com`, `tmpgrih.gree.com` (Gree's "GRIH" —
  Gree Region IoT Hub — cloud servers), plus discovery/routing hosts
  `<region>.dis.gree.com` (e.g. `ru.dis.gree.com`, `au.dis.gree.com`,
  `in.dis.gree.com`, `me.dis.gree.com`, `na.dis.gree.com`, `sa.dis.gree.com`,
  `ts.dis.gree.com`, `eb.dis.gree.com`, `hk.dis.gree.com`) and
  `*.as.gree.com` — bundled as TLS pinning certificates
  (`_.as.gree.com.cer`, `_.gree.com.cer`) and referenced in the native
  string pool. Whether the app actually talks to these directly, or only
  through its own AppSync backend, wasn't determined from static analysis
  alone — that needs live traffic capture.

### Permissions

Notable ones from the app's manifest: `BLUETOOTH`, `BLUETOOTH_SCAN`,
`BLUETOOTH_CONNECT`, `ACCESS_FINE_LOCATION`, `ACCESS_BACKGROUND_LOCATION`,
`NEARBY_WIFI_DEVICES`, `CHANGE_WIFI_STATE`, `CHANGE_WIFI_MULTICAST_STATE`,
`ACCESS_WIFI_STATE`, `CAMERA`, `NFC` — all consistent with BLE/AP-mode
WiFi device provisioning (`CHANGE_WIFI_MULTICAST_STATE` in particular is
needed for UDP broadcast discovery on the LAN protocol).

## Things that were *not* cracked

- Exact REST/GraphQL paths used by the app's own backend, and the real
  "send a command" mutation against the AppSync backend — not present as
  literal strings anywhere in the analyzed build; would require either
  further static work against obfuscated/minified logic, or capturing
  live HTTPS traffic (mitmproxy + Frida SSL-unpinning) while using the
  real app.
- Whether `libgree.so` embeds a second, cloud-facing protocol variant or
  is purely the LAN-protocol crypto helper — no literal endpoint strings
  in the binary either way.
- A full Java decompile of the entire app (tens of thousands of classes)
  was attempted but is extremely slow and wasn't completed/used; all
  findings above came from targeted string extraction plus the Hermes
  bundle parse, not a full source dump.
