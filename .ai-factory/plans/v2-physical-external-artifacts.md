# Implementation Plan: Physical External Information Artifacts

Branch: main
Created: 2026-10-03
Improved: 2026-10-03 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete roadmap milestone; this plan adds WorldEngine-owned external information artifacts and an opt-in interpretation mode, and leaves `multi_hop_testimony_tracking` unowned.

## Compatibility contract

This plan adds an objective external-memory channel on top of the existing physical world. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only objective mutation authority for artifact create/modify/move/destroy. Cognition never receives `WorldState`, private world modules, another agent's observation, or another agent's interpretation ledger. Observation proves physical presence and objective marks only — never shared meaning.
2. Do not own a capability flag. Do not add a `V2CapabilityFlags` field. Do not add `external_artifacts`, `collective_memory`, or any new flag name. `multi_hop_testimony_tracking` stays unimplemented and still fails closed with `capability_unimplemented`. Off for this feature is an empty `WorldState.artifacts` map plus `ArtifactInterpretationMode.DISABLED`. That pair does not change commands chosen by V1 agents, memories, beliefs, relationships, audits, or `exact_trajectory_hash` for catalog A–E and the reference scenario. World admission still accepts artifact commands when tests/scripts submit them; cognition simply does not compile them when the mode is `DISABLED`.
3. V1 regression gate stays green under flags-off, interpretation mode `DISABLED`, empty artifacts, and tracing-off. Catalog A–E and the reference scenario keep their current `exact_trajectory_hash` values. Experiment Z is additive and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. Schema bumps use accepted-set + exact key-set discipline. Default write stays `runner-config-v4` and replay-v5. Add `runner-config-v19` to the accepted set; emit it only when some agent's `ArtifactInterpretationMode` is `DETERMINISTIC`. Add `EVENT_SCHEMA_REPLAY_V8` as accepted. **Event/codec write pair is chosen at run start** by an extended helper (see Write pair) — never mid-run after the first artifact commit. `CURRENT_PHYSICAL_EVENT_SCHEMA_VERSION` and `EVENT_SCHEMA_VERSION` stay replay-v5. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. Widen every prior-mode allowlist that currently ends at v18 so v19 remains legal. Define `_COGNITION_KEYS_V19` as `_COGNITION_KEYS_V18` plus `artifact_interpretation_mode`; decode v19 before the v18 branch; `_require_keys` stays exact. Encode `artifact_interpretation_mode` only on v19. Reject v19 when every artifact-interpretation mode is `DISABLED` (`v19_requires_artifact_interpretation`). Reject `DETERMINISTIC` on v1–v18 (`artifact_interpretation_mode_requires_v19`). Equality `v18_requires_social_conventions` stays equality on v18. Membership upgrades at least: `social_convention_mode` → `{v18, v19}`; `social_norm_mode` → `{v17, v18, v19}`; `group_formation_mode` → `{v16, v17, v18, v19}`; and every other mode/spec set that currently ends at v18 gains v19 the same way (named frozensets in `runner_serialization.py` and every local set in `SimulationRunnerConfig.__post_init__`). Encode/decode `capability_flags`, `cognition_trace`, `environmental_dynamics`, `social_norm_mode`, and `social_convention_mode` on v19 when present so combined configs do not drop prior fields. Do not mix event schemas inside one run.
5. No scripted emergence. No culture, tradition, literacy class, or milestone that grants reading skill. Scenarios may seed objective artifacts; they must not seed shared interpretation, true labels, or researcher meaning onto agent state.
6. No LLM → world shortcuts. A provider never emits artifact content, an `AgentCommand` the policy did not already allow, or a world mutation. When `allow_provider` is false (default), there is no provider path and no prompt package.
7. Experiments stay reproducible. Paired arms share seed, topology, bodies, and stochastic identity. No wall clock and no new RNG purpose in interpretation. Experiment Z and `external_artifact_memory@1` stay analysis-only and off the V1 regression gate. The metric is not an input to cognition.
8. Optional cognition tracing stays outside the objective fold. Do not insert a `ComponentKind` or an ordinal in `_STAGE_ORDER`. Do not bump `COGNITION_TRACE_SUMMARY_SCHEMA`, add trace enum members, or add an Alembic revision. Tracing on versus off must not change `exact_trajectory_hash` when artifacts are unused and interpretation is `DISABLED`.

## Goal

Add physical external information artifacts as objective WorldEngine objects while keeping meaning subjective and observer graphics independent of any agent's reading.

Closed artifact kinds:

- mark
- sign
- note
- map
- record
- memorial

These are a collective-memory channel distinct from `Talk` / `Ask` / `Tell`. An artifact's existence does not download information into memory. Agents must perceive objective marks, interpret them privately, remember that interpretation, and may misunderstand.

Observer projection exposes location-based graphical entities with presentation metadata (`visual_category`, `icon_key`, `size_category`, researcher `display_label`) without encoding interpretation as objective visual truth. Godot draws the physical artifact from the objective frame alone.

## Design Decisions (locked)

