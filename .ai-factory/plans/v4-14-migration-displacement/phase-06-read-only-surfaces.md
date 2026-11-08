# Phase 6: Read-Only API, Research UI, and Godot Overlays

Plan: [index.md](index.md)
Tasks: 20-22
Depends on: Phase 5 / Tasks 18-19

## Objective

Serve the committed migration-displacement snapshot through six GET-only routes,
render a four-section read-only Research UI panel, and add four client-side
Godot overlay kinds on the existing three-class evidence model. No client gains
write, analysis, or world authority.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/api/routes/borders.py` | router prefix 33; auth 51-55; snapshot 57-70; fingerprint 71-80; cursor 81-128; six routes 197-348 | Exact route/auth/cursor pattern |
| `src/api/borders_schemas.py` | strict models 14-84; `MAX_PAGE_LIMIT=500` | Exact schema pattern |
| `src/api/borders_cursor.py` | `BordersCursorCodec` | Exact HMAC cursor pattern |
| `src/api/dependencies.py` | `get_borders_reader` 178-179 | Dependency pattern |
| `src/api/app.py` | `_attach_borders_reader` 383-402; include router 558 | App wiring pattern |
| `src/api/routes/__init__.py` | router export 3, 30 | Router registry |
| `docs/research-api.md` | route and status conventions | API contract |
| `clients/research-ui/src/api/borders.ts` | typed fetch client | UI API pattern |
| `clients/research-ui/src/views/BordersPanel.svelte` | four-section read-only panel | UI pattern |
| `clients/research-ui/src/views/RunOverview.svelte` | import 46, tab 113, render 339-340 | UI integration |
| `clients/research-ui/src/research/selection.ts` | view id 22 | Selection integration |
| `clients/godot-observer/scripts/view/border_overlay.gd` | overlay kinds and draw path | Godot overlay pattern |
| `clients/godot-observer/scripts/presentation/evidence_class.gd` | 5-81 | Three-class evidence model |
| `clients/godot-observer/scripts/net/session.gd` | border fetch 1577-1592 | Session fetch pattern |
| `clients/godot-observer/scripts/ui/overlay_legend.gd` | legend entries | Legend pattern |
| `clients/godot-observer/tests/test_borders_overlay.gd` | overlay tests | GDScript test pattern |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/api/routes/migration_displacement.py` | create | Six GET routes and cursor handling |
| `src/api/migration_displacement_schemas.py` | create | Strict response models and page wrappers |
| `src/api/migration_displacement_cursor.py` | create | Purpose-specific HMAC cursor codec |
| `src/api/dependencies.py` | modify | `get_migration_displacement_reader` |
| `src/api/app.py` | modify | Attach reader/codec and include router |
| `src/api/routes/__init__.py` | modify | Export the router |
| `clients/research-ui/src/api/migrationDisplacement.ts` | create | Typed read-only client |
| `clients/research-ui/src/views/MigrationDisplacementPanel.svelte` | create | Four-section panel |
| `clients/research-ui/src/views/MigrationDisplacementPanel.test.ts` | create | Panel behavior and labels |
| `clients/research-ui/src/research/selection.ts` | modify | Add `migration-displacement` |
| `clients/research-ui/src/views/RunOverview.svelte` | modify | Import, tab, render |
| `clients/godot-observer/scripts/view/migration_overlay.gd` | create | Four overlay kinds and draw/read behavior |
| `clients/godot-observer/scripts/net/session.gd` | modify | Fetch six migration routes |
| `clients/godot-observer/scripts/ui/overlay_legend.gd` | modify | Four legend entries |
| `clients/godot-observer/scripts/view/world_view.gd` | modify | Register/refresh migration overlay |
| `clients/godot-observer/scripts/main.gd` | modify | Wire overlay selection |
| `clients/godot-observer/tests/test_migration_overlay.gd` | create | Overlay/evidence mapping |
| `clients/godot-observer/tests/test_evidence_class.gd` | modify | Three-class model unchanged |
| `tests/unit/test_migration_displacement_api.py` | create | Routes, auth, statuses, cursors |
| `tests/compose/test_research_ui_wiring.py` | modify | Migration view wiring, if the existing test owns it |

