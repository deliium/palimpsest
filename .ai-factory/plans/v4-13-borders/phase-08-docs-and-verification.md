# Phase 8: Documentation and Final Verification

Plan: [index.md](index.md)
Tasks: 26-27
Depends on: Phase 7 / Tasks 23-25

## Objective

Document the verified border contract, the four layers, the activation rule, the
`bdr_v1` frame, the snapshot/store/routes/UI/Godot surfaces, and the exact pins.
Then audit the verification receipt and certify only when every required lane is
`executed_passed`.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `docs/analysis-metrics.md` | catalog 7-41; spatial 31-33; conflict 604-611 | Current 172 pin and metric documentation |
| `docs/research-api.md` | runner/owned flags 88; diplomacy 242-270; organized conflict 272-280 | Route documentation pattern |
| `docs/research-ui.md` | 45; 270-296 | UI panel documentation |
| `docs/godot-civilization-overlays.md` | evidence classes 15-24; class rules 26-41; sidecars 43-58 | Overlay documentation |
| `docs/godot-observer.md` | 109 | Subjective/analytical overlay precedent |
| `docs/configuration.md` | 316-326; 468-478 | Settings documentation pattern |
| `docs/architecture.md` | 215-220; V4 sections | Authority and V4 seam documentation |
| `docs/v4-architecture.md` | 342-378 | V4-10/V4-11/V4-12 seam precedent |
| `docs/social-communication.md` | 46-48 | Existing territorial-claim documentation |
| `.ai-factory/ARCHITECTURE.md` | "Current baseline through V4-12" 177-207; V4-12 seam 907-941 | Authoritative architecture baseline and capability ownership |
| `.ai-factory/DESCRIPTION.md` | V4-12 paragraph 450-472 | Authoritative project-state summary used by later plans |
| `README.md` | documentation index | Must link the new contract |
| `tests/unit/test_organized_conflict_docs.py` | parity-test pattern | Closest docs-test template |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `docs/borders-and-claims.md` | create | Canonical border contract |
| `docs/analysis-metrics.md` | modify | Four families, catalog 176, historical notes intact |
| `docs/research-api.md` | modify | Six routes, auth, errors, cursors |
| `docs/research-ui.md` | modify | Four-layer panel |
| `docs/godot-civilization-overlays.md` | modify | Four border overlay kinds and three-class mapping |
| `docs/godot-observer.md` | modify | Border overlay toggle/clear behavior |
| `docs/configuration.md` | modify | `PALIMPSEST_BORDERS_*` settings |
| `docs/architecture.md` | modify | V4-13 seam and authority statement |
| `docs/v4-architecture.md` | modify | V4-13 seam section |
| `docs/social-communication.md` | modify | Link border beliefs to the existing territorial-claim section |
| `README.md` | modify | Link the new contract |
| `docs/organizations.md` | modify | Note the border sidecar and read-only anchors |
| `docs/diplomacy.md` | modify | Note optional treaty anchors; no treaty rewrite |
| `.ai-factory/ARCHITECTURE.md` | modify | V4-13 baseline, 176 families, seam, unchanged ownership |
| `.ai-factory/DESCRIPTION.md` | modify | V4-13 project-state paragraph and pins |
| `tests/unit/test_borders_docs.py` | create | Documentation parity for the new contract and counts |
| `index.md` | modify | Final receipt and certification outcome |

## Task 26: Execute the documentation checkpoint

### Intent

Make the documented behavior match the code exactly. The docs must state what
border beliefs control, what they never control, how the four layers differ, and
every count/pin. Historical revision statements stay intact; current 172 pins
move to 176.

### Implementation Steps

