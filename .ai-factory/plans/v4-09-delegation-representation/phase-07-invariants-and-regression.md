# Phase 7: Invariants, End-to-End Representation, and Regression

Plan: [index.md](index.md)
Tasks: 20-22
Depends on: Tasks 2-19

## Objective

Prove every authority claim with executable checks: no representation oracle, no
command path, no world read, no peer-ledger read, no truth leakage, exact version
pins; exercise the full path from speech to API on the real runner; and record an
honest three-state qualification receipt.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `tests/architecture/test_evidence_testimony_boundaries.py` | pins 256-317 | Boundary suite template |
| `tests/unit/test_evidence_testimony_physical_distinction.py` | contested vs impossible command | Physical distinction template |
| `tests/integration/test_evidence_testimony_e2e.py` | run → harvest → publish → store → API | E2E template |
| `tests/unit/test_evidence_testimony_determinism.py` | ordering/no RNG | Determinism template |
| `tests/architecture/test_v4_architecture_invariants.py` | 160-200 | Registry pins to extend |
| `docs/development.md` | verification commands | Lane definitions |
| `tests/compose/acceptance.py` | Compose/browser lane | Qualification prerequisite |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `tests/architecture/test_delegation_representation_boundaries.py` | modify | Full authority and pin suite |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | V4-09 ownership case |
| `tests/unit/test_delegation_representation_physical_distinction.py` | create | Contested vs impossible command |
| `tests/integration/test_delegation_representation_e2e.py` | create | Real-run E2E |
| `tests/unit/test_evidence_testimony_catalog.py` | modify | Count 160 and first-160 digest |
| `tests/unit/test_evidence_testimony_boundaries.py` | modify | Add representation route/cursor pins |

## Task 20: Add the representation boundary and determinism suite

### Intent

The suite is the executable contract. It must fail if any later change turns a
belief into an authority, adds a command/event/migration, reads a peer ledger, or
leaks an objective comparison into cognition.

### Implementation Steps

1. Extend `tests/architecture/test_delegation_representation_boundaries.py`
   with these groups:
   - **Ownership:** recursive foreign-owner rejection; no peer ledger parameter
     on `apply_representation_update`; prepared sidecars must share the owner.
   - **No oracle:** AST scan of
     `agents/cognition/delegation_representation*.py` for forbidden names
     (`TruthEngine`, `LegitimacyOracle`, `RepresentationAuthority`, `Verifier`,
     `Authenticator`, `Winner`) and forbidden field names (`truth`, `verified`,
     `legitimate`, `permission`, `authorized`, `winner`).
   - **No command path:** AST/import scan for `AgentCommand`,
     `ActionSubmission`, `WorldEngine`, `world._`, admission, or event-store
     imports; assert the module exposes no function returning a command.
   - **No world read:** grep/import scan that `WorldEngine`, `agent_runtime`
     admission, stop selectors, and perception never import the ledger module;
     the ledger module imports no `world`, `simulation`, `persistence`, or `api`.
   - **No peer read:** assert the public signature contains only typed owner
     sidecars and no arbitrary mapping/ledger.
   - **Version pins:** commands 43, observer semantic types 73, replay
     `EVENT_SCHEMA_REPLAY_V22 == 22`, codec `v20` accepted and `v21` not,
     Alembic head `0017` with no `0018_*`, 14 contexts, 12 flags, 3 owned flags,
     no `runner-config-v57`, no new runner spec/config field.
   - **Surfaces:** exactly six representation routes with GET only; six cursor
     purposes; snapshot `delegation-representation-snapshot-v1`; store
     `delegation-representation-store-v1`; sibling codecs still decode.
   - **Catalog:** 160 families; first 157 digest unchanged; the three new ids are
     the last three.
2. Add `test_v4_09_deepens_organizations_without_new_schema` to
   `tests/architecture/test_v4_architecture_invariants.py`, following the
   existing `test_v4_08_deepens_legal_disputes_without_new_schema` shape at
   lines 181-200: 14 contexts, 12 flags, 3 owned flags, no
   `runner-config-v57`, `diplomacy` still unowned and fail-closed.
