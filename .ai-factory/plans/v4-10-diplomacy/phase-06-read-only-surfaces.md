# Phase 6: Read-Only API and Research UI

Plan: [index.md](index.md)
Tasks: 20-21
Depends on: Phase 5 / Task 19

## Objective

Serve six GET-only `/v1` diplomacy routes behind `SUBJECTIVE_DEBUG` with an
explicit disabled state and purpose-bound cursors, then add a read-only Research
UI panel that renders server fields without deriving authority, legitimacy, or a
winning party.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/api/routes/delegation_representation.py` | router prefix; six handlers; `service_unavailable(code="representation_disabled")` | Route shape and disabled state |
| `src/api/delegation_representation_schemas.py` | summary/mandate/position/revocation/lineage and page models | Strict response-model shape |
| `src/api/delegation_representation_cursor.py` | `DelegationRepresentationCursorCodec`; TTL 900s; invalid/expired codes | Cursor codec shape |
| `src/infrastructure/settings.py` | `representation_root`, `representation_cursor_key`, validators, health flags | Settings shape |
| `src/api/app.py` | `_attach_delegation_representation_reader` 352; `app.state.representation_reader`; router include 477 | Composition wiring |
| `src/api/dependencies.py` | `get_delegation_representation_reader` | DI hook |
| `clients/research-ui/src/api/representation.ts` | typed client and `CAPABILITY` | Client shape |
| `clients/research-ui/src/views/RepresentationPanel.svelte` | loading/available/empty/unavailable/error states | Panel shape |
| `clients/research-ui/src/views/RunOverview.svelte` | panel import/render | Mount point |
| `clients/research-ui/src/research/selection.ts` | selection facet | Navigation facet |
| `docs/research-api.md` | route documentation pattern | Docs task reference |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/api/routes/diplomacy.py` | create | Six GET handlers |
| `src/api/diplomacy_schemas.py` | create | Strict response models |
| `src/api/diplomacy_cursor.py` | create | Purpose-bound HMAC cursor codec |
| `src/infrastructure/settings.py` | modify | Root, cursor key, validators, health flags |
| `src/api/app.py` | modify | Reader/codec wiring and router include |
| `src/api/dependencies.py` | modify | Reader dependency |
| `clients/research-ui/src/api/diplomacy.ts` | create | Typed client |
| `clients/research-ui/src/views/DiplomacyPanel.svelte` | create | Read-only panel |
| `clients/research-ui/src/views/RunOverview.svelte` | modify | Render panel |
| `clients/research-ui/src/research/selection.ts` | modify | `diplomacy` facet |
| `tests/unit/test_diplomacy_api.py` | create | Route, cursor, disabled-state tests |
| `tests/unit/test_diplomacy_settings.py` | create | Settings tests |

## Task 20: Add six GET routes, schemas, settings, and app wiring

### Intent

Researchers need to read the published artifact. Every route is GET-only, gated
by `SUBJECTIVE_DEBUG`, cursor-bound, and explicitly unavailable when no root is
configured. No route can mutate state or run analysis.

### Implementation Steps

1. Create `src/api/routes/diplomacy.py` with `router = APIRouter(prefix=
   "/v1/simulations", tags=["diplomacy"])` and six handlers:
   - `GET /{run_id}/diplomacy` → summary
   - `GET /{run_id}/diplomacy/relations` → paged relations
   - `GET /{run_id}/diplomacy/relations/{relation_id}` → detail
   - `GET /{run_id}/diplomacy/instruments` → paged instruments
   - `GET /{run_id}/diplomacy/instruments/{instrument_id}` → detail
   - `GET /{run_id}/diplomacy/lineage` → paged lineage
2. Every handler requires the `SUBJECTIVE_DEBUG` capability dependency, reusing
   the existing route dependency pattern. No handler accepts a body or a
   non-GET verb.
3. A missing reader yields HTTP 503 with
   `{"code": "diplomacy_disabled"}` via the shared `service_unavailable` helper;
   an unknown published relation/instrument id yields 404 with
   `diplomacy_unknown_relation`/`diplomacy_unknown_instrument`.
4. Create `src/api/diplomacy_schemas.py` with strict models (`extra="forbid"`)
   for summary, relation, party, contact, envoy, negotiation, instrument,
   declaration, misrepresentation, termination, conflict, lineage, and
   `*PageOut` responses. Fields expose only content-addressed row ids, hashed
   tokens, owner-safe `orgc-`/region anchors, and counts.
5. Create `src/api/diplomacy_cursor.py` with `DiplomacyCursorCodec`
   (`from_secret`, `encode`, `decode`), TTL 900 seconds, HMAC over the purpose
   plus the Task 17 fingerprint, and reasons
   `diplomacy_cursor_invalid` (400) / `diplomacy_cursor_expired` (410).
6. Add settings: `diplomacy_root: Path | None = None`,
   `diplomacy_cursor_key: SecretStr | None = None`; env
   `PALIMPSEST_DIPLOMACY_ROOT`, `PALIMPSEST_DIPLOMACY_CURSOR_KEY`; validators
   require a ≥32-byte key when set; health flags `has_diplomacy_root`,
   `diplomacy_enabled`, `diplomacy_cursor_enabled`.
