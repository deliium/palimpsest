# Phase 6: Read-Only API, Research UI, and Godot Overlays

Plan: [index.md](index.md)
Tasks: 20-22
Depends on: Phase 5 / Tasks 18-19

## Objective

Serve the committed `borders-snapshot-v1` through six GET-only routes, add a
read-only Research UI panel with four epistemically labeled sections, and add
four Godot overlay kinds that distinguish physical control, subjective claim,
agreement, and analytical control pattern. No surface writes, derives authority,
or renders a winner, sovereignty, legitimacy, or composite score.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/api/routes/organized_conflict.py` | router/count 38-40; disabled/reader/auth 43-59; snapshot/404 62-69; cursor 72-124; mappers 127-176; six routes 179-377 | Exact six-route pattern |
| `src/api/organized_conflict_schemas.py` | strict schemas 9-112; `MAX_PAGE_LIMIT = 500` | Schema pattern |
| `src/api/organized_conflict_cursor.py` | 15-17 | Cursor alias pattern |
| `src/api/app.py` | import 44; attach 354-379; call 501; include 533 | App wiring points |
| `src/api/dependencies.py` | 174-175 | Reader dependency pattern |
| `src/api/routes/__init__.py` | 21, 44 | Router export |
| `src/api/routes/civilization.py` | 97-112 | Layer-scoped auth precedent |
| `src/api/security.py` | capabilities 43-49; require 119-199 | Capability names and errors |
| `clients/research-ui/src/api/organizedConflict.ts` | 3-122 | UI client pattern |
| `clients/research-ui/src/views/OrganizedConflictPanel.svelte` | 15-126 | Panel/state/neutral wording pattern |
| `clients/research-ui/src/research/selection.ts` | views 8-40; run-scoped 42-70; evidence class 72 | View registration |
| `clients/research-ui/src/views/RunOverview.svelte` | tabs 62-129; render 333-336 | Tab/render integration |
| `clients/godot-observer/scripts/presentation/evidence_class.gd` | wire constants 5-7; overlay map 14-38; helpers 41-81 | Three evidence classes and overlay mapping |
| `clients/godot-observer/scripts/ui/overlay_legend.gd` | toggle rows 10-31; signal 43-59 | Overlay toggles |
| `clients/godot-observer/scripts/view/claim_overlay.gd` | layer gate 15-22; targets 45-48; metadata 55-57 | Subjective overlay pattern |
| `clients/godot-observer/scripts/view/analytics_overlay.gd` | layer gate 15-22; readings 53-104 | Analytical overlay pattern |
| `clients/godot-observer/scripts/main.gd` | toggle dispatch 452-518; payload dispatch 521-542 | Client wiring |
| `clients/godot-observer/scripts/net/session.gd` | claims 1478-1480; analytics 1571-1573 | HTTP request pattern |
| `clients/godot-observer/scripts/view/world_view.gd` | claims 126-132; analytics 134-140; clear 173-182 | Layer application |
| `tests/unit/test_organized_conflict_api.py` | route/disabled/404/cursor cases | API test pattern |
| `clients/research-ui/src/views/OrganizedConflictPanel.test.ts` | 98-126 | Neutrality and unavailable-state tests |
| `clients/godot-observer/tests/test_evidence_class.gd` | existing mapping tests | Overlay mapping test pattern |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/api/routes/borders.py` | create | Six GET-only routes |
| `src/api/borders_schemas.py` | create | Strict response schemas |
| `src/api/borders_cursor.py` | create | Cursor codec alias |
| `src/api/app.py` | modify | Attach reader, include router |
| `src/api/dependencies.py` | modify | `get_borders_reader` |
| `src/api/routes/__init__.py` | modify | Router export |
| `clients/research-ui/src/api/borders.ts` | create | Types and fetch functions |
| `clients/research-ui/src/views/BordersPanel.svelte` | create | Four-layer read-only panel |
| `clients/research-ui/src/views/BordersPanel.test.ts` | create | State and neutrality tests |
| `clients/research-ui/src/research/selection.ts` | modify | Add `borders` to view and run-scoped lists |
| `clients/research-ui/src/views/RunOverview.svelte` | modify | Tab and render branch |
| `clients/godot-observer/scripts/presentation/evidence_class.gd` | modify | Four border overlay mappings |
| `clients/godot-observer/scripts/ui/overlay_legend.gd` | modify | Four border toggles |
| `clients/godot-observer/scripts/view/border_overlay.gd` | create | Four-layer border overlay |
| `clients/godot-observer/scripts/view/world_view.gd` | modify | Route/clear border payloads |
| `clients/godot-observer/scripts/main.gd` | modify | Toggle and payload dispatch |
| `clients/godot-observer/scripts/net/session.gd` | modify | Border HTTP requests |
| `clients/godot-observer/tests/test_borders_overlay.gd` | create | Mapping and leak tests |
| `clients/godot-observer/tests/test_evidence_class.gd` | modify | Four new overlay mappings and three-class invariants |
| `docs/development.md` | modify | Protocol suite count 48 -> 49 |
| `tests/unit/test_borders_api.py` | create | Route count, auth, disabled, 404, cursor |
| `tests/compose/test_research_ui_wiring.py` | modify | Optional border asset wiring check |

