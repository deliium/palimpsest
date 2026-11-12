# Phase 5: Read-Only Surfaces

Plan: [index.md](index.md)
Tasks: 15-16
Depends on: Phase 4 / Tasks 12-14

## Objective

Serve the published accounting snapshot through seven GET-only dual-gated
routes with purpose-bound cursors, then add one read-only Research UI panel. No
Godot change and no write/v2 route.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/api/routes/credit_relationships.py` | router 23; count 25; authorize 46-52; disabled 30-43; corrupt 54-59; cursor 98-119; page body 192-205; seven handlers 208-356 | Exact route template. |
| `src/api/credit_relationships_cursor.py` | aliases the shared diplomacy cursor codec, TTL 900 | Reuse the shared codec; map its expired reason to the accounting code. |
| `src/api/app.py` | credit attach 599-625; include 838 | Reader wiring. |
| `src/infrastructure/settings.py` | dual gate 885-897 | Reader is enabled only when both settings exist. |
| `clients/research-ui/src/api/creditRelationships.ts` | client 1-236 | Typed client template. |
| `clients/research-ui/src/views/CreditRelationshipsPanel.svelte` | panel 1-279 | Read-only panel template (parallel loads, window filter, no forms). |
| `clients/research-ui/src/views/CreditRelationshipsPanel.test.ts` | 300 | Test template including the no-write-endpoint assertion. |
| `clients/research-ui/src/views/RunOverview.svelte` | import 52; render 367-368 | Registration point. |
| `clients/research-ui/src/research/selection.ts` | `RESEARCH_UI_VIEWS` 28; `RUN_SCOPED_VIEWS` 69 | View registration. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/api/routes/accounting_ledgers.py` | create | Seven GET-only routes and schemas. |
| `src/api/accounting_ledgers_cursor.py` | create | Cursor codec alias and reason mapping. |
| `src/api/app.py` | modify | Attach reader and include router. |
| `clients/research-ui/src/api/accountingLedgers.ts` | create | Typed client. |
| `clients/research-ui/src/views/AccountingLedgersPanel.svelte` | create | Read-only panel. |
| `clients/research-ui/src/views/AccountingLedgersPanel.test.ts` | create | Panel tests. |
| `clients/research-ui/src/views/RunOverview.svelte` | modify | Render the panel. |
| `clients/research-ui/src/research/selection.ts` | modify | Register the view. |

---

## Task 15: Add seven GET-only dual-gated accounting routes

### Intent

Expose the published snapshot read-only under `SUBJECTIVE_DEBUG`, failing closed
when either setting is absent and rejecting cross-window cursors.

### Implementation Steps

1. Create `src/api/routes/accounting_ledgers.py`:
   - `APIRouter(prefix="/v1/simulations", tags=["accounting-ledgers"])`.
   - `ACCOUNTING_LEDGERS_ROUTE_COUNT = 7`.
   - `_authorize` requires `ApiCapability.SUBJECTIVE_DEBUG` for every route.
   - Routes:
     1. `GET /{run_id}/accounting-ledgers` → summary.
     2. `GET /{run_id}/accounting-ledgers/entries`.
     3. `GET /{run_id}/accounting-ledgers/records`.
     4. `GET /{run_id}/accounting-ledgers/conditions`.
     5. `GET /{run_id}/accounting-ledgers/flows`.
     6. `GET /{run_id}/accounting-ledgers/counterparties`.
     7. `GET /{run_id}/accounting-ledgers/alignment`.
   - Query params: `limit` default 100, `ge=1, le=500`; `cursor`; `window_index`
     `ge=0, le=511`.
   - Page body: `{run_id, publication_id, window_index, rows, next_cursor, coverage}`.
   - Summary body: `run_id`, `publication_id`, `digest`, `schema_version`,
     per-family counts, per-family coverage, `truncated`.
   - Response bodies are plain typed dictionaries built in the route module,
     exactly like `_page_body` in the credit route; no separate schema package
     is introduced.
   - The reader is required; if absent return `503 accounting_ledgers_disabled`.
2. Create `src/api/accounting_ledgers_cursor.py`:
   - `AccountingLedgersCursorCodec = DiplomacyCursorCodec` (shared HMAC), TTL 900.
   - Map the shared codec's expired indicator to
     `accounting_ledgers_cursor_expired` at the route boundary.
3. Cursor validation:
   - decode; verify `purpose`, `fingerprint`, and `window_index` match the
     request; otherwise `400 accounting_ledgers_cursor_invalid`.
   - a cursor whose `window_index` differs from the request is rejected 400.
4. Error mapping:
   - missing reader/codec → 503 `accounting_ledgers_disabled`;
   - `ValueError` from the store → 500 `accounting_ledgers_store_corrupt`;
   - missing snapshot/run → 404 `accounting_ledgers_run_not_found`;
   - malformed/mismatched cursor → 400;
   - expired cursor → 410.
5. `src/api/app.py`: import the router at the existing import block, add
   `_attach_accounting_ledgers_reader` beside 599-625 using the Task 13 settings,
   call it beside 797, and `include_router` beside 838.
6. Log `INFO accounting_ledgers_router_ready` and
   `WARN accounting_ledgers_reader_disabled` (no settings values).

