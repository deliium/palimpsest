# Phase 1: Cursor-correct objective civilization map

Plan: [index.md](index.md)  
Tasks: 1–3  
Depends on: none

## Objective

Expose existing physical V3 state through a separate GET sidecar, without widening strict legacy observer frames or introducing settlement/institution world entities.

## Current-Code Evidence

| Path | Symbols | Consequence |
|---|---|---|
| `src/simulation/observer_facts.py` | `ObjectiveFacts`, `ObjectiveScene` | Detached scenes already retain repositories, projects, regions, journeys and lifecycle records. |
| `src/simulation/engine.py` | `WorldEngine.detached_objective_facts` | Existing objective export boundary; preserve current user edits. |
| `src/simulation/replay.py` | `FoldedObjectiveHistory`, `scene_at_tick` | Resolve the selected historical prefix; `history.events` is not necessarily the whole journal. |
| `src/observer/contracts.py` | `ObserverCollectiveProject`, `ObserverRepository`, `ObserverArtifact` | Internal DTOs exceed current HTTP frame fields. |
| `src/api/observer_service.py` | `_frame_out`, `_history`, `_history_through_event` | Legacy HTTP output omits repositories/projects and extended artifact metadata. |
| `src/simulation/observer_demographics.py` | `DemographicProjection` | Existing off/empty/partial and pagination precedent. |
| `src/world/regions.py` | `RegionsMigrationSpec`, `RouteSpec`, `Journey` | Configured routes are not region-envelope adjacency. |

## Files to Change

| Path | Action | Responsibility |
|---|---|---|
| `src/simulation/civilization_models.py` | create | Neutral immutable sidecar/publication DTOs, selectors, errors and budgets. |
| `src/simulation/civilization_ports.py` | create | Separate read/publish/capture protocols. |
| `src/simulation/observer_civilization.py` | create | Pure detached physical projection. |
| `src/api/civilization_schemas.py` | create | Strict HTTP models and explicit serializers. |
| `src/api/civilization_cursor.py` | create | Purpose-specific signed keyset cursors. |
| `src/api/civilization_service.py` | create | Resolve cursor once, project and page. |
| `src/api/observer_service.py` | modify | Public `ObserverReadService.resolve_objective_history` wrapper over existing replay methods. |
| `src/api/routes/civilization.py` | create | Objective route now; captured routes in Task 7. |
| `src/api/app.py`, `src/api/routes/__init__.py` | modify | Register GET routes and service. |
| `src/simulation/__init__.py` | modify | Export only new public contracts; no authority internals. |
| `tests/unit/test_observer_civilization.py`, `tests/unit/test_observer_civilization_api.py` | create | Projection and API compatibility tests. |

## Task 1: Define independent civilization contracts

### Intent

Commit the temporal, epistemic and bounded-query vocabulary shared by every subsequent phase.

### Implementation Steps

1. Introduce frozen `CivilizationCursor(run_id, world_id, tick, through_sequence, boundary_tick, revision)` and `CivilizationScope(layer, evidence_class, owner_id)`. `tick` means start-of-tick; sequence is inclusive and requires tick. `boundary_tick` is present only for a complete boundary, using the accepted frame's resolved world tick, not its last-event resume pair.
2. Introduce `CivilizationCoverage(state, reason, capture_start, capture_end, missing_intervals, observed_count, expected_count)`; states are `complete`, `partial`, `unavailable`, `disabled`. Restricted/stale/loading are client/request states, not fabricated server data. Complete-empty is `complete` plus no rows. A missing denominator yields null, never zero.
3. Define `CivilizationAnchor(kind, location_id, entity_id, evidence_ref, evidence_tick)` with kinds `location`, `structure`, `repository`, `project`, `agent_at_evidence`, `none`. An anchor is presentation provenance, not ownership or authority. IDs must resolve inside the same run and time. Unknown anchors remain nonspatial; do not encode simulation coordinates.
4. Define closed typed row unions for map sections and captured layers; do not use arbitrary payload dictionaries. Use `OBJECTIVE`, `SUBJECTIVE`, `ANALYTICAL` wire evidence values, mapped explicitly to the client's existing evidence enum in Task 8.
5. Add `CivilizationReadPort` (catalogue, exact snapshot and paged rows), `CivilizationPublicationPort` (publish immutable boundary, seal catalogue), and `CivilizationBoundarySink` (capture finalized detached inputs). Readers have no publish method. Declare `CivilizationReadBudget`: limit default100/max200, 1MiB HTTP response, 2,000 decoded/scanned rows, 16 physical files and 12MiB physically read/request, reserved before opening/decoding. Metadata files are <=64KiB; row/catalogue shards <=1MiB and200 rows; a boundary's total encoded files <=64MiB; JSON depth32. Count cached decoded rows against scan budgets too. Cache hits do not consume physical bytes, but cannot bypass validation or row limits.
6. Schema IDs: `observer-civilization-map-v1`, `observer-civilization-catalogue-v1`, `observer-civilization-overlay-v1`, `observer-civilization-markers-v1`, storage `civilization-snapshot-v1` and `civilization-catalogue-v1`. These are new sidecars, not observer-protocol/runner/result/lineage schema replacements.