- **A new world entity, not an `Item` or `Structure`.** `InformationArtifact` lives in `src/world/artifacts.py` (public facade; no private-world import) and on `WorldState.artifacts: Mapping[EntityId, InformationArtifact]`, default empty. It is not an `Item`, not a `Structure`, not a `Resource`, and not a `MemoryTrace`. Constructors that omit `artifacts` keep an empty map. `rebuild_world_state` copies the collection. Global id uniqueness includes artifact ids (`_reject_global_id_collisions`).
- **Closed kind enum.** `ArtifactKind`: `mark`, `sign`, `note`, `map`, `record`, `memorial`. Unknown kind fails closed with `invalid_artifact_kind`.
- **Portability split.**
  - Portable: `note`, `map`, `mark` — exactly one of `location_id` or `holder_id` (body).
  - Fixed: `sign`, `record`, `memorial` — always `location_id`; `holder_id` is forbidden (`artifact_not_portable`).
  - `ARTIFACT_MOVED` / domain `ArtifactMoved` is legal only for portable kinds.
- **Held placement is parallel to inventory, not inside it.** Portable artifacts with `holder_id` are **not** members of `AgentBody.inventory` and do not consume `ItemLoad` / carry capacity. `Take` / `Drop` / `Give` remain Item-only and must reject artifact ids with `not_an_item` (or the existing item-missing reject path — do not silently no-op). Transfer of portable artifacts uses only `TransferArtifact`. World validation enforces: every held artifact's `holder_id` names a living body; no inventory↔artifact agreement is required; a body may hold at most `8` portable artifacts (`artifact_hold_cap`).
- **Objective fields on every artifact.**
  - `artifact_id: EntityId`
  - `kind: ArtifactKind`
  - `author_id: EntityId` (creating body; immutable after create)
  - `created_tick: int` (`>= 0`)
  - `location_id` XOR `holder_id` per portability rules
  - `content: ArtifactContent` (objective marks only)
  - `content_revision: int` (starts at `0`; increments on each successful amend)
  - Destroyed artifacts are removed from `WorldState.artifacts` (no tombstone row). Destruction is witnessed only by the committed event.
- **Objective content is structured marks, not meaning.** `ArtifactContent` holds:
  - `marks: tuple[str, ...]` — closed lowercase tokens `[a-z][a-z0-9_]{0,31}`, max 16
  - `relations: tuple[ArtifactRelation, ...]` — each has `subject`, `predicate`, `object` tokens with the same token rules, max 8
  - Empty content is legal (blank slate / empty memorial face).
  - Domain content forbids free-form prose, natural-language paragraphs, and any field named `meaning`, `interpretation`, `translation`, `pixels`, `sprite`, `animation`, `color`, `dx`, `dy`, `screen_x`, or `screen_y`.
  - Example: a sign may store marks `("water", "north")` and relation `water / at / north`. Alice and Bob may form different private readings of those same marks.
  - Occurrence `public_facts` for artifact events may include only `artifact_id`, `artifact_kind`, and `content_revision` — never mark or relation tokens.
- **Commands.** Add exact classes to the closed `AgentCommand` union (verify baseline `20`, then `20 → 24`). Update `_COMMAND_TYPES`, `COMMAND_RULE_MATRIX`, operation arms, and `tests/unit/test_domain_contract_evolution_policy.py` (`len == 24`). No new `SystemEffectFamily` member — artifact mutations use `ActionCause` like other agent commands.
  - `Inscribe(kind, content, hold: bool = False)` — creates at the actor's location when `hold` is false; when `hold` is true, kind must be portable and the artifact is held by the actor (`invalid_artifact_hold` if fixed kind + `hold=True`). Default `hold=False` for every kind.
  - `Amend(artifact_id, content)` — replaces content and increments `content_revision`.
  - `Erase(artifact_id)` — destroys.
  - `TransferArtifact` — exact fields: `artifact_id: EntityId`, `mode: Literal["deposit", "claim", "give"]`, `recipient_id: EntityId | None = None`. Rules: `deposit` and `claim` require `recipient_id is None`; `give` requires a non-None living `recipient_id` at the actor's location. Zero/wrong combinations fail with `artifact_transfer_mode_invalid`. Portable only.
  - Admission checks liveness and one action slot. Actor must share the artifact's location or hold it to amend/erase/transfer. Claim requires the artifact on the ground at the actor's location. Deposit/give require the actor currently holds it.
  - Reject reasons: `unknown_artifact`, `artifact_not_portable`, `artifact_not_held`, `artifact_not_colocated`, `artifact_content_invalid`, `invalid_artifact_kind`, `invalid_artifact_hold`, `artifact_transfer_mode_invalid`, `artifact_hold_cap`, `recipient_unavailable`, `not_an_item` (Take/Drop/Give on an artifact id).
  - Created ids use `derive_entity_id(config, "information-artifact", ...)`. Do not add an allocator.
