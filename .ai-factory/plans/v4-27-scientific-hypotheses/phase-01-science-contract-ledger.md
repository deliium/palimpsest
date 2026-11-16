# Phase 1: Science Ownership, Contract, and Owner Ledger

Plan: [index.md](index.md)
Tasks: 1-4
Depends on: none

## Objective

Own the already-declared `science` V4 capability flag on the accepted
`runner-config-v56` seam, lock the `scientific-hypotheses.v1` detached-analysis
contract, and turn the existing owner-scoped experiment ledger into an explicit
testable-hypothesis ledger with claim, conditions, predicted result, confidence,
supporting observations, contradictions, creator/source, and append-only
historical revisions. After this phase the science context is owned and its
owner-side model is complete; no world rule is exposed and no runner schema,
command, event, write pair, or migration changes.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/v4_architecture.py` | `V4ContextId.SCIENCE` (74), science `V4ContextSpec` (235-250), `V4_EVENT_REUSING_CONTEXTS` membership via `versioning.py` (111) | The context is already declared as `OWNER_SCOPED`, seam `v4_capability_flags.science`, `uses_existing_events=True`, prerequisite `formal_rules`; it only lacks an owning plan |
| `src/simulation/runner_models.py` | `_V4_CAPABILITY_FLAG_NAMES` (307-320), `_V4_OWNED_CAPABILITY_FLAGS` (328-339), `V4CapabilityFlags.science` (1150), v56 requirement (8232-8244), `BoundedExperimentationSpec` (4752-4851) | Exact ownership set and the existing bounded-experimentation spec that supplies caps |
| `src/simulation/compatibility.py` | `V4_OWNED_CAPABILITY_FLAGS` (155-166), `v4_capability_flags` matrix text (778-801) | Two ownership sources must agree and the published matrix text must stop calling science unowned |
| `src/simulation/runner.py` | fail-closed V4 validation (2456-2528), world-model mode derivation (1065-1077), formal-rule mode derivation (1615-1632) | Science must fail closed only for its real preconditions; the run-level flag pattern already exists |
| `src/agents/cognition/experimentation.py` | `ExperimentHypothesis` (99-141), `ExperimentTrial` (144-164), `ExperimentLedger` (167-205), `score_remembered_experiment` (275-356), `compile_experiment_command` (499-613) | The ledger to deepen; support/counter, predicted outcome, evidence ids, and trials already exist |
| `src/agents/cognition/world_model.py` | `CausalHypothesis` (272-336), `CausalUpdateRecord` (238-268), `confidence_from_masses` (205-216) | The subjective causal model being extended; reuse its owner-scoped, support-ratio confidence posture |
| `src/world/actions.py` | `Experiment` (650-680), command registry (957-1003) | The already-closed test command; command count stays 43 |
| `src/world/experimentation.py` | `ExperimentOperator`, `ExperimentOutcomeClass`, `ExperimentProcessToken`, `DiscoveryMode` (8-47) | Closed prediction/outcome vocabulary; no new event or command is needed |
| `src/world/_experiment_apply.py` | `resolve_experiment` (52-84), `ExperimentResolved` write | Objective resolution stays world-owned; cognition only sees outcomes it remembers |
| `src/world/events.py` | `ExperimentResolved` (2225) | Existing committed evidence for trials |
| `src/agents/cognition/formal_rules.py` | `FormalRuleLedger` / `require_owner_formal_rules` (1289-1403) | V4 owner-ledger precedent without a runner schema bump |
| `tests/unit/test_experiment_hypothesis_draft.py`, `tests/unit/test_experiment_remember_repeat.py` | draft rejection, trial caps, support/counter, learning gate | Existing behavior that must remain green |
| `tests/unit/test_causal_world_model.py` | confidence quanta and owner scoping (200-220) | Confidence must stay integer/quantized and owner-relative |
| `tests/unit/test_runner_config_v56.py` (249-275), `tests/unit/test_v4_scaffolding_gate.py` (100-150) | science is currently parameterized as unowned | These are the pins this phase flips |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/simulation/runner_models.py` | modify | Add `science` to the owned V4 set; require predictive world model and bounded experimentation when science is enabled; update comments |
| `src/simulation/compatibility.py` | modify | Add `science` to the published owned set and update the matrix text; no version bump |
| `src/agents/cognition/experimentation.py` | modify | Add hypothesis enums/value objects, extend `ExperimentHypothesis`/`ExperimentLedger`, and add lifecycle helpers |
| `src/analysis/scientific_hypotheses_contract.py` | create | Policy token, closed enums, forbidden objective-rule vocabulary, token minting, layer guard, error codes |
| `src/analysis/scientific_hypotheses_policy.py` | create | Frozen validated policy, defaults, window helpers, caps |
| `src/analysis/scientific_hypotheses_rows.py` | create | Detached facts and token-only analysis rows |
| `src/analysis/__init__.py` | modify | Export contract, policy, and row symbols |
| `src/agents/cognition/__init__.py` | modify | Export new hypothesis symbols |
| `tests/unit/test_scientific_hypotheses_activation.py` | create | Science ownership and activation fail-closed matrix |
| `tests/unit/test_scientific_hypotheses_contract.py` | create | Closed vocabulary, forbidden keys, token determinism |
| `tests/unit/test_scientific_hypotheses_policy.py` | create | Defaults, ranges, frozen behavior |
| `tests/unit/test_scientific_hypotheses_ledger.py` | create | Claim, conditions, source, revisions, caps, owner checks |
| `tests/unit/test_scientific_hypotheses_lifecycle.py` | create | Support, contradiction, confidence, status, revision, idempotence |
| `tests/unit/test_scientific_hypotheses_layers.py` | create | Hard leakage guard |
| `tests/architecture/test_scientific_hypotheses_invariants.py` | create | 17/12/9/3, v56 only, no v57, no write pair, no migration |