### Required Interfaces and Contracts

All HTTP page envelopes carry schema, run/world IDs, requested/resolved cursor, section/layer, scope, coverage, rows, `next_cursor`, `truncated`, and source revision. Captured pages additionally carry publication ID/digest, policy version and exact window. Sort rows by stable typed identity, never label or array ordinal. Totals describe the full supported source population, not the current page; report unavailable totals when source coverage is incomplete.

New map section union: `regions`, `routes`, `locations`, `projects`, `repositories`, `records`. New captured layer union: `settlements`, `migration`, `trade`, `culture`, `technology`, `social_groups`, `institutions`. Every row has a stable row ID and evidence references; owner-local IDs are qualified by owner. Captured layer/evidence combinations are fixed in the manifest.

Each encoded row is <=64KiB. Inline evidence/source refs are capped at32 each; member/participant IDs at64 each. Publish full scalar counts, deterministic retained prefixes and `detail_truncated` for shortened inline details, with qualified refs to existing bounded lineage/event queries. Large collections become separate typed rows, not arbitrarily nested arrays. Detail truncation does not change a complete measurement's denominator/coverage. An intrinsically oversized scalar/row rejects that layer's publication with `civilization_row_too_large`; it must not yield an endless empty continuation page. Page byte exhaustion stops before the next row, keeps that row for the next cursor, and always makes progress.

Define marker DTOs here, before client parsing: `CivilizationMarker(marker_id, marker_type, seek_boundary, evidence_class, owner_id, layer, row_id, source_refs, coverage)`. Marker types are `settlement_activated`, `settlement_deactivated`, `journey_started`, `journey_arrived`, `journey_ended`, `technology_acquired`, `institution_transition`; missing intervals are separate coverage bands, not transition markers. Its strict HTTP route/serialization is implemented in Task7, not deferred until Task14.

Hashing is an acyclic payload contract: row-shard bytes contain neither their own digest nor any parent digest; boundary manifests reference shard digests; catalogue pages reference boundary-manifest digests; catalogue index references catalogue-page digests; the final commit reference contains the catalogue-index digest. All hashes are SHA256 over canonical UTF-8/LF bytes. The publication ID is a stable ID established before hashing, not a digest that recursively depends on itself. No root/catalogue digest is embedded in hashed child content.

### Requirement Evidence

Original Request — epistemic distinction/history; ARCHITECTURE — Versioned Extension Contract; `docs/observer.md` — cursor semantics. Prefix versus complete-boundary and off versus empty combinations must be exercised.

### Error Handling and Logging

Reject unknown fields/enums, bool-as-int, negative ticks, duplicate IDs, NaN and invalid owner/evidence combinations. DEBUG logs schema, safe run ID, layer, counts and reason only; never row bodies, trait fingerprints, credentials or cursors. Validation exceptions expose closed safe codes.

### Tests

Round-trip every row union and marker; reject invalid scope/anchor/future evidence; complete-empty versus disabled; no mutable aliases; no coordinate fields; old observer fixtures unchanged. Test inline caps/full scalar counts, one oversized row, byte-limited page progress, physical-budget reservation and the nonrecursive digest DAG with a known-answer fixture.

### Acceptance Criteria and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_observer_civilization.py tests/unit/test_godot_protocol_mirror.py -q` passes. Contracts alone do not change existing event/frame serializers or count pins.

## Task 2: Project physical regions, facilities and location population

### Intent

Close the internal-to-HTTP data gap with objective facts at the displayed cursor.

### Implementation Steps

1. Add `project_civilization_map(scene: ObjectiveScene, *, cursor: CivilizationCursor, section: str)`. It consumes detached values only, not a live engine or private world modules.
2. Project configured region definitions and exact location assignments; routes carry endpoints, duration and fatigue cost from configuration. Unassigned locations remain unassigned. Draw no route inferred from region overlap.
3. Project location rows with living/dead body counts, registered-agent count, structure/repository/project counts, and active journey IDs. Distinguish living bodies from registered agents; lifecycle counts are unavailable when that channel is absent. Journey participants stay at origin until committed arrival.
4. Project projects with real location, kind/status, labor/material progress and required amounts, accepted contributions, linked structure, shortages and public-act counts. Public-good benefit/maintenance/opposition are distinct facts, not access rights or moral labels.
5. Project repository ID/location/status/member count/access/linked structure/maintenance; record ID/genre/integrity/placement/custodian and lineage metadata. Do not expose marks, interpreted text, index contents or automatically call a repository a Library institution. Resolve a carried record's physical location only through its actual holder binding at this scene.
6. Represent large contributor/member/evidence collections as scalar counts plus Task1's bounded inline IDs/refs and explicit detail-truncation flag. No unbounded nested arrays. A selected project/repository can request its direct row by ID without loading every earlier page; existing event/lineage detail queries supply bounded provenance drill-down, not a new unbounded details endpoint.

