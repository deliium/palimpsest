# Phase 5: Read-Only Surfaces

Plan: [index.md](index.md)
Tasks: 13-15
Depends on: Phase 4 / Tasks 10-12

## Objective

Expose the published trade-network snapshot through seven GET-only, dual-gated
API routes and read-only Research UI and Godot presentations. No client gains
write authority, cognition access, or raw payload leakage.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/api/routes/inter_society_relations.py` | route count 49; disabled 65-74; auth 76-80; summary/paged routes 282-531 | Exact API pattern. |
| `src/api/inter_society_relations_schemas.py` | page/summary schemas | Schema pattern. |
| `src/api/inter_society_relations_cursor.py` | `INTER_SOCIETY_RELATIONS_CURSOR_TTL_SECONDS = 900`; codec alias | Cursor pattern. |
| `src/api/dependencies.py` | reader getters 182-191 | Dependency pattern. |
| `src/api/app.py` | attach readers 478-515; include routers 641-677 | Composition root. |
| `clients/research-ui/src/api/interSocietyRelations.ts` | full client | UI API pattern. |
| `clients/research-ui/src/views/InterSocietyRelationsPanel.svelte` | full panel | UI panel pattern. |
| `clients/research-ui/src/views/RunOverview.svelte` | imports 117-119; tabs 347-352 | Panel wiring. |
| `clients/research-ui/src/research/selection.ts` | keys 23-25/60-62 | Selection wiring. |
| `clients/godot-observer/scripts/view/infrastructure_overlay.gd` | layers 1-120; forbidden scan 86-97 | Godot overlay pattern. |
| `clients/godot-observer/scripts/view/migration_overlay.gd` | four-layer style 1-237 | Godot analytical overlay pattern. |
| `clients/godot-observer/scripts/main.gd` | toggles 544-566; payload dispatch 609 | Overlay wiring. |
| `clients/godot-observer/scripts/net/session.gd` | fetch methods 1626-1648 | Snapshot fetch pattern. |
| `clients/godot-observer/tests/run_protocol.gd` | suite registration 33 | Test registration. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/api/routes/trade_networks.py` | create | Seven GET-only routes, dual gate, paging, safe errors. |
| `src/api/trade_networks_schemas.py` | create | Strict response schemas for each page/summary. |
| `src/api/trade_networks_cursor.py` | create | Purpose-bound HMAC cursor codec (900 s TTL). |
| `src/api/dependencies.py` | modify | `get_trade_networks_reader`. |
| `src/api/app.py` | modify | Attach reader/codec and include router. |
| `clients/research-ui/src/api/tradeNetworks.ts` | create | Typed fetch client for seven routes. |
| `clients/research-ui/src/views/TradeNetworksPanel.svelte` | create | Read-only corridor/flow/location/dependence/cross-society/network panel. |
| `clients/research-ui/src/views/TradeNetworksPanel.test.ts` | create | Present/disabled/empty/error tests. |
| `clients/research-ui/src/views/RunOverview.svelte` | modify | Import, tab, render. |
| `clients/research-ui/src/research/selection.ts` | modify | Add the trade-networks selection key. |
| `clients/godot-observer/scripts/view/trade_overlay.gd` | create | Corridor, major-location, and cross-society layers. |
| `clients/godot-observer/tests/test_trade_overlay.gd` | create | Layer, forbidden-field, and empty-state tests. |
| `clients/godot-observer/fixtures/protocol/civilization/overlay_trade.json` | create | Deterministic fixture. |
| `clients/godot-observer/scripts/view/world_view.gd` | modify | Instantiate/apply/enable/clear the trade overlay. |
| `clients/godot-observer/scripts/main.gd` | modify | Toggle and payload dispatch. |
| `clients/godot-observer/scripts/net/session.gd` | modify | Fetch the trade summary/corridors/locations. |
| `clients/godot-observer/tests/run_protocol.gd` | modify | Register the new suite. |
| `tests/unit/test_trade_networks_routes.py` | create | Route count, disabled, auth, paging, corruption. |
| `tests/unit/test_trade_networks_api_cursor.py` | create | Purpose binding and expiry. |

## Task 13: Add seven GET-only dual-gated trade-network API routes

### Intent

Provide the researcher API over the published snapshot without importing
analysis or experiments and without granting write authority.

### Implementation Steps

1. Create `src/api/routes/trade_networks.py` with
   `router = APIRouter(prefix="/v1/simulations",
   tags=["trade-networks"])` and `TRADE_NETWORKS_ROUTE_COUNT: Final[int] = 7`.
2. Implement helpers:
   - `_reader(reader)` raises `service_unavailable(code="trade_networks_disabled")`
     when `None`.
   - `_codec(request)` returns `TradeNetworksCursorCodec` or the same 503.
   - `_authorize(request, settings)` calls
     `require_http_capability(..., capability=ApiCapability.SUBJECTIVE_DEBUG)`.
   - `_snapshot(reader, run_id)` maps
     `trade_networks_store_corrupt` to `internal(code=...)`; absent run is 404
     with `trade_networks_run_not_found`.
