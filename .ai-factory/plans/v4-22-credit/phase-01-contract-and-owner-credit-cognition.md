# Phase 1: Contract and Owner-Scoped Credit Cognition

Plan: [index.md](index.md)
Tasks: 1-4
Depends on: none

## Objective

Introduce the locked `credit-relationships.v1` owner-scoped contract: bounded
credit terms, repayment/default/renegotiation/forgiveness/dispute beliefs,
`crd_v1` speech frames, activation derived from `markets_credit` plus the
existing V3-17 `structured_commitments` channel, trust-sensitive willingness,
and full carry through perspective, checkpoints, and the runner result. No
command, event, observer semantic type, V4 flag, V4 context, runner schema, or
migration is added.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/agents/cognition/structured_commitments.py` | `COMMITMENT_STATUSES` 33-44, `CommitmentInterpretation` 89-203, `StructuredCommitmentLedger` 206-234, `apply_structured_commitment_update` 353-647, `commitment_social_requests` 841-929 | Existing promise/debt seam and owner-local status vocabulary to extend, never replace |
| `src/world/structured_commitments.py` | `COMMITMENT_KINDS` 16-26, `COMMITMENT_ACTS` 27-35, `COMMITMENT_OWED_BY` 36-39 | Closed objective promise vocabulary; `debt` and `future_exchange` are credit evidence |
| `src/agents/cognition/subjective_value.py` | `ValuationRow` 51-92, `SubjectiveValuationLedger` 95-128 | Owner valuation remains an input, not a price or a credit score |
| `src/agents/cognition/emergent_prices.py` | policy 282-338, `PriceExpectationRow` 565-645, `EmergentPriceLedger` 657-695, `apply_emergent_price_update` 919-1166 | Exact owner-ledger, cap, confidence, and update pattern to mirror |
| `src/agents/cognition/emergent_prices_communication.py` | `PriceClaim` 103-155, encode 158-174, parse 177-222, relation 225-249, attachment 297-351 | Exact bounded-frame and one-relation attachment pattern to mirror as `crd_v1` |
| `src/agents/cognition/configuration.py` | `CognitionPriceMode` 486-496, fields 775-778, validation 1390-1411, material 1863-1867, resolved 2182-2183 | Mode/policy wiring pattern |
| `src/agents/cognition/contracts.py` | `Perspective` 143-177, owner validation 440-447 | Owner-scoped perspective carry point |
| `src/agents/cognition/models.py` | `SubjectiveSnapshot` 723-745, loop result 4018, proposal 4382 | Snapshot/result carry points |
| `src/simulation/runner.py` | `_cognition_config_for` 1024-1040, price activation 1473-1490, config bind 1725-1746, checkpoint validation 5048-5075, result export 5897-5910 | Activation and export point |
| `src/simulation/runner_models.py` | `RUNNER_SCHEMA_VERSION_V56` 152, `markets_credit` 1149, result ledger validation 6871-6929 | No v57; owner-ordered result ledger validation |
| `src/simulation/agent_runtime.py` | `_commit_emergent_prices` 1392-1419, perspective 2613, commit 3115-3116, restore 3711-3714, checkpoint 3910 | Carry/checkpoint pattern |
| `src/agents/cognition/deliberation.py` | price attachment 1405-1417, commitment proposal 1594-1604 | Speech attachment hook and existing commitment path |
| `src/social/relationships.py` | `RelationshipDimension.TRUST` 56-67, signed-unit validation 111-117 | Subjective trust input; signed trust maps to `[0, 1000]` |
| `src/agents/cognition/communication.py` | `project_trust_inputs` 88-109 | Existing deterministic trust projection to mirror |
| `src/simulation/v4_architecture.py` | `MARKETS_CREDIT` 212-228 | Owned context; non-goals already forbid a central bank and enforced debt |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/agents/cognition/credit_relationships.py` | create | Policy, enums, identifiers, terms, claims, rows, ledger, folding, willingness |
| `src/world/credit_relationships.py` | create | Neutral `crd_v1` frame vocabulary and strict encode/parse |
| `src/agents/cognition/credit_relationships_communication.py` | create | Claim selection and one-relation attachment |
| `src/world/__init__.py` | modify | Export the frame codec if the world façade requires it |
| `src/agents/cognition/configuration.py` | modify | `CognitionCreditMode`, mode/policy fields, validation, material, resolved copy |
| `src/agents/cognition/loop.py` | modify | Mode/policy attrs, `_prepare_credit_relationships`, incoming-claim parser, result/proposal propagation, fork state |
| `src/agents/cognition/models.py` | modify | Snapshot/result/proposal fields |
| `src/agents/cognition/contracts.py` | modify | `Perspective.credit_relationships` and owner validation |
| `src/agents/cognition/fork_state.py` | modify | `prepared_credit_relationships` field and type check |
| `src/agents/cognition/deliberation.py` | modify | Attach one `crd_v1` relation after selected command |
| `src/agents/cognition/__init__.py` | modify | Public exports |
| `src/simulation/perception.py` | modify | `build_perspective(..., credit_relationships=None)` |
| `src/simulation/run_control.py` | modify | `AgentRuntimeCheckpoint.credit_relationships` |
| `src/simulation/agent_runtime.py` | modify | Commit/clear, perspective pass, restore, runtime checkpoint |
| `src/simulation/runner.py` | modify | Derive mode, validate result ledgers, export |
| `src/simulation/runner_models.py` | modify | `SimulationRunnerResult.credit_relationship_ledgers` validation |
| `src/simulation/__init__.py` | modify | Export public credit ledger symbols if the façade requires them |
| `tests/unit/test_credit_relationships_helpers.py` | create | Shared owner/peer/terms/claim/signal builders |
| `src/agents/cognition/emergent_prices.py` | no change | Credit reads the existing price ledger; it never edits price rows |

