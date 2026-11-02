# Phase 6: Read-Only API and Research UI

Plan: [index.md](index.md)
Tasks: 17-18
Depends on: Phase 5 / Task 16

## Objective

Add the sixth GET-only organization route for collective agency, additive
summary/candidate fields, and a read-only Research UI section. Repair the
existing cursor digest plumbing so every paged organization route can issue
reusable cursors. No write route, `/v2` route, or new capability is added.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/api/routes/organization.py` | router 43; purposes 45-49; `_decode_cursor` 88-109; `_charge` 112-117; summary 168-199; candidates 202-269; candidate 272-325; lineage 328-400; operations 402-485 | Exact route/cursor pattern; empty `snapshot_digest` at 250, 381, 466 |
| `src/api/organization_schemas.py` | `OrganizationSummaryOut`, `OrganizationCandidateOut`, `OrganizationCandidateDetailOut`, `OrganizationOperationOut`, `OrganizationOperationListOut` | Additive schema pattern |
| `src/api/app.py` | reader/codec attach 259-276; router registration 340, 366 | No new settings; the existing root/cursor key gate remains |
| `src/simulation/organization_ports.py` | summary digest and `collective_agency` method (Task 14) | Route inputs |
| `clients/research-ui/src/api/organizations.ts` | DTOs and `getOrganization*` helpers | Add the sixth DTO/helper |
| `clients/research-ui/src/views/OrganizationsPanel.svelte` | load function 36-58; summary 100-110; filters/tables | Add a collective-agency section |
| `clients/research-ui/src/views/OrganizationsPanel.test.ts` | existing panel tests | Extend |
| `tests/unit/test_organization_operations_api.py` | GET-only and cursor tests 257-269 | Pattern to mirror |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/api/organization_schemas.py` | modify | Summary/candidate fields; collective decision/implementation/list schemas |
| `src/api/routes/organization.py` | modify | Sixth route; summary digest on every paged route; `_decode_cursor` digest check; candidate detail agency records |
| `tests/unit/test_organization_agency_api.py` | create | Route/auth/cursor/response tests |
| `tests/unit/test_organization_operations_api.py` | modify | Five → six routes; cursor reuse for existing paged routes |
| `tests/unit/test_organization_api.py` | modify | Summary/candidate additive fields; GET-only scan |
| `clients/research-ui/src/api/organizations.ts` | modify | DTOs and helper |
| `clients/research-ui/src/views/OrganizationsPanel.svelte` | modify | Load/render collective-agency section |
| `clients/research-ui/src/views/OrganizationsPanel.test.ts` | modify | New section/filter/empty/unavailable tests |
| `tests/unit/test_organization_operations_docs.py` | modify | Route count/docs references in Task 22 |

## Task 17: Add the sixth GET route and additive response fields

### Intent

Expose committed collective-agency records with `SUBJECTIVE_DEBUG`, the existing
disabled state, purpose-bound cursors, and no owner-local ids. Fix cursor reuse
for all paged organization routes.

### Implementation Steps

1. In `src/api/organization_schemas.py`:
   - Add to `OrganizationSummaryOut`: `snapshot_digest: str`,
     `collective_proposal_count: int`, `collective_amendment_count: int`,
     `collective_support_count: int`, `collective_oppose_count: int`,
     `collective_abstain_count: int`, `collective_decision_count: int`,
     `collective_implementation_count: int`,
     `unimplemented_decision_count: int`.
   - Add to `OrganizationCandidateOut`: `collective_proposal_count: int`,
     `collective_amendment_count: int`, `collective_support_count: int`,
     `collective_oppose_count: int`, `collective_abstain_count: int`,
     `collective_decision_count: int`, `collective_implementation_count: int`,
     `unimplemented_decision_count: int`, `contested_decision_count: int`.
   - Add `OrganizationCollectiveImplementationOut` with:
     `implementation_id`, `actor_ref`, `status`, `effect`, `observed_tick`,
     `provenance_code`, `resolved`.
   - Add `OrganizationCollectiveDecisionOut` with:
     `decision_id`, `organization_id`, `proposal_ref`, `revision`,
     `procedure_ref`, `recognition`, `authority_basis`, `support_count`,
     `oppose_count`, `abstain_count`, `contest_count`, `implementation_mode`,
     `effect`, `target_kind`, `target_ref`, `decided_tick`, `window_end_tick`,
     `implementation_status`, `provenance_code`, `resolved`,
     `implementations`.
   - Add `OrganizationCollectiveAgencyListOut` with `publication_id`, `items`,
     `next_cursor`, `truncated`.
   - Add `collective_decisions` to `OrganizationCandidateDetailOut`.
