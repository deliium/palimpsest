# Implementation Plan: Communication Strategy

Branch: main
Created: 2026-09-29

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone. This plan adds an opt-in communication-strategy mode under that V2 program and does not claim the still-unowned `multi_hop_testimony_tracking` flag.

## Compatibility contract

This plan lets a speaker choose how to render one claim. The choice is computed for that utterance from goals, the relationship toward the listener, theory of mind when a model is already present, expected consequences already on the selected future, the self-model, and emotional state when it is already appraised. Norms are an unused input. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only mutation authority. Strategy selection reads the owner's honest communication candidate, `GoalBoard`, directed profile toward the recipient, optional `TheoryOfMind`, optional selected-future risk kinds, `SelfModel`, and optional non-passthrough `AgentEmotionalState`. It never receives `WorldState`, `PhysicalRules`, `AgentBody`, `WorldEvent`, an event repository, replay, analysis labels, or another agent's runtime, goals, drives, beliefs, emotion, relationships, memories, or mind model.
2. Do not own a capability flag. Do not add a `V2CapabilityFlags` field. Do not add `strategic_communication` or any new flag name. `multi_hop_testimony_tracking` stays unimplemented and still fails closed with `capability_unimplemented`. Owned flags stay owned. Off for this feature is `CommunicationStrategyMode.DISABLED`, which does not change commands or audits.
3. V1 regression gate stays green under flags-off, strategy-disabled, and tracing-off. Catalog A–E and the reference scenario keep their current `exact_trajectory_hash` values. Experiments N, O, and P are additive and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. Schema bump only for the enabled mode. Default write stays `runner-config-v4`. Add `runner-config-v9` to the accepted set. `runner-config-v9` carries every `runner-config-v8` cognition key plus `communication_strategy_mode`. Emit v9 only when that mode is `DETERMINISTIC`. Reject v9 when the mode is `DISABLED`, and reject `DETERMINISTIC` on v1–v8. Add v9 to the consolidation, reflection, and prospective schema allowlists. A non-disabled counterfactual mode is accepted on v8 or v9. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. No policy weights in runner JSON. Leave `v1_regression_profile` unchanged: it checks flags and tracing, and catalog A–E stay on v4 with this mode `DISABLED`.
5. No scripted emergence. No friend, enemy, leader, trader, liar, honesty, or culture label. No new `AgentCommand`, `ActionDirection`, or `CommunicationSourceBasis`.
6. No LLM path. There is no provider schema and no prompt package. `DETERMINISTIC` never calls `LLMProvider`.
7. Experiments stay reproducible. Paired arms share seed, scenario, and stochastic identity. No RNG and no wall clock in strategy selection.
8. Optional cognition tracing stays outside the objective fold. Do not insert a `ComponentKind` or an ordinal in `_STAGE_ORDER`. Do not bump `COGNITION_TRACE_SUMMARY_SCHEMA`, add trace enum members, or add an Alembic revision. Do not copy strategy, stance, or epistemic category onto the trace summary. Tracing on versus off must not change `exact_trajectory_hash` when the mode is `DISABLED`.

## Goal

Extend Talk, Ask, and Tell past honest transmission. For one utterance, a speaker may use exactly one closed strategy:

| Strategy | What the listener can receive |
| --- | --- |
| `truthful` | Atoms and sender confidence match the speaker's selected source |
| `uncertain` | Same atoms, asked or marked with predicate `uncertain` |
| `refusal` | A `decline` utterance that does not copy the source atoms |
| `omission` | No delivery of that claim |
| `selective_disclosure` | Exactly one source atom, with the rest dropped |
| `exaggeration` | Same atoms, sender confidence raised to `1.0` |
| `deliberate_false_statement` | One object token replaced by another token the speaker already holds |

The strategy is not a character trait. Nothing on `Agent`, `SelfModel`, `IdentityState`, `IdentityAspect`, `Goal`, or `DirectedRelationshipProfile` stores liar, honesty, deceit, or a deception propensity.

Three categories name why a received statement can fail to match the world. They are not strategies and they are not visible to the listener:

| Category | When analysis assigns it |
| --- | --- |
| `memory_error` | Stance is `assert_match`, a `cited_event_id` names a committed occurrence, and the source tokens are not a subset of that occurrence's public tokens. The speaker did not choose a divergent render. |
| `uncertain_inference` | Strategy is `uncertain`. Later objective truth does not change this label. |
| `deliberate_deception` | Strategy is `deliberate_false_statement`, `exaggeration`, or `selective_disclosure`. A lie that happens to match the world stays in this category. |

