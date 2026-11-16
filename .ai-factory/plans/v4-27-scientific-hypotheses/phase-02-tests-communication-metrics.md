# Phase 2: Intentional Tests, Communication, Analysis, and Metrics

Plan: [index.md](index.md)
Tasks: 5-8
Depends on: Phase 1 (Tasks 1-4)

## Objective

Turn the owner hypothesis ledger into behavior: an agent with `science` enabled
may deliberately replace a default `Wait` with one existing `Experiment`
command when its conditions hold, may communicate a claim with `hyp_v1`, and may
adopt a communicated claim as provisional evidence-free belief. Detached analysis
then composes bounded hypothesis, evidence, test, revision, source, and outcome
rows and emits six metric families (244 -> 250). No objective law, rule row,
delta, product id, or probability is exposed at any layer.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/agents/cognition/experimentation.py` | `compile_experiment_command` (499-613), `_deterministic_action` (463-480), `parse_experiment_draft` (414-460) | Existing test compiler and closed draft path |
| `src/agents/cognition/loop.py` | loop state/result (285-334, 1811), frame ingest for credit (3187-3215) and evidence (3940-3959), result assembly (7327-7330), remembered experiment scoring (7074) | Exact wiring points for test selection, adoption, and result replacement |
| `src/agents/cognition/configuration.py` | `CognitionWorldModelMode` (269-274), config fields (721), validation (876-888), digest (1968-1970) | Internal mode pattern; no runner schema |
| `src/simulation/runner.py` | `_cognition_config_for` (1065-1077), formal-rule mode derivation (1615-1632) | Pass `science` into the loop without a new runner key |
| `src/world/actions.py` | `Experiment` (650-680) | The only command the test path may emit |
| `src/world/events.py` | `ExperimentResolved` (2225-2265) | Objective evidence; carries `delta`, `product_id`, `health_delta`, which must never enter analysis |
| `src/agents/cognition/formal_rule_communication.py` | `fr_v1` encode/parse/attach (344-548) | Speech-frame template |
| `src/agents/cognition/evidence_testimony_communication.py` | `ev_v1` parse/attach (393-574) | Ingest and owner-check template |
| `src/analysis/economic_cascades_analysis.py` | `harvest_economic_cascades_analysis` (250-471), layer guard call (419-427) | Detached composition template |
| `src/analysis/scientific_hypotheses_contract.py` | created in Task 2 | Closed vocabulary and layer guard |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT` (53), family enum (318-325), key tuples (9199-9251), builders (10682-10689) | Exact append mechanics |
| `src/analysis/metric_service.py` | input field (449), guarded emission block (2831-2883) | Exact service wiring |
| `tests/unit/test_economic_cascades_catalog.py` | first-244 digest guard (17-30, 50-52) | The append proof this phase must extend |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/agents/cognition/experimentation.py` | modify | Add `compile_scientific_test`, condition observation helpers, and test-intent revisions |
| `src/agents/cognition/configuration.py` | modify | Add internal `CognitionScientificHypothesesMode`, fields, validation, digest |
| `src/simulation/runner.py` | modify | Derive the mode from `v4_capability_flags.science` |
| `src/agents/cognition/loop.py` | modify | Prepare/carry the ledger, replace `Wait` with one test, adopt `hyp_v1` frames |
| `src/agents/cognition/scientific_hypothesis_communication.py` | create | `hyp_v1` encode, parse, attach, adopt |
| `src/agents/cognition/__init__.py` | modify | Export communication and test symbols |
| `src/analysis/scientific_hypotheses_analysis.py` | create | Bounded harvest and `ScientificHypothesesAnalysis` |
| `src/analysis/scientific_hypotheses_metrics.py` | create | Six `MetricDocument` computers |
| `src/analysis/specifications.py` | modify | Count 250, six ids, key tuples, builder and spec functions |
| `src/analysis/metric_service.py` | modify | Input field and guarded emission block |
| `src/analysis/__init__.py` | modify | Export analysis and metric symbols |
| `src/experiments/collectors.py` | modify | Inject the analysis behind the science gate (Task 9 supplies the builder) |
| `tests/unit/test_scientific_hypotheses_test_wiring.py` | create | Wait replacement, condition gating, caps, passthrough |
| `tests/unit/test_scientific_hypotheses_communication.py` | create | Frame round-trip, adoption, no evidence copy |
| `tests/unit/test_scientific_hypotheses_analysis.py` | create | Empty/one/multi-window, owner tokenization, no-rule fields |
| `tests/unit/test_scientific_hypotheses_analysis_properties.py` | create | Ordering/cap/digest properties |
| `tests/unit/test_scientific_hypotheses_catalog.py` | create | 250 count, first-244 digest, six appended ids |
| `tests/unit/test_scientific_hypotheses_metrics.py` | create | Six families, availability, keys, no score |
| `tests/unit/test_scientific_hypotheses_metric_service.py` | create | Injection and absence |

## Task 5: Wire intentional scientific tests from `Wait` to one `Experiment`

### Intent
Let an agent deliberately test an existing hypothesis without adding a command:
when science is enabled, the selected command is the default `Wait`, and a
hypothesis's conditions hold, the loop replaces that `Wait` with one existing
`Experiment` command that names the hypothesis. The agent never overrides a
meaningful action, never reads an objective law, and never exceeds the bounded
trial budget.

### Implementation Steps
1. In `src/agents/cognition/configuration.py`:
   - Add `CognitionScientificHypothesesMode(StrEnum)` with `DISABLED` and
     `DETERMINISTIC`.
   - Add `scientific_hypotheses_mode: CognitionScientificHypothesesMode =
     CognitionScientificHypothesesMode.DISABLED` and
     `scientific_hypotheses_policy: str = "scientific-hypotheses.v1"` to
     `CognitionLoopConfig`.
   - Validate the mode type and exact policy token; include the mode and policy
     in the config digest next to the existing world-model/formal-rule entries
     **only when the mode is not `DISABLED`**, so science-off config identity is
     unchanged.
2. In `src/simulation/runner.py::_cognition_config_for`, set
   `scientific_hypotheses_mode=ENABLED` exactly when
   `config.v4_capability_flags.science` is true; otherwise `DISABLED`. Do not
   add a runner root or per-agent key.
3. In `src/agents/cognition/experimentation.py`, add:
   - `HypothesisConditionSlot` → observation accessor helper
     `observed_condition_tokens(observation) -> Mapping[HypothesisConditionSlot,
     tuple[str, ...]]`. Read only public observation attributes; return an empty
     mapping when an attribute is absent. Never inspect `WorldState`, rules, or
     law catalogs.
   - `conditions_hold(conditions, observation) -> bool`: every condition's
     `(slot, value_token)` must appear in the observed mapping.
   - `compile_scientific_test(owner_id, ledger, observation, *,
     hypothesis_id=None, formulate_if_missing=False,
     causal_model=None) -> ExperimentCompile`:
     - validate owner and ledger; when `causal_model` is provided it must be an
       owner-matching `CausalWorldModel` (or `None`);
     - reject when the per-tick trial cap is already reached
       (`experiment_trial_cap`);
     - select candidates where `active` is true, status is not `superseded` or
       `retired`, `predicted_outcome` is not `None`, conditions hold, and no
       trial for this hypothesis exists at this tick;
     - sort candidates by `(0 if counter > support else 1, created_tick,
       hypothesis_id)` and take the first;
     - when `causal_model` is provided, choose the highest-confidence
       `CausalHypothesis` owned by the same agent whose atoms are all present in
       `observed_condition_tokens(observation)`; attach its `hypothesis_id` as
       `causal_hypothesis_id` and map `provenance_kind` `observation` ->
       `HypothesisSourceKind.OBSERVED` and `memory` ->
       `HypothesisSourceKind.REMEMBERED`. If no causal hypothesis matches, leave
       `causal_hypothesis_id=""` and keep the existing source. Never read
       engine laws or probabilities;
     - if none and `formulate_if_missing` is true **and the ledger has no other
       active hypothesis with a predicted outcome**, call the existing
       `_deterministic_action(observation)` path, create a hypothesis with
       conditions from `observed_condition_tokens` and
       `source_kind=HypothesisSourceKind.OBSERVED`, and use it; an explicit
       draft keeps `source_kind=SELF_FORMULATED`; if active hypotheses exist
       but none is currently testable, return
       `scientific_hypothesis_untestable` without creating a new row;
     - return `ExperimentCompile(ledger=updated, command=Experiment(...,
       hypothesis_id=stored.hypothesis_id), hypothesis=stored)` after appending
       one `test_formulated` revision with reason `test_formulated`;
     - on no candidate return `ExperimentCompile(ledger,
       reason="scientific_hypothesis_untestable")`.
   - Extend `compile_experiment_command` with an optional
     `conditions: tuple[HypothesisCondition, ...] = ()` parameter so the
     science path can attach observed conditions; the legacy path passes the
     empty tuple and remains byte-identical.
4. In `src/agents/cognition/loop.py`:
   - Add `_scientific_hypotheses_mode` initialized from the config and carried
     with the existing experiment ledger.
   - Immediately before the `CognitiveLoopResult` construction at 7327, add:
     ```python
     if self._scientific_hypotheses_mode is ENABLED and type(command) is Wait:
         compiled = compile_scientific_test(
             loop_input.agent_id,
             self.experiment_ledger_for(loop_input.agent_id),
             loop_input.observation,
             formulate_if_missing=True,
             causal_model=proposal.causal_world_model,
         )
         self._experiment_ledger = compiled.ledger
         if compiled.command is not None:
             command = compiled.command
             _LOG.info("scientific_test_proposed")
     ```
     `loop_input.agent_id`, `loop_input.observation`, and
     `proposal.causal_world_model` are the in-scope values on the success path;
     do not use a bare `owner`, `observation`, or `world_model` name that may be
     out of scope.
   - Leave every non-`Wait` command untouched and leave `DISABLED` a pure
     passthrough.
5. Add tests with a synthetic observation exposing `tick`, `location_id`,
   `day_phase`, `weather`, `held_item_kind`, `counterpart`, `season`,
   `temperature_band`, `hazard`, `action`, and `concept`.

### Required Interfaces and Contracts
- The emitted command is always an existing `Experiment`; command count stays
  43 and no event is added.
- `Wait` replacement happens only when science is `DETERMINISTIC`; all other
  modes are passthrough.
- Conditions are checked against the owner's observation only. No law, rule,
  probability, product id, or delta is read.
- At most `max_trials_per_tick` tests are emitted per tick.
- A test of an existing hypothesis appends exactly one `test_formulated`
  revision; a newly formulated hypothesis appends `formulated` and
  `test_formulated`.

### Requirement Evidence
- Original Request "Agents may intentionally formulate tests" and "Do not
  expose objective rules".
- `src/agents/cognition/experimentation.py:499-613` (existing compiler).
- `src/world/actions.py:650-680` (existing command).
- `.ai-factory/ARCHITECTURE.md` Key Principle 4 (optional channels leave
  off-path behavior unchanged).

### Error Handling and Logging
- INFO `scientific_test_proposed` once per emitted command, with no operand or
  claim values.
- WARN `scientific_test_skipped reason_code=<token>` for
  `scientific_hypothesis_untestable` and `experiment_trial_cap`.
- ERROR only for invalid owner/ledger types.
- Never log conditions, operand ids, predicted outcomes, or the hypothesis id.

### Tests
- `tests/unit/test_scientific_hypotheses_test_wiring.py`:
  - science off leaves `Wait` unchanged and the ledger untouched.
  - science on with a matching hypothesis replaces `Wait` with one `Experiment`
    whose `hypothesis_id` is the selected row.
  - a matching causal hypothesis is attached as `causal_hypothesis_id` with the
    expected observed/remembered source; no match leaves the link empty.
  - a non-`Wait` command is never replaced.
  - conditions mismatch produces no command and no revision.
  - trial cap produces `experiment_trial_cap` and no command.
  - new formulation attaches observed conditions.
  - `compile_scientific_test` rejects a foreign-owner ledger.
  - a source scan asserts no `world._experiment_laws` / `world._rules` import.
- Add one loop-level test using `CognitionLoopConfig(mode=ENABLED)` and a
  scripted observation, asserting the final result command type and ledger
  carry.

### Acceptance Criteria
- A science-enabled agent can intentionally test an existing hypothesis.
- A science-disabled agent is a pure passthrough.
- No command, event, runner key, or objective rule is added.

### Verification
- `uv run pytest tests/unit/test_scientific_hypotheses_test_wiring.py tests/unit/test_experiment_hypothesis_draft.py -q`
- Expected result: pass.

## Task 6: Add `hyp_v1` claim communication and communicated adoption

### Intent
Let an owner communicate a claim, its conditions, predicted result, confidence,
and source without exposing objective rules. A receiver may adopt the claim as
a provisional hypothesis, but communication is testimony, not evidence: support
and contradictions start at zero and no event ids are copied.

### Implementation Steps
1. Create `src/agents/cognition/scientific_hypothesis_communication.py`:
   - `SCIENTIFIC_HYPOTHESIS_FRAME = "hyp_v1"`,
     `SCIENTIFIC_HYPOTHESIS_FRAME_MAX_CHARS = 384`,
     `SCIENTIFIC_HYPOTHESIS_RELATION_MAX = 32`.
   - `CommunicatedScientificHypothesis` frozen slots dataclass with
     `operator`, `operand_a_id`, `operand_b_id`, `process_token`,
     `predicted_outcome`, `confidence_milli`, `conditions`, `source_kind`,
     `source_token`, `claim_token`.
   - `encode_scientific_hypothesis_claim(hypothesis) ->
     CommunicationRelation`: subject `hyp_v1`, predicate `claim`, object is a
     colon-separated payload with the fields above and condition pairs encoded
     as `slot=value` joined by `+`; reject `:`/`|`/whitespace in values.
   - `parse_scientific_hypothesis_claim_relation(relation) ->
     CommunicatedScientificHypothesis | None`: return `None` on any malformed
     field; reject objective-rule keys or values; never raise on malformed peer
     input.
   - `attach_scientific_hypothesis_claim(utterance, hypothesis) ->
     StructuredUtterance`: only for `Talk`/`Tell`; preserve recipient and
     existing relations; append at most one `hyp_v1` frame; reject at the
     relation cap.
   - `adopt_communicated_hypothesis(ledger, claim, *, source_token, tick) ->
     ExperimentLedger`: validate owner ledger; compute the receiving owner's
     stable `experiment_hypothesis_id(ledger.owner_id, claim.operator,
     claim.operand_a_id, claim.operand_b_id, claim.process_token)`; never use the
     sender's `claim_token` as the local hypothesis id (it is provenance only);
     create a row with `source_kind=COMMUNICATED`, `source_token=source_token`,
     `support=0`, `counter=0`, empty evidence, `status=PROVISIONAL`, and one
     `source_adopted` revision; return the ledger unchanged when the id already
     exists.
2. In `src/agents/cognition/loop.py`, add
   `_apply_scientific_hypothesis_relations(owner, relations, tick)` next to the
   existing evidence-frame ingest at 3940-3959 and call it with
   `loop_input.agent_id`. For each relation whose subject is `hyp_v1`, parse it
   and adopt it when science is enabled; pass
   `source_token=f"evt:{delivery_event_id}"` from the received `Talked`/`Told`
   occurrence, never the sender's agent id. Do not create a memory, trial,
   support, or contradiction from receipt alone.
3. Add `_select_scientific_hypothesis(ledger, tick)` in `loop.py`:
   choose the most recent hypothesis with a `test_formulated` revision at or
   before `tick`, still active, and no `source_adopted`/communicated revision;
   sort by `(revision.tick, hypothesis_id)` and take the last; return at most
   one. Immediately before result assembly at 7327, attach it with
   `attach_scientific_hypothesis_claim(command, hypothesis)` only when
   `type(command) in (Talk, Tell)` and science is enabled. Do not attach in the
   deliberation decorator chain: that function has only `snapshot`/`profile`
   and no experiment ledger. At most one `hyp_v1` frame per utterance.
4. Export the new symbols from `src/agents/cognition/__init__.py`.

### Required Interfaces and Contracts
- `hyp_v1` travels inside existing `Talk`/`Tell`; no command, event, or observer
  semantic type is added.
- Attachment happens at the loop result boundary where the experiment ledger is
  in scope, at most once per utterance, and only for a recently tested active
  claim with no prior communicated revision.
- A communicated claim carries no evidence and no objective rule payload.
- The adoption source token is the receiver-observed `Talked`/`Told` delivery
  event token, never the sender's agent id.
- Same-root retellings never count as independent evidence; the trial path is
  the only evidence path.
- Adoption is idempotent by hypothesis id and owner-scoped.

### Requirement Evidence
- Original Request "creator/source" and "Do not expose objective rules".
- `src/agents/cognition/formal_rule_communication.py:344-548` (frame pattern).
- `src/agents/cognition/evidence_testimony_communication.py:393-574`
  (owner/ingest pattern).
- `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts"
  (testimony is not evidence; shared roots are not corroboration).

