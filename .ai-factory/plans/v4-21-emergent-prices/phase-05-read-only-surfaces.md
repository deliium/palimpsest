# Phase 5: Read-Only Surfaces

Plan: [index.md](index.md)
Tasks: 17-18
Depends on: Phase 4 / Tasks 14-16

## Objective

Serve the published snapshot through seven GET-only, dual-gated `/v1` routes and
add one read-only Research UI panel. No Godot overlay is added.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/api/routes/market_institutions.py` | 30-58, 98-167, 223-458 | Route/gate/cursor/error pattern to mirror |
| `src/api/market_institutions_schemas.py` | 31-203 | Strict frozen Pydantic response models |
| `src/api/market_institutions_cursor.py` | 15-17 | Purpose cursor alias pattern |
| `src/api/app.py` | 44, 537-564, 719-733, 750-778 | Reader attachment and router inclusion |
| `src/api/routes/__init__.py` | 25-26, 61 | Router export pattern |
| `src/infrastructure/settings.py` | 252-255, 448-457, 831-843 | Dual gate settings |
| `clients/research-ui/src/api/marketInstitutions.ts` | 1-40, 139-155 | Existing typed client and `CAPABILITY = 'subjective_debug'` pattern |
| `clients/research-ui/src/views/MarketInstitutionsPanel.svelte` | 1-120 | Read-only panel convention |
| `clients/research-ui/src/views/MarketInstitutionsPanel.test.ts` | 1-120 | Panel test convention |
| `clients/research-ui/src/views/RunOverview.svelte` | 51, 110-130, 355-365 | Import, view registry, and render mount point |
| `clients/research-ui/src/research/selection.ts` | 7-70 | `RESEARCH_UI_VIEWS` and `RUN_SCOPED_VIEWS` membership |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/api/emergent_prices_schemas.py` | create | Strict frozen response/page models |
| `src/api/emergent_prices_cursor.py` | create | Cursor codec alias and TTL |
| `src/api/routes/emergent_prices.py` | create | Seven GET-only routes |
| `src/api/routes/__init__.py` | modify | Export router |
| `src/api/app.py` | modify | Attach reader, include router |
| `clients/research-ui/src/api/emergentPrices.ts` | create | Typed read-only client and response types |
| `clients/research-ui/src/views/EmergentPricesPanel.svelte` | create | Read-only panel |
| `clients/research-ui/src/views/EmergentPricesPanel.test.ts` | create | Panel tests |
| `clients/research-ui/src/research/selection.ts` | modify | Add `emergent-prices` to `RESEARCH_UI_VIEWS` and `RUN_SCOPED_VIEWS` |
| `clients/research-ui/src/views/RunOverview.svelte` | modify | Import, view tab, and render branch |

## Task 17: Add seven GET-only dual-gated price routes

### Intent

Expose the published distribution read model with the same fail-closed and
cursor discipline as every other V4 surface.

### Implementation Steps

1. `src/api/emergent_prices_schemas.py`: frozen strict Pydantic models
   (`extra="forbid"`) for `PriceUnitOut`, `PriceExpectationOut`,
   `PriceQuoteOut`, `PriceDistributionOut`, `PriceMarketOut`, `PriceRelationOut`,
   `EmergentPricesSummaryOut`, and six page wrappers plus
   `EmergentPricesMarketsPageOut`. `PriceDistributionOut` exposes
   `sample_source` and the five `bin_shares_milli`; `PriceRelationOut` exposes
   `sample_source`; `PriceExpectationOut` exposes `distribution_source`;
   `PriceQuoteOut` exposes `source_tick`.
2. `src/api/emergent_prices_cursor.py`: alias `EmergentPricesCursorCodec =
   DiplomacyCursorCodec`, `EmergentPricesCursorError = DiplomacyCursorError`,
   `EMERGENT_PRICES_CURSOR_TTL_SECONDS = 900`.
3. `src/api/routes/emergent_prices.py`:
   - `router = APIRouter(prefix="/v1/simulations", tags=["emergent-prices"])`;
   - `EMERGENT_PRICES_ROUTE_COUNT: Final[int] = 7`;
   - `_reader`/`_codec` raise `503 service_unavailable(code=
     "emergent_prices_disabled")` when either app state object is absent;
   - `_authorize` requires `ApiCapability.SUBJECTIVE_DEBUG`;
   - routes:
     1. `GET /v1/simulations/{run_id}/emergent-prices` → summary;
     2. `GET .../emergent-prices/units`;
     3. `GET .../emergent-prices/expectations`;
     4. `GET .../emergent-prices/quotes`;
     5. `GET .../emergent-prices/distributions`;
     6. `GET .../emergent-prices/markets`;
     7. `GET .../emergent-prices/relations`.
4. Every page route accepts `limit: int = 100` (1..500) and
   `window_index: int | None = None` (0..511). `_after_key` decodes the cursor
   and validates run id, publication id, digest, fingerprint, and purpose;
   `_next_cursor` uses the per-purpose row key.
