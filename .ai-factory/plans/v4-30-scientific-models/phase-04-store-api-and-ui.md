# Phase 4: Read-only model inspection

Plan: [index.md](index.md)
Tasks: 13–16
Depends on: Tasks 9–12

## Objective

Expose published predictions, observed outcomes, revisions and qualified
performance comparison through the existing research security boundary.

## Current-Code Evidence

| Path | Symbols / section | Why it matters |
| --- | --- | --- |
| `src/persistence/replication_filesystem.py` | `FilesystemReplicationStore`, reader/publisher factories | Atomic immutable sibling publications with cumulative quotas. |
| `src/infrastructure/settings.py` | replication/hypothesis root and cursor settings | Optional paired configuration and secret validation. |
| `src/api/routes/replication.py` | eight read-only routes | `SUBJECTIVE_DEBUG`, purpose-bound cursors, error mapping. |
| `src/api/app.py`, `src/api/routes/__init__.py` | research reader attachment/router export | Composition root only. |
| `clients/research-ui/src/api/replication.ts` | typed fetch/paging | Existing science client pattern. |
| `clients/research-ui/src/views/ReplicationPanel.svelte`, `RunOverview.svelte` | panel and integration | Read-only, uncertainty-aware presentation. |

## Files to Change

| Path | Action | Responsibility |
| --- | --- | --- |
| `src/persistence/scientific_models_filesystem.py` | create | Reader/publisher adapter and atomic store. |
| `src/infrastructure/settings.py` | modify | Optional root/cursor-key pair. |
| `src/api/routes/scientific_models.py` | create | Summary plus seven section GET routes. |
| `src/api/scientific_models_cursor.py` | create | Shared cursor aliases, TTL and feature purpose namespace. |
| `src/api/app.py`, `src/api/routes/__init__.py` | modify | Reader lifecycle/router registration. |
| `clients/research-ui/src/api/scientificModels.ts` | create | Typed snapshot/paging client. |
| `clients/research-ui/src/views/ScientificModelsPanel.svelte` | create | Forecast/outcome/calibration/comparison inspector. |
| `clients/research-ui/src/views/RunOverview.svelte` | modify | Register panel with existing run selection. |
| `tests/unit/test_scientific_models_store.py`, `test_scientific_models_api.py` | create | Storage and routes. |
| `tests/unit/test_scientific_models_cursor.py` | create | Purpose, expiry, publication/filter binding and cross-family rejection. |
| `tests/integration/test_scientific_models_store_api.py` | create | Real filesystem publisher/reader/API path. |
| `clients/research-ui/src/api/scientificModels.test.ts`, `src/views/ScientificModelsPanel.test.ts` | create | Client and presentation behavior. |
| `tests/architecture/test_scientific_models_boundaries.py` | create | Authority, imports and closed contract enforcement. |

## Task 13: Implement immutable quota-bounded filesystem storage

### Implementation Steps

1. Add `FilesystemScientificModelsStore` using
   `scientific-models-store-v1`. Follow replication's locking, canonical filename,
   child-before-manifest write, atomic publication reference and digest checks.
   Use independent store root; never reuse scientific-evidence SQL tables.
2. Reader and publisher factories implement only their declared inner ports.
   Reader never creates root directories, repairs files or updates a manifest.
   Validate run/publication identifiers and reject traversal, unexpected symlinks,
   digest mismatch, unknown versions and oversize payloads.
3. Preserve older publications and pinned pagination; repeated identical content
   publication is idempotent. Quotas are cumulative per run, not reset by a new
   publication. Defaults are `enabled=False`, `max_publications=16`,
   `max_bytes=8_388_608`, matching `ReplicationPublicationOptions`. Add explicit
   positive-integer validation (reject bool) to the new options contract; the
   sibling options dataclass does not provide a validator to reuse. Preserve
   cumulative accounting.
4. Make interrupted writes invisible and leave the previous publication readable.
   No delete/archive rewrite or live-cognition read is added.
5. Distinguish `scientific_models_store_run_missing` (no published run in this
   artifact store), `scientific_models_store_publication_missing` (run exists,
   requested publication absent), and `scientific_models_store_corrupt`
   (manifest names a missing/malformed child or digest mismatch). “Run missing”
   is artifact-scoped, not proof the simulation never existed. Do not copy a
   sibling's ambiguous single missing code.