## Task 20: Add six GET border routes, schemas, and app wiring

### Intent

Serve a committed border snapshot without importing analysis or rebuilding it.
All six routes are GET-only, require `SUBJECTIVE_DEBUG`, fail closed when the
store is unconfigured, and return 404 for unknown published records.

### Implementation Steps

1. Create `src/api/borders_cursor.py`:
   - `BordersCursorCodec = DiplomacyCursorCodec`
   - `BORDERS_CURSOR_TTL_SECONDS = 900`
2. Create `src/api/borders_schemas.py` with strict frozen Pydantic models
   (`extra="forbid"`):
   - `BordersSummaryOut` (including `candidate_count`)
   - `BordersClaimOut`
   - `BordersAgreementOut`
   - `BordersControlRowOut`
   - `BordersPageOut[T]` or concrete `BordersClaimPageOut` /
     `BordersAgreementPageOut` / `BordersControlPageOut`
   - `MAX_PAGE_LIMIT = 500`
3. Create `src/api/routes/borders.py`:
   - `router = APIRouter(prefix="/v1/simulations", tags=["borders"])`
   - `BORDERS_ROUTE_COUNT = 6`
   - `_authorize(request)` requires `ApiCapability.SUBJECTIVE_DEBUG`.
   - `_reader(request)` and `_codec(request)` raise 503
     `borders_disabled` when `app.state.borders_reader` or
     `app.state.borders_cursor_codec` is `None`.
   - `_snapshot(request, run_id)` returns 404 `borders_publication_not_found`
     for an unknown published run.
   - Six routes:
     1. `GET /{run_id}/borders` -> summary.
     2. `GET /{run_id}/borders/claims` -> claim page.
     3. `GET /{run_id}/borders/claims/{claim_id}` -> claim detail.
     4. `GET /{run_id}/borders/agreements` -> agreement page.
     5. `GET /{run_id}/borders/agreements/{agreement_id}` -> agreement detail.
     6. `GET /{run_id}/borders/control` -> physical and/or analytical page,
        with `layer` in `physical`, `analytical`, `all` (default `all`).
   - Every page route accepts `cursor` and `limit` (1..500).
   - The control route filters by `layer` and includes the layer in the cursor
     fingerprint.
   - Detail routes return 404 `borders_record_not_found` for an unknown token.
   - Cursor mismatch -> 400 `borders_cursor_invalid`; expiry -> 410
     `borders_cursor_expired`.
   - Response rows contain only hashed/opaque tokens and closed labels.
4. In `src/api/app.py`:
   - Import `borders` at line 44 area.
   - Add `_attach_borders_reader(app, settings)` near 354-379:
     - if `settings.borders_root` and `settings.borders_cursor_key` are present,
       create `create_borders_reader` and `BordersCursorCodec(key)`;
     - otherwise set both to `None`;
     - never log the root or key.
   - Call it at line 501 area.
   - `include_router(borders.router)` at line 533 area.
5. In `src/api/dependencies.py`, add `get_borders_reader(request)` returning
   `app.state.borders_reader`.
6. In `src/api/routes/__init__.py`, export the router.
7. Do not add a `/v2` route, a write method, a POST/PUT/PATCH/DELETE, or an
   analysis import.

### Required Interfaces and Contracts