5. Error mapping: missing publication → `404 emergent_prices_run_not_found`;
   corrupt store → `500 emergent_prices_store_corrupt`; expired cursor → `410
   emergent_prices_cursor_expired`; invalid cursor → `400
   emergent_prices_cursor_invalid`.
6. `src/api/app.py`: add `_attach_emergent_prices_reader` requiring both
   settings; install codec via `from_secret` and filesystem reader; otherwise set
   state to `None` and log `emergent_prices_attach enabled=false`. Include the
   router after market institutions and before `/version`.
7. `routes/__init__.py`: export `router as emergent_prices_router` and add it to
   `__all__`.

### Required Interfaces and Contracts

- Exactly seven routes; all GET; no POST/PUT/PATCH/DELETE.
- Default limit 100, max 500; `window_index ≤ 511`.
- Cursor is bound to `window_index`; a cursor minted for another window is
  rejected 400.
- No route returns a canonical price, composite score, ranking, severity, or
  recommendation.
- No observer protocol or capability name changes.

### Requirement Evidence

- Route/gate/cursor pattern: `api/routes/market_institutions.py:30-458`.
- Dual gate: `settings.py:252-255,831-843`; app wiring `app.py:537-564,733,772`.
- Research capabilities: `.ai-factory/ARCHITECTURE.md` "LLM and outer composition".

### Error Handling and Logging

- `INFO emergent_prices_route_served purpose=<token>` counts only.
- Never log run ids, cursor keys, cursor payloads, publication ids, item kinds,
  units, or ratios.

### Tests

- `tests/unit/test_emergent_prices_api.py`: all seven routes registered; gate
  unset → 503 on each; missing run → 404; corrupt store → 500; cursor window
  mismatch → 400; limit bounds; purpose paging.
- `tests/architecture/test_emergent_prices_boundaries.py`: API imports no
  analysis/experiments; only GET routes; route count seven.

### Acceptance Criteria

- Every route fails closed when either setting is unset.
- Paged output is strictly cursor-bound and deterministic.
- No Godot or observer protocol surface changes.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_api.py tests/architecture/test_emergent_prices_boundaries.py -q`
- Expected: all pass.

## Task 18: Add the Research UI price client and panel

### Intent

Give researchers a read-only view of distributions and convergence without
adding any authority or write path.

### Implementation Steps

1. `clients/research-ui/src/api/emergentPrices.ts`: export `CAPABILITY =
   'subjective_debug'`, the seven response shapes, and `getSummary`, `getUnits`,
   `getExpectations`, `getQuotes`, `getDistributions`, `getMarkets`,
   `getRelations`, each using `apiFetch` with run id, limit, optional
   `windowIndex`, and cursor; no mutation helpers.
2. `clients/research-ui/src/views/EmergentPricesPanel.svelte`: sections for
   summary, units, expectations, distributions, markets, and
   convergence/divergence; display counts, quantile columns, sample source and
   count, five bin shares, overlap milli, and closed relation tokens; show an
   explicit `disabled` / `missing` / `partial` state. Mirror
   `MarketInstitutionsPanel.svelte` props `{runId, selection}` and styling.
3. `clients/research-ui/src/research/selection.ts`: add `'emergent-prices'` to
   both `RESEARCH_UI_VIEWS` and `RUN_SCOPED_VIEWS`.
4. `clients/research-ui/src/views/RunOverview.svelte`: import the panel, add
   `{ id: 'emergent-prices', label: 'Emergent prices' }` after
   `market-institutions`, and add the `{:else if view === 'emergent-prices'}`
   render branch after the market branch.
5. Add `EmergentPricesPanel.test.ts` using the existing market panel fixture
   style; assert no write controls, no canonical-price label, and explicit
   empty/partial states.

### Required Interfaces and Contracts

- UI is read-only: no forms, no mutation calls, no local derived "price".
- Distributions render quantiles and samples; convergence renders a closed
  relation token.
- Missing coverage renders an explicit empty state, never zeros as data.

### Requirement Evidence

- User request: "Support analytical price distributions rather than one
  canonical price"; "Measure convergence/divergence between markets".
- Client read-only contract: `.ai-factory/ARCHITECTURE.md` V3-40 through V3-42 seam.

### Error Handling and Logging

- Client surfaces HTTP status/code text; it logs nothing server-side.
- No run ids, tokens, or row content in browser console logs.

### Tests

- `clients/research-ui/src/views/EmergentPricesPanel.test.ts` (vitest): panel
  renders summary/distribution/relation rows; disabled state; no mutation
  import; formatting of milli values and five bin shares.
- `svelte-check` with the app tsconfig.

### Acceptance Criteria

- The panel is mounted and read-only.
- Types match API schemas.
- No Godot file is changed for this feature.

### Verification

- `cd clients/research-ui && ./node_modules/.bin/vitest run`
- `cd clients/research-ui && ./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json`
- Expected: all pass with 0 errors.

## Phase Risks and Mitigations

- Risk: a UI label implies a canonical market price.
  Mitigation: labels say "distribution", "median ratio", "overlap"; tests reject
  canonical-price wording.
- Risk: route count drift.
  Mitigation: `EMERGENT_PRICES_ROUTE_COUNT = 7` asserted by unit and
  architecture tests.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
