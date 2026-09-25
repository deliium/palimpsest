# Implementation Plan: Reflection Engine for Periodic Metacognition

Branch: main
Created: 2026-09-25
Improved: 2026-09-25 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete roadmap milestone; this plan adds opt-in `ReflectionMode` and does not own a reserved capability flag, so M6 stays open for flag ownership.

## Compatibility contract

This plan adds an opt-in `ReflectionEngine` that runs in agent cognition only when a configured subjective trigger fires. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only mutation authority. Reflection reads the owner's `Observation`, `SubjectiveSnapshot`, and prepare-stage artifacts. It never receives `WorldState`, `WorldEvent`, an event repository, replay, or another agent's store.
2. Capability flags unchanged. Do not add or own a `V2CapabilityFlags` field. `short_term_emotional_state` stays the only owned flag. Reserved flags still fail closed with `capability_unimplemented`. Reflection is `ReflectionMode` on `AgentCognitionSpec`, default `DISABLED`.
3. V1 regression gate stays green under flags-off, tracing-off, and default `ReflectionMode.DISABLED`. Catalog A–E and the reference scenario keep their current `exact_trajectory_hash` values. Experiment G is additive and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. Schema bumps use accepted-set + exact key-set discipline. The default write stays `runner-config-v4`. `runner-config-v5` stays consolidation-only: it requires `consolidation_mode`, rejects `reflection_mode`, and requires at least one non-disabled consolidation mode. A non-disabled consolidation mode is legal on v5 or v6. `runner-config-v6` is emitted only when some agent's reflection mode is not `DISABLED`, including when consolidation is also enabled. v6 requires the v5 cognition keys plus `reflection_mode`. v1–v4 omit both extra keys and restore `DISABLED`. v1–v5 omit `reflection_mode` and reject that key. A non-disabled reflection mode on v4 or v5 fails closed (`reflection_mode_requires_v6`). v6 joins every encode/decode membership set that currently ends at v5, so a round-trip keeps agent `name`, `initial_goals`, `capability_flags`, `cognition_trace`, and the v4 root keys. Thresholds stay on `ReflectionPolicy` and are not runner JSON keys.
5. No scripted emergence. No friend, enemy, leader, or culture labels. Example sentences in this plan are meanings of structured claims, not stored prose and not hard-coded social roles.
6. No LLM → world shortcuts. The provider may only select ids from a deterministic candidate set through `StructuredOutput`. It never becomes an `AgentCommand` and never mutates world state.
7. Experiments stay reproducible. Experiment G arms share seed, scenario, and stochastic identity. LLM tests use `FakeLLMProvider`.
8. Optional cognition tracing stays outside the objective fold. This plan does not insert a `CognitiveLoop` ordinal and does not bump the cognition-trace schema or Alembic. Tracing on versus off must not change `exact_trajectory_hash` when reflection is disabled.

## Goal

Give an agent a periodic metacognitive pass, `ReflectionEngine`, that is not part of every tick. When a configured trigger fires, the engine reviews owner-scoped subjective material and may commit structured conclusions. Those conclusions can change a later command. They must not rewrite objective history.

Triggers, all configurable on `ReflectionPolicy`, any one of which can request a pass subject to a minimum gap:

- elapsed ticks since the last reflection
- significant perceived occurrences already present on this `Observation`
- strong emotional intensity already on the owner's emotional state
- repeated subjective failure
- completion of a major goal already visible on the goal board
- a large contradiction mass or contradiction count on an owned semantic belief
- a directed relationship revision the owner has not yet reflected on

The pass may examine only:

- a bounded selection of owned memories
- semantic beliefs
- goals
- the prepare-stage `SelfModel` (projection, not a stored record)
- directed relationships
- a subjective decision journal
- subjective outcomes recorded from later observations the agent already received

It may emit only these conclusion kinds:

- revised belief
- new hypothesis (`BeliefActivationState.CANDIDATE`)
- new long-term goal
- abandoned goal
- updated self-belief (owner-referential belief revision)
- relationship reassessment
- detected behavioral pattern. `repeated_action` and `repeated_help` are a hypothesis or revised belief. `repeated_failure` and `prediction_error` are goal intents. There is no second pattern store.

Illustrative meanings. Slots are copied from cited subjective evidence. Pattern codes are candidate labels, not invented belief predicates.

