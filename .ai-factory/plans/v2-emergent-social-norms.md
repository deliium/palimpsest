# Implementation Plan: Emergent Social Norms

Branch: main
Created: 2026-10-02

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete roadmap milestone. This plan adds an opt-in owner-scoped norm ledger and leaves `multi_hop_testimony_tracking` unowned.

## Compatibility contract

A norm is a private expectation inferred from repeated behavior. The plan must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only mutation authority. `PhysicalRules`, `_operations`, and `_rules` stay free of normative predicates. Updates read the owner's `Observation`, the owner's previous `NormLedger`, and the owner's `OwnerSafeSocialIdentity`. They never receive `WorldState`, `PhysicalRules`, `AgentBody`, `WorldEvent`, an event repository, replay, analysis output, another agent's runtime, goals, drives, beliefs, emotion, relationships, memories, mind model, reputation ledger, territorial ledger, or group ledger.
2. Do not own a capability flag. Do not add a `V2CapabilityFlags` field. Do not add `social_norms` or any new flag name. `multi_hop_testimony_tracking` stays unimplemented and still fails closed with `capability_unimplemented`. Off for this feature is `SocialNormMode.DISABLED`, which does not change commands, memories, semantic beliefs, relationships, reputation, territorial claims, group formation, or audits.
3. V1 regression gate stays green under flags-off, norm-mode disabled, and tracing-off. Catalog A–E and the reference scenario keep their current `exact_trajectory_hash` values. Experiment X is additive and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. Schema bump only for the enabled mode. Default write stays `runner-config-v4`. Add `runner-config-v17` to the accepted set. v17 carries every `runner-config-v16` key plus `social_norm_mode` on each agent. Emit v17 only when some agent's `SocialNormMode` is `DETERMINISTIC`. A group-only config still writes v16. Reject v17 when every social-norm mode is `DISABLED` (`v17_requires_social_norms`). Reject `DETERMINISTIC` social-norm mode on v1–v16 (`social_norm_mode_requires_v17`). Widen every existing mode and spec allowlist that currently ends at v16 so v17 remains legal for communication strategy, reputation, skill learning, teaching, production knowledge, reflection, consolidation, prospective imagination, counterfactual reasoning, environmental dynamics, territorial claims, and group formation. That includes the named frozensets in `src/simulation/runner_serialization.py` and every local set in `SimulationRunnerConfig.__post_init__` that currently ends at v16. Encode and decode `capability_flags` and `cognition_trace` on v17. Encode and decode `environmental_dynamics` on v17 when the spec is present, using the same rule as v16. Decode v17 agent cognition with `_COGNITION_KEYS_V17`, defined as `_COGNITION_KEYS_V16` plus `social_norm_mode`, before the v16 branch. `_require_keys` is an exact key check. Group-only equality (`v16_requires_group_formation`) stays an equality check. A config that enables both group formation and social norms writes v17, so `group_formation_mode_requires_v16` becomes membership in `{v16, v17}`. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. No policy weights in runner JSON. Leave `v1_regression_profile` unchanged. Baseline: the accepted set already ends at `runner-config-v16`.
5. No scripted emergence. No norm, custom, culture, moral, friend, enemy, or leader field on `World`, `WorldState`, `Observation`, commands, or events. No new `AgentCommand`, `ActionDirection`, `CommunicationSourceBasis`, `RelationshipDimension`, or `WorldEvent` kind. Scenarios must not contain a norm, obligation, or roster field. Sleep stays a one-tick fatigue action. Do not add a sleeping flag to `AgentBody` or `VisibleBody`.
6. No LLM path. There is no provider schema and no prompt package. `DETERMINISTIC` never calls `LLMProvider`.
7. Experiments stay reproducible. Paired arms share seed, topology, and stochastic identity. No RNG and no wall clock in norm updates. Experiment X and `emergent_social_norms@1` stay analysis-only and off the V1 regression gate. The metric is not an input to cognition. `repeated_conventions` stays the existing motif family and is not rewritten.
8. Optional cognition tracing stays outside the objective fold. Do not insert a `ComponentKind` or an ordinal in `_STAGE_ORDER`. Do not bump `COGNITION_TRACE_SUMMARY_SCHEMA`, add trace enum members, or add an Alembic revision. Do not copy pattern tokens, supporter ids, or analysis readings onto the trace summary. `subjective-v1` stays unchanged. Tracing on versus off must not change `exact_trajectory_hash` when the mode is `DISABLED`.

## Goal

Repeated behavior and the belief that behavior is expected stay different objects.

| Layer | What it is | Who may read it during a tick |
| --- | --- | --- |
| Repeated behavior | An external count of give, sleep, and attack patterns in the objective log | Analysis only, after the fact |
| Norm belief | One owner's private expectation: behavior, context, confidence, evidence, perceived supporters, and perceived consequences | That owner's cognition |
| Response | The owner's choice this tick: `follow`, `ignore`, `violate`, `communicate`, or `enforce` | That owner's cognition; analysis may compare it later |

