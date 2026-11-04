# Phase 7: Invariants, End-to-End Evidence, and Regression

Plan: [index.md](index.md)
Tasks: 20-22
Depends on: Phase 6 / Task 19

## Objective

Make every V4-08 authority claim a failing test: no truth oracle, no global
evidence registry, no trust oracle, no command construction, no peer-ledger or
world-ledger read, exact pins, deterministic output, and an end-to-end scenario
that proves evidence never changes physical admission. Then execute the full
required lanes and record a three-state receipt.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `tests/architecture/test_dispute_boundaries.py` | module inventory 62-88; AST helpers 156-190; forbidden symbols 90-153; import rules 283-372; route/pin/carry checks 375-544 | Boundary suite template |
| `tests/integration/test_dispute_e2e.py` | runner → publication → store → API | E2E template |
| `tests/unit/test_dispute_determinism.py` | repeated digest equality | Determinism template |
| `tests/unit/test_dispute_physical_distinction.py` | disputed but admitted / impossible rejected | Physical distinction template |
| `src/world/_rules.py` | `COMMAND_RULE_MATRIX` | Command count pin |
| `observer/version.py` | `SEMANTIC_EVENT_TYPES` | Observer semantic pin |
| `src/simulation/persistence.py` | accepted event/codec versions | Replay/codec pins |
| `docs/development.md` | exact verification commands | Lane commands |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `tests/architecture/test_evidence_testimony_boundaries.py` | create | V4-08 authority/pin/route invariants |
| `tests/unit/test_evidence_testimony_determinism.py` | create | Repeated deterministic output |
| `tests/unit/test_evidence_testimony_physical_distinction.py` | extend | Cross-reference boundary assertions |
| `tests/integration/test_evidence_testimony_e2e.py` | create | Full run → publication → API |
| `tests/integration/test_dispute_e2e.py` | modify | Assert dispute snapshot/store behavior unchanged |
| `index.md` | modify | Verification receipt rows for Task 22 |

## Task 20: Add the evidence boundary and determinism suite

### Intent

Prevent the model from drifting into a truth oracle, a shared registry, a trust
oracle, a command path, or a world read, and lock every compatibility pin.

### Implementation Steps

1. Create `tests/architecture/test_evidence_testimony_boundaries.py` with:
   - `EVIDENCE_MODULES` inventory: `agents/cognition/evidence_testimony.py`,
     `agents/cognition/evidence_testimony_communication.py`, every
     `analysis/evidence_testimony_*.py`, every `simulation/evidence_testimony_*.py`,
     `experiments/evidence_testimony_*.py`,
     `persistence/evidence_testimony_filesystem.py`,
     `api/routes/evidence_testimony.py`, `api/evidence_testimony_schemas.py`,
     `api/evidence_testimony_cursor.py`,
     `research_runner/evidence_testimony_composition.py`.
   - AST helpers `_tree`, `_import_roots`, `_referenced_names`,
     `_class_field_names`.
   - Forbidden symbols: `WorldState`, `WorldEvent`, `PerceptionService`,
     `MemoryService`, `EventStore`, `ActionSubmission`, `TickToken`,
     `resolve_tick`, `EvidenceOracle`, `TruthEngine`, `ProofEngine`,
     `Authenticator`, `Verifier`, `ChainOfCustodyAuthority`, `Polygraph`,
     `LieDetector`, `WitnessAuthority`, `EvidenceRegistry`,
     `GlobalEvidenceRegistry`, `Court`, `Judge`, `Jury`, `Verdict`, `Judgment`,
     `LiabilityEngine`.
   - Forbidden field names include every `EVIDENCE_FORBIDDEN_FIELD_NAMES` entry
     plus `correct_account`, `true_source`, `reliable`, `probability_true`.
   - Command-construction tokens: `AgentCommand(`, `ActionSubmission(`,
     `submit_command`, `resolve_tick`, `admit_command`.
   - Import rules: analysis imports only analysis/stdlib; cognition imports no
     analysis/experiments/persistence/api/infrastructure/observer; API imports
     no analysis/experiments/domain ledgers; persistence imports no analysis.
   - Runtime guards: `apply_evidence_update` signature accepts no `Observation`,
     `WorldState`, `WorldEvent`, `MemoryService`, `EventStore`, peer ledger, or
     command; `build_perspective` accepts `evidence` only as an opaque `object`.
   - Route assertions: exactly six GET routes, six cursor purposes, every route
     requires `SUBJECTIVE_DEBUG`, `evidence_testimony_disabled` exists.
   - Pin assertions: snapshot schema `evidence-testimony-snapshot-v1`, store
     schema `evidence-testimony-store-v1`, `METRIC_FAMILY_COUNT == 157`,
     `EVENT_SCHEMA_REPLAY_V22 == 22`, commands 43, observer semantics 73,
     Alembic `0017` and no `0018`, `runner-config-v56` accepted and no
     `runner-config-v57`, context registry 14/12/3, dispute/org/formal snapshots
     unchanged.
   - Owner-local prefix containment: no `evs-`/`evw-`/`evi-`/`evc-`/`evx-`/
     `eva-` id becomes an analytical candidate; no `disp-`/`frule-`/`org-`/
     `msoc-` id is minted by evidence analysis.
   - Vocabulary parity: the analysis token frozensets equal the corresponding
     cognition enum values exactly (source kinds, provenance channels,
     interpretations, custody statuses, trust bases, confidence bands).
   - Facade parity: `agents.cognition`, `analysis`, `experiments`,
     `simulation`, and `api.routes` each expose their evidence entry points in
     `__all__`; no evidence module is reachable only by a deep import.
   - Carried-ledger roundtrip: `Perspective(evidence=ledger).to_snapshot()
     .evidence is ledger`.
