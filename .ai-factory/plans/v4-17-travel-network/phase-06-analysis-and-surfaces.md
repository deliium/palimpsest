# Phase 6: Analysis and Read-Only Surfaces

Plan: [index.md](index.md)
Tasks: 17-20
Depends on: Phase 3 (Tasks 7-9), Phase 4 (Tasks 10-13); Task 17 also on Task 18 within this phase

## Objective

Publish the objective route network and detached route-quality evidence through
the existing infrastructure research surfaces, appending four metric families
(188 -> 192) without adding settings, stores, database tables, or a new API
version. All readers stay GET-only and read-only.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT` 53; infrastructure registrations 9061-9064; infrastructure family ids 262-265 | The catalog is append-only; V4-17 appends four ids without reordering prior families. |
| `src/analysis/metric_service.py` | infrastructure emit gate 2373-2399; `MetricComputationInputs` | Optional detached inputs gate family emission; no live cognition input. |
| `src/analysis/infrastructure_networks_analysis.py` | `InfrastructureAssetAnalysisRow` 46; `InfrastructureNetworksAnalysis` 101; harvest 138 | Extend the detached analysis input with route rows. |
| `src/analysis/infrastructure_metrics.py` | four compute functions 145/197/255/318 | Add four pure route computes with counts/coverage/availability only. |
| `src/simulation/infrastructure_models.py` | policy/version 32-37; asset record 147-240; summary 242; snapshot 294; empty 335 | Snapshot v2 adds bounded route rows; v1 stays decodable. |
| `src/simulation/infrastructure_codec.py` | canonical/encode/decode 37-167 | Add v2 codec with exact keys and canonical hash. |
| `src/simulation/infrastructure_paging.py` | page limit 22; selection 28-34; paging 64-102 | Add a `routes` purpose and keyset. |
| `src/simulation/infrastructure_ports.py` | cursor purposes 33-40; summary/publication 44-65; reader 164-183 | Add route summary/read methods; keep publisher separate. |
| `src/experiments/infrastructure_completed_run.py` | compose 35-55 | Compose v2 with route rows after completion. |
| `src/experiments/infrastructure_publication.py` | publication 196-279; receipt 282 | Same opt-in publication; no new gate. |
| `src/api/routes/infrastructure_networks.py` | route count 41; six handlers 213-355 | Add a seventh `routes` GET under the same `SUBJECTIVE_DEBUG` gate. |
| `src/api/infrastructure_networks_schemas.py` | summary 10; asset 27; page 45 | Add strict route schemas; no score fields. |
| `src/infrastructure/settings.py` | root/key 244-247; validator 407-416; enabled flags 755-766 | Reuse the existing dual gate; add no settings. |
| `clients/research-ui/src/views/InfrastructureNetworksPanel.svelte` | fetch/load 37-80; sections 82-192 | Add a read-only routes table to the existing panel. |
| `clients/godot-observer/scripts/view/infrastructure_overlay.gd` | four kinds 9-12; forbidden fields 28-43; apply 115 | Add route-status edge styling; no new overlay kind. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/analysis/infrastructure_networks_analysis.py` | modify | Add route analysis rows/input. |
| `src/analysis/infrastructure_metrics.py` | modify | Add four pure compute functions. |
| `src/analysis/specifications.py` | modify | Append four family ids and count 192. |
| `src/analysis/metric_service.py` | modify | Gate/emit the four families. |
| `src/experiments/collectors.py` | modify | Populate `MetricComputationInputs.travel_network_analysis` from snapshot v2 route rows. |
| `src/simulation/infrastructure_models.py` | modify | Snapshot v2 route rows and summary. |
| `src/simulation/infrastructure_codec.py` | modify | v2 encode/decode and finalize. |
| `src/simulation/infrastructure_paging.py` | modify | Route paging purpose. |
| `src/simulation/infrastructure_ports.py` | modify | Route read protocol. |
| `src/experiments/infrastructure_completed_run.py` | modify | Compose v2. |
| `src/experiments/infrastructure_publication.py` | modify | Publish v2; v1 remains readable. |
| `src/api/routes/infrastructure_networks.py` | modify | Seventh GET route. |
| `src/api/infrastructure_networks_schemas.py` | modify | Route schemas. |
| `src/api/infrastructure_networks_cursor.py` | modify | Add the purpose-bound cursor constant/TTL alias. |
| `src/research_runner/infrastructure_composition.py` | verify | Same options/publish path. |
| `clients/research-ui/src/api/infrastructureNetworks.ts` | modify | Route fetcher. |
| `clients/research-ui/src/views/InfrastructureNetworksPanel.svelte` | modify | Routes section. |
| `clients/godot-observer/scripts/view/infrastructure_overlay.gd` | modify | Route-status styling. |
| `clients/godot-observer/scripts/ui/overlay_legend.gd` | modify | Route-status legend mapping. |
| `clients/godot-observer/scripts/presentation/evidence_class.gd` | modify | Objective route-status class mapping. |
| `clients/godot-observer/scripts/net/session.gd` | modify | Fetch route page. |
| `clients/godot-observer/scripts/main.gd` | modify | Apply route payload. |