## Task 20: Add six GET migration routes, schemas, and app wiring

### Intent

Expose the committed migration-displacement publication to researchers under
`SUBJECTIVE_DEBUG`, with explicit disabled/not-found/cursor/corrupt semantics.
The API reads the store; it never imports analysis or rebuilds a snapshot.

### Implementation Steps

1. Create `src/api/migration_displacement_schemas.py` with strict
   `extra="forbid"`, `frozen=True` models:
   - `MigrationDisplacementSummaryOut`:
     `run_id`, `publication_id`, `digest`, `schema_version`, `candidate_count`,
     `wave_count`, `cluster_count`, `outcome_count`, `movement_count`,
     `cause_count`, `displacement_like_count`, `mixed_count`,
     `not_displacement_like_count`, `unknown_count`, `coverage`.
   - `MigrationWaveOut`: `wave_token`, `origin_token`, `destination_token`,
     `participant_tokens`, `route_tokens`, `start_tick`, `end_tick`,
     `cause_support_counts`, `displacement_classification`,
     `displacement_bases`, `independent_cause_count`, `cluster_tokens`,
     `coverage`.
   - `MigrationWaveDetailOut`: the same fields plus `lineage_tokens` and
     `alignment_tokens`.
   - `MigrationRouteOut`: `route_token`, `owner_token`, `origin_token`,
     `destination_token`, `route_tokens`, `observed_duration_ticks`,
     `fatigue_cost`, `basis`, `status`, `first_tick`, `last_tick`.
   - `MigrationCauseOut`: `cause_token`, `owner_token`, `cause_kind`,
     `source_kind`, `anchor_token`, `confidence`, `tick`, `status`.
   - `MigrationOutcomeOut`: `outcome_token`, `participant_token`,
     `destination_token`, `residence_ticks`, `access_evidence_count`,
     `participation_evidence_count`, `relationship_evidence_count`,
     `conflict_evidence_count`, `classification`, `coverage`, `censored`.
   - Page wrappers: `MigrationWavePageOut`, `MigrationRoutePageOut`,
     `MigrationCausePageOut`, `MigrationOutcomePageOut`, each with `items` and
     `next_cursor`.
2. Create `src/api/migration_displacement_cursor.py` with
   `MigrationDisplacementCursorCodec`, mirroring `BordersCursorCodec`:
   - `from_secret(secret: bytes)` and `encode(payload)`, `decode(token)`;
   - HMAC-SHA-256 over canonical JSON;
   - reject tampering, wrong purpose, and expiry.
3. Create `src/api/routes/migration_displacement.py`:
   - `router = APIRouter(prefix="/v1/simulations", tags=["migration-displacement"])`.
   - `_authorize(request, settings)` requires the `SUBJECTIVE_DEBUG` capability
     exactly as `borders.py` does.
   - `_reader(reader)` returns 503 `migration_displacement_disabled` when unset.
   - `_snapshot(reader, run_id)` returns 503 disabled, 404 unknown, or 500
     `migration_displacement_store_corrupt`; never a false 404 for corruption.
   - Six routes:
     `GET /{run_id}/migration` → `MigrationDisplacementSummaryOut`;
     `GET /{run_id}/migration/waves` → `MigrationWavePageOut`;
     `GET /{run_id}/migration/waves/{wave_id}` → `MigrationWaveDetailOut`;
     `GET /{run_id}/migration/routes` → `MigrationRoutePageOut`;
     `GET /{run_id}/migration/causes` → `MigrationCausePageOut`;
     `GET /{run_id}/migration/outcomes` → `MigrationOutcomePageOut`.
   - Query parameters: `cursor: str | None`, `limit: int = 100`,
     and filters `classification`, `cause_kind`, `outcome`, `origin_token`,
     `destination_token`, `cluster_token`.
   - Reject an unknown filter value with 422; reject limit `<1` or `>500` with
     422; cursor mismatch 400 `migration_displacement_cursor_invalid`; expiry
     410 `migration_displacement_cursor_expired`.
   - Detail route: 404 `migration_displacement_not_found` for an unknown token.
   - Every response contains tokens only; no raw ids, routes, causes, frames, or
     evidence bodies.
