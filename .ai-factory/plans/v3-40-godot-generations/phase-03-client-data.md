# Phase 3: Read-only Godot data and session integration

Plan: [index.md](index.md)  
Tasks: 6–8  
Depends on: Tasks 2, 3 and 5

## Objective

Consume backend demographic/lineage projections with strict identity, cursor, authorization and source-replacement handling before adding visual controls.

## Current-Code Evidence

| Path | Symbols / section | Why it matters |
|---|---|---|
| `clients/godot-observer/scripts/protocol/models.gd` | `AgentModel`, `_agent`, `parse_frame` | Existing frame mirror remains unchanged; new sidecars need separate parsers. |
| `clients/godot-observer/scripts/protocol/urls.gd` | `_build`, `build_get` | GET-only and query allowlist; currently silently drops lineage parameters. |
| `clients/godot-observer/scripts/net/http_client.gd` | `get_json`, `_on_completed` | Currently accepts dictionary JSON only and drops error envelopes; `/lineage/families` is an array. |
| `src/api/security.py`, `clients/godot-observer/scripts/net/session.gd` | `_configured_secret`, `_start`, `_token` | Inspection/debug credentials may differ; current session sends one ProjectSettings token everywhere. |
| `clients/godot-observer/scripts/net/session.gd` | `_request_path`, `_request`, `_on_http`, `_http_epoch`, `_seek_serial`, `_teardown_source` | Existing stale-response protection and non-observer route seam. |
| `clients/godot-observer/tests/test_session_switch.gd` | session reset tests | Protects run/source replacement. |
| `clients/godot-observer/tests/run_protocol.gd` | `SUITES` | Every new GDScript suite must be registered. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `clients/godot-observer/scripts/protocol/demographics.gd` | create | Typed sidecar parsers. |
| `clients/godot-observer/scripts/protocol/lineage.gd` | create | Qualified refs, coverage, graph/catalogue/participant parsers. |
| `clients/godot-observer/scripts/protocol/urls.gd` | modify | Preserve allowed lineage pagination/scope parameters. |
| `clients/godot-observer/scripts/net/http_client.gd` | modify | Explicit object/array response shape and safe structured errors. |
| `clients/godot-observer/scripts/net/generational_source.gd` | create | Bounded request/result state owned by a session. |
| `clients/godot-observer/scripts/net/session.gd` | modify | Sidecar orchestration and reset guards. |
| `clients/godot-observer/scripts/ui/credentials_panel.gd`, `clients/godot-observer/scenes/ui/credentials_panel.tscn` | create | Browser-accessible memory-only inspection/debug credential entry before bootstrap. |
| `clients/godot-observer/scenes/ui/ui_layer.tscn`, `clients/godot-observer/scripts/main.gd` | modify | Top-level Credentials control and session binding, independent of selected agent. |
| `clients/godot-observer/tests/test_generational_http.gd` | create | Array/object/error transport and credential header routing. |
| `clients/godot-observer/tests/test_demographic_models.gd` | create | New schema tests. |
| `clients/godot-observer/tests/test_lineage_models.gd` | create | New lineage parser tests. |
| `clients/godot-observer/tests/test_generational_session.gd` | create | Stale response, auth and request tests. |
| `clients/godot-observer/tests/run_protocol.gd` | modify | Register suites. |
| `clients/godot-observer/fixtures/protocol/generational/` | create text fixture files | Server-produced sidecars and lineage responses, no generated export. |

## Task 6: Parse sidecar projections and preserve lineage query parameters

### Intent

Treat demographic and lineage responses as explicit backend facts; do not turn the frame reducer into a second demographic or genealogy engine.

### Implementation Steps

