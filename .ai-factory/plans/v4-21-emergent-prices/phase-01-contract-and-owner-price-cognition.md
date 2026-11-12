# Phase 1: Contract and Owner-Scoped Price Cognition

Plan: [index.md](index.md)
Tasks: 1-4
Depends on: none

## Objective

Introduce the locked `emergent-prices.v1` owner-scoped contract: bounded price
expectation beliefs, `prc_v1` speech frames, activation derived from
`markets_credit` plus the existing V3-18 valuation channel, and full carry
through perspective, checkpoints, and the runner result. No command, event,
observer semantic type, V4 flag, runner schema, or migration is added.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/agents/cognition/subjective_value.py` | `VALUATION_COMPONENTS` 23-33, `ValuationRow` 51-92, `SubjectiveValuationLedger` 95-128, `empty_subjective_valuations` 142-146 | Owner-local `item_kind`/`reference_kind`/`reservation` is the valuation input and reference-unit source |
| `src/agents/cognition/acceptance_memory.py` | `AcceptanceMemoryRow` 24-64, `note_exchange_completed` 127-226 | V3-19 observed medium evidence; supplies `observed_medium` unit candidates |
| `src/agents/cognition/market_institutions.py` | policy 306-360, ledger 652-749, fold 756-1262, `apply_market_institution_update` 1265-1453 | Exact owner-ledger pattern to mirror |
| `src/agents/cognition/market_institutions_communication.py` | `MARKET_FRAME_SUBJECT` 36, `MarketClaim` 86-154, encode 157-180, parse 183-253, relation 256-283 | Exact bounded-frame pattern to mirror as `prc_v1` |
| `src/agents/cognition/configuration.py` | `CognitionMarketMode` 470-478, fields 758-759, validation 1349-1370, material 1815-1819, resolved 2132-2133 | Mode/policy wiring pattern |
| `src/simulation/runner.py` | `markets_enabled` 1036, mode/policy 1454-1470, config 1720-1730, ledger validation 5026-5037, export 5850-5863 | Activation and export point |
| `src/simulation/runner_models.py` | `RUNNER_SCHEMA_VERSION_V56` 152, `V4CapabilityFlags` 1128-1179, `markets_credit` 1149, result ledger validation 6871-6899 | No v57; result field validation pattern |
| `src/simulation/agent_runtime.py` | `_commit_market_institutions` 1355-1388, perspective 2565-2578, restore 3669-3680, checkpoint export 3846-3901 | Carry/checkpoint pattern |
| `src/agents/cognition/deliberation.py` | attendance 1218-1235, utterance attachment 1393-1405 | Speech attachment hook |
| `src/simulation/runner_models.py` | `SubjectiveValuationSpec` 5213-5265, `RESOURCE_EXCHANGE_PROFILE_POLICY_ID` 5273-5293 | Existing V3-18/V3-19 activation seams |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/agents/cognition/emergent_prices.py` | create | Policy, enums, ids, rows, ledger, validation, fold/update |
| `src/agents/cognition/emergent_prices_communication.py` | create | `prc_v1` encode/parse/attach/select |
| `src/agents/cognition/configuration.py` | modify | `CognitionPriceMode`, mode/policy fields, validation, material, resolved copy |
| `src/agents/cognition/loop.py` | modify | Mode/policy attrs, `_prepare_emergent_prices`, result/proposal propagation, fork state |
| `src/agents/cognition/models.py` | modify | Snapshot/proposal/result fields |
| `src/agents/cognition/contracts.py` | modify | Perspective field and owner validation |
| `src/agents/cognition/fork_state.py` | modify | Prepared price ledger field/type |
| `src/agents/cognition/deliberation.py` | modify | Attach one `prc_v1` relation after command selection |
| `src/agents/cognition/__init__.py` | modify | Public exports |
| `src/simulation/perception.py` | modify | `build_perspective(..., emergent_prices=None)` |
| `src/simulation/run_control.py` | modify | `AgentRuntimeCheckpoint.emergent_prices` |
| `src/simulation/agent_runtime.py` | modify | Commit/clear, perspective pass, restore, runtime view |
| `src/simulation/runner.py` | modify | Derive mode, validate result ledgers, export |
| `src/simulation/runner_models.py` | modify | `SimulationRunnerResult.emergent_price_ledgers` validation |
| `src/simulation/emergent_prices_export.py` | create | Token-only neutral owner export rows |