4. In `src/api/dependencies.py`, add `get_migration_displacement_reader`.
5. In `src/api/app.py`:
   - add `_attach_migration_displacement_reader(app)`;
   - read `settings.migration_displacement_root` and
     `settings.migration_displacement_cursor_key`;
   - set `app.state.migration_displacement_reader` and
     `app.state.migration_displacement_cursor_codec`;
   - include the router.
6. In `src/api/routes/__init__.py`, export
   `migration_displacement_router`.
7. Ensure the API never imports `analysis`, `agents.cognition`,
   `experiments`, or `persistence` beyond the reader factory.

### Required Interfaces and Contracts

- Six GET routes only; no POST/PUT/PATCH/DELETE.
- All require `SUBJECTIVE_DEBUG`; missing/unset reader is 503
  `migration_displacement_disabled`.
- Unknown run/publication/wave is 404 `migration_displacement_not_found`.
- Cursor mismatch is 400 `migration_displacement_cursor_invalid`; expiry is 410
  `migration_displacement_cursor_expired`.
- Corrupt store is 500 `migration_displacement_store_corrupt`.
- Page limit is `1..500`; default 100.
- No response field is named `refugee`, `asylum`, `forced`, `wellbeing`,
  `assimilation`, `score`, or `composite`.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — research analytics and read-only tracking.
- Source: `docs/research-api.md`; `src/api/routes/borders.py`.
- Supported combinations: disabled; authorized success; missing debug
  credential; unknown run; unknown wave; corrupt store; cursor reuse; changed
  binding; expiry; each filter; each is tested.

### Error Handling and Logging

- Log `INFO migration_displacement_api_disabled` only when unset.
- Log `WARN migration_displacement_cursor_invalid` and
  `WARN migration_displacement_cursor_expired` without the cursor body.
- Log `ERROR migration_displacement_store_corrupt` without the payload.
- Never log run ids, tokens, routes, causes, participants, or query bodies.

### Tests

- `tests/unit/test_migration_displacement_api.py`
  - `test_six_get_routes_exist`
  - `test_subjective_debug_is_required`
  - `test_unset_reader_is_503_disabled`
  - `test_summary_and_pages_return_tokens_only`
  - `test_unknown_run_or_wave_is_404`
  - `test_corrupt_store_is_500_not_404`
  - `test_cursor_reuse_succeeds_for_same_binding`
  - `test_cursor_mismatch_is_400_and_expiry_is_410`
  - `test_limit_and_filter_validation`
  - `test_no_refugee_or_score_field_in_schemas`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_api.py -q`
- Expected: all pass.

### Acceptance Criteria

- Exactly six GET routes are registered under `/v1/simulations/{run_id}/migration`.
- Auth and error semantics match the contract.
- Responses expose only published tokens and counts.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_api.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_api.py -q`
- Expected: pass.

## Task 21: Add the read-only Research UI migration view

### Intent

Give researchers a four-section view that visibly separates objective movement,
subjective cause, analytical wave/displacement, and integration outcome. The
panel is read-only and never labels a person as a refugee.

### Implementation Steps

1. Create `clients/research-ui/src/api/migrationDisplacement.ts`:
   - types mirroring the six API responses;
   - `fetchMigrationSummary(runId)`,
     `fetchMigrationWaves(runId, {cursor, limit, classification, ...})`,
     `fetchMigrationWave(runId, waveId)`,
     `fetchMigrationRoutes(runId, ...)`,
     `fetchMigrationCauses(runId, ...)`,
     `fetchMigrationOutcomes(runId, ...)`;
   - no mutation helpers.
