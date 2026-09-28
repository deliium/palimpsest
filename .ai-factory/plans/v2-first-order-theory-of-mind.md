# Implementation Plan: First-Order Theory of Mind

Branch: main
Created: 2026-09-28

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan owns the still-unimplemented `advanced_social_inference` flag and leaves `multi_hop_testimony_tracking` unowned.

## Compatibility contract

This plan adds an owner-scoped first-order theory of mind. Each agent keeps hypotheses about other agents. A hypothesis may be wrong. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only mutation authority. An update reads the owner's `Observation`, reconstructed memories already retrieved for that owner, the owner's own directed relationship profiles, and the cue history already stored on that owner's mind model. It never receives `WorldState`, `PhysicalRules`, `AgentBody`, `WorldEvent`, an event repository, replay, analysis truth, or another agent's runtime, goals, drives, beliefs, emotion, relationships, memories, or mind model.
2. Own exactly one reserved flag. Add `advanced_social_inference` to `_V2_OWNED_CAPABILITY_FLAGS`. Default remains off. Off is a passthrough: no hypotheses, no checkpoint field value, no command bias, no audit, and the trace view stays `unavailable` / `tom_not_implemented`. `multi_hop_testimony_tracking` stays unimplemented and still fails closed with `capability_unimplemented`. Owned flags stay owned.
3. V1 regression gate stays green under flags-off and tracing-off. Catalog A–E and the reference scenario keep their current `exact_trajectory_hash` values. Experiment L is additive and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. No runner schema bump. `advanced_social_inference` is already a key on `runner-config-v3` through `v8`. Do not add policy knobs to runner JSON. Do not add `runner-config-v9`. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. Thresholds live on `TheoryOfMindPolicy`.
5. No scripted emergence. Example sentences in this plan are meanings of structured atoms copied from records the owner already holds. There is no friend, enemy, leader, trader, or culture label, and no new `AgentCommand`.
6. No LLM → world shortcuts. The provider may only choose hypothesis ids from a deterministic candidate set through `StructuredOutput`. It never emits a probability, a new atom, an `AgentCommand`, or a world mutation.
7. Experiments stay reproducible. Experiment L arms share seed, scenario, and stochastic identity. LLM tests use `FakeLLMProvider`. Analysis comparison runs after the run and is not fed back into cognition.
8. Optional cognition tracing stays outside the objective fold. Do not insert a `ComponentKind` or an ordinal in `_STAGE_ORDER`. Do not bump `COGNITION_TRACE_SUMMARY_SCHEMA`, add `CognitionTraceCountKey` or `CognitionTraceRefKind` members, or add an Alembic revision. Tracing on versus off must not change `exact_trajectory_hash` when the flag is off.

## Goal

Give each agent a private first-order theory of mind, used only when `V2CapabilityFlags.advanced_social_inference` is enabled. The agent forms hypotheses such as the ones below. Slots are copied from subjective records the agent already holds. They are not stored prose and not read from another agent's private cognition.

| Meaning | Subject | Aspect | Atoms copied from the owner's records |
| --- | --- | --- | --- |
| "Alice believes Bob is hungry." | Bob | `NEED` | `NEED_KIND=hunger`, from Bob's witnessed `eat`, or from one allowed concept token `food` on a communication Alice already received |
| "Alice believes Bob wants access to the northern storage." | Bob | `GOAL` | `OUTCOME=reach_place` plus `LOCATION` equal to `ObservedOccurrence.destination_id` on Bob's witnessed `move`, or to one visible location/exit id named by an allowed relation |
| "Alice believes Bob distrusts Carol." | Bob | `RELATIONSHIP` | `DIMENSION=trust`, `POLARITY=negative`, `TARGET` equal to Carol's id only when that id is already `other_entity_id` on a non-bystander occurrence or the object of one allowed relation |

`VisibleBody` exposes life status and coarse health only. It has no hunger, thirst, inventory, goals, or emotion. Perception must stay that way. A bystander occurrence has `actor_id` and `kind` and a null `other_entity_id`. Do not widen `_other_entity_for_role` or `_public_facts_for_role` to recover a hidden target.

The model may be incomplete, incorrect, over-applied, and biased toward salient cues and toward speakers the owner trusts. Confidence is a subjective support ratio. It is not an estimate of the other agent's true drive, goal, or next command.

Each hypothesis stores:

- subject (the other agent)
- aspect
- content atoms
- confidence
- evidence
- counter-evidence
- provenance channel
- update history

Depth is exactly one. Alice may hypothesize that Bob wants a place, needs food, believes a location is empty, intends an action, feels fear, distrusts Carol, knows a witnessed fact, or will next take an action. Alice may not hypothesize what Bob believes Alice believes. Nested mind predicates are dropped.

Learning uses only observed behavior, communication, memories, the owner's relationships, and the owner's own social-history cursor. The resulting model biases social planning, communication, cooperation, conflict avoidance, negotiation (recipient and offer choice inside the existing command set), and future simulation.

## Design Decisions (locked)

