# Phase 5: Read-Only Surfaces

Plan: [index.md](index.md)
Tasks: 15-16
Depends on: Phase 4 (snapshot, store, publication)

## Objective

Expose the published credit snapshot through seven GET-only, dual-gated `/v1`
routes and one read-only Research UI panel. No route mutates a run, rebuilds an
artifact, or reaches into simulation or analysis. Godot receives no new overlay.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/api/routes/emergent_prices.py` | reader gate 28-42, snapshot/error mapping 52-64, fingerprint 67-118, row keys 121-142, paging 145-180, seven routes remainder | Exact route, cursor, and failure pattern to mirror |
| `src/api/emergent_prices_cursor.py` | cursor codec wrapper | Exact signed cursor construction |
| `src/api/emergent_prices_schemas.py` | strict Pydantic base 24-26, row/page models 28-178 | Exact response model pattern |
| `src/api/app.py` | attach reader 568-595, lifespan attach 765, router include 805 | Exact composition-root wiring |
| `src/api/routes/__init__.py` | router exports 12 and `__all__` 54 | Router registration point |
| `src/api/security.py` | `ApiCapability.SUBJECTIVE_DEBUG` | Required capability |
| `src/api/errors.py` | `service_unavailable`, `bad_request`, `gone`, `internal`, `not_found` | Exact error helpers |
| `clients/research-ui/src/api/emergentPrices.ts` | types and fetchers 1-120+ | Exact client shape |
| `clients/research-ui/src/views/EmergentPricesPanel.svelte` | state/load/status/panel 1-120+ | Exact read-only panel pattern |
| `clients/research-ui/src/views/RunOverview.svelte` | import 51, render 366 | Panel mount point |
| `clients/research-ui/src/views/EmergentPricesPanel.test.ts` | ready/empty/unavailable/error cases | Exact UI test pattern |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/api/credit_relationships_cursor.py` | create | `CreditRelationshipsCursorCodec` |
| `src/api/credit_relationships_schemas.py` | create | Strict summary/row/page response models |
| `src/api/routes/credit_relationships.py` | create | Seven GET-only dual-gated routes |
| `src/api/routes/__init__.py` | modify | Export/include the router |
| `src/api/app.py` | modify | Attach reader/codec and include router |
| `clients/research-ui/src/api/creditRelationships.ts` | create | Types and seven fetchers |
| `clients/research-ui/src/views/CreditRelationshipsPanel.svelte` | create | Read-only panel |
| `clients/research-ui/src/views/CreditRelationshipsPanel.test.ts` | create | Ready/empty/unavailable/error/window tests |
| `clients/research-ui/src/views/RunOverview.svelte` | modify | Import and render the panel |
| `clients/godot-observer/**` | no change | No overlay; existing suite is the regression gate |

## Task 15: Add seven GET-only dual-gated credit routes

### Intent

Serve the published snapshot with the same security, cursor, and failure
semantics as every other V4 research surface. The routes fail closed when either
setting is absent and never fall back to live analysis.

### Implementation Steps

1. Create `src/api/credit_relationships_cursor.py` with
   `CreditRelationshipsCursorCodec` mirroring
   `EmergentPricesCursorCodec`: `from_secret(secret)`, `encode(...)`, and
   `decode(token, *, purpose)` returning the payload mapping. Reuse the existing
   cursor codec base if one is shared; otherwise copy the price wrapper.
2. Create `src/api/credit_relationships_schemas.py` with `_Strict`
   (`extra="forbid"`, `frozen=True`) and exact models:
   - `CreditRelationshipsSummaryOut(run_id, publication_id, digest,
     schema_version, window_tick, window_count, relationship_count, claim_count,
     performance_count, distribution_count, counterparty_count,
     alignment_count, claim_event_count, transfer_event_count,
     evidence_coverage, owner_coverage, relationship_coverage,
     performance_coverage, distribution_coverage, counterparty_coverage,
     alignment_coverage, coverage, truncated)`;
   - `CreditRelationshipOut` with every `CreditRelationshipRecord` field;
   - `CreditClaimOut`, `CreditPerformanceOut`, `CreditDistributionOut`,
     `CreditCounterpartyOut`, `CreditAlignmentOut`;
   - page models `CreditRelationshipsPageOut`, `CreditClaimsPageOut`,
     `CreditPerformancesPageOut`, `CreditDistributionsPageOut`,
     `CreditCounterpartiesPageOut`, `CreditAlignmentPageOut`, each with
     `rows` and `next_cursor`.