3. Add exactly seven GET routes:
   - `GET /{run_id}/trade-networks` -> summary
   - `GET /{run_id}/trade-networks/corridors`
   - `GET /{run_id}/trade-networks/flows`
   - `GET /{run_id}/trade-networks/locations`
   - `GET /{run_id}/trade-networks/dependence`
   - `GET /{run_id}/trade-networks/cross-society`
   - `GET /{run_id}/trade-networks/networks`
4. Every paged route accepts `cursor: str | None`,
   `limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT)`, and
   `window_index: int | None = Query(default=None, ge=0, le=511)`, binds the
   cursor purpose, and calls the matching paging function with a filter-bound
   fingerprint.
5. Create strict Pydantic response schemas in
   `src/api/trade_networks_schemas.py`; use `model_config =
   ConfigDict(extra="forbid")` and only scalar/row fields already in the
   snapshot. Expose network `status`, `previous_network_ids`,
   `next_network_ids`, `rerouted`, `sustained`; cross-society anchors and
   overlap count; location `trade_post_present`; flow `cross_location_count`;
   and summary lineage/venue counts. Do not expose analysis notices, raw
   events, item ids, person ids, prompts, or payloads.
6. Create `src/api/trade_networks_cursor.py` reusing the diplomacy cursor codec
   (same as existing V4 cursor aliases) with
   `TRADE_NETWORKS_CURSOR_TTL_SECONDS = 900`.
7. Add `get_trade_networks_reader(request)` in `src/api/dependencies.py`.
8. In `src/api/app.py` add `_attach_trade_networks_reader(app)` that sets
   `trade_networks_cursor_codec` and `trade_networks_reader` only when both
   settings are present; log `trade_networks_attach enabled=...` without the
   secret. Include `trade_networks_router`.
9. Do not import `analysis`, `experiments`, or `persistence` concrete stores
   from the route module; only the reader protocol/objects injected by the app.

### Required Interfaces and Contracts

- Seven routes, all GET, all `SUBJECTIVE_DEBUG`.
- Unconfigured root/key -> 503 `trade_networks_disabled`.
- Corrupt store -> 500 `trade_networks_store_corrupt`.
- Purpose-bound cursors; a cursor from one route is rejected by another.
- No write, mutation, capture, or control route is added.
- `/v1` stays the only API version.

### Error Handling and Logging

- `INFO trade_networks_api_disabled` on 503; `ERROR
  trade_networks_store_corrupt` on corruption.
- `DEBUG trade_networks_api purpose=%s` only.
- Never log cursor contents, credentials, item ids, person ids, or row payloads.

### Tests

- `tests/unit/test_trade_networks_routes.py`:
  - `test_route_count_is_seven_and_all_get`
  - `test_disabled_without_root_or_key`
  - `test_requires_subjective_debug`
  - `test_summary_and_each_page_round_trip`
  - `test_cursor_purpose_mismatch_rejected`
  - `test_window_filter_applies_to_every_paged_route`
  - `test_cursor_from_other_window_is_rejected`
  - `test_network_status_and_cross_society_anchors_round_trip`
  - `test_corrupt_store_returns_safe_error`
  - `test_absent_run_returns_not_found`
- `tests/unit/test_trade_networks_api_cursor.py`:
  - `test_cursor_ttl_and_purpose`
  - `test_tampered_cursor_rejected`

### Acceptance Criteria

- Exactly seven GET routes exist and are dual-gated.
- Every page returns canonical snapshot rows within the requested limit.
- No route imports analysis, experiments, or a concrete store.

### Verification

- `uv run pytest tests/unit/test_trade_networks_routes.py tests/unit/test_trade_networks_api_cursor.py -q`
- Expected result: all tests pass; disabled and auth paths fail closed.

## Task 14: Add Research UI trade-network API client and panel

### Intent

Let researchers inspect trade corridors, flows, dependence, major locations, and
cross-society flows without implying a central trade model or a score.

### Implementation Steps

1. Create `clients/research-ui/src/api/tradeNetworks.ts` with typed functions
   for all seven routes, a shared disabled/error result shape, and no direct
   `fetch` outside the existing API helper conventions.
2. Create `TradeNetworksPanel.svelte` with six read-only sections:
   - Corridors: from/to, window, transfer count, class counts.
   - Flows: class totals, imports, exports, local.
   - Locations: major flag, in/out/local, corridor degree.
   - Dependence: class, imported, locally originated, milli ratio,
     `high_dependence`, coverage.
   - Cross-society: pair ids, society ids, class counts, direction counts.
   - Networks: network id, status/lineage counts, corridors, locations.
   Show network `status`/`rerouted`/`sustained`, cross-society anchor
   locations, `trade_post_present`, and `cross_location_count`. Provide a
   `window_index` selector that passes the API filter. Show `Trade networks are
   disabled for this run.` on 503 and an empty state without inventing a
   network.
3. Use existing formatting/selection/error components and the established
   epistemic chrome; do not add a global state store.
4. Wire the panel in `RunOverview.svelte` (import, tab, render) and add the
   selection key in `selection.ts`.