## Task 1: Lock the credit relationship contract, policy, and identifiers

### Intent

Fix every token, closed vocabulary, cap, identifier, and forbidden field before
any folding, speech, or analysis code depends on it. A smaller implementer must
not invent names or reintroduce a bank, a credit score, or a canonical debt.

### Implementation Steps

1. Create `src/agents/cognition/credit_relationships.py` with module docstring:
   "One owner's beliefs about credit terms and repayment. Nothing here creates a
   bank, money, enforceable debt, or an objective credit record."
2. Add constants:
   `CREDIT_RELATIONSHIPS_POLICY_VERSION = "credit-relationships.v1"`,
   `CREDIT_ROW_PREFIX = "cred-"`, `CREDIT_ANCHOR_PREFIX = "crd-"`,
   `CREDIT_HEX_LEN = 16`, `CREDIT_MAX_ROWS = 32`,
   `CREDIT_MAX_CLAIMS_PER_ROW = 16`, `CREDIT_MAX_REVISIONS_PER_ROW = 8`,
   `CREDIT_MAX_COUNTERPARTIES = 8`, `CREDIT_MAX_NOTICES = 8`,
   `CREDIT_MAX_PRINCIPAL_QUANTITY = 16`,
   `CREDIT_MAX_REPAYMENT_QUANTITY = 16`,
   `CREDIT_MAX_COLLATERAL_QUANTITY = 16`,
   `CREDIT_RATIO_MAX_MILLI = 64_000`,
   `CREDIT_CONFIDENCE_MAX_MILLI = 1_000`,
   `CREDIT_DUE_HORIZON_TICKS = 64`, `CREDIT_GRACE_TICKS = 8`,
   `CREDIT_STALE_AFTER_TICKS = 128`,
   `CREDIT_ACCEPT_MIN_WILLINGNESS_MILLI = 500`,
   `CREDIT_STRONG_MIN_CONFIDENCE_MILLI = 750`,
   `CREDIT_WEAK_MAX_CONFIDENCE_MILLI = 449`.
3. Add `CreditDirection(StrEnum)` with exactly `owner_debtor` and
   `owner_creditor`.
4. Add `CreditStatus(StrEnum)` with exactly `proposed`, `accepted`, `open`,
   `partially_repaid`, `repaid`, `defaulted`, `forgiven`, `disputed`,
   `withdrawn`, `declined`, `expired`.
5. Add `CreditAct(StrEnum)` with exactly `propose`, `accept`, `decline`, `repay`,
   `default`, `renegotiate`, `forgive`, `dispute`, `withdraw`.
6. Add `CreditCondition(StrEnum)` with exactly `on_receipt`, `by_deadline`,
   `after_return`, `shared_witness`, `unspecified`.
7. Add `CreditCollateralKind(StrEnum)` with exactly `none`, `item_pledge`,
   `service_pledge`, `custody_pledge`, `reputation_pledge`, `unspecified`.
8. Add `CreditExpectationLevel(StrEnum)` with exactly `none`, `weak`, `expected`,
   `strong`. Thresholds come from policy values.
9. Add `CreditClaimSource(StrEnum)` with exactly `self_authored` and
   `communicated`.
10. Add `CREDIT_NOTICE_CODES` frozenset with exactly
    `credit_ledger_truncated`, `credit_terms_unresolved`,
    `credit_claim_rejected`, `credit_terms_mismatch`,
    `credit_anchor_ambiguous`, `credit_frame_malformed`,
    `credit_counterparty_unresolved`, `credit_overdue`,
    `credit_repayment_ambiguous`, `credit_repayment_unmatched`.
11. Add `CREDIT_FORBIDDEN_FIELD_NAMES` frozenset with exactly `bank`, `banker`,
    `loan`, `interest`, `interest_rate`, `apr`, `credit_score`, `credit_limit`,
    `deposit`, `reserve`, `money`, `currency`, `legal_tender`, `collateral_lien`,
    `enforcement`, `collection`, `allocation`, `quota`, `planner`, `ranking`,
    `recommendation`, `default_probability`. Data fields use `credit`,
    `principal`, `repayment`, `willingness`, and `expectation`, never a field
    named `loan` or `interest`.
12. Add `CreditRelationshipError(ValueError)` with `reason_code`;
    `_fail(code)` logs `ERROR credit_relationship_invalid reason_code=<code>`
    and raises.
13. Add `credit_anchor(*, party_a: str, party_b: str, principal_kind: ItemKind,
    repayment_kind: ItemKind, opened_tick: int) -> str`: sort the two party
    values, SHA-256 over
    `party_a|party_b|principal_kind|repayment_kind|opened_tick`, return
    `crd-` plus 16 lowercase hex. Add `require_credit_anchor(value)`.
14. Add `credit_row_id(owner_id: AgentId, anchor: str) -> str`: SHA-256 over
    `owner_id.value|anchor`, return `cred-` plus 16 lowercase hex. Add
    `require_credit_row_id(value)`.
15. Add `CreditRelationshipPolicy` frozen dataclass with exact fields and
    `CREDIT_RELATIONSHIP_LOCKED_POLICY`:
    `max_rows=32`, `max_claims_per_row=16`, `max_revisions_per_row=8`,
    `max_counterparties=8`, `max_notices=8`, `due_horizon_ticks=64`,
    `grace_ticks=8`, `stale_after_ticks=128`,
    `accept_min_willingness_milli=500`,
    `strong_min_confidence_milli=750`, `weak_max_confidence_milli=449`,
    `max_principal_quantity=16`, `max_repayment_quantity=16`,
    `max_collateral_quantity=16`, `ratio_max_milli=64_000`,
    `confidence_base=200`, `confidence_per_own_claim=150`,
    `confidence_per_received_claim=100`, `confidence_per_promise=100`.
