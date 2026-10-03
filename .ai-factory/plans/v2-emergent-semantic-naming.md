# Implementation Plan: Bounded Socially Emerging Semantic Naming

Branch: main
Created: 2026-10-03
Improved: 2026-10-03

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete roadmap milestone. Adds an opt-in owner-scoped terminology ledger and researcher perspective overlays; leaves `multi_hop_testimony_tracking` unowned.

## Compatibility contract

Semantic naming is a private, bounded label system — not a natural language, not a world dictionary, and not an automatic shared lexicon. The plan must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only mutation authority. `PhysicalRules`, `_operations`, and `_rules` stay free of naming, lexicon, or terminology predicates. Updates read the owner's `Observation`, the owner's previous `TerminologyLedger`, the owner's `OwnerSafeSocialIdentity`, the owner's already-loaded `snapshot.memories` (reinforce-only), and an optional caller-built `NamingCueSummary` of duck-typed kind/id/action tokens. They never receive `WorldState`, `PhysicalRules`, `AgentBody`, `WorldEvent`, an event repository, replay, analysis output, another agent's runtime, goals, drives, beliefs, emotion, relationships, mind model, reputation ledger, territorial ledger, group ledger, norm ledger, convention ledger, or artifact-interpretation ledger objects. The naming module must not import `group_formation`, `social_norms`, `social_conventions`, or `artifacts` modules. They never call a memory reconstructor or import `memory` package writers. Researcher/analysis joins between subjective labels and objective ids never flow into cognition.
2. Do not own a capability flag. Do not add a `V2CapabilityFlags` field. Do not add `semantic_naming`, `shared_language`, `lexicon`, or any new flag name. `multi_hop_testimony_tracking` stays unimplemented and still fails closed with `capability_unimplemented`. Off for this feature is `SemanticNamingMode.DISABLED`, which does not change commands, memories, semantic beliefs, relationships, reputation, territorial claims, group formation, social norms, social conventions, artifact interpretation, or audits.
3. V1 regression gate stays green under flags-off, naming-mode disabled, and tracing-off. Catalog A–E and the reference scenario keep their current `exact_trajectory_hash` values. Experiment AA is additive and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. Schema bump only for the enabled mode. Default write stays `runner-config-v4`. Add `runner-config-v20` to the accepted set. v20 carries every `runner-config-v19` key plus `semantic_naming_mode` on each agent. Emit v20 only when some agent's `SemanticNamingMode` is `DETERMINISTIC`. An artifacts-only config still writes v19. Reject v20 when every semantic-naming mode is `DISABLED` (`v20_requires_semantic_naming`). Reject `DETERMINISTIC` semantic-naming mode on v1–v19 (`semantic_naming_mode_requires_v20`). Widen every existing mode and spec allowlist that currently ends at v19 so v20 remains legal for communication strategy, reputation, skill learning, teaching, production knowledge, reflection, consolidation, prospective imagination, counterfactual reasoning, environmental dynamics, territorial claims, group formation, social norms, social conventions, and artifact interpretation. That includes the named frozensets in `src/simulation/runner_serialization.py` and every local set in `SimulationRunnerConfig.__post_init__` that currently ends at v19. Encode and decode `capability_flags` and `cognition_trace` on v20. Encode and decode `environmental_dynamics` on v20 when the spec is present, using the same rule as v19. **Encode and decode `artifact_interpretation_mode` on both v19 and v20** (today it is exact-equality / v19-only — an artifacts+naming config writes v20 and must not drop the artifact field). Encode `social_convention_mode` on `{v18, v19, v20}` and widen every other prior-mode membership set that currently ends at v19 the same way. Encode `semantic_naming_mode` only on v20. Decode v20 agent cognition with `_COGNITION_KEYS_V20`, defined as `_COGNITION_KEYS_V19` plus `semantic_naming_mode`, before the v19 branch. `_require_keys` is an exact key check. Artifacts-only equality (`v19_requires_artifact_interpretation`) stays an equality check on v19. A config that enables both artifact interpretation and semantic naming writes v20, so `artifact_interpretation_mode_requires_v19` becomes membership in `{v19, v20}`. `social_convention_mode_requires_v18` becomes membership in `{v18, v19, v20}`. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. No policy weights in runner JSON. Leave `v1_regression_profile` unchanged. Baseline: the accepted set already ends at `runner-config-v19`.
5. No scripted emergence. No language, dialect, culture, or glossary **field** on `World`, `WorldState`, `Observation`, commands, events, or scenario builders. No predefined shared dictionary that agents receive as ground truth. **Do not mint label seeds from `ObservedLocation.name`, `VisibleExit.name`, or any free-text world name** (shared name parsing would force premature vocabulary convergence). Closed communication relation predicate `call` is legal (same pattern as norms' `expect` / conventions' `usually`); it is an utterance token, not a world field. No new `AgentCommand`, `ActionDirection`, `CommunicationSourceBasis`, or `WorldEvent` kind. Scenarios must not contain a language, lexicon, glossary, or shared-name field. Sleep stays a one-tick fatigue action. Closed label tokens are not free-form natural language.
6. No LLM path. There is no provider schema and no prompt package. `DETERMINISTIC` never calls `LLMProvider`.
7. Experiments stay reproducible. Paired arms share seed, topology, and stochastic identity. No RNG and no wall clock in naming updates. Experiment AA and `emergent_semantic_naming@1` stay analysis-only and off the V1 regression gate. The metric is not an input to cognition. Existing families (`emergent_group_formation@1`, `emergent_social_norms@1`, `persistent_social_conventions@1`, `external_artifact_memory@1`) stay unchanged.
8. Optional cognition tracing stays outside the objective fold. Do not insert a `ComponentKind` or an ordinal in `_STAGE_ORDER`. Do not bump `COGNITION_TRACE_SUMMARY_SCHEMA`, add trace enum members, or add an Alembic revision. Do not copy label tokens, referent ids, or analysis readings onto the trace summary. `subjective-v1` stays unchanged. Tracing on versus off must not change `exact_trajectory_hash` when the mode is `DISABLED`.

