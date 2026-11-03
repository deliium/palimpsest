# Phase 6: Read-Only API and Research UI

Plan: [index.md](index.md)
Tasks: 18-19
Depends on: Phase 5 / Tasks 16-17

## Objective

Serve the committed dispute snapshots through six GET-only `/v1` routes under
`SUBJECTIVE_DEBUG`, with strict schemas and digest-bound cursors, and render them
in a read-only Research UI view that never implies a verdict.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/api/routes/formal_rule.py` | router 43; auth 91-94; disabled 78-88; six routes 238-544 | Exact six-route pattern. |
| `src/api/formal_rule_schemas.py` | strict models 8-167; paged shape 119-148 | Response-schema pattern. |
| `src/api/formal_rule_cursor.py` | `FormalRuleCursorCodec` 26; encode/decode 76-135 | HMAC cursor pattern. |
| `src/api/app.py` | `_attach_formal_rule_reader` 280-297; attach 359-363; include 379-395 | App wiring point. |
| `src/api/dependencies.py` | `get_formal_rule_reader` | Dependency pattern. |
| `src/api/routes/__init__.py` | router exports | Registration point. |
| `src/api/errors.py` | `ProblemDetail` 19-30; `ApiError` 33-61; helpers 64-97 | Error shape. |
| `src/infrastructure/settings.py` | formal-rule fields 220-223; validators 316-318; safe summary 598-601 | Settings pattern. |
| `src/api/security.py` | `ApiCapability` 43-49; `require_http_capability` 119-199 | Auth scope. |
| `clients/research-ui/src/api/formalRules.ts` | typed client, capability, six fetches | UI API pattern. |
| `clients/research-ui/src/views/FormalRulesPanel.svelte` | status machine, load, read-only render | Panel pattern. |
| `clients/research-ui/src/research/selection.ts` | `RESEARCH_UI_VIEWS`, `RUN_SCOPED_VIEWS` | View registration. |
| `clients/research-ui/src/views/RunOverview.svelte` | tab group and render branch | UI integration point. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/infrastructure/settings.py` | modify | Add `dispute_root`, `dispute_cursor_key`, validators, safe summary. |
| `src/api/dispute_cursor.py` | create | HMAC cursor with six purposes and digest binding. |
| `src/api/dispute_schemas.py` | create | Strict summary/candidate/claim/resolution/lineage/page models. |
| `src/api/routes/dispute.py` | create | Six GET routes, auth, disabled state, cursor/error mapping. |
| `src/api/routes/__init__.py` | modify | Export `dispute_router`. |
| `src/api/dependencies.py` | modify | `get_dispute_reader`. |
| `src/api/app.py` | modify | Attach reader/codec and include router. |
| `clients/research-ui/src/api/disputes.ts` | create | Typed client and six fetches. |
| `clients/research-ui/src/views/DisputesPanel.svelte` | create | Read-only panel. |
| `clients/research-ui/src/views/DisputesPanel.test.ts` | create | Panel tests. |
| `clients/research-ui/src/research/selection.ts` | modify | Register `disputes` in view lists. |
| `clients/research-ui/src/views/RunOverview.svelte` | modify | Add tab and render branch. |
| `tests/unit/test_dispute_api.py` | create | Route/auth/cursor/disabled/size tests. |
| `tests/unit/test_dispute_settings.py` | create | Settings validation and safe summary. |

## Task 18: Add six GET routes, schemas, settings, and app wiring

### Intent

Expose the published snapshot read-only with the same security and cursor
semantics as the existing V4 contexts. Unconfigured storage fails closed.

### Implementation Steps

1. In `src/infrastructure/settings.py`:
   - add `dispute_root: Path | None = None` and
     `dispute_cursor_key: SecretStr | None = Field(default=None, repr=False)`;
   - treat a blank root as unset;
   - require a cursor key of at least 32 UTF-8 bytes;
   - add `has_dispute_root` and `has_dispute_cursor_key` to the safe summary;
   - never expose the key value.