A regularity can be frequent when every ledger is empty. An agent can expect a behavior that the objective rate does not support. One owner's ledger is not copied to another owner.

`repeated_conventions@1` already counts action n-grams. This plan leaves that family, its algorithm, and its value keys unchanged. `emergent_social_norms@1` is a separate document with two blocks, `repeated_behavior` and `norm_belief`.

## Design Decisions (locked)

- **A ledger, not a world rule and not a semantic belief.** `NormLedger` is owner-scoped state on `SubjectiveSnapshot.social_norms`, default `None`. It holds `NormBelief` values. A belief is not a `SemanticBelief`, not a `ReputationProfile`, not a `GroupConcept`, and not a `DirectedRelationshipProfile`. Updates do not call `revise_semantic_belief`, `merge_relationship_revision`, `apply_reputation_update`, `apply_territorial_update`, or `apply_group_update`. `RelationshipDimension.DEBT` already moves on resource given and received. The updater does not read that dimension and does not write it. The return pattern is counted from `give` occurrences only.
- **Disabled mode is a passthrough.** `SocialNormMode.DISABLED` leaves `snapshot.social_norms` as `None`, appends no evidence, emits no utterance, applies no intention penalty, and writes no runner field. Commands match the pre-norm planner.
- **Four patterns, closed tokens.** `NormPattern`: `return_transfer`, `share_under_scarcity`, `spare_after_sleep`, `reciprocal_exchange`. These tokens are absent from world events and from INFO logs.
- **Expected behavior is a closed action token.** `NormExpectation`: `give_back`, `give`, `withhold_attack`, `give_again`. Each pattern has one expectation, stored on the belief. The world does not check it.
- **Context is the situation the expectation applies to.** `NormContext` stores `pattern`, `location_id` when the pattern is scarcity, `counterpart_id` when the pattern is a directed pair, and `window_until_tick`. Context matching uses the owner's current observation only.
- **Sleep has no duration in the world.** `Slept` reduces fatigue for one committed action. The spare pattern uses a ledger window of `spare_window_ticks` (1) after a witnessed `sleep` occurrence. An attack whose `other_entity_id` resolves to that sleeper inside the window is a violation. The engine continues to accept that attack.
- **Food sharing uses the visible food resource.** `ObservedOccurrence` for `give` does not carry the item kind, and bystander public facts do not either. Conforming evidence for `share_under_scarcity` is a `give` whose success is not `False` while some `ObservedResource` at the owner's location has `ResourceKind.FOOD` and `quantity <= scarcity_quantity` (1.0). A missing give is not a violation. An owner whose hunger or thirst, divided by 100, is at least `0.75` may select `EAT` while that context holds, and that selection is recorded as `violate`.
- **Bodies and agents stay distinct.** Occurrence actor and other ids are `EntityId` values. Ledger owner, supporter, and counterpart ids are `AgentId`. Resolve with the owner's `OwnerSafeSocialIdentity`. An entity with no binding yields `unresolved_entity` and no evidence.
- **Confidence is subjective support.** Quantize to `1e-6` and clamp to `[0, 1]`. A belief starts as `candidate` after the first conforming item. It becomes `active` only when conforming count is at least 3 and confidence is at least `0.40`. Candidates are stored and are not followed, communicated, or enforced. Support below `0.20` sets status `retired`. Decay of `0.05` applies to a belief that received no evidence this tick.
- **Perceived supporters are witnessed conforming actors.** At most 8 resolved agent ids on one belief. The owner may be a supporter of their own conforming act. A supporter who was also the actor of a later violation stays in the set. The set is not an objective roster.
- **Perceived consequences are witnessed sanctions.** Closed `NormSanction`: `criticism`, `refusal`, `reduced_trust`, `retaliation`, `exclusion`. A consequence is stored only with a channel. `witnessed` accepts `criticism` from a delivered talk, ask, or tell whose relation predicate is exactly `criticize` and whose object is a known pattern token, and `retaliation` from an `attack` whose other entity is the actor of a violation recorded in the last 2 ticks. `refusal`, `reduced_trust`, and `exclusion` enter the field only with channel `own_act` after this owner applied that sanction. Absence of help is not evidence.
- **Responses never invent a command.** `norm_response_penalties(...)` returns penalties for futures the planner already has, using the same shape as `territorial_respect_penalties`: a map of future id to a non-negative float. The penalty quantum is `0.35`. If the preferred future is absent, the response is still recorded and the reason is `no_candidate`. The command stays the planner's command. Attack, help, give, and talk are not inserted into the future set.
- **Carry follows group formation.** `group_formation` is the latest owner ledger already on `SubjectiveSnapshot`, `CognitiveLoopProposal`, `CognitiveLoopResult`, `AgentRuntimeCheckpoint`, `Perspective`, and `build_perspective`. `AgentRuntime` holds the norm ledger the same way, default `None`, including a `require_owner_social_norms` check. `CognitiveLoop.prepare` calls `_prepare_social_norms` immediately after `_prepare_group_formation` and before `_prepare_competence`. Pass the ledger into intention and planning through `_planner_options`, the same way territorial claims are passed. `SubjectiveMutationBatch` does not grow a norm field. `subjective-v1` does not gain a version or a required key. There is no Alembic revision. A disabled checkpoint stores `None`.
- **Quantization and caps.** At most 8 beliefs per owner and 32 evidence items per belief. Further items drop with `cap_exceeded`. Belief id is sha256 of owner id, pattern, and sorted counterpart id when present. Evidence id is sha256 of belief id, ordinal, channel, and lineage ref. No RNG, wall clock, or Python `hash()`.
- **Fail closed.** Unknown pattern, expectation, status, response, sanction, or channel; owner mismatches; non-finite numbers; and a future penalty below 0 abort with stable reason codes. A bad occurrence is ignored. Passing `WorldState`, `WorldEvent`, or a metric document into `apply_norm_update` raises `TypeError`.