## Task 1: Lock `emergent-prices.v1` contract, policy, and identifiers

### Intent

Fix every token, closed vocabulary, cap, and identifier before any folding or
analysis code depends on it. A smaller implementer must not invent names.

### Implementation Steps

1. Create `src/agents/cognition/emergent_prices.py` with module docstring:
   "Owner-scoped price expectations. These numbers are not a world price and no
   owner reads another owner's ledger."
2. Add constants: `EMERGENT_PRICES_POLICY_VERSION = "emergent-prices.v1"`,
   `PRICE_BELIEF_PREFIX = "prcb-"`, `PRICE_BELIEF_HEX_LEN = 16`,
   `PRICE_MAX_UNITS = 8`, `PRICE_MAX_ROWS = 32`, `PRICE_MAX_NOTICES = 8`,
   `PRICE_RATIO_MAX_MILLI = 64_000`, `PRICE_CONFIDENCE_MAX_MILLI = 1_000`.
3. Add `PriceUnitSource(StrEnum)` with exactly `owner_reference`,
   `observed_medium`, `exchange_counterpart`, `quoted`, `unknown`.
4. Add `PriceQuoteDirection(StrEnum)` with exactly `give_for_unit` and
   `unit_for_give`.
5. Add `PriceQuoteSource(StrEnum)` with exactly `observed_offer`,
   `communicated`, and `self_authored`.
6. Add `PriceExpectationLevel(StrEnum)` with exactly `none`, `weak`,
   `expected`, `strong`. Level thresholds are policy values, not magic numbers.
7. Add `EMERGENT_PRICE_NOTICE_CODES` frozenset with exactly
   `price_ledger_truncated`, `price_unit_unresolved`, `price_valuation_stale`,
   `price_quote_malformed`, `price_evidence_unpaired`.
8. Add `PRICE_FORBIDDEN_FIELD_NAMES` frozenset: `price`, `canonical_price`,
   `price_index`, `clearing_price`, `rate`, `money`, `currency`, `numeraire`,
   `bid`, `ask`, `spread`, `fee`, `commission`, `tax`, `debt`, `credit_limit`,
   `market_score`, `ranking`, `severity`, `recommendation`, `allocation`,
   `quota`, `central_planner`, `unit_of_account`, `medium_of_exchange`,
   `store_of_value`. Data fields use `ratio_milli` and `expectation`, never a
   field literally named `price`.
9. Add `EmergentPriceError(ValueError)` with `reason_code`, `_fail(code)` logging
   `ERROR emergent_price_invalid reason_code=<code>`.
10. Add id helpers `price_belief_id(owner_id, item_kind, unit_token)` using
    SHA-256 over `owner_id.value|item_kind.value|unit_token` and
    `require_price_belief_id(value)`; owner-local ids are `prcb-` plus 16 hex.
11. Add `EmergentPricePolicy` frozen dataclass with validated ranges and
    `EMERGENT_PRICE_LOCKED_POLICY`: `max_rows=32`, `max_observations_per_row=32`,
    `max_quotes_per_row=8`, `max_counterparties=8`, `max_units=8`,
    `max_notices=8`, `stale_after_ticks=64`, `expected_min_observations=2`,
    `strong_min_confidence_milli=750`, `quote_min_confidence_milli=250`,
    `medium_min_received=2`, `ratio_max_milli=64_000`,
    `confidence_base_per_evidence=150`, `confidence_base_cap=600`.
12. Add `default_emergent_price_policy()` returning the locked policy.

### Required Interfaces and Contracts

