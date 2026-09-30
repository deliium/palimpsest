# Implementation Plan: Learnable Agent Skills

Branch: main
Created: 2026-09-30

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete roadmap milestone; this plan adds an opt-in skill-learning mode and leaves `multi_hop_testimony_tracking` unowned.

## Compatibility contract

This plan adds objective skill levels and a separate subjective competence model. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only mutation authority. Objective skill levels change an action's success probability or efficiency only inside explicit engine resolution. Cognition never receives `WorldState`, `PhysicalRules`, the objective ledger, or another agent's competence model.
2. Do not own a capability flag. Do not add a `V2CapabilityFlags` field. `multi_hop_testimony_tracking` stays unimplemented and still fails closed with `capability_unimplemented`. Owned flags stay owned. Off for this feature is `SkillLearningMode.DISABLED`, which does not change probabilities, fatigue, help gain, commands, memories, beliefs, or audits.
3. V1 regression gate stays green under flags-off, skill mode `DISABLED`, and tracing-off. Catalog A–E and the reference scenario keep their current `exact_trajectory_hash` values. Experiment R is additive and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. `runner-config-v11` is the only new runner schema. It is emitted only when some agent's `SkillLearningMode` is `DETERMINISTIC`. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. v11 cognition keys are the v10 key set plus `skill_learning_mode` and the locked rate keys below. Do not add a new event schema. `EVENT_SCHEMA_VERSION` stays replay-v5.
5. No scripted emergence. Skill domains are closed tokens. There is no profession, role, or culture label, and no new `AgentCommand`.
6. No LLM → world shortcuts. Subjective ranking may use `StructuredOutput` only to choose domain tokens already on the owner's model. The provider never emits a probability, a skill level, an `AgentCommand`, or a world mutation.
7. Experiments stay reproducible. Experiment R arms share seed, scenario, and stochastic identity. Analysis comparison runs after the run and is not fed back into cognition or into the engine.
8. Optional cognition tracing stays outside the objective fold. Do not insert a `ComponentKind` or an ordinal in `_STAGE_ORDER`. Do not add a `CognitionTraceStageKind`. Do not bump `COGNITION_TRACE_SUMMARY_SCHEMA`, add `CognitionTraceCountKey` or `CognitionTraceRefKind` members, or add an Alembic revision. Do not emit a skill trace stage. Tracing on versus off must not change `exact_trajectory_hash` when skill mode is off.

## Goal

Give each agent eight learnable skills. Objective capability and the agent's belief about that capability are different stores and may disagree.

Closed domains:

- `foraging`
- `navigation`
- `resource_detection`
- `crafting`
- `building`
- `healing`
- `communication`
- `teaching`

Objective levels live in a private ledger folded from committed events. Only `WorldEngine` reads that ledger, and only while resolving an action that already has a probability or an efficiency constant. Subjective competence lives on the owner. It is updated from that owner's observation of practice, success, failure, instruction, and witnessed success. It may bias which existing command the agent attempts. It must not change the Bernoulli draw or the efficiency constant.

## Design Decisions (locked)

