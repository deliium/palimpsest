# Phase 7: Invariants, End-to-End Evidence, and Regression

Plan: [index.md](index.md)
Tasks: 20-22
Depends on: Phase 6 / Tasks 18-19

## Objective

Prove the dispute feature is owner-scoped, non-binding, memory-faithful,
deterministic, and isolated from world authority; exercise one real
contested-debt/ownership scenario through mediation, publication, API, and
metrics; then run the full V1-V4 regression and qualification lanes.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `tests/architecture/test_formal_rule_boundaries.py` | AST module list, forbidden law/engine classes, command scan, route/cursor/pin assertions | Boundary-test template. |
| `tests/architecture/test_organization_boundaries.py` | ownership split, no global registry, API isolation | Ownership/identity test template. |
| `tests/unit/test_formal_rule_regression.py` | catalog/pin assertions | Regression-pin template. |
| `tests/unit/test_formal_rule_docs.py` | docs parity | Documentation test template. |
| `tests/integration/test_agent_runtime_world_engine.py` | real runtime/engine path | E2E runtime pattern. |
| `src/world/actions.py` | `Give`, `Take`, `Attack`, `Talk`, `Tell` | Physical effects remain ordinary commands. |
| `src/simulation/engine.py` | admission/resolution | Physical impossibility remains there. |
| `src/agents/cognition/mediation_actions.py` | `compile_mediation_undertaking` 75-125 | Only supported undertaking path. |
| `docs/development.md` | test commands and lanes | Exact qualification commands. |
| `tests/compose/acceptance.py` | three-state result handling | Required-lane receipts. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `tests/architecture/test_dispute_boundaries.py` | create | Authority, command, registry, route, cursor, pin, determinism boundaries. |
| `tests/unit/test_dispute_determinism.py` | create | Shuffled input/delivery determinism. |
| `tests/unit/test_dispute_physical_distinction.py` | create | Social dispute vs physical impossibility. |
| `tests/integration/test_dispute_e2e.py` | create | Real runner, mediation, publication, API, metrics. |
| `tests/unit/test_dispute_docs.py` | create | Documentation parity (Task 23 fills docs). |
| `tests/unit/test_v1_regression_gate.py` | modify only if a shared helper requires it; expected no change | V1 gate remains green. |
| `tests/unit/test_v2_scientific_invariants.py` | modify only if a shared helper requires it; expected no change | V2 gate remains green. |

## Task 20: Add the dispute boundary and determinism suite

### Intent

Make forbidden architectures fail tests rather than review: no justice oracle,
no court/judge, no shared registry, no peer-ledger read, no command construction,
no world read, no nondeterminism, and exact version pins.

### Implementation Steps

1. Create `tests/architecture/test_dispute_boundaries.py` with an explicit
   module list:
   - `agents.cognition.legal_disputes`
   - `agents.cognition.legal_dispute_communication`
   - every `analysis.dispute_*`
   - `simulation.dispute_models`, `dispute_codec`, `dispute_paging`,
     `dispute_ports`
   - `experiments.dispute_harvest`, `dispute_publication`
   - `persistence.dispute_filesystem`
   - `api.routes.dispute`, `api.dispute_schemas`, `api.dispute_cursor`
   - `research_runner.dispute_composition`
   Use AST parsing; do not import application modules at test collection time.
2. Assert forbidden symbols/classes are absent: `WorldState`, `WorldEvent`,
   `PerceptionService`, `MemoryService`, `EventStore`, `ActionSubmission`,
   `TickToken`, `resolve_tick`, `Court`, `Judge`, `Jury`, `Verdict`,
   `Judgment`, `JusticeEngine`, `ArbitrationEngine`, `SanctionEngine`,
   `LiabilityEngine`, `GlobalDisputeRegistry`, `DisputeRegistry`.
3. Assert forbidden field names (from Task 1) do not appear as attribute/field
   names in any dispute record or schema.
4. Assert no command construction in `legal_disputes.py` or analysis:
   - no call to `AgentCommand(`, `Give(`, `Take(`, `Attack(`, `Talk(`, `Tell(`,
     `Feed(`, `Transport(`, `Help(`;
   - no `.submit(` or `resolve_tick`;
   - `legal_dispute_communication.py` may only type-check/decorate an existing
     command; it must not instantiate one.
5. Assert no cross-owner read:
   - `apply_dispute_update` rejects a prior/mediation/formal-rule/office ledger
     whose owner differs;
   - no `peer`, `other_owner`, `all_agents`, or batch observation API is used.
6. Assert no cognition import in `analysis.dispute_*` and no analysis import in
   `agents.cognition.legal_disputes*`.