`refusal` and `omission` are withholding. Their analysis category is `not_asserted`, not one of the three above.

A receiver cannot read the category off the utterance, the observation, or their new memory trace. Two statements with the same rendered atoms can be a memory error or a deliberate false statement. Only the speaker's hidden audit separates them.

## Design Decisions (locked)

- **Intent is not dialogue.** `CommunicationIntent` is the structured choice. `StructuredUtterance` on `Talk`, `Ask`, or `Tell` is the render. The intent records strategy, stance, factor codes, source kind, source confidence band, source atom tokens, `cited_event_id`, divergence code, recipient id, and tick. The utterance does not carry those fields. `select` returns a `SocialMessageSelection` with `command: Talk | Ask | Tell | None` and `intent: CommunicationIntent | None`. The world receives only the command. Omission keeps the intent (`delivered=False`) and the planner emits `Wait`.
- **Honest source atoms.** Take atoms from the winning belief, reconstruction, or communicated trace before the fallback hello. The hello path is `text` only, `source_basis=unreferenced`, confidence `1.0`, and no concepts. An empty atom list stays `truthful`. Rules 5–7 do not fire. `cited_event_id` is copied only from that trace's existing `observed_source_id`. A belief or reconstruction with no such id stores `None`.
- **Disabled mode is today's selector, with one skip.** `CommunicationStrategyMode.DISABLED` calls the current path and returns `intent=None`. It does not build an audit. Do not construct the emotion `ask` or `talk` utterances that pass `CommunicationSourceBasis.DIRECT_OBSERVATION`; that value is not on the enum and raises inside `origin_utterance`. Enabled mode builds the structured candidate, then `apply_communication_strategy` may replace the utterance or leave the command unset.
- **Stance is what the speaker did to their own record.** Closed `SpeakerStance`: `assert_match`, `hedge`, `withhold`, `refuse`, `diverge`. Cognition does not store `memory_error`. The speaker does not know that a reconstruction is false. Analysis assigns `memory_error` only when `cited_event_id` names a committed occurrence whose public tokens do not cover the source tokens.
- **Hidden research metadata.** `CommunicationIntentAudit` is in-run and analysis-only, following `MindAudit` on `SimulationRunnerResult`: in-memory field, default empty, omitted from runner-result serialization. It is the only object that carries strategy, stance, divergence, source atoms, and `cited_event_id` together. It is not copied onto `StructuredUtterance`, `DeclaredTransmission`, `ObservedCommunication`, `CommunicationEnvelope`, `MemoryTrace`, `CommunicatedTransmissionMeta`, semantic beliefs, relationship revisions, the cognition-trace summary, or logs.
- **Receiver path stays evidence-based.** `evaluate_communicated_testimony` and trust updates do not grow a strategy or category argument. A deliberate false statement does not itself lower trust. Trust still moves only on the existing corroboration or contradiction path.
- **No global score.** There is no honesty weight, deceit weight, or per-agent bias that persists across ticks. Each call reads this tick's inputs. Missing inputs are reason codes, not defaults that create a lie.
- **Norms are a closed gap.** `apply_communication_strategy(..., norms: object | None = None)`. `None` logs `norms_unavailable` and selection continues. A non-`None` value is rejected with `norms_unimplemented` and the call fails closed to the honest candidate with strategy `truthful` only if the candidate exists; it does not interpret the object. This plan does not add a norm catalog.
- **Other modes stay independent.** Strategy `DETERMINISTIC` does not enable `advanced_social_inference`, `short_term_emotional_state`, `extended_self_model`, prospective imagination, or counterfactual mode. `None` theory of mind, passthrough emotion, and `SelfModel.identity is None` are valid inputs. Missing theory of mind is `tom_absent`. Passthrough emotion (driver code `passthrough`) is `emotion_absent`. Identity is not read as honesty. `SelfModel` contributes only when one focused goal id is already on `SelfModel.goal_ids` (`self_model_goal`). `self_model_absent` when there is no such overlap.
- **Factor codes.** Closed set, any number may be recorded, none is a trait: `goal_preserve_life`, `goal_other`, `relationship_missing`, `fear_high`, `resentment_high`, `trust_low`, `tom_absent`, `tom_attack`, `tom_anger`, `risk_physical_harm`, `risk_social_cost`, `risk_absent`, `self_model_goal`, `self_model_absent`, `emotion_absent`, `emotion_anger`, `epistemic_secret`, `epistemic_uncertain`, `low_confidence`, `alternate_token`, `no_alternate_token`, `norms_unavailable`.
- **Thresholds on `CommunicationStrategyPolicy`.** Version `communication-strategy.v1`. Relationship high `0.4`. Low source confidence `0.55`. Emotion intensity `0.4`. Quantize with the existing `_EFFECT_QUANTUM = 1e-6`. No new quantum. Thresholds are not runner JSON keys.
- **First matching rule wins.** Secret and uncertainty are judged with the existing epistemic judgments when a ledger is present. Missing ledger does not invent `secret`.

  1. No eligible recipient: return no command and no intent. Existing `no_eligible_recipient` and `Wait` behavior stays. A hello fallback with an empty atom list is still a candidate: strategy `truthful`, and rules 5–7 do not fire.
  2. `epistemic_secret` and (`fear_high` or `tom_attack` or `goal_preserve_life` or `risk_physical_harm`): strategy `refusal`, stance `refuse`, divergence `refused`. Render `Talk` with exactly one relation predicate `decline` and no source object or concept. `source_basis` stays the candidate's existing basis. Sender confidence stays the source confidence.
  3. `epistemic_secret` otherwise: strategy `omission`, stance `withhold`, divergence `withheld`, `delivered=False`. `command` is `None`. The planner emits `Wait`. The intent and audit still record the withheld source atoms.
  4. `low_confidence` or `epistemic_uncertain`: strategy `uncertain`, stance `hedge`, divergence `none`. Render `Ask` with the source atoms unchanged and sender confidence equal to the source. Predicate may be `uncertain` only when the candidate was already a `Tell` and the action kind must stay `ask` by switching the command to `Ask`. Do not put the word "uncertain" in `CommunicationContent.text`.
  5. (`risk_physical_harm` or `fear_high` or `tom_attack` or (`resentment_high` and `emotion_anger`)) and `alternate_token` and not `relationship_missing` unless a risk or tom pressure is present: strategy `deliberate_false_statement`, stance `diverge`, divergence `atom_substituted`. Replace exactly one object token with the alternate. Confidence stays the source confidence.
  6. (`resentment_high` or `emotion_anger`) and `no_alternate_token` and source confidence `< 1`: strategy `exaggeration`, stance `diverge`, divergence `confidence_inflated`. Atoms unchanged. Sender confidence is `1.0`.
  7. `trust_low` and the candidate has more than one source atom and `relationship_missing` is false: strategy `selective_disclosure`, stance `diverge`, divergence `atoms_dropped`. Copy the single allowlisted atom of highest source confidence. If none is allowlisted, copy the first atom only.
  8. Otherwise: strategy `truthful`, stance `assert_match`, divergence `none`. Atoms and confidence match the candidate.

