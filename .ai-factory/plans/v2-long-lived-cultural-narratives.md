# Implementation Plan: Long-Lived Cultural Narrative Lineages

Branch: main
Created: 2026-10-03
Improved: 2026-10-03

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete roadmap milestone. Extends V1 rumor provenance into opt-in owner-scoped narrative lineages and analysis detectors; leaves `multi_hop_testimony_tracking` unowned.

## Compatibility contract

A cultural narrative is a recurring story variant privately tracked by one owner from observation, memory reconstruction, communication, artifact misreading, or deliberate false testimony. It is not a hard-coded Myth object, not a world rule, and not an automatic society-wide influence. The plan must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only mutation authority. `PhysicalRules`, `_operations`, and `_rules` stay free of myth, legend, culture, tradition, or narrative predicates. Narrative updates read the owner's `Observation`, previous `NarrativeLedger`, `OwnerSafeSocialIdentity`, already-loaded `snapshot.memories`, an optional caller-built `NarrativeCueSummary` of duck-typed distorted-artifact / reconstruction cue tokens, and closed utterance tokens already on the observation. They never receive `WorldState`, `PhysicalRules`, `AgentBody`, `WorldEvent`, an event repository, replay, analysis output, another agent's runtime, goals, drives, emotion, relationships, mind model, reputation ledger, territorial ledger, group ledger, norm ledger, convention ledger, terminology ledger, or artifact-interpretation ledger objects. The narrative module must not import `artifacts`, `semantic_naming`, `social_conventions`, `social_norms`, or `group_formation` modules. They never call a memory reconstructor or import `memory` package **writers** (`MemoryService`); importing frozen belief-request types for return values is allowed (counterfactual pattern). Opaque `EventId` correlation only — never dereference event stores. Reconstructions are not on `SubjectiveSnapshot`; prepare passes `RetrievedMemoryContext.reconstructions` (competence pattern), never invents a snapshot reconstruction field.
2. Do not own a capability flag. Do not add a `V2CapabilityFlags` field. Do not add `cultural_narratives`, `myths`, `legends`, or any new flag name. `multi_hop_testimony_tracking` stays unimplemented and still fails closed with `capability_unimplemented`. Off for this feature is `CulturalNarrativeMode.DISABLED`, which does not change commands, memories, semantic beliefs, relationships, reputation, territorial claims, group formation, social norms, social conventions, semantic naming, artifact interpretation, or audits.
3. V1 regression gate stays green under flags-off, narrative-mode disabled, and tracing-off. Catalog A–E and the reference scenario keep their current `exact_trajectory_hash` values. Experiment AB is additive and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. Schema bump only for the enabled mode. Default write stays `runner-config-v4`. Add `runner-config-v21` to the accepted set. v21 carries every `runner-config-v20` key plus `cultural_narrative_mode` on each agent. Emit v21 only when some agent's `CulturalNarrativeMode` is `DETERMINISTIC`. A naming-only config still writes v20. Reject v21 when every cultural-narrative mode is `DISABLED` (`v21_requires_cultural_narratives`). Reject `DETERMINISTIC` cultural-narrative mode on v1–v20 (`cultural_narrative_mode_requires_v21`). Widen every existing mode and spec allowlist that currently ends at v20 so v21 remains legal for communication strategy, reputation, skill learning, teaching, production knowledge, reflection, consolidation, prospective imagination, counterfactual reasoning, environmental dynamics, territorial claims, group formation, social norms, social conventions, artifact interpretation, and semantic naming. That includes the named frozensets in `src/simulation/runner_serialization.py` and every local set in `SimulationRunnerConfig.__post_init__` that currently ends at v20. Encode and decode `capability_flags` and `cognition_trace` on v21. Encode and decode `environmental_dynamics` on v21 when the spec is present, using the same rule as v20. **Landmines (exact equality today):** `runner_serialization.py` branches that encode, `_require_keys(..., _COGNITION_KEYS_V20)`, and decode `semantic_naming_mode` under `schema_version == RUNNER_SCHEMA_VERSION_V20` must become membership in `{v20, v21}` (or decode v21 before v20 with `_COGNITION_KEYS_V21`). `runner_models.py` `semantic_naming_mode_requires_v20` equality must become membership in `{v20, v21}`. Keep `v20_requires_semantic_naming` as equality on v20 only. Widen `artifact_interpretation_mode` encode/decode to `{v19, v20, v21}` and every other prior-mode membership set ending at v20 the same way. Encode `cultural_narrative_mode` only on v21. Decode v21 agent cognition with `_COGNITION_KEYS_V21`, defined as `_COGNITION_KEYS_V20` plus `cultural_narrative_mode`, before the v20 branch. `_require_keys` is an exact key check. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. No policy weights in runner JSON. Leave `v1_regression_profile` unchanged. Baseline: the accepted set already ends at `runner-config-v20`.
5. No scripted emergence. No Myth, Legend, Culture, Tradition, or Narrative **field** on `World`, `WorldState`, `Observation`, commands, events, or scenario builders. No predefined myth catalogs or hard-coded stories that auto-influence society. Closed communication relation predicates `tell_story`, `retell`, and `merge_story` are legal as **feature-local** utterance tokens (same pattern as naming's `call` / conventions' `usually`); the world layer accepts any bounded relation string and does not maintain a global predicate allowlist. No new `AgentCommand`, `ActionDirection`, `CommunicationSourceBasis`, `RelationshipDimension`, or `WorldEvent` kind. Scenarios must not contain a myth/legend/culture roster argument. Sleep stays a one-tick fatigue action.
6. No LLM path. There is no provider schema and no prompt package. `DETERMINISTIC` never calls `LLMProvider`.
7. Experiments stay reproducible. Paired arms share seed, topology, and stochastic identity. No RNG and no wall clock in narrative updates. Experiment AB and `cultural_narrative_lineage@1` stay analysis-only and off the V1 regression gate. The metric is not an input to cognition. Existing families `rumor_distortion@1`, `knowledge_diffusion@1`, `cultural_transmission@1` (teaching), `persistent_social_conventions@1`, `emergent_semantic_naming@1`, and `external_artifact_memory@1` stay unchanged.
8. Optional cognition tracing stays outside the objective fold. Do not insert a `ComponentKind` or an ordinal in `_STAGE_ORDER`. Do not bump `COGNITION_TRACE_SUMMARY_SCHEMA`, add trace enum members, or add an Alembic revision. Do not copy story tokens, narrative text, fingerprints, or analysis readings onto the trace summary. `subjective-v1` stays unchanged. Tracing on versus off must not change `exact_trajectory_hash` when the mode is `DISABLED`.

