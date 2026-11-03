# Phase 6: Read-Only API and Research UI

Plan: [index.md](index.md)
Tasks: 17-18
Depends on: Phase 5 / Task 16

## Objective

Expose six GET-only `/v1` formal-rule routes behind `SUBJECTIVE_DEBUG`, with an
explicit `formal_rule_disabled` state and digest-bound cursors, and render the
published fields in a read-only Research UI panel without deriving law,
violation truth, or enforcement.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/api/routes/organization.py` | prefixes 39-48; auth 73-98; cursor decode 100-130; six routes 168-485 | Exact route/auth/cursor/error pattern. |
| `src/api/organization_cursor.py` | TTL 24; codec 36-130 | HMAC cursor codec to mirror. |
| `src/api/organization_schemas.py` | summary/candidate/detail/page models | Pydantic response pattern. |
| `src/api/dependencies.py` | `get_organization_reader`, `get_settings` | Dependency wiring. |
| `src/api/app.py` | `_attach_organization_reader` 260-279; lifespan attach calls | App state wiring. |
| `src/infrastructure/settings.py` | root/cursor fields 218-222; validators 250-270 | New root/secret fields from Task 16. |
| `clients/research-ui/src/api/organizations.ts` | client types and fetchers | API client pattern. |
| `clients/research-ui/src/views/OrganizationsPanel.svelte` | load/status/detail pattern | Panel pattern. |
| `clients/research-ui/src/views/RunOverview.svelte` | import 40; render 313 | Panel registration point. |
| `clients/research-ui/src/views/OrganizationsPanel.test.ts` | render/status tests | UI test pattern. |
| `docs/research-api.md` | line 30 organization routes; line 53 unowned statement | Must be updated in Task 22. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/api/formal_rule_schemas.py` | create | Response/list/detail models. |
| `src/api/formal_rule_cursor.py` | create | Purpose-bound HMAC cursor codec. |
| `src/api/routes/formal_rule.py` | create | Six GET routes. |
| `src/api/dependencies.py` | modify | Reader dependency. |
| `src/api/app.py` | modify | Attach reader/codec; import router. |
| `tests/unit/test_formal_rule_api.py` | create | Auth, routes, cursors, errors. |
| `tests/unit/test_formal_rule_cursor.py` | create | Reuse, mismatch, expiry. |
| `clients/research-ui/src/api/formalRules.ts` | create | Typed read-only client. |
| `clients/research-ui/src/views/FormalRulesPanel.svelte` | create | Read-only panel. |
| `clients/research-ui/src/views/FormalRulesPanel.test.ts` | create | Panel tests. |
| `clients/research-ui/src/views/RunOverview.svelte` | modify | Import and render the panel. |
| `docs/research-ui.md` | modify | Panel inventory (Task 22 owns final wording). |

## Task 17: Add six GET routes, schemas, settings, and app wiring

### Intent

Provide a complete read surface for summaries, candidates, candidate detail,
rules, versions, and lineage without importing analysis, experiments, or the
producer.

### Implementation Steps

1. Create `src/api/formal_rule_schemas.py` with Pydantic models:
   - `FormalRuleCoverageOut(observed, expected, partial)`
   - `FormalRuleSummaryOut(run_id, publication_id, schema_version, generated_tick,
     candidate_count, rule_count, version_count, window_count, coverage,
     provenance_code, snapshot_digest)`
   - `FormalRuleCandidateOut(candidate_id, status, scope_kind, stage,
     action_token, constraint_kinds, authority_kinds, system_count, rule_count,
     version_count, competing_candidate_ids, first_tick, last_tick)`
   - `FormalRuleCandidateDetailOut(candidate, coverage)`
   - `FormalRuleWrittenRepresentationOut(status, artifact_present,
     artifact_revision, repository_present)`
   - `FormalRuleOut(rule_id, candidate_id, stage, constraint_kind, scope_kind,
     action_token, authority_kind, recognition, written_representation,
     sanction_kinds, exception_count, version_count, latest_version,
     proponent_count, response_counts)`
   - `FormalRuleVersionOut(version_id, rule_id, version_number, stage,
     constraint_kind, scope_kind, scope_digest, action_token, authority_kind,
     recognition, written_representation, sanction_kinds, exception_count, tick,
     revision_kind, supersedes_version_id)`
   - `FormalRuleLineageEdgeOut(edge_id, source_candidate_id,
     target_candidate_id, kind, tick, jaccard, containment)`
   - Page envelopes with `items`, `next_cursor`, `truncated`.
2. Create `src/api/formal_rule_cursor.py`:
   - `FORMAL_RULE_CURSOR_TTL_SECONDS = 900`.
   - `FormalRuleCursorCodec` with `from_secret`, `encode`, `decode`, keyed on
     `purpose`, `run_id`, `publication_id`, `snapshot_digest`, `offset`,
     `query_fingerprint`, expiry.
   - Error codes `formal_rule_cursor_invalid` and `formal_rule_cursor_expired`.
