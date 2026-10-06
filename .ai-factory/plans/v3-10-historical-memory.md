# Implementation Plan: V3-10 Historical Memory Layers

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-06

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Deepens the already-owned `cultural_historical_memory` surface with analysis-only Assmann-style living / communicative / cultural layers so researchers can measure historical distance without injecting those labels into agent knowledge.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-10-historical-memory.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; suggested stem `v3-10-historical-memory`; git.create_branches=false so stem is description slug (branch-derived naming disabled)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; scope is explicitly v3-10 under M7 so linkage uses M7
INFO [aif-improve] refined 2026-10-06: v32 cultural-gate rewrite + encode/decode; analysis-only Task 2 (no cognition bind); exact DTO field tables; flag×object edge rows; AM arm matrix; MetricComputationInputs/harvest; matrix finalize owned by Task 12; deps; mandatory docs/pins; GraphsPanel deferred

## Compatibility contract

This plan **deepens** already-owned **`V3CapabilityFlags.cultural_historical_memory`** (v3-09). It adds **analysis-only** historical memory layer classification (living / communicative / cultural) derived from provenance graphs, death, and generation transitions. These categories are researcher constructs — they must **never** become automatic agent knowledge, Observation fields, WorldEngine laws, or subjective ledger labels.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents receive immutable per-agent `Observation` / `Perspective` only. `WorldEvent` records remain immutable and append-only. Subjective state stays outside the objective fold. Godot remains read-only. Deterministic replay continues. No scripted civilization / memory_layer_emerged outcomes.
2. Flag ownership unchanged: keep `cultural_historical_memory`, `generational_population`, and `kinship_inheritance` owned. Do **not** own `multi_polity_migration`, `institutional_economy`, or `multi_hop_testimony_tracking`. **No new V3 capability flag.**
3. Flags-off / channel-off / layers-object-absent = prior baseline. With all V3 flags off, or with `cultural_historical_memory=False` / `cultural_feature_provenance` absent / `historical_memory_layers` absent, trajectories and `exact_trajectory_hash` match the pre-plan baseline for AE–AL where applicable. V2 Experiment AB (`cultural_narrative_lineage@1`) and V3 Experiment AL metric families stay unchanged (sibling families only).
4. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2/V3 versions in the same change that adds a write version.
5. **Analytical categories ≠ agent knowledge (locked).** Forbidden: writing `living` / `communicative` / `cultural` (or synonyms) into `SubjectiveCulturalBelief`, narrative ledgers, semantic beliefs, Observation, prompts, or SelfModel. Agents must not receive layer labels as facts about "what kind of memory I have."
6. **Provenance graphs determine historical distance** — not hardcoded generation cutoffs alone, not researcher narrative, and not Analysis→cognition feedback.
7. **Deaths and generations drive transitions** — layer membership is tick-as-of and recomputed when witness sets and generation distance change; transitions are analysis events, not world events.
8. Preserve v3-02–v3-09 locks: blank-slate deny-list; closed Observation `lifecycle`; ELDER ≠ leader; related ≠ affection; no parent→caregiver hardwiring; no global Culture; no internal-state copy; Alembic head `0017` by default; kinship cultural inheritance handoff stays deferred. **Do not** add a blank-slate store for layers (analysis-only; `cultural_features` blank-slate already covers subjective cultural ledger).
9. **`api` must not import `analysis`.** Persist query/metric docs offline; serve via existing `MetricReadService` / inspection projections only.
10. Closed `AgentCommand` count stays **26**. No new event-schema write-pair. SEMANTIC count stays **43**.

## Goal

Give researchers analytical support to distinguish, for a source event / knowledge unit and an as-of tick:

| Layer | Meaning (analytical) |
| --- | --- |
| **living** | At least one agent who personally experienced the source event is still alive (direct witness set non-empty among living agents) |
| **communicative** | No living direct witnesses remain, but at least one living agent learned through a provenance chain connected to witnesses (spoke with / was taught by / received testimony from a witness or a short hop from one) |
| **cultural** | Knowledge persists only after direct witness chains have disappeared — carriers know it via stories, artifacts, distant hops, or cultural-feature/narrative persistence with no surviving witness-connected communicative path |

Deliver:

- Exact optional root sibling `historical_memory_layers` on **`runner-config-v32`** (analysis harvest / query config only; never a cognition mode)
- Analysis-only provenance graph + layer classifier + transition tracker
- Closed researcher query report answering: Are any direct witnesses alive? Does anyone remember speaking to a witness? Is the event known only from stories/artifacts?
- Sibling metric families (do not overload `cultural_feature_*`, `cultural_narrative_lineage@1`, or social-transmission families)
- Integration with narrative lineage harvest + Research UI epistemic chrome / Analytics (GraphsPanel provenance chrome deferred)
- Off-gate Experiment AM comparing layers-off vs layers-on across witness death and multi-generation arms

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` remains the only authority over objective physical reality; historical layers are never world rules.
2. Agents never receive historical-layer labels, society encyclopedias, or analysis query documents.
3. `WorldEvent` records remain immutable; authoritative history stays append-only (no `MemoryLayerTransitioned` world event).
4. Subjective cultural beliefs / narrative variants remain fallible owner-scoped state; layer classification is researcher-only.
5. Analytical layer assignments must not bias live cognition, intention, or memory formation.
6. LLM output remains non-authoritative.
7. No scripted `living_memory_must_persist` / `cultural_memory_emerged` booleans.
8. Godot remains read-only; this plan does **not** require Godot layer chrome (Research UI Analytics first; GraphsPanel / observer overlay deferred).
9. Runs remain reproducible where claimed (explicit seeds, deterministic streams, deterministic fakes / recorded LLM paths).

### Capability / ownership (locked)

1. **No new V3 flag.** Enabling layers requires already-owned `cultural_historical_memory=True` plus exact `cultural_feature_provenance` **and** exact `historical_memory_layers` on `runner-config-v32`.
2. When `generational_population` is also on, generation_index and Died events participate in distance / transition scoring. Cultural-only (lifecycle off) remains legal: living/communicative/cultural still derived from witness death when deaths occur by other causes, but generation-distance features degrade with stable DEBUG `historical_memory_generation_unavailable`.
3. Do **not** implement kinship cultural inheritance handoff.
4. Other unowned V3 flags still fail closed.
5. When layers object absent: AE–AL bit-identity matches pre-plan for the same roster and seeds (no new analysis layer rows required for trajectory hash).
6. Do **not** claim that enabling layers auto-enables narrative / artifact / teaching modes; compose joins available harvested rows and skips missing sources with DEBUG.
7. **No cognition bind.** Layers must **not** add `_historical_memory_loop_kwargs`, `AgentCognitionSpec` fields, CulturalFeatureLedger writes, or SubjectiveSnapshot fields. Spec is validated on config and consumed only by post-run analysis / experiment collectors.

### Flag × object gate matrix (locked)

| Config shape | Allowed? | Reject / notes |
| --- | --- | --- |
| Cultural flag off, both objects absent | Yes (off) | Passthrough |
| Layers object present, cultural flag off | No | `historical_memory_without_cultural_flag` |
| Layers object present, `cultural_feature_provenance` absent (any schema) | No | `historical_memory_requires_cultural_provenance` |
| Cultural flag on + provenance on **v31**, layers absent | Yes | Pre-plan AL behavior; no layer metrics |
| Cultural flag on + provenance + layers on **v31** | No | `historical_memory_requires_v32` |
| Cultural flag on + provenance + layers on **v32** | Yes | Analysis-only layer compute enabled |
| Layers object on schema ≠ v32 | No | `historical_memory_requires_v32` |
| Schema `v32` without layers object | No | `v32_requires_historical_memory_layers` |
| Schema `v32` + layers + provenance absent | No | `historical_memory_requires_cultural_provenance` (and/or existing `cultural_feature_requires_flag` if flag on without provenance) |
| Cultural flag on + provenance absent + layers absent | No | Existing `cultural_feature_requires_flag` |
| Layers `mode=disabled` present | No | `historical_memory_mode_invalid` — omit object for off |
| **Cultural-only on v32** (flag on; lifecycle off) + layers | Yes | Widen `_cultural_only` beyond exact-v31; forbid lifecycle siblings with existing `cultural_only_forbids_*` |
| Generational + cultural + layers on v32 | Yes | Full death + generation transition tracking |
| Kinship-only + cultural + layers on v32 | Yes | Kinship-only forbids lifecycle siblings; allow cultural + layers |
| Mentorship / developmental without lifecycle | No | Unchanged existing rejects |

**Live-code rewrite required:** today `cultural_feature_provenance` requires `schema_version == v31` (`cultural_feature_requires_v31`) and `_cultural_only` is hardcoded to exact v31. This plan **must** widen provenance acceptance to `{v31, v32}` while keeping AL on v31 (layers absent). Prefer keeping reject code id `cultural_feature_requires_v31` with updated message covering `{v31,v32}`, or introduce `cultural_feature_requires_v31_or_v32` and update all call sites — pick one in Task 1 and pin it.

### Scope split (locked)

| This plan (v3-10) | Deferred |
| --- | --- |
| Analysis-only living / communicative / cultural layers | Writing layer labels into agent knowledge / prompts |
| Provenance-graph historical distance + death/generation transitions | Owning `multi_hop_testimony_tracking` |
| Researcher query report + Research UI Analytics / epistemic overlays | Full Godot historical-memory atlas; GraphsPanel provenance chrome |
| Compose narrative lineage + cultural-feature audits + social edges + Died | Kinship cultural inheritance / estate knowledge handoff |
| Experiment AM (off V1 gate) | Natural-language free-form historiography authority |
| Alembic head stays `0017` | New event-schema write-pair / `/v2` HTTP |
| `generation_distance_weight` as ignored-or-DEBUG soft knob (default `0.0`) | Soft metric bands driven by generation weight |
| `transition_tick_resolution=every_tick` for unit tests | Experiment AM arm that requires every_tick |

### Analytical layer taxonomy (locked)

Package: `analysis/historical_memory.py` (and metrics sibling). **Forbidden** in `agents/`, `world/`, cognition prompts.

Closed ids (`HistoricalMemoryLayerId` StrEnum):

| Id | Predicate sketch (exact algorithm in classifier section) |
| --- | --- |
| `living` | `\|living ∩ direct_witnesses(source)\| ≥ 1` at as-of tick |
| `communicative` | not living, and ∃ living carrier whose provenance path to a direct witness has length ∈ `[1, max_communicative_hops]` and path does not rely solely on artifact/story-only edges after last witness death |
| `cultural` | not living and not communicative; knowledge still attested via cultural-feature carriers, narrative variants, artifacts, or hops beyond `max_communicative_hops` / post-chain-break persistence |

**Unified forbidden aliases** (runner decode + architecture tests — reject with stable codes):

- Layer inject: `inject_into_agents`, `label_agent_memories`, `assmann_cognition_mode`, `auto_layer_beliefs`, `assmann_label_for_agent`
- Pseudo agent classes: `agent_memory_class`, `self_knowledge_layer`, `lived_experience_flag`, `living_memory`, `communicative_memory`, `cultural_memory`, `society_memory_tier`, `assmann_*`
- Authority hardcodes: no ELDER→memory-authority; no kinship→layer handoff; no Observation / SelfModel / MemoryTrace / NarrativeVariant / SubjectiveCulturalBelief layer field

**Critical:** These ids appear only in analysis DTOs, metric payloads, and Research UI `research_inference` chrome — never in subjective projections served as agent beliefs.

### Runner configuration versioning (locked)

Introduce `RUNNER_SCHEMA_VERSION_V32 = "runner-config-v32"`:

- Exact root key set = **v31 accepted roots** ∪ sibling root object **`historical_memory_layers`**.
- Default write remains `runner-config-v4` when all V3 flags are off and no existing mode requires a higher schema.
- `historical_memory_layers` present ⇒ `schema_version == runner-config-v32` and `cultural_historical_memory=True` with exact `cultural_feature_provenance` + exact layers object.
- Decode of v23–v31 synthesizes no `historical_memory_layers` object (absent ≡ analysis layers off).
- Widen **every** mode allowlist currently capped at `v31` to also accept `v32`.
- Gate rewrite: `cultural_historical_memory=True` accepts `{v31, v32}` (v31 = provenance only; v32 = provenance + layers). Rewrite live exact-`v31` provenance gate and `_cultural_only` for `{v31,v32}`. `generational_population=True` / `kinship_inheritance=True` allowlists widen to include `v32`.
- **Matrix finalize ownership (Task 12 only):** accept `v32`; priority if-elif inserts `historical_memory_on` **before** `cultural_feature_on`; widen `needs_lifecycle` / `needs_init` with `V32`; AM uses v32; AL stays v31; default finalize stays `v4` when V3 flags off. Task 1 must **not** edit finalize priority (models/serialization/gates only).
- Update `simulation/compatibility.py` version matrix row for v32 (**no new event-schema write-pair**; mirror v31 cultural text).

### Serialization contract (locked)

Mirror v31 cultural_feature pattern in `runner_serialization.py`:

- Many `_RUNNER_ROOT_KEYS_V32_*` = corresponding v31 frozenset ∪ `"historical_memory_layers"`
- Exact child keyset `_HISTORICAL_MEMORY_LAYERS_KEYS` matching the spec table below
- `_encode_historical_memory_layers` / `_decode_historical_memory_layers` with `_require_keys` (no silent extras)
- Encode: `schema_version == V32` requires both provenance + layers present
- Decode: v23–v31 → `historical_memory_layers=None`
- DEBUG log present/absent on decode (metadata only)

### HistoricalMemoryLayersSpec (exact root sibling — locked)

Root key `historical_memory_layers` exact children:

| Key | Role | Validation |
| --- | --- | --- |
| `mode` | Closed id: must be `deterministic` when object present — **not** an `AgentCognitionSpec` enum; analysis harvest/config only | `disabled` → `historical_memory_mode_invalid` |
| `max_communicative_hops` | Int in `[1, 8]` — default `2` | out of range → `historical_memory_max_hops_invalid` |
| `witness_definition` | `occurrence_participants` (default) \| `occurrence_participants_plus_colocated_observers` | else → `historical_memory_witness_definition_invalid` |
| `include_narrative_lineage` | Bool — default `true` | must be bool |
| `include_cultural_features` | Bool — default `true` | must be bool |
| `include_artifact_edges` | Bool — default `true` | must be bool |
| `include_teaching_edges` | Bool — default `true` | must be bool |
| `generation_distance_weight` | Float in `[0, 1]` — default `0.0`; optional soft score only (never sole classifier); ignored with DEBUG when lifecycle off | out of range → `historical_memory_generation_weight_invalid` |
| `query_event_selector` | `all_tracked_sources` (default) \| `experiment_marked_only` | else → `historical_memory_query_selector_invalid` |
| `transition_tick_resolution` | `on_death_and_generation_boundary` (default) \| `every_tick` (unit tests / small runs) | else → `historical_memory_transition_resolution_invalid` |
| `applicability` | `all_tracked_sources` (default) | else → `historical_memory_applicability_invalid` |

Provide `example_historical_memory_layers_spec()` and `SimulationRunnerConfig.historical_memory_layers: HistoricalMemoryLayersSpec | None` in `runner_models.py`.

### Provenance graph model — exact fields (locked)

Analysis-only types in `analysis/historical_memory.py` (duck-type harvest; no cognition imports):

**`HistoricalSourceRef`**

| Field | Role |
| --- | --- |
| `source_event_id` | Opaque EventId token (required) |
| `content_key` | Optional opaque join key |
| `transmission_root_id` | Optional narrative root token |
| `cultural_digest_token` | Optional cultural-feature digest token |

**`HistoricalProvenanceNode`**

| Field | Role |
| --- | --- |
| `node_id` | Stable opaque id |
| `kind` | `source_event` \| `agent` \| `artifact_mark` \| `narrative_variant` \| `cultural_belief_audit` |
| `ref_token` | Opaque id for the underlying entity |
| `generation_index` | Optional int when lifecycle map present |

**`HistoricalProvenanceEdge`**

| Field | Role |
| --- | --- |
| `edge_id` | Stable opaque id |
| `from_node_id` / `to_node_id` | Endpoints |
| `edge_kind` | Closed set below |
| `at_tick` | Tick when edge became valid (if known) |
| `hop_metadata` | Optional int (e.g. cultural `hop_index`) |

| Edge kind | Meaning |
| --- | --- |
| `experienced` | Agent was a direct witness of source (per `witness_definition`) |
| `communicated` | Talk/Ask/Tell (or declared transmission parent) between agents |
| `taught` | Teaching / mentorship-taught-content public act (metadata only) |
| `narrative_transmitted` | Narrative lineage parent/carrier edge from harvested rows |
| `cultural_feature_hop` | Cultural-feature parent hop from audits (`hop_index` metadata) |
| `artifact_mediated` | Artifact mark / interpretation cue linking carrier to source tokens |
| `generation_successor` | Optional lifecycle generation_index adjacency (soft; not sufficient alone for communicative) |

**`HistoricalProvenanceGraph`**

| Field | Role |
| --- | --- |
| `as_of_tick` | Classification tick |
| `nodes` / `edges` | Frozen tuples |
| `build_reason_codes` | Ordered frozen reason tokens |
| `witness_count` / `living_witness_count` | Metadata counts |

Build inputs (duck-typed):

1. Objective committed events: source occurrences + `Died` (+ lifecycle entry ticks / `generation_index` when present). Reuse existing analysis patterns: `MetricComputationInputs.death_ticks`, `living_agent_ticks` death-exclusive semantics — **do not assume a shared Died×generation helper exists**; build maps ad hoc in harvest.
2. Communication / teaching public edges (social-transmission style)
3. Optional narrative lineage rows (`include_narrative_lineage`)
4. Optional cultural-feature audits (`include_cultural_features`) — duck-type `__name__ == "CulturalFeatureAudit"` / getattr fields like v3-09 traits
5. Optional artifact evidence (`include_artifact_edges`)

Logging: DEBUG graph build counts (nodes, edges, witness_count, living_witness_count); never utterance text / fingerprints as payloads.

### Classifier — exact assignment fields (locked)

Function: `classify_historical_memory_layer(graph, source, as_of_tick, spec) -> HistoricalMemoryLayerAssignment | None`

**`HistoricalMemoryLayerAssignment`**

| Field | Role |
| --- | --- |
| `source_ref` | `HistoricalSourceRef` |
| `as_of_tick` | int |
| `layer` | `HistoricalMemoryLayerId` |
| `living_witness_ids` | Frozen opaque agent id tokens |
| `communicative_carrier_ids` | Frozen opaque agent id tokens |
| `cultural_carrier_ids` | Frozen opaque agent id tokens |
| `witness_chain_broken` | bool |
| `reason_code` | Closed: `historical_memory_living` \| `historical_memory_communicative` \| `historical_memory_cultural` \| `historical_memory_unattested` |
| `max_path_hops_to_witness` | Optional non-neg int |

Order of evaluation (fail closed to `cultural` only when knowledge still attested; else `None` / unattested):

1. Compute `direct_witnesses(source)` from `experienced` edges.
2. Compute `living(as_of)` from Died ticks / living roster (death tick exclusive — post-death not living).
3. If `living ∩ direct_witnesses` non-empty → **`living`**.
4. Else BFS/DFS from living agents along allowed communicative edge kinds (`communicated`, `taught`, and narrative/cultural hops only when they retain a path that intersects a direct witness without requiring solely `artifact_mediated` after the last witness death) with length ≤ `max_communicative_hops` → if any path → **`communicative`**.
5. Else if any attestation remains via narrative carriers, cultural-feature audits, artifacts, or hops > cap → **`cultural`**.
6. Else → no layer assignment (`reason_code=historical_memory_unattested`); do not invent cultural persistence.

`generation_distance_weight > 0` may only adjust optional soft scores — **must not** override steps 3–5. Soft bands are deferred (default weight `0.0`).

### Transition tracking — exact fields (locked)

**`HistoricalMemoryTransition`**

| Field | Role |
| --- | --- |
| `source_ref` | `HistoricalSourceRef` |
| `from_layer` / `to_layer` | `HistoricalMemoryLayerId` (or `unattested` sentinel only for `new_attestation` entry) |
| `at_tick` | int |
| `cause` | Closed set below |

| Cause | When |
| --- | --- |
| `last_direct_witness_died` | Last living direct witness dies → typically living→communicative (if paths remain) or living→cultural |
| `witness_chain_expired` | Last communicative path to any witness breaks → communicative→cultural |
| `generation_boundary` | Optional: generation_index cohort change with no living witnesses and no communicative paths — reinforce cultural; never alone create living |
| `new_attestation` | Rare: new artifact/narrative attestation appears after unattested — may enter cultural only |
| `reclassification` | Spec-driven recompute without death (tests) |

Emit transitions under `transition_tick_resolution`. Prefer death/boundary sampling for long runs. Transitions are **not** `WorldEvent`s and do not affect replay identity.

### Researcher queries — exact answer DTOs (locked)

**`HistoricalMemoryQueryAnswer`**

| Field | Role |
| --- | --- |
| `query_id` | Closed id below |
| `source_ref` | `HistoricalSourceRef` |
| `as_of_tick` | int |
| `answer` | bool |
| `layer` | Optional `HistoricalMemoryLayerId` |
| `witness_ids` / `carrier_ids` | Frozen opaque tokens (empty when N/A) |
| `path_hop_bands` | Optional frozen hop band tokens |
| `reason_code` | Stable code |

| Query id | Question | True when |
| --- | --- | --- |
| `any_direct_witnesses_alive` | Are any direct witnesses alive? | living witnesses non-empty |
| `anyone_remembers_speaking_to_witness` | Does anyone remember speaking to a witness? | communicative paths exist **or** living agents have `communicated`/`taught` edges to a (living or dead) direct witness within hop cap |
| `event_known_only_from_stories_or_artifacts` | Is the event known only from stories/artifacts? | layer=`cultural` and attestation uses only narrative/artifact/cultural-feature edges (no living/communicative witness path) |

**`HistoricalMemoryQueryReport`:** frozen tuple of answers + `as_of_tick` + `source_count` + summary true-counts by query id.

Batch API: `answer_historical_memory_queries(graph, sources, as_of_tick, spec) -> HistoricalMemoryQueryReport`.

Censoring: metadata-only; `layer=research_analytics`; never cognition.

### Analysis metrics (locked)

| Family id | Version string | Signal |
| --- | --- | --- |
| `historical_memory_layers` | `historical_memory_layers@1` | Per-source / cohort layer histogram; living_witness counts; communicative vs cultural carrier shares |
| `historical_memory_transitions` | `historical_memory_transitions@1` | Transition counts by cause; living→communicative / communicative→cultural rates; death-linked share |
| `historical_memory_queries` | `historical_memory_queries@1` | Aggregated answers for the three locked queries across tracked sources at selected as-of ticks |

Registration recipe (Task 8):

1. Add three `MetricFamilyId` members
2. Add `_spec_historical_memory_*` with `version_identifier` `@1`, `value_keys`, `formulas`, `empty_case`, `censoring_policy="analysis-only …; never cognition"`, `deceased_policy` documented
3. Append to `_BUILDERS`
4. Bump `METRIC_FAMILY_COUNT` 53 → **56**
5. Extend `MetricComputationInputs` with historical-memory harvest field(s) (assignments / transitions / query report and/or raw duck-typed source bundle)
6. `assemble_metric_documents` / `_safe` compute when inputs present else ABSENT
7. Export from `analysis/__init__.py`
8. Update `test_metric_specifications.py` and any A–E opt-in exclusion / e2e reference sets that pin 53

Do **not** overload `cultural_feature_provenance@1`, `cultural_trait_diffusion@1`, `cultural_feature_mutation@1`, `cultural_narrative_lineage@1`, `knowledge_diffusion@1`, or `rumor_distortion@1`.

### Harvest / collector boundary (locked)

Today `inputs_with_opt_in_metric_rows` / `collectors.collect_run_metrics` do **not** auto-attach cultural audits. Task 9 must:

- Build duck-typed harvest from `SimulationRunnerResult.cultural_feature_audits` (when present), Died/`death_ticks`, optional narrative rows, communication/teaching edges, artifact marks, optional `generation_index_by_owner`
- Attach onto `MetricComputationInputs` (new field(s)) via `experiments.composition` / collectors / AM-only path
- Never import `SubjectiveCulturalBelief` / narrative ledger classes into analysis (duck-type audits only)
- Never import `analysis` from `api`

### Narrative lineage integration (locked)

When `include_narrative_lineage=true` and narrative harvest rows exist:

- Map `transmission_root_id` / `parent_variant_ids` / `carrier_agent_ids` / `source_event_id` into provenance nodes/edges (`narrative_transmitted`).
- Narrative hops never invent speaker order from metric aggregates (same rule as Godot SUBJECTIVE hops).
- Layer classification may use narrative edges for communicative/cultural paths but must still require witness connectivity rules above.
- Subjective `project_cultural_narratives` / ledger projections stay unchanged — **no layer field added**.

### Research UI / API integration (locked)

Boundary: `api` must not import `analysis`.

1. Experiments / collectors compute layer metrics + query reports → `persist_metric_bundle` (existing ports).
2. API continues to serve persisted docs via `GET .../metrics` and `GET .../metrics/{set}/{family}`.
3. Research UI (`clients/research-ui/`):
   - Extend `epistemic.ts` `ANALYTICAL_OVERLAYS` with `historical_memory_layers`, `historical_memory_transitions`, `historical_memory_queries` (do not assume cultural_feature_* overlays already exist — v3-09 deferred UI).
   - AnalyticsPanel: discover new families from metric catalog; show layer histogram + query answers with `research_inference` badge. Optionally add to `PRIORITY_FAMILIES` if that list is the product discovery surface.
   - **GraphsPanel provenance chrome: deferred** (out of scope for this plan).
4. Do **not** add layer labels to subjective projection endpoints (`cultural-narratives`, memories/beliefs summaries).
5. Prefer metrics-only surface; no `subjective_debug` layer projection that could imply agent knowledge.

### Experiment AM — arm matrix (locked)

- Catalog: `experiment_am_historical_memory_layers` / id `experiment-am-historical-memory-layers` on **runner-config-v32**, off the V1 gate.
- Profile: `historical_memory_layers_profile` requiring schema==v32 + `cultural_historical_memory=True` + exact `cultural_feature_provenance` + exact `historical_memory_layers`; reject unowned V3 flags.

| Arm | Schema | Layers object | Lifecycle | Extra | Expected |
| --- | --- | --- | --- | --- | --- |
| `am-layers-off` | v31 | absent | off | cultural provenance on | No layer families required; baseline vs AL-like |
| `am-living` | v32 | on | optional | witnesses alive; `include_teaching_edges` as needed | `any_direct_witnesses_alive=true`; layer=`living` |
| `am-witness-death` | v32 | on | on preferred | kill last direct witness mid-run | Transition living→communicative (or cultural); query answers flip |
| `am-communicative` | v32 | on | optional | no living witnesses; ≤`max_communicative_hops` speaker path | layer=`communicative`; `anyone_remembers_speaking_to_witness=true` |
| `am-cultural-only` | v32 | on | on (multi-gen) | chain break / stories+artifacts only | layer=`cultural`; `event_known_only_from_stories_or_artifacts=true` |
| `am-narrative-join` | v32 | on | optional | `include_narrative_lineage=true` + narrative mode on | Narrative edges contribute; still analysis-only; no subjective layer fields |
| `am-flags-off` | v4 | absent | off | all V3 off | Hash stability vs pre-plan |

- Prove: flags-off / layers-off hashes stable; V1 gate + `test_v2_scientific_invariants` green under V3 flags-off; architecture isolation green; SEMANTIC **43**; command count **26**.
- Matrix allowlist includes AM without enabling on default batches.

### Architecture isolation (locked)

Mirror v3-09 dual-representation / isolation tests:

- `agents` / `agents.cognition` must not import `analysis.historical_memory` or layer enums.
- `analysis.historical_memory` / metrics must not import `SubjectiveCulturalBelief` / narrative ledger classes (duck-type harvest rows).
- `api` / `simulation` cognition paths must not import `analysis`.
- No `HistoricalMemoryLayer` field on Observation, MemoryTrace, SubjectiveCulturalBelief, NarrativeVariant, WorldState, or SelfModel.
- Forbidden string aliases rejected in runner decode.
- World tree: no society-memory / Assmann controller classes.

### Docs (locked — mandatory)

Update (no “optional” hedges):

- `docs/architecture.md` — V3 seams row + Downstream V3 contract (v32 deepens cultural; cultural flag accepts `{v31,v32}`; no new flag; no event write-pair)
- `docs/analysis-metrics.md` — three new families + query report
- `docs/cognition-runtime.md` — explicit note: historical layers are analysis-only; not agent knowledge
- `.ai-factory/DESCRIPTION.md` — V3 scaffolding blurb for v32 layers
- `.ai-factory/ARCHITECTURE.md` — allowlists / owned-flag notes for v32
- Research UI contributor note for epistemic overlays if a docs page exists

## Commit Plan

- **Commit 1** (after tasks 1–2): `feat(v3): add historical_memory_layers runner-config-v32 gates`
- **Commit 2** (after tasks 3–6): `feat(analysis): provenance graph and historical memory layer classifier`
- **Commit 3** (after tasks 7–9): `feat(analysis): historical memory queries, metrics, and harvest`
- **Commit 4** (after tasks 10–12): `feat(experiments): Experiment AM historical memory layers`
- **Commit 5** (after task 13): `feat(research-ui): surface historical memory layer metrics`
- **Commit 6** (after tasks 14–16): `docs(v3): historical memory layers analysis seams` + verification pins

## Tasks

### Phase 1: Schema, serialization, and gates

- [x] Task 1: Add `RUNNER_SCHEMA_VERSION_V32`, `HistoricalMemoryLayersSpec`, `SimulationRunnerConfig.historical_memory_layers`, `example_historical_memory_layers_spec()`, exact encode/decode + `_HISTORICAL_MEMORY_LAYERS_KEYS` / v32 root frozensets, and full reject-code set. **Rewrite** live exact-`v31` cultural provenance gate and `_cultural_only` to accept `{v31,v32}`. Widen every mode/lifecycle/kinship allowlist capped at v31 to include v32. Update `compatibility.py` v32 row (no event write-pair). **Do not** edit matrix finalize priority here (Task 12 owns that).
  - Deliverable: Config round-trip tests for present/absent layers; reject rows from flag×object matrix including layers-on-v31 and cultural-only-on-v32; decode v23–v31 synthesizes layers=None; forbidden aliases rejected.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `tests/unit/test_historical_memory_layers_spec.py`, `tests/unit/test_runner_config_v32*.py`
  - Logging: DEBUG decode present/absent; INFO/raise stable reject codes on fail-closed; never log free-form alias dumps as payloads
  - Depends on: none

- [x] Task 2: Config enable/skip + negative cognition proofs (analysis-only). Validate layers in `__post_init__` only; runner/from_config logs enable/skip; **prove** no `_cultural_features_loop_kwargs`-style bind, no AgentCognitionSpec field, no CulturalFeatureLedger writes from layers alone, no SubjectiveSnapshot/blank-slate store for layers. Passthrough when object absent.
  - Deliverable: Unit tests assert cognition wiring unchanged for AL/v31 and that v32 layers do not touch subjective commit paths.
  - Files: `src/simulation/runner.py` (log-only if needed), `src/simulation/runner_models.py` (gates), `tests/unit/test_historical_memory_from_config.py`
  - Logging: INFO `historical_memory_layers_enabled` with max_communicative_hops + witness_definition; DEBUG skip when absent
  - Depends on: 1

<!-- Commit checkpoint: tasks 1-2 -->

### Phase 2: Provenance graph, classifier, transitions, isolation

- [x] Task 3: Implement analysis-only provenance graph builder (`HistoricalProvenanceGraph`) with exact node/edge field tables; join Died, witness edges, communication/teaching, optional narrative/cultural/artifact rows per spec flags. Duck-type harvest inputs; no cognition imports. Build death_ticks / generation maps ad hoc (no assumed shared helper).
  - Files: `src/analysis/historical_memory.py`, `tests/unit/test_historical_memory_provenance_graph.py`
  - Logging: DEBUG `historical_memory_graph_built` nodes/edges/witness_count/living_witness_count/as_of_tick; WARN on malformed duck-typed rows skipped
  - Depends on: 1

- [x] Task 4: Implement locked layer classifier (`living` / `communicative` / `cultural` / unattested) with exact `HistoricalMemoryLayerAssignment` fields, hop cap, and witness-definition modes. Property/unit tests for each decision-table arm.
  - Files: `src/analysis/historical_memory.py`, `tests/unit/test_historical_memory_classifier.py`
  - Logging: DEBUG `historical_memory_classified` source_token + layer + reason_code + living_witness_count + max_path_hops; never content payloads
  - Depends on: 3

- [x] Task 5: Implement transition tracker with exact `HistoricalMemoryTransition` fields and closed causes; golden tests for living→communicative and communicative→cultural on death / chain expiry.
  - Files: `src/analysis/historical_memory.py`, `tests/unit/test_historical_memory_transitions.py`
  - Logging: INFO `historical_memory_transition` from_layer→to_layer + cause + at_tick + source_token; DEBUG skipped resolution ticks
  - Depends on: 4

- [x] Task 6: Architecture isolation tests — forbid cognition/api imports of `analysis.historical_memory`; forbid layer fields on subjective/world models; forbid unified inject/Assmann aliases in decode; dual-rep walls mirroring v3-09. (Module must exist — depends on Task 3.)
  - Files: `tests/architecture/test_v3_historical_memory_analysis_only.py`, extend `test_analysis_isolation.py` / cultural isolation patterns as needed
  - Logging: N/A (assert-only); test failures must name the violating import
  - Depends on: 1, 3

<!-- Commit checkpoint: tasks 3-6 -->

### Phase 3: Queries, metrics, harvest

- [x] Task 7: Implement `HistoricalMemoryQueryReport` / answer DTOs and the three locked researcher queries with deterministic answers from the graph/classifier (including empty/`unattested` shapes).
  - Files: `src/analysis/historical_memory.py`, `tests/unit/test_historical_memory_queries.py`
  - Logging: DEBUG per-query answer bool + counts; INFO report summary query_count + true_counts by query id
  - Depends on: 4

- [x] Task 8: Register three metric families end-to-end per registration recipe (`MetricFamilyId`, `_spec_*`, `_BUILDERS`, `MetricComputationInputs` fields, assemble/`_safe`, `analysis/__init__.py` exports, exclusion-set updates). Bump `METRIC_FAMILY_COUNT` 53→56. Do not overload listed sibling families.
  - Files: `src/analysis/specifications.py`, `src/analysis/historical_memory_metrics.py`, `src/analysis/metric_service.py`, `src/analysis/__init__.py`, `tests/unit/test_historical_memory_metrics.py`, `tests/unit/test_metric_specifications.py` (+ any A–E exclusion pins)
  - Logging: DEBUG metric assemble family_id + source_count; censoring_policy must state analysis-only / never cognition
  - Depends on: 4, 5, 7

- [x] Task 9: Harvest wiring — map `cultural_feature_audits`, Died/`death_ticks`, narrative rows, communication/teaching edges, artifact marks, optional `generation_index` into `MetricComputationInputs` via `experiments.composition` / collectors / AM path. Prove collectors attach rows when layers enabled (today cultural audits are not auto-attached). No `api`↔`analysis` import violations; duck-type only.
  - Files: `src/experiments/composition.py`, `src/experiments/metric_collection.py`, collectors as needed, `tests/unit/test_historical_memory_harvest.py`
  - Logging: DEBUG harvest counts by source kind; WARN when layers enabled but cultural audits empty
  - Depends on: 4, 8

<!-- Commit checkpoint: tasks 7-9 -->

### Phase 4: Experiment AM + matrix finalize

- [x] Task 10: Add `historical_memory_layers_profile` and `experiment_am_historical_memory_layers` catalog entry (off V1 gate) with locked arm matrix; export from `experiments/__init__.py`. Pin schema v32 + both objects + flag on on-arms.
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, scenario helpers as needed, `tests/unit/test_experiment_am_historical_memory_layers.py`
  - Logging: INFO `experiment_am_built` experiment_id + arm_id + schema_version; DEBUG flag/object presence
  - Depends on: 2, 9

- [x] Task 11: Arm assertions — living / witness-death / communicative / cultural-only / narrative-join / layers-off / flags-off hash stability; prove query flips on last-witness death; prove no layer labels in subjective exports.
  - Files: `tests/unit/test_experiment_am_*.py`, possibly `tests/unit/test_v3_flags_off_hash_stability.py` extensions
  - Logging: test logs only; failures must cite arm_id + query id + expected layer
  - Depends on: 10

- [x] Task 12: Matrix finalize + allowlist ownership — insert `historical_memory_on` **before** `cultural_feature_on`; accept v32; widen `needs_lifecycle` / `needs_init` with `V32`; include AM on allowlist without default V1 batches; keep AL on v31 when layers absent.
  - Files: `src/experiments/matrix_schema.py`, matrix allowlist / finalize tests
  - Logging: DEBUG finalize selected schema_version reason (`historical_memory_on` / `cultural_feature_on` / …)
  - Depends on: 1, 10

<!-- Commit checkpoint: tasks 10-12 -->

### Phase 5: Research UI + docs + pins

- [x] Task 13: Research UI epistemic overlays + AnalyticsPanel surfacing for the three metric families and query answers (`research_inference` only). No subjective ledger fields. **GraphsPanel provenance chrome deferred** — do not block on it.
  - Files: `clients/research-ui/src/epistemic.ts`, `clients/research-ui/src/epistemic.test.ts`, `clients/research-ui/src/views/AnalyticsPanel.svelte`, related client tests
  - Logging: N/A in SPA; use existing client error toasts for metric fetch failures
  - Depends on: 8

- [x] Task 14: Mandatory docs via `/aif-docs` — architecture V3 seams + Downstream contract (v32 deepen, cultural `{v31,v32}`, no new flag), analysis-metrics families, cognition-runtime note that layers are never agent knowledge, DESCRIPTION + ARCHITECTURE artifacts.
  - Files: `docs/architecture.md`, `docs/analysis-metrics.md`, `docs/cognition-runtime.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`
  - Logging: N/A
  - Depends on: 1, 8, 13

- [x] Task 15: Final regression — V1 gate + `test_v2_scientific_invariants` under V3 flags-off; architecture isolation green; `METRIC_FAMILY_COUNT=56`; command count 26; SEMANTIC 43; Alembic head `0017`.
  - Files: existing gate tests; no new production files unless a hole is found
  - Logging: pytest output only
  - Depends on: 6, 8, 11, 12, 14

- [x] Task 16: Close plan verification pins — ensure checkbox-ready for `/aif-verify`; keep the Verification pins table below accurate (implementer updates pins only — no new scope).
  - Files: this plan file (pins only), optionally `docs/architecture.md`
  - Logging: N/A
  - Depends on: 15

<!-- Commit checkpoint: tasks 13-16 -->

## Verification pins (target)

| Pin | Value |
| --- | --- |
| Runner schema | `runner-config-v32` when `historical_memory_layers` present (`v32_requires_historical_memory_layers`) |
| Cultural flag | already owned `cultural_historical_memory` (no new flag); accepts `{v31,v32}` |
| Event write-pair | none (analysis-only deepen) |
| Alembic head | `0017` |
| `AgentCommand` count | 26 |
| SEMANTIC count | 43 |
| `METRIC_FAMILY_COUNT` | 56 (+3) |
| Experiment | `experiment-am-historical-memory-layers` (off V1 gate) |
| Profile | `historical_memory_layers_profile` |
| Metric families | `historical_memory_layers@1`, `historical_memory_transitions@1`, `historical_memory_queries@1` |
| Layer ids | `living`, `communicative`, `cultural` |
| Queries | `any_direct_witnesses_alive`, `anyone_remembers_speaking_to_witness`, `event_known_only_from_stories_or_artifacts` |
| AM arms | `am-layers-off`, `am-living`, `am-witness-death`, `am-communicative`, `am-cultural-only`, `am-narrative-join`, `am-flags-off` |
| Reject codes (core) | `historical_memory_without_cultural_flag`, `historical_memory_requires_cultural_provenance`, `historical_memory_requires_v32`, `v32_requires_historical_memory_layers`, `historical_memory_mode_invalid`, plus nested validation codes; cultural gate widened for `{v31,v32}` |
| Forbidden | layer labels in agent knowledge / Observation / SelfModel; cognition bind; GraphsPanel required chrome |

## Non-goals

- Injecting Assmann categories into agent SelfModel, beliefs, or prompts
- Owning `multi_hop_testimony_tracking` or claiming testimony capability
- Global Culture / society memory store
- Kinship cultural inheritance handoff
- Godot layer atlas / GraphsPanel provenance chrome (deferred)
- Soft `generation_distance_weight` metric bands (default weight stays `0.0`)
- New WorldEvent types for layer transitions
- Alembic `0018+`
- `/v2` HTTP routes
- Blank-slate store for historical layers
