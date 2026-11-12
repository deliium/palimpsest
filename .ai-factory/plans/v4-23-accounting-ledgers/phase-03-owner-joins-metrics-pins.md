# Phase 3: Owner Joins, Metrics, and Pins

Plan: [index.md](index.md)
Tasks: 8-11
Depends on: Phase 2 / Tasks 5-7

## Objective

Join detached owner exports to objective record evidence, classify
researcher-only alignment, assemble one deterministic
`AccountingLedgersAnalysis`, append four metric families to exactly 220, and
sweep every active suite and documentation pin in the same change.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/analysis/credit_relationships_expectations.py` | `join_credit_relationships`, `CreditOwnerJoin` | Owner-token join template; alignment never reaches cognition. |
| `src/analysis/credit_relationships_analysis.py` | `harvest_credit_relationships_analysis`, `empty_*`, `*_digest` | Analysis object template with per-family coverage. |
| `src/analysis/credit_relationships_metrics.py` | four `compute_*` + `assemble_*` | Metric assembly template. |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT` 53; `MetricFamilyId` tail 286-293; credit keys 8971-9019; `_credit_spec` 9278-9306; builders 9397-9438; `_BUILDERS` 9733; append 9946-9949; `validate_metric_catalog` 9971-10004 | Exact 216→220 append points. |
| `src/analysis/metric_service.py` | imports 34-40; inputs 403-405; credit block 2623-2651 | Wiring and `catalog=216` log. |
| `src/analysis/durable_record_metrics.py` | durable record harvest adapters | Reuse existing record evidence; do not duplicate families. |
| `tests/unit/test_credit_relationships_catalog.py` | 21-62 | Catalog order/version/value-key assertions to mirror. |
| `tests/architecture/test_credit_relationships_invariants.py` | 48-64 baseline hash; 67-90 no-bump; 104-113 context authority; 222-230 unowned guard | Invariant template. |
| `tests/unit/test_credit_relationships_pins.py` | 60-71 pins | Pin sweep template. |
| `tests/unit/test_*_docs.py` | family-count assertions | Every active docs pin must move 216→220. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/analysis/accounting_ledgers_expectations.py` | create | Owner join and researcher-only alignment. |
| `src/analysis/accounting_ledgers_analysis.py` | create | `AccountingLedgersAnalysis` harvest/empty/digest. |
| `src/analysis/accounting_ledgers_metrics.py` | create | Four metric documents. |
| `src/analysis/specifications.py` | modify | Count 220, four enum members, four key tuples, four specs, builder append. |
| `src/analysis/metric_service.py` | modify | Inputs + emit block + `catalog=220`. |
| `src/analysis/__init__.py` | modify | Public exports. |
| `tests/unit/test_*_docs.py` | modify | 216→220 count pins. |
| `tests/unit/test_*_pins.py`, `tests/architecture/test_*_invariants.py` | modify | Count and catalog pins. |

---

## Task 8: Join detached owner rows and researcher-only alignment

### Intent

Combine token-only owner exports with committed record/transfer evidence and
classify agreement for researchers only, without creating a shared ledger or
feeding any result back into cognition.

### Implementation Steps

1. Create `src/analysis/accounting_ledgers_expectations.py`:
   - `AccountingOwnerRowInput`: `owner_token`, `entry_token`, `record_token`,
     `entry_kind`, `direction`, `item_kind`, `quantity`, `assessment`,
     `confidence_milli`, `first_tick`, `last_tick`, `window_index`.
   - `join_accounting_owners(*, owner_rows, record_rows, transfer_rows, policy=None) -> AccountingOwnerJoin`.
   - For each owner row:
     - no matching record/transfer → `not_applicable`;
     - matching record and quantity/direction agree within the tolerance →
       `consistent`;
     - remaining gap `>= 750` milli → `inconsistent`;
     - otherwise → `unresolved`.
   - `gap_milli = abs(owner_quantity - evidence_quantity) * 1000 // max(1, evidence_quantity)`,
     clamped to 0..1000; token-only, no payloads.
   - Emit one `AccountingAlignmentRow` per owner entry, capped by policy.
2. Guard: the function accepts no `WorldState`, event store, API object, or peer
   ledger; only frozen owner rows and evidence rows.
