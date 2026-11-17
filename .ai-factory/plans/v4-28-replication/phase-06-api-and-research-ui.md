# Phase 6: Read-only API and Research UI

Plan: [index.md](index.md)
Tasks: 21–24
Depends on: Tasks 17–20

## Objective

Expose designs, conditions, results, uncertainty, replication relationships and social interpretations without a truth/consensus dashboard.

## Current-Code Evidence

| Path | Symbols / behavior | Significance |
| --- | --- | --- |
| `src/api/routes/scientific_hypotheses.py` | router, `_authorize`, `_page`, seven GETs | Existing gated scientific read pattern. |
| `src/api/diplomacy_cursor.py` | HMAC-SHA256, injected clock, 900-second TTL | Signing precedent; new decoder must strictly validate its own envelope. |
| `src/api/app.py` | `_attach_scientific_hypotheses_reader` | Attach only when both settings exist. |
| `src/infrastructure/settings.py` | scientific root/`SecretStr` cursor key | Prefix and validation conventions. |
| `clients/research-ui/src/api/scientificHypotheses.ts` | typed query/fetch functions | Subjective-debug client convention. |
| `clients/research-ui/src/views/ScientificHypothesesPanel.svelte` | loading/ready/empty/unavailable/error | UI pattern, but it does not consume next cursors; do not copy that limitation. |
| `clients/research-ui/src/views/RunOverview.svelte` | existing science panel mount | Adjacent replication panel placement. |

## Files to Change

Create `src/api/routes/replication.py`, `src/api/replication_cursor.py`, `clients/research-ui/src/api/replication.ts`, `clients/research-ui/src/views/ReplicationPanel.svelte` and corresponding unit/UI tests. Modify API app/router registration, settings and `RunOverview.svelte`. Add `tests/integration/test_replication_store_api.py`.

## Task 21: Add dual-gated snapshot-pinned GET routes

### Intent

Serve already published artifacts; never compose analysis or enable experiments on read.

### Implementation Steps

1. Add settings `scientific_replication_root` and `scientific_replication_cursor_key` → `PALIMPSEST_SCIENTIFIC_REPLICATION_ROOT` / `PALIMPSEST_SCIENTIFIC_REPLICATION_CURSOR_KEY`. Key is `SecretStr`, at least 32 UTF-8 bytes. Both absent is disabled; one missing keeps the reader disabled; a present invalid key fails settings validation. Never generate a replacement secret silently.
2. Add `_attach_replication_reader` in API composition, using public persistence reader factory and feature cursor codec. No publisher, analysis or experiments imports in API.
3. Add eight GET-only routes under `/v1/simulations/{run_id}/scientific-replication`: summary, `/designs`, `/attempts`, `/results`, `/comparisons`, `/interpretations`, `/collaborations`, `/coverage`. Define route count 8. Authenticate `SUBJECTIVE_DEBUG` before store reads.
4. Summary optionally accepts `publication_id`; page routes accept `publication_id`, `cursor`, `limit` (1–500/default100), `window_index` (0–511), `design_token`, `collaboration_token` according to Phase 5's purpose/filter contract. Reject semantic unsupported combinations with safe 400; ordinary malformed constrained query types follow FastAPI 422 conventions.
5. First page resolves latest or explicitly requested publication; every response includes run/publication/digest, policy, coverage, rows and next cursor. When a cursor is present, verify its signature/purpose first, read that exact publication, then validate run/digest/query fingerprint/explicit publication agreement.
6. New `ReplicationCursorCodec` follows the existing HMAC/base64url format but uses strict exact keys/types, bounded 8,192-character input, injected clock, 900-second TTL, and namespaced purposes `scientific-replication:<section>`. Bind all filters and page limit. Do not reuse an unnamespaced other-feature cursor. No credential in query strings.
7. Map disabled 503 `scientific_replication_disabled`; missing run/publication 404 `scientific_replication_run_not_found` / `scientific_replication_publication_not_found`; corruption 500 `scientific_replication_store_corrupt`; invalid cursor 400 `scientific_replication_cursor_invalid`; expired cursor 410 `scientific_replication_cursor_expired`. Unexpected store errors are safe 500, not mislabeled 404.