- **Separate store.** Hypotheses are not `SemanticBelief` records, not `CausalHypothesis` rows, not `DirectedRelationshipProfile` dimensions, not `Goal` rows, and not `AgentEmotionalState`. Do not emit `BeliefRevisionRequest` or `RelationshipRevisionRequest` from a mind update. The owner's profile toward Bob remains Alice's attitude. A relationship hypothesis is Alice's guess about Bob's attitude toward someone else.
- **First order only.** `MindAspect` is a closed catalog: `NEED`, `GOAL`, `BELIEF`, `INTENTION`, `EMOTION`, `RELATIONSHIP`, `KNOWLEDGE`, `FUTURE_ACTION`. A hypothesis has no child model. `BELIEF` atoms use world-fact predicates only: `at`, `has`, `empty`, `danger`. Predicates `believes`, `thinks`, `wants`, `feels`, `knows`, `intends`, `trusts`, `distrusts`, and `fears` are not valid `BELIEF` content. `trusts` / `distrusts` / `fears` map only to `RELATIONSHIP`. `wants` / `needs` map only to `GOAL` or `NEED`. `knows` maps only to `KNOWLEDGE`. `intends` maps only to `INTENTION`. `feels` maps only to `EMOTION`. Any other predicate, or a relation whose object is itself a mind predicate, is dropped with reason `nested_mind_rejected`. The subject id is never the owner.
- **Flag, not a new mode enum on the runner.** `CognitionTheoryOfMindMode` is `PASSTHROUGH` or `ENABLED`, derived in `simulation.runner._cognition_config_for` the same way as `predictive_world_model`. `PASSTHROUGH` when the flag is off. `ENABLED` when it is on. `TheoryOfMindPolicy.allow_provider` defaults to false even when the flag is on. Tests may pass a policy with `allow_provider=True` on `CognitionLoopConfig`. That boolean is not a runner JSON key.
- **Not a loop stage.** Do not add a `ComponentKind` or an ordinal in `_STAGE_ORDER`. From `CognitiveLoop.prepare`, after emotional appraisal and before `FUTURES`, call `update_theory_of_mind` only when mode is `ENABLED`. Pass the resulting `TheoryOfMind` into `imagine`, prospective scoring, motivation, intention selection, planning, and `DeterministicSocialMessagePolicy.select`. When mode is `PASSTHROUGH`, those arguments stay `None` and the existing functions keep today's behavior.
- **Commit on successful finalize.** `prepare` computes the next model and uses it for this tick's command. `AgentRuntime.finalize_pending` stores it only after a successful `resolve_tick`, same durability rule as the causal world model. Abort discards the tentative model so a retry recomputes it from the same observation. Flag off leaves the runtime field `None`.
- **Checkpoint.** Add optional `theory_of_mind` on the in-memory `AgentRuntimeCheckpoint`, default `None`. Thread it through `export_runtime_checkpoint` and `restore_runtime_checkpoint`. Do not bump a checkpoint schema and do not add an Alembic revision. The checkpoint is not a versioned JSON document. Flag off leaves the field `None`. Do not add the model to `subjective-v1`.
- **Who can be a subject.** A subject id must already appear as a `VisibleBody.entity_id`, an occurrence `actor_id` or `other_entity_id`, or a communication `speaker_id` or `listener_id` on this owner's observation or on a reconstructed memory used for this update. Drop everyone else with reason `unknown_subject`. Drop the owner with reason `self_subject`.
- **Cue channels.** Closed `MindEvidenceChannel`: `OBSERVED_BEHAVIOR`, `COMMUNICATION`, `MEMORY`, `RELATIONSHIP`, `SOCIAL_HISTORY`, `DERIVED`.
  - Behavior reads `ObservedOccurrence.kind`, `actor_id`, `other_entity_id`, `destination_id`, `success`, and `audience_role`. It does not read `public_facts` and does not parse text.
  - Communication reads `speaker_id`, `listener_id`, `action_kind`, `declared.hop_count`, and at most one `CommunicationRelation` or one concept token. It does not read or store `utterance.text`. `hop_count > 1` is dropped with reason `multi_hop_deferred`. That drop does not implement `multi_hop_testimony_tracking`.
  - Memory uses the same atom rules on reconstructions whose provenance id is not already on this observation.
  - Relationship uses the owner's `DirectedRelationshipProfile` toward the speaker only as a weight on testimony. It does not copy the owner's dimensions into the subject's hypothesized relationship.
  - Social history is the bounded cue cursor already on `TheoryOfMind` (max 32). It deduplicates provenance ids. It is not an event log and not another agent's memory.
  - `DERIVED` is used only for `FUTURE_ACTION` produced from an existing hypothesis in the same update.