| Meaning | Pattern code | Writer | Slots taken from cited evidence |
| --- | --- | --- | --- |
| "I keep sharing food with Alice." | `repeated_action` | belief or relationship revision | predicate already on cited `MemoryRelation`s, counterpart id, count |
| "My predictions about the forest are often wrong." | `prediction_error` | goal intent only | place id and `NO_PROGRESS` count from decision records whose outcome is already filled |
| "Bob helped me three times." | `repeated_help` | belief revision | help predicate already on cited traces, counterpart id, count |
| "I repeatedly fail when searching at night." | `repeated_failure` | goal intent only | command kind and `DayPhase` from decision records whose outcome is already filled |

Reflection must not query objective `WorldEvent`s. Perceived occurrences are the redacted `Observation.occurrences` the agent already holds. Opaque ids already copied onto observations or memory provenance may be retained; they must not be dereferenced.

## Design Decisions (locked)

- **Not a loop stage.** Do not add a `ComponentKind` or an ordinal in `_STAGE_ORDER`. Call `ReflectionEngine` from `CognitiveLoop.complete` after the memory-update stage and after optional sleep consolidation. The effective command for this tick is already chosen. Reflection changes later ticks only. `DISABLED` adds no boundary record, no trace envelope, and no objective event.
- **Not every tick.** `ReflectionPolicy.min_gap_ticks` defaults to the same value as `interval_ticks` (default `8`). A pass runs only when the gap has elapsed and at least one enabled trigger is true. Inside the gap, true triggers are recorded as skipped. Setting `interval_ticks` to `1` is a valid test override on `ReflectionPolicy`; it is not a runner JSON field. The default configuration is not every tick. `DISABLED` never evaluates triggers. `CognitionLoopConfig` may carry a `ReflectionPolicy` for tests. The runner builds the default policy from the mode and sets `allow_provider` only for `LLM_ASSISTED`.
- **Trigger meanings.**
  - `elapsed_ticks`: when `last_reflection_tick` is an `int`, fire when `tick - last_reflection_tick >= interval_ticks`. When it is `None`, there has been no prior pass, and the trigger is `tick + 1 >= interval_ticks`. Do not store `-1`. `require_exact_nonneg_int` rejects a negative tick.
  - `significant_occurrences`: count of this observation's `Observation.occurrences` whose `kind` is in `significant_occurrence_kinds` and whose count meets `significant_occurrence_count`. An empty allowlist disables this trigger. Compare kind strings already on the observation. Do not import `world.events` and do not resolve `ObservationProvenance` to an event.
  - `strong_emotion`: `AgentEmotionalState.max_intensity()` is at least the policy threshold. Missing or passthrough emotional state makes this trigger false. Do not enable `short_term_emotional_state`.
  - `repeated_failure`: either the journal reaches `repeated_failure_count` of `NO_PROGRESS` outcomes for the same `command_kind`, or this observation contains that many owner-actor `ObservedOccurrence` values with `success is False`. Records whose `outcome_code` is still `UNKNOWN` do not count. The record appended on the current tick is stored and is not evidence until a later tick fills its outcome. Both sources are subjective.
  - `major_goal_completion`: a snapshot goal with status `COMPLETED`, horizon in `{DESIRE, LONG_TERM}` by default, whose id is not yet on `cursor.acknowledged_goal_ids`.
  - `belief_contradiction`: an owned belief whose `contradiction_mass` or `evidence_contradiction_count` meets the policy threshold.
  - `relationship_change`: a `DirectedRelationshipProfile.revision_ordinal` greater than the ordinal stored on the cursor for that pair. The first time a pair is seen, store the ordinal during finalize and do not treat the initial profile as a change.
