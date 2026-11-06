# Phase 6: Read-Only API and Research UI

Plan: [index.md](index.md)
Tasks: 20-21
Depends on: Phase 5

## Objective

Serve the published organized-conflict snapshot through six GET-only routes under
`SUBJECTIVE_DEBUG`, with purpose-bound cursors and stable disabled/404
semantics, and add a read-only Research UI view that renders the same facts
without deriving authority, legitimacy, enforcement, score, winner, or war
status.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/api/routes/diplomacy.py` | router 50; reader/codec 54-64; auth 67-70; errors 73-86; cursor 88-141; mapping 143-196; eight routes 199-422 | Route/cursor/error pattern |
| `src/api/diplomacy_cursor.py` | TTL 21; HMAC 40-65; payload 67-87; decode 89-105 | Cursor signing pattern |
| `src/api/diplomacy_schemas.py` | strict base 39-40; limit 36; summary 43-64; rows 168-316 | Schema pattern |
| `src/api/routes/__init__.py` | imports/exports 9, 32 | Router registration |
| `src/api/app.py` | import 33; `_attach_diplomacy_reader` 353-372; attach 471; include 502 | App wiring |
| `src/api/dependencies.py` | reader dependency 170-171 | Dependency wiring |
| `src/api/security.py` | `SUBJECTIVE_DEBUG` 49; enforcement 106, 130 | Capability gate |
| `src/infrastructure/settings.py` | root/cursor settings 230-231; summary 654-660 | Settings names |
| `clients/research-ui/src/api/diplomacy.ts` | capability 3; models 5-216; fetchers 222-294 | Client pattern |
| `clients/research-ui/src/views/DiplomacyPanel.svelte` | state 31-43; load 49-97; states 111-119; sections 120-251 | Panel pattern |
| `clients/research-ui/src/views/DiplomacyPanel.test.ts` | fixtures 20-170; fetch stub 172-189; render 195-272 | Panel tests |
| `clients/research-ui/src/views/RunOverview.svelte` | tabs 100-111; import 44; render 329-331; unknown view 341-348 | Host view and the current diplomacy routing gap |
| `clients/research-ui/src/research/selection.ts` | view ids 19-20; run-scoped 52-53 | View registry |
| `tests/unit/test_diplomacy_api.py` | route set 43-50; exactly eight 126-134; capability 137-153; cursor 156+ | API test pattern |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/api/organized_conflict_schemas.py` | create | Strict summary/episode/plan/interpretation/lineage models |
| `src/api/organized_conflict_cursor.py` | create | HMAC cursor codec |
| `src/api/routes/organized_conflict.py` | create | Six GET routes and error mapping |
| `src/api/routes/__init__.py` | modify | Import/export router |
| `src/api/app.py` | modify | Attach reader/codec and include router |
| `src/api/dependencies.py` | modify | Reader dependency |
| `tests/unit/test_organized_conflict_api.py` | create | Route set, capability, 503/404, cursor |
| `clients/research-ui/src/api/organizedConflict.ts` | create | Client models and six fetchers |
| `clients/research-ui/src/views/OrganizedConflictPanel.svelte` | create | Read-only panel |
| `clients/research-ui/src/views/OrganizedConflictPanel.test.ts` | create | Render/empty/disabled/error tests |
| `clients/research-ui/src/views/RunOverview.svelte` | modify | Import, tab, render branch |
| `clients/research-ui/src/research/selection.ts` | modify | Add `organized-conflict` view id |

## Task 20: Add six GET conflict routes schemas and app wiring

### Intent

Expose the published snapshot with the same security and cursor discipline as the
existing research surfaces, without adding a new API version.

### Implementation Steps

1. Create `src/api/organized_conflict_schemas.py`:
   - `MAX_PAGE_LIMIT = 500`.
   - `_Strict` with `extra="forbid"`, frozen.
   - `OrganizedConflictSummaryResponse` with episode/plan/interpretation counts,
     classification counts, sustained count, coverage.
   - `OrganizedConflictEpisodeResponse` with `episode_id`, `classification`,
     `start_tick`, `end_tick`, participant/opponent token tuples, `side_count`,
     `hostile_event_count`, `active_window_count`, `reciprocal_window_count`,
     `sustained`, `region_tokens`, `org_ids`, `msoc_ids`.
   - `OrganizedConflictParticipantResponse`.
   - `OrganizedConflictPlanResponse`.
   - `OrganizedConflictInterpretationResponse` with `alignment`.
   - `OrganizedConflictLineageResponse`.
   - Page envelopes with `items`, `next_cursor`, `truncated`.