7. In `src/api/app.py`, add `_attach_diplomacy_reader` beside the representation
   attachment (352), set `app.state.diplomacy_reader` and
   `app.state.diplomacy_cursor_codec`, and include the router at the
   representation include site (477).
8. In `src/api/dependencies.py`, add `get_diplomacy_reader(request)`.
9. The API must not import `analysis`, `experiments`, or `research_runner`.

### Required Interfaces and Contracts

- Exactly six routes, all GET, all `SUBJECTIVE_DEBUG`.
- Disabled state is 503 `diplomacy_disabled`, never an empty 200.
- Cursor errors are 400/410 with safe codes.
- Response models reject unknown fields and never expose raw ids, anchors,
  subjects, or frame bodies.
- No `/v2` route and no change to `/version`.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md`: research capabilities separate control,
  objective inspection, agent-visible projection, and default-disabled
  subjective debug.
- `docs/research-api.md`: existing route conventions.

### Error Handling and Logging

- Codes: `diplomacy_disabled`, `diplomacy_cursor_invalid`,
  `diplomacy_cursor_expired`, `diplomacy_unknown_relation`,
  `diplomacy_unknown_instrument`.
- `DEBUG diplomacy_api route=%s rows=%s`.
- Never log credentials, cursor values, run content, or tokens.

### Tests

- `tests/unit/test_diplomacy_api.py`: exactly six GET routes and no other verbs;
  capability required; 503 when unconfigured; 200 with a fixture; relation
  detail includes terminations; cursor reuse works; changed
  run/filter/publication/digest yields 400; expiry yields 410; unknown ids 404
  with the exact safe codes; response models reject extra fields and expose no
  raw agent ids/subjects; no `/v2`; `/version` unchanged.
- `tests/unit/test_diplomacy_settings.py`: defaults None; env parsing; short key
  rejected; health flags.

### Acceptance Criteria

- Six read-only, capability-gated routes with explicit disabled and cursor
  semantics.
- No write path and no analysis import.

### Verification

- `uv run pytest tests/unit/test_diplomacy_api.py tests/unit/test_diplomacy_settings.py -q`
- Expected: pass.

## Task 21: Add the read-only Research UI diplomacy view

### Intent

The panel presents server fields. It must not compute a bilateral score, rank
parties, infer authority, or decide which agreement is real.

### Implementation Steps

1. Create `clients/research-ui/src/api/diplomacy.ts` with types mirroring the
   six responses and functions `getDiplomacySummary`, `getDiplomacyRelations`,
   `getDiplomacyRelation`, `getDiplomacyInstruments`, `getDiplomacyInstrument`,
   `getDiplomacyLineage`; export `CAPABILITY` values for the view's disabled
   state.
2. Create `views/DiplomacyPanel.svelte` with props `runId` and `selection`,
   states `loading | available | empty | unavailable | error`, and read-only
   tables for relations, parties, envoys, negotiations, instruments,
   declarations, misrepresentation, terminations, conflicts, and lineage.
3. Render envoy standing as a server-provided status label; never as a badge of
   authority or legitimacy.
4. Render misrepresentation rows as retained observations; never as "lie" or
   "confirmed".
5. Render explicit empty and unavailable states; no client-side aggregation.
6. Mount the panel in `RunOverview.svelte` beside the representation panel and
   add a `diplomacy` facet in **both** `RESEARCH_UI_VIEWS` (line 19) and
   `RUN_SCOPED_VIEWS` (line 51) in `selection.ts`; update `deeplink.test.ts` if
   it enumerates the view set.
7. Do not add derived metrics, sorting by an invented score, or client-side
   totals that are not server fields. Render termination rows as retained
   observations, not as a verdict.

### Required Interfaces and Contracts

- The client never writes, never derives authority, and never builds a
  relationship score.
- All displayed identifiers are the server's tokens.
- The panel fails closed to `unavailable` on 503 and to `error` otherwise.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md`: clients are presentation-only and never advance
  the simulation.
- Original Request: "Do not create magical bilateral relationship scores".

### Error Handling and Logging

- Client shows safe codes only; no retry storm and no console logging of tokens
  or payloads.
- Existing UI error conventions apply.

### Tests

- `clients/research-ui/src/views/DiplomacyPanel.test.ts` (the flat location used
  by `RepresentationPanel.test.ts`): loading, available, empty, unavailable,
  error; no derived score rendered; misrepresentation and termination rows use
  neutral labels; six client functions map to six routes.
- `pnpm --dir clients/research-ui test`, `pnpm --dir clients/research-ui check`,
  and `pnpm --dir clients/research-ui build` when the toolchain is available.

### Acceptance Criteria

- The panel is read-only and derives nothing.
- It consumes exactly the six routes.

### Verification

- `uv run pytest tests/unit/test_diplomacy_api.py -q`
- Expected: pass.
- `pnpm --dir clients/research-ui test`; expected: pass when `pnpm` is
  installed; otherwise record the lane as unexecuted with prerequisite `pnpm`.

## Phase Risks and Mitigations

- Risk: the panel implies legitimacy or a winner.
  Mitigation: neutral status labels, no aggregation, and a test asserting no
  score rendering.
- Risk: route count drifts.
  Mitigation: exact six-route assertions and a route-set pin in Task 22.
- Risk: disabled state degrades into a misleading empty page.
  Mitigation: explicit 503 and a distinct UI state.

## Phase Completion Checklist

- Every task in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
