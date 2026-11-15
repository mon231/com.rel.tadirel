# The Gree "Gree+" LAN protocol (what Tadirel actually uses)

This is the open, community-documented protocol spoken by the AC's WiFi
module over your local network. It needs no account, no internet, and no
vendor server — just UDP connectivity to the unit on your subnet.
Tadirel's backend talks this protocol via the `greeclimate` PyPI library
(the same one Home Assistant's `gree` integration uses).

References: `tomikaa87/gree-remote`, `cmroche/greeclimate`.

## Transport

- UDP, port **7000** on the AC's WiFi module.
- Every message is a JSON object. Most messages carry an encrypted
  `pack` field (base64 AES ciphertext of another JSON object) plus
  envelope fields:

  ```json
  {"t": "pack", "i": 0, "uid": 0, "cid": "<mac>", "tcid": "",
   "pack": "<base64 AES ciphertext>"}
  ```

  (bind/scan requests use `"i": 1` and a fixed "generic" key; everything
  after binding uses `"i": 0` and the per-device key returned by bind.)

## Message flow

1. **Scan** — broadcast (or unicast) `{"t": "scan"}` to `255.255.255.255:7000`
   (or a specific IP). Any unit on the network replies with its identity
   (`pack.t == "dev"`), containing at least `cid` (MAC), `mac`, `name`,
   `brand`, `model`, `ver`, `mid` — encrypted with the **generic** key.
2. **Bind** — send a bind request (`pack.t == "bind"`, containing `mac`),
   encrypted with the generic key. The unit replies
   (`pack.t == "bindok"`) with a **device-specific key** — this is the
   "local key" value Tadirel reports after binding. All further messages
   to that unit use this key instead of the generic one.
3. **Status** — send `{"t":"status", "cols":["Pow","Mod","SetTem",...]}`
   (encrypted). Reply `pack.t == "dat"` contains `cols` + `dat` (parallel
   arrays) with current values.
4. **Command** — send `{"t":"cmd", "opt":[...names...], "p":[...values...]}`
   (encrypted). Reply `pack.t == "res"` echoes back the applied values.

There is no persistent "connection" — it's simple request/reply UDP.
Replies arrive asynchronously (via the OS socket's receive callback), so
code that sends a request and immediately reads local state without
waiting a beat will see nothing (`greeclimate`'s `send()` explicitly
documents "completion does not imply a reply" — see
[Library notes](library-notes.md)).

## Keys and ciphers

Two cipher variants exist in the wild (`greeclimate` tries V1, falls back
to V2 automatically):

- **CipherV1** — AES-128-**ECB**, PKCS7 padding. Generic/default key used
  for scan+bind: `a3K8Bx%2r8Y7#xDh` (ASCII, 16 bytes). This is the
  well-known public "Gree generic key" published by every open-source
  Gree project; it is **not secret** and is the same across every
  Gree-protocol device worldwide — it isn't tied to any individual unit
  or account, it's a shared bootstrap key the protocol uses before a
  per-device key is negotiated.
- **CipherV2** — AES-128-**GCM**. Some newer firmware/WiFi modules only
  speak this even for the initial scan reply. Fixed values observed in
  the library/protocol: generic key `{yxAHAY_Lm6pbC/<` (16 bytes), GCM
  nonce `54 40 78 44 49 67 5a 51 6c 5e 63 13` (12 bytes), and additional
  authenticated data (AAD) `qualcomm-test`.

The per-device key obtained at bind time replaces the generic key for
everything after binding, under whichever cipher version the unit
actually negotiated. This per-device key is **not secret either** in any
meaningful sense — it's handed to any client on the LAN that completes
the public bind handshake with the unit; it just scopes subsequent
messages to that one device rather than authenticating a user.

## Property keys (`Props` in `greeclimate.air_conditioner`)

These are the literal JSON keys sent/received in `cols`/`opt` and `dat`/`p`.
Confirmed present as literal strings in the official Tadiran app's own
binary for at least `Pow`, `Lig`, `Tur` (see [App teardown](app-teardown.md))
— strong direct evidence Tadiran units speak this exact protocol, not just
"something Gree-like".

| Key              | Meaning                          | Values |
|------------------|-----------------------------------|--------|
| `Pow`            | Power                              | `0` off / `1` on |
| `Mod`            | Mode                                | `0` auto, `1` cool, `2` dry, `3` fan, `4` heat |
| `SetTem`         | Target temperature                 | integer, see `TemRec`/`TemUn` below |
| `TemUn`          | Temperature unit                   | `0` Celsius, `1` Fahrenheit |
| `TemRec`         | Temperature "recommend" bit        | fine-grained encoding alongside `SetTem` for half-degree F precision; `greeclimate` manages this automatically |
| `TemSen`         | Current temperature sensor reading | integer, decoded via `TemRec`/`TemUn` |
| `WdSpd`          | Fan speed                          | `0` auto, `1`–`5` (low→high) |
| `Air`            | Fresh air / "Air" valve            | `0`/`1` |
| `Blo`            | X-Fan (blow residual moisture out after cooling/dry) | `0`/`1` |
| `Health`         | Anion/health/ionizer               | `0`/`1` |
| `SwhSlp`         | Sleep mode                         | `0`/`1` (paired with `SlpMod`) |
| `SlpMod`         | Sleep mode (secondary flag)         | `0`/`1` |
| `Lig`            | Display light / LED                | `0`/`1` |
| `SwingLfRig`     | Horizontal swing / louver position  | integer enum (unit-dependent) |
| `SwUpDn`         | Vertical swing / louver position    | integer enum (unit-dependent) |
| `Quiet`          | Quiet mode                          | `0` off, `2` on (not `1` — `greeclimate` encodes this) |
| `Tur`            | Turbo mode                          | `0`/`1` |
| `StHt`           | Steady heat (8°C heating)            | `0`/`1` |
| `SvSt`           | Power save mode                     | `0`/`1` |
| `HeatCoolType`   | Unknown/unused heat-cool type flag   | present in some firmware, not exposed via a `greeclimate` setter |

Valid target temperature range (Celsius): **8–30 °C**.

## Confirmed working live

Scanned a real home LAN and found 4 real units (all `mid=10001`, UDP port
7000). Round-tripped a real status read and a real power on→off cycle
against one of them — bound, read status (power/mode/target+current
temp/fan speed), toggled power on, verified via a second status read, then
restored it to its original state.
