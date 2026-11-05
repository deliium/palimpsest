# Phase 6: Read-Only API and Research UI

Plan: [index.md](index.md)
Tasks: 19-20
Depends on: Phase 5

## Objective

Expose treaties and versions through GET-only `/v1` routes that require
`SUBJECTIVE_DEBUG`, fail closed with `diplomacy_disabled`, return 404 for
unknown published records, and bind cursors to the publication. Add a
read-only Research UI treaties view that shows versions, participants,
declarations, recollections, and lineage without deriving authority,
legitimacy, enforcement, or a winner.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/api/routes/diplomacy.py` | `_reader` 46-50; `_authorize` 59-63; `_fingerprint` 80-89; `_cursor_key` 90-115; `_next_cursor` 116-134; `_summary_out` 135-156; six route handlers 180-343 | Exact authorization, cursor, and response pattern for new routes. |
| `src/api/diplomacy_schemas.py` | page/detail/summary models | Add treaty response models without changing existing keys. |
| `src/api/diplomacy_cursor.py` | `DiplomacyCursorCodec` | Purposes and binding come from `DIPLOMACY_CURSOR_PURPOSES`. |
| `src/api/app.py` | `_attach_diplomacy_reader` 353-372; `include_router` 502 | No new app wiring beyond the existing router. |
| `src/infrastructure/settings.py` | `diplomacy_root` 230; `diplomacy_cursor_key` 231; diagnostics 654-660 | No new settings; the same root/cursor key enables treaty reads. |
| `docs/research-api.md` | 242-256 | Route table to extend. |
| `clients/research-ui/src/api/diplomacy.ts` | summary/types/readers 1-160+ | Add treaty types and fetchers. |
| `clients/research-ui/src/views/DiplomacyPanel.svelte` | 1-120+ | Add treaty tabs/rows and version detail. |
| `tests/unit/test_diplomacy_api.py` | 124-240 | Exact route count, capability, cursor, and 404 tests to extend. |
| `clients/research-ui/src/views/DiplomacyPanel.test.ts` | panel tests | Extend read-only treaty rendering tests. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/api/diplomacy_schemas.py` | modify | Add treaty summary/page/detail/version/declaration/recollection/lineage models. |
| `src/api/routes/diplomacy.py` | modify | Add two GET handlers and extend summary output. |
| `src/api/diplomacy_cursor.py` | modify | Accept the two new purposes; no algorithm change. |
| `src/api/app.py` | verify | No new router; confirm the existing reader wiring serves treaties. |
| `docs/research-api.md` | modify later in Task 24 | Document the route table. |
| `clients/research-ui/src/api/diplomacy.ts` | modify | Add treaty types and fetchers. |
| `clients/research-ui/src/views/DiplomacyPanel.svelte` | modify | Add read-only treaties view and version detail. |
| `clients/research-ui/src/views/DiplomacyPanel.test.ts` | modify | Render treaty rows, versions, empty/unavailable/error states. |
| `tests/unit/test_diplomacy_treaty_api.py` | create | Routes, auth, 503/404, cursors, exact count. |

## Task 19: Add GET treaty routes schemas and app wiring

### Intent

Serve treaty records through the established read-only API without adding a
route version, mutation, store, or settings surface. The API must remain unable
to import cognition or analysis.

### Implementation Steps

1. In `src/api/diplomacy_schemas.py`, add:
   - `DiplomacyTreatyOut` with `treaty_id`, `relation_id`, `owner_token`,
     `party_tokens`, `subject_kind`, `current_version_id`, `status`,
     `opened_tick`, `last_tick`, `provenance`.
   - `DiplomacyTreatyVersionOut` with the version fields plus
     `parent_version_ids`, `change_kind`, `status`, `acceptance_basis`,
     `provision_kinds`, `terms_digest`, `record_refs`,
     `institutional_memory_refs`, `effective_tick`, `end_tick`,
     `proposer_party_token`, `proposer_envoy_token`.
   - `DiplomacyTreatyDeclarationOut`, `DiplomacyTreatyRecollectionOut`,
     `DiplomacyTreatyMisrepresentationOut`, and
     `DiplomacyTreatyLineageOut`.
   - `DiplomacyTreatyPageOut` and `DiplomacyTreatyDetailOut` with
     `treaty`, `versions`, `declarations`, `recollections`,
     `misrepresentations`, `lineage`, and `truncated`.
   Extend `DiplomacySummaryOut` with `treaty_count`,
   `treaty_version_count`, `treaty_accepted_count`, and
   `treaty_recollection_count`.