2. Create `clients/research-ui/src/views/MigrationDisplacementPanel.svelte`:
   - props `runId`, `selection`;
   - four sections:
     1. **Movement and routes** (objective badge): origin/destination/route
        tokens, participants, counts, coverage.
     2. **Cause evidence** (subjective badge): cause/source counts, unresolved
        anchors, same-root suppression, coverage.
     3. **Waves and clusters** (analytical badge): wave participants,
        classification, bases, cluster sizes, lineage.
     4. **Integration outcomes** (integration badge): settled/transient/
        returned/onward/unknown counts, residence and evidence counts,
        censored/coverage.
   - use `displacement_like (analytical)` with a tooltip: "researcher-only
     classification from independent causal evidence; not a legal or social
     status".
   - never render the words `Refugee`, `Asylum`, `Forced`, or `Displaced person`
     as a status label.
   - disable actions and show empty/disabled/error states.
3. Update `clients/research-ui/src/research/selection.ts` with
   `'migration-displacement'`.
4. Update `clients/research-ui/src/views/RunOverview.svelte`:
   - import the panel;
   - add tab `{ id: 'migration-displacement', label: 'Migration and displacement' }`;
   - render `<MigrationDisplacementPanel {runId} {selection} />`.
5. Create `MigrationDisplacementPanel.test.ts`:
   - renders four sections with badges;
   - shows disabled state on 503;
   - shows empty state on no rows;
   - asserts no refugee/asylum/forced status text;
   - asserts analytical caveat is present;
   - asserts no write controls.
6. Update `tests/compose/test_research_ui_wiring.py` only if the existing test
   enumerates views; keep it read-only.

### Required Interfaces and Contracts

- The panel is read-only; no POST/PUT/DELETE.
- Four visible epistemic badges: `objective`, `subjective`, `analytical`,
  `integration`.
- No score, wellbeing, assimilation, legitimacy, refugee, asylum, or forced
  status.
- Missing data is explicit (`disabled`, `empty`, `partial`, `missing`), never
  zero-filled as fact.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — distinguish physical movement, cause evidence,
  clusters, integration outcomes.
- Source: `docs/research-ui.md`; V4-13 `BordersPanel.svelte`.
- Supported combinations: disabled; empty; full; partial; cursor pagination;
  detail; each is tested.

### Error Handling and Logging

- The UI surfaces safe status codes only; it never logs response bodies or
  tokens.
- A failed fetch renders an error state with no partial fabricated data.
- No client-side persistence of tokens.

### Tests

- `npx pnpm@10.34.9 test --run clients/research-ui/src/views/MigrationDisplacementPanel.test.ts`
- `npx pnpm@10.34.9 check`
- `npx pnpm@10.34.9 build`
- Expected: all pass.

### Acceptance Criteria

- The panel has four sections and four epistemic badges.
- No refugee/asylum/forced status label exists.
- The panel is read-only and handles disabled/empty/partial states.

### Verification

- `npx pnpm@10.34.9 test --run`
- `npx pnpm@10.34.9 check`
- `npx pnpm@10.34.9 build`
- Expected: pass.

## Task 22: Add the four-layer Godot migration overlays

### Intent

Add four read-only client-side overlay kinds that distinguish objective route,
subjective cause, analytical wave/displacement, and integration outcome, without
changing the observer protocol, evidence classes, world physics, or cognition.

### Implementation Steps

