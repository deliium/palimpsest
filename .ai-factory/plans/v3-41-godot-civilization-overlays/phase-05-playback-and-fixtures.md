# Phase 5: Historical playback, bounded detail and representative evidence

Plan: [index.md](index.md)  
Tasks: 13–15  
Depends on: Tasks 1–12

## Objective

Researchers can watch past spatial/social change, seek backwards safely and play rapidly without stale overlays, discarded scientific evidence or animation backlogs.

## Current-Code Evidence

| Path | Symbols | Consequence |
|---|---|---|
| `clients/godot-observer/scripts/protocol/playback.gd` | `policy`, `coalesce_tick_envelopes` | Existing >=8× snapping; coalescing helper is not integrated in inspected ingestion. |
| `clients/godot-observer/scripts/net/session.gd` | `seek_tick`, `seek_event`, `_on_envelope`, `_apply_sought_frame` | History is frame replacement, not reverse event execution; live buffer cap is 256. |
| `clients/godot-observer/scripts/ui/ui_layer.gd` | speed options | Preserve 0.25/0.5/1/2/4/8/16× and existing controls. |
| `clients/godot-observer/tests/test_playback.gd`, `test_transport.gd` | policy/transport tests | Need resulting-state equivalence, not only speed-policy tests. |
| `src/experiments/observer_graphical_scenario.py` | graphical fixture producer | Tick-1000 seek high water is synthetic, not proof of a 1,000-tick simulation. |
| `tests/compose/start_generational.py`, `seed_generational_evidence.py` | actual run plus explicitly constructed private presentation fixtures | Reuse harness; disclose fixture versus emergence provenance. |

## Files to Change

Modify client `scripts/protocol/playback.gd`, `scripts/net/session.gd`, `scripts/view/world_view.gd`, `scripts/ui/ui_layer.gd`, `scripts/ui/civilization_panel.gd`, `scripts/main.gd`, `scenes/ui/ui_layer.tscn`. Introduce `scripts/ui/civilization_timeline.gd` and packed scene `scenes/ui/civilization_timeline.tscn` as the civilization-only timeline adapter; instantiate `$CivilizationTimeline` through that actual UI scene and connect through `ui_layer.gd` rather than replacing the existing `$Timeline`/`scripts/ui/timeline.gd` generation-marker implementation.

The backend marker route/schema/cursor and `tests/unit/test_civilization_markers_api.py` belong to Task7 and are prerequisites already complete. This phase consumes them without moving their implementation back after the parser. Create client `tests/test_civilization_playback.gd`, `tests/test_civilization_timeline.gd`, `fixtures/protocol/civilization/README.md` plus canonical fixture JSON. Create `tests/compose/start_civilization.py`, `tests/compose/seed_civilization_evidence.py`, `tests/unit/test_civilization_fixtures.py`.

Abbreviated client paths are under `clients/godot-observer/`; existing `test_playback.gd`, `test_transport.gd`, `test_advanced_replay_integration.gd`, `tests/run_protocol.gd` are extended.

## Task 13: Integrate high-speed level of detail without dropping state

### Intent

Animation cost may degrade aggressively, but accepted objective state, historical overlays and scientific event navigation remain correct.

### Implementation Steps