## Task 1: Own the `science` V4 capability flag and lock activation

### Intent
Promote `science` from a declared-but-unowned V4 flag to an owned flag without
adding a context, runner schema, per-agent key, command, event, write pair, or
migration. Later tasks can then gate the hypothesis ledger on the flag, exactly
as V4-06 gates formal rules.

### Implementation Steps
1. In `src/simulation/runner_models.py`:
   - Add `"science"` to `_V4_OWNED_CAPABILITY_FLAGS` (the frozenset at
     328-339) and update the adjacent comment and `V4CapabilityFlags` docstring:
     V4-27 owns `science`; `epidemics`, `ecological_feedback`, and `disasters`
     remain unowned.
   - In `SimulationRunnerConfig.__post_init__`, next to the existing v56
     requirement at 8232-8244, add after the v56 check:
     ```python
     if self.v4_capability_flags.science:
         if self.schema_version != RUNNER_SCHEMA_VERSION_V56:
             raise ValueError(
                 "science requires runner-config-v56 "
                 "(code=science_requires_v56)"
             )
         if self.bounded_experimentation is None:
             raise ValueError(
                 "science requires bounded_experimentation "
                 "(code=science_requires_bounded_experimentation)"
             )
         if not self.capability_flags.predictive_world_model:
             raise ValueError(
                 "science requires predictive_world_model "
                 "(code=science_requires_predictive_world_model)"
             )
     ```
   - Do not require `formal_rules` at runtime: the V4 registry declares
     prerequisites as planning order, not a runtime gate.
   - Do not add `science` to `AgentCognitionSpec`; no per-agent key is added.
2. In `src/simulation/compatibility.py`:
   - Add `"science"` to `V4_OWNED_CAPABILITY_FLAGS` (155-166).
   - Update the `v4_capability_flags` `bump_trigger` text to say V4-27 owns
     `science`, nine flags are owned, three remain unowned, and v56 remains the
     accepted-only seam.
   - Change no version constant, accepted set, matrix entry id, or write version.
3. In `src/simulation/runner.py`, change nothing for ownership: the existing
   `unimplemented_enabled_names()` check at 2456-2528 now admits `science` once
   the owned set contains it. Do not add a new catch-all branch.
4. Keep `V4_CONTEXT_MAP_VERSION = "v4-context-map-v5"` and
   `_REQUIRED_CONTEXT_COUNT = 17`; ownership does not add a context.

### Required Interfaces and Contracts
- `V4CapabilityFlags.science` remains a default-off bool on
  `runner-config-v56`.
- Effective activation is exactly: v56 **and** `science` **and**
  `bounded_experimentation` **and** `predictive_world_model`.