```python
class PriceUnitSource(StrEnum): ...
class PriceQuoteDirection(StrEnum): ...
class PriceQuoteSource(StrEnum): ...
class PriceExpectationLevel(StrEnum): ...

@dataclass(frozen=True, slots=True)
class EmergentPricePolicy:
    max_rows: int = 32
    max_observations_per_row: int = 32
    max_quotes_per_row: int = 8
    max_counterparties: int = 8
    max_units: int = 8
    max_notices: int = 8
    stale_after_ticks: int = 64
    expected_min_observations: int = 2
    strong_min_confidence_milli: int = 750
    quote_min_confidence_milli: int = 250
    medium_min_received: int = 2
    ratio_max_milli: int = 64_000
```

- Policy fields are validated by type and inclusive range in `__post_init__`.
- `item_kind` values are `world.values.ItemKind`; `unit_kind` is
  `world.values.ItemKind | None`; `unit_token` is `unit_kind.value` or `none`.
- No global registry, table, singleton, or module-level mutable state exists.

### Requirement Evidence

- V4-21 deepens the owned `markets_credit` context and adds no flag/context:
  `src/simulation/v4_architecture.py:212-228`, `runner_models.py:1128-1179`.
- Valuation representation is owner-local and bounded:
  `src/agents/cognition/subjective_value.py:23-128`.
- Forbidden authoritative fields follow the existing pattern:
  `src/analysis/market_institutions_contract.py:120-147`.

### Error Handling and Logging

- Invalid token, enum, cap, or id raises `EmergentPriceError` with a safe code
  (`price_invalid_policy`, `price_invalid_identifier`, `price_invalid_unit`).
- `DEBUG price_contract_locked policy=emergent-prices.v1 max_rows=32` may log
  counts only. Never log item kinds, unit tokens, valuations, or `prcb-` ids.

### Tests

- `tests/unit/test_emergent_prices_contract.py`: every enum exact member set;
  every cap boundary accepted/rejected; id determinism across processes; no
  field name in `PRICE_FORBIDDEN_FIELD_NAMES`; locked policy equality.
- `tests/unit/test_emergent_prices_pins.py`: policy token and `prcb-` prefix
  pinned; no `runner-config-v57` reference.

### Acceptance Criteria

- The module imports without any `simulation`, `analysis`, `experiments`,
  `persistence`, `api`, or `observer` dependency.
