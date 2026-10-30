# Phase 7: Read-Only API, CLI, and Research UI

Plan: [index.md](index.md)
Tasks: 14-16
Depends on: Phase 5 (Task 11), Phase 6 (Tasks 12-13)

## Objective

Expose macro-society snapshots through GET-only `/v1` routes, compose the
producer in `research_runner`, and add a read-only Research UI panel. No client
gains authority, no observer protocol changes, and no Godot contract changes.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/infrastructure/settings.py` | `lineage_root` (214), `civilization_root` (215), cursor keys (216-217), presentation-root validator (257-271), cursor-key validators (275-292), `has_*` log extras (551-553) | Settings pattern for roots and secret cursor keys. |
| `src/api/lineage_cursor.py` | `LineageCursorCodec` (121) | HMAC, purpose-bound, TTL cursor codec to mirror. |
| `src/api/routes/lineage.py` | router prefix, capability dependency, disabled-service 503, page/cursor handling | Route shape to mirror. |
| `src/api/app.py` | `_attach_lineage_service` (246-247) | Composition-root wiring point. |
| `src/research_runner/lineage_composition.py` | producer options, capture install, finalize | CLI producer pattern. |
| `src/research_runner/cli.py` | `--lineage-root`, `--lineage-cadence`, quota flags | Flag naming and receipt pattern. |
| `clients/research-ui/src/api/` | existing typed API clients | Client module convention. |
| `clients/research-ui/src/router.ts`, `src/App.svelte` | route and navigation wiring | Where the panel is registered. |
| `clients/research-ui/src/views/LineagePanel.svelte` + `.test.ts` | read-only panel plus test | Panel and test pattern. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/infrastructure/settings.py` | modify | `macro_society_root`, `macro_society_cursor_key`, validators, safe log extras. |
| `src/api/macro_society_cursor.py` | create | Purpose-bound HMAC cursor codec. |
| `src/api/routes/macro_society.py` | create | Four GET routes. |
| `src/api/app.py` | modify | Attach reader/optional disabled state. |
| `src/research_runner/macro_society_composition.py` | create | CLI options and publish-after-run helper. |
| `src/research_runner/cli.py` | modify | Flags and receipt wiring. |
| `clients/research-ui/src/api/macroSocieties.ts` | create | Typed client. |
| `clients/research-ui/src/views/MacroSocietiesPanel.svelte` | create | Read-only panel. |
| `clients/research-ui/src/views/MacroSocietiesPanel.test.ts` | create | Panel tests. |
| `clients/research-ui/src/router.ts`, `src/App.svelte` | modify | Route and navigation entry. |
| `tests/unit/test_macro_society_api.py` | create | Route, credential, cursor, disabled-state tests. |
| `tests/unit/test_macro_society_cli.py` | create | CLI composition tests. |

## Task 14: Add settings and GET-only API routes

### Intent

Researchers need a query surface, but the API must stay a read adapter: it can
serve a committed publication and nothing else.

### Implementation Steps

1. In `src/infrastructure/settings.py` add
   `macro_society_root: Path | None = None` and
   `macro_society_cursor_key: SecretStr | None = Field(default=None, repr=False)`.
   Register `macro_society_root` in `empty_presentation_root_is_unset`, and add a
   validator requiring at least 32 UTF-8 bytes for
   `macro_society_cursor_key` (code `macro_society cursor key must be at least 32
   UTF-8 bytes`). Add `has_macro_society_root` and
   `has_macro_society_cursor_key` to the boolean log extras.
2. Create `src/api/macro_society_cursor.py` mirroring `LineageCursorCodec`:
   `MacroSocietyCursorCodec(secret: bytes, *, ttl_seconds: int = 900)` with
   `encode(purpose, run_id, publication_id, snapshot_digest, offset, filter_fingerprint)`
   and `decode(token, *, expected_purpose)`. Base64url payload + HMAC-SHA256;
   decode failures raise `macro_society_cursor_invalid`, expiry
   `macro_society_cursor_expired`. The codec must reject a changed purpose, run,
   publication, digest, or filter fingerprint.