### Error Handling and Logging
- WARN `scientific_hypothesis_frame_dropped reason_code=<token>` for malformed
  or oversized frames; never raise into the tick loop.
- DEBUG `scientific_hypothesis_adopted source_kind=communicated`.
- Never log claim payloads, operand ids, source tokens, or the raw relation.

### Tests
- `tests/unit/test_scientific_hypotheses_communication.py`:
  - encode/parse round-trip for one and two conditions.
  - reject `:`/whitespace in values and > 8 conditions.
  - reject payloads containing `law`, `rules`, `probability`, `delta`,
    `product_id`, or `harm_band`.
  - attach only to `Talk`/`Tell`, preserve recipient/relations, relation cap;
    at most one frame; no attach for `Ask` or when no test revision exists.
  - adopt creates a provisional zero-evidence row with `source_adopted`; the
    source token is the received delivery event token, never the sender agent
    id.
  - adopting the same claim twice is a no-op.
  - a received claim produces no support, contradiction, or trial.
  - foreign-owner ledger rejected.
- Add one loop-level test that feeds a `hyp_v1` relation through the perspective
  ingest and asserts the ledger gained exactly one provisional row.

### Acceptance Criteria
- Claims can be communicated and adopted without new wire surfaces.
- Adoption never manufactures evidence or truth.
- No objective rule value can cross the frame.

