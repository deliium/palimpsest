# Phase 8: Documentation and Final Verification

Plan: [index.md](index.md)
Tasks: 26-27
Depends on: Phases 1-7 / Tasks 1-25

## Objective

Document the verified migration-displacement contract, update every current pin,
and perform the final V4-14 audit. The roadmap remains owned by
`$aif-roadmap`.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `docs/borders-and-claims.md` | canonical V4-13 contract | Exact documentation pattern |
| `docs/analysis-metrics.md` | metric catalog and family sections | Pin sweep target |
| `docs/research-api.md` | route/status tables | API documentation target |
| `docs/research-ui.md` | panel list | UI documentation target |
| `docs/godot-civilization-overlays.md` | overlay kinds | Godot documentation target |
| `docs/godot-observer.md` | observer protocol and overlays | Godot documentation target |
| `docs/v4-architecture.md` | V4 seam history | Architecture documentation target |
| `docs/regions-migration.md` | existing migration contract | Canonical extension target |
| `docs/organizations.md` | owned organizations context | Deepening target |
| `docs/social-communication.md` | bounded speech frames | `mdp_v1` target |
| `README.md` | documentation index | Landing page link |
| `.ai-factory/ARCHITECTURE.md` | baseline through V4-13 | Move baseline through V4-14 |
| `.ai-factory/DESCRIPTION.md` | V4-13 project state | Record V4-14 state |
| `tests/unit/test_borders_docs.py` | documentation parity pattern | Test shape to mirror |
| `tests/unit/test_*_docs.py` | current pin assertions | Pin-sweep target |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `docs/migration-displacement.md` | create | Canonical V4-14 contract |
| `docs/analysis-metrics.md` | modify | Four families; catalog 180 |
| `docs/research-api.md` | modify | Six routes and statuses |
| `docs/research-ui.md` | modify | Migration panel |
| `docs/godot-civilization-overlays.md` | modify | Four overlay kinds |
| `docs/godot-observer.md` | modify | Overlay behavior; protocol unchanged |
| `docs/v4-architecture.md` | modify | V4-14 seam |
| `docs/regions-migration.md` | modify | Extended migration contract |
| `docs/organizations.md` | modify | Deepened context |
| `docs/social-communication.md` | modify | `mdp_v1` |
| `docs/configuration.md` | modify | Settings and feature gates |
| `docs/architecture.md` | modify | Authority boundaries |
| `README.md` | modify | Documentation index link |
| `.ai-factory/ARCHITECTURE.md` | modify | Baseline through V4-14 |
| `.ai-factory/DESCRIPTION.md` | modify | V4-14 project state |
| `tests/unit/test_migration_displacement_docs.py` | create | Documentation parity |
| `index.md` | modify | Final verification receipt |

## Task 26: Execute the documentation checkpoint

### Intent

Document what migration beliefs control, what they never control, how the four
layers differ, how `mdp_v1` works, how routes are observed, and every current
count. The docs sweep must distinguish current pins from historical revision
statements.

### Implementation Steps

1. Create `docs/migration-displacement.md` as the canonical contract:
   - **Purpose and authority**: owner-scoped beliefs, no objective migration;
   - **Activation**: v56 + `organizations` + `multi_polity_migration` +
     deterministic regional migration;
   - **Vocabulary**: six row families, cause kinds and sources, route contract,
     cluster bases, integration domains and statuses, wave observation;
   - **Physical movement**: existing `Move`/`Transport`/`Flee`; no teleport, no
     new command;
   - **`mdp_v1`**: 13 semantic fields, 14 parts, 256 characters, 4 relations,
     delivery provenance, speaker binding;
   - **Update order**: the exact eleven steps;
   - **Four layers**: objective movement, subjective cause, analytical wave,
     integration outcome; hard leakage guard;
   - **Waves and no telepathy**: independent movements, same-root suppression,
     no shared ledger;
   - **Displacement-like classification**: closed labels, independent bases,
     researcher-only, not a refugee/asylum/legal/social status;
   - **Integration outcomes**: closed labels, counts/durations/coverage, no
     wellbeing or assimilation score;
   - **Caps and notices**;
   - **Snapshot, store, routes, UI, Godot**;
   - **What it never controls**: world state, admission, permission, truth,
     refugee status, enforcement, legitimacy, score, winner, sovereignty.
