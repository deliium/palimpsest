# Implementation Plan: Emergent Group Formation

Branch: main
Created: 2026-10-02
Improved: 2026-10-02
Status: implemented (2026-10-02). Tasks 1–11 are done. M6 stays open because `multi_hop_testimony_tracking` is still unowned.

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete roadmap milestone. This plan adds an opt-in owner-scoped group-formation mode and leaves `multi_hop_testimony_tracking` unowned.

## Compatibility contract

Groups are not assigned. External analysis may detect candidate clusters from recorded patterns. An agent may separately hold a private membership belief, and may hold a `GroupConcept` only when that belief is backed by social evidence. The plan must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only mutation authority. Updates read the owner's `Observation`, the owner's existing group ledger, the owner's `OwnerSafeSocialIdentity`, and trust floats the caller already projected. They never receive `WorldState`, `PhysicalRules`, `AgentBody`, `WorldEvent`, an event repository, replay, analysis output, another agent's runtime, goals, drives, beliefs, emotion, relationships, memories, mind model, reputation ledger, territorial ledger, or group ledger.
2. Do not own a capability flag. Do not add a `V2CapabilityFlags` field. Do not add `group_formation` or any new flag name. `multi_hop_testimony_tracking` stays unimplemented and still fails closed with `capability_unimplemented`. Off for this feature is `GroupFormationMode.DISABLED`, which does not change commands, memories, semantic beliefs, relationships, reputation, territorial claims, or audits.
3. V1 regression gate stays green under flags-off, group-mode disabled, and tracing-off. Catalog A–E and the reference scenario keep their current `exact_trajectory_hash` values. Experiment W is additive and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. Schema bump only for the enabled mode. Default write stays `runner-config-v4`. Add `runner-config-v16` to the accepted set. v16 carries every `runner-config-v15` key plus `group_formation_mode` on each agent. Emit v16 only when some agent's `GroupFormationMode` is `DETERMINISTIC`. A territorial-only config still writes v15. Reject v16 when every group mode is `DISABLED` (`v16_requires_group_formation`). Reject `DETERMINISTIC` group mode on v1–v15 (`group_formation_mode_requires_v16`). Widen every existing mode and spec allowlist that currently ends at v15 so v16 remains legal for communication strategy, reputation, skill learning, teaching, production knowledge, reflection, consolidation, prospective imagination, counterfactual reasoning, environmental dynamics, and territorial claims. That includes the named frozensets and every local set in `SimulationRunnerConfig.__post_init__` that currently ends at v15: `consolidation_schemas`, `reflection_schemas`, `prospective_schemas`, the counterfactual, communication-strategy, and reputation sets, `_SKILL_SCHEMAS`, the teaching and production sets, the shared teaching-weight check, the shared production-catalog check, and `dynamics_schemas`. Encode and decode `capability_flags` and `cognition_trace` on v16. Encode and decode `environmental_dynamics` on v16 when the spec is present, using the same rule as v15. Decode v16 agent cognition with `_COGNITION_KEYS_V16` before the v15 branch. `_require_keys` is an exact key check, so a v16 document that omits those root fields fails the round trip. Territorial-only equality (`v15_requires_territorial_claims`) stays an equality check. A config that enables both territorial claims and group formation writes v16, so `territorial_claim_mode_requires_v15` becomes membership in `{v15, v16}`. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. No policy weights in runner JSON. Leave `v1_regression_profile` unchanged. Baseline: the accepted set already ends at `runner-config-v15`. There is no `_COGNITION_KEYS_V14`; v14 reuses `_COGNITION_KEYS_V13` and adds the root key `environmental_dynamics`. `_COGNITION_KEYS_V15` is that v13 set plus `territorial_claim_mode`. A v15 document uses `_RUNNER_ROOT_KEYS_V14` when `environmental_dynamics` is present and `_RUNNER_ROOT_KEYS_V4` otherwise. v16 keeps that root-key rule and adds no root field.
5. No scripted emergence. No friend, enemy, leader, team, faction, culture, or member role on `World`, `WorldState`, `Observation`, commands, or events. No new `AgentCommand`, `ActionDirection`, `CommunicationSourceBasis`, `RelationshipDimension`, or `WorldEvent` kind. Scenarios must not contain a team, faction, or roster field.
6. No LLM path. There is no provider schema and no prompt package. `DETERMINISTIC` never calls `LLMProvider`.
7. Experiments stay reproducible. Paired arms share seed, topology, and stochastic identity. No RNG and no wall clock in group updates. Experiment W and `emergent_group_formation@1` stay analysis-only and off the V1 regression gate. The metric is not an input to cognition. `group_community_structure` stays the existing trust-only modularity family and is not rewritten.
8. Optional cognition tracing stays outside the objective fold. Do not insert a `ComponentKind` or an ordinal in `_STAGE_ORDER`. Do not bump `COGNITION_TRACE_SUMMARY_SCHEMA`, add trace enum members, or add an Alembic revision. Do not copy stances, member ids, or analysis readings onto the trace summary. `subjective-v1` stays unchanged. Tracing on versus off must not change `exact_trajectory_hash` when the mode is `DISABLED`.

## Goal