1. Add independent parser classes for `observer-demographics-v1`, `observer-generation-markers-v1`, existing lineage family/snapshot/node/graph/availability envelopes, and `lineage-participants-v1`. Validate expected type, nonnegative exact integer counts/ticks (reject booleans), nullable fields, stable refs, schema identifier and required scope fields.
2. Preserve graph node keys as opaque strings. Validate edge endpoint presence in page nodes/context, maintain matched/context-only distinction, and never hash/reconstruct qualified identities in Godot. Deduplicate repeated nodes/edges by server keys only within the same snapshot/scope.
3. Extend `ObserverUrls` allowed query names with `evidence_class`, `owner_id`, `boundary_tick`, `native_kind`, `native_id`, `root_key`, `direction`, `max_depth`, `max_nodes`, `max_edges`, `living_only`, `after`, `include_restricted`, `role`, `section`, `after_agent_id`, `after_group_key`, `after_generation_index`. Use existing `agent_id`, `tick`, window and limit keys. Encode opaque cursor strings once. Keep GET enforcement and no-secret-query behavior unchanged.
4. Extend `http_client.gd.get_json(url, request_id, token, expected_root="object")` with an explicit `object|array` response-shape selector; retain the current three-argument default for all V2 callers. Only the lineage families request uses array. On non-2xx, inspect a bounded JSON error envelope for its stable `code` (matching existing API error schema); pass through only a recognized safe code plus HTTP status, never the raw message/body. Distinguish missing credential401, debug-disabled403, missing run/root404, expired/gone410, and lineage-disabled/corrupt503 in the new source without changing the base observer's existing fatal-error policy. Invalid shapes/scalars/malformed JSON produce `invalid_json`; a200 lineage availability envelope remains a successful object response.
5. Produce fixtures from Python API responses built in Tasks2/3/5 and existing lineage tests. Check fixtures into the first-party protocol fixture tree with source run/boundary/evidence annotations in a text README. Include the actual array family response, safe error objects, absent/disabled/partial/complete-empty responses and paged demographic sections.

### Required Interfaces and Contracts

Existing frames still parse without sidecars; unknown new sidecar schemas fail as unavailable without disconnecting the base observer. Do not add demographic state to the objective event reducer. No new network verbs, localhost defaults, SDKs or Godot extensions.

### Requirement Evidence

User request — all lineage from backend, preserved V2 observer. `docs/lineage-explorer.md` — opaque scoped identity and pagination. Existing `ObserverUrls` GET-only contract.

### Error Handling and Logging

Malformed sidecars emit bounded `demographics_invalid`/`lineage_invalid` reason codes and clear only that panel. DEBUG schema/count/status; never dump response dictionaries, cursor strings, credentials or content keys.

### Tests

Round-trip server fixtures; legacy frames; malformed schema/null/boolean counts; repeated context nodes; two owners with same native ID; missing endpoints; empty availability envelopes. Exercise the HTTP adapter itself with array/object/scalar bodies, malformed JSON, real error-envelope shape and401/403/404/410/503 status mapping; parser-only tests are insufficient. URL tests assert every selector survives encoding, `after` differs from event resume pair, no token query parameter is permitted, and POST remains rejected.

### Acceptance Criteria and Verification

Run the pinned two-pass Godot suite listed at the end of this phase. Expected: fixtures parse and requests preserve exactly the intended scope/query; no local lineage inference appears.

## Task 7: Fetch demographic pages and marker windows for the displayed cursor

### Intent

Keep live/replay demographic overlays synchronized without updating stale generations after a seek, reconnect, or branch switch.

### Implementation Steps

