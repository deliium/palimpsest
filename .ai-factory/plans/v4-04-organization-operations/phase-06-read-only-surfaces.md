# Phase 6: Read-Only API and Research UI

Plan: [index.md](index.md)
Tasks: 17-18
Depends on: Phase 5 / Tasks 15-16

## Objective

Expose the operational provenance and disagreement through the existing
`SUBJECTIVE_DEBUG`-gated, GET-only organization surface, and render it read-only
in the Research UI. The four V4-03 routes keep their paths; a fifth operation
route and additive fields are the only API change.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/api/routes/organization.py` | purposes 41-63; helpers 65-135; summary 138-168; candidates 171-239; candidate 241-291; lineage 294-366 | Add one route and additive detail fields using the same auth/cursor/charge helpers. |
| `src/api/organization_schemas.py` | strict models 8-111 | Add operation strict models and counts. |
| `src/api/organization_cursor.py` | codec/purpose binding | No codec change is expected; the purpose comes from the ports constant. |
| `src/api/dependencies.py` | `get_organization_reader` 147-149 | Reader resolution is unchanged. |
| `src/infrastructure/settings.py` | organization root/cursor key 220-221, 302-309, 584-585 | No new setting. |
| `clients/research-ui/src/api/organizations.ts` | types 5-90; functions 98-134 | Add operation types and one read function. |
| `clients/research-ui/src/views/OrganizationsPanel.svelte` | load 32-52; select 54-56; summary/table/detail/lineage 88-166 | Add an operations section without client-side derivation. |
| `clients/research-ui/src/views/OrganizationsPanel.test.ts` | fixtures/mocks | Extend for the new route and renders. |
| `tests/unit/test_organization_api.py` | 80-100 and route cases | Existing four-route behavior must remain. |
| `tests/architecture/test_organization_boundaries.py` | 287-304 | Route must remain GET-only and the client write-free. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/api/organization_schemas.py` | modify | Operation out/list models; summary/candidate counts; detail operations. |
| `src/api/routes/organization.py` | modify | Fifth GET route; additive candidate detail operations; purpose constant. |
| `src/api/routes/__init__.py` | modify only if exports change | Router export unchanged. |
| `clients/research-ui/src/api/organizations.ts` | modify | Operation types and `getOrganizationOperations`. |
| `clients/research-ui/src/views/OrganizationsPanel.svelte` | modify | Operations summary/filter/table/detail and disagreement badges. |
| `clients/research-ui/src/views/OrganizationsPanel.test.ts` | modify | Mock/assert the new route and rendering. |
| `tests/unit/test_organization_operations_api.py` | create | Fifth route, auth, disabled, cursors, filters, read-only. |

## Task 17: Add the fifth GET route and additive response fields

### Intent

Make provenance inspectable without creating a write channel or a client-side
derivation layer. The route is additive and remains under `/v1`.

### Implementation Steps

1. In `organization_schemas.py`:
   - add `OrganizationOperationOut` with exactly the published fields:
     `operation_id`, `domain`, `act`, `stance`, `authority_basis`,
     `provenance_code`, `outcome`, `command_kind`, `target_kind`, `anchor_kind`,
     `anchor_id`, `tick`, `first_tick`, `last_tick`, `support_count`,
     `contest_count`, `resolved`;
   - add `OrganizationOperationListOut` with `publication_id`, `items`,
     `next_cursor`, `truncated`;
   - add `operation_count` and `contested_operation_count` to
     `OrganizationSummaryOut`/`OrganizationCandidateOut`;
   - add `operations: tuple[OrganizationOperationOut, ...]` to
     `OrganizationCandidateDetailOut`.
2. In `routes/organization.py`:
   - add `_PURPOSE_OPERATIONS = "organization_operations"`;
   - implement
     `GET /{run_id}/organizations/operations` with `domain:
     Literal["resource_control","storage","record_keeping",
     "membership_admission","membership_departure","role_assignment",
     "procedure_action","internal_commitment"] | None`, `organization_id:
     str | None`, `limit: int = 100`, `cursor: str | None`, `publication: str =
     ""`;
   - require `SUBJECTIVE_DEBUG`, set `Cache-Control: no-store`, resolve the
     reader (503 `organization_disabled`), resolve the summary (404
     `organization_publication_missing`);
   - compute the fingerprint with
     `{"domain": domain, "organization_id": organization_id}`;
   - decode/validate the cursor with the operations purpose;
   - call `reader.operations(run_id, publication_id, offset, min(limit,
     MAX_PAGE_ROWS), domain, organization_id)`;
   - map rows to `OrganizationOperationOut`, build the next cursor, charge the
     response, and return.
3. In the summary route, pass `operation_count`; in `_candidate_out`, pass
   `operation_count`/`contested_operation_count`; in the detail route, map
   `candidate.operations` to `OrganizationOperationOut`.
4. Keep the four existing routes byte-compatible except for the additive count
   fields.
5. Do not add POST/PUT/PATCH/DELETE, query-string credentials, a `/v2` route, or
   a new capability.
6. Log DEBUG `organization_api_request route=operations run_id=%s domain=%s`
   and never log ids, anchors, or payloads.

### Required Interfaces and Contracts

- The fifth route is GET-only and requires the same `SUBJECTIVE_DEBUG`
  capability as the existing four.
- `PALIMPSEST_ORGANIZATION_ROOT` unset → 503 `organization_disabled`; no
  publication → 404 `organization_publication_missing`.