1. Extend `Playback.policy`: <4× normal motion with existing effects; 4× reduced (no trails, max 32 concurrent transient effects); >=8× or >3 pending motions snap (no tweens, pulses, particles or flow travel); 16× additionally hide unselected individual labels and use location aggregate badges. Existing speed list stays unchanged. Detail changes do not alter fetched scientific selectors or counts.
2. Integrate policy in session→world-view processing. Apply every received scientific event/reducer transition in order when using events; suppress draw/effect dispatch until at most one final presentation plan per rendered frame. Do not run the existing coalescing helper over mixed event journals. Only complete replaceable tick/state envelopes may be coalesced to the newest frame, preserving the scientific event stream/resume cursor and ignoring stale epochs.
3. Keep canonical scientific journal/cursor navigation separate from disposable presentation work. Bound pending presentation snapshots to one latest accepted frame, transient pool to 32, queued incoming live envelopes to existing 256. If ingestion cannot keep up, follow existing behind-live/catch-up/reconnect semantics using the last safely applied cursor; do not acknowledge unseen events or silently drop resume evidence.
4. Add `_request_playback_state` and `_accept_playback_bundle` in session for automatic civilization-history play at every speed. Keep explicit `seek_tick`/`seek_event` and legacy event navigation unchanged. Do not call `_begin_seek` for every automatic timer step: its `_cancel_http`/epoch increment would cancel the sidecars being awaited. Maintain one playback navigation epoch, one in-flight state request, one pending frame and one latest desired boundary. Derive desired boundary from the accepted frame's `world.tick`, elapsed presentation time and speed (not `transport.tick`, which can be the prior event tick); cap to run high water or recorded-boundary catalogue. Faster targets replace only the queued target, not the active request epoch. Do not add speed to queries or issue control/tick requests.
5. When the state response arrives, stage that frame and call Task8 `prepare_bundle` for its exact cursor; do not yet replace the displayed frame. Show immediate busy feedback. Wait until enabled-layer first pages are ready/terminal (including disabled/restricted/missing/error) or a fixed2second presentation deadline, then atomically accept frame plus matching ready sidecars and explicit unavailable states for timed-out layers. This wait affects automatic presentation only, not live scientific execution, independent live mode or network journal progress. Next target is the newest queued desired boundary, allowing skipped presentation frames without starving the active bundle. Explicit pause/scrub/run/branch/owner/credential switch increments the navigation epoch and cancels staging; pause keeps the last displayed boundary and can refresh its exact layers once. At the horizon stop requesting new frames. A same-cursor retry is allowed while paused; no timed-out result paints a different boundary.
6. Refresh civilization sources once per accepted/staged target, never per dropped effect/event. Build canonical semantic state then the LOD-specific draw plan. On return to slow speed or pause rebuild missing labels/detail from retained same-cursor semantic state, not skipped animations. Expose a test-only semantic digest/cursor/count snapshot through bounded test instrumentation, without runtime payload/digest logging. Scientific event pages remain independently queryable and complete even when presentation frames were skipped.

### Required Interfaces and Contracts

`WorldView` gets `set_presentation_detail(lod)` and `apply_civilization_plan(plan)`; its model still follows normal reducer/frame adoption. `semantic_digest` covers the accepted objective world, cursor and pre-LOD civilization logical identities/counts/status/coverage; it excludes effect/label/glyph selection and transient positions/tween clocks. Fast/slow semantic equality requires both clients to finish loading the same requested layer scope at the same cursor. LOD draw-plan digests may differ during playback; after pausing, select common detail and rebuild both before comparing actual drawings. If a bundle timed out, equality is checked after an explicit same-boundary refresh, while the earlier unavailable state is tested as such rather than equated to complete data. Selected focus/navigation survives LOD changes. Browser remains single-threaded Compatibility Web.

### Requirement Evidence

Original Request — aggressive high-speed simplification with state correctness; observer docs — presentation-only speed; existing journal/catch-up contracts. Cover live bursts, slow/fast/slow and backward historical seek.

### Error Handling and Logging

DEBUG per-batch counters/LOD transition, not one line per event/frame; WARN overflow/catch-up reason with safe counts. Never freeze network on a transient effect error; clear failed effect and retain accepted model. Resource caps are explicit UI display truncation, not scientific data truncation.

### Tests

Feed identical canonical event/frame sequences at1×/4×/8×/16× with effects enabled/disabled and compare final world/semantic digests and cursor after the same scopes load; separately compare drawings at a shared paused LOD. Include journey arrival, structure/repository deletion, population admission/death, technology acquisition and institution transition. Delay sidecars by1second while targets advance every50ms and assert intermediate matching bundles actually display, not only the horizon state. Exercise2second deadline, unavailable layers, pause/scrub invalidation, prior-event resume tick versus actual frame tick, same-cursor refresh, one active seek/no repeated `_cancel_http` during automatic play and end-of-history stop. Burst>256 exercises catch-up rather than data loss. Assert<=32 transients, one pending frame/latest target, no animations>=8×, <=2civilization requests in flight and unchanged full event pages.