- Mutating a returned policy is impossible (frozen).
- No field, constant, or docstring claims a canonical price or money object.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_contract.py -q`
- `uv run mypy src/agents/cognition/emergent_prices.py`
- Expected: all pass.

## Task 2: Add the owner-scoped emergent price ledger

### Intent

Provide the only place where an owner forms price expectations, from its own
valuation, own observations, and received quotes. The ledger never reads another
owner's state or world state and never produces a command.

### Implementation Steps

1. Add `PriceObservation(source_tick: int, item_kind: ItemKind,
   unit_kind: ItemKind, counterparty_ids: tuple[EntityId, ...],
   exchange_count: int, proposed_count: int, withdrawn_count: int,
   observed_ratio_milli: int | None, digest: str)`. `digest` is a SHA-256 prefix
   over counts and ratio only; no item ids.
2. Add `PriceQuote(venue_id: str, direction: PriceQuoteDirection,
   counterparty_id: EntityId | None, ratio_milli, confidence_milli,
   source: PriceQuoteSource, source_tick: int, first_tick: int,
   last_tick: int)` where `venue_id` is a content-addressed venue token or
   `none`, and `source_tick` is the observation or utterance tick.
3. Add `PriceExpectationRow(item_kind: ItemKind, unit_kind: ItemKind | None,
   unit_source: PriceUnitSource, expected_ratio_milli: int,
   confidence_milli: int, level: PriceExpectationLevel,
   valuation_reservation: int, observation_count: int, quote_count: int,
   first_tick: int, last_tick: int, observations: tuple[PriceObservation, ...],
   quotes: tuple[PriceQuote, ...], row_id: str)`. Validate: confidence and ratio
   ranges, `len(observations) ≤ max_observations_per_row`,
   `len(quotes) ≤ max_quotes_per_row`, sorted unique observation and quote
   `source_tick`, owner-local `row_id` equals
   `price_belief_id(owner, item_kind, unit_token)`.
4. Add `EmergentPriceLedger(owner_id: AgentId, rows: tuple[PriceExpectationRow, ...],
   notices: tuple[str, ...], policy_version: str)` plus
   `empty_emergent_prices(owner_id)`, `require_owner_emergent_prices(value,
   owner_id, *, field_name)`, `validate_emergent_price_caps(ledger, policy)`.
5. Add `apply_emergent_price_update(*, owner_id, tick,
   observations: tuple[PriceObservation, ...] = (),
   observed_quotes: tuple[PriceQuote, ...] = (),
   prior: EmergentPriceLedger | None, valuations: SubjectiveValuationLedger | None,
   acceptance: AcceptanceMemoryLedger | None, policy=None) -> EmergentPriceLedger`.
6. Build unit candidates deterministically, in this order:
   - `owner_reference`: every `kind_row` whose `reservation == 1`, using
     `reference_kind` as the unit.
   - `observed_medium`: every acceptance row with
     `received_count >= policy.medium_min_received`, highest count first.
   - `exchange_counterpart`: every unit kind carried by `observations` or
     `observed_quotes`.
   - `quoted`: unit kind named by received `prc_v1` quotes.
   Deduplicate by `(unit_kind, unit_source)`, cap at `policy.max_units`.
7. Group `observations` and `observed_quotes` by `(item_kind, unit_kind)`, then
   fold evidence for each `(item_kind, unit)` pair:
   - valuation ratio = `reservation(item) * 1000 // reservation(unit)` when the
     unit reservation is `1`; skip when absent.
   - observed exchange ratio from each grouped observation's
     `observed_ratio_milli`.
   - quote ratios with `confidence_milli >= policy.quote_min_confidence_milli`.
   Deduplicate observations by `(item_kind, unit_token, source_tick)`; an
   identical repeat fold is a no-op, and a conflicting repeat is ignored without
   incrementing any count. Deduplicate observed/communicated quotes by
   `(venue_id, item_kind, unit_token, direction, source_tick)`; the first in
   canonical order wins.
   Observed `ExchangeProposed`/`ExchangeWithdrawn` quotes are created only for
   `paired` sides (one homogeneous distinct kind per side); their
   `confidence_milli` is the locked neutral value 500. Communicated quotes use
   the frame confidence, and self-authored quotes use the owning row's current
   confidence. `heterogeneous`, `same_kind`, and `out_of_range` offers create no
   quote.
8. Set `expected_ratio_milli` to the deterministic weighted lower median of
   `(weight, ratio)` samples where valuation weight is 1, observed weight is
   `exchange_count`, quote weight is 1. Empty samples yield no row.
9. Compute `confidence_milli` exactly:
   `evidence = observation_count + quote_count`;
   `base = min(confidence_base_cap, evidence * confidence_base_per_evidence)`;
   `dispersion = (max_ratio - min_ratio) * 1000 // max(1, max_ratio)`;
   `agreement = 1000 - min(1000, dispersion)`;
   `confidence = min(1000, base + agreement * (1000 - base) // 2000)`.
10. Set `level`: `none` when no evidence; `weak` when
    `observation_count < expected_min_observations`; `strong` when confidence ≥
    `strong_min_confidence_milli`; otherwise `expected`.
11. Append `price_valuation_stale` when the newest valuation tick is more than
    `stale_after_ticks` behind `tick`; do not fabricate a valuation.
12. Sort rows by `(item_kind.value, unit_token, unit_source.value)`, truncate to
    `max_rows`, and append one `price_ledger_truncated` notice.
13. Add `src/simulation/emergent_prices_export.py` with a neutral
    `EmergentPriceOwnerRow` dataclass and
    `price_owner_export(ledgers, *, allowed_owner_ids=None)`: token-only rows
    containing owner token, venue token, window index, item-kind token, unit
    token, unit source, expected ratio, confidence, level, valuation reservation,
    counts, tick bounds, quote direction, quote source tick, and coverage. The export never includes counterparty ids, raw
    observations, valuations, or digest content. The module stays inside
    `simulation` and does not import `analysis`; composition maps these neutral
    rows to analysis inputs in Task 13.

### Required Interfaces and Contracts