- **One primary cue per occurrence.** One provenance id supports one primary aspect. `eat` → `NEED/hunger`. `drink` → `NEED/thirst`. `sleep` → `NEED/fatigue`. `flee`, or an `attack` whose `other_entity_id` is the subject → `NEED/safety` and, when the subject is the actor of `flee` or `attack`, `EMOTION` (`fear` or `anger`). `move` with a `destination_id` → `GOAL/reach_place`. `attack` or `help` whose `other_entity_id` is present → `RELATIONSHIP` toward that id. Do not also open an `INTENTION` and a `FUTURE_ACTION` from that same provenance. `INTENTION` is recorded only when the occurrence does not already match a more specific aspect above; its atom is the occurrence `kind` restricted to the existing command-kind strings. Absence of an occurrence creates nothing.
- **Communication allowlists.** Copy a concept only when the utterance has exactly one concept and that token is in `food`, `water`, `rest`, `danger`. Map `food` → `NEED/hunger`, `water` → `NEED/thirst`, `rest` → `NEED/fatigue`, `danger` → `NEED/safety`. Copy a relation only when the utterance has exactly one relation, its subject token equals the speaker id, and its object is a single token. Location and agent objects must equal an id already visible on the observation (`VisibleBody`, `ObservedLocation`, `VisibleExit.destination_id`, occurrence actor/other/destination). Closed predicates are the lists under first-order only. `empty` and `danger` as belief objects need no entity id. Anything else is dropped with reason `ambiguous_utterance` or `nested_mind_rejected`.
- **Relationship polarity.** `help` from subject to a known other, or predicate `trusts`, stores `DIMENSION=trust`, `POLARITY=positive`. `attack` from subject to a known other, or predicate `distrusts`, stores `DIMENSION=trust`, `POLARITY=negative`. Predicate `fears` stores `DIMENSION=fear`, `POLARITY=positive`. A bystander `attack` with null `other_entity_id` does not invent Carol. Reuse `RelationshipDimension` names. Do not invent a distrust dimension.
- **Knowledge.** When the subject is the occurrence actor, or the subject is a `VisibleBody` co-present with an occurrence the owner witnessed, store `KNOWLEDGE` of that occurrence `kind` plus `LOCATION` equal to the owner's `self_body.location_id` when `self_body` is present. This is a hypothesis that the subject noticed the same public event. It is not a read of the subject's memory. Omit it when several locations would apply.
- **Emotion.** Closed `EmotionKind` values already in cognition, inferred from behavior only. Subject actor `flee` → `fear`. Subject actor `attack` → `anger`. Subject is `other_entity_id` of `help` → `relief`. `VisibleBody.coarse_health` in `critical` or `injured` → `anxiety`. Do not read any `AgentEmotionalState` belonging to the subject. The owner's already-appraised emotion may multiply support only under the weight rule below. Missing emotion does not enable `short_term_emotional_state`.
- **Future action.** After primary updates, derive at most one `FUTURE_ACTION` per subject from the highest-confidence primary hypothesis at or above `action_threshold`. `NEED/hunger` → `eat`. `NEED/thirst` → `drink`. `NEED/fatigue` → `sleep`. `NEED/safety` → `flee`. `GOAL/reach_place` → `move`. `INTENTION` copies its action atom. `EMOTION/anger` → `attack`. `EMOTION/fear` → `flee`. `RELATIONSHIP` negative trust toward the owner → `attack`. Other aspects derive nothing. Provenance is `DERIVED`. Parent hypothesis id is stored on the update record, not as a nested model. Support mass is the parent's support multiplied by `future_discount` `0.5`, quantized. Recompute confidence from that mass plus prior. A derived row does not create a second parent.
- **Confidence.** Policy version `theory-of-mind-v1`. Let `prior = 1`. `confidence = support / (support + counter + prior)`, quantized with `_EFFECT_QUANTUM = 1e-6` from `src/agents/cognition/models.py` into `[0, 1]`. Do not introduce a coarser quantum.
  - Observed behavior weight `4`.
  - Testimony base weight `2`.
  - Owner trust toward the speaker, when a profile exists: trust `>= 0.5` multiplies testimony weight by `2`; trust `< 0` multiplies by `0.5`; otherwise multiply by `1`. Missing profile keeps base weight `2`.
  - Owner emotional intensity at or above the policy emotion threshold multiplies the cue weight by `2` only when an `AgentEmotionalState` is already present for the owner.
  - Derived future weight is the discounted parent mass above, not another behavior weight.
  - One witnessed `eat` yields `4/5 = 0.8`. Two later mild counters yield `4/7`, which stays above default `action_threshold` `0.55`. Three mild counters yield `0.5`, below the threshold. This is the false-hunger persistence fixture.
  - One stranger testimony (`food`) yields `2/3`, above threshold. High trust makes that testimony weight `4`, so a lie can persist through two mild counters. Distrust (`trust < 0`) yields weight `1` and confidence `0.5`, below threshold, so one distrusted claim does not move action.
- **Mild counters.** Silence and an invisible subject add no counter-mass. A mild counter of weight `1` applies only when the subject is on `visible_bodies` and is the actor of an occurrence in this tick, and that kind contradicts the hypothesis:
  - `NEED/hunger`: actor kind is not `eat`.
  - `NEED/thirst`: actor kind is not `drink`.
  - `NEED/fatigue`: actor kind is not `sleep`.
  - `GOAL/reach_place` for location L: actor `move` whose `destination_id` is present and is not L.
  - `FUTURE_ACTION` of kind K: actor kind is not K.
  - `RELATIONSHIP` negative trust toward T: subject `help` with `other_entity_id` T.
  - A tick that does not meet these conditions does not counter. Do not counter from the absence of an occurrence.
