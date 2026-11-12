# Phase 3: Owner Joins, Metrics, and Pins

Plan: [index.md](index.md)
Tasks: 8-11
Depends on: Phase 2 (evidence, detection, policy)

## Objective

Join detached owner credit rows to objective performance evidence, keep
researcher-only alignment separate from cognition, compose one bounded
`CreditRelationshipsAnalysis`, append four metric families (212 -> 216), and
sweep every active ownership/catalog pin without rewriting history.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/emergent_prices_expectations.py` | owner input rows 50-180, join 183-330, unit summary 333-388 | Exact owner-to-distribution join and alignment pattern |
| `src/analysis/emergent_prices_analysis.py` | analysis dataclass 62-104, empty 107-130, harvest 150-288, digest 304-315 | Exact bounded composition and digest pattern |
| `src/analysis/emergent_prices_metrics.py` | constant 41-44, `_document` 74-123, four computes 143-415 | Exact `MetricDocument` emission and coverage pattern |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT` 53, enum tail 286-289, price keys 8921-8965, price specs 9269-9310, builders 9814-9818 | Exact append-only metric catalog seam |
| `src/analysis/metric_service.py` | input field 397, price emission 2586-2614 | Metric service wiring point |
| `tests/unit/test_emergent_prices_pins.py` | 52-80 | Active pin assertions to extend |
| `tests/architecture/test_emergent_prices_invariants.py` | `BASELINE_208` 37, catalog digest 92-101 | Baseline-digest pattern for prior catalog preservation |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/credit_relationships_rows.py` | modify | Add owner input, analytical relationship, alignment rows |
| `src/analysis/credit_relationships_expectations.py` | create | Owner join and researcher-only alignment |
| `src/analysis/credit_relationships_analysis.py` | create | `CreditRelationshipsAnalysis`, harvest, digest |
| `src/analysis/credit_relationships_metrics.py` | create | Four compute functions and assembly |
| `src/analysis/__init__.py` | modify | Export public analysis and metric symbols |
| `src/analysis/specifications.py` | modify | Append four families and raise count to 216 |
| `src/analysis/metric_service.py` | modify | Input field, emission block, catalog log |
| `tests/unit/test_credit_relationships_metrics.py` | create | Four-family behavior and unknown states |
| `tests/unit/test_credit_relationships_catalog.py` | create | Exact ids/order/keys and 216 |
| `tests/unit/test_emergent_prices_pins.py` | modify | 212 -> 216 active pins |
| `tests/architecture/test_emergent_prices_invariants.py` | modify | Keep first-212 baseline, assert 216 |
| `tests/architecture/test_credit_relationships_invariants.py` | create | First-212 baseline and 216 |
| `tests/unit/test_*_catalog.py`, `tests/unit/test_*_docs.py`, `tests/architecture/test_*` | modify | Every active 212 pin becomes 216; historical text stays |

## Task 8: Join detached owner rows and researcher-only alignment

### Intent

Correlate an owner's exported credit beliefs with objective claim and transfer
evidence without letting that correlation become a truth test, a score, or a
cognition input.

### Implementation Steps

1. Add `CreditOwnerInput` to `credit_relationships_rows.py`:
   `owner_token, window_index, anchor_token, counterparty_token, direction,
   principal_kind, principal_quantity, repayment_kind, repayment_quantity,
   paid_quantity, due_tick, condition, collateral_kind, collateral_quantity,
   status, confidence_milli, level, trust_milli, expectation_milli,
   claim_count, promise_count, first_tick, last_tick, coverage`.
   Validate owner token, peer token prefix `credpeer-`, enum values, counts,
   `paid_quantity <= repayment_quantity`, `first_tick <= last_tick`, and
   coverage.
2. Add `AnalyticalCreditRelationshipRow`:
   `relationship_id, window_index, owner_token, counterparty_token, direction,
   anchor_token, principal_kind, principal_quantity, repayment_kind,
   repayment_quantity, repayment_ratio_milli, due_tick, condition,
   collateral_kind, collateral_quantity, status, confidence_milli,
   expectation_milli, trust_milli, claim_count, coverage`.
   `relationship_id` is `credit_owner_token(owner, anchor, window)`.
3. Add `CreditAlignmentRow`:
   `alignment_id, window_index, owner_token, anchor_token, alignment,
   owner_status, analytical_outcome, owner_paid_quantity,
   declared_repayment_quantity, observed_transfer_count, gap_milli, coverage`.
   `alignment_id` is `credit_alignment_token(owner, anchor, window)`.
4. Add `join_credit_relationships(owner_inputs, performances, *, policy=None)
   -> CreditOwnerJoin` with `relationships`, `alignments`, `coverage`,
   `notices`.
5. For each owner row:
   - match a performance by `(anchor_token, window_index)`;
   - keep the owner row even when no performance exists;
   - set `alignment=not_applicable` when the owner row has no repayment/default
     claim and no matching performance;
   - compute `gap_milli = abs(owner_paid_quantity - observed_transfer_count) *
     1000 // max(1, repayment_quantity)`;
   - `consistent` when gap <= 250, owner status in
     `{partially_repaid, repaid}`, and observed transfer count > 0;
   - `inconsistent` when gap >= 750, or owner status is `repaid` and observed
     transfer count is 0, or owner status is `defaulted` and a full repayment
     was claimed;
   - otherwise `unresolved`.