- **Mode, not a flag.** `SkillLearningMode` is `DISABLED` or `DETERMINISTIC`, on `AgentCognitionSpec` and lockstep with `CognitionSkillLearningMode`. Default `DISABLED`. `simulation.runner._cognition_config_for` builds `default_competence_belief_policy()` only when the mode is `DETERMINISTIC`. The runner passes one shared `ObjectiveSkillPolicy` into `WorldEngine` as an optional argument that defaults to `None`. `None` builds no ledger and does not call the adjustment helpers. Do not add the policy to `SimulationRunConfig`. That config stays seed, physical rules, derivation version, and stochastic identity, so disabled runs keep their current run ids and world-snapshot bytes.
- **Two policies, one numeric contract.** Objective rates and gains live on `ObjectiveSkillPolicy` in private `world/_skills.py`. Belief rates live on `CompetenceBeliefPolicy` in `agents/cognition/competence.py`. Runner JSON carries both numeric groups on every v11 agent so replay can rebuild them. Every v11 agent must carry the same rate tuple. A mismatch fails closed with `skill_rate_mismatch` before the run starts. The run builds one objective policy and one belief policy from that tuple. The cognition module must not import `world._skills`. The private skill module must not import `agents`. Tests assert both domain enums share the same eight string values.
- **Who is in the ledger.** Modifiers and growth apply only to entity ids whose agent is `DETERMINISTIC`. A `DISABLED` actor in a mixed v11 run uses the bypass formulas and is not written into the ledger. A listener or witness outside that set gains nothing.
- **Level.** A level is a float in `[0, 1]`, quantized after every write with a local `round(value / 1e-6) * 1e-6` in `world/_skills.py` and the same expression in `agents/cognition/competence.py`. Neither module imports the other's helper. `world/_skills.py` does not import `agents`. Tests compare a level to that expression applied to the expected value. They do not compare it to the raw literal `0.07`: `quantize(0.02 + 0.05) == 0.07` is false, and `quantize(0.02 + 0.05) == quantize(0.07)` is true. Initial level for every domain on every enabled body is `0`. Dead bodies do not gain. There is no birth; bootstrap initializes every enabled body.
- **Identity at zero, and a true bypass when off.** When mode is `DISABLED`, search, move, flee, and help call today's formulas and do not call the adjustment helpers. When mode is `DETERMINISTIC` and the relevant level is `0`, the helper returns the same value the current formula produces, and search still uses `PHYSICAL_PURPOSE_SEARCH_SUCCESS` (`search_success`). Do not add a named RNG purpose. A new purpose would change the stream even when the probability matches.
- **Search split.** Untargeted `Search` (`target_id is None`) is `foraging`. Targeted `Search` is `resource_detection`. Foraging multiplies only `search_base_probability`. Resource detection multiplies only the visibility term. At level 0 the sum equals today's `clamp_unit_interval(search_base_probability + search_visibility_weight * visibility)`.
- **Efficiency hooks that exist today.** Navigation divides `move_fatigue` and `flee_fatigue` by `(1 + efficiency_gain * navigation_level)` before `round_physical`. Healing multiplies `help_health_gain` by `(1 + efficiency_gain * healing_level)` before `round_physical`. Helper fatigue is unchanged. At level 0 both equal the current constants (`5.0`, `10.0`, and `10.0`).
- **Domains with no matching rule.** `crafting`, `building`, and `communication` have objective growth and subjective beliefs, and their probability/efficiency multiplier is exactly `1`. This plan does not add Craft, Build, or a communication miss. `teaching` does not change talk delivery. It scales instruction transfer, defined below.
- **Growth is a fold of committed facts.** One tick uses start-of-tick levels for every modifier and every transfer, and the start-of-tick `WorldState` for witnesses. Deltas for that tick are summed per body and domain, quantized once, then clamped to `[0, 1]`. No intra-tick compounding. Same-tick moves do not change the witness set. Replay groups committed events by tick, projects only earlier ticks, then folds tick T against that start-of-tick state with the v11 policy. The ledger is not a field on `AgentBody` and is not written on `Observation`. The next ledger lives on the detached tick candidate and is published only when the tick finalizes. An aborted prepare leaves the previous ledger in place.
- **Channels.**
  - Practice: an admitted applied action (`BatchItemStatus.APPLIED` only). Untargeted search → `foraging`. Targeted search → `resource_detection`. `Move` and `Flee` → `navigation`. `Help` → `healing`. Delivered `Talk`, `Ask`, or `Tell` → `communication` on the speaker. A delivered utterance that is also an instruction additionally practices `teaching` on the speaker. `REJECTED`, `CONFLICTED`, and `DEFERRED_POLICY` add nothing.
  - Success: stochastic `Searched.success is True`, `Fled.success is True`, applied `Move`, applied `Help`, delivered talk/ask/tell. Adds `success_rate` on the practiced domain.
  - Failure: stochastic `Searched.success is False` or `Fled.success is False` only. Adds `failure_rate` on the practiced domain. A rejected action is not a failure.
  - Instruction: a delivered utterance with exactly one relation on `utterance.content.relations`, predicate `instruct`, and object equal to one domain token. The listener is `Talked`, `Asked`, or `Told.recipient_id`. Anything else is not instruction. Transfer to the listener is `instruction_rate * teacher_teaching_level` using the teacher's start-of-tick teaching level. A teacher at `0` transfers `0` and still receives teaching practice. Do not read utterance text.
  - Observation: another living enabled body in the start-of-tick `WorldState` whose `location_id` equals the action's `origin_location_id`, when that location's effective visibility is `>= 0.5`, and only when the occurrence is a successful public action: untargeted search, targeted search, move, flee, or help. The witness gains `observation_rate` on that action's domain. Misses are not copied. `Talk`, `Ask`, and `Tell` are recipient-private and do not use this channel, including for a co-located bystander. `crafting` and `building` are not observed from actions. Crafting and building grow only through instruction.