- **Bootstrap / seed path.** `WorldBootstrap` gains optional `artifacts: tuple[InformationArtifact, ...] = ()`. `_materialize_world` copies them into `WorldState.artifacts` with id-collision checks. Scenario helpers may pass seeded artifacts; they must not attach interpretation ledgers. Empty default keeps today's bootstrap bit-identical.
- **Events (replay-v8 only).** Detail types: `ArtifactCreated`, `ArtifactModified`, `ArtifactMoved`, `ArtifactDestroyed`. Each is effect-complete on schema 8 and illegal below (`invalid_event_schema_version`). Schema 8 also accepts production (v6) and environment (v7) details so a combined run stays one schema. Payloads carry artifact id, kind, author id (create), content revision, resulting location/holder, and success. No presentation fields. Domain kind strings: `artifact_created`, `artifact_modified`, `artifact_moved`, `artifact_destroyed`.
- **Write pair (run start, env-shaped).** Extend `checkpoint_schema_for_production` / `select_checkpoint_schema` with keyword-only `artifacts_active: bool = False`. Priority:

  | Condition at run start | Event schema | Codec |
  | --- | --- | --- |
  | `artifacts_active` | `EVENT_SCHEMA_REPLAY_V8` | `"v5"` |
  | else `dynamics_active` | v7 | `"v4"` |
  | else `production_active` | v6 | `"v3"` |
  | else | replay-v5 | `"v2"` |

  `artifacts_active` is true when bootstrap/seeded `artifacts` is non-empty **or** the run configuration admits artifact commands for this world (engine/runner flag derived from non-empty seed **or** an explicit `artifacts_enabled` kw on engine/bootstrap used by Experiment Z and unit tests; default false). Catalog A–E leave it false. A DISABLED interpretation mode with seeded artifacts still selects `(v8, "v5")`. A DETERMINISTIC mode with empty seeds and `artifacts_enabled=false` may stay on the prior event/codec pair until the run enables artifacts — Experiment Z sets `artifacts_enabled=true` on both arms that need Inscribe/Erase. Codec `v5` requires key `artifacts` plus every v4 key (`active_hazards`, `structures`, `production_jobs`, `tool_marks`). `v4` decode rejects `artifacts`. Journal writes dynamics/production keys on v4 and v5; only v5 writes `artifacts`. `WorldSnapshot` accepts codec `v5` only with event schema 8. `RunCreateRequest` accepts the `(v8, v5)` pair. `schema_projector_compatible` accepts schema 8 with projector `v2`. `ACCEPTED_PERSISTENCE_CODEC_VERSIONS` includes `v5`. `PERSISTENCE_CODEC_VERSION` stays `v2`. `PROJECTOR_VERSION` stays `v2`. `CURRENT_PHYSICAL_EVENT_SCHEMA_VERSION` stays `5`.
- **Perception.** Add `ObservedArtifact` under `CONTENT_VISIBILITY_THRESHOLD` (`0.5`) for artifacts at the observer's location, and always for artifacts held by self. Fields: `entity_id`, `kind`, `author_id`, `created_tick`, `content`, `content_revision`, placement (`GROUND_HERE` / `HELD_BY_SELF`). Do not project another agent's held artifact. Do not project interpretation, display labels, or icon keys onto `Observation`. **Domain encode always includes `artifacts` (tuple/list, possibly empty)** — same discipline as `structures`, not season-style omit. Decode accepts a missing key as empty. Update `_FROZEN_OBSERVATION_FIELDS` in `test_domain_contract_evolution_policy.py` to include `artifacts`. Occurrence `public_facts` as locked above.
- **Information is not auto-downloaded.** `build_direct_scene_memory_trace` and `DirectObservationMemoryUpdateHook` must **not** copy artifact ids, marks, or relations into episodic memory. Presence of `Observation.artifacts` alone must not create a `MemoryTrace`. Occurrence-based direct traces may record the occurrence kind token (`artifact_created`, …) but must not copy `ArtifactContent` tokens into concepts/relations and must not set `other_entity_id` from mark tokens. Communicated utterance content stays on the speech channel only.
- **Subjective interpretation is opt-in.** `ArtifactInterpretationMode` is `DISABLED` or `DETERMINISTIC`, default `DISABLED`, in `agents/cognition/artifacts.py`.
  - `DISABLED`: no ledger, no interpretation memory intents, no command bias from readings. World commands may still be submitted by tests/scripts; cognition does not compile `Inscribe` / `Amend` / `Erase` / `TransferArtifact`.
  - `DETERMINISTIC`: owner-scoped `ArtifactInterpretationLedger` on `SubjectiveSnapshot.artifact_interpretations` (default `None`). Each `ArtifactInterpretation` stores `artifact_id`, `observed_revision`, closed `reading_marks` / `reading_relations`, `confidence`, `distorted: bool`, `source_tick`, and observation provenance (`source_event_id` opaque `EventId` when known, else tick lineage). Correction: Cap 16 interpretations per owner; further drops with `cap_exceeded`. Updates read only the owner's `Observation` and prior ledger.
  - **Fail closed.** Unknown kind/status/placement; owner mismatches; non-finite confidence; future penalty below 0 abort with stable reason codes. Passing `WorldState`, `WorldEvent`, `PhysicalRules`, another owner's ledger, or a metric/analysis document into `apply_artifact_interpretation_update` raises `TypeError`. The module must not import `world._state`, `analysis`, or private world ops.
  - **Distortion rule (deterministic, no new RNG purpose):** when `observation.visibility < 0.75` **or** self fatigue `>= 0.70`, drop the last relation from the copied content and set `distorted=True`. Otherwise copy marks/relations exactly and set `distorted=False`. Confidence `0.55` when distorted, `0.85` otherwise. Re-observing a higher `content_revision` replaces the entry. Empty relations cannot drop further; still set `distorted=True` when the trigger fires.
  - Interpretation forms a dedicated `MemoryTrace` only through `ArtifactInterpretationMemoryUpdateHook` (policy `artifact-interpretation-memory.v1`) with concepts prefixed `artifact_reading:` — never by extending the default scene hook.
  - **Planner (locked):** when mode is on, a `COMMUNICATE` future already exists, no colocated living listener is visible, and the owner holds no unread need to speak, prefer depositing/inscribing a `note` or `record` by adding penalty `0.30` to other futures and compiling `Inscribe` only when that preferred future wins. Missing candidate records `no_candidate` and does not insert a command. Do not invent a literacy skill. Do not construct artifact commands from analysis.
  - **Carry laundry list.** Add `artifact_interpretations` beside `social_conventions` on `SubjectiveSnapshot`, `CognitiveLoopProposal`, `CognitiveLoopResult`, `AgentRuntimeCheckpoint`, `Perspective`, and `build_perspective`. `AgentRuntime` holds the ledger the same way, default `None`, with `require_owner_artifact_interpretations`. `CognitiveLoop.prepare` calls `_prepare_artifact_interpretations` immediately after `_prepare_social_conventions` and before `_prepare_competence`. Pass the ledger into intention/planning through `_planner_options`. Wire withhold/penalty helpers in deliberation. `SubjectiveMutationBatch` does not grow an artifact field. `subjective-v1` unchanged. No Alembic revision. Disabled checkpoint stores `None`. Files: `agents/cognition/artifacts.py`, `loop.py`, `deliberation.py`, `configuration.py`, `simulation/agent_runtime.py`, `simulation/run_control.py`, `agents/cognition/contracts.py` / perspective builders, `simulation` perception kw sites as needed.
