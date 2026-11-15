# Phase 4: Read Surfaces

Plan: [index.md](index.md)
Tasks: 13-14
Depends on: Phase 3 (Tasks 10-11)

## Objective

Serve the published snapshot through seven GET-only, dual-gated `/v1` routes and
render it in a read-only Research UI panel. No write route, no observer
protocol change, and no Godot overlay is added.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/api/routes/social_mobility.py` | prefix/count (22-24), helpers (29-109), routes (192-298) | Newest route template |
| `src/api/routes/economic_inequality.py` | `ECONOMIC_INEQUALITY_ROUTE_COUNT` (26), cursor validation (83-109), error codes (195-319) | Paging/error template |
| `src/api/social_mobility_cursor.py` | alias and TTL (15-17) | Cursor codec reuse |
| `src/api/app.py` | `_attach_social_mobility_reader` (662-689), attach calls (891-892), includes (935-936) | Dual-gate wiring |
| `src/api/routes/__init__.py` | router exports (44) | Export point |
| `src/api/security.py` | `ApiCapability.SUBJECTIVE_DEBUG` (43-49), `require_http_capability` (186) | Authorization gate |
| `src/simulation/economic_cascades_ports.py` | cursor/fingerprint/protocols (created in Task 10) | Read contract |
| `clients/research-ui/src/api/socialMobility.ts` | client types and query builder | Client template |
| `clients/research-ui/src/views/SocialMobilityPanel.svelte` | read-only panel | Panel template |
| `clients/research-ui/src/research/selection.ts` | `RESEARCH_UI_VIEWS` (8-49), `RUN_SCOPED_VIEWS` (53-92) | Registration |
| `clients/research-ui/src/views/RunOverview.svelte` | panel imports (53-54), dispatch (377-380) | Mount point |
| `tests/integration/test_social_mobility_store_api.py` | existing store/API integration shape | Integration template |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/api/economic_cascades_cursor.py` | create | Cursor codec alias and TTL |
| `src/api/routes/economic_cascades.py` | create | Seven GET-only routes |
| `src/api/routes/__init__.py` | modify | Export router |
| `src/api/app.py` | modify | Attach reader/codec behind both settings; include router |
| `clients/research-ui/src/api/economicCascades.ts` | create | Typed client |
| `clients/research-ui/src/views/EconomicCascadesPanel.svelte` | create | Read-only panel |
| `clients/research-ui/src/research/selection.ts` | modify | View and run-scoped registration |
| `clients/research-ui/src/views/RunOverview.svelte` | modify | Import and dispatch |
| `tests/unit/test_economic_cascades_routes.py` | create | Route contract, gates, paging, errors |
| `tests/unit/test_economic_cascades_api_cursor.py` | create | Cursor codec and fingerprint |
| `tests/integration/test_economic_cascades_store_api.py` | create | Real atomic store plus real app/TestClient read of all seven routes |
| `clients/research-ui/src/api/economicCascades.test.ts` | create | Client query/envelope |
| `clients/research-ui/src/views/EconomicCascadesPanel.test.ts` | create | Panel rendering states |
| `clients/research-ui/src/research/selection.test.ts` | modify | New view ordering |

## Task 13: Add seven GET-only dual-gated routes

### Intent
Expose summary, disruptions, dependencies, chains, propagation, windows, and
coverage without granting any write authority or leaking analysis internals.

### Implementation Steps
1. Create `src/api/economic_cascades_cursor.py`:
   - `EconomicCascadesCursorCodec = DiplomacyCursorCodec`,
     `EconomicCascadesCursorError = DiplomacyCursorError`,
     `ECONOMIC_CASCADES_CURSOR_TTL_SECONDS = 900`.
2. Create `src/api/routes/economic_cascades.py`:
   - `router = APIRouter(prefix="/v1/simulations", tags=["economic-cascades"])`
     and `ECONOMIC_CASCADES_ROUTE_COUNT = 7`.
   - Helpers: `_reader(request)` from `app.state.economic_cascades_reader`;
     `_codec(request)`; `_authorize(request)` requiring
     `ApiCapability.SUBJECTIVE_DEBUG`; `_snapshot(run_id, reader, codec)`
     mapping store errors to the closed HTTP codes; `_fingerprint(...)`; and
     `_cursor(...)` that rejects a cursor whose purpose or query fingerprint does
     not match.
   - Routes, all `GET`:
     `/v1/simulations/{run_id}/economic-cascades` (summary; no paging
     parameters), and the six paged routes `.../disruptions`,
     `.../dependencies`, `.../chains`, `.../propagation`, `.../windows`,
     `.../coverage`, each with `limit: int = Query(100, ge=1, le=500)`,
     `cursor: str | None = None`, and `window_index: int | None =
     Query(None, ge=0, le=511)`.
   - Error mapping: unconfigured reader →
     `503 economic_cascades_disabled`; missing run →
     `404 economic_cascades_run_not_found`; corrupt store →
     `500 economic_cascades_store_corrupt`; bad cursor →
     `400 economic_cascades_cursor_invalid`; expired cursor →
     `410 economic_cascades_cursor_expired`.
3. Export the router from `src/api/routes/__init__.py`.
4. In `src/api/app.py`, add `_attach_economic_cascades_reader(app, settings)`
   that requires both `settings.economic_cascades_root` and
   `settings.economic_cascades_cursor_key`; otherwise sets reader and codec to
   `None` and logs `enabled=false`. Call it on startup next to the social
   attach, and include the router.
