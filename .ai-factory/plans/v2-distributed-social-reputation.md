# Implementation Plan: Distributed Social Reputation

Branch: main
Created: 2026-09-29

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone. This plan adds an opt-in owner-scoped reputation mode under that V2 program and does not claim the still-unowned `multi_hop_testimony_tracking` flag.

## Compatibility contract

Each agent keeps its own directed assessments of other agents. There is no world-owned reputation score, and no agent can read another agent's ledger or an analysis aggregate. The plan must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only mutation authority. The updater reads the owner's `Observation`, the owner's `MemoryTrace` values, the owner's `OwnerSafeSocialIdentity`, trust floats the caller already projected, and the owner's existing reputation ledger. It never receives `WorldState`, `PhysicalRules`, `AgentBody`, `WorldEvent`, an event repository, replay, analysis output, or another agent's runtime, goals, drives, beliefs, emotion, relationships, memories, mind model, or ledger.
2. Do not own a capability flag. Do not add a `V2CapabilityFlags` field. Do not add `distributed_reputation` or any new flag name. `multi_hop_testimony_tracking` stays unimplemented and still fails closed with `capability_unimplemented`. Owned flags stay owned. Off for this feature is `ReputationMode.DISABLED`, which does not change commands, memories, relationships, beliefs, or audits.
3. V1 regression gate stays green under flags-off, reputation-disabled, strategy-disabled, and tracing-off. Catalog A–E and the reference scenario keep their current `exact_trajectory_hash` values. Experiment Q is additive and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. Schema bump only for the enabled mode. Default write stays `runner-config-v4`. Add `runner-config-v10` to the accepted set. `runner-config-v10` carries every `runner-config-v9` cognition key plus `reputation_mode`. Emit v10 only when some agent's `ReputationMode` is `DETERMINISTIC`. Emit v9 only when communication strategy is `DETERMINISTIC` and every reputation mode is `DISABLED`. Reject v10 when every reputation mode is `DISABLED` (`v10_requires_reputation`). Reject `DETERMINISTIC` reputation on v1–v9 (`reputation_mode_requires_v10`). Widen `communication_strategy_mode_requires_v9` so a non-disabled strategy is accepted on v9 or v10. Leave `v9_requires_communication_strategy` on v9 only. Add v10 to the consolidation, reflection, prospective, and counterfactual schema allowlists. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. No policy weights in runner JSON. Leave `v1_regression_profile` unchanged.
5. No scripted emergence. No friend, enemy, leader, culture, rumor, morality, prestige, or personality label. No new `AgentCommand`, `ActionDirection`, `CommunicationSourceBasis`, or `RelationshipDimension`.
6. No LLM path. There is no provider schema and no prompt package. `DETERMINISTIC` never calls `LLMProvider`.
7. Experiments stay reproducible. Paired arms share seed, scenario, and stochastic identity. No RNG and no wall clock in reputation updates.
8. Optional cognition tracing stays outside the objective fold. Do not insert a `ComponentKind` or an ordinal in `_STAGE_ORDER`. Do not bump `COGNITION_TRACE_SUMMARY_SCHEMA`, add trace enum members, or add an Alembic revision. Do not copy dimension values, channel, source trust, or analysis readings onto the trace summary. `subjective-v1` stays unchanged. Tracing on versus off must not change `exact_trajectory_hash` when the mode is `DISABLED`.

## Goal

Reputation is a distributed social phenomenon. Every owner holds a private ledger of beliefs about other agents. Two owners can assign contradictory standing to the same target. Social clusters can diverge because they do not share evidence.

The ledger stores four independent signed dimensions, not a global score and not the colloquial labels:

| Dimension | High reading, analysis only | Low reading, analysis only |
| --- | --- | --- |
| `reliability` | trustworthy | unreliable |
| `harm` | dangerous | — |
| `generosity` | generous | — |
| `competence` | competent | — |

`trustworthy` and `unreliable` are opposite ends of `reliability`. They are not two stored axes. `dangerous`, `generous`, and `competent` are readings of `harm`, `generosity`, and `competence`. Agents never store those five words, and they never receive a combined score.

Evidence arrives through four channels. Each contribution records its channel, lineage, and the trust placed in its source at adoption time:

| Channel | What the owner actually has |
| --- | --- |
| `direct_observation` | This tick's `ObservedOccurrence` whose `actor_id` resolves to the target agent |
| `remembered_interaction` | An older `MemoryTrace` of an interaction in which the owner's body took part |
| `communication` | A delivered utterance whose relation subject resolves to the speaker |
| `third_party_story` | A delivered utterance whose relation subject resolves to some other agent |

Adoption of spoken evidence scales with the owner's directed `trust` toward the speaker. Direct observation and remembered interaction are the owner's own evidence and use a fixed scale. Analysis can later average ledgers inside a neighborhood. That average is not written back onto any agent.

## Design Decisions (locked)

- **A ledger, not a relationship and not a semantic belief.** `ReputationLedger` is owner-scoped state on `SubjectiveSnapshot.reputation`, default `None`. A profile is one `(owner, target)` head. It is not a `DirectedRelationshipProfile`, not a `SemanticBelief`, and not a `MindHypothesis`. Updates do not call `merge_relationship_revision` or `revise_semantic_belief`. `IdentityAspect.RELIABILITY` is not read or written. `DriveKind.STATUS` is not read or written.
- **Disabled mode is a passthrough.** `ReputationMode.DISABLED` leaves `snapshot.reputation` as `None`, appends no evidence, emits no reputation `Tell`, and writes no runner field. Commands match the pre-reputation planner.
- **Dimensions stay independent.** Values are signed and quantized to `1e-6`, clamped to `[-1, 1]`, using the same quantum as relationship scores. A target may be high on `generosity` and high on `harm` at once. Cognition must not sum the four dimensions into one score, weight, or rank.
- **Colloquial words are analysis readings.** `distributed_reputation@1` may emit `trustworthy`, `unreliable`, `dangerous`, `generous`, and `competent` when a neighborhood mean crosses `±0.4` on the matching dimension. Those strings exist only in the metric result. They are absent from ledger types, utterances, observations, logs at INFO, prompts, and commands.
- **Bodies and agents stay distinct.** Observations, memory entities, and relation subjects carry `EntityId` values. Ledger owner, target, and source ids are `AgentId`. Resolve with the owner's `OwnerSafeSocialIdentity` the way `DefaultMemoryUpdater` already maps a body to a counterpart. An entity with no binding yields `unresolved_entity` and no profile. Do not treat an entity id string as an agent id. `identity_divergence_scenario` already uses different strings for `body-a` and `agent-a`.
- **Direct observation uses this tick only.** From `Observation.occurrences`, accept `kind == "help"` or `kind == "give"` when `success is not False`, and `kind == "attack"` when `success is True`. Resolve `actor_id` to the reputation target. Any other kind is ignored. Those three kinds do not move `competence`. Deltas, before source scale: help → `generosity +0.25`, `reliability +0.10`, `harm -0.05`; give → `generosity +0.30`, `reliability +0.05`; attack → `harm +0.35`, `reliability -0.10`, `generosity -0.15`. Scale is `1.0`. Lineage is `provenance.source_event_id`.
- **Remembered interaction is an older trace of the owner's own participation.** A `MemoryTrace` qualifies only when `provenance.kind` is `direct_observation`, `provenance.source_tick` is strictly less than the current tick, `social_identity.owner_entity_id` equals the `e-actor` or `e-other` entity, and the `c-kind` concept written by `build_direct_observation_memory_trace` is `help`, `attack`, or `give`. The other of those two entities, resolved to an `AgentId`, is the target. Apply the same deltas at scale `0.5`, once per memory id. Skip the trace when `provenance.observed_source_id` equals an existing `direct_observation` lineage ref. Do not invent concept tokens, and do not rewrite the trace. A trace with no such token contributes nothing. `competence` stays unchanged.
- **Spoken evidence is one relation on an existing utterance.** Predicate is the dimension name (`reliability`, `harm`, `generosity`, `competence`). Subject is the target's entity id. Object is the speaker's current quantized signed value, canonical decimal text. `CommunicationContent.text` is that dimension name. `require_bounded_text` rejects an empty string. Do not write `trustworthy`, `dangerous`, `generous`, `competent`, or `unreliable` into text, concepts, or predicates. `source_basis` is `unreferenced`. Do not use `belief`: that basis is the existing path that cites a `SemanticBelief` id. `extract_evidence_candidates` may still emit an ordinary relation claim from the communicated trace. That claim is not the ledger, and the reputation module does not copy it back. Do not special-case the extractor.
- **Channel split for speech.** `hop_count > 1` is dropped and creates no contribution. This plan does not implement multi-hop tracking. For hop 0 or 1, a subject that resolves to the speaker is `communication`. A subject that resolves to neither speaker nor listener is `third_party_story`. A subject that resolves to the listener does not update a ledger. One utterance may update one target on the dimensions it names, capped at four relations.
- **Source trust scales speech only.** The caller projects trust with the existing `project_trust_inputs` for the owner's profile toward the resolved speaker and passes that float in `[0, 1]`. `reputation.py` does not import `communication.py`. Missing profile keeps today's neutral pair `(0.5, 0.2)` and reason `source_trust_missing`. Do not treat missing trust as zero. Direct observation and remembered interaction ignore that float. Speech moves the listener toward the testified value: `delta = (testified - current) * 0.5 * source_trust`. One story cannot replace the listener's head in one tick.
- **Provenance is kept on the contribution.** Each `ReputationEvidenceItem` stores target id, dimension, channel, lineage ref (event id, memory id, or communication id), source agent id (the owner for observation and memory; the speaker for speech), quantized pre-scale delta, source-trust band (`low` / `mid` / `high`, or `unmediated` for the owner's own evidence), tick, and policy version `reputation-formation.v1`. The head stores the clamped value, support mass, and contradiction mass per dimension. Positive and negative contributions both remain in the evidence tuple.
- **Dedupe and caps.** The same `(target, channel, lineage ref, dimension)` applied twice does not stack. At most 32 profiles per owner and 64 evidence items per profile. Further items are dropped with reason `cap_exceeded`. Profile id is sha256 of owner id and target id. Evidence id is sha256 of profile id, ordinal, dimension, channel, and lineage ref. No RNG, wall clock, or Python `hash()`.
- **Carry follows theory of mind.** `AgentRuntime` holds the ledger between ticks the way it holds `theory_of_mind`, including `CognitiveLoopProposal`, `CognitiveLoopResult`, and `AgentRuntimeCheckpoint` with default `None`. Export and restore copy it in `export_runtime_checkpoint` and `restore_runtime_checkpoint`. `SubjectiveMutationBatch` does not grow a reputation field. `subjective-v1` does not gain a version or a required key, and there is no Alembic revision. A disabled checkpoint stores `None`.
- **Speech replaces `Wait` only.** `ActionPlan` holds exactly one `AgentCommand`. When the mode is `DETERMINISTIC`, the selected command is `Wait`, a head has some absolute dimension value `>= 0.4`, and an eligible recipient exists who is not the target, `CommandPlanner` may replace that `Wait` with one `Tell` built with `origin_utterance` and the relation above. Any other selected command stays, with reason `command_already_selected`. This does not run inside `choose_communication_strategy`. `DISABLED` does not emit that `Tell`. Reputation does not change `Help`, `Attack`, `Give`, or `Move`.
- **No shared aggregate.** `compute_distributed_reputation` lives in `src/analysis/reputation_metrics.py`. Inputs are owner ledgers plus a caller-supplied map from owner id to neighborhood id. It returns per-neighborhood means, a disagreement magnitude per dimension for one requested target, and the reading labels. Empty input returns `MetricAvailability.ABSENT`. The function must not import `agents`. `CognitiveLoop`, `SocialMessagePolicy`, and `AgentRuntime` must not import `analysis`. The metric result is not a snapshot field.
- **Neighborhoods are start locations, not groups inside cognition.** `_validate_topology` requires a connected graph, so `east` and `west` share one symmetric edge. `_validate_weather_coverage` requires weather on both. `focal`, `east_a`, and `east_b` start in `east`. `west_a` and `west_b` start in `west`, so they are not colocated with `focal` at tick 0. Delivery still requires colocation. Divergence is proved by fixtures that feed east owners a `help` occurrence by `focal`'s entity and west owners a hop-0 `Tell` from `west_a` whose subject is `focal`'s entity id and whose `harm` object is `0.8`. The catalog builder checks arm identity only. It does not run the metric and does not require a live tick to diverge.
- **Other modes stay independent.** `ReputationMode.DETERMINISTIC` does not enable `advanced_social_inference`, `short_term_emotional_state`, `extended_self_model`, `predictive_world_model`, communication strategy, prospective imagination, or counterfactual mode.
- **Fail closed.** Unknown dimension or channel strings, owner mismatches, non-finite numbers, unresolved entities, hop count above 1 presented as a contribution, and a testified object that is not a canonical signed decimal abort with stable reason codes. A bad utterance is ignored. It is not repaired from the world.

## Non-Goals

- One authoritative or agent-visible global reputation score, prestige rank, or sanction
- Owning `multi_hop_testimony_tracking`, or keeping utterances whose `hop_count` is greater than 1
- Storing `trustworthy`, `dangerous`, `generous`, `competent`, or `unreliable` on domain objects
- A new `RelationshipDimension`, `SemanticBelief` predicate catalog write, personality trait, or `IdentityAspect`
- Special-casing `extract_evidence_candidates` so a reputation relation skips the ordinary claim path
- Changing trust, fear, affection, debt, respect, resentment, familiarity, or dependency from reputation updates
- Adding an `AgentCommand`, an `ActionDirection`, a `CommunicationSourceBasis`, a `V2CapabilityFlags` field, or runner JSON policy weights
- Inserting a `CognitiveLoop` ordinal, bumping the cognition-trace schema, bumping `subjective-v1`, or adding an Alembic revision
- Letting an agent read another agent's ledger or any neighborhood mean
- An LLM assessor or free-form reputation text
- Putting Experiment Q on the V1 regression gate

## Commit Plan
- **Commit 1** (after tasks 1–3): `feat(cognition): add owner-scoped reputation ledgers`
- **Commit 2** (after tasks 4–6): `feat(cognition): adopt reputation from memory and testimony`
- **Commit 3** (after tasks 7–9): `test(experiments): show split reputations across neighborhoods`
- **Commit 4** (after tasks 10–11): `docs(cognition): document distributed reputation`

## Tasks

### Phase 1: Contracts and Mode

- [x] Task 1: Add reputation contracts and `ReputationFormationPolicy`.
  - Deliverable: frozen types in `src/agents/cognition/reputation.py`, exported from `src/agents/cognition/__init__.py`. `DISABLED` construction of a ledger is unnecessary because the snapshot field stays `None`.
  - Types: `ReputationDimension` (`reliability`, `harm`, `generosity`, `competence`), `ReputationChannel` (`direct_observation`, `remembered_interaction`, `communication`, `third_party_story`), `ReputationEvidenceItem` (evidence id, owner `AgentId`, target `AgentId`, dimension, channel, lineage ref, source `AgentId`, pre-scale delta, source-trust band, tick, policy version), `ReputationDimensionState` (quantized value, support mass, contradiction mass), `ReputationProfile` (profile id, owner `AgentId`, target `AgentId`, four dimension states, evidence tuple), `ReputationLedger` (owner `AgentId`, profiles), `ReputationFormationPolicy` (`reputation-formation.v1`, speech rate `0.5`, remembered scale `0.5`, reading threshold `0.4`, caps 32 and 64), `CognitionReputationMode` (`DISABLED`, `DETERMINISTIC`) in `src/agents/cognition/configuration.py` and the matching runner enum in `src/simulation/runner_models.py`.
  - No field on these types is named `global_score`, `trustworthy`, `dangerous`, `generous`, `competent`, `unreliable`, `rumor`, or `prestige`.
  - Constructors reject unknown enums, non-finite numbers, values outside `[-1, 1]`, duplicate profile targets, evidence over the cap, and owner/target mismatches, with stable reason codes.
  - Logging: logger `agents.cognition.reputation`. DEBUG on construction with owner id, policy version, and profile count. ERROR with field name and reason code on validation failure. No utterance text and no dimension magnitudes.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Files: `src/agents/cognition/reputation.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/__init__.py`, `src/simulation/runner_models.py`, `tests/unit/test_reputation.py`.

- [x] Task 2: Wire `DETERMINISTIC` through `runner-config-v10` without owning a new flag.
  - Deliverable: mode off keeps `runner-config-v4` and today's commands. Mode on is accepted only as `runner-config-v10`. `multi_hop_testimony_tracking` still fails closed. A v10 document can still carry communication strategy, counterfactual, prospective, reflection, and consolidation keys.
  - Add `reputation_mode` to `AgentCognitionSpec` in `src/simulation/runner_models.py` and to `CognitionLoopConfig` in `src/agents/cognition/configuration.py`. Default both to `DISABLED`. Accept v10 in the version set. v10 cognition keys are the v9 key set plus `reputation_mode`. In the existing schema checks, change `communication_strategy_mode_requires_v9` so a non-disabled strategy is legal on v9 or v10. Leave `v9_requires_communication_strategy` true only for v9. Add `reputation_mode_requires_v10` for `DETERMINISTIC` reputation on v1–v9, and `v10_requires_reputation` when v10 has every reputation mode `DISABLED`. Add v10 beside v9 on the consolidation, reflection, prospective, and counterfactual allowlists in `src/simulation/runner_models.py` and `src/simulation/runner_serialization.py`. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. Do not add a `V2CapabilityFlags` field. `simulation.runner._cognition_config_for` sets `CognitionReputationMode.DETERMINISTIC` only from that field and builds `default_reputation_policy()`. Update `src/simulation/compatibility.py` with the same accepted-set note.
  - Tests: an enabled `multi_hop_testimony_tracking` still returns `capability_unimplemented`; a disabled reputation mode does not bump the written schema; strategy-only deterministic still writes v9; reputation deterministic writes v10 and round-trips; v10 with reputation disabled is rejected. Run `uv run ruff check` on each touched file.
  - Logging: DEBUG `cognition_config_reputation_mode mode=%s policy_version=%s` on logger `simulation.runner`. Do not log policy thresholds. ERROR on schema rejection uses the existing stable runner codes.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 1.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/runner.py`, `src/simulation/__init__.py`, `src/agents/cognition/configuration.py`, `tests/unit/test_runner_models.py`, `tests/unit/test_runner_serialization.py`, `tests/unit/test_simulation_runner_construction.py`, `tests/unit/test_v2_flag_defaults.py`, `tests/unit/test_cognition_configuration.py`.

### Phase 2: Private Evidence

- [x] Task 3: Apply direct observation into the owner's ledger.
  - Deliverable: `apply_reputation_update(...)` returns a new `ReputationLedger` for one owner. Given this tick's occurrences and the owner's `OwnerSafeSocialIdentity`, it resolves `actor_id` to an `AgentId`, appends `direct_observation` evidence, and moves only the named dimensions by the locked deltas. `help`, `attack`, and `give` do not move `competence`. Passing `WorldState` or `WorldEvent` raises `TypeError`. The module must not import `analysis`, `simulation`, `communication`, `world.models`, `world.events`, or `world._state`. It may import `world.observations`. Trust floats, when later tasks pass them, are already projected by the caller.
  - An `actor_id` with no counterpart binding logs `unresolved_entity` and adds no profile. Unknown occurrence kinds leave the ledger unchanged. A repeated lineage ref does not stack. Caps drop new items with `cap_exceeded` and keep older evidence. Disabled callers do not call this function.
  - Logging: DEBUG `reputation_observation_applied` with owner id, tick, target id, dimension, channel, and sign (`positive`, `negative`, or `zero`). INFO `reputation_head_updated` with owner id, target count, and evidence count. WARNING `reputation_evidence_dropped` with reason `cap_exceeded`, `ignored_kind`, or `unresolved_entity`. ERROR on owner mismatch. No public-fact payloads.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 1.
  - Files: `src/agents/cognition/reputation.py`, `tests/unit/test_reputation.py`.

- [x] Task 4: Apply remembered interactions without rewriting memory.
  - Deliverable: the same updater accepts the owner's current `MemoryTrace` values and appends `remembered_interaction` evidence only under the locked trace rules. The cue is the `c-kind` concept from `build_direct_observation_memory_trace` (`help`, `attack`, or `give`). Participation is `social_identity.owner_entity_id` matching `e-actor` or `e-other`. The other entity resolves to the target `AgentId`. Qualifying traces move `generosity`, `reliability`, and `harm` at scale `0.5`. `competence` stays unchanged. Traces with no such concept contribute nothing. The returned traces are the same objects the caller passed in.
  - Skip the trace when `provenance.observed_source_id` equals an existing `direct_observation` lineage ref. A missing binding on the counterpart entity is `unresolved_entity`.
  - Logging: DEBUG `reputation_memory_applied` with owner id, tick, memory id, target id, dimension, and sign. WARNING `reputation_memory_skipped` with reason `no_cue`, `too_recent`, `not_participant`, `already_observed`, or `unresolved_entity`. No concept lists at INFO.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 3.
  - Files: `src/agents/cognition/reputation.py`, `tests/unit/test_reputation.py`.

### Phase 3: Social Transmission

- [x] Task 5: Let source trust scale adoption of communication and third-party stories.
  - Deliverable: a delivered `ObservedCommunication` or inbox envelope whose hop count is 0 or 1 and whose relations use the locked dimension predicates updates the listener's ledger. Relation subjects are entity ids. Resolve the speaker and the subject through `OwnerSafeSocialIdentity` before choosing a channel or a profile. Speaker-subject relations use channel `communication`. Other-agent subjects use channel `third_party_story`. The caller passes `source_trust` already produced by `project_trust_inputs`. The delta pulls toward the testified value at `0.5 * source_trust`. Missing relationship trust uses `(0.5, 0.2)` and records `source_trust_missing`. Hop count above 1 adds nothing. A non-canonical object token is ignored with `invalid_testimony`. An unresolved speaker or subject is `unresolved_entity`.
  - `reputation.py` does not import `communication.py`. The listener's `DirectedRelationshipProfile` values are unchanged. The speaker's ledger is not copied. The updater does not call `revise_semantic_belief` and does not alter `extract_evidence_candidates`. Two listeners with different trust toward the same speaker finish with different heads from the same utterance.
  - Logging: DEBUG `reputation_testimony_applied` with owner id, tick, speaker id, target id, channel, dimension, and source-trust band. WARNING `reputation_testimony_rejected` with reason `hop_dropped`, `invalid_testimony`, `self_subject`, or `unresolved_entity`. No relation object text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 3.
  - Files: `src/agents/cognition/reputation.py`, `tests/unit/test_reputation.py`.

- [x] Task 6: Carry the ledger across ticks and replace `Wait` with one testimony `Tell` only when enabled.
  - Deliverable: `SubjectiveSnapshot`, `CognitiveLoopProposal`, and `CognitiveLoopResult` gain `reputation: object | None = None`. `AgentRuntimeCheckpoint` gains the same optional field. `AgentRuntime` loads, exports, and restores it the way it already stores `theory_of_mind`. After a successful enabled tick, the runtime replaces the ledger with the updater result. Abort and `DISABLED` leave it unset and append nothing. `SubjectiveMutationBatch` and `subjective-v1` do not change. There is no Alembic revision.
  - `ActionPlan` still holds one command. When enabled, the selected command is `Wait`, some absolute dimension on a head is `>= 0.4`, and an eligible recipient exists who is not the target, `CommandPlanner` replaces that `Wait` with one `Tell` from `origin_utterance`. Text is the dimension name. `source_basis` is `unreferenced`. Each relation subject is the target's entity id, the predicate is the dimension name, and the object is the quantized signed value, up to four relations. A selected `Help`, `Attack`, `Give`, `Move`, `Talk`, `Ask`, or `Tell` stays in place with reason `command_already_selected`. `DISABLED` adds no command. Do not call `choose_communication_strategy` from the reputation module, and do not add a `ComponentKind`. The caller projects speaker trust and passes the float into `apply_reputation_update`.
  - Thread the optional ledger through `CognitionLoopInput` / `CognitiveLoop` the same way `theory_of_mind` is threaded. Update `tests/fakes/cognition.py` only where a constructor grew. Run `uv run ruff check` on each touched file.
  - Logging: DEBUG `reputation_ledger_carried` / `reputation_ledger_skipped` with owner id, tick, mode, and profile count on logger `simulation.agent_runtime`. DEBUG `reputation_testimony_emitted` with owner id, recipient id, target id, and dimension names on logger `agents.cognition.deliberation`, or `reputation_testimony_skipped` with reason `mode_disabled`, `below_threshold`, `no_recipient`, or `command_already_selected`. No signed values and no utterance text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on tasks 2, 4, and 5.
  - Files: `src/agents/cognition/models.py`, `src/agents/cognition/loop.py`, `src/agents/cognition/deliberation.py`, `src/agents/cognition/contracts.py`, `src/simulation/agent_runtime.py`, `src/simulation/perception.py`, `src/simulation/run_control.py`, `tests/fakes/cognition.py`, `tests/unit/test_reputation.py`, `tests/unit/test_reputation_runtime.py`.

### Phase 4: External Aggregate

- [x] Task 7: Add analysis-only `distributed_reputation@1`.
  - Deliverable: `compute_distributed_reputation` in `src/analysis/reputation_metrics.py` joins caller-supplied ledgers with a caller-supplied owner-to-neighborhood map. For one target id it returns each neighborhood's mean per dimension, the max pairwise mean gap per dimension, and reading labels at threshold `0.4`. It does not return a single score across dimensions. Empty input yields `MetricAvailability.ABSENT` and does not invent a mean.
  - Register `MetricFamilyId.DISTRIBUTED_REPUTATION` the same way as `theory_of_mind@1` in `src/analysis/specifications.py` and `src/analysis/__init__.py`. Duck-type ledger attributes with `getattr`. The module must not import `agents`, `apply_reputation_update`, or `AgentRuntime`. The result type has no path back into `CognitiveLoop`.
  - Logging: DEBUG `distributed_reputation_metric` with ledger count, neighborhood count, and gap per dimension. Logger `analysis.reputation_metrics`. Do not log reading labels at INFO. Do not log agent belief text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 1.
  - Files: `src/analysis/reputation_metrics.py`, `src/analysis/specifications.py`, `src/analysis/__init__.py`, `tests/unit/test_reputation_experiment.py`.

### Phase 5: Split Neighborhoods

- [x] Task 8: Add Experiment Q off the V1 gate.
  - Deliverable: `experiment_q_distributed_reputation` pairs `q-disabled` / `reputation_disabled` on `runner-config-v4` with `q-enabled` / `reputation_deterministic` on `runner-config-v10`. Arms share seed, scenario, and stochastic identity. The catalog function checks that pairing and the mode field. It does not run the metric. Register it in `src/experiments/catalog.py` and export it from `src/experiments/__init__.py`. Do not add it to `tests/unit/test_v1_regression_gate.py`.
  - Scenario builder `distributed_reputation_scenario` in `src/experiments/reputation_scenario.py` follows `identity_divergence_scenario`. Locations `east` and `west` have one symmetric adjacency edge, and each location has weather. Agents `east_a`, `east_b`, and `focal` start at `east`. Agents `west_a` and `west_b` start at `west`. Body ids and agent ids stay distinct, with a counterpart binding for each pair. Do not add a culture, faction, or role field. The world must pass `_validate_topology` and `_validate_weather_coverage`.
  - Logging: DEBUG `experiment_q_built` with experiment id and condition ids. Logger `experiments.catalog`. No utterance text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 2.
  - Files: `src/experiments/reputation_scenario.py`, `src/experiments/catalog.py`, `src/experiments/__init__.py`, `tests/unit/test_reputation_experiment.py`.

- [x] Task 9: Prove one target can hold opposite reputations, and that the aggregate stays outside the agents.
  - Deliverable: tests that fail if a global score appears on a ledger, if neighborhoods converge despite different evidence, or if a listener's command input includes the metric result.
  - Required cases in `tests/unit/test_reputation.py`, `tests/unit/test_reputation_runtime.py`, and `tests/unit/test_reputation_experiment.py`:
    - East owner observes `focal` `help` once. The occurrence `actor_id` is `focal`'s entity id, resolved through `OwnerSafeSocialIdentity` to `focal`'s `AgentId`. `generosity` increases by `0.25` and `reliability` by `0.10`; `harm` decreases by `0.05`; `competence` stays `0`; channel is `direct_observation`; no relationship dimension changes. An occurrence whose actor has no binding adds no profile.
    - The same help trace on a later tick, with `e-actor` or `e-other` equal to the owner's entity, `c-kind` concept `help`, and `observed_source_id` not already stored, moves the same dimensions at half scale and channel `remembered_interaction`. Applying that memory id twice does not stack. A trace without those concept tokens does not move the ledger. A trace whose `observed_source_id` matches the direct-observation lineage does not stack either.
    - West owner with trust `1.0` toward `west_a` hears a hop-0 `Tell` whose relation subject is `focal`'s entity id, predicate `harm`, object `0.8`, and text `harm`: channel `third_party_story`, `harm` moves halfway toward `0.8`, and the text is not a colloquial label. `source_basis` is `unreferenced`. The ledger value is not read back from any `SemanticBelief` the existing extractor may create.
    - The same story heard with missing trust uses scale `0.5` and records `source_trust_missing`. A listener with trust `0.2` moves strictly less than a listener with trust `1.0`.
    - A self-report whose subject is the speaker uses channel `communication`. Hop count `2` adds no evidence. Enabling `multi_hop_testimony_tracking` still raises `capability_unimplemented`.
    - After those fixtures, the east owner's `reliability` of `focal` is at least `0.4` and the trusting west owner's `harm` of `focal` is at least `0.4`. The signs of the two profiles differ. Neither ledger contains an aggregate field.
    - The metric, given neighborhood ids `east` and `west`, reports a `harm` mean gap of at least `0.4` and the readings `trustworthy` for east's high reliability and `dangerous` for west's high harm. Those reading strings are absent from `ReputationLedger`, `StructuredUtterance`, and `SubjectiveSnapshot`. The ledger object is not a `SemanticBelief`.
    - Mode `DISABLED`: snapshot reputation stays `None`, no reputation `Tell` is appended, and the command matches the planner without this feature.
    - Mode `DETERMINISTIC`: when the selected command is `Wait` and a head has `generosity >= 0.4`, the one command becomes a `Tell` whose predicates are dimension names and whose subject is the target entity id. When the selected command is `Help` or `Attack`, that command stays and the skip reason is `command_already_selected`.
    - `CognitiveLoop` source and `AgentRuntime` source do not import `analysis.reputation_metrics`.
  - Logging assertions: the DEBUG lines are `reputation_observation_applied` and `reputation_testimony_applied`. Each includes channel and dimension. Neither includes utterance text or the words `trustworthy` and `dangerous`.
  - Depends on tasks 6, 7, and 8.
  - Files: `tests/unit/test_reputation.py`, `tests/unit/test_reputation_runtime.py`, `tests/unit/test_reputation_experiment.py`, `tests/unit/test_v1_regression_gate.py` (assert Experiment Q is absent only if the gate enumerates experiment ids), `tests/unit/test_v2_flag_defaults.py`.

### Phase 6: Gate and Documentation

- [x] Task 10: Keep the V1 gate green when the mode is disabled.
  - Deliverable: flags-off, reputation-disabled, strategy-disabled, tracing-off catalog A–E and the reference scenario keep their current hashes. Leave `v1_regression_profile` unchanged. It checks capability flags and tracing only, so catalog A–E stay green by continuing to write `runner-config-v4` with `reputation_mode` `DISABLED`. Do not add a schema rejection there. Replay of a disabled run is unchanged. Run `uv run ruff check` on every file in the plan diff, including new test modules.
  - Logging: existing regression DEBUG lines only. Add no payload logs.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on tasks 2 and 6.
  - Files: `tests/unit/test_v1_regression_gate.py`.

- [x] Task 11: Document private ledgers, transmission channels, and the external aggregate.
  - Deliverable: readers can see that each agent has its own dimensional beliefs, that colloquial assessments are analysis readings, and that neighborhood means never re-enter cognition. Route the edits through `/aif-docs`.
  - Update `docs/social-communication.md` with the four channels, the hop cutoff, and the source-trust scale. Update the downstream checklist in `docs/architecture.md` so `runner-config-v10` carries the v9 cognition keys plus `reputation_mode`, Experiment Q is named, `distributed_reputation@1` is analysis-only, and `multi_hop_testimony_tracking` is still unowned. State that `v1_regression_profile` is unchanged and that no capability flag was added. Update the mode table in `docs/cognition-runtime.md` and the schema paragraph in `docs/simulation-runner.md`. Update `.ai-factory/DESCRIPTION.md` only where the runner-schema sentence would otherwise stay stale. Update `.ai-factory/ARCHITECTURE.md` only where its runner-schema or flag sentence would otherwise stay stale.
  - Logging: none in docs. Implementation touchpoints already log mode, channel, dimension, drops, testimony emission, and metric gaps as specified above.
  - Depends on tasks 2, 6, and 8.
  - Files: `docs/social-communication.md`, `docs/architecture.md`, `docs/cognition-runtime.md`, `docs/simulation-runner.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`.
