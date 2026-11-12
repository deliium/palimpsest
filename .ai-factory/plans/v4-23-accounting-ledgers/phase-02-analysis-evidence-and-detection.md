# Phase 2: Analysis Evidence and Detection

Plan: [index.md](index.md)
Tasks: 5-7
Depends on: Phase 1 / Task 1

## Objective

Build the detached, read-only analysis pipeline: a locked analysis contract and
policy, reconstruction of committed record/transfer/contribution evidence plus
`acc_v1` speech, and deterministic detection of accounting entries, record
conditions, counterparty structure, and per-window flow distributions from
committed events only.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/analysis/credit_relationships_contract.py` | policy version, prefixes, enums, forbidden keys, token minters | Exact contract silhouette for a detached feature. |
| `src/analysis/credit_relationships_policy.py` | `CreditRelationshipsAnalysisPolicy`, locked map, window helpers | Copy the frozen-int policy with `_INT_RANGES` and `window_index_for_tick`. |
| `src/analysis/credit_relationships_rows.py` | row dataclasses + harvest container | Row families are frozen detached DTOs, never cognition types. |
| `src/analysis/credit_relationships_events.py` | `credit_evidence_rows_from_events`, digest, `_MAX_NOTICES` | Reconstructs claims/transfers from committed events with bounded notices. |
| `src/analysis/credit_relationships_detection.py` | performances, distributions, counterparties, layer separation | Descriptive statistics with `insufficient_samples`. |
| `src/analysis/credit_relationships_expectations.py` | owner joins and researcher-only alignment | Owner-token-only joins. |
| `src/analysis/credit_relationships_analysis.py` | harvest, empty result, digest | One deterministic analysis object. |
| `src/analysis/durable_record_metrics.py` | durable record harvest rows | Existing durable-record evidence shape to reuse, not duplicate. |
| `src/world/events.py` | `ArtifactCreated` 1400-1434; `ArtifactModified` 1437-1468; `ArtifactCopied` 1548-1590; `ArtifactAnnotated` 1593-1625; `ArtifactDamaged` 1628-1661; `ArtifactPartiallyLost` 1664-1704; `ArtifactDestroyed` 1507-1545; `ExchangeCompleted` 2515-2564; `Given` 639-656; `ItemCrafted` 1105+; `ProjectContributed` 2591-2614; `ProjectCompleted` 2648-2674; `PublicGoodBenefit` 2677-2718 | The only objective record/transfer/contribution sources. `Given` carries no item kind; `ExchangeCompleted` carries kinds. |
| `src/world/events.py` | `Talked`/`Told` ~639-656, 708-764 | Source of committed `acc_v1` claims. |
| `src/analysis/emergent_prices_events.py` | 155-331 | Reference for bounded speech/event harvesting. |
| `src/world/structured_commitments.py` | kinds 24-49 | `debt`/`future_exchange` context for alignment hints, never a truth source. |
| `src/world/collective_projects.py` | `ProjectContribution` 314-339; tails 449-475 | Contribution effort shape (`labor_delta` 0/1 + item id). |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/analysis/accounting_ledgers_contract.py` | create | Detached contract, enums, prefixes, forbidden keys, token minters. |
| `src/analysis/accounting_ledgers_policy.py` | create | Frozen policy, locked map, window helpers. |
| `src/analysis/accounting_ledgers_rows.py` | create | Detached row dataclasses and harvest container. |
| `src/analysis/accounting_ledgers_events.py` | create | Committed-event evidence reconstruction. |
| `src/analysis/accounting_ledgers_detection.py` | create | Entry/condition/counterparty/flow detection. |
| `src/analysis/__init__.py` | modify | Public exports only. |

---

## Task 5: Lock the accounting analysis contract, policy, and caps

### Intent

Freeze the detached vocabulary, policy, caps, window math, and token prefixes so
that evidence reconstruction, detection, metrics, snapshot, and API all agree
without re-deciding anything.

### Implementation Steps

1. Create `src/analysis/accounting_ledgers_contract.py`:
   - `ACCOUNTING_LEDGERS_ANALYSIS_POLICY_VERSION = "accounting-ledgers.v1"`.
   - Prefixes: `acco-` (owner), `accr-` (record), `accc-` (claim), `accf-` (flow),
     `acccp-` (counterparty), `acca-` (alignment), `accpeer-` (peer token);
     hex length 16.
   - `AccountingAnalysisLayer` (`objective_record`, `owner_claim`,
     `analytical_entry`), `AccountingAnalysisError`, forbidden field names.
   - Token minters: `accounting_owner_token`, `accounting_record_row_token`,
     `accounting_claim_token`, `accounting_flow_token`,
     `accounting_counterparty_token`, `accounting_alignment_token`.
   - `assert_accounting_layer_separation(*rows)`.
