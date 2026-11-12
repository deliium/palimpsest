# Phase 2: Analysis Evidence and Detection

Plan: [index.md](index.md)
Tasks: 5-7
Depends on: Phases 1 (ledger contract) for the vocabulary consumed by analysis

## Objective

Build a detached, read-only credit analysis substrate from committed events
only. It reconstructs `crd_v1` claims, physical `Given` transfers, performance
outcomes, repayment-ratio distributions, and counterparty aggregates. It never
reads `WorldState`, cognition ledgers, persistence, API objects, or observers,
and it never mints a canonical debt, credit score, or enforceable obligation.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/emergent_prices_contract.py` | policy token 50, prefixes 51-55, enums 63-143, forbidden keys 148-178, layer prefixes 180-196, token helpers 231-311 | Exact detached contract and token pattern to mirror |
| `src/analysis/emergent_prices_policy.py` | ranges 23-43, policy 47-82, locked map 87-89, window helpers 98-129 | Exact capped policy and window pattern |
| `src/analysis/emergent_prices_rows.py` | `ExchangePriceEvidenceRow` 70-137, `PriceQuoteEvidenceRow` 139-186, `PriceEvidenceHarvest` 188-214, `PriceDistributionRow` 261-346 | Frozen detached row validation pattern |
| `src/analysis/emergent_prices_events.py` | `_kind_index` 63-78, `_pairing` 107-144, `price_evidence_rows_from_events` 155-331 | Committed-event reconstruction, stable ordering, dedupe, truncation |
| `src/analysis/emergent_prices_detection.py` | `distribution_summary` 77-136, `detect_venue_distributions` 152-222, layer assertion 359-407 | Nearest-rank quantiles, five bin shares, deterministic grouping |
| `src/world/events.py` | `Given` 639-656, `Talked` 708-726, `Told` 747-764, `ExchangeCompleted` 2515-2564 | Committed speech and transfer event shapes |
| `src/world/structured_commitments.py` | `COMMITMENT_KINDS` 16-26, `COMMITMENT_ACTS` 27-35 | Objective promise vocabulary available as supporting evidence |
| `src/analysis/market_institutions_contract.py` | venue token helper | Existing stable token convention if a venue context is later needed |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/credit_relationships_contract.py` | create | Closed enums, tokens, forbidden keys, layer prefixes, errors |
| `src/analysis/credit_relationships_policy.py` | create | Locked analysis policy, cap ranges, window helpers |
| `src/analysis/credit_relationships_rows.py` | create | Frozen evidence, owner, relationship, performance, distribution, counterparty, alignment rows |
| `src/analysis/credit_relationships_events.py` | create | Committed `crd_v1` claims and `Given` transfer evidence |
| `src/analysis/credit_relationships_detection.py` | create | Performance outcomes, repayment distributions, counterparty aggregates, layer assertion |
| `src/analysis/__init__.py` | modify | Export the new public analysis symbols |
| `src/world/credit_relationships.py` | no change | Neutral `crd_v1` codec created in Task 4; analysis imports its parser |
| `src/agents/cognition/credit_relationships.py` | no change | Analysis imports no cognition module |
| `src/agents/cognition/credit_relationships_communication.py` | no change | Analysis uses the world codec, not the cognition selector |
| `src/world/events.py` | no change | No event, field, or rule is added |

## Task 5: Lock the credit analysis contract, policy, and caps

### Intent

Fix the detached vocabulary and every cap before event reconstruction or
metric emission depends on it. The analysis layer must be unable to grow a bank,
a canonical debt, or a global credit registry by accident.

### Implementation Steps

1. Create `src/analysis/credit_relationships_contract.py` with module docstring:
   "Detached credit relationship analysis over committed speech and transfer
   evidence. No canonical debt, credit score, bank, money, or enforcement."
2. Add constants:
   `CREDIT_RELATIONSHIPS_ANALYSIS_POLICY_VERSION = "credit-relationships.v1"`,
   `CREDIT_OWNER_PREFIX = "credo-"`, `CREDIT_PERFORMANCE_PREFIX = "credp-"`,
   `CREDIT_DISTRIBUTION_PREFIX = "credd-"`,
   `CREDIT_COUNTERPARTY_PREFIX = "credcp-"`,
   `CREDIT_PEER_PREFIX = "credpeer-"`,
   `CREDIT_CLAIM_PREFIX = "credcl-"`,
   `CREDIT_ALIGNMENT_PREFIX = "creda-"`,
   `CREDIT_ANALYSIS_HEX_LEN = 16`.
