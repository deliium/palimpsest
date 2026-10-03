# Implementation Plan: Repeated Socially Transmitted Conventions

Branch: main
Created: 2026-10-02
Improved: 2026-10-02

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete roadmap milestone. Adds an opt-in owner-scoped convention ledger and external persistence detectors; leaves `multi_hop_testimony_tracking` unowned.

## Compatibility contract

A convention is a private habitual belief of the form "we usually do X in situation Y." It is not a world rule, not a scripted tradition, and not a sanctioning norm. The plan must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only mutation authority. `PhysicalRules`, `_operations`, and `_rules` stay free of convention, ritual, or tradition predicates. Updates read the owner's `Observation`, the owner's previous `ConventionLedger`, the owner's `OwnerSafeSocialIdentity`, and the owner's already-loaded `snapshot.memories` (reinforce-only). They never receive `WorldState`, `PhysicalRules`, `AgentBody`, `WorldEvent`, an event repository, replay, analysis output, another agent's runtime, goals, drives, beliefs, emotion, relationships, mind model, reputation ledger, territorial ledger, group ledger, or norm ledger. They never call a memory reconstructor or import `memory` package writers.
2. Do not own a capability flag. Do not add a `V2CapabilityFlags` field. Do not add `social_conventions`, `traditions`, or any new flag name. `multi_hop_testimony_tracking` stays unimplemented and still fails closed with `capability_unimplemented`. Off for this feature is `SocialConventionMode.DISABLED`, which does not change commands, memories, semantic beliefs, relationships, reputation, territorial claims, group formation, social norms, or audits.
3. V1 regression gate stays green under flags-off, convention-mode disabled, and tracing-off. Catalog A–E and the reference scenario keep their current `exact_trajectory_hash` values. Experiment Y is additive and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. Schema bump only for the enabled mode. Default write stays `runner-config-v4`. Add `runner-config-v18` to the accepted set. v18 carries every `runner-config-v17` key plus `social_convention_mode` on each agent. Emit v18 only when some agent's `SocialConventionMode` is `DETERMINISTIC`. A norms-only config still writes v17. Reject v18 when every social-convention mode is `DISABLED` (`v18_requires_social_conventions`). Reject `DETERMINISTIC` social-convention mode on v1–v17 (`social_convention_mode_requires_v18`). Widen every existing mode and spec allowlist that currently ends at v17 so v18 remains legal for communication strategy, reputation, skill learning, teaching, production knowledge, reflection, consolidation, prospective imagination, counterfactual reasoning, environmental dynamics, territorial claims, group formation, and social norms. That includes the named frozensets in `src/simulation/runner_serialization.py` and every local set in `SimulationRunnerConfig.__post_init__` that currently ends at v17. Encode and decode `capability_flags` and `cognition_trace` on v18. Encode and decode `environmental_dynamics` on v18 when the spec is present, using the same rule as v17. **Encode and decode `social_norm_mode` on both v17 and v18** (today it is exact-equality on v17 only — a norms+conventions config writes v18 and must not drop the norm field). Encode `group_formation_mode` on `{v16, v17, v18}` and widen every other prior-mode membership set that currently ends at v17 the same way. Encode `social_convention_mode` only on v18. Decode v18 agent cognition with `_COGNITION_KEYS_V18`, defined as `_COGNITION_KEYS_V17` plus `social_convention_mode`, before the v17 branch. `_require_keys` is an exact key check. Norms-only equality (`v17_requires_social_norms`) stays an equality check on v17. A config that enables both social norms and social conventions writes v18, so `social_norm_mode_requires_v17` becomes membership in `{v17, v18}`. `group_formation_mode_requires_v16` becomes membership in `{v16, v17, v18}`. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. No policy weights in runner JSON. Leave `v1_regression_profile` unchanged. Baseline: the accepted set already ends at `runner-config-v17`.
5. No scripted emergence. No tradition, ritual, custom, culture, ceremony, or roster **field** on `World`, `WorldState`, `Observation`, commands, events, or scenario builders. No predefined tradition scripts or named ceremony catalogs. Closed communication relation predicates `usually`, `greet`, and `custom` remain legal (same pattern as norms' `expect` / `criticize`); they are utterance tokens, not world fields. No new `AgentCommand`, `ActionDirection`, `CommunicationSourceBasis`, `RelationshipDimension`, or `WorldEvent` kind. Scenarios must not contain a tradition, ritual, or convention field. Sleep stays a one-tick fatigue action.
6. No LLM path. There is no provider schema and no prompt package. `DETERMINISTIC` never calls `LLMProvider`.
7. Experiments stay reproducible. Paired arms share seed, topology, and stochastic identity. No RNG and no wall clock in convention updates. Experiment Y and `persistent_social_conventions@1` stay analysis-only and off the V1 regression gate. The metric is not an input to cognition. `repeated_conventions@1` stays the existing motif family and is not rewritten. `emergent_social_norms@1` stays unchanged.
8. Optional cognition tracing stays outside the objective fold. Do not insert a `ComponentKind` or an ordinal in `_STAGE_ORDER`. Do not bump `COGNITION_TRACE_SUMMARY_SCHEMA`, add trace enum members, or add an Alembic revision. Do not copy pattern tokens, participant ids, explanations, or analysis readings onto the trace summary. `subjective-v1` stays unchanged. Tracing on versus off must not change `exact_trajectory_hash` when the mode is `DISABLED`.

## Goal

Objective repetition, private habit belief, and analytical ritual/tradition labels stay different objects.

| Layer | What it is | Who may read it during a tick |
| --- | --- | --- |
| Objective repetition | External motif / co-occurrence counts over the objective log (existing `repeated_conventions@1` plus new persistence/transmission detectors) | Analysis only, after the fact |
| Convention belief | One owner's private habit: "we usually do X in situation Y," with participants, duration, transmission, remembered explanation, and competing variants | That owner's cognition |
| Analytical label | Detector scores such as `reason_loss_persistence` or `ritual_like_persistence` | Analysis only; never written onto the ledger |

A regularity can be frequent when every ledger is empty. An agent can hold a habit belief that the objective rate does not support. One owner's ledger is not copied to another owner. Ritual and tradition labels stay analytical until an agent itself forms a closed conceptualization token from communicated evidence.

`repeated_conventions@1` already counts action n-grams. This plan leaves that family, its algorithm, and its value keys unchanged. `persistent_social_conventions@1` is a separate document with blocks for objective persistence, subjective habit, transmission, reason-loss, and competing variants.

## Design Decisions (locked)

- **A ledger, not a world rule and not a semantic belief.** `ConventionLedger` is owner-scoped state on `SubjectiveSnapshot.social_conventions`, default `None`. It holds `ConventionBelief` values. A belief is not a `SemanticBelief`, not a `NormBelief`, not a `GroupConcept`, not a `ReputationProfile`, and not a `DirectedRelationshipProfile`. Updates do not call `revise_semantic_belief`, `apply_norm_update`, `apply_group_update`, `merge_relationship_revision`, or reputation/territorial writers. The updater must not read `NormLedger` or any other owner's convention ledger. When both `SocialNormMode` and `SocialConventionMode` are `DETERMINISTIC`, a `give` may contribute to both ledgers in the same tick; dual counting is intentional (habit vs expectation).
- **Disabled mode is a passthrough.** `SocialConventionMode.DISABLED` leaves `snapshot.social_conventions` as `None`, appends no evidence, emits no utterance, applies no intention bias, and writes no runner field. Commands match the pre-convention planner.
- **Situation families are detectors, not tradition scripts.** Closed `ConventionSituation`: `colocated_meeting`, `timed_gathering`, `greeting_exchange`, `habitual_exchange`, `collective_action`. These name observable situation shapes (place, day phase, talk, give, multi-agent same action). They are not named traditions, ceremonies, or culture roles. Tokens are absent from world events and from INFO logs.
- **Meeting attribution is exclusive.** For wait/talk meeting evidence: if `Observation.day_phase` is not `None`, attribute only to `timed_gathering` (store phase on first evidence; later ticks must match). Otherwise attribute only to `colocated_meeting`. Never feed the same wait/talk occurrence into both situations on one tick.
- **Habit content is situation + usual action.** `ConventionContent` stores `situation`, `usual_action` (closed action-kind token from the existing vocabulary), optional `location_id`, optional `day_phase`, and optional `counterpart_class` (`none`, `specific_agent`, `any_present`). Belief id is sha256 of owner id and the canonical content key. Competing variants share situation/location/day_phase but differ in `usual_action`.
- **Subjective form.** Each active belief is the owner's approximate claim "we usually do X in situation Y." Status values: `candidate`, `active`, `retired`. Promotion requires repetition count at least `3`, participant count at least `2` (except `habitual_exchange` may promote at 1 directed counterpart after 3 repetitions), and habit strength at least `0.40`.
- **Tracked fields on every belief.**
  - `repetition_count` — conforming observations, remembered reinforcements, or adopted testimony count
  - `participant_ids` — resolved agent ids capped at 8
  - `first_tick` / `last_tick` — duration span
  - `transmission` — closed `ConventionTransmission` on the belief: `observed`, `communicated`, `both`. Evidence items carry a separate channel including `remembered`. Remembered reinforcement does not change an `observed`/`communicated`/`both` belief field by itself.
  - `remembered_explanation` — closed `ConventionExplanation`: `resource_access`, `fatigue_rest`, `coordination`, `hunger_relief`, `social_contact`, `unknown`, `forgotten`
  - `competing_variant_ids` — other belief ids that share situation key but differ in `usual_action`
  - `conceptualization` — closed `ConventionConceptualization`: `none`, `named_usual`, `named_custom` (the last only after the owner receives a delivered utterance whose relation predicate is exactly `custom` citing this content; never seeded by scenarios)
- **Reason fade without habit fade.** When the practical cue that first supported an explanation is absent for `explanation_fade_ticks` (8) consecutive ticks while the habit still receives conforming evidence, set explanation to `forgotten` and keep status `active` if strength stays `>= 0.40`. Decay of `0.05` applies only when neither conforming evidence nor successful transmission/memory evidence arrived this tick. Strength below `0.20` retires the belief.
- **Initial explanation inference (closed, deterministic).** At first candidate creation only: `timed_gathering`/`colocated_meeting` → `coordination` if multiple others present else `social_contact`; `greeting_exchange` → `social_contact`; `habitual_exchange` → `resource_access` when a local resource quantity is `<= 1.0` else `unknown`; `collective_action` with `sleep` → `fatigue_rest`; `collective_action` with `eat` → `hunger_relief`; otherwise `unknown`. Never invent free-form prose.
- **Evidence from observation (learn, do not script).** Dedup on `(situation, usual_action, source_event_id)` with lineage `tick-{tick}-{ordinal}` when event id is missing.

| Evidence the owner has this tick | Situation / usual action | Delta | Notes |
| --- | --- | --- | --- |
| Owner and at least one other resolved body at same location; owner or other `wait` or `talk`; `day_phase` is `None` | `colocated_meeting` / that action | conforming `+0.12` | Participants = present resolved agents. Not used when day_phase is present. |
| Same wait/talk meeting rule, and `day_phase` is not `None` (first evidence stores phase; later must match) | `timed_gathering` / that action | conforming `+0.15` | Exclusive with colocated_meeting on the same occurrence. |
| Delivered talk/ask/tell hop 0 or 1 with relation predicate exactly `greet` | `greeting_exchange` / `talk` | conforming `+0.12` | Exact predicate only. No "bare talk counts as greet" fallback. |
| Successful `give` (success is not `False`) involving owner or witnessed between two resolved agents | `habitual_exchange` / `give` | conforming `+0.15` | Counterpart stored when directed. May also feed norms when that mode is on. |
| Two or more resolved agents including or witnessed by owner perform the same action kind this tick at the owner's location | `collective_action` / that action kind | conforming `+0.15` | Caps participants at 8 |

- **Memory reinforcement (channel `remembered`).** `apply_convention_update` also accepts the owner's already-loaded `memories` sequence from `SubjectiveSnapshot`. For each `MemoryTrace`, scan `concepts` and `relations` for closed tokens matching a content key already present on the ledger, or relation predicates in `{usually, greet, custom}` citing that key. On match, reinforce that existing belief by `+0.08` and append evidence with channel `remembered`. **Never mint a new belief from memory alone.** Do not import reconstructors, `MemoryService`, or analysis. Forgotten/expired traces (`forgotten_at_tick` set, or `expires_at_tick` elapsed) are ignored. Dedup remembered items on `(belief_id, memory_id)`.
- **Transmission via communication.** When the owner is listener on a delivered utterance with relation predicate `usually` and object tokens matching a known content key (situation + action + optional location), adopt or reinforce that belief with channel `communicated` (or upgrade `observed` → `both`). Delta `+0.10`. Speaker must resolve; unresolved yields `unresolved_entity` and no adoption. Owner never copies the speaker's ledger object — only the closed content tokens from the utterance.
- **Communicate without inventing commands.** When habit strength `>= 0.40`, a `COMMUNICATE` future already exists, and the owner has not uttered this content in the last `utterance_interval` ticks (4), prefer that future by adding penalty `0.30` to other futures. `convention_communicate_utterance(...)` returns the relation recipe for an existing Talk (predicate `usually`, subject=situation, object=usual_action, `CommunicationSourceBasis.UNREFERENCED`), mirroring `norm_communicate_utterance`. Do not construct a new `Talk`. Conceptualization `named_custom` may instead use predicate `custom` only when that conceptualization is already `named_custom`.
- **Habit bias without inventing commands.** `convention_habit_penalties(...)` returns a map of future id → non-negative float (quantum `0.30`) favoring futures whose action matches an active belief's `usual_action` when the current observation matches that belief's situation. Missing preferred future records `no_candidate` and does not insert a command. Same shape as `norm_response_penalties` / `territorial_respect_penalties`.
- **Bodies and agents stay distinct.** Occurrence and utterance ids are `EntityId`. Ledger owner and participant ids are `AgentId`. Resolve with `OwnerSafeSocialIdentity`. Unresolved → `unresolved_entity`, no participant.
- **Carry follows social norms.** Add `social_conventions` beside `social_norms` on `SubjectiveSnapshot`, `CognitiveLoopProposal`, `CognitiveLoopResult`, `AgentRuntimeCheckpoint`, `Perspective`, and `build_perspective`. `AgentRuntime` holds the ledger the same way, default `None`, with `require_owner_social_conventions`. `CognitiveLoop.prepare` calls `_prepare_social_conventions` immediately after `_prepare_social_norms` and before `_prepare_competence`, passing `snapshot.memories` into `apply_convention_update`. Pass the ledger into intention/planning through `_planner_options`. Wire `convention_communicate_utterance` in deliberation beside the norm utterance path. `SubjectiveMutationBatch` does not grow a convention field. `subjective-v1` unchanged. No Alembic revision. Disabled checkpoint stores `None`.
- **Quantization and caps.** Strength quantized to `1e-6`, clamped to `[0, 1]`. At most 8 beliefs per owner, 32 evidence items per belief, 8 participants, 4 competing variant links. Further items drop with `cap_exceeded`. No RNG, wall clock, or Python `hash()`.
- **Fail closed.** Unknown situation, explanation, transmission, conceptualization, or status; owner mismatches; non-finite numbers; future penalty below 0 abort with stable reason codes. Passing `WorldState`, `WorldEvent`, or a metric document into `apply_convention_update` raises `TypeError`.
- **Ritual/tradition labels are analysis-only by default.** Cognition never stores strings `ritual` or `tradition`. Analysis may compute `ritual_like_persistence` as a detector over reason-loss + duration + multi-participant repetition. Agent-side `named_custom` is the only path toward agent conceptualization and still does not write analysis labels into the ledger.

### Analysis

`compute_persistent_social_conventions` in `src/analysis/social_convention_metrics.py` builds blocks from caller-supplied rows. Duck-type with `getattr`. Must not import `agents`, `apply_convention_update`, or `AgentRuntime`.

**Block `objective_persistence`** from objective rows `(tick, actor_id, kind, other_id, success, location_id, day_phase)`:

| Key | Value |
| --- | --- |
| `recurrent_meeting_rate` | Colocated multi-agent wait/talk ticks divided by multi-agent colocated ticks |
| `timed_gathering_rate` | Same with matching day phase across at least 3 distinct ticks |
| `habitual_exchange_rate` | Repeated give pairs within window 8 divided by opened give opportunities |
| `collective_action_rate` | Ticks where ≥2 agents share action kind at one location, divided by multi-agent colocated ticks |

Empty denominators → `MetricAvailability.ABSENT` for that key only.

**Block `subjective_habit`** from detached belief rows `(tick, owner_id, situation, usual_action, status, strength, participant_count, transmission, explanation, conceptualization, duration_ticks, variant_count)`:

| Key | Value |
| --- | --- |
| `active_habit_count` | Rows with status `active` |
| `mean_habit_strength` | Mean strength of active rows; none → `ABSENT` |
| `mean_duration_ticks` | Mean `last_tick - first_tick` of active rows |
| `mean_participant_count` | Mean participants on active rows |
| `transmission_adoption_rate` | Active rows with transmission in `{communicated, both}` divided by active rows |
| `forgotten_reason_rate` | Active rows with explanation `forgotten` divided by active rows |
| `competing_variant_share` | Active rows with `variant_count >= 1` divided by active rows |
| `named_custom_rate` | Active rows with conceptualization `named_custom` divided by active rows |

**Block `divergence`:**

| Key | Value |
| --- | --- |
| `repetition_without_habit` | Situation families whose objective rate `>= 0.50` while every owner has zero active habits for that situation |
| `habit_without_repetition` | Active habits whose situation objective rate `< 0.50` or `ABSENT` |
| `reason_loss_persistence` | Fraction of adjacent history ticks that keep an active habit with explanation `forgotten` and strength `>= 0.40` |
| `ritual_like_persistence` | Analysis-only composite: fraction of history steps where an active habit has explanation in `{forgotten, unknown}`, duration `>= 8`, participants `>= 2`, and strength `>= 0.40`. Label stays in analysis values only |

`compute_convention_persistence` takes ordered documents and reports `behavior_persistence` (objective rate stays `>= 0.50`) and `habit_persistence` (same owner+situation+action still active at strength `>= 0.40`). Empty history → `ABSENT`.

Family id `persistent_social_conventions`. Tag `persistent_social_conventions@1`. Bump `METRIC_FAMILY_COUNT` from 30 to 31. Not added to the V1 bundle for catalog A–E.

## Non-Goals

- A `WorldEngine` predicate that forces meetings, greetings, exchanges, or collective actions
- Predefined tradition/ritual scripts, ceremony catalogs, or culture role fields on world/scenario objects (communication predicates `usually` / `greet` / `custom` are allowed)
- Rewriting `repeated_conventions@1` or `emergent_social_norms@1`
- Writing convention tokens into `SemanticBelief` or `NormLedger`
- Reading `NormLedger` from the convention updater (dual give counting when both modes are on is fine)
- Minting a new convention belief from memory alone
- A new `AgentCommand`, `ActionDirection`, `CommunicationSourceBasis`, or `WorldEvent` kind
- Inserting talk/give/wait futures the planner did not already propose
- Owning `multi_hop_testimony_tracking`
- Inserting a `CognitiveLoop` ordinal, bumping cognition-trace schema, bumping `subjective-v1`, or adding an Alembic revision
- Letting an agent read another agent's ledger or any analysis document
- An LLM assessor or free-form tradition prose
- Putting Experiment Y on the V1 regression gate
- Feeding `ritual_like_persistence` or other analysis labels into cognition
- Treating bare talk with no relation as a greeting

## Commit Plan
- **Commit 1** (after tasks 1–2): `feat(simulation): add opt-in social conventions on runner-config-v18`
- **Commit 2** (after tasks 3–6): `feat(cognition): learn owner-scoped habitual conventions`
- **Commit 3** (after tasks 7–9): `test(analysis): detect persistent transmitted conventions`
- **Commit 4** (after tasks 10–11): `docs(cognition): document repeated social conventions`

## Tasks

### Phase 1: Contracts and Mode

- [x] Task 1: Add social-convention contracts and `SocialConventionPolicy`.
  - Deliverable: frozen types in `src/agents/cognition/social_conventions.py`, exported from `src/agents/cognition/__init__.py`. `DISABLED` leaves the snapshot field `None`.
  - Types: `ConventionSituation` (`colocated_meeting`, `timed_gathering`, `greeting_exchange`, `habitual_exchange`, `collective_action`), `ConventionExplanation` (`resource_access`, `fatigue_rest`, `coordination`, `hunger_relief`, `social_contact`, `unknown`, `forgotten`), `ConventionTransmission` (`observed`, `communicated`, `both`), `ConventionEvidenceChannel` (`observed`, `communicated`, `remembered`), `ConventionConceptualization` (`none`, `named_usual`, `named_custom`), `ConventionStatus` (`candidate`, `active`, `retired`), `ConventionEvidenceItem`, `ConventionContent`, `ConventionBelief`, `ConventionLedger`, `SocialConventionPolicy` (`social-conventions.v1`, active strength `0.40`, retire strength `0.20`, decay `0.05`, conforming deltas as locked, transmission delta `0.10`, remembered delta `0.08`, penalty `0.30`, promotion count `3`, explanation fade ticks `8`, utterance interval `4`, caps 8 beliefs / 32 evidence / 8 participants / 4 variants). `CognitionSocialConventionMode` (`DISABLED`, `DETERMINISTIC`) in `src/agents/cognition/configuration.py` and matching runner enum in `src/simulation/runner_models.py`.
  - Constructors reject unknown enums, participant sets larger than 8, and `named_custom` without prior communicated `custom` evidence lineage.
  - Logging: logger `agents.cognition.social_conventions`. DEBUG on construction with owner id, policy version, and belief count. ERROR with field name and reason code on validation failure. No participant id lists, no situation tokens at INFO, never log `ritual`/`tradition` as cognition fields.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Files: `src/agents/cognition/social_conventions.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/__init__.py`, `src/simulation/runner_models.py`, `tests/unit/test_social_conventions.py`.

- [x] Task 2: Wire `DETERMINISTIC` through `runner-config-v18` without owning a new flag.
  - Deliverable: mode off keeps `runner-config-v4` and today's commands. Mode on is accepted only as `runner-config-v18`. `multi_hop_testimony_tracking` still fails closed. A v18 document can still carry every prior mode including social norms.
  - Add `social_convention_mode` to `AgentCognitionSpec` and `CognitionLoopConfig`. Default both to `DISABLED`. Accept v18 in `SUPPORTED_RUNNER_SCHEMA_VERSIONS`. Define `_COGNITION_KEYS_V18` as `_COGNITION_KEYS_V17` plus `social_convention_mode`. Add v18 to every allowlist that currently ends at v17. Encode/decode `capability_flags`, `cognition_trace`, and optional `environmental_dynamics` on v18. **Encode/decode `social_norm_mode` on `{v17, v18}`** (replace today's exact `== v17` branches). Encode `group_formation_mode` on `{v16, v17, v18}` and widen other prior-mode membership sets ending at v17 the same way. Encode `social_convention_mode` only on v18. Decode v18 before the v17 branch. Keep `v17_requires_social_norms` as equality on v17. `social_norm_mode_requires_v17` becomes membership in `{v17, v18}`. `group_formation_mode_requires_v16` becomes membership in `{v16, v17, v18}`. Add `social_convention_mode_requires_v18` and `v18_requires_social_conventions`. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. Do not add a `V2CapabilityFlags` field. `simulation.runner._cognition_config_for` sets `CognitionSocialConventionMode.DETERMINISTIC` only from that field and builds `default_social_convention_policy()`. Update `src/simulation/compatibility.py`. Export `RUNNER_SCHEMA_VERSION_V18` from `src/simulation/__init__.py`.
  - Tests: multi_hop still `capability_unimplemented`; disabled mode does not bump schema; norms-only still writes v17; convention deterministic writes v18 and round-trips **including `social_norm_mode` when both modes are on**; v18 with convention mode disabled is rejected; norms+conventions writes v18. One combined config with conventions, norms, groups, and environmental dynamics round-trips flags and tracing. Run `uv run ruff check` on each touched file.
  - Logging: DEBUG `cognition_config_social_convention_mode mode=%s policy_version=%s` on logger `simulation.runner`. ERROR on schema rejection uses existing stable runner codes.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 1.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/runner.py`, `src/simulation/__init__.py`, `src/agents/cognition/configuration.py`, `tests/unit/test_runner_models.py`, `tests/unit/test_runner_serialization.py`, `tests/unit/test_simulation_runner_construction.py`, `tests/unit/test_v2_flag_defaults.py`, `tests/unit/test_cognition_configuration.py`, `tests/unit/test_compatibility_matrix.py`.

### Phase 2: Private Habit Learning

- [x] Task 3: Apply observation and memory evidence into owner-scoped convention beliefs.
  - Deliverable: `apply_convention_update(...)` returns a new `ConventionLedger` for one owner. Accepts this tick's `Observation`, `OwnerSafeSocialIdentity`, previous ledger, and optional owner `memories` sequence. Passing `WorldState`, `WorldEvent`, or a metric document raises `TypeError`. Module must not import `analysis`, `simulation`, `world.models`, `world.events`, or `world._state`. May import `world.observations` and `world.communications` contracts for relation predicates only. May type-check `MemoryTrace` via `TYPE_CHECKING` or duck-typing on `concepts`/`relations`/`memory_id` without importing reconstructors or `MemoryService`.
  - Apply locked evidence table and tick order: open/match situations → conforming deltas → remembered reinforcement → participant/duration updates → explanation fade → candidate promotion → competing-variant links → decay. Meeting wait/talk uses exclusive attribution (timed vs colocated). Greetings require predicate exactly `greet`. Memory reinforces existing beliefs only (`+0.08`, channel `remembered`); never mints. Unknown occurrence kinds leave the ledger unchanged. Caps drop with `cap_exceeded`.
  - Logging: DEBUG `convention_belief_applied` with owner id, tick, and sign. DEBUG `convention_memory_reinforced` with owner id and tick when remembered evidence applies. INFO `convention_belief_updated` with owner id and belief count. WARNING `convention_evidence_dropped` with reason `cap_exceeded`, `ignored_kind`, `unresolved_entity`, or `memory_no_match`. ERROR on owner mismatch. No participant lists and no utterance text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 1.
  - Files: `src/agents/cognition/social_conventions.py`, `tests/unit/test_social_conventions.py`.

- [x] Task 4: Promote candidates, fade explanations while habits persist, and link competing variants.
  - Deliverable: promote `candidate` → `active` under locked thresholds. After `explanation_fade_ticks` without the original practical cue but with continuing conforming evidence, set explanation `forgotten` and keep `active` when strength `>= 0.40`. Link competing variants that share situation key and differ in `usual_action` (cap 4). Two owners updated from the same occurrences keep separate ledgers. Decay `0.05` when no evidence this tick; retire below `0.20`.
  - Logging: DEBUG `convention_belief_promoted`, `convention_explanation_forgotten`, or `convention_belief_retired` with owner id, tick, and status. WARNING `convention_belief_withheld` with reason `below_count`, `below_strength`, or `candidate`. No participant lists.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 3.
  - Files: `src/agents/cognition/social_conventions.py`, `tests/unit/test_social_conventions.py`.

- [x] Task 5: Adopt conventions from communication and emit `usually` without creating commands.
  - Deliverable: listener path adopts/reinforces from predicate `usually` (and upgrades conceptualization to `named_custom` only from predicate `custom`). `convention_habit_penalties(...)` and communicate-prefer path use locked quantum `0.30`. Add `convention_communicate_utterance(...)` mirroring `norm_communicate_utterance` (returns relation recipe for an existing Talk; does not construct commands). Disabled mode and non-ledger return empty map / `None`. Missing preferred future records `no_candidate`. Functions do not construct `Talk`, `Give`, or `Wait`.
  - Logging: DEBUG `convention_transmission_applied` / `convention_response_selected` with owner id, tick, and channel/response. WARNING `convention_response_withheld` with reason `no_candidate`, `candidate_only`, or `utterance_interval`. No utterance text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 4.
  - Files: `src/agents/cognition/social_conventions.py`, `tests/unit/test_social_conventions.py`.

- [x] Task 6: Prove world authority is unchanged by convention habits.
  - Deliverable: focused regression in `tests/unit/test_social_conventions_world.py`: meetings, greetings, gives, and collective waits still admit under current physical rules with no engine convention check. Tests call existing operations only.
  - Logging: DEBUG only on existing world loggers; no convention tokens in world logs.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 5.
  - Files: `tests/unit/test_social_conventions_world.py`.

### Phase 3: Runtime and Measurement

- [ ] Task 7: Carry the ledger and pass habit penalties into deliberation.
  - Deliverable: add `social_conventions` beside `social_norms` on `SubjectiveSnapshot`, `CognitiveLoopProposal`, `CognitiveLoopResult`, `Perspective`, `build_perspective`, and `AgentRuntime` checkpoint state (same surfaces norms already use in `agent_runtime.py`, `perception.py`, and `run_control.py`). `require_owner_social_conventions` accepts `None` or matching-owner `ConventionLedger`. `CognitiveLoop.prepare` calls `_prepare_social_conventions` immediately after `_prepare_social_norms`, passing `snapshot.memories` into `apply_convention_update`. Thread through `_planner_options` and apply `convention_habit_penalties` next to norm penalties in `deliberation.py`. Wire `convention_communicate_utterance` beside `norm_communicate_utterance`. `DISABLED` keeps pre-convention commands.
  - Do not insert a `ComponentKind`. Do not bump `subjective-v1`.
  - Logging: DEBUG `social_conventions_carried` with owner id and belief count on logger `agents.cognition.loop`. DEBUG `convention_penalty_applied` with future count on logger `agents.cognition.deliberation`. WARNING `convention_carry_rejected` with reason `owner_mismatch` or `invalid_type`.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on tasks 2 and 5.
  - Files: `src/agents/cognition/models.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/loop.py`, `src/agents/cognition/deliberation.py`, `src/simulation/agent_runtime.py`, `src/simulation/perception.py`, `src/simulation/run_control.py`, `tests/unit/test_social_conventions_runtime.py`.

- [ ] Task 8: Add external detectors for persistent repeated conventions.
  - Deliverable: `compute_persistent_social_conventions` and `compute_convention_persistence` in `src/analysis/social_convention_metrics.py`. Add `MetricFamilyId.PERSISTENT_SOCIAL_CONVENTIONS`, bump `METRIC_FAMILY_COUNT` from 30 to 31, register tag `persistent_social_conventions@1`. Implement locked keys including `reason_loss_persistence` and analysis-only `ritual_like_persistence`. Leave `compute_repeated_conventions` and `compute_emergent_social_norms` unchanged.
  - Logging: logger `analysis.social_convention_metrics`. DEBUG `social_conventions_metric_computed` with situation count and active habit count. WARNING `social_conventions_metric_empty` with reason `no_rows` or `no_history`. No owner id lists.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 1.
  - Files: `src/analysis/social_convention_metrics.py`, `src/analysis/specifications.py`, `src/analysis/__init__.py`, `src/analysis/metric_service.py`, `tests/unit/test_social_convention_metrics.py`, `tests/unit/test_metric_specifications.py`.

- [ ] Task 9: Add Experiment Y off the V1 gate.
  - Deliverable: `experiment_y_social_conventions` pairs `y-disabled` / `social_conventions_disabled` on `runner-config-v4` with `y-enabled` / `social_conventions_deterministic` on `runner-config-v18`. Arms share seed, scenario, and stochastic identity. Register in `src/experiments/catalog.py` and export from `src/experiments/__init__.py`. Do not add to `tests/unit/test_v1_regression_gate.py`.
  - Scenario builder `social_conventions_scenario` in `src/experiments/social_conventions_scenario.py`: one location `clearing`, day/night weather, three agents `ada`, `ben`, `cy`, distinct body ids, modest food resource. `max_ticks` default 24 so promotion, fade window, and transmission can elapse. Builder accepts no tradition, ritual, convention, culture, or roster argument.
  - Enabled arm may finish with zero active habits. Disabled arm must finish with `social_conventions is None` on every runtime. Catalog test asserts metric blocks are requested for the enabled arm when rows exist.
  - Logging: DEBUG `experiment_y_built` with experiment id and condition ids. Logger `experiments.catalog`. No utterance text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on tasks 2 and 8.
  - Files: `src/experiments/social_conventions_scenario.py`, `src/experiments/catalog.py`, `src/experiments/__init__.py`, `tests/unit/test_social_conventions_experiment.py`.

### Phase 4: Proofs

- [ ] Task 10: Prove habit learning, reason-loss persistence, transmission, memory reinforce-only, and label separation.
  - Deliverable: tests that fail if a scenario accepts a tradition/ritual field, if a metric document can be passed into `apply_convention_update`, if one conforming event promotes a belief, if one owner's ledger appears on another owner, if `repeated_conventions` value keys change, if `ritual`/`tradition` appear as cognition ledger fields, if bare talk without `greet` creates `greeting_exchange`, if memory alone mints a belief, or if disabled mode changes the command.
  - Required cases across `tests/unit/test_social_conventions.py`, `test_social_conventions_runtime.py`, `test_social_conventions_world.py`, `test_social_conventions_experiment.py`, and `test_social_convention_metrics.py`:
    - Three colocated meeting ticks promote `colocated_meeting`; one tick stays `candidate` with `below_count`.
    - Timed gathering stores day phase on first evidence and only reinforces on matching phase; wait/talk with day_phase does not also create colocated_meeting.
    - Habitual exchange promotes after three successful gives; competing `wait` variant for same situation links in `competing_variant_ids`.
    - Explanation fades to `forgotten` after 8 ticks without the original cue while conforming evidence continues; strength stays active.
    - Listener adopts via `usually` with transmission `communicated`; speaker ledger is not copied by object identity.
    - Memory with matching tokens reinforces an existing candidate/active belief; the same memory set with an empty ledger leaves the ledger empty / unchanged (no mint).
    - `named_custom` only after predicate `custom`; never from scenario seeds.
    - `DISABLED` runtime keeps pre-convention command and stores no ledger.
    - Metric fixtures report `repetition_without_habit`, `habit_without_repetition`, `reason_loss_persistence`, and `ritual_like_persistence` on separate setups; persistence splits behavior vs habit.
  - Logging: tests may assert DEBUG events listed above. They must not require participant id lists in log records.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on tasks 6, 7, 8, and 9.
  - Files: `tests/unit/test_social_conventions.py`, `tests/unit/test_social_conventions_runtime.py`, `tests/unit/test_social_conventions_world.py`, `tests/unit/test_social_conventions_experiment.py`, `tests/unit/test_social_convention_metrics.py`.

### Phase 5: Documentation

- [ ] Task 11: Document the habit/belief/analysis split and the v18 mode.
  - Deliverable: mandatory docs checkpoint via `/aif-docs`. Append to `docs/architecture.md` item 7 after the existing `SocialNormMode` / Experiment X sentence: `SocialConventionMode` defaults to `DISABLED`, `runner-config-v18` is emitted only when some agent's mode is `DETERMINISTIC`, Experiment Y and `persistent_social_conventions@1` stay off the V1 gate and out of cognition, and the policy is `social-conventions.v1`. Add a section to `docs/social-communication.md` stating objective repetition, owner habit beliefs ("we usually do X in Y"), observation + memory reinforce + communication, remembered explanations, competing variants, and that ritual/tradition labels are analysis-only until `named_custom`. Add one sentence to `.ai-factory/DESCRIPTION.md` after the existing social-norms / `runner-config-v17` sentence. Update `.ai-factory/ROADMAP.md` M6 to list this plan (already started in `/aif-plan`). Do not invent a roadmap milestone.
  - Tests: doc mentions stay consistent with `social-conventions.v1`, `persistent_social_conventions@1`, `runner-config-v18`, and `repeated_conventions`.
  - Logging: none beyond existing docs tooling.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL` where a docs check emits logs.
  - Depends on tasks 2, 8, and 9.
  - Files: `docs/architecture.md`, `docs/social-communication.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ROADMAP.md`.