## Goal

V1 already preserves declared communication lineage and measures short-horizon `rumor_distortion`. This plan extends that substrate into long-lived cultural narrative tracking without inventing world-owned myths.

| Layer | What it is | Who may read it during a tick |
| --- | --- | --- |
| Objective event / artifact mark | World-committed occurrence or information mark | Analysis joins after the fact; cognition sees only observation tokens |
| Episodic / reconstructed memory | Owner-scoped traces and reconstructions on the retrieve context | That owner's cognition |
| Narrative variant ledger | Private recurring story claims with lineage, branches, and merges | That owner's cognition |
| Semantic belief (optional uplift) | Existing `SemanticBelief` revised only via `BeliefRevisionRequest` intents when a frequent active narrative supplies closed claim evidence | That owner's cognition via existing subjective commit |
| Analytical detectors | Persistence, mutation, distortion, source loss, convergence, geographic/social spread | Analysis only; never written onto the ledger |

A story can persist in analysis when every ledger is empty. An agent can hold an inaccurate narrative that diverges from the founding event. One owner's ledger is not copied to another owner. Hard-coded Myth objects do not exist and must never auto-bias society.

## Design Decisions (locked)

- **A ledger of variants, not a Myth type and not a world rule.** `NarrativeLedger` is owner-scoped state on `SubjectiveSnapshot.cultural_narratives`, default `None`. It holds `NarrativeVariant` values. A variant is not a `SemanticBelief`, not a `NormBelief`, not a `ConventionBelief`, not a `LabelBinding`, and not a world Myth. Updates do not invent Myth objects. When both narrative mode and other modes are `DETERMINISTIC`, dual counting is intentional (story vs habit vs expectation vs label).
- **Disabled mode is a passthrough.** `CulturalNarrativeMode.DISABLED` leaves `snapshot.cultural_narratives` as `None`, appends no evidence, emits no utterance, applies no intention bias, writes no semantic-belief uplift intents, and writes no runner field. Commands match the pre-narrative planner.
- **Story content is closed structured tokens.** `NarrativeContent` stores ordered concept tokens and relation triples (subject/predicate/object tokens) drawn from the existing communication content vocabulary plus locked narrative predicates. Free-form prose is forbidden — including `ReconstructedMemory.narrative` text, which must never enter `NarrativeContent`. Identity is `content_fingerprint` via `world.communications.content_fingerprint` over a projected `CommunicationContent` (required type). Projection uses a **stable closed `text`** token (e.g. `"tell_story"` / `"retell"` / `"merge_story"` matching the utterance predicate) because `canonical_content_bytes` hashes `text` together with concepts and relations. Content tokens never appear in INFO logs.
- **Cue summary boundary (NamingCueSummary pattern).** Frozen `NarrativeCueSummary` holds only duck-typed closed tokens the loop already knows: distorted artifact cue rows `(artifact_id, distorted: bool, reading_relation_count, mark_relation_count)` and optional reconstruction cue rows `(reconstruction_id, source_memory_ids, concept tokens, relation triples already resolved to strings)`. Built in `CognitiveLoop._prepare_cultural_narratives` after artifact/naming prepare and after memory retrieval has produced `RetrievedMemoryContext`. `apply_narrative_update` accepts `NarrativeCueSummary | None` and must not import sibling ledger modules or reconstructors.
- **Origin catalog (closed `NarrativeOrigin`).** Every variant records exactly one founding origin class:

| Origin | How it enters the ledger |
| --- | --- |
| `observed_event` | Owner observes an occurrence; opaque `source_event_id` recorded when present |
| `reconstructed_memory` | Cue/reconstruction or memory tokens mint or reinforce; opaque `source_memory_id` / optional `reconstruction_id`. Mentions resolve `RelationEndpoint` → concept/entity labels; do not assume string triples on raw `MemoryRelation` |
| `deliberate_lie` | Delivered `Tell`/`Talk` with `CommunicationSourceBasis.UNREFERENCED` accepted as story content; never proved true by world |
| `misread_artifact` | `NarrativeCueSummary` row with `distorted=True` (current artifact distortion keeps marks, truncates relations / sets `distorted` — **not** mark-token mismatch on `Observation`, which has marks only) |
| `retold_story` | Listener adopts from feature-local predicates `tell_story` / `retell` / `merge_story` citing another variant's fingerprint or transmission root |

