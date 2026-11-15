# The remote/cloud control path — what's known, what isn't, and why Tadirel doesn't use it

Short version: **it's not publicly documented, and Tadirel deliberately
does not reimplement it.** Everything below is the research trail, kept
for reference in case someone wants to pick it up later. A second pass
through the decoded app's JS bundle (see [App teardown](app-teardown.md)
for how the Hermes bytecode was parsed) turned up a much fuller REST API
surface than the first pass found — recorded here.

## Backend architecture (confirmed)

The app's backend is a **hybrid REST + GraphQL + AWS Cognito** stack,
and — new finding — it's a **white-label platform serving more than one
HVAC brand**: the bundle also contains a complete Ferroli onboarding flow
(`FerroliConnectFirstScreen`, `FerroliConnectSecondScreen`,
`ferroliConnectScreen:step1_*`/`step2_*` translation keys). Tadiran's app
is one brand's skin on a shared backend/app platform, not a bespoke
Tadiran-only system.

- **Auth**: AWS Cognito, not a custom login endpoint. Concrete identifiers
  recovered from the app's native (dex) string pool:
  - Cognito User Pool ID: `eu-west-1_WG1VW4YTe`
  - Cognito Identity Pool ID: `eu-west-1:6f339b1c-924e-4e71-a751-d32bfe454e74`
  - Both are `eu-west-1`, matching the AppSync endpoint's region exactly —
    strong confirmation these belong to the same backend. No literal App
    Client ID was found with confidence (one 26-character lowercase
    alphanumeric candidate, `312eed498hlvku8pdup0lvfpir`, sits near
    version-number strings in the pool with no corroborating context —
    treat as unconfirmed, not a finding).
  - No custom `/login`, `/signin`, `/register`, `/otp`, or `/refresh`
    paths exist anywhere in the bundle — consistent with auth being
    handled entirely by the Cognito SDK (SRP login, token refresh,
    `RespondToAuthChallenge`/`AdminRespondToAuthChallenge` are generic AWS
    SDK symbol names also present, not app-specific endpoints).
- **GraphQL (AWS AppSync)**: `https://hz5g3vbxy5h2jhpjclyvzfhiju.appsync-api.eu-west-1.amazonaws.com/graphql`.
  Literal `/graphql`, `/mqtt`, and `/realtime` path strings are all
  present in the bundle, consistent with AppSync's standard real-time
  subscription transport (AppSync multiplexes GraphQL subscriptions over
  an MQTT-over-WebSocket channel). Two literal operations survived
  Apollo/Amplify's codegen compilation (most queries/mutations get
  compiled to AST objects, not kept as text — see "What's still missing"
  below):

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

  Redux-slice identifiers (`deviceDesiredShadow`, `addDesired`,
  `removeDesired`, `desiredList`, `reported`) confirm a **device-shadow**
  pattern: the app writes a "desired" state, something downstream
  reconciles it against the real unit, "reported" state flows back.
- **REST API**: versioned, brand-prefixed base paths, found as literal
  strings:
  - `/tadiran-mobile-app/api/v1`
  - `/tadiran-mobile-app/api/v2`
  - `/mobile-app/api/v1` (brand-generic variant/fallback)
  - `/eu/management/api/v1` (a separate "management" subsystem — likely
    installer/service/warranty tooling, not the consumer app's main
    surface; `activateWarrantyAsyncThunk`, `application-restriction/`,
    and `service/` sit in the same region of the string pool)
  - Host is presumably `api.tadiran-iot.co.il` per the earlier pass, but
    that association wasn't re-confirmed by this pass (the host and the
    path prefixes never appeared adjacent as one concatenated literal).

### REST resource paths (literal strings, high confidence)

These appeared as plain path-segment string literals (not Redux
action-type names — see the caveat below), most with the trailing slash
typical of a REST resource base:

```
/devices/                          /devices/AC/combined-rules/
/devices/create/                   /devices/AC/grouped-commands/
/devices/schedules/                /devices/schedules/all_rooms/
/devices/shabbat_mode/             /devices/timers/
/devices/tips/                     /devices/quick-actions/
/devices/quick-actions/defaults/   /devices/invitations/
/devices/sub-units/invitations/    /sub-devices/
/sub-units/                        /vrf-box/
/groups/                           /shared-users/
/shared-users/invite/              /shared-users/sub-unit/invite/
/invitations/                      /invitations/accept/
/invitations/reject/               /user/
/user/update/                      /user/consumption-history/
/user/consumption-summary/         /user/fcm-token/update/
/self-profile/                     /self-profile/delete/
/manufacturer-token/               /models/
/models/ai/                        /models/ai/recognize/
/models/ai/upload-image/           /smart-ir/
/questionnaire/                    /config/
/test-command/                     /tadiran-email-check/
```

Notable ones:

- `/models/ai/recognize/` + `/models/ai/upload-image/` — the app can
  identify an AC model from a photo (upload an image, get a model match).
- `/smart-ir/` — IR-blaster-based "dumb" AC support, a separate path from
  the WiFi/Gree-protocol device flow this project actually uses.
- `/tadiran-email-check/` — brand-specific (not `/mobile-app-email-check/`),
  confirming the white-label platform namespaces at least some endpoints
  per brand even though most paths are shared.
- `/test-command/` — exists as its own resource, separate from whatever
  the real device-command endpoint is; possibly a connectivity/dry-run
  check.

### Operation inventory (Redux action-type names, lower confidence as URLs)