3. Create `src/api/routes/macro_society.py` with
   `APIRouter(prefix="/v1/simulations", tags=["macro-societies"])` and four
   `@router.get` handlers:
   - `""`/`"/{run_id}/macro-societies"` → `macro_society_summary`
   - `"/{run_id}/macro-societies/candidates"` → `macro_society_candidates`
     with `status: Literal["supported","fragmented","contested"] | None`,
     `limit: int = 100`, `cursor: str | None`
   - `"/{run_id}/macro-societies/candidates/{macro_society_id}"` →
     `macro_society_candidate`
   - `"/{run_id}/macro-societies/lineage"` → `macro_society_lineage`
     with `kind` filter, `limit`, `cursor`
   Every route uses `Depends(require_http_capability(ApiCapability.SUBJECTIVE_DEBUG))`
   because candidates join owner-scoped evidence. Unknown ids return 404;
   unknown status/kind values return 422 through the existing validation layer.
4. In `src/api/app.py` attach the reader when `settings.macro_society_root` is
   set and the cursor key is present:
   `app.state.macro_society_reader`, `app.state.macro_society_cursor_codec`.
   When either is absent, leave the state unset and return 503
   `{"detail": "macro_society_disabled"}` from every route.
5. Response schemas are strict Pydantic-free dictionaries built by the route
   layer from the port DTOs, exactly like the lineage routes; no analysis import
   in `api`.

### Required Interfaces and Contracts

- GET only. No POST/PUT/PATCH/DELETE route exists.
- Credentials come from headers or WebSocket subprotocols, never query strings.
- The route layer never imports `analysis` or `experiments`.
- Responses never include unpublished evidence, member content, or prompt text.

### Error Handling and Logging

- `macro_society_disabled` 503; `macro_society_publication_missing` 404;
  `macro_society_cursor_invalid` 400; `macro_society_cursor_expired` 410.
- `INFO macro_society_read route=%s run=%s rows=%s` (counts only); `WARN` on
  cursor failure with the reason code only.

### Tests

`tests/unit/test_macro_society_api.py`:
- Each route returns the expected document from a stub reader.
- Missing credential → 401/403 as the existing capability dependency defines.
- Unset root → 503 for all four routes.
- Invalid cursor → 400; expired cursor → 410; cursor with a changed filter → 400.
- Unknown candidate id → 404.
- AST check: the route module contains no non-GET decorator and imports no
  `analysis`/`experiments` module.
- No route accepts `limit > MAX_PAGE_ROWS`.

### Acceptance Criteria

- Four GET routes exist under `/v1/simulations`.
- Disabled state is explicit, never a silent empty result.
- Cursor binding is purpose- and content-specific.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_macro_society_api.py tests/unit/test_lineage_api.py -q`

## Task 15: Compose the producer in research_runner

### Intent

A run produces a macro-society snapshot only when the operator asks for it, and
publication status is reported separately from scientific status.

### Implementation Steps

1. Create `src/research_runner/macro_society_composition.py`:
   - `@dataclass(frozen=True, slots=True) class MacroSocietyProducerOptions`
     with `root: Path | None`, `max_publications: int = 16`,
     `max_artifact_bytes: int = 8 * 1024 * 1024`.
   - `producer_options_from_args(args) -> MacroSocietyProducerOptions`.
   - `publish_macro_society_harvest(*, options, harvest) -> dict[str, object]`
     returning a receipt `{"status": "published" | "disabled" | "failed",
     "publication_id", "digest", "candidate_count", "edge_count", "reason_code"}`
     and never raising for storage failure; it logs `ERROR` with the safe code
     instead.
2. In `src/research_runner/cli.py` add `--macro-society-root`,
   `--macro-society-max-publications`, `--macro-society-max-bytes`, and include
   the receipt under `artifact_receipts` in the completed-run document. The
   producer runs only after successful scientific completion, in the same place
   the lineage finalizer runs.
3. Do not add live cadence capture; the harvest is built from the completed run's
   detached evidence. Document this limit in the module docstring and Task 19.
4. Ensure the CLI never starts HTTP and never imports `api`.

### Required Interfaces and Contracts

- Publication is opt-in and default off.
- A storage failure changes only `receipts.publication.status`, never
  `status`/metrics of the run.
- Receipt keys are stable and contain no member ids.

### Error Handling and Logging

- `ERROR macro_society_publish_failed run=%s reason_code=%s` on failure.
- `INFO macro_society_publish_skipped run=%s reason=disabled`.

### Tests

`tests/unit/test_macro_society_cli.py`:
- Args parse into `MacroSocietyProducerOptions`.
- Disabled options return `status="disabled"` and write nothing.
- A stub publisher failure returns `status="failed"` with the code and the
  scientific result object is unchanged.
- Receipt contains no member or owner ids.
- AST check: `research_runner` macro module imports no `api`.

### Acceptance Criteria

- Opt-in publication works end to end against the filesystem publisher.
- Scientific status and publication status are independent.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_macro_society_cli.py tests/unit/test_lineage_composition.py -q`
- `uv run --frozen --python 3.12.14 palimpsest-matrix --help` lists the new flags.