- **Utterance `CommunicationSourceBasis` map (legal members only).** `CommunicationSourceBasis` has `BELIEF`, `RECONSTRUCTED_MEMORY`, `GOAL`, `RELATIONSHIP`, `UNREFERENCED` — there is **no** `DIRECT_OBSERVATION`. Locked mapping for `narrative_communicate_utterance`:

| Origin / case | `source_basis` |
| --- | --- |
| `observed_event` founding communicate | `UNREFERENCED` |
| `reconstructed_memory` | `RECONSTRUCTED_MEMORY` |
| `deliberate_lie` | `UNREFERENCED` |
| `misread_artifact` | `UNREFERENCED` |
| `retold_story` / child retell | inherit declared basis from the parent's last known transmission when present; else `UNREFERENCED` |
| merged result | dominant parent's mapped basis (same dominance rule as merge origin) |

- **Lineage chain (locked fields on every variant).** Preserve the research chain without collapsing stages:

```
objective event id (optional)
  → memory id (optional)
  → reconstruction id (optional)
  → communication id / transmission_root_id (optional)
  → parent_variant_ids (0..N)
  → this variant_id
  → child links via later parents
```

Required fields on every `NarrativeVariant`:
  - `variant_id` — sha256 of `owner_id|founding_fingerprint|mutation_generation|parent_salt` (hex); no Python `hash()`
  - `owner_id`
  - `content` / `content_fingerprint`
  - `origin` / `status` (`candidate` / `active` / `retired` / `merged`)
  - `strength` — quantized to `1e-6`, clamped `[0, 1]`
  - `repetition_count` / `first_tick` / `last_tick` / `last_utterance_tick` (optional int, default none)
  - `mutation_generation` (0 for founding; +1 per branch)
  - `parent_variant_ids` (cap 4) / `merged_into_id` (optional)
  - `competing_variant_ids` (cap 4; same transmission root, different fingerprint, not merged)
  - `evidence` — tuple of `NarrativeEvidenceItem` (cap 32)
  - `source_event_id` / `source_memory_id` / `reconstruction_id` / `transmission_root_id` / `last_communication_id` (optional opaque)
  - `location_ids` (cap 8) / `carrier_agent_ids` (cap 8)
- **Branching.** When an owner retells or reconstructs a story and the new content fingerprint differs from the parent while sharing the same `transmission_root_id` or an explicit parent link, mint a child variant with `mutation_generation = parent + 1`, `parent_variant_ids = (parent,)`, and origin `retold_story` or `reconstructed_memory` as appropriate. Do not overwrite the parent.
- **Merging.** When two active variants for the same owner share ≥ `merge_token_overlap` (locked 0.75) of canonical concept∪relation tokens and both have `repetition_count >= 2`, create a merged variant: union of tokens (deterministic sort), `parent_variant_ids` = both parents (ordered), origin = dominant parent origin (higher repetition; tie → lexicographic fingerprint), status `active`, parents flip to `merged` with `merged_into_id` set. Cap 4 parents on any variant. Analysis sees merge edges; cognition never reads analysis.
- **Promotion / decay.** Promote `candidate` → `active` when `repetition_count >= 3` and strength ≥ `0.40`. Strength deltas: observed `+0.12`, reconstructed/remembered reinforce `+0.08`, communicated adopt `+0.10`, deliberate_lie founding `+0.10`, misread_artifact founding `+0.10`. Decay `0.05` when no evidence this tick. Retire below `0.20`. Caps: 8 variants per owner, 32 evidence items per variant, 8 carriers, 8 locations, 4 parents, 4 competing sibling links.
- **Memory / reconstruction rules.** Memory alone **reinforces** existing fingerprints (`+0.08`, channel `remembered`) and never mints. Reconstruction cues from `NarrativeCueSummary` may **mint** a founding `reconstructed_memory` variant when no parent exists yet **only** if the cue carries a non-empty concept∪relation set and an opaque source correlation (`source_event_id` or `source_memory_id`). Forgotten/expired traces are ignored. Never copy another owner's ledger.
- **Semantic belief uplift (allowed, gated; counterfactual pattern).** When an `active` variant has `repetition_count >= semantic_uplift_repetitions` (locked 5) and strength ≥ `0.55`, `narrative_semantic_evidence(...)` returns a tuple of `BeliefRevisionRequest` values (import types from `memory.beliefs` / `memory.belief_formation`; each `BeliefEvidenceContribution` needs a real `MemoryId` anchor — prefer `source_memory_id` when present, else a stable synthetic lineage memory id derived from `variant_id` only if an existing owner memory id is unavailable and tests document that path). CognitiveLoop merges those requests into `MemoryUpdateIntent(kind=REVISE_SEMANTIC_BELIEF, ...)` the same way counterfactuals do — **never** invents a second belief store, **never** calls `MemoryService` writers from the ledger, and **never** writes analysis labels into beliefs. There is no function named `revise_semantic_belief`. Disabled mode and non-active statuses return `()`. Log metadata only (owner, tick, variant count, uplift applied boolean) — never claims/values.
- **Communicate without inventing commands.** When an active variant has strength ≥ `0.40`, a `COMMUNICATE` future already exists, and the owner has not uttered this fingerprint in the last `utterance_interval` ticks (4), prefer that future by adding penalty `0.30` to other futures. `narrative_communicate_utterance(...)` returns a relation recipe for an existing Talk: predicate `tell_story` (founding/active) or `retell` (child) or `merge_story` (merged result), subject/object from closed content tokens, `source_basis` from the locked map above. Feature-local allowlists live only in `cultural_narratives.py`. Do not construct a new `Talk`. Missing preferred future records `no_candidate`.
- **No automatic society influence.** Narrative penalties only bias an already-proposed `COMMUNICATE` future. They never insert actions, never change `PhysicalRules`, never force other agents to believe, and never download ledger objects across owners. Listeners adopt tokens from utterances only.
- **Bodies and agents stay distinct.** Occurrence, utterance, artifact, and memory ids are `EntityId` / opaque ids. Ledger owner and carrier ids are `AgentId`. Resolve with `OwnerSafeSocialIdentity`. Unresolved → `unresolved_entity`, no carrier.
- **Carry follows semantic naming.** Add `cultural_narratives` beside `semantic_naming` on `SubjectiveSnapshot`, `CognitiveLoopProposal`, `CognitiveLoopResult`, `AgentRuntimeCheckpoint`, `Perspective` (including `to_snapshot()`), and `build_perspective`. `AgentRuntime` holds `_cultural_narratives`, `_commit_cultural_narratives`, pass-into-perspective, commit-from-`loop_result`, and export/restore beside naming. `require_owner_cultural_narratives` accepts `None` or matching-owner ledger. `CognitiveLoop.prepare` calls `_prepare_cultural_narratives` immediately after `_prepare_semantic_naming` and before `_prepare_competence`: build `NarrativeCueSummary` from already-prepared artifact interpretations + retrieve-context reconstructions, call `apply_narrative_update` with `snapshot.memories` and that summary, then collect `narrative_semantic_evidence` into pending belief intents. Pass communicate preference through `_planner_options` / deliberation (`narrative_communicate_penalties` / `narrative_communicate_utterance` kwargs beside naming). Observer/API checkpoint field allowlists in `src/observer/contracts.py` and `src/api/observer_schemas.py` must include `"cultural_narratives"` beside `"semantic_naming"`. `SubjectiveMutationBatch` does not grow a narrative field (belief uplift rides existing belief intents). `subjective-v1` unchanged. No Alembic revision. Disabled checkpoint stores `None`.
- **Quantization and caps.** Strength quantized to `1e-6`, clamped to `[0, 1]`. Token-overlap for merge uses quantized float. No RNG, wall clock, or Python `hash()`.
- **Fail closed.** Unknown origin/status/predicate; owner mismatches; non-finite numbers; future penalty below 0 abort with stable reason codes. Passing `WorldState`, `WorldEvent`, or a metric document into `apply_narrative_update` raises `TypeError`.
- **Analysis never feeds cognition.** Persistence/mutation/distortion/source-loss/convergence/spread scores stay in metric documents only.