1. Add `GenerationalSource` as session-owned request state, invoked through `ObserverSession._request_path` and the existing HTTP adapter. Keep separate request serials for demographics, markers, and lineage. Stamp run, epoch, selected agent, requested tick/sequence, revision, scope, credential generation and panel generation into request metadata.
2. Add a canonical viewed-cursor descriptor derived from each accepted frame, not `transport.tick` alone. If `after_tick` is null, or `frame.world.tick > after_tick`, it is a full boundary at `world.tick`; the last-event resume cursor does not make that frame partial. If `world.tick == after_tick`, it is the partial prefix `(after_tick, after_sequence)`. Reject impossible future-after-tick shapes. Canonical full-boundary demographic requests use `tick=world.tick` without sequence; partial requests use that exact event pair. Private lineage is eligible only for the full-boundary descriptor. A complete prefix with last event at T and world tick T+1 is therefore eligible at T+1.
3. On adopted frame or completed seek invalidate prior sidecars. Fetch the first agents section page at the canonical cursor only when enabled; automatic page size100, explicit Load more. Fetch cohorts/generations only on the selected grouping section, one bounded page per action. Selected-agent inspection uses the exact `agent_id` filter independently of roster pages, so an agent beyond800 cached rows remains inspectable. Cache at most8 roster/group pages and800 agent rows; keep only the current selected-agent row outside that cache. Missing rows show loading/unavailable, never generation0. Echoed section and selected ID must match the request before application.
4. Markers use full boundary B as high-water; during a partial prefix at T they use the full start boundary T. Fetch one marker page on enable/window change; explicit Load more, maximum200 retained marks, visible truncation. Never scan historical events to guess generations.
5. Debounce frame notifications into one outstanding request per sidecar kind. On every newly applied live event, immediately mark accepted demographic summaries/badges stale and clear cursor-sensitive private lineage; do not issue a prefix replay request per streamed event. Refresh after the next accepted state frame, discarding obsolete replies without blocking base rendering. On reconnect/source replacement/branch switch clear pages, counts, markers, errors and pending requests. Test slow HTTP while ticks keep arriving; stale replies must not trigger an unbounded request queue.
6. Require response run, exact requested cursor, resolved tick/revision, section, selection and request generation to match the viewed descriptor before application. Marker responses match their pinned high-water. Retained older data must visibly say stale/loading; never display it as current.
7. Add `ObserverSession.configure_credentials(inspection_token, debug_token)` and `forget_credentials()`, using two independent in-memory values. Preserve legacy `palimpsest/api_token` only as the initial inspection fallback; `_start()` must not overwrite runtime-entered values. Add a top-level Credentials panel with masked LineEdits, Apply/Reconnect and Forget, accessible before any manifest succeeds and without agent selection. Clear input text after Apply, never persist either secret in `ProjectSettings`, files, browser storage, query strings, export assets or logs. Validate header-safe shape/length. Bind credentials to origin; origin change/Forget clears both. Same-origin branch switching may retain credentials but clears response state/cursors. Changing a credential increments its generation, clears queued old requests and corresponding private state; in-flight responses with old generations are ignored. Inspection replacement reconnects the objective stream; debug-only replacement does not restart the objective socket.
8. Route objective demographics/markers/genealogy and ordinary frame/stream requests with the inspection credential. Use debug credential only for subjective/analytical lineage and restricted family discovery; do not try debug as an inspection fallback or vice versa. Pass an explicit closed request capability in `_request_path` metadata and choose the header token at enqueue time. Families discovery can use objective-only mode without debug. Missing debug credentials keep private controls restricted without breaking objective playback. The existing HTTP client owns only a short-lived queued header value and drops it on completion/clear.

### Required Interfaces and Contracts

No demographic network request while all demographic controls are disabled. Credential entry remains available in a published browser export; no local editor/export rebuild is required to authenticate. View cache is presentation-only. Historical seek never resumes a subjective runtime. A404 on a new endpoint against an older backend disables that feature while preserving V2 playback; distinguish it from a known endpoint's coded run/root miss.

### Error Handling and Logging

403 means restricted, 404 unsupported/missing as coded, 409 ahead cursor means wait/refetch after frame, malformed payload means unavailable. Do not busy-loop. INFO source clear/feature availability; DEBUG request counts/cursor/stale-reply reasons; safe metadata only.

### Tests

Out-of-order replies; source switch with same IDs; backward seek; normal full frame carrying a resume pair; genuinely partial prefix; complete last-event prefix; eventless full boundary; live event invalidation before state refresh; advancing live head during pagination; selected agent beyond cache; group pagination; off-state zero requests; old backend404; cache/queue caps. Test distinct inspection/debug secrets with auth required, runtime entry before bootstrap, debug-only replacement, queued/in-flight old-secret replies, origin change and Forget. Assert correct headers without exposing secrets in recorded diagnostics, screenshots or request URLs; no polling loop or mutation URL.

### Acceptance Criteria and Verification

Pinned Godot suite: request logs show exact cursor and GET-only paths; stale replies never alter displayed population, markers or labels.

## Task 8: Fetch on-demand genealogy, mentorship and knowledge projections