2. Update `docs/analysis-metrics.md`:
   - add the four families at positions 177-180;
   - document every value key and denominator;
   - set the current catalog count to 180;
   - preserve historical revision statements and the first-176 order.
3. Update `docs/research-api.md`:
   - add the six GET routes under
     `/v1/simulations/{run_id}/migration`;
   - document `SUBJECTIVE_DEBUG`, 503, 404, 400, 410, 500, page limit, filters,
     and the six cursor purposes;
   - state that responses contain tokens only.
4. Update `docs/research-ui.md`:
   - add the Migration and displacement panel;
   - document the four sections and four badges;
   - state the analytical caveat and the forbidden refugee/asylum labels.
5. Update `docs/godot-civilization-overlays.md` and `docs/godot-observer.md`:
   - add the four overlay kinds and their evidence-class mapping;
   - state that the protocol, capabilities, `/version`, and three-class evidence
     model are unchanged.
6. Update `docs/v4-architecture.md`:
   - record V4-14 as a deepening of `organizations` and the V3 migration seam;
   - record 176 -> 180 and the new snapshot/store/routes;
   - keep V4-13 historical statements intact.
7. Update `docs/regions-migration.md`, `docs/organizations.md`,
   `docs/social-communication.md`, `docs/configuration.md`, and
   `docs/architecture.md`:
   - link the canonical contract;
   - document the activation gate, `mdp_v1`, settings, and authority boundaries.
8. Update `README.md` with a link to `docs/migration-displacement.md`.
9. Update `.ai-factory/ARCHITECTURE.md`:
   - move the baseline through V4-14;
   - add the V4-14 seam section;
   - set metric families to 180;
   - keep capability ownership at 5 owned / 7 unowned.
10. Update `.ai-factory/DESCRIPTION.md` with the V4-14 project-state paragraph.
11. Sweep current pins:
    - `rg -n "\b176\b" docs tests src .ai-factory` and classify each match as
      current or historical;
    - update current pins to 180;
    - keep historical V4-13 "172 -> 176" statements unchanged;
    - keep the first-176 family order and digests unchanged.
12. Create `tests/unit/test_migration_displacement_docs.py`:
    - canonical doc exists and links from README;
    - four families and 180 are present;
    - six routes and six purposes are present;
    - panel and four overlays are present;
    - no `Refugee` status label or score claim;
    - docs mention owner-only authority and the four layers;
    - current pin guard passes while historical statements remain.
13. Run the existing `test_*_docs.py` suite; update only current pin assertions.

### Required Interfaces and Contracts

- `docs/migration-displacement.md` is the canonical contract.
- Every documented count matches the code.
- Historical revision statements are not rewritten as current pins.
- No doc claims prevalence, prediction, refugee status, wellbeing, or a
  composite score.
- `.ai-factory/ARCHITECTURE.md` and `.ai-factory/DESCRIPTION.md` are updated;
  `.ai-factory/ROADMAP.md` is not.

### Requirement Evidence (when reconciliation applies)

- Source: Plan Settings — mandatory `$aif-docs` checkpoint.
- Source: Original Request — track origin, route, destination, cause evidence,
  clusters, integration outcomes, waves without telepathy.
- Source: V4-13 docs checkpoint precedent.
- Supported combinations: current vs historical pin; canonical link; each
  surface; each is tested.

### Error Handling and Logging

- Documentation commands log only file counts and status.
- A stale pin is a test failure with the file and line.
- No doc contains a token, credential, DSN, prompt, memory, or payload.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_docs.py tests/unit/test_*_docs.py -q`
- Expected: all pass.

### Acceptance Criteria

- The canonical contract exists and is linked.
- Every current pin is 180; historical statements remain.
- The docs state what migration beliefs control and never control.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_docs.py tests/unit/test_*_docs.py -q`
- `rg -n "\b176\b" docs tests src .ai-factory` — expected: historical statements only, no current pin.
- Expected: pass.

## Task 27: Perform final V4-14 verification

### Intent

Audit the completed bundle, pins, receipts, and repository state. Final
verification does not edit the roadmap or close M8; it certifies only V4-14.