2. Create `src/api/organized_conflict_cursor.py`:
   - `TTL_SECONDS = 900`.
   - HMAC-SHA256 with a 32-byte minimum key.
   - Payload binds `purpose`, `run_id`, `publication_id`, `digest`,
     `fingerprint`, `after_key`, `expiry`.
   - `encode_organized_conflict_cursor` / `decode_organized_conflict_cursor`.
   - reject wrong purpose, bad signature, expired.
3. Create `src/api/routes/organized_conflict.py`:
   - router prefix `/v1/simulations`, tag `organized-conflict`.
   - `_reader` -> 503 `organized_conflict_disabled` when unset.
   - `_codec` -> 503 `organized_conflict_disabled` when cursor key unset.
   - `_authorize` requires `ApiCapability.SUBJECTIVE_DEBUG`.
   - `_read` maps:
     * `organized_conflict_not_found` -> 404 `organized_conflict_not_found`
     * unknown episode -> 404 `organized_conflict_unknown_episode`
     * unknown plan -> 404 `organized_conflict_unknown_plan`
     * `organized_conflict_cursor_expired` -> 410
     * other port errors -> 400 `organized_conflict_cursor_invalid`
     * artifact errors -> 404 `organized_conflict_not_found`
   - cursor fingerprint/key/next-cursor helpers.
   - Six routes:
     1. `GET /v1/simulations/{run_id}/organized-conflict`
     2. `GET /v1/simulations/{run_id}/organized-conflict/episodes`
     3. `GET /v1/simulations/{run_id}/organized-conflict/episodes/{episode_id}`
     4. `GET /v1/simulations/{run_id}/organized-conflict/plans`
     5. `GET /v1/simulations/{run_id}/organized-conflict/plans/{plan_id}`
     6. `GET /v1/simulations/{run_id}/organized-conflict/interpretations`
4. Wire `src/api/routes/__init__.py`, `src/api/app.py`, and
   `src/api/dependencies.py` exactly like diplomacy: attach reader/codec only
   when both root and cursor key are configured; include the router once.
5. Add tests:
   - exact route set and count = 6;
   - capability required;
   - 503 when root unset;
   - 404 for unknown published record;
   - cursor same binding 200, changed binding 400, expired 410;
   - no `/v2` route and no observer protocol change.

### Required Interfaces and Contracts

```python
router = APIRouter(prefix="/v1/simulations", tags=["organized-conflict"])
ORGANIZED_CONFLICT_ROUTE_COUNT: Final[int] = 6
```

Compatibility: `/v1` only; no `/v2`; no change to Godot or `observer-protocol-v1`.

### Requirement Evidence

- Source: `docs/research-api.md` 242-270 — route/capability/error conventions.
- Source: `src/api/routes/diplomacy.py` 50-422 — implementation pattern.
- Supported combinations: each route; disabled; unknown; cursor same/changed/
  expired; unauthorized.

### Error Handling and Logging

- INFO `organized_conflict_api_disabled` once per app attach when root unset.
- WARN `organized_conflict_api_not_found purpose=%s`.
- DEBUG `organized_conflict_api_page purpose=%s rows=%s`.
- Never log run ids beyond the safe path token, cursors, publication ids, digests,
  episode ids, or tokens.

### Tests

- `tests/unit/test_organized_conflict_api.py`
  - `test_six_get_routes_are_registered`
  - `test_subjective_debug_is_required`
  - `test_unset_root_returns_503_disabled`
  - `test_unknown_episode_and_plan_return_404`
  - `test_cursor_binding_and_expiry`
  - `test_no_v2_routes`
- Command: `uv run pytest tests/unit/test_organized_conflict_api.py -q`

### Acceptance Criteria