5. Create `TradeNetworksPanel.test.ts` covering present data, disabled, empty,
   malformed response, and no-score/no-money copy.
6. Keep all copy descriptive: "exchange evidence", "observed dependence",
   "analytical network", never "market price", "trade score", or "planned
   route".

### Required Interfaces and Contracts

- Read-only: no fetch mutates state; no route is called with a write method.
- The panel never displays raw event payloads or person/item identifiers beyond
  the snapshot row fields.
- `trade_networks@1` and snapshot version labels may be shown; no claim of
  objective society or money.

### Error Handling and Logging

- Disabled -> explicit empty/disabled copy.
- Network/parse error -> safe error banner with no response body.
- No client-side console logging of payloads.

### Tests

- `clients/research-ui`: `npx vitest run` includes
  `TradeNetworksPanel.test.ts`.
- `npx svelte-check --tsconfig ./tsconfig.app.json` -> 0 errors, 0 warnings.

### Acceptance Criteria

- The panel renders all six sections for a present snapshot.
- Disabled and empty states are explicit and non-fabricating.
- No score, money, price, or central-routing language appears.

### Verification

- `cd clients/research-ui && npx vitest run`
- `cd clients/research-ui && npx svelte-check --tsconfig ./tsconfig.app.json`
- Expected result: all UI tests pass; 0 TypeScript/Svelte errors.

## Task 15: Add Godot trade-network overlay and fixtures

### Intent

Give the read-only observer a spatial presentation of corridors, major exchange
locations, and cross-society flows without turning analysis into world authority.

### Implementation Steps

1. Create `clients/godot-observer/scripts/view/trade_overlay.gd`:
   - Four layers: `corridors`, `major_locations`, `cross_society`, `coverage`.
   - Corridor line color by flow class or coverage, not by score; major
     locations use a marker; trade-post locations use a distinct venue marker;
     network status/sustained rows use labels only; cross-society rows use pair
     links only when both society anchors resolve to known locations.
   - Scan loaded payloads for forbidden fields (`price`, `money`, `currency`,
     `planner`, `quota`, `allocation`, `score`, `ranking`) and reject the
     overlay with a safe code rather than rendering it.
   - Empty/missing snapshot -> no-op with a status message.
2. Add a deterministic fixture
   `clients/godot-observer/fixtures/protocol/civilization/overlay_trade.json`
   containing a reverse corridor pair, a sustained network status, a major
   location, a trade-post location, and one cross-society pair with resolved and
   unresolved anchor variants.
3. Wire the overlay in `world_view.gd` (instantiate/apply/enable/clear),
   `main.gd` (toggle and payload dispatch), and `session.gd` (fetch summary,
   corridors, locations, cross-society, and networks; pass `window_index` when
   the overlay has a selected window).
4. Register `test_trade_overlay.gd` in `tests/run_protocol.gd`.
5. Do not add a new overlay protocol, semantic event type, or world coordinate
   authority; overlays remain presentation-only.

### Required Interfaces and Contracts

- The client never imports or executes Python analysis.
- Overlay selection never mutates world state or advances the simulation.
- Unresolved society anchors are skipped with a bounded status count.
- Forbidden-field payloads are rejected, not partially rendered.

### Error Handling and Logging

- Safe client status codes only; no payload dump.
- Missing routes/503 -> overlay disabled message.

### Tests

- `clients/godot-observer/tests/test_trade_overlay.gd`:
  - `test_corridor_layer_renders_expected_lines`
  - `test_major_location_markers`
  - `test_cross_society_layer_uses_resolved_anchor`
  - `test_cross_society_layer_skips_unresolved_anchor`
  - `test_network_status_and_sustained_markers`
  - `test_trade_post_marker_is_distinct_from_major_location`
  - `test_forbidden_score_payload_is_rejected`
  - `test_empty_snapshot_is_noop`
- Pinned suite:
  `"${GODOT_BIN}" --headless --editor --path clients/godot-observer --quit`
  then
  `"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd`.

### Acceptance Criteria

- The overlay renders the fixture and skips unresolved anchors.
- Forbidden fields reject the whole trade overlay.
- The protocol suite reports `failed=0`.

### Verification

- Pinned Godot editor pass then protocol suite; expected `godot_protocol_tests
  failed=0`.
- If no Godot binary is available, record `unexecuted` with the exact
  prerequisite in Task 22.

## Phase Risks and Mitigations

- Risk: API schemas could accidentally expose analysis internals.
  Mitigation: strict `extra="forbid"` schemas over snapshot fields only.
- Risk: UI/Godot could present analytical rows as objective facts.
  Mitigation: explicit labels and no score/money copy; negative tests.
- Risk: cross-society anchors may not resolve in the client.
  Mitigation: bounded skip with a status count, never a guessed location.

## Phase Completion Checklist

- Every Task 13-15 acceptance criterion is satisfied.
- Required verification commands pass or are recorded `unexecuted` with
  prerequisites.
- `index.md` task checkboxes are updated immediately after verified completion.