1. Create `docs/borders-and-claims.md` with these sections:
   - **What it is** — one owner's belief about a set of logical `EntityId`
     locations; no grid, polygon, country, border object, or objective owner.
   - **Activation** — `runner-config-v56` + `v4_capability_flags.organizations` +
     agent `territorial_claim_mode=DETERMINISTIC`; legacy v15/v44/v55 unchanged;
     no new flag/context/runner key/v57.
   - **What it controls** — domain claims, boundary recognitions, access
     expectations, agreements, disputes, notices, and local boundary edges.
   - **What it never controls** — world state, admission, perception, memory,
     prompts, stop selectors, observer semantics, Godot physics, commands,
     permissions, obligations, truth, sovereignty, legitimacy, enforcement,
     winner, or score.
   - **Location sets and boundaries** — sorted exact locations, 1-8 per domain,
     observed adjacency only, no grid/region-to-border conversion, unobserved is
     unresolved.
   - **The five row families** — domain claim, recognition, access expectation,
     agreement, dispute; statuses and caps.
   - **`bdr_v1`** — exact 256-character/8-relation frame, acts, speaker binding,
     malformed/oversize drop behavior.
   - **Four analysis layers** — physical control, subjective claim, agreement,
     analytical control pattern; what each contains and what it never means.
   - **Detection** — overlap/dispute/recognition/control-pattern precedence; no
     winner/score.
   - **Snapshot/store/API/UI/Godot** — `borders-snapshot-v1` with a required
     summary and candidate row family, `borders-store-v1`, six GET routes,
     four-layer panel, four overlay kinds.
   - **Non-goals** — no objective CountryOwner, `world.at_war`, border
     enforcement, access control, grid, polygon, territory registry, new
     event/command/write pair/migration, `/v2`, or `observer-protocol-v2`.
2. Update `docs/analysis-metrics.md`:
   - Append the four families after the organized-conflict families (604-611).
   - State the catalog moved 172 -> 176.
   - Correct the treaty-family sentence at 592-594 from "164 to 172" to
     "164 to 168" so it agrees with the organized-conflict "168 to 172"
     statement; preserve both historical revisions.
   - Add a note that physical control is derived and not ownership.
3. Update `docs/research-api.md`:
   - Add the six `/v1/simulations/{run_id}/borders` routes.
   - `SUBJECTIVE_DEBUG` for all six.
   - 503 `borders_disabled`, 404 `borders_publication_not_found`/
     `borders_record_not_found`, 400/410 cursor codes.
   - `layer=physical|analytical|all` on the control route.
4. Update `docs/research-ui.md`:
   - Add the Borders and claims panel; four sections and epistemic badges.
   - Read-only; no authority/legitimacy/score/winner.
5. Update `docs/godot-civilization-overlays.md` and `docs/godot-observer.md`:
   - Four border overlay kinds and their evidence-class mapping.
   - Agreement is a distinct subjective overlay, not a fourth evidence class.
   - Tokens are never in URLs; overlay toggles are default-off.
6. Update `docs/configuration.md`:
   - `PALIMPSEST_BORDERS_ROOT`, `PALIMPSEST_BORDERS_CURSOR_KEY`.
   - Opt-in, post-completion, atomic store, quotas.
7. Update `docs/architecture.md` and `docs/v4-architecture.md`:
   - Add the V4-13 seam after V4-12.
   - State no new context/flag/schema/command/event/write pair/route version/
     migration; `organizations` is deepened.
   - Update the baseline pin table to 176 metric families and six border routes.
8. Update `.ai-factory/ARCHITECTURE.md`:
   - Rename "Current baseline through V4-12" to "through V4-13".
   - Add the four V4-13 families to the 176-family row.
   - Add a V4-13 seam section after V4-12: location-set beliefs, observed
     boundaries, `bdr_v1`, four layers, snapshot/store/routes, and the unchanged
     ownership split (five owned / seven unowned V4 flags).
   - Keep `runner-config-v56`, 43 commands, 73 observer semantic types, replay
     v22, codec v20, Alembic `0017`, and `observer-protocol-v1` unchanged.
9. Update `.ai-factory/DESCRIPTION.md`:
   - Add a V4-13 paragraph after V4-12 with the same seam, activation, four
     families, snapshot/store, six routes, Research UI, Godot overlays, and
     pins.
   - Do not claim a new flag, context, runner schema, command, event, write
     pair, route version, or migration.