### Evidence

Apply one tick in this order: open-window bookkeeping, conforming and violating deltas, supporter and consequence updates, candidate promotion, response selection, then decay of `0.05` on beliefs that received no evidence this tick.

Dedup occurrences on `(pattern, source_event_id)`. When `source_event_id` is missing, the lineage ref is `tick-{tick}-{ordinal}`.

| Evidence the owner has this tick | Pattern and expectation | Delta | Notes |
| --- | --- | --- | --- |
| `give`, success is not `False`, later opposite `give` within `return_window_ticks` (8) | `return_transfer` / `give_back` | conforming `+0.15` | The first `give` opens the window and is not itself conforming. The opposite `give` conforms and closes the window. |
| Open `return_transfer` window reaches `window_until_tick` with no opposite `give` | same | violation `-0.20` | The window closes after that one violation. |
| `give`, success is not `False`, while a local food resource has quantity `<= 1.0` | `share_under_scarcity` / `give` | conforming `+0.15` | No violation delta for a missing give. |
| Witnessed `sleep`, and no `attack` in that same observation targets the sleeper | `spare_after_sleep` / `withhold_attack` | conforming `+0.15` | Opens a spare window of 1 tick on the sleeper. |
| `attack` whose other entity is inside an open spare window | same | violation `-0.20` | The attack still commits if the engine accepts it. |
| A directed pair already has `give` in both directions, and either direction gives again | `reciprocal_exchange` / `give_again` | conforming `+0.15` | The two opening gives establish the pair and do not conform. A later give does. |
| Established reciprocal pair receives no `give` for `return_window_ticks` (8) | same | violation `-0.20` | One violation, then the idle window resets. |

### Responses

Select one response per active belief after promotion and before decay. Candidates stay `ignore`. Priority for an active belief:

1. `enforce`, when this observation contains a violation of that belief by a resolved actor other than the owner and confidence is at least `0.50`.
2. `communicate`, when no enforcement was selected, confidence is at least `0.40`, a `COMMUNICATE` future already exists, and this owner has not uttered this pattern in the last `utterance_interval` ticks (4).
3. `violate`, when the pattern is `share_under_scarcity`, the owner's hunger or thirst divided by 100 is at least `0.75`, and an `EAT` future already exists.
4. `follow`, when confidence is at least `0.40` and a future already matches the expectation.
5. `ignore` otherwise.

`follow` adds `0.35` to futures that contradict the expectation: `ATTACK` on a sleeper inside the spare window, and `EAT` while scarcity holds and hunger is below the critical ratio. It does not add a `GIVE` future.

`communicate` prefers an existing `COMMUNICATE` future by adding `0.35` to the other futures in that belief's comparison. The emitted `Talk` uses `CommunicationSourceBasis.UNREFERENCED` and one `CommunicationRelation`: predicate `expect`, subject the pattern token, object the counterpart id or `location`. No new command kind.

### Sanctions

When the response is `enforce`, choose the first sanction whose precondition holds. Record it on the belief as `chosen_sanction`.