### Required Interfaces and Contracts

Eight new GET routes; existing seven scientific-hypothesis routes unchanged. No POST, write credential, new API version, observer semantic or Godot overlay. Source reports and analytical comparisons retain explicit layer/provenance labels in responses.

### Error Handling and Logging

INFO disabled/read status and bounded row counts; WARN invalid/expired cursor code; ERROR corruption code. Never log keys, bearer credentials, signed cursor body, reports or condition values. HTTP errors must not expose filesystem paths or original exception messages.

### Tests / Acceptance / Verification

Create `tests/unit/test_replication_routes.py`, `test_replication_api_cursor.py`, `test_replication_settings.py`. Cover all gates, route verbs/count, strict filters/keys, cross-feature/purpose/run/publication/filter cursor rejection, expiry with injected clock, corrupt store and no publication calls. Run these with coverage.

## Task 22: Prove API paging, publication pinning and safe failure

### Intent

Test real adapter-to-HTTP behavior beyond route mocks.

### Implementation Steps

1. Build a temporary real filesystem store with more than 500 result rows and two immutable publications; use the actual reader/app composition.
2. Traverse all sections with page size 2/100/500 and compare concatenation against pure snapshot records. Preserve distinct contradictory result reports.
3. Between page 1 and page 2 publish a newer snapshot; the old cursor must still resolve the old publication, while a fresh first page resolves latest. Explicit publication disagreement is invalid, not silently redirected.
4. Test missing settings independently, insufficient byte-length UTF-8 key, unauthorized requests before store reads, equal-count content tampering, invalid publication path and no raw IDs/secret canaries in HTTP/log output.
5. Add opt-in integration coverage in `tests/integration/test_replication_store_api.py` using only temporary filesystem state for this feature. Do not provision or mutate production databases.

### Required Interfaces and Contracts

Repeated GETs do not change files, quotas, run lifecycle or owner state. Signed cursors bind immutable content, not mutable latest.

### Error Handling and Logging

Assert safe error codes and allowlisted log metadata for every negative case. Expired cursor is distinct from invalid cursor; corruption is distinct from missing.

### Tests / Acceptance / Verification

Run `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_replication_routes.py tests/unit/test_replication_api_cursor.py tests/unit/test_replication_settings.py -q` and `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term -m integration tests/integration/test_replication_store_api.py -q`. Verify no existing scientific route bytes/contracts changed.

## Task 23: Add typed Research UI API and pagination state

### Intent

Represent uncertainty/availability honestly and never silently stop at the first 100 rows.

### Implementation Steps

1. Define exact TypeScript summary/row/page types from the Phase 4/5 schemas in `api/replication.ts`; results are a discriminated union of `row_kind="execution"` objective receipts and `row_kind="report"` owner reports. Categorical report uncertainty has `unreported` vs `declared_set`, with nullable outcome explicit. Never add report fields to an execution variant to simplify rendering.
2. Add query builder and fetch helpers using existing API client and subjective-debug capability handling. Tokens are URL-encoded; credentials stay in existing headers, never links, cursors or logged URLs.
3. Return publication/digest/coverage and next cursor for every page. Client requests after the summary/first page pass explicit publication identity to prevent a mixed-publication panel.
4. Add a small per-section page state in the panel: rows, next cursor, loading and error. Loading more appends unique stable IDs only for the same query/publication; changed run/window/design/collaboration resets state.
5. Abort or generation-guard stale requests on selection changes; responses from an old run cannot overwrite the new selection. Cursor expiry requires explicit reload/reset, not silently mixing a new latest publication into old rows.
6. Query construction follows the exact Phase 5 filter matrix. Omit design/collaboration filters from results/coverage and collaboration filters from designs; reject explicitly unsupported combinations in the public query helper instead of silently stripping a caller's request. The panel supplies per-purpose allowed queries and labels the resulting scope.