3. Add `CreditCoverage(StrEnum)` with `complete`, `partial`, `missing`.
4. Add `CreditLayer(StrEnum)` with `objective_claim`, `owner_credit`,
   `analytical_performance`, `comparison_view`.
5. Add `CreditSampleSource(StrEnum)` with `proposed`, `agreed`.
6. Add `CreditDistributionStatus(StrEnum)` with `available`,
   `insufficient_samples`.
7. Add `CreditPerformanceOutcome(StrEnum)` with `active`,
   `partially_repaid`, `repaid`, `defaulted`, `forgiven`, `disputed`, `expired`,
   `insufficient_evidence`.
8. Add `CreditAlignment(StrEnum)` with `consistent`, `unresolved`,
   `inconsistent`, `not_applicable`.
9. Add `CREDIT_ANALYSIS_FORBIDDEN_KEYS` frozenset with `bank`, `banker`, `loan`,
   `interest`, `interest_rate`, `apr`, `credit_score`, `credit_limit`,
   `default_probability`, `money`, `currency`, `legal_tender`, `deposit`,
   `reserve`, `enforceable_debt`, `enforcement`, `collection`, `allocation`,
   `quota`, `canonical_credit`, `ranking`, `recommendation`.
10. Add `CREDIT_LAYER_FORBIDDEN_PREFIXES`:
    - objective claim layer forbids `credo-`, `credp-`, `credd-`, `credcp-`,
      `creda-`;
    - owner credit layer forbids `credp-`, `credd-`, `credcp-`, `creda-`;
    - analytical performance layer forbids `event_token`, `raw_event_token`;
    - comparison view forbids `event_token`, `raw_event_token`.
11. Add `CREDIT_ANALYSIS_NOTICE_CODES` frozenset with exactly
    `credit_claim_malformed`, `credit_evidence_truncated`,
    `credit_ratio_out_of_range`, `credit_direction_conflict`,
    `credit_performance_truncated`, `credit_distribution_truncated`,
    `credit_counterparty_truncated`, `credit_owner_truncated`,
    `credit_alignment_truncated`, `credit_terms_mismatch`,
    `credit_missing_owner_rows`, `credit_missing_evidence`.
12. Add `CREDIT_ANALYSIS_ERROR_CODES` frozenset with
    `credit_analysis_invalid_policy`, `credit_analysis_invalid_row`,
    `credit_analysis_invalid_window`, `credit_analysis_cap_exceeded`,
    `credit_analysis_forbidden_key`, `credit_analysis_layer_leak`,
    `credit_analysis_missing_input`.
13. Add `CreditRelationshipAnalysisError(ValueError)` with `reason_code`.
14. Add stable token helpers:
    - `credit_owner_token(owner_token, anchor_token, window_index)` -> `credo-`
      plus 16 hex;
    - `credit_performance_token(anchor_token, window_index)` -> `credp-`;
    - `credit_distribution_token(principal_kind, repayment_kind,
      sample_source, window_index)` -> `credd-`;
    - `credit_counterparty_token(left_token, right_token, window_index)` ->
      `credcp-` over sorted party tokens;
    - `credit_peer_token(party_token)` -> `credpeer-` plus 16 hex over the
      party token, used only for detached owner-export joins;
    - `credit_claim_token(event_token, act, direction)` -> `credcl-` plus 16
      hex, used to identify one claim relation without exposing the event body;
    - `credit_alignment_token(owner_token, anchor_token, window_index)` ->
      `creda-`.
    Hash material joins length-prefixed parts with `\x1f` exactly like
    `_token_hash` in `emergent_prices_contract.py:231-234`.
15. Create `src/analysis/credit_relationships_policy.py` with
    `CreditRelationshipsAnalysisPolicy` and `_INT_RANGES`:
    `window_ticks (1, 4096)`, `max_windows (1, 65536)`,
    `max_claim_events (1, 1_000_000)`,
    `max_transfer_events (1, 1_000_000)`,
    `max_owner_rows (1, 16_384)`, `max_claim_rows (1, 16_384)`,
    `max_relationship_rows (1, 65_536)`,
    `max_performance_rows (1, 65_536)`,
    `max_distribution_rows (1, 65_536)`,
    `max_counterparty_rows (1, 16_384)`,
    `max_alignment_rows (1, 65_536)`,
    `max_owners (1, 16_384)`, `max_item_kinds (1, 1_024)`,
    `min_distribution_samples (1, 1_000)`,
    `max_ratio_milli (1, 1_000_000)`,
    `alignment_high_milli (1, 1_000)`, `alignment_low_milli (0, 1_000)`.