3. Create `src/api/routes/formal_rule.py` with:
   - `router = APIRouter(prefix="/v1/simulations", tags=["formal-rules"])`.
   - `_authorize` requiring `ApiCapability.SUBJECTIVE_DEBUG`.
   - `_reader` returning 503 `formal_rule_disabled` when unset.
   - Purpose constants exactly match the six simulation purposes:
     `formal_rule_summary`, `formal_rule_candidates`, `formal_rule_candidate`,
     `formal_rule_rules`, `formal_rule_versions`, `formal_rule_lineage`; map
     each to the corresponding `FormalRuleCursor` purpose by stripping the
     `formal_rule_` prefix.
   - Routes:
     1. `GET /v1/simulations/{run_id}/formal-rules`
     2. `GET /v1/simulations/{run_id}/formal-rules/candidates`
     3. `GET /v1/simulations/{run_id}/formal-rules/candidates/{candidate_id}`
     4. `GET /v1/simulations/{run_id}/formal-rules/candidates/{candidate_id}/rules`
     5. `GET /v1/simulations/{run_id}/formal-rules/candidates/{candidate_id}/versions`
     6. `GET /v1/simulations/{run_id}/formal-rules/lineage`
   - Query params: `limit` (1..`MAX_PAGE_ROWS`), `cursor`, `status`, `stage`,
     `kind`, `rule_id`.
   - Decode the cursor, verify run/publication/digest/fingerprint, map expiry to
     410 and mismatch to 400, charge response bytes, and return
     `next_cursor` only when `next_offset` is not `None`.
   - Map `formal_rule_unknown` to 404.
4. `src/api/dependencies.py`: add `get_formal_rule_reader` returning the app
   state reader or `None`.
5. `src/api/app.py`:
   - add `_attach_formal_rule_reader(app)` mirroring `_attach_organization_reader`;
   - require both `settings.formal_rule_root` and
     `settings.formal_rule_cursor_key`; set both state attributes to `None`
     otherwise, and never leave a reader/codec from a previous app state;
   - call it during lifespan startup next to the organization attach;
   - include the router in the app.
6. Do not read analysis, experiments, persistence internals, or the producer.
   The route reads only the port.
7. Add `tests/unit/test_formal_rule_api.py`:
   - `test_six_get_only_routes_exist`
   - `test_formal_rule_router_is_registered_exactly_once`
   - `test_every_route_requires_subjective_debug`
   - `test_unset_root_returns_503_formal_rule_disabled`
   - `test_unset_secret_clears_reader_and_cursor_codec`
   - `test_app_state_has_no_stale_reader_after_unset_settings`
   - `test_summary_and_candidate_pages_are_bounded`
   - `test_candidate_rules_versions_and_lineage_filters`
   - `test_unknown_candidate_returns_404`
   - `test_response_bytes_are_charged`
   - `test_api_does_not_import_analysis_or_experiments`
8. Add `tests/unit/test_formal_rule_cursor.py`:
   - `test_cursor_round_trips_same_filter_run_publication_digest`
   - `test_changed_filter_run_publication_or_digest_is_invalid`
   - `test_expired_cursor_is_reported`
   - `test_purpose_is_bound`
   - `test_tampered_or_malformed_cursor_is_invalid`

### Required Interfaces and Contracts

- Six GET routes, no write verb, no `/v2`.
- All require `SUBJECTIVE_DEBUG`.
- Unset root/secret → 503 `formal_rule_disabled`.
- Cursor binds all six fields; expiry 410; mismatch 400.
- Page size ≤ `MAX_PAGE_ROWS`, response ≤ `MAX_RESPONSE_BYTES`.
- Response fields are copied from the snapshot; no server-side derivation of
  law, guilt, or objective compliance.

### Requirement Evidence

- `docs/research-api.md` line 30 (organization route precedent).
- `api/routes/organization.py` 39-130, 168-485.
- `api/organization_cursor.py` 24-130.
- `api/app.py` 260-279.

### Error Handling and Logging

- `formal_rule_disabled` 503.
- `formal_rule_cursor_invalid` 400; `formal_rule_cursor_expired` 410.
- `formal_rule_unknown` 404.
- `formal_rule_page_limit` / `formal_rule_size_limit` 400.
- INFO: `formal_rule_read route=%s run_id=%s rows=%s` (safe ids/counts).
- Never log cursor tokens, digests, candidate ids, scope anchors, or rule
  bodies.

### Tests

- `uv run pytest tests/unit/test_formal_rule_api.py tests/unit/test_formal_rule_cursor.py -q`
- `uv run pytest tests/unit/test_organization_api.py tests/unit/test_organization_cursor.py -q`
  (adjust to actual names; keep organization routes green)