2. Create `tests/unit/test_evidence_testimony_determinism.py`:
   - repeated harvest/derive/summarize/layers produce identical digests and
     metric values;
   - ledger id minting is stable across processes (subprocess check optional);
   - no wall-clock, UUID, or `hash()` appears in evidence modules.
3. Extend `tests/unit/test_evidence_testimony_physical_distinction.py` with:
   - a socially contested but physically possible command is admitted;
   - a physically impossible command is rejected;
   - the evidence ledger contains the dispute belief while admission is
     unchanged.

### Required Interfaces and Contracts

- The boundary suite fails on any forbidden symbol, field, import, route, or pin
  drift.
- Determinism claims are executable, not prose.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Key Principles" 1-2; "Objective authority and
  runtime"; "Versioned Extension Contract".
- `tests/architecture/test_dispute_boundaries.py` 62-544.

### Error Handling and Logging

- Tests only; no runtime logging changes.

### Tests

- `uv run pytest tests/architecture/test_evidence_testimony_boundaries.py tests/unit/test_evidence_testimony_determinism.py tests/unit/test_evidence_testimony_physical_distinction.py -q`
- Expected: pass.

### Acceptance Criteria

- Every V4-08 non-goal has a failing test if violated.
- No pin regresses.

### Verification

- `uv run pytest tests/architecture/test_evidence_testimony_boundaries.py tests/unit/test_evidence_testimony_determinism.py tests/unit/test_evidence_testimony_physical_distinction.py -q`
- Expected: pass.

## Task 21: Add the evidence end-to-end scenario

### Intent

Prove the complete path with real components: a witness testifies, a record and
artifact are cited, custody is claimed, a contradiction is retained, an owner
evaluates under its own trust, the run completes, the snapshot publishes, the
store serves it, and the API reads it — while objective inconsistency never
changes the agent ledger or admission.

### Implementation Steps

1. Create `tests/integration/test_evidence_testimony_e2e.py`:
   - build a two-owner run on `runner-config-v56` with
     `v4_capability_flags.legal_disputes=True` (and `formal_rules=True` for the
     rule-authority branch);
   - owner A observes an artifact/record and a physical event; owner B sends a
     `Talk` carrying an `ev_v1` direct testimony; owner A records a
     communicated retelling with a shared root;
   - owner A cites the written record, claims a custody link, interprets two
     sources oppositely, and retains a contradiction;
   - assert both owners' ledgers are owner-scoped and ordered;
   - complete the run, harvest with committed events, publish to a temp
     `PALIMPSEST_EVIDENCE_ROOT`, and read through the filesystem reader and the
     six API routes;
   - assert researcher-only alignment includes an `inconsistent` classification
     when committed history contradicts one claim, while the owner ledger bytes
     are unchanged before/after analysis;
   - assert a physically possible adversarial command is admitted and an
     impossible one is rejected;
   - assert the dispute snapshot and store produced by the same run remain
     readable (no regression).
