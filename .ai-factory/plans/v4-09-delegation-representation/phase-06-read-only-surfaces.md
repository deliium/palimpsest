# Phase 6: Read-Only API and Research UI

Plan: [index.md](index.md)
Tasks: 18-19
Depends on: Phase 5 / Task 17

## Objective

Serve six GET-only `/v1` representation routes under `SUBJECTIVE_DEBUG` with a
disabled state, digest-bound cursors, bounded payloads, and a Research UI panel
that renders representation as beliefs without deriving legitimacy.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/api/routes/evidence_testimony.py` | router 43; authorize 67-70; disabled 54-64; six routes 218-451 | Route template |
| `src/api/evidence_testimony_cursor.py` | codec 26; TTL; encode 82; decode 104 | Cursor template |
| `src/api/routes/evidence_testimony.py` | cursor decode 86-109; size charge 133-138 | Error mapping |
| `src/api/evidence_testimony_schemas.py` | page limit 21; schemas 28-128 | Schema template |
| `src/infrastructure/settings.py` | evidence settings 226-227; key validator 334-339; health flags 618-619 | Settings template |
| `src/api/app.py` | reader attach 323-348; call 415; router 444 | App wiring |
| `src/api/dependencies.py` | accessor 165 | Dependency accessor |
| `clients/research-ui/src/api/evidence.ts` | client functions 90-136 | UI client template |
| `clients/research-ui/src/views/EvidencePanel.svelte` | load 42; disabled 59-63; detail 70; states 102-171 | Panel template |
| `clients/research-ui/src/views/RunOverview.svelte` | tab 106; render 324-325 | Tab wiring |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/api/routes/delegation_representation.py` | create | Six GET routes |
| `src/api/routes/__init__.py` | modify | Router import and `__all__` entry |
| `src/api/delegation_representation_cursor.py` | create | Purpose-bound HMAC cursor |
| `src/api/delegation_representation_schemas.py` | create | Strict response models |
| `src/api/app.py` | modify | Attach reader and include router |
| `src/api/dependencies.py` | modify | Reader accessor |
| `src/infrastructure/settings.py` | modify | Root + cursor key settings and health flags |
| `src/api/__init__.py` | modify | Exports |
| `clients/research-ui/src/api/representation.ts` | create | Six client functions |
| `clients/research-ui/src/views/RepresentationPanel.svelte` | create | Read-only panel |
| `clients/research-ui/src/views/RepresentationPanel.test.ts` | create | Component tests |
| `clients/research-ui/src/views/RunOverview.svelte` | modify | Tab and render |
| `tests/unit/test_delegation_representation_api.py` | create | Route/auth/cursor |
| `tests/unit/test_delegation_representation_settings.py` | create | Settings validation |

## Task 18: Add six GET routes, schemas, settings, and app wiring

### Intent

The API is a read-only view of the committed store. It must fail closed when
unconfigured and must never import analysis or the producer.

### Implementation Steps

1. Add settings to `src/infrastructure/settings.py`:
   `representation_root: Path | None = None` and
   `representation_cursor_key: SecretStr | None = None`, reading
   `PALIMPSEST_REPRESENTATION_ROOT` and
   `PALIMPSEST_REPRESENTATION_CURSOR_KEY`; validate the key at ≥32 bytes; add
   boolean health flags `representation_enabled` and
   `representation_cursor_enabled`.
2. Create `src/api/delegation_representation_cursor.py`: `PurposeBoundCursor`
   with TTL 900 seconds, `encode(cursor)`, `decode(token, *, purpose, run_id,
   publication_id, digest, fingerprint)`, HMAC-SHA256 with the secret, constant
   error codes.
3. Create `src/api/delegation_representation_schemas.py` with strict
   `ConfigDict(extra="forbid")` models: `RepresentationSummaryResponse`,
   `RepresentationMandatesResponse`, `RepresentationMandateResponse`,
   `RepresentationPositionsResponse`, `RepresentationRevocationsResponse`,
   `RepresentationLineageResponse`; `MAX_PAGE_LIMIT = 500`. Response fields are
   `owner_token`, `principal_token`, `representative_token`, and `actor_token`
   only; no raw agent id, principal ref, or free-text scope subject is exposed.
4. Create `src/api/routes/delegation_representation.py` with
   `APIRouter(prefix="/v1/simulations", tags=["representation"])` and the six
   routes listed under Required Interfaces.
5. Authorize every route with
   `require_http_capability(..., capability=ApiCapability.SUBJECTIVE_DEBUG)`.
6. When the reader or cursor codec is missing, return
   `503 {"detail": "representation_disabled"}`.
7. Decode cursors per route; on a binding mismatch return
   `400 {"detail": "representation_cursor_invalid"}`; on expiry return
   `410 {"detail": "representation_cursor_expired"}`; on a response over 2 MiB
   return `400 {"detail": "representation_size_limit"}`.
8. In `src/api/app.py`, add `_attach_delegation_representation_reader(app,
   settings)` and call it beside the evidence reader; include the router beside
   the evidence router.