- **Alternate token.** An alternate is a location id or concept token already on the owner's observation or on the candidate's own other atoms, and it is not the token being replaced. Allowlisted concept tokens remain `food`, `water`, `rest`, `danger`. Never invent an id. No alternate yields `no_alternate_token` and rule 5 does not fire.
- **Pressure without a profile.** `relationship_missing` blocks resentment, fear, and trust rules. It does not block `risk_physical_harm` or `tom_attack`. A stranger with no profile and no risk and no mind model cannot take rules 5–7.
- **Source basis.** Use only existing `CommunicationSourceBasis` values (`belief`, `reconstructed_memory`, `goal`, `relationship`, `unreferenced`). Do not pass `direct_observation`. Do not add an enum member. Do not bump `communication.v1`.
- **Declared lineage stays testimony.** A deliberate substitution does not add a field that says the lineage is false. `origin_utterance` / `retell_utterance` rules are unchanged. `hop_count > 1` stays dropped. This plan does not implement multi-hop tracking.
- **Expected consequences.** Read `ImaginedFuture.risks` on the future `CommandPlanner.plan` already resolves. Do not run a second search and do not call another agent's planner. No selected future yields `risk_absent`.
- **Goals.** Pass `goal_board` into `CommandPlanner.plan` and stop discarding it. A focused `current_intention` whose outcome is `preserve_life` records `goal_preserve_life`. Any other focus records `goal_other`. `gather_information` and `relate_to_agent` do not select a false statement by themselves.
- **Relationships.** After the recipient is chosen, read only the owner's `DirectedRelationshipProfile` toward that recipient from `loop_input.snapshot.relationships`. `fear >= 0.4` is `fear_high`. `resentment >= 0.4` is `resentment_high`. `trust < 0.5` is `trust_low`. Missing profile is `relationship_missing`, not trust zero.
- **Theory of mind.** When a model is present, an above-threshold hypothesis (`action_threshold` already on `TheoryOfMindPolicy`, default `0.55`) about the recipient supplies `tom_attack` for `FUTURE_ACTION` `attack` toward the owner and `tom_anger` for `EMOTION` `anger`. Do not read hypotheses about anyone except the recipient. Do not call `update_theory_of_mind` from the strategy module.
- **Emotion.** When the evaluation is present and its driver is not `passthrough`, anger intensity `>= 0.4` records `emotion_anger`. Any other kind records no deception pressure.
- **Identity.** Do not read `IdentityAspect` values `reliability`, `commitment`, or `risk_tolerance`. Do not add an aspect.
- **Ids.** Intent id is sha256 of owner, recipient, tick, strategy, and canonical source atom key. No RNG, wall clock, or Python `hash()`.
- **Caps.** At most 8 source atom tokens and 8 factor codes. Drop extras with reason `cap_exceeded` rather than concatenating prose.
- **Analysis labels.** `communication_strategy@1` in `src/analysis/communication_strategy_metrics.py` takes `Sequence[object]` audits and `Sequence[WorldEvent]` events. It uses `getattr` the way `theory_of_mind@1` does. It must not import `agents`, `apply_communication_strategy`, or `choose_communication_strategy`.
  - Stance `hedge` → `uncertain_inference`.
  - Strategy in `deliberate_false_statement`, `exaggeration`, `selective_disclosure` → `deliberate_deception`.
  - Stance `assert_match` with `cited_event_id` set, event found, and source tokens a subset of that event's public tokens → `veridical`. Public tokens are the utterance concept list on `Talked`, `Asked`, or `Told`. On any other occurrence they are the occurrence kind plus actor, other, and destination ids.
  - Stance `assert_match` with `cited_event_id` set, event found, and source tokens not a subset → `memory_error`.
  - Stance `assert_match` with `cited_event_id` missing, or with no matching event → `unmatched`. Do not invent a rate.
  - Stance `refuse` or `withhold` → `not_asserted`.
  - Cascade count: later assertions by a different owner whose rendered atoms equal an earlier `atom_substituted` render and whose own stance is `assert_match`. Those later speakers do not carry the origin audit.
  - Trust series: the metric does not update relationships. A separate test shows the receiver's trust dimension is unchanged after an uncontradicted false statement.
