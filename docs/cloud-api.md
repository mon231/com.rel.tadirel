# The remote/cloud control path — what's known, what isn't, and why Tadirel doesn't use it

Short version: **it's not publicly documented, and Tadirel deliberately
does not reimplement it.** Everything below is the research trail, kept
for reference in case someone wants to pick it up later.

## What's confirmed to exist

- The official app's own backend: `https://api.tadiran-iot.co.il` (no
  public DNS/API docs found for it).
- An AWS AppSync GraphQL endpoint:
  `https://hz5g3vbxy5h2jhpjclyvzfhiju.appsync-api.eu-west-1.amazonaws.com/graphql`,
  used with AWS Amplify + Cognito auth (identity + idp endpoints for every
  AWS region are bundled in the app, standard Amplify boilerplate).
- Two literal GraphQL operations recovered from the app's JS bundle (see
  [App teardown](app-teardown.md) for the full documents): a `LastData`
  query and an `UpdatedShadow` subscription, both keyed by `asset_id`.
  Redux-slice names (`deviceDesiredShadow`, `addDesired`, `removeDesired`,
  `desiredList`, `reported`) strongly imply a **device-shadow** pattern:
  the app writes a "desired" state, something downstream reconciles it
  against the real unit, and "reported" state flows back — classic IoT
  shadow design (same idea as AWS IoT Device Shadow, though this looks
  like a custom implementation on top of AppSync, not the actual AWS IoT
  Device Shadow service).
- Gree's own cloud infrastructure is referenced too: `grih.gree.com` and
  seven regional variants, `*.dis.gree.com` (discovery/routing),
  `*.as.gree.com`, with bundled TLS pinning certs for `gree.com` domains
  (full hostname list in [App teardown](app-teardown.md)).

## What's missing

- The actual **mutation** that sends a command (the write-side of the
  shadow pattern) was not found as a literal string anywhere — GraphQL
  queries/mutations built with Apollo/Amplify codegen are often compiled
  to AST objects at build time rather than kept as literal query text,
  which is almost certainly what happened here (only two operations
  happened to survive as plain strings).
- No login/auth flow details (Cognito user pool IDs, client IDs, how an
  app account maps to a Gree cloud account if at all).
- No confirmation of whether commands actually reach the unit via Gree's
  cloud, via the vendor's own Lambda-behind-AppSync layer, or some
  hybrid.
- The app's native Gree crypto library has no literal URL/path strings in
  it at all — if it contains cloud-protocol logic, the strings are either
  built at runtime or it's purely the crypto primitives for the *local*
  protocol (more likely, given its tiny size).

## Public reverse-engineering landscape

Checked for existing community work on Gree's cloud API specifically:

- The LAN protocol is thoroughly documented and has multiple independent
  open-source implementations (see [LAN protocol](lan-protocol.md)).
- The cloud/remote protocol is **not**. Multiple long-running Home
  Assistant / SmartThings / openHAB community threads about Gree
  integrations explicitly say the cloud side is essentially undocumented
  ("pretty hard to get any documentation for the EWPE/gree.com cloud").
  No public `openapi.gree.com`, no public OAuth flow, no community client
  library for it exists, unlike the LAN side.
- The vendor's own IoT backend has zero public footprint — no developer
  portal, nothing indexed.

## Why Tadirel doesn't chase it further

1. It would require capturing live HTTPS traffic from the real app
   (mitmproxy + Frida SSL-unpinning on a rooted/emulated device) to see
   actual request/response bodies — meaningfully more effort than what's
   already been extracted statically.
2. Even captured, it'd depend on Cognito-issued, presumably short-lived
   auth tokens tied to a real account — fragile to reimplement and
   maintain compared to the LAN protocol, which needs no account at all.
3. It is **not** demonstrably "open and free to use" the way the LAN
   protocol is — nothing here confirms the vendor's actual terms bless
   third-party reimplementation of their private cloud API.
4. The actual goal — "control my own AC, including from outside my
   house" — is fully achievable by tunneling into the LAN (Tailscale/
   WireGuard) and using the local protocol, with none of the above risk.
   That's the path Tadirel takes; see [Architecture](architecture.md).

## If someone wants to pick this up anyway

The concrete next step would be: install the app on a device you can MITM
(or an emulator + Frida), trigger one "send command" action while on
mobile data (not WiFi, to force it through the cloud path), and capture
the GraphQL mutation body + headers. Once you have one real request, the
bind-time local key (see [LAN protocol](lan-protocol.md)) is worth testing
as a decryption key for any encrypted payload field in that
request/response — the local and cloud paths plausibly reuse the same
per-device key for their respective `pack`-style payloads, though this is
**unverified speculation**, not a confirmed finding.