### Verification
- `uv run pytest tests/unit/test_scientific_hypotheses_communication.py -q`
- Expected result: pass.

## Task 7: Compose the bounded `ScientificHypothesesAnalysis` harvest

### Intent
Build one detached analysis value from committed `ExperimentResolved` events
and owner-exported hypothesis facts. The analysis keeps objective evidence,
owner hypothesis rows, and analytical summaries in separate layers, copies no
objective rule payload from `ExperimentResolved`, and never back-fills a trial
that the owner did not remember.

### Implementation Steps
1. Create `src/analysis/scientific_hypotheses_analysis.py`:
   - `ScientificHypothesesAnalysis` frozen slots dataclass with
     `objective_rows`, `hypothesis_rows`, `revision_rows`, `trial_rows`,
     `source_rows`, `outcome_rows`, `coverage_rows`, `notices`, `policy_version`,
     plus `row_count` and `source_layers`.
   - `empty_scientific_hypotheses_analysis(policy=...)` returns `missing`
     coverage and no rows.
   - `scientific_hypotheses_analysis_digest(analysis)` hashes only counts,
     ordering, coverage, and notices; never row payloads or owner tokens.
   - `harvest_scientific_hypotheses_analysis(*, events, facts, policy=None,
     window_end=None)`:
     - accept only `Sequence[WorldEvent]` and
       `Sequence[HypothesisFact]`; reject any other type;
     - keep only `ExperimentResolved` events; copy only `event_id`, `tick`,
       `operator`, `outcome_class`, and `discovery_mode`; never copy `delta`,
       `product_id`, `harm_band`, `health_delta`, `resulting_health`, or
       `created_item_id`;
     - group facts by tokenized owner and window; the bridge has already
       tokenized `counterpart` condition values, so the harvest never receives a
       raw agent id;
     - emit one objective evidence row per safe event, one hypothesis row per
       fact (including `created_tick`, its ordered `condition_pairs`, and
       `causal_hypothesis_token`), one revision row per revision (including
       `revision_tick`), one trial row per hypothesis, one source row per source
       kind, one outcome row per outcome class, and one coverage row per window;
     - link a trial to objective evidence only when the trial's event token
       equals a safe event token; otherwise the trial is owner-only and the
       evidence row is `unlinked`;
     - enforce caps independently with deterministic prefixes and
       `coverage="partial"` plus one notice per truncated family;
     - compute availability: `missing` when no facts; `insufficient_samples`
       when fewer than `min_samples` hypotheses or trials; `available`
       otherwise;
     - call `assert_scientific_hypothesis_layer_separation` with one group per
       layer.