### Analysis

`compute_cultural_narrative_lineage` in `src/analysis/cultural_narrative_metrics.py` builds blocks from caller-supplied rows. Duck-type with `getattr`. Must not import `agents`, `apply_narrative_update`, or `AgentRuntime`. Leave `compute_rumor_distortion` algorithm and value keys unchanged; this family may *join* hop distortion rows as optional inputs but must not rewrite them. Metric registration mirrors Experiment AA: `MetricFamilyId` + `_spec_*` in `specifications.py`, `compute_*` module, unit fixtures — not a catalog-embedded comparison-metric table.

**Block `narrative_persistence`** from detached variant history rows `(tick, owner_id, variant_id, fingerprint, status, strength, origin, repetition_count, mutation_generation, has_source_event, location_count, carrier_count)`:

| Key | Value |
| --- | --- |
| `active_variant_count` | Rows with status `active` at final tick |
| `mean_active_strength` | Mean strength of active rows; none → `ABSENT` |
| `mean_duration_ticks` | Mean `last_tick - first_tick` of active/merged rows |
| `persistence_rate` | Fraction of founding fingerprints still represented by an active or merged-into-active lineage at the final tick |

**Block `mutation_rate`:**

| Key | Value |
| --- | --- |
| `branch_rate` | Child variants (`mutation_generation >= 1`) divided by founding variants |
| `mean_mutation_generation` | Mean generation over active rows; none → `ABSENT` |
| `fingerprint_churn` | Distinct fingerprints per transmission root (mean); empty → `ABSENT` |

**Block `distortion`:**

| Key | Value |
| --- | --- |
| `token_add_rate` | Mean added concept/relation tokens vs founding fingerprint per active child |
| `token_loss_rate` | Mean lost tokens vs founding fingerprint per active child |
| `inaccuracy_vs_objective` | Fraction of active variants whose founding `source_event_id` is present in the objective join set but whose token set fails the closed coverage check against that event's public tokens (caller supplies boolean `covers_source`; analysis does not load events) |

**Block `source_loss`:**

| Key | Value |
| --- | --- |
| `source_event_drop_rate` | Fraction of active lineages whose earliest ancestor had `has_source_event` true but the live variant has it false |
| `origin_shift_rate` | Fraction of active children whose `origin` differs from the founding ancestor origin |
| `orphan_retell_rate` | Active `retold_story` variants with empty `source_event_id` and empty `source_memory_id` divided by active rows |

**Block `convergence`:**

| Key | Value |
| --- | --- |
| `merge_rate` | Merged parent rows divided by variants that ever reached `active` |
| `mean_parents_per_merge` | Mean parent arity on merge results; none → `ABSENT` |
| `competing_variant_share` | Active rows with ≥1 competing sibling divided by active rows |

**Block `geographic_social_spread`:**