6. Sort owner rows by `(owner_token, window_index, anchor_token)` and alignment
   rows by `(window_index, alignment_id)`; cap each at
   `max_relationship_rows`/`max_alignment_rows` with one truncation notice per
   family and `coverage=partial` on retained rows.
7. Never let an owner row overwrite an analytical row, and never let alignment
   feed cognition, prompts, memory, world state, observer semantics, or stop
   selectors.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class CreditOwnerJoin:
    relationships: tuple[AnalyticalCreditRelationshipRow, ...]
    alignments: tuple[CreditAlignmentRow, ...]
    coverage: CreditCoverage
    notices: tuple[str, ...]

def join_credit_relationships(
    owner_inputs: Sequence[CreditOwnerInput],
    performances: Sequence[CreditPerformanceRow],
    *,
    policy: CreditRelationshipsAnalysisPolicy | None = None,
) -> CreditOwnerJoin: ...
```

- Owner rows are detached exports, not live ledgers.
- Absent owner exports yield empty relationships/alignments and
  `coverage=missing`; no owner token is fabricated.
- Alignment is researcher-only and never numeric beyond `gap_milli`.

### Requirement Evidence

- Price owner join and researcher-only alignment:
  `src/analysis/emergent_prices_expectations.py:50-395`.
- Credit owner export shape is created in Phase 4 Task 14; this task defines the
  input contract it must satisfy.
- Three-layer separation: `src/analysis/emergent_prices_contract.py:63-76`.

### Error Handling and Logging

- Invalid owner row raises `CreditRelationshipAnalysisError`
  (`credit_analysis_invalid_row`).
- `WARN credit_owner_truncated family=%s count=%s` logs counts only.
- `DEBUG credit_owner_join relationships=%s alignments=%s coverage=%s` logs
  counts and status token only; never owner tokens or anchors.

### Tests

- `tests/unit/test_credit_relationships_expectations.py`: consistent/
  unresolved/inconsistent/not_applicable; no performance; no owner rows; gap
  boundaries 250/750; cap/truncation; owner row retained on mismatch.
- `tests/unit/test_credit_relationships_leakage.py` is extended with an
  owner-join case that asserts no `credp-`/`credd-`/`credcp-`/`creda-` value
  appears in the owner layer.

### Acceptance Criteria

- A matching repaid owner row with one observed transfer is `consistent`.
- A claimed repayment with zero observed transfers is `inconsistent`.
- An owner row without a matching performance is retained and
  `not_applicable`.
- No owner row changes a performance or distribution row.

### Verification

- `uv run pytest tests/unit/test_credit_relationships_expectations.py -q`
- Expected: all pass.

## Task 9: Compose the bounded CreditRelationshipsAnalysis harvest

### Intent

Provide the single detached result object that snapshot, metrics, publication,
and docs consume. It must expose coverage per family and deterministic digests.

### Implementation Steps

1. Create `src/analysis/credit_relationships_analysis.py`:
   `CreditRelationshipsAnalysis(window_tick, policy_version, evidence_coverage,
   owner_coverage, relationship_coverage, performance_coverage,
   distribution_coverage, counterparty_coverage, alignment_coverage, coverage,
   relationships, claims, performances, distributions, counterparties,
   alignments, notices, claim_count, transfer_count, evidence=())`.
2. Add `empty_credit_relationships_analysis()` with every coverage `missing`,
   empty tuples, and zero counts.
3. Add `harvest_credit_relationships_analysis(*, committed_events,
   owner_inputs=(), policy=None, window_end=None)`:
   - reject non-iterable/missing events;
   - return empty analysis for no events;
   - call `credit_evidence_rows_from_events`;
   - compute `latest_tick` from event ticks and validate `window_end`;
   - call `detect_credit_performances(evidence, window_end=window_end)`,
     `detect_credit_distributions`, `detect_credit_counterparties`;
   - call `join_credit_relationships`;
   - compose overall coverage exactly like price analysis:
     `missing` when evidence is missing or all analytical families are empty;
     `partial` when any family is partial/missing or any distribution is
     `insufficient_samples`; otherwise `complete`;
   - union and sort notices, capped at 8.
4. Add `credit_relationships_analysis_digest(analysis)` using canonical JSON
   with sorted keys, compact separators, `ensure_ascii=True`, enum `.value`
   conversion, and SHA-256 hex.
5. Add `assert_credit_layer_separation` call on the four layers in the harvest.
6. Export from `analysis/__init__.py`.

### Required Interfaces and Contracts

```python
def harvest_credit_relationships_analysis(
    *,
    committed_events: Iterable[object],
    owner_inputs: Sequence[CreditOwnerInput] = (),
    policy: CreditRelationshipsAnalysisPolicy | None = None,
    window_end: int | None = None,
) -> CreditRelationshipsAnalysis: ...
```

- `claims` and `evidence` may carry objective event tokens; analytical rows
  must not.
- `window_end` defaults to the newest committed tick.
- The digest is stable for identical inputs and differs when a claim, term,
  outcome, or distribution changes.

### Requirement Evidence

- Price analysis composition and coverage:
  `src/analysis/emergent_prices_analysis.py:62-315`.
- No live authority: `.ai-factory/ARCHITECTURE.md` "Key Principles" 1.

### Error Handling and Logging

- Missing events raise `credit_analysis_missing_input`.
- Invalid window raises `credit_analysis_invalid_window`.
- `INFO credit_analysis_harvested relationships=%s performances=%s
  distributions=%s coverage=%s` logs counts and status only.

### Tests

- `tests/unit/test_credit_relationships_analysis.py`: empty input; full harvest;
  coverage transitions; notice union; deterministic digest; owner-input join;
  no event mutation.
- `tests/unit/test_credit_relationships_analysis_determinism.py`: repeated
  harvest and digest equality; shuffled event order with same tick/sequence
  rejected or normalized deterministically.

### Acceptance Criteria

- One harvest returns one deterministic object with all six family coverages.
- Empty evidence returns the explicit empty analysis, not a fabricated row.
- Changing one claim term changes the digest.
- No analysis object contains an `AgentCommand` or `WorldState`.

### Verification

- `uv run pytest tests/unit/test_credit_relationships_analysis.py tests/unit/test_credit_relationships_analysis_determinism.py -q`
- `uv run mypy src/analysis/credit_relationships_analysis.py`
- Expected: all pass.

## Task 10: Append four credit metric families to 216

### Intent

Add exactly four analysis-only families after the existing 212, preserving the
first 212 ids, order, algorithm versions, and value keys byte-for-byte.

### Implementation Steps

1. In `src/analysis/specifications.py`, append four `MetricFamilyId` members
   after `MARKET_PRICE_CONVERGENCE`:
   `CREDIT_RELATIONSHIP_FORMATION = "credit_relationship_formation"`,
   `CREDIT_REPAYMENT_PERFORMANCE = "credit_repayment_performance"`,
   `CREDIT_TERM_ALIGNMENT = "credit_term_alignment"`,
   `CREDIT_DISTRIBUTION_STRUCTURE = "credit_distribution_structure"`.
2. Add exact key tuples:
   - `CREDIT_RELATIONSHIP_FORMATION_KEYS = ("window_tick",
     "relationship_count", "proposed_count", "accepted_count",
     "declined_count", "withdrawn_count", "renegotiated_count",
     "distinct_counterparty_pairs", "collateral_claim_count",
     "conditional_count", "mean_confidence_milli", "relationship_coverage")`;
   - `CREDIT_REPAYMENT_PERFORMANCE_KEYS = ("window_tick",
     "performance_count", "repaid_count", "partially_repaid_count",
     "defaulted_count", "forgiven_count", "disputed_count", "expired_count",
     "declared_repayment_count", "observed_transfer_count",
     "mean_repayment_ratio_milli", "performance_coverage")`;
   - `CREDIT_TERM_ALIGNMENT_KEYS = ("window_tick", "alignment_row_count",
     "consistent_count", "unresolved_count", "inconsistent_count",
     "not_applicable_count", "mean_gap_milli", "alignment_coverage")`;
   - `CREDIT_DISTRIBUTION_STRUCTURE_KEYS = ("window_tick",
     "distribution_count", "available_distribution_count",
     "insufficient_sample_count", "sample_count",
     "median_repayment_ratio_milli", "mean_iqr_milli",
     "mean_dispersion_milli", "distribution_coverage")`.
3. Add `_credit_spec` mirroring `_price_spec` with
   `evidence_inputs={EvidenceStage.OBJECTIVE_EVENT_STATE}`,
   `cohort_window="credit_relationships_window_tick"`,
   `deceased_policy="retain_committed_credit_evidence"`,
   `zero_holding_policy="no_credit_claims_or_owner_rows_unknown"`,
   `self_edge_policy="owner tokens never create self-edges"`,
   `censoring_policy="insufficient samples remain explicit"`,
   `availability_behavior="explicit_unknown_without_credit_evidence"`.
4. Add four spec builders with populations/denominators:
   - `owner_scoped_credit_relationships` / `observed_credit_relationships`,
     `DenominatorKind.EVALUABLE_CLAIMS`;
   - `analytical_credit_performances` / `observed_credit_performances`,
     `DenominatorKind.OCCURRENCE`;
   - `owner_scoped_credit_alignment` / `observed_alignment_rows`,
     `DenominatorKind.EVALUABLE_CLAIMS`;
   - `analytical_credit_distributions` / `observed_distribution_samples`,
     `DenominatorKind.ACTIVE_EDGES`.
5. Append the four builders after `_spec_market_price_convergence`.
6. Set `METRIC_FAMILY_COUNT = 216`.
7. Create `src/analysis/credit_relationships_metrics.py` with:
   - `_POLICY_TOKEN = "credit-relationships"`;
   - `_document` using `source_kind="credit_relationships_analysis"`,
     `notes_code="detached_credit_analysis"`;
   - four compute functions with signatures
     `(analysis, *, run_id, input_revision) -> MetricDocument`;
   - `assemble_credit_relationship_metrics(analysis, *, run_id,
     input_revision) -> tuple[MetricDocument, ...]`.
8. `compute_credit_relationship_formation`: state from
   `relationship_coverage`; values from count fields; `observed` = complete
   relationship rows, `expected` = all relationship rows.
9. `compute_credit_repayment_performance`: state from
   `performance_coverage`; counts by outcome; mean ratio from performance rows
   with positive principal quantity, computing
   `repayment_quantity*1000//principal_quantity` and averaging with integer
   floor; `observed` = complete rows.
