# Phase 5: Read-Only Surfaces

Plan: [index.md](index.md)
Tasks: 17-18
Depends on: Phase 4 (Tasks 14-16)

## Objective

Expose the published snapshot through seven GET-only, dual-gated `/v1` routes
and a read-only Research UI panel. No Godot overlay is added: dependency graphs
and bottleneck rows are non-spatial analytical structures, and the presentation
client stays untouched.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/api/routes/trade_networks.py` | prefix 50; route count 52; `_authorize` 70-73; disabled 57-66; corrupt 82; not found 83-87; cursor 125-136; page defaults 220-223 (`limit=100`, `le=500`, `window_index le=511`); routes 170-569 | Route/gating/default pattern |
| `src/api/trade_networks_schemas.py` | 24-140; page envelope 103-115 (`items`, `next_cursor`) | Strict response schema pattern |
| `src/api/dependencies.py` | reader dependency 194-195 | Reader injection |
| `src/api/app.py` | 479-506 | Reader/cursor attachment gate |
| `src/api/routes/inter_society_relations.py` | 41-90/275-330 | Dual-gated sibling |
| `clients/research-ui/src/api/client.ts` | `apiFetchResponse` 46-96; `ApiClientError` 78-93 | Request helper and error codes |
| `clients/research-ui/src/api/tradeNetworks.ts` | capability 3; types 7-114; `base()` 120; `query()` 124; fetchers 132-196 | Client shape |
| `clients/research-ui/src/views/TradeNetworksPanel.svelte` | `windowIndex()` 37; `load()` 43-96; disabled 85-89 | Panel shape |
| `clients/research-ui/src/research/selection.ts` | `RESEARCH_UI_VIEWS` 7-36; `RUN_SCOPED_VIEWS` 39-72 | View registration |
| `clients/research-ui/src/views/RunOverview.svelte` | imports 49-50; `tabGroups` 67-140; nav 225-246; render 353-356 | Panel mounting |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/api/supply_chain_schemas.py` | create | Strict summary/page models |
| `src/api/routes/supply_chains.py` | create | Seven GET-only routes under `SUBJECTIVE_DEBUG` |
| `src/api/dependencies.py` | modify | `supply_chain_reader` dependency |
| `src/api/app.py` | modify | Attach reader + cursor codec on the dual gate |
| `src/api/routes/__init__.py` | modify | Include the router |
| `clients/research-ui/src/api/supplyChains.ts` | create | Types + fetchers |
| `clients/research-ui/src/views/SupplyChainsPanel.svelte` | create | Read-only panel |
| `clients/research-ui/src/views/SupplyChainsPanel.test.ts` | create | Panel tests |
| `clients/research-ui/src/research/selection.ts` | modify | Register view id |
| `clients/research-ui/src/views/RunOverview.svelte` | modify | Mount panel |
| `tests/unit/test_supply_chain_routes.py` | create | Route/gating/cursor tests |
| `tests/integration/test_supply_chain_store_api.py` | create | DB-free store→API round trip |

## Task 17: Add seven GET-only dual-gated supply-chain API routes

### Intent

Serve the published artifact through the same capability boundary as every
other V4 analytical surface, with a fail-closed disabled state and
window-bound cursors.

### Implementation Steps

1. `src/api/supply_chain_schemas.py`: strict `extra="forbid"` models
   `SupplyChainSummaryOut`, `SupplyStageOut`, `SupplyDependencyOut`,
   `SupplyChainOut`, `SupplyLineageOut`, `SupplyBottleneckOut`,
   `SupplyLocationOut`, `SupplyOrganizationOut`, plus page envelopes
   `SupplyStagesPageOut`, `SupplyDependenciesPageOut`, `SupplyChainsPageOut`,
   `SupplyBottlenecksPageOut`, `SupplyLocationsPageOut`,
   `SupplyOrganizationsPageOut`. Each page is `items: list[...]` and
   `next_cursor: str | None = None` (no extra fields).
2. `src/api/routes/supply_chains.py`:
   - `router = APIRouter(prefix="/v1/simulations", tags=["supply-chains"])`,
     `SUPPLY_CHAIN_ROUTE_COUNT = 7`;
   - `_authorize` requires `ApiCapability.SUBJECTIVE_DEBUG`;
   - `_reader` returns `request.app.state.supply_chain_reader` or raises 503
     `supply_chains_disabled`;
   - routes in order: `GET /{run_id}/supply-chains` (summary),
     `/supply-chains/stages`, `/dependencies`, `/chains`, `/bottlenecks`,
     `/locations`, `/organizations`;
   - list routes accept `cursor: str | None = Query(default=None)`,
     `limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT)`, and
     `window_index: int | None = Query(default=None, ge=0, le=511)`;
   - error mapping: 410 `supply_chains_cursor_expired`;
     400 `supply_chains_cursor_invalid` on any fingerprint mismatch including
     `window_index`; 404 `supply_chains_run_not_found`; 500
     `supply_chains_store_corrupt`.
3. `src/api/dependencies.py`: `get_supply_chain_reader(request)` returning
   `getattr(request.app.state, "supply_chain_reader", None)`.
4. `src/api/app.py`: in the dual-gate block (479-506), attach
   `app.state.supply_chain_reader` and the cursor codec only when both settings
   exist; create the reader through `create_supply_chain_reader`.
5. Include the router in `src/api/routes/__init__.py`. No `/v2`, no mutating
   method.

### Required Interfaces and Contracts

- Exactly seven routes, all GET, all `SUBJECTIVE_DEBUG`.
- Disabled → 503 `supply_chains_disabled` on every route.
- `window_index` is bound into the cursor fingerprint.
- Response models reject unknown fields and never expose claim bodies.

### Requirement Evidence