### Required Interfaces and Contracts

- GET only; no POST/PUT/PATCH/DELETE route exists.
- All seven routes require `SUBJECTIVE_DEBUG`.
- Default limit 100; max 500; `window_index` 0..511.
- Cursors are purpose-bound and window-bound.
- No route imports `analysis` or constructs a snapshot.

### Requirement Evidence (when reconciliation applies)

- Original Request "Allow agents/institutions to use ledgers as evidence" — the
  read surface exposes evidence, not authority.
- `.ai-factory/ARCHITECTURE.md` — API is GET-only read composition.
- `src/api/routes/credit_relationships.py`.

### Error Handling and Logging

- Never log cursors, cursor keys, digests, publication ids, or row payloads.
- Log only route-ready/disabled status and safe error codes.

### Tests

Create `tests/unit/test_accounting_ledgers_api.py`:
- all seven routes exist and are GET-only;
- 403/401 without `SUBJECTIVE_DEBUG`;
- 503 when either setting is missing;
- 500 for corrupt store; 404 for unknown run;
- 400 for a cursor from another window or purpose;
- 410 for expiry;
- limit bounds and `window_index` bounds.

Command: `uv run pytest tests/unit/test_accounting_ledgers_api.py -q`.

### Acceptance Criteria

- Seven GET-only routes fail closed with the documented codes.
- Cursors bind the window filter.
- No write or `/v2` route exists.

### Verification

- The command above — expected: pass.
- `rg -n "\.post\(|\.put\(|\.patch\(|\.delete\(" src/api/routes/accounting_ledgers.py` — expected: no output.

---

## Task 16: Add the Research UI accounting client and panel

### Intent

Give researchers a read-only view of accounting summary, entries, records,
conditions, flows, counterparties, and alignment — with an explicit
belief-vs-truth disclaimer and no mutation path.

### Implementation Steps

1. `clients/research-ui/src/api/accountingLedgers.ts`:
   - `CAPABILITY = 'subjective_debug'`.
   - Types mirroring the seven response bodies.
   - Seven fetchers with the base path
     `/v1/simulations/{runId}/accounting-ledgers`.
   - No write helper.
2. `clients/research-ui/src/views/AccountingLedgersPanel.svelte`:
   - load summary plus six pages in parallel;
   - window filter input (0..511) propagated to every fetcher;
   - render family counts, coverage, truncation, condition shares, and
     alignment rows;
   - show a fixed disclaimer: accounting entries are owner beliefs; `consistent`
     does not mean true and `suspected_fraudulent` does not mean proven fraud;
   - render a disabled state for `accounting_ledgers_disabled` and a generic
     error state;
   - no forms, no write buttons.
3. Register the view:
   - add `'accounting-ledgers'` to `RESEARCH_UI_VIEWS` and `RUN_SCOPED_VIEWS`
     in `clients/research-ui/src/research/selection.ts`;
   - add `{ id: 'accounting-ledgers', label: 'Accounting ledgers' }` to the
     `tabGroups` Institutions group in `RunOverview.svelte` (71-129), otherwise
     the panel is unreachable from navigation;
   - import the panel beside line 52 and add a
     `{:else if view === 'accounting-ledgers'}` render branch beside the
     emergent-prices branch (366-368).
4. `clients/research-ui/src/views/AccountingLedgersPanel.test.ts`:
   - renders all families;
   - disabled state;
   - empty state;
   - generic error;
   - window filter propagation;
   - asserts no write endpoint is called;
   - asserts no rendered data label is `balance`, `net worth`, or `solvency`.
5. Add a selection/deeplink smoke test that
   `parseResearchSelection` accepts `view=accounting-ledgers` with a run id and
   rejects it without one (run-scoped), and that `RunOverview`'s tab list
   contains the new label.

### Required Interfaces and Contracts

- Read-only; no fetch uses a non-GET method.
- The panel never computes a balance, total value, or score.
- The disclaimer is always visible when data renders.

### Requirement Evidence (when reconciliation applies)

- Original Request "Do not make ledger content objective truth".
- `.ai-factory/ARCHITECTURE.md` V3-40 through V3-42 presentation seams.

### Error Handling and Logging

- Client surfaces the safe error code only; never logs response bodies.
- Disabled state is a first-class UI state.

### Tests

- `cd clients/research-ui && ./node_modules/.bin/vitest run src/views/AccountingLedgersPanel.test.ts`
- `cd clients/research-ui && ./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json`

### Acceptance Criteria

- The panel is read-only and disabled-safe.
- The belief disclaimer is present.
- Types check with zero errors/warnings.

### Verification

- The two commands above — expected: tests pass; 0 errors, 0 warnings.

## Phase Risks and Mitigations

- Risk: a future contributor adds a mutation route.
  Mitigation: the no-write route test and the UI no-write-endpoint assertion.
- Risk: the shared diplomacy cursor codec leaks a misleading reason code.
  Mitigation: the route boundary maps it to the accounting code and a test
  asserts the accounting token.
- Risk: the panel implies objective truth.
  Mitigation: fixed disclaimer and forbidden-word UI test.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
