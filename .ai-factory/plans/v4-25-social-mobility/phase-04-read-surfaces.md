# Phase 4: Read Surfaces

Plan: [index.md](index.md)
Tasks: 13-14
Depends on: Phase 3 (Tasks 10-12)

## Objective

Serve the published snapshot through seven GET-only, dual-gated routes with
purpose-bound cursors, and add a read-only Research UI panel. After this phase
the API round-trips a real store and the panel renders domains, generation
lags, and coverage without computing a score.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/api/economic_inequality_cursor.py` | `EconomicInequalityCursorCodec` (15), error alias (16), TTL (17) | Cursor codec alias pattern |
| `src/api/routes/economic_inequality.py` | `router` (24), route count (26), `_reader` (29-34), `_authorize` (47-52), `_snapshot` (55-67), `_after_key` (83-109), `_page` (130-171), summary route (195-222), six paged routes (246-319) | Exact route, gate, cursor, and error conventions |
| `src/api/app.py` | `_attach_economic_inequality_reader` (631-658), call site (860), router include (903) | Composition-root wiring |
| `src/api/routes/__init__.py` | economic import (16) and export (61) | Router facade |
| `clients/research-ui/src/research/selection.ts` | `RESEARCH_UI_VIEWS` (8-48, economic at 30), `RUN_SCOPED_VIEWS` (52+, economic at 73), `isView` (274) | View registration |
| `clients/research-ui/src/views/RunOverview.svelte` | panel import (53), tab groups (111-135, economic tab 131), mount branch (375-376) | Panel mounting |
| `clients/research-ui/src/api/economicInequality.ts` | types (5-69), `base` (98-99), summary/dimensions/cohorts/societies getters (101-127) | Typed fetch client pattern |
| `clients/research-ui/src/views/EconomicInequalityPanel.svelte` | Props (15-20), status/state (22-29), `load()` (48+) | Panel state machine and honest unavailable rendering |
| `clients/research-ui/src/views/EconomicInequalityPanel.test.ts` | fetch stubs (99-101, 178-180), describe (109) | Vitest panel test pattern |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/api/social_mobility_cursor.py` | create | TTL-900 purpose-bound cursor codec aliases |
| `src/api/routes/social_mobility.py` | create | Seven GET routes, dual gate, cursor binding, filters |
| `src/api/routes/__init__.py` | modify | Import/export `social_mobility_router` |
| `src/api/app.py` | modify | `_attach_social_mobility_reader` and include router |
| `clients/research-ui/src/api/socialMobility.ts` | create | Typed summary/domain/generation/coverage client |
| `clients/research-ui/src/views/SocialMobilityPanel.svelte` | create | Read-only panel |
| `clients/research-ui/src/views/SocialMobilityPanel.test.ts` | create | Panel tests |
| `clients/research-ui/src/research/selection.ts` | modify | Register `social-mobility` view and run scope |
| `clients/research-ui/src/views/RunOverview.svelte` | modify | Import, tab, mount |
| `clients/research-ui/src/research/selection.test.ts` | modify | New view recognition |
| `tests/unit/test_social_mobility_routes.py` | create | Route/gate/filter/cursor tests |
| `tests/unit/test_social_mobility_api_cursor.py` | create | Cursor TTL/binding tests |
| `tests/unit/test_social_mobility_research_ui.py` | create | Client file/registration assertions |
| `tests/integration/test_social_mobility_store_api.py` | create | Store/API round-trip, dual gate, cursor mismatch |

## Task 13: Add seven GET-only dual-gated routes

### Intent
Expose the artifact with the smallest possible surface and fail closed whenever
either setting is missing.

### Implementation Steps
1. Create `src/api/social_mobility_cursor.py`:
   `SocialMobilityCursorCodec = DiplomacyCursorCodec`,
   `SocialMobilityCursorError = DiplomacyCursorError`,
   `SOCIAL_MOBILITY_CURSOR_TTL_SECONDS = 900`.
2. Create `src/api/routes/social_mobility.py`:
   - `router = APIRouter(prefix="/v1/simulations", tags=["social-mobility"])`.
   - `SOCIAL_MOBILITY_ROUTE_COUNT: Final[int] = 7`.
   - Helpers mirroring the economic route module:
     `_reader` → 503 `social_mobility_disabled`;
     `_codec` → 503 `social_mobility_disabled`;
     `_authorize` → `ApiCapability.SUBJECTIVE_DEBUG`;
     `_snapshot` → 500 `social_mobility_store_corrupt` or 404
     `social_mobility_run_not_found`;
     `_after_key` → 410 `social_mobility_cursor_expired` / 400
     `social_mobility_cursor_invalid`, verifying run id, publication id,
     snapshot digest, purpose, limit, and `window_index`.
   - Route table:
     1. `GET /v1/simulations/{run_id}/social-mobility` → summary only
        (`get_social_mobility_summary`), no cursor or limit.
     2. `GET .../social-mobility/domains` → all six domains.
     3. `GET .../social-mobility/economy` → `resources`,
        `productive_assets`.
     4. `GET .../social-mobility/human-capital` → `skills`,
        `educational_access`.
     5. `GET .../social-mobility/standing` → `social_influence`,
        `organization_roles`.
     6. `GET .../social-mobility/generations` → generation and lag rows.
     7. `GET .../social-mobility/coverage` → coverage record only.
   - Query parameters: `limit: int = Query(default=100, ge=1, le=500)`,
     `window_index: int | None = Query(default=None, ge=0, le=511)`,
     `cursor: str | None = Query(default=None)` for paged routes.
   - `_page_body` returns `run_id`, `publication_id`, `window_index`, `rows`,
     `next_cursor`, and `coverage` (domain coverage for domain rows,
     generation coverage for generation/lag rows, coverage for coverage route).