16. Defaults: `window_ticks=32`, `max_windows=512`,
    `max_claim_events=200_000`, `max_transfer_events=200_000`,
    `max_owner_rows=4_096`, `max_claim_rows=4_096`,
    `max_relationship_rows=8_192`, `max_performance_rows=8_192`,
    `max_distribution_rows=8_192`, `max_counterparty_rows=1_024`,
    `max_alignment_rows=4_096`, `max_owners=4_096`,
    `max_item_kinds=1_024`, `min_distribution_samples=4`,
    `max_ratio_milli=64_000`, `alignment_high_milli=750`,
    `alignment_low_milli=250`.
    Reject `alignment_low_milli >= alignment_high_milli`.
17. Add `default_credit_relationships_analysis_policy()`,
    `window_index_for_tick(tick, policy=None)`, and
    `window_bounds(window_index, policy)`, mirroring the price helpers exactly.

### Required Interfaces and Contracts

```python
CREDIT_RELATIONSHIPS_ANALYSIS_POLICY_VERSION = "credit-relationships.v1"

@dataclass(frozen=True, slots=True)
class CreditRelationshipsAnalysisPolicy:
    window_ticks: int = 32
    max_windows: int = 512
    max_claim_events: int = 200_000
    max_transfer_events: int = 200_000
    max_owner_rows: int = 4_096
    max_claim_rows: int = 4_096
    max_relationship_rows: int = 8_192
    max_performance_rows: int = 8_192
    max_distribution_rows: int = 8_192
    max_counterparty_rows: int = 1_024
    max_alignment_rows: int = 4_096
    max_owners: int = 4_096
    max_item_kinds: int = 1_024
    min_distribution_samples: int = 4
    max_ratio_milli: int = 64_000
    alignment_high_milli: int = 750
    alignment_low_milli: int = 250
```

- No analysis module imports `agents.cognition`, `simulation`, `experiments`,
  `persistence`, `api`, or `observer`.
- Tokens are content-addressed hashes, never retained event ids in analytical
  rows.
- Policy token is shared with cognition by literal value, not by import.

### Requirement Evidence

- Detached analysis isolates objective, owner, analytical, and comparison
  layers: `src/analysis/emergent_prices_contract.py:63-196`.
- Window and cap discipline: `src/analysis/emergent_prices_policy.py:23-129`.
- No canonical price/credit field: `.ai-factory/ARCHITECTURE.md` "Key
  Principles" 1 and 5.

### Error Handling and Logging

- Every invalid policy/row/window raises `CreditRelationshipAnalysisError` with
  a safe code.
- `WARN credit_relationships_policy_invalid field=%s` logs field names only.
- Never log anchors, counterparties, item kinds, ratios, confidence, or owner
  tokens.

### Tests

- `tests/unit/test_credit_relationships_analysis_contract.py`: exact enums,
  forbidden keys, layer-prefix leaks, token determinism/symmetry, policy bounds,
  window helper boundaries.
- `tests/unit/test_credit_relationships_analysis_policy.py`: every cap accepted
  at boundary and rejected outside; locked defaults unchanged.

### Acceptance Criteria

- The contract module imports only the standard library.
- Every token helper is deterministic across processes and returns the exact
  prefix plus 16 lowercase hex.
- No analysis field or enum member names a bank, loan, interest, credit score,
  money, or canonical credit.

### Verification

- `uv run pytest tests/unit/test_credit_relationships_analysis_contract.py tests/unit/test_credit_relationships_analysis_policy.py -q`
- `uv run mypy src/analysis/credit_relationships_contract.py src/analysis/credit_relationships_policy.py`
- Expected: all pass.

## Task 6: Extract committed credit claims and transfer evidence

### Intent

Reconstruct only what committed events actually say: `crd_v1` claims inside
`Talked`/`Told` and `Given` transfers. Nothing is inferred from inventories,
intent, or another owner's ledger.

### Implementation Steps