- `science` stays in `V4_EVENT_REUSING_CONTEXTS`; it owns no reserved or
  deepening write pair and needs no migration stage.
- No `runner-config-v57`, no new root key, no new per-agent cognition key.
- Legacy configs with `science=False` are byte- and digest-identical.

### Requirement Evidence
- Original Request "Extend subjective causal world models into explicitly
  testable hypotheses".
- `src/simulation/v4_architecture.py:235-250` (science authority, seam,
  existing mechanism, non-goals).
- `src/simulation/versioning.py:102-118` (science is reuse-only).
- `.ai-factory/ARCHITECTURE.md` V4-01 ownership rules and requirement 5
  (flags stay runner JSON; no automatic migration).

### Error Handling and Logging
- Fail closed with `science_requires_bounded_experimentation` and
  `science_requires_predictive_world_model`; surface the existing
  `capability_unimplemented` path only for the three still-unowned flags.
- INFO `science_capability_owned` once at module import or runner construction,
  with no config values.
- Never log enabled/disabled flags together with run ids or agent ids.

### Tests
- `tests/unit/test_scientific_hypotheses_activation.py`:
  - v56 + science + bounded spec + predictive world model validates.
  - science without bounded spec raises `science_requires_bounded_experimentation`.
  - science without predictive world model raises
    `science_requires_predictive_world_model`.
  - science on v4/v55 fails closed with the existing v56 requirement (or the
    serializer's schema rejection for a schema that does not accept the
    `v4_capability_flags` key); the test asserts the closed error path, not a
    specific exception class.
  - `V4_OWNED_CAPABILITY_FLAGS` contains science and the unowned set is exactly
    `{epidemics, ecological_feedback, disasters}`.
  - `science=False` leaves the existing digest unchanged.
  - `"runner-config-v57"` is absent from `SUPPORTED_RUNNER_SCHEMA_VERSIONS`.
- Update `tests/unit/test_runner_config_v56.py` and
  `tests/unit/test_v4_scaffolding_gate.py` so science is asserted as owned and
  the fail-closed parameterization covers only the three remaining flags.

### Acceptance Criteria
- `science` can be enabled on v56 with its two real prerequisites.
- Every other combination fails closed with a closed code.
- Contexts remain 17, flags 12, map `v4-context-map-v5`.
- No schema, event, command, write-pair, or migration change exists.

### Verification
- `uv run pytest tests/unit/test_scientific_hypotheses_activation.py tests/unit/test_runner_config_v56.py tests/unit/test_v4_scaffolding_gate.py -q`
- `uv run python -c "from simulation.v4_architecture import validate_v4_contexts; validate_v4_contexts()"`
- `uv run python -c "from simulation.versioning import validate_write_pair_reservations as v; v()"`
- Expected result: pass for the new science tests; existing repository-wide
  `8 owned / 4 unowned` pins remain expected-red until Task 18, and that state
  is recorded rather than hidden.

## Task 2: Lock the `scientific-hypotheses.v1` contract, policy, and detached row DTOs

### Intent
Give analysis, the completed-run bridge, snapshot, and docs one closed
vocabulary so no implementation can expose an objective rule, invent a truth
field, or introduce a composite scientific score. The analysis layer must not
import `agents.cognition`; therefore the contract defines detached facts that
the experiments bridge maps from owner ledgers.