| Order | Sanction | Precondition | Effect |
| --- | --- | --- | --- |
| 1 | `criticism` | A `COMMUNICATE` future already exists | Same utterance path as communicate, with predicate `criticize`. Append `criticism` to perceived consequences with channel `own_act`. |
| 2 | `refusal` | A `HELP` or `GIVE` future already targets the violator | Add `0.35` to those futures. Append `refusal` with channel `own_act`. If no such future exists, record `sanction_latent` and do not change the command. |
| 3 | `reduced_trust` | The owner already has a relationship profile toward the violator | The loop appends one `MemoryUpdateKind.REVISE_RELATIONSHIP` intent for `RelationshipDimension.TRUST` with delta `-0.25`. The norm module does not call the relationship writer. Missing profile logs `trust_revision_skipped` with reason `no_profile` and creates nothing. Append `reduced_trust` with channel `own_act` only when the intent is appended. |
| 4 | `retaliation` | `retaliation` is already in perceived consequences with channel `witnessed`, and an `ATTACK` future already targets the violator | Add `0.35` to the other futures in that comparison. If the attack future is absent, record `sanction_unavailable`. |
| 5 | `exclusion` | `exclusion` is already in perceived consequences with channel `own_act`, or step 2 already recorded `refusal` on an earlier tick | Set `withhold_until_tick` to `tick + 8` for that directed pair. During the window, add `0.35` to existing `HELP`, `GIVE`, and `COMMUNICATE` futures toward that agent. The window is a ledger field. It is not a world ban. |

The first attack in a run is never created as retaliation. Reduced trust is a private relationship revision. Refusal and exclusion change which existing future wins. None of these steps reject a command inside `WorldEngine`.

### Analysis

`compute_emergent_social_norms` in `src/analysis/social_norm_metrics.py` builds two blocks from caller-supplied rows. It duck-types ledgers with `getattr`. It must not import `agents`, `apply_norm_update`, or `AgentRuntime`.

`repeated_behavior` reads objective rows `(tick, actor_id, kind, other_id, success, location_id, food_quantity)`.

| Key | Value |
| --- | --- |
| `return_transfer_rate` | Opposite gives within 8 ticks, divided by opened give windows. Empty windows yield `MetricAvailability.ABSENT` for this key only. |
| `share_under_scarcity_rate` | Gives while `food_quantity <= 1.0`, divided by ticks in that context. |
| `spare_after_sleep_rate` | Sleep occurrences with no same-tick attack on the sleeper, divided by sleep occurrences. |
| `reciprocal_exchange_rate` | Later gives on pairs that already exchanged both ways, divided by such opportunities. |

`norm_belief` reads detached belief rows `(tick, owner_id, pattern, status, confidence, supporter_count, consequences, response)`.

| Key | Value |
| --- | --- |
| `active_belief_count` | Rows with status `active`. |
| `mean_confidence` | Mean confidence of active rows, quantized. No active row yields `ABSENT` for this key only. |
| `repetition_without_belief` | Patterns whose repeated-behavior rate is `>= 0.50` while every owner has zero active beliefs for that pattern. |
| `belief_without_repetition` | Active beliefs whose pattern has a repeated-behavior rate `< 0.50`, or `ABSENT`. |

`compute_norm_persistence` takes ordered documents. `behavior_persistence` is the fraction of adjacent ticks whose repeated-behavior rate stays `>= 0.50`. `belief_persistence` is the fraction of adjacent ticks that still contain an active belief with confidence `>= 0.40` for the same owner and pattern. Empty history returns `MetricAvailability.ABSENT`. Neither fraction is fed back into a ledger.

The stored result uses `MetricDocument` family `emergent_social_norms`. `MetricSpecification.version_identifier` is derived as `{family_id.value}@{algorithm_version}`, so the tag is `emergent_social_norms@1`. Bump `METRIC_FAMILY_COUNT` from 29 to 30. The family is not added to the V1 bundle assembled for catalog A–E.

## Non-Goals

- A `WorldEngine` or `PhysicalRules` predicate that forbids attacks on sleepers, requires returned gifts, or requires sharing
- A sleeping flag on `AgentBody`, `VisibleBody`, or `Observation`
- Writing norm tokens into `SemanticBelief` or `RelationshipDimension.DEBT`
- Rewriting `repeated_conventions@1` or `group_community_structure`
- A new `AgentCommand`, `ActionDirection`, `CommunicationSourceBasis`, or `WorldEvent` kind
- Inserting an attack, give, help, or talk future that the planner did not already propose
- Owning `multi_hop_testimony_tracking`
- Inserting a `CognitiveLoop` ordinal, bumping the cognition-trace schema, bumping `subjective-v1`, or adding an Alembic revision
- Letting an agent read another agent's ledger or any analysis document
- An LLM assessor or free-form norm prose
- Putting Experiment X on the V1 regression gate

## Commit Plan
- **Commit 1** (after tasks 1–2): `feat(simulation): add opt-in social norms on runner-config-v17`
- **Commit 2** (after tasks 3–6): `feat(cognition): infer owner-scoped norm beliefs and sanctions`
- **Commit 3** (after tasks 7–9): `test(analysis): measure norm emergence apart from repeated behavior`
- **Commit 4** (after tasks 10–11): `docs(cognition): document emergent social norms`