### Acceptance Criteria and Verification

Pinned headless suite passes with strong state equality tests and existing transport/replay tests. High-speed path is actually invoked by session integration; testing a pure unused coalescer is insufficient.

## Task 14: Add bounded historical change markers and capture-aware navigation

### Intent

Make long-horizon changes discoverable without substituting current beliefs over historical frames.

### Implementation Steps

1. Consume the marker endpoint/strict schema already implemented and tested in Task7 and parsed in Task8. Preserve its evidence/owner/window/purpose-bound publication pin,200row/2,000scan/1MiBresponse/physical-read budgets and missing-interval semantics. No backend contract is first invented during this UI task.
2. Instantiate `$CivilizationTimeline` from `scenes/ui/civilization_timeline.tscn` in `scenes/ui/ui_layer.tscn`, attach `scripts/ui/civilization_timeline.gd`, and route its seek/window/load-more signals through `UILayer` to session's existing explicit seek path. It consumes paged catalogue/marker responses, not client-inferred births/community/technology transitions. Display separate tracks for objective movement/population context, analytical settlement change, knowledge acquisition/diffusion and institution evidence transitions; owner badges on subjective tracks. Existing `$Timeline` keeps its generation markers and signals; population context comes from existing demographic APIs, not duplicated transition inference.
3. Default historical playback still seeks objective ticks. Optional `Recorded boundaries only` explicitly advances between captured boundaries from the pinned catalogue; show exact target B and disclose skipped gaps. Do not silently enable this mode or interpolate missing/private snapshots. An empty catalogue disables this option, not ordinary playback.
4. Click marker seeks its backend-provided complete post-event boundary, waits for accepted frame, then fetches matching overlays. Existing event drill-down may produce a prefix: preserve the objective prefix and disable finalized captured overlays until returning to full boundary. Never reuse the latest captured private state.
5. Bounds: max200 displayed markers, eight catalogue/marker pages per explicit window, four cached windows under the Task 8 cache budget. Sort tick/type/identity; overflow exposes Load more/narrow window and coverage. Run/branch/owner/publication switches clear tracks and continuations. Existing generation markers coexist; do not synthesize duplicate generation events.

### Required Interfaces and Contracts

Markers contain schema/source pin, marker ID/type, exact seek boundary, evidence class/scope, referenced row ID and coverage. No private text labels in objective tracks. Timeline uses backend labels/reasons and identity only; no causal claims from adjacent markers.

### Requirement Evidence

Original Request — watch settlement growth/movement/technology spread/institution changes; lineage/cultural docs — exact captures and missing spans. Supported combinations: objective-only run, captured mixed layers, prefix seek, gap/cadence, expired publication and owner change.

### Error Handling and Logging

Invalid window/owner/evidence is400; expired pin410 requires explicit restart; corruption503. Nonfatal client unavailable/restricted/gap states remain visible. DEBUG window/returned counts and safe reason; no cursor or private content logging.

### Tests

Reuse Task7's passing real-publication marker API tests. Instantiate the actual packed UI scene and assert timeline node/script/signal connections; headless marker click and accepted-frame request ordering; recorded-boundary mode; reverse seek; missing spans don't become collapse markers; changed owner/private tracks clear; >200markers and sparse continuation; old generation timeline/navigation tests remain green.

### Acceptance Criteria and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_civilization_markers_api.py -q` and pinned headless suite pass. Each timeline target is resolvable through the same historical cursor contract as the map.

## Task 15: Build representative producer-backed civilization fixtures

### Intent

Prove positive and absent-data paths with actual serializers/producer boundaries, while explicitly distinguishing controlled presentation evidence from scientific emergence.