16. Add `default_credit_relationship_policy()` returning the single frozen
    policy instance.

### Required Interfaces and Contracts

```python
class CreditDirection(StrEnum): ...
class CreditStatus(StrEnum): ...
class CreditAct(StrEnum): ...
class CreditCondition(StrEnum): ...
class CreditCollateralKind(StrEnum): ...
class CreditExpectationLevel(StrEnum): ...
class CreditClaimSource(StrEnum): ...

@dataclass(frozen=True, slots=True)
class CreditRelationshipPolicy:
    max_rows: int = 32
    max_claims_per_row: int = 16
    max_revisions_per_row: int = 8
    max_counterparties: int = 8
    max_notices: int = 8
    due_horizon_ticks: int = 64
    grace_ticks: int = 8
    stale_after_ticks: int = 128
    accept_min_willingness_milli: int = 500
    strong_min_confidence_milli: int = 750
    weak_max_confidence_milli: int = 449
    max_principal_quantity: int = 16
    max_repayment_quantity: int = 16
    max_collateral_quantity: int = 16
    ratio_max_milli: int = 64_000
    confidence_base: int = 200
    confidence_per_own_claim: int = 150
    confidence_per_received_claim: int = 100
    confidence_per_promise: int = 100
```

- `__post_init__` rejects unknown fields via
  `CREDIT_FORBIDDEN_FIELD_NAMES`, validates exact integers against
  `CREDIT_RELATIONSHIP_LOCKED_POLICY`, and rejects `weak_max_confidence_milli >=
  strong_min_confidence_milli`.
- Item kinds are `world.values.ItemKind`; party values are strings.
- No global registry, table, singleton, module-level mutable state, or wall-clock
  value exists.

### Requirement Evidence

- V4-22 deepens the owned `markets_credit` context and adds no context/flag:
  `src/simulation/v4_architecture.py:212-228`,
  `src/simulation/compatibility.py` (`V4_OWNED_CAPABILITY_FLAGS`).
- Credit extends V3-17 promises/debts without replacing them:
  `src/world/structured_commitments.py:16-39`,
  `src/agents/cognition/structured_commitments.py:33-234`.
- No bank or enforced debt is allowed by the context non-goals:
  `src/simulation/v4_architecture.py:224-227`.

### Error Handling and Logging

- Invalid token, enum, cap, or id raises `CreditRelationshipError` with a safe
  code (`credit_invalid_policy`, `credit_invalid_identifier`,
  `credit_invalid_terms`, `credit_invalid_anchor`).
- `DEBUG credit_contract_locked policy=credit-relationships.v1 max_rows=32`
  logs counts only. Never log anchors, counterparties, item kinds, quantities,
  confidence values, or owner ids.

### Tests

- `tests/unit/test_credit_relationships_contract.py`: exact enum member sets;
  every cap boundary accepted/rejected; anchor symmetry for swapped parties;
  row-id owner separation; no forbidden field name; locked policy equality;
  frozen policy mutation fails.
- `tests/unit/test_credit_relationships_pins.py`: policy token, `cred-`/`crd-`
  prefixes, and no `runner-config-v57` reference in credit modules.

### Acceptance Criteria

- The module imports without `simulation`, `analysis`, `experiments`,
  `persistence`, `api`, or `observer`.
- Anchor is identical for the two parties of one agreement and differs by
  `opened_tick`, principal kind, or repayment kind.
- No field, constant, or docstring claims a bank, money, interest, credit score,
  enforceable debt, or a global credit registry.

### Verification

- `uv run pytest tests/unit/test_credit_relationships_contract.py tests/unit/test_credit_relationships_pins.py -q`
- `uv run mypy src/agents/cognition/credit_relationships.py`
- Expected: all pass.

## Task 2: Add the owner-scoped credit relationship ledger

### Intent

Provide the only place where an owner forms credit terms and repayment beliefs,
from its own authored claims, received `crd_v1` claims, the V3-17 commitment
ledger, the V4-21 price ledger, and directed trust signals. The ledger never
reads another owner's ledger, `WorldState`, inventories, or command admission.

### Implementation Steps

1. Add `CreditTerms(principal_kind: ItemKind, principal_quantity: int,
   repayment_kind: ItemKind, repayment_quantity: int, due_tick: int | None,
   condition: CreditCondition, collateral_kind: CreditCollateralKind,
   collateral_item_kind: ItemKind | None, collateral_quantity: int)`.
   `__post_init__` enforces quantities in `[1, 16]`, valid `due_tick` or `None`,
   and collateral consistency:
   - `none`/`unspecified`: `collateral_item_kind is None`,
     `collateral_quantity == 0`;
   - `item_pledge`/`custody_pledge`: item kind required, quantity in `[1, 16]`;
   - `service_pledge`/`reputation_pledge`: item kind `None`, quantity `0`.
   Add `repayment_ratio_milli()` returning
   `min(CREDIT_RATIO_MAX_MILLI, repayment_quantity * 1_000 // principal_quantity)`.
2. Add `CreditTermsRevision(tick: int, terms: CreditTerms, reason: str)` where
   `reason` is one of `renegotiated`, `corrected`.