- **Cursor and journal.** Carry `ReflectionCursor` and a bounded `SubjectiveDecisionRecord` ring on `AgentRuntime`. `AgentRuntimeCheckpoint` in `src/simulation/run_control.py` is an in-memory dataclass, not a canonical JSON document. Add optional `reflection_cursor` and `decision_journal` defaulting to `None`, and thread them through `export_runtime_checkpoint` and `restore_runtime_checkpoint`, the same way `emotional_state` was added. Do not bump a checkpoint schema. On every enabled successful finalize, append one decision record, backfill the previous record's `outcome_code`, and record relationship ordinals seen for the first time. Set `last_reflection_tick` and `acknowledged_goal_ids` only when a reflection pass is applied. Append a decision record only when reflection mode is not `DISABLED`, from the effective command type name and self-visible observation fields (`day_phase`, place id when present). Outcome codes are `NO_PROGRESS`, `PERCEIVED_CHANGE`, and `UNKNOWN`. Deliberation, imagination, and motivation must not read the journal or the cursor. `DISABLED` leaves both fields `None`, so checkpoints and commands match today.
- **Inputs.** `ReflectionContext` is built in `agents.cognition` from the owner snapshot, the prepare-stage `SelfModel`, this invocation's pending subjective intents, the observation's occurrences, the emotional evaluation, the cursor, and the decision journal. Memory selection is deterministic: tick, then memory id, capped by `max_memories`, preferring traces cited by contradicting beliefs, relationship evidence, and recent decision places. The context must reject `WorldState`, `WorldEvent`, event repositories, analysis DTOs, `RecallAuditRecord`, and foreign owner ids.
- **Deterministic candidates first.** Policy version `reflection-v1` materializes a closed candidate set. Each candidate has a `ReflectionConclusionKind`, a non-empty evidence-id set drawn only from the context, and slots copied from those records. A predicate that does not already appear on a cited memory relation cannot be invented. Counts are exact integers. Floats use the existing score quantum. No RNG, wall clock, or Python `hash()`.
- **Outputs reuse current writers.** Belief and relationship conclusions cite only `MemoryId` values already in the context. The stored predicate is copied from a cited `MemoryRelation`. Do not invent a predicate, including the pattern code. `repeated_action` and `repeated_help` emit a `BeliefRevisionRequest`: `BeliefActivationState.CANDIDATE` when that subject and predicate are new, otherwise a revision of the existing belief, with a numeric count value. Self-beliefs are those revisions whose `ClaimSubject` is the owner agent and whose predicate was copied from a cited relation. Relationships use `RelationshipRevisionRequest` whose `memory_ref` values are those memory ids; the reverse edge is never created. `repeated_failure` and `prediction_error` are supported by decision-record ids, which are not `MemoryId`s. They emit `GoalTransitionIntent` only and must not become `BeliefRevisionRequest`. Adopted goals use `GoalHorizon.LONG_TERM`, `GoalOriginKind.INFERRED`, a `description` that is the closed pattern-code token (bounded text, not a sentence), and `belief_refs` set to the decision-record ids. `GoalTransitionIntentReason.ADOPTED` maps onto the existing receipt code `REVISED`. Abandoned goals use `ABANDONED` only when the goal's `belief_refs` intersect those decision-record ids or the goal outcome matches the failed command kind. Do not abandon an already `COMPLETED` goal. Do not persist `SelfModel` and do not enable `extended_self_model`.
- **No double-write with sleep consolidation.** When both modes run on a sleep tick, consolidation runs first. Reflection drops a conclusion whose belief id is already in `OfflineConsolidationPlan.belief_revisions`, whose relationship pair is already in `relationship_revisions`, or whose goal id is already in `goal_intents`.
- **LLM grounding.** `LLM_ASSISTED` calls `LLMProvider.generate` only through schema `reflection.selection.v1` and prompt package `llm/prompts/reflection/v1/`. The payload is candidate ids, counts, and closed codes. The schema has no prose claim field. Every returned id must already be in the candidate set. Missing provider, `allow_provider=False`, transport error, schema failure, or a foreign id applies the deterministic selection and sets `fallback_used`. `DISABLED` and `DETERMINISTIC` never call the provider.
- **Apply path.** Add `reflection` on `CognitiveLoopResult`, default `None`, and set it from `complete` after consolidation. `AgentRuntime.finalize_pending` applies it only after a successful `resolve_tick`, through the existing subjective batch and `apply_goal_transition_intents`. Abort drops the plan. Operation ids are `reflection:{tick}:{evidence_root}` and are idempotent on repeated finalize. Journal append and first-seen relationship ordinals happen on every enabled successful finalize. `last_reflection_tick` and acknowledged goal ids update only when a pass is applied.
- **Schema.** Add `ReflectionMode` (`DISABLED`, `DETERMINISTIC`, `LLM_ASSISTED`) and lockstep `CognitionReflectionMode`. Keep `RUNNER_SCHEMA_VERSION` as `runner-config-v4`. Add `runner-config-v6` whose cognition object is the v5 key set plus required `reflection_mode`. Emit v6 only when some agent is not `DISABLED` for reflection. A v6 document may also carry a non-disabled `consolidation_mode`. v5 remains consolidation-only and rejects `reflection_mode`. Widen `consolidation_mode_requires_v5` so a non-disabled consolidation mode is accepted on v5 or v6. Add v6 beside v5 in the encode/decode sets for agent `name` / `initial_goals`, `capability_flags`, `cognition_trace`, and the runner root keys. `COGNITION_POLICY_VERSION` and `GOAL_MODEL_VERSION` stay unchanged. Do not add policy thresholds to the runner JSON.
- **Audits and traces.** `ReflectionAudit` (owner, tick, mode, trigger codes, conclusion kind counts, evidence-id counts, `fallback_used`) is in-run and analysis-only, attached on `SimulationRunnerResult` the same way as consolidation audits. Do not put audits on observations, prompts, or `runner-result-v2`. Do not project reflection into `SCIENTIFIC_TRACE_STAGE_SEQUENCE`.
- **Behavior proof.** Imagination already changes command type when a belief predicate is in `_DANGER_PREDICATES` or `_SAFETY_PREDICATES` (`src/agents/cognition/imagination.py`), including `is_dangerous` and `is_safe`. The future-decision test seeds memories whose cited `MemoryRelation.predicate` is already one of those codes. The default retriever does not compile those traces into that belief. Reflection copies the predicate into a belief. Decision records alone do not become beliefs. The disabled and deterministic arms share the reflection tick's command and the hashes of events committed through that tick. The following cognitive pass differs. Applying the subjective plan does not change those already committed event hashes. Experiment G does not carry this fixture. It checks schema, a shared objective hash through the reflection tick, and an audit on the deterministic arm only.
- **Fail closed.** Unknown mode strings, owner mismatches, non-finite knobs, empty evidence, foreign evidence ids, and predicates absent from cited relations abort with stable reason codes. A candidate that fails provenance is dropped, not repaired from the world.