1. Create `src/analysis/credit_relationships_rows.py`:
   - `CreditClaimEvidenceRow(claim_id, tick, window_index, event_token,
     actor_token, counterparty_token, act, direction, anchor_token,
     principal_kind, principal_quantity, repayment_kind, repayment_quantity,
     paid_quantity, opened_tick, due_tick, condition, collateral_kind,
     collateral_item_kind, collateral_quantity, confidence_milli, coverage)`.
     Validate the `credcl-` claim id, enums, positive quantities,
     `paid_quantity` rules, `due_tick` optional, collateral consistency, and
     coverage.
   - `CreditTransferEvidenceRow(tick, window_index, event_token, actor_token,
     recipient_token, item_kind, quantity, coverage)`. `item_kind` is a stable
     token or `unknown`; `quantity` is a positive integer.
   - `CreditEvidenceHarvest(claims, transfers, coverage, notices, claim_count,
     transfer_count)`.
   - All rows call a shared `_forbid_keys` against
     `CREDIT_ANALYSIS_FORBIDDEN_KEYS`.
2. Create `src/analysis/credit_relationships_events.py`:
   - import only `world.events` (`Given`, `Talked`, `Told`,
     `ExchangeCompleted`, `Fed`, `WorldEvent`) and analysis modules;
   - build a `kind_of` index from `ExchangeCompleted.give_item_ids`/
     `give_item_kinds`, `take_item_ids`/`take_item_kinds`, and `Fed.item_id`/
     `item_kind`, exactly like `emergent_prices_events._kind_index`;
   - sort events by `(tick, sequence)`; reject duplicate event tokens;
   - for `Talked`/`Told`, iterate `details.utterance.content.relations`, call
     `parse_credit_claim_relation` from `world.credit_relationships` (the
     neutral codec), and emit one `CreditClaimEvidenceRow` per valid relation;
   - set `claim_id` with `credit_claim_token(event_id, act, direction)` so two
     relations in one utterance remain distinct;
   - the actor is the event's `actor_id`; the counterparty is
     `details.recipient_id`;
   - if a relation is a `crd_v1` subject but malformed, count one
     `credit_claim_malformed` notice and continue;
   - for `Given`, emit `CreditTransferEvidenceRow(actor=event.actor_id,
     recipient=details.recipient_id, item_kind=kind_of.get(item_id.value,
     "unknown"), quantity=1)`;
   - cap claims at `max_claim_events` and transfers at `max_transfer_events`
     with deterministic event order and add `credit_evidence_truncated`;
   - coverage is `missing` when both families are empty, `partial` when any
     notice or unresolved item kind exists, otherwise `complete`.
3. Add `credit_evidence_digest(harvest)` over canonical row fields (no raw
   event bodies).
4. Export the new rows and harvest from `analysis/__init__.py`.

### Required Interfaces and Contracts

```python
def credit_evidence_rows_from_events(
    events: Sequence[object],
    *,
    policy: CreditRelationshipsAnalysisPolicy | None = None,
) -> CreditEvidenceHarvest: ...
```

- A `crd_v1` frame from an unrelated subject is ignored.
- A malformed or oversize frame never raises out of the harvest; it increments
  the notice set once.
- A `Given` transfer with an unresolved item kind is retained with
  `item_kind="unknown"` and `coverage=partial`; it is never guessed from a
  holder's inventory.
- No event is rewritten, reordered within a tick, or deduplicated across
  distinct event tokens.

### Requirement Evidence

- Speech events carry relations in `utterance.content.relations`:
  `src/world/events.py:708-764`.
- The neutral `crd_v1` codec lives in `world`, so analysis may parse committed
  frames without importing cognition; `world` imports no other first-party
  package (`src/world/structured_commitments.py:1-5`).
- `Given` carries only recipient and item id; kind resolution must use existing
  event facts: `src/world/events.py:639-656`.
- Price event reconstruction is the bounded precedent:
  `src/analysis/emergent_prices_events.py:155-331`.

### Error Handling and Logging

- `WARN credit_claim_malformed count=%s` and
  `WARN credit_evidence_truncated family=%s` log counts only.
- `DEBUG credit_evidence_harvested claims=%s transfers=%s coverage=%s` logs
  counts and a status token only.
- Never log anchors, actor/counterparty tokens, item kinds, or quantities.

### Tests