- **Fail closed.** Unknown strategy strings, owner mismatches, empty renders for `refusal` that still contain a source object, non-finite confidence, and `norms` other than `None` abort or fall back with stable reason codes. A bad input is not repaired from the world.

## Non-Goals

- Owning `multi_hop_testimony_tracking`, or keeping utterances whose `hop_count` is greater than 1
- A persisted liar, honesty, or deception-propensity trait
- A norm catalog, reputation, or sanction system
- Teaching the receiver to classify `memory_error`, `uncertain_inference`, or `deliberate_deception`
- Adding an `AgentCommand`, an `ActionDirection`, a `CommunicationSourceBasis`, a `V2CapabilityFlags` field, or a runner field for policy weights
- Inserting a `CognitiveLoop` ordinal, bumping the cognition-trace schema, or adding an Alembic revision
- Copying intent onto events, observations, envelopes, or listener memory
- Enabling theory of mind, emotion, identity, prospective, or counterfactual behavior as a side effect
- An LLM selector or free-form dialogue text
- Fixing the existing emotion-path `direct_observation` source basis, except by not using that value in the new renderer
- Feeding metric labels back into live planning
- Putting Experiments N, O, or P on the V1 regression gate

## Commit Plan
- **Commit 1** (after tasks 1–3): `feat(cognition): add per-utterance communication strategy`
- **Commit 2** (after tasks 4–5): `feat(cognition): keep deception metadata off the receiver`
- **Commit 3** (after tasks 6–8): `test(experiments): classify trust, deception, and cascades`
- **Commit 4** (after tasks 9–10): `docs(cognition): document communication strategy`

## Tasks

### Phase 1: Contracts and Mode