### Implementation Steps
1. Create `src/analysis/scientific_hypotheses_contract.py`:
   - Constants:
     `SCIENTIFIC_HYPOTHESES_POLICY_VERSION = "scientific-hypotheses.v1"`,
     `HYPOTHESIS_TOKEN_PREFIX = "schyp-"`,
     `OWNER_TOKEN_PREFIX = "owner-"`,
     `CLAIM_TOKEN_PREFIX = "claim-"`,
     `EVIDENCE_TOKEN_PREFIX = "evt:"`,
     `NONE_TOKEN = "none"`,
     `TOKEN_HEX_LEN = 16`.
   - Closed enums:
     `ScientificHypothesisStatus(provisional, supported, contradicted,
     inconclusive, superseded, retired)`,
     `ScientificHypothesisSourceKind(self_formulated, observed, remembered,
     communicated, recorded, unknown)`,
     `ScientificHypothesisRevisionReason(formulated, prediction_revised,
     condition_revised, support_added, contradiction_added,
     confidence_revised, source_adopted, test_formulated, superseded, retired)`,
     `ScientificHypothesisConditionSlot(location, day_phase, weather,
     held_item_kind, counterpart, season, temperature_band, hazard, action,
     concept)`,
     `ScientificHypothesisLayer(objective_evidence, owner_hypothesis,
     analytical_summary)`,
     `ScientificHypothesisCoverage(complete, partial, missing)`,
     `ScientificHypothesisAvailability(available, insufficient_samples,
     unavailable)`.
   - `SCIENTIFIC_HYPOTHESES_FORBIDDEN_KEYS`: frozen set containing at least
     `law`, `laws`, `rule`, `rules`, `objective_rule`, `engine_probability`,
     `success_probability`, `probability`, `delta`, `product_id`, `harm_band`,
     `truth`, `verified`, `proven`, `proof`, `score`, `accuracy`, `calibration`,
     `severity`, `rank`, `class`, `merit`, `blame`.
   - `SCIENTIFIC_HYPOTHESES_ERROR_CODES`: closed set including
     `scientific_hypotheses_invalid_policy`, `_invalid_cap`,
     `_invalid_hypothesis`, `_invalid_condition`, `_invalid_revision`,
     `_invalid_trial`, `_unstable_token`, `_forbidden_key`, `_layer_violation`,
     `_nonfinite_value`.
   - `mint_owner_token(owner_token)`, `mint_claim_token(operator,
     operand_a_id, operand_b_id, process_token, predicted_outcome)`, and
     `mint_hypothesis_token(owner_token, claim_token, created_tick)`: SHA-256
     over a `\x1f`-joined canonical string, first 16 hex chars, stable prefix;
     reject empty/unstable parts.
   - `assert_scientific_hypothesis_layer_separation(*groups)`: each group is
     homogeneous; objective rows may not carry hypothesis/claim tokens, owner
     rows may not carry objective rule keys, analytical rows may not carry
     `owner_token`, `source_token`, `event_token`, or `body_token`; no row may
     carry a forbidden key.
   - `ScientificHypothesesError(reason_code)`.
2. Create `src/analysis/scientific_hypotheses_policy.py`:
   - `ScientificHypothesesPolicy` frozen dataclass:
     `window_ticks=32`, `max_windows=512`, `max_events=200_000`,
     `max_owners=64`, `max_hypotheses=4_096`, `max_conditions=8_192`,
     `max_revisions=8_192`, `max_trials=4_096`,
     `max_summary_rows=1_024`, `max_notices=8`,
     `min_samples=3`, `confidence_prior=1`.
   - `__post_init__` rejects bools-as-ints, out-of-range caps, and
     `confidence_prior < 1`.
   - `window_index(tick)`, `window_tick(index)`, `window_bounds(tick)`,
     `default_policy()`, `policy_with(**overrides)`.
3. Create `src/analysis/scientific_hypotheses_rows.py` with frozen slots
   dataclasses. Facts (created by the experiments bridge) and rows (created by
   analysis) are separate:
   - `HypothesisConditionFact(slot, value_token)`
   - `HypothesisRevisionFact(revision_index, tick, reason, claim_token,
     predicted_outcome, condition_pairs, confidence_milli, evidence_ref)`
   - `HypothesisTrialFact(tick, event_token, outcome_class, discovery_mode,
     predicted_outcome, matched)`
   - `HypothesisFact(owner_token, hypothesis_token, claim_token,
     causal_hypothesis_token, status, predicted_outcome, confidence_milli,
     created_tick, active, source_kind, source_token, conditions, revisions,
     trials)` — `predicted_outcome` and `causal_hypothesis_token` use
     `NONE_TOKEN` when absent so rows never carry `None`.
   - `ScientificObjectiveEvidenceRow(window_index, window_tick, sequence,
     event_token, operator, outcome_class, discovery_mode, coverage)`
   - `ScientificHypothesisRow(window_index, window_tick, owner_token,
     hypothesis_token, claim_token, causal_hypothesis_token, status,
     predicted_outcome, confidence_milli, condition_count, condition_pairs,
     support_count, contradiction_count, revision_count, source_kind, active,
     created_tick, coverage)` — `condition_pairs` is an ordered tuple of
     `(slot, value_token)` pairs, at most eight; `causal_hypothesis_token` is
     `"none"` when no causal link exists; `created_tick` is the formulation tick.
   - `ScientificRevisionRow(window_index, window_tick, hypothesis_token,
     revision_index, revision_tick, reason, claim_token, predicted_outcome,
     condition_pairs, confidence_milli, coverage)`
   - `ScientificTrialRow(window_index, window_tick, hypothesis_token,
     trial_count, matched_count, mismatched_count, inconclusive_count,
     last_trial_tick, coverage)`
   - `ScientificSourceRow(window_index, window_tick, source_kind,
     hypothesis_count, adopted_count, coverage)`
   - `ScientificOutcomeRow(window_index, window_tick, outcome_class,
     trial_count, matched_count, mismatched_count, share_milli, coverage,
     availability)`
   - `ScientificCoverageRow(window_index, window_tick, window_count,
     event_count, owner_count, hypothesis_count, condition_count,
     revision_count, trial_count, truncated, coverage, availability)`
   - Every row validates stable tokens, non-negative ints, bool rejection, and
     forbidden keys at construction.
