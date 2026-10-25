# Phase 3: Scoped queries, client parsing and evidence controls

Plan: [index.md](index.md)  
Tasks: 7–9  
Depends on: Tasks 1–6

## Objective

Read published history through bounded capability-gated APIs and expose optional controls that always show evidence class, time and availability.

## Current-Code Evidence

| Path | Symbols | Consequence |
|---|---|---|
| `src/api/routes/lineage.py` | family/snapshot/query routes | Objective inspection versus subjective-debug scopes, exact boundary and 410 semantics. |
| `src/api/app.py` | `_attach_lineage_service` | Optional read-model service attachment, no analysis imports. |
| `clients/godot-observer/scripts/net/generational_source.gd` | latest-request queuing, append metadata | Preserve existing user edits; use a separate source. |
| `clients/godot-observer/scripts/net/lineage_source.gd` | per-panel queue, coverage parsing | Pinned publication and owner invalidation precedent. |
| `clients/godot-observer/scripts/net/session.gd` | `_adopt_frame`, `_apply_sought_frame`, `_apply_live_event`, credentials | Accepted frame is the authoritative display cursor. |
| `clients/godot-observer/scripts/presentation/evidence_class.gd` | `OVERLAY_CLASSES`, `from_wire` | Existing exact client evidence constants. |
| `clients/godot-observer/scripts/ui/overlay_legend.gd` | `_TOGGLE_ROWS` | Default-off controls, currently weak ordinary-overlay availability display. |

## Files to Change

Backend: extend `src/api/routes/civilization.py`, `src/api/civilization_service.py`, `src/api/civilization_schemas.py`, `src/api/civilization_cursor.py`, `src/api/app.py`; use the Task 6 reader port, not an analysis/publisher dependency.

Client: create `clients/godot-observer/scripts/protocol/civilization.gd`, `scripts/net/civilization_source.gd`, `scripts/ui/civilization_panel.gd`, `scenes/ui/civilization_panel.tscn`; modify `scripts/net/session.gd`, `scripts/main.gd`, `scripts/presentation/evidence_class.gd`, `scripts/ui/overlay_legend.gd`, `scripts/ui/ui_layer.gd`, and the actual scene `scenes/ui/ui_layer.tscn`. Preserve existing `scenes/ui/generational_panel.tscn`/population node and its signal consumers. Modify `scripts/net/http_client.gd` only to add the closed new safe codes; preserve all user transport fixes.

Tests: create `tests/unit/test_civilization_overlay_api.py`, `tests/unit/test_civilization_markers_api.py`; client `tests/test_civilization_protocol.gd`, `tests/test_civilization_source.gd`, `tests/test_civilization_controls.gd`; register them in `tests/run_protocol.gd`.

All client paths above are relative to `clients/godot-observer/` where abbreviated.

## Task 7: Serve exact captured overlay pages and catalogues

### Intent

Make analytical/subjective history available without granting the API analysis or write authority.

### Implementation Steps

