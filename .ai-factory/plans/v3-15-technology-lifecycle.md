# Implementation Plan: V3-15 Technology and Technique Lifecycle

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-08
Improved: 2026-10-08 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Deepens already-owned `cultural_historical_memory` with analysis-only technique states so research can see discovery, diffusion, local extinction, global loss, and independent rediscovery without a technology tree.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-15-technology-lifecycle.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; suggested stem `v3-15-technology-lifecycle`; git.create_branches=false so stem is description slug (branch-derived naming disabled)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; scope is explicitly v3-15 under M7 so linkage uses M7
INFO [aif-improve] refined 2026-10-08: `_KNOWLEDGE_GENEALOGY_SCHEMAS` and the v36 experimentation equality widen to v37; cultural-only still forbids `population_lifecycle` and allows `technique_lifecycle`; recipe ids checked in `SimulationRunnerConfig` post-init; holder place is the latest `AppliedActionRow.location_id`; record-only extant is `rare` or `discovered`, and `known` requires `known_by_n >= 1`; `teaching_chain_failed` needs a prior chain; detached harvest task supplies node, item, and artifact `location_id` rows; AR second holder inside the window is `diffusing`

## Compatibility contract

This plan **deepens** already-owned **`V3CapabilityFlags.cultural_historical_memory`** (v3-09 through v3-14). It adds **research support for a technique lifecycle**. States are computed after the run from existing skills, recipes, tools, practical knowledge, teaching, and records. They are not world rules.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents receive immutable per-agent `Observation` / `Perspective` only. `WorldEvent` records remain immutable and append-only. Subjective state stays outside the objective fold. Godot remains read-only. Deterministic replay continues. No scripted `technology_unlocked` / `technique_must_spread` / `rediscovery_required` outcomes.
2. Flag ownership unchanged: keep `cultural_historical_memory`, `generational_population`, and `kinship_inheritance` owned. Do **not** own `multi_polity_migration`, `institutional_economy`, or `multi_hop_testimony_tracking`. **No new V3 capability flag.**
3. Flags-off / channel-off / lifecycle-object-absent = prior baseline. With all V3 flags off, or with `cultural_historical_memory=False` / `cultural_feature_provenance` absent / `knowledge_genealogy` absent / `technique_lifecycle` absent, trajectories and `exact_trajectory_hash` match the pre-plan baseline for AE–AQ where applicable. Existing genealogy, experiment, durable, repository, and cultural metric families stay unchanged (sibling families only).
4. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2/V3 versions in the same change that adds a write version.
5. **No technology tree (locked).** There is no unlock graph, no prerequisite edge between techniques, no society-wide tech level, and no command that becomes legal only after a state flips. Forbidden aliases include `technology_tree`, `tech_unlock`, `civilization_tech`, `required_tech`, `unlock_prerequisite`, `global_technique_registry`, `society_technology`.
6. **Identity (locked).** A technique is one practical-knowledge `content_key` (`tech:{token}`). Objective skills, recipe rows, tool roles, teaching hops, and durable records are **grounding evidence** for that key. They are not separate unlock nodes. `SkillDomain` growth does not mint a lifecycle row by itself.
7. **Analysis only (locked).** No new `AgentCommand`, no new `WorldEvent`, no replay/codec bump, no Alembic revision, no Observation field, no cognition feedback. Command count stays **35**. Observer semantic count stays **54**. Protocol id stays `observer-protocol-v1`. Alembic head stays `0017`. Write-pair selection stays the v3-14 priority (experimentation on → replay-v15 / codec v12; otherwise unchanged).
8. **Loss does not erase stores (locked).** Classifying `globally_lost` does not delete practical-knowledge audits, skill rows, dead-holder inventory, or tombstoned artifacts. Holder death already leaves the ledger in place; `query_who_currently_knows` already drops the dead. This plan only labels that fact.
9. **Independent rediscovery (locked).** A new `KnowledgeTransmissionOrigin.independent_discovery` root (hop 0, new `lineage_root_id`) that appears after `globally_lost`, or inside a location that was `locally_extinct`, is `rediscovered`. A second independent root while the technique is still known somewhere is the existing genealogy dual-emergence count, not this state. Rediscovery does not merge lineage and does not copy the lost root.
10. **Materials do not delete knowledge (locked).** Empty resource nodes and missing tools set `performable=false` and may attach loss cause `materials_absent`. They do not flip `globally_lost` while a living holder or an intact cited record remains, and they do not block `Harvest` / `Craft` / `Experiment`. Practice can be unavailable while the technique is still `known`.
11. **Preserve v3-02–v3-14 locks:** blank-slate deny-list unchanged (no new subjective ledger); closed Observation unchanged; ELDER ≠ leader; related ≠ affection; no parent→caregiver hardwiring; no global Culture / LibraryInstitution / `GlobalTechniqueRegistry`; durable marks ≠ truth; historical layers stay analysis-only; a successful experiment is not knowledge until learn/teach/record; LLM drafts cannot name physics; kinship cultural inheritance handoff stays deferred; triple representation (objective capability ≠ subjective knowledge ≠ research lineage) stays intact.
12. **`api` must not import `analysis`.** Persist metric docs offline; serve via existing `MetricReadService` / inspection projections only. `simulation` and `persistence` must not import `analysis`.