4. Export the public symbols from `src/analysis/__init__.py`.
5. Do not define a truth, verified, proven, accuracy, calibration, severity, or
   composite scientific score field.

### Required Interfaces and Contracts
- Analysis imports only `world`, `simulation`, and `memory` contracts plus its
  own modules; it never imports `agents.cognition` or `world._experiment_laws`.
- The detached facts are the only crossing point from the experiments bridge.
- All analysis-visible owner and source identities are tokens; no raw
  `AgentId`, `EntityId`, or owner label is retained.
- Closed enums are the only vocabulary; every row rejects forbidden keys.

### Requirement Evidence
- Original Request "Represent: claim conditions predicted result confidence
  supporting observations contradictions creator/source historical revisions"
  and "Do not expose objective rules".
- `.ai-factory/ARCHITECTURE.md` Key Principle 1 (separate authorities) and
  dependency rule (analysis reads only world/simulation/memory contracts).
- `src/analysis/economic_cascades_contract.py` and
  `src/analysis/social_mobility_contract.py` for the closed-contract pattern.

### Error Handling and Logging
- Contract failures raise `ScientificHypothesesError` with a closed code.
- WARN `scientific_hypotheses_forbidden_key` and
  `scientific_hypotheses_layer_violation` with the code only.
- Never log claims, conditions, predicted outcomes, source tokens, revisions,
  owner tokens, or event ids.

### Tests
- `tests/unit/test_scientific_hypotheses_contract.py`: policy token and
  prefixes; every enum value; forbidden keys include `law`/`rules`/`truth`/
  `verified`/`score`; deterministic token minting across hash seeds; row
  rejection of forbidden keys and float/bool ints; the analysis condition slots
  and cognition `HypothesisConditionSlot` values are identical (the test may
  import both; analysis itself may not).
- `tests/unit/test_scientific_hypotheses_policy.py`: defaults, ranges, frozen
  behavior, integer window arithmetic, `policy_with` validation.
- `tests/unit/test_scientific_hypotheses_layers.py`: clean three-layer bundle
  accepted; objective row with claim token rejected; analytical row with owner
  token rejected; owner row with `law` key rejected; mixed group rejected.
- `tests/architecture/test_scientific_hypotheses_invariants.py`: analysis
  modules do not import `agents`, `world._experiment_laws`, or `world._rules`;
  no `runner-config-v57`; no `alembic/versions/0018*`.

### Acceptance Criteria
- The detached vocabulary is closed and contains no objective-rule or truth
  field.
- Facts can describe every requested field without raw owner ids.
- Layer separation rejects every cross-layer leak tested.

### Verification
- `uv run pytest tests/unit/test_scientific_hypotheses_contract.py tests/unit/test_scientific_hypotheses_policy.py tests/unit/test_scientific_hypotheses_layers.py -q`
- Expected result: pass.

## Task 3: Extend the owner experiment ledger with explicit claim, conditions, source, and revisions

### Intent
Make the existing owner-scoped experiment hypothesis carry every requested
representation explicitly, while keeping the legacy draft compiler and trial
caps compatible. This is the subjective model that agents reason over; it never
reads objective laws.