5. Do not add POST/PUT/PATCH/DELETE, `/v2`, or an observer capability entry.
6. Create `tests/integration/test_economic_cascades_store_api.py` (marker
   `integration`) that publishes a finalized snapshot through the real
   filesystem store into `tmp_path`, attaches the reader through the app factory
   with both settings present, and reads all seven routes with `TestClient`.
   Assert 200 plus the expected section envelope, a window-filtered page, and
   the 503/500/400/410 failure paths. This is the file named by Task 21's
   integration lane; do not leave it to Task 16.

### Required Interfaces and Contracts
- Seven GET routes, no more; `ECONOMIC_CASCADES_ROUTE_COUNT` is asserted.
- `window_index` filters rows to that window before paging.
- A cursor minted for another window, purpose, or limit is rejected with 400.
- Response envelopes carry rows plus `next_cursor` and `window_index`; no
  analysis-internal token or owner id appears.

### Requirement Evidence
- Original Request "Provide dependency/cascade analytics" (read model).
- `src/api/routes/social_mobility.py:22-298` and
  `src/api/app.py:662-689,891-892,935-936`.

### Error Handling and Logging
- INFO `economic_cascades_reader_attached enabled=<bool>` on startup only.
- WARN `economic_cascades_cursor_invalid`.
- ERROR `economic_cascades_store_corrupt` with a code only.
- Never log cursor keys, digests, run ids, rows, or response bodies.

### Tests
- `tests/unit/test_economic_cascades_routes.py` with FastAPI `TestClient`:
  route count; each route's happy path; unconfigured gate 503; missing run 404;
  corrupt store 500; bad cursor 400; expired cursor 410; window mismatch 400;
  default 100/max 500; no non-GET method.
- `tests/unit/test_economic_cascades_api_cursor.py`: codec round-trip, TTL
  expiry, fingerprint mismatch.
- `tests/integration/test_economic_cascades_store_api.py` (`-m integration`):
  real store publication plus real app/TestClient reads and the four failure
  paths.

### Acceptance Criteria
- All seven routes fail closed when either setting is absent.
- Paging is window-bound and deterministic.
- No write surface exists.

### Verification
- `uv run pytest tests/unit/test_economic_cascades_routes.py tests/unit/test_economic_cascades_api_cursor.py -q`
- Expected result: pass.

## Task 14: Add the Research UI client and panel

### Intent
Render cascade evidence read-only: per-kind disruption counts, dependency edges,
chain states, propagation summaries, and coverage. No score, severity, ranking,
or causal badge is shown.

### Implementation Steps
1. Create `clients/research-ui/src/api/economicCascades.ts`:
   - Types for summary, disruption, dependency, chain, propagation, coverage,
     and the paged envelope; `EconomicCascadeRow` union keyed by section.
   - `buildEconomicCascadesQuery({limit, cursor, windowIndex})` appending only
     non-empty parameters; `getEconomicCascadesSummary(runId)`,
     `getEconomicCascadesDisruptions`, `...Dependencies`, `...Chains`,
     `...Propagation`, `...Windows`, `...Coverage` using the injected fetch
     base URL pattern from `socialMobility.ts`.
2. Create `clients/research-ui/src/views/EconomicCascadesPanel.svelte`:
   - Six sections (summary card, disruptions, dependencies, chains,
     propagation, coverage) with an empty state when the route returns 503 or an
     empty envelope.
   - Chain state is rendered as the literal `linked|unlinked|unresolved|
     unavailable` token; no colour-coded severity, no "cause" label, no ranking.
   - Show counts, milli shares, depth, and lag only.
3. Register `economic-cascades` in `RESEARCH_UI_VIEWS` and
   `RUN_SCOPED_VIEWS` in `selection.ts`, and dispatch it in `RunOverview.svelte`
   next to the social-mobility branch.
4. Do not add a Godot overlay or any client write action.

### Required Interfaces and Contracts
- Panel is read-only and uses the public `/v1` client only.
- No new dependency, no chart library, no colour scale.
- Disabled/absent data renders an explicit empty state, not zeros.

### Requirement Evidence
- Original Request "Provide dependency/cascade analytics".
- `.ai-factory/ARCHITECTURE.md` V3-40 through V3-42 presentation seam.

### Error Handling and Logging
- UI surfaces route error codes as text; no retry loop.
- No client-side logging of run ids or rows.

### Tests
- `clients/research-ui/src/api/economicCascades.test.ts`: query building and
  envelope parsing.
- `clients/research-ui/src/views/EconomicCascadesPanel.test.ts`: populated,
  empty, and disabled states; asserts no severity/score text.
- `selection.test.ts`: view present and run-scoped.

### Acceptance Criteria
- Panel renders all six sections from fixtures.
- No forbidden vocabulary appears in rendered text.
- `svelte-check` reports no errors.

### Verification
- `cd clients/research-ui && ./node_modules/.bin/vitest run -- EconomicCascadesPanel economicCascades selection`
- `cd clients/research-ui && ./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json`
- Expected result: tests pass and 0 errors/0 warnings.

## Phase Risks and Mitigations
- Risk: a route leaks chain subjects or owner ids.
  Mitigation: snapshot rows carry no owner ids; route tests scan responses for
  forbidden keys.
- Risk: cursor reuse across windows returns mixed rows.
  Mitigation: query fingerprint includes purpose, window, and limit; mismatch is
  400.
- Risk: UI implies severity.
  Mitigation: literal state tokens only and a test asserting no severity text.

## Phase Completion Checklist
- Seven GET-only routes are wired and fail closed.
- Research UI panel and client tests pass.
- No Godot client change exists.
- `index.md` Tasks 13-14 checkboxes are updated after verification.