3. Set `coverage="missing"` when `owner_rows` is empty; never fabricate an
   `acco-` row.
4. Log `DEBUG accounting_ledger_joined owners=%s alignments=%s`.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class AccountingOwnerJoin:
    owner_rows: tuple[AccountingOwnerRowInput, ...]
    alignments: tuple[AccountingAlignmentRow, ...]
    coverage: str
    notices: tuple[str, ...]

def join_accounting_owners(*, owner_rows, record_rows, transfer_rows, policy=None) -> AccountingOwnerJoin: ...
```

Invariants:
- Alignment is researcher-only; no consumer under `src/agents`, `src/world`,
  `src/simulation` engine, `src/observer`, or stop selectors imports it.
- `not_applicable` is legal and does not imply falsity.
- Owner tokens are opaque 16-hex values.

### Requirement Evidence (when reconciliation applies)

- Original Request "Do not make ledger content objective truth" and "Allow
  agents/institutions to use ledgers as evidence".
- `.ai-factory/ARCHITECTURE.md` — researcher-only alignment never reaches
  cognition.

### Error Handling and Logging

- Duplicate owner/entry token: keep first, count `duplicate_owner_rows`.
- Cap overflow: deterministic prefix + `coverage="partial"`.
- Never log tokens or quantities.

### Tests

Create `tests/unit/test_accounting_ledgers_expectations.py`:
- all four alignment values;
- gap thresholds at 249/250/749/750;
- missing owner rows → `coverage="missing"` and no synthetic row;
- owner row without evidence → `not_applicable`;
- duplicated row handling and cap truncation.

Command: `uv run pytest tests/unit/test_accounting_ledgers_expectations.py -q`.

### Acceptance Criteria

- Alignment is bounded, descriptive, and researcher-only.
- No shared ledger or objective truth object exists.

### Verification

- `uv run pytest tests/unit/test_accounting_ledgers_expectations.py -q` — expected: pass.
- `rg -n "accounting_ledgers_expectations" src/agents src/world src/simulation/engine.py src/observer` — expected: no output.

---

## Task 9: Compose the bounded AccountingLedgersAnalysis harvest

### Intent

Provide one deterministic, digestible analysis object that carries every capped
row family, per-family coverage, and bounded notices for the metric layer,
snapshot layer, and completed-run bridge.

### Implementation Steps

1. Create `src/analysis/accounting_ledgers_analysis.py`:
   - `AccountingLedgersAnalysis` frozen dataclass with `run_id`, `entries`,
     `records`, `conditions`, `flows`, `counterparties`, `alignments`, `owners`,
     `coverage` (mapping with six keys), `truncated`, `notices`, `policy_version`,
     `digest`.
   - `harvest_accounting_ledgers_analysis(*, run_id, events, owner_rows=(), policy=None)`:
     calls Task 6 evidence reconstruction, Task 7 detection, and Task 8 join in
     order; assembles the object; computes the digest.
   - `empty_accounting_ledgers_analysis(run_id)` for absent channels.
   - `accounting_ledgers_analysis_digest(analysis)` over canonical tuples.
2. Coverage per family: `complete` when no truncation, `partial` when a cap was
   hit, `missing` when the source is absent.
3. `truncated` is true when any family is `partial`.
4. Keep the object independent of `simulation`/`experiments` imports.

### Required Interfaces and Contracts

```python
def harvest_accounting_ledgers_analysis(
    *, run_id: str, events: Iterable[object],
    owner_rows: Sequence[AccountingOwnerRowInput] = (),
    policy: AccountingLedgersAnalysisPolicy | None = None,
) -> AccountingLedgersAnalysis: ...