### Implementation Steps
1. In `src/agents/cognition/experimentation.py`, add closed value objects:
   - `HypothesisConditionSlot(StrEnum)` with the same ten observation slots
     as the analysis contract (`location`, `day_phase`, `weather`,
     `held_item_kind`, `counterpart`, `season`, `temperature_band`, `hazard`,
     `action`, `concept`).
   - `HypothesisSourceKind(StrEnum)` with `self_formulated`, `observed`,
     `remembered`, `communicated`, `recorded`, `unknown`.
   - `HypothesisStatus(StrEnum)` with `provisional`, `supported`,
     `contradicted`, `inconclusive`, `superseded`, `retired`.
   - `HypothesisRevisionReason(StrEnum)` with `formulated`,
     `prediction_revised`, `condition_revised`, `support_added`,
     `contradiction_added`, `confidence_revised`, `source_adopted`,
     `test_formulated`, `superseded`, `retired`.
   - `HypothesisCondition(slot, value_token)`; reject empty/unstable values and
     `|`/`=` separators.
   - `HypothesisClaim(operator, operand_a_id, operand_b_id, process_token,
     predicted_outcome)`; `predicted_outcome` is either a closed
     `ExperimentOutcomeClass` value or `None` for an as-yet untested claim, and
     is never an engine probability.
   - `HypothesisRevision(revision_index, tick, reason, claim, conditions,
     confidence_milli, evidence_ref)`; `revision_index` is monotonic from 0,
     `confidence_milli` is `0..1000`, `evidence_ref` is an opaque token or
     `""`, and `conditions` is the condition set in force at that revision.
2. Extend `ExperimentHypothesis` with defaults so legacy constructions remain
   valid:
   - `causal_hypothesis_id: str = ""`
   - `conditions: tuple[HypothesisCondition, ...] = ()`
   - `confidence_milli: int | None = None`
   - `counter_evidence_event_ids: tuple[str, ...] = ()`
   - `source_kind: HypothesisSourceKind = SELF_FORMULATED`
   - `source_token: str = "self"`
   - `status: HypothesisStatus | None = None`
   - `revisions: tuple[HypothesisRevision, ...] = ()`
   - Add a `claim` property returning `HypothesisClaim` from the existing
     operator/operands/process/prediction fields.
   - Validate: max 8 conditions, unique `(slot, value_token)` pairs; max 32
     revisions with strictly increasing indexes; `source_token` stable and not
     `"self"` when source is not `self_formulated`; evidence tuples are tuples
     of non-empty strings.
   - In `__post_init__`, when `confidence_milli is None`, set it with
     `confidence_milli_from_masses(support, counter)`; when `status is None`,
     set it with `derive_hypothesis_status(support, counter)`. Explicit values
     are validated against the same bounds. This keeps legacy constructions
     valid and prevents a default `0` confidence from contradicting non-zero
     masses.
3. Extend `ExperimentLedger` validation and helpers:
   - Constants `MAX_HYPOTHESIS_CONDITIONS = 8`,
     `MAX_HYPOTHESIS_REVISIONS = 32`,
     `MAX_HYPOTHESIS_EVIDENCE = 64`, `HYPOTHESIS_CONFIDENCE_PRIOR = 1`.
   - `confidence_milli_from_masses(support, counter, *, prior=1) -> int`:
     `((support + prior) * 1000) // (support + counter + 2 * prior)`, clamped to
     `0..1000`; rejects bools and negative masses.
   - `derive_hypothesis_status(support, counter, *, min_evidence=2) -> str`:
     `provisional` when `support + counter < min_evidence`; `contradicted` when
     `counter >= min_evidence` and `counter > support`; `supported` when
     `support >= min_evidence` and `support > counter`; `inconclusive`
     otherwise.
   - `admit_hypothesis` eviction is deterministic: sort by
     `(confidence_milli, created_tick, hypothesis_id)` and drop the lowest;
     never evict another owner's row.
   - `record_trial` keeps the per-tick cap and trial idempotence by event id.
4. Keep `ExperimentCognitionBinding`, `parse_experiment_draft`,
   `compile_experiment_command`, `cite_experiment_event`, and
   `commit_experiment_learning` behavior unchanged for science-off runs.