- Exactly six GET routes exist.
- All require `SUBJECTIVE_DEBUG`.
- Disabled state is explicit and fail-closed.
- Unknown published records return 404.
- Cursor mismatch is 400 and expiry 410.
- No new API version.

### Verification

- `uv run pytest tests/unit/test_organized_conflict_api.py -q`
- Expected: all pass.

## Task 21: Add the read-only Research UI conflict view

### Intent

Make the published analysis inspectable without adding any write path or derived
authority.

### Implementation Steps

1. Create `clients/research-ui/src/api/organizedConflict.ts`:
   - `CAPABILITY = 'subjective_debug'`.
   - TypeScript models for summary, episode, participant, plan, interpretation,
     lineage, and page envelopes.
   - `base(runId)` -> `/v1/simulations/${runId}/organized-conflict`.
   - Six fetchers with `cursor`/`limit` query parameters.
2. Create `clients/research-ui/src/views/OrganizedConflictPanel.svelte`:
   - local `$state` only; no global store.
   - load summary, episodes, plans, and interpretations in parallel.
   - episode detail and plan detail on selection.
   - render closed labels and counts; no color-coded “good/bad” or “winner”.
   - explicit loading, empty, disabled, and error states.
   - neutral wording: “episode”, “classification”, “participant”, “role”,
     “interpretation”, “alignment”, “coverage”; never “war”, “enemy”, “victory”,
     “defeat”, “legitimate”, “score”.
3. In `RunOverview.svelte`:
   - import the panel;
   - add a `conflict` tab entry and render branch for
     `view === 'conflict'`;
   - ensure a direct URL is reachable (do not repeat the diplomacy routing gap).
4. In `research/selection.ts`:
   - add `'conflict'` to `RESEARCH_UI_VIEWS` and run-scoped views.
5. Add tests:
   - fetch stub for all six paths;
   - summary/episode/plan/interpretation render;
   - empty, disabled, error;
   - neutral labels and absence of score/war/winner text;
   - tab reachability.

### Required Interfaces and Contracts

```ts
const CAPABILITY = 'subjective_debug' as const;
export async function fetchOrganizedConflictSummary(runId: string, signal?: AbortSignal): Promise<OrganizedConflictSummary>;
export async function fetchOrganizedConflictEpisodes(runId: string, cursor?: string, limit?: number): Promise<OrganizedConflictEpisodePage>;
```

Compatibility: Svelte client only; Python never imports the client; the API serves
the prebuilt tree at `/research/`.

### Requirement Evidence

- Source: `clients/research-ui/src/api/diplomacy.ts` 1-294 — client pattern.
- Source: `clients/research-ui/src/views/DiplomacyPanel.svelte` 1-251 — panel
  pattern.
- Source: `docs/research-ui.md` 270-288 — read-only presentation rules.
- Supported combinations: summary/episodes/plans/interpretations; empty;
  disabled; error; direct URL.

### Error Handling and Logging

- UI errors show a safe message and reason code, never raw response bodies.
- No `console.log` of fetched rows.
- Disabled state explains that organized-conflict publication is not configured.

### Tests

- `clients/research-ui/src/views/OrganizedConflictPanel.test.ts`
- Commands:
  - `npx pnpm@10.34.9 test`
  - `npx pnpm@10.34.9 check`
  - `npx pnpm@10.34.9 build`

### Acceptance Criteria

- The panel is reachable from a tab and a direct URL.
- It renders only published tokens, labels, and counts.
- It derives no authority, legitimacy, enforcement, score, winner, or war status.
- Empty/disabled/error states are explicit.

### Verification

- `npx pnpm@10.34.9 test && npx pnpm@10.34.9 check && npx pnpm@10.34.9 build`
- Expected: all pass; build artifact count recorded.

## Phase Risks and Mitigations

- Risk: the UI renders “war” or “winner” language.
  Mitigation: neutral-label tests and a forbidden-word scan.
- Risk: the panel is unreachable like the current diplomacy direct URL.
  Mitigation: tab entry plus direct-URL test.
- Risk: API reads memory instead of the committed store.
  Mitigation: reader dependency only, no analysis import.
- Risk: cursor key reuse across contexts.
  Mitigation: separate `PALIMPSEST_ORGANIZED_CONFLICT_CURSOR_KEY`.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