2. Create `src/analysis/accounting_ledgers_policy.py` with
   `AccountingLedgersAnalysisPolicy` and `ACCOUNTING_LEDGERS_ANALYSIS_LOCKED_POLICY`:
   - `window_ticks=32`, `max_windows=512`;
   - `max_record_events=200_000`, `max_transfer_events=200_000`,
     `max_contribution_events=200_000`, `max_claim_events=200_000`;
   - `max_owner_rows=4_096`, `max_entry_rows=4_096`, `max_record_rows=2_048`,
     `max_counterparty_rows=1_024`, `max_flow_rows=4_096`,
     `max_alignment_rows=4_096`, `max_condition_rows=1_024`, `max_owners=4_096`,
     `max_item_kinds=1_024`;
   - `min_distribution_samples=4`, `max_quantity=64`,
     `max_valuation_milli=64_000`, `alignment_consistent_milli=250`,
     `alignment_inconsistent_milli=750`.
   - `window_index_for_tick`, `window_bounds`.
3. Every numeric field is validated against a `_INT_RANGES` map; booleans and
   non-ints raise `AccountingAnalysisError("accounting_analysis_invalid_policy")`.
4. Log only policy name and window count; never quantities or owners.

### Required Interfaces and Contracts

```python
ACCOUNTING_LEDGERS_ANALYSIS_POLICY_VERSION: Final[str] = "accounting-ledgers.v1"

@dataclass(frozen=True, slots=True)
class AccountingLedgersAnalysisPolicy:
    window_ticks: int = 32
    max_windows: int = 512
    ...

def default_accounting_ledgers_analysis_policy() -> AccountingLedgersAnalysisPolicy: ...
def window_index_for_tick(tick: int, policy=None) -> int: ...
def window_bounds(index: int, policy=None) -> tuple[int, int]: ...
```

Invariants:
- One locked policy value per process.
- Window index is `tick // 32` and is rejected at `>= 512`.
- Alignment thresholds are ordered.

### Requirement Evidence (when reconciliation applies)

- Original Request "records may be correct / wrong / outdated / fraudulent /
  damaged" requires descriptive, not adjudicative, analysis.
- `src/analysis/specifications.py:9278-9306` — the `_credit_spec` availability
  contract pattern.
- `.ai-factory/ARCHITECTURE.md` "Key Principles" 1 — three authorities stay
  separate.

### Error Handling and Logging

- Invalid policy: `WARN accounting_ledgers_policy_invalid field=<name>` then raise.
- Invalid window: `AccountingAnalysisError("accounting_analysis_invalid_window")`.
- No payload or identifier logging.

### Tests

Create `tests/unit/test_accounting_ledgers_analysis_policy.py`:
- defaults and boundaries for every int;
- bool/non-int/out-of-range rejection;
- window index/bounds at 0, 31, 32, 511, 512;
- locked map matches the dataclass exactly.

Command: `uv run pytest tests/unit/test_accounting_ledgers_analysis_policy.py -q`.

### Acceptance Criteria

- The analysis contract is frozen and independent of cognition imports.
- Window math matches the credit/prices convention.

### Verification

- `uv run pytest tests/unit/test_accounting_ledgers_analysis_policy.py -q` — expected: pass.

---

## Task 6: Extract committed record, transfer, and contribution evidence

### Intent

Reconstruct the objective half of accounting from committed events only: record
creation/mutation/damage, item transfers, and collective contribution/benefit
evidence — plus committed `acc_v1` claims from `Talked`/`Told`.

### Implementation Steps

1. Create `src/analysis/accounting_ledgers_rows.py`:
   - `AccountingRecordEvidenceRow`: `record_token`, `record_genre`,
     `observed_integrity`, `content_revision`, `author_token`, `tick`,
     `event_ordinal`, `copy_generation`, `tombstoned`.
   - `AccountingTransferEvidenceRow`: `transfer_token`, `giver_token`,
     `receiver_token`, `item_kind`, `quantity`, `tick`, `event_ordinal`.
   - `AccountingContributionEvidenceRow`: `project_token`, `actor_token`,
     `accepted`, `labor_delta`, `tick`, `event_ordinal`.
   - `AccountingClaimEvidenceRow`: `claim_token`, `record_token`,
     `entry_kind`, `direction`, `item_kind`, `quantity`, `assessment`,
     `confidence_milli`, `speaker_token`, `tick`, `event_ordinal`.
   - `AccountingEvidenceHarvest`: four tuples plus `notices`,
     `coverage` (`complete`/`partial`/`missing`).