- Invalid/expired cursors → 400 `organization_cursor_invalid` / 410
  `organization_cursor_expired`.
- Filters are exact; a cursor with changed filters/run/publication is rejected.
- Response size is bounded by `MAX_RESPONSE_BYTES`.
- The route never mutates, repairs, or re-derives operations.

### Requirement Evidence

- `docs/research-api.md` organization route contract.
- V4-03 read-only API precedent.
- Original Request: provenance must be recorded and inspectable; no write
  channel.

### Error Handling and Logging

- Use the existing `_reader`, `_authorize`, `_decode_cursor`, and `_charge`
  helpers; do not create parallel error paths.
- Safe codes only; no payload logging.

### Tests

- `tests/unit/test_organization_operations_api.py`:
  - summary includes `operation_count`;
  - candidate detail includes `operations` and contested counts;
  - the operations route pages/filters by domain and organization id;
  - missing capability → 401/403 per existing policy;
  - unset root → 503 `organization_disabled`;
  - missing publication → 404;
  - changed filter with an old cursor → 400; expired cursor → 410;
  - the router contains only GET decorators;
  - no POST/PUT/PATCH/DELETE exists.
- Command:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_api.py tests/unit/test_organization_api.py -q`

### Acceptance Criteria

- Provenance is served through one additive GET route.
- Authorization, disabled state, cursors, and byte caps match V4-03.
- No write channel or new capability exists.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_api.py tests/unit/test_organization_api.py -q`
- Expected: pass.

## Task 18: Add the read-only Research UI operations view

### Intent

Let a researcher see control, storage, record, membership, role, procedure, and
commitment provenance, plus disagreement, without the client computing a new
classification.

### Implementation Steps

1. In `clients/research-ui/src/api/organizations.ts`:
   - add `OrganizationOperation` and `OrganizationOperationPage` types matching
     the API exactly;
   - add `getOrganizationOperations(runId, { domain?, organizationId?, limit?,
     cursor? })` using `apiFetch` with capability `subjective_debug`;
   - add `operation_count`/`contested_operation_count` to summary/candidate types
     and `operations` to the detail type.
2. In `OrganizationsPanel.svelte`:
   - load one operations page (`limit: 200`) alongside summary/candidates/lineage;
   - add a summary tile for operations and contested operations;
   - add a domain filter (`all` plus the eight domains);
   - add a read-only table with operation id, domain, act, stance, authority,
     provenance, tick, anchor kind, support, and contest;
   - show a `contested` badge when `contest_count > 0` or stance is `disputed`;
   - show candidate detail operations beneath the existing members/structure;
   - keep the existing `organization_disabled` → unavailable behavior and the
     explanatory note that candidates are analytical, not typed organizations;
   - do not compute counts, statuses, or provenance in the client.
3. In `OrganizationsPanel.test.ts`, add the operation fixture and assert:
   - the summary tile/table render;
   - the domain filter narrows rows;
   - a contested row shows the badge;
   - the unavailable state still renders when the API returns
     `organization_disabled`.
4. Keep the client read-only: no POST/PUT/PATCH/DELETE strings.

### Required Interfaces and Contracts

- The client renders only server-provided fields; it never infers authority,
  membership, control, or provenance.
- The operations page is bounded to 200 rows; the panel does not paginate
  indefinitely.
- The panel remains one read-only view; no new capability, route, or write.
- Empty operations is a normal state, not an error.
- The panel does not claim that a candidate is a government/church/etc.

### Requirement Evidence

- `docs/research-ui.md` read-only panel contract.
- V4-03 `OrganizationsPanel` precedent.
- Original Request: operations and provenance must be visible to researchers.

### Error Handling and Logging

- `organization_disabled` → unavailable; other API errors → error with the safe
  code.
- No client logging of ids or anchors; no payload logging.

### Tests

- `clients/research-ui/src/views/OrganizationsPanel.test.ts`:
  - renders summary/operation table;
  - domain filter works;
  - contested badge appears;
  - unavailable state works;
  - no write calls.
- Commands:
  - `cd clients/research-ui && node_modules/.bin/vitest run src/views/OrganizationsPanel.test.ts`
  - `cd clients/research-ui && node_modules/.bin/svelte-check --tsconfig ./tsconfig.json`
  - Expected: pass.

### Acceptance Criteria

- The panel displays operations and provenance read-only.
- No client-side derivation or write call exists.
- The disabled state remains explicit.

### Verification

- `cd clients/research-ui && node_modules/.bin/vitest run src/views/OrganizationsPanel.test.ts`
- `cd clients/research-ui && node_modules/.bin/svelte-check --tsconfig ./tsconfig.json`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: a fifth route is treated as a new API version or capability.
  Mitigation: it stays under `/v1` and reuses `SUBJECTIVE_DEBUG`.
- Risk: the client computes authority or disagreement.
  Mitigation: the panel only renders server fields; the test asserts no write and
  no local classification.
- Risk: cursor filters are not bound.
  Mitigation: fingerprint includes domain and organization id; the API test
  reuses a cursor with a changed filter.

## Phase Completion Checklist

- Every Task 17-18 acceptance criterion is met.
- Five GET-only routes exist; all require `SUBJECTIVE_DEBUG`.
- The Research UI renders operations read-only.
- `index.md` task checkboxes are updated immediately after verified completion.