- [x] Task 1: Add communication-intent contracts and `CommunicationStrategyPolicy`.
  - Deliverable: frozen types in `src/agents/cognition/communication_strategy.py`, exported from `src/agents/cognition/__init__.py`.
  - Types: `CommunicationStrategy` (`truthful`, `uncertain`, `refusal`, `omission`, `selective_disclosure`, `exaggeration`, `deliberate_false_statement`), `SpeakerStance` (`assert_match`, `hedge`, `withhold`, `refuse`, `diverge`), `CommunicationDivergence` (`none`, `confidence_inflated`, `atom_substituted`, `atoms_dropped`, `withheld`, `refused`), `CommunicationFactor` (the factor codes in Design Decisions), `CommunicationIntent` (intent id, owner id, recipient id, tick, strategy, stance, divergence, source basis, source confidence band, source atom tokens, `cited_event_id`, factor codes, delivered), `CommunicationIntentAudit` (the same research fields, plus `fallback_used`), `CommunicationStrategyPolicy` (`communication-strategy.v1`, relationship high `0.4`, low confidence `0.55`, emotion intensity `0.4`), `CognitionCommunicationStrategyMode` (`DISABLED`, `DETERMINISTIC`) in `src/agents/cognition/configuration.py` and the matching runner enum in `src/simulation/runner_models.py`.
  - `cited_event_id` is optional. Callers copy it only from a memory trace's existing `observed_source_id`. Leave it `None` when that id is absent. Do not look up an event store to fill it.
  - No field named liar, honesty, deceit, or deception propensity exists on these types or on `SelfModel`.
  - Intent id is sha256 of owner, recipient, tick, strategy, and canonical source atom key. No RNG, wall clock, or Python `hash()`.
  - Constructors reject unknown enums, non-finite confidence, empty refusal renders that still include a source token, and more than 8 atoms or factor codes, with stable reason codes.
  - Logging: logger `agents.cognition.communication_strategy`. DEBUG on construction with owner id, policy version, and strategy value. ERROR with field name and reason code on validation failure. No atom tokens, utterance text, or another agent's drive values.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Files: `src/agents/cognition/communication_strategy.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/__init__.py`, `src/simulation/runner_models.py`, `tests/unit/test_communication_strategy.py`.