10. Update `docs/social-communication.md`, `docs/organizations.md`, and
    `docs/diplomacy.md`:
    - Link to the new contract.
    - State border claims are beliefs, not permissions; organization anchors are
      read-only; treaty anchors are optional and never rewritten.
11. Update `README.md` documentation index with the new contract.
12. Create `tests/unit/test_borders_docs.py` mirroring
    `tests/unit/test_organized_conflict_docs.py`:
    - canonical doc exists and is linked from README;
    - 176 family count and the four family names;
    - the corrected treaty 164 -> 168 statement plus the organized-conflict
      168 -> 172 statement;
    - six route paths and capability/error codes;
    - four overlay kinds and the three-class mapping;
    - `PALIMPSEST_BORDERS_ROOT`/`PALIMPSEST_BORDERS_CURSOR_KEY`;
    - `.ai-factory/ARCHITECTURE.md` and `.ai-factory/DESCRIPTION.md` contain the
      V4-13 seam and 176-family pin;
    - no forbidden authority/score/sovereignty wording;
    - historical 172 statements remain only in revision notes.
13. Run the docs parity tests and the stale-pin sweep:
    - `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_docs.py tests/unit/test_*_docs.py -q`
    - `rg -n "172" docs README.md .ai-factory/ARCHITECTURE.md \
      .ai-factory/DESCRIPTION.md tests src/analysis/specifications.py`
    - classify each match as current pin or historical statement; update current
      pins only.
14. Verify no doc claims a capability the code does not have: no enforcement,
    no access grant, no objective border object, no CountryOwner, no grid, no
    territorial registry.

### Required Interfaces and Contracts

- `docs/borders-and-claims.md` is the canonical contract.
- `docs/analysis-metrics.md` documents exactly 176 families and the four new
  ones.
- `docs/research-api.md` documents exactly six routes.
- `docs/research-ui.md` documents the four-layer panel.
- `docs/godot-civilization-overlays.md` documents four overlay kinds on three
  evidence classes.
- Every count matches the code.
- Historical revision statements remain unchanged.

### Requirement Evidence (when reconciliation applies)

- Source: Plan Settings — docs yes; Original Request — four-layer distinction.
- Source: `.ai-factory/ARCHITECTURE.md` — current baseline pin table.
- Source: V4-12 docs checkpoint precedent.
- Supported combinations: every documented activation/route/overlay matches a
  test.

### Error Handling and Logging

- Documentation tests fail on missing links, stale current pins, or forbidden
  claims.
- No runtime logging change.
- If a doc count cannot be reconciled, stop and fix the code or the doc; do not
  weaken the test.

### Tests

- `tests/unit/test_borders_docs.py`
- Commands:
  - `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_docs.py tests/unit/test_*_docs.py -q`
  - `rg -n "172" docs README.md tests src/analysis/specifications.py`
- Expected: docs tests pass; current pins are 176; historical statements remain.

### Acceptance Criteria