- **Deltas, before clamp.** `practice_rate + success_rate` on success, `practice_rate + failure_rate` on stochastic failure, instruction as above, observation as above. Attack does not practice a skill.
- **Subjective model is not the ledger.** `CompetenceSelfModel` stores, per domain, believed level, support mass, and counter mass. `believed = support / (support + counter + prior)`, quantized into `[0, 1]`. It is updated only from the owner's `Observation` and reconstructions already retrieved for that owner. Passing `WorldState`, `ObjectiveSkillLedger`, or `ObjectiveSkillPolicy` into the updater raises `TypeError`. Identity `competence` / `ability` claims stay on `extended_self_model`. This plan does not emit `BeliefRevisionRequest` and does not enable that flag.
- **Belief defaults diverge on purpose.** Support mass after one own successful untargeted search is `belief_success_rate` (`0.10`). Counter mass stays `0` for this plan. Believed level is `quantize(0.10 / 1.10)`, not `0.10`. Objective foraging for that success is `quantize(0.07)`. After one own missed untargeted search, objective foraging is `quantize(0.03)` and believed support stays `0`, so believed level stays `0`, because `belief_failure_rate` is `0`. Objective growth is visible at the end of tick T. Belief moves on prepare of tick T+1, when that occurrence is on the owner's `Observation`. Same-tick belief is unchanged.
- **Selection bias only.** `_compare_pair` adds `(left_term - right_term)` to its integer vote total before the sign check. The term is `belief_action_weight * believed_level` for that future's existing direction: untargeted `SEARCH` is `foraging`, targeted `SEARCH` is `resource_detection`, `MOVE` and `FLEE` are `navigation`, `HELP` is `healing`, `COMMUNICATE` is `communication`. `crafting`, `building`, and `teaching` do not change a score or a command. This is a float difference, not a new `±1` vote. The maximum term is `0.25`, so a nonzero integer total still wins. `_critical_vetoes` stays earlier and unchanged. Search preference runs in `_compile_command` among `SEARCH` futures already legal on the observation: prefer untargeted search when believed foraging exceeds believed resource detection, and targeted search when the reverse holds. `None` model leaves the total unchanged. Bias does not change engine inputs. A test with believed foraging `1` and objective foraging `0` must draw the level-0 search probability.
- **Caps and identity.** Each domain cursor stores occurrence ids already on the owner's `Observation`, caps at 32 by dropping the oldest, and skips an id already stored. Domain id is the token string. No RNG, wall clock, or Python `hash()` in either update.
- **Checkpoint.** Do not add a skill key to world-snapshot JSON and do not edit `src/simulation/journal.py`. Decode there uses an exact key set and rejects an unknown field with `unknown_field`. On resume, group committed events by tick. For tick T, project events from earlier ticks, then apply the growth rules to that start-of-tick state. Enabled entity ids come from the v11 runner config. `simulation/replay.py` passes that policy into `restore_from_snapshot`. A caller-supplied ledger that disagrees fails with `skill_ledger_mismatch`. Disabled runs skip the refold and pass neither argument. Subjective model is an optional field `competence_model` on the in-memory `AgentRuntimeCheckpoint`, default `None`, copied in `export_runtime_checkpoint` and `restore_runtime_checkpoint` the same way `reputation` is. Do not bump a subjective schema and do not add an Alembic revision. Do not add either store to `subjective-v1`.
- **Audits.** `SkillAudit` is in-run and analysis-only on `SimulationRunnerResult`, same durability style as `WorldModelAudit`: in-memory, default empty, not a field on `SimulationRunnerResultDocument`, so runner-result serialization omits it. Both sides use `agent_id`. The objective ledger stays keyed by entity id; the audit row copies the registration's agent id. Each row is agent id, side (`objective` or `subjective`), domain token, quantized level, and tick. No utterance text.
- **Trace view.** Do not emit a skill trace stage. `BELIEFS` and `THEORY_OF_MIND` are already owned, and a new `CognitionTraceStageKind` would bump the trace schema.
- **LLM grounding.** `CompetenceBeliefPolicy.allow_provider` defaults to false. `allow_provider=True` calls `LLMProvider.generate` only through schema `competence.selection.v1` and prompt package `llm/prompts/competence/v1/`. The payload is domain tokens and quantized believed levels already computed. The schema returns a subset of those tokens. Unknown tokens, missing provider, transport error, or schema failure keep the deterministic ranking and set `fallback_used`. Import the `llm` facade from `agents.cognition.competence_selection` only. Do not import `llm.models` from a module that simulation loads. `competence.py` does not import the selection module. `CognitiveLoop` imports it only when `allow_provider` is true. Add `agents.cognition.competence_selection -> llm` to the Pydantic forbidden-import contract's `ignore_imports` in `pyproject.toml`.
- **Fail closed.** Unknown domain tokens, non-finite rates, negative objective rates, levels outside `[0, 1]` before clamp, owner mismatch, and a listener who is not the recipient are dropped with stable reason codes or rejected at policy construction. A bad cue is dropped, not repaired from the world.

### Locked v11 numbers

Objective (`ObjectiveSkillPolicy`, version `objective-skill-v1`):

| Key | Default |
| --- | --- |
| `practice_rate` | `0.02` |
| `success_rate` | `0.05` |
| `failure_rate` | `0.01` |
| `instruction_rate` | `0.04` |
| `observation_rate` | `0.01` |
| `probability_gain` | `0.50` |
| `efficiency_gain` | `0.50` |

