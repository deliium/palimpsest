# Phase 5: Read-Only Surfaces

Plan: [index.md](index.md)
Tasks: 17-18
Depends on: Phase 4 / Tasks 14-16

## Objective

Expose the published snapshot through seven GET-only, dual-gated API routes and
one read-only Research UI panel. No Godot overlay is added: market-like
institutions are detached analytical structures, and the existing presentation
suite remains the regression gate.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/api/routes/trade_networks.py` | router/count (50-52), authorize (70-73), gates (55-67), cursor errors (109-138), routes (170-569) | Route/gate/cursor pattern |
| `src/api/trade_networks_schemas.py` | strict schemas (24-158) | `extra="forbid"` response models |
| `src/api/trade_networks_cursor.py` | codec alias (13-15) | Reuse the shared HMAC cursor codec |
| `src/api/diplomacy_cursor.py` | TTL and HMAC payload (21,40-105) | Cursor implementation |
| `src/api/app.py` | reader attach (480-507), call (700), include (738), import (55) | Composition-root wiring |
| `src/api/security.py` | `SUBJECTIVE_DEBUG` (49), capability check (130-156,186-199) | Credential gate |
| `src/api/errors.py` | `service_unavailable`/`internal`/`not_found` (64-73) | Error envelope |
| `clients/research-ui/src/api/tradeNetworks.ts` | fetchers (120-196) | Client shape |
| `clients/research-ui/src/views/TradeNetworksPanel.svelte` | load/error handling (51-91) | Panel shape |
| `clients/research-ui/src/views/RunOverview.svelte` | import/nav/render (50,122,357-358) | Mount point |
| `clients/research-ui/src/research/selection.ts` | view ids (26,65) | Selection registry |
| `clients/research-ui/src/views/TradeNetworksPanel.test.ts` | read-only/disabled/empty tests (158-239) | UI test pattern |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/api/market_institutions_schemas.py` | create | Strict response models |
| `src/api/market_institutions_cursor.py` | create | Purpose-bound cursor codec alias |
| `src/api/routes/market_institutions.py` | create | Seven GET routes |
| `src/api/app.py` | modify | Attach reader/codec and include router |
| `clients/research-ui/src/api/marketInstitutions.ts` | create | Seven fetchers |
| `clients/research-ui/src/views/MarketInstitutionsPanel.svelte` | create | Read-only panel |
| `clients/research-ui/src/views/RunOverview.svelte` | modify | Nav entry and render branch |
| `clients/research-ui/src/research/selection.ts` | modify | View registry entries |

## Task 17: Add seven GET-only dual-gated market API routes

### Intent

Serve the published artifact with the same credentialed, fail-closed contract as
other V4 read surfaces, and bind cursors to the requested window filter.

### Implementation Steps

1. Create `src/api/market_institutions_schemas.py` with strict Pydantic models
   (`extra="forbid"`) for:
   - `MarketInstitutionsSummaryOut`;
   - `MarketVenuesPageOut`, `MarketGatheringsPageOut`,
     `MarketExpectationsPageOut`, `MarketRolesPageOut`,
     `MarketRecordsPageOut`, `MarketMarketsPageOut`;
   - one row model per snapshot row type plus `next_cursor`, `window_index`, and
     `coverage`.
   Field names mirror the snapshot exactly; no aliases, computed scores, or
   recommendations.
2. Create `src/api/market_institutions_cursor.py`:
   - `MarketInstitutionsCursorCodec = DiplomacyCursorCodec` alias;
   - `MARKET_INSTITUTIONS_CURSOR_TTL_SECONDS = 900` re-exported for tests.
3. Create `src/api/routes/market_institutions.py`:
   - `router = APIRouter(prefix="/v1/simulations", tags=["market-institutions"])`;
   - `MARKET_INSTITUTIONS_ROUTE_COUNT = 7`;
   - `_reader(request)` returns `service_unavailable(code=
     "market_institutions_disabled")` when either the reader or codec is
     `None`;
   - `_authorize` calls `require_http_capability(...,
     capability=ApiCapability.SUBJECTIVE_DEBUG)`;
   - seven GET routes:
     1. `/{run_id}/market-institutions` → summary;
     2. `/{run_id}/market-institutions/venues` → venues;
     3. `/{run_id}/market-institutions/gatherings` → gatherings;
     4. `/{run_id}/market-institutions/expectations` → expectations;
     5. `/{run_id}/market-institutions/roles` → roles;
     6. `/{run_id}/market-institutions/records` → records;
     7. `/{run_id}/market-institutions/markets` → candidates and lineage rows;
   - query parameters: `limit: int = 100` (`ge=1, le=500`), `cursor: str |
     None`, `window_index: int | None` (`ge=0, le=511`);
   - cursor decode failures: expired → 410
     `market_institutions_cursor_expired`; all others → 400
     `market_institutions_cursor_invalid`; fingerprint/run/publication/digest
     mismatch → 400;
   - store decode failure `market_institutions_store_corrupt` → 500 internal;
     other read failures → 404 `market_institutions_run_not_found`.
4. In `src/api/app.py`:
   - add `_attach_market_institutions_reader(app, settings)` mirroring
     `_attach_trade_networks_reader`; when either setting is absent set
     `app.state.market_institutions_reader = None` and
     `app.state.market_institutions_cursor_codec = None`;
   - otherwise build `create_market_institutions_reader(root)` and
     `MarketInstitutionsCursorCodec.from_secret(secret)`;
   - call the attach function and include the router in the same block as the
     sibling V4 routers.
5. Keep every route GET-only; add no write, POST, or mutation route.

### Required Interfaces and Contracts

- All seven routes require `x-palimpsest-token` with `subjective_debug`; query
  string credentials are rejected by existing middleware.