## Goal

Agents may invent, adopt, compete over, merge, shift, and forget bounded labels for objective entities — without inventing a full natural language, and without the observer silently replacing researcher identity with any agent's slang.

| Layer | What it is | Who may read it during a tick |
| --- | --- | --- |
| Objective identity | Stable entity id + researcher display name (`location_17` / `Northern Forest`) | World, observer objective frame, analysis |
| Owner label binding | One agent's private term for a possible referent (`dead_a1b2c3d4` → candidate location id) | That owner's cognition |
| Social transmission | Delivered `call` utterances carrying closed label tokens | Listeners who receive the utterance; not auto-grounded for non-listeners |
| Researcher perspective overlay | Additive projection of one agent's labels beside objective ids | Observer/API under `subjective_debug`; never mutates the objective frame |
| Analytical metrics | Vocabulary convergence and semantic drift over detached rows | Analysis only, after the fact |

Example (observer must keep both layers visible when an overlay is on):

```text
objective:   location_17 / Northern Forest
Alice view:  Dead A1b2c3d4          (subjective; token dead_a1b2c3d4)
Bob view:    Place E5f6g7h8         (subjective; token place_e5f6g7h8)
```

Different agents mint different owner-scoped digest seeds for the same objective entity. Convergence happens only through social `call` transmission (and later self-binding), never through shared world-name parsing. Mappings between subjective terms and objective referents are private hypotheses; they are not automatically published to other agents or written into the objective frame.

## Design Decisions (locked)

- **A ledger, not a world dictionary and not a semantic belief.** `TerminologyLedger` is owner-scoped state on `SubjectiveSnapshot.semantic_naming`, default `None`. It holds `LabelBinding` values. A binding is not a `SemanticBelief`, not a `NormBelief`, not a `GroupConcept`, not a `ConventionBelief`, and not a `DirectedRelationshipProfile`. Updates do not call `revise_semantic_belief`, `apply_norm_update`, `apply_group_update`, `apply_convention_update`, `apply_artifact_interpretation_update`, `merge_relationship_revision`, or reputation/territorial writers. The updater must not read another owner's terminology ledger. When both group formation and semantic naming are on, a group concept may become a naming referent candidate for kind `group` only via a loop-built `NamingCueSummary` token — without copying the group ledger object into the naming module.
- **Disabled mode is a passthrough.** `SemanticNamingMode.DISABLED` leaves `snapshot.semantic_naming` as `None`, appends no evidence, emits no utterance, applies no intention bias, and writes no runner field. Commands match the pre-naming planner.
- **Bounded semantic tokens, not natural language.** Label tokens are closed lowercase snake_case strings matching `[a-z][a-z0-9_]{0,31}` (max 32 chars). Forbidden: spaces, punctuation, free-form prose, paragraphs, and fields named `sentence`, `utterance_text`, `translation`, or `natural_language`. Display for researcher overlays may title-case underscores for presentation (`dead_a1b2c3d4` → `Dead A1b2c3d4`) without changing the stored token.
- **Closed referent kinds.** `NamingReferentKind`: `location`, `agent`, `group`, `recurring_event`, `dangerous_resource`, `social_practice`. These name what the owner is trying to label. They are not culture roles and are absent from world events and INFO logs.
- **Soft objective links stay private hypotheses.** Each `LabelBinding` may store zero or more `candidate_referent` rows: `(kind, entity_id | opaque_token, confidence)`. Entity ids are the owner's resolved candidates from observation/identity — never a researcher-forced ground-truth dictionary. Other agents do not receive these candidate rows. Analysis may join detached rows after the fact; cognition never reads analysis joins.
- **Cue summary boundary.** Frozen `NamingCueSummary` holds only duck-typed closed tokens the loop already knows from the owner's updated snapshot fields (group concept ids, active convention/norm usual/expect action kinds). It is built in `CognitiveLoop._prepare_semantic_naming` after group/norm/convention/artifact prepare. `apply_naming_update` accepts `NamingCueSummary | None` and must not import sibling ledger modules.
- **Minting is evidence-driven.** An owner mints or reinforces a label only from:
  1. Repeated direct observation of a referent-shaped cue (location presence, resolved body, dangerous resource quantity drop, hazard kinds, recurring colocated action pattern via accumulating evidence_count, group/social-practice tokens from `NamingCueSummary` when present).
  2. Delivered communication with relation predicate exactly `call`.
  3. Memory reinforce-only for an already-known label token (never mint from memory alone).
- **Label lifecycle (social dynamics).**

| Dynamics | Mechanism |
| --- | --- |
| Spread | Listener adopts/reinforces via predicate `call` (channel `communicated` or upgrade `observed` → `both`) |
| Compete | Multiple active labels that share a self-bound top candidate; strengths compete; preferred label is the highest-strength active binding for that referent |
| Merge | When two labels share overlapping high-confidence candidates (Jaccard of candidate entity ids `>= 0.50`) and strengths both `>= 0.40`, retire the weaker as `merged_into` the stronger and copy residual evidence (cap merge fan-in at 4) |
| Change meaning | When new evidence raises a different candidate above the current top candidate by `>= 0.20` confidence for `meaning_shift_ticks` (6) consecutive ticks, rebind the top candidate and record `sense_revision += 1` |
| Disappear | Decay `0.05` on ticks with no conforming or transmission evidence; retire below `0.20`; status `retired` |

- **Subjective form.** Status values: `candidate`, `active`, `retired`. Promotion requires evidence count at least `3`, at least one candidate with confidence `>= 0.40`, and strength at least `0.40`.
- **Tracked fields on every binding.**
  - `binding_id` — `sha256(owner_id|referent_kind|label_token)` hex
  - `label_token` — closed snake_case token
  - `referent_kind` — closed `NamingReferentKind`
  - `candidates` — ordered candidate referent rows (cap 4)
  - `strength` — quantized to `1e-6`, clamped `[0, 1]`
  - `evidence_count` / `first_tick` / `last_tick`
  - `transmission` — closed `NamingTransmission`: `observed`, `communicated`, `both`
  - `sense_revision` — non-negative int; increments on meaning change
  - `merged_into` — optional other binding id
  - `competing_label_ids` — other binding ids that share top candidate (cap 4)
