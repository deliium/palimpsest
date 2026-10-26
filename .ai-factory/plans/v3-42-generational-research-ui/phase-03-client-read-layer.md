# Phase 3: Typed bounded client reads

Plan: [index.md](index.md)  
Tasks: 7–8  
Depends on: Tasks 1, 3–6

## Objective
Centralize schema validation, capability selection, paging, cancellation and source identity before building nineteen research surfaces.

## Current-Code Evidence
| Path | Symbols | Why it matters |
|---|---|---|
| `clients/research-ui/src/api/client.ts` | `apiFetch`, `ApiClientError`, `FetchOptions` | Existing header-only credentials; response casts alone do not validate new data |
| `clients/research-ui/src/auth/credentials.ts` | capability slots/sessionStorage | Sensitive caches must clear on credential change |
| `src/api/observer_demographic_schemas.py` | demographics/marker envelopes | Exact totals and actual-admission markers |
| `src/api/lineage_schemas.py` | node/graph/availability/coverage | Qualified refs and snapshot-pinned paging |
| `src/api/civilization_schemas.py` | map/catalogue/overlays/markers | Independent evidence scope/publication contracts |

## Files to Change
Modify `clients/research-ui/src/api/client.ts`, `auth/credentials.ts`. Introduce `src/api/research.ts`, `src/api/researchSchemas.ts`, `src/research/requests.ts`, `src/research/paging.ts`, `src/research/sampling.ts`, `src/research/json.ts` under `clients/research-ui/`, with sibling `.test.ts` files. No new charting/state/network dependency.

## Task 7: Implement typed clients and runtime guards for research APIs
### Intent
Bind frontend models to actual read contracts rather than `any`-typed generic cards.
### Implementation Steps
1. Add typed GET functions for demographics/generation markers; all eight lineage families/snapshots/nodes/traverse/participants; civilization map/catalogue/overlays/markers; new cultural comparison/metrics/evidence and semantic history; current labels/symbolic/translation and generational narrative metadata.
2. Introduce handwritten schema guards for consumed fields: supported schema IDs, bounded finite numbers, evidence/owner combinations, page limits, qualified refs, coverage, publication and declared counts. Unknown data is never coerced to zero. Keep unconsumed extensions opaque; reject unknown versions rather than silently interpreting them.
3. Carry `AbortSignal` through `apiFetch`, HTTP and parsing. Build paths with `encodeURIComponent`, query via `URLSearchParams`, and select inspection/debug based on the registry. Normalize lineage lowercase classes and civilization uppercase classes only at the adapter boundary. For analytical lineage, omit API `owner_id` even when the selected node requires `identity_owner`; preserve that owner in refs and returned-node matching. `/lineage/families?include_restricted=true` requires debug and returns a bare descriptor array, not an envelope. Use separate credential-scoped descriptor results rather than assuming inspection discovery lists private families.
4. Decode stored metric base64 as bytes + UTF-8 `TextDecoder`, not `atob` text alone. Validate document schema/provenance and use `(metric_set_id, family, version)` keys; remove analytics `.slice(0,24)` silent omission for explicitly selected families. `research/json.ts` implements a bounded JSON tokenizer/parser with per-object duplicate-key detection before accepting `rows_json`;16MiB UTF-8/depth32, finite scalar rows, cancellation checks before and after decode. Do not rely on `JSON.parse` alone to detect duplicate keys. Preserve nested row availability/coverage and reject unsupported shape/version rather than chart raw serialized JSON as one scalar.
5. Add client-side `resolveLineageSelection`: resolve optional publication ID by paged `/snapshots` discovery to its returned boundary/digest, query `/nodes` by native kind/ID at that boundary, and select the exact six-part ref including identity owner. If an explicit key is present use `/traverse?root_key=...` at the resolved boundary and verify returned root/ref. Both first reads and continuation must match expected publication/digest; otherwise show `research_snapshot_changed`. Never send `publication_id` or `identity_owner` as unsupported lineage HTTP query keys. Civilization focus instead uses its own catalogue/overlay `publication_id`, class/scope owner and exact row/source-ref matching; no cross-source ID reinterpretation.
6. Preserve Task4 artifact-binding header in a typed response metadata object while returning stored document bodies unchanged. Runtime-bound versus legacy-unverified is independent of PRESENT/PARTIAL measurement status and does not grant debug access. No header/body mismatch may be silently discarded.
### Required Interfaces and Contracts
All functions return validated discriminated envelopes retaining source identity, not chart-ready numbers alone. `getLineage*` must preserve matched/context-only keys, empty-with-next and stop reasons. `getCivilization*` must forward exact publication pin and coverage. Credentials never enter URLs.
### Requirement Evidence
Phase1 state and evidence contracts; current backend schemas are authoritative wire descriptions. Existing API auth distinguishes inspection and debug even for analytical artifacts.
### Error Handling and Logging
`ApiClientError` keeps status/safe code; malformed schemas become `unsupported_research_schema` or `invalid_research_response`. Abort is not an error alert. Logs include route template, schema and row count, never bodies/credentials/cursors.
### Tests
`api/research.test.ts` uses real Godot generational/civilization JSON fixtures plus new backend response fixtures. Test every endpoint capability, escaping, malformed/unknown schema, empty/partial/unavailable, Unicode metrics and distinct metric sets. Add restricted descriptor discovery, analytical native-owner-with-no-scope-owner, exact publication discovery/returned-digest mismatch, unsupported query-key absence, civilization concept focus, binding header and nested `rows_json` malformed/duplicate/depth cases. `research/json.test.ts` tests escaped keys/strings and finite number validation as well as byte/depth boundaries.
### Acceptance Criteria
No new panel performs ad-hoc fetch/casts or guesses evidence classes; all requested source families have typed readers.
### Verification
`pnpm --dir clients/research-ui test src/api/research.test.ts`; `pnpm --dir clients/research-ui check`.

