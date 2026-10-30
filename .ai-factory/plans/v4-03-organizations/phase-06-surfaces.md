# Phase 6: Read-Only API, CLI, and Research UI

Plan: [index.md](index.md)
Tasks: 16-18
Depends on: Phase 5 / Tasks 14-15

## Objective

Expose published organization snapshots through four GET-only `/v1` routes, an
opt-in completed-run CLI producer, and a read-only Research UI panel. The API
reads committed artifacts only, requires `SUBJECTIVE_DEBUG`, and has an explicit
disabled state.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/infrastructure/settings.py` | `Settings` 124-138; artifact roots 211-219; root validator 261-276; secret validator 278-297; summary 562-569 | Exact pattern for a new root and cursor key. |
| `src/api/routes/macro_society.py` | router 22; `_reader`/`_cursor_codec` 28-40; `_authorize` 55-58; four routes 61-257 | Exact four-route, SUBJECTIVE_DEBUG, 503/400/410 pattern. |
| `src/api/macro_society_cursor.py` | HMAC codec 40-131; TTL 900s | Purpose-bound cursor signing. |
| `src/api/dependencies.py` | `get_macro_society_reader` 141-143 | Reader dependency pattern. |
| `src/api/app.py` | `_attach_macro_society_reader` 242-255; `create_app` 318/343 | Attachment and router inclusion. |
| `src/api/errors.py` | `bad_request`, `gone`, `not_found`, `service_unavailable`, `ProblemDetail` | RFC-7807 error mapping. |
| `src/api/lineage_schemas.py` | `_Strict` models | Strict response-schema pattern. |
| `src/research_runner/cli.py` | generational args 1245-1276/1384-1386; publication 1162-1219 | Opt-in sidecar and receipt pattern. |
| `src/research_runner/macro_society_composition.py` | options 36-66; publish 69-123 | Producer options and failure isolation. |
| `clients/research-ui/src/api/macroSocieties.ts` | typed fetch with `subjective_debug` | API client pattern. |
| `clients/research-ui/src/views/MacroSocietiesPanel.svelte` | status union and disabled state | Panel pattern. |
| `clients/research-ui/src/views/RunOverview.svelte` | tab entry 93-101; render 308-309 | Registration points. |
| `clients/research-ui/src/research/selection.ts` | `RESEARCH_UI_VIEWS` 8-31; `RUN_SCOPED_VIEWS` 35-57 | View registration. |
| `tests/unit/test_macro_society_api.py` | routes/auth/disabled/cursor | Test pattern. |
| `tests/unit/test_macro_society_cli.py` | options/receipt/failure | Test pattern. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/infrastructure/settings.py` | modify | Add `organization_root`, `organization_cursor_key`, validators, summary flags. |
| `src/api/organization_schemas.py` | create | Strict response models. |
| `src/api/organization_cursor.py` | create | HMAC cursor codec. |
| `src/api/routes/organization.py` | create | Four GET routes. |
| `src/api/dependencies.py` | modify | `get_organization_reader`. |
| `src/api/app.py` | modify | Attach reader/codec; include router. |
| `src/research_runner/organization_composition.py` | create | Producer options, publish, receipt. |
| `src/research_runner/cli.py` | modify | Three options on `run`, `resume`, `generational`; invoke producer; write receipt. |
| `clients/research-ui/src/api/organizations.ts` | create | Typed GET client. |
| `clients/research-ui/src/views/OrganizationsPanel.svelte` | create | Read-only panel. |
| `clients/research-ui/src/views/RunOverview.svelte` | modify | Tab and render branch. |
| `clients/research-ui/src/research/selection.ts` | modify | View id and run-scoped registration. |
| `clients/research-ui/src/views/OrganizationsPanel.test.ts` | create | Panel tests. |
| `tests/unit/test_organization_settings.py` | create | Root/secret validation. |
| `tests/unit/test_organization_api.py` | create | Route/auth/disabled/cursor/schemas. |
| `tests/unit/test_organization_cli.py` | create | Options/receipt/failure. |

## Task 16: Add settings and GET-only API routes

### Intent

Serve committed snapshots without rebuilding analysis or importing it. The API
must be explicit about disabled configuration and must never mutate artifacts.