2. In `src/api/routes/organization.py`:
   - Add `_PURPOSE_COLLECTIVE_AGENCY = "organization_collective_agency"`.
   - Change `_decode_cursor` to accept `snapshot_digest: str` and reject a
     cursor whose digest differs, with `organization_cursor_invalid`.
   - Update candidates/lineage/operations to pass
     `summary.snapshot_digest` on both encode and decode. This is the cursor
     fix; do not weaken the TTL, fingerprint, or purpose checks.
   - Add `_collective_decision_out` and `_implementation_out`.
   - Add `@router.get("/{run_id}/organizations/collective-agency")` with:
     `recognition: Literal["recognized","contested","unrecognized","expired","unknown"] | None`,
     `organization_id: str | None`, `limit`, `cursor`, `publication`.
     - `_authorize`, `_codec`, `_reader`, summary lookup, publication default.
     - Fingerprint includes `recognition` and `organization_id`.
     - Call `reader.collective_agency(...)`.
     - Return `OrganizationCollectiveAgencyListOut`.
     - `Cache-Control: no-store`, `_charge`, DEBUG counts only.
   - Add `collective_decisions` to candidate detail from
     `candidate.collective_decisions`, bounded by the model.
   - Add summary fields from `summary`.
3. Keep the four V4-03 paths and the V4-04 operations path unchanged. The new
   path is additive.
4. Do not add a writer, a `POST`, a `/v2` route, or a new capability.
5. Do not add a new setting; `PALIMPSEST_ORGANIZATION_ROOT` and
   `PALIMPSEST_ORGANIZATION_CURSOR_KEY` semantics are unchanged.

### Required Interfaces and Contracts

- Six GET-only routes under `/v1/simulations/{run_id}/organizations...`.
- All require `SUBJECTIVE_DEBUG`.
- Unconfigured root or cursor key → `503 organization_disabled`. Preserve the
  existing `_attach_organization_reader` gate at `src/api/app.py:259-276`; do not
  change it to root-only.
- Missing publication → `404 organization_publication_missing`.
- Unknown candidate → `404 organization_unknown_candidate` (existing detail
  route only).
- Cursor reuse with the same filter/run/publication → `200`; changed
  filter/run/publication/digest → `400 organization_cursor_invalid`; expired →
  `410 organization_cursor_expired`.
- Response bytes are charged against `MAX_RESPONSE_BYTES`; `limit` is capped at
  `MAX_PAGE_ROWS`.
- No owner-local ids, raw actor ids, labels, or utterance content in any
  response.

### Requirement Evidence

- `docs/research-api.md` organization route contract.
- V4-03/V4-04 API route and cursor tests.
- Original Request: proposals, positions, recognized outcomes, compliance,
  refusal, sabotage.
- User decision: fix all paged routes, not only the new route.

### Error Handling and Logging

- Reuse `bad_request`, `gone`, `not_found`, `service_unavailable` with closed
  codes.
- Log DEBUG `organization_api_request route=collective_agency
  recognition=%s candidate=%s rows=%s` (no ids beyond the candidate key? Use
  `candidate=present|all`, not the id).
- Never log cursor tokens, proposal refs, actor refs, or response bodies.

### Tests

Create `tests/unit/test_organization_agency_api.py`:
- The new route is GET-only and requires `SUBJECTIVE_DEBUG`.
- Disabled reader → `503 organization_disabled` with either the root or the
  cursor key missing, proving the existing gate is unchanged.
- Missing publication → `404 organization_publication_missing`.
- Returns decisions with nested implementations, recognition filter, candidate
  filter, limit cap, and response charge.
- Cursor reuse with the same filter → `200`; changed filter/run/publication/
  digest → `400`; expired → `410`.
- The four existing paged routes also reuse a freshly issued cursor successfully.
- Summary and candidate detail include the additive counts and decisions.
- No response contains `orgc-`, `orgp-`, `orgpm-`, `orgcd-`, `orgci-`,
  `orgcev-`, or a raw actor id.
- Route count is six and all are GET.

Update `tests/unit/test_organization_operations_api.py` and
`tests/unit/test_organization_api.py` for six routes and the new summary fields.