2. Create `src/api/dispute_cursor.py`:
   - `DisputeCursorCodec` with HMAC-SHA256, key >= 32 bytes, TTL 900 seconds;
   - payload binds `purpose`, `run_id`, `publication_id`, `snapshot_digest`,
     `offset`, `query_fingerprint`, and expiry;
   - `from_secret`, `encode`, `decode`;
   - stable errors `dispute_cursor_invalid` and `dispute_cursor_expired`.
3. Create `src/api/dispute_schemas.py` with `model_config =
   ConfigDict(extra="forbid")`:
   - `DisputeCoverageOut`, `DisputeSummaryOut`, `DisputeCandidateOut`,
     `DisputeCandidateDetailOut`, `DisputeClaimOut`, `DisputeTestimonyOut`,
     `DisputeEvidenceOut`, `DisputeRuleReferenceOut`,
     `DisputeAuthorityReferenceOut`, `DisputeMediationReferenceOut`,
     `DisputeResolutionOut`, `DisputeResolutionResponseOut`,
     `DisputeLineageEdgeOut`. `DisputeSummaryOut` is built from the read-port
     `DisputeSummary`, not the analysis `DisputeAnalysisSummary`;
   - paged models `DisputeCandidatePageOut`, `DisputeClaimPageOut`,
     `DisputeResolutionPageOut`, `DisputeLineagePageOut` with `items`,
     `next_cursor`, `truncated`.
4. Create `src/api/routes/dispute.py`:
   - `router = APIRouter(prefix="/v1/simulations", tags=["disputes"])`;
   - six GET routes:
     - `GET /{run_id}/disputes` → `reader.summary(run_id)`;
     - `GET /{run_id}/disputes/candidates` →
       `reader.candidates(run_id, status=status, offset=offset, limit=limit)`;
     - `GET /{run_id}/disputes/candidates/{candidate_id}` →
       `reader.candidate(run_id, candidate_id)`;
     - `GET /{run_id}/disputes/candidates/{candidate_id}/claims` →
       `reader.claims(run_id, candidate_id=candidate_id, role=role,
       offset=offset, limit=limit)`;
     - `GET /{run_id}/disputes/candidates/{candidate_id}/resolutions` →
       `reader.resolutions(run_id, candidate_id=candidate_id, status=status,
       offset=offset, limit=limit)`;
     - `GET /{run_id}/disputes/lineage` →
       `reader.lineage(run_id, kind=kind, offset=offset, limit=limit)`.
   - `_authorize` uses `ApiCapability.SUBJECTIVE_DEBUG` and requires debug
     enabled; query-string credentials are rejected by the existing security
     helper.
   - `_reader(None)` and `_codec(None)` raise
     `service_unavailable(code="dispute_disabled")` (503).
   - expired cursor → 410 `dispute_cursor_expired`; any other cursor error → 400
     `dispute_cursor_invalid`.
   - `_charge(payload.model_dump())` against `MAX_RESPONSE_BYTES`; overflow →
     400 `dispute_size_limit`.
5. Wire `src/api/dependencies.py` with `get_dispute_reader(request)` returning
   `app.state.dispute_reader`.
6. In `src/api/app.py`:
   - add `_attach_dispute_reader(app)` that reads
     `settings = getattr(app.state, "settings", None)` defensively; when
     settings are absent, set `dispute_cursor_codec` and `dispute_reader` to
     `None` and return without raising (the 2026-10-26 patch records the
     `AttributeError` from eager `app.state.settings` access on a bare app);
   - when settings exist, set both only when root and key exist; otherwise set
     both to `None`;
   - call it with the other V4 readers;
   - `app.include_router(dispute_router)`;
   - mount `/research/` before the Godot root unchanged.
7. No `/v2` route, no POST/PUT/PATCH/DELETE, no observer protocol change, no
   analysis import in API.

### Required Interfaces and Contracts

```python
router = APIRouter(prefix="/v1/simulations", tags=["disputes"])

# GET /{run_id}/disputes
# GET /{run_id}/disputes/candidates
# GET /{run_id}/disputes/candidates/{candidate_id}
# GET /{run_id}/disputes/candidates/{candidate_id}/claims
# GET /{run_id}/disputes/candidates/{candidate_id}/resolutions
# GET /{run_id}/disputes/lineage

def get_dispute_reader(request: Request) -> object: ...
```