- **Initial token inference (closed, deterministic, digest-only).** At first candidate creation only, derive a seed token from owner-scoped digests — never free prose and never from world/location/exit names:
  - `location` → `place_<stable8>`
  - `agent` → `agent_<stable8>`
  - `group` → `group_<stable8>` from cue concept id when `NamingCueSummary` supplies it; otherwise do not mint kind `group`
  - `recurring_event` → `gathering_<stable8>` from action-kind + location id digest (evidence accumulates across ticks on the candidate binding)
  - `dangerous_resource` → `hazard_<resource_kind>` when a depleting `ResourceKind` is observed, or `hazard_cold_snap` / `hazard_heat` when `Observation.hazard_kinds` is present
  - `social_practice` → `practice_<action_kind>` when `NamingCueSummary` supplies an active convention/norm action; otherwise do not mint
  - Stable8 is the first 8 hex chars of sha256 over `owner_id|referent_kind|referent_id` (no Python `hash()`). Different owners therefore mint different seeds for the same objective entity.
- **Closed modifier evolution (not world rename).** When an owner already holds an active location binding and observes `hazard_kinds` non-empty or a death occurrence at that location, mint a **competing** label by applying closed prefixes in order: strip a leading `place_` if present, then `dark_<stable8>` on first qualifying tick window, then `dead_<stable8>` on a later qualifying window (requires the prior dark competing label to be active or the base active with hazard continuing). Never mutate `WorldState`, location names, or layout display names. Example path for one owner: `place_a1b2c3d4` → competing `dark_a1b2c3d4` → competing `dead_a1b2c3d4`.
- **Evidence from observation (learn, do not script).** Dedup on `(label_token, referent_kind, source_event_id)` with lineage `tick-{tick}-{ordinal}` when event id is missing. Cross-tick “≥3 ticks” rules are implemented by incrementing `evidence_count` on the candidate/active binding across ticks — Observation is single-tick only.

| Evidence the owner has this tick | Kind / token path | Delta | Notes |
| --- | --- | --- | --- |
| Owner at a location | `location` / `place_<stable8>` or existing | conforming `+0.12` | Candidate = that location id |
| Resolved body colocated | `agent` / `agent_<stable8>` or existing | conforming `+0.10` | Candidate = that agent id; promote after evidence_count ≥ 3 |
| `NamingCueSummary` group concept id present | `group` / `group_<stable8>` | conforming `+0.12` | Candidate = concept id token; no group ledger copy |
| ≥2 resolved agents including owner share action kind at owner's location | `recurring_event` / `gathering_<stable8>` | conforming `+0.12` | Accumulate across ticks via evidence_count |
| Local `hazard_kinds` non-empty or witnessed resource quantity drop | `dangerous_resource` / `hazard_*` | conforming `+0.15` | Also may trigger dark_/dead_ competing location labels |
| `NamingCueSummary` practice action present | `social_practice` / `practice_<action>` | conforming `+0.10` | Mint once from cue; later ticks reinforce |

- **Memory reinforcement (channel `remembered`).** `apply_naming_update` also accepts the owner's already-loaded `memories` sequence. For each `MemoryTrace`, scan `concepts`/`relations` for closed tokens matching a label already on the ledger, or relation predicate exactly `call` citing that label. On match, reinforce by `+0.08`. **Never mint a new binding from memory alone.** Forgotten/expired traces ignored. Dedup on `(binding_id, memory_id)`.
- **Transmission via communication.** When the owner is listener on a delivered utterance with relation predicate exactly `call` and object/subject tokens matching a label token (+ optional kind), adopt or reinforce with channel `communicated` (or upgrade `observed` → `both`). Delta `+0.10`. Speaker must resolve; unresolved yields `unresolved_entity` and no adoption. Owner never copies the speaker's ledger object — only closed tokens from the utterance. Candidate referents from the speaker are **not** auto-imported; the listener must bind candidates from their own observation (or leave candidates empty until they do). **Adopted empty-candidate bindings stay `candidate`, do not enter competition/merge, and are ignored by `naming_communicate_utterance` until a self-bound top candidate exists.**
- **Communicate without inventing commands.** When a binding has a top candidate, strength `>= 0.40`, a `COMMUNICATE` future already exists, and the owner has not uttered this label in the last `utterance_interval` ticks (4), prefer that future by adding penalty `0.30` to other futures. `naming_communicate_utterance(...)` returns the relation recipe for an existing Talk (predicate `call`, subject=label_token, object=referent_kind, `CommunicationSourceBasis.UNREFERENCED`), mirroring `convention_communicate_utterance`. Do not construct a new `Talk`.
- **No command invention / no world rename.** Naming never inserts futures the planner did not propose. Naming never mutates location names, agent ids, layout display names, or `WorldState`.
- **Bodies and agents stay distinct.** Occurrence and utterance ids are `EntityId`. Ledger owner and agent candidates are `AgentId`. Resolve with `OwnerSafeSocialIdentity`. Unresolved → `unresolved_entity`, no candidate.
- **Carry follows social conventions / artifacts.** Add `semantic_naming` beside `artifact_interpretations` on `SubjectiveSnapshot`, `CognitiveLoopProposal`, `CognitiveLoopResult`, `AgentRuntimeCheckpoint`, `Perspective`, and `build_perspective`. `AgentRuntime` holds the ledger the same way, default `None`, with `require_owner_semantic_naming`. `CognitiveLoop.prepare` calls `_prepare_semantic_naming` immediately after `_prepare_artifact_interpretations` and before `_prepare_competence`: build `NamingCueSummary` from the owner's already-updated group/norm/convention snapshot fields, then call `apply_naming_update` with `snapshot.memories` and that summary. Pass the ledger into intention/planning through `_planner_options`. Wire `naming_communicate_utterance` in deliberation beside the convention utterance path. Include `semantic_naming` on `export_runtime_checkpoint` / restore beside `artifact_interpretations`. `SubjectiveMutationBatch` does not grow a naming field. `subjective-v1` unchanged. No Alembic revision. Disabled checkpoint stores `None`.
- **Quantization and caps.** Strength/confidence quantized to `1e-6`, clamped to `[0, 1]`. At most 16 bindings per owner, 32 evidence items per binding, 4 candidates, 4 competing links, 4 merge fan-in. Further items drop with `cap_exceeded`. No RNG, wall clock, or Python `hash()`.
- **Fail closed.** Unknown kind, transmission, status; owner mismatches; non-finite numbers; future penalty below 0; illegal label tokens abort with stable reason codes. Passing `WorldState`, `WorldEvent`, or a metric document into `apply_naming_update` raises `TypeError`.
- **Objective observer identity is sacred.** Ordinary objective observer frames continue to use stable canonical researcher identifiers/display names from the layout catalog and world names (`ObserverLocation.location_id`, `name`, `display_name`; agent `agent_id` / `entity_id`). Naming must never overwrite those fields.
- **Overlay strength bands (closed).** `strength_band`: `candidate` when status is `candidate`; else `low` if strength `< 0.40`; `mid` if `< 0.70`; `high` otherwise.