| Key | Value |
| --- | --- |
| `mean_location_span` | Mean distinct `location_ids` on active rows |
| `mean_carrier_span` | Mean distinct `carrier_agent_ids` on active rows |
| `multi_location_rate` | Active rows with `location_count >= 2` divided by active rows |
| `social_reach_rate` | Active rows with `carrier_count >= 3` divided by active rows |

Empty denominators → `MetricAvailability.ABSENT` for that key only.

Family id `cultural_narrative_lineage`. Tag `cultural_narrative_lineage@1`. Bump `METRIC_FAMILY_COUNT` from 33 to 34. Not added to the V1 bundle for catalog A–E.

## Non-Goals

- Hard-coded Myth / Legend objects, world myth fields, or automatic society-wide narrative influence
- Predefined culture/ritual/tradition scripts on world or scenario builders
- Owning `multi_hop_testimony_tracking` or changing hop>1 drop behavior in unrelated consumers
- Rewriting `rumor_distortion@1`, `knowledge_diffusion@1`, `cultural_transmission@1` (teaching), or `emergent_semantic_naming@1`
- A new `AgentCommand`, `ActionDirection`, `CommunicationSourceBasis`, or `WorldEvent` kind
- Inserting talk futures the planner did not already propose
- Free-form narrative prose in cognition state or logs (including reconstruction `narrative` text)
- Minting narrative variants from memory alone (memory reinforce-only; reconstruction cues may mint)
- Inserting a `CognitiveLoop` ordinal, bumping cognition-trace schema, bumping `subjective-v1`, or adding an Alembic revision
- Letting an agent read another agent's ledger or any analysis document
- Importing sibling ledger modules (`artifacts`, naming, conventions, norms, groups) into `cultural_narratives.py`
- Calling `MemoryService` writers from the narrative ledger
- An LLM assessor
- Putting Experiment AB on the V1 regression gate
- Feeding analysis detector scores into cognition
- Replacing semantic naming, norms, or conventions ledgers

## Commit Plan
- **Commit 1** (after tasks 1–2): `feat(simulation): add opt-in cultural narratives on runner-config-v21`
- **Commit 2** (after tasks 3–7): `feat(cognition): track owner-scoped narrative lineages`
- **Commit 3** (after tasks 8–10): `test(analysis): measure cultural narrative persistence and distortion`
- **Commit 4** (after tasks 11–12): `docs(cognition): document long-lived cultural narratives`

## Tasks

### Phase 1: Contracts and Mode

- [x] Task 1: Add cultural-narrative contracts and `CulturalNarrativePolicy`.
  - Deliverable: frozen types in `src/agents/cognition/cultural_narratives.py`, exported from `src/agents/cognition/__init__.py`. `DISABLED` leaves the snapshot field `None`.
  - Types: `NarrativeOrigin` (`observed_event`, `reconstructed_memory`, `deliberate_lie`, `misread_artifact`, `retold_story`), `NarrativeStatus` (`candidate`, `active`, `retired`, `merged`), `NarrativeEvidenceChannel` (`observed`, `remembered`, `reconstructed`, `communicated`, `artifact`), `NarrativeContent`, `NarrativeEvidenceItem`, `NarrativeVariant` (required fields as locked above, including `strength`, `evidence`, `last_utterance_tick`, `competing_variant_ids`), `NarrativeLedger`, `NarrativeCueSummary`, `CulturalNarrativePolicy` (`cultural-narratives.v1`, active strength `0.40`, retire strength `0.20`, decay `0.05`, deltas as locked, promotion count `3`, semantic uplift repetitions `5`, semantic uplift strength `0.55`, merge token overlap `0.75`, utterance interval `4`, penalty `0.30`, caps 8 variants / 32 evidence / 8 carriers / 8 locations / 4 parents / 4 competing). `CognitionCulturalNarrativeMode` (`DISABLED`, `DETERMINISTIC`) in `src/agents/cognition/configuration.py` and matching runner enum in `src/simulation/runner_models.py`. Helpers: `content_fingerprint` projection via `CommunicationContent` with stable closed `text`; feature-local predicate allowlist `{tell_story, retell, merge_story}`.
  - Constructors reject unknown enums, parent sets larger than 4, `merged` status without `merged_into_id` on parents / without ≥2 parents on the merge result, and free-form prose fields.
  - Logging: logger `agents.cognition.cultural_narratives`. DEBUG on construction with owner id, policy version, and variant count. ERROR with field name and reason code on validation failure. No content tokens, fingerprints as payload surrogates, or claim text at INFO.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Files: `src/agents/cognition/cultural_narratives.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/__init__.py`, `src/simulation/runner_models.py`, `tests/unit/test_cultural_narratives.py`.