- [x] Task 2: Wire `DETERMINISTIC` through `runner-config-v9` without owning a new flag.
  - Deliverable: mode off keeps `runner-config-v4` and today's commands. Mode on is accepted only as `runner-config-v9`. `multi_hop_testimony_tracking` still fails closed. A v9 config can still carry the earlier cognition modes.
  - Add `communication_strategy_mode` to `AgentCognitionSpec` in `src/simulation/runner_models.py` and to `CognitionLoopConfig` in `src/agents/cognition/configuration.py`. Default both to `DISABLED`. Accept v9 in the version set. v9 cognition keys are the v8 key set plus `communication_strategy_mode`. Reject v9 when every agent's mode is `DISABLED`. Reject `DETERMINISTIC` on v1–v8. Add v9 to the consolidation, reflection, and prospective schema allowlists in `src/simulation/runner_models.py` and `src/simulation/runner_serialization.py`. Accept a non-disabled counterfactual mode when the schema is v8 or v9. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. Do not add a `V2CapabilityFlags` field. `simulation.runner._cognition_config_for` sets `CognitionCommunicationStrategyMode.DETERMINISTIC` only from that field, and builds `default_communication_strategy_policy()`. Update `src/simulation/compatibility.py` with the same accepted-set note.
  - Update runner model, serialization, construction, and `tests/unit/test_cognition_configuration.py` so an enabled `multi_hop_testimony_tracking` still returns `capability_unimplemented`, a disabled strategy mode does not bump the written schema, and a v9 document round-trips with counterfactual, prospective, reflection, and consolidation keys present. Run `uv run ruff check` on `tests/unit/test_cognition_configuration.py` and every other file whose signature grew.
  - Logging: DEBUG `cognition_config_communication_strategy_mode mode=%s policy_version=%s` on logger `simulation.runner`. Do not log policy thresholds. ERROR on schema rejection uses the existing stable runner codes.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 1.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/runner.py`, `src/simulation/__init__.py`, `src/agents/cognition/configuration.py`, `tests/unit/test_runner_models.py`, `tests/unit/test_runner_serialization.py`, `tests/unit/test_simulation_runner_construction.py`, `tests/unit/test_v2_flag_defaults.py`, `tests/unit/test_cognition_configuration.py`.

### Phase 2: Choice and Render

- [x] Task 3: Implement deterministic choice and render.
  - Deliverable: `choose_communication_strategy(...)` returns one `CommunicationIntent`. `render_communication_intent(...)` returns either one `Talk`, `Ask`, or `Tell`, or `None` for omission. The utterance contains no strategy, stance, category, or provenance field.
  - The caller passes source atoms taken from the winning belief, reconstruction, or communicated trace. An empty atom list returns strategy `truthful` and does not apply rules 5–7. Apply the first-match table, alternate-token rule, missing-profile rule, caps, and source-basis rule in Design Decisions. Quantize confidence with `_EFFECT_QUANTUM`. `norms is None` records `norms_unavailable`. A non-`None` `norms` returns the honest candidate, sets `fallback_used`, and uses reason `norms_unimplemented`. `cited_event_id` is the optional id the caller already copied from `observed_source_id`.
  - The function parameter for the world view is the existing observation type already accepted by `DeterministicSocialMessagePolicy`. Passing `WorldState`, `PhysicalRules`, or `AgentBody` raises `TypeError`. The module must not import `analysis`, `simulation`, `world.models`, `world.events`, or `world._state`. It may import `world.communications`, `world.actions`, and `world.observations`.
  - Logging: DEBUG `communication_strategy_chosen` with owner id, tick, recipient id, strategy, stance, divergence, factor codes, and confidence band. INFO once per non-`truthful` choice with strategy and stance only. WARNING on fallback or `cap_exceeded` with reason code and no atoms. ERROR on owner mismatch. No utterance text and no source tokens.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 1.
  - Files: `src/agents/cognition/communication_strategy.py`, `tests/unit/test_communication_strategy.py`.

- [x] Task 4: Apply the strategy only when the mode is `DETERMINISTIC`.
  - Deliverable: disabled runs keep today's command and `intent is None`. Enabled runs build a structured candidate, then replace the utterance or leave the command unset. The world receives only `selection.command`. Omission still yields an intent.
  - Change `SocialMessagePolicy.select` and `DeterministicSocialMessagePolicy.select` to return `SocialMessageSelection` (`command: Talk | Ask | Tell | None`, `intent: CommunicationIntent | None`). Reuse the existing `emotional_state` and `mind` parameters. Add keyword-only `strategy_mode` defaulting to `DISABLED`, `goal_board`, `relationships`, `risks`, `self_model`, and `norms`. Do not add a second emotion or mind argument, and do not pass a precomputed epistemic judgment. `DISABLED` does not call `choose_communication_strategy`.
  - Source atoms come from the winning belief, reconstruction concepts, or communicated-trace concepts, before the hello fallback. Copy `cited_event_id` only from that trace's `observed_source_id`. An empty atom list becomes `truthful`. Skip the `act_pref == "ask"` and `act_pref == "talk"` branches that pass `DIRECT_OBSERVATION`. Call `epistemic_disclosure` inside `select` for the chosen proposition. A `None` model or empty ledger records no `epistemic_secret`.
  - In `CommandPlanner.plan`, stop discarding `goal_board`. Pass it, `loop_input.snapshot.relationships`, `self_state`, and `future.risks` from the future `_resolve_future` already returns. After the recipient is chosen, use the profile aimed at that recipient. Omission sets `command` to `None`. The planner then emits `Wait` and still keeps the intent.
  - Add `communication_intent: CommunicationIntent | None = None` on `CognitiveLoopProposal` and `CognitiveLoopResult`. The loop copies `selection.intent` onto the proposal. `__repr__` of the selection includes strategy value and confidence band, never text or atoms.
  - Thread the new optional arguments through `src/agents/cognition/contracts.py`, `tests/fakes/cognition.py`, and every test stub whose `select` or `plan` signature grew. Run `uv run ruff check` on each of those files.
  - Logging: DEBUG `communication_strategy_message` with owner id, tick, mode, action kind or `wait`, recipient id, strategy or `none`, and `intent_present`. WARNING `communication_strategy_skipped` with reason `mode_disabled` or `no_candidate`. Logger `agents.cognition.communication`. No utterance text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on tasks 2 and 3.
  - Files: `src/agents/cognition/communication.py`, `src/agents/cognition/communication_strategy.py`, `src/agents/cognition/deliberation.py`, `src/agents/cognition/loop.py`, `src/agents/cognition/models.py`, `src/agents/cognition/contracts.py`, `tests/fakes/cognition.py`, `tests/unit/test_communication_strategy.py`.

### Phase 3: Hidden Metadata

- [x] Task 5: Store the audit on the runner result and keep it off every agent-facing channel.
  - Deliverable: enabled ticks append one `CommunicationIntentAudit` per intent, including omissions that were not delivered. Disabled ticks append nothing. The listener's next observation and new `MemoryTrace` are unchanged in schema.
  - Follow `export_world_model_audits`. The runtime copies `CognitiveLoopProposal.communication_intent` into one `CommunicationIntentAudit` after a successful finalize, including omissions whose command was `Wait` and whose `delivered` is `False`. Abort drops the tentative proposal and appends nothing. Disabled ticks leave the field `None` and append nothing. `SimulationRunnerResult` gains `communication_intent_audits` defaulting to an empty tuple. Runner-result serialization omits the field. Checkpoint code does not gain a version bump and does not store the audit in `subjective-v1`. The audit's `cited_event_id` is the intent's id, still optional.
  - Assert in tests that `StructuredUtterance`, `DeclaredTransmission`, `ObservedCommunication`, `CommunicationEnvelope`, and `MemoryTrace` field sets do not include `strategy`, `stance`, `memory_error`, `uncertain_inference`, or `deliberate_deception`. `evaluate_communicated_testimony` keeps its current signature.
  - Projection onto `project_cognition_trace_stages` is forbidden for these fields. Planned-action `selection_codes` stay as they are today.
  - Logging: DEBUG `communication_intent_audit_committed` / `communication_intent_audit_skipped` with owner id, tick, `audit_present`, and strategy. Logger `simulation.agent_runtime`. DEBUG `communication_intent_audit_export` with run id and audit count on logger `simulation.runner`. No source atoms.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 4.
  - Files: `src/simulation/agent_runtime.py`, `src/simulation/runner.py`, `src/simulation/runner_models.py`, `src/agents/cognition/trace.py`, `tests/unit/test_communication_strategy.py`, `tests/unit/test_communication_strategy_runtime.py`.

### Phase 4: Experiments

- [x] Task 6: Add `communication_strategy@1`.
  - Deliverable: analysis joins audits to committed occurrences and returns category counts for `memory_error`, `uncertain_inference`, and `deliberate_deception`, plus `not_asserted`, `veridical`, and `unmatched`. It also returns a cascade count. Empty input yields `MetricAvailability.ABSENT` and does not invent a rate.
  - Register `MetricFamilyId` the same way as `theory_of_mind@1` in `src/analysis/specifications.py` and `src/analysis/__init__.py`. Duck-type audit attributes (`cited_event_id`, `stance`, `strategy`, `source_atom_tokens`, `owner_id`). Apply the support rules in Design Decisions. The module must not import `agents`. Build the proof with constructed audits and `WorldEvent` values. A missing `cited_event_id` on an `assert_match` row is `unmatched`, not `memory_error`.
  - The metric result is not an input to `CognitiveLoop`, `SocialMessagePolicy`, or relationship revision.
  - Logging: DEBUG `communication_strategy_metric` with audit count, counts per category, unmatched count, and cascade count. Logger `analysis.communication_strategy_metrics`. Do not log atom tokens or utterance text at INFO.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 5.
  - Files: `src/analysis/communication_strategy_metrics.py`, `src/analysis/specifications.py`, `src/analysis/__init__.py`, `tests/unit/test_communication_strategy_experiment.py`.

- [x] Task 7: Add Experiments N, O, and P off the V1 gate.
  - Deliverable: three catalog entries pair a disabled arm on `runner-config-v4` with an enabled arm on `runner-config-v9`. Arms in each experiment share seed, scenario, and stochastic identity. The catalog function checks that pairing and the mode field. It does not run the metric and does not require a live lie, trust change, or cascade. Register them beside Experiment M in `src/experiments/catalog.py` and export them from `src/experiments/__init__.py`. Do not add them to `tests/unit/test_v1_regression_gate.py`.
  - Experiment N `experiment-n-communication-trust`: `n-disabled` / `communication_strategy_disabled` and `n-enabled` / `communication_strategy_deterministic`.
  - Experiment O `experiment-o-deception-detection`: the same arm shape.
  - Experiment P `experiment-p-information-cascade`: the same arm shape.
  - The trust stasis, the three category labels, and the cascade count are Task 8 fixtures.
  - Logging: DEBUG `experiment_n_built`, `experiment_o_built`, and `experiment_p_built` with experiment id and condition ids. Logger `experiments.catalog`. No utterance text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 2.
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, `tests/unit/test_communication_strategy_experiment.py`.

- [ ] Task 8: Prove the three categories stay distinct and invisible to the receiver.
  - Deliverable: tests that fail if a trait field appears, if a receiver is handed a category, or if the three labels collapse into one strategy.
  - Required cases in `tests/unit/test_communication_strategy.py` and `tests/unit/test_communication_strategy_runtime.py`:
    - High-confidence reconstruction, no profile, no risk, no mind model: strategy `truthful`, stance `assert_match`. The audit's `cited_event_id` points at a constructed `WorldEvent` whose public tokens do not cover the source tokens. The metric category is `memory_error`. The same stance with `cited_event_id` left `None` is `unmatched`. The listener `MemoryTrace` has no category field.
    - Source confidence below `0.55`: strategy `uncertain`, command type `Ask`, metric category `uncertain_inference`, even when the occurrence later matches the atoms.
    - Fear `>= 0.4` or physical-harm risk, plus an alternate visible location: strategy `deliberate_false_statement`, metric category `deliberate_deception`, including when the alternate happens to be the objective location. The listener observation equals the rendered utterance only.
    - Secret judgment plus `preserve_life` focus: strategy `refusal`, category `not_asserted`, rendered predicate `decline`, source token absent from the utterance.
    - Secret judgment without fear, risk, or attack: strategy `omission`, planner command `Wait`, no `Talked`, `Asked`, or `Told` for that claim, audit `delivered=False`.
    - Resentment and anger without an alternate, source confidence below `1`: strategy `exaggeration`, atoms unchanged, sender confidence `1.0`, category `deliberate_deception`.
    - Trust below `0.5` with two atoms and no deception pressure: strategy `selective_disclosure`, one atom rendered, category `deliberate_deception`.
    - Missing relationship and no risk and no mind model: strategy stays `truthful` even if tests would otherwise set resentment on a different target.
    - `SelfModel`, `IdentityState`, and strategy module source contain no `liar`, `honesty`, or `deception_propensity`. `reliability` is not read.
    - `norms=None` records `norms_unavailable`. A non-`None` norms object does not change atoms and sets `norms_unimplemented`.
    - Mode `DISABLED`: `intent is None`, audit tuple empty, and the command matches the pre-strategy selector for the same fixture.
    - Hop count above 1 is still dropped. Enabling `multi_hop_testimony_tracking` still raises `capability_unimplemented`.
    - An uncontradicted false statement leaves the listener's trust dimension at its prior value. A later observation that contradicts it still uses the existing testimony path.
    - Hello fallback with no concepts, under `DETERMINISTIC`, is strategy `truthful`. Rules 5–7 do not fire.
    - Constructed audits for the cascade: a later owner with stance `assert_match` repeats the substituted tokens, the cascade count is at least 1, and that later audit is not the origin audit. A retell case with `hop_count > 1` stays dropped and does not increase the count.
  - Logging assertions: the DEBUG lines are exactly `communication_strategy_chosen` and `communication_intent_audit_committed`. Each line includes strategy and stance. Neither line contains utterance text or source atom tokens.
  - Depends on tasks 3, 5, 6, and 7.
  - Files: `tests/unit/test_communication_strategy.py`, `tests/unit/test_communication_strategy_runtime.py`, `tests/unit/test_communication_strategy_experiment.py`, `tests/unit/test_v1_regression_gate.py` (assert Experiments N, O, and P are absent only if the gate enumerates experiment ids), `tests/unit/test_v2_flag_defaults.py`.

### Phase 5: Documentation

- [ ] Task 9: Keep the V1 gate green when the mode is disabled.
  - Deliverable: flags-off, strategy-disabled, tracing-off catalog A–E and the reference scenario keep their current hashes. Leave `v1_regression_profile` unchanged. It checks capability flags and tracing only, so catalog A–E stay green by continuing to write `runner-config-v4` with `communication_strategy_mode` `DISABLED`. Do not add a schema rejection there. Replay of a disabled run is unchanged.
  - Logging: existing regression DEBUG lines only. Add no payload logs.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on tasks 2 and 4.
  - Files: `tests/unit/test_v1_regression_gate.py`.

- [ ] Task 10: Document intent, render, and the analysis-only categories.
  - Deliverable: readers can see that strategy is per utterance, that the three categories are analysis labels, and that another agent never receives them. Route the edits through `/aif-docs`.
  - Update `docs/social-communication.md` with the intent-versus-utterance split, the `Wait` omission path, and the leak boundary. Update the downstream checklist in `docs/architecture.md` so `runner-config-v9` carries the v8 cognition keys plus `communication_strategy_mode`, Experiments N, O, and P are named, `communication_strategy@1` assigns `memory_error` only from `cited_event_id`, and `multi_hop_testimony_tracking` is still unowned. State that `v1_regression_profile` is unchanged. Update the mode table in `docs/cognition-runtime.md` and the schema paragraph in `docs/simulation-runner.md`. State that no capability flag was added. Update `.ai-factory/DESCRIPTION.md` only where the runner-schema sentence would otherwise stay stale.
  - Logging: none in docs. Implementation touchpoints already log mode, strategy, stance, fallback, audit export, and metric counts as specified above.
  - Depends on tasks 2, 5, and 7.
  - Files: `docs/social-communication.md`, `docs/architecture.md`, `docs/cognition-runtime.md`, `docs/simulation-runner.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md` only if its runner-schema sentence would otherwise stay stale.