## Task 17: Append four travel-network metric families to 192

### Intent

Add detached, count/coverage-only route metrics without creating a route score,
civilization score, or truth oracle.

### Implementation Steps

1. Add `TravelRouteAnalysisRow` to
   `src/analysis/infrastructure_networks_analysis.py` with:
   `origin_id`, `destination_id`, `status`, `seasonal_availability`,
   `blockage_cause`, `duration_ticks`, `fatigue_cost`, `capacity`, `risk`,
   `infrastructure_quality`, `as_of_tick`, `observed_belief_count`,
   `believed_closed_count`, `believed_restricted_count`.
2. Extend `InfrastructureNetworksAnalysis` with
   `routes: tuple[TravelRouteAnalysisRow, ...] = ()` and a coverage flag.
3. Extend `harvest_infrastructure_networks_analysis` to accept detached route
   rows and optional owner destination-belief rows; never import simulation or
   live state.
4. Add four pure compute functions in
   `src/analysis/infrastructure_metrics.py`:
   - `compute_travel_route_structure` — route count, adjacent-edge coverage,
     road/bridge coverage, capacity distribution;
   - `compute_travel_route_condition` — open/restricted/closed counts, seasonal
     availability counts, risk/quality quantiles (counts only in value keys);
   - `compute_travel_route_blockage` — blockage-cause counts and blocked-edge
     coverage;
   - `compute_travel_route_belief_alignment` — owner-belief counts,
     unknown/stale/contradicted counts, researcher-only alignment
     (`consistent`, `unresolved`, `inconsistent`, `not_applicable`).
5. Register family ids in `src/analysis/specifications.py`:
   `travel_route_structure@1`, `travel_route_condition@1`,
   `travel_route_blockage@1`, `travel_route_belief_alignment@1`; increment
   `METRIC_FAMILY_COUNT` to 192.
6. In `metric_service.py`, add
   `travel_network_analysis: object | None = None` to
   `MetricComputationInputs`; emit the four families only when it is present.
7. In `src/experiments/collectors.py:146`, extend the completed-run
   `MetricComputationInputs` construction to populate
   `travel_network_analysis` from the snapshot v2 route rows and detached
   owner-belief rows. Add a real collector → metric-service test; unit tests
   that call the metric service directly are not sufficient.
8. Do not emit a composite route score, route risk index, or civilization
   score. Belief alignment is researcher-only and never feeds cognition.

### Required Interfaces and Contracts

- First 188 families keep id, order, version, and value keys unchanged.
- New families are append-only and scalar; no shared metric model change.
- `MetricComputationInputs.travel_network_analysis` is optional and detached.
- Empty/unknown input emits explicit unavailable/empty metrics, not fabricated
  zeros.

### Requirement Evidence

