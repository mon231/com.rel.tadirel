# Tadirel — research notes

This is the knowledge base behind **Tadirel**, a from-scratch client
(backend + desktop app + Android app) that controls Tadiran/Gree air
conditioners **locally over LAN**, built by reverse-engineering the
official Tadiran consumer app and the public Gree AC protocol.

!!! note "Not tracked in git"
    This `docs/` folder is a local research reference only — it is
    gitignored and never committed. It exists so this knowledge survives
    between sessions without putting reverse-engineered protocol details
    in the project's git history.

## Map

- **[App teardown](app-teardown.md)** — what's inside the official app:
  bundled vendor SDKs, native libraries, permissions, how it's built.
- **[LAN protocol](lan-protocol.md)** — the wire protocol actually used to
  talk to the AC's WiFi module (UDP port 7000, AES-encrypted JSON). This
  is the protocol Tadirel's own backend uses.
- **[Cloud API](cloud-api.md)** — what is and isn't known about the
  remote/cloud control path. Short version: not publicly documented, not
  reimplemented here.
- **[Architecture](architecture.md)** — design of Tadirel's own
  backend/desktop/Android apps.
- **[Library notes](library-notes.md)** — quirks found in the
  `greeclimate` PyPI package while building against real hardware.

## tl;dr for someone who just wants to control their AC

1. Your AC units are already on your home WiFi (bound once via the
   official app or the unit's own setup flow — Tadirel does **not** redo
   WiFi/BLE pairing, only talks to units already on the network).
2. Each unit listens on UDP port 7000 and speaks Gree's open, community
   documented "Gree+" LAN protocol — AES-encrypted JSON packets, no cloud
   account needed, nothing proprietary to Tadiran.
3. Tadirel's backend scans your subnet for these units, lets you name
   them, and sends them commands (power, mode, temp, fan, swing, light,
   turbo, etc).
4. The desktop app (Eel-based) and Android app (Chaquopy-based) are thin
   UIs over that one shared backend.
5. Everything only works on the same LAN/subnet as the AC units. For
   control from outside the house, tunnel into the LAN (Tailscale/
   WireGuard) rather than going through Tadiran's undocumented cloud —
   see [Cloud API](cloud-api.md) for why.

## Confirmed hardware/software facts

- Tadiran-branded AC units sold with the official app are **rebranded
  Gree hardware**. The app's native AC-control layer is literally Gree's
  own `com.gree.greeplus.sdk` library (unobfuscated class names found in
  the app's bytecode) plus a native `libgree.so`.
- The wire protocol property keys found in the app binary (`Pow`, `Mod`,
  `SetTem`, `WdSpd`, `Lig`, `Tur`, `SwingLfRig`, `SwUpDn`, `Blo`, `Health`,
  `SwhSlp`, `StHt`, `SvSt`, `TemUn`, `TemRec`) are **byte-for-byte
  identical** to the public, community reverse-engineered Gree LAN
  protocol (`tomikaa87/gree-remote`, `cmroche/greeclimate`), which is what
  Tadirel's backend uses.
- Live-verified: 4 real units discovered and controlled on a home LAN —
  scan, status read, and a real power/light on→off round trip all
  confirmed against actual hardware.