Agents are never placed on predefined teams. Two readings of "a group" stay different objects.

| Layer | What it is | Who may read it during a tick |
| --- | --- | --- |
| Candidate cluster | An external pattern over interaction frequency, mutual assistance, resource exchange, communication, shared harm, shared beliefs, spatial proximity, and trust | Analysis only, after the fact |
| Membership belief | One owner's private stance toward a set of agents: `we`, `our_group`, or `those_agents` | That owner's cognition |
| `GroupConcept` | An optional record minted from a membership belief only when social evidence supports it | That owner's cognition; analysis may compare it later |

A candidate cluster can exist when no agent recognizes a group. An agent can recognize a group that analysis does not recover as a cluster. Membership can overlap, decay, split, and merge. One owner's belief need not match another's.

## Design Decisions (locked)

- **A ledger, not a team and not a semantic belief.** `GroupLedger` is owner-scoped state on `SubjectiveSnapshot.group_formation`, default `None`. It holds `GroupMembershipBelief` values and optional `GroupConcept` values. A belief is not a `SemanticBelief`, not a `ReputationProfile`, not a `TerritorialClaim`, and not a `MindHypothesis`. Updates do not call `revise_semantic_belief`, `merge_relationship_revision`, `apply_reputation_update`, or `apply_territorial_update`. `World`, `WorldState`, and `Observation` gain no team, faction, group, or member field.
- **Disabled mode is a passthrough.** `GroupFormationMode.DISABLED` leaves `snapshot.group_formation` as `None`, appends no evidence, emits no utterance, applies no intention bias, and writes no runner field. Commands match the pre-group planner. This mode does not replace `Wait`.
- **Stances are the agent's words.** Closed `GroupStance`: `we`, `our_group`, `those_agents`. `we` and `our_group` require the owner id in the member set. `those_agents` forbids the owner id in the member set. These tokens are absent from world events, commands, analysis cluster ids, and INFO logs.
- **A concept is optional.** A `GroupConcept` is created only from a belief whose `social_evidence` is true and whose support is at least `0.40`. `we` never mints a concept. Proximity and trust never set `social_evidence`. `our_group` is the inclusive stance that replaces `we` for that exact member set once social evidence exists. `those_agents` mints a concept only when the owner witnessed assistance, exchange, or communication among the members. Shared harm never mints a concept by itself.
- **Social evidence is witnessed interaction, not an analysis label.** Channels that set `social_evidence`: `assistance` when the pair is reciprocal for an inclusive set, or when the owner witnesses `help` among others; `exchange` on the same rule for `give`; `communication` on hop 0 or 1. Channels that raise support and leave `social_evidence` false: `proximity`, `trust`, `shared_harm`.
- **Bodies and agents stay distinct.** `VisibleBody.entity_id`, occurrence actor and other ids, and communication speaker and listener ids are `EntityId` values. Ledger owner and member ids are `AgentId`. Resolve with the owner's `OwnerSafeSocialIdentity`. An entity with no binding yields `unresolved_entity` and no belief. Do not treat an entity id string as an agent id.
- **Visible bodies are proximity.** `VisibleBody` has no location field. Perception already limits `observation.visible_bodies` to the owner's location. Each resolved visible body adds proximity support on the inclusive pair `{owner, other}`. Analysis proximity is separate and uses caller-supplied `(tick, agent_id, location_id)` rows.
- **Shared beliefs stay outside cognition.** The updater does not read `SemanticBelief` stores, including the owner's. Shared-belief overlap is an analysis signal over caller-supplied triples. Missing triples make that signal `MetricAvailability.ABSENT`. They do not count as zero overlap.
- **Shared enemies are an analysis reading of shared harm.** The ledger channel is `shared_harm`: two resolved agents attacked by the same actor, or two resolved agents attacking the same target, on occurrences the owner can see. The string `shared_enemies` may appear only as a metric reading. It is not a relationship dimension and not a stance.
- **Existing trust modularity stays put.** `compute_group_community_structure` and `MetricFamilyId.GROUP_COMMUNITY_STRUCTURE` keep their current inputs, algorithm, and value keys. `emergent_group_formation@1` does not call that function and does not replace it. The trust signal inside the new metric may call `build_signed_trust_digraph`.
- **Overlap, asymmetry, instability, split, and merge.** One owner may hold several active beliefs and concepts whose member sets intersect. Two owners may assign different stances to overlapping sets; nothing copies a ledger across owners. Support decays by `0.05` on a set that received no evidence this tick. A belief or concept with support below `0.20` becomes `retired`. Split and merge rules are below. Analysis lineage is a different computation over candidate clusters and is not written onto the ledger.
- **Carry follows territorial claims.** `territorial_claims` is the latest owner ledger already on `SubjectiveSnapshot`, `CognitiveLoopProposal`, `CognitiveLoopResult`, `AgentRuntimeCheckpoint`, `Perspective`, and `build_perspective`. `AgentRuntime` holds the group ledger the same way, default `None`, including a `require_owner_group_formation` check. `CognitiveLoop.prepare` calls `_prepare_group_formation` immediately after `_prepare_territorial_claims` and before `_prepare_competence`. The ledger is not passed into deliberation. `SubjectiveMutationBatch` does not grow a group field. `subjective-v1` does not gain a version or a required key. There is no Alembic revision. A disabled checkpoint stores `None`.
- **Quantization and caps.** Support is quantized to `1e-6` and clamped to `[0, 1]`. Member-set size is 2 through 8. At most 16 beliefs and 8 concepts per owner, and 64 evidence items per belief. Further items drop with `cap_exceeded`. Belief id is sha256 of owner id, stance, and sorted member ids. Concept id is sha256 of belief id and the literal `concept`. Evidence id is sha256 of belief id, ordinal, channel, and lineage ref. Split and merge children use a new id and store `parent_ids`. No RNG, wall clock, or Python `hash()`.
- **Fail closed.** Unknown stance or channel, owner mismatches, owner placed in `those_agents`, owner missing from `we` or `our_group`, sets smaller than 2 or larger than 8, non-finite numbers, and a concept with `social_evidence` false abort with stable reason codes. A bad occurrence is ignored. It is not repaired from the world. Passing `WorldState`, `WorldEvent`, or an analysis cluster object into `apply_group_update` raises `TypeError`.