3. Add `CreditClaim(act: CreditAct, direction: CreditDirection, anchor: str,
   terms: CreditTerms, paid_quantity: int, opened_tick: int,
   confidence_milli: int, counterparty_id: EntityId,
   source: CreditClaimSource, source_tick: int)`.
   Validate `paid_quantity` in `[0, 16]`, confidence in `[0, 1000]`, and
   `paid_quantity == 0` unless `act is CreditAct.REPAY`.
4. Add `CreditCounterpartySignal(counterparty_id: EntityId,
   trust_milli: int, confidence_milli: int)` with both values in `[0, 1000]`.
5. Add `CreditRepaymentObservation(counterparty_id: EntityId,
   item_kind: ItemKind, quantity: int, tick: int)` with quantity in `[1, 16]`
   and non-negative tick. It is owner-observed physical evidence, not a claim.
6. Add `CreditRelationshipRow(anchor: str, counterparty_id: EntityId,
   direction: CreditDirection, terms: CreditTerms, status: CreditStatus,
   paid_quantity: int, expectation_milli: int, trust_milli: int,
   trust_confidence_milli: int, price_confidence_milli: int,
   confidence_milli: int, level: CreditExpectationLevel,
   proposed_by_owner: bool, last_repayment_tick: int | None,
   own_claim_count: int, received_claim_count: int, promise_count: int,
   revisions: tuple[CreditTermsRevision, ...], claims: tuple[CreditClaim, ...],
   first_tick: int, last_tick: int, row_id: str)`. Validate sorted unique claim
   keys `(anchor, act, source, source_tick, counterparty_id)`; `paid_quantity <=
   terms.repayment_quantity`; `len(claims) <= max_claims_per_row`;
   `len(revisions) <= max_revisions_per_row`; `row_id ==
   credit_row_id(owner, anchor)`; `first_tick <= last_tick`;
   `last_repayment_tick` is `None` or within `[first_tick, last_tick]`.
6. Add `CreditRelationshipLedger(owner_id: AgentId,
   rows: tuple[CreditRelationshipRow, ...], notices: tuple[str, ...],
   policy_version: str)` plus `empty_credit_relationships(owner_id)`,
   `require_owner_credit_relationships(value, owner_id, *, field_name)`,
   `validate_credit_relationship_caps(ledger, policy=None)`.
7. Add `apply_credit_relationship_update(*, owner_id: AgentId, tick: int,
   claims: tuple[CreditClaim, ...] = (),
   repayments: tuple[CreditRepaymentObservation, ...] = (),
   prior: CreditRelationshipLedger | None = None,
   commitments: StructuredCommitmentLedger | None = None,
   prices: EmergentPriceLedger | None = None,
   signals: tuple[CreditCounterpartySignal, ...] = (),
   policy: CreditRelationshipPolicy | None = None) -> CreditRelationshipLedger`.
8. Fold claims in this exact order:
   - Normalize received claims: invert `direction` because the frame is
     speaker-relative, set `counterparty_id` to the speaker, and keep
     `source_tick` and `source`. Self-authored claims already carry the listener
     as counterparty and the authored direction.
   - Derive row key `(counterparty_id, anchor)`.
   - For `propose` only, recompute
     `credit_anchor(party_a=owner_value, party_b=counterparty.value,
     principal_kind=terms.principal_kind,
     repayment_kind=terms.repayment_kind, opened_tick=claim.opened_tick)` and
     reject a mismatch with `credit_anchor_ambiguous`; later acts keep the
     original anchor across renegotiation.
   - For a later act with no existing row, create a `proposed` row from the
     frame terms and apply the act as evidence; no terms are invented.
   - Deduplicate identical `(anchor, act, source, source_tick, counterparty_id)`
     claims; a repeat is a no-op.
   - Unknown act/direction combinations are rejected with
     `credit_claim_rejected`; they never raise out of the update.
9. Apply acts deterministically:
   - `propose`: create `proposed`; set `proposed_by_owner=True` when the claim
     source is `self_authored`, else `False`; if the row already exists, keep
     earlier terms and add a revision only when terms changed.
   - `accept`: `proposed` -> `accepted`; otherwise ignore with
     `credit_claim_rejected`.
   - `decline`: `proposed` -> `declined`; otherwise ignore.
   - `withdraw`: `proposed` -> `withdrawn`; otherwise ignore.
   - `repay`: add `paid_quantity` to the row's paid total, capped at
     `terms.repayment_quantity`; status becomes `repaid` when the total reaches
     the repayment quantity, else `partially_repaid`. A repayment claim on a
     `forgiven`, `disputed`, `withdrawn`, or `declined` row is rejected.
   - `default`: accepted only when `terms.due_tick is not None and tick >=
     terms.due_tick`, or when the speaker is the debtor self-declaring; status
     becomes `defaulted`.
   - `forgive`: status becomes `forgiven` from any non-withdrawn status.
   - `dispute`: status becomes `disputed` from any non-withdrawn status.
   - `renegotiate`: replace terms, append `CreditTermsRevision` with reason
     `renegotiated`, reset `paid_quantity` to `0` only when the repayment kind or
     repayment quantity changed, and keep status `proposed` or `open` as
     appropriate.
   - `accept` on a row whose terms mismatch the claim terms is rejected with
     `credit_terms_mismatch`; all other non-proposal acts require exact term
     equality.
   - After acts, fold `repayments` into owner-debtor rows whose status is
     `accepted`, `open`, or `partially_repaid`, whose counterparty matches, and
     whose `terms.repayment_kind` matches the observation's `item_kind`; add
     `quantity` to `paid_quantity`, set `last_repayment_tick=tick`, and set the
     status as a repay claim would. If more than one open row matches, add
     `credit_repayment_ambiguous` and change none. If none matches, add
     `credit_repayment_unmatched`.