3. In `src/api/app.py`, add `_attach_social_mobility_reader(app)`:
   require both `settings.social_mobility_root` and
   `settings.social_mobility_cursor_key`; otherwise set both app-state handles
   to `None` and return. On success build the codec and reader, set
   `app.state.social_mobility_reader` and
   `app.state.social_mobility_cursor_codec`, and log
   `social_mobility_router_ready`. Call it beside the economic attach and
   include the router before the version router.
4. Export `social_mobility_router` from `src/api/routes/__init__.py`.
5. Do not add a `/v2` route or any write method.

### Required Interfaces and Contracts
- All seven routes require `SUBJECTIVE_DEBUG`.
- Any unset setting → 503 `social_mobility_disabled` on every route.
- Cursors are bound to purpose, filter set, limit, window index, run,
  publication, and digest; a mismatch is 400.
- Summary and coverage responses never expose owner tokens.

### Requirement Evidence
- Original Request analytical read surface.
- `.ai-factory/ARCHITECTURE.md` V4-24 read-surface seam and capability
  separation.

### Error Handling and Logging
- INFO router ready/disabled.
- WARN cursor mismatch.
- ERROR store corruption; never log cursor keys, tokens, or rows.

### Tests
- `tests/unit/test_social_mobility_routes.py`: route count and paths, dual-gate
  503, summary shape, four domain filters, generations route, coverage route,
  window filter, cursor mismatch 400.
- `tests/unit/test_social_mobility_api_cursor.py`: TTL, purpose binding,
  tamper rejection.
- `tests/integration/test_social_mobility_store_api.py` (`pytest.mark.integration`):
  publish via filesystem store, read through `TestClient`, dual gate success,
  503 failure, cursor mismatch.

### Acceptance Criteria
- Exactly seven GET routes exist.
- A cursor minted for another window or filter set is rejected.
- Corrupt store returns 500, not a partial page.

### Verification
- `uv run pytest tests/unit/test_social_mobility_routes.py tests/unit/test_social_mobility_api_cursor.py -q`
- `uv run pytest tests/integration/test_social_mobility_store_api.py -q -m integration`
- Expected result: pass.

## Task 14: Add the Research UI client and panel

### Intent
Give researchers a read-only view of domains, generation lags, and coverage,
with honest `unavailable`/`insufficient_samples` states.

### Implementation Steps
1. Create `clients/research-ui/src/api/socialMobility.ts`:
   - Types for summary, domain row, generation row, lag row, coverage record,
     and paged responses.
   - `base(runId)` → `/v1/simulations/${runId}/social-mobility`.
   - `getSummary`, `getDomains`, `getEconomy`, `getHumanCapital`,
     `getStanding`, `getGenerations`, `getCoverage` using the existing
     capability-gated `apiFetch`.
2. Create `clients/research-ui/src/views/SocialMobilityPanel.svelte`:
   - `Props { runId: string; selection: ... }`.
   - Statuses `loading|ready|empty|unavailable|error`.
   - Render summary, domain table with all four statistics and persistence
     direction, generation/lag tables, and coverage.
   - Show `unavailable` and `insufficient_samples` literally; never compute a
     composite or sort domains from best to worst.
3. Register the view:
   - `selection.ts`: add `'social-mobility'` to `RESEARCH_UI_VIEWS` and
     `RUN_SCOPED_VIEWS`.
   - `RunOverview.svelte`: import the panel, add tab
     `{ id: 'social-mobility', label: 'Social mobility' }` in the Institutions
     group, and mount it in the view branch.
4. No Godot file changes.

### Required Interfaces and Contracts
- Panel is read-only; no POST/PUT.
- No payload logging in the browser console; only `loading`, `ready`, `empty`,
  `unavailable`, `error`.
- Panel never labels a domain or generation as best, worst, elite, or
  underclass.

### Requirement Evidence
- Original Request analytical comparison; `.ai-factory/ARCHITECTURE.md`
  V3-40…V3-42 presentation rules.

### Error Handling and Logging
- `error` status on fetch failure; `unavailable` on 503 with the safe code.
- No payload or token logging.

### Tests
- `clients/research-ui/src/views/SocialMobilityPanel.test.ts`: ready render,
  empty, unavailable, error, insufficient-samples text, no composite text.
- `clients/research-ui/src/research/selection.test.ts`: new view accepted.

### Acceptance Criteria
- Panel renders all three row families and coverage.
- Unavailable states are visible, not replaced by zeros.
- No Godot changes and no new write path.

### Verification
- `cd clients/research-ui && ./node_modules/.bin/vitest run`
- `cd clients/research-ui && ./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json`
- Expected result: pass, 0 type errors.

## Phase Risks and Mitigations
- Risk: route helper copy leaves economic-specific purpose names.
  Mitigation: a test asserts the seven purpose tokens and that
  `economic_inequality` does not appear in the new module.
- Risk: UI accidentally ranks domains.
  Mitigation: panel test forbids "best"/"worst"/"class" strings and renders the
  server order unchanged.

## Phase Completion Checklist
- Every Task in this phase satisfies its acceptance criteria.
- Python route/cursor/integration tests and Research UI tests pass.
- `index.md` Task 13-14 checkboxes are updated after verification.