### Implementation Steps

1. Commit protocol fixtures generated through the new DTO serializers, with README recording schema/policy/run/world/config/source/boundary/window identities, evidence class and fixture provenance. Include all map sections/layers, complete-empty/off/missing/partial/restricted/error and prefix/full-boundary examples. Fixture generation is an explicit script/test operation, not runtime parsing of arbitrary JSON.
2. Add `tests/compose/start_civilization.py` to build a controlled persisted test run through real manager/runner/database ports: three locations (two in region A, one in B), configured interregional route, six founders, two initial physical structures, one repository, one collective project, owned lifecycle with periodic admissions/finite lifespan. Run 256 real finalized ticks with deterministic scripted policies using ordinary admitted commands for at least one journey, completed exchange, project contribution, public-good act, record deposit/retrieval, arrival and death. Use existing public scenario/build helpers and typed configuration versions selected by enabled features; do not edit runner JSON schemas to force feature combinations.
3. Test policies/control schedules are test composition only, never production emergence rules. Use actual runner civilization capture/publisher to produce settlement/culture/technology/group/institution inputs that are available in the enabled run; independently verify counts against committed events and retained native owner ledgers. If a native cognition category has no positive instance, report it honestly rather than relabel a speech act or force a global institution.
4. Add separate `seed_civilization_evidence.py` for constructed positive presentation cases not guaranteed by the real run (conflicting memberships, ambiguous knowledge edges, institution lifecycle/grounding). Feed typed detached native evidence through the real composer/publisher into a separately identified fixture run/publication. Mark every such artifact `constructed presentation evidence` in the fixture README/test diagnostics; do not overwrite the real capture or claim spontaneous emergence. Grounding positive unit/integration tests must additionally exercise Task 4's exact-observation witness builder, not only hand-authored anchor rows.
5. Extend Compose fixture setup through the actual Task6 optional override with read-only API civilization volume, producer-only writable mount, same disposable database, persistent test cursor key, distinct inspect/debug credentials and capture-off counterpart. Exercise CLI hook composition for a durable ordinary matrix cell and a durable generational assignment, verifying API run discovery/state replay against their publications; do not test only a manually installed sink. Inject publication failure and exercise all three matrix skip/adoption paths without re-execution. Reuse existing graphical-v2 and V3-40 generational packs unchanged as regression fixtures; never use their synthetic tick-1000 high water as a long-run proof.

### Required Interfaces and Contracts

Real fixture acceptance binds events, world frame, owner captures and publication to the same persisted run. Constructed packs have separate identities and explicit provenance. Fixture producer uses disposable `palimpsest_test` database names and fail-closed migration targeting. No new catalog experiment, capability or metric is required.

### Requirement Evidence

Requirements Reconciliation — real representative artifacts; `tests/compose/start_generational.py`/`seed_generational_evidence.py` — existing mixed real/constructed precedent; Original Request — all visualized categories and long-horizon watching.

### Error Handling and Logging

Fail setup with bounded missing prerequisite/evidence code; never silently skip a demanded positive browser assertion. Diagnostics safe run/tick/count/provenance only. Do not print ledgers/credentials or full generated JSON.

### Tests

Python fixture-schema/mirror/digest/provenance tests; headless parse/render of each fixture; producer event/receipt counts; real 256-tick high water; no direct world writes outside allowed setup/engine admission; separate constructed identity; capture-off base map.

### Acceptance Criteria and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_civilization_fixtures.py tests/unit/test_godot_observer_fixtures.py tests/unit/test_godot_protocol_mirror.py -q` and pinned headless suite pass. Real fixture producer is exercised by Task 17's Compose tests; missing Docker/database prerequisites remain explicit unexecuted gates.

## Phase Risks and Completion

Large requested horizons are not performance proof if synthetic. Keep actual event coverage and fixture provenance visible. Simplification must target transient presentation only. Update Tasks 13–15 only in `index.md` after verification.