- Canonical contract exists and is linked from README.
- Four families, six routes, four overlays, and settings are documented.
- Every count matches the code.
- No overclaim or authority language exists.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_docs.py tests/unit/test_*_docs.py -q`
- `rg -n "172" docs README.md tests src/analysis/specifications.py`
- Expected: pass; only historical 172 statements remain.

## Task 27: Perform final V4-13 verification

### Intent

Audit the receipt, re-run the decisive gates, and certify only if every required
lane is `executed_passed`. A missing prerequisite leaves the lane `unexecuted`
and blocks certification; it is never a skip-pass.

### Implementation Steps

1. Re-run the focused suite and the boundary suite:
   ```bash
   uv run --frozen --python 3.12.14 pytest \
     tests/unit/test_borders_*.py \
     tests/unit/test_borders_e2e.py \
     tests/architecture/test_borders_boundaries.py -q
   ```
2. Re-run static gates:
   ```bash
   uv run --frozen --python 3.12.14 ruff check src tests
   uv run --frozen --python 3.12.14 mypy src tests
   uv run --frozen --python 3.12.14 lint-imports
   ```
3. Re-run docs parity:
   ```bash
   uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_docs.py tests/unit/test_*_docs.py -q
   ```
4. Audit `index.md`:
   - every Task 1-27 checkbox is checked with verified evidence;
   - the verification receipt has exactly one state per required lane;
   - no `unexecuted` lane without a prerequisite;
   - the pins in the index match the code and docs (176 families, 43 commands,
     73 observer semantic types, replay v22, codec v20, Alembic 0017, 14
     contexts, 12 flags, 5 owned flags, six border routes).
5. Confirm:
   - no `runner-config-v57`, new V4 flag, new context, root field, per-agent
     runner key, command, event, write pair, observer semantic type, `/v2` route,
     `observer-protocol-v2`, or SQL migration exists;
   - no `class Border`, `CountryOwner`, `Sovereignty`, `TerritoryRegistry`,
     `BorderRegistry`, `BorderAuthority`, `WinnerOracle`, or `LegitimacyOracle`
     exists;
   - no objective world/observer field contains `borders`, `country_owner`,
     `sovereign`, `territory_owner`, or `controller`;
   - no border helper constructs, submits, resolves, or blocks a command;
   - no raw ids/frame bodies/evidence bodies are published;
   - the roadmap is not edited.
6. Confirm the Godot/UI/API surfaces match the docs and tests.
7. Set the certification outcome:
   - `certified` only when every required lane is `executed_passed`;
   - otherwise `not certified` with the exact unexecuted/failed lane and
     prerequisite.
8. Do not commit, edit the roadmap, close M8, or create a branch in this
   planning invocation. The implementation checkpoint commits are suggestions
   in `index.md`; the implementing session decides whether to commit.

### Required Interfaces and Contracts

- The receipt is the single certification source.
- Required lanes: unit+architecture with coverage, focused V4-13, in-process E2E,
  V1-V4 regression, docs parity, Ruff, Mypy, import-linter, integration,
  integration-scale, Compose config, Compose/browser, Godot, benchmark/scale,
  Research UI tests/check/build.
- `unexecuted` blocks certification.
- No pin is weakened to make a lane pass.

### Requirement Evidence (when reconciliation applies)

- Source: Plan Settings — full strategy; Definition of Done in `index.md`.
- Source: V4-11/V4-12 verification precedents.
- Supported combinations: every lane recorded; a failure/unexecuted is honest.

### Error Handling and Logging

- A failed lane records the command, safe error code, and whether it is
  reproducible.
- A missing prerequisite records the prerequisite, not a skip-pass.
- No credentials, DSNs, tokens, or payloads in the receipt.

### Tests

- This is the final verification run; it does not add tests.
- Commands: the focused/static/docs lanes above plus the full qualification lanes
  from Task 25.
- Expected: all required lanes `executed_passed` for certification.

### Acceptance Criteria

- All 27 tasks have verified completion evidence.
- The receipt is complete and truthful.
- No forbidden surface exists.
- The final certification outcome is explicit.

### Verification

- Read `index.md` from top to bottom.
- `git status --short` shows only intended implementation/docs/plan files; no
  `.ai-factory/ROADMAP.md` change.
- Expected: consistent plan, receipt, and workspace state.

## Phase Risks and Mitigations

- Risk: docs drift from code after the count sweep.
  Mitigation: Task 26 runs docs parity and a stale-pin sweep; Task 27 re-runs.
- Risk: a required lane is unexecuted but the plan claims certification.
  Mitigation: Task 27 sets `not certified` and names the prerequisite.
- Risk: historical 172 statements are rewritten as current pins.
  Mitigation: Task 26 classifies every match before editing.
- Risk: a forbidden surface slips in during docs/verification edits.
  Mitigation: Task 27 re-runs the boundary suite.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass or are truthfully recorded as unexecuted.
- `index.md` task checkboxes and receipt are updated immediately after verified
  completion.