## Task 8: Implement cancellation-safe paging and bounded timeline sampling
### Intent
Large runs and rapid navigation must not leak stale private data, overload history replay or freeze graphs.
### Implementation Steps
1. Add `ResearchRequestScope` in `research/requests.ts`, keyed by run/view/time/evidence/owner/publication/filter plus credential-generation. Cancel obsolete work and reject out-of-order responses after every await. Credentials emit a generation-change event; clear in-memory results and cancel requests before rendering a new scope. No persistent research-data cache.
2. Add generic explicit Load more controller. Default page100, client graph cap500 nodes/1500 edges; never exceed server advertised depth/node/edge budgets. Keep continuation when a page is empty. Stop loops on repeated cursor, duplicate inconsistent ref, changed publication or local cap; show reason and a restart action.
3. Keep marker discovery separate from sampled view time: obtain finalized run high-water `H` from existing `getObserverRun` metadata, pin marker requests/pages to `tick=H`, and cache only for `(run,H,revision,credentialGeneration)`. Changing view tick does not lower H or remove future admitted markers. A user Refresh may advance H; never move selected tick automatically. Sample objective population/project histories at most32 boundaries per explicit inclusive range, including endpoints and loaded markers when they fit. For >32 markers disclose deterministic sampling and omitted count. Default range is selected boundary only; full history requires user action. Four concurrent reads maximum, never an unbounded per-tick replay loop.
4. For captured layers, use catalogue boundaries within range, max32 per load and explicit continuation, pin one publication. Never request unrecorded ticks or interpolate across missing coverage. Deduplicate by qualified row identity + boundary, not label. Data points from different publications are separate series.
### Required Interfaces and Contracts
Objective samples are observations, not complete event history; no birth/death rate derived from sparse differences. Sample display includes schedule and gaps. Every request controller supports dispose/reset. No automatic retries for403/404/410/409; explicit reload for changed publication/expired cursor. At most one bounded transient request collection per mounted panel.
### Requirement Evidence
Existing immutable captures and replay costs; user requires tick/generation navigation, not exhaustive re-execution from the browser.
### Error Handling and Logging
DEBUG pending/completed/cancelled counts and local truncation reasons; WARN repeated/mismatched cursors. Preserve valid earlier pages on a transient continuation failure with explicit partial status. Clear them on auth/run/scope change.
### Tests
Deferred promises prove A→B→A responses cannot contaminate selection; credential rotation wipes debug data; empty pages continue; repeated cursors stop; caps/concurrency enforced; exact samples/gaps; new publication restart; unmount cancellation. Pin markers at H while viewing0, step through later generations and back without losing Next; advance H only on Refresh and reject mixed-H marker continuation.
### Acceptance Criteria
No stale response changes current graphs/charts; bounded loads stay responsive and disclose omissions.
### Verification
`pnpm --dir clients/research-ui test src/research/requests.test.ts src/research/paging.test.ts src/research/sampling.test.ts`.

## Phase Risks and Mitigations
Wire classes differ by endpoint: normalize once and retain original metadata. Unknown fields need not invalidate existing versioned envelopes, but unknown schema IDs must stop plotting.

## Phase Completion Checklist
Focused tests/check pass and index progress is updated.