- Missing either setting yields 503 `market_institutions_disabled` before any
  store access.
- `window_index` filters both rows and the cursor fingerprint; a cursor for a
  different window is rejected with 400.
- Default limit is 100 and the maximum is 500; no route returns an unbounded
  page.
- Response models reject unknown fields and never add price, money, score,
  ranking, severity, or recommendation.

### Requirement Evidence

- Original Request: "Detect market-like persistence analytically."
- `src/api/routes/trade_networks.py:50-569` — route/gate/cursor contract.
- `docs/configuration.md:539-558` — dual-gate documentation pattern.

### Error Handling and Logging

- WARN: `market_institutions_route_disabled`, `market_institutions_cursor_invalid`
  with reason code only.
- ERROR: `market_institutions_store_corrupt` at the route boundary.
- Never log the cursor token, cursor key, run id, publication id, digest, window
  filter, or response rows.

### Tests

- `tests/unit/test_market_institutions_routes.py`: route count 7 and all GET;
  each route returns 503 with either setting missing; 401/403 gate cases;
  default/max limit; `window_index` bounds; cursor round-trip and cross-window
  rejection; corrupt store 500; missing run 404; strict schemas.
- `tests/integration/test_market_institutions_store_api.py` (DB-free,
  `pytest.mark.integration`): publish a real snapshot to a temp root, build an
  app with both settings, read summary and one paged route, assert 200 and row
  identity.

### Acceptance Criteria

- All seven routes are registered and GET-only.
- A cursor created for `window_index=1` returns 400 on `window_index=2` and 200
  on `window_index=1`.

### Verification

- `uv run pytest tests/unit/test_market_institutions_routes.py -q`
- `uv run pytest tests/integration/test_market_institutions_store_api.py -q -m integration`
- Expected result: all pass.

## Task 18: Add the Research UI market client and panel

### Intent

Give researchers a read-only view of venue recurrence, expectations, roles,
records, and lineage, with the same disable/empty/error behavior as sibling V4
panels.

### Implementation Steps

1. Create `clients/research-ui/src/api/marketInstitutions.ts`:
   - `CAPABILITY = 'subjective_debug'`;
   - `base(runId)` → `/v1/simulations/${runId}/market-institutions`;
   - `query({cursor, limit = 200, windowIndex})` adds `cursor`, `limit`, and
     `window_index` only when present;
   - seven fetchers: summary, venues, gatherings, expectations, roles, records,
     markets;
   - no `method` option; `apiFetch` defaults to GET.
2. Create `clients/research-ui/src/views/MarketInstitutionsPanel.svelte`:
   - load summary plus six pages in parallel;
   - map 503/`market_institutions_disabled` to an `unavailable` state and other
     failures to a safe generic error;
   - render counts and closed status/alignment/label tokens only;
   - show no price, money, score, ranking, recommendation, allocation, or quota
     text.
3. Mount the panel:
   - import it in `RunOverview.svelte`;
   - add `{ id: 'market-institutions', label: 'Market-like institutions' }` to
     the nav list;
   - add the render branch.
4. Add `'market-institutions'` to `RESEARCH_UI_VIEWS` and
   `RUN_SCOPED_VIEWS` in `research/selection.ts`.
5. Add `clients/research-ui/src/views/MarketInstitutionsPanel.test.ts`:
   - renders rows from mocked fetchers;
   - unavailable state on 503;
   - empty state;
   - malformed payload shows a safe error;
   - the rendered text contains none of `price`, `money`, `currency`,
     `market score`, `ranking`, `recommendation`.
6. Do not modify `clients/godot-observer/`.

### Required Interfaces and Contracts

- The panel is read-only: no POST, no local persistence, no mutation of server
  state.
- All displayed values are counts, closed tokens, or timestamps already present
  in the API response; the client computes no score or rank.
- The panel tolerates a missing page and renders the summary plus an empty
  section instead of failing the whole view.

### Requirement Evidence

- `clients/research-ui/src/views/TradeNetworksPanel.svelte:51-91` — load and
  unavailable handling.
- `tests/architecture/test_v4_architecture_invariants.py:309-327` — read-only
  client guard.
- Original Request: analytical detection only; no market UI authority.

### Error Handling and Logging

- Client-side errors are user-facing strings with no server payload echo.
- No console logging of rows, tokens, cursors, or capability secrets.
- The panel never retries with a different credential.

### Tests

- `cd clients/research-ui && ./node_modules/.bin/vitest run src/views/MarketInstitutionsPanel.test.ts`
- `cd clients/research-ui && npx svelte-check --tsconfig ./tsconfig.app.json`

### Acceptance Criteria

- The panel appears in the run overview and loads all seven endpoints through GET
  only.
- The 503 state reads as unavailable, not as an error or empty market.
- No forbidden commercial vocabulary appears in the component or its test.

### Verification

- `cd clients/research-ui && npx vitest run`
- `cd clients/research-ui && npx svelte-check --tsconfig ./tsconfig.app.json`
- Expected result: 0 failed tests, 0 type errors.

## Phase Risks and Mitigations

- Risk: a route reads the store before checking the dual gate.
  Mitigation: `_reader` runs before any store call and is tested for both
  missing settings.
- Risk: cursor filters drift from row filters.
  Mitigation: one fingerprint function binds `window_index` and `limit`, and a
  cross-window cursor test proves rejection.
- Risk: UI text implies a price or score. Mitigation: the UI test scans rendered
  text and the architecture test scans source for forbidden keys.

## Phase Completion Checklist

- Every Task 17-18 acceptance criterion is verified.
- Seven GET-only routes exist; all fail closed with
  `market_institutions_disabled`.
- The Research UI panel is read-only and the Godot client is unchanged.
- `index.md` task checkboxes are updated immediately after verified completion.
