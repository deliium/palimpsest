# Phase 4: Read Surfaces

Plan: [index.md](index.md)
Tasks: 13-14
Depends on: Phase 3 (Tasks 10-11)

## Objective

Serve the published science snapshot through seven GET-only, dual-gated `/v1`
routes and render it in a read-only Research UI panel. No write route, no
observer protocol change, and no Godot overlay is added.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/api/routes/economic_cascades.py` | prefix/count (24-26), helpers (29-111), summary (189-218), paged routes (242-311) | Newest route template |
| `src/api/social_mobility.py` | route count and helpers | Sibling shape |
| `src/api/economic_cascades_cursor.py` | codec alias and TTL (15-17) | Cursor codec reuse |
| `src/api/app.py` | reader attach (663-690), attach calls (924), includes (969) | Dual-gate wiring |
| `src/api/routes/__init__.py` | router exports (16, 63) | Export point |
| `src/api/security.py` | `ApiCapability.SUBJECTIVE_DEBUG` (43-49), `require_http_capability` (186) | Authorization gate |
| `src/simulation/scientific_hypotheses_ports.py` | cursor/fingerprint/protocols (created in Task 10) | Read contract |
| `clients/research-ui/src/api/economicCascades.ts` | typed client and query builder (3-181) | Client template |
| `clients/research-ui/src/views/EconomicCascadesPanel.svelte` | load states and read-only sections (19-254) | Panel template |
| `clients/research-ui/src/research/selection.ts` | views (32, 77) | Registration |
| `clients/research-ui/src/views/RunOverview.svelte` | import (54), tab (135), dispatch (383-384) | Mount point |
| `tests/integration/test_economic_cascades_store_api.py` | real store plus TestClient reads | Integration template |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/api/scientific_hypotheses_cursor.py` | create | Cursor codec alias and TTL |
| `src/api/routes/scientific_hypotheses.py` | create | Seven GET-only routes |
| `src/api/routes/__init__.py` | modify | Export router |
| `src/api/app.py` | modify | Attach reader/codec behind both settings; include router |
| `clients/research-ui/src/api/scientificHypotheses.ts` | create | Typed client |
| `clients/research-ui/src/views/ScientificHypothesesPanel.svelte` | create | Read-only panel |
| `clients/research-ui/src/research/selection.ts` | modify | View and run-scoped registration |
| `clients/research-ui/src/views/RunOverview.svelte` | modify | Import, tab, dispatch |
| `tests/unit/test_scientific_hypotheses_routes.py` | create | Route contract, gates, paging, errors |
| `tests/unit/test_scientific_hypotheses_api_cursor.py` | create | Cursor codec and fingerprint |
| `tests/integration/test_scientific_hypotheses_store_api.py` | create | Real store plus real app/TestClient |
| `clients/research-ui/src/api/scientificHypotheses.test.ts` | create | Client query/envelope |
| `clients/research-ui/src/views/ScientificHypothesesPanel.test.ts` | create | Panel states and no truth vocabulary |
| `clients/research-ui/src/research/selection.test.ts` | modify | New view ordering |

## Task 13: Add seven GET-only dual-gated routes

### Intent
Expose summary, hypotheses, evidence, tests, revisions, sources, and coverage
without granting write authority or leaking analysis internals, owner ids, or
objective rules.

### Implementation Steps
1. Create `src/api/scientific_hypotheses_cursor.py`:
   - `ScientificHypothesesCursorCodec = DiplomacyCursorCodec`,
     `ScientificHypothesesCursorError = DiplomacyCursorError`,
     `SCIENTIFIC_HYPOTHESES_CURSOR_TTL_SECONDS = 900`.