### Required Interfaces and Contracts

Objective location population/infrastructure is not a settlement classification. Preserve that neutral terminology even when the analytical settlement layer is off. Reuse demographic owner/body bindings rather than assuming equality. `regions_migration=None` and no active journeys are different states.

### Requirement Evidence

Original Request — regions/migration/projects/public goods/archives; `src/world/collective_projects.py` — contribution/public-act semantics; architecture — physical records and private meaning. Test before/after construction, destruction, repository deposit/damage and journey arrival.

### Error Handling and Logging

Unresolved holder/anchor produces `unresolved_anchor` and a nonspatial row, not `(0,0)`. Inconsistent scene identity fails closed. DEBUG projection counts; WARN bounded reason codes for inconsistent optional metadata, no artifact contents.

### Tests

Extend new projection tests using real detached scenes from `test_repository_observer.py`, `test_collective_project_observer.py`, `test_public_good_observer.py`, `test_regional_migration_observer.py` patterns. Cover empty world, two populated locations, dead bodies, non-identical agent/body IDs, multiple route endpoints, damaged records and channels off. Compare historical projection to the equivalent live detached scene.

### Acceptance Criteria and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_observer_civilization.py tests/unit/test_repository_observer.py tests/unit/test_collective_project_observer.py tests/unit/test_public_good_observer.py tests/unit/test_regional_migration_observer.py -q` passes; legacy frame output remains byte/canonically equivalent.

## Task 3: Serve bounded objective map pages at exact replay cursors

### Intent

Make the map useful to Godot and other read-only consumers without introducing new simulation authority.

### Implementation Steps

1. Add GET `/v1/simulations/{run_id}/observer/civilization/map` with `section`, optional `tick`, `through_sequence`, `entity_id`, `limit`, `cursor`. Default section `locations`; absent tick resolves the current objective head once and returns the explicit resolved cursor. Pagination thereafter requires that explicit tick.
2. Add public `ObserverReadService.resolve_objective_history(run_id, *, tick, through_sequence) -> FoldedObjectiveHistory` in `src/api/observer_service.py`, delegating to its existing `_history`/`_history_through_event` methods and trusted replay-context injection. Inject this resolver into the new service and normalize its resulting scene cursor once. Do not import private world modules or copy restoration logic; preserve user changes elsewhere.
3. `CivilizationCursorCodec` uses purpose `civilization-map-v1`, HMAC, constant-time verification and a one-hour expiry. Bind run, section, entity filter, resolved tick/sequence/revision, ordering version, limit and last key. Use a new `PALIMPSEST_CIVILIZATION_CURSOR_KEY` setting, memory-only generated fallback in local mode; configured deployments use a persistent secret. Do not reuse lineage cursor purpose/signature formats.
4. Require objective-inspection capability before replay or row counts. Set `Cache-Control: no-store`. Validate exact query key sets and enforce row/source/serialized-byte budgets, with continuation after the last scanned key; no false exhaustion on sparse filters.
5. Return 400 for bad selectors/cursors, 404 for unknown run/entity, 409 for an event beyond high water, 410 for expired/gone pinned context, 503 for required replay context/storage failure. Optional absent channels use an availability envelope rather than an invented empty success.

### Required Interfaces and Contracts

No subjective or analytical rows in this endpoint. A valid event prefix can project physical facts but cannot authorize a private finalized-boundary snapshot. Read requests never create sidecars, repair files, commit ticks or mutate run control.

### Requirement Evidence

ARCHITECTURE — API authority and version discipline; `test_observer_demographic_api.py` — strict queries/paging/cursor precedent; Original Request — historical state correctness. Cover distinct inspect/debug secrets and historical prefixes.

### Error Handling and Logging

INFO service attachment/capability-neutral readiness; DEBUG resolved tick/section/scanned/returned counts; WARN safe cursor/budget/storage reason. Never log HMAC material, raw query strings or capabilities. Register only closed codes in any client allowlist later.

### Tests

API tests: all sections; selected late entity; >450 rows; empty scan page with continuation; response cap; malformed/foreign/expired cursor; changed filter/run/limit; inspect-only access; missing replay context; partial/full prefix parity; no mutation before/after requests. Add lifecycle-off legacy fixture compatibility.

### Acceptance Criteria and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_observer_civilization_api.py tests/unit/test_observer_population_replay.py tests/unit/test_observer_demographic_api.py tests/architecture/test_observer_isolation.py -q` passes. No fields are added to `ObserverWorldStateOut` or existing WS envelopes.

## Phase Risks and Completion

Historical checkpoint folds can omit metadata: reuse the V3-40 replay context, test real checkpoints, never join live head data. Rich internal DTOs are not proof of wire availability: assert actual HTTP JSON. After verification, update Tasks 1–3 in `index.md` only.