### Evidence deltas

All deltas are applied to the belief for that member set, then clamped. Reciprocal means the ledger already holds the opposite direction for that pair on that channel. Apply one tick in this order: evidence deltas, social-evidence flags, `we` to `our_group` promotion, split, merge, then decay of `0.05` on beliefs that received no evidence this tick.

Dedup occurrences and communications on `(channel, source_event_id)`. When `source_event_id` is missing, the lineage ref is `tick-{tick}-{ordinal}`. Proximity and trust use `{tick}:{other_agent_id}`, so each tick applies once and the next tick applies again. The trust float is the first value from `project_trust_inputs`, already mapped onto `[0, 1]` as `0.5 + 0.5 * signed`. Compare that float with `0.60`. The updater does not import `social`. `_prepare_group_formation` walks `snapshot.relationships` and passes `Mapping[str, float]` keyed by agent id.

| Evidence the owner has this tick | Set and stance | Delta | Social evidence |
| --- | --- | --- | --- |
| Resolved `VisibleBody` | `{owner, other}`, `we` | `proximity +0.10` | no |
| Caller trust toward other `>= 0.60` | `{owner, other}`, `we` | `trust +0.10` | no |
| `help`, `success is not False`, owner is actor or other | `{owner, partner}`, `we` until reciprocal | `assistance +0.25` | only once both directions exist |
| `help`, owner is neither party, both parties resolve | `{actor, other}`, `those_agents` | `assistance +0.25` | yes |
| `give`, same participation rules as `help` | inclusive or exclusive pair | `exchange +0.30` | same rule as help |
| Delivered talk, ask, or tell, hop 0 or 1, owner is speaker or listener | `{owner, counterpart}`, `we` | `communication +0.20` | yes |
| Same utterance, owner is neither party | `{speaker, listener}`, `those_agents` | `communication +0.20` | yes |
| Hop count above 1 | none | none | no |
| Two visible attacks sharing an actor or a target | the two patients, or the two actors, as `those_agents` when the owner is outside that pair; otherwise the inclusive pair at `we` | `shared_harm +0.20` | no |

When an inclusive set already has social evidence and support reaches `0.40`, its stance becomes `our_group` and a `GroupConcept` with status `active` is stored. The previous `we` belief for that exact set becomes `retired` with reason `promoted`. A `those_agents` belief at support `>= 0.40` with social evidence mints an active concept and the belief stays active.

### Split and merge

- **Split.** An active concept has at least 3 members, and this tick records `shared_harm` whose two endpoints are both members. The concept status becomes `split`. Remove the lexicographically greater endpoint id from the set. If the remaining set has size at least 2, open a child belief. The child belief and child concept copy the parent's support and `social_evidence` after this tick's evidence and before decay. Mint the child concept only when that copied support is at least `0.40` and `social_evidence` is true. Child stance is `our_group` when the owner remains in an inclusive parent, otherwise `those_agents`. The removed agent does not form a size-1 concept. `parent_ids` contains the split concept id.
- **Merge.** Two active concepts of the same owner and the same stance have Jaccard similarity of at least `0.5`, both supports are at least `0.40`, and the union has size at most 8. Both parents become `merged`. One child concept stores the union, support equal to the max of the parents, `social_evidence` true, and both parent ids. Jaccard below `0.5` leaves both concepts active, which is the overlapping-group case. Different stances do not merge (`stance_mismatch`). A union larger than 8 does not merge (`merge_blocked`).

### Decay

A belief that received no new evidence this tick loses `0.05` support, quantized. An active concept follows its backing belief. Support below `0.20` sets status `retired`. Retired records stay until the cap drops the oldest. A retired concept is not a member of later merges.

### Analysis candidate clusters

`compute_emergent_group_candidates` in `src/analysis/group_formation_metrics.py` builds eight signals from caller-supplied rows. It duck-types ledgers with `getattr`. It must not import `agents`, `apply_group_update`, or `AgentRuntime`.