- `PriceExpectationRow.expected_ratio_milli ∈ [0, 64_000]`.
- `confidence_milli ∈ [0, 1_000]`.
- `valuation_reservation ∈ [0, 16]` and is `0` when no valuation exists.
- Each grouped observation's `observed_ratio_milli` is `None` unless the source
  exchange had one homogeneous kind per side and distinct kinds; otherwise no
  ratio is invented.
- A ledger with no valuation, no observation, and no quote is
  `EmergentPriceLedger(owner_id, (), (), "emergent-prices.v1")`.

### Requirement Evidence

- User request: "Allow agents to develop subjective price expectations", "No
  global price table", represent "agent valuation, observed past exchanges,
  quoted offers, reference units, confidence".
- V3-18 valuations: `subjective_value.py:37-128`.
- V3-19 observed medium: `acceptance_memory.py:24-226`.
- Owner-scoped bounded pattern: `market_institutions.py:306-749,1265-1453`.

### Error Handling and Logging

- Reject foreign owners, non-`ItemKind` kinds, duplicate observations, oversize
  rows, and unknown unit sources with closed safe codes.
- `DEBUG price_ledger_updated owner=<redacted> rows=<n> truncated=<bool>` may log
  counts only. Never log valuation values, item kinds, unit tokens, quote
  amounts, counterparty sets, or digests.

### Tests

- `tests/unit/test_emergent_prices_ledger.py`:
  - one observation → `weak`; two → `expected`; high agreement plus confidence
    ≥ 750 → `strong`;
  - duplicate `(item_kind, unit, source_tick)` fold is byte-identical;
  - valuation-only row has `unit_source=owner_reference`;
  - acceptance row with `received_count=2` creates `observed_medium`;
  - a quote below `quote_min_confidence_milli` never changes the expectation;
  - an observed quote from a paired offer gets confidence 500; a heterogeneous
    or same-kind offer creates no quote;
  - duplicate quote `(venue, item, unit, direction, source_tick)` folds once;
  - stale valuation adds exactly one notice;
  - row/cap truncation is deterministic and sets one notice;
  - foreign owner and cross-owner export inputs are rejected.
- `tests/unit/test_emergent_prices_export.py`: export is token-only and stable.

### Acceptance Criteria

- No code path reads `WorldState`, a peer ledger, a runtime, a store, or an API
  object.