```python
BORDERS_ROUTE_COUNT: Final[int] = 6
MAX_PAGE_LIMIT: Final[int] = 500

@router.get("/{run_id}/borders")
async def read_borders_summary(...) -> BordersSummaryOut: ...

@router.get("/{run_id}/borders/claims")
async def read_border_claims(...) -> BordersClaimPageOut: ...

@router.get("/{run_id}/borders/claims/{claim_id}")
async def read_border_claim(...) -> BordersClaimOut: ...

@router.get("/{run_id}/borders/agreements")
async def read_border_agreements(...) -> BordersAgreementPageOut: ...

@router.get("/{run_id}/borders/agreements/{agreement_id}")
async def read_border_agreement(...) -> BordersAgreementOut: ...

@router.get("/{run_id}/borders/control")
async def read_border_control(...) -> BordersControlPageOut: ...
```

- Exactly six routes, all GET.
- All require `SUBJECTIVE_DEBUG`.
- 503 `borders_disabled` when unconfigured.
- 404 for unknown run/publication/record.
- 400/410 cursor errors.
- No analysis import, no store write.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — four read-only overlays.
- Source: `docs/research-api.md` 242-280 and `src/api/routes/organized_conflict.py`
  179-377.
- Supported combinations: configured/unconfigured; known/unknown run; known/
  unknown record; first/next/last page; valid/changed/expired cursor; layer
  physical/analytical/all; each tested.

### Error Handling and Logging

- Disabled: `503 {"detail":{"code":"borders_disabled"}}`.
- Unknown: `404 {"detail":{"code":"borders_publication_not_found"}}` or
  `borders_record_not_found`.
- Cursor: 400/410 with stable codes.
- Logs: `DEBUG borders_api route=%s rows=%s`; never log run ids, tokens, cursor
  values, or payloads.

### Tests

- `tests/unit/test_borders_api.py`
  - `test_exactly_six_get_routes`
  - `test_all_routes_require_subjective_debug`
  - `test_unconfigured_store_returns_borders_disabled`
  - `test_unknown_publication_and_record_return_404`
  - `test_cursor_round_trip_and_changed_binding_400`
  - `test_expired_cursor_410`
  - `test_control_layer_filter_and_fingerprint`
  - `test_no_write_method_no_v2_route`
  - `test_no_analysis_import_in_router`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_api.py -q`
- Expected: all pass.

### Acceptance Criteria

- Exactly six GET routes exist.
- All require `SUBJECTIVE_DEBUG` and fail closed.
- Cursors bind run/publication/digest/purpose/filters.
- No write, analysis import, or `/v2` route exists.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_api.py -q`
- `rg -n "borders" src/api/routes/borders.py | rg "post|put|patch|delete"` —
  expected: no matches.
- Expected: pass.

## Task 21: Add the read-only Research UI border view

### Intent

Render the four layers in one read-only panel with explicit epistemic labels.
The researcher can see physical control, subjective claims, agreements, and
analytical control patterns without the UI implying truth, sovereignty, or a
winner.

### Implementation Steps

1. Create `clients/research-ui/src/api/borders.ts`:
   - `CAPABILITY = 'subjective_debug'`.
   - Type mirrors for summary, claim, agreement, control row, and page.
   - `bordersBase(runId)` and six fetch functions matching the routes.
   - Disabled (`503`/`borders_disabled`) maps to an `unavailable` state, not an
     error banner.
2. Create `clients/research-ui/src/views/BordersPanel.svelte`:
   - Props `{ runId, selection }` matching `OrganizedConflictPanel.svelte`.
   - Status union `idle | loading | ready | empty | unavailable | error`.
   - `load()` fetches summary plus claims, agreements, and control in
     `Promise.all`; control is fetched once with `layer=all`.
   - Four sections with `EpistemicBadge`:
     - `Physical control` — objective.
     - `Claims` — subjective.
     - `Agreements` — agreement/subjective.
     - `Control patterns` — analytical.
   - Render only closed labels, counts, tokens, and statuses.
   - No text or link uses `winner`, `loser`, `legitimate`, `sovereignty`,
     `score`, `ownership`, or `border truth`.
3. In `clients/research-ui/src/research/selection.ts`:
   - Add `'borders'` to `RESEARCH_UI_VIEWS`.
   - Add `'borders'` to `RUN_SCOPED_VIEWS`.