### Errors, Logging and Tests

Expose closed corruption/quota/not-found codes; filesystem paths and payloads
never appear in client errors or operational exception text. Test idempotence,
two publications, cumulative quota, concurrent publishers, incomplete writes,
corrupt manifests/children, path escapes/symlinks and read-only missing roots.

### Acceptance Criteria and Verification

Only complete digest-verified snapshots become discoverable, and readers cannot
mutate the store.

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_scientific_models_store.py -q`

## Task 14: Add dual-gated GET-only scientific-model routes

### Implementation Steps

1. Add optional `PALIMPSEST_SCIENTIFIC_MODELS_ROOT` and
   `PALIMPSEST_SCIENTIFIC_MODELS_CURSOR_KEY` (`SecretStr`, at least 32 UTF-8
   bytes). Neither set means disabled; exactly one set is invalid configuration.
   Do not require these values at import time or add default deployment secrets.
2. Construct the reader in `api.app` lifecycle and register routes under
   `/v1/simulations/{run_id}/scientific-models`: summary at the root, then
   `/models`, `/predictions`, `/outcomes`, `/calibration`, `/revisions`,
   `/comparisons`, `/coverage`. Every route requires `SUBJECTIVE_DEBUG`.
   No POST/PATCH/DELETE or publication endpoint.
   Add `_attach_scientific_models_reader` to actual `create_app` wiring;
   explicitly initialize reader/cursor attributes to `None` when disabled.
   New cursor module aliases shared `DiplomacyCursorCodec`/`DiplomacyCursorError`
   as `ScientificModelsCursorCodec`/`ScientificModelsCursorError`, and exports
   `SCIENTIFIC_MODELS_CURSOR_TTL_SECONDS = 900`, following
   `api.replication_cursor`. Remap underlying expiry codes at the HTTP boundary;
   no diplomacy-family public errors escape.
3. Use snapshot-pinned HMAC cursors, domain-separated for this route family and
   section. Bind run, publication, normalized full filters, last row and expiry;
   never accept replication/hypothesis cursors. Page defaults 100, max 500.
   Filters are exactly Phase 3's paging contract.
   Expose optional `publication_id` on summary/sections. Authenticate, decode
   the cursor, then read its signed publication; never resolve latest first.
   Reject an explicit selector conflicting with the cursor. Bind snapshot
   digest and page limit too. Without cursor, use explicit publication or
   latest. Publishing B must not invalidate a valid cursor against retained A.
4. Map disabled → `scientific_models_disabled`/503, unknown run → 404,
   corruption → 500, malformed/tampered/filter-mismatched cursor → 400,
   expired cursor → 410; use the corresponding `scientific_models_*` safe codes.
   No read rebuilds analysis or creates a missing publication.
   Distinct store-missing cases map to
   `scientific_models_run_not_found` and
   `scientific_models_publication_not_found` (404). Missing published children
   remain corruption/500, never a not-found downgrade.
5. Lock section-specific filters:
   - `models`: `model_token`, `target_kind`, lifecycle `status`;
   - `predictions`/`outcomes`: `model_token`, `target_kind`, case `status`,
     `issued_from_tick`, `issued_through_tick`;
   - `calibration`/`revisions`: `model_token`, `target_kind`;
   - `comparisons`: `model_token` matching either member, `target_kind`,
     comparison `status`;
   - `coverage`: `target_kind`.
   Reject inapplicable filters/unknown section-status values with
   `scientific_models_filter_invalid`/400. Outcome model filters join through
   shared-case predictions. Aggregate rows expose their cohort/window bounds;
   reject arbitrary issuance ranges rather than relabeling unchanged precomputed
   statistics as a narrower cohort.

### Errors, Logging and Tests

Authorization fails before reading subjective data. No query-string credentials,
cursor secrets, raw cursor/payload logging or filesystem detail leakage.
Test both/unset/partial settings, all eight route paths, authorization,
bounded filters, frozen publication pagination and every cursor failure mode.
Use real `create_app(settings, attach_default_manager=False)` attachment.
Assert HTTP expiry/410, both 404s, section/filter failures and cursor A continuing
after publication B becomes latest.

### Acceptance Criteria and Verification

Routes expose only published research evidence behind existing subjective-debug
credentials and add no API/protocol version.

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_scientific_models_api.py -q`