## Task 16: Add the read-only Research UI panel

### Intent

Researchers need a visual index of overlapping candidates and split/merge
history, clearly labelled as analytical output. The panel reads published
artifacts through the API and never derives its own identity.

### Implementation Steps

1. Create `clients/research-ui/src/api/macroSocieties.ts` with typed fetch
   helpers for the four routes and a shared `MacroSocietySummary`,
   `MacroSocietyCandidatePage`, `MacroSocietyCandidate`, and
   `MacroSocietyLineagePage` interface. Reuse the existing API client's error and
   credential handling.
2. Create `clients/research-ui/src/views/MacroSocietiesPanel.svelte`:
   - Summary strip: policy version, window count, candidate count, coverage
     ratios, `member_list_truncated` badge when set.
   - Candidate table: id, status, member count, lane chips, self-identification
     support, overlap marker.
   - Detail drawer: lane support counts, overlap members count, lineage parents
     and children with edge kind and Jaccard.
   - Lineage list filtered by kind.
   - Explicit empty state: "no published macro-society snapshot" and a disabled
     state when the API returns `macro_society_disabled`.
   - No client-side clustering, no id derivation, no merge/split inference.
3. Register the route in `clients/research-ui/src/router.ts` and add a navigation
   entry in `src/App.svelte` next to the lineage entry.
4. Add `MacroSocietiesPanel.test.ts` covering: summary render, candidate filter by
   status, overlap badge, lineage kind labels, disabled state, empty state, and
   that score/derivation functions are absent (no client-side computation).
5. Run `pnpm --dir clients/research-ui build` and `pnpm --dir clients/research-ui test`
   (Node 24.22.1 / pnpm 10.34.9 as pinned).

### Required Interfaces and Contracts

- Read-only: no mutating request, no client-side identity, no authority.
- Unknown fields from newer servers are ignored, unknown capability names are
  counted, not rendered as truth.
- The panel never imports analysis or simulation Python code (different runtime).

### Error Handling and Logging

- Client errors surface the safe code (`macro_society_disabled`,
  `macro_society_publication_missing`) and a retry hint.
- No member-level logging in the browser console.

### Tests

- `pnpm --dir clients/research-ui test` passes including the new panel suite.
- Existing Research UI tests stay green.

### Acceptance Criteria

- Panel renders published data only.
- Disabled and empty states are distinguishable.
- No Godot file changes.

### Verification

- `pnpm --dir clients/research-ui build`
- `pnpm --dir clients/research-ui test`

## Phase Risks and Mitigations

- Risk: the API leaks subjective evidence to an objective credential.
  Mitigation: every route requires `SUBJECTIVE_DEBUG`, tested explicitly.
- Risk: UI re-derives candidates and disagrees with the server.
  Mitigation: no computation in the client; tests assert absence of derivation
  helpers.
- Risk: CLI publication failure marks a run failed.
  Mitigation: separate receipt status, tested.

## Phase Completion Checklist

- Every Task 14-16 acceptance criterion is satisfied.
- Routes are GET-only and credential-gated.
- CLI publication is opt-in and non-interfering.
- Research UI is read-only and tested.
- `index.md` task checkboxes are updated immediately after verified completion.