4. In `clients/research-ui/src/views/RunOverview.svelte`:
   - Add `{ id: 'borders', label: 'Borders and claims' }` to the run tab group.
   - Import `BordersPanel`.
   - Add the render branch next to `conflict`.
5. Create `clients/research-ui/src/views/BordersPanel.test.ts`:
   - loading/ready/empty/unavailable/error;
   - four section labels and epistemic badges;
   - neutral wording test rejects the forbidden words;
   - disabled 503 maps to `unavailable`.
6. Update `tests/compose/test_research_ui_wiring.py` if it enumerates panel
   assets; the check must accept the new panel without requiring a running API.

### Required Interfaces and Contracts

```ts
const CAPABILITY = 'subjective_debug';

export type BordersSummary = { ... };
export async function fetchBordersSummary(runId: string, options: CredentialOptions): Promise<BordersSummary>;
export async function fetchBorderClaims(runId: string, options: CredentialOptions): Promise<Page<BordersClaim>>;
export async function fetchBorderAgreements(runId: string, options: CredentialOptions): Promise<Page<BordersAgreement>>;
export async function fetchBorderControl(runId: string, options: CredentialOptions): Promise<Page<BordersControlRow>>;
```

- The panel is read-only: no POST/PUT/PATCH/DELETE.
- Four layers are visibly distinct.
- No authority/legitimacy/score/winner/war/sovereignty wording.
- Disabled is an explicit unavailable state.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — Godot/research overlays must distinguish four
  layers.
- Source: `clients/research-ui/src/views/OrganizedConflictPanel.svelte` 15-126.
- Source: `clients/research-ui/src/research/selection.ts` 8-70.
- Supported combinations: available/empty/disabled/error; each layer present or
  empty; each tested.

### Error Handling and Logging

- `borders_disabled`/HTTP 503 -> `unavailable`.
- Other HTTP errors -> `error` with a safe status code, no payload echo.
- No browser console logging of tokens, run ids, or rows.
- The panel never writes.

### Tests

- `clients/research-ui/src/views/BordersPanel.test.ts`
- Commands:
  - `npx pnpm@10.34.9 test --run`
  - `npx pnpm@10.34.9 check`
  - `npx pnpm@10.34.9 build`
- Expected: tests pass, 0 type errors, build succeeds.

### Acceptance Criteria

- The panel renders four distinct sections.
- Disabled/empty/error states are explicit.
- No forbidden authority/score wording exists.
- No write call exists.

### Verification

- `cd clients/research-ui && npx pnpm@10.34.9 test --run`
- `cd clients/research-ui && npx pnpm@10.34.9 check`
- Expected: pass.

## Task 22: Add the four-layer Godot border overlays

### Intent

Let the Godot observer display physical control, subjective claims, agreements,
and analytical control patterns as four distinct overlay kinds while preserving
the three-class evidence model. Agreements are shown as a distinct subjective
layer, not a fourth evidence class.

### Implementation Steps

1. In `clients/godot-observer/scripts/presentation/evidence_class.gd`:
   - Add `OVERLAY_CLASSES` entries:
     - `"border_physical"` -> `OBJECTIVE`
     - `"border_claims"` -> `SUBJECTIVE_TO_SELECTED_AGENT`
     - `"border_agreements"` -> `SUBJECTIVE_TO_SELECTED_AGENT`
     - `"border_patterns"` -> `ANALYTICAL_INFERRED`
   - Add short labels: `Physical`, `Claims`, `Agreements`, `Patterns`.
   - Do not add a fourth `EvidenceClass` constant.
2. In `clients/godot-observer/scripts/ui/overlay_legend.gd`:
   - Add four toggle rows with the same evidence class and distinct copy:
     - "Physical control" (OBJECTIVE)
     - "Border claims" (SUBJECTIVE)
     - "Border agreements" (SUBJECTIVE)
     - "Control patterns" (ANALYTICAL)
3. Create `clients/godot-observer/scripts/view/border_overlay.gd`:
   - Accept only payloads with `layer` in
     `{physical_control, subjective_claims, subjective_agreements,
     analytical_pattern}`.
   - Marker style:
     - physical: solid objective marker;
     - claims: dashed subjective outline;
     - agreements: double outline with an agreement badge;
     - patterns: dotted analytical marker.
   - Marker metadata includes `overlay_kind`, `evidence_class`, `layer`,
     `location_id`/`domain_token`, and a safe copy string.
   - Reject a payload with raw owner/agent/entity ids or forbidden result fields.
   - Clear all border markers on a layer toggle off.