def empty_accounting_ledgers_analysis(run_id: str) -> AccountingLedgersAnalysis: ...
```

Invariants:
- Deterministic ordering for every tuple.
- Digest changes only when visible content changes.
- `truncated` is exactly the OR of `coverage == "partial"`.
- No cognition type is imported.

### Requirement Evidence (when reconciliation applies)

- Original Request; `.ai-factory/ARCHITECTURE.md` analysis isolation.

### Error Handling and Logging

- Empty events: return the empty analysis with all six `missing`.
- `WARN accounting_ledgers_analysis_truncated family=<token>` for each partial.
- `INFO accounting_ledgers_analysis_built run=%s families=%s` (count only; the
  run id is an operational token already allowed elsewhere, but prefer no id —
  log `families=6` only if the run id is not already logged by the caller).

### Tests

Create `tests/unit/test_accounting_ledgers_analysis.py`:
- empty input returns all `missing` and a stable digest;
- complete/partial/missing coverage combinations;
- digest stability under tuple order permutations;
- no `world`/`simulation` imports via AST check.

Command: `uv run pytest tests/unit/test_accounting_ledgers_analysis.py -q`.

### Acceptance Criteria

- One analysis object carries every family and coverage state.
- No live or private state is read.

### Verification

- `uv run pytest tests/unit/test_accounting_ledgers_analysis.py -q` — expected: pass.

---

## Task 10: Append four accounting metric families to 220

### Intent

Append exactly four detached families after the 216 credit families, preserving
the first 216 ids, order, versions, and value keys byte-for-byte, and wire their
computation into the catalog and metric service.

### Implementation Steps

1. `src/analysis/specifications.py`:
   - change `METRIC_FAMILY_COUNT` from 216 to 220 (line 53);
   - add to `MetricFamilyId` after line 293:
     `ACCOUNTING_RECORD_COVERAGE`, `ACCOUNTING_ENTRY_ALIGNMENT`,
     `ACCOUNTING_RECORD_CONDITION`, `ACCOUNTING_FLOW_STRUCTURE`.
2. Add four key tuples after line 9019, each beginning with
   `accounting_ledgers_window_tick`:
   - `ACCOUNTING_RECORD_COVERAGE_KEYS` (10 keys): window tick, record rows,
     entry rows, record-backed entries, unbacked entries, intact rows, damaged
     rows, tombstoned rows, coverage token, availability token.
   - `ACCOUNTING_ENTRY_ALIGNMENT_KEYS` (10 keys): window tick, consistent,
     unresolved, inconsistent, not_applicable, owner rows, evidence rows,
     alignment share milli, coverage token, availability token.
   - `ACCOUNTING_RECORD_CONDITION_KEYS` (12 keys): window tick, unassessed,
     consistent, contradicted, outdated, suspected_fraudulent, damaged, total
     rows, assessed share milli, damaged share milli, coverage token,
     availability token.
   - `ACCOUNTING_FLOW_STRUCTURE_KEYS` (12 keys): window tick, exchange count,
     debt count, inventory count, organizational_resource count, contribution
     count, inflow count, outflow count, holding count, counterparty count,
     coverage token, availability token.
3. Add an `_accounting_spec` helper beside `_credit_spec` (9278-9306) with
   `cohort_window="accounting_ledgers_window_tick"`, the retains/unknown
   availability behavior, and `algorithm_version="1"`.
4. Add four `_spec_accounting_*` builders after 9438 and append them to
   `_BUILDERS` after 9949.
5. `src/analysis/metric_service.py`:
   - import `AccountingLedgersAnalysis` and four `compute_*`;
   - add `accounting_ledgers_analysis` to `MetricComputationInputs` near 405;
   - add the emit block after 2651, logging
     `DEBUG accounting_ledger_metrics_emitted families=4 catalog=220`.
6. `src/analysis/__init__.py`: export the new public symbols.

### Required Interfaces and Contracts

- Families and order:
  1. `accounting_record_coverage@1`
  2. `accounting_entry_alignment@1`
  3. `accounting_record_condition@1`
  4. `accounting_flow_structure@1`
- The first 216 specs are byte-identical (asserted by a SHA-256 baseline).
- Every family's `algorithm_version` is `"1"`.
- `metric_specification()` returns the new specs by id; `validate_metric_catalog`
  passes with 220.

### Requirement Evidence (when reconciliation applies)

- Original Request; `src/analysis/specifications.py` append-only contract.
- `.ai-factory/ARCHITECTURE.md` "Versioned Extension Contract" — append-only
  catalog discipline.

### Error Handling and Logging

- A missing analysis input yields `UNKNOWN` availability, never a zero claim.
- `ERROR metric_catalog_invalid` is raised by the existing validator; no new
  error code.
- Log counts only.

### Tests

Create `tests/unit/test_accounting_ledgers_catalog.py`,
`tests/unit/test_accounting_ledgers_metrics.py`, and
`tests/architecture/test_accounting_ledgers_invariants.py`:
- count 220; `specs[216:220]` exact family ids/versions;
- first 216 SHA-256 baseline unchanged;
- value keys exact per family and `cohort_window` correct;
- four documents in order; empty analysis yields `UNKNOWN`;
- `validate_metric_catalog()` passes.

Command: `uv run pytest tests/unit/test_accounting_ledgers_catalog.py tests/unit/test_accounting_ledgers_metrics.py tests/architecture/test_accounting_ledgers_invariants.py -q`.

### Acceptance Criteria

- Catalog count is exactly 220.
- The first 216 families are unchanged.
- No other package imports `analysis`.

### Verification

- `uv run pytest tests/unit/test_accounting_ledgers_catalog.py tests/unit/test_accounting_ledgers_metrics.py tests/architecture/test_accounting_ledgers_invariants.py -q` — expected: pass.
- `uv run pytest tests/unit/test_credit_relationships_catalog.py -q` — expected: pass after the 220 sweep.

---

## Task 11: Sweep suite-wide ownership and catalog pins

### Intent

Prevent a partially swept tree where one test still expects 216 families or an
unowned `organizations` flag. Every active count, ownership, and catalog pin
moves in this task.

### Implementation Steps

1. Update every active `216` family-count assertion to `220` in
   `tests/unit/test_*_docs.py`, `tests/unit/test_*_pins.py`,
   `tests/architecture/test_*_invariants.py`, and any README/docs pin test.
2. Update V4 ownership assertions:
   - keep 14 contexts / 12 flags / 8 owned / 4 unowned;
   - assert `organizations` remains `OWNER_SCOPED`, `uses_existing_events=True`,
     prerequisites `()`, owner packages unchanged;
   - assert `markets_credit` is unchanged;
   - assert no test expects `organizations` or `markets_credit` to be unowned.
3. Add `tests/unit/test_accounting_ledgers_pins.py`:
   - `METRIC_FAMILY_COUNT == 220`;
   - 43 commands, 73 observer semantic types;
   - replay-v27 / codec `v25`;
   - Alembic `0017`;
   - `/v1` and `observer-protocol-v1`;
   - policy version `accounting-ledgers.v1`.
4. Add `tests/architecture/test_accounting_ledgers_invariants.py`:
   - 14/12/8/4 counts;
   - no `runner-config-v57` constant or accepted write;
   - no new V4 context or flag name;
   - `accounting` symbols absent from `src/observer` and `src/api/observer*`.
5. Add the two scientific regression gates to the verification set (no edits
   expected, flags stay off):
   `tests/unit/test_v1_regression_gate.py` and
   `tests/unit/test_v2_scientific_invariants.py`.
6. Emit no new logging.

### Required Interfaces and Contracts

- Every pin is asserted in exactly one owning test file plus the shared
  architecture invariants.
- No test file asserts a historical count as current.
- Historical prose in docs may keep old counts only inside dated sections.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` "Versioned Extension Contract" and
  "Capability ownership".
- `.ai-factory/RULES.md` axiom 5.

### Error Handling and Logging

- Not applicable (test-only task).

### Tests

- The sweep itself is verified by running the affected files.

Command:
`uv run pytest tests/unit/test_accounting_ledgers_pins.py tests/architecture/test_accounting_ledgers_invariants.py tests/unit/test_credit_relationships_pins.py tests/architecture/test_v4_architecture_invariants.py tests/architecture/test_v4_context_registry.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py -q`.

### Acceptance Criteria

- No active assertion expects 216 or an unowned V4 flag.
- The new pin file and invariant file pass.

### Verification

- The command above — expected: pass.
- `rg -n "216 metric families|METRIC_FAMILY_COUNT = 216" tests/` — expected: no output.

## Phase Risks and Mitigations

- Risk: a docs test outside the sweep keeps asserting 216 and fails late.
  Mitigation: the sweep is a dedicated task and the final `rg` check is part of
  verification.
- Risk: the append accidentally reorders the catalog.
  Mitigation: the first-216 SHA-256 baseline is an architecture invariant.
- Risk: owner alignment is imported by cognition.
  Mitigation: AST boundary tests plus an explicit grep in Task 8 verification.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
