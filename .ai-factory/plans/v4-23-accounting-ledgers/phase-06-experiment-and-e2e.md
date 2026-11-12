# Phase 6: Experiment and End-to-End

Plan: [index.md](index.md)
Tasks: 17-19
Depends on: Phase 3 / Task 10, Phase 4 / Task 14, Phase 5 / Task 15

## Objective

Register the off-gate `accounting_ledgers@1` experiment, prove the full seam with
a real in-process run (real commands, events, snapshot, store, and API read), and
lock determinism, cap-bound properties, and leakage guards.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/experiments/catalog.py` | off-gate ids 2800-2837; `credit_relationships@1` 2835; experiment builder 5711-5729 | Registration template. |
| `src/experiments/credit_relationship_scenario.py` | id 41; scenario 100; arms 116-140; v56/seams 141-152 | Scenario template with four arms. |
| `src/experiments/emergent_prices_scenario.py` | id 38; scenario 96 | Second reference. |
| `src/experiments/collectors.py` | 414-439 | Metric input injection; accounting must add its input without touching runner. |
| `src/experiments/credit_relationships_publication.py` | entrypoint 379 | Post-run publication bridge. |
| `tests/unit/test_credit_relationships_end_to_end.py` | 260 | Real-engine E2E pattern. |
| `tests/unit/test_credit_relationships_determinism.py` | hash-seed/event-order determinism | Determinism pattern. |
| `tests/unit/test_credit_relationships_bounds.py`, `_evidence_bounds.py` | Hypothesis caps | Property pattern. |
| `tests/unit/test_credit_relationships_leakage.py` | leakage guards | Leakage pattern. |
| `src/world/actions.py` | `Inscribe` 347-392; `Talk` 131; `Tell` 171 | Real commands used by the E2E. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/experiments/accounting_ledger_scenario.py` | create | `accounting_ledgers@1` scenario and arms. |
| `src/experiments/catalog.py` | modify | Off-gate registration and builder. |
| `src/experiments/collectors.py` | modify | Inject the accounting analysis input. |
| `tests/unit/test_accounting_ledgers_experiment.py` | create | Registration/arm discipline. |
| `tests/unit/test_accounting_ledgers_end_to_end.py` | create | Real in-process E2E. |
| `tests/unit/test_accounting_ledgers_determinism.py` | create | Determinism. |
| `tests/unit/test_accounting_ledgers_bounds.py` | create | Hypothesis caps. |
| `tests/unit/test_accounting_ledgers_leakage.py` | create | Leakage guards. |

---

## Task 17: Register off-gate accounting_ledgers@1

### Intent

Ship a reproducible experiment that composes `organizations`, `durable_records`,
and optional `structured_commitments`/`subjective_valuation`/`evidence_testimony`
without entering the V1 A-E gate.

### Implementation Steps

1. `src/experiments/accounting_ledger_scenario.py`:
   - `ACCOUNTING_LEDGERS_EXPERIMENT_ID = "accounting_ledgers@1"`.
   - `accounting_ledger_scenario(...)` builds a v56 config with
     `v4_capability_flags.organizations=True`, `v3_capability_flags`
     `cultural_historical_memory=True`, a deterministic
     `CulturalFeatureProvenanceSpec`, a deterministic `DurableRecordsSpec`
     (`enabled_genres` includes `inventory_record` and `agreement`),
     deterministic `ArtifactInterpretationMode`, and deterministic
     `CommunicationStrategyMode`. The cultural/provenance inputs are the durable
     channel's existing prerequisites, not new accounting inputs.
   - Minimum `max_ticks=96`; reject shorter.
   - Four arms:
     - `al-records-off`: organizations on, durable records off.
     - `al-records-only`: organizations off, durable records on.
     - `al-ledger-on`: both on, deterministic artifact interpretation.
     - `al-ledger-dialogue`: both on plus deterministic communication.
   - `paired_world_group="accounting_ledgers@1-world"`.
2. `src/experiments/catalog.py`:
   - add `"accounting_ledgers@1"` to `OFF_GATE_MATRIX_EXPERIMENT_IDS` (2834-2835).
   - add `experiment_accounting_ledgers` beside 5711-5729.
3. `src/experiments/collectors.py`: inject `accounting_ledgers_analysis` into
   `MetricComputationInputs` beside 414-439; do not change runner or CLI.
4. Log `INFO experiment_registered experiment_id=accounting_ledgers@1 arms=4`.

### Required Interfaces and Contracts

- Arm composition uses only existing fields/specs; no new runner key.
- The experiment stays off the V1 gate.
- Each arm changes exactly one declared axis from the control.
- `max_ticks >= 96`.

### Requirement Evidence (when reconciliation applies)

- Original Request; `.ai-factory/ARCHITECTURE.md` — feature experiments stay off
  the V1 gate.

### Error Handling and Logging

- Invalid arm axis: fail before execution with `accounting_experiment_invalid`.
- Log arm counts only; never log config payloads.

### Tests

Create `tests/unit/test_accounting_ledgers_experiment.py`:
- id registered and off-gate;
- four arms with exactly one axis difference;
- v56 and deterministic communication asserted;
- `max_ticks < 96` rejected;
- no V1-gate membership.