3. Create `tests/unit/test_delegation_representation_physical_distinction.py`:
   with `organizations` enabled, a mandate rejected/contested by every member
   must not block a physically possible `Move`/`Give`; a physically impossible
   command is still rejected with the existing error code; `WorldEngine` never
   reads `RepresentationLedger`.
4. Re-verify the catalog pins updated in Task 13: count 160, first-157 digest,
   full-160 digest, and the three new ids last. Do not weaken the first-154 pin.
5. Re-run the stale-pin guard from Task 13 and assert no metric-count assertion
   still compares against 157.
6. Extend `tests/unit/test_evidence_testimony_boundaries.py` so the
   representation route and cursor sets are included in the global surface pins.
7. Add determinism assertions in
   `tests/unit/test_delegation_representation_determinism.py`: repeated
   construction from shuffled inputs yields identical digests; no `hash(`,
   `uuid`, `random`, or `datetime.now` in the new modules.

### Required Interfaces and Contracts

- Tests read source files directly for AST/import checks and use
  `__dataclass_fields__` for schema pins.
- No test weakens an existing pin; expired counts are updated only where the
  plan declares the change (157 → 160, six new routes, new snapshot/store).
- Sibling snapshot byte-verification tests remain untouched and green.

### Error Handling and Logging

- Test failures name the symbol, path, and expected value.
- No network, Docker, PostgreSQL, or browser is required for this suite.

### Tests

- `uv run pytest tests/architecture/test_delegation_representation_boundaries.py tests/architecture/test_v4_architecture_invariants.py tests/unit/test_delegation_representation_physical_distinction.py tests/unit/test_delegation_representation_determinism.py -q`
- `uv run pytest tests/unit/test_evidence_testimony_catalog.py tests/unit/test_evidence_testimony_boundaries.py tests/unit/test_delegation_representation_catalog_pins.py -q`

### Acceptance Criteria

- Every authority claim in the plan has at least one failing-if-violated test.
- Pins are exact and no sibling contract is weakened.

### Verification

- Commands above return pass.
- Expected: zero skips other than environment-gated lanes declared in Task 22.

## Task 21: Add the representation end-to-end scenario

### Intent

A scripted multi-owner scenario proves the real path: speech frames create
mandates, recognition is contested and revoked, analysis harvests rows,
publication stores a snapshot, and the API serves it — without changing
admission.

### Implementation Steps

1. Create `tests/integration/test_delegation_representation_e2e.py` with a
   disposable PostgreSQL database name containing `palimpsest_test` when the
   integration marker is used; otherwise run against the in-memory runner path
   used by the evidence E2E.
2. Build a run with `runner-config-v56` and only `organizations=True`; four
   owners: principal A, representative B, member C, sceptic D.
3. Tick 1: B sends a `Tell` to A and C with a
   `rep_v1:rep_claim` frame naming B as representative for
   `speak_for`/`scope_subject=border`. Assert `claimed` and that no command was
   created by the frame.
4. Tick 2: C sends `rep_support`; D sends `rep_oppose`; assert derived status
   `contested` with both positions retained and one independence root per actor.
5. Tick 3: A sends `rep_accept`; assert `recognized` with
   `principal_declaration`, and D's opposition is retained.
6. Tick 4: A sends `rep_delegate` naming C for the same principal and scope;
   assert a second `recognized` mandate, a `duplicate_mandate` conflict with B,
   and coexistence of both.
7. Tick 5: A sends `rep_revoke` for B; assert `revoked`, positions retained, C
   still recognized, and a fresh self-claim by B is `claimed`, never
   `recognized`.
8. Tick 6: A claims a mandate for a `settlement` principal whose region is
   visible; assert resolved; a second claim for an unobserved region stays
   `claimed` with `representation_region_unavailable`.
9. Tick 7: D attempts an unauthorized revocation of C; assert a
   `revocation_dispute` conflict and that C stays recognized.
10. Run analysis harvest, build candidate/lineage/layers, and assert the three
    metric documents are present with `partial`/`complete` coverage.
11. Publish to a temp root, read via the filesystem reader, then call the six API
    routes with a test client and `SUBJECTIVE_DEBUG`; assert 200, digest-stable
    pages, and a rejected cursor after a digest change.