## Goal

Let a researcher see, for each practical technique, whether it is newly found, known by N living agents, spreading, scarce, gone from a place, gone from the world, or found again independently.

Closed states (one per technique per scope per `as_of_tick`):

| State | Meaning |
| --- | --- |
| `discovered` | No prior loss. Either one living holder at one location whose peak never exceeded 1, or a cited record with `known_by_n=0` and no living holder on any earlier tick |
| `known` | Extant, `known_by_n >= 1`, and none of the other states apply |
| `diffusing` | Extant, and inside the window the living-holder count rose, the location count rose, or a new teaching/imitation entry appeared |
| `rare` | Still extant, and either living holders are at or below `rare_max` after a higher peak, or `known_by_n=0` while an intact cited record remains after any earlier living holder |
| `locally_extinct` | This location once had a living holder or an intact cited record and now has neither, while the technique still exists somewhere else |
| `globally_lost` | No living holder anywhere and no intact cited record anywhere |
| `rediscovered` | Extant again because a new independent-discovery root appeared after global loss, or inside a location that had been locally extinct |

`known_by_n` is a count on every extant row, including `discovered`, `known`, `diffusing`, `rare`, and `rediscovered`. It is the number of living agents with an active entry for that `content_key`. It is not a separate enum member per N.

Disappearance causes (a set, not a state). More than one may be true:

| Cause | When it attaches |
| --- | --- |
| `holders_died` | Living-holder count fell because those agents' death ticks are now `<= as_of_tick` |
| `records_destroyed` | A cited artifact moved to `RecordIntegrity.DESTROYED`, or a repository `destroy` dropped the last intact cited member |
| `materials_absent` | A declared recipe anchor has no usable resource or required tool in scope (`performable=false`) |
| `teaching_chain_failed` | A `teaching` or `imitation` entry, or a mentorship bond, existed on an earlier tick, and no living holder continues it. A lone independent root does not set this cause |

Deliver:

- Exact optional root sibling `technique_lifecycle` on **`runner-config-v37`**
- Analysis-only classifier over detached genealogy audits, death ticks, cited artifact integrity, optional recipe anchors, and teaching/mentorship audits
- Three sibling metric families plus a diffusion/lineage query
- Research UI Analytics discovery badges for the three families
- Off-gate Experiment AR

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` does not read or write lifecycle states.
2. Agents never receive lifecycle rows, loss causes, or another agent's knowledge ledger.
3. `WorldEvent` records remain immutable; authoritative history stays append-only.
4. Research queries must not bias live cognition.
5. No scripted spread, extinction, or rediscovery booleans.
6. Godot remains read-only; this plan adds no map chrome and no semantic event type.
7. Runs remain reproducible (explicit seeds, no lifecycle RNG, deterministic fakes).

### Scope split (locked)

| This plan (v3-15) | Deferred |
| --- | --- |
| Analysis states for existing `tech:{token}` keys | Civilization unlock trees and tech prerequisites |
| Loss causes from death, tombstones, materials, teaching failure | Deleting ledgers, skills, or records when a state flips |
| `performable` overlay from recipe anchors | New tool-break / durability events |
| Independent rediscovery after loss, new lineage root | Merging a rediscovery into the lost lineage |
| `runner-config-v37` thresholds only | Replay/codec bump, Alembic `0018+`, `/v2` HTTP |
| Three sibling metrics + Experiment AR | Interactive diffusion map in GraphsPanel |
| Optional material anchors declared on the spec | Inferring recipe links from free text or LLM output |

**Rationale for cultural coupling:** v3-09 reserved cultural memory under `cultural_historical_memory`. v3-13 records who holds a method and who taught it. v3-14 records how a method can start in private experiment. v3-15 is the research reading of what happens to that method across deaths, lost records, missing materials, and failed teaching. The classifier is not a fourth knowledge store.

### Capability / ownership (locked)

1. **No new V3 flag.** Enabling the lifecycle requires already-owned `cultural_historical_memory=True`, exact `cultural_feature_provenance`, exact `knowledge_genealogy`, and exact `technique_lifecycle` on `runner-config-v37`.
2. **Prerequisite:** genealogy is required because practical-knowledge audits are committed only while that channel is on. `durable_records`, `knowledge_repositories`, production catalog, skill learning, teaching, mentorship, and `bounded_experimentation` are **optional**. Without durable records, `records_destroyed` stays `not_applicable`. Without a production catalog, material anchors are rejected. Without teaching/mentorship, `teaching_chain_failed` is evaluated from practical-knowledge origins alone.
3. **v36 without `technique_lifecycle`** stays valid (AQ baseline). Schema `v37` always requires `technique_lifecycle` when that schema is selected.
4. Do **not** implement kinship knowledge inheritance handoff.
5. Other unowned V3 flags still fail closed.
6. When the lifecycle object is absent: AE–AQ bit-identity matches pre-plan for the same roster and seeds.
7. Do **not** claim that enabling the lifecycle auto-enables teaching, skill learning, durable records, genealogy, or experimentation. The classifier skips a missing optional harvest with DEBUG.

### Flag × object gate matrix (locked)

| Config shape | Allowed? | Reject / notes |
| --- | --- | --- |
| Cultural flag off, lifecycle absent | Yes (off) | Passthrough |
| Lifecycle object present, cultural flag off | No | `technique_lifecycle_without_cultural_flag` |
| Lifecycle object present, provenance absent | No | `technique_lifecycle_requires_cultural_provenance` |
| Lifecycle object present, genealogy absent | No | `technique_lifecycle_requires_knowledge_genealogy` |
| Lifecycle object present on schema ≠ v37 | No | `technique_lifecycle_requires_v37` |
| Cultural + provenance + genealogy on **v36**, lifecycle absent | Yes | Pre-plan AQ behavior |
| Cultural + provenance + genealogy + lifecycle on **v31..v36** | No | `technique_lifecycle_requires_v37` |
| Cultural + provenance + genealogy + lifecycle on **v37** | Yes | Classifier enabled |
| Schema `v37` without lifecycle object | No | `v37_requires_technique_lifecycle` |
| Schema `v37` without provenance | No | `v37_requires_cultural_provenance` |
| Schema `v37` without genealogy | No | `v37_requires_knowledge_genealogy` |
| Experimentation / durable / repository on **v37** (with lifecycle + genealogy) | Yes | Widen allowlists capped at v36 to include v37 |
| Lifecycle `mode=disabled` present | No | `technique_lifecycle_mode_invalid` — omit object for off |
| Cultural flag on, `generational_population` off, schema v37, `technique_lifecycle` present | Yes | Extend `_HISTORICAL_MEMORY_CULTURAL_SCHEMAS` and the cultural-only error string through v37. Cultural-only still forbids `population_lifecycle`. It allows `technique_lifecycle` |
| Genealogy on v37 without lifecycle | No | `v37_requires_technique_lifecycle` |
| Material anchor whose `content_key` lacks `tech:` | No | `technique_anchor_content_key` |
| Material anchor `recipe_id` absent from the run catalog | No | `technique_anchor_unknown_recipe` |
| Material anchor with `requires_technique` or any other technique id | No | `technique_anchor_prerequisite_forbidden` |
| Duplicate anchor `content_key` | No | `technique_anchor_duplicate` |

### Runner schema (locked)

Introduce `RUNNER_SCHEMA_VERSION_V37 = "runner-config-v37"`:

- Exact root key set = **v36 accepted roots** ∪ sibling **`technique_lifecycle`** (genealogy required when v37 is selected; experimentation / durable / repository keys remain optional).
- `technique_lifecycle` present ⇒ `schema_version == runner-config-v37`, cultural flag on with exact provenance, and exact `knowledge_genealogy`.
- Decode v23–v36 synthesizes `technique_lifecycle=None`.
- Gate rewrite: `cultural_historical_memory=True` accepts `{v31..v37}`. Add v37 to `_HISTORICAL_MEMORY_CULTURAL_SCHEMAS`, `_DURABLE_RECORDS_SCHEMAS`, `_HISTORICAL_MEMORY_LAYER_SCHEMAS`, `_KNOWLEDGE_REPOSITORIES_SCHEMAS`, and `_KNOWLEDGE_GENEALOGY_SCHEMAS` (today `{v35, v36}` only). Change the `bounded_experimentation` schema check from `schema_version == runner-config-v36` to a set that includes v37, so an optional experiment channel on v37 does not raise `bounded_experimentation_requires_v36`. Extend the cultural-only error string, which still names only v31–v35, through v37. Cultural-only means `generational_population` is off: it still forbids `population_lifecycle` and it allows `technique_lifecycle`.
- Default write stays `runner-config-v4` when all V3 flags are off.
- **No write-pair bump.** Do not add `EVENT_SCHEMA_REPLAY_V16` or codec `v13`. `checkpoint_schema_for_production` is unchanged.
- **Matrix finalize (Task 9 only):** in `src/experiments/matrix_schema.py`, insert `technique_lifecycle_on` immediately before the current first branch `bounded_experimentation_on` (v37 beats v36). Task 1 must **not** edit finalize priority.

### Serialization contract (locked)

Mirror the v36 helper pattern in `runner_serialization.py`:

- v37 root keys = v36 family helper ∪ `{technique_lifecycle}` minus optional objects that are absent
- Exact child keyset `_TECHNIQUE_LIFECYCLE_KEYS` and nested `_TECHNIQUE_MATERIAL_ANCHOR_KEYS`
- `_encode_technique_lifecycle` / `_decode_technique_lifecycle` with `_require_keys`
- Encode: `schema_version == V37` requires provenance + genealogy + lifecycle; experimentation/durable/repository/layers optional
- Decode: v23–v36 → `technique_lifecycle=None`
- DEBUG log present/absent, `anchor_count`, and threshold integers on decode (no `content_key` values)
- Reject forbidden aliases listed in the compatibility contract

### `TechniqueLifecycleSpec` (locked)

Root sibling object; omit for off. Exact keys (reject extras / missing):

| Key | Type / values | Role |
| --- | --- | --- |
| `policy_id` | `technique-lifecycle-v1` only | Closed policy id |
| `diffusion_window_ticks` | int 1..64, default 8 | Lookback for holder growth, location growth, and new teaching entries |
| `rare_max` | int 1..4, default 1 | Living-holder ceiling for `rare` after a higher peak |
| `rediscovery_latch_ticks` | int 1..32, default 4 | How long `rediscovered` stays latched after the new root appears |
| `material_anchors` | tuple, max 64, default empty | Optional `TechniqueMaterialAnchor` rows. Empty means `materials_absent` is `not_applicable` for every technique |

`TechniqueMaterialAnchor` exact keys:

| Key | Type | Role |
| --- | --- | --- |
| `content_key` | `tech:{token}` | Technique being anchored. Not a prerequisite |
| `recipe_id` | catalog recipe id | Must exist on every `agent.cognition.production_catalog`. Checked in `SimulationRunnerConfig` post-init, same site as `experiment_law_unknown_product`, after the existing `production_catalog_mismatch` digest check. Decode only checks the key shape |

No `requires_technique`, no tier, no cost, no unlock flag. The anchor is a research join from an existing recipe onto an existing content key. It does not add a recipe and does not change production rules.

### Runtime channel flags (locked)

1. `technique_lifecycle_active = config.technique_lifecycle is not None` at run start.
2. Bind the spec only into analysis assembly and the experiment AR profile. Do **not** pass it into `CognitiveLoop` or `WorldEngine`.
3. No subjective checkpoint field. No blank-slate key. No SQLAlchemy table.

### Grounding (locked)

Build one `TechniqueLifecycleSnapshot` per `content_key` that appears in harvested practical-knowledge audits. Do not invent keys from skill rows alone.

| Ground | Source | Rule |
| --- | --- | --- |
| Living knowledge | `build_knowledge_genealogy_graph` + `query_who_currently_knows` | Living active entry. Dead holders stay in audits and do not count |
| Holder place | Latest `AppliedActionRow.location_id` for that agent with `tick <= as_of_tick` | No such row buckets as `location:unknown` and never emits `locally_extinct`. Genealogy nodes and `SurvivalAgentRow` have no place |
| Skill | `capability_anchor` on the audit, read-only | Reported as a grounding token. A skill level never creates or deletes a state |
| Record | `evidence_refs` prefix `artifact:{id}` joined to artifact integrity and `location_id` | Intact / damaged / partially lost cited artifacts support the technique. `DESTROYED` does not. Tombstones stay out of Observation, as today. Uncited artifacts do not support a technique. Place comes from the detached artifact row, which Task 6 adds |
| Teaching | origin `teaching` or `imitation`, hop index, mentorship bonds when that channel is on | A chain is intact when a living holder has one of those origins or a living mentor bond covers the technique |
| Recipe / tool / material | Anchor `recipe_id` → `ProductionRecipe`, read against detached node and item rows | `ResourceHoldingRow` is not a node quantity. `ResourceNameInput` is absent in a scope when every matching node row there has `quantity == 0` or no node row exists. `HeldItemNameInput` / `HeldItemKindInput` are absent when no matching item row exists in scope. `tool_role` is absent when no item row carries that `ToolMark`. Items on dead bodies still count as present. Nodes at 0 are not deleted |
| Experiment provenance | existing `evt:` evidence refs | Optional citation on the diffusion row. Does not mint a state and does not call the learn gate |

`performable=true` when every input and tool on each declared anchor recipe is present in scope. No anchor ⇒ `performable` is omitted (`not_applicable`), not `false`.

### State machine (locked)

Evaluate global scope and each resolved location independently. First matching row wins:

1. **`rediscovered`** — extant now, and a new `independent_discovery` root (new `lineage_root_id`, hop 0) appeared after `globally_lost` (global scope) or after `locally_extinct` (that location), and `as_of_tick` is within `rediscovery_latch_ticks` of that root's tick. `reconstruction` after global loss is also `rediscovered` (memory, not a living teacher). `written_record` cannot rediscover a global loss, because global loss already means no intact cited record.
2. **`globally_lost`** — global scope only: zero living holders and zero intact cited records.
3. **`locally_extinct`** — location scope only: that location was extant at an earlier tick and is not extant now, and the global scope is not `globally_lost`.
4. **`diffusing`** — extant, and inside `diffusion_window_ticks` the living-holder count increased, the distinct-location count increased, or a new `teaching` / `imitation` entry appeared.
5. **`rare`** — extant, and either (`known_by_n <= rare_max` and a prior tick had `known_by_n > rare_max`) or (`known_by_n` is 0, an intact cited record remains, and some earlier tick had a living holder).
6. **`discovered`** — extant, no prior loss episode, and either (peak `known_by_n` is 1 and distinct locations never exceeded 1) or (`known_by_n` is 0, an intact cited record remains, and no tick ever had a living holder).
7. **`known`** — extant, `known_by_n >= 1`, and no earlier row matched. `known_by_n=0` is never `known`.

Extant means at least one living holder or one intact cited record in that scope.

After `rediscovery_latch_ticks`, drop the `rediscovered` row and evaluate this list again. A prior loss episode blocks `discovered`.

Loss-cause flags attach on the transition into `rare`, `locally_extinct`, or `globally_lost`, and `materials_absent` also attaches whenever `performable=false`. `teaching_chain_failed` attaches only when a `teaching` or `imitation` entry, or a mentorship bond, existed on an earlier tick and no living holder continues it. A lone independent root leaves the cause unset. Causes do not change command legality.

Dual independent emergence while the technique never left the living population stays on `knowledge_genealogy_lineage@1`. Do not also mark `rediscovered`.

### Analysis (locked)

Sibling families (catalog 68 → **71**):

| Family | Reads |
| --- | --- |
| `technique_lifecycle_state@1` | Counts by the seven states; histogram of `known_by_n`; `performable_false_count` |
| `technique_lifecycle_loss@1` | Episode counts by `holders_died`, `records_destroyed`, `materials_absent`, `teaching_chain_failed`; share of globally lost techniques |
| `technique_lifecycle_diffusion@1` | Mean location spread, mean hop of living holders, rediscovery count, share of rediscoveries that opened a new lineage root |

DTOs are counts and ids only. No ledger payloads, no mark text, no cognition feedback.

Researcher query (analysis-only): `technique_lineage_diffusion(content_key, as_of_tick)` → state, `known_by_n`, location counts, loss-cause set, `performable`, prior and new `lineage_root_id` when rediscovered, else empty. Never imported by cognition, `api`, `simulation`, or `persistence`.

Families assemble only when `TechniqueLifecycleSpec` was present. Channel off ⇒ empty harvest, not zeros that look like a measured extinction.

Detached inputs added in Task 6, then read by Task 7:

- Artifact rows gain `location_id` in `artifact_objective_rows_from_artifacts`.
- `MetricComputationInputs` gains node rows (`name`, `location_id`, `quantity`) and item rows (`item_kind`, `name`, `tool_role`, `location_id`, `holder_id`).
- Holder place stays the latest `AppliedActionRow.location_id`. `ResourceHoldingRow` stays unused for this classifier.

### Experiment AR (locked)

Off the V1 gate. Profile id `technique_lifecycle@1`. Arms:

| Arm | Schema | Channel | Proves |
| --- | --- | --- | --- |
| `ar-channel-off` | v36 | absent | Hash matches pre-plan AQ fixture |
| `ar-discovered-known` | v37 | on + genealogy | One living holder ⇒ `discovered` and `known_by_n=1`. A second living holder acquired inside `diffusion_window_ticks` ⇒ `diffusing` and `known_by_n=2`. The same roster read again after the window, with no further growth, ⇒ `known` and `known_by_n=2` |
| `ar-diffusing` | v37 | on + teaching or imitation uptake | New teaching entry inside the window ⇒ `diffusing` |
| `ar-holders-died` | v37 | on + population mortality | Last living holder's death ⇒ `globally_lost` with `holders_died`; audits remain |
| `ar-records-destroyed` | v37 | on + durable records | Last intact cited artifact destroyed ⇒ record support gone; with no living holder ⇒ `globally_lost` and `records_destroyed` |
| `ar-materials` | v37 | on + production catalog + one anchor | All matching nodes at quantity 0 ⇒ `performable=false` and `materials_absent`; living holder keeps the row out of `globally_lost` |
| `ar-teaching-failed` | v37 | on + mentorship or teaching | Teacher dies, apprentice never holds the entry, no record ⇒ `teaching_chain_failed` |
| `ar-rediscovered` | v37 | on + independent discovery | After `globally_lost`, a new hop-0 root ⇒ `rediscovered` and a new `lineage_root_id`; old root is not merged |
| `ar-not-a-tree` | v37 | on | Anchor or document that names `requires_technique` / `technology_tree` is rejected; no command set changes |
| `ar-flags-off` | v4 | absent | V3 flags off; hash stable |

Matrix allowlist includes AR without enabling it on default batches.

### Architecture isolation (locked)

- `agents.cognition` and `world` must not import `analysis.technique_lifecycle`.
- `llm` must not import world, simulation, cognition, or analysis.
- Analysis harvests detached audits, death ticks, artifact integrity, and catalog rows. It must not import cognition live ledgers or private world modules.
- `api`, `simulation`, and `persistence` must not import `analysis` to compute these families.
- Forbidden alias strings rejected at decode.

### Docs (locked — mandatory)

Update:

- `docs/architecture.md` — seam row + Downstream V3 contract (v37, no write-pair bump, no new flag, analysis-only lifecycle)
- `docs/cognition-runtime.md` — lifecycle is not a cognition input; practical knowledge and teaching are unchanged
- `docs/analysis-metrics.md` — three families + `technique_lineage_diffusion` + the seven states and four loss causes
- `docs/physical-simulation.md` — one paragraph: resource depletion and tombstones are unchanged; lifecycle does not add tech gates
- `.ai-factory/DESCRIPTION.md` — V3 scaffolding blurb for v37
- `.ai-factory/ARCHITECTURE.md` — no command/semantic count change; owned-flag note
- `.ai-factory/ROADMAP.md` — M7 plans list + v3-15 sentence under `cultural_historical_memory`

## Commit Plan

- **Commit 1** (after tasks 1–2): `feat(v3): add technique_lifecycle runner-config-v37 gates`
- **Commit 2** (after tasks 3–5): `feat(analysis): classify technique lifecycle from holders records and materials`
- **Commit 3** (after tasks 6–8): `feat(analysis): technique lifecycle diffusion metrics`
- **Commit 4** (after tasks 9–10): `feat(experiments): add technique lifecycle Experiment AR`

## Tasks

### Phase 1: Schema

- [x] Task 1: Add `RUNNER_SCHEMA_VERSION_V37`, `TechniqueLifecycleSpec`, nested `TechniqueMaterialAnchor` validation, `SimulationRunnerConfig.technique_lifecycle`, exact encode/decode, forbidden-alias frozenset, and the reject codes in the flag×object matrix. Add v37 to `_HISTORICAL_MEMORY_CULTURAL_SCHEMAS`, `_DURABLE_RECORDS_SCHEMAS`, `_HISTORICAL_MEMORY_LAYER_SCHEMAS`, `_KNOWLEDGE_REPOSITORIES_SCHEMAS`, and `_KNOWLEDGE_GENEALOGY_SCHEMAS`. Change the `bounded_experimentation` check from `schema_version == runner-config-v36` to a set that includes v37. Extend the cultural-only error string through v37. Cultural-only still forbids `population_lifecycle` and allows `technique_lifecycle`. Decode checks anchor key shape only. `SimulationRunnerConfig` post-init rejects an unknown `recipe_id` against every `agent.cognition.production_catalog` after `production_catalog_mismatch`, with `technique_anchor_unknown_recipe`. Decode v23–v36 synthesizes `technique_lifecycle=None`. Do not edit matrix finalize priority (Task 9). Do not add a replay or codec version.
  - Deliverable: Round-trip tests; reject rows for missing provenance, missing genealogy, v37 without the object, `mode=disabled`, duplicate anchors, unknown `recipe_id`, `requires_technique`, and v36+lifecycle; v36 experimentation-only still loads; v37 plus optional `bounded_experimentation` loads; cultural-only v37 with `technique_lifecycle` and without `population_lifecycle` loads.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `tests/unit/test_technique_lifecycle_spec.py`
  - Logging: DEBUG decode with `present`, `anchor_count`, and the three thresholds only; INFO/raise stable reject codes; never log `content_key` values at INFO
  - Depends on: none

- [x] Task 2: Add analysis-only enums and snapshot DTOs in `src/analysis/technique_lifecycle.py`: `TechniqueLifecycleState` (seven values), `TechniqueLossCause` (four values), `TechniqueLifecycleSnapshot` (`content_key`, scope, state, `known_by_n`, `performable`, cause set, lineage root ids). Export them from `src/analysis/__init__.py`. No world module and no command.
  - Deliverable: Construct snapshots in unit tests; reject unknown state tokens; architecture test that `src/world`, `src/agents`, `src/api`, `src/simulation`, and `src/persistence` do not import `analysis.technique_lifecycle`.
  - Files: `src/analysis/technique_lifecycle.py`, `src/analysis/__init__.py`, `tests/architecture/test_v3_technique_lifecycle_isolation.py`, `tests/unit/test_technique_lifecycle_snapshot.py`
  - Logging: DEBUG `technique_lifecycle_snapshot` with state and `known_by_n` only
  - Depends on: 1

<!-- Commit checkpoint: tasks 1–2 -->

### Phase 2: Classifier

- [x] Task 3: Implement holder, record, and teaching grounding. Input is a detached genealogy graph, death ticks, cited `artifact:{id}` integrity plus `location_id`, optional mentorship audits, and `AppliedActionRow` places. Holder place is the latest row for that agent with `tick <= as_of_tick` and a `location_id`. No such row is `location:unknown` and never yields `locally_extinct`. Output per `content_key` and scope: living holder ids, location ids, intact-record count, teaching-chain intact flag. Destroyed cited artifacts contribute 0. Uncited artifacts are ignored. Do not read live cognition ledgers.
  - Deliverable: Known-answer tests for one living holder, a dead former holder, an intact cited record, a tombstone, a holder with no action row, and a teaching origin versus an independent root.
  - Files: `src/analysis/technique_lifecycle.py`, `tests/unit/test_technique_lifecycle_grounding.py`
  - Logging: DEBUG `technique_grounding` with holder count, intact record count, and `teaching_chain_intact`; no agent rosters at INFO
  - Depends on: 2

- [x] Task 4: Implement material and tool performability from `TechniqueMaterialAnchor` rows, the run `ProductionCatalog`, and detached node and item rows from the Grounding table (unit tests pass those rows directly). Do not read `ResourceHoldingRow`. `ResourceNameInput` matches node `name`; held-item inputs match item `name` or `item_kind`; `tool_role` matches the item row's `tool_role`. Quantity 0 or a missing node is absent. Items on dead bodies remain present. No anchor ⇒ `performable` omitted. This function must not mutate world state and must not add recipe prerequisites.
  - Deliverable: Tests for present materials, depleted nodes, missing tools, dead-holder inventory still counting, and `not_applicable` when the anchor list is empty.
  - Files: `src/analysis/technique_lifecycle.py`, `tests/unit/test_technique_lifecycle_materials.py`
  - Logging: DEBUG `technique_performable` with `content_key` hash prefix, `performable`, and cause `materials_absent` or `not_applicable`
  - Depends on: 3

- [x] Task 5: Implement the priority state machine and rediscovery latch from the design section. `classify_technique_lifecycle` is a pure function of the grounding snapshot plus thresholds. `known` requires `known_by_n >= 1`. Record-only extant (`known_by_n=0` plus an intact cited record) is `rare` when any earlier tick had a living holder, and `discovered` when nobody ever held it and there is no prior loss. `globally_lost` does not require `materials_absent`. `performable=false` with a living holder stays out of `globally_lost`. `teaching_chain_failed` requires a prior `teaching` or `imitation` entry, or a mentorship bond, that no living holder continues. A lone independent root does not set that cause. A second independent root without a prior loss is not `rediscovered`. A new hop-0 root after global loss is `rediscovered` and keeps a distinct `lineage_root_id`. After the latch, evaluate the list again; a prior loss blocks `discovered`.
  - Deliverable: Table tests for all seven states, the record-only `rare` and `discovered` rows, overlapping loss causes, latch expiry that stays out of `discovered` after a loss, a lone independent root without `teaching_chain_failed`, and dual emergence left unmarked.
  - Files: `src/analysis/technique_lifecycle.py`, `tests/unit/test_technique_lifecycle_states.py`
  - Logging: INFO `technique_state` with state, scope kind (`global` or `local`), and `known_by_n`; DEBUG loss-cause set; never log mark text
  - Depends on: 3, 4

<!-- Commit checkpoint: tasks 3–5 -->

### Phase 3: Harvest and metrics

- [x] Task 6: Extend the detached harvest. Copy `location_id` onto durable artifact rows in `artifact_objective_rows_from_artifacts`. Add node rows (`name`, `location_id`, `quantity`) and item rows (`item_kind`, `name`, `tool_role`, `location_id`, `holder_id`) on `MetricComputationInputs`. Fill them from `src/experiments/collectors.py` and `src/experiments/metric_collection.py`. Do not treat `ResourceHoldingRow` as a node quantity. Channel off leaves the new slices absent.
  - Deliverable: Harvest tests for artifact `location_id`, a zero-quantity node, an item on a dead holder, and absent slices when `technique_lifecycle` is omitted.
  - Files: `src/experiments/composition.py`, `src/experiments/collectors.py`, `src/experiments/metric_collection.py`, `src/analysis/metric_service.py`, `tests/unit/test_technique_lifecycle_harvest.py`
  - Logging: DEBUG `technique_lifecycle_harvest` with node count, item count, and artifact rows that carry `location_id`; no names or mark text
  - Depends on: 3, 4

- [x] Task 7: Add `technique_lineage_diffusion` and the three metric families. Pin `METRIC_FAMILY_COUNT` to 71 in `src/analysis/specifications.py` and sweep every unit test that asserts `== 68` for that constant, including `tests/unit/test_metric_specifications.py`, `test_bounded_experiment_metrics.py`, `test_knowledge_genealogy_metrics.py`, `test_v3_knowledge_genealogy_regression.py`, `test_v3_knowledge_repositories_regression.py`, `test_v3_durable_records_regression.py`, `test_mentorship_metrics.py`, `test_historical_memory_metrics.py`, `test_developmental_learning_metrics.py`, `test_dependency_care_metrics.py`, `test_cultural_narrative_metrics.py`, and `test_cultural_feature_metrics.py`. Assemble only when the spec was present, using the Task 6 slices. Empty harvest when the channel is off. No cognition import.
  - Deliverable: Known-answer metric tests; channel-off empty harvest; diffusion query returns root ids only after rediscovery; no remaining `METRIC_FAMILY_COUNT == 68` pin.
  - Files: `src/analysis/technique_lifecycle.py`, `src/analysis/technique_lifecycle_metrics.py`, `src/analysis/specifications.py`, `src/analysis/metric_service.py`, `src/analysis/__init__.py`, `tests/unit/test_technique_lifecycle_metrics.py`, and the pin files named above
  - Logging: DEBUG `technique_lifecycle_metrics_assembled` with family ids and row counts; no snapshot payloads
  - Depends on: 5, 6

- [x] Task 8: Research UI Analytics discovery badges for the three new families only (same pattern as genealogy badges; no new graph panel) in `clients/research-ui/src/epistemic.ts`, `clients/research-ui/src/views/AnalyticsPanel.svelte`, and `clients/research-ui/src/epistemic.test.ts`. Badges stay `research_inference`. Do not render loss narratives or technique tokens as objective facts.
  - Deliverable: Overlay kinds map to `research_inference`; the three family ids appear in the analytics priority set.
  - Files: `clients/research-ui/src/epistemic.ts`, `clients/research-ui/src/views/AnalyticsPanel.svelte`, `clients/research-ui/src/epistemic.test.ts`
  - Logging: none in the UI; do not print ledger contents into badge titles
  - Depends on: 7

<!-- Commit checkpoint: tasks 6–8 -->

### Phase 4: Experiment and docs

- [x] Task 9: Register off-gate Experiment AR (`technique_lifecycle@1`) with the arms in the design section. In `src/experiments/matrix_schema.py`, insert `technique_lifecycle_on` immediately before the `bounded_experimentation_on` branch (v37 beats v36). Add `experiment-ar-technique-lifecycle` to `OFF_GATE_MATRIX_EXPERIMENT_IDS`. AR stays off the V1 gate. Default batches do not enable it. Export the builder from `src/experiments/__init__.py`.
  - Deliverable: Catalog tests for each arm's assertion, including inside-window `diffusing` and after-window `known`; V1 regression gate and `test_v2_scientific_invariants` green with V3 flags off; `ar-channel-off` hash matches the AQ fixture.
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, `src/experiments/matrix_schema.py`, `tests/unit/test_experiment_ar.py`
  - Logging: INFO experiment arm start with arm id and schema version; DEBUG channel active flag
  - Depends on: 5, 7

- [x] Task 10: Docs and pins listed in the Docs section. Confirm Alembic head `0017`, protocol id unchanged, command count 35, semantic count 54, and no new write-pair. Run `ruff check` on the full changed Python set, including new tests and `__init__.py` exports, before this commit.
  - Deliverable: Doc updates; architecture isolation green; ruff clean on the changed set.
  - Files: `docs/architecture.md`, `docs/cognition-runtime.md`, `docs/analysis-metrics.md`, `docs/physical-simulation.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/ROADMAP.md`
  - Logging: none in docs; docs must not describe states as agent-visible facts
  - Depends on: 8, 9

<!-- Commit checkpoint: tasks 9–10 -->