- **Match and action bias.** A hypothesis matches a candidate when its subject is the candidate's `target_entity_id` or, for a place goal, when the place id is the move destination. Among matches at or above `action_threshold`, choose the highest confidence, then aspect order `FUTURE_ACTION`, `INTENTION`, `NEED`, `GOAL`, `EMOTION`, `RELATIONSHIP`, `KNOWLEDGE`, `BELIEF`, then smaller hypothesis id. Apply one bias, magnitude equal to that confidence. Do not sum several aspects from the same subject. `None` model leaves scores unchanged. Bias does not override a critical veto.
- **Social planning and cooperation.** Above-threshold `NEED` prefers `ActionDirection.HELP` toward that subject. `_compile_command` still uses the existing help path, which may emit `Give`. Above-threshold `GOAL/reach_place` prefers `ActionDirection.MOVE` toward that destination when that exit is already on the observation, and otherwise prefers `HELP` toward the subject. Do not add a direction or a storage command.
- **Conflict avoidance.** Above-threshold `FUTURE_ACTION` or `INTENTION` of `attack` toward the owner, or `EMOTION/anger` on a visible subject, prefers `ActionDirection.FLEE` and down-ranks `ATTACK`. A false anger or attack hypothesis can cause an unnecessary flee. That is required behavior, not a bug. Existing threat predicates stay in place.
- **Negotiation.** No negotiate command. When the owner is communicating and a hypothesis about the preferred subject is above threshold, `preferred_recipient_id` becomes that subject. If a third party T is the target of that subject's above-threshold negative `RELATIONSHIP`, T is removed from the front of the recipient list for this message. If the owner also has an above-threshold `NEED` for the subject, the help bias above is the offer. Utterances stay structured. A mind-informed `Ask` may copy the single allowlisted concept already stored on the hypothesis (`food`, `water`, `rest`, `danger`). `source_basis` is `UNREFERENCED` when the content comes from a mind hypothesis, so the receiver's existing testimony path does not treat it as the speaker's semantic belief. Sender confidence is the hypothesis confidence. Do not add a `CommunicationSourceBasis` value and do not bump `communication.v1`.
- **Future simulation.** `ImaginationEngine` and `prospective._score_seed` take an optional model. Matching `FUTURE_ACTION/attack` raises `SubjectiveRiskKind.PHYSICAL_HARM` on `MOVE` toward that subject by the hypothesis confidence. Matching `FUTURE_ACTION` in `help`, `give`, `talk`, `ask`, or `tell` raises belonging support for `COMMUNICATE` toward that subject. The rollout does not call the other agent's `CognitiveLoop`, planner, or stores. Prospective mode stays independent. ToM bias applies on the one-step path when prospective mode is `DISABLED`, and inside `rollout_prospective` when that mode is enabled. Enabling ToM does not enable prospective mode.
- **Caps.** `max_hypotheses` 64. When full, drop the lowest confidence, then the oldest last-update tick, then the greater id. Cap evidence ids, counter-evidence ids, and update-history entries at `max_history` 32 by dropping the oldest. Cap the social-history cursor at 32 the same way.
- **Provenance.** Evidence ids are opaque strings copied from observation provenance or `MemoryId` values already in the retrieval context. `MindUpdateRecord` stores tick, hypothesis id, support delta, counter delta, channel, and a closed reason (`SUPPORT`, `COUNTER`, `DERIVE`, `DROP`). No utterance text and no drive values from any other agent.
- **Identity.** Hypothesis id is sha256 of owner, subject, aspect, and canonical atom key, following `belief_formation` id stability. No RNG, wall clock, or Python `hash()`.
- **LLM grounding.** `allow_provider=True` calls `LLMProvider.generate` only through schema `theory_of_mind.selection.v1` and prompt package `llm/prompts/theory_of_mind/v1/`. The payload is hypothesis ids, aspect codes, atom counts, and quantized confidence bands already computed. The schema returns a subset of those ids. It has no probability field and no atom field. Unknown ids, missing provider, transport error, or schema failure keep the deterministic ranking and set `fallback_used`. `allow_provider=False` never calls the provider. Add `agents.cognition.theory_of_mind_selection -> llm` next to the existing `world_model_selection` import-linter ignore. The updater module must not import `llm`.
- **Trace view.** `CognitionTraceStageKind.THEORY_OF_MIND` already exists. When the snapshot model is `None`, keep `unavailable_stage_summary(..., reason_code=tom_not_implemented)`. When a model is present, emit `COMPLETED` using existing fields only: `candidate_count` = hypothesis count, `claim_count` = count at or above threshold, `selection_codes` = distinct aspect values, `id_refs` of kind `AGENT` for subject ids (bounded by the existing ref cap), and confidence = max hypothesis confidence. No new count keys, no atom payloads, no utterance text.
- **Audits.** `MindAudit` is in-run and analysis-only. Fields: owner, tick, mode, hypothesis count, update count, max confidence, `fallback_used`, and a bounded `snapshots` tuple. Each snapshot is hypothesis id, subject id, aspect, canonical atom tokens, channel, and quantized confidence. It does not include utterance text or evidence payloads. Attach it on `SimulationRunnerResult` the same way as `WorldModelAudit` (in-memory field, default empty, not written by runner-result serialization).
- **Objective comparison.** `analysis/theory_of_mind_metrics.py` implements `theory_of_mind@1`. It reads audit snapshots and later committed occurrences through the existing analysis event source. For a `FUTURE_ACTION` snapshot, the empirical outcome is the subject's next committed occurrence kind with that actor. `predicted_action`, `empirical_action`, and absolute error are stored when that later occurrence exists. When no later occurrence exists, set `empirical_status=unmatched` and do not guess. This module must not import `update_theory_of_mind`, and the updater must not import `analysis`. It must not read another agent's drives, goals, emotion, or beliefs. The unit tests that prove a model is false construct the hidden true code in the test and assert that cognition never received it.
- **Fail closed.** Unknown aspect or slot strings, owner mismatches, self subjects, non-finite weights, empty atom sets, nested mind content, and foreign memory ids abort with stable reason codes. A bad cue is dropped, not repaired from the world.

## Non-Goals