1. Add GET `/v1/simulations/{run_id}/observer/civilization/catalogue` with mandatory `evidence_class`, optional `owner_id`, `layer`, `limit`, `cursor`. Scope before loading any counts. Return bounded boundary rows and layer availability; catalogue resolution pins a committed publication ID/digest. Separate calls for objective versus restricted scopes prevent catalogue leakage.
2. Add GET `/v1/simulations/{run_id}/observer/civilization/overlays` with required `tick`, `layer`, `evidence_class`; optional `owner_id`, `location_id`, `region_id`, `entity_id`, `limit`, `cursor`, `publication_id`. `tick` is the exact complete boundary B, not a nearest snapshot. This route rejects `through_sequence` and conflicting location/region filters. Supported combinations are in `index.md`.
3. Require inspection for OBJECTIVE migration rows and subjective-debug (enabled plus credential) for all SUBJECTIVE/ANALYTICAL layers, including aggregates in this new endpoint. This conservative policy does not alter older aggregate metric endpoints. SUBJECTIVE requires owner; ANALYTICAL/OBJECTIVE reject scope owner. Owner provenance inside an analytical row is retained but is not a scope-owner selector.
4. Implement the marker route now so Task8 has its final API contract: GET `/v1/simulations/{run_id}/observer/civilization/markers`, required `evidence_class`, `from_tick`, `to_tick`, optional `layer`, `owner_id`, `publication_id`, `limit`, `cursor`. Window is `[from_tick,to_tick)`, maximum4,096 ticks. Scope/auth/layer combinations match overlays; use Task1 marker DTOs, exact seek boundaries, typed transition reasons and separate missing-interval bands. Return `observer-civilization-markers-v1` from retained Task5 markers, never a future-derived episode summary or client inference. Population/generation context reuses existing demographic marker endpoints; no duplicate civilization birth/generation markers are added.
5. Extend cursor codec with distinct `civilization-catalogue-v1`, `civilization-overlay-v1`, `civilization-markers-v1` purposes. Bind publication ID/catalogue-index digest, run, exact boundary/window, layer, evidence class, owner, all filters, ordering/policy version, limit and last scanned key. Reader follows verified shard indexes; enforce200 returned/2,000 decoded-scanned/1MiB response/16physical-files/12MiB physically read per request, reserving before decode. Stop before an unreserved shard and return continuation, including when no filtered rows matched. Use Task1 nested-row caps; no cross-publication append or unbounded marker-window scan.
6. Availability: root absent → disabled; no run publication/exact boundary/layer → unavailable with closed reason; complete-empty → empty complete; partial → rows with coverage. Invalid/mismatched query/cursor →400; unknown run→404; expired/missing pinned publication→410; corrupt/storage→503. Do not leak a restricted layer's existence before authorization. Reads are no-store and never regenerate/repair/publish.

### Required Interfaces and Contracts

Create `ArtifactCivilizationApiService(reader, codec, run_repository)` with read-only ports. Validate run/world/config identity against the persisted run manifest before accepting a publication. New service does not import experiments, analysis or live runtimes. Publication read and objective map resolved cursors must match world/run/B/revision before a spatial overlay is displayed. Markers, catalogue and overlays share one committed catalogue-index pin; child files contain no cyclic root digest.

### Requirement Evidence

Original Request — evidence separation/history; architecture — analysis/API separation; lineage docs — signed pinned cursors. Verify inspect-only versus debug, exact versus missing boundary, changing source during paging, and malformed owner combinations.

### Error Handling and Logging

DEBUG bounded scan/return counts and safe layer/tick; WARN authorization-neutral error codes. Never raw cursors, publication data, labels, content digests or secrets. Service attach failures leave base objective observation usable; configured corrupt roots report service-unavailable rather than silently disabled.

### Tests

Exercise the real temp filesystem publisher and API reader, not only mocked rows. Use separate inspect/debug credentials; test restricted catalogue metadata/counts; same local ID for two owners; wrong run/config/revision; missing exact boundary; sparse450-row scans; measured file/read/scan/response ceilings; oversized inline details; digest corruption; tamper/expiry/filter change; read-only filesystem and zero publish calls. Marker tests cover exact bounds, empty bands versus confirmed changes, >200markers with continuation, auth, pinning, expiry and future-evidence exclusion.

### Acceptance Criteria and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_civilization_overlay_api.py tests/unit/test_civilization_markers_api.py tests/unit/test_lineage_api.py tests/unit/test_observer_civilization_api.py -q` passes, with no changes to legacy endpoint permissions. All four civilization GET contracts exist before Task8 starts parsing them.

## Task 8: Parse and fetch cursor-pinned civilization layers

### Intent

Prevent stale, cross-owner, cross-run or future overlays from appearing on a different world frame.

### Implementation Steps