10. Fold V3-17 commitment evidence:
    - For each `CommitmentInterpretation` with `kind in {"debt",
      "future_exchange"}` and status in `{"proposed", "accepted", "open",
      "partial", "fulfilled", "violated", "disputed"}`:
      - derive terms when `now_item_kind` and `item_kind` are present:
        `principal_kind=now_item_kind`, `repayment_kind=item_kind`,
        `principal_quantity=quantity`, `repayment_quantity=quantity`,
        `due_tick=commitment.due_tick`, `condition=by_deadline` when a due tick
        exists else `on_receipt`, and `collateral_kind=none`;
      - set direction `owner_debtor` when `owed_by == "self"`, else
        `owner_creditor`;
      - derive the anchor from the owner, the other party, the two kinds, and
        `commitment.created_tick`;
      - when no row exists, create it with status `proposed` for a `proposed`
        commitment and `open` otherwise; set `proposed_by_owner=True` when the
        owner was the speaker, i.e. `(direction is owner_debtor and owed_by ==
        "self")` or `(direction is owner_creditor and owed_by ==
        "counterparty")`, else `False`;
      - increment `promise_count` on the matching row.
    - A commitment never supplies a principal quantity different from its
      declared `quantity`, never invents a collateral claim, and never creates a
      repayment ratio.
11. Fold price confidence: for each row, find an `EmergentPriceLedger` row whose
    `(item_kind, unit_kind)` equals `(principal_kind, repayment_kind)` or
    `(repayment_kind, principal_kind)`; use the maximum `confidence_milli`, else
    `500`.
12. Fold trust: map the signal for the row's counterparty to `trust_milli`;
    missing signal is `500` with confidence `200`.
13. Compute willingness exactly:
    `willingness = (trust_milli * 500 + history_milli * 300 +
    price_confidence_milli * 200) // 1000`, where `history_milli` is `500` when
    the owner has no prior repaid/defaulted row with that counterparty, else
    `repaid_count * 1000 // (repaid_count + defaulted_count)`.
14. Compute confidence exactly:
    `min(1000, confidence_base
    + confidence_per_own_claim * min(4, own_claim_count)
    + confidence_per_received_claim * min(3, received_claim_count)
    + confidence_per_promise * min(3, promise_count))`.
15. Compute level: `none` when no row; `weak` when confidence is below `450`;
    `expected` when below `750`; `strong` when at least `750` and the owner has
    at least one `repaid` row with that counterparty. `strong` never exceeds
    `expected` when the row is only supported by received claims.
16. Expire overdue rows: when status is `accepted`, `open`, or
    `partially_repaid`, `due_tick` is present, `tick > due_tick + grace_ticks`,
    and paid quantity is below repayment quantity, set status `expired` and add
    `credit_overdue`. A later `repay`/`default` claim may move it again.
17. Build rows in sorted order by `(counterparty_id.value, anchor)`, cap at
    `max_rows` after selecting the most recent `last_tick` rows, add
    `credit_ledger_truncated` when capped, and return the ledger.

### Required Interfaces and Contracts

```python
def apply_credit_relationship_update(
    *,
    owner_id: AgentId,
    tick: int,
    claims: tuple[CreditClaim, ...] = (),
    repayments: tuple[CreditRepaymentObservation, ...] = (),
    prior: CreditRelationshipLedger | None = None,
    commitments: StructuredCommitmentLedger | None = None,
    prices: EmergentPriceLedger | None = None,
    signals: tuple[CreditCounterpartySignal, ...] = (),
    policy: CreditRelationshipPolicy | None = None,
) -> CreditRelationshipLedger: ...
```

- The updater accepts only owner-scoped DTOs. It never receives `WorldState`,
  another owner's ledger, item ids, inventories, or an `AgentCommand`.
- Repeated folding of the same claim set leaves row bytes, counts, confidence,
  and notices unchanged.
- Rows are owner-local; the same `crd-` anchor may appear in two owners' ledgers
  with independent status, terms, and confidence.

### Requirement Evidence

- Promise/debt evidence is V3-17, not a new debt primitive:
  `src/agents/cognition/structured_commitments.py:89-234`.
- Subjective trust is a directed relationship dimension, not an engine score:
  `src/social/relationships.py:56-67`, `agents/cognition/communication.py:88-109`.
- Price expectations are optional V4-21 inputs:
  `src/agents/cognition/emergent_prices.py:657-695`.
- No command is returned by any credit helper:
  `.ai-factory/ARCHITECTURE.md` "Anti-Patterns".

### Error Handling and Logging

- Malformed or inconsistent claims are dropped with
  `credit_claim_rejected`/`credit_terms_mismatch`; simulation continues.
- `WARN credit_ledger_truncated family=rows cap=32` logs counts only.
- `DEBUG credit_ledger_updated rows=%s claims=%s truncated=%s` never logs
  anchors, counterparties, item kinds, quantities, trust, or confidence.

### Tests

- `tests/unit/test_credit_relationships_ledger.py`: all act transitions;
  renegotiation revisions; partial/full repayment; self-default rule; forgery
  rejection; duplicate-fold no-op; exact term mismatch; cap truncation; notice
  bounds; missing trust/price defaults; willingness formula boundaries;
  commitment-seeded candidate rows; `proposed_by_owner` speaker rule;
  repayment-observation ambiguity.
- `tests/unit/test_credit_relationships_helpers.py`: shared builders for owner,
  peer, terms, claim, signal, and commitment evidence.

### Acceptance Criteria