### Implementation Steps

1. In `src/infrastructure/settings.py`:
   - add `organization_root: Path | None = None` beside `macro_society_root`;
   - add `organization_cursor_key: SecretStr | None = Field(default=None,
     repr=False)`;
   - add both to the empty-root validator list and the cursor-key validator
     (minimum 32 UTF-8 bytes);
   - add `has_organization_root` and `has_organization_cursor_key` to the
     secret-safe summary dict.
2. Create `src/api/organization_schemas.py` with strict frozen models
   (`extra="forbid"`):
   - `OrganizationSummaryOut`
   - `OrganizationCandidateOut`
   - `OrganizationMemberOut`
   - `OrganizationStructuralOut`
   - `OrganizationWindowOut`
   - `OrganizationLineageEdgeOut`
   - `OrganizationCandidateListOut`
   - `OrganizationLineageListOut`
   - `OrganizationCoverageOut`
3. Create `src/api/organization_cursor.py`:
   - `OrganizationCursorCodec.from_secret(secret)` requires >= 32 bytes;
   - encode/decode `OrganizationCursor` with canonical JSON, base64url, and
     HMAC-SHA256;
   - TTL `900` seconds;
   - reject purpose mismatch, signature mismatch, expiry, run/publication/
     fingerprint mismatch with `OrganizationCursorError` codes;
   - never log token contents.
4. Create `src/api/routes/organization.py`:
   - `APIRouter(prefix="/v1/simulations", tags=["organizations"])`;
   - `GET /{run_id}/organizations` → summary;
   - `GET /{run_id}/organizations/candidates?status=&limit=&cursor=` → page;
   - `GET /{run_id}/organizations/candidates/{organization_id}` → detail;
   - `GET /{run_id}/organizations/lineage?kind=&limit=&cursor=` → page;
   - all routes `@router.get`, `Cache-Control: no-store`;
   - `_authorize` always requires `ApiCapability.SUBJECTIVE_DEBUG`;
   - missing reader/codec → 503 `organization_disabled`;
   - missing run/publication → 404 `organization_publication_missing`;
   - unknown candidate → 404 `organization_unknown_candidate`;
   - invalid cursor/fingerprint → 400 `organization_cursor_invalid`;
   - expired cursor → 410 `organization_cursor_expired`;
   - `limit` default 100, `ge=1`; paging clamps to 500;
   - `status`/`kind` are closed `Literal` values;
   - response bytes are capped at `MAX_RESPONSE_BYTES`; over-cap → 400
     `organization_response_limit`.
5. In `src/api/dependencies.py`, add `get_organization_reader` reading the app
   state key; return `None` when unattached.
6. In `src/api/app.py`, add `_attach_organization_reader`:
   - when `settings.organization_root is None` or the cursor key is unset,
     attach nothing;
   - otherwise create the codec and `create_organization_reader`;
   - include the router once.
7. Tests:
   - summary/candidates/detail/lineage happy paths;
   - missing credential → 401;
   - disabled → 503 `organization_disabled`;
   - unknown candidate → 404;
   - invalid vs expired cursor → 400/410;
   - cursor reused with a changed filter/publication → 400;
   - response cap enforced;
   - route module contains only `@router.get`;
   - API modules import no `analysis`, `experiments`, or `agents.cognition`.

### Required Interfaces and Contracts

```text
GET /v1/simulations/{run_id}/organizations
GET /v1/simulations/{run_id}/organizations/candidates
GET /v1/simulations/{run_id}/organizations/candidates/{organization_id}
GET /v1/simulations/{run_id}/organizations/lineage
```

- All four require `SUBJECTIVE_DEBUG`; there is no credential-free variant.
- `organization_disabled` is the only disabled code.
- The API never builds, repairs, or mutates a snapshot.
- `GET /version`, observer protocol, and observer capabilities are unchanged.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Read-only presentation": `/v1` GET-only,
  purpose-specific credentials, explicit disabled state.
- `docs/research-api.md` versioning policy: no `/v2`, no write route.
- V4-02 route precedent.

### Error Handling and Logging

- Stable problem codes only.
- INFO `organization_api_request route=%s run_id=%s rows=%s` (no ids beyond
  run/publication).