2. Do not add `hypothesis_id` to `ExperimentResolved`; the objective event has
   no such field and adding it would widen replay-v27/codec `v25`. The owner
   trial row is the only link.
3. Export the public analysis symbols from `src/analysis/__init__.py`.

### Required Interfaces and Contracts
- Analysis imports only `world` events, its own contract/policy/rows, and
  standard library. It never imports `agents.cognition`, `world._experiment_laws`,
  `world._rules`, simulation runtime, persistence, or API.
- Owner rows carry tokenized `owner_token` only; analytical rows and the future
  snapshot carry no owner token.
- Objective evidence rows carry no hypothesis token, claim token, or status.
- No row carries an objective rule field or a truth/score field.
- The harvest is deterministic for any input order and independent of
  `PYTHONHASHSEED`.

### Requirement Evidence
- Original Request "supporting observations", "contradictions",
  "creator/source", "historical revisions", "Do not expose objective rules".
- `src/analysis/economic_cascades_analysis.py:250-471` (detached composition
  and layer guard).
- `src/world/events.py:2225-2265` (the rule payload that must not be copied).
- `.ai-factory/ARCHITECTURE.md` dependency rule for `analysis`.

### Error Handling and Logging
- WARN `scientific_hypotheses_truncated family=<token>` once per family.
- WARN `scientific_hypotheses_unlinked_trial` with a count only.
- ERROR `scientific_hypotheses_harvest_invalid` with a closed code.
- Never log facts, owner tokens, event tokens, claims, or conditions.