## Non-Goals

- Owning or adding a `V2CapabilityFlags` entry for reflection
- Running reflection on every tick under the default policy
- Inserting a `CognitiveLoop` ordinal, bumping the cognition-trace schema, or adding an Alembic revision
- Reading `WorldEvent`, event stores, analysis truth, or another agent's memory to correct a conclusion
- Letting LLM prose become a stored claim, goal description, or relationship label
- Persisting `SelfModel` or enabling `extended_self_model`
- Wiring LLM provider lifecycle into the API or `compose.yaml`
- Putting Experiment G on the V1 regression gate
- Teaching deliberation to read the decision journal directly
- Feeding reflection audits back into live planning

## Commit Plan
- **Commit 1** (after tasks 1–3): `feat(cognition): add reflection contracts and deterministic pattern policy`
- **Commit 2** (after tasks 4–6): `feat(cognition): reflect on subjective evidence between ticks`
- **Commit 3** (after tasks 7–9): `test(experiments): show reflection changes later commands without rewriting history`

## Tasks

### Phase 1: Contracts, Schema, and Deterministic Policy

- [x] Task 1: Add closed reflection modes, policy, cursor, and conclusion types.
  - Deliverable: Add `ReflectionMode` (`DISABLED`, `DETERMINISTIC`, `LLM_ASSISTED`) in `src/simulation/runner_models.py` and lockstep `CognitionReflectionMode` in `src/agents/cognition/configuration.py`. Add frozen `ReflectionPolicy` version `reflection-v1` with quantized thresholds for interval, minimum gap, emotion intensity, contradiction mass, contradiction count, repeated-failure count, memory cap, `significant_occurrence_count`, and the occurrence-kind allowlist. `allow_provider` defaults false. `CognitionLoopConfig` may hold this policy for tests. Do not add the thresholds to runner JSON. Add `ReflectionTriggerKind`, `ReflectionConclusionKind`, `SubjectiveDecisionRecord`, `ReflectionCursor` (`last_reflection_tick: int | None = None`), `ReflectionCandidate`, and `ReflectionAudit` in `src/agents/cognition/reflection.py`. Evidence ids are ordered and non-empty on every candidate. Audits store ids, counts, and reason codes only. Default mode is `DISABLED`.
  - Expected behavior: Disabled is the default. A cursor with `last_reflection_tick is None` is valid, and constructing one with `-1` fails. Repr of candidates and audits omits propositions, goal text, and relationship assessments. Invalid knobs and empty evidence fail closed. The new module does not import `world.events` or `simulation`.
  - Files: `src/simulation/runner_models.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/reflection.py`, `src/agents/cognition/__init__.py`, `tests/unit/test_reflection_models.py`.
  - Logging requirements: Model construction stays log-free. Later wiring may DEBUG mode and policy version only. ERROR on invalid mode uses a stable reason code. Never log claim text, goal descriptions, prompts, or payloads. Levels follow `PALIMPSEST_LOG_LEVEL`.
  - Dependencies: None.