Compatibility invariants:

- Exactly six GET routes.
- `SUBJECTIVE_DEBUG` is required.
- Unconfigured storage returns `503 dispute_disabled`.
- Cursors bind to the publication digest and filter fingerprint.
- API imports no analysis or production bridge.

### Requirement Evidence

- `src/api/routes/formal_rule.py` 43, 78-121, 238-544.
- `src/api/formal_rule_cursor.py` 26, 76-135.
- `src/api/app.py` 280-297: optional reader attachment pattern.
- `src/infrastructure/settings.py` 220-223, 316-318, 598-601.
- `.ai-factory/patches/2026-10-26-01.22.md`: optional attachment must not assume
  `app.state.settings`.
- `.ai-factory/ARCHITECTURE.md` "Research capabilities separate control,
  objective inspection, agent-visible projection, and default-disabled
  subjective debug."

### Error Handling and Logging

- Missing credential: `401 unauthorized`.
- Wrong capability: `403 forbidden`.
- Debug disabled: `403 debug_disabled`.
- Unconfigured store: `503 dispute_disabled`.
- Missing run/publication: `404 dispute_not_found`.
- Invalid cursor: `400 dispute_cursor_invalid`; expired: `410`.
- Oversize response: `400 dispute_size_limit`.
- INFO request log with route, status, count, and duration; never claim content.

### Tests

`tests/unit/test_dispute_api.py`:

- `test_six_get_routes_exist_and_no_write_methods`
- `test_subjective_debug_is_required`
- `test_unconfigured_reader_returns_dispute_disabled`
- `test_cursor_round_trip_and_changed_filter_invalidates`
- `test_expired_cursor_returns_410`
- `test_oversized_response_returns_size_limit`
- `test_api_does_not_import_analysis_or_experiments_producer`
- `test_bare_app_attachment_without_settings_is_optional`

`tests/unit/test_dispute_settings.py`:

- `test_blank_dispute_root_is_unset`
- `test_cursor_key_requires_32_bytes`
- `test_safe_summary_exposes_presence_only`

Run: `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_api.py tests/unit/test_dispute_settings.py -q`.

### Acceptance Criteria