2. Create `src/api/routes/scientific_hypotheses.py`:
   - `router = APIRouter(prefix="/v1/simulations",
     tags=["scientific-hypotheses"])` and
     `SCIENTIFIC_HYPOTHESES_ROUTE_COUNT = 7`.
   - Helpers: `_reader(request)` from
     `app.state.scientific_hypotheses_reader`; `_codec(request)`;
     `_authorize(request)` requiring `ApiCapability.SUBJECTIVE_DEBUG`;
     `_snapshot(run_id, reader, codec)` mapping store errors to closed HTTP
     codes; `_fingerprint(...)`; `_cursor(...)` rejecting a cursor whose
     purpose, publication, digest, or query fingerprint does not match.
   - Routes, all `GET`:
     - `/v1/simulations/{run_id}/scientific-hypotheses` (summary; no paging);
     - `.../scientific-hypotheses/hypotheses`;
     - `.../scientific-hypotheses/evidence`;
     - `.../scientific-hypotheses/tests`;
     - `.../scientific-hypotheses/revisions`;
     - `.../scientific-hypotheses/sources`;
     - `.../scientific-hypotheses/coverage`.
   - Every paged route accepts
     `limit: int = Query(100, ge=1, le=500)`, `cursor: str | None = None`,
     and `window_index: int | None = Query(None, ge=0, le=511)`.
   - Error mapping: unconfigured reader -> `503 scientific_hypotheses_disabled`;
     missing run -> `404 scientific_hypotheses_run_not_found`; corrupt store ->
     `500 scientific_hypotheses_store_corrupt`; bad cursor ->
     `400 scientific_hypotheses_cursor_invalid`; expired cursor ->
     `410 scientific_hypotheses_cursor_expired`.
3. Export the router from `src/api/routes/__init__.py`.
4. In `src/api/app.py`, add `_attach_scientific_hypotheses_reader(app,
   settings)` requiring both `settings.scientific_hypotheses_root` and
   `settings.scientific_hypotheses_cursor_key`; otherwise set reader and codec
   to `None` and log `enabled=false`. Call it on startup next to the
   economic-cascades attach and include the router.
5. Do not add POST/PUT/PATCH/DELETE, `/v2`, or an observer capability entry.
6. Create `tests/integration/test_scientific_hypotheses_store_api.py` (marker
   `integration`) that publishes a finalized snapshot through the real
   filesystem store into `tmp_path`, attaches the reader through the app factory
   with both settings present, and reads all seven routes with `TestClient`.
   Assert 200 plus the expected envelope, a window-filtered page, and the
   503/500/400/410 failure paths.

### Required Interfaces and Contracts
- Seven GET routes, no more; `SCIENTIFIC_HYPOTHESES_ROUTE_COUNT` is asserted.
- `window_index` filters rows before paging.
- A cursor minted for another window, purpose, publication, or limit is
  rejected with 400.
- Response envelopes carry rows plus `next_cursor` and `window_index`; no
  owner token, objective rule, truth, or score appears.
- Summary does not accept paging parameters.

### Requirement Evidence
- Original Request representation list and "Do not expose objective rules".
- `src/api/routes/economic_cascades.py:24-311` and
  `src/api/app.py:663-690,924,969`.

### Error Handling and Logging
- INFO `scientific_hypotheses_reader_attached enabled=<bool>` on startup only.
- WARN `scientific_hypotheses_cursor_invalid`.
- ERROR `scientific_hypotheses_store_corrupt` with a code only.
- Never log cursor keys, digests, run ids, rows, or response bodies.

### Tests
- `tests/unit/test_scientific_hypotheses_routes.py` with FastAPI `TestClient`:
  route count and exact paths; each route's happy path; unconfigured gate 503;
  missing run 404; corrupt store 500; bad cursor 400; expired cursor 410;
  cross-window cursor 400; default 100/max 500; no non-GET method; summary
  rejects `limit`.
- `tests/unit/test_scientific_hypotheses_api_cursor.py`: codec round-trip, TTL
  expiry, fingerprint mismatch.
- `tests/integration/test_scientific_hypotheses_store_api.py`
  (`-m integration`): real store publication plus real app/TestClient reads and
  the four failure paths.

### Acceptance Criteria
- All seven routes fail closed when either setting is absent.
- Paging is window-bound and deterministic.
- No write surface exists.

### Verification
- `uv run pytest tests/unit/test_scientific_hypotheses_routes.py tests/unit/test_scientific_hypotheses_api_cursor.py -q`
- Expected result: pass.

## Task 14: Add the Research UI client and panel

### Intent
Render science evidence read-only: summary counts, hypothesis statuses and
confidence, evidence/contradiction counts, test activity, revisions, sources,
and coverage. No truth badge, proof, verification, accuracy, ranking, or
composite scientific score is shown.

