# Phase 6: Read-Only API and Research UI

Plan: [index.md](index.md)
Tasks: 18-19
Depends on: Phase 5 / Task 17

## Objective

Serve the committed evidence snapshot through six GET-only `/v1` routes under
`SUBJECTIVE_DEBUG`, with explicit disabled, cursor, and size-limit behavior, and
consume those routes in a read-only Research UI view that never derives truth.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/api/routes/dispute.py` | router prefix 50; cursor purposes 53-58; `_authorize` 97-100; `_read` 103-114; `_charge` 143-145; six routes 372-647 | Exact route, auth, cursor, and error pattern |
| `src/api/dispute_schemas.py` | coverage/summary/candidate/detail/page models 8-231; `MAX_PAGE_LIMIT` 233 | Schema precedent |
| `src/api/dispute_cursor.py` | TTL 26; HMAC cursor 47-135 | Cursor codec precedent |
| `src/api/app.py` | reader attach 301-321; attach call 387; router include 415 | Composition wiring |
| `src/api/dependencies.py` | `get_dispute_reader` 160-162 | Dependency injection |
| `src/infrastructure/settings.py` | dispute root/key 224-225; validators 276, 330-336; health 614-615 | Settings shape and env mapping |
| `clients/research-ui/src/api/disputes.ts` | capability 5; types 7-168; base path 172-174; fetchers 176-230 | Client API pattern |
| `clients/research-ui/src/views/DisputesPanel.svelte` | states 26-28; load 42-68; select 70-84; render 92-417 | Panel pattern |
| `clients/research-ui/src/views/RunOverview.svelte` | tab 96-107; render 320-321 | Tab wiring |
| `clients/research-ui/src/views/DisputesPanel.test.ts` | 1-371 | Test pattern |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/api/routes/evidence_testimony.py` | create | Six GET routes |
| `src/api/evidence_testimony_schemas.py` | create | Strict response models |
| `src/api/evidence_testimony_cursor.py` | create | HMAC purpose-bound cursors |
| `src/api/dependencies.py` | modify | `get_evidence_testimony_reader` |
| `src/api/routes/__init__.py` | modify | Router import and `__all__` entry |
| `src/api/app.py` | modify | Attach reader and include router |
| `src/infrastructure/settings.py` | modify | Root/key fields, validators, health |
| `clients/research-ui/src/api/evidence.ts` | create | Read-only client |
| `clients/research-ui/src/views/EvidencePanel.svelte` | create | Read-only panel |
| `clients/research-ui/src/views/RunOverview.svelte` | modify | Evidence tab |
| `clients/research-ui/src/views/EvidencePanel.test.ts` | create | Panel states |
| `tests/unit/test_evidence_testimony_api.py` | create | Routes, auth, errors, cursors |
| `tests/unit/test_evidence_testimony_settings.py` | create | Optional settings validation |

## Task 18: Add six GET routes, schemas, settings, and app wiring

### Intent

Expose the committed snapshot read-only. The API imports no analysis and builds
no snapshot; it only authorizes, reads, pages, and maps safe errors.

### Implementation Steps

1. Create `src/api/routes/evidence_testimony.py` (router prefix
   `/v1/simulations`, tag `evidence`) with exactly:
   1. `GET /{run_id}/evidence` → `EvidenceTestimonySummaryOut`
   2. `GET /{run_id}/evidence/candidates` → `EvidenceCandidatePageOut`
   3. `GET /{run_id}/evidence/candidates/{candidate_id}` →
      `EvidenceCandidateDetailOut`
   4. `GET /{run_id}/evidence/candidates/{candidate_id}/sources` →
      `EvidenceSourcePageOut`
   5. `GET /{run_id}/evidence/candidates/{candidate_id}/contradictions` →
      `EvidenceContradictionPageOut`
   6. `GET /{run_id}/evidence/lineage` → `EvidenceLineagePageOut`
2. Require `ApiCapability.SUBJECTIVE_DEBUG` on every route.
3. Cursor purposes exactly `summary`, `candidates`, `candidate`, `sources`,
   `contradictions`, `lineage`; compute a query fingerprint per route.
4. Error mapping:
   - reader unset or disabled → 503 `evidence_testimony_disabled`;
   - `evidence_testimony_not_found` → 404;
   - `evidence_testimony_size_limit` and invalid filters →
     400 `evidence_testimony_size_limit`/`evidence_testimony_cursor_invalid`;
   - expired cursor → 410 `evidence_testimony_cursor_expired`;
   - artifact decode errors → 404 `evidence_testimony_not_found`.
5. Enforce a 2 MiB response charge per request.
6. Create `src/api/evidence_testimony_schemas.py` with strict Pydantic models
   (`extra="forbid"`), including coverage, summary, candidate, source,
   testimony, item, custody, contradiction, evaluation, detail, edge, and page
   envelopes. `MAX_PAGE_LIMIT = 500`.
7. Create `src/api/evidence_testimony_cursor.py` with
   `EVIDENCE_TESTIMONY_CURSOR_TTL_SECONDS = 900`, HMAC-SHA256 signing, a
   ≥32-byte key, and errors `evidence_testimony_cursor_invalid` /
   `evidence_testimony_cursor_expired`. The payload binds purpose, run,
   publication, digest, offset, fingerprint, and expiry.
8. `src/infrastructure/settings.py`: add `evidence_root: Path | None = None`
   and `evidence_cursor_key: SecretStr | None = None`; reject empty root; require
   ≥32 bytes for the key when set; add health fields. Env names are
   `PALIMPSEST_EVIDENCE_ROOT` and `PALIMPSEST_EVIDENCE_CURSOR_KEY`.
9. `src/api/app.py`: add `_attach_evidence_testimony_reader` (requires both
   settings), attach it, and include the router. `src/api/dependencies.py`:
   add the reader dependency.