10. `compute_credit_term_alignment`: state from `alignment_coverage`; counts by
    alignment; mean gap over rows with numeric gap; never infer beyond rows.
11. `compute_credit_distribution_structure`: state from
    `distribution_coverage`; available/insufficient counts; sample total;
    median across available distribution medians; mean IQR/dispersion integer
    floors.
12. In `src/analysis/metric_service.py`, import
    `CreditRelationshipsAnalysis` and the four computes; add
    `credit_relationships_analysis: CreditRelationshipsAnalysis | None = None`
    to `MetricServiceInputs`; add an emission block after the price block:
    four `_safe(...)` calls and
    `INFO credit_relationship_metrics_emitted families=4 catalog=216`.
13. Export the new metric functions and analysis type from `analysis/__init__.py`.

### Required Interfaces and Contracts

```python
MetricFamilyId.CREDIT_RELATIONSHIP_FORMATION
MetricFamilyId.CREDIT_REPAYMENT_PERFORMANCE
MetricFamilyId.CREDIT_TERM_ALIGNMENT
MetricFamilyId.CREDIT_DISTRIBUTION_STRUCTURE
```

- New families append; no existing family id, order, version, or key changes.
- Unknown coverage emits `MetricAvailability.UNKNOWN`, empty values, and zero
  coverage.