- One owner can hold two independent rows with the same counterparty when
  anchors differ.
- A received proposal is stored with inverted direction; an own proposal keeps
  authored direction.
- Repayment cannot exceed the term quantity; forgiveness and dispute never move
  items or change objective state.
- No row carries a field named `bank`, `loan`, `interest`, `credit_score`, or
  `money`.

### Verification

- `uv run pytest tests/unit/test_credit_relationships_ledger.py -q`
- `uv run mypy src/agents/cognition/credit_relationships.py`
- Expected: all pass.

## Task 3: Activate and carry credit relationships under markets_credit

### Intent

Wire the ledger into deterministic cognition only when the owned
`markets_credit` flag and the V3-17 `structured_commitments` spec are both
present. Every other combination must leave V3-17, V4-20, and V4-21 behavior
byte-identical.

### Implementation Steps

1. In `src/agents/cognition/configuration.py`, add
   `CognitionCreditMode` with `DISABLED` and `DETERMINISTIC`, documented as
   "active only when `markets_credit` and `structured_commitments` are both
   present; a cognition mode, not a capability flag or runner schema".
2. Add `credit_relationship_mode: CognitionCreditMode` and
   `credit_relationship_policy: CreditRelationshipPolicy | None` to
   `CognitionLoopConfig`. Validate: disabled clears policy; enabled with `None`
   installs `default_credit_relationship_policy()`; wrong type raises
   `TypeError`. Add mode/policy to `material` and `resolved` copies exactly like
   price mode.
3. In `src/simulation/runner.py`, add
   `structured_commitments_active: bool = False` to `_cognition_config_for`.
   Compute `credit_enabled = markets_enabled and structured_commitments_active`.
   Build `credit_mode`/`credit_policy` beside price mode and pass
   `credit_relationship_mode`/`credit_relationship_policy` into
   `CognitionLoopConfig`.
4. Update both `_cognition_config_for` call sites (lines 2908-2937 and
   7150-7171) to pass
   `structured_commitments_active=(config.structured_commitments is not None)`.
   Log `INFO credit_relationship_mode mode=%s` only on activation.
5. In `src/agents/cognition/loop.py`, add slots/attrs
   `_credit_relationship_mode`, `_credit_relationship_policy`,
   `_prepared_credit_relationships`; validate mode/policy in `__init__` exactly
   like price mode; clear the prepared ledger when disabled.
6. Add `_prepare_credit_relationships(loop_input, commitments, prices)`:
   - read the carried ledger from `snapshot.credit_relationships`;
   - read `snapshot.relationships` and project trust per counterparty:
     signed trust `[-1, 1]` -> `int(round((0.5 + 0.5 * trust) * 1000))`,
     confidence -> `int(round(confidence * 1000))`; missing profile ->
     `500`/`200`;
   - parse incoming `crd_v1` claims from `observation.communications`;
   - collect owner-observed `give` occurrences where the owner is the actor and
     the recipient is a credit counterparty, resolve the item kind from
     `public_facts`, and build `CreditRepaymentObservation` values;
   - call `apply_credit_relationship_update` with claims, repayments,
     commitments, prices, and signals;
   - store the result in `self._prepared_credit_relationships` and return it.
   Call it after `_prepare_emergent_prices` and before deliberation.
7. Add `_received_credit_claims(observation, owner_value)`: iterate
   `observation.communications`; for each `Talked`/`Told`-backed communication,
   inspect `utterance.content.relations`; parse `crd_v1` relations; drop
   malformed/oversize frames with one `WARN credit_frame_dropped` and continue;
   set `source=COMMUNICATED` for received claims and `SELF_AUTHORED` when the
   owner is the speaker; invert direction only in the ledger fold.
8. Add `credit_relationships` to `SubjectiveSnapshot` (models.py),
   `Perspective` (contracts.py), the loop result/proposal dataclasses, and
   `CognitiveLoopForkState.prepared_credit_relationships`; validate owner
   identity through `require_owner_credit_relationships`.
9. In `src/simulation/perception.py`, add
   `credit_relationships: object | None = None` to `build_perspective` and pass
   it through.
10. In `src/simulation/run_control.py`, add
    `credit_relationships` to `AgentRuntimeCheckpoint`; validate owner identity.
11. In `src/simulation/agent_runtime.py`, add `_credit_relationships`, a
    `_commit_credit_relationships` method mirroring `_commit_emergent_prices`,
    pass the ledger into perspective, commit after the loop result, restore from
    checkpoints, and include it in the runtime checkpoint.
12. In `src/simulation/runner_models.py`, add
    `credit_relationship_ledgers: tuple[object, ...] = ()` to
    `SimulationRunnerResult`; validate type, owner order, owner identity, and
    caps exactly like `emergent_price_ledgers`.
13. In `src/simulation/runner.py`, add
    `export_credit_relationship_ledgers()` mirroring
    `export_emergent_price_ledgers`, pass it into the result construction at
    line 5356, and validate checkpoint ledgers at 5048-5075.
14. Export the public ledger DTOs from `agents.cognition.__init__` and
    `simulation.__init__` only where existing façades already export the price
    equivalents.

### Required Interfaces and Contracts

```python
class CognitionCreditMode(StrEnum):
    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"

# CognitionLoopConfig
credit_relationship_mode: CognitionCreditMode = CognitionCreditMode.DISABLED
credit_relationship_policy: CreditRelationshipPolicy | None = None
```

- Activation truth table:
  `markets_credit` off -> credit disabled regardless of commitments;
  `markets_credit` on + commitments absent -> credit disabled;
  `markets_credit` on + commitments present -> deterministic credit mode.