The bundle is full of `createAsyncThunk`-style Redux Toolkit action names
ending in `AsyncThunk`, each with `/pending`, `/fulfilled`, `/rejected`
suffix variants also present in the pool. These describe **operations**,
not necessarily literal URL paths (a Redux Toolkit thunk's type string is
usually `"sliceName/thunkName"`, and Hermes's string deduplication means
what we see starting with `/` could be the tail half of such a type
string rather than a URL). Treat this list as "operations that exist",
not "endpoints that exist":

```
getDevicesStatusesAsyncThunk        commandDeviceAsyncThunk
commandBulkSubDeviceAsyncThunk      commandGroupDeviceAsyncThunk
commandDeviceCombinedRuleAsyncThunk addDeviceAsyncThunk
addSubDeviceAsyncThunk              updateDeviceAsyncThunk
deleteDeviceAsyncThunk              getDeviceOtaStatusAsyncThunk
getSubDeviceShadowAsyncThunk        getSubDevicesShadowAsyncThunk
discoverVrfBoxDevicesAsuncThunk     getVrfBoxDevicesAsuncThunk
getACModelsAsyncThunk               getACModelBySerialNumber
addUserAsyncThunk                   getUserAsyncThunk
getMyUsersAsyncThunk                deleteUserAsyncThunk
patchUserAsyncThunk                 getSelfProfileDataAsyncThunk
deleteSharedUserAsyncThunk          deleteSharedUserDevicesAsyncThunk
activateDeviceScheduleAsyncThunk    createDeviceScheduleAsyncThunk
deleteSelectedDeviceScheduleAsyncThunk
updateSelectedDeviceScheduleAsyncThunk
getDevicesSchedulesAsyncThunk       getAllRoomsSchedulesAsyncThunk
setSelectedDeviceTimerAsyncThunk    deleteSelectedDeviceTimer
updateSelectedDeviceTimerAsyncThunk getDevicesTimersAsyncThunk
fetchDeviceQuestionnaire            patchDeviceQuestionnaire
fetchConsumptionHistoryAsyncThunk   fetchConsumptionSummaryAsyncThunk
getQuickActionsAsyncThunk           upsertQuickActionAsyncThunk
deleteQuickActionAsyncThunk         signOutAsyncThunk
rateTipAsyncThunk                   getTipsAsyncThunk
setFiltersReminderAsyncThunk        activateWarrantyAsyncThunk
setSmartIRFetchedInfo
```

(Shabbat-mode scheduling — `fetchShabbatTimeDataAsyncThunk`,
`setShabbatModeStatusAndLocationAsyncThunk`, and about a dozen related
thunks — is a real, fairly elaborate feature: AC schedules that respect
Shabbat/holiday timing rules, specific to the Israeli market.)

### Transport/header hints

Literal strings `Authorization`, `x-api-key`, `Content-Type`, `BASE_URL`,
`baseURL`/`baseUrl` all exist in the bundle. These are generic HTTP client
symbol names (the kind any fetch/axios-based API client would reference),
not proof of specific header *values* — no actual API key or bearer token
format was recovered.

## What's still missing

- The actual **command** request/response shape: which REST path takes
  the Gree protocol command, what JSON body it expects (raw `Pow`/`Mod`/
  `SetTem`-style keys? Tuya-style `{"code": ..., "value": ...}` DPs, given
  the app also bundles Tuya's SDK? Something else entirely?), and what
  HTTP method it uses. `/test-command/` and `commandDeviceAsyncThunk`
  exist, but their payload format wasn't recoverable from static strings.
- The GraphQL **mutation** that writes to the device shadow (the
  write-side of the shadow pattern) — not found as a literal string;
  almost certainly compiled to an AST object by Apollo/Amplify codegen
  rather than kept as text, same as most other GraphQL operations here.
- Request authentication details beyond "it's Cognito" — no App Client
  ID confirmed, no observed token format, no confirmation of whether REST
  calls carry a Cognito ID token, access token, or an AppSync-style API
  key via `x-api-key`.
- Whether commands reach the unit via Gree's own cloud
  (`grih.gree.com` and regional variants, `*.dis.gree.com`, bundled as
  TLS-pinned hosts — see [App teardown](app-teardown.md)), via the
  vendor's own Lambda-behind-AppSync/REST layer, or some hybrid of both.

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
  portal, nothing indexed, despite now having a much fuller picture of
  its URL surface than a typical "zero public footprint" API would
  suggest existed.

## Why Tadirel doesn't chase it further

1. It would still require capturing live HTTPS traffic from the real app
   (mitmproxy + Frida SSL-unpinning on a rooted/emulated device) to see
   actual request/response bodies — the path *names* are now known, but
   not a single full request/response pair, auth header, or payload shape.
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

Now that real path names exist, the lowest-risk next static step (still
short of live traffic capture) would be probing which of these paths
resolve on `api.tadiran-iot.co.il` with an unauthenticated `OPTIONS` or
`GET` request (e.g. `/config/` sounds like exactly the kind of endpoint
an app would call *before* authenticating, to fetch its own AWS Amplify
config — which would hand over the App Client ID this pass couldn't
confirm). Beyond that, the concrete next step is still: install the app
on a device you can MITM (or an emulator + Frida), trigger a real "send
command" action while on mobile data (not WiFi, to force it through the
cloud path rather than Tadirel's own LAN path), and capture the actual
request. Once you have one real request, the bind-time local key (see
[LAN protocol](lan-protocol.md)) is worth testing as a decryption key for
any encrypted payload field in that request/response — the local and
cloud paths plausibly reuse the same per-device key for their respective
`pack`-style payloads, though this is **unverified speculation**, not a
confirmed finding.
