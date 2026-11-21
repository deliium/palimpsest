# Phase 3: Publish a bounded research view

Plan: [index.md](index.md)  
Tasks: 7–9  
Depends on: Phase 2

## Objective

Expose completed-run practice, evidence coverage and lineage through an opt-in, immutable research artifact. Neither the API nor either client runs detection.

## Current-Code Evidence

| Path | Existing seam |
|---|---|
| `src/experiments/competing_theories_publication.py` | `compose_competing_theories_snapshot` is an analysis-to-artifact composition precedent |
| `src/simulation/competing_theories_{models,codec,paging,ports}.py` | Explicit DTO shapes, canonical JSON/identity, read and publication ports |
| `src/persistence/replication_filesystem.py` | `FilesystemReplicationStore` locks writers and treats atomic `state.json` as the visibility boundary; competing-theory directory discovery and unbounded reads are not the store template |
| `src/api/routes/competing_theories.py`, `src/api/competing_theories_cursor.py` | `SUBJECTIVE_DEBUG`, stable snapshot pinning and read-only routes |
| `clients/research-ui/src/views/RunOverview.svelte`, `clients/research-ui/src/views/CompetingTheoriesPanel.svelte` | Read-only views with run-scoped selection and disabled/empty/errors |

## Files to Change

| Path | Action | Responsibility |
|---|---|---|
| `src/simulation/scientific_institutions_{models,codec,paging,ports}.py` | Create | Frozen snapshot contract and separate ports |
| `src/experiments/scientific_institutions_publication.py` | Create | Compose from detached output and explicitly publish |
| `src/persistence/scientific_institutions_filesystem.py` | Create | Atomic bounded store |
| `src/api/routes/scientific_institutions.py`, `src/api/scientific_institutions_cursor.py` | Create | Capability-protected typed reads |
| `src/infrastructure/settings.py`, `src/api/app.py`, `src/api/routes/__init__.py` | Modify | Dual settings, lifespan adapter construction, route registration |
| `clients/research-ui/src/api/scientificInstitutions.ts`, `clients/research-ui/src/views/ScientificInstitutionsPanel.{svelte,test.ts}` | Create | Typed read-only client and view |
| `clients/research-ui/src/views/RunOverview.svelte` | Modify | Mount with run/selection lifecycle |

## Task 7: Define and publish canonical snapshots

1. Define `scientific-institutions-snapshot-v1` with headers `schema_version`, `policy_version`, `run_id`, `input_revision`, `boundary_tick`, `windows`, `practice`, `signals`, `lineage`. Treat `input_revision` as a digest of canonical bounded detached inputs and source boundary identities, not a wall-clock timestamp. `windows` contains half-open ranges, mandatory and optional coverage and unassigned/ambiguous counts; `practice` has `(window, org token, operator, process token, status)`, participant counts and opaque evidence refs by layer; `signals` has keyed per-practice signal code, coverage and count/ref records; `lineage` contains episode window nodes by reference and typed edges or boundary records from Task 5. Validate exact keys/types, total rows and all window, practice and episode references. No raw native owner identifiers or payload save paths in the snapshot. Namespace export-facing organization tokens to the run; keep mappings internal to composition.
2. Reuse canonical JSON and separate read/publication port conventions. In `compose_scientific_institutions_snapshot`, reject rather than trim at 8,192 total rows (no section can exceed this), 8 MiB canonical bytes and the Phase 1 input caps. Recheck on encode and bounded decode. Use the replication store's commit pattern with a versioned `state.json` index, capped at 64 KiB, 32 entries and 64 MiB of committed snapshot bytes per run. Under a per-run writer lock, read/validate the index, check cumulative quota, write/fsync the content-addressed snapshot, then atomically replace/fsync the index. Only index entries are visible; readers ignore unindexed blobs and temp files. Identical publication is idempotent and cannot advance the current default. `latest` means last committed index entry, never lexicographic directory order. Verify exact run/publication/digest/size identities; bound reads before decoding, and confine run directories/files under the configured root without following symlink entries. Components use validated path segments. Retry may reuse a verified unindexed blob of the same digest; unindexed content never counts as published.
3. Safe DEBUG count/size/section codes at compose and read, INFO on successful new publish, WARNING on invalid/quota failures; no raw paths, credential, cursor, or row contents.