10. `src/api/routes/__init__.py`: import `router as evidence_testimony_router`
    and add it to `__all__` beside `dispute_router`, `formal_rule_router`, and
    `organization_router`.
11. Do not import `analysis`, `experiments`, or domain ledgers in the route,
    schemas, settings, app wiring, or route package facade.

### Required Interfaces and Contracts

- Exactly six GET routes exist; no POST/PUT/PATCH/DELETE.
- Response models reject unknown fields and never expose owner ids or tokens.
- `evidence_testimony_disabled` is explicit; an empty store is 404, not a
  fabricated summary.
- Cursors cannot be reused across runs, publications, digests, purposes, or
  filters.

### Requirement Evidence

- `docs/research-api.md` capability and cursor rules.
- `src/api/routes/dispute.py` 50-647; `src/api/dispute_cursor.py` 26-135;
  `src/infrastructure/settings.py` 224-225, 276, 330-336.

### Error Handling and Logging

- Errors return only stable codes and never echo cursor or filter content.
- INFO `evidence_testimony_read route=%s status=%s` (route name only).
- WARN `evidence_testimony_disabled` once per request at most.
- Never log run ids, cursor values, tokens, or digests.

### Tests

- Create `tests/unit/test_evidence_testimony_api.py`:
  - exactly six routes and all are GET;
  - every route requires `SUBJECTIVE_DEBUG`;
  - unset reader → 503 `evidence_testimony_disabled`;
  - summary/candidates/detail/sources/contradictions/lineage return bounded
    pages;
  - cursor round-trip succeeds on every paged route;
  - changed run/filter/publication/digest → 400;
  - expired cursor → 410;
  - a >2 MiB response is refused;
  - no route constructs or imports analysis.
- Create `tests/unit/test_evidence_testimony_settings.py`:
  - both settings default to unset;
  - an empty root is rejected;
  - a short cursor key is rejected;
  - health reports presence only.
- Command: `uv run pytest tests/unit/test_evidence_testimony_api.py tests/unit/test_evidence_testimony_settings.py -q`.

### Acceptance Criteria

- The API surface is read-only, authorized, bounded, and disabled by default.
- Cursor behavior matches the other V4 contexts.

### Verification

- `uv run pytest tests/unit/test_evidence_testimony_api.py tests/unit/test_evidence_testimony_settings.py -q`
- Expected: pass.

## Task 19: Add the read-only Research UI evidence view

### Intent

Let researchers inspect candidates, sources, contradictions, custody status, and
alignment counts without the client deriving truth, authenticity, or a winning
account.

### Implementation Steps

1. Create `clients/research-ui/src/api/evidence.ts`:
   - `CAPABILITY = 'subjective_debug'`.
   - Response types mirroring the six API envelopes; optional fields stay
     optional and are rendered as "unknown".
   - Base path `/v1/simulations/{runId}/evidence`.
   - Fetchers `getEvidenceSummary`, `getEvidenceCandidates`,
     `getEvidenceCandidate`, `getEvidenceSources`, `getEvidenceContradictions`,
     `getEvidenceLineage`; page size 200.
2. Create `clients/research-ui/src/views/EvidencePanel.svelte`:
   - states loading/available/empty/unavailable/error;
   - `load()` fetches summary + candidates + lineage;
   - `selectCandidate()` fetches detail + sources + contradictions in parallel;
   - maps `evidence_testimony_disabled` to unavailable;
   - renders summary counts, candidates, and detail sections for sources,
     testimony, items, custody status, contradictions, evaluations, and lineage;
   - labels alignment as "researcher-only" and never renders a truth/guilt/
     authenticity field (none exist);
   - no client-side inference of a correct source.
3. `clients/research-ui/src/views/RunOverview.svelte`: add tab id `evidence`,
   label `Evidence`, under the Institutions group, and render the panel.
4. Create `clients/research-ui/src/views/EvidencePanel.test.ts` covering
   available, empty, disabled, error, and selection states with the six
   endpoints stubbed.

### Required Interfaces and Contracts

- The client reads only, derives nothing, and sends no control requests.
- Missing or null fields render explicitly, never as a default truth value.
- The panel does not compute a composite evidence-quality score.

### Requirement Evidence

- Original Request research tooling.
- `.ai-factory/ARCHITECTURE.md` "Research capabilities separate control,
  objective inspection, agent-visible projection, and default-disabled
  subjective debug."
- `clients/research-ui/src/views/DisputesPanel.svelte` 26-417.

### Error Handling and Logging

- UI shows the server error code; no console logging of payloads.
- Unavailable state names the missing capability, not a stack trace.

### Tests

- `./node_modules/.bin/vitest run src/views/EvidencePanel.test.ts`
- `./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json`
- Expected: tests pass, 0 errors/0 warnings.

### Acceptance Criteria

- Researchers can inspect every published evidence surface.
- Claims of truth, authenticity, guilt, liability, or a winning account are
  impossible from the rendered data.

### Verification

- `cd clients/research-ui && ./node_modules/.bin/vitest run src/views/EvidencePanel.test.ts`
- `cd clients/research-ui && ./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json`
- `cd clients/research-ui && ./node_modules/.bin/tsc -p tsconfig.node.json`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: route overlap with dispute paths.
  Mitigation: distinct `/evidence` and `/evidence/candidates/...` paths; Task 20
  asserts the full route set.
- Risk: client invents a truth view.
  Mitigation: no such field exists server-side; the panel renders only server
  fields and a test asserts labels.
- Risk: cursor key/root misconfiguration exposes data.
  Mitigation: both settings required to attach; explicit disabled state.

## Phase Completion Checklist

- Every Task 18-19 in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