- `tests/unit/test_credit_relationships_events.py`: valid claim extraction;
  unrelated frame ignored; malformed/oversize dropped; duplicate event token
  rejected; deterministic ordering; transfer kind resolution from exchange/fed;
  unresolved kind partial; caps and notices.
- `tests/unit/test_credit_relationships_evidence_bounds.py`: property bounds on
  claim count, transfer count, notice count, and digest stability.

### Acceptance Criteria

- The harvest contains exactly one row per valid claim relation and one row per
  `Given`.
- No row includes a raw event body, item id, inventory, or peer ledger field.
- Empty input returns `coverage=missing`, zero counts, and no notices.
- Repeated harvest of the same events returns identical counts and digest.

### Verification

- `uv run pytest tests/unit/test_credit_relationships_events.py tests/unit/test_credit_relationships_evidence_bounds.py -q`
- `uv run mypy src/analysis/credit_relationships_events.py src/analysis/credit_relationships_rows.py`
- Expected: all pass.

## Task 7: Detect credit performances and repayment distributions

### Intent

Turn objective claim and transfer evidence into descriptive performance
outcomes, repayment-ratio distributions, and counterparty aggregates. These are
analytical classifications, not an objective debt ledger, a credit score, or a
collection recommendation.

### Implementation Steps

1. Create `src/analysis/credit_relationships_detection.py`.
2. Add `credit_distribution_summary(ratios, *, policy=None)` with exact
   nearest-rank math copied from `emergent_prices_detection.distribution_summary`
   but returning a credit status:
   - below `min_distribution_samples` -> `insufficient_samples`, zero
     quantiles/bins, actual sample count;
   - otherwise min, p25 at `(count-1)//4`, median at `(count-1)//2`, p75 at
     `3*(count-1)//4`, max, `iqr=p75-p25`,
     `dispersion=iqr*1000//max(1,median)`, five bin shares using the q20/q40/
     q60/q80 boundaries, last share forced to make the sum exactly 1000.
3. Add `detect_credit_performances(evidence, *, window_end=None, policy=None)`:
   - default `window_end` to the maximum claim or transfer tick when omitted;
   - group claims by `anchor_token` and `window_index`;
   - derive the first terms from the earliest `propose`/`accept`/`renegotiate`
     claim; if none exists, use the earliest claim's terms;
   - if claims for one anchor disagree on direction or principal/repayment
     kinds, use the earliest claim and add `credit_direction_conflict` with
     partial coverage;
   - count `propose`, `accept`, `decline`, `withdraw`, `repay`, `default`,
     `renegotiate`, `forgive`, `dispute` claims;
   - cumulative declared repayment is the maximum `paid_quantity` across repay
     claims, capped at `repayment_quantity`;
   - derive the debtor and creditor tokens from the earliest claim's
     `direction`: `owner_debtor` means actor is debtor and counterparty is
     creditor; `owner_creditor` means actor is creditor and counterparty is
     debtor;
   - observed transfer count is the number of `Given` rows from the debtor to
     the creditor only; creditor-to-debtor principal transfers are not counted
     as repayment;
   - outcome priority: `repaid` when cumulative paid reaches repayment
     quantity; else `defaulted` when a default claim exists; else `forgiven`;
     else `disputed`; else `partially_repaid` when any repay claim exists; else
     `expired` when `due_tick` is present and `window_end > due_tick + 8` with
     no repayment/default/forgiveness/dispute claim; else `active`; if there
     are no claims and no transfers -> `insufficient_evidence`;
   - emit one `CreditPerformanceRow` with `performance_id` from
     `credit_performance_token(anchor, window)`, claim counts, paid/principal/
     repayment quantities, transfer count, outcome, and coverage;
   - deterministic sort by `(window_index, performance_id)`; cap with
     `credit_performance_truncated` and mark retained rows partial.
4. Add `detect_credit_distributions(evidence, *, policy=None)`:
   - sample only claims with `act in {propose, accept, renegotiate}`;
   - `sample_source=proposed` for `propose`, `agreed` for `accept` and
     `renegotiate`;
   - compute `ratio = min(max_ratio_milli, repayment_quantity*1000 //
     principal_quantity)`; skip zero or out-of-range ratios and count one
     notice;
   - group by `(window_index, principal_kind, repayment_kind, sample_source)`;
   - emit one `CreditDistributionRow` with `distribution_id`, sample count,
     quantiles, IQR, dispersion, five bins, status, coverage;
   - cap with `credit_distribution_truncated` and mark partial.