| Signal key | Edge when |
| --- | --- |
| `interaction_frequency` | count of help, give, talk, ask, and tell rows between the pair, weight `min(count, 8) / 8`, edge at weight `>= 0.5` |
| `mutual_assistance` | both directions of help exist at least once; weight `1` |
| `resource_exchange` | give rows; both directions weight `1`, one direction weight `0.5`; edge at `>= 0.5` |
| `communication` | talk, ask, and tell count, weight `min(count, 4) / 4`, edge at `>= 0.5` |
| `shared_harm` | the pair shares an attacker or a common attack target at least once; weight `1`; metric reading `shared_enemies` |
| `shared_beliefs` | Jaccard of caller-supplied `(subject, predicate, object)` keys per owner `>= 0.5`; omitted triples yield `ABSENT` for this signal only |
| `spatial_proximity` | fraction of supplied ticks sharing `location_id` `>= 0.5` |
| `trust_network` | `min(trust_ab, trust_ba) >= 0.6` on caller-supplied trust rows |

For each present signal, insert nodes in sorted agent-id order and edges in sorted endpoint order. Candidate clusters are maximal cliques of size at least 2 from that graph. Clique membership may overlap inside one signal. Emit cliques sorted by their sorted member-id tuples. Cluster id is sha256 of the signal key and the sorted member ids. A signal with no edge returns an empty cluster tuple and `MetricAvailability.PRESENT`. A signal with no input rows returns `MetricAvailability.ABSENT` for that signal. The document also lists, per agent, the cluster ids that contain that agent.

`compute_group_persistence` takes an ordered sequence of those candidate documents plus optional detached concept rows `(tick, owner_id, stance, member_ids, status)`.

- On one signal, compare every cluster at tick `t` with every cluster at `t+1`. A pair continues when Jaccard similarity is at least `0.5`. Matching is all pairs, not a greedy assignment.
- `persistence_fraction` is continued links divided by links that had a next tick. Empty history returns `MetricAvailability.ABSENT`.
- One earlier cluster with two or more matches records one `split`. One later cluster with two or more earlier matches records one `merge`.
- A lineage is `unstable` when its present ticks are strictly less than `window_length / 2`.
- `cluster_without_concept` counts clusters whose best Jaccard against any active concept at that tick is below `0.5`.
- `concept_without_cluster` counts active concepts whose best Jaccard against any cluster at that tick is below `0.5`.
- Neither count is fed back into a ledger.

The stored result uses `MetricDocument` family `emergent_group_formation`. `MetricSpecification.version_identifier` is derived as `{family_id.value}@{algorithm_version}`, so the tag is `emergent_group_formation@1`. It is not added to the V1 bundle assembled for catalog A–E.

## Non-Goals

- Assigning agents to teams, factions, cultures, or roles in the scenario or the world
- Equating a candidate cluster with a `GroupConcept`
- Storing `enemy`, `friend`, `leader`, or `shared_enemies` on domain objects
- Writing group stances into `SemanticBelief` or changing `extract_evidence_candidates`
- A new `AgentCommand`, intention bias, or `Tell` that announces membership
- Owning `multi_hop_testimony_tracking`, or keeping utterances whose hop count is greater than 1
- Rewriting `group_community_structure` or changing its value keys
- Rewriting `spatial_control@1` or moving `MetricFamilyId.SPATIAL_CONTROL`
- Inserting a `CognitiveLoop` ordinal, bumping the cognition-trace schema, bumping `subjective-v1`, or adding an Alembic revision
- Letting an agent read another agent's ledger, beliefs, or any analysis document
- An LLM assessor or free-form group names
- Putting Experiment W on the V1 regression gate

## Commit Plan
- **Commit 1** (after tasks 1–2): `feat(simulation): add opt-in group formation on runner-config-v16`
- **Commit 2** (after tasks 3–6): `feat(cognition): form owner-scoped group beliefs and concepts`
- **Commit 3** (after tasks 7–10): `test(analysis): measure emergent clusters and group persistence`
- **Commit 4** (after task 11): `docs(cognition): document emergent groups`

## Tasks

### Phase 1: Contracts and Mode

- [x] Task 1: Add group-formation contracts and `GroupFormationPolicy`.
  - Deliverable: frozen types in `src/agents/cognition/group_formation.py`, exported from `src/agents/cognition/__init__.py`. `DISABLED` leaves the snapshot field `None`.
  - Types: `GroupStance` (`we`, `our_group`, `those_agents`), `GroupChannel` (`proximity`, `trust`, `assistance`, `exchange`, `communication`, `shared_harm`), `GroupStatus` (`active`, `retired`, `split`, `merged`), `GroupEvidenceItem`, `GroupMembershipBelief`, `GroupConcept`, `GroupLedger`, `GroupFormationPolicy` (`group-formation.v1`, concept threshold `0.40`, retire threshold `0.20`, decay `0.05`, trust floor `0.60`, merge Jaccard `0.5`, caps 16, 8, and 64, set size 2 through 8). `CognitionGroupFormationMode` (`DISABLED`, `DETERMINISTIC`) in `src/agents/cognition/configuration.py` and the matching runner enum in `src/simulation/runner_models.py`.
  - No field on these types is named `team`, `faction`, `enemy`, `friend`, `leader`, or `shared_enemies`. A concept constructor rejects `social_evidence` false, stance `we`, and a member set that violates the stance's owner rule.
  - Logging: logger `agents.cognition.group_formation`. DEBUG on construction with owner id, policy version, belief count, and concept count. ERROR with field name and reason code on validation failure. No stance tokens and no member id lists.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Files: `src/agents/cognition/group_formation.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/__init__.py`, `src/simulation/runner_models.py`, `tests/unit/test_group_formation.py`.