### Required Interfaces and Contracts

The client performs reads only, does not interpret a report as truth, and does not compute hidden comparisons or reconstruct missing lineage.

### Error Handling and Logging

Surface API reason codes through existing client errors; no console dumps of row payloads/credentials. Disabled, missing, empty, partial and error states remain distinct.

### Tests / Acceptance / Verification

Create `clients/research-ui/src/api/replication.test.ts`: every endpoint, encoding/filter identity, auth handling, nullable uncertainty/outcomes, cursor/publication forwarding and error codes. Run `pnpm --dir clients/research-ui test src/api/replication.test.ts` and `pnpm --dir clients/research-ui check`.

## Task 24: Render evidence-scoped replication and community disagreement

### Intent

Make the requested five dimensions inspectable without a universal scientific verdict.

### Implementation Steps

1. Mount `ReplicationPanel.svelte` next to the science panel in `RunOverview.svelte`, accepting `runId` and existing `ResearchSelection`. Reuse existing layout/accessibility conventions; do not alter Godot or add action controls.
2. Render seven bounded sections: designs/parent lineage, attempts/conditions, measurements/uncertainty, replication comparisons, owner interpretations, collaboration declarations/individual executions, coverage. Within measurements show objective execution receipts and owner reports in visibly separate typed lanes; a report/receipt content mismatch must not overwrite either value.
3. Show original and child categories side by side; display `conflicting`, `not comparable`, missing source, unreported uncertainty and partial coverage distinctly. “Compatible categorical observations” is not “hypothesis confirmed”.
4. Label pseudonymous participant rows as owner-scoped testimony/appraisal; a claimed group is not verified membership. Trust appraisal, category difference and detached comparison must not collapse into one confidence number.
5. Include working “Load more” per section, publication identifier, exact window filter (manual 0–511 selector; do not invent a mapping from generation to analysis window), purpose-specific design/collaboration filters, stale-request guards, and keyboard-accessible status/empty text. Explicitly label result/coverage sections “selected window; not narrowed by design/collaboration” when narrower filters apply elsewhere.
6. No true/proven badge, N-replication progress-to-truth meter, scientific merit score, majority-wins indicator, or automatic hypothesis update UI.

### Required Interfaces and Contracts

Read-only presentation; selected evidence never feeds cognition, world state, prompts, memory or stop selectors. Existing science panel remains usable when replication is disabled.

### Error Handling and Logging

Display safe reason codes and explicit reload for expired cursor. Keep unknown uncertainty visibly unknown; no fallback to `0 ± 0`, 100% confidence or empty-success.

### Tests / Acceptance / Verification

Create `clients/research-ui/src/views/ReplicationPanel.test.ts`: loading/disabled/missing/known-empty/partial/error, source/child conflicting results, an owner report disagreeing with a separate objective receipt, uncertainty distinction, >100 mixed-variant rows and load more, new publication pin, changed run race, exact filter matrix and scope labels, keyboard controls and absence of truth badges. Run `pnpm --dir clients/research-ui test src/api/replication.test.ts src/views/ReplicationPanel.test.ts`, `pnpm --dir clients/research-ui check`, and `pnpm --dir clients/research-ui build`.

## Phase Risks and Mitigations

- Client accidentally mixes publications: pin every request and reset state on changed identity.
- Presentation hides disagreement: preserve both reports and their distinct provenance.
- Existing permissive cursor pattern: new feature validates exact envelope fields and namespaces purposes.

## Phase Completion Checklist

- Tasks 21–24 pass API, real-store, UI and static checks.
- No presentation path can invoke experiments or mutate hypotheses.