### Tests
- `tests/unit/test_scientific_hypotheses_analysis.py`:
  - no facts -> `missing`, no documents.
  - one hypothesis -> owner row, revision row, source row, coverage.
  - two windows -> separate rows and correct window indexes.
  - event with `delta`/`product_id` produces no such field in any row or
    serialized analysis.
  - trial linking by event token; unlinked trial retained owner-only.
  - owner ids are tokenized; analytical rows have no owner token.
  - each cap truncates independently with `partial` and one notice.
  - fewer than 3 hypotheses/trials -> `insufficient_samples`.
- `tests/unit/test_scientific_hypotheses_analysis_properties.py`: shuffled
  input order produces the same digest; caps monotone; window bounds exact.

### Acceptance Criteria
- The analysis represents all requested fields without objective rules.
- Layers cannot mix and owner ids never reach analytical rows.
- Empty and partial states are explicit, not zeros.

### Verification
- `uv run pytest tests/unit/test_scientific_hypotheses_analysis.py tests/unit/test_scientific_hypotheses_analysis_properties.py -q`
- Expected result: pass.

## Task 8: Append six metric families (244 -> 250) and wire the service

### Intent
Expose the analysis as six independent descriptive families. The first 244
families keep their ids, order, versions, and value keys. No family is a
composite scientific score, accuracy, calibration, or truth metric.