4. In `clients/godot-observer/scripts/view/world_view.gd`:
   - Add `set_border_overlay(payload)` and `clear_border_overlay()`.
   - Route physical/claims/agreements/patterns to the new overlay.
   - Keep existing `territorial_claims` and `spatial_control` overlays
     independent.
5. In `clients/godot-observer/scripts/main.gd`:
   - Add four toggle dispatch cases next to `territorial_claims`/`spatial_control`.
   - Add four payload routing branches.
   - The existing default-off state is unchanged.
6. In `clients/godot-observer/scripts/net/session.gd`:
   - Add `request_border_summary`, `request_border_claims`,
     `request_border_agreements`, `request_border_control(layer)`.
   - Use the `debug` capability for all four because the published border
     snapshot is a subjective-debug read model; never pass a query-string token.
   - Accept only bounded JSON; never send a token in the URL.
7. Update `clients/godot-observer/tests/test_evidence_class.gd`:
   - assert the four new overlay kinds map to the expected three evidence
     classes;
   - assert agreement remains subjective and is not a fourth evidence class;
   - keep every existing overlay mapping unchanged.
8. Add `clients/godot-observer/tests/test_borders_overlay.gd`:
   - four overlay kinds map to the expected evidence class;
   - four distinct visual styles;
   - agreement layer is not an objective class;
   - raw-id/forbidden-field payloads are rejected;
   - toggle off clears markers;
   - existing claim/analytics overlays still work.
9. Register the new test suite in the Godot protocol runner (the same list that
   runs `test_evidence_class.gd`) and update `docs/development.md` from
   "48 suites" to "49 suites".

### Required Interfaces and Contracts

```gdscript
const BORDER_OVERLAY_KINDS := [
    "border_physical",
    "border_claims",
    "border_agreements",
    "border_patterns",
]
```

```text
overlay kind          evidence class              visual
border_physical       OBJECTIVE                   solid
border_claims         SUBJECTIVE_TO_SELECTED      dashed
border_agreements     SUBJECTIVE_TO_SELECTED      double outline + badge
border_patterns       ANALYTICAL_INFERRED         dotted
```

- Four semantic layers are distinguishable.
- The evidence class remains three-valued.
- No objective frame gains a border field.
- No authority/legitimacy/score/winner/sovereignty copy exists.
- Tokens never appear in a URL.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — "Godot/research overlays must distinguish physical
  control, subjective claim, agreement, analytical control pattern."
- Source: `clients/godot-observer/scripts/presentation/evidence_class.gd` 5-81
  and `docs/godot-civilization-overlays.md` 15-58.
- Supported combinations: each overlay on/off; each payload layer; malformed
  payload; raw-id payload; existing overlays unchanged; each tested.

### Error Handling and Logging

- Unknown layer: reject the payload and log
  `WARN border_overlay_rejected reason_code=unknown_layer` (no body).
- Raw id/forbidden field: reject and log a safe code.
- Network failure: hide the overlay; do not affect physics or playback.
- Never log tokens, ids, or payload bodies.

### Tests

- `clients/godot-observer/tests/test_borders_overlay.gd`
- `clients/godot-observer/tests/test_evidence_class.gd`
- Command:
  `"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd`
- Expected: `godot_protocol_tests failed=0` and 49 registered suites.

### Acceptance Criteria

- Four distinct border overlays exist.
- The three-class evidence model is preserved.
- Agreement is visibly distinct from claim and from analytical pattern.
- Existing overlays and playback behavior are unchanged.
- No raw ids or forbidden result fields are rendered.

### Verification

- `"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd`
- Expected: `failed=0`.

## Phase Risks and Mitigations

- Risk: the API rebuilds analysis on read.
  Mitigation: routes read only the committed store; Task 20 tests no analysis
  import.
- Risk: the UI implies sovereignty or a winner.
  Mitigation: four neutral epistemic sections and a forbidden-word test.
- Risk: Godot invents a fourth evidence class and breaks existing contracts.
  Mitigation: four overlay kinds map onto the existing three classes.
- Risk: physical control is rendered as ownership.
  Mitigation: objective markers are labeled "Physical control" and use counts/
  use evidence only.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