5. Add `detect_credit_counterparties(evidence, *, policy=None)`:
   - group claims by `(window_index, sorted pair of actor/counterparty tokens)`;
   - `counterparty_token` from `credit_counterparty_token`;
   - counts: `relationship_count` (distinct anchors), `owner_count` (distinct
     actors), `claim_count`, `repay_claim_count`, `default_claim_count`,
     `forgive_claim_count`, `dispute_claim_count`, `renegotiate_claim_count`,
     `observed_transfer_count`;
   - coverage complete/partial/missing; cap with
     `credit_counterparty_truncated`.
6. Add `assert_credit_layer_separation(layers)` mirroring the price assertion:
   reject forbidden field names and cross-layer token prefixes.
7. Sort every family deterministically and truncate only as a stable prefix.

### Required Interfaces and Contracts

```python
def credit_distribution_summary(
    ratios: Sequence[int], *, policy=None
) -> object: ...

def detect_credit_performances(
    evidence: CreditEvidenceHarvest,
    *,
    window_end: int | None = None,
    policy=None,
) -> tuple[CreditPerformanceRow, ...]: ...

def detect_credit_distributions(
    evidence: CreditEvidenceHarvest, *, policy=None
) -> tuple[CreditDistributionRow, ...]: ...

def detect_credit_counterparties(
    evidence: CreditEvidenceHarvest, *, policy=None
) -> tuple[CreditCounterpartyRow, ...]: ...
```

- Performance outcomes are descriptive labels, never a probability, score, or
  ranking.
- Distributions report `sample_count`, five quantiles, IQR, dispersion, and five
  bin shares in integer milli; never one canonical repayment ratio.
- `proposed` and `agreed` samples are never pooled.
- A distribution with fewer than four samples is `insufficient_samples`.
- Transfers are counts only; no amount is inferred from an unresolved `Given`
  item.

### Requirement Evidence

- Price distribution math and sample-source separation:
  `src/analysis/emergent_prices_detection.py:77-222`.
- V3-17 commitment statuses inform outcome labels but are not copied:
  `src/agents/cognition/structured_commitments.py:33-44`.
- No objective debt/score vocabulary: `.ai-factory/ARCHITECTURE.md`
  "Anti-Patterns".

### Error Handling and Logging

- Invalid evidence types raise `CreditRelationshipAnalysisError`.
- `WARN credit_performance_truncated count=%s`,
  `credit_distribution_truncated`, `credit_counterparty_truncated`,
  `credit_ratio_out_of_range` log counts only.
- `DEBUG credit_detection_completed performances=%s distributions=%s
  counterparties=%s` logs counts only.

### Tests

- `tests/unit/test_credit_relationships_detection.py`: outcome priority;
  partial/full repayment; self-default vs overdue; proposed/agreed separation;
  quantile/bins/IQR; insufficient samples; out-of-range ratio; deterministic
  sort; caps.
- `tests/unit/test_credit_relationships_detection_properties.py`: Hypothesis
  properties for quantile ordering, bin sum 1000, and monotone sample counts.

### Acceptance Criteria

- A single anchor yields exactly one performance row per window.
- Identical proposed and agreed ratios produce two separate distributions.
- No distribution row contains a field named `credit_score`, `interest`, or
  `canonical_credit`.
- Truncation always marks retained rows `partial` and never reports more rows
  than the cap.

### Verification

- `uv run pytest tests/unit/test_credit_relationships_detection.py tests/unit/test_credit_relationships_detection_properties.py -q`
- `uv run mypy src/analysis/credit_relationships_detection.py`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: analysis treats a `crd_v1` claim as an objective agreement.
  Mitigation: every row is evidence; performance outcomes are descriptive and
  researcher-facing only.
- Risk: transfer counts are mistaken for repayment amounts.
  Mitigation: `Given` contributes a count only; amounts come from declared
  terms, and unresolved kinds remain `unknown`.
- Risk: proposed and agreed terms are pooled into one ratio.
  Mitigation: separate `CreditSampleSource` values and separate distribution
  rows.
- Risk: a performance classifier becomes a credit score.
  Mitigation: closed outcome labels, no numeric score, no ranking, no
  probability.

## Phase Completion Checklist

- Every Task 5-7 in this phase satisfies its acceptance criteria.
- Focused unit/property tests and mypy pass.
- `index.md` checkboxes are updated only after verified completion.