7. Assert no world/simulation/API/persistence import in analysis, and no
   analysis/experiments import in API.
8. Assert exactly six GET routes and six cursor purposes; no POST/PUT/PATCH/
   DELETE; `SUBJECTIVE_DEBUG` is required; `dispute_disabled` exists.
9. Assert schema pins:
   - snapshot `dispute-resolution-snapshot-v1`;
   - store `dispute-resolution-store-v1`;
   - `legal_disputes` owned with `formal_rules` prerequisite;
   - 14 contexts / 12 flags / 3 owned;
   - four write-pair reservations unchanged;
   - replay `EVENT_SCHEMA_REPLAY_V22`, codec `v20`;
   - commands 43, observer semantics 73, metric families 154;
   - Alembic `0017`, no `0018`;
   - no `runner-config-v57`;
   - `/v1`, `observer-protocol-v1`, no `observer-protocol-v2` serving.
10. Assert settings/app isolation: settings never reads a ledger; app wiring
    imports no analysis/experiments producer; the reader is optional.
11. Create `tests/unit/test_dispute_determinism.py`:
    - shuffle harvested rows, windows, evidence, and deliveries; assert identical
      ledger, candidate ids, lineage, layers, and metric documents;
    - assert content-addressed ids are stable across permutations;
    - AST-scan dispute modules for `hash(`, `uuid`, `random`, `time.time`,
      `datetime.now`, `secrets`, and global RNG use.
12. Create `tests/unit/test_dispute_physical_distinction.py`:
    - a socially disputed but physically possible command is admitted normally;
    - a physically impossible command is rejected by the existing world rules;
    - the dispute ledger is never consulted during admission;
    - no dispute helper returns or submits a command outside the mediation
      delegation.

### Required Interfaces and Contracts

```python
DISPUTE_MODULES: tuple[str, ...] = (...)
FORBIDDEN_DISPUTE_SYMBOLS: frozenset[str] = frozenset({...})
FORBIDDEN_DISPUTE_FIELDS: frozenset[str] = ...

def test_no_objective_justice_or_global_registry() -> None: ...
def test_no_command_construction_or_world_read() -> None: ...
def test_exact_routes_cursors_and_pins() -> None: ...
def test_shuffled_inputs_are_deterministic() -> None: ...
def test_social_dispute_does_not_change_admission() -> None: ...
```

Compatibility invariants:

- This suite may mention `runner-config-v57` only in a negative pin assertion.
- It may mention `0018` only to assert absence.
- It must not weaken any existing V4 pin.

### Requirement Evidence

- Original Request "Do not implement an objective justice oracle" and "Research
  infrastructure knows objective history but agents do not."
- `.ai-factory/ARCHITECTURE.md` "Anti-Patterns" and "Versioned Extension
  Contract".
- `tests/architecture/test_formal_rule_boundaries.py` and
  `tests/architecture/test_organization_boundaries.py`.

### Error Handling and Logging

- Test failures print only file/symbol/line; no payload content.
- The suite does not start app servers, databases, or clients.

### Tests

Run:

- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_dispute_boundaries.py tests/unit/test_dispute_determinism.py tests/unit/test_dispute_physical_distinction.py -q`

Coverage assertions:

- `test_no_objective_justice_or_global_registry`
- `test_no_command_construction_or_world_read`
- `test_no_peer_ledger_or_cross_owner_read`
- `test_analysis_is_read_only_and_cognition_imports_no_analysis`
- `test_exactly_six_get_routes_and_six_cursor_purposes`
- `test_exact_context_flag_reservation_and_wire_pins`
- `test_no_new_event_command_observer_semantic_or_migration`
- `test_settings_and_app_do_not_read_dispute_content`
- `test_shuffled_deliveries_and_rows_are_deterministic`
- `test_social_dispute_does_not_change_admission`

### Acceptance Criteria

- Every forbidden architecture is a failing test.
- Determinism holds under shuffled inputs.
- Physical admission is unchanged.
- Exact version pins hold.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_dispute_boundaries.py tests/unit/test_dispute_determinism.py tests/unit/test_dispute_physical_distinction.py -q`
- Expected result: all tests pass.

## Task 21: Add the dispute end-to-end scenario

### Intent

Exercise one realistic contested-debt/ownership dispute through the real runner,
mediation, publication, six API reads, and metric assembly, proving the feature
works without an objective justice oracle.

### Implementation Steps