- Partial coverage emits `MetricAvailability.PARTIAL` with observed/expected
  counts.
- No value key is named `bank`, `loan`, `interest`, `credit_score`, or
  `canonical_credit`.

### Requirement Evidence

- Append-only catalog contract: `src/analysis/specifications.py:53, 286-289,
  8921-8965, 9269-9310, 9814-9818`.
- Metric document and coverage contract: `src/analysis/metric_service.py:397,
  2586-2614`.
- V4-21 catalog was 212; V4-22 must append exactly four:
  `.ai-factory/ARCHITECTURE.md` baseline table.

### Error Handling and Logging

- Invalid analysis type raises `CreditRelationshipAnalysisError`.
- Forbidden metric key raises `credit_analysis_forbidden_key`.
- `INFO credit_relationship_metrics_emitted families=4 catalog=216`.
- Never log owner tokens, anchors, item kinds, ratios, or confidence.

### Tests

- `tests/unit/test_credit_relationships_metrics.py`: present/partial/unknown for
  each family; exact value keys; observed/expected counts; forbidden-key
  rejection.
- `tests/unit/test_credit_relationships_catalog.py`: four ids append after
  `market_price_convergence`; exact order; exact version/value keys; count 216;
  `metric_specification` lookup works.

### Acceptance Criteria