- [x] Task 2: Wire `DETERMINISTIC` through `runner-config-v21` without owning a new flag.
  - Deliverable: mode off keeps `runner-config-v4` and today's commands. Mode on is accepted only as `runner-config-v21`. `multi_hop_testimony_tracking` still fails closed. A v21 document can still carry every prior mode including semantic naming and artifact interpretation.
  - Add `cultural_narrative_mode` to `AgentCognitionSpec` and `CognitionLoopConfig`. Default both to `DISABLED`. Accept v21 in `SUPPORTED_RUNNER_SCHEMA_VERSIONS`. Define `_COGNITION_KEYS_V21` as `_COGNITION_KEYS_V20` plus `cultural_narrative_mode`. **Fix landmines:** replace `schema_version == RUNNER_SCHEMA_VERSION_V20` encode / `_require_keys(..., _COGNITION_KEYS_V20)` / decode of `semantic_naming_mode` with membership `{v20, v21}` (decode v21 branch first). Change `semantic_naming_mode_requires_v20` to membership `{v20, v21}`; keep `v20_requires_semantic_naming` equality on v20. Widen `artifact_interpretation_mode` to `{v19, v20, v21}` and every other prior-mode set ending at v20. Encode `cultural_narrative_mode` only on v21. Add `cultural_narrative_mode_requires_v21` and `v21_requires_cultural_narratives`. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. Do not add a `V2CapabilityFlags` field. `simulation.runner._cognition_config_for` sets `CognitionCulturalNarrativeMode.DETERMINISTIC` only from that field and builds `default_cultural_narrative_policy()`. Update `src/simulation/compatibility.py`. Export `RUNNER_SCHEMA_VERSION_V21` from `src/simulation/__init__.py`.
  - Tests: multi_hop still `capability_unimplemented`; disabled mode does not bump schema; naming-only still writes v20; narrative deterministic writes v21 and round-trips prior modes when combined (especially `semantic_naming_mode` + `artifact_interpretation_mode`); v21 with narrative mode disabled is rejected; naming+narratives writes v21. One combined config with narratives, naming, artifacts, conventions, and environmental dynamics round-trips flags and tracing. Run `uv run ruff check` on each touched file.
  - Logging: DEBUG `cognition_config_cultural_narrative_mode mode=%s policy_version=%s` on logger `simulation.runner`. ERROR on schema rejection uses existing stable runner codes.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 1.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/runner.py`, `src/simulation/__init__.py`, `src/agents/cognition/configuration.py`, `tests/unit/test_runner_models.py`, `tests/unit/test_runner_serialization.py`, `tests/unit/test_simulation_runner_construction.py`, `tests/unit/test_v2_flag_defaults.py`, `tests/unit/test_cognition_configuration.py`, `tests/unit/test_compatibility_matrix.py`.

### Phase 2: Private Narrative Learning

- [x] Task 3: Seed and reinforce variants from observation, memory, reconstruction cues, lies, and distorted artifacts.
  - Deliverable: `apply_narrative_update(...)` returns a new `NarrativeLedger` for one owner. Accepts this tick's `Observation`, `OwnerSafeSocialIdentity`, previous ledger, optional owner `memories` sequence, and optional `NarrativeCueSummary`. Passing `WorldState`, `WorldEvent`, artifact-ledger objects, or a metric document raises `TypeError`. Module must not import `analysis`, `simulation`, `world.models`, `world.events`, `world._state`, or sibling ledger modules. May import `world.observations` and `world.communications` contracts. May type-check memory via `TYPE_CHECKING` or duck-typing without importing `MemoryService` or reconstructors.
  - Apply locked origin table and tick order: match observed events → deliberate_lie detections → `NarrativeCueSummary` misread_artifact / reconstruction mint-or-reinforce → memory reinforce-only → participant/location updates → candidate promotion → competing-variant links → decay. Dedup evidence on `(fingerprint, channel, source_id)`. Caps drop with `cap_exceeded`. Memory never mints. Reconstruction mint only from cue rows with source correlation. Misread uses `distorted=True` cue rows (not observation mark mismatch). Resolve reconstruction/memory relation endpoints to string tokens before fingerprinting; ignore free-form `narrative` prose.
  - Logging: DEBUG `narrative_variant_applied` with owner id, tick, origin, and sign. INFO `narrative_ledger_updated` with owner id and variant count. WARNING `narrative_evidence_dropped` with reason `cap_exceeded`, `ignored_kind`, `unresolved_entity`, or `empty_content`. ERROR on owner mismatch. No content tokens or claim text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 1.
  - Files: `src/agents/cognition/cultural_narratives.py`, `tests/unit/test_cultural_narratives.py`.

- [x] Task 4: Branch, merge, and retire narrative lineages.
  - Deliverable: fingerprint-diverging retells/reconstructions create child variants with incremented `mutation_generation` and single parent. Merge under locked overlap/repetition rules; parents become `merged` with `merged_into_id`. Decay and retire under locked thresholds. Competing sibling links for same transmission root / different fingerprint (cap 4).
  - Logging: DEBUG `narrative_variant_branched`, `narrative_variant_merged`, `narrative_variant_promoted`, or `narrative_variant_retired` with owner id, tick, status, and generation. WARNING `narrative_merge_withheld` with reason `below_overlap`, `below_count`, or `cap_exceeded`. No fingerprints as payload surrogates at INFO.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 3.
  - Files: `src/agents/cognition/cultural_narratives.py`, `tests/unit/test_cultural_narratives.py`.

- [x] Task 5: Adopt from communication and prefer story utterances without creating commands.
  - Deliverable: listener path adopts/reinforces from feature-local predicates `tell_story`, `retell`, and `merge_story` (origin `retold_story`; preserve declared `transmission_root_id` / communication ids when present). `narrative_communicate_penalties(...)` and `narrative_communicate_utterance(...)` use locked quantum `0.30` and the locked `CommunicationSourceBasis` map (no `DIRECT_OBSERVATION`). Disabled mode and non-ledger return empty map / `None`. Missing preferred future records `no_candidate`. Functions do not construct `Talk`.
  - Logging: DEBUG `narrative_transmission_applied` / `narrative_response_selected` with owner id, tick, and channel/response. WARNING `narrative_response_withheld` with reason `no_candidate`, `candidate_only`, or `utterance_interval`. No utterance text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 4.
  - Files: `src/agents/cognition/cultural_narratives.py`, `tests/unit/test_cultural_narratives.py`.

- [x] Task 6: Prove world authority is unchanged by narrative habits.
  - Deliverable: focused regression in `tests/unit/test_cultural_narratives_world.py`: Talk/Ask/Tell with story predicates still admit under current physical rules with no engine myth/narrative check. Tests call existing operations only. Scenario/builders reject myth/legend/culture/narrative roster kwargs.
  - Logging: DEBUG only on existing world loggers; no narrative content tokens in world logs.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 5.
  - Files: `tests/unit/test_cultural_narratives_world.py`.

- [x] Task 7: Gate semantic belief uplift via `BeliefRevisionRequest` (API only).
  - Deliverable: `narrative_semantic_evidence(...)` returns `tuple[BeliefRevisionRequest, ...]` only when active + repetition/strength gates pass (mirror `counterfactual_belief_requests`). Each contribution anchors a real `MemoryId`. Prove uplift does not run for `candidate` / `retired` / `merged` / disabled. Prove claim tokens are owner-scoped and never copy another owner's belief ids. Ledger must not call `MemoryService` or emit `MemoryUpdateIntent` itself — loop wiring is Task 8.
  - Logging: DEBUG `narrative_semantic_uplift` with owner id, tick, variant count, and uplift boolean. WARNING `narrative_uplift_withheld` with reason `below_repetition`, `below_strength`, `inactive_status`, `disabled`, or `no_memory_anchor`. Never log claim/value text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 4.
  - Files: `src/agents/cognition/cultural_narratives.py`, `tests/unit/test_cultural_narratives.py`, `tests/unit/test_cultural_narratives_beliefs.py`.

### Phase 3: Runtime and Measurement

- [x] Task 8: Carry the ledger, observer allowlists, uplift intents, and communicate penalties.
  - Deliverable: add `cultural_narratives` on the same surfaces naming already uses (`SubjectiveSnapshot`, loop proposal/result, `Perspective` + `to_snapshot()`, `build_perspective`, `AgentRuntime` `_cultural_narratives` / `_commit_cultural_narratives` / export-restore). `require_owner_cultural_narratives` accepts `None` or matching-owner ledger. `CognitiveLoop.prepare` calls `_prepare_cultural_narratives` after `_prepare_semantic_naming`: build `NarrativeCueSummary` from already-prepared artifact interpretations + `RetrievedMemoryContext.reconstructions`, call `apply_narrative_update`, merge `narrative_semantic_evidence` into pending `REVISE_SEMANTIC_BELIEF` intents (counterfactual merge pattern). Thread `narrative_communicate_penalties` / `narrative_communicate_utterance` through `_planner_options` and deliberation kwargs. Add `"cultural_narratives"` to observer checkpoint field allowlists in `src/observer/contracts.py` and `src/api/observer_schemas.py` beside `"semantic_naming"`. `DISABLED` keeps pre-narrative commands and stores no ledger.
  - Do not insert a `ComponentKind`. Do not bump `subjective-v1`.
  - Logging: DEBUG `cultural_narratives_carried` with owner id and variant count on logger `agents.cognition.loop`. DEBUG `narrative_penalty_applied` with future count on logger `agents.cognition.deliberation`. WARNING `narrative_carry_rejected` with reason `owner_mismatch` or `invalid_type`.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on tasks 2, 5, and 7.
  - Files: `src/agents/cognition/models.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/loop.py`, `src/agents/cognition/deliberation.py`, `src/simulation/agent_runtime.py`, `src/simulation/perception.py`, `src/simulation/run_control.py`, `src/observer/contracts.py`, `src/api/observer_schemas.py`, `tests/unit/test_cultural_narratives_runtime.py`.

- [x] Task 9: Add analysis detectors for cultural narrative lineage.
  - Deliverable: `compute_cultural_narrative_lineage` in `src/analysis/cultural_narrative_metrics.py`. Add `MetricFamilyId.CULTURAL_NARRATIVE_LINEAGE`, bump `METRIC_FAMILY_COUNT` from 33 to 34, register tag `cultural_narrative_lineage@1`. Implement locked blocks/keys. Leave `compute_rumor_distortion`, teaching `cultural_transmission`, and `compute_emergent_semantic_naming` unchanged.
  - Logging: logger `analysis.cultural_narrative_metrics`. DEBUG `cultural_narrative_metric_computed` with active variant count and block availability codes. WARNING `cultural_narrative_metric_empty` with reason `no_rows` or `no_history`. No owner id lists or fingerprints as payload surrogates.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on task 1.
  - Files: `src/analysis/cultural_narrative_metrics.py`, `src/analysis/specifications.py`, `src/analysis/__init__.py`, `src/analysis/metric_service.py`, `tests/unit/test_cultural_narrative_metrics.py`, `tests/unit/test_metric_specifications.py`.

- [x] Task 10: Add Experiment AB where a real event becomes a persistent inaccurate narrative.
  - Deliverable: `experiment_ab_cultural_narratives` pairs `ab-disabled` / `cultural_narratives_disabled` on `runner-config-v4` with `ab-enabled` / `cultural_narratives_deterministic` on `runner-config-v21`. Arms share seed, scenario, and stochastic identity (mirror Experiment AA). Register in `src/experiments/catalog.py` and export from `src/experiments/__init__.py`. Update catalog module docstring from “A–Z and AA” to include AB. Do not add to `tests/unit/test_v1_regression_gate.py`.
  - Scenario builder `cultural_narratives_scenario` in `src/experiments/cultural_narratives_scenario.py`: two locations (`clearing`, `ridge`), day/night weather, four agents (`ada`, `ben`, `cy`, `dia`), distinct body ids, one clear objective founding event (e.g. a visible resource depletion or portable transfer that yields public tokens). Agents can observe, reconstruct, and retell across locations over `max_ticks` default 36 so promotion, mutation, merge window, and semantic uplift gates can elapse. Builder accepts no myth/legend/culture/narrative roster argument. Enabled arm may plant at most a structural opportunity for misremembering/retelling (topology + tick budget) — never a hard-coded Myth object and never an automatic society influence field.
  - Enabled arm may finish with zero active variants. Disabled arm must finish with `cultural_narratives is None` on every runtime. Catalog/unit tests assert metric blocks are requested for the enabled arm when rows exist, and a fixture path demonstrates `inaccuracy_vs_objective` / `persistence_rate` can be non-zero when child tokens diverge from founding public tokens while the lineage remains active.
  - Logging: DEBUG `experiment_ab_built` with experiment id and condition ids. Logger `experiments.catalog`. No utterance or story text.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on tasks 2 and 9.
  - Files: `src/experiments/cultural_narratives_scenario.py`, `src/experiments/catalog.py`, `src/experiments/__init__.py`, `tests/unit/test_cultural_narratives_experiment.py`.

### Phase 4: Proofs

- [x] Task 11: Prove lineage, mutation, merge, uplift gates, cue boundaries, and no hard-coded myths.
  - Deliverable: tests that fail if a scenario accepts a myth/legend/culture field, if a metric document or artifact ledger object can be passed into `apply_narrative_update`, if one conforming event promotes a variant, if one owner's ledger appears on another owner, if `rumor_distortion` value keys change, if `Myth` types appear in cognition exports, if disabled mode changes the command, if semantic uplift runs below repetition/strength gates, if uplift calls `MemoryService`, if `DIRECT_OBSERVATION` is used as a communication basis, if free-form reconstruction prose enters content, or if narrative mode owns `multi_hop_testimony_tracking`.
  - Required cases across unit/runtime/world/experiment/metric/belief tests:
    - Three observed founding ticks promote `observed_event`; one tick stays `candidate` with `below_count`.
    - Reconstruction cue can mint a founding variant when source correlation exists; memory alone does not mint; forgotten traces do not reinforce.
    - `deliberate_lie` founding from UNREFERENCED tell; world does not mark it true.
    - `misread_artifact` founding from `NarrativeCueSummary` `distorted=True` rows; observation-only marks without cue do not mint misread.
    - Retell with mutated tokens branches (`mutation_generation` increments; parent preserved).
    - Two overlapping active variants merge; parents become `merged` with `merged_into_id`.
    - Listener adopts via `tell_story`/`retell` without copying speaker ledger object identity; utterance basis uses locked map.
    - Semantic uplift withheld below gates; applied at locked thresholds returning `BeliefRevisionRequest`; loop merge covered in runtime tests.
    - `DISABLED` runtime keeps pre-narrative command and stores no ledger; observer allowlist includes the field name when present.
    - World tests admit story-predicate Talk with no engine myth check.
    - Metric fixtures report persistence, mutation, distortion, source loss, convergence, and geographic/social spread on separate setups; `inaccuracy_vs_objective` uses caller-supplied coverage booleans only.
  - Logging: tests may assert DEBUG events listed above. They must not require content tokens in log records.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL`.
  - Depends on tasks 6, 7, 8, 9, and 10.
  - Files: `tests/unit/test_cultural_narratives.py`, `tests/unit/test_cultural_narratives_beliefs.py`, `tests/unit/test_cultural_narratives_runtime.py`, `tests/unit/test_cultural_narratives_world.py`, `tests/unit/test_cultural_narratives_experiment.py`, `tests/unit/test_cultural_narrative_metrics.py`.