- The ledger contains no item ids, inventories, prices, money, credit, or debt.
- Repeated folding of the same facts leaves counts and canonical bytes unchanged.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_ledger.py tests/unit/test_emergent_prices_export.py -q`
- Expected: all pass.

## Task 3: Activate and carry price expectations under `markets_credit`

### Intent

Make price cognition deterministic only when both the owned V4 flag and the V3-18
valuation channel are active, with no new runner schema, root field, or per-agent
runner key, and carry one owner's ledger through the existing lifecycle.

### Implementation Steps

1. `configuration.py`: add `CognitionPriceMode(StrEnum)` with `DISABLED` and
   `DETERMINISTIC`; add `price_expectation_mode: CognitionPriceMode = DISABLED`
   and `price_expectation_policy: EmergentPricePolicy | None = None`.
2. Validate: disabled clears the policy; deterministic installs the locked
   default when absent; any other type raises. Add both fields to canonical
   material only when deterministic (`price_expectation_mode`,
   `price_expectation_policy_version`) and to the resolved config copy.
3. `runner.py`: set
   `price_mode = DETERMINISTIC if (config.v4_capability_flags.markets_credit and
   config.subjective_valuation is not None) else DISABLED`; pass mode and policy
   into the cognition config. Do not emit a runner schema key and do not add a
   `runner-config-v57`.
4. `loop.py`: store `_price_expectation_mode`/`_price_expectation_policy`; add
   `_prepare_emergent_prices(tick, perspective)` that collects only the owner's
   observed `ExchangeCompleted` aggregates, observed `ExchangeProposed`/
   `ExchangeWithdrawn` quotes, and received `prc_v1` quotes, then calls
   `apply_emergent_price_update` and returns the ledger. A quote venue token is
   derived from the owner's current location only; the loop never reads a hidden
   occurrence origin for cognition. It must run after
   `_prepare_subjective_valuations` and `_fold_acceptance_memory`.
5. Add the ledger to `SubjectiveSnapshot`, `CognitiveLoopProposal`,
   `CognitiveLoopResult`, `Perspective`, and fork state with exact owner/type
   validation.
6. `agent_runtime.py`: add slot/init, `_commit_emergent_prices` (clear when mode
   is disabled or ledger is `None`; reject foreign owner), perspective pass,
   checkpoint restore, and runtime view.
7. `run_control.py`: add `AgentRuntimeCheckpoint.emergent_prices` with owner and
   cap validation.
8. `runner_models.py`: add `SimulationRunnerResult.emergent_price_ledgers:
   tuple[EmergentPriceLedger, ...]` with ordered, owner-sorted, unique-owner,
   typed, cap-valid validation. `runner.py` validates and exports them through
   `export_emergent_price_ledgers()`.
9. `__init__.py` exports every public symbol from both new modules.

### Required Interfaces and Contracts

- Active iff `markets_credit is True` **and** `runner_config.subjective_valuation
  is not None`. Otherwise the ledger is empty and no cognition cost is paid.
- `markets_credit` off with valuation on remains V3-18 behavior only; no price
  ledger, no price notices.
- No new runner field appears in v56 encoding; v56 keyset stays exact.
- Checkpoints preserve one owner's ledger; admission copies nothing.

### Requirement Evidence

- Owned context and prerequisites: `v4_architecture.py:212-228`.
- V4-20 activation/carry pattern: `runner.py:1454-1470`, `agent_runtime.py:1355-1388,3669-3680`.
- Valuation activation: `runner_models.py:5198-5265`, `loop.py:2139-2230`.

### Error Handling and Logging

- Foreign owner, wrong ledger type, duplicate owner, or cap violation fails
  closed with the owning module's existing error type (`AgentRuntimeErrorCode.
  OWNERSHIP`, `SimulationRunnerError`).
- `INFO price_expectation_activation enabled=<bool> reason=market_flag|valuation_missing`
  and `DEBUG price_expectation_carried rows=<n>` are counts/tokens only.
- Never log owner ids, item kinds, unit tokens, valuations, quotes, or state.

### Tests

- `tests/unit/test_emergent_prices_activation.py`:
  - flag off + valuation on → disabled, empty ledger, no notice;
  - flag on + valuation off → disabled, empty ledger;
  - flag on + valuation on → deterministic and locked policy;
  - mode disabled clears policy;
  - runner config round-trips without v57 or a new key.
- `tests/unit/test_emergent_prices_carry.py`: perspective/checkpoint/result
  round-trip, foreign owner rejected, cap violation rejected, disabled clears.
- `tests/unit/test_emergent_prices_regression.py`: flag-off trajectories and
  checkpoint bytes match the pre-change baseline fixture.

### Acceptance Criteria

- Enabling only V4-20 (`markets_credit` without valuation) never allocates a
  price ledger, so the existing `market_institutions@1` experiment is unchanged.
- No new command, event, semantic type, write pair, runner version, or migration.
- Checkpoint and result carry are deterministic and order-stable.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_activation.py tests/unit/test_emergent_prices_carry.py tests/unit/test_emergent_prices_regression.py -q`
- Expected: all pass.

## Task 4: Add `prc_v1` speech frames with bounded quote attachment

### Intent

Represent quoted offers and expectations in existing speech without adding a
command or a convention situation, and without letting a received claim become
truth or a shared price.

### Implementation Steps

1. Create `src/agents/cognition/emergent_prices_communication.py` with
   `PRICE_FRAME_SUBJECT = "prc_v1"`,
   `PRICE_COMMUNICATION_POLICY_VERSION = "emergent-prices-communication.v1"`,
   `PRICE_FRAME_MAX_CHARS = 256`, `PRICE_FRAME_MAX_RELATIONS = 32`.
2. Add `PriceCommunicationAct` (`quote_offer`, `quote_counter`,
   `withdraw_quote`, `cite_expectation`) and `PRICE_ACT_PREDICATES`
   (`prc_quote`, `prc_counter`, `prc_withdraw`, `prc_expect`).