12. Assert that a socially contested or rejected mandate does not prevent A, B,
    C, or D from submitting a physically possible command, and that a physically
    impossible command is still rejected.
13. Account for one-tick delivery latency: a frame sent at tick T is observed by
    its listener at tick T+1, so each assertion targets the listener's
    next-tick ledger.

### Required Interfaces and Contracts

- Uses existing `Talk`/`Tell` and `SimulationRunner` APIs; no test-only hooks.
- Uses the real `apply_representation_update`, `record_representation_utterance`,
  analysis, publication, store, and API.
- Asserts objective command outcomes are unchanged by representation status.

### Error Handling and Logging

- The test asserts that no domain identifiers appear in captured log records at
  INFO or above (use `caplog` with a token filter).
- A publication failure path is exercised separately and must leave the result
  unchanged.

### Tests

- `uv run pytest tests/integration/test_delegation_representation_e2e.py -q`
- Expected: pass.

### Acceptance Criteria

- The scenario covers claim, support, opposition, acceptance, revocation,
  settlement resolution, conflict, metrics, publication, and API.
- Admission remains independent of representation.

### Verification

- `PALIMPSEST_TEST_DATABASE_URL=... uv run pytest -m "integration and not scale" -q`
  (when PostgreSQL is available) or the in-memory path otherwise.
- Expected: no failures; any environment-gated case is recorded in Task 22.

## Task 22: Execute the full V1-V4 regression and qualification lanes

### Intent

Ship an honest three-state receipt. A lane that cannot run is `unexecuted` with
its prerequisite, never a skip-pass.

### Implementation Steps

1. Run and record each lane exactly once as `executed_passed`,
   `executed_failed`, or `unexecuted`:
   - `uv run pytest tests/unit tests/architecture -q --cov --cov-report=term`
   - focused V4-09 selection (unit + architecture + E2E)
   - `-k "organization or v4 or formal_rule or dispute or evidence_testimony or representation or metric_specification or runner_config_v56"`
   - documentation parity suites for existing pages (the V4-09 docs parity suite
     is created in Task 23 and re-run in Task 24)
   - `uv run ruff check src tests`
   - `uv run mypy src tests`
   - `uv run lint-imports`
   - `uv run pytest -m "integration and not scale" -q` against a disposable
     `palimpsest_test` database
   - integration including scale (declare the 100,000-tick prerequisite)
   - `docker compose config --quiet`
   - Compose/browser acceptance (pinned API image + Playwright chromium)
   - pinned Godot 4.7.2 protocol suite
   - benchmark/scale lane (multi-hour 100,000-tick harness)
   - Research UI `vitest run`, `svelte-check`, `tsc -p tsconfig.node.json`,
     `vite build`
2. Record counts, durations if available, and exact commands in the `index.md`
   Verification Receipt.
3. For every `unexecuted` lane, write the missing prerequisite. Do not convert
   an environment skip into a pass.
4. Set the certification outcome to `not certified` when any required lane is
   `unexecuted` or `executed_failed`.
5. Save any failure output to the plan bundle only as a bounded excerpt; do not
   paste full logs.

### Required Interfaces and Contracts

- Receipt rows use exactly the three states.
- No lane is marked passed because it was skipped by a marker expression.
- Coverage remains enabled for Python lanes.

### Error Handling and Logging

- Record the failing command and the first failing assertion or error code.
- Never include secrets, DSNs, tokens, or payloads in the receipt.

### Tests

- This task is the execution itself; the artifact is the receipt.

### Acceptance Criteria

- Every required lane has a state and evidence.
- The outcome is honest and reproducible from the receipt.

### Verification

- Re-run any `executed_passed` lane that produced a failure in a later task and
  update the receipt.

## Phase Risks and Mitigations

- Risk: the E2E accidentally relies on repository state outside the run.
  Mitigation: use a temp root and a fresh seed; assert deterministic digests.
- Risk: qualification pressure turns skips into passes.
  Mitigation: three-state receipt with named prerequisites and withheld
  certification.
- Risk: new family count weakens the evidence catalog pin silently.
  Mitigation: first-157 digest assertion plus explicit count update only in this
  task.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass or are recorded `unexecuted` with a
  prerequisite.
- `index.md` task checkboxes are updated immediately after verified completion.