### Phase 5: Documentation

- [x] Task 12: Document the narrative/lineage/analysis split and the v21 mode.
  - Deliverable: mandatory docs checkpoint via `/aif-docs`. Append to `docs/architecture.md` item 7 after the existing semantic-naming / Experiment AA sentence: `CulturalNarrativeMode` defaults to `DISABLED`, `runner-config-v21` is emitted only when some agent's mode is `DETERMINISTIC`, Experiment AB and `cultural_narrative_lineage@1` stay off the V1 gate and out of cognition inputs, and the policy is `cultural-narratives.v1`. Add a section to `docs/social-communication.md` stating V1 rumor provenance extends into owner-scoped narrative lineages (origins, `NarrativeCueSummary`, branch/merge, `BeliefRevisionRequest` uplift gates) and that Myth objects / automatic society influence are forbidden. Add analysis keys to `docs/analysis-metrics.md`. Add one sentence to `.ai-factory/DESCRIPTION.md` after the existing semantic-naming / `runner-config-v20` sentence. Update `.ai-factory/ROADMAP.md` M6 to list this plan as started/implemented when done; keep `multi_hop_testimony_tracking` as the remaining open flag item. Do not invent a roadmap milestone.
  - Tests: doc mentions stay consistent with `cultural-narratives.v1`, `cultural_narrative_lineage@1`, `runner-config-v21`, and Experiment AB.
  - Logging: none beyond existing docs tooling.
  - Control: levels follow `PALIMPSEST_LOG_LEVEL` where a docs check emits logs.
  - Depends on tasks 2, 9, and 10.
  - Files: `docs/architecture.md`, `docs/social-communication.md`, `docs/analysis-metrics.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ROADMAP.md`.