### Implementation Steps
1. In `src/analysis/specifications.py`:
   - Set `METRIC_FAMILY_COUNT = 250`.
   - Append six `MetricFamilyId` members after `CASCADE_COVERAGE`:
     `SCIENTIFIC_HYPOTHESIS_STRUCTURE`,
     `SCIENTIFIC_HYPOTHESIS_EVIDENCE`,
     `SCIENTIFIC_HYPOTHESIS_TEST_ACTIVITY`,
     `SCIENTIFIC_HYPOTHESIS_REVISIONS`,
     `SCIENTIFIC_HYPOTHESIS_PROVENANCE`,
     `SCIENTIFIC_HYPOTHESIS_PREDICTION_OUTCOMES`.
   - Add six ordered key tuples:
     - `SCIENTIFIC_HYPOTHESIS_STRUCTURE_KEYS` =
       `hypothesis_count`, `active_count`, `provisional_count`,
       `supported_count`, `contradicted_count`, `inconclusive_count`,
       `superseded_count`, `retired_count`, `condition_count`, `claim_count`,
       `mean_conditions_milli`, `coverage_ratio_milli`.
     - `SCIENTIFIC_HYPOTHESIS_EVIDENCE_KEYS` =
       `support_observation_count`, `contradiction_count`,
       `hypotheses_with_support`, `hypotheses_with_contradiction`,
       `evidence_event_count`, `unresolved_evidence_count`,
       `support_share_milli`, `contradiction_share_milli`,
       `confidence_mean_milli`, `confidence_min_milli`,
       `confidence_max_milli`.
     - `SCIENTIFIC_HYPOTHESIS_TEST_ACTIVITY_KEYS` =
       `test_formulated_count`, `trial_count`, `deliberate_trial_count`,
       `accidental_trial_count`, `tested_hypothesis_count`,
       `untested_hypothesis_count`, `mean_trials_milli`.
     - `SCIENTIFIC_HYPOTHESIS_REVISIONS_KEYS` =
       `revision_count`, `revised_hypothesis_count`,
       `formulated_revision_count`, `prediction_revision_count`,
       `condition_revision_count`, `evidence_revision_count`,
       `source_revision_count`, `superseded_revision_count`,
       `mean_revision_depth_milli`, `max_revision_depth`.
     - `SCIENTIFIC_HYPOTHESIS_PROVENANCE_KEYS` =
       `self_formulated_count`, `observed_count`, `remembered_count`,
       `communicated_count`, `recorded_count`, `unknown_count`,
       `adopted_count`, `communicated_share_milli`,
       `independent_evidence_count` — the last counts hypotheses with at least
       one owner-generated trial evidence id, never communicated claims.
     - `SCIENTIFIC_HYPOTHESIS_PREDICTION_OUTCOMES_KEYS` =
       `matched_count`, `mismatched_count`, `inconclusive_count`,
       `unexpected_count`, `success_count`, `partial_success_count`,
       `failure_count`, `harm_count`, `matched_share_milli`,
       `mismatched_share_milli`.
   - Add `_scientific_hypotheses_spec(...)` using the V4-26 `_base` pattern with
     `evidence_inputs={OBJECTIVE_EVENT_STATE, AGENT_VISIBLE_PROJECTION,
     BELIEF_REVISION_TESTIMONY}`, `empty_case="unavailable_unknown"`,
     `one_case="insufficient_samples"`, `all_zero_case="emit_zero"`.
   - Add six `_spec_*` functions with descriptive populations:
     `hypotheses` / `active_hypotheses`; `hypothesis_evidence` /
     `observed_evidence`; `hypothesis_trials` / `tested_hypotheses`;
     `hypothesis_revisions` / `revised_hypotheses`; `hypothesis_sources` /
     `hypotheses`; `hypothesis_trials` / `classified_trials`.
   - Append the six builders to `_BUILDERS` after the cascade builders.