Search at foraging level `1`, detection level `0`: base term times `1.5`, visibility term unchanged, then `clamp_unit_interval`. Move fatigue at navigation level `1`: `5.0 / 1.5` before `round_physical`. Help gain at healing level `1`: `10.0 * 1.5` before `round_physical`.

Subjective (`CompetenceBeliefPolicy`, version `competence-belief-v1`):

| Key | Default |
| --- | --- |
| `belief_practice_rate` | `0.00` |
| `belief_success_rate` | `0.10` |
| `belief_failure_rate` | `0.00` |
| `belief_instruction_rate` | `0.08` |
| `belief_observation_rate` | `0.02` |
| `belief_prior` | `1.0` |
| `belief_action_weight` | `0.25` |

All objective rates and gains are finite and `>= 0`. Belief rates are finite and `>= 0`. `belief_action_weight` is finite and in `[0, 1]`. `probability_gain` and `efficiency_gain` are finite and in `[0, 1]`.

## Non-Goals

- Owning `multi_hop_testimony_tracking` or adding any `V2CapabilityFlags` field
- Adding an `AgentCommand`, an `ActionDirection`, a `CommunicationSourceBasis`, or replay-v6
- Crafting, building, or communication probability rules with no existing world constant
- Putting skill levels, inventories, or utterance text on `Observation` or in logs
- Letting subjective belief, identity `competence`, or reputation `competence` change a Bernoulli input or an efficiency constant
- Letting the agent read or copy another agent's objective ledger or competence model
- Feeding `skill_learning@1` back into cognition or into engine resolution
- Enabling `extended_self_model`, prospective, counterfactual, emotion, world-model, or theory-of-mind flags as a side effect of this mode
- Putting Experiment R on the V1 regression gate
- Adding a world-snapshot or journal key for the objective ledger
- Adding a `CognitionTraceStageKind` or emitting a skill trace stage

## Commit Plan
- **Commit 1** (after tasks 1–2): `feat(world): add opt-in skill levels and learning rates`
- **Commit 2** (after tasks 3–5): `feat(engine): apply skill rules and fold practice into levels`
- **Commit 3** (after tasks 6–8): `feat(cognition): track competence beliefs apart from skill`
- **Commit 4** (after task 9): `docs(simulation): document learnable skills and competence beliefs`

## Tasks

### Phase 1: Contracts and Runner Schema

- [x] Task 1: Add objective skill contracts and subjective competence contracts.
  - Deliverable: frozen types and pure helpers. No engine wiring yet.
  - Objective, private module `src/world/_skills.py`: `SkillDomain` (`foraging`, `navigation`, `resource_detection`, `crafting`, `building`, `healing`, `communication`, `teaching`), `ObjectiveSkillLedger` (entity id → eight quantized levels), `ObjectiveSkillPolicy` with the locked defaults and version `objective-skill-v1`. Helpers `adjusted_search_probability`, `adjusted_move_fatigue`, `adjusted_flee_fatigue`, `adjusted_help_gain`, and `growth_delta` implement the identity-at-zero formulas and the channel deltas. Export nothing from `world/__init__.py`.
  - Subjective, `src/agents/cognition/competence.py`, exported from `src/agents/cognition/__init__.py`: `CompetenceDomain` with the same eight values, `CompetenceBelief`, `CompetenceSelfModel`, `CompetenceBeliefPolicy` (`competence-belief-v1`, locked belief defaults, `allow_provider=False`), `CognitionSkillLearningMode` (`DISABLED`, `DETERMINISTIC`) in `src/agents/cognition/configuration.py`.
  - Constructors reject unknown domains, non-finite numbers, and out-of-range gains with stable reason codes. Quantize with a local `round(value / 1e-6) * 1e-6` in each module. `world/_skills.py` does not import `agents` or the helper in `agents/cognition/deliberation.py`. `competence.py` does not import `world._skills`. Counter mass stays `0`.
  - Tests prove level `0` search equals `clamp_unit_interval(base + weight * visibility)` for a fixed visibility `0.5`, level `0` move fatigue equals `5.0`, level `0` flee fatigue equals `10.0`, and level `0` help gain equals `10.0`. Success bundle: objective level `== quantize(0.07)` and belief support is `0.10`, so believed level `== quantize(0.10 / 1.10)`. Failure bundle: objective level `== quantize(0.03)` and belief support stays `0`. Do not assert `== 0.07` or `== 0.10` against the raw literals.
  - Logging: logger `world._skills` and `agents.cognition.competence`. DEBUG on construction with policy version and domain count. ERROR with field name and reason code on validation failure. The construction test asserts those DEBUG tokens and the ERROR `reason_code`. No levels at INFO.
  - Files: `src/world/_skills.py`, `src/agents/cognition/competence.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/__init__.py`, `tests/unit/test_objective_skills.py`, `tests/unit/test_competence_belief.py`.