5. Export the new symbols from `src/agents/cognition/__init__.py`.

### Required Interfaces and Contracts
- The ledger remains owner-scoped and frozen; helper functions return a new
  ledger, never mutate in place.
- `source_kind` is descriptive provenance, not trust: a communicated hypothesis
  starts at zero support and zero contradictions.
- Conditions are observation slots and values only. No condition may name a
  law, a rule row, an engine probability, a product id, a delta, or a harm band.
- `ExperimentOutcomeClass` remains the only predicted-result vocabulary.
- The ledger never imports or reads `world._experiment_laws`,
  `BoundedExperimentationSpec.laws`, or `world._rules`.

### Requirement Evidence
- Original Request list of eight represented fields.
- `src/agents/cognition/experimentation.py:99-205` (existing fields and caps).
- `src/agents/cognition/world_model.py:272-336` (owner-scoped causal
  hypotheses, support/counter, evidence ids, update history).
- `src/world/experimentation.py:8-47` (closed outcomes).
- `.ai-factory/ARCHITECTURE.md` Key Principle 1 and requirement 4.

### Error Handling and Logging
- Raise `ValueError` with stable field/reason codes such as
  `conditions: invalid_cap`, `revisions: out_of_order`,
  `predicted_outcome: invalid_outcome`, and `source_token: invalid_type`.
- DEBUG `scientific_hypothesis_admitted hypothesis_prefix=<12>` and
  `scientific_hypothesis_evicted hypothesis_prefix=<12>`.
- Never log claim operands, condition values, source tokens, or evidence ids.

### Tests
- `tests/unit/test_scientific_hypotheses_ledger.py`:
  - legacy `ExperimentHypothesis` construction still works with defaults.
  - claim projection round-trips operator/operands/process/prediction.
  - conditions reject duplicates, unknown slots, empty values, and > 8 rows.
  - revisions require monotonic indexes and ≤ 32 rows.
  - source `communicated` requires a non-empty source token; evidence starts
    empty.
  - owner mismatch rejected; eviction order is deterministic.
  - no `law`/`rules`/`probability` attribute exists on the hypothesis or
    ledger.
- Extend `tests/unit/test_experiment_hypothesis_draft.py` only where the new
  defaults change equality or repr.

### Acceptance Criteria
- Every requested field is explicitly represented and validated.
- Legacy science-off ledger behavior is unchanged.
- No objective rule is reachable from the ledger API.

### Verification
- `uv run pytest tests/unit/test_scientific_hypotheses_ledger.py tests/unit/test_experiment_hypothesis_draft.py tests/unit/test_experiment_remember_repeat.py -q`
- Expected result: pass.

## Task 4: Implement deterministic support, contradiction, confidence, and revision lifecycle

### Intent
Make hypothesis evolution explicit and auditable: each new trial appends
evidence, updates confidence, derives an owner-relative status, and appends one
revision. Hypotheses may be supported, contradicted, inconclusive, superseded,
or retired; none of these is an objective truth value.

### Implementation Steps
1. Add to `src/agents/cognition/experimentation.py`, reusing the
   `confidence_milli_from_masses` and `derive_hypothesis_status` helpers added
   in Task 3:
   - `formulate_hypothesis(...) -> ExperimentHypothesis` with a `formulated`
     revision at index 0.
   - `append_revision(hypothesis, *, reason, claim=None, conditions=None,
     confidence_milli=None, evidence_ref="", tick)`: returns a new hypothesis
     with one monotonic revision whose index is `max(existing indexes) + 1` (or
     `0` when empty); the revision records the claim and condition set in force
     at that point; trims the oldest revisions past 32 but never renumbers
     retained rows.
   - `revise_hypothesis(ledger, hypothesis_id, *, predicted_outcome=None,
     conditions=None, reason, tick)`: appends one revision, sets
     `status=provisional`, resets `active=True` for a prediction revision, and
     never rewrites old revisions. A retired hypothesis may be reopened; a
     superseded hypothesis is terminal and requires a new hypothesis instead.
   - `apply_test_outcome(ledger, hypothesis_id, *, outcome_class, event_id,
     tick, discovery_mode) -> ExperimentLedger`: idempotent by `event_id`;
     `unexpected` is always a contradiction regardless of the prediction;
     otherwise match the observed class against the prediction recorded in the
     most recent `test_formulated` revision at or before `tick` (falling back to
     the current `predicted_outcome` when no test revision exists), so a later
     prediction revision cannot retroactively change an earlier trial; when no
     prediction exists at all, record the trial as `inconclusive` without
     incrementing support or contradiction; append the event id to
     `evidence_event_ids` or `counter_evidence_event_ids` (capped at 64 each,
     newest kept) only for a classified prediction; recompute confidence and
     status; append one `support_added`, `contradiction_added`, or
     `confidence_revised` revision.
   - `supersede_hypothesis` and `retire_hypothesis` appending the matching
     revision and status.