### Observer / Godot perspective overlays

- **Additive overlays only.** Introduce a researcher projection `SubjectiveLabelOverlay` (layer token `subjective_labels`) that lists, for a chosen perspective agent, bindings as `{objective_id, objective_display_name, referent_kind, label_token, label_display, sense_revision, strength_band, label_source: "agent_perspective"}`. Objective id/display remain present on every row. Never replace `ObserverLocation.display_name` or agent identity fields in the objective frame. Rows with empty candidates omit `objective_id` / use empty string and still keep `label_source`; they must not invent a referent.
- **Capability.** Overlay routes require `subjective_debug` (same gate as relationship summaries / territorial claims). Objective manifest/state/stream stay free of private ledgers when debug is off (`debug_disabled`).
- **Query/projection (live checkpoint path).** Add `GET /v1/simulations/{run_id}/observer/agents/{agent_id}/labels` mirroring territorial-claims live access: API loads `owner_runtime_checkpoint` → extracts duck-typed binding rows → `observer.project_subjective_label_overlay(rows, objective_display_index)`. Observer must not import `agents.cognition` or `TerminologyLedger`; accept tuples/duck-typed rows only (same pattern as `observer.relationships`). Optional `tick=` fails closed with `labels_unavailable_at_tick` unless it matches the live head (no durable per-tick terminology history in this plan). Projection reads only that agent's rows. It must not include other agents' ledgers, memories, beliefs, goals, emotions, inbox text, or hidden observation content beyond the label rows. Switching Godot perspective calls this endpoint; it must not widen credentials to unlock unrelated debug pages.
- **Godot.** Add a perspective selector and a `label_overlay.gd` layer analogous to `claim_overlay.gd` (`layer == "subjective_labels"`). Paint subjective labels as secondary captions clearly marked (e.g. distinct style / prefix), while the primary caption stays the canonical researcher display name. Protocol stays `observer-protocol-v1`; unknown keys remain ignored by older clients. Do not encode subjective labels into objective `world_replaced` identity fields.
- **Logging.** Observer/API log counts and agent id only — never dump full label lexicons at INFO.

### Analysis

`compute_emergent_semantic_naming` in `src/analysis/semantic_naming_metrics.py` builds blocks from caller-supplied rows. Duck-type with `getattr`. Must not import `agents`, `apply_naming_update`, or `AgentRuntime`.

**Block `vocabulary_convergence`** from detached binding rows `(tick, owner_id, label_token, referent_kind, top_candidate_id, status, strength, sense_revision, transmission)` joined optionally to objective entity ids supplied by the caller:

| Key | Value |
| --- | --- |
| `shared_label_rate` | Fraction of objective entities that have ≥2 owners with the same active top label token |
| `mean_labels_per_entity` | Mean distinct active label tokens per objective entity that has ≥1 binding |
| `mean_owners_per_label` | Mean distinct owners per active label token that has a top candidate |
| `preferred_label_agreement` | Fraction of entity pairs of owners whose preferred (max-strength) labels match |
| `empty_lexicon_owner_rate` | Owners with zero active bindings divided by owners in the row set |

Empty denominators → `MetricAvailability.ABSENT` for that key only.

**Block `semantic_drift`:**

| Key | Value |
| --- | --- |
| `mean_sense_revision` | Mean `sense_revision` of active bindings |
| `label_turnover_rate` | Fraction of adjacent history ticks where an owner's preferred label for a candidate changes |
| `meaning_shift_rate` | Fraction of active bindings with `sense_revision >= 1` |
| `merge_rate` | Fraction of retired bindings with `merged_into` set over all retired+active in the window |
| `competition_rate` | Fraction of active bindings with `competing_label_ids` non-empty |
| `extinction_rate` | Fraction of labels active at window start that are retired by window end |

`compute_naming_persistence` takes ordered documents and reports `label_persistence` (same owner+token+top candidate still active at strength `>= 0.40`) and `sense_stability` (active binding with `sense_revision` unchanged across the window). Empty history → `ABSENT`.

Family id `emergent_semantic_naming`. Tag `emergent_semantic_naming@1`. Bump `METRIC_FAMILY_COUNT` from 32 to 33. Not added to the V1 bundle for catalog A–E.

## Non-Goals