- `len(all_metric_specifications()) == 216`.
- The first 212 specs are unchanged.
- Each new family emits one document, and unknown analysis emits four UNKNOWN
  documents without values.
- No new family is emitted when `credit_relationships_analysis is None`.

### Verification

- `uv run pytest tests/unit/test_credit_relationships_metrics.py tests/unit/test_credit_relationships_catalog.py -q`
- `uv run mypy src/analysis/credit_relationships_metrics.py`
- Expected: all pass.

## Task 11: Sweep suite-wide ownership and catalog pins

### Intent

Make every active pin agree on 216 and eight owned V4 flags. Historical
narrative counts such as "208 -> 212" stay as history and must not be rewritten.

### Implementation Steps

1. Create `tests/unit/test_credit_relationships_pins.py`:
   - `CREDIT_RELATIONSHIPS_POLICY_VERSION == "credit-relationships.v1"`;
   - `CREDIT_FRAME_SUBJECT == "crd_v1"`;
   - `METRIC_FAMILY_COUNT == 216`;
   - 43 commands, 73 observer semantics, 14 V4 contexts, 12 V4 flags,
     `len(V4_OWNED_CAPABILITY_FLAGS) == 8` with `markets_credit` owned;
   - Alembic `0017`, no `0018` file, max accepted event schema 27, codec `v25`
     accepted, `/v1`, `observer-protocol-v1`;
   - no credit module text contains `runner-config-v57`.