2. In `src/api/routes/diplomacy.py`, add exactly two handlers:
   - `GET /{run_id}/diplomacy/treaties` -> `DiplomacyTreatyPageOut`,
     cursor purpose `"treaties"`, limit `1..MAX_PAGE_LIMIT`.
   - `GET /{run_id}/diplomacy/treaties/{treaty_id}` ->
     `DiplomacyTreatyDetailOut`, no cursor.
   Use `_authorize`, `_reader`, `_read`, `_cursor_key`, `_next_cursor`, and
   `_row_out`. Extend `_row_out` with branches for every new snapshot treaty
   row type, and extend `_summary_out` with the four summary counts. Map
   unknown treaty IDs to 404 with `diplomacy_not_found`.
3. In `src/api/diplomacy_cursor.py`, accept the two new purposes from
   `DIPLOMACY_CURSOR_PURPOSES`. Do not change the signing, expiry, or binding
   algorithm.
4. In `src/api/app.py`, confirm no change is needed: the existing
   `diplomacy_router` and reader already serve the new paths. If the router
   prefix or dependency factory needs an explicit type update, keep it
   metadata-only.
5. In `src/infrastructure/settings.py`, add no settings. The existing
   `PALIMPSEST_DIPLOMACY_ROOT` and `PALIMPSEST_DIPLOMACY_CURSOR_KEY` govern
   treaty reads too.
6. Preserve the existing six V4-10 routes exactly. The diplomacy route count
   becomes eight, and `tests/unit/test_diplomacy_api.py::test_exactly_six_get_routes`
   is renamed/updated to `test_exactly_eight_get_routes`.
7. Ensure the API imports neither `agents.cognition.diplomacy` nor
   `analysis`; it consumes the read port only.
8. Return 503 `diplomacy_disabled` when the reader is unset, 400
   `diplomacy_cursor_invalid` for a changed binding, and 410 for an expired
   cursor, using the existing error mapping.

### Required Interfaces and Contracts

- Exactly eight GET routes under `/v1/simulations/{run_id}/diplomacy`:
  summary, relations page, relation detail, instruments page, instrument
  detail, lineage page, treaties page, treaty detail.
- All require `SUBJECTIVE_DEBUG`; no write method exists.
- Unknown published treaty/version -> 404 `diplomacy_not_found`.
- Unconfigured root -> 503 `diplomacy_disabled`.
- Cursor binding includes run, publication, digest, purpose, and filters.
- Response rows expose tokens, record IDs, and closed values only. No raw
  agent IDs, free-text terms, frame bodies, or private anchors.
- No `/v2` route, no `observer-protocol-v2`, no command, event, or migration.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` "read-only surfaces" and V4-10 API seam.
- `docs/configuration.md` 455-465: existing diplomacy settings, no new keys.
- `docs/research-api.md` 242-256: route contract to extend.
- Original Request "Track versions and lineage" requires a version-visible
  read API.

### Error Handling and Logging

- Log `treaty_api_read purpose=<closed> rows=%s` at DEBUG with counts only.
- Log 503/404/400/410 at WARN with stable codes only.
- Never log run IDs, treaty IDs, version IDs, tokens, terms digests, or
  record anchors.

### Tests

`tests/unit/test_diplomacy_treaty_api.py`:

- Assert exactly eight GET routes and no non-GET route.
- Assert `SUBJECTIVE_DEBUG` is required for both treaty routes.
- Assert 503 `diplomacy_disabled` when the reader is unset.
- Assert 404 for unknown treaty ID and unknown run.
- Assert treaty page and detail return tokens/versions/declarations/
  recollections/lineage plus derived `status`/`acceptance_basis` labels.
- Assert cursor reuse works for the same run/publication/digest/purpose; a
  changed run, publication, digest, or filter yields 400; expiry yields 410.
- Assert response JSON has no raw agent IDs, free-text terms, score, truth,
  legitimacy, or enforcement keys.
- Assert the API module imports neither cognition nor analysis.

### Acceptance Criteria

- Two GET treaty routes are added; total diplomacy GET routes are eight.
- Authorization, disabled state, 404, cursor binding, and expiry match V4-10.
- Responses are token-only and read-only.
- No new settings, router version, or mutation path exists.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_api.py tests/unit/test_diplomacy_api.py -q`
- Expected: all tests pass.

## Task 20: Add the read-only Research UI treaties view

### Intent

Let researchers inspect treaty records, versions, participants, declarations,
recollections, and lineage without the UI deriving authority, legitimacy,
enforcement, a score, or a winner.