### Implementation Steps

1. Confirm every Task 1-26 checkbox in `index.md` has verified evidence and
   every linked phase file exists.
2. Confirm the bundle integrity:
   - one `<!-- aif:plan-mode:ultra -->` marker;
   - every Phase Index link resolves;
   - every Task N maps to exactly one phase section;
   - no orphan phase file;
   - no phase file contains task checkboxes.
3. Confirm the compatibility pins:
   - 180 metric families; first 176 unchanged;
   - 43 commands; 73 observer semantic types;
   - replay v22 / codec v20;
   - Alembic `0017` with no `0018`;
   - 14 V4 contexts / 12 flags / 5 owned / 7 unowned;
   - `/v1`, `observer-protocol-v1`, `observer-layout-v1`;
   - six migration GET routes and six cursor purposes;
   - `migration-displacement-snapshot-v1` and
     `migration-displacement-store-v1`;
   - no `runner-config-v57`, no new flag, no new command/event/write pair/codec/
     `/v2` route/migration.
4. Confirm authority claims:
   - no `WorldEngine`, perception, admission, stop selector, memory, prompt,
     observer semantic, or Godot physics reads a migration ledger;
   - no migration helper returns, constructs, submits, resolves, or blocks an
     `AgentCommand`;
   - no peer ledger is read;
   - no `org-`/`msoc-` identity is minted, renamed, split, merged, or dissolved;
   - no `Refugee` category, score, or truth field exists.
5. Confirm the verification receipt in `index.md`:
   - every required lane has exactly one state;
   - every `unexecuted` lane has a prerequisite;
   - certification is `not certified` if any required lane is unexecuted or
     failed;
   - no skip is reported as a pass.
6. Run the final static gates:
   - `uv run --frozen --python 3.12.14 ruff check src tests`
   - `uv run --frozen --python 3.12.14 mypy src tests`
   - `uv run --frozen --python 3.12.14 lint-imports`
7. Confirm `git status --short` contains only V4-14 implementation/docs/test
   paths and no `.ai-factory/ROADMAP.md` modification.
8. Record the final outcome in `index.md`:
   - `Certification outcome: certified` only if every required lane passed;
   - otherwise `not certified` with the blocking lanes.
9. Do not edit `.ai-factory/ROADMAP.md`; `$aif-roadmap` owns M8 registration and
   closure.

### Required Interfaces and Contracts

- Final verification is read-only except for `index.md` receipt updates.
- A missing or contradictory pin is a failure.
- A roadmap edit is a failure.
- A task checkbox without evidence is a failure.
- An `unexecuted` required lane blocks certification.

### Requirement Evidence (when reconciliation applies)

- Source: Plan Settings — explicit complete required-gate certification.
- Source: `.ai-factory/ARCHITECTURE.md` — versioned extension contract.
- Source: V4-13 final-verification precedent.

### Error Handling and Logging

- Record only safe status/count metadata.
- Never log tokens, payloads, prompts, credentials, DSNs, or bodies.
- A failure names the path, pin, or lane only.

### Tests

- The final audit commands in Steps 6-7.
- Expected: all pass or a truthful `not certified` receipt.

### Acceptance Criteria

- The bundle is internally consistent.
- Every pin and authority claim is verified.
- The roadmap is untouched.
- Certification honestly reflects the receipt.

### Verification

- `uv run --frozen --python 3.12.14 ruff check src tests`
- `uv run --frozen --python 3.12.14 mypy src tests`
- `uv run --frozen --python 3.12.14 lint-imports`
- `git status --short`
- Expected: pass; no roadmap modification.

## Phase Risks and Mitigations

- Risk: a current pin is confused with a historical statement.
  Mitigation: Task 26 classifies every `176` match before editing and preserves
  historical V4-13 statements.
- Risk: docs claim refugee status or a score.
  Mitigation: Task 26 tests forbidden labels and the analytical caveat.
- Risk: final verification certifies despite an unexecuted required lane.
  Mitigation: Task 27 blocks certification and records the prerequisite.
- Risk: the roadmap is edited during verification.
  Mitigation: Task 27 asserts `git status` has no roadmap change.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