1. Create `tests/integration/test_dispute_e2e.py` with a deterministic scenario:
   - world with agents A, B, C, D, a shared item, and a finite tick horizon;
   - `runner-config-v56` with `v4_capability_flags.legal_disputes=True` and
     `formal_rules=True`;
   - A and B receive different memory evidence for the same transfer event;
   - A asserts a `contested_debt`/`resource_appropriation` claim;
   - B asserts a counterclaim `ownership_claim`;
   - C provides direct testimony; D retells the same root;
   - A cites a formal rule `obligation` to return the item; B cites a competing
     `permission` interpretation;
   - a mediation case exists and the mediator proposes a `Give` resolution;
   - A accepts; B rejects; a later proposal is accepted by both and becomes
     `apparently_accepted`.
2. Use the real `SimulationRunner` and `WorldEngine`; do not stub the update or
   admission. Build claims through `dispute_communicate_utterance` on an
   existing `Talk`/`Tell`, then run the tick.
3. Assert:
   - A's ledger and B's ledger each contain their own claims; neither contains
     the other's private ledger object;
   - A and B can hold opposite claims on the same subject;
   - C's direct testimony is `independently_evidenced`; D's retelling shares the
     root and is not independent;
   - rule references resolve only against each owner's formal-rule ledger;
   - mediation links exist and the recommendation is a belief, not a binding
     decision;
   - the resolution becomes `apparently_accepted` only after both declarations;
   - a proposal and acceptance submitted in one tick is refused with
     `dispute_resolution_requires_prior_tick`; the same acceptance submitted on
     the next tick succeeds;
   - no `verdict`, `guilty`, `liable`, `winner`, or `true_owner` field exists.
4. Export a real `AgentRuntimeCheckpoint` for both owners, re-import it through
   the supported restore path, and assert the dispute ledger equality before
   continuing. Do not construct a synthetic “restored” ledger (the 2026-10-19
   patch records a synthetic-map gap masking a missing round trip).
5. Build the completed-run harvest, publish to a temporary filesystem root, and
   read all six API routes through the FastAPI test client with
   `SUBJECTIVE_DEBUG`. Assert the six responses match the published candidate,
   claims, resolutions, and lineage.
6. Assemble metrics through `experiments.collectors.collect_arm_metric_bundle`
   or the established completed-run helper; assert the three dispute documents
   are present and the objective-alignment values are present but not in any
   agent ledger or prompt.
7. Inject a publisher that raises; assert the runner result, event history, and
   metric inputs are unchanged and the receipt is `failed`.
8. Execute a physically possible `Give` while the social dispute remains open;
   assert admission succeeds. Execute a physically impossible transfer; assert
   the existing rejection is unchanged and no dispute attribution is added.
9. Confirm the E2E never calls `resolve_tick` from a dispute helper and never
   reads a peer ledger.

### Required Interfaces and Contracts

```python
def test_contested_debt_and_ownership_dispute_e2e(tmp_path: Path) -> None: ...
def test_conflicting_memories_produce_separate_claims(tmp_path: Path) -> None: ...
def test_real_checkpoint_round_trip_preserves_dispute_ledgers(tmp_path: Path) -> None: ...
def test_mediation_recommendation_is_not_binding(tmp_path: Path) -> None: ...
def test_same_tick_acceptance_is_refused_then_next_tick_succeeds(tmp_path: Path) -> None: ...
def test_publication_failure_preserves_scientific_result(tmp_path: Path) -> None: ...
def test_physical_admission_is_independent_of_dispute_belief(tmp_path: Path) -> None: ...
```

Compatibility invariants:

- The E2E uses real admission and real publication; no shortcut.
- The publisher failure is injected, not simulated by skipping publication.
- The API reads committed artifacts only.

### Requirement Evidence

- Original Request all requirements, especially "Do not implement an objective
  justice oracle" and "Research infrastructure knows objective history but agents
  do not."
- `tests/integration/test_agent_runtime_world_engine.py`.
- `src/agents/cognition/mediation_actions.py` 75-125.
- `src/api/routes/dispute.py` from Task 18.
- `.ai-factory/patches/2026-10-19-15.56.md`: a real checkpoint round trip, not a
  synthetic restored map.

### Error Handling and Logging

- E2E logs only stage names and counts.
- A failed assertion identifies the stage, not claim content.
- Temporary publication roots are isolated and removed by `tmp_path`.

### Tests

Run:

- `uv run --frozen --python 3.12.14 pytest -m integration tests/integration/test_dispute_e2e.py -q`
- Also run without the marker for the in-memory portions:
  `uv run --frozen --python 3.12.14 pytest tests/integration/test_dispute_e2e.py -q`

### Acceptance Criteria