## Tasks

### Phase 1: Contracts and Mode

- [x] Task 1: Add social-norm contracts and `SocialNormPolicy`.
  - Deliverable: frozen types in `src/agents/cognition/social_norms.py`, exported from `src/agents/cognition/__init__.py`. `DISABLED` leaves the snapshot field `None`.
  - Types: `NormPattern` (`return_transfer`, `share_under_scarcity`, `spare_after_sleep`, `reciprocal_exchange`), `NormExpectation` (`give_back`, `give`, `withhold_attack`, `give_again`), `NormStatus` (`candidate`, `active`, `retired`), `NormResponse` (`follow`, `ignore`, `violate`, `communicate`, `enforce`), `NormSanction` (`criticism`, `refusal`, `reduced_trust`, `retaliation`, `exclusion`), `NormConsequenceChannel` (`witnessed`, `own_act`), `NormEvidenceItem`, `NormContext`, `NormBelief`, `NormLedger`, `SocialNormPolicy` (`social-norms.v1`, active confidence `0.40`, enforce confidence `0.50`, retire confidence `0.20`, decay `0.05`, conforming delta `0.15`, violation delta `-0.20`, penalty `0.35`, conforming count `3`, return window `8`, spare window `1`, utterance interval `4`, exclusion window `8`, scarcity quantity `1.0`, critical need ratio `0.75`, trust delta `-0.25`, caps 8 beliefs, 32 evidence, 8 supporters). `CognitionSocialNormMode` (`DISABLED`, `DETERMINISTIC`) in `src/agents/cognition/configuration.py` and the matching runner enum in `src/simulation/runner_models.py`.
  - A belief constructor rejects an expectation that does not match its pattern, a supporter set larger than 8, and a consequence whose sanction is `refusal`, `reduced_trust`, or `exclusion` with channel `witnessed`.
  - Logging: logger `agents.cognition.social_norms`. DEBUG on construction with owner id, policy version, and belief count. ERROR with field name and reason code on validation failure. No supporter id lists and no pattern tokens at INFO.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Files: `src/agents/cognition/social_norms.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/__init__.py`, `src/simulation/runner_models.py`, `tests/unit/test_social_norms.py`.