2. Use only disposable database names containing `palimpsest_test` when the
   scenario touches the database; prefer the in-process runner otherwise.
3. Keep the scenario deterministic: fixed seeds, fixed tick horizon, fixed
   tokens.

### Required Interfaces and Contracts

- The E2E uses the real update, frame parser, runner, harvest, publication,
  filesystem store, and API router.
- No fixture bypasses owner checks or truth boundaries.
- The analysis comparison is performed after the run and never injected into
  cognition.

### Requirement Evidence

- Original Request "compare evidence with objective history without leaking
  truth into cognition".
- `.ai-factory/ARCHITECTURE.md` "analysis is read-only"; V4-07 E2E precedent.

### Error Handling and Logging

- The scenario asserts safe error codes for impossible commands and disabled
  readers; no payload logging.

### Tests

- `uv run pytest tests/integration/test_evidence_testimony_e2e.py -q -m integration`
- Expected: pass with the disposable test database when the lane requires it.

### Acceptance Criteria

- The full path works end to end.
- Objective alignment is demonstrably researcher-only.
- Physical admission is unchanged.

### Verification

- `uv run pytest tests/integration/test_evidence_testimony_e2e.py -q -m integration`
- Expected: pass.

## Task 22: Execute the full V1-V4 regression and qualification lanes

### Intent

Run every required lane and record exactly one of `executed_passed`,
`executed_failed`, or `unexecuted` with a prerequisite. Never record a skip as a
pass.

### Implementation Steps

1. Run and record in `index.md`:
   - `uv run pytest tests/unit tests/architecture -q --cov --cov-report=term`;
   - `uv run pytest tests/unit/test_evidence_testimony_*.py tests/architecture/test_evidence_testimony_boundaries.py -q --cov`;
   - `uv run pytest -k "organization or v4 or formal_rule or dispute or evidence_testimony or metric_specification or runner_config_v56" tests/unit tests/architecture -q`;
   - `uv run pytest tests/unit/test_dispute_docs.py tests/unit/test_formal_rule_docs.py tests/unit/test_organization_docs.py tests/unit/test_organization_operations_docs.py -q`;
   - `uv run ruff check src tests`;
   - `uv run mypy src tests`;
   - `uv run lint-imports`;
   - `uv run pytest -m "integration and not scale" -q`;
   - `uv run pytest -m "integration" -q` (including the 100k scale lane);
   - `docker compose config --quiet`;
   - the Compose/browser acceptance lane;
   - the pinned Godot 4.7.2 suite;
   - the benchmark/scale lane;
   - Research UI tests, type checks, and build.
2. For each lane, record state + evidence. If a prerequisite is missing
   (database, Docker, browser driver, `GODOT_BIN`, benchmark host), record
   `unexecuted` and the prerequisite. Do not weaken the lane or mark it passed.
3. Keep failures as `executed_failed` with the failing command and a bounded
   excerpt; do not hide them.

### Required Interfaces and Contracts

- The receipt is the only certification source; a missing lane blocks
  certification.
- Coverage stays enabled for Python lanes.

### Requirement Evidence

- Plan Settings "Testing: yes; full strategy".
- `docs/development.md`; `.ai-factory/ARCHITECTURE.md` requirement 3.

### Error Handling and Logging

- Report bounded test/linter output; never dump full logs into the plan.

### Tests

- All commands above.

### Acceptance Criteria

- Every lane row is one of the three states.
- No required lane is silently skipped.

### Verification

- `index.md` receipt is complete and internally consistent with the recorded
  commands.

## Phase Risks and Mitigations

- Risk: boundary tests are weakened to pass.
  Mitigation: Task 24 audits that every forbidden symbol/pin still asserts.
- Risk: E2E classification leaks into cognition.
  Mitigation: explicit before/after ledger equality assertion.
- Risk: an unavailable lane is reported as passed.
  Mitigation: three-state receipt and Task 24 audit.

## Phase Completion Checklist

- Every Task 20-22 in this phase satisfies its acceptance criteria.
- Required verification commands pass or are explicitly recorded `unexecuted`.
- `index.md` task checkboxes are updated immediately after verified completion.