- WARN `organization_api_cursor_invalid reason=%s`.
- Never log cursor tokens, member ids, or labels.

### Tests

- `uv run pytest tests/unit/test_organization_settings.py tests/unit/test_organization_api.py -q`
- `uv run pytest tests/architecture/test_organization_boundaries.py -q -k api`
- Expected: pass.

### Acceptance Criteria

- Four GET-only routes exist under `/v1`.
- `SUBJECTIVE_DEBUG` and disabled state are enforced.
- Cursors bind run, publication, purpose, and filters.
- API imports no analysis/experiments/cognition.

### Verification

- `uv run python -c "from api.routes.organization import router; print(sorted((r.path, tuple(sorted(r.methods))) for r in router.routes))"`
- Expected: four paths, each with `GET` only.

## Task 17: Compose the producer in research_runner

### Intent

Publish organizations only after scientific completion, as an opt-in sidecar.
A storage or composition failure changes only the receipt.

### Implementation Steps

1. Create `src/research_runner/organization_composition.py`:
   - `OrganizationProducerOptions`: `root`, `max_publications=16`,
     `max_artifact_bytes=8 * 1024 * 1024`; `enabled` is `root is not None`.
   - `producer_options_from_args(args)` reads
     `organization_root`, `organization_max_publications`,
     `organization_max_bytes`; enforce positive values and upper caps
     (`1024`, `256 MiB`).
   - `publish_organization_harvest(runner_result, *, run_id, input_revision,
     generated_tick, options)`:
     - return `{"status": "disabled", "reason_code": "organization_disabled"}`
       when disabled;
     - return `unavailable` with `organization_run_incomplete` when the run did
       not complete;
     - build the harvest; on `OrganizationArtifactError` return `unavailable`
       with the code;
     - publish through `create_organization_publisher`; return the safe
       publication document with `status="published"`;
     - catch `OrganizationArtifactError`, `ValueError`, `OSError` and return
       `failed` with a reason code only.
2. In `src/research_runner/cli.py`:
   - add `--organization-root`, `--organization-max-publications` (default 16),
     `--organization-max-bytes` (default 8_388_608) to the `generational` parser
     only; do not add them to the matrix `run`/`resume` commands because V4 flags
     remain rejected by matrix finalization;
   - after `arm = asyncio.run(execute_generational_assignment(...))`, read
     `arm.runner_result` and `arm.config_fingerprint`; use
     `runner_stop_is_failure(arm.runner_result.stop_reason)` to decide whether
     the run is incomplete;
   - when options are enabled and the run is complete, call
     `publish_organization_harvest(runner_result=arm.runner_result,
     run_id=assignment.run_id.value, input_revision=arm.config_fingerprint,
     generated_tick=arm.runner_result.ticks_committed, options=...)`;
   - write `<artifact_root>/organization-publication-<run_id>.json` with the
     receipt; a receipt write failure only logs;
   - print `organization_publication_status`, `..._reason`, and optional
     `..._id`;
   - never alter the scientific result or exit code.
3. Do not add a new CLI subcommand. Do not import `api`.
4. Tests:
   - option parsing and cap rejection;
   - disabled writes nothing;
   - missing/incomplete run → `unavailable`;
   - publication failure → `failed` receipt;
   - receipt is id-free and contains no member/owner ids;
   - end-to-end publish from a completed fixture;
   - CLI does not import `api`.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class OrganizationProducerOptions:
    root: Path | None
    max_publications: int = 16
    max_artifact_bytes: int = 8 * 1024 * 1024

    @property
    def enabled(self) -> bool: ...