### Acceptance Criteria

- Six routes exist and are GET-only.
- Auth, disabled state, cursor binding, and error mapping are exact.
- Organization routes and schemas are unchanged.

### Verification

- `uv run pytest tests/unit/test_formal_rule_api.py tests/unit/test_formal_rule_cursor.py -q`
- `uv run mypy src/api/formal_rule_*.py src/api/routes/formal_rule.py`

## Task 18: Add the read-only Research UI formal-rules view

### Intent

Let a researcher inspect the published summary, competing systems, rule stages,
versions, and declared responses without the client inventing facts.

### Implementation Steps

1. Create `clients/research-ui/src/api/formalRules.ts`:
   - types mirroring Task 17;
   - `getFormalRuleSummary(runId)`
   - `getFormalRuleCandidates(runId, {status?, limit?, cursor?})`
   - `getFormalRuleCandidate(runId, candidateId)`
   - `getFormalRuleRules(runId, candidateId, {stage?, limit?, cursor?})`
   - `getFormalRuleVersions(runId, candidateId, {ruleId?, limit?, cursor?})`
   - `getFormalRuleLineage(runId, {kind?, limit?, cursor?})`
   - all via `apiFetch`; no client-side derivation or caching.
2. Create `clients/research-ui/src/views/FormalRulesPanel.svelte`:
   - props `{ runId, selection }`;
   - statuses `loading | available | empty | unavailable | error`;
   - load summary, candidates, lineage; on candidate selection load detail,
     rules, and versions;
   - render server fields only:
     - summary counts and coverage;
     - candidate status/stage/constraint/authority/competing ids;
     - rule stage, constraint, authority, recognition, written representation
       status, sanction kinds, exceptions, version count;
     - versions with revision kind and supersedes;
     - lineage edges;
     - declared response counts with a visible note: "Declared responses, not
       objective compliance."
   - `formal_rule_disabled` → `unavailable`; other errors → `error` with code.
   - no local rule inference, no "guilty/violated" label, no sanction action.
3. `clients/research-ui/src/views/RunOverview.svelte`: import and render
   `<FormalRulesPanel {runId} {selection} />` next to `OrganizationsPanel`.
4. Create `clients/research-ui/src/views/FormalRulesPanel.test.ts`:
   - renders summary and candidates;
   - renders competing candidates as separate rows;
   - renders stages, versions, written representation, sanctions, and response
     counts;
   - shows `unavailable` for `formal_rule_disabled`;
   - shows `error` for other failures;
   - asserts no derived violation/compliance label is rendered;
   - asserts read-only behavior (no mutation fetch).
5. Do not change the Godot client, observer protocol, or `/version`.

### Required Interfaces and Contracts

- The panel consumes the six routes only.
- Every displayed value comes from a server field.
- The response section is explicitly labeled as declared responses.
- No client-side calculation of stage progression, authority, or compliance.
- No write action, credential prompt, or capture channel.

### Requirement Evidence

- `clients/research-ui/src/api/organizations.ts` types/fetchers.
- `clients/research-ui/src/views/OrganizationsPanel.svelte` load/status pattern.
- `clients/research-ui/src/views/OrganizationsPanel.test.ts` render pattern.
- `clients/research-ui/src/views/RunOverview.svelte` 40, 313.

### Error Handling and Logging

- UI shows safe codes only; never raw response bodies or tokens.
- No console logging of payloads.
- `formal_rule_disabled` is a normal unavailable state, not an error.

### Tests

- `cd clients/research-ui && npm run test -- --run src/views/FormalRulesPanel.test.ts`
- `cd clients/research-ui && npx svelte-check --tsconfig ./tsconfig.json`
- `cd clients/research-ui && npx tsc --noEmit`

### Acceptance Criteria

- The panel is read-only and server-faithful.
- Competing systems render separately.
- Declared responses are not labeled as objective compliance.
- Existing panels and tests remain green.

### Verification

- `cd clients/research-ui && npm run test -- --run`
- `cd clients/research-ui && npm run build`

Expected: all tests pass; build succeeds; no TypeScript errors.

## Phase Risks and Mitigations

- Risk: the API imports analysis or experiments to build responses.
  Mitigation: routes depend only on `FormalRuleReadPort`; add an import-boundary
  test.
- Risk: cursor omits the digest or candidate id.
  Mitigation: one-field-at-a-time mutation tests and a shared fingerprint
  builder.
- Risk: the UI derives "violation" from response counts.
  Mitigation: fixed labels plus a test asserting no derived compliance label.
- Risk: adding six routes breaks organization route-count assertions.
  Mitigation: count routes per prefix, not globally, and update the aggregate
  read-surface pin intentionally.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
- Six GET formal-rule routes and six GET organization routes coexist.
- No Godot, observer protocol, or `/version` change.