- Owning `multi_hop_testimony_tracking`, or keeping cues whose `hop_count` is greater than 1
- Second-order content (a hypothesis whose object is someone else's mental state)
- Reading or copying another agent's private cognition, including by widening `VisibleBody` or bystander `other_entity_id`
- Adding an `AgentCommand`, an `ActionDirection`, a `CommunicationSourceBasis`, or a runner schema version
- Inserting a `CognitiveLoop` ordinal, bumping the cognition-trace schema, or adding an Alembic revision
- Writing mind hypotheses into `SemanticBelief`, relationship revisions, the causal world model, or the self-model
- Letting LLM output become a stored confidence or a command
- Feeding empirical rates or analysis metrics back into live planning
- Putting Experiment L on the V1 regression gate
- Enabling prospective, counterfactual, identity, emotion, or world-model flags as a side effect of this flag

## Commit Plan
- **Commit 1** (after tasks 1–3): `feat(cognition): add first-order mind hypotheses`
- **Commit 2** (after tasks 4–7): `feat(cognition): let mind hypotheses bias social action`
- **Commit 3** (after tasks 8–10): `test(experiments): compare theory-of-mind predictions with later actions`
- **Commit 4** (after tasks 11–12): `docs(cognition): document first-order theory of mind`

## Tasks

### Phase 1: Contracts, Flag Ownership, and Deterministic Updates

- [x] Task 1: Add mind-hypothesis contracts and `TheoryOfMindPolicy`.
  - Deliverable: frozen types in `src/agents/cognition/theory_of_mind.py`, exported from `src/agents/cognition/__init__.py`.
  - Types: `MindAspect` (`NEED`, `GOAL`, `BELIEF`, `INTENTION`, `EMOTION`, `RELATIONSHIP`, `KNOWLEDGE`, `FUTURE_ACTION`), `MindSlot` (`NEED_KIND`, `OUTCOME`, `LOCATION`, `CONCEPT`, `CLAIM_PREDICATE`, `CLAIM_OBJECT`, `ACTION`, `EMOTION_KIND`, `DIMENSION`, `POLARITY`, `TARGET`), `MindAtom` (slot plus bounded copied value), `MindPolarity` (`POSITIVE`, `NEGATIVE`), `MindEvidenceChannel` (`OBSERVED_BEHAVIOR`, `COMMUNICATION`, `MEMORY`, `RELATIONSHIP`, `SOCIAL_HISTORY`, `DERIVED`), `MindUpdateReason` (`SUPPORT`, `COUNTER`, `DERIVE`, `DROP`), `MindUpdateRecord`, `MindHypothesis` (subject id, aspect, atoms, support, counter, confidence, evidence ids, counter-evidence ids, channel, update history), `TheoryOfMind` (owner id, hypotheses, cue cursor, last tick), `TheoryOfMindPolicy` (`theory-of-mind-v1`, prior `1`, behavior weight `4`, testimony weight `2`, trust high multiplier `2`, trust low multiplier `0.5`, emotion multiplier `2`, future discount `0.5`, action threshold `0.55`, caps above, `allow_provider=False`), `CognitionTheoryOfMindMode` (`PASSTHROUGH`, `ENABLED`) next to the other cognition modes in `src/agents/cognition/configuration.py`.
  - Hypothesis id is sha256 of owner, subject, aspect, and canonical atom key. No RNG, wall clock, or Python `hash()`.
  - Quantize confidence with `_EFFECT_QUANTUM = 1e-6`. The persistence fixture is `4/5 = 0.8` after one behavior cue and `4/7` after two mild counters, still above `0.55`.
  - Constructors reject empty atoms, duplicate slots, non-finite masses, owner mismatch, self subject, nested mind predicates, and unknown enums with stable reason codes.
  - Logging: logger `agents.cognition.theory_of_mind`. DEBUG on construction with owner id, policy version, and hypothesis count. ERROR with field name and reason code on validation failure. No atom values, utterance text, or another agent's drive values at INFO.
  - Files: `src/agents/cognition/theory_of_mind.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/__init__.py`, `tests/unit/test_theory_of_mind.py`.

- [x] Task 2: Own `advanced_social_inference` and wire passthrough versus enabled.
  - Deliverable: the flag may be enabled without `capability_unimplemented`. Off stays V1-equivalent.
  - Add the name to `_V2_OWNED_CAPABILITY_FLAGS` in `src/simulation/runner_models.py`. Update the dataclass docstring and the owned-flag note in `src/simulation/compatibility.py` so `advanced_social_inference` is listed beside `extended_self_model`, `predictive_world_model`, and `short_term_emotional_state`. In `simulation.runner._cognition_config_for`, set `CognitionTheoryOfMindMode.ENABLED` only when the flag is true, and build `default_theory_of_mind_policy(allow_provider=False)`.
  - Update `tests/unit/test_runner_models.py`, `tests/unit/test_v2_flag_defaults.py`, and `tests/unit/test_simulation_runner_construction.py` so an enabled `advanced_social_inference` is owned and `unimplemented_enabled_names()` is empty for that flag. Keep `multi_hop_testimony_tracking` unimplemented. Enabling that flag alone still fails closed. Update `tests/unit/test_identity_flag_gating.py` only where it still assumes this flag is unowned.
  - Logging: existing runner DEBUG line `cognition_config_theory_of_mind_mode flag=%s mode=%s policy_version=%s` beside the world-model mode log. Logger `simulation.runner`. Do not log policy weights.
  - Depends on task 1.
  - Files: `src/simulation/runner_models.py`, `src/simulation/compatibility.py`, `src/simulation/runner.py`, `src/agents/cognition/configuration.py`, `tests/unit/test_runner_models.py`, `tests/unit/test_v2_flag_defaults.py`, `tests/unit/test_simulation_runner_construction.py`, `tests/unit/test_identity_flag_gating.py`.

- [x] Task 3: Implement the deterministic cue updater.
  - Deliverable: `update_theory_of_mind(model, cues, policy) -> TheoryOfMind`, `cues_from_observation`, `cues_from_reconstructions`, and `derive_future_actions`.
  - Apply the aspect, allowlist, first-order, one-primary-cue, confidence, trust, mild-counter, derivation, dedup, and cap rules in Design Decisions. Recompute confidence from masses with `_EFFECT_QUANTUM`. Preserve update history order. The same provenance id does not add support twice.
  - `cues_from_observation` accepts `Observation`, owner id, the owner's relationship profiles, and the previous model cursor. Its parameter type is `Observation`. Passing `WorldState`, `PhysicalRules`, `AgentBody`, or another agent's goal board raises `TypeError`. It must not import `world.models`, `world.events`, `world._state`, `simulation`, or `analysis`. It may import `world.observations` and `world.communications`.
  - Reconstructed cues skip provenance ids already used by observation cues. Relationship profiles scale testimony weight only. `hop_count > 1` drops the cue with `multi_hop_deferred` and does not store the chain.
  - Mild counters follow the visible-actor table. Silence does not counter. A bystander attack with null `other_entity_id` does not create a Carol target.
  - Logging: DEBUG per applied update with owner id, tick, hypothesis id, aspect, channel, reason code, atom count, and quantized confidence. INFO once per call with cue count, created count, updated count, dropped count. WARNING when a cue is dropped, with reason code and no payload. ERROR on owner mismatch.
  - Depends on task 1.
  - Files: `src/agents/cognition/theory_of_mind.py`, `tests/unit/test_theory_of_mind.py`.

### Phase 2: Runtime and Social Use

- [x] Task 4: Apply the update inside `prepare` and carry the model on the runtime.
  - Deliverable: enabled agents update from the current observation before they imagine, and successful finalize persists the new model. Flag off does not change commands, boundary records, or checkpoints.
  - Add optional `theory_of_mind` defaulting to `None` on `SubjectiveSnapshot`, `Perspective`, `CognitiveLoopProposal`, and `CognitiveLoopResult`. In `CognitiveLoop.prepare`, after emotional appraisal and world-model update, and before `FUTURES`, when mode is `ENABLED`, build cues, update from the model on the loop input snapshot, derive future actions, and store the result on the proposal. Pass it as a keyword-only optional argument into imagine, motivation, intention, and planning. `PASSTHROUGH` skips the call and leaves the argument `None`.
  - Thread that optional argument through `src/agents/cognition/contracts.py`, `src/agents/cognition/defaults.py`, and `tests/fakes/cognition.py` so existing stubs keep working. Run `uv run ruff check` on every file that gained the parameter.
  - `AgentRuntime` holds the model, copies it onto the subjective snapshot, exports and restores it, and commits it only after successful resolve. Abort leaves the prior model in place. The checkpoint field lives on the in-memory `AgentRuntimeCheckpoint` and defaults to `None`.
  - Logging: DEBUG `theory_of_mind_prepare` with owner id, tick, mode, hypothesis count. DEBUG `theory_of_mind_committed` / `theory_of_mind_commit_skipped` with owner id, tick, and `theory_of_mind_present`. No hypotheses at INFO. Logger `agents.cognition.loop` for the prepare hook and `simulation.agent_runtime` for commit, matching the world-model lines.
  - Depends on tasks 2 and 3.
  - Files: `src/agents/cognition/loop.py`, `src/agents/cognition/models.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/defaults.py`, `src/simulation/agent_runtime.py`, `src/simulation/run_control.py`, `src/simulation/subjective_state.py`, `tests/fakes/cognition.py`, `tests/unit/test_theory_of_mind_runtime.py`.

- [x] Task 5: Bias cooperation, conflict avoidance, and social planning.
  - Deliverable: a passed model at or above `action_threshold` changes direction preference once per candidate. A `None` model preserves current scores and the selected command for the same fixture.
  - Extend `MultiCriteriaIntentionSelector.select` with an optional model argument defaulting to `None`. Apply the single-winner match from Design Decisions. `NEED` prefers `HELP`. `GOAL/reach_place` prefers `MOVE` only when the destination is already an exit, otherwise `HELP`. Attack, anger, or negative trust toward the owner prefers `FLEE` and down-ranks `ATTACK`. The bias runs after feasibility and does not override a critical veto. Quantize with `_EFFECT_QUANTUM`. `_compile_command` stays on the existing help and communicate compilation. Do not construct a new command type in the selector.
  - Logging: DEBUG `theory_of_mind_deliberation_bias` with owner id, tick, matched hypothesis id, aspect, quantized confidence, and direction. DEBUG when the model is `None` with `status=skipped`. No observation bodies. Logger `agents.cognition.deliberation`.
  - Depends on task 4.
  - Files: `src/agents/cognition/deliberation.py`, `src/agents/cognition/loop.py`, `tests/unit/test_theory_of_mind_runtime.py`.

- [x] Task 6: Use the model in communication and negotiation.
  - Deliverable: when a model is passed, recipient choice and one allowlisted concept follow the winning hypothesis. When the model is `None`, `DeterministicSocialMessagePolicy.select` keeps today's utterances.
  - Add keyword-only `mind: TheoryOfMind | None = None` to `SocialMessagePolicy.select` and `DeterministicSocialMessagePolicy.select`. Set `preferred_recipient_id` from the winning subject when the caller did not already pass one. Drop a third party who is the target of that subject's above-threshold negative trust hypothesis from the front of the recipient list. An `Ask` may copy `food`, `water`, `rest`, or `danger` only when that token is already an atom on the winning hypothesis. `source_basis` for that utterance is `UNREFERENCED`. Sender confidence is the hypothesis confidence. Do not read `utterance.text`, do not add a source-basis enum value, and do not emit a `Tell` of another agent's private state.
  - Logging: DEBUG `theory_of_mind_message` with owner id, tick, action kind, recipient id, aspect, concept count, confidence band, and `mind_present`. WARNING `theory_of_mind_message_skipped` with reason `no_eligible_recipient` or `status=skipped`. No utterance text. Logger `agents.cognition.communication`.
  - Depends on tasks 4 and 5.
  - Files: `src/agents/cognition/communication.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/deliberation.py`, `tests/unit/test_theory_of_mind_runtime.py`.

- [x] Task 7: Bias one-step imagination and prospective rollouts.
  - Deliverable: a hypothesized future action changes subjective risk and belonging inside both the current `imagine` path and `rollout_prospective`. The search never calls another agent's planner. A `None` model preserves current path values.
  - Extend `ImaginationEngine.imagine` and `prospective._score_seed` with an optional model argument defaulting to `None`. Matching `FUTURE_ACTION/attack` raises physical-harm risk on `MOVE` toward that subject. Matching a cooperative future action (`help`, `give`, `talk`, `ask`, `tell`) raises belonging on `COMMUNICATE` toward that subject. Magnitudes are the quantized hypothesis confidence. Thread the same optional argument through `rollout_prospective` without changing prospective budgets, seeds, or the disabled-mode one-step path's command when the model is `None`.
  - Logging: DEBUG `theory_of_mind_imagination_bias` and `theory_of_mind_prospective_bias` with owner id, tick, matched hypothesis id, action atom, quantized confidence, and direction. DEBUG when the model is `None` with `status=skipped`. Loggers `agents.cognition.imagination` and `agents.cognition.prospective`.
  - Depends on task 4.
  - Files: `src/agents/cognition/imagination.py`, `src/agents/cognition/prospective.py`, `src/agents/cognition/loop.py`, `tests/unit/test_theory_of_mind_runtime.py`.

### Phase 3: Trace, LLM, Experiment, Proofs, and Docs

- [x] Task 8: Project the existing theory-of-mind trace view when a model is present.
  - Deliverable: flags-off traces still use `tom_not_implemented`. Enabled runs with a model emit a completed summary built from existing summary fields.
  - In `project_cognition_trace_stages`, when `SubjectiveSnapshot.theory_of_mind` is `None`, keep `unavailable_stage_summary` and `TOM_UNAVAILABLE_REASON`. When it is a `TheoryOfMind`, emit `COMPLETED` with `candidate_count`, `claim_count`, aspect `selection_codes`, `AGENT` id refs for subjects, and max confidence. Do not add trace enum members or bump `COGNITION_TRACE_SUMMARY_SCHEMA`. Do not put atom values or utterance text on the summary.
  - Logging: DEBUG `theory_of_mind_trace` with owner id, status, hypothesis count, and reason code. No snapshots at INFO. Logger `agents.cognition.trace`.
  - Depends on task 4.
  - Files: `src/agents/cognition/trace.py`, `tests/unit/test_theory_of_mind_runtime.py`.

- [x] Task 9: Add optional structured LLM selection over existing hypotheses.
  - Deliverable: when `allow_provider` is true, the provider returns a subset of hypothesis ids and action bias prefers those that also pass the deterministic match and threshold. Failures fall back to confidence order and set `fallback_used`. Default policy never calls the provider.
  - Add schema `theory_of_mind.selection.v1` under the layout used by `llm/prompts/world_model/v1/`. Payload fields are ids, aspect codes, atom counts, and confidence bands. Reject responses that contain a probability, a new atom, or an unknown id. Selection lives in `src/agents/cognition/theory_of_mind_selection.py` and is the only new module that imports `llm`. Add the import-linter ignore beside `world_model_selection`.
  - Attach `MindAudit` on `SimulationRunnerResult` for enabled agents only, following `WorldModelAudit` in `src/simulation/runner.py`. Include the bounded snapshot tuple and keep the field out of runner-result serialization.
  - Logging: DEBUG `theory_of_mind_llm_selection` with owner id, tick, candidate count, selected count, `fallback_used`. WARNING on fallback with reason code (`missing_provider`, `schema_rejected`, `foreign_id`, `transport`). Do not log prompts or raw provider bodies. Logger `agents.cognition.theory_of_mind`. LLM metadata stays on the existing `llm` logger.
  - Depends on tasks 4 and 5.
  - Files: `src/agents/cognition/theory_of_mind_selection.py`, `src/agents/cognition/theory_of_mind.py`, `llm/prompts/theory_of_mind/v1/`, `pyproject.toml`, `src/simulation/runner.py`, `tests/unit/test_theory_of_mind.py`.

- [x] Task 10: Add Experiment L and the post-hoc comparison metric.
  - Deliverable: two arms share seed, scenario, and stochastic identity. `l-disabled` leaves the flag off on `runner-config-v4`. `l-enabled` sets `advanced_social_inference=True` and stays on `runner-config-v4`. The disabled arm's objective hash matches the same base config. The enabled arm may diverge after a hypothesis crosses threshold. Register it beside Experiment K in `src/experiments/catalog.py`. Do not add it to `tests/unit/test_v1_regression_gate.py`.
  - `theory_of_mind@1` in `src/analysis/theory_of_mind_metrics.py` joins `FUTURE_ACTION` audit snapshots to the subject's later committed occurrence and writes predicted action, empirical action, absolute error, and match status. No later occurrence yields `empirical_status=unmatched` and an empty rate. Register the spec the same way as `causal_world_model@1` (`src/analysis/specifications.py`, `src/analysis/__init__.py`). Do not import `update_theory_of_mind`. The metric result is not an input to `CognitiveLoop`.
  - Logging: DEBUG `experiment_l_built` with experiment id and condition ids, logger `experiments.catalog`. DEBUG `theory_of_mind_metric` with hypothesis count, matched count, unmatched count, logger `analysis.theory_of_mind_metrics`. Do not log per-hypothesis empirical actions at INFO.
  - Depends on tasks 2 and 9.
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, `src/analysis/theory_of_mind_metrics.py`, `src/analysis/specifications.py`, `src/analysis/__init__.py`, `tests/unit/test_theory_of_mind_experiment.py`.

- [x] Task 11: Prove incorrect models form, persist, and steer action without reading private minds.
  - Deliverable: tests that fail if a false hypothesis is erased by two mild counters, if a nested mind predicate is stored, if a bystander attack invents a hidden target, if hop count above 1 is kept, or if the updater can see another agent's body or goals.
  - Required cases in `tests/unit/test_theory_of_mind.py` and `tests/unit/test_theory_of_mind_runtime.py`:
    - Alice witnesses Bob `eat` once. Confidence for Bob `NEED/hunger` is `0.8`. The test fixture holds Bob's true hunger as low on an `AgentBody` that is not passed into `cues_from_observation`. Two later ticks where Bob is visible and is the actor of `wait` leave confidence at `4/7`, still above `0.55`. Alice's selected direction is `HELP` toward Bob. Three mild counters fall below the threshold and the help bias stops. Bob's hunger value is unchanged. The hypothesis object contains no `Hunger` and no `Goal`.
    - Bob tells Alice one concept token `food` with `hop_count` 0 and no owner trust profile. Confidence is `2/3` and Alice asks Bob with that concept, `source_basis=unreferenced`. The same tell with owner trust `< 0` stays at `0.5` and does not change the command. `hop_count` 2 is dropped and stores nothing.
    - Bob `move`s once to a destination id already on the occurrence. Alice stores `GOAL/reach_place` for that id. If Alice has that exit, she prefers `MOVE` there; otherwise she prefers `HELP` toward Bob. A bystander occurrence with null `other_entity_id` does not create a relationship target named Carol. A single relation `distrusts` whose object is Carol's already visible id does create `RELATIONSHIP` trust-negative toward Carol, and Carol is not chosen as the message recipient.
    - Alice hypothesizes Bob's `FUTURE_ACTION/attack` toward herself from witnessed `attack` where she is the target. She prefers `FLEE` even when Bob's next committed action in the fixture is `wait`. The analysis metric on that pair reports absolute error at least `0.5` while the stored confidence is unchanged. The updater's return value contains no empirical action.
    - A relation predicate `believes` whose object is `hungry`, and a belief atom whose predicate is `wants`, are dropped with `nested_mind_rejected`. The owner is rejected as a subject.
    - An observation with no weather and no third-party id produces neither a weather atom nor a guessed target.
    - Flag off: the runtime model stays `None`, the trace reason is `tom_not_implemented`, and the command sequence of a fixed fixture matches the passthrough loop.
    - `src/agents/cognition/theory_of_mind.py` source does not contain `WorldState`, `AgentBody`, `GoalBoard`, `AgentEmotionalState`, or `PhysicalRules`. Constructing cues from a `WorldState` or `AgentBody` raises `TypeError`.
  - Logging assertions: DEBUG records for the salient update contain aspect and reason codes and do not contain utterance text or `resulting_hunger`.
  - Depends on tasks 3, 5, 6, 7, and 10.
  - Files: `tests/unit/test_theory_of_mind.py`, `tests/unit/test_theory_of_mind_runtime.py`, `tests/unit/test_theory_of_mind_experiment.py`, `tests/unit/test_v1_regression_gate.py` (assert Experiment L is absent only if the gate enumerates experiment ids).

- [x] Task 12: Document the owned flag and the subjective/objective split.
  - Deliverable: readers can see that `advanced_social_inference` is owned and default off, that one agent does not receive another agent's private cognition, and that `theory_of_mind@1` is analysis-only. Route the edits through `/aif-docs`.
  - Update the owned-flag lists and downstream checklist examples in `docs/architecture.md`, the capability table and the ToM placeholder paragraph in `docs/cognition-runtime.md`, and the fail-closed paragraph in `docs/simulation-runner.md`. State Experiment L and `theory_of_mind@1` stay off the V1 regression gate. State that `multi_hop_testimony_tracking` is still unowned.
  - Logging: none in docs. Implementation touchpoints already log mode, update counts, bias, fallback, and metric match counts as specified above.
  - Depends on tasks 2 and 10.
  - Files: `docs/architecture.md`, `docs/cognition-runtime.md`, `docs/simulation-runner.md`, `.ai-factory/ARCHITECTURE.md` only if its owned-flag sentence would otherwise stay stale.