2. Create `src/analysis/scientific_hypotheses_metrics.py`:
   - `_document(...)` copying the V4-26 availability/coverage/provenance
     pattern with `source_kind="scientific_hypotheses_analysis"`.
   - `compute_scientific_hypothesis_structure`,
     `compute_scientific_hypothesis_evidence`,
     `compute_scientific_hypothesis_test_activity`,
     `compute_scientific_hypothesis_revisions`,
     `compute_scientific_hypothesis_provenance`, and
     `compute_scientific_hypothesis_prediction_outcomes`.
   - Each returns one `MetricDocument`; an absent analysis returns an
     `unavailable` document with empty values.
   - `prediction_outcomes` reports matched/mismatched/inconclusive counts and
     share milli only; `unexpected` is counted separately and is always also a
     mismatch.
3. In `src/analysis/metric_service.py`:
   - Add `scientific_hypotheses_analysis: ScientificHypothesesAnalysis | None =
     None` to `MetricComputationInputs`.
   - Add a guarded block after the economic-cascade block: when the input is not
     `None`, call the six compute functions and append the documents; log
     `scientific_hypotheses_metrics_emitted families=6 catalog=250`.
   - Do not emit any document when the input is `None`.
4. In `src/experiments/collectors.py`, add the science gate and injection after
   the cascade block. The builder is created in Task 9; in this task wire the
   gate to `replace(inputs, scientific_hypotheses_analysis=...)` with a lazy
   import and a WARN on failure.