**Acceptance and tests:** `tests/unit/test_scientific_institutions_snapshot.py` and `tests/unit/test_scientific_institutions_store.py` cover canonical bytes, referenced rows, raw payload exclusion, oversized inputs and reads, corruption, concurrent cumulative-quota checks, retry/idempotence, and a fault after writing the blob but before index replacement. Assert old pages remain readable after a newer commit and an unindexed blob is neither listed nor selected.

## Task 8: Add capability-gated read routes

1. Add paired `PALIMPSEST_SCIENTIFIC_INSTITUTIONS_ROOT` and `PALIMPSEST_SCIENTIFIC_INSTITUTIONS_CURSOR_KEY` settings following existing secret/settings patterns and the competing-theory cursor key minimum (32 UTF-8 bytes). No pair: disabled. Half-pair or malformed configured key: startup validation error, before filesystem access. Construct store/reader only in `api.app` composition; do not import `analysis`/`experiments`.
2. Under `GET /v1/simulations/{run_id}/scientific-institutions`, serve summary at root plus `windows`, `practice`, `signals`, and `lineage` as separately paged sections. Summary includes pinned publication identity, policy/version, coverage, and section counts; no rows. Require `SUBJECTIVE_DEBUG` before lookup; no pair yields `scientific_institutions_disabled`, no publication uses the existing research unavailable/not-found convention, corrupt publication fails closed. A completely observed zero publishes an empty practice/lineage view with explicit coverage.
3. Require explicit `publication_id` for first section pages; only summary can resolve `latest`. Return publication ID and digest from summary and all sections; the client passes the summary ID to every first-page request and rejects any identity mismatch. Use a distinct `scientific-institutions:<section>` HMAC cursor purpose bound to run, publication, digest, limit and position for subsequent pages; reject mismatched explicit IDs, foreign/tampered cursors (400) and expiration (410). No filters, no automatic alias advance and no writes. Debug codes/context sizes only; never log key, token, cursor, native bodies or filesystem paths.

**Acceptance and tests:** `tests/unit/test_scientific_institutions_routes.py` covers unauthorized-before-store access, disabled, absent, empty, valid pages, tampering, expiry, cross-section/run mismatch, half-config and non-GET. Advance `latest` between summary and the first section fetch and again mid-pagination; both reads must remain pinned. Exercise one configured and one disabled deployment through `create_app`/lifespan rather than only assigning `app.state`. Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_scientific_institutions_{snapshot,store,routes}.py -q`.

## Task 9: Show practice and lineage in the Research UI

1. Add a typed client and a read-only panel keyed by active run using the competing-theory fetch/cancellation and selection patterns. Load summary first; load pages for windows, practice/signals, and lineage with explicit “load more” using the pinned publication. On run/selection change abort or ignore old responses and reset pages. Show stable, supported, observed-only, not-observed and coverage-unknown distinctly. Separate action facts, owner claims and analytical links in labels. Show lineage graph data as forward-time rows with upstream organization relation where supplied; no new graph renderer, Godot view, control action or credential in URL.
2. Use the existing research request path; don't add console logging of response or auth, and render safe error and unavailable states. Distinguish complete-empty from “not captured” and show the no-truth/no-prevalence caveat.

**Acceptance and tests:** `ScientificInstitutionsPanel.test.ts` covers gate/empty/partial, stale response after run switch, paged lineage, distinct statuses and no writes. Run `pnpm --dir clients/research-ui test`, `pnpm --dir clients/research-ui check` and `pnpm --dir clients/research-ui build`.

## Phase Risks and Mitigations

- Cross-publication joins: page cursors lock the snapshot and position; tests advance the latest pointer between pages.
- Misread authority: label all organizational roles and scientific institution links as research interpretations, not permission or proof of truth.