3. Add `PriceClaim(act, item_kind_token, unit_token, unit_source, direction,
   ratio_milli, confidence_milli, anchor)`. Validate token patterns, ratio and
   confidence ranges, `unit_token == "none"` iff `unit_source == unknown`, and
   `anchor` bounded to 64 safe characters.
4. `encode_price_claim` produces exactly 9 colon-separated parts:
   `prc_v1:<predicate>:<item_kind>:<unit>:<unit_source>:<direction>:<ratio>:<confidence>:<anchor>`.
5. `parse_price_claim` enforces the 9-part exact shape, no whitespace/control
   characters, closed enums, numeric-only ratio/confidence, and fails closed
   with safe codes (`price_invalid_frame`, `price_frame_oversize`,
   `price_invalid_enum`, `price_invalid_ratio`, `price_invalid_anchor`).
6. `price_claim_relation` and `parse_price_claim_relation` follow the
   `mkt_v1` pattern; unrelated relations return `None`.
7. `price_communicate_utterance(command, *, owner_id, ledger, counterparty_id,
   policy=None)` attaches at most one relation to an already-selected `Talk` or
   `Tell`. Selection order: highest `confidence_milli`, then
   `expected_ratio_milli`, then `item_kind.value`, then `unit_token`. Only rows
   with `confidence_milli >= policy.quote_min_confidence_milli` and a resolved
   unit are expressible. No utterance is created; no command is replaced.
8. `deliberation.py` calls the attachment after the command is selected, before
   the proposal is returned. It must be a no-op when the mode is disabled, the
   ledger is empty, or the command is not `Talk`/`Tell`.
9. Fold inbound `prc_v1` relations in `apply_emergent_price_update` as
   `communicated` quotes with the speaker as counterparty; a peer claim never
   sets `expected_ratio_milli` directly and never raises level above `expected`.

### Required Interfaces and Contracts

- `PriceClaim.ratio_milli ∈ [0, 64_000]`; `confidence_milli ∈ [0, 1_000]`.
- At most one `prc_v1` relation is attached per utterance.
- Malformed, oversize, or speaker-mismatched frames are dropped and counted;
  they never raise into the simulation loop.
- No new `Talk`/`Ask`/`Tell` field, no new command, no new convention situation.

### Requirement Evidence

- User request: represent "quoted offers", "reference units", "confidence".
- Existing bounded speech pattern: `market_institutions_communication.py:36-283`,
  `market_institutions.py:1119-1239`.
- Speech delivery is proof of delivery only: `.ai-factory/ARCHITECTURE.md`
  "Memory, testimony, and subjective concepts".

### Error Handling and Logging

- `WARN price_frame_dropped reason_code=<code>` with counts only.
- Never log the frame body, item kind, unit token, ratio, confidence, speaker,
  counterparty, or anchor.

### Tests

- `tests/unit/test_emergent_prices_communication.py`: exact 9-part round-trip;
  malformed/oversize/whitespace frames fail closed; unrelated relation returns
  `None`; speaker mismatch dropped; one relation maximum; quote selection is
  deterministic and respects the confidence floor; low-confidence ledger attaches
  nothing; a peer frame cannot mint a strong expectation.
- `tests/unit/test_emergent_prices_deliberation.py`: `Wait`, `Move`, `Give`,
  `NegotiateExchange` are never altered; only `Talk`/`Tell` may gain one
  relation.

### Acceptance Criteria

- No new command-producing path exists.
- `NegotiateExchange` admission and V3-18 offer fields are untouched.
- Agent speech remains bounded and malformed input is contained.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_communication.py tests/unit/test_emergent_prices_deliberation.py -q`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: auto-activation under `markets_credit` changes an existing V4-20 run that
  also uses valuations.
  Mitigation: activation requires both; V4-20's scenario does not set
  `subjective_valuation`; regression tests pin it.
- Risk: expectation math drifts into an effective global price through shared
  helper state.
  Mitigation: all state is per-owner frozen dataclasses; module-level mutable
  state is forbidden; leakage tests assert no cross-owner reads.
- Risk: frame text carries item/unit tokens into logs.
  Mitigation: logging uses counts and closed codes only; tests assert no frame
  body appears in captured logs.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