2. Create `src/analysis/accounting_ledgers_events.py`:
   - `accounting_evidence_rows_from_events(events, *, run_id, policy=None)`.
   - Reconstruct records from `ArtifactCreated`, `ArtifactModified`,
     `ArtifactCopied`, `ArtifactAnnotated`, `ArtifactDamaged`,
     `ArtifactPartiallyLost`, `ArtifactDestroyed`; derive `record_token` with the
     same `accrec-<16 hex>` function used by cognition (analysis must not import
     cognition; duplicate the pure hash helper in the contract module with a
     parity test).
   - Reconstruct transfers from `ExchangeCompleted` (`give_item_kinds` /
     `take_item_kinds`; quantity is the tuple length) and `Given` (quantity 1,
     `item_kind="unknown"` unless a committed `ItemCrafted` for the same
     `item_id` appears in the harvest, in which case use that kind). Never read
     bootstrap state for kinds.
   - Reconstruct contributions from `ProjectContributed` and
     `PublicGoodBenefit`.
   - Reconstruct claims from `Talked`/`Told` relations whose subject is `acc_v1`;
     parse with a local strict parser that mirrors the world codec (no world
     import).
   - Apply event caps with deterministic prefixes; set `coverage="partial"` and
     append one notice per truncated family; set `coverage="missing"` when a
     family has no events at all.
3. Add `accounting_evidence_digest(harvest)` over canonical tuples.
4. Log `DEBUG accounting_ledger_evidence records=%s transfers=%s contributions=%s claims=%s`.

### Required Interfaces and Contracts

```python
def accounting_evidence_rows_from_events(
    events: Iterable[object], *, run_id: str,
    policy: AccountingLedgersAnalysisPolicy | None = None,
) -> AccountingEvidenceHarvest: ...
```

Invariants:
- Reads only committed event objects; never a store, runtime, API object,
  `WorldState`, or peer ledger.
- Tombstoned records are counted, never treated as an available entry.
- Claims from `Talked`/`Told` are testimony; they are not objective facts.
- Deterministic order: `(tick, event_ordinal, token)`.

### Requirement Evidence (when reconciliation applies)

- Original Request "Support records of exchanges / debts / inventories /
  organizational resources / contributions".
- `src/analysis/emergent_prices_events.py:155-331` — committed speech evidence
  pattern.
- `.ai-factory/ARCHITECTURE.md` — analysis reads detached committed facts only.

### Error Handling and Logging

- Malformed frame: drop, increment `malformed_claims`, continue.
- Unknown item kind: map to `unknown` and count.
- `WARN accounting_ledger_evidence_truncated family=<token> kept=%s` (count only).
- Never log tokens, item kinds, quantities, or speakers.

### Tests

Create `tests/unit/test_accounting_ledgers_events.py` and
`tests/unit/test_accounting_ledgers_analysis_helpers.py`:
- record lifecycle reconstruction including tombstone and damage;
- transfer and contribution extraction from synthetic committed events;
- `acc_v1` speech parsing, unrelated predicates ignored, malformed dropped;
- digest token parity with the cognition token helper;
- cap/truncation and coverage states;
- Hypothesis: arbitrary event order permutations produce the same digest.

Command: `uv run pytest tests/unit/test_accounting_ledgers_events.py tests/unit/test_accounting_ledgers_analysis_helpers.py -q`.

### Acceptance Criteria

- All five record kinds have an evidence source.
- Coverage is explicit (`complete`/`partial`/`missing`).
- No live or private state is read.

### Verification

- `uv run pytest tests/unit/test_accounting_ledgers_events.py tests/unit/test_accounting_ledgers_analysis_helpers.py -q` — expected: pass.

---

## Task 7: Detect accounting entries, record conditions, and flow distributions

### Intent

Turn evidence rows into descriptive accounting entries, record-condition
counts, counterparty aggregates, and per-window flow distributions in integer
milli — never a balance, total value, or solvency judgment.

### Implementation Steps

1. Create `src/analysis/accounting_ledgers_rows.py` additions:
   - `AnalyticalAccountingEntryRow`: `entry_token`, `record_token`,
     `entry_kind`, `direction`, `item_kind`, `quantity`, `assessment`,
     `confidence_milli`, `first_tick`, `last_tick`, `window_index`,
     `source_layers`.
   - `AccountingRecordConditionRow`: `condition`, `record_count`,
     `quantity` histogram, `share_milli`, `window_index`.
   - `AccountingFlowRow`: `entry_kind`, `direction`, `event_count`,
     `quantity_sum`, `owner_count`, `counterparty_count`, `window_index`.
   - `AccountingCounterpartyRow`: `counterparty_token`, `entry_count`,
     `kinds`, `first_tick`, `last_tick`.
   - `AccountingAlignmentRow`: `entry_token`, `alignment`, `gap_milli`,
     `record_token`.