## Task 15: Build the read-only Scientific Models panel

### Implementation Steps

1. Implement typed client functions for summary/seven sections with explicit
   tagged evidence layers, nullable metrics, status enums and opaque pagination
   cursors. Reuse the shared authenticated API transport; do not place credentials
   in URLs, local storage or Godot links.
   Fetch summary first, then pin its publication ID for every section request,
   including concurrent fetches; never mix different “latest” publications.
   Expose only filters supported by the selected section.
2. Add `ScientificModelsPanel.svelte` to `RunOverview.svelte`. Present model/source
   lineage and immutable revisions; an issuance timeline with prediction,
   confidence, committed-after tick, target tick, actual observed outcome and
   receipt tick; separate calibration bins and paired model comparison.
3. Labels must say “owner-observed outcome,” “predictive probability,”
   “retained-cohort calibration,” “lower loss on paired observations,” and
   “net resource change (not isolated regeneration).” Show disease unavailable,
   source missing, partial export, retention, pending/right-censored, unattempted
   production and insufficient samples distinctly.
4. Display Brier/calibration only inside qualified target/context/horizon groups.
   Do not pool them into a score, winner badge, truth indicator, owner ranking,
   science progress bar or recommendation. Zero is distinct from unavailable.
   Changing run/filter invalidates local cursors and ignores stale responses.
5. No edit model, revise forecast, trigger experiment, advance tick, tool control
   or Godot overlay is added. The UI renders already-published evidence only.

### Errors, Logging and Tests

Use existing safe disabled/error states; do not dump responses to console.
Component/client tests cover all sections, loading/disabled/missing/corrupt
states, stale fetches, pagination reset, escaped hostile labels, null versus zero,
comparability and exact epistemic labels.

### Acceptance Criteria and Verification

A researcher can inspect a prior prediction and its later observed outcome and
compare two models without confusing observation with truth.

- `pnpm --dir clients/research-ui test`
- `pnpm --dir clients/research-ui check`
- `pnpm --dir clients/research-ui build`

## Task 16: Prove end-to-end read isolation and authorization

### Implementation Steps

1. Add architecture assertions covering new cognition, analysis, simulation ports,
   experiments bridge, persistence and API modules. Enforce existing allowed
   package facades and no API→analysis, simulation→analysis, cognition→events/
   stores, or client→world writes.
2. Add real-filesystem integration: complete a representative science run,
   compose/publish its predictive snapshot, create the app with the supplied
   reader, traverse all sections and compare canonical published prediction
   tokens/ticks to API output. The run must contain a genuine pre-outcome case;
   a hand-written JSON snapshot is not the only end-to-end fixture.
   Use the production app factory with configured root/key, not assigned
   `app.state` readers or a hand-mounted router. Cover at least two issuance
   windows, all eight routes and multi-page traversal without skipped/duplicate
   rows. Publish B during traversal and prove A's cursor remains pinned to A.
3. Verify authorized repeated GETs leave files, manifests, objective events,
   runner state and publication digests unchanged. Missing publications are
   reported, never repaired.
4. Add log-capture tests with sentinel credentials, source claims, target names,
   distributions and outcomes. Prove sentinel absence in logs/errors and prevent
   safe-ID fields from carrying content hashes or payloads.

### Errors, Logging and Tests

Integration uses a temporary filesystem root; no production paths or database
required for this lane. Mark consistently with existing store/API integration.
Any optional database lane must use a disposable `palimpsest_test` database and
fail closed on ambiguous targets. Do not remove coverage to speed checks.

### Acceptance Criteria and Verification

The complete producer→immutable store→authorized API path works without
granting any read consumer mutation or live-analysis authority.

- `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/architecture/test_scientific_models_boundaries.py -q`
- `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term -m integration tests/integration/test_scientific_models_store_api.py -q`

## Phase Risks and Mitigations

- Small calibration values can look authoritative: qualify evidence/cohort and
  show unavailable/sample counts beside every statistic.
- Cross-family cursors can leak filters/publications: domain-separate and bind
  every query dimension.
- API reads might accidentally compose artifacts: enforce import and
  non-mutation tests over the real store path.

## Phase Completion Checklist

- Store, authorization, paging, UI and real publication path pass their tests.
- No deployment, SQL schema, world replay, API-version or Godot change.
- Update progress only in `index.md`.