### Intent

Selecting an agent provides scoped lineage navigation only when requested; missing capture is a first-class outcome.

### Implementation Steps

1. Add source methods `request_genealogy(agent_id, direction)`, `request_participants(agent_id, role, evidence_class, owner_id)`, `request_knowledge_root(native_kind, native_id, evidence_class, owner_id)`, and `load_more_lineage`. All use `_request_path` with encoded path segments and safe query parameters.
2. Genealogy: discover family support, resolve `nodes` with `native_kind=agent`/selected `agent_id`, then request `traverse` with returned `ref.key`, direction ancestors/descendants, depth1, max nodes100/edges200, page size100. Offer explicit deeper exploration depth up to4; do not silently turn the direct parents/children panel into an ancestor list. Only direct server `parent_of` edges fill parents/children.
3. Participants: use new endpoint with explicit role and selected agent. Default subjective owner is the selected agent, not all owners. Offer analytical scope as a separate debug-gated control. Mentorship bonds use existing `mentorship` `nodes`/`traverse` responses; preserve the server role/status and owner on every edge.
4. Knowledge: catalogue/traverse the existing `knowledge` family under explicit scope using returned native refs/keys. Participant content cards link to their `mentorship_entry` lineage; no content-key-to-knowledge-ID guess. Present empty/unresolved links as such. An explicit knowledge node selection can navigate its `held_by`, `acquired_from`, and `knowledge_parent` server edges without claiming every source is a teacher.
5. Use Task7's canonical viewed-cursor descriptor. For a full boundary B request exactly B, even when the frame carries a last-event resume pair. At a genuinely partial prefix clear private lineage and display `finalized_boundary_required`; offer only an explicit earlier captured-boundary selection, labeled separately. Snapshot catalogue browsing is a GET with the scope-appropriate credential and opaque cursor; never silently substitute latest. Keep requested/captured tick displayed.
6. Limit one in-flight lineage request per panel; one page on demand, explicit Load more; cumulative client cap500 nodes/1000 edges/200 participant cards. Show cap/stop reasons. Cache scope + publication ID/digest; a new publication or any scope/owner/run/selection change invalidates pages/cursors. On 410 clear cursor and require explicit restart, not replay of a mismatched continuation.

### Required Interfaces and Contracts

Credentials use Task7's capability-specific in-memory routing over existing header/subprotocol transport. The client may display multiple evidence classes but never merge their identities/graphs. Debug denied/disabled, capture disabled, complete-empty, partial, missing boundary, truncated, unresolved root and corrupt service remain distinct states. No client file access, raw ledger endpoint, API write, automatic capture, or generation-based kinship construction.

### Error Handling and Logging

401/403 clear restricted data and disable private controls until credentials change. 503 keeps base playback alive. Repeated cursor or page identity mismatch stops pagination with safe reason. DEBUG family/class/counts/request generation; no response payload, cursor, or credentials.

### Tests

GET chain including array-valued family discovery, snapshot catalogue, native root lookup and traversal; direct parent filtering; learner participants beyond the first physical catalogue page; same local IDs across owners; mixed evidence never merges; missing capture; exact-boundary miss; private partial-prefix refusal and complete-prefix allowance; stale selected-agent/credential response;410 explicit restart; repeated/non-progressing cursor; context dedup/caps; inspection and debug credentials intentionally different with protected objective APIs.

### Acceptance Criteria and Verification

`"${GODOT_BIN}" --headless --editor --path clients/godot-observer --quit`

`"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd`

Expected: `godot_protocol_tests failed=0` using the pinned 4.7.2-stable executable. These are contributor/CI commands, never an end-user prerequisite.

## Phase Risks and Mitigations

- URL allowlist silently loses new parameters: assert complete encoded URLs in request tests.
- Private data survives source replacement: one reset path clears models, credentials-derived state and cursors; test run/branch/owner/selection changes.
- Historical subjective evidence is sparse: explicit boundary and availability chrome, no live-state fallback.

## Phase Completion Checklist

- All new suites are registered and pass the pinned two-pass test sequence.
- Base observer works against legacy backend responses.
- Update progress only in `index.md`.