2. Create `src/analysis/accounting_ledgers_detection.py`:
   - `detect_accounting_entries(harvest, policy=None)` merges record evidence and
     `acc_v1` claims into analytical entries keyed by `(record_token, kind,
     direction, item_kind, window_index)`; claims without a record keep
     `record_token=None`.
   - `detect_record_conditions(entries, policy=None)` produces one row per
     assessment value with record counts and share in milli; `insufficient_samples`
     when the total is below 4.
   - `detect_accounting_flows(entries, transfers, contributions, policy=None)`
     produces per-window/per-kind/direction counts and `quantity_sum` (a claimed
     sum, never a balance).
   - `detect_accounting_counterparties(entries, policy=None)`.
   - `assert_accounting_layer_separation` call at the end of each detector.
3. Distribution helper `accounting_distribution_summary(values, policy=None)`
   returning `available`/`insufficient_samples`, sample count, min/p25/median/
   p75/max, IQR, dispersion, and five bin shares in milli.
4. Log `DEBUG accounting_ledger_detected entries=%s conditions=%s flows=%s`.

### Required Interfaces and Contracts

```python
def detect_accounting_entries(harvest, policy=None) -> tuple[AnalyticalAccountingEntryRow, ...]: ...
def detect_record_conditions(entries, policy=None) -> tuple[AccountingRecordConditionRow, ...]: ...
def detect_accounting_flows(entries, transfers, contributions, policy=None) -> tuple[AccountingFlowRow, ...]: ...
def detect_accounting_counterparties(entries, policy=None) -> tuple[AccountingCounterpartyRow, ...]: ...
def accounting_distribution_summary(values, policy=None) -> AccountingDistributionSummary: ...
```

Invariants:
- No `balance`, `total_value`, `net_worth`, `solvency`, `score`, or `ranking`.
- Quantities are integer sums of claims; shares and gaps are integer milli.
- Fewer than four samples is `insufficient_samples`, never a fabricated median.
- Entries with `quantity > 64` are `out_of_range`: excluded and counted.
- Layers stay separated: objective rows, owner claims, analytical entries.

### Requirement Evidence (when reconciliation applies)

- Original Request "Do not make ledger content objective truth" — descriptive
  only.
- `src/analysis/credit_relationships_detection.py` — the bounded descriptive
  distribution pattern.
- `.ai-factory/ARCHITECTURE.md` "Key Principles" 1.

### Error Handling and Logging

- Empty input: return `()` and `coverage="missing"` upstream.
- Invalid value: exclude and count `out_of_range`.
- `WARN accounting_ledger_row_out_of_range family=<token>` (count only).
- Never log quantities, item kinds, counterparties, or entry tokens.

### Tests

Create `tests/unit/test_accounting_ledgers_detection.py` and
`tests/unit/test_accounting_ledgers_detection_properties.py`:
- all five kinds and six directions detected;
- condition histograms sum to the entry count and shares are 0..1000;
- `insufficient_samples` below four; `available` at four;
- out-of-range quantity excluded and counted;
- layer separation raises on a mixed row list;
- Hypothesis: detected counts never exceed caps and shares never exceed 1000.

Command: `uv run pytest tests/unit/test_accounting_ledgers_detection.py tests/unit/test_accounting_ledgers_detection_properties.py -q`.

### Acceptance Criteria

- Detection produces only descriptive counts, sums, and milli shares.
- No output field implies truth, balance, or solvency.
- Truncation is deterministic and reported.

### Verification

- `uv run pytest tests/unit/test_accounting_ledgers_detection.py tests/unit/test_accounting_ledgers_detection_properties.py -q` — expected: pass.
- `rg -n "balance|solvency|net_worth|total_value" src/analysis/accounting_ledgers_*.py` — expected: no output.

## Phase Risks and Mitigations

- Risk: a claimed `quantity_sum` is read as an objective balance.
  Mitigation: the field is named `quantity_sum`, documented as a claim sum, and
  forbidden-name tests reject `balance`/`total`.
- Risk: re-deriving record tokens diverges from cognition.
  Mitigation: a parity test hashes the same inputs through both helpers.
- Risk: `acc_v1` relations from unrelated predicates pollute evidence.
  Mitigation: only `subject == "acc_v1"` relations are parsed; everything else is
  ignored.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