- **Bodies vs agents.** Artifact `author_id` is a body `EntityId`. Ledger owner ids are `AgentId`. Resolve with existing identity helpers; unresolved → `unresolved_entity`, no ledger write.
- **Observer protocol stays v1.** Do not change `OBSERVER_PROTOCOL_VERSION`. Keep every current semantic type. Append `ARTIFACT_CREATED`, `ARTIFACT_MODIFIED`, `ARTIFACT_MOVED`, `ARTIFACT_DESTROYED`. Verify baseline `len(SEMANTIC_EVENT_TYPES) == 32`, then `32 → 36`.
  - `ObjectiveScene` / `ObserverWorldState` gain ordered `artifacts` (default empty). `ObserverArtifact` carries `artifact_id`, `kind`, `location_id` or `holder_id`, `author_id`, `created_tick`, `content_revision`, optional mark token list for researcher inspection, and optional `EntityPresentation`.
  - **`EntityPresentation` grows `display_label: str | None = None`.** Today the type has only `visual_category`, `icon_key`, `size_category`. Update `src/observer/presentation.py`, `EntityPresentationOut` in `src/api/observer_schemas.py`, and `observer_service` mapping. Catalog rows for artifacts use `entity_presentation(kind_value, kind_value)` (pair `(kind, kind)` string values). Each of the six kinds sets `visual_category="artifact"`, `icon_key=f"artifact_{kind}"`, `size_category="small"`, and `display_label` equal to the kind token (`"sign"`, …). **Presentation must not encode interpretation.**
  - `ObserverEvent` may add optional `artifact_id`. `public_mapping` includes it only when set. Still reject `pixels`, `sprite`, `animation`, `dx`, `dy`, and `AGENT_UN*`.