- `src/analysis/specifications.py` 53/262-265/9061-9064; `src/analysis/metric_service.py` 2373-2399; `src/experiments/collectors.py` 146; index metrics row.

### Error Handling and Logging

- `INFO metric_families_appended count=4 catalog=192`.
- `WARN travel_network_analysis_missing reason_code=unavailable` once per run.
- No route/owner payloads at INFO.

### Tests

- `tests/unit/test_travel_network_metrics.py`:
  - catalog count 192;
  - four ids present and prior 188 unchanged;
  - empty/unknown input;
  - structure/condition/blockage counts;
  - belief alignment statuses;
  - emit gate off/on;
  - real collector → metric-service path populates the input.
- `uv run pytest tests/unit/test_travel_network_metrics.py tests/unit/test_infrastructure_metrics.py tests/unit/test_metric_specifications.py -q`

### Acceptance Criteria

- Catalog is exactly 192 with four new families.
- No composite score or truth field.
- Detached analysis never reaches cognition.

### Verification

- `uv run pytest tests/unit/test_travel_network_metrics.py tests/unit/test_infrastructure_metrics.py tests/unit/test_metric_specifications.py -q`
- Expected: all pass.

## Task 18: Extend infrastructure snapshot to v2 with route rows

### Intent

Publish route structure and condition with the existing infrastructure snapshot
and store, keeping v1 decode and byte verification.

### Implementation Steps

1. In `src/simulation/infrastructure_models.py`:
   - add `TravelRouteRecord` with the `RouteCondition` fields plus `status` etc.;
   - add `TravelRouteSummary` with route counts by status/availability/cause;
   - bump snapshot policy/version to
     `infrastructure-networks-snapshot-v2`;
   - add `routes: tuple[TravelRouteRecord, ...] = ()` and `route_summary`;
   - cap routes at `MAX_ROUTE_CONDITIONS = 512`.
2. In `src/simulation/infrastructure_codec.py`:
   - encode/decode v1 (no routes) and v2 (with routes);
   - canonical key order is fixed;
   - finalize/hash includes route rows;
   - reject v2 rows in a v1 document and vice versa.
3. In `src/simulation/infrastructure_paging.py`:
   - add purpose `routes`;
   - keyset by `(origin_id.value, destination_id.value)`;
   - enforce `MAX_PAGE_LIMIT = 500`;
   - deterministic ordering.
4. In `src/simulation/infrastructure_ports.py`:
   - add `routes(...)` to the reader protocol;
   - add route summary counts; keep publication/read separation.
5. In `src/experiments/infrastructure_completed_run.py`:
   - compose v2 from the engine snapshot's `travel_network` rows;
   - v1 composition remains available for legacy runs.
6. In `src/experiments/infrastructure_publication.py`:
   - publish v2 with the same receipt statuses and atomicity;
   - accept/read v1 without rewriting it.
7. Do not add a settings key, store version, or database migration.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class TravelRouteRecord:
    origin_location_id: EntityId
    destination_location_id: EntityId
    status: str
    seasonal_availability: str
    blockage_cause: str
    duration_ticks: int
    fatigue_cost: float
    capacity: int
    risk: float
    infrastructure_quality: float
    as_of_tick: int