1. Create `clients/godot-observer/scripts/view/migration_overlay.gd`:
   - constants:
     `MIGRATION_ROUTE = "migration_route"`,
     `MIGRATION_CAUSE = "migration_cause"`,
     `MIGRATION_WAVE = "migration_wave"`,
     `MIGRATION_INTEGRATION = "migration_integration"`.
   - mapping to the existing evidence classes:
     `migration_route -> EvidenceClass.OBJECTIVE`;
     `migration_cause -> EvidenceClass.SUBJECTIVE`;
     `migration_wave -> EvidenceClass.ANALYTICAL`;
     `migration_integration -> EvidenceClass.ANALYTICAL`.
   - draw/read methods consume only the six published routes and display
     tokens/counts; no raw ids.
   - an unknown kind falls back to `hidden`, never to a guessed class.
2. Update `clients/godot-observer/scripts/net/session.gd`:
   - add `fetch_migration_summary`, `fetch_migration_waves`,
     `fetch_migration_routes`, `fetch_migration_causes`,
     `fetch_migration_outcomes` using the six routes;
   - do not add a protocol version, new semantic type, or write path.
3. Update `clients/godot-observer/scripts/ui/overlay_legend.gd` with four
   entries and the analytical caveat for displacement-like classification.
4. Update `clients/godot-observer/scripts/view/world_view.gd` to register,
   refresh, and clear the four overlay kinds.
5. Update `clients/godot-observer/scripts/main.gd` to expose overlay selection
   without changing simulation control.
6. Create `tests/test_migration_overlay.gd`:
   - four kinds map to objective/subjective/analytical/analytical;
   - unknown kind is hidden;
   - route/cause/wave/integration render tokens only;
   - no refugee/asylum/forced string;
   - no write/session mutation path.
7. Update `test_evidence_class.gd` only if the existing three-class assertions
   require the new client constants; the evidence class enum itself must not
   gain a fourth value.

### Required Interfaces and Contracts

- Exactly four migration overlay kinds.
- Existing evidence class stays three-valued: `objective`, `subjective`,
  `analytical`.
- The observer protocol, capabilities, `/version`, and layout are unchanged.
- No client code imports Python or mutates the simulation.
- No overlay displays a refugee/asylum/forced status.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — distinguish physical movement, cause evidence,
  analytical classification, integration outcome.
- Source: `clients/godot-observer/scripts/presentation/evidence_class.gd` 5-81;
  V4-13 `border_overlay.gd`.
- Supported combinations: each kind; unknown kind; disabled data; empty page;
  partial coverage; each is tested.

### Error Handling and Logging

- A missing publication hides overlays and shows no fabricated geometry.
- An unknown kind logs a metadata-only warning with the kind name, never a
  token or payload.
- No GDScript `print` of tokens, routes, causes, participants, or bodies.

### Tests

- `clients/godot-observer/tests/test_migration_overlay.gd`
- Optional headless command:
  `GODOT_BIN=/path/to/Godot godot --headless --path clients/godot-observer --script tests/test_migration_overlay.gd`
- Expected: all pass; if the pinned binary is unavailable, record the lane
  `unexecuted` with the prerequisite in Task 25.

### Acceptance Criteria

- Four overlay kinds exist and map onto the existing three evidence classes.
- Cause, wave, and integration are visibly distinct.
- The protocol and evidence model are unchanged.

### Verification

- `GODOT_BIN=<pinned> godot --headless --path clients/godot-observer --script tests/test_evidence_class.gd`
- `GODOT_BIN=<pinned> godot --headless --path clients/godot-observer --script tests/test_migration_overlay.gd`
- Expected: pass, or record `unexecuted` with the missing binary.

## Phase Risks and Mitigations

- Risk: the UI invents a Refugee category.
  Mitigation: Task 21 uses `displacement_like (analytical)` with a caveat and
  tests for forbidden status labels.
- Risk: the API rebuilds analysis.
  Mitigation: Task 20 reads only the committed store and imports no analysis.
- Risk: Godot adds a fourth evidence class or a protocol change.
  Mitigation: Task 22 maps four overlay kinds onto the existing three classes
  and asserts the protocol is unchanged.
- Risk: a corrupt store becomes a 404.
  Mitigation: Task 20 maps corruption to 500 explicitly.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