- **Godot draws objective artifacts.** Edit `clients/godot-observer/` so an artifact-aware layer paints ground artifacts from the replaced `state_tick` world snapshot by `kind` → local theme/icon mapping in `theme_catalog.gd`. `models.gd` must parse `world.artifacts` (structures remain out of scope). Held artifacts may appear in a slot cue only when `holder_id` matches a visible body; no interpretation overlays. `event_router.gd` / `event_log.gd` / `KNOWN_TYPES` learn the four artifact semantic types only (do not backfill production's six unknowns in this plan). Protocol version stays `observer-protocol-v1`. `src/` must not import `clients/godot-observer`.
- **Runner schema.** `runner-config-v19` = every v18 cognition key plus `artifact_interpretation_mode`. Emit only when some mode is `DETERMINISTIC`. Conventions-only configs still write v18. Combined conventions+artifacts writes v19 and must still encode `social_convention_mode`. `v1_regression_profile` unchanged.
- **Experiment Z — external records outlast memory.** `experiment-z-external-artifacts` with paired arms sharing seed and topology; both arms set `artifacts_enabled=true` and use existing sleep-consolidation soft-forget (no new test-only forget helper module).
  - Arm `artifact_channel`: agent A `Inscribe`s a `record` at location L with locked marks/relations for a scarce-resource cue; after consolidation soft-forgets A's episodic cue traces, agent B observes the record under `DETERMINISTIC` interpretation. Scenario keeps visibility `>= 0.75` and fatigue `< 0.70` so recovery is exact.
  - Arm `memory_only`: same setup but the record is `Erase`d (or never inscribed) before the read step; recovery fails after the same forget step.
  - Metric `external_artifact_memory@1` (analysis-only). Bump `METRIC_FAMILY_COUNT` from `31` to `32`. Update `test_metric_specifications.py` and e2e/reference exclusion sets the same way prior families did.

### Analysis

`compute_external_artifact_memory` in `src/analysis/external_artifact_metrics.py` builds blocks from caller-supplied rows. Duck-type with `getattr`. Must not import `agents`, `apply_artifact_interpretation_update`, or `AgentRuntime`.

**Block `artifact_survival`** from objective rows `(tick, artifact_id, kind, content_revision, present)`:

| Key | Value |
| --- | --- |
| `record_present_after_forget` | 1.0 if a `record` with the scenario artifact id has `present=True` on/after forget tick; else 0.0 |
| `mean_content_revision` | Mean revision among present rows at/after forget tick; none → `ABSENT` |

**Block `memory_loss`** from detached memory rows `(tick, owner_id, has_cue_concept, forgotten)`:

| Key | Value |
| --- | --- |
| `memory_loss_rate` | Forgotten cue rows divided by cue rows for owner A; empty → `ABSENT` |

**Block `reading_recovery`** from interpretation rows `(owner_id, artifact_id, observed_revision, reading_marks, distorted)` joined to objective marks:

| Key | Value |
| --- | --- |
| `reading_recovery_rate` | Owners whose `reading_marks` equal objective marks and `distorted` is false, divided by readers; empty → `ABSENT` |

**Block `divergence`** from paired owner readings of the same artifact id:

| Key | Value |
| --- | --- |
| `interpretation_divergence` | Fraction of owner-pairs whose `reading_marks` differ while objective content is identical; no pair → `ABSENT` |

Empty denominators → `MetricAvailability.ABSENT` for that key only.

### Locked numbers

- Max marks per content: `16`. Max relations: `8`. Token pattern: one lowercase letter then up to 31 `[a-z0-9_]`.
- Max held portable artifacts per body: `8`.
- Visibility gate: `0.5`. Distortion visibility threshold: `0.75`. Distortion fatigue threshold: `0.70`.
- Interpretation confidence: `0.85` clean / `0.55` distorted. Max interpretations per owner: `16`.
- Planner preference penalty: `0.30`.
- Semantic event count after this plan: `36` (baseline 32). Command union size: `24` (baseline 20). Metric family count: `32` (baseline 31).
- No new RNG purpose. No Alembic revision. No observer protocol bump.

## Non-Goals

- Free-form natural-language inscriptions or OCR
- Encoding Alice/Bob interpretations on observer frames or Godot sprites
- Owning `multi_hop_testimony_tracking` or adding a `V2CapabilityFlags` field
- Putting Experiment Z on the V1 regression gate or changing catalog A–E / reference `exact_trajectory_hash`
- Feeding `external_artifact_memory@1` (or any analysis label) into cognition
- Letting an agent read another owner's interpretation ledger
- Inserting `Inscribe` / `Amend` / `Erase` / `TransferArtifact` futures the planner did not already prefer via the locked penalty rule
- Exact x/y coordinates or server-driven sprite/animation payloads on domain events
- Literacy skills, language families, or culture labels
- An Alembic revision or a cognition-trace stage / ordinal
- Auto-writing artifact content through `DirectObservationMemoryUpdateHook`
- Tombstone rows for destroyed artifacts
- Mixing event schemas inside one run
- Bumping `OBSERVER_PROTOCOL_VERSION`, `CURRENT_PHYSICAL_EVENT_SCHEMA_VERSION`, `RUNNER_SCHEMA_VERSION`, or default `PERSISTENCE_CODEC_VERSION`
- LLM/provider path for artifact content or commands
- Backfilling Godot `KNOWN_TYPES` for the six production semantic events
- Putting portable artifacts into `AgentBody.inventory` or coupling them to `ItemLoad`

## Commit Plan

- **Commit 1** (after tasks 1–4): `feat(world): add information artifacts, seed path, and replay-v8 events`
- **Commit 2** (after tasks 5–7): `feat(cognition): interpret artifacts without auto-download memory`
- **Commit 3** (after tasks 8–10): `feat(observer): project artifacts and Godot objective glyphs`
- **Commit 4** (after tasks 11–12): `feat(experiments): prove external records outlast memory`
- **Commit 5** (after task 13): `docs(world): describe external information artifacts`

Each checkpoint is a git commit on `main` created when those tasks are done. Do not squash them into one commit at the end.

## Tasks

### Phase 1: World Model, Events, Resolution, Seed

- [x] Task 1: v2- Define information-artifact types and commands.
  - Deliverable: `ArtifactKind`, `ArtifactRelation`, `ArtifactContent`, and `InformationArtifact` in `src/world/artifacts.py`, re-exported from `world`. Placement enforces the portability split and held-vs-inventory non-membership. `Inscribe(kind, content, hold=False)`, `Amend`, `Erase`, and `TransferArtifact(artifact_id, mode, recipient_id=None)` join `AgentCommand` and `require_agent_command` with the locked field rules. Constructors reject invalid tokens, over-long tuples, fixed kinds with `holder_id`, portable kinds with both/neither placement, `hold=True` on fixed kinds, invalid transfer mode/recipient combos, and forbidden presentation field names. `WorldState.artifacts` defaults empty. Update `_COMMAND_TYPES` and `test_domain_contract_evolution_policy.py` so the closed command count is `24` (baseline was `20`). `world/__init__.py` exports the new types and commands.
  - Logging: logger `world.artifacts`. DEBUG on construct with `kind`, `mark_count`, `relation_count`, `content_revision`, and `hold`. ERROR on validation with field name and reason code. Do not log mark tokens at INFO.
  - Files: `src/world/artifacts.py`, `src/world/actions.py`, `src/world/_state.py`, `src/world/__init__.py`, `tests/unit/test_information_artifacts.py`, `tests/unit/test_domain_contract_evolution_policy.py`.

- [x] Task 2: v2- Add replay-v8 artifact events.
  - Deliverable: `ArtifactCreated`, `ArtifactModified`, `ArtifactMoved`, and `ArtifactDestroyed` join `EventDetails` and are effect-complete only on `EVENT_SCHEMA_REPLAY_V8`. `CURRENT_PHYSICAL_EVENT_SCHEMA_VERSION` remains `5`. Encoders below v8 reject the new details with `invalid_event_schema_version`. Schema 8 accepts existing v6 production and v7 environment details. Domain codecs in `src/simulation/serialization.py` gain exact-key arms for command tags `inscribe`, `amend`, `erase`, and `transfer_artifact`, and for the four event kinds. `SUPPORTED_EVENT_SCHEMA_VERSIONS` / `REPLAYABLE_EVENT_SCHEMA_VERSIONS` / compatibility accepted sets include `8`. Payloads have no presentation fields and no mark tokens in public occurrence facts beyond the locked keys.
  - Logging: logger `world.events`. DEBUG `artifact_event_built schema_version=%s kind=%s artifact_id=%s`. ERROR `invalid_event_schema_version` with kind and schema. No content tokens at INFO.
  - Depends on task 1.
  - Files: `src/world/events.py`, `src/simulation/serialization.py`, `src/simulation/compatibility.py`, `tests/unit/test_artifact_events.py`.

- [x] Task 3: v2- Resolve inscribe, amend, erase, and transfer with placement rules.
  - Deliverable: private operations/rules admit and mutate `WorldState.artifacts` through `WorldEngine` only. Wire `COMMAND_RULE_MATRIX` and operation arms for the four commands. `Inscribe` creates with `author_id=actor`, `created_tick=tick`, `content_revision=0`. Held portable artifacts stay outside `AgentBody.inventory` and enforce `artifact_hold_cap` (`8`). `Take`/`Drop`/`Give` reject artifact ids. `Amend` replaces content and increments revision. `Erase` removes the entity and emits `ArtifactDestroyed`. `TransferArtifact` rebinds placement for portable kinds and emits `ArtifactMoved`. Fixed kinds reject transfer with `artifact_not_portable`. Colocation/holder/mode checks use the locked reason codes. Created ids use `derive_entity_id(config, "information-artifact", ...)`. No new `SystemEffectFamily` member.
  - Logging: logger `world._operations` / artifact resolution logger and `simulation.engine`. DEBUG `artifact_resolved kind=%s op=%s mode=%s reason_code=%s`. INFO one line per committed artifact event with event id, tick, and domain kind. WARNING on reject codes with actor id and artifact id. Do not log mark tokens at INFO.
  - Depends on tasks 1 and 2.
  - Files: `src/world/_operations.py`, `src/world/_rules.py`, `src/world/_state.py`, `src/simulation/actions.py`, `src/simulation/engine.py`, `tests/unit/test_artifact_resolution.py`.

- [x] Task 4: v2- Seed artifacts through bootstrap without interpretation.
  - Deliverable: `WorldBootstrap.artifacts` optional tuple default `()`. Materialization copies into `WorldState.artifacts`, participates in global id collision checks, and does not create interpretation ledgers. Unit test seeds one `record` at tick 0, observes it, and asserts empty ledgers under `DISABLED`. Experiment Z and unit tests may also set engine/runner `artifacts_enabled=true` without seeding.
  - Logging: logger `simulation.bootstrap`. DEBUG `artifacts_seeded count=%s`. ERROR on id collision with reason code. No mark tokens at INFO.
  - Depends on tasks 1 and 3.
  - Files: `src/simulation/bootstrap.py`, `src/simulation/engine.py`, `src/world/_state.py`, `tests/unit/test_artifact_bootstrap.py`.

### Phase 2: Perception, Replay, and Subjective Interpretation

- [x] Task 5: v2- Project observed artifacts without interpretation.
  - Deliverable: `ObservedArtifact` + `Observation.artifacts`. Ground artifacts at the observer location require visibility `>= 0.5`. Held-by-self artifacts are always visible. Foreign held artifacts are omitted. **Domain encode always writes `artifacts` (empty tuple/list when none)** — mirror `structures`, do not use season-style omit. Decode missing key as empty. Update `_FROZEN_OBSERVATION_FIELDS` to include `artifacts`. Occurrence `public_facts` include only `artifact_id`, `artifact_kind`, and `content_revision` for actor and visible bystanders. No icon keys, display labels, readings, or mark tokens in `public_facts`.
  - Logging: logger `world._perception`. DEBUG `artifacts_observed count=%s`. Do not log marks at INFO.
  - Depends on task 3.
  - Files: `src/world/_perception.py`, `src/world/observations.py`, `src/simulation/serialization.py`, `tests/unit/test_artifact_perception.py`, `tests/unit/test_domain_contract_evolution_policy.py`.

- [x] Task 6: v2- Select replay-v8 / codec v5 at run start and fold artifacts.
  - Deliverable: extend `checkpoint_schema_for_production` and `select_checkpoint_schema` with `artifacts_active` and the locked priority table; update every call site (`engine.py`, `runner.py`, service). Replay folds the four v8 details into `artifacts`. Codec `v5` adds `artifacts` and requires the v4 key set; journal writes v4 keys on v4/v5 and `artifacts` only on v5. Resume restores artifacts then folds later events. A v4 checkpoint rejects `artifacts`. `WorldSnapshot` pairs codec `v5` only with schema 8. `RunCreateRequest` accepts `(v8, v5)`. `schema_projector_compatible` accepts schema 8 with projector `v2`. `ACCEPTED_PERSISTENCE_CODEC_VERSIONS` includes `v5`. `PERSISTENCE_CODEC_VERSION` stays `v2`. Unit tests cover: seeded artifacts → `(v8,"v5")` even when interpretation is `DISABLED`; dynamics-only still `(v7,"v4")`; production-only still `(v6,"v3")`; artifacts+dynamics → `(v8,"v5")` and still folds hazards/structures.
  - Logging: logger `simulation.persistence` / `simulation.replay` / `simulation.engine`. DEBUG `artifact_schema_selected event_schema=%s codec=%s artifacts_active=%s`. ERROR on codec/schema mismatch with reason codes only.
  - Depends on tasks 3, 4, and 5.
  - Files: `src/simulation/persistence.py`, `src/simulation/engine.py`, `src/simulation/runner.py`, `src/world/_replay.py`, `src/simulation/replay.py`, `src/simulation/journal.py`, `src/simulation/compatibility.py`, `tests/unit/test_artifact_replay.py`.

- [x] Task 7: v2- Add opt-in interpretation without auto-download memory.
  - Deliverable: `ArtifactInterpretationMode`, `ArtifactInterpretation`, `ArtifactInterpretationLedger`, and `apply_artifact_interpretation_update` in `agents/cognition/artifacts.py`. `DISABLED` leaves snapshot field `None` and does not compile artifact commands. `DETERMINISTIC` updates from `Observation.artifacts` with the locked distortion rule, stores provenance, and proposes memory only via `ArtifactInterpretationMemoryUpdateHook`. Assert unit tests that `DirectObservationMemoryUpdateHook` / `build_direct_scene_memory_trace` produce no artifact mark/relation concepts when artifacts are visible. Carry `artifact_interpretations` on the full laundry list in Design Decisions (`SubjectiveSnapshot`, proposal/result, checkpoint, `Perspective`, `build_perspective`, `AgentRuntime`, `run_control`, prepare after conventions / before competence). Planner uses the locked `0.30` penalty / `no_candidate` rule only. Raise `TypeError` for `WorldState`, `WorldEvent`, `PhysicalRules`, foreign ledgers, and metric documents. `subjective-v1` unchanged; no Alembic.
  - Logging: logger `agents.cognition.artifacts`. DEBUG `artifact_interpretation_updated owner_id=%s entry_count=%s distorted_count=%s`. INFO `artifact_command_withheld reason_code=%s`. WARNING `unresolved_entity` / `cap_exceeded`. No mark tokens at INFO.
  - Depends on tasks 5 and 6.
  - Files: `src/agents/cognition/artifacts.py`, `src/agents/cognition/memory.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/deliberation.py`, `src/agents/cognition/loop.py`, `src/agents/cognition/contracts.py`, `src/simulation/agent_runtime.py`, `src/simulation/run_control.py`, `tests/unit/test_artifact_interpretation.py`, `tests/unit/test_artifact_memory_boundary.py`.

### Phase 3: Runner, Observer, Godot, Experiment, Docs

- [x] Task 8: v2- Accept interpretation mode only on runner-config-v19.
  - Deliverable: `runner-config-v19` carries every v18 key plus `artifact_interpretation_mode`. `_COGNITION_KEYS_V19` = `_COGNITION_KEYS_V18` + `artifact_interpretation_mode`; decode v19 before the v18 branch. Emit only when some mode is `DETERMINISTIC`. Widen every named frozenset and `__post_init__` membership set that currently ends at v18 to include v19; apply the locked membership upgrades for conventions/norms/group and prior modes. Encode prior mode fields on v19 so norms+conventions+artifacts round-trips. Equality `v18_requires_social_conventions` stays v18-only. Runner passes mode into cognition and `artifacts_active` / seeds into the write-pair helper. Empty artifacts + `DISABLED` keep default replay-v5 / codec v2 / `runner-config-v4`. Tests: conventions-only still v18; artifacts `DETERMINISTIC` → v19; combined round-trip; v19 with all interpretation `DISABLED` → `v19_requires_artifact_interpretation`. `tests/unit/test_v1_regression_gate.py` is not extended.
  - Logging: logger `simulation.runner`. INFO `artifact_config schema_version=%s mode_count=%s artifacts_active=%s`. ERROR `artifact_interpretation_mode_requires_v19` / `v19_requires_artifact_interpretation` with schema and reason code. DEBUG is ids and counts. No seeds.
  - Depends on tasks 6 and 7.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/runner.py`, `src/simulation/compatibility.py`, `src/simulation/__init__.py`, `tests/unit/test_artifact_runner.py`, `tests/unit/test_compatibility_matrix.py`.

- [x] Task 9: v2- Project artifacts and semantic events for the observer.
  - Deliverable: `ObjectiveScene.artifacts` default empty. `project_frame` adds ordered `ObserverArtifact` rows with presentation from `entity_presentation(kind, kind)`. Extend `EntityPresentation` / `EntityPresentationOut` / service mapping with optional `display_label`. Catalog six artifact rows with locked tokens. `adapt_event` maps the four domain kinds to `ARTIFACT_*`. Verify baseline semantic count `32`, then `len(SEMANTIC_EVENT_TYPES) == 36`. Optional `artifact_id` on `ObserverEvent` / API schemas. Protocol stays `observer-protocol-v1`. Frames must not carry per-agent readings. Domain/world payloads still contain no `pixels`/`sprite`/coordinate commands.
  - Logging: logger `observer.project` and `observer.adapt`. DEBUG `artifacts_projected count=%s event_kind=%s`. ERROR `unknown_event_kind` / `presentation_instruction_forbidden`. Do not log icon keys at INFO.
  - Depends on tasks 2 and 6.
  - Files: `src/simulation/observer_facts.py`, `src/observer/version.py`, `src/observer/contracts.py`, `src/observer/adapt.py`, `src/observer/project.py`, `src/observer/presentation.py`, `src/api/observer_schemas.py`, `src/api/observer_service.py`, `tests/unit/test_artifact_observer.py`, `tests/unit/test_observer_contracts.py`.

- [x] Task 10: v2- Draw objective artifacts in Godot independently of interpretation.
  - Deliverable: Godot client parses `artifacts` from the world object installed by `state_tick` / `world_replaced`. Local `theme_catalog.gd` maps kind → icon/color. Object/artifact layer draws ground artifacts at the layout slot for `location_id`. Event router/log/`KNOWN_TYPES` recognize the four artifact semantic types only. A client test asserts a frame with artifacts and no interpretation fields paints from kind tokens only. Golden Python fixture event names stay a subset of `SEMANTIC_EVENT_TYPES` and keep prior names unchanged. `src/` must not contain `clients/godot-observer` as an import string.
  - Logging: no Python production logger. Client-side debug may count drawn artifacts; do not print mark tokens.
  - Depends on task 9.
  - Files: `clients/godot-observer/` (`theme_catalog.gd`, object/artifact layer, `models.gd`, `event_router.gd`, `event_log.gd`, tests), `tests/unit/test_godot_observer_fixtures.py`, `tests/architecture/test_godot_client_isolation.py`.

- [x] Task 11: v2- Add Experiment Z and `external_artifact_memory@1`.
  - Deliverable: catalog arm `experiment-z-external-artifacts` with paired `artifact_channel` vs `memory_only`, shared seed/topology/stochastic identity, `artifacts_enabled=true`, and soft-forget via existing consolidation (no new forget helper package). Analysis `compute_external_artifact_memory` implements the locked blocks/keys/`ABSENT` rules. Bump `METRIC_FAMILY_COUNT` `31 → 32` and update specification/e2e exclusion tests. Off the V1 regression gate. Composition maps detached rows only.
  - Logging: logger `experiments.external_artifacts` / `analysis.external_artifact_memory`. INFO experiment build with experiment id and condition ids. DEBUG metric block availability. No content tokens at INFO.
  - Depends on tasks 4, 7, 8, and 9.
  - Files: `src/experiments/external_artifacts_scenario.py`, `src/experiments/catalog.py`, `src/experiments/__init__.py`, `src/analysis/external_artifact_metrics.py`, `src/analysis/specifications.py`, `src/analysis/__init__.py`, `src/experiments/composition.py`, `tests/unit/test_external_artifact_memory.py`, `tests/unit/test_metric_specifications.py`.

- [x] Task 12: v2- Prove auto-download boundary, write-pair matrix, and divergent readings.
  - Deliverable: unit tests covering (1) visible artifact + `DISABLED` → no ledger and no artifact content concepts in default memory hooks; (2) distortion triggers (`visibility < 0.75` or `fatigue >= 0.70`) drop last relation, set `distorted=True`, confidence `0.55`; clean path confidence `0.85`; (3) higher `content_revision` replaces ledger entry; cap 16 → `cap_exceeded`; (4) two owners, one fatigued → divergent readings while `ObserverArtifact` marks stay identical; (5) portable note transfer emits `ARTIFACT_MOVED`; fixed memorial rejects transfer; Take on artifact id rejects; (6) write-pair matrix from Task 6; (7) runner rejects/round-trips from Task 8; (8) Experiment Z constraints (visibility/fatigue, artifact arm recovers, memory-only fails); (9) V1 regression gate still green without referencing Experiment Z; (10) command count 24 and semantic count 36.
  - Logging: tests assert logger reason codes already defined; no new INFO payload fields.
  - Depends on tasks 6, 7, 8, 9, and 11.
  - Files: `tests/unit/test_artifact_memory_boundary.py`, `tests/unit/test_artifact_interpretation.py`, `tests/unit/test_artifact_resolution.py`, `tests/unit/test_artifact_replay.py`, `tests/unit/test_artifact_runner.py`, `tests/unit/test_external_artifact_memory.py`, `tests/unit/test_v1_regression_gate.py` (run only; do not append Z).

- [x] Task 13: v2- Document external artifacts and the observer boundary.
  - Deliverable: update `docs/physical-simulation.md`, `docs/observer.md`, `docs/memory-reconstruction.md`, `docs/architecture.md` (Downstream V2 contract: replay-v8 accepted, default write stays replay-v5; Experiment Z / `external_artifact_memory@1` off the V1 gate; command count 24; `runner-config-v19`), and brief surface notes in `.ai-factory/DESCRIPTION.md` / `.ai-factory/ARCHITECTURE.md` (catalog A–Z). Cover WorldEngine ownership, subjective meaning, no auto-download, held-vs-inventory split, run-start write pair, codec v5, presentation `display_label`, and Godot objective drawing. Do not invent a roadmap milestone.
  - Logging: no runtime logger. Docs name logger channels from tasks 1–12 and the reject/reason codes listed in Design Decisions.
  - Depends on tasks 8, 10, 11, and 12.
  - Files: `docs/physical-simulation.md`, `docs/observer.md`, `docs/architecture.md`, `docs/memory-reconstruction.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`.