- Credit mode never enables `markets_credit`, `structured_commitments`, or
  `subjective_valuation`; it only consumes them.
- No runner schema, root key, per-agent runner key, or write pair changes.

### Requirement Evidence

- V4-21 price activation is the exact two-input precedent:
  `src/simulation/runner.py:1479-1485`.
- V3-17 commitments activate on their own spec and remain independent:
  `src/simulation/runner.py:875-917`,
  `src/simulation/runner_models.py:9260-9284`.
- `markets_credit` is owned and uses existing events:
  `src/simulation/v4_architecture.py:212-228`.

### Error Handling and Logging

- Disabled mode allocates `None`, logs `DEBUG credit_relationship_disabled`,
  and leaves V4-20/V4-21 bytes unchanged.
- Foreign/mistyped ledgers raise `TypeError` at the boundary, never inside the
  tick loop.
- `INFO credit_relationship_mode mode=deterministic` on activation;
  `DEBUG credit_relationships_carried rows=%s claims=%s notices=%s` counts only.

### Tests

- `tests/unit/test_credit_relationships_activation.py`: all four activation
  combinations; disabled clears ledger; runner config mode; no v57; no root key.
- `tests/unit/test_credit_relationships_carry.py`: perspective ownership,
  snapshot/proposal/result carry, checkpoint restore, foreign-ledger rejection.
- `tests/unit/test_structured_commitments_metrics.py` and existing
  `test_subjective_value_metrics.py` stay green unchanged.

### Acceptance Criteria

- With either prerequisite off, no credit ledger is allocated and no `crd_v1`
  relation is attached.
- With both on, every runtime carries exactly one owner ledger and the runner
  result exports owner-ordered ledgers.
- No command, event, observer semantic, runner schema, or migration is added.

### Verification

- `uv run pytest tests/unit/test_credit_relationships_activation.py tests/unit/test_credit_relationships_carry.py -q`
- `uv run pytest tests/unit/test_subjective_value_metrics.py tests/unit/test_structured_commitments_metrics.py -q`
- Expected: all pass.

## Task 4: Add crd_v1 speech frames with bounded trust-sensitive attachment

### Intent

Let an owner state credit terms and acts inside existing `Talk`/`Tell` speech,
and let received claims become evidence. The frame is testimony, never a
contract, bank record, or authority to give or collect. The only behavioural
effect is one optional relation on an already-selected utterance.

### Implementation Steps

1. Create `src/world/credit_relationships.py` as the neutral frame codec so
   analysis may parse committed `crd_v1` speech without importing cognition.
   Add `CREDIT_FRAME_SUBJECT = "crd_v1"`,
   `CREDIT_FRAME_MAX_CHARS = 320`, `CREDIT_FRAME_MAX_RELATIONS = 32`.
2. Add `CREDIT_ACT_PREDICATES` exactly:
   `propose -> crd_propose`, `accept -> crd_accept`,
   `decline -> crd_decline`, `repay -> crd_repay`,
   `default -> crd_default`, `renegotiate -> crd_renegotiate`,
   `forgive -> crd_forgive`, `dispute -> crd_dispute`,
   `withdraw -> crd_withdraw`.
3. Add frame DTO `CreditClaimFrame(act, direction, anchor,
   principal_kind_token, principal_quantity, repayment_kind_token,
   repayment_quantity, paid_quantity, opened_tick, due_tick,
   condition, collateral_kind, collateral_item_token, collateral_quantity,
   confidence_milli)`.
4. Encode as exactly 16 colon-separated parts:
   `crd_v1:<predicate>:<direction>:<anchor>:<principal>:<principal_qty>:<repayment>:<repayment_qty>:<paid_qty>:<opened_tick>:<due_tick|none>:<condition>:<collateral_kind>:<collateral_item|none>:<collateral_qty>:<confidence>`.
5. Parse strict: reject wrong part count, wrong subject, unknown predicate,
   whitespace/control characters, invalid item token regex
   `^[a-z][a-z0-9_-]*$`, invalid anchor regex
   `^crd-[0-9a-f]{16}$`, quantities outside `[0, 16]`, confidence outside
   `[0, 1000]`, oversize text, or inconsistent collateral.
6. Add `credit_claim_relation(frame)` returning one
   `CommunicationRelation(subject="crd_v1", predicate=..., object=<frame body>)`
   and `parse_credit_claim_relation(relation)` returning `None` for unrelated
   predicates. `world.credit_relationships` imports only `world.communications`
   and the standard library; it does not import cognition, simulation, analysis,
   experiments, persistence, API, or observer.
7. Create `src/agents/cognition/credit_relationships_communication.py` with
   `CREDIT_COMMUNICATION_POLICY_VERSION =
   "credit-relationships-communication.v1"` and
   `credit_communicate_utterance(command, *, owner_id, ledger, tick,
   policy=None)`:
   - return unchanged unless `type(command) in {Talk, Tell}` and the ledger is
     owner-local;
   - do not attach when a `crd_v1` relation already exists or the relation cap
     is reached;
   - select exactly one row and act by this priority:
     1. `proposed` rows with `proposed_by_owner=False`: choose the row with
        highest `expectation_milli`, then oldest `first_tick`, then `anchor`;
        emit `accept` when `expectation_milli >=
        policy.accept_min_willingness_milli`, else `decline`. Rows the owner
        proposed are never auto-accepted by the owner.
     2. Owner-debtor rows with `last_repayment_tick == tick` and status
        `partially_repaid` or `repaid`: emit `repay` with the row's
        `paid_quantity` (capped at 16).
     3. Owner-debtor `open`/`partially_repaid` rows whose `due_tick` is present
        and `tick >= due_tick`: emit `default` when `expectation_milli < 250`,
        else `renegotiate` with the same terms and `due_tick = tick + 8`.
     4. Owner-creditor `open`/`partially_repaid` rows whose `due_tick` is
        present and `tick >= due_tick + policy.grace_ticks`: emit `dispute`.
     5. Owner-creditor `defaulted`/`expired` rows with `trust_milli >= 750`:
        emit `forgive`.
     6. Owner-proposed `proposed` rows with `tick - first_tick >= 8`: emit
        `withdraw` with the same terms.
     7. Otherwise emit nothing.
   - The selector never emits `propose`; `propose` exists for explicit authored
     claims and tests. The normal proposal path is a V3-17
     `debt`/`future_exchange` commitment, which seeds a `proposed` candidate
     row in Task 2, and the receiver accepts or declines it through step 1.
   - encode one relation through the world codec and replace the utterance
     content; never change the command class, recipient, or any other field.