- The real runner produces two owner-scoped dispute views.
- Conflicting memories remain separate.
- Testimony independence and rule references work.
- Mediation is linked but not binding.
- All-party acceptance is `apparently_accepted` only.
- Publication failure does not change science.
- Physical admission is independent of dispute belief.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/integration/test_dispute_e2e.py -q`
- Expected result: all tests pass.

## Task 22: Execute the full V1-V4 regression and qualification lanes

### Intent

Run the complete required-gate matrix and record each lane as
`executed_passed`, `executed_failed`, or `unexecuted`. An unexecuted lane blocks
certification.

### Implementation Steps

1. Run the focused V4-07 suite:
   `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_*.py tests/architecture/test_dispute_boundaries.py -q`.
2. Run the V4/organization/formal-rule regression selection:
   `uv run --frozen --python 3.12.14 pytest tests/unit -q -k "organization or v4 or formal_rule or dispute or metric_specification or runner_config_v56"`.
3. Run the full Python unit + architecture suite with coverage enabled:
   `uv run --frozen --python 3.12.14 pytest tests/unit tests/architecture -q`.
   Explicitly include
   `tests/unit/test_v1_regression_gate.py` and
   `tests/unit/test_v2_scientific_invariants.py`; both must stay green with
   `legal_disputes` off and on.
4. Run `uv run --frozen --python 3.12.14 ruff check src tests`,
   `uv run --frozen --python 3.12.14 mypy src tests`, and
   `uv run --frozen --python 3.12.14 lint-imports`.
5. Run integration without scale:
   `PALIMPSEST_TEST_DATABASE_URL=...palimpsest_test_v407 uv run --frozen --python 3.12.14 pytest -m "integration and not scale" -q`.
6. Run integration including scale:
   `PALIMPSEST_TEST_DATABASE_URL=...palimpsest_test_v407_scale uv run --frozen --python 3.12.14 pytest -m "integration and scale" tests/integration -q`,
   including the 100,000-tick generational lane.
7. Run `docker compose config --quiet`.
8. Run the Compose/browser acceptance lane with a pinned API image and
   `PALIMPSEST_V3_ACCEPTANCE_REQUIRED=1`; record the exact test count.
9. Run the pinned Godot 4.7.2 editor/protocol lane; the plan does not change the
   client, so this is a regression gate.
10. Run the benchmark/scale lane:
    `PALIMPSEST_TEST_DATABASE_URL=...palimpsest_test_v407_bench uv run --frozen --python 3.12.14 pytest -m "integration and scale" tests/benchmarks/ -q`.
11. Run `cd clients/research-ui && pnpm test && pnpm check && pnpm build`.
12. Record every lane in the `index.md` Verification Receipt with exact counts,
    database names, image tags, browser/Godot versions, and prerequisites.
13. If a prerequisite is missing, record `unexecuted` with the prerequisite. Do
    not convert a skip into a pass.
14. Fix any failure in the owning task; do not weaken a pin, delete a test, or
    mark a lane passed without evidence.

### Required Interfaces and Contracts

```text
executed_passed | executed_failed | unexecuted
```

Compatibility invariants:

- V1 A-E gate and `test_v2_scientific_invariants.py` remain green.
- No existing pin is weakened.
- The 100,000-tick lane is an actual durability gate, not a skip-pass.

### Requirement Evidence

- `docs/development.md` test matrix.
- Plan Settings "Testing: yes; full strategy."
- `.ai-factory/ARCHITECTURE.md` requirements 3 and 6.

### Error Handling and Logging

- Record exact command, exit status, and count.
- A missing prerequisite is a blocker, not a warning.
- Do not paste claim/evidence/rule content into receipts.

### Tests

This task is the execution of the lanes above; it adds no new test code. The
receipt table in `index.md` is the durable evidence.

### Acceptance Criteria

- Every required lane is recorded with a three-state outcome.
- All possible lanes are `executed_passed`.
- Any unexecuted lane names its prerequisite and blocks certification.

### Verification

- The `index.md` Verification Receipt matches the actual command outputs.
- Expected result: all required lanes pass, or certification is withheld.

## Phase Risks and Mitigations

- Risk: A boundary test is satisfied by an empty module list.
  Mitigation: Task 20 asserts the module list matches actual files.
- Risk: E2E uses a shortcut that bypasses admission or publication.
  Mitigation: Task 21 real runner/API assertions.
- Risk: A required lane is silently skipped.
  Mitigation: Task 22 three-state receipt and Task 24 audit.
- Risk: A test weakens an existing pin to pass.
  Mitigation: Task 20/24 pin diff review.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass or are recorded `unexecuted` with a blocker.
- `index.md` task checkboxes and Verification Receipt are updated immediately
  after verified completion.