Run:
`uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_api.py tests/unit/test_organization_operations_api.py tests/unit/test_organization_api.py -q`

### Acceptance Criteria

- The sixth route is additive and read-only.
- Cursor reuse works on every paged organization route.
- No existing route path, auth rule, or error code changes.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_api.py tests/unit/test_organization_operations_api.py tests/unit/test_organization_api.py -q`
- Expected: all tests pass.

## Task 18: Add the read-only Research UI collective-agency view

### Intent

Render server-provided proposals, positions, decisions, implementation statuses,
refusal, and owner-attributed sabotage in the existing Organizations panel
without local derivation or write actions.

### Implementation Steps

1. In `clients/research-ui/src/api/organizations.ts`:
   - Add DTOs `OrganizationCollectiveImplementation`,
     `OrganizationCollectiveDecision`, and
     `OrganizationCollectiveAgencyPage`.
   - Add `getOrganizationCollectiveAgency(runId, options)` using
     `CAPABILITY = 'subjective_debug'` and the existing `apiFetch` pattern.
   - Add the new counts to `OrganizationSummary`, `OrganizationCandidate`, and
     `OrganizationCandidateDetail`.
2. In `clients/research-ui/src/views/OrganizationsPanel.svelte`:
   - Add `collectiveDecisions` state and `collectiveRecognition` filter.
   - Load `getOrganizationCollectiveAgency(runId, { limit: 200 })` after the
     operations route.
   - Add summary counts for proposals, amendments, support, opposition,
     abstention, decisions, implementations, and unimplemented decisions.
   - Add a section titled "Collective agency" with:
     - recognition filter (`all`, `recognized`, `contested`, `unrecognized`,
       `expired`, `unknown`);
     - a table of decision id, recognition, support/oppose/abstain, procedure,
       implementation status, and decision tick;
     - a bounded nested list of per-actor implementation statuses with
       `actor_ref` and provenance;
     - a caveat that sabotage is an owner attribution, not an objective fact.
   - Render only server fields; no client-side derivation of counts or statuses.
   - Do not add a write control, command button, or proposal editor.
3. Keep the existing candidate/lineage/operations sections and filters.
4. Update `OrganizationsPanel.test.ts`:
   - Renders the section and counts when the route succeeds.
   - Recognition filter narrows the table.
   - Empty state and `organization_disabled` state.
   - Nested implementations render for a decision.
   - Sabotage caveat is present.
   - No write controls are rendered.
5. Run the UI checks.

### Required Interfaces and Contracts

- The panel consumes only the six GET routes.
- It never derives recognition or implementation status from raw evidence.
- It displays `actor_ref`, not a raw agent id.
- It remains read-only: no form, POST, or command control.
- Existing panel behavior and view registration are unchanged.

### Requirement Evidence

- `docs/research-ui.md` read-only panel contract.
- V4-03/V4-04 `OrganizationsPanel.svelte` patterns.
- Original Request: support proposals, supporters, opponents, abstention,
  amendments, recognized outcomes, compliance, refusal, sabotage.

### Error Handling and Logging

- A failed agency fetch sets the panel error state with the safe code; the
  existing sections remain usable if the summary/candidates load.
- No client logging of payloads, actor ids, or proposal refs.

### Tests

Update `clients/research-ui/src/views/OrganizationsPanel.test.ts` and run:
`cd clients/research-ui && pnpm test -- --run`
`cd clients/research-ui && pnpm check`
`cd clients/research-ui && pnpm build`

### Acceptance Criteria

- The panel renders collective decisions and implementation statuses read-only.
- Recognition and implementation values come from the server.
- No write action or client-side truth derivation exists.
- Existing panel tests remain green.

### Verification

- `cd clients/research-ui && pnpm test -- --run`
- `cd clients/research-ui && pnpm check`
- `cd clients/research-ui && pnpm build`
- Expected: all tests pass, 0 type/Svelte errors, build succeeds.

## Phase Risks and Mitigations

- Risk: the new route is added after a catch-all and becomes unreachable.
  Mitigation: it is declared on the existing organization router before any
  optional catch-all; route tests hit the exact path.
- Risk: cursor reuse still fails because a route encodes an empty digest.
  Mitigation: every encode/decode site uses `summary.snapshot_digest`; tests
  reuse a cursor on all paged routes.
- Risk: the UI implies sabotage is objective.
  Mitigation: an explicit owner-attribution caveat and server provenance field.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