### Implementation Steps
1. Create `clients/research-ui/src/api/scientificHypotheses.ts`:
   - `CAPABILITY = 'subjective_debug'`.
   - Types for summary, hypothesis, evidence, test, revision, source, coverage,
     and the paged envelope; a row union keyed by section.
   - `buildScientificHypothesesQuery({limit, cursor, windowIndex})` appending
     only non-empty parameters; summary and six paged getters using the injected
     fetch base URL pattern from `economicCascades.ts`.
2. Create `clients/research-ui/src/views/ScientificHypothesesPanel.svelte`:
   - Props `{ runId, selection }`.
   - Status `loading | ready | empty | unavailable | error`.
   - Load summary then six pages in `Promise.all`; explicit empty, disabled, and
     error states.
   - Sections: Summary, Hypotheses, Evidence, Tests, Revisions, Sources,
     Coverage.
   - Each hypothesis row renders its claim token, causal lineage token,
     predicted outcome, confidence `n/1000`, status, source kind, `created_tick`,
     and ordered condition pairs (`slot=value` tokens) in a read-only cell.
   - The Revisions section shows `revision_index`, `revision_tick`, reason
     token, claim token, predicted outcome, confidence `n/1000`, and condition
     pairs; old revisions are never collapsed or re-numbered.
   - Status renders the literal `provisional|supported|contradicted|inconclusive|superseded|retired`
     token; source renders the literal source-kind token.
   - Confidence renders as `n/1000`; no percentage, gauge, colour scale, or
     ranking.
   - `data-testid="scientific-hypotheses-panel"`.
3. Register `scientific-hypotheses` in `RESEARCH_UI_VIEWS` and
   `RUN_SCOPED_VIEWS` in `selection.ts`; add the import, tab, and render branch
   in `RunOverview.svelte` next to the economic-cascades branch.
4. Do not add a Godot overlay or any client write action.

### Required Interfaces and Contracts
- Panel is read-only and uses the public `/v1` client only.
- No new dependency, chart library, or colour scale.
- Disabled/absent data renders an explicit empty state, not zeros.
- No rendered text uses truth, verified, proven, proof, accuracy, calibration,
  score, rank, or objective-rule vocabulary.

### Requirement Evidence
- Original Request "Do not expose objective rules" and "Hypotheses can be
  wrong".
- `.ai-factory/ARCHITECTURE.md` V3-40 through V3-42 presentation seam.
- `clients/research-ui/src/views/EconomicCascadesPanel.svelte:19-254`.

### Error Handling and Logging
- UI surfaces route error codes as text; no retry loop.
- No client-side logging of run ids, tokens, or rows.

### Tests
- `clients/research-ui/src/api/scientificHypotheses.test.ts`: query building and
  envelope parsing.
- `clients/research-ui/src/views/ScientificHypothesesPanel.test.ts`: populated,
  empty, and disabled states; seven sections; literal status/source tokens; no
  truth/verified/proven/score/accuracy text.
- `selection.test.ts`: view present and run-scoped.

### Acceptance Criteria
- Panel renders all seven sections from fixtures.
- Contradicted hypotheses are visually and textually first-class.
- No forbidden vocabulary appears in rendered text.
- `svelte-check` reports no errors.

### Verification
- `cd clients/research-ui && ./node_modules/.bin/vitest run -- ScientificHypothesesPanel scientificHypotheses selection`
- `cd clients/research-ui && ./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json`
- Expected result: tests pass and 0 errors/0 warnings.

## Phase Risks and Mitigations
- Risk: a route leaks owner tokens or rule payloads.
  Mitigation: the snapshot has no such fields; route tests scan responses.
- Risk: cursor reuse across windows returns mixed rows.
  Mitigation: fingerprint includes purpose, publication, digest, window, and
  limit; mismatch is 400.
- Risk: UI implies truth or accuracy.
  Mitigation: literal status tokens, `n/1000` confidence, and a test asserting
  no truth/score text.

## Phase Completion Checklist
- Seven GET-only routes are wired and fail closed.
- Research UI panel and client tests pass.
- No Godot client change exists.
- `index.md` Tasks 13-14 checkboxes are updated after verification.