Command: `uv run pytest tests/unit/test_accounting_ledgers_experiment.py -q`.

### Acceptance Criteria

- `accounting_ledgers@1` is registered off-gate with four disciplined arms.

### Verification

- The command above — expected: pass.

---

## Task 18: Add in-process accounting end-to-end coverage

### Intent

Prove the whole seam with real components: engine admission of `Inscribe` and
`Tell`, committed record and speech events, cognition folding, analysis,
snapshot, store, and an API read — no fakes for the world boundary.

### Implementation Steps

1. Create `tests/unit/test_accounting_ledgers_end_to_end.py`:
   - build a real `WorldEngine` and a small deterministic scenario with
     `organizations` + `durable_records`.
   - issue a real `Inscribe` command whose content is built by
     `accounting_record_content` with at least three `acc_v1` relations covering
     `exchange`, `debt`, and `inventory`.
   - advance ticks so the owner observes the artifact and folds the ledger.
   - issue a real `Talk`/`Tell` whose selected command receives one `acc_v1`
     relation; commit it and confirm the receiver folded a `communicated` claim.
   - run the completed-run analysis, compose the snapshot, publish through the
     real filesystem store, and read the summary and entries through the real
     API reader.
   - assert the physical world is unchanged by the accounting ledger (no item
     moved, no structure quantity changed).
2. Add an integration twin under
   `tests/integration/test_accounting_ledgers_store_api.py` marked
   `@pytest.mark.integration` for the real filesystem publish/read and the
   corrupt-store 500.
3. Log only counts at DEBUG.

### Required Interfaces and Contracts

- Uses real `WorldEngine` admission, real `Inscribe`/`Tell`, real events, a real
  snapshot, a real store, and a real API read.
- The `Inscribe` command is the existing command; no new command is added.
- The accounting ledger never mutates world state.

### Requirement Evidence (when reconciliation applies)

- Original Request "Extend external records with accounting-like artifacts" and
  "Allow agents/institutions to use ledgers as evidence".

### Error Handling and Logging

- Assertions fail with safe messages; no payload dumps.

### Tests

- The E2E file and the integration twin.

Commands:
- `uv run pytest tests/unit/test_accounting_ledgers_end_to_end.py -q`
- `uv run pytest tests/integration/test_accounting_ledgers_store_api.py -q -m integration`

### Acceptance Criteria

- The E2E proves record creation, interpretation, speech, analysis, publication,
  and read in one run.
- World state is provably unchanged by accounting beliefs.

### Verification

- The two commands above — expected: pass.

---

## Task 19: Add determinism, property bounds, and leakage coverage

### Intent

Lock the scientific guarantees: identical inputs produce identical ledgers,
analysis, snapshot bytes, and metrics across hash seeds and event order; caps
hold under arbitrary inputs; no private or analysis data leaks across boundaries.

### Implementation Steps

1. `tests/unit/test_accounting_ledgers_determinism.py`:
   - run the fold twice under `PYTHONHASHSEED=0` and `PYTHONHASHSEED=1` in
     subprocesses; compare ledger bytes, analysis digest, snapshot digest, and
     metric documents;
   - permute committed event order and assert the same digest.
2. `tests/unit/test_accounting_ledgers_bounds.py`:
   - Hypothesis over arbitrary relation tokens, quantities, confidence, and
     owner/record tokens; assert no exception beyond the safe contract error and
     all caps hold.
3. `tests/unit/test_accounting_ledgers_leakage.py`:
   - AST check: `src/agents` and `src/world` never import `analysis`;
     `src/analysis` never imports `agents.cognition.accounting_ledgers`,
     `simulation`, or `experiments`;
   - `src/api` never imports `analysis`;
   - no client file imports Python;
   - the snapshot and API rows contain no raw owner/item/record ids;
   - the researcher alignment type is unreachable from cognition, prompts,
     memory, world state, observer semantics, and stop selectors.
4. Log no payloads.

### Required Interfaces and Contracts

- Determinism is byte-level for ledger and snapshot, digest-level for analysis.
- Every cap family has an independent property.
- Leakage checks are AST/grep based and fail closed.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` "Key Principles" 1-2 and dependency rules.
- `.ai-factory/RULES.md` axioms 1-5.

### Error Handling and Logging

- Not applicable beyond assertion messages.

### Tests

Commands:
- `uv run pytest tests/unit/test_accounting_ledgers_determinism.py -q`
- `uv run pytest tests/unit/test_accounting_ledgers_bounds.py -q`
- `uv run pytest tests/unit/test_accounting_ledgers_leakage.py -q`

### Acceptance Criteria

- Determinism, cap bounds, and leakage guards pass.
- No boundary is weakened.

### Verification

- The three commands above — expected: pass.

## Phase Risks and Mitigations

- Risk: the E2E accidentally uses a fake engine and proves nothing.
  Mitigation: instantiate the real `WorldEngine` and assert committed events.
- Risk: determinism only holds within one process.
  Mitigation: subprocess runs with different hash seeds.
- Risk: alignment leaks into cognition through a convenient import.
  Mitigation: AST boundary test plus a runtime reachability assertion.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