- [x] Task 2: Accept `runner-config-v6` only when reflection is enabled.
  - Deliverable: Add `RUNNER_SCHEMA_VERSION_V6 = "runner-config-v6"` to `SUPPORTED_RUNNER_SCHEMA_VERSIONS`. Leave `RUNNER_SCHEMA_VERSION` as `runner-config-v4`. Version-branch `_encode_cognition` / `_decode_cognition`: v1–v4 keep today's key set and restore both consolidation and reflection to `DISABLED`; v5 requires `consolidation_mode` and rejects `reflection_mode`; v6 requires the v5 keys plus `reflection_mode`. Widen `SimulationRunnerConfig` validation so a non-disabled `consolidation_mode` is legal when `schema_version` is v5 or v6. v5 still requires some non-disabled consolidation mode and still rejects `reflection_mode`. A config whose reflection mode is not `DISABLED` and whose schema is not v6 fails closed (`reflection_mode_requires_v6`). v6 requires at least one non-disabled reflection agent and may also enable consolidation. In `src/simulation/runner_serialization.py`, add v6 to every membership set that currently includes v5 and stops there: `_encode_agent` name and `initial_goals`, capability-flag encode/decode, cognition-trace encode/decode, and the v4 root-key branch used for decode. A v6 document must still round-trip agent names, flags, and trace. Update the `runner_config` bump text in `src/simulation/compatibility.py` so the default write stays v4, v5 stays consolidation-only, and v6 is accepted when reflection is enabled. Add the mode field to `AgentCognitionSpec` and `CognitionLoopConfig`. `_cognition_config_for` copies it into `CognitionReflectionMode` and builds the default `ReflectionPolicy` with `allow_provider` true only for `LLM_ASSISTED`. Do not serialize policy thresholds. Export new public names through existing facades and `__all__`.
  - Expected behavior: Golden v1–v5 documents still decode. v4 fingerprints and `exact_trajectory_hash` values stay unchanged when reflection is `DISABLED`. A v5 consolidation document still round-trips without a reflection key and still fails if every consolidation mode is `DISABLED`. A v6 document with reflection enabled and consolidation `DISABLED` round-trips `reflection_mode`, agent names, capability flags, and cognition trace. A v6 document with both modes enabled is accepted. A v6 document with reflection `DISABLED` fails closed. Unknown strings fail closed. `COGNITION_POLICY_VERSION` remains `cognition-policy-v1`. `tests/unit/test_v1_regression_gate.py` still sees `RUNNER_SCHEMA_VERSION_V4`.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/runner.py`, `src/agents/cognition/configuration.py`, facade `__init__.py` files as needed, `tests/unit` runner serialization and compatibility tests. Do not retarget the v4 pins in `test_v1_regression_gate.py`.
  - Logging requirements: DEBUG `runner_config_decoded` may include schema version and reflection mode string. ERROR `invalid_enum` / `invalid_fields` with path and reason code. Never log scenario payloads or DSN material.
  - Dependencies: Task 1.

- [x] Task 3: Implement the deterministic pattern policy.
  - Deliverable: Add a pure function in `src/agents/cognition/reflection.py` that, given a `ReflectionContext`, emits the candidate set for `repeated_action`, `prediction_error`, `repeated_help`, and `repeated_failure`. Pattern codes are labels. Copy predicates, counterpart ids, place ids, command kinds, and day phases only from cited records. Emit a candidate only when the count meets the policy minimum. `repeated_action` and `repeated_help` emit `BeliefRevisionRequest` and, when the relation cites a counterpart, `RelationshipRevisionRequest`. The belief predicate is the cited `MemoryRelation.predicate`. Use `BeliefActivationState.CANDIDATE` when that subject and predicate are new, and a revision when they already exist. The claim value is the numeric count. Self-beliefs are the revisions whose `ClaimSubject` is the owner and whose predicate was copied. `repeated_failure` and `prediction_error` emit `GoalTransitionIntent` only. Do not pass decision-record ids as `BeliefEvidenceContribution.memory_id`. Exclude records whose `outcome_code` is `UNKNOWN`. Adopted goals use `GoalHorizon.LONG_TERM`, `GoalOriginKind.INFERRED`, `description` equal to the pattern code, and `belief_refs` equal to the decision-record ids. Add `GoalTransitionIntentReason.ADOPTED` and map it to receipt code `REVISED` in `_intent_reason_to_receipt_code`. Abandoned goals use `ABANDONED` when the goal's `belief_refs` intersect those ids or the goal outcome matches the failed command kind. Goal ids are `goal-reflection:{owner}:{tick}:{pattern_code}`. Do not import `simulation` or `world.events`.
  - Expected behavior: Identical inputs yield identical candidates. Three cited help traces about one counterpart produce one `repeated_help` hypothesis whose evidence ids are those traces and whose predicate is copied from them. A night-search failure series whose outcomes are `NO_PROGRESS` produces `repeated_failure` and can abandon a matching goal, with no `BeliefRevisionRequest`. A decision record still marked `UNKNOWN` does not count. A predicate that appears on no cited relation produces no belief candidate. A foreign owner id fails closed. Empty inputs yield an empty candidate set.
  - Files: `src/agents/cognition/reflection.py`, `src/agents/cognition/models.py`, `src/simulation/agent_runtime.py`, `tests/unit/test_reflection_policy.py`.
  - Logging requirements: The pure policy stays log-free. Tests may assert later orchestration metadata, not payload logs.
  - Dependencies: Task 1.

### Phase 2: Triggers, Runtime, and LLM Selection

- [x] Task 4: Evaluate triggers and record subjective decisions without changing the current command.
  - Deliverable: Add `ReflectionEngine.triggers` that returns the matched `ReflectionTriggerKind` values under the gap rule in the design decisions. On an enabled successful finalize, append one `SubjectiveDecisionRecord` from the effective command and the current observation, backfill `outcome_code` for the previous open record from this observation, and store first-seen relationship ordinals without firing `relationship_change`. The new record stays `UNKNOWN` and is not trigger evidence until a later tick fills it. Store the journal and cursor on `AgentRuntime`. Add optional `reflection_cursor` and `decision_journal` on `AgentRuntimeCheckpoint`, both defaulting to `None`, and copy them in `export_runtime_checkpoint` and `restore_runtime_checkpoint`. Do not bump a checkpoint schema. Do not read the journal from deliberation. `DISABLED` does not append records and does not create a cursor. `last_reflection_tick` and `acknowledged_goal_ids` stay unchanged unless a pass is applied in Task 5.
  - Expected behavior: A tick inside `min_gap_ticks` does not request a pass. With `last_reflection_tick is None`, the elapsed trigger waits until `tick + 1 >= interval_ticks`. Each trigger fires on a fixture that satisfies only that condition, and stays silent when the condition is false. An initial relationship profile does not count as a change. A journal entry still `UNKNOWN` does not count as `repeated_failure`. Passthrough emotion never trips `strong_emotion`. A disabled runtime checkpoint leaves the new fields `None`. Restoring a cursor preserves `last_reflection_tick` so the next gap is deterministic.
  - Files: `src/agents/cognition/reflection.py`, `src/simulation/agent_runtime.py`, `src/simulation/run_control.py`, `tests/unit/test_reflection_triggers.py`.
  - Logging requirements: DEBUG `reflection_triggers` with owner id, tick, mode, matched trigger codes, and gap. INFO `reflection_skipped` with reason `disabled`, `min_gap`, or `no_trigger`. DEBUG `reflection_decision_recorded` with command kind and outcome code only. ERROR `reflection_cursor_rejected` with reason code `owner_mismatch`. Never log observation narrative or occurrence facts.
  - Dependencies: Task 1.

- [x] Task 5: Run one reflection pass after the command is chosen and commit it in finalize.
  - Deliverable: Add `reflection: object | None = None` on `CognitiveLoopResult`. In `CognitiveLoop.complete`, after memory update and optional sleep consolidation, call `ReflectionEngine` only when `CognitionReflectionMode` is `DETERMINISTIC` or `LLM_ASSISTED` and Task 4 reports a trigger. Pass the owner snapshot, prepare-stage `SelfModel`, pending subjective intents, occurrences, emotional evaluation, cursor, and journal, excluding the current tick's still-`UNKNOWN` decision record from pattern evidence. Drop a conclusion whose belief id is in `OfflineConsolidationPlan.belief_revisions`, whose relationship pair is in `relationship_revisions`, or whose goal id is in `goal_intents`. Set `CognitiveLoopResult.reflection`. Thread belief revisions, relationship revisions, and goal intents through the existing pending batch. `AgentRuntime.finalize_pending` applies them after successful `resolve_tick`, then sets `last_reflection_tick` and acknowledged goal ids. Journal append and first-seen relationship ordinals still happen when no pass runs. Abort discards the plan and the uncommitted journal update. Attach `reflection_audits` on the in-memory `SimulationRunnerResult` without a `runner-result` schema bump. `DISABLED` performs no reflection calls and adds no boundary records.
  - Expected behavior: The command submitted on the reflection tick is identical to the disabled arm. After finalize, the next snapshot contains the new belief, hypothesis, relationship revision, or goal, and the following loop can select a different command. A belief conclusion is absent when consolidation already revises that belief id. A repeated finalize with the same `reflection:{tick}:{evidence_root}` operation id does not double-apply. If resolve fails, stores and the cursor stay unchanged. A quiet tick writes no conclusions and does not move `last_reflection_tick`.
  - Files: `src/agents/cognition/loop.py`, `src/agents/cognition/reflection.py`, `src/simulation/agent_runtime.py`, `src/simulation/runner.py`, `src/simulation/runner_models.py`, `tests/unit/test_reflection_runtime.py`.
  - Logging requirements: Use stdlib logging on `agents.cognition.reflection`. INFO `reflection_skipped` as in Task 4. DEBUG `reflection_pending` and `reflection_applied` with mode, trigger codes, and counts by conclusion kind. ERROR `reflection_aborted` with reason code when apply fails. Do not attach claim bodies. World resolution logs stay unchanged.
  - Dependencies: Tasks 2, 3, and 4.

- [x] Task 6: Add LLM-assisted selection over the deterministic candidate set.
  - Deliverable: Add prompt package `src/llm/prompts/reflection/v1/` (`manifest.json`, `system.txt`, `user.txt`) and schema `reflection.selection.v1` containing only candidate-id lists. `LLMReflectionSelector` calls `LLMProvider.generate` only when mode is `LLM_ASSISTED`. The runner sets `allow_provider=True` only for that mode. Validate that every returned id is in the candidate set. On missing provider, disallow, transport error, schema failure, or foreign id, apply the deterministic selection and record `fallback_used`. Inject the provider the same way as `LLMOfflineConsolidationSelector`. Do not compose providers in API lifespan.
  - Expected behavior: A fake provider that returns a legal subset changes which conclusions apply and still cannot introduce a new evidence id, predicate, or prose claim. A fake provider that returns an unknown id falls back with no extra writes. `LLM_ASSISTED` without a bound provider falls back and still leaves the current tick's command unchanged.
  - Files: `src/llm/prompts/reflection/v1/*`, `src/agents/cognition/reflection.py`, `src/simulation/runner.py`, `tests/unit/test_reflection_llm.py`, `tests/fakes/` as needed.
  - Logging requirements: DEBUG `reflection_llm_start` / `_complete` with prompt version, schema version, candidate counts, selected counts, `used_provider`, and `fallback_used`. ERROR `reflection_llm_rejected` with reason code `foreign_id`, `schema_invalid`, or `provider_error`. Never log prompts, completions, or candidate narratives. Match the `llm` metadata allowlist. Tests that assert these records filter `caplog` to `agents.cognition.reflection`.
  - Dependencies: Tasks 3 and 5.

### Phase 3: Decision Proof, Experiment, and Docs

- [x] Task 7: Prove reflection changes the next decision and does not rewrite objective history.
  - Deliverable: Add a paired runtime test. Both arms share seed, observation, and seeded memories whose cited `MemoryRelation.predicate` is already `is_dangerous` or `is_safe` from the closed sets in `src/agents/cognition/imagination.py`. The default retriever does not compile those traces into that belief, and decision records alone do not. The deterministic arm's policy copies that predicate into a belief. Assert the reflection tick admits the same command in both arms, the committed `WorldEvent` hashes through that tick match, and applying the subjective plan leaves those hashes and the objective revision unchanged. Assert the next cognitive pass admits a different command type only on the reflecting arm. Add an architecture assertion that `agents.cognition.reflection` does not import `world.events`, `simulation.replay`, or `simulation.journal`. Add a provenance test that drops a candidate citing an id outside the context, drops a `BeliefRevisionRequest` built from a decision-record id, and does not replace a false memory with a fact present only in world state.
  - Expected behavior: The disabled arm's following command matches its reflection-tick command type. The deterministic arm's following command differs because of the copied belief. Prior event hashes stay equal after the subjective commit. A conclusion with a foreign evidence id is absent from the applied batch. A journal-only pattern does not produce a belief. The world is not consulted to correct the false memory.
  - Files: `tests/unit/test_reflection_decision_divergence.py`, `tests/unit/test_reflection_no_world_events.py`, `tests/architecture/test_cognitive_loop_isolation.py` or the existing subjective/objective boundary module.
  - Logging requirements: Tests may assert metadata fields (`mode`, trigger codes, `fallback_used`, conclusion counts). They must not require payload logging. Architecture checks are import-graph checks, not log checks.
  - Dependencies: Task 5.

- [x] Task 8: Add Experiment G and metric family `reflection@1`.
  - Deliverable: Add `reflection_mode` to `_with_agent_modes` in `src/experiments/catalog.py`. Add `experiment_g_reflection` with arms `g-disabled` (`ReflectionMode.DISABLED`, `runner-config-v4`) and `g-deterministic` (`DETERMINISTIC`, `runner-config-v6`) using the default `ReflectionPolicy` (`interval_ticks` 8). Set `max_ticks` so the elapsed trigger can fire. Do not preload Task 7 memories, and do not require a later command to change. Do not enable consolidation or capability flags. Export the builder from `src/experiments/__init__.py`. Do not add the experiment to the V1 regression catalog tuple. Harvest `reflection_audits` into `MetricComputationInputs` the same way as consolidation audits, without adding them to `runner-result-v2`. Add `MetricFamilyId` for reflection, bump `METRIC_FAMILY_COUNT` from 17 to 18, and update `_BUILDERS` plus catalog validation tests. Implement `src/analysis/reflection_metrics.py` with quantized values `reflection_invocations`, `belief_revisions`, `hypotheses`, `goals_adopted`, `goals_abandoned`, `relationship_reassessments`, and `patterns_detected`. Empty or disabled input follows the catalog's existing absent/empty convention. Metrics stay in `analysis`.
  - Expected behavior: Both arms share an objective hash through the reflection tick. The disabled arm stays schema v4 with no reflection audit. The deterministic arm is schema v6 and records an audit once the default interval elapses. Re-running either arm is deterministic. Metric counts match the audits. V1 catalog assembly still succeeds when the report is missing. Command-type divergence stays in Task 7.
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, `src/experiments/composition.py`, `src/experiments/collectors.py`, `src/analysis/specifications.py`, `src/analysis/reflection_metrics.py`, `src/analysis/metric_service.py`, `src/analysis/__init__.py`, `tests/unit/test_experiment_definitions.py`, `tests/unit/test_reflection_experiment.py`, `tests/unit/test_metric_specifications.py`.
  - Logging requirements: Experiment construction DEBUG logs experiment id, condition ids, and reflection mode strings only. DEBUG `reflection_metrics_assembled` with family id and which value keys are present. Never log belief text or memory content.
  - Dependencies: Tasks 2 and 5.

- [x] Task 9: Document reflection and the metadata-only log allowlist.
  - Deliverable: Update `docs/cognition-runtime.md`, `docs/memory-reconstruction.md`, `docs/experiments.md`, `docs/analysis-metrics.md`, and `docs/llm-providers.md`. Describe the mode table, the seven triggers, the minimum gap, the structured pattern table (which codes become beliefs and which become goal intents), evidence-id provenance, LLM candidate restriction, Experiment G, and the rule that reflection does not read `WorldEvent`s. Note that fatigue, sleep consolidation, and capability flags are unchanged, and that v6 may also carry consolidation. This task is the documentation checkpoint for Docs: yes; keep the docs aligned with shipped behavior and route wording through `/aif-docs` during implementation.
  - Expected behavior: A reader can configure `DISABLED`, `DETERMINISTIC`, and `LLM_ASSISTED`, see which schema version is written, and see why a later command can change while earlier event hashes stay. `test_v1_regression_gate.py` passes without Experiment G. Docs list the metadata-only allowlist for the new log event names.
  - Files: `docs/cognition-runtime.md`, `docs/memory-reconstruction.md`, `docs/experiments.md`, `docs/analysis-metrics.md`, `docs/llm-providers.md`.
  - Logging requirements: Docs describe DEBUG/INFO/ERROR event names and the ban on claim text, prompts, and occurrence narratives. Tests from earlier tasks remain the enforcement.
  - Dependencies: Tasks 5–8.

## Verification checklist

- [ ] Default `ReflectionMode.DISABLED`; default write stays `runner-config-v4`; A–E trajectory hashes and v4 fingerprints stay unchanged
- [ ] `runner-config-v5` still means consolidation-only; a non-disabled consolidation mode is also legal on `runner-config-v6`; v6 is accepted only when some agent enables reflection, and that document round-trips names, flags, and cognition trace
- [ ] `V2CapabilityFlags`, cognition-trace schema, and `runner-result-v2` are unchanged; no new Alembic revision
- [ ] Reflection does not run on ticks inside the minimum gap, and `DISABLED` never calls the engine
- [ ] Conclusions cite only subjective evidence and do not import or query `WorldEvent`s
- [ ] `LLM_ASSISTED` selects only candidate ids and falls back when validation fails
- [ ] The reflection tick's command and committed event hashes match the disabled arm; a later command can differ; those earlier hashes stay unchanged after the subjective write
- [ ] Experiment G compares `g-disabled` and `g-deterministic` under a shared seed
- [ ] `reflection@1` assembles from audits; missing reports do not break V1 metric assembly
- [ ] Logs for the new path are metadata-only
- [ ] Each commit runs `ruff check` on the full plan diff, including `tests/fakes/` and `CognitiveLoop` signature stubs