- A full natural language, grammar, morphology engine, or free-form sentence generator
- A `WorldEngine` rename of locations/agents/resources
- Predefined culture/dialect/language fields on world/scenario objects (communication predicate `call` is allowed)
- Minting label seeds from `ObservedLocation.name`, `VisibleExit.name`, or other free-text world names
- Writing label tokens into `SemanticBelief`, `NormLedger`, `ConventionLedger`, or artifact interpretation ledgers
- Auto-importing another agent's candidate referent map from a `call` utterance
- Minting a new binding from memory alone
- A new `AgentCommand`, `ActionDirection`, `CommunicationSourceBasis`, or `WorldEvent` kind
- Silently replacing objective observer identity with subjective labels
- Serving private ledgers on ordinary `objective_inspection` frames without `subjective_debug`
- Durable per-tick terminology history / historical label replay (live checkpoint only)
- Owning `multi_hop_testimony_tracking`
- Inserting a `CognitiveLoop` ordinal, bumping cognition-trace schema, bumping `subjective-v1`, or adding an Alembic revision
- Letting an agent read another agent's ledger or any analysis document
- An LLM assessor or free-form naming prose
- Putting Experiment AA on the V1 regression gate
- Feeding convergence/drift metrics into cognition

## Commit Plan
- **Commit 1** (after tasks 1–3): `feat(simulation): add opt-in semantic naming on runner-config-v20`
- **Commit 2** (after tasks 4–7): `feat(cognition): learn owner-scoped emergent labels`
- **Commit 3** (after tasks 8–10): `feat(observer): add subjective label perspective overlays`
- **Commit 4** (after tasks 11–13): `test(analysis): measure vocabulary convergence and drift`
- **Commit 5** (after task 14): `docs(cognition): document emergent semantic naming`

## Tasks

### Phase 1: Contracts and Mode

- [x] Task 1: v2- Add semantic-naming contracts and `SemanticNamingPolicy`.
  - Deliverable: frozen types in `src/agents/cognition/semantic_naming.py`, exported from `src/agents/cognition/__init__.py`. `DISABLED` leaves the snapshot field `None`.
  - Types: `NamingReferentKind` (`location`, `agent`, `group`, `recurring_event`, `dangerous_resource`, `social_practice`), `NamingTransmission` (`observed`, `communicated`, `both`), `NamingEvidenceChannel` (`observed`, `communicated`, `remembered`), `NamingStatus` (`candidate`, `active`, `retired`), `NamingStrengthBand` (`candidate`, `low`, `mid`, `high`), `NamingCandidate`, `NamingEvidenceItem`, `LabelBinding`, `TerminologyLedger`, `NamingCueSummary` (placeholder export; full cue contract locked in Task 2), `SemanticNamingPolicy` (`semantic-naming.v1`, active strength `0.40`, retire strength `0.20`, decay `0.05`, conforming deltas as locked, transmission delta `0.10`, remembered delta `0.08`, penalty `0.30`, promotion count `3`, meaning shift ticks `6`, merge Jaccard `0.50`, utterance interval `4`, caps 16 bindings / 32 evidence / 4 candidates / 4 competitors / 4 merge fan-in). Helpers: `default_semantic_naming_policy()`, `require_owner_semantic_naming(...)`, `label_binding_id(owner_id, referent_kind, label_token) -> sha256 hex`. `CognitionSemanticNamingMode` (`DISABLED`, `DETERMINISTIC`) in `src/agents/cognition/configuration.py` and matching runner enum in `src/simulation/runner_models.py`.
  - Constructors reject unknown enums, illegal label tokens, candidate sets larger than 4, binding_id mismatches, and non-finite strength/confidence.
  - Logging: logger `agents.cognition.semantic_naming`. DEBUG on construction with owner id, policy version, and binding count. ERROR with field name and reason code on validation failure. No label token lists at INFO, never log free-form prose fields.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Files: `src/agents/cognition/semantic_naming.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/__init__.py`, `src/simulation/runner_models.py`, `tests/unit/test_semantic_naming.py`.

- [x] Task 2: v2- Define `NamingCueSummary` and the import-closed cue boundary.
  - Deliverable: freeze `NamingCueSummary` in `src/agents/cognition/semantic_naming.py` as an immutable duck-typed cue bag: optional group concept id tokens, optional practice action-kind tokens (from convention/norm usual/expect), no ledger objects, no analysis rows. Document that only `CognitiveLoop` may construct it from the owner's already-updated snapshot fields. `apply_naming_update` accepts `cues: NamingCueSummary | None = None`. Module must not import `group_formation`, `social_norms`, `social_conventions`, or `artifacts`. Unit tests prove constructing a summary from plain strings works and that passing a ledger-like object with forbidden type names fails closed.
  - Logging: DEBUG `naming_cues_accepted` with owner id and cue counts (group/practice). WARNING `naming_cues_dropped` with reason `invalid_token` or `forbidden_type`. No concept id dumps at INFO.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 1.
  - Files: `src/agents/cognition/semantic_naming.py`, `tests/unit/test_semantic_naming.py`.