### Implementation Steps

1. In `clients/research-ui/src/api/diplomacy.ts`, add types matching Task 19:
   `DiplomacyTreaty`, `DiplomacyTreatyVersion`,
   `DiplomacyTreatyDeclaration`, `DiplomacyTreatyRecollection`,
   `DiplomacyTreatyMisrepresentation`, `DiplomacyTreatyLineage`,
   `DiplomacyTreatyPage`, `DiplomacyTreatyDetail`.
   Extend `DiplomacySummary` with the four treaty counts.
2. Add `getDiplomacyTreaties(runId, cursor?)` and
   `getDiplomacyTreaty(runId, treatyId)` using `apiFetch` with
   `capability: 'subjective_debug'`.
3. In `DiplomacyPanel.svelte`:
   - load treaty page alongside relations/instruments/lineage;
   - add a "Treaties" section with columns: subject kind, participants count,
     current version, derived status label, opened, last;
   - selecting a treaty loads detail and shows versions in order, each with
     change kind, derived status/acceptance basis, participant tokens,
     provision kinds, record anchor count, institutional-memory anchor count,
     and lineage parents;
   - show declarations and recollections as read-only rows;
   - show recollection alignment only if the server exposes it in a future
     document; do not compute it client-side;
   - show empty (`no treaty records`), unavailable (`diplomacy_disabled`),
     and error states explicitly.
4. Add no aggregation, ranking, winner, legitimacy, enforcement, or score.
   Do not sort parties by importance; preserve server order.
5. Update `DiplomacyPanel.test.ts` to cover:
   - treaty rows render;
   - version detail renders parent/child lineage;
   - declarations/recollections render;
   - disabled/empty/error states;
   - no `score`, `winner`, `legitimate`, `enforced`, or `truth` text.
6. Do not change the Godot client, observer protocol, layout, capabilities, or
   `/version`.

### Required Interfaces and Contracts

- The panel consumes only the two GET routes plus the existing summary.
- It never computes authority, recognition, alignment, legitimacy, or a
  composite.
- It never writes, commands, or mutates.
- It displays `terms_digest` only as an opaque digest or hides it; it does not
  translate it into terms.
- It renders participant and envoy tokens as opaque labels.
- Version lineage is displayed as parent/child edges, not as a score.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` "read-only clients" and V4-10 Research UI seam.
- `docs/research-ui.md` 270-277.
- Original Request "Track versions and lineage" and "Later generations may
  remember ... reinterpret ... ignore ... renew".

### Error Handling and Logging

- UI errors use the existing `ApiClientError.code` and display stable labels.
- No console logging of treaty IDs, tokens, terms, or payloads.

### Tests

`clients/research-ui/src/views/DiplomacyPanel.test.ts` additions:

- Mock summary + treaties page + treaty detail; assert treaty list, version
  list, derived status labels, lineage, declarations, recollections.
- Assert `diplomacy_disabled` renders the unavailable state.
- Assert empty treaty page renders the empty state.
- Assert no authority/score/winner/enforcement text is present.
- Assert no fetch outside the diplomacy routes.

### Acceptance Criteria

- The Research UI has a read-only treaties view.
- Versions and lineage are visible.
- No authority, legitimacy, score, winner, or enforcement is derived.
- Godot and observer contracts are untouched.

### Verification

- `cd clients/research-ui && pnpm test && pnpm check && pnpm build`
- Expected: tests, type/Svelte checks, and build pass. If `pnpm` is absent,
  record the lane `unexecuted` with that prerequisite; never skip-pass.

## Phase Risks and Mitigations

- Risk: Adding routes silently changes the V4-10 route-count contract.
  Mitigation: update the count test to eight and document the addition.
- Risk: The API imports cognition or analysis to derive status.
  Mitigation: consume only the read port; AST test forbids both imports.
- Risk: The UI computes alignment or a winner.
  Mitigation: render server fields only; test for forbidden text and absence
  of client-side aggregation.
- Risk: A cursor is reused across a different publication.
  Mitigation: existing binding includes run, publication, digest, purpose,
  filters; tests cover each change.

## Phase Completion Checklist

- Every Task 19-20 acceptance criterion is met.
- Exactly eight GET diplomacy routes exist.
- Authorization, disabled state, 404, and cursor behavior match V4-10.
- The Research UI is read-only and derives no authority or score.
- Godot/observer/`/version` are untouched.
- `index.md` checkboxes are updated only after verification passes.