- [x] Task 2: Add `runner-config-v11` and keep the disabled path free of skill state.
  - Deliverable: a non-disabled `skill_learning_mode` is legal only on v11, and v11 requires some agent in `DETERMINISTIC`. v10 and earlier reject the new keys. Default write stays `runner-config-v4`. `SkillLearningMode` on `AgentCognitionSpec` in `src/simulation/runner_models.py` locksteps with `CognitionSkillLearningMode`. v11 exact keys are the v10 cognition key set plus `skill_learning_mode`, `practice_rate`, `success_rate`, `failure_rate`, `instruction_rate`, `observation_rate`, `probability_gain`, `efficiency_gain`, `belief_practice_rate`, `belief_success_rate`, `belief_failure_rate`, `belief_instruction_rate`, `belief_observation_rate`, `belief_prior`, `belief_action_weight`.
  - Keep the existing reason codes. Add v11 to the allowed version set for consolidation, reflection, prospective simulation, counterfactual mode, communication strategy, and reputation. The reputation check in `src/simulation/runner_models.py` currently requires exactly v10 (`reputation_mode_requires_v10`). Change that comparison, and the matching checks for the other modes, so a non-disabled mode stays legal on its current schema and on v11. A reputation-only config still writes v10. A config with both reputation and skill learning writes v11. Do not add a `V2CapabilityFlags` field. Mirror the version sets in `src/simulation/runner_serialization.py` and `src/simulation/compatibility.py`.
  - Every v11 agent carries the same rate tuple. Differing rates fail closed with `skill_rate_mismatch` before bootstrap. The run builds one `ObjectiveSkillPolicy` and one `CompetenceBeliefPolicy` from that tuple. `simulation.runner._cognition_config_for` sets the cognition mode from `skill_learning_mode` and passes `default_competence_belief_policy()` only when it is `DETERMINISTIC`. Do not store the policy on `SimulationRunConfig`.
  - `v1_regression_profile` still rejects only enabled capability flags and enabled tracing. Catalog A–E stay on `runner-config-v4` with skill mode `DISABLED`.
  - Keep `RUNNER_SCHEMA_VERSION` equal to `runner-config-v4` so `tests/unit/test_compatibility_matrix.py` stays green. Round-trip the v11 key set in `tests/unit/test_runner_serialization.py`. Run `uv run ruff check` on every file this task touches.
  - Logging: existing runner DEBUG style, logger `simulation.runner`, one line `cognition_config_skill_learning_mode mode=%s policy_version=%s`. ERROR `skill_rate_mismatch` with agent count and reason code, not the rate values. Do not log rate values. The unit test asserts `mode=` and `policy_version=` on the DEBUG line and `reason_code=skill_rate_mismatch` on the error.
  - Depends on task 1.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/__init__.py`, `src/simulation/runner.py`, `src/agents/cognition/configuration.py`, `tests/unit/test_runner_models.py`, `tests/unit/test_runner_serialization.py`, `tests/unit/test_v2_flag_defaults.py`, `tests/unit/test_simulation_runner_construction.py`.

### Phase 2: Objective Resolution, Growth, and Replay

- [x] Task 3: Apply skill modifiers only inside WorldEngine resolution.
  - Deliverable: disabled runs keep today's search probability, move fatigue, flee fatigue, and help gain code paths. Enabled actors read the start-of-tick ledger.
  - `WorldEngine` stores state in `__slots__`. Add the policy, enabled entity ids, and ledger there. `__init__` and `restore_from_snapshot` both gain those optional keywords, default `None`. `None` keeps today's formulas and builds no ledger. Existing restore callers pass neither argument and stay on the absent path. The runner passes the shared `ObjectiveSkillPolicy` plus the entity ids whose mode is `DETERMINISTIC`. Do not add the policy to `SimulationRunConfig`. A `DISABLED` actor in a mixed run uses the bypass path.
  - Compute the next ledger on `_PreparedTickCandidate`. Publish it only in `_finalize_tick_candidate`. `resolve_tick` rolls back `_snapshot` on abort and must leave the previous ledger in place.
  - When the policy is present, pass the adjusted search probability into the existing `sample_bernoulli` call in `_resolve_search_effect` on `PHYSICAL_PURPOSE_SEARCH_SUCCESS`. Pass adjusted move fatigue, flee fatigue, and help gain into `_mutate_move`, `_mutate_flee`, and `_mutate_help` as optional keywords. When the keyword is absent, those functions keep `rules.move_fatigue` (`5.0`), `rules.flee_fatigue` (`10.0`), and `rules.help_health_gain` (`10.0`). Do not import the ledger from cognition.
  - Seeded test: two runs, same seed, mode on, fixed ledger levels, identical success bits and identical resulting fatigue and target health. Same seed with mode off matches the current unadjusted search stream. A ledger at all zeros matches the mode-off search bit and the mode-off fatigue and help numbers. A mixed run adjusts only the enabled actor.
  - A high subjective belief cannot be passed into `_resolve_search_effect`. The resolver accepts only the objective ledger. Passing a `CompetenceSelfModel` raises `TypeError`.
  - Logging: logger `simulation.engine`. DEBUG `skill_modifier tick=%s entity_id=%s domain=%s level=%s outcome=%s` with the quantized level and `success` or `miss` or `efficiency`. ERROR with reason code if the ledger is missing a domain while that actor is enabled. Do not log the probability, the RNG draw, inventories, or seeds. `tests/unit/test_skill_resolution.py` asserts those DEBUG tokens and the ERROR `reason_code`.
  - Depends on tasks 1 and 2.
  - Files: `src/simulation/engine.py`, `src/simulation/runner.py`, `src/world/_rules.py`, `src/world/_skills.py`, `tests/unit/test_skill_resolution.py`.

- [x] Task 4: Fold practice, success, failure, instruction, and observation into the objective ledger.
  - Deliverable: `fold_skill_growth(ledger, applied_actions, policy, *, world_state, tick, rules) -> ObjectiveSkillLedger` in `src/world/_skills.py`. Call it from `_resolve_ordered` after `prepare_action_batch` and before `apply_autonomous_physical_step`, passing `snap.world.state`, that tick, and the physical rules. Levels, transfers, and witnesses all come from that start-of-tick state, not from `pending.working_state`.
  - Only `BatchItemStatus.APPLIED` grows a skill. `REJECTED`, `CONFLICTED`, and `DEFERRED_POLICY` add nothing.
  - Instruction recognition reads `utterance.content.relations`: exactly one relation, predicate `instruct`, object equal to one domain token. The listener is `Talked`, `Asked`, or `Told.recipient_id`. Do not read utterance text. The speaker, when enabled, gains teaching practice and success. The private recipient, when enabled, gains `instruction_rate * start_of_tick_teaching_level`. A first lesson from a teacher at `0` leaves the listener unchanged and raises the teacher's teaching level to `quantize(0.07)`. A co-located bystander does not gain from the utterance.
  - Witnesses are living enabled bodies in that start-of-tick state whose `location_id` equals the action's `origin_location_id`. Same-tick moves do not change the set. Effective visibility of that location uses the existing rules and the `0.5` threshold. Only a successful public action applies `observation_rate`: untargeted search, targeted search, move, flee, or help. The actor does not observe their own action. A second enabled witness at that origin gains the same delta. `Talk`, `Ask`, and `Tell` never use this channel.
  - Tests compare levels with `quantize(...)`, not with the raw literals. Cover one untargeted search success (`foraging == quantize(0.07)`), one targeted search miss (`resource_detection == quantize(0.03)`), one help (`healing == quantize(0.07)`), one move (`navigation == quantize(0.07)`), one plain talk (`communication == quantize(0.07)`, teaching unchanged, bystander unchanged), the zero-teacher instruction case, a visible public witness, a witness below visibility `0.5` who gains nothing, a disabled actor who gains nothing, and a rejected move that gains nothing. Attack changes no domain.
  - Logging: logger `world._skills`. DEBUG `skill_growth tick=%s entity_id=%s domain=%s channel=%s delta=%s` with channel in `practice`, `success`, `failure`, `instruction`, `observation`. DEBUG drop reasons `not_instruction`, `unknown_domain`, `not_visible`, `rejected`, `private_utterance`, `actor_disabled`. No utterance text. `tests/unit/test_skill_growth.py` asserts those tokens.
  - Depends on task 3.
  - Files: `src/world/_skills.py`, `src/simulation/engine.py`, `tests/unit/test_skill_growth.py`.

- [x] Task 5: Rebuild the ledger by refolding projected events.
  - Deliverable: replay and restore of an enabled run reproduce the live ledger. World-snapshot JSON gains no skill key. Do not edit `src/simulation/journal.py`. Its decode rejects an unknown field with `unknown_field`.
  - Group committed events by tick. For tick T, project only events from earlier ticks, then run the task 4 fold against that start-of-tick state. Do not project an earlier move from the same tick before listing witnesses. Visibility and co-located witnesses are not on the event. Enabled entity ids come from the v11 runner config. `simulation/replay.py` passes that policy and those ids into `restore_from_snapshot`. A caller-supplied ledger that disagrees with the refold raises `skill_ledger_mismatch`. A disabled restore passes neither argument and skips the refold.
  - Live versus restored observation parity stays green on the disabled path. Enabled-path parity is an additional test, not a change to the V1 gate. That test includes one public search witness and one private `instruct` utterance so the refold is not only an action fold.
  - Logging: logger `simulation.engine`. INFO `skill_ledger_restored entity_count=%s domain_count=%s` on successful restore. ERROR `skill_ledger_mismatch` with entity id and domain token, without both full ledgers. DEBUG when skill resolution is absent: `skill_ledger=absent`. The restore test asserts those tokens.
  - Depends on task 4.
  - Files: `src/world/_skills.py`, `src/simulation/engine.py`, `src/simulation/replay.py`, `tests/unit/test_skill_replay.py`.

### Phase 3: Subjective Belief, Bias, and Proof

- [x] Task 6: Update competence beliefs from the owner's observation only.
  - Deliverable: `update_competence(model, observation, reconstructions, policy) -> CompetenceSelfModel`. Own success adds `belief_success_rate` to support for the mapped domain. Own stochastic failure adds `belief_failure_rate` (default `0`, so support is unchanged and counter stays `0`). A received private `instruct` relation adds `belief_instruction_rate` to support for that domain, and does not scale by the objective teaching level. A witnessed public success on the same observation adds `belief_observation_rate`. A witnessed `Talk`, `Ask`, or `Tell` does not. Recompute believed level from support, counter, and `belief_prior`.
  - The function signature has no ledger parameter. A test passes a ledger object and expects `TypeError`.
  - Each domain cursor stores occurrence ids already on the owner's `Observation`, caps at 32 by dropping the oldest, and skips an id already stored. A stochastic failure adds `belief_failure_rate` to support. Counter mass stays `0`.
  - Prepare runs before resolution, and an observation for tick N carries tick N−1. Belief therefore moves on the next `CognitiveLoop.prepare`, not on the tick that committed the action. Same-tick belief stays at the prior model. `prepare` calls the updater only when mode is `DETERMINISTIC`. `AgentRuntime.finalize_pending` stores the model computed for this prepare only after a successful `resolve_tick`. Abort discards the tentative model. `DISABLED` leaves the runtime field `None`.
  - Do not emit a skill trace stage. Do not add a `CognitionTraceStageKind`. `BELIEFS` and `THEORY_OF_MIND` stay owned by their current summaries.
  - Checkpoint field `competence_model` on `AgentRuntimeCheckpoint` defaults to `None`. Copy it in `export_runtime_checkpoint` and `restore_runtime_checkpoint` the same way `reputation` is copied. No schema bump.
  - Logging: logger `agents.cognition.competence`. DEBUG `competence_update owner_id=%s domain=%s channel=%s believed=%s` with the quantized believed level. ERROR with reason code on owner mismatch. No objective levels and no utterance text. The update test asserts those tokens, and it asserts believed level `== quantize(0.10 / 1.10)` only on the prepare that receives the prior search.
  - Depends on tasks 1 and 2.
  - Files: `src/agents/cognition/competence.py`, `src/agents/cognition/loop.py`, `src/simulation/agent_runtime.py`, `src/simulation/run_control.py`, `tests/unit/test_competence_update.py`, `tests/unit/test_competence_checkpoint.py`.

- [x] Task 7: Let competence beliefs bias command choice, and prove they do not change world math.
  - Deliverable: `_compare_pair` adds `(left_term - right_term)` to its integer vote total before the sign check. The term is `belief_action_weight * believed_level` for that future's direction: untargeted `SEARCH` → `foraging`, targeted `SEARCH` → `resource_detection`, `MOVE` and `FLEE` → `navigation`, `HELP` → `healing`, `COMMUNICATE` → `communication`. `crafting`, `building`, and `teaching` do not change a score or a command. This is a float difference, not a new `±1` vote. The maximum term is `0.25`, so a nonzero integer total still wins. `_critical_vetoes` stays earlier and unchanged. A `None` model leaves the total unchanged. No new direction and no new command.
  - Search preference runs in `_compile_command` among `SEARCH` futures already legal on the observation: prefer untargeted search when believed foraging exceeds believed resource detection, and targeted search when the reverse holds.
  - `allow_provider=False` never calls the provider. Provider calls live in `src/agents/cognition/competence_selection.py`. Define `CompetenceSelectionOutput(StructuredOutput)` there, importing `StructuredOutput` from the `llm` facade, matching `theory_of_mind_selection.py`. Do not import `llm.models`. Add the prompt package `src/llm/prompts/competence/v1/` for schema `competence.selection.v1`. `competence.py` does not import the selection module. `CognitiveLoop` imports the selection module only inside the `allow_provider` branch. Add `agents.cognition.competence_selection -> llm` to `ignore_imports` on the Pydantic forbidden-import contract in `pyproject.toml`.
  - Proof test: objective foraging level `0`, believed foraging `1`, same seed. The search Bernoulli input equals the level-0 probability and the success bit matches a disabled run that issued the same `Search`. Move fatigue stays `5.0` when objective navigation is `0`, even if believed navigation is `1`.
  - Logging: logger `agents.cognition.competence`. DEBUG `competence_bias owner_id=%s domain=%s believed=%s weight=%s` using the quantized believed level. Do not log the resulting command payload. INFO is not required on the unchanged-score path. ERROR if a belief domain is outside the eight tokens, with `reason_code` on that line. `tests/unit/test_competence_bias.py` asserts those tokens and asserts the line has no probability and no utterance text.
  - Depends on tasks 3 and 6.
  - Files: `src/agents/cognition/deliberation.py`, `src/agents/cognition/competence_selection.py`, `src/agents/cognition/competence.py`, `src/agents/cognition/loop.py`, `src/llm/prompts/competence/v1/`, `pyproject.toml`, `tests/unit/test_competence_bias.py`.

- [x] Task 8: Add seeded learning tests and Experiment R with an analysis-only gap metric.
  - Deliverable: a fixed seed, `DETERMINISTIC` mode, and the default rates produce the same ledger and the same competence model on two full runner invocations. Objective level and believed level are compared at the prepare that follows the search, not on the commit tick. A disabled twin of that scenario keeps the current search bits of an otherwise identical disabled run.
  - Experiment R in `src/experiments/catalog.py` has two arms, shared seed and scenario, skill mode off versus `runner-config-v11`. Extend the catalog helper that copies `reputation_mode` with `skill_learning_mode` so the enabled arm sets `DETERMINISTIC`. It is not added to `tests/unit/test_v1_regression_gate.py`. `v1_regression_profile` stays unchanged.
  - `src/analysis/skill_learning_metrics.py` implements `skill_learning@1`. Bump `METRIC_FAMILY_COUNT` from `25` to `26`, add the family enum, and update the `== 25` assertion in `tests/unit/test_metric_specifications.py`. The metric reads `SkillAudit` rows after the run and joins both sides on `agent_id` plus domain. It stores objective level, believed level, and absolute gap. A missing side sets `empirical_status=unmatched` and does not guess. The metric module must not import `fold_skill_growth` or `update_competence`. The updaters must not import `analysis`.
  - `skill_audits` is a default-empty tuple on `SimulationRunnerResult`, exported the way `world_model_audits` are. Both sides use `agent_id`. The objective ledger stays keyed by entity id; the audit row copies the registration's agent id. It is not a field on `SimulationRunnerResultDocument`, so `encode_runner_result_document` stays unchanged.
  - Logging: logger `experiments.catalog` INFO `experiment_r_built experiment_id=%s arm_id=%s schema_version=%s skill_mode=%s`. Logger `analysis.skill_learning_metrics` DEBUG `skill_gap agent_id=%s domain=%s gap=%s` with the quantized absolute gap. No utterance text and no ledger dumps.
  - Depends on tasks 5, 6, and 7.
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, `src/analysis/skill_learning_metrics.py`, `src/analysis/specifications.py`, `src/analysis/__init__.py`, `src/simulation/runner.py`, `src/simulation/runner_models.py`, `tests/unit/test_skill_learning_experiment.py`, `tests/unit/test_skill_learning_metrics.py`, `tests/unit/test_metric_specifications.py`.

### Phase 4: Documentation

- [x] Task 9: Document objective skill rules and subjective competence.
  - Deliverable: a reader can see that skill changes probability or efficiency only through WorldEngine, that competence beliefs can disagree, and that v11 is opt-in.
  - Update `docs/physical-simulation.md` with the eight domains, the search/move/flee/help formulas, the growth channels, the start-of-tick witness rule, the level-0 identity rule, and the refold that does not add a snapshot key. Update `docs/cognition-runtime.md` with the competence model, the one-tick lag, the `quantize(0.10 / 1.10)` fixture, and the pairwise selection bias. Update `docs/architecture.md` Downstream V2 plan contract with one short paragraph: `SkillLearningMode` defaults to `DISABLED`, `runner-config-v11` is emitted only when that mode is `DETERMINISTIC`, no capability flag was added, and Experiment R plus `skill_learning@1` stay off the V1 regression gate. Update `docs/experiments.md` for Experiment R. Update `docs/simulation-runner.md` so the schema paragraph emits `runner-config-v11` only when some agent's skill mode is `DETERMINISTIC`, keeps the default write at `runner-config-v4`, and accepts reputation and the earlier cognition modes on v11. Update the owned-mode notes in `.ai-factory/DESCRIPTION.md` and `.ai-factory/ARCHITECTURE.md` only where they list runner schema versions, so v11 is mentioned beside v10. Do not mark M6 complete and do not edit `ROADMAP.md` from this plan.
  - Logging: documentation only. No new runtime log lines.
  - Depends on tasks 2 through 8.
  - Files: `docs/physical-simulation.md`, `docs/cognition-runtime.md`, `docs/architecture.md`, `docs/experiments.md`, `docs/simulation-runner.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`.