5. Export the public metric symbols from `src/analysis/__init__.py`.

### Required Interfaces and Contracts
- Six families append exactly at positions 244-249; the first 244 are unchanged.
- Every family reports its own descriptive counts; no cross-family composite.
- `unexpected` is a mismatch and never treated as success.
- Availability is `insufficient_samples` below 3 hypotheses/trials, not zero.
- No value key contains `score`, `accuracy`, `calibration`, `truth`, `verified`,
  `proven`, `law`, or `rule`.

### Requirement Evidence
- Original Request representation list and "Hypotheses can be wrong".
- `src/analysis/specifications.py:53,318-325,9199-9251,10682-10689`.
- `src/analysis/metric_service.py:449,2831-2883`.
- `.ai-factory/ARCHITECTURE.md` catalog/append discipline.

### Error Handling and Logging
- INFO `scientific_hypotheses_metrics_emitted families=6 catalog=250`.
- WARN `scientific_hypotheses_metrics_failed family=<token>` with a code only.
- Never log values, counts tied to owners, claims, or conditions.

### Tests
- `tests/unit/test_scientific_hypotheses_catalog.py`: count 250; first-244
  digest equals the V4-26 append digest; `specs[-6:]` equals the six new ids in
  order; no composite score; each family's value keys exactly match the locked
  tuples.
- `tests/unit/test_scientific_hypotheses_metrics.py`: six documents with
  analysis; `unavailable` without; per-family values; `insufficient_samples`;
  unexpected counted as mismatch; no score-like key.
- `tests/unit/test_scientific_hypotheses_metric_service.py`: injected analysis
  emits six documents; absent analysis emits none; a compute failure is logged
  and re-raised.

### Acceptance Criteria
- Catalog is exactly 250 with the first 244 unchanged.
- Six families are emitted only with science analysis.
- No family is a truth, accuracy, calibration, or composite score.

### Verification
- `uv run pytest tests/unit/test_scientific_hypotheses_catalog.py tests/unit/test_scientific_hypotheses_metrics.py tests/unit/test_scientific_hypotheses_metric_service.py -q`
- Expected result: pass; existing repository-wide `244` pins remain
  expected-red until Task 18, and that state is recorded in the verification
  receipt rather than hidden.

## Phase Risks and Mitigations
- Risk: test selection reads objective laws to choose an experiment.
  Mitigation: selection uses only observed conditions and the owner ledger; a
  source scan rejects `world._experiment_laws` and `world._rules`.
- Risk: a communicated claim is treated as evidence.
  Mitigation: adoption creates zero support/counter and copies no event ids.
- Risk: `ExperimentResolved` rule payload leaks into analysis.
  Mitigation: the harvest copies an explicit five-field allowlist and tests
  reject `delta`, `product_id`, `harm_band`, and health fields.
- Risk: metric values encode a scientific score.
  Mitigation: closed key tuples contain no score/accuracy/calibration key.

## Phase Completion Checklist
- Intentional tests and communicated adoption work without new wire surfaces.
- The analysis composes all requested fields with no objective rule payload.
- Six families append at 244-249 and the service emits them only on evidence.
- No command, event, write pair, runner schema, or migration was added.
- `index.md` Tasks 5-8 checkboxes are updated after verification.