2. Rewrite `score_remembered_experiment` to delegate its hypothesis update to
   `apply_test_outcome` while preserving the existing trial row, trial cap,
   discovery-mode logging, and unknown-offset behavior. Keep the function
   signature and return type.
3. Keep `commit_experiment_learning` thresholds unchanged; it reads
   `trials`, not the new status.

### Required Interfaces and Contracts
- Confidence is a support ratio, not a probability and not a calibrated score.
- Status is owner-relative and never named `true`, `verified`, or `proven`.
- A hypothesis with more contradictions than support remains in the ledger;
  it is not deleted or hidden.
- Revisions are append-only, ordered, bounded, and immutable.
- Trial scoring never creates a command, event, or objective write.

### Requirement Evidence
- Original Request "Hypotheses can be wrong", "supporting observations",
  "contradictions", "historical revisions".
- `src/agents/cognition/world_model.py:205-268` (support ratio and update
  records) and `src/agents/cognition/experimentation.py:275-356` (trial
  scoring).
- `.ai-factory/ARCHITECTURE.md` Key Principle 1.

### Error Handling and Logging
- Reject unknown hypothesis ids with `ValueError("hypothesis_not_found")` and
  duplicate trial events as a no-op.
- DEBUG `scientific_hypothesis_scored support=<n> counter=<n> status=<token>`
  and `scientific_hypothesis_revised reason=<token> revisions=<n>`.
- WARN `scientific_hypothesis_evidence_capped` when an evidence tuple is
  trimmed.
- Never log outcome values together with claim operands or owner ids.

### Tests
- `tests/unit/test_scientific_hypotheses_lifecycle.py`:
  - strict match increments support and appends `support_added`.
  - failure/harm/unexpected increments counter and appends
    `contradiction_added`; `unexpected` always contradicts.
  - duplicate event id is a no-op.
  - confidence is integer, monotone with support, and bounded.
  - status thresholds: provisional, supported, contradicted, inconclusive.
  - revision indexes stay monotonic after trimming; old revisions unchanged.
  - supersede/retire are terminal for test selection but retain evidence.
  - a hypothesis with five contradictions remains queryable.
  - property test: confidence and status are independent of Python hash seed.

### Acceptance Criteria
- Every trial produces exactly one revision and one evidence append.
- Wrong predictions are retained and visible as contradictions.
- Confidence and status are deterministic integer/closed-token values.

### Verification
- `uv run pytest tests/unit/test_scientific_hypotheses_lifecycle.py tests/unit/test_experiment_remember_repeat.py -q`
- Expected result: pass.

## Phase Risks and Mitigations
- Risk: a new per-agent key is smuggled in for science.
  Mitigation: Task 1 asserts `runner-config-v57` is absent and
  `AgentCognitionSpec` gains no field; activation uses the run-level flag.
- Risk: the analysis layer imports owner cognition to read ledgers.
  Mitigation: Task 2 defines detached facts; Task 9 maps them in `experiments`.
- Risk: conditions or revisions become a channel for objective rules.
  Mitigation: closed condition slots, forbidden-key validation, and the
  no-`world._experiment_laws` architecture test.
- Risk: confidence is read as a probability.
  Mitigation: integer milli, fixed prior, docs and tests state it is a support
  ratio only.

## Phase Completion Checklist
- `science` is owned and fails closed without its two prerequisites.
- The detached contract, policy, facts, and rows are locked.
- The owner ledger represents all requested fields.
- Lifecycle tests prove wrong hypotheses survive as contradictions.
- No runner schema, command, event, write pair, or migration was added.
- `index.md` Tasks 1-4 checkboxes are updated after verification.