```

- Receipt statuses are exactly `disabled`, `unavailable`, `published`, `failed`.
- A publication failure is not a scientific failure.
- No HTTP server is started.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Read-only presentation": publication is opt-in
  and completed-run only.
- V4-02 CLI receipt precedent.
- `.ai-factory/ARCHITECTURE.md` "Dependency Rules": `research_runner` must not
  import `api`.

### Error Handling and Logging

- WARN `organization_publication_failed run_id=%s reason=%s`.
- INFO `organization_publication_published run_id=%s publication_id=%s`.
- Never log member/owner ids.

### Tests

- `uv run pytest tests/unit/test_organization_cli.py -q`
- Expected: pass.

### Acceptance Criteria

- Publication is opt-in, post-completion, and receipt-isolated.
- No new subcommand or HTTP dependency.
- Receipts are id-free.

### Verification

- `uv run pytest tests/unit/test_organization_cli.py -q -k disabled`
- Expected: pass.

## Task 18: Add the read-only Research UI panel

### Intent

Let researchers inspect organization candidates and lineage without client-side
derivation or write access. The panel must show explicit disabled and empty
states and invent no data.

### Implementation Steps

1. Create `clients/research-ui/src/api/organizations.ts`:
   - types `OrganizationSummary`, `OrganizationCandidate`,
     `OrganizationCandidateDetail`, `OrganizationMember`,
     `OrganizationStructural`, `OrganizationLineageEdge`;
   - functions `getOrganizationSummary`, `getOrganizationCandidates`,
     `getOrganizationCandidate`, `getOrganizationLineage`;
   - all use `apiFetch` with `capability: 'subjective_debug'` and the route base
     `/v1/simulations/<runId>/organizations`.
2. Create `OrganizationsPanel.svelte`:
   - props `{ runId, selection }`;
   - local `$state`; status union
     `loading | available | empty | unavailable | error`;
   - `$effect` reloads on `runId`;
   - fetch summary, candidates (`limit: 200`), and lineage (`limit: 200`);
   - map `ApiClientError.code === 'organization_disabled'` to `unavailable`;
   - render summary counts, status filter, candidate table (id, status,
     temporal scope, members, roles, goals, records), candidate detail
     (membership statuses, structural anchors, lineage), and explicit copy for
     disabled/empty;
   - no derived organization labels, no client-side lineage reconstruction, no
     write calls.
3. Register the view:
   - add `'organizations'` to `RESEARCH_UI_VIEWS` and `RUN_SCOPED_VIEWS` in
     `selection.ts`;
   - add a `{ id: 'organizations', label: 'Organizations' }` tab in the
     Institutions group of `RunOverview.svelte`;
   - add the render branch.
4. Tests `OrganizationsPanel.test.ts`:
   - summary/candidates/lineage render;
   - disabled state invents no data;
   - empty state is explicit;
   - status filter changes the request;
   - no POST/PUT/PATCH/DELETE call exists.

### Required Interfaces and Contracts

- The panel performs only GET requests with `subjective_debug`.
- No client-side candidate detection, identity minting, or lineage derivation.
- Disabled means absent, not empty.
- The panel uses the existing Research UI view registry; no new router.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Read-only presentation": presentation selection
  never mutates world state.
- `.ai-factory/ARCHITECTURE.md` "Dependency Rules": Python never imports either
  client.
- V4-02 Research UI precedent.

### Error Handling and Logging

- Show a safe error message with the API code; never render raw payloads.
- No console logging of member ids or labels.

### Tests

- `cd clients/research-ui && pnpm test -- OrganizationsPanel`
- `cd clients/research-ui && pnpm run check`
- Expected: pass.

### Acceptance Criteria

- A read-only panel consumes the four routes.
- Disabled/empty states are explicit.
- No client-side derivation or write path exists.

### Verification

- `cd clients/research-ui && pnpm test -- OrganizationsPanel`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: the API imports analysis to recompute rows.
  Mitigation: it consumes only the read port; Task 19 AST check.
- Risk: missing settings silently serve an empty page.
  Mitigation: `None` reader → 503 `organization_disabled`.
- Risk: the CLI publication failure changes the run result.
  Mitigation: catch and receipt only; test exit/result parity.
- Risk: the UI fabricates organization labels or membership.
  Mitigation: render only server rows; no derivation; disabled/empty tests.
- Risk: cursor reuse across filters serves inconsistent pages.
  Mitigation: fingerprint binding and 400 on mismatch.

## Phase Completion Checklist

- Every Task 16-18 acceptance criterion is met.
- Settings, API, CLI, and UI tests pass.
- Four GET-only `/v1` routes exist; no `/v2`, write route, or observer change.
- `index.md` checkboxes are updated immediately after verified completion.