2. Create `tests/architecture/test_credit_relationships_invariants.py`:
   - define `BASELINE_212 =
     "87fd875c1b53e588e19af116ca6c974515a5e8fa4b878901def526c096eb496e"`
     as the SHA-256 of `family_id|algorithm_version|joined value_keys` for
     `specs[:212]` with `\x1f`/`\x1e` separators;
   - assert `METRIC_FAMILY_COUNT == 216` and that baseline digest;
   - assert the four credit families occupy positions 212-215 and their
     algorithm versions are unchanged;
   - assert no credit context/flag is declared, no v57 exists, no `0018` file
     exists, and ownership is still eight;
   - assert `agents.cognition.credit_relationships` does not import
     `simulation`, `analysis`, `experiments`, `persistence`, `api`, or
     `observer`;
   - assert `analysis.credit_relationships_*` does not import cognition,
     simulation, experiments, persistence, api, or observer.
3. Update `tests/architecture/test_emergent_prices_invariants.py`:
   - rename `BASELINE_208` to `BASELINE_212` and hash `specs[:212]`;
   - assert `METRIC_FAMILY_COUNT == 216`;
   - keep the existing seam, count, and version assertions unchanged.
4. Sweep active pins mechanically, then review each diff:
   - `rg -l "METRIC_FAMILY_COUNT == 212|== 212|212 families|212 metric|catalog=212" tests`
   - update only assertions or current-state prose that mean "the active
     catalog"; change them to 216;
   - do not change historical strings such as `(208 -> 212)` or `V4-21 ...
     212`.
   - `rg -l "supply_chains.*unowned|markets_credit.*unowned" tests` and correct
     any stale ownership fixture; V4-21 already owned `markets_credit`.
5. Update `tests/unit/test_emergent_prices_docs.py` and every
   `test_*_docs.py` that asserts the current catalog count.
6. Add a regression assertion that no test expects `markets_credit` to be
   unowned.

### Required Interfaces and Contracts

- The first 212 catalog entries keep id, order, algorithm version, and value
  keys.
- Active count is 216 everywhere.
- Historical plan/document counts remain historical.
- `V4_OWNED_CAPABILITY_FLAGS` stays exactly
  `{organizations, formal_rules, legal_disputes, diplomacy, organized_conflict,
  infrastructure_networks, supply_chains, markets_credit}`.

### Requirement Evidence

- Existing active pins: `tests/unit/test_emergent_prices_pins.py:52-80`,
  `tests/architecture/test_emergent_prices_invariants.py:37-101`.
- Append-only rule: `.ai-factory/ARCHITECTURE.md` "Requirements for later
  changes" 1.
- Current ownership: `src/simulation/compatibility.py`
  (`V4_OWNED_CAPABILITY_FLAGS`).

### Error Handling and Logging

- No runtime logging; this is a pin/test sweep.
- If a sweep cannot decide whether `212` is historical or active, leave it and
  record the path in the verification receipt rather than guessing.

### Tests

- `tests/unit/test_credit_relationships_pins.py`
- `tests/architecture/test_credit_relationships_invariants.py`
- `tests/architecture/test_emergent_prices_invariants.py`
- every swept catalog/docs test

### Acceptance Criteria

- No active test or current-state document asserts 212.
- The first-212 baseline digest still matches.
- No test expects `markets_credit` unowned.
- No credit module mentions `runner-config-v57`.

### Verification

- `uv run pytest tests/unit/test_credit_relationships_pins.py tests/architecture/test_credit_relationships_invariants.py tests/architecture/test_emergent_prices_invariants.py -q`
- `uv run pytest tests/unit -q -k "catalog or docs or pins"`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: owner rows overwrite analytical rows.
  Mitigation: separate row types, separate layers, no assignment between them.
- Risk: alignment becomes a truth test.
  Mitigation: researcher-only labels; no cognition import; no score.
- Risk: catalog append changes prior keys.
  Mitigation: first-212 digest baseline and exact append position.
- Risk: a blanket 212 -> 216 replacement rewrites history.
  Mitigation: only active-count assertions/prose change; historical strings
  stay.

## Phase Completion Checklist

- Every Task 8-11 in this phase satisfies its acceptance criteria.
- Focused unit, catalog, pin, and architecture tests pass.
- `index.md` checkboxes are updated only after verified completion.