- [x] Task 2: Wire `DETERMINISTIC` through `runner-config-v16` without owning a new flag.
  - Deliverable: mode off keeps `runner-config-v4` and today's commands. Mode on is accepted only as `runner-config-v16`. `multi_hop_testimony_tracking` still fails closed. A v16 document can still carry communication strategy, reputation, skill learning, teaching, production, reflection, consolidation, prospective imagination, counterfactual reasoning, environmental dynamics, and territorial claims.
  - Add `group_formation_mode` to `AgentCognitionSpec` and to `CognitionLoopConfig`. Default both to `DISABLED`. Accept v16 in `SUPPORTED_RUNNER_SCHEMA_VERSIONS`. Define `_COGNITION_KEYS_V16` as `_COGNITION_KEYS_V15` plus `group_formation_mode`. Do not invent `_COGNITION_KEYS_V14`. Add v16 to every allowlist that currently ends at v15: `_SKILL_SCHEMA_VERSIONS`, `_COGNITION_SCHEMA_CONSOLIDATION`, `_COGNITION_SCHEMA_REFLECTION`, `_COGNITION_SCHEMA_PROSPECTIVE`, `_COGNITION_SCHEMA_COUNTERFACTUAL`, `_COGNITION_SCHEMA_STRATEGY`, `_COGNITION_SCHEMA_REPUTATION`, the teaching set `{v12..v15}`, the production set `{v13..v15}`, and the environmental-dynamics schema set. Also add v16 to every local set in `SimulationRunnerConfig.__post_init__` that currently ends at v15: `consolidation_schemas`, `reflection_schemas`, `prospective_schemas`, the counterfactual, communication-strategy, and reputation sets, `_SKILL_SCHEMAS`, the teaching and production sets, the shared teaching-weight check, the shared production-catalog check, and `dynamics_schemas`. Encode and decode `capability_flags` and `cognition_trace` on v16. Encode and decode `environmental_dynamics` on v16 when the spec is present, using the same rule as v15. Encode `territorial_claim_mode` on v15 and v16. Encode `group_formation_mode` only on v16. v15 decode stays on `_COGNITION_KEYS_V15`. Decode v16 agent cognition with `_COGNITION_KEYS_V16` before the v15 branch. v16 root keys follow the v15 rule: `_RUNNER_ROOT_KEYS_V14` when `environmental_dynamics` is present, otherwise `_RUNNER_ROOT_KEYS_V4`. Keep `v15_requires_territorial_claims` as an equality on v15. `territorial_claim_mode_requires_v15` becomes membership in `{v15, v16}`. Add `group_formation_mode_requires_v16` for `DETERMINISTIC` group mode on v1–v15, and `v16_requires_group_formation` when v16 has every group mode `DISABLED`. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. Do not add a `V2CapabilityFlags` field. `simulation.runner._cognition_config_for` sets `CognitionGroupFormationMode.DETERMINISTIC` only from that field and builds `default_group_formation_policy()`. Update `src/simulation/compatibility.py` with the same accepted-set note. Export `RUNNER_SCHEMA_VERSION_V16` from `src/simulation/__init__.py`.
  - Tests: an enabled `multi_hop_testimony_tracking` still returns `capability_unimplemented`; a disabled group mode does not bump the written schema; territorial-only deterministic still writes v15; group deterministic writes v16 and round-trips; v16 with group mode disabled is rejected; a config with both territorial claims and group formation writes v16. One v16 config enables group formation, territorial claims, and environmental dynamics together and round-trips `capability_flags` and `cognition_trace`. Run `uv run ruff check` on each touched file.
  - Logging: DEBUG `cognition_config_group_formation_mode mode=%s policy_version=%s` on logger `simulation.runner`. Do not log thresholds. ERROR on schema rejection uses the existing stable runner codes.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 1.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/runner.py`, `src/simulation/__init__.py`, `src/agents/cognition/configuration.py`, `tests/unit/test_runner_models.py`, `tests/unit/test_runner_serialization.py`, `tests/unit/test_simulation_runner_construction.py`, `tests/unit/test_v2_flag_defaults.py`, `tests/unit/test_cognition_configuration.py`, `tests/unit/test_compatibility_matrix.py`.

### Phase 2: Private Membership

- [x] Task 3: Apply observation evidence into owner-scoped membership beliefs.
  - Deliverable: `apply_group_update(...)` returns a new `GroupLedger` for one owner. It accepts this tick's `Observation`, the owner's `OwnerSafeSocialIdentity`, caller-projected trust floats, and the previous ledger. Passing `WorldState`, `WorldEvent`, or a candidate-cluster object raises `TypeError`. The module must not import `analysis`, `simulation`, `communication`, `memory`, `world.models`, `world.events`, or `world._state`. It may import `world.observations`.
  - Apply the locked deltas and the locked tick order. Proximity comes from resolved `visible_bodies`. Trust is the first value from `project_trust_inputs` (mapped onto `[0, 1]` as `0.5 + 0.5 * signed`). `_prepare_group_formation` walks `snapshot.relationships` and passes `Mapping[str, float]` keyed by agent id. The updater does not import `social` and does not call `project_trust_inputs`. Compare that float with the floor `0.60`. `help` and `give` follow the inclusive and exclusive rows. Communication uses hop 0 or 1 and drops a higher hop. Shared harm uses two visible attack occurrences that share an actor or a target. An unresolved entity logs `unresolved_entity` and adds no member. Unknown occurrence kinds leave the ledger unchanged. Dedup occurrences and communications on `(channel, source_event_id)`. When `source_event_id` is missing, the lineage ref is `tick-{tick}-{ordinal}`. Proximity and trust use `{tick}:{other_agent_id}`, so each tick applies once and the next tick applies again. Caps drop new items with `cap_exceeded`.
  - A proximity-only or trust-only set may become a `we` belief once support reaches `0.40`. It must not create a `GroupConcept`. Disabled callers do not call this function. Apply one tick in this order: evidence deltas, social-evidence flags, `we` to `our_group` promotion, split, merge, then decay of `0.05` on beliefs that received no evidence this tick.
  - Logging: DEBUG `group_belief_applied` with owner id, tick, channel, and sign (`positive`, `negative`, or `zero`). INFO `group_belief_updated` with owner id, belief count, and concept count. WARNING `group_evidence_dropped` with reason `cap_exceeded`, `ignored_kind`, `hop_dropped`, or `unresolved_entity`. ERROR on owner mismatch. No member lists and no utterance text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 1.
  - Files: `src/agents/cognition/group_formation.py`, `tests/unit/test_group_formation.py`.

- [x] Task 4: Mint `GroupConcept` records only from socially evidenced beliefs, and decay unsupported ones.
  - Deliverable: the same updater promotes `we` to `our_group` and appends an active `GroupConcept` when assistance, exchange, or communication has set `social_evidence` and support is at least `0.40`. A witnessed exclusive set on those channels mints a `those_agents` concept at the same threshold. Shared harm, proximity, and trust never set `social_evidence` and never mint a concept. The retired `we` belief remains with reason `promoted`.
  - Sets with no new evidence this tick decay by `0.05`. Support below `0.20` retires the belief and its active concept. One owner may hold two active concepts that share a member when their Jaccard similarity is below `0.5`. Two owners updated from the same occurrences keep separate ledgers.
  - Logging: DEBUG `group_concept_minted` or `group_concept_retired` with owner id, tick, stance, and status. WARNING `group_concept_withheld` with reason `no_social_evidence`, `below_threshold`, or `proximity_only`. No member lists.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 3.
  - Files: `src/agents/cognition/group_formation.py`, `tests/unit/test_group_formation.py`.

- [x] Task 5: Split and merge concepts inside one owner's ledger.
  - Deliverable: apply the locked split rule when `shared_harm` lands inside an active concept of size at least 3, using lexicographic endpoint order. The child belief and child concept copy the parent's support and `social_evidence` after this tick's evidence and before decay. Mint the child concept only when that copied support is at least `0.40` and `social_evidence` is true. Apply the locked merge rule for same-stance active concepts. Overlapping concepts below the Jaccard floor stay distinct. Stance mismatches and unions above size 8 leave both parents active and record `stance_mismatch` or `merge_blocked`. Child records store `parent_ids`. A size-1 remainder is not stored. The removed agent is not stored.
  - Logging: DEBUG `group_concept_split` or `group_concept_merged` with owner id, tick, parent count, and child status. WARNING `group_concept_rewrite_skipped` with reason `stance_mismatch`, `merge_blocked`, or `remainder_too_small`. No member lists.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 4.
  - Files: `src/agents/cognition/group_formation.py`, `tests/unit/test_group_formation.py`.

- [x] Task 6: Carry the ledger across ticks without changing the selected command.
  - Deliverable: copy the landed `territorial_claims` carry. `SubjectiveSnapshot`, `CognitiveLoopProposal`, `CognitiveLoopResult`, `AgentRuntimeCheckpoint`, and `Perspective` gain `group_formation: object | None = None`, each checked by `require_owner_group_formation`. `build_perspective` gains the same optional argument beside `territorial_claims`. `AgentRuntime` loads, exports, and restores it beside `_territorial_claims`. After a successful enabled tick, the runtime replaces the ledger with the updater result. Abort and `DISABLED` leave it unset. `SubjectiveMutationBatch` and `subjective-v1` do not change. There is no Alembic revision.
  - `CognitiveLoop._prepare_group_formation` is called in `prepare` immediately after `_prepare_territorial_claims` and before `_prepare_competence`. Do not pass the ledger into deliberation. `DISABLED` returns `None` and does not call `apply_group_update`. The selected `AgentCommand` is unchanged, including `Wait`. The updater does not call `revise_semantic_belief`, `apply_reputation_update`, or `apply_territorial_update`. The caller walks `snapshot.relationships`, projects each counterpart with `project_trust_inputs`, and passes the mapped trust floats in. Thread the optional ledger through `CognitiveLoopInput` the same way `territorial_claims` is threaded. Do not add an inspection route, a subjective query, or edits to `src/api/routes/inspection.py` and `src/simulation/inspection.py`. Add `group_formation` to `_OBJECTIVE_LEAK_FIELDS` in `src/observer/contracts.py`. Update `tests/fakes/cognition.py` only where a constructor grew. Run `uv run ruff check` on each touched file.
  - Logging: DEBUG `group_ledger_carried` or `group_ledger_skipped` with owner id, tick, mode, belief count, and concept count on logger `simulation.agent_runtime`. DEBUG `group_command_unchanged` with owner id and tick on logger `agents.cognition.loop`. No stance tokens.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on tasks 2 and 5.
  - Files: `src/agents/cognition/models.py`, `src/agents/cognition/loop.py`, `src/agents/cognition/contracts.py`, `src/simulation/agent_runtime.py`, `src/simulation/perception.py`, `src/simulation/run_control.py`, `src/observer/contracts.py`, `tests/fakes/cognition.py`, `tests/unit/test_group_formation.py`, `tests/unit/test_group_formation_runtime.py`.

### Phase 3: External Clusters and Persistence

- [x] Task 7: Add analysis-only `emergent_group_formation@1` candidate clusters.
  - Deliverable: `compute_emergent_group_candidates` in `src/analysis/group_formation_metrics.py` implements the eight locked signals and overlapping maximal cliques. Empty input for a signal yields `MetricAvailability.ABSENT` for that signal and does not invent a cluster. Emit cliques sorted by their sorted member-id tuples. Append `MetricFamilyId.EMERGENT_GROUP_FORMATION` with value `emergent_group_formation` after `SPATIAL_CONTROL` in `src/analysis/specifications.py`. Bump `METRIC_FAMILY_COUNT` from 28 to 29. Append `_spec_emergent_group_formation` to `_BUILDERS` with non-empty `value_keys` and `formulas` so `test_every_spec_names_policy_and_version` stays green. `version_identifier` is derived, so the tag is `emergent_group_formation@1`. Update the `== 28` assertion in `tests/unit/test_metric_specifications.py`. Add the new family to the exclusion set in `tests/unit/test_reference_scenario_e2e.py` so `assemble_metric_documents` stays unchanged for catalog A–E. Export the function from `src/analysis/__init__.py`. Do not change `_spec_group_community` value keys. Do not change `spatial_control@1` or `SPATIAL_CONTROL_METRIC_VERSION`. Do not register the new family in the V1 metric bundle used by catalog A–E. Do not bump `METRIC_CATALOG_VERSION`.
  - Duck-type rows and ledgers. The module must not import `agents`. The result type has no path back into `CognitiveLoop`. Reading label `shared_enemies` exists only on the shared-harm signal inside the metric document.
  - Logging: DEBUG `emergent_group_candidates` with signal count, cluster count, and agent count. Logger `analysis.group_formation_metrics`. Do not log reading labels at INFO. Do not log member id lists.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 1.
  - Files: `src/analysis/group_formation_metrics.py`, `src/analysis/specifications.py`, `src/analysis/__init__.py`, `tests/unit/test_group_formation_experiment.py`, `tests/unit/test_metric_specifications.py`, `tests/unit/test_reference_scenario_e2e.py`.
  - Run `uv run ruff check` on each touched file, including `src/analysis/__init__.py`.

- [x] Task 8: Add persistence, split, merge, and agreement hooks.
  - Deliverable: `compute_group_persistence` in the same module consumes ordered candidate documents and optional detached concept rows. It returns continuation, `persistence_fraction`, split counts, merge counts, unstable lineage counts, `cluster_without_concept`, and `concept_without_cluster`. On one signal, compare every cluster at tick `t` with every cluster at `t+1`. A pair continues when Jaccard similarity is at least `0.5`. Matching is all pairs, not a greedy assignment. One earlier cluster with two or more matches records one split. One later cluster with two or more earlier matches records one merge. A lineage is unstable when its present ticks are strictly less than `window_length / 2`. Empty history returns `MetricAvailability.ABSENT`. The function does not mutate input rows and does not return a ledger.
  - Tests in this task cover one signal that persists, one bridge whose removal splits a lineage, one bridge whose addition merges two lineages, a cluster with no concept, and a concept with no cluster. Fixtures are row sequences, not a live `WorldEngine` run.
  - Logging: DEBUG `group_persistence_computed` with tick count, continued links, split count, and merge count. WARNING `group_persistence_empty` with reason `no_history`. No member id lists.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 7.
  - Files: `src/analysis/group_formation_metrics.py`, `tests/unit/test_group_formation_experiment.py`.

### Phase 4: Scenario and Proofs

- [x] Task 9: Add Experiment W off the V1 gate.
  - Deliverable: `experiment_w_emergent_groups` pairs `w-disabled` / `group_formation_disabled` on `runner-config-v4` with `w-enabled` / `group_formation_deterministic` on `runner-config-v16`. Experiment W is unused. Experiment V is already `experiment_v_territorial_claims` and stays unchanged. Arms share seed, scenario, and stochastic identity. The catalog function checks that pairing and the mode field. It does not run the metric and does not require a live tick to mint a concept. Register it in `src/experiments/catalog.py` and export it from `src/experiments/__init__.py`. Do not add it to `tests/unit/test_v1_regression_gate.py`.
  - Scenario builder `emergent_group_scenario` in `src/experiments/group_formation_scenario.py` follows the catalog pairing shape of `experiment_v_territorial_claims`, with its own world. Locations `north` and `south` have one symmetric adjacency edge, and each location has weather. Agents `north_a` and `north_b` start at `north`. Agents `south_a` and `south_b` start at `south`. Agent `lone` starts at `north`. Body ids and agent ids stay distinct, with a counterpart binding for each pair. The builder accepts no team, faction, culture, or roster argument. The world must pass `_validate_topology` and `_validate_weather_coverage`. Do not edit `territorial_claims_scenario` or reuse the scarce and abundant worlds.
  - Logging: DEBUG `experiment_w_built` with experiment id and condition ids. Logger `experiments.catalog`. No utterance text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 2.
  - Files: `src/experiments/group_formation_scenario.py`, `src/experiments/catalog.py`, `src/experiments/__init__.py`, `tests/unit/test_group_formation_experiment.py`.

- [x] Task 10: Prove clusters and recognized groups can diverge, and that groups can overlap, disagree, decay, split, and merge.
  - Deliverable: tests that fail if a scenario accepts a team field, if a candidate cluster can be passed into `apply_group_update`, if proximity alone mints a concept, if one owner's ledger appears on another owner, or if `group_community_structure` value keys change.
  - Required cases in `tests/unit/test_group_formation.py`, `tests/unit/test_group_formation_runtime.py`, and `tests/unit/test_group_formation_experiment.py`:
    - Reciprocal `help` between owner `north_a` and `north_b` mints `our_group` for `{north_a, north_b}` with social evidence. The same one-way `help` leaves a `we` belief and zero concepts.
    - Colocation through `visible_bodies` raises proximity support and withholds a concept with reason `proximity_only`.
    - Owner `north_a` can hold active concepts `{north_a, north_b}` and `{north_a, lone}` at once. Owner `north_b`, given the same occurrences plus an exclusive witnessed talk between `south_a` and `south_b`, can hold `those_agents` for `{south_a, south_b}` while holding no inclusive concept that matches `north_a`'s set.
    - Three ticks of support `0.40` with no new evidence stay active through `0.25`. Support `0.15` retires the concept.
    - A size-3 `our_group` splits when `shared_harm` is recorded between two members, the lexicographically greater member leaves, and the child stores the parent id.
    - Two same-stance concepts at Jaccard `0.5` merge. Two concepts at Jaccard below `0.5` stay two active concepts. Different stances record `stance_mismatch`.
    - Analysis on row fixtures reports all eight signal keys, marks `shared_beliefs` absent when triples are omitted, reports a `shared_enemies` reading only inside the metric document, and reports both `cluster_without_concept` and `concept_without_cluster` on a fixture built to produce each.
    - Persistence fixtures record continuation, one split, one merge, and one unstable lineage.
    - `DISABLED` runtime keeps the command chosen by the pre-group planner, stores no ledger, and leaves semantic belief revision functions uncalled.
    - `group_community_structure` still returns `community_count`, `modularity`, `largest_community_share`, and `node_count` only.
  - Logging: tests may assert DEBUG events listed above. They must not require member id lists in log records.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on tasks 6, 8, and 9.
  - Files: `tests/unit/test_group_formation.py`, `tests/unit/test_group_formation_runtime.py`, `tests/unit/test_group_formation_experiment.py`.

### Phase 5: Documentation

- [x] Task 11: Document the two group readings and the v16 mode.
  - Deliverable: this is the mandatory docs checkpoint. Route the prose through `/aif-docs`. Append to `docs/architecture.md` item 7, after the existing `TerritorialClaimMode` / Experiment V sentence: `runner-config-v16` is emitted only when some agent's `GroupFormationMode` is `DETERMINISTIC`, Experiment W and `emergent_group_formation@1` stay off the V1 gate and out of cognition, and the policy is `group-formation.v1`. Leave the Experiment V sentence in place. Add a section to `docs/social-communication.md` that states candidate clusters, membership beliefs, and `GroupConcept` records are different, that concepts require social evidence, and that overlap, decay, asymmetric beliefs, splits, and merges are expected. Add one sentence to `.ai-factory/DESCRIPTION.md` after the existing `TerritorialClaimMode` / `runner-config-v15` sentence. Do not invent a roadmap milestone.
  - Tests: doc mentions stay consistent with the constants `group-formation.v1`, `emergent_group_formation@1`, `runner-config-v16`, and `group_community_structure`. No new test module is required beyond a link check if `/aif-docs` adds one.
  - Logging: none beyond existing docs tooling.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL` where a docs check emits logs.
  - Depends on tasks 2, 7, and 9.
  - Files: `docs/architecture.md`, `docs/social-communication.md`, `.ai-factory/DESCRIPTION.md`.