8. In `src/agents/cognition/deliberation.py`, attach credit after price
   attachment at 1405-1417, passing
   `tick=loop_input.observation.tick`, the snapshot ledger, and policy from
   `CognitionLoopConfig`.
9. Do not add a credit relation to `Ask`, `Give`, `Exchange`, `Wait`, or any
   non-speech command. Do not create or replace a command.
10. Add public exports for the frame codec from `world.__init__` if the existing
    façade exports `world.communications` symbols, and for the attachment
    function from `agents.cognition.__init__`.

### Required Interfaces and Contracts

```python
CREDIT_FRAME_SUBJECT = "crd_v1"
CREDIT_FRAME_MAX_CHARS = 320
CREDIT_FRAME_MAX_RELATIONS = 32

def credit_communicate_utterance(
    command: object,
    *,
    owner_id: AgentId,
    ledger: object | None,
    tick: int,
    policy: CreditRelationshipPolicy | None = None,
) -> object: ...
```

- `CREDIT_FRAME_SUBJECT`, `CREDIT_FRAME_MAX_CHARS`, `CREDIT_FRAME_MAX_RELATIONS`,
  `CreditClaimFrame`, `credit_claim_relation`, and
  `parse_credit_claim_relation` live in `world.credit_relationships` so analysis
  can parse committed speech without importing cognition.
- `credit_communicate_utterance` lives in
  `agents.cognition.credit_relationships_communication` and is the only
  selection/attachment path.
- Received frames are testimony. A received `accept`, `repay`, `default`,
  `forgive`, or `dispute` claim changes only the receiver's owner-local belief.
- A frame from an unrelated predicate or subject is ignored without error.
- Malformed or oversize frames are dropped with one bounded warning count;
  simulation continues.
- Credit attachment never reads `WorldState`, another owner's ledger, or
  command admission.

### Requirement Evidence

- `prc_v1` is the exact bounded speech-frame precedent:
  `src/agents/cognition/emergent_prices_communication.py:52-351`.
- `mkt_v1`, `org_v1`, and `fr_v1` establish one-relation speech attachment:
  `src/agents/cognition/market_institutions_communication.py:36-283`.
- Existing `Talk`/`Tell` prove delivery only, not agreement:
  `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts".

### Error Handling and Logging

- Parser failures log `WARN credit_frame_invalid reason_code=<safe>` and raise
  `ValueError` to the caller; the loop catches and counts them.
- Attachment logs `DEBUG credit_frame_attached act=%s` only.
- Never log anchors, counterparties, item kinds, quantities, trust, or
  confidence values.

### Tests

- `tests/unit/test_credit_relationships_communication.py`: exact 16-part
  round-trip; every act predicate; malformed/short/oversize/unknown predicate;
  unrelated relation returns `None`; one-relation cap; non-speech command
  unchanged; accept vs decline threshold; debtor renegotiation and creditor
  dispute timing; default below willingness 250; creditor forgiveness at trust
  750; proposer withdrawal after 8 ticks; repayment declaration; no command
  class change.
- `tests/unit/test_credit_relationships_deliberation.py`: attachment only after
  a selected `Talk`/`Tell`; disabled mode attaches nothing; no `Give`/`Wait`
  mutation.

### Acceptance Criteria

- A `crd_v1` frame round-trips through encode/parse without data loss.
- Only `Talk`/`Tell` can carry a credit relation, and at most one per utterance.
- The selected command class, recipient, and non-relation fields are unchanged.
- Malformed frames never abort a tick and never create a row.

### Verification

- `uv run pytest tests/unit/test_credit_relationships_communication.py tests/unit/test_credit_relationships_deliberation.py -q`
- `uv run mypy src/agents/cognition/credit_relationships_communication.py`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: credit terms duplicate V3-17 commitments and create two sources of
  truth.
  Mitigation: commitments remain the objective promise speech; they seed
  owner-local credit candidates, and `crd_v1` acts refine the owner's belief.
- Risk: trust-sensitive willingness becomes a hidden credit score.
  Mitigation: willingness is owner-local, bounded, never exported as a score,
  and used only to choose accept/decline speech.
- Risk: received claims are treated as agreement.
  Mitigation: every claim is testimony; status is owner-local and never moves
  items or grants permission.
- Risk: disabled combinations change legacy bytes.
  Mitigation: disabled mode allocates `None`, attaches nothing, and leaves all
  V3-17/V4-20/V4-21 paths untouched.

## Phase Completion Checklist

- Every Task 1-4 in this phase satisfies its acceptance criteria.
- Focused unit tests and mypy pass.
- `index.md` checkboxes are updated only after verified completion.