3. Create `src/api/routes/credit_relationships.py`:
   - `router = APIRouter(prefix="/v1/simulations", tags=["credit-relationships"])`;
   - `CREDIT_RELATIONSHIPS_ROUTE_COUNT = 7`;
   - `_reader(request)` reads `app.state.credit_relationships_reader`; missing
     -> `service_unavailable(code="credit_relationships_disabled")`;
   - `_codec(request)` reads `app.state.credit_relationships_cursor_codec`;
     missing/wrong type -> the same 503;
   - `_authorize(request)` requires `ApiCapability.SUBJECTIVE_DEBUG`;
   - `_snapshot(reader, run_id)` maps `ValueError` text
     `credit_relationships_store_corrupt` -> 500 with that code; other
     `ValueError`/exceptions -> 404 `credit_relationships_run_not_found`; `None`
     -> 404;
   - `_filters(window_index)` -> `{}` or `{"window_index": value}`;
   - `_fingerprint(...)` uses `credit_relationships_query_fingerprint`;
   - `_after_key(...)` decodes, checks run/publication/digest/query fingerprint,
     and maps expired/invalid cursors to
     `credit_relationships_cursor_expired` / `credit_relationships_cursor_invalid`;
   - `_ROW_KEYS` exact:
     relationships `("window_index","relationship_id")`,
     claims `("window_index","claim_id")`,
     performances `("window_index","performance_id")`,
     distributions `("window_index","distribution_id")`,
     counterparties `("window_index","counterparty_token")`,
     alignment `("window_index","alignment_id")`;
   - `_page(...)` calls `page_credit_relationships`, returns rows and a next
     cursor only when the page is full.
4. Add the seven routes:
   - `GET /{run_id}/credit-relationships` -> summary;
   - `GET /{run_id}/credit-relationships/relationships`;
   - `GET /{run_id}/credit-relationships/claims`;
   - `GET /{run_id}/credit-relationships/performances`;
   - `GET /{run_id}/credit-relationships/distributions`;
   - `GET /{run_id}/credit-relationships/counterparties`;
   - `GET /{run_id}/credit-relationships/alignment`.
   Every route takes `limit: int = Query(100, ge=1, le=500)`,
   `cursor: str | None = None`, and `window_index: int | None =
   Query(None, ge=0, le=511)` except summary, which takes no cursor/limit.
5. In `src/api/app.py`, add `_attach_credit_relationships_reader(app)`:
   - read `settings.credit_relationships_root` and
     `settings.credit_relationships_cursor_key`;
   - if either is absent, set both state values to `None` and log
     `INFO credit_relationships_attach enabled=false`;
   - otherwise create `CreditRelationshipsCursorCodec.from_secret(secret)` and
     `create_credit_relationships_reader(root)`, log
     `INFO credit_relationships_attach enabled=true`.
   Call it in the lifespan beside `_attach_emergent_prices_reader` and include
   the router beside `app.include_router(emergent_prices_router)`.
6. In `src/api/routes/__init__.py`, import the router as
   `credit_relationships_router` and add it to `__all__`.
7. Do not import `analysis`, `experiments`, `simulation` internals, or any
   publisher from the route module. Read only through the port.
8. Do not add a Godot route, protocol, overlay, or semantic type.

### Required Interfaces and Contracts

```python
CREDIT_RELATIONSHIPS_ROUTE_COUNT = 7

# GET only
/v1/simulations/{run_id}/credit-relationships
/v1/simulations/{run_id}/credit-relationships/relationships
/v1/simulations/{run_id}/credit-relationships/claims
/v1/simulations/{run_id}/credit-relationships/performances
/v1/simulations/{run_id}/credit-relationships/distributions
/v1/simulations/{run_id}/credit-relationships/counterparties
/v1/simulations/{run_id}/credit-relationships/alignment
```

- Unset root or cursor key -> 503 `credit_relationships_disabled` on all seven.
- Corrupt store -> 500 `credit_relationships_store_corrupt`.
- Missing run -> 404 `credit_relationships_run_not_found`.
- Cursor from another window/filter/run/publication/digest -> 400
  `credit_relationships_cursor_invalid`.
- Default limit 100; max 500; `window_index` in `[0, 511]`.
- Responses are strict, frozen, and contain no raw event bodies or payloads.

### Requirement Evidence

- Seven-route dual-gated pattern:
  `src/api/routes/emergent_prices.py:1-348`,
  `src/api/app.py:568-595, 765, 805`.
- Capability requirement: `src/api/security.py`
  (`ApiCapability.SUBJECTIVE_DEBUG`).
- Read-only boundary: `.ai-factory/ARCHITECTURE.md` "Layer/Module
  Communication" and "Anti-Patterns".

### Error Handling and Logging

- `INFO credit_relationships_route_disabled` when no reader/codec.
- `ERROR credit_relationships_store_corrupt` only for corruption.
- `INFO credit_relationships_attach enabled=%s`.
- Never log run ids, cursors, anchors, owner/counterparty tokens, item kinds,
  ratios, or confidence values.

### Tests

- `tests/unit/test_credit_relationships_api.py`: all seven routes; 503 when
  either gate unset; 500 corrupt; 404 missing; 400 cross-window cursor; limit
  100/500/501; window 0/511/512; summary shape; page `next_cursor`.
- `tests/unit/test_credit_relationships_settings.py` is extended with attach
  behavior if needed.

### Acceptance Criteria

- All seven routes are GET-only and require `SUBJECTIVE_DEBUG`.
- Neither gate alone enables a reader.
- A cursor bound to `window_index=1` is rejected for `window_index=2`.
- No route writes, repairs, or publishes a snapshot.