- `trade_networks.py` 50-136/220-223/170-569;
  `trade_networks_schemas.py` 103-115; `dependencies.py` 194-195;
  `app.py` 479-506; ARCHITECTURE requirement 6.
- Supported combinations: gate unset, corrupt store, missing run, expired
  cursor, mismatched cursor, filtered/unfiltered page, invalid limit.

### Error Handling and Logging

- `DEBUG supply_chain_api_route route=<name> window_index=<n|->`.
- `WARN supply_chains_disabled route=<name>` once per request.
- Never log cursor values, claims, or snapshot bodies.

### Tests

- `tests/unit/test_supply_chain_routes.py`:
  `test_seven_routes_registered`, `test_all_routes_are_get`,
  `test_disabled_returns_503_code`, `test_requires_subjective_debug`,
  `test_summary_returns_counts`, `test_page_with_window_filter`,
  `test_default_limit_is_100`, `test_window_index_upper_bound`,
  `test_cursor_mismatched_window_is_400`, `test_expired_cursor_is_410`,
  `test_missing_run_is_404`, `test_corrupt_store_is_500`,
  `test_limit_bounds`, `test_no_post_routes`,
  `test_page_envelope_is_items_and_cursor`.
- `tests/integration/test_supply_chain_store_api.py` (DB-free):
  `test_publish_then_read_summary`, `test_publish_then_page_stages`,
  `test_window_filter_round_trip`.
- `uv run pytest tests/unit/test_supply_chain_routes.py -q`;
  `uv run pytest tests/integration/test_supply_chain_store_api.py -q -m integration`.

### Acceptance Criteria

- Seven GET routes appear exactly once in OpenAPI.
- Without both settings every route returns 503.
- A cursor for window 1 is rejected on a window 2 request.

### Verification

- `uv run pytest tests/unit/test_supply_chain_routes.py -q` → all pass.
- `uv run pytest tests/integration/test_supply_chain_store_api.py -q -m integration` → all pass.

## Task 18: Add Research UI supply-chain client and panel

### Intent

Give researchers a read-only view of stages, dependency edges, chains,
bottlenecks, locations, and organization attribution, with the standard disabled
handling.

### Implementation Steps

1. `clients/research-ui/src/api/supplyChains.ts`:
   - `CAPABILITY = 'subjective_debug'`;
   - types `SupplyChainSummary`, `SupplyStage`, `SupplyDependency`,
     `SupplyChain`, `SupplyLineage`, `SupplyBottleneck`, `SupplyLocation`,
     `SupplyOrganization`, `Page<T>`, `SupplyListOptions` (`limit`, `cursor`,
     `windowIndex`);
   - `base(runId)` → `/v1/simulations/${encodeURIComponent(runId)}/supply-chains`;
   - `query()` adds `limit`, `cursor`, `window_index` only when set;
   - fetchers for summary and the six pages.
2. `SupplyChainsPanel.svelte`: props `runId`, optional `initialWindowIndex`;
   state `summary`, `stages`, `dependencies`, `chains`, `bottlenecks`,
   `locations`, `organizations`, `windowIndex`, `status`
   (`idle|loading|ready|unavailable|error`); `load()` fetches summary then the
   six pages; `ApiClientError` with `supply_chains_disabled` or 503 →
   `unavailable` with the message "Supply chains are not published for this
   run."; render summary counts/coverage, stage table, dependency table, chain
   list, bottleneck table, location/organization tables; window selector clears
   the cursor on change; no severity sorting, no recommendation UI.
3. `research/selection.ts`: add `'supply-chains'` to `RESEARCH_UI_VIEWS` and
   `RUN_SCOPED_VIEWS` in alphabetical position.
4. `RunOverview.svelte`: import the panel, add a `Supply chains` tab row, and a
   `{:else if view === 'supply-chains'}` render branch.

### Required Interfaces and Contracts

- Read-only: no POST/PUT/PATCH/DELETE.
- The panel never computes a score, rank, or recommendation.
- Cursor resets on window change.
- Absent publication is `unavailable`, not an error toast.

### Requirement Evidence

- `tradeNetworks.ts` 3-196; `TradeNetworksPanel.svelte` 25-96;
  `client.ts` 46-103; `selection.ts` 7-72; `RunOverview.svelte` 49-140/225-356.
- Supported combinations: unavailable, empty, populated, window filter, page
  error.

### Error Handling and Logging

- Errors surface as `ApiClientError` codes; no tokens or payloads logged.
- No `console.log` of response bodies.

### Tests

- `clients/research-ui/src/views/SupplyChainsPanel.test.ts`:
  `renders summary counts`, `renders disabled state for 503`,
  `renders error state`, `renders empty tables`,
  `resets cursor on window change`, `does not render score columns`.
- `cd clients/research-ui && npx vitest run`;
  `cd clients/research-ui && npx svelte-check --tsconfig ./tsconfig.app.json`.

### Acceptance Criteria

- Panel appears in run-scoped nav and renders all six families plus summary.
- 503 shows the disabled message with no retry loop.
- `svelte-check` reports 0 errors and 0 warnings.

### Verification

- `cd clients/research-ui && npx vitest run` → all pass.
- `cd clients/research-ui && npx svelte-check --tsconfig ./tsconfig.app.json` → 0/0.

## Phase Risks and Mitigations

- Risk: a route allows a mutating method or skips capability checks.
  Mitigation: GET-only and auth tests per route.
- Risk: the UI invents ranking. Mitigation: no score columns; negative test.
- Risk: half-configured reader state. Mitigation: partial gates are disabled and
  tested.
- Risk: Godot fixtures drift. Mitigation: locked non-goal; no Godot edits.

## Phase Completion Checklist

- Every Task 17-18 satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