- Six GET routes exist and require `SUBJECTIVE_DEBUG`.
- Unconfigured storage fails closed.
- Cursor invalid/expired mapping is exact.
- API never imports analysis or the producer.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_api.py tests/unit/test_dispute_settings.py -q`
- Expected result: all tests pass.

## Task 19: Add the read-only Research UI disputes view

### Intent

Let researchers inspect claims, testimony, evidence, rule references, mediation
links, and proposed/declared resolutions without deriving truth or a verdict.

### Implementation Steps

1. Create `clients/research-ui/src/api/disputes.ts`:
   - `CAPABILITY = 'subjective_debug'`;
   - types mirroring the six response schemas;
   - functions `getDisputeSummary`, `getDisputeCandidates`,
     `getDisputeCandidate`, `getDisputeClaims`, `getDisputeResolutions`,
     `getDisputeLineage`, each using `apiFetch` and `credentialFor`.
2. Create `clients/research-ui/src/views/DisputesPanel.svelte`:
   - props `runId`, `selection`;
   - status machine `loading | available | empty | unavailable | error`;
   - load summary and candidates; on selection load detail, claims, resolutions,
     and lineage;
   - map `dispute_disabled` to `unavailable`, not an error;
   - render:
     - summary counts/coverage/publication;
     - candidate table with kind, status, party count, claim/counterclaim counts,
       disagreement count, coverage;
     - claim table with **Claimant**, **Role**, **Polarity**, **Claim kind**,
       **Evidence count**, **First tick**, **Last tick**;
     - testimony table with **Speaker**, **Channel**, **Root**, **Independent**;
     - evidence/rule/authority/mediation reference tables with safe counts and
       tokens;
     - resolution table with **Proposer**, **Source**, **Terms digest**,
       **Status**, **Accepted parties**, **Rejected parties**, **Expiry**;
     - response table with **Party**, **Declaration**, **Tick**, **Terms
       digest**;
     - lineage table.
   - Use labels `claimed`, `reported`, `declared`, `apparently accepted`; never
     `verdict`, `guilty`, `liable`, `winner`, `true owner`, or `binding`.
   - No POST/PUT/PATCH/DELETE; no local derivation of truth.
3. Create `clients/research-ui/src/views/DisputesPanel.test.ts`:
   - mock the six API calls;
   - assert read-only rendering, `dispute_disabled` mapping, empty state, and
     no verdict labels;
   - assert candidate selection reloads detail/claims/resolutions.
4. In `clients/research-ui/src/research/selection.ts`, add `'disputes'` to
   `RESEARCH_UI_VIEWS` and `RUN_SCOPED_VIEWS`.
5. In `clients/research-ui/src/views/RunOverview.svelte`, import
   `DisputesPanel`, add a `Disputes` tab next to Formal rules, and render it when
   `view === 'disputes'`.
6. Do not change the Godot client, observer protocol, or `/version`.

### Required Interfaces and Contracts

```ts
export const CAPABILITY = 'subjective_debug'
export async function getDisputeSummary(runId: string): Promise<DisputeSummary>
export async function getDisputeCandidates(runId: string, cursor?: string): Promise<DisputeCandidatePage>
export async function getDisputeCandidate(runId: string, candidateId: string): Promise<DisputeCandidateDetail>
export async function getDisputeClaims(runId: string, candidateId: string, cursor?: string): Promise<DisputeClaimPage>
export async function getDisputeResolutions(runId: string, candidateId: string, cursor?: string): Promise<DisputeResolutionPage>
export async function getDisputeLineage(runId: string, cursor?: string): Promise<DisputeLineagePage>
```

Compatibility invariants:

- Read-only: no write call exists.
- The panel uses only server-provided fields.
- No truth, guilt, liability, or winner is derived.
- `dispute_disabled` is a normal unavailable state.

### Requirement Evidence

- `clients/research-ui/src/api/formalRules.ts`;
  `clients/research-ui/src/views/FormalRulesPanel.svelte`;
  `clients/research-ui/src/research/selection.ts`;
  `clients/research-ui/src/views/RunOverview.svelte`.
- `.ai-factory/ARCHITECTURE.md` "Both clients stay read-only."

### Error Handling and Logging

- API error with `dispute_disabled` → `unavailable`.
- Other API error → `error` with the safe code.
- Empty candidates → `empty`.
- No client-side logging of claims, parties, evidence, or resolution terms.

### Tests

`clients/research-ui/src/views/DisputesPanel.test.ts`:

- `test_renders_claims_and_counterclaims_separately`
- `test_renders_declared_acceptance_without_binding_label`
- `test_maps_dispute_disabled_to_unavailable`
- `test_empty_state`
- `test_candidate_selection_loads_detail_claims_and_resolutions`
- `test_no_write_requests`

Commands:

- `cd clients/research-ui && pnpm test`
- `cd clients/research-ui && pnpm check`
- `cd clients/research-ui && pnpm build`

### Acceptance Criteria

- A read-only Disputes panel is reachable from a run.
- Claims, counterclaims, testimony, evidence, rule references, mediation links,
  and resolutions render.
- No verdict/guilt/liability/winner label exists.
- Test, check, and build lanes pass.

### Verification

- `cd clients/research-ui && pnpm test && pnpm check && pnpm build`
- Expected result: all tests pass, zero type/Svelte errors, production build
  succeeds.

## Phase Risks and Mitigations

- Risk: A route accidentally exposes an owner-local id.
  Mitigation: Task 14 publication filtering and Task 18 schema tests.
- Risk: A cursor from another context is accepted.
  Mitigation: Task 18 purpose binding and changed-filter tests.
- Risk: UI derives a verdict from objective alignment.
  Mitigation: Task 19 label test and no-truth rendering.
- Risk: API imports analysis or the producer.
  Mitigation: Task 18 import test and Task 20 boundary scan.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