```

- v2 is canonical; v1 remains decodable and byte-verifiable.
- Route rows are objective only; no owner beliefs in this snapshot.
- No score, planner, or remote-topology field.

### Requirement Evidence

- `src/simulation/infrastructure_models.py` 32-37/294; `infrastructure_codec.py`; `infrastructure_paging.py`; index surface row.

### Error Handling and Logging

- Stable errors: `travel_route_invalid`, `travel_route_duplicate`,
  `travel_route_cap_exceeded`, `snapshot_v2_requires_routes`.
- `INFO travel_network_snapshot_published version=v2 routes=<n>`.
- No route payload dumps.

### Tests

- `tests/unit/test_travel_network_snapshot.py`:
  - v1 decode unchanged;
  - v2 round-trip/hash;
  - v1/v2 mismatch rejection;
  - route paging keyset/order/limit;
  - summary counts;
  - publication atomic/quota behavior.
- `uv run pytest tests/unit/test_travel_network_snapshot.py tests/unit/test_infrastructure_snapshot.py -q`

### Acceptance Criteria

- Snapshot v2 carries bounded route rows.
- v1 remains readable.
- No new settings/store/migration.

### Verification

- `uv run pytest tests/unit/test_travel_network_snapshot.py tests/unit/test_infrastructure_snapshot.py -q`
- Expected: all pass.

## Task 19: Publish routes through existing read-only surfaces

### Intent

Expose route structure and condition through the same dual-gated,
`SUBJECTIVE_DEBUG` infrastructure surface. No new credential or settings gate.

### Implementation Steps

1. In `src/api/infrastructure_networks_cursor.py`, add the
   `infrastructure_networks_routes` purpose constant and reuse the existing
   TTL/HMAC codec alias. Do not create a second codec implementation.
2. In `src/api/routes/infrastructure_networks.py`:
   - add `GET /v1/simulations/{run_id}/infrastructure-networks/routes`;
   - increment `INFRASTRUCTURE_NETWORKS_ROUTE_COUNT` to 7;
   - use the same `_authorize`, `_snapshot`, `_fingerprint`, `_after_key`,
     `_next_cursor`, and `_page` helpers;
   - use the new purpose-bound cursor purpose;
   - return 503 `infrastructure_networks_disabled` when the reader is absent.
3. In `src/api/infrastructure_networks_schemas.py`:
   - add strict `TravelRouteResponse` and `TravelRoutePageResponse` with
     `extra="forbid"`;
   - include status/availability/cause/capacity/risk/quality/as_of_tick;
   - no score/planner/owner fields.
4. In `src/api/app.py` and `src/api/dependencies.py`, verify the existing
   reader attachment/dependency still works; no new settings or reader.
5. In `src/research_runner/infrastructure_composition.py`, verify publication
   writes v2; add `--include-routes` only if the existing CLI already exposes
   snapshot selectors; otherwise no CLI change.
6. Update `docs/research-api.md` route list and the six-to-seven count in a later
   docs phase.
7. Ensure all seven routes are GET-only and require `SUBJECTIVE_DEBUG`.

### Required Interfaces and Contracts

- Route: `GET /v1/simulations/{run_id}/infrastructure-networks/routes`.
- Query: `limit` (default 100, max 500), `after` (opaque signed cursor).
- Response: strict page with `items`, `next_cursor`, `fingerprint`,
  `publication`.
- Dual gate: `PALIMPSEST_INFRASTRUCTURE_NETWORKS_ROOT` and cursor key must both
  be set; otherwise 503 `infrastructure_networks_disabled`.
- No POST/PUT/PATCH/DELETE.

### Requirement Evidence

- `src/api/routes/infrastructure_networks.py` 41/213-355; `src/api/infrastructure_networks_schemas.py`; `src/api/infrastructure_networks_cursor.py`; index surface row.

### Error Handling and Logging

- 503 `infrastructure_networks_disabled` when unconfigured.
- 400 `invalid_cursor`, 404 `snapshot_not_found`, 500 `snapshot_corrupt`.
- `INFO infrastructure_routes_read run_id=<id> count=<n>`.
- No route payloads or cursor secrets at INFO.

### Tests

- `tests/unit/test_travel_network_routes.py`:
  - seventh route registered;
  - unset gate 503;
  - auth required;
  - paging/keyset/limit;
  - cursor purpose binding and expiry;
  - corrupt snapshot 500;
  - no write methods.
- `uv run pytest tests/unit/test_travel_network_routes.py tests/unit/test_infrastructure_routes.py -q`

### Acceptance Criteria

- Routes are readable through the existing surface.
- No new settings/store/credential.
- All routes remain read-only and fail closed.

### Verification

- `uv run pytest tests/unit/test_travel_network_routes.py tests/unit/test_infrastructure_routes.py -q`
- Expected: all pass.

## Task 20: Add Research UI and Godot route presentation

### Intent

Present route status and condition without granting either client simulation
authority or a new evidence class.

### Implementation Steps

1. In `clients/research-ui/src/api/infrastructureNetworks.ts`:
   - add `fetchTravelRoutes(runId, limit, after)` using the same base URL and
     credential-free inspect path as the other infrastructure fetchers.
2. In `InfrastructureNetworksPanel.svelte`:
   - add a "Routes" table with status, availability, blockage, duration,
     capacity, risk, quality, and as-of tick;
   - map 503 to the existing disabled message;
   - label the section "Objective route condition";
   - no score, color ranking, or action controls.
3. Update `clients/research-ui/src/views/InfrastructureNetworksPanel.test.ts`
   with route fixtures, ready/disabled/error states, and an assertion that the
   rendered table contains the route rows — not merely that the fetch fixture
   exists. V4-11's patch records a panel that imported a fetcher but never
   rendered its data.
4. In `clients/godot-observer/scripts/view/infrastructure_overlay.gd`:
   - map route status to edge styling: open/restricted/closed;
   - keep the existing forbidden-field rejection and add `score`, `route_score`,
     `planner`;
   - no new overlay kind; reuse the objective infrastructure layer.
5. In `clients/godot-observer/scripts/ui/overlay_legend.gd` and
   `scripts/presentation/evidence_class.gd`, add the route-status legend/class
   mapping; keep the evidence class objective, not subjective or analytical.
6. In `session.gd`, fetch the routes page when the infrastructure overlay is
   enabled; in `main.gd`, apply the payload to the overlay.
7. Add/extend `clients/godot-observer/tests/test_infrastructure_overlay.gd` for
   status mapping, unknown status, forbidden fields, and no-write behavior.
8. Do not import Python, analysis, or persistence from either client.

### Required Interfaces and Contracts

- Research UI fetch is GET-only and read-only.
- Godot overlay maps status, not truth or score.
- Unknown status falls back to neutral styling; malformed payload is ignored.
- No client sends commands or advances ticks.

### Requirement Evidence

- `clients/research-ui/src/views/InfrastructureNetworksPanel.svelte`; `clients/godot-observer/scripts/view/infrastructure_overlay.gd`; `clients/godot-observer/scripts/ui/overlay_legend.gd`; `clients/godot-observer/scripts/presentation/evidence_class.gd`; index surface row.

### Error Handling and Logging

- Research UI surfaces 503/corrupt states; no retry storm.
- `WARN infrastructure_routes_payload_invalid` in Godot; no payload dump.
- Python logs no client payload bodies.

### Tests

- `clients/research-ui`: `pnpm test` / `pnpm check` (pinned commands from the
  repository docs); the panel test asserts rendered route rows.
- `clients/godot-observer`: pinned Godot suite; `failed=0`.
- `uv run pytest tests/unit/test_travel_network_routes.py -q`

### Acceptance Criteria

- Both clients show route status read-only.
- No new evidence class or overlay kind.
- Godot forbidden-field tests pass.

### Verification

- Research UI test/check commands from `docs/development.md`.
- Godot command from `docs/development.md`.
- Expected: both green; no writes.

## Phase Risks and Mitigations

- Risk: the new route route breaks the pinned six-route count.
  Mitigation: update the count to seven in code/tests/docs deliberately and keep
  all other infrastructure routes unchanged.
- Risk: v2 snapshot breaks v1 readers.
  Mitigation: dual decode + byte verification + publication tests.
- Risk: presentation implies a route score.
  Mitigation: no score fields; labels say "objective route condition".

## Phase Completion Checklist

- Every task above satisfies its acceptance criteria.
- `index.md` checkboxes for Tasks 17-20 are updated after verification.
- No phase file contains task checkboxes.