- [x] Task 2: Wire `DETERMINISTIC` through `runner-config-v17` without owning a new flag.
  - Deliverable: mode off keeps `runner-config-v4` and today's commands. Mode on is accepted only as `runner-config-v17`. `multi_hop_testimony_tracking` still fails closed. A v17 document can still carry communication strategy, reputation, skill learning, teaching, production, reflection, consolidation, prospective imagination, counterfactual reasoning, environmental dynamics, territorial claims, and group formation.
  - Add `social_norm_mode` to `AgentCognitionSpec` and to `CognitionLoopConfig`. Default both to `DISABLED`. Accept v17 in `SUPPORTED_RUNNER_SCHEMA_VERSIONS`. Define `_COGNITION_KEYS_V17` as `_COGNITION_KEYS_V16` plus `social_norm_mode`. Add v17 to every allowlist that currently ends at v16, including `_SKILL_SCHEMA_VERSIONS` and the consolidation, reflection, prospective, counterfactual, communication-strategy, reputation, teaching, production, environmental-dynamics, and group-formation sets, plus every local set in `SimulationRunnerConfig.__post_init__` that currently ends at v16. Encode and decode `capability_flags` and `cognition_trace` on v17. Encode and decode `environmental_dynamics` on v17 when the spec is present. Encode `group_formation_mode` on v16 and v17. Encode `social_norm_mode` only on v17. Decode v17 agent cognition with `_COGNITION_KEYS_V17` before the v16 branch. Keep `v16_requires_group_formation` as an equality on v16. `group_formation_mode_requires_v16` becomes membership in `{v16, v17}`. Add `social_norm_mode_requires_v17` for `DETERMINISTIC` mode on v1–v16, and `v17_requires_social_norms` when v17 has every social-norm mode `DISABLED`. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. Do not add a `V2CapabilityFlags` field. `simulation.runner._cognition_config_for` sets `CognitionSocialNormMode.DETERMINISTIC` only from that field and builds `default_social_norm_policy()`. Update `src/simulation/compatibility.py` with the same accepted-set note. Export `RUNNER_SCHEMA_VERSION_V17` from `src/simulation/__init__.py`.
  - Tests: an enabled `multi_hop_testimony_tracking` still returns `capability_unimplemented`; a disabled social-norm mode does not bump the written schema; group-only deterministic still writes v16; social-norm deterministic writes v17 and round-trips; v17 with the mode disabled is rejected; a config with both group formation and social norms writes v17. One v17 config enables social norms, group formation, and environmental dynamics together and round-trips `capability_flags` and `cognition_trace`. Run `uv run ruff check` on each touched file.
  - Logging: DEBUG `cognition_config_social_norm_mode mode=%s policy_version=%s` on logger `simulation.runner`. Do not log thresholds. ERROR on schema rejection uses the existing stable runner codes.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 1.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/runner.py`, `src/simulation/__init__.py`, `src/agents/cognition/configuration.py`, `tests/unit/test_runner_models.py`, `tests/unit/test_runner_serialization.py`, `tests/unit/test_simulation_runner_construction.py`, `tests/unit/test_v2_flag_defaults.py`, `tests/unit/test_cognition_configuration.py`, `tests/unit/test_compatibility_matrix.py`.

### Phase 2: Private Expectations

- [x] Task 3: Apply observation evidence into owner-scoped norm beliefs.
  - Deliverable: `apply_norm_update(...)` returns a new `NormLedger` for one owner. It accepts this tick's `Observation`, the owner's `OwnerSafeSocialIdentity`, and the previous ledger. Passing `WorldState`, `WorldEvent`, or a metric document raises `TypeError`. The module must not import `analysis`, `simulation`, `communication`, `memory`, `world.models`, `world.events`, or `world._state`. It may import `world.observations`.
  - Apply the locked deltas and the locked tick order. The first `give` opens `return_transfer` and does not raise confidence. The opposite `give` within 8 ticks conforms and closes it. An elapsed window writes one violation. Food scarcity is an `ObservedResource` of kind `food` with quantity `<= 1.0` at the owner's location. A `give` in that context conforms. A missing give does not. A `sleep` with no same-tick attack on that actor conforms and opens a one-tick spare window. An `attack` inside that window violates. Two opposite gives establish `reciprocal_exchange`. A later give conforms. Eight idle ticks write one violation and reset the idle window. An unresolved entity logs `unresolved_entity` and adds no supporter. Unknown occurrence kinds leave the ledger unchanged. Caps drop new items with `cap_exceeded`.
  - A single conforming event stays `candidate`. Disabled callers do not call this function.
  - Logging: DEBUG `norm_belief_applied` with owner id, tick, and sign (`positive`, `negative`, or `zero`). INFO `norm_belief_updated` with owner id and belief count. WARNING `norm_evidence_dropped` with reason `cap_exceeded`, `ignored_kind`, or `unresolved_entity`. ERROR on owner mismatch. No supporter lists and no utterance text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 1.
  - Files: `src/agents/cognition/social_norms.py`, `tests/unit/test_social_norms.py`.

- [x] Task 4: Promote candidates, record supporters and consequences, and decay unsupported beliefs.
  - Deliverable: the same updater promotes a `candidate` to `active` when conforming count is at least 3 and confidence is at least `0.40`. Conforming actors become perceived supporters, capped at 8. Witnessed `criticize` relations and post-violation attacks append perceived consequences with channel `witnessed`. Sets with no new evidence this tick decay by `0.05`. Confidence below `0.20` retires the belief. Two owners updated from the same occurrences keep separate ledgers. A repeated behavior the owner never saw stays out of that owner's ledger.
  - Logging: DEBUG `norm_belief_promoted` or `norm_belief_retired` with owner id, tick, and status. WARNING `norm_belief_withheld` with reason `below_count`, `below_confidence`, or `candidate`. No supporter lists.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 3.
  - Files: `src/agents/cognition/social_norms.py`, `tests/unit/test_social_norms.py`.

- [x] Task 5: Select follow, ignore, violate, communicate, and enforce without creating commands.
  - Deliverable: `norm_response_penalties(...)` accepts the ledger, the observation, existing futures, hunger, and thirst. Disabled mode and a non-ledger return an empty map. Apply the locked response priority. Penalties are `0.35` on futures that contradict the selected response. A missing preferred future records `no_candidate` and leaves the map without a new future id. `violate` is selected for `share_under_scarcity` only when hunger or thirst divided by 100 is at least `0.75` and an `EAT` future already exists. `communicate` attaches the relation recipe `(predicate=expect, subject=pattern, object=counterpart or location)` for the planner to place on an existing `Talk`. It uses `CommunicationSourceBasis.UNREFERENCED`.
  - The function does not construct an `Attack`, `Give`, `Help`, or `Talk` command.
  - Logging: DEBUG `norm_response_selected` with owner id, tick, and response. WARNING `norm_response_withheld` with reason `no_candidate`, `candidate_only`, or `utterance_interval`. No utterance text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 4.
  - Files: `src/agents/cognition/social_norms.py`, `tests/unit/test_social_norms.py`.

- [x] Task 6: Apply criticism, refusal, reduced trust, retaliation, and exclusion as private choices.
  - Deliverable: when the response is `enforce`, walk the locked sanction order. Criticism reuses the communicate utterance path with predicate `criticize`. Refusal and exclusion only penalize existing `HELP`, `GIVE`, and `COMMUNICATE` futures. Reduced trust asks the loop to append one `MemoryUpdateKind.REVISE_RELATIONSHIP` intent on `RelationshipDimension.TRUST` with delta `-0.25` when a profile already exists. Retaliation penalizes other futures only when an `ATTACK` future already targets the violator and `retaliation` is already a `witnessed` consequence. Each applied sanction appends a perceived consequence with channel `own_act`. Unavailable sanctions record `sanction_latent` or `sanction_unavailable` and leave the command unchanged.
  - Add a focused regression in `tests/unit/test_social_norms_world.py`: a sleeper can still be attacked by `WorldEngine`, and a one-way `give` still commits with no engine-created return. Those tests call the existing operations. They do not add a rule.
  - Logging: DEBUG `norm_sanction_applied` with owner id, tick, and sanction. WARNING `norm_sanction_skipped` with reason `no_candidate`, `no_profile`, `sanction_latent`, or `sanction_unavailable`. No counterpart id lists.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 5.
  - Files: `src/agents/cognition/social_norms.py`, `src/agents/cognition/loop.py`, `tests/unit/test_social_norms.py`, `tests/unit/test_social_norms_world.py`.

### Phase 3: Runtime and Measurement

- [x] Task 7: Carry the ledger and pass response penalties into deliberation.
  - Deliverable: add `social_norms` beside `group_formation` on `SubjectiveSnapshot`, `CognitiveLoopProposal`, `CognitiveLoopResult`, `Perspective`, `build_perspective`, and `AgentRuntime` checkpoint state. `require_owner_social_norms` accepts `None` or a `NormLedger` whose owner matches. `CognitiveLoop.prepare` calls `_prepare_social_norms` immediately after `_prepare_group_formation`. Thread the ledger through `_planner_options` into intention selection and planning, and add the penalty map from `norm_response_penalties` next to `territorial_respect_penalties` inside the pairwise selection in `src/agents/cognition/deliberation.py`. `DISABLED` passes an empty map and keeps the pre-norm command.
  - The relationship revision intent from task 6 is attached in the loop after planning, only for an applied `reduced_trust` sanction. Do not insert a `ComponentKind`. Do not bump `subjective-v1`.
  - Logging: DEBUG `social_norms_carried` with owner id and belief count on logger `agents.cognition.loop`. DEBUG `norm_penalty_applied` with future count on logger `agents.cognition.deliberation`. WARNING `norm_carry_rejected` with reason `owner_mismatch` or `invalid_type`.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on tasks 2 and 6.
  - Files: `src/agents/cognition/models.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/loop.py`, `src/agents/cognition/deliberation.py`, `src/simulation/agent_runtime.py`, `src/simulation/perception.py`, `src/simulation/run_control.py`, `tests/unit/test_social_norms_runtime.py`.

- [x] Task 8: Measure repeated behavior and norm belief as separate blocks.
  - Deliverable: `compute_emergent_social_norms` and `compute_norm_persistence` in `src/analysis/social_norm_metrics.py`. Add `MetricFamilyId.EMERGENT_SOCIAL_NORMS`, bump `METRIC_FAMILY_COUNT` from 29 to 30, and register the specification whose tag is `emergent_social_norms@1`. Implement the locked keys. `repetition_without_belief` and `belief_without_repetition` are both present in the value map. A fixture with a high return rate and zero active beliefs yields a positive `repetition_without_belief` and `active_belief_count` of 0. A fixture with an active belief and a return rate below `0.50` yields a positive `belief_without_repetition`. Empty history returns `MetricAvailability.ABSENT` from the persistence function. The module duck-types rows and does not import `agents`.
  - Leave `compute_repeated_conventions` and its value keys unchanged.
  - Logging: logger `analysis.social_norm_metrics`. DEBUG `social_norms_metric_computed` with pattern count and active belief count. WARNING `social_norms_metric_empty` with reason `no_rows` or `no_history`. No owner id lists.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 1.
  - Files: `src/analysis/social_norm_metrics.py`, `src/analysis/specifications.py`, `src/analysis/__init__.py`, `src/analysis/metric_service.py`, `tests/unit/test_social_norm_metrics.py`, `tests/unit/test_metric_specifications.py`.

- [x] Task 9: Add Experiment X off the V1 gate.
  - Deliverable: `experiment_x_social_norms` pairs `x-disabled` / `social_norms_disabled` on `runner-config-v4` with `x-enabled` / `social_norms_deterministic` on `runner-config-v17`. Arms share seed, scenario, and stochastic identity. The catalog function checks that pairing and the mode field. It does not require a live tick to promote a belief. Register it in `src/experiments/catalog.py` and export it from `src/experiments/__init__.py`. Do not add it to `tests/unit/test_v1_regression_gate.py`.
  - Scenario builder `social_norms_scenario` in `src/experiments/social_norms_scenario.py` uses one location `clearing` with weather, three agents `ada`, `ben`, and `cy`, distinct body ids, one `food` resource at quantity `1.0`, and one food item in each inventory. `max_ticks` default is 16 so return windows and the conforming count of 3 can elapse. The builder accepts no norm, obligation, culture, or roster argument. The world must pass the existing topology and weather checks. Harvest detached belief rows into the metric the same way group-formation concepts are harvested, without adding them to `runner-result-v2`.
  - The enabled arm may finish with zero active beliefs. The disabled arm must finish with `social_norms is None` on every runtime. Persistence is asserted on row fixtures in task 8, and the catalog test asserts both metric blocks are requested for the enabled arm's result document when rows exist.
  - Logging: DEBUG `experiment_x_built` with experiment id and condition ids. Logger `experiments.catalog`. No utterance text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on tasks 2 and 8.
  - Files: `src/experiments/social_norms_scenario.py`, `src/experiments/catalog.py`, `src/experiments/__init__.py`, `tests/unit/test_social_norms_experiment.py`.

### Phase 4: Proofs

- [x] Task 10: Prove behavior and belief diverge, and that enforcement stays a private choice.
  - Deliverable: tests that fail if a scenario accepts a norm field, if a metric document can be passed into `apply_norm_update`, if one conforming give promotes a belief, if one owner's ledger appears on another owner, if `repeated_conventions` value keys change, or if disabled mode changes the command.
  - Required cases in `tests/unit/test_social_norms.py`, `tests/unit/test_social_norms_runtime.py`, `tests/unit/test_social_norms_world.py`, and `tests/unit/test_social_norms_experiment.py`:
    - Three opposite give pairs across separate windows promote `return_transfer`. One opposite pair stays `candidate` with reason `below_count`.
    - A `give` while the local food resource quantity is `1.0` conforms for `share_under_scarcity`. The same give at quantity `2.0` does not. No give under scarcity writes no violation.
    - A `sleep` with no same-tick attack conforms. A later attack inside the one-tick spare window violates and the existing attack operation still returns success under current physical rules.
    - Two opening gifts establish `reciprocal_exchange` at candidate confidence. The third gift in either direction conforms.
    - `DISABLED` runtime keeps the pre-norm command, stores no ledger, and leaves relationship revision uncalled.
    - Enforcement with no communicate future and no attack future records `sanction_unavailable` or `sanction_latent` and does not add a command.
    - Reduced trust with no profile records `no_profile` and leaves relationships unchanged.
    - Metric fixtures report `repetition_without_belief` and `belief_without_repetition` on separate setups, and persistence reports `behavior_persistence` and `belief_persistence` separately, including a history where behavior persists and belief persistence is 0.
  - Logging: tests may assert DEBUG events listed above. They must not require supporter id lists in log records.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on tasks 6, 7, 8, and 9.
  - Files: `tests/unit/test_social_norms.py`, `tests/unit/test_social_norms_runtime.py`, `tests/unit/test_social_norms_world.py`, `tests/unit/test_social_norms_experiment.py`.

### Phase 5: Documentation

- [x] Task 11: Document the behavior/belief split and the v17 mode.
  - Deliverable: this is the mandatory docs checkpoint. Route the prose through `/aif-docs`. Append to `docs/architecture.md` item 7, after the existing `GroupFormationMode` / Experiment W sentence: `SocialNormMode` defaults to `DISABLED`, `runner-config-v17` is emitted only when some agent's mode is `DETERMINISTIC`, Experiment X and `emergent_social_norms@1` stay off the V1 gate and out of cognition, and the policy is `social-norms.v1`. Leave the Experiment W sentence in place. Add a section to `docs/social-communication.md` that states repeated behavior, owner norm beliefs, and responses are different objects, that a norm becomes active only after repeated evidence, and that sanctions are existing talk, help, give, attack, and trust revisions chosen by the owner. Add one sentence to `.ai-factory/DESCRIPTION.md` after the existing `GroupFormationMode` / `runner-config-v16` sentence. The roadmap entry under M6 is already present. Mark that entry implemented when this plan completes. Do not invent a roadmap milestone.
  - Tests: doc mentions stay consistent with the constants `social-norms.v1`, `emergent_social_norms@1`, `runner-config-v17`, and `repeated_conventions`. No new test module is required beyond a link check if `/aif-docs` adds one.
  - Logging: none beyond existing docs tooling.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL` where a docs check emits logs.
  - Depends on tasks 2, 8, and 9.
  - Files: `docs/architecture.md`, `docs/social-communication.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ROADMAP.md`.