### Verification

- `uv run pytest tests/unit/test_credit_relationships_api.py -q`
- `uv run mypy src/api/routes/credit_relationships.py src/api/credit_relationships_schemas.py`
- Expected: all pass.

## Task 16: Add the Research UI credit client and panel

### Intent

Give researchers a read-only view of credit relationships, claims, performances,
distributions, counterparties, and researcher-only alignment. The panel never
writes, retries a publication, or displays a credit score.

### Implementation Steps

1. Create `clients/research-ui/src/api/creditRelationships.ts`:
   - `export const CAPABILITY = 'subjective_debug'`;
   - TypeScript types mirroring every response model;
   - `getSummary(runId)`, `getRelationships`, `getClaims`, `getPerformances`,
     `getDistributions`, `getCounterparties`, `getAlignment`, each accepting
     `{ windowIndex?: number; limit?: number; cursor?: string }`;
   - use the existing `apiFetch` and URL-encode `runId`;
   - no write method, no POST, no PUT, no DELETE.
2. Create `clients/research-ui/src/views/CreditRelationshipsPanel.svelte`:
   - props `runId: string`, `selection: ResearchSelection`;
   - status union `loading | ready | empty | unavailable | error`;
   - window filter input parsed as a non-negative integer;
   - load summary and six pages with `Promise.all`;
   - treat `credit_relationships_disabled` and `http_503` as `unavailable`;
   - render summary coverage, relationship count, performance outcome counts,
     distribution median/IQR/dispersion, counterparty counts, and alignment
     counts;
   - label values with `replaceAll('_', ' ')`;
   - include a visible note: "Owner-scoped credit beliefs. No bank, money,
     enforceable debt, credit score, or canonical credit is shown.";
   - no form submission, mutation button, or automatic publication.
3. Create `clients/research-ui/src/views/CreditRelationshipsPanel.test.ts`:
   - ready state renders summary and at least one row per family;
   - empty state when all pages are empty;
   - unavailable state on `credit_relationships_disabled`;
   - error state on another `ApiClientError`;
   - window filter passes the parsed index to fetchers;
   - no write endpoint is called.
4. In `clients/research-ui/src/views/RunOverview.svelte`, import the panel and
   render `<CreditRelationshipsPanel {runId} {selection} />` beside the
   emergent-price panel.
5. Do not modify the Godot observer or its protocol. Existing Godot suites are
   the regression gate only.

### Required Interfaces and Contracts

```ts
export type CreditRelationship = { ... }
export type CreditClaim = { ... }
export type CreditPerformance = { ... }
export type CreditDistribution = { ... }
export type CreditCounterparty = { ... }
export type CreditAlignment = { ... }
export type CreditRelationshipsSummary = { ... }
```

- Read-only: no POST/PUT/PATCH/DELETE helper exists.
- Disabled state is explicit and does not retry.
- Panel text never claims a bank, money, interest, enforceable debt, credit
  score, or canonical credit.

### Requirement Evidence

- Research UI pattern:
  `clients/research-ui/src/api/emergentPrices.ts`,
  `clients/research-ui/src/views/EmergentPricesPanel.svelte`,
  `clients/research-ui/src/views/EmergentPricesPanel.test.ts`,
  `clients/research-ui/src/views/RunOverview.svelte:51,366`.
- Clients never mutate simulation:
  `.ai-factory/ARCHITECTURE.md` "V3-40 through V3-42 presentation seams".

### Error Handling and Logging

- UI reason codes are displayed as safe tokens only.
- No console logging of row payloads, owner tokens, anchors, or item kinds.
- A failed page renders an error state rather than partial fabricated rows.

### Tests

- `cd clients/research-ui && ./node_modules/.bin/vitest run src/views/CreditRelationshipsPanel.test.ts`
- `cd clients/research-ui && ./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json`
- Expected: all pass, 0 errors/warnings.

### Acceptance Criteria

- The panel is present in `RunOverview` and read-only.
- All seven client functions exist and none is a write.
- Disabled, empty, ready, and error states are covered.
- Godot files are unchanged.

### Verification

- `cd clients/research-ui && ./node_modules/.bin/vitest run`
- `cd clients/research-ui && ./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json`
- Expected: all tests pass; 0 type errors/warnings.

## Phase Risks and Mitigations

- Risk: a route falls back to live analysis when the store is absent.
  Mitigation: missing reader/codec returns 503 before any read.
- Risk: cursor reuse across windows returns wrong rows.
  Mitigation: window index is part of the query fingerprint.
- Risk: UI shows a composite score.
  Mitigation: counts, statuses, quantiles, and explicit non-goal text only.
- Risk: Godot protocol drift.
  Mitigation: no Godot file changes; existing suite remains the gate.

## Phase Completion Checklist

- Every Task 15-16 in this phase satisfies its acceptance criteria.
- API, Research UI, and type-check lanes pass.
- `index.md` checkboxes are updated only after verified completion.