1. New `CivilizationProtocol` parser validates all Task 1 envelopes/row unions with closed evidence values, scope, integer ticks, finite numbers, coverage, source windows and typed anchors. Explicit mapping: OBJECTIVE→`OBJECTIVE`; SUBJECTIVE→`SUBJECTIVE_TO_SELECTED_AGENT`; ANALYTICAL→`ANALYTICAL_INFERRED`. Unknown schema/evidence/owner mismatch fails closed and clears that layer.
2. New `CivilizationSource` subscribes to accepted frame and credential changes through session integration. A request key includes source epoch, run/branch, resolved cursor/revision, layer, evidence/owner, filters, publication and debug-credential generation. Generation guards apply to successful and failed replies. Never identify a full boundary from the WS resume pair alone.
3. Default every new fetch off. On toggle, request objective map sections or the scoped catalogue then exact overlay. On explicit seek/run/branch/owner change, immediately clear affected data and supersede in-flight work. Automatic forward play uses a bounded presentation bundle rather than invalidating every request on each timer tick: track one displayed boundary plus one pending target, fetch matching enabled-layer first pages for that target with at most two in-flight civilization requests total, and publish `bundle_ready(cursor, layer_states)` only for its exact cursor. The Task13 scheduler advances automatic display after this bundle is ready or its bounded wait expires; faster desired targets replace only the queued target, not the active request epoch. At expiry missing layers become visibly unavailable for that boundary; late/mismatched data is not painted over a newer frame. Do not issue one request per streamed event. Normal live mode can still clear stale sidecars until its accepted refresh; it is not blocked by private-layer availability.
4. Each layer cache: max 800 rows/eight pages/8MiB canonical decoded content; at most four boundary entries shared across active layers, 32MiB total. Use explicit Load more rather than automatic full-roster fetching. Evict full cache entries deterministically; cache key includes all selectors/credentials generation. At a client cap mark partial/truncated, not complete. Map totals remain server totals.
5. Append only pages matching the exact pinned snapshot and scope; deduplicate row IDs but reject conflicting duplicate contents. Empty page+continuation is not exhaustion. A 410 clears continuation and offers explicit Restart; do not automatically mix in a new latest publication.
6. Live event ahead of accepted state marks civilization layers stale and removes cursor-sensitive overlays; refresh only after an accepted world frame. Prefix frames can fetch objective map state; captured layers show `finalized_boundary_required` until an exact full boundary is accepted. Debug revocation clears all private caches/queues but preserves objective stream and independent inspect credentials.

### Required Interfaces and Contracts

`CivilizationSource` emits `layer_changed(layer_id, state)` and `bundle_ready(cursor, layer_states)`; states include request key, availability/reason, rows/total/coverage, cursor, evidence and source metadata. Add `prepare_bundle(cursor, enabled_layers)` and `cancel_bundle(reason)`. Task8 tests these source primitives without depending on the later playback scheduler; Task13 adds automatic play orchestration. Views receive immutable/copy-detached render inputs. Credentials remain origin-scoped, memory-only, routed by capability; never query strings, local storage or exports. Reuse existing session HTTP adapter rather than bypassing it. Parser tests include the final Task7 marker endpoint, not only overlay pages.

### Requirement Evidence

Original Request — historical state correctness; V3-40 code — accepted-frame/queue/credentials patterns. Test rapid seeks, delayed replies, partial event prefix, selected owner changes and different capability credentials.

### Error Handling and Logging

DEBUG layer/epoch/tick/count/reason; WARN unknown schemas and safe status codes. Respect runtime debug switch; no row dumps, paths with tokens, content digests or credential text. Layer failure must not fail base session/bootstrap.

### Tests

Strict parser positive/negative fixtures for every layer and markers; test request URI/headers; delayed old success/error ignored; per-layer latest queue; two-request cap; client memory/page caps; mismatch publication append; sparse continuation;410restart; debug logout; prefix/full-boundary classification; run/branch/source reset. Simulate a1second sidecar latency while forward targets advance every50ms: the active target must complete/display a matching bundle rather than starve behind perpetual cancellation. Missing/error layers produce bounded terminal bundle states; explicit scrub still invalidates all older bundles.

### Acceptance Criteria and Verification

`${GODOT_BIN} --headless --editor --path clients/godot-observer --quit` then `${GODOT_BIN} --headless --path clients/godot-observer --script res://tests/run_protocol.gd` passes, including new parser/source tests. Existing modified sources are not replaced/refactored wholesale.