9. In `src/api/routes/__init__.py`, import
   `delegation_representation_router` and add it to `__all__`, matching the
   evidence router entry.
10. In `src/api/dependencies.py`, add
    `get_delegation_representation_reader(request)`.
11. Ensure `api` imports only `simulation`, `infrastructure`, `persistence`, and
    `observer`; no `analysis`, `experiments`, or `research_runner`.

### Required Interfaces and Contracts

```text
GET /v1/simulations/{run_id}/representation
GET /v1/simulations/{run_id}/representation/mandates
GET /v1/simulations/{run_id}/representation/mandates/{mandate_id}
GET /v1/simulations/{run_id}/representation/mandates/{mandate_id}/positions
GET /v1/simulations/{run_id}/representation/mandates/{mandate_id}/revocations
GET /v1/simulations/{run_id}/representation/lineage
```

- Exactly six routes; no POST/PUT/PATCH/DELETE.
- The mandate list accepts an optional `candidate_id` query filter, which is
  bound into the cursor fingerprint.
- Cursor purpose per route: `summary`, `mandates`, `mandate`, `positions`,
  `revocations`, `lineage`.
- The summary response exposes counts and coverage; mandate detail exposes
  principal kind, scope kind, duration kind, status, and recognition basis, but
  not a boolean `authorized`/`legitimate`.

### Error Handling and Logging

- `INFO representation_api_read route=%s` at DEBUG for repeat reads and INFO for
  first read per request; never log run ids, mandate ids, or filters.
- WARN `representation_cursor_rejected` with a reason code only.
- No stack traces containing domain values.

### Tests

- `tests/unit/test_delegation_representation_api.py`: six routes and methods;
  SUBJECTIVE_DEBUG required; disabled state when unset; each cursor error;
  payload cap; schema forbids extra fields; no ninth route; no write method; the
  router is exported from `api.routes`; no response contains a raw
  representative or principal agent id.
- `tests/unit/test_delegation_representation_settings.py`: env parsing, key
  length, unset state, health flags.

### Acceptance Criteria

- Six GET-only routes with the exact paths and cursor purposes.
- Unconfigured state is an explicit 503, never an empty success.
- The API imports no analysis or producer module.

### Verification

- `uv run pytest tests/unit/test_delegation_representation_api.py tests/unit/test_delegation_representation_settings.py -q`
- Expected: pass; `uv run pytest tests/unit/test_evidence_testimony_api.py -q` stays green.

## Task 19: Add the read-only Research UI representation view

### Intent

Researchers need to see who claims, supports, rejects, revokes, and contests
representation without the UI implying that a representative is legitimate.

### Implementation Steps

1. Create `clients/research-ui/src/api/representation.ts` with capability
   `subjective_debug`, base `/v1/simulations/{runId}/representation`, and six
   functions mirroring the evidence client (90-136).
2. Create `clients/research-ui/src/views/RepresentationPanel.svelte` with:
   - run summary load on mount;
   - states: `loading`, `disabled` (mapping `representation_disabled` to
     `unavailable`), `error`, `empty`, `ready`;
   - a candidate/mandate list with principal kind, scope kind, duration, status,
     recognition basis, support/opposition counts, and revocation count;
   - a detail view that loads positions and revocations on selection;
   - explicit epistemic labels: "owner belief", "not legitimacy", "contested",
     "revoked" without deriving a winner.
3. Add the tab `{ id: 'representation', label: 'Representation' }` and render
   `<RepresentationPanel {runId} {selection} />` in `RunOverview.svelte`.
4. Keep the panel read-only: no mutation, no publication trigger, no derived
   `authorized`/`legitimate`/`winner` field.
5. Create `RepresentationPanel.test.ts` covering disabled, empty, ready,
   contested, and revoked rendering plus the "not legitimacy" label.

### Required Interfaces and Contracts

- All displayed values come from server fields; the client computes no
  recognition, truth, or legitimacy.
- Status colors/labels are presentation only and never assert correctness.

### Error Handling and Logging

- UI logs no principal, representative, or scope subject to the console.
- Errors render a safe message from the server code.

### Tests

- `pnpm --dir clients/research-ui test -- RepresentationPanel`
- `pnpm --dir clients/research-ui run check`
- Expected: component tests pass; svelte-check reports 0 errors.

### Acceptance Criteria

- The panel covers all six routes it needs and never derives legitimacy.
- Disabled and empty states are explicit.

### Verification

- `pnpm --dir clients/research-ui run test`
- Expected: all tests pass, including the new panel suite.

## Phase Risks and Mitigations

- Risk: the UI badge "recognized" is read as "legitimate".
  Mitigation: explicit "owner belief — not legitimacy" chrome and a test that
  asserts the label.
- Risk: the API leaks owner ids through detail responses.
  Mitigation: schemas expose tokens only; no actor/representative ids.
- Risk: a cursor is reused across purposes.
  Mitigation: purpose-bound HMAC plus per-route purpose tests.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