- [x] Task 3: v2- Wire `DETERMINISTIC` through `runner-config-v20` without owning a new flag.
  - Deliverable: mode off keeps `runner-config-v4` and today's commands. Mode on is accepted only as `runner-config-v20`. `multi_hop_testimony_tracking` still fails closed. A v20 document can still carry every prior mode including artifact interpretation.
  - Add `semantic_naming_mode` to `AgentCognitionSpec` and `CognitionLoopConfig`. Default both to `DISABLED`. Accept v20 in `SUPPORTED_RUNNER_SCHEMA_VERSIONS`. Define `_COGNITION_KEYS_V20` as `_COGNITION_KEYS_V19` plus `semantic_naming_mode`. Add v20 to every allowlist that currently ends at v19. Encode/decode `capability_flags`, `cognition_trace`, and optional `environmental_dynamics` on v20. **Encode/decode `artifact_interpretation_mode` on `{v19, v20}`** (replace today's exact `== v19` branches). Encode `social_convention_mode` on `{v18, v19, v20}` and widen other prior-mode membership sets ending at v19 the same way. Encode `semantic_naming_mode` only on v20. Decode v20 before the v19 branch. Keep `v19_requires_artifact_interpretation` as equality on v19. `artifact_interpretation_mode_requires_v19` becomes membership in `{v19, v20}`. `social_convention_mode_requires_v18` becomes membership in `{v18, v19, v20}`. Add `semantic_naming_mode_requires_v20` and `v20_requires_semantic_naming`. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. Do not add a `V2CapabilityFlags` field. `simulation.runner._cognition_config_for` sets `CognitionSemanticNamingMode.DETERMINISTIC` only from that field and builds `default_semantic_naming_policy()`. Update `src/simulation/compatibility.py`. Export `RUNNER_SCHEMA_VERSION_V20` and `SemanticNamingMode` from `src/simulation/__init__.py`.
  - Tests: multi_hop still `capability_unimplemented`; disabled mode does not bump schema; artifacts-only still writes v19; naming deterministic writes v20 and round-trips **including `artifact_interpretation_mode` when both modes are on**; v20 with naming mode disabled is rejected; artifacts+naming writes v20. One combined config with naming, artifacts, conventions, norms, groups, and environmental dynamics round-trips flags and tracing. Run `uv run ruff check` on each touched file.
  - Logging: DEBUG `cognition_config_semantic_naming_mode mode=%s policy_version=%s` on logger `simulation.runner`. ERROR on schema rejection uses existing stable runner codes.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 1.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/runner.py`, `src/simulation/__init__.py`, `src/agents/cognition/configuration.py`, `tests/unit/test_runner_models.py`, `tests/unit/test_runner_serialization.py`, `tests/unit/test_simulation_runner_construction.py`, `tests/unit/test_v2_flag_defaults.py`, `tests/unit/test_cognition_configuration.py`, `tests/unit/test_compatibility_matrix.py`.

### Phase 2: Private Label Learning

- [x] Task 4: v2- Apply observation, cues, and memory evidence into owner-scoped label bindings.
  - Deliverable: `apply_naming_update(...)` returns a new `TerminologyLedger` for one owner. Accepts this tick's `Observation`, `OwnerSafeSocialIdentity`, previous ledger, optional owner `memories`, and optional `NamingCueSummary`. Passing `WorldState`, `WorldEvent`, or a metric document raises `TypeError`. Module must not import `analysis`, `simulation`, `world.models`, `world.events`, `world._state`, `group_formation`, `social_norms`, `social_conventions`, or `artifacts`. May import `world.observations` and `world.communications` contracts for relation predicates only. May type-check `MemoryTrace` via `TYPE_CHECKING` or duck-typing without importing reconstructors or `MemoryService`.
  - Seed tokens are digest-only per locked Design Decisions. Never parse `ObservedLocation.name` or `VisibleExit.name`. Apply locked evidence table and tick order: open/match cues → conforming deltas → remembered reinforcement → candidate confidence updates → candidate promotion → competing links → meaning-shift check → merge → decay. Memory reinforces existing bindings only (`+0.08`, channel `remembered`); never mints. Unknown occurrence kinds leave the ledger unchanged. Caps drop with `cap_exceeded`.
  - Logging: DEBUG `naming_binding_applied` with owner id, tick, and sign. DEBUG `naming_memory_reinforced` with owner id and tick when remembered evidence applies. INFO `naming_ledger_updated` with owner id and binding count. WARNING `naming_evidence_dropped` with reason `cap_exceeded`, `ignored_kind`, `unresolved_entity`, `illegal_token`, or `memory_no_match`. ERROR on owner mismatch. No label lexicons and no utterance text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on tasks 1 and 2.
  - Files: `src/agents/cognition/semantic_naming.py`, `tests/unit/test_semantic_naming.py`.

- [x] Task 5: v2- Promote candidates, compete, merge, shift meaning, and retire labels.
  - Deliverable: promote `candidate` → `active` under locked thresholds (requires a self-bound top candidate). Competing labels that share top candidate link in `competing_label_ids` (cap 4). Merge weaker into stronger at Jaccard `>= 0.50` and both strengths `>= 0.40`. Meaning shift after `meaning_shift_ticks` with alternate-candidate lead `>= 0.20` increments `sense_revision` and rebinds top candidate. Closed modifier evolution mints competing `dark_<stable8>` / `dead_<stable8>` from hazard/death cues without renaming the world. Decay `0.05` when no evidence this tick; retire below `0.20`. Empty-candidate bindings never compete or merge.
  - Logging: DEBUG `naming_binding_promoted`, `naming_labels_merged`, `naming_meaning_shifted`, or `naming_binding_retired` with owner id, tick, and status. WARNING `naming_binding_withheld` with reason `below_count`, `below_strength`, `candidate`, or `empty_candidates`. No token dumps at INFO.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 4.
  - Files: `src/agents/cognition/semantic_naming.py`, `tests/unit/test_semantic_naming.py`.

- [x] Task 6: v2- Adopt labels from `call` communication without importing speaker mappings.
  - Deliverable: listener path adopts/reinforces from predicate `call` without copying speaker candidate referent rows. Adopted empty-candidate bindings stay `candidate`, are excluded from competition/merge, and are ignored by communicate-prefer until a self-bound top candidate exists. `naming_communicate_utterance(...)` returns the relation recipe for an existing Talk only for bindings with top candidate and strength `>= 0.40`; does not construct commands. Disabled mode and non-ledger return empty map / `None`. Missing preferred future records `no_candidate`.
  - Logging: DEBUG `naming_transmission_applied` / `naming_response_selected` with owner id, tick, and channel/response. WARNING `naming_response_withheld` with reason `no_candidate`, `candidate_only`, `empty_candidates`, or `utterance_interval`. No utterance text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 5.
  - Files: `src/agents/cognition/semantic_naming.py`, `tests/unit/test_semantic_naming.py`.

- [x] Task 7: v2- Prove world authority and objective names are unchanged by labeling.
  - Deliverable: focused regression in `tests/unit/test_semantic_naming_world.py`: locations keep bootstrap/world names; layout display names unchanged; physical admission unaffected; two owners mint different `place_<stable8>` seeds for the same location. Tests call existing operations only. Assert no naming tokens appear in world logs at INFO.
  - Logging: DEBUG only on existing world loggers; no naming tokens in world logs.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 6.
  - Files: `tests/unit/test_semantic_naming_world.py`.

### Phase 3: Runtime Carry

- [x] Task 8: v2- Carry the ledger, build cues, and pass communicate penalties into deliberation.
  - Deliverable: add `semantic_naming` beside `artifact_interpretations` on `SubjectiveSnapshot`, `CognitiveLoopProposal`, `CognitiveLoopResult`, `Perspective`, `build_perspective`, and `AgentRuntime` checkpoint state. `require_owner_semantic_naming` accepts `None` or matching-owner `TerminologyLedger`. `CognitiveLoop.prepare` calls `_prepare_semantic_naming` immediately after `_prepare_artifact_interpretations`: build `NamingCueSummary` from the owner's already-updated `group_formation` / `social_norms` / `social_conventions` snapshot fields (duck-typed active concept ids and usual/expect action kinds only), then call `apply_naming_update(..., cues=summary, memories=snapshot.memories)`. Thread through `_planner_options` and apply communicate-prefer penalties next to convention penalties in `deliberation.py`. Wire `naming_communicate_utterance` beside `convention_communicate_utterance`. Include `semantic_naming` on `export_runtime_checkpoint` / restore beside `artifact_interpretations` in `agent_runtime.py` / `run_control.py`. `DISABLED` keeps pre-naming commands.
  - Do not insert a `ComponentKind`. Do not bump `subjective-v1`.
  - Logging: DEBUG `semantic_naming_carried` with owner id and binding count on logger `agents.cognition.loop`. DEBUG `naming_penalty_applied` with future count on logger `agents.cognition.deliberation`. WARNING `naming_carry_rejected` with reason `owner_mismatch` or `invalid_type`.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on tasks 2, 3, and 6.
  - Files: `src/agents/cognition/models.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/loop.py`, `src/agents/cognition/deliberation.py`, `src/simulation/agent_runtime.py`, `src/simulation/perception.py`, `src/simulation/run_control.py`, `tests/unit/test_semantic_naming_runtime.py`.

### Phase 4: Observer Perspective Overlays

- [x] Task 9: v2- Project subjective label overlays without mutating objective frames.
  - Deliverable: `project_subjective_label_overlay(...)` in `src/observer/labels.py` (relationships pattern) builds layer `subjective_labels` from duck-typed rows only — observer must not import `agents.cognition` or `TerminologyLedger`. Each row always includes objective id/display when a top candidate exists, plus subjective label fields, closed `strength_band`, and `label_source="agent_perspective"`. `project_frame` remains objective-only. API route `GET /v1/simulations/{run_id}/observer/agents/{agent_id}/labels` under `subjective_debug`, loading live `owner_runtime_checkpoint` the same way as territorial claims (`simulation_manager.owner_runtime_checkpoint`). When debug is off → `debug_disabled`. Empty ledger → empty readings, not an error. Optional `tick=` fails closed with `labels_unavailable_at_tick` unless it matches the live head.
  - Logging: logger `observer.labels` / API route logger. DEBUG with agent id and row count. WARNING on unavailable tick. Never log full lexicons at INFO.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on tasks 1 and 8.
  - Files: `src/observer/labels.py`, `src/observer/__init__.py`, `src/api/observer_service.py`, `src/api/observer_schemas.py`, `src/api/routes/observer.py`, `src/api/security.py` (reuse capability), `tests/unit/test_semantic_naming_observer.py`.

- [x] Task 10: v2- Add Godot perspective switching for subjective labels.
  - Deliverable: Godot client gains a researcher perspective control and `label_overlay.gd` that consumes `layer == "subjective_labels"` payloads. Primary captions continue to use canonical researcher identity (`ObserverIdentity` / layout display names). Secondary captions show subjective labels and are visually marked as subjective. Switching perspective refetches the labels route for the selected agent and must not require or expose unrelated subjective debug collections (memories/beliefs). Protocol stays `observer-protocol-v1`. Add focused GDScript tests for overlay parse + non-replacement of objective names.
  - Logging: existing `ObserverLog.debug` with layer name and marker count only.
  - Control: client-side debug logging only.
  - Depends on task 9.
  - Files: `clients/godot-observer/scripts/view/label_overlay.gd`, `clients/godot-observer/scripts/ui/` (perspective control), `clients/godot-observer/scripts/presentation/identity.gd` (keep objective primary), `clients/godot-observer/tests/test_label_overlay.gd`, related scene wiring as needed.

### Phase 5: Measurement and Experiment

- [x] Task 11: v2- Add external detectors for vocabulary convergence and semantic drift.
  - Deliverable: `compute_emergent_semantic_naming` and `compute_naming_persistence` in `src/analysis/semantic_naming_metrics.py`. Add `MetricFamilyId.EMERGENT_SEMANTIC_NAMING`, bump `METRIC_FAMILY_COUNT` from 32 to 33, register tag `emergent_semantic_naming@1` in `all_metric_specifications()`. Implement locked keys. Leave prior social metric families unchanged.
  - Logging: logger `analysis.semantic_naming_metrics`. DEBUG `semantic_naming_metric_computed` with entity count and active binding count. WARNING `semantic_naming_metric_empty` with reason `no_rows` or `no_history`. No owner id lists.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 1.
  - Files: `src/analysis/semantic_naming_metrics.py`, `src/analysis/specifications.py`, `src/analysis/__init__.py`, `src/analysis/metric_service.py`, `tests/unit/test_semantic_naming_metrics.py`, `tests/unit/test_metric_specifications.py`.

- [x] Task 12: v2- Add Experiment AA off the V1 gate.
  - Deliverable: `experiment_aa_emergent_naming` pairs `aa-disabled` / `semantic_naming_disabled` on `runner-config-v4` with `aa-enabled` / `semantic_naming_deterministic` on `runner-config-v20`. Arms share seed, scenario, and stochastic identity. Register in `src/experiments/catalog.py` and export from `src/experiments/__init__.py`. Do not add to `tests/unit/test_v1_regression_gate.py`. Extend catalog lettering docs from A–Z to include AA for this additive arm.
  - Scenario builder `emergent_naming_scenario` in `src/experiments/emergent_naming_scenario.py`: two locations with researcher-canonical names (`Northern Forest`, `Clearing`), modest hazard or depleting resource at the forest, three agents `alice`, `bob`, `cy`, distinct body ids. `max_ticks` default 24 so promotion, competition, and transmission can elapse. Builder accepts no language, lexicon, glossary, dialect, or shared-name argument. Location names must not be used as label seeds; agents mint digest tokens. Bootstrap/layout display names remain the researcher canonical names.
  - Enabled arm may finish with zero active bindings. Disabled arm must finish with `semantic_naming is None` on every runtime. Catalog test asserts metric blocks are requested for the enabled arm when rows exist.
  - Logging: DEBUG `experiment_aa_built` with experiment id and condition ids. Logger `experiments.catalog`. No utterance text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on tasks 3 and 11.
  - Files: `src/experiments/emergent_naming_scenario.py`, `src/experiments/catalog.py`, `src/experiments/__init__.py`, `tests/unit/test_semantic_naming_experiment.py`.

### Phase 6: Proofs

- [x] Task 13: v2- Prove spread/compete/merge/shift/extinction, mapping privacy, digest seeds, and observer non-replacement.
  - Deliverable: tests that fail if a scenario accepts a language/lexicon field, if a metric document can be passed into `apply_naming_update`, if one conforming event promotes a binding, if one owner's ledger appears on another owner, if a `call` utterance copies speaker candidate referents, if objective observer `display_name` is overwritten by a subjective token, if the labels route works without `subjective_debug`, if memory alone mints a binding, if seeds are derived from location/exit names, if two owners mint identical seeds for the same location, if empty-candidate adopted labels enter competition, or if disabled mode changes the command.
  - Required cases across `tests/unit/test_semantic_naming.py`, `test_semantic_naming_runtime.py`, `test_semantic_naming_world.py`, `test_semantic_naming_observer.py`, `test_semantic_naming_experiment.py`, and `test_semantic_naming_metrics.py`:
    - Three location presence ticks promote a `location` binding; one tick stays `candidate` with `below_count`.
    - Two owners mint different `place_<stable8>` tokens for the same location id.
    - Hazard/death cues introduce competing `dark_<stable8>` / `dead_<stable8>` tokens without renaming the world location.
    - Listener adopts token via `call` with transmission `communicated` but does not inherit speaker candidates; empty-candidate adoption stays out of competition until self-bound.
    - Competing labels link; merge retires the weaker into the stronger at Jaccard threshold.
    - Meaning shift increments `sense_revision` after locked alternate-candidate lead window.
    - Memory reinforces existing bindings only; empty ledger + memories does not mint.
    - `DISABLED` runtime keeps pre-naming command and stores no ledger.
    - Objective frame display names unchanged when overlay is projected; overlay rows include both objective and subjective fields with `label_source="agent_perspective"` and closed `strength_band`.
    - Labels API uses live checkpoint path; `tick=` mismatch returns `labels_unavailable_at_tick`.
    - Metric fixtures report `shared_label_rate` / `preferred_label_agreement` (convergence) and `meaning_shift_rate` / `label_turnover_rate` (drift) on separate setups.
  - Logging: tests may assert DEBUG events listed above. They must not require full lexicon dumps in log records.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on tasks 7, 8, 9, 10, 11, and 12.
  - Files: `tests/unit/test_semantic_naming.py`, `tests/unit/test_semantic_naming_runtime.py`, `tests/unit/test_semantic_naming_world.py`, `tests/unit/test_semantic_naming_observer.py`, `tests/unit/test_semantic_naming_experiment.py`, `tests/unit/test_semantic_naming_metrics.py`, `clients/godot-observer/tests/test_label_overlay.gd`.

### Phase 7: Documentation

- [ ] Task 14: v2- Document the objective/subjective naming split, v20 mode, overlays, and Experiment AA.
  - Deliverable: mandatory docs checkpoint via `/aif-docs`. Append to `docs/architecture.md` item 7 after the existing artifact-interpretation / Experiment Z sentence: `SemanticNamingMode` defaults to `DISABLED`, `runner-config-v20` is emitted only when some agent's mode is `DETERMINISTIC`, Experiment AA and `emergent_semantic_naming@1` stay off the V1 gate and out of cognition, and the policy is `semantic-naming.v1`. Add a section to `docs/social-communication.md` stating digest-only seeds (no world-name parsing), private candidate links, `call` transmission without auto-grounding, `NamingCueSummary` boundary, lifecycle (spread/compete/merge/shift/disappear), and analysis-only convergence/drift. Update `docs/observer.md` and `docs/godot-observer.md` for additive `subjective_labels` overlays, live-checkpoint + `subjective_debug` gating, closed `strength_band`, and the rule that objective identity is never silently replaced. Add one sentence to `.ai-factory/DESCRIPTION.md` after the existing artifact / `runner-config-v19` sentence. Update package overviews that currently say catalog `A–Z` to mention AA as the additive naming experiment without claiming it is on the V1 gate. Update `.ai-factory/ROADMAP.md` M6 to list this plan. Do not invent a roadmap milestone.
  - Tests: doc mentions stay consistent with `semantic-naming.v1`, `emergent_semantic_naming@1`, `runner-config-v20`, and Experiment AA.
  - Logging: none beyond existing docs tooling.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL` where a docs check emits logs.
  - Depends on tasks 3, 9, 11, and 12.
  - Files: `docs/architecture.md`, `docs/social-communication.md`, `docs/observer.md`, `docs/godot-observer.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ROADMAP.md`, `.ai-factory/ARCHITECTURE.md`.