## Task 9: Add optional evidence-labeled controls and visible availability

### Intent

Researchers must understand what a colored map means and whether it is known, inferred, incomplete or absent.

### Implementation Steps

1. Create `scenes/ui/civilization_panel.tscn` with script `scripts/ui/civilization_panel.gd`, instantiated as `$CivilizationPanel` by the actual `scenes/ui/ui_layer.tscn` through a declared ExtResource/load_steps update. Place it outside the selection-hidden inspector. Provide six primary optional toggles: population, culture, technology, migration, social groups, institutions. `UILayer` owns one population-enabled boolean and setter; both the new group toggle and existing `$GenerationalPanel/Column/Population` mirror it using no-signal setters. Route both toggle signals through that setter and emit the existing `population_toggled` once per state transition. Keep existing population control ID, demographic source, panel/lineage visibility and `main.gd::_on_population_toggled` wiring; do not create a second independent state or duplicate fetch.
2. Add facility/context switches for regions/routes, settlement candidates, trade/exchange summaries, collective projects/public goods and records/repositories. Existing base physical structures/region envelopes remain available with overlays off; a new switch is presentation only, never a capability enable request.
3. Register exact evidence classes per layer; mixed-mode categories expose explicit submodes rather than one ambiguous class: groups `selected-owner beliefs` versus `inferred communities`; technology `selected-owner knowledge` versus `inferred diffusion`; institutions `selected-owner concepts` versus `inferred episodes`. Culture/settlement/trade aggregate categories are ANALYTICAL / INFERRED; individual committed exchange/journey drill-down events remain OBJECTIVE.
4. Visible header badges: OBJECTIVE, SUBJECTIVE (selected owner ID), ANALYTICAL / INFERRED. Distinguish by icon/line pattern/text, not color alone. Show exact boundary/window, source policy, coverage and denominator/basis next to quantitative summaries.
5. State rows display off, loading, complete-empty, ready, partial/truncated, stale, unavailable, restricted and error. Show safe reason plus retry/restart/Load more when allowed. Clearing unavailable rows removes associated graphics, including ordinary legacy optional overlays touched by civilization mode; never leave the previous historical image silently visible.
6. Institution/culture summaries without physical anchors appear in the panel as unplaced/nonspatial. Unavailable channels must not render zero% or an empty inferred society. Keep overlays default off and preserve existing V2 controls and credentials accessibility.

### Required Interfaces and Contracts

Panel emits only presentation/fetch actions; no simulation control methods, new model enablement or analytic calculations. Selected owner is explicit and global to subjective submodes. Legends/filters do not change scientific selectors without resetting request keys and pages.

### Requirement Evidence

Original Request — optional overlays and explicit evidence classes; existing `evidence_class.gd` constants; cultural metrics docs — unknown versus known zero. UI tests must assert rendered labels and state, not only log a checklist.

### Error Handling and Logging

Show bounded safe reason strings; do not display HTTP exception bodies. DEBUG toggle/submode/state transitions with counts; no private labels/content in logs. A restricted private category remains clickable for credential guidance without exposing existence counts.

### Tests

Defaults off, six toggles accessible without selection, instantiate actual `res://scenes/ui/ui_layer.tscn` and assert new packed-scene/script/signal links. Toggle population from each mirrored control and verify synchronized button state, existing generational visibility/lineage behavior, exactly one existing signal emission and no duplicate demographic fetch. Test every evidence badge/submode, partial coverage and denominator, missing/error clearing, nonspatial rows, credential revocation, keyboard/focus behavior in compact viewport and V2 legend compatibility.

### Acceptance Criteria and Verification

Pinned headless protocol suite passes with `test_civilization_controls.gd` and existing `test_evidence_class.gd`/generational navigation tests. No category is represented by an unlabeled generic metric marker.

## Phase Risks and Completion

Generic metrics currently fall back to origin markers; the new source must never use that fallback. Source/credential epochs must guard every response path. Update Tasks 7–9 only in `index.md` after verification.
