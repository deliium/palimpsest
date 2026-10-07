# Implementation Plan: V3-13 Knowledge and Skill Genealogy

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-07
Improved: 2026-10-07 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Deepens already-owned `cultural_historical_memory` so researchers can track transferable practical-knowledge lineages as DAGs (discovery, teaching, imitation, written record, reconstruction, combination) without collapsing objective skill levels into subjective know-how or installing a society encyclopedia.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-13-knowledge-genealogy.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; suggested stem `v3-13-knowledge-genealogy`; git.create_branches=false so stem is description slug (branch-derived naming disabled)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; scope is explicitly v3-13 under M7 so linkage uses M7
INFO [aif-improve] refined 2026-10-07: cross-owner lineage via analysis join (not peer entry_id copy); PracticalKnowledgeAudit field table; content_key=tech:{token}; mutation child entries + library AP arms; Task 15 matrix finalize (was mislabeled 16); Commit Plan aligned; carry/harvest file lists; blank-slate deny-list; lifecycle survival arm; ROADMAP docs; METRIC_FAMILY_COUNT pin sweep; hop_cap mentorship semantics; drop cultural compose claim

## Compatibility contract

This plan **deepens** already-owned **`V3CapabilityFlags.cultural_historical_memory`** (v3-09; analysis deepen v3-10; durable records v3-11; repositories v3-12). It adds **knowledge and skill genealogy**: owner-scoped subjective practical-knowledge lineages with multi-parent transmission DAGs, mutation across hops, and analysis-only researcher queries — while **objective capability** remains the existing WorldEngine skill ledger and **research lineage** stays outside live cognition.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents receive immutable per-agent `Observation` / `Perspective` only. `WorldEvent` records remain immutable and append-only. Subjective state stays outside the objective fold. Godot remains read-only. Deterministic replay continues. No scripted civilization / technique_must_diffuse / true_genealogy_restored outcomes.
2. Flag ownership unchanged: keep `cultural_historical_memory`, `generational_population`, and `kinship_inheritance` owned. Do **not** own `multi_polity_migration`, `institutional_economy`, or `multi_hop_testimony_tracking`. **No new V3 capability flag.**
3. Flags-off / channel-off / genealogy-object-absent = prior baseline. With all V3 flags off, or with `cultural_historical_memory=False` / `cultural_feature_provenance` absent / `knowledge_genealogy` absent, trajectories and `exact_trajectory_hash` match the pre-plan baseline for AE–AO where applicable. Existing skill_learning / mentorship / cultural / durable / repository metric families stay unchanged (sibling families only).
4. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2/V3 versions in the same change that adds a write version.
5. **Triple representation (locked).** Distinguish and never collapse:
   - **Objective capability** — WorldEngine `ObjectiveSkillLedger` / `SkillDomain` levels (foraging, healing, crafting, navigation, building, …). Capability is physical competence, not a genealogy of know-how.
   - **Subjective knowledge** — owner-scoped practical-knowledge entries (methods/techniques) with fallible fingerprints, multi-parent lineage, and transmission origins. May be wrong, incomplete, mutated, or recombined.
   - **Research lineage** — analysis-only DAG + researcher queries over detached harvest rows. Never imported by cognition; never written into agent stores; never a WorldEngine law.
6. **No society encyclopedia / GlobalKnowledge / TechniqueRegistry (locked).** Forbidden: world-snapshot technique catalogs, automatic society-wide know-how download, kinship auto-inheritance of techniques, or a controller that asserts the "true" method.
7. **Lineage is a DAG, not a single-teacher tree (locked).** Owner-local multi-parent `parent_entry_ids` are first-class for combination / mutate / reinforce. Cross-owner transmission is recorded via public `source_agent_id` + evidence refs; analysis joins peers into a DAG — never by copying peer `entry_id`s into live ledgers. Mentorship's single-parent `TaughtContentLineageEntry` remains valid evidence for the *teaching* origin channel but is **not** the genealogy store.
8. **Mutation across transmission (locked).** Mutation creates a **new child entry** (`parent_entry_ids=(prior,)`, hop+1, `mutated=true` when distance ≥ threshold). Independent discovery hop_index = 0. Hop cap fails closed (`hop_index >= max_hop_depth`, mentorship semantics: default 16 ⇒ max legal hop 15).
9. **No internal-state copy.** Transmission never copies another agent's practical-knowledge ledger, cultural ledger, mentorship lineage, developmental ledger, competence beliefs, relationships, goals, or SelfModel. Uptake forms fresh owner-scoped entries from public acts / observations / artifacts / reconstructive cues only.
10. **Preserve v3-02–v3-12 locks:** blank-slate deny-list; closed Observation `lifecycle`; ELDER ≠ leader; related ≠ affection; no parent→caregiver hardwiring; no global Culture/LibraryInstitution; durable marks ≠ truth; written information ≠ objective truth; historical layers stay analysis-only; Alembic head `0017` by default; kinship cultural inheritance handoff stays deferred.
11. **`api` must not import `analysis`.** Persist metric docs offline; serve via existing `MetricReadService` / inspection projections only.
12. Closed `AgentCommand` count stays **34**. SEMANTIC observer types stay **53**. **No new event write-pair** (subjective + analysis channel; default event write unchanged when genealogy-only).
13. Do **not** overload `skill_learning@1`, `cultural_transmission@1`, `mentorship_*`, `cultural_feature_*`, `durable_record_*`, `knowledge_repository_*`, `historical_memory_*`, or `kinship_genealogy`. Sibling families only.

## Goal

Track lineage of **transferable practical knowledge** — methods and techniques that agents can discover, teach, imitate, reconstruct, write down, or combine — without treating skill levels as genealogy or installing an authoritative technique encyclopedia.

Example technique kinds (closed enum; not free text):

| Kind | Maps near objective `SkillDomain` (anchor only) |
| --- | --- |
| `foraging_method` | `foraging` |
| `healing_technique` | `healing` |
| `crafting_process` | `crafting` |
| `navigation_knowledge` | `navigation` |
| `building_method` | `building` |

Closed transmission origins:

| Origin | Meaning |
| --- | --- |
| `independent_discovery` | New root; no parents; hop_index = 0 |
| `teaching` | Learned via teaching / mentorship / instruction acts |
| `imitation` | Learned by observing another agent's practice |
| `written_record` | Learned from durable marks / repository retrieval / artifact cues |
| `reconstruction` | Rebuilt from incomplete memory / partial evidence (reconstructive path) |
| `combination` | Recombined from ≥2 **owner-local** parent entries |

Support researcher queries (analysis-only):

1. **Who currently knows technique T?** — living holders with active subjective entries for `content_key` (and kind when policy says)
2. **Who taught them?** — `source_agent_id` / teaching-origin edges (analysis may also resolve peer joins)
3. **Where did the oldest surviving lineage originate?** — independent_discovery roots still reachable from living holders (min acquired_tick / root id)
4. **Did the knowledge emerge independently twice?** — count of distinct independent_discovery roots for the same technique key (≥2 ⇒ yes)

Deliver:

- Exact optional root sibling `knowledge_genealogy` on **`runner-config-v35`**
- Owner-scoped subjective practical-knowledge ledger + multi-parent lineage + mutation/recombination APIs
- Optional compose from teaching (incl. mentorship cues), imitation, written_record (durable + repositories), reconstruction, developmental, independent_discovery — never Observation-forced method catalogs; **no cultural-feature compose key** (ledgers stay siblings)
- Analysis-only genealogy DAG + four locked researcher queries + three sibling metric families
- Research UI Analytics discovery badges for the three families
- Off-gate Experiment AP comparing channel-off vs genealogy-on across discovery / teaching / mutation / combination / dual-emergence / written-record / reconstruction / lifecycle-survival / capability-join arms

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` remains the only authority over objective skill levels and physical state; practical-knowledge genealogy never rewrites `ObjectiveSkillLedger`.
2. Agents never receive another agent's private knowledge ledger, a society technique pack, or analysis query documents as facts.
3. `WorldEvent` records remain immutable; authoritative history stays append-only.
4. Subjective knowledge may be wrong, incomplete, mutated, or recombined and never folds into objective replay identity.
5. Research lineage queries and analytical DAGs must not bias live cognition.
6. LLM output remains non-authoritative.
7. No scripted `technique_must_spread` / `true_method_restored` / `independent_discovery_forced` booleans.
8. Godot remains read-only; this plan does **not** require knowledge-map chrome (optional metadata presentation deferred).
9. Runs remain reproducible where claimed (explicit seeds, deterministic streams, deterministic fakes / recorded LLM paths).

### Scope split (locked)

| This plan (v3-13) | Deferred |
| --- | --- |
| Subjective practical-knowledge ledger + owner-local multi-parent DAG | Hard-coded GlobalTechniqueRegistry / society encyclopedia |
| Analysis genealogy queries + sibling metrics + Experiment AP | Owning `institutional_economy` / schools as institutions |
| Optional compose from teaching/durable/developmental/imitation/reconstruction channels | Kinship cultural / knowledge inheritance handoff |
| `runner-config-v35` (no write-pair) | Alembic `0018+`; `/v2` HTTP; new AgentCommand |
| Capability↔knowledge join via analysis (skill_learning pattern) | Collapsing competence beliefs into genealogy entries |
| Research UI Analytics discovery badges | Full interactive genealogy browser in GraphsPanel |
| Cross-owner DAG edges resolved in analysis only | Live peer `entry_id` pointers / ledger downloads |

**Rationale for cultural coupling:** genealogy deepens the same M7 `cultural_historical_memory` seam (transmissible owner-scoped know-how with provenance). It stays a **sibling ledger** to cultural features — cultural `production_technique` / `practice` beliefs are symbolic/social framing; practical-knowledge entries are method/technique lineages with capability anchors and researcher genealogy queries. Ledgers must not merge. Do **not** claim analysis cross-links by cultural `content_key` (cultural audits lack that field).

### Capability / ownership (locked)

1. **No new V3 flag.** Enabling genealogy requires already-owned `cultural_historical_memory=True` plus exact `cultural_feature_provenance` **and** exact `knowledge_genealogy` on `runner-config-v35`.
2. **Prerequisite objects on v35:** `cultural_feature_provenance` required. `durable_records` / `knowledge_repositories` / `historical_memory_layers` / `mentorship` / `developmental_learning` remain **optional compose sources** — genealogy-on without durable is legal (teaching/imitation/discovery arms).
3. **v34 without genealogy** stays valid (AO baseline). Schema `v35` always requires `knowledge_genealogy` when that schema is selected (mirror v34↔repository discipline).
4. Do **not** implement kinship knowledge inheritance handoff.
5. Other unowned V3 flags still fail closed.
6. When genealogy object absent: AE–AO bit-identity matches pre-plan for the same roster and seeds; skill_learning / mentorship / cultural behavior unchanged.
7. Do **not** claim that enabling genealogy auto-enables teaching / skill learning / durable / repositories — omit object / keep modes `DISABLED` for objective-only or teaching-off arms; compose skips with DEBUG.

### Flag × object gate matrix (locked)

| Config shape | Allowed? | Reject / notes |
| --- | --- | --- |
| Cultural flag off, genealogy absent | Yes (off) | Passthrough |
| Genealogy object present, cultural flag off | No | `knowledge_genealogy_without_cultural_flag` |
| Genealogy object present, `cultural_feature_provenance` absent | No | `knowledge_genealogy_requires_cultural_provenance` |
| Genealogy object present on schema ≠ v35 | No | `knowledge_genealogy_requires_v35` |
| Cultural + provenance on **v34**, genealogy absent | Yes | Pre-plan AO behavior |
| Cultural + provenance + genealogy on **v31..v34** | No | `knowledge_genealogy_requires_v35` |
| Cultural + provenance + genealogy on **v35** | Yes | Genealogy channel enabled |
| Schema `v35` without genealogy object | No | `v35_requires_knowledge_genealogy` |
| Schema `v35` without provenance | No | `v35_requires_cultural_provenance` |
| Durable / repository / layers on **v35** (with genealogy) | Yes | Widen allowlists capped at v34 to include v35 |
| Genealogy `mode=disabled` present | No | `knowledge_genealogy_mode_invalid` — omit object for off |
| Cultural-only on v35 (lifecycle off) + genealogy | Yes | Widen `_cultural_only` to include v35 |
| Generational + cultural + genealogy on v35 | Yes | Multi-generation survival / dual-emergence arms |
| Mentorship / developmental without lifecycle | No | Unchanged existing rejects |

### Runner schema (locked)

Introduce `RUNNER_SCHEMA_VERSION_V35 = "runner-config-v35"`:

- Exact root key set = **v34 accepted roots** ∪ sibling **`knowledge_genealogy`** (prefer helper extraction over copy-pasting all 72 `_RUNNER_ROOT_KEYS_V34_*` variants; v35 may omit durable/repository keys when those objects are absent).
- `knowledge_genealogy` present ⇒ `schema_version == runner-config-v35` and cultural flag on with exact provenance + genealogy objects.
- Decode v23–v34 synthesizes `knowledge_genealogy=None` (absent ≡ genealogy channel off).
- Gate rewrite: `cultural_historical_memory=True` accepts `{v31, v32, v33, v34, v35}`. Rewrite cultural provenance / `_cultural_only` / `_HISTORICAL_MEMORY_*` / durable / repository allowlists capped at v34 to include v35.
- **Repository / durable co-rewrite (Task 1):** `knowledge_repositories` / `durable_records` accept schema sets widened with v35 when their objects are present (keep existing reject **code strings**; extend allowlist messages to “v34 or v35”). Prove v35 + repositories without genealogy rejects `v35_requires_knowledge_genealogy`.
- Default write stays `runner-config-v4` when all V3 flags are off.
- **No write-pair bump.** Checkpoint selection unchanged by genealogy-only (still V14/v11 when repositories active, else prior priority). Genealogy state is subjective + analysis harvest only.
- **Matrix finalize (Task 15 only):** insert `knowledge_genealogy_on` **before** `knowledge_repositories_on` (v35 beats v34); widen `needs_lifecycle` / `needs_init` with `V35`; AP on v35; AO on v34 when genealogy absent; … Task 1 must **not** edit finalize priority.

### Serialization contract (locked)

Mirror v34 pattern in `runner_serialization.py`:

- Prefer `_v34_family_root_keys(data)` helper then v35 = that ∪ `{knowledge_genealogy}` (minus optional durable/repository keys when absent) — do **not** blindly duplicate 72 frozensets × optional dimensions.
- Exact child keyset `_KNOWLEDGE_GENEALOGY_KEYS` matching nested policy tables below
- `_encode_knowledge_genealogy` / `_decode_knowledge_genealogy` with `_require_keys` (no silent extras)
- Encode: `schema_version == V35` requires provenance + genealogy present; durable/repository/layers optional
- Decode: v23–v34 → `knowledge_genealogy=None`
- DEBUG log present/absent on decode (metadata only)
- Reject forbidden aliases via frozenset parallel to `_HISTORICAL_MEMORY_FORBIDDEN_ALIASES` / cultural forbidden aliases: `global_technique_registry`, `society_encyclopedia`, `true_method_catalog`, `knowledge_pack`, `parent_technique_copy`, `technique_pack`, …

### Runtime channel flags (locked)

1. `knowledge_genealogy_active = config.knowledge_genealogy is not None` at run start (boolean for gating/logs only).
2. Bind the **`KnowledgeGenealogySpec` object** into cognition / loop kwargs (mirror `cultural_features_spec` / mentorship — loop needs `max_*`, compose flags, mutation policy). Do **not** bind a bare bool as the only loop input.
3. Do **not** change `checkpoint_schema_for_production` / `engine.select_checkpoint_schema` for genealogy-only.
4. Subjective checkpoint / runtime carry for the new ledger follows existing cultural-feature / mentorship patterns (owner-scoped; outside objective fold; in-memory runtime checkpoint — no SQLAlchemy subjective serializer).

### `KnowledgeGenealogySpec` (locked)

Root sibling object; omit for off. Exact keys (reject extras / missing):

| Key | Type / values | Role |
| --- | --- | --- |
| `knowledge_genealogy_mode` | `deterministic` only | Present object implies on; `disabled` rejected |
| `lineage_policy` | Exact nested object | Hop caps, parent caps, eviction |
| `mutation_policy` | Exact nested object | Mutation / combination rules |
| `uptake_compose` | Exact nested object | Which existing channels may seed uptake |
| `query_policy` | Exact nested object | Analysis query depth caps (research-facing defaults) |
| `enabled_kinds` | Non-empty unique tuple of `PracticalKnowledgeKind` values | Arms may narrow kinds |
| `applicability` | `all_live_agents` \| `mid_run_new_agents` \| `lifecycle_learning_stage` | Mirror developmental applicability |
| `max_evidence_refs` | Positive int (default `8`) | Cap evidence ref tuple |
| `rng_namespace` | Token string | Seed material namespace for deterministic mutation (`knowledge_genealogy`) |

**`lineage_policy` exact keys:**

| Key | Role |
| --- | --- |
| `max_entries_per_owner` | Positive int (default `64`) |
| `max_parent_ids` | Positive int (default `4`) |
| `max_hop_depth` | Positive int (default `16`; hard ceiling constant in module — reject above ceiling) |
| `allow_multi_parent` | Bool (default `true`) — when false, combination rejected |

**`mutation_policy` exact keys:**

| Key | Role |
| --- | --- |
| `allow_mutation` | Bool (default `true`) |
| `allow_combination` | Bool (default `true`) |
| `mutation_distance_threshold` | Float in (0,1] (default `0.15`) — `mutated := (1 − jaccard(cue_fp, child_fp)) >= threshold` |
| `max_token_edits` | Non-neg int (default `2`) |
| `mutation_requires_evidence` | Bool (default `true`) |
| `min_token_overlap` | Float in [0,1] (default `0.25`) — combination parent fingerprint overlap floor |
| `require_combination_distinct_roots` | Bool (default `false`) — when true, combination parents must not share `lineage_root_id` |

**`uptake_compose` exact keys (all bool, default false):**

| Key | Role |
| --- | --- |
| `teaching` | Compose from teaching acts **and** mentorship taught-content public cues (gated by teaching mode / mentorship spec when present) |
| `imitation` | Compose from colocated practice observation |
| `written_record` | Compose from durable artifact **and** repository retrieval cues (gated by `artifacts_enabled` and durable/repository channels) |
| `reconstruction` | Compose from reconstructive-memory cues (when memory mode allows) |
| `developmental` | Compose from developmental acquisition audits in `skills`/`practices` domains |
| `independent_discovery` | Allow experimentation / practice success to mint independent roots |

No `cultural` key. No separate `mentorship` / `durable` / `repositories` keys — folded into `teaching` / `written_record` as above.

**`query_policy` exact keys:**

| Key | Role |
| --- | --- |
| `max_query_depth` | Positive int (default `32`; hard ceiling = `_KINSHIP_MAX_QUERY_DEPTH_CEILING` = 32 in `runner_models.py`) |
| `include_dead_holders` | Bool (default `true`) — dead agents remain in **historical** lineage / `who_taught` / holders-family dead counts; **`who_currently_knows` always filters living** |
| `independent_root_match` | `content_key` (default) \| `content_key_and_kind` — dual-emergence root comparison (`content_key` is kind-free so the modes differ) |

Provide `example_knowledge_genealogy_spec()` in `runner_models.py` for tests and Experiment AP. Plumb run `seed` as `seed_material` through `_knowledge_genealogy_loop_kwargs` so mutation hashes differ across seeds (`sha256(f"{rng_namespace}:{seed_material}:{id}:{tick}")` — cultural-style, not a shared RNG stream that would move AE–AO hashes).

### Domain model (locked)

Package: new `agents/cognition/practical_knowledge.py` (owner-scoped ledger; facade export). Do **not** invent a WorldEngine technique registry. Do **not** import `world._skills` — use string-parity capability anchors (mirror `teaching.AdviceDomain`) + a parity test against `SkillDomain` values.

**`PracticalKnowledgeKind` (StrEnum):** `foraging_method`, `healing_technique`, `crafting_process`, `navigation_knowledge`, `building_method`.

**`KnowledgeTransmissionOrigin` (StrEnum):** `independent_discovery`, `teaching`, `imitation`, `written_record`, `reconstruction`, `combination`.

**`content_key` stability (locked):**

- `content_key = f"tech:{technique_token}"` — kind-free, source-free; `technique_token` via `require_stable_id` grammar only.
- At most one **active** row per `(owner_id, content_key)`. Reinforce updates the active row; mutate/supersede leave predecessors `active=False`. Evict inactive first, then oldest by `(acquired_tick, entry_id)`.

**Per-origin `technique_token` / kind sources:**

| Origin | Token / kind source |
| --- | --- |
| `teaching` | `AdviceDomain` mapped to kind (`foraging`/`healing`/`crafting`/`navigation`/`building` only; skip `resource_detection`/`communication`/`teaching` with DEBUG). Mentorship `practical_skills` / `production_recipes` when `teaching` compose on and mentorship present |
| `imitation` | Successful colocated practice occurrence kinds mapped to technique tokens (never embed other agent id in `content_key`) |
| `written_record` | Artifact / repository perception cues (`instruction` / inventory-like genres); marks ≠ true methods |
| `reconstruction` | Reconstructive-memory incomplete technique cues |
| `developmental` | `DevelopmentalDomainId.SKILLS` / `PRACTICES` audit rows |
| `independent_discovery` | Experimentation / own successful practice when compose flag on |
| `combination` | Derived from combined parent content keys (stable join token) |

**`SubjectivePracticalKnowledge` fields:**

| Field | Role |
| --- | --- |
| `entry_id` | Opaque stable id |
| `owner_id` | Agent id (ledger owner) |
| `kind` | `PracticalKnowledgeKind` |
| `content_key` | `tech:{technique_token}` |
| `content_fingerprint` | Frozen token tuple for mutation distance (never logged as payload) |
| `capability_anchor` | Optional skill-domain value string (analysis join only; not a skill write) |
| `origin` | `KnowledgeTransmissionOrigin` |
| `parent_entry_ids` | Owner-local only: 0 for independent / peer-taught uptake; 1 for mutate/reinforce-from-self; ≥2 for combination |
| `lineage_root_id` | Owner-local: inherited from owner parents, or `root:{source_or_owner}:{kind}:{content_key}` for peer-taught / independent |
| `hop_index` | Owner-local: independent = 0; peer-taught uptake = 1 (or parent_hop+1); else max(owner parent hops)+1 |
| `mutated` | Bool |
| `source_agent_id` | Optional public teacher / demonstrator / author / speaker id |
| `teacher_agent_id` | Optional alias when origin is `teaching` (same as `source_agent_id` when set from teaching) |
| `evidence_refs` | Opaque refs (`teach:{occurrence}`, …); counts logged, not payloads |
| `acquired_tick` | Non-neg int |
| `active` | Bool — soft-forget / supersession without DELETE |

**Cross-owner lineage mechanism (locked):**

1. Live ledger **never** stores another agent's `entry_id` in `parent_entry_ids`.
2. Peer transmission records `source_agent_id` + `evidence_refs` only (public cues).
3. Analysis builds `transmitted_from` edges by joining (`source_agent_id`, same `content_key`, latest active source entry with `acquired_tick <=` child tick, tie-break `entry_id`). Unresolved joins counted, never fabricated.
4. Owner-local `hop_cap` ≠ analysis DAG depth (capped by `query_policy.max_query_depth`).

**Invariants:**

- `independent_discovery` ⇒ empty parents, hop 0, no teacher/source required
- Peer-taught / imitation / written_record uptake ⇒ empty `parent_entry_ids` allowed; `source_agent_id` and/or evidence required per origin
- `combination` ⇒ `len(owner-local parents) >= 2`, `allow_combination`, and `allow_multi_parent`
- Mutate child ⇒ `parent_entry_ids=(prior_entry_id,)`, hop = prior.hop+1
- Evicted parent hop fallback: missing parent without `parent_hop_index` hint ⇒ hop 1 (not 0); mirror cultural `_resolve_hop_index`
- `hop_index >= max_hop_depth` ⇒ reject `knowledge_genealogy_hop_cap`
- Cycle check on **owner-local** parent edges only
- `__post_init__` enforces module hard ceiling; ledger methods enforce spec `max_hop_depth`

**APIs (deterministic):**

- `empty_practical_knowledge_ledger(owner, *, max_entries, max_parent_ids, max_hop_depth, max_evidence_refs)`
- `require_owner_practical_knowledge(ledger, owner_id, *, field_name)`
- `entry_to_audit(entry, *, tick, reason_code, fingerprint_distance_q=…)`
- `form_or_reinforce_practical_knowledge(...)` (accepts optional `parent_hop_index`)
- `mutate_practical_knowledge(...)` — **new child entry**
- `combine_practical_knowledge(...)` — multi-parent; origin=`combination`
- `supersede_practical_knowledge(...)` — `active=False` on prior; no DELETE
- `PracticalKnowledgeLedger` + `PracticalKnowledgeAudit`

**`PracticalKnowledgeAudit` fields (locked — event log; last row per `entry_id` wins for “current”):**

| Field | Role |
| --- | --- |
| `owner_id` | Agent id |
| `entry_id` | Opaque id |
| `kind` | Kind enum value string |
| `content_key` | `tech:…` token |
| `origin` | Origin enum value string |
| `parent_entry_ids` | Tuple (owner-local) |
| `lineage_root_id` | Root token |
| `hop_index` | Non-neg int |
| `mutated` | Bool |
| `source_agent_id` | Optional |
| `teacher_agent_id` | Optional |
| `capability_anchor` | Optional |
| `acquired_tick` | Non-neg int |
| `tick` | Audit emission tick |
| `active` | Bool at emission |
| `reason_code` | Stable code (`formed` / `reinforced` / `mutated` / `combined` / `superseded` / …) |
| `fingerprint_distance_q` | Quantized float distance at write time (analysis never sees raw fingerprints) |

Emit one audit row per form / reinforce / mutate / combine / supersede.

### Compose / cognition wiring (locked)

1. Do **not** add a new `AgentCognitionSpec` mode solely for genealogy (channel is runner sibling object).
2. `_prepare_practical_knowledge` runs **after** `_prepare_teaching`, `_prepare_developmental_knowledge`, `_prepare_mentorship`, `_prepare_cultural_features`, and `_prepare_artifact_interpretations` (consumes advice deltas, developmental audits, observation).
3. Compose adapters map public cues → fresh entries when corresponding `uptake_compose.*` is true and source mode/channel is active; otherwise DEBUG skip (`teaching_mode_on`, `artifacts_on`, `repositories_on = artifacts_on and knowledge_repositories_active`, `mentorship_on = _mentorship_spec is not None`, reconstructive memory mode, developmental channel).
4. Teaching compose sets `source_agent_id` / `teacher_agent_id` from public teaching act metadata — never copies teacher ledger rows.
5. Written-record compose uses artifact/repository **perception cues** only.
6. Reconstruction compose requires reconstructive memory path producing incomplete technique cues.
7. Independent discovery may mint roots from experimentation / practice success when flag on — still subjective; does not bump objective skill by itself.
8. Mutation / combination library APIs are **not** required to have a live loop trigger in this plan (mirror cultural mutate/recombine). Experiment AP arms `ap-mutation-hop` and `ap-multi-parent-dag` prove them via **direct ledger calls**.
9. Observation / Perspective must **never** project a world technique catalog or genealogy DAG.

### Blank-slate (locked)

In `src/simulation/new_agent_initialization.py`:

- `SUBJECTIVE_COPY_DENY_LIST`: add `practical_knowledge`, `knowledge_ledger`, `technique_pack`, `knowledge_pack`, `parent_technique_copy`, `knowledge_genealogy`
- `BLANK_SLATE_SUBJECTIVE_STORES`: append `practical_knowledge`
- `BlankSlateStoreCounts`: add `practical_knowledge: int = 0`
- Update `tests/unit/test_new_agent_blank_slate_guard.py` to the live store tuple (currently stale vs mentorship/cultural) and include the new store
- Mid-run admission: fresh `AgentRuntime` starts with empty/None ledger; prove via admission test

### Analysis: genealogy DAG + queries (locked)

New module `src/analysis/knowledge_genealogy.py` (analysis-only):

**`KnowledgeGenealogyGraph`** — frozen nodes/edges over detached duck-typed audit rows (do **not** overload `HistoricalProvenanceGraph`). Node kinds: `holder`, `knowledge_entry`, `independent_root`. Edge kinds: `holds`, `transmitted_from` (analysis peer join), `combined_from`, `mutated_from`, `unresolved_transmission`.

Inputs: audit rows + `death_ticks` + `as_of_tick` (reuse `analysis.historical_memory.is_agent_living_at` / `_death_ticks_from_events` — genealogy-only runs must still derive death ticks from events). Optional `generation_index_by_agent` for holders breakdown / dual-emergence spread only.

**Locked researcher queries** (`KnowledgeGenealogyQueryId`):

| Query id | Behavior |
| --- | --- |
| `who_currently_knows` | Living holders with `active` entry matching technique key (and kind when policy says) |
| `who_taught` | Distinct `teacher_agent_id` / `source_agent_id` for holder+technique; may include dead when `include_dead_holders` |
| `oldest_surviving_lineage_origin` | Among independent roots still reachable from living active holders, min `(acquired_tick, lineage_root_id)` |
| `independent_emergence_count` | Count distinct independent_discovery roots for technique key; `emerged_independently_twice = count >= 2` |

Depth clamped by `query_policy.max_query_depth` + hard ceiling. Results sorted by `(depth, id)`.

Optional analysis join: capability gap via skill_learning unmatched pattern using `capability_anchor` — never fabricate skill levels from knowledge entries.

### Analysis metrics (locked)

Sibling families (bump `METRIC_FAMILY_COUNT` **62 → 65**):

| Family id | Version string | Signal |
| --- | --- | --- |
| `knowledge_genealogy_holders` | `knowledge_genealogy_holders@1` | Active holders per technique; living vs dead (via `death_ticks`); mean hop; teacher coverage |
| `knowledge_genealogy_lineage` | `knowledge_genealogy_lineage@1` | Root counts; multi-parent share; combination rate; max owner-local + analysis DAG depth; dual independent-emergence rate; unresolved transmission count |
| `knowledge_genealogy_mutation` | `knowledge_genealogy_mutation@1` | Mutated hop share; mean `fingerprint_distance_q`; origin histogram |

DTO summaries: counts/histograms/id lists only — never fingerprints/payloads in metric notes.

### Experiment AP (locked)

`experiment_ap_knowledge_genealogy` / `knowledge_genealogy_profile` (off V1 gate).

`knowledge_genealogy_profile(config)` mirrors `knowledge_repositories_profile`: require v35 + cultural flag + provenance + genealogy; allow extra flags only from `{generational_population, kinship_inheritance, cultural_historical_memory}` with matching reject codes. Add id to `OFF_GATE_MATRIX_EXPERIMENT_IDS` in Task 13 (`catalog.py`).

| Arm id | Schema | Genealogy | Focus |
| --- | --- | --- | --- |
| `ap-channel-off` | v34 | absent | AO baseline path (reuse v34 repositories builder); hash stability |
| `ap-independent-discovery` | v35 | on | Mint independent roots; holders family > 0; hop 0 |
| `ap-teaching-lineage` | v35 | on + teaching compose | `source_agent_id` / `who_taught` non-empty; analysis may resolve `transmitted_from` |
| `ap-multi-parent-dag` | v35 | on | **Direct ledger** `combine_practical_knowledge`; lineage multi-parent share > 0 |
| `ap-mutation-hop` | v35 | on + mutation | **Direct ledger** mutate child; mutation family populated |
| `ap-dual-emergence` | v35 | on | Two isolated discoverers same `content_key`; `independent_emergence_count >= 2` |
| `ap-written-record` | v35 | on + durable compose | Origin written_record from artifact cue; no Observation catalog |
| `ap-reconstruction` | v35 | on + reconstruction compose | Origin reconstruction; incomplete cue still forms entry |
| `ap-lifecycle-survival` | v35 | on + lifecycle | Teacher dies; living student retains active knowledge; historical lineage retains dead teacher when `include_dead_holders` |
| `ap-capability-join` | v35 | on + skill learning | Analysis join objective skill vs subjective knowledge; unmatched allowed |
| `ap-flags-off` | v4 | absent | All V3 off; hash stability vs pre-plan |

- Prove: flags-off / genealogy-off hashes stable; V1 gate + `test_v2_scientific_invariants` green under V3 flags-off; architecture isolation green; SEMANTIC **53**; command count **34**; Alembic head `0017`; write-pair unchanged when genealogy-only.
- Matrix allowlist includes AP without enabling on default batches.

### Architecture isolation (locked)

- `agents` / `agents.cognition` must not import analysis knowledge-genealogy modules or `world._skills` mutators.
- Analysis must not import private `world._*` authority modules or `agents.cognition` live ledgers (duck-typed audits only).
- `api` / cognition paths must not import `analysis`.
- No `GlobalTechniqueRegistry`, society encyclopedia, or Observation technique-catalog enums.
- Forbidden string aliases rejected in runner decode / domain module.
- Follow `tests/architecture/test_v3_cultural_feature_isolation.py` / `test_v3_knowledge_repositories_isolation.py` patterns (`_module_imports_forbidden`).

### Docs (locked — mandatory)

Update (no “optional” hedges):

- `docs/architecture.md` — V3 seams row + Downstream V3 contract (v35 deepens cultural; cultural flag accepts `{v31..v35}`; no new flag; no write-pair; triple representation; cross-owner analysis join)
- `docs/cognition-runtime.md` — practical-knowledge ledger; compose gates; Observation never catalogs techniques
- `docs/analysis-metrics.md` — three new families + four researcher queries + DTO exposure
- Reconstructive/memory note — reconstruction origin is subjective rebuild, not world truth
- `.ai-factory/DESCRIPTION.md` — V3 scaffolding blurb for v35 knowledge genealogy
- `.ai-factory/ARCHITECTURE.md` — allowlists / owned-flag notes for v35
- `.ai-factory/ROADMAP.md` — M7 Plans list + “Also owned” sentence for v3-13 (avoid the v3-12 follow-up gap)

No `docs/observer.md` / `docs/physical-simulation.md` changes required (SEMANTIC and write-pair unchanged).

## Commit Plan

- **Commit 1** (after tasks 1–2): `feat(v3): add knowledge_genealogy runner-config-v35 gates`
- **Commit 2** (after tasks 3–5): `feat(cognition): practical knowledge ledger and multi-parent lineage`
- **Commit 3** (after tasks 6–8): `feat(cognition): knowledge genealogy compose carry and isolation`
- **Commit 4** (after tasks 9–12): `feat(analysis): knowledge genealogy DAG queries metrics harvest`
- **Commit 5** (after tasks 13–15): `feat(experiments): Experiment AP knowledge genealogy`
- **Commit 6** (after tasks 16–18): `docs(v3): knowledge genealogy seams` + Research UI discovery + verification pins

## Tasks

### Phase 1: Schema, serialization, and gates

- [x] Task 1: Add `RUNNER_SCHEMA_VERSION_V35`, `KnowledgeGenealogySpec` (+ nested policies, `enabled_kinds`, `applicability`, `max_evidence_refs`), `SimulationRunnerConfig.knowledge_genealogy`, `example_knowledge_genealogy_spec()`, exact encode/decode + `_KNOWLEDGE_GENEALOGY_KEYS`, helper-based v35 root-key construction (avoid 72×N frozenset explosion), forbidden-alias frozenset, and full reject-code set. **Rewrite** cultural provenance / `_cultural_only` / `_HISTORICAL_MEMORY_*` / durable / repository allowlists capped at v34 to include v35. Add `v35_requires_knowledge_genealogy`, `v35_requires_cultural_provenance`, and genealogy reject codes from the flag×object matrix. Keep existing reject **code strings** for durable/repository; widen allowlists. Compatibility: genealogy-only does **not** change write-pair priority. **Do not** edit matrix finalize priority here (**Task 15** owns that).
  - Deliverable: Config round-trip tests; reject rows including genealogy-on-v34, v35 without provenance, v35 without genealogy, durable+repository+genealogy on v35 legal, v35+repositories without genealogy rejected; decode v23–v34 synthesizes genealogy=None; forbidden aliases rejected; table-driven root-key Cartesian coverage.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `tests/unit/test_knowledge_genealogy_spec.py`, `tests/unit/test_runner_config_v35*.py`, extend v34/durable/historical allowlist tests as needed
  - Logging: DEBUG decode present/absent; INFO/raise stable reject codes on fail-closed; never log fingerprints/payloads
  - Depends on: none

- [x] Task 2: Config enable/skip + runner/runtime channel wiring. Validate genealogy in `SimulationRunnerConfig.__post_init__` (not a separate `from_config`); compute `knowledge_genealogy_active`; build `_knowledge_genealogy_loop_kwargs` passing the **spec object** + `seed_material` at **both** initial loop-build (`runner.py` ~L1734) and mid-run admission (~L3199). Prove cultural ownership unchanged; unowned V3 flags fail closed; passthrough when object absent (AE–AO hash-stable fixtures). Do **not** claim ledger-write skip proofs here (Task 6).
  - Deliverable: Unit tests for enable/skip and kwargs plumbing.
  - Files: `src/simulation/runner.py`, `src/simulation/runner_models.py`, `src/agents/cognition/configuration.py`, `tests/unit/test_knowledge_genealogy_from_config.py`
  - Logging: INFO `knowledge_genealogy_enabled` with max_entries + max_hop_depth + compose flags summary; DEBUG skip when absent
  - Depends on: 1

<!-- Commit checkpoint: tasks 1-2 -->

### Phase 2: Subjective ledger and lineage DAG

- [x] Task 3: Add enums, `SubjectivePracticalKnowledge`, `PracticalKnowledgeLedger`, `PracticalKnowledgeAudit`, `empty_practical_knowledge_ledger`, `require_owner_practical_knowledge`, `entry_to_audit`, locked invariants (independent/combination/hop/parent caps/eviction/owner-local cycle), and `content_key=tech:{token}` helpers. Update blank-slate deny-list / `BLANK_SLATE_SUBJECTIVE_STORES` / `BlankSlateStoreCounts` in `new_agent_initialization.py`; fix stale blank-slate unit pin and add architecture text checks. Export via `agents.cognition` facade.
  - Deliverable: Unit tests for legal/illegal constructions; hop resolution + parent_hop fallback; multi-parent combination; eviction order; blank-slate pins include `practical_knowledge`.
  - Files: `src/agents/cognition/practical_knowledge.py` (new), `src/agents/cognition/__init__.py`, `src/simulation/new_agent_initialization.py`, `tests/unit/test_practical_knowledge_model.py`, `tests/unit/test_new_agent_blank_slate_guard.py`, `tests/architecture/test_v3_new_agent_blank_slate.py`
  - Logging: DEBUG `practical_knowledge_constructed` kind + hop + parent_count + origin (no fingerprint dumps)
  - Depends on: 1

- [x] Task 4: Implement `form_or_reinforce_practical_knowledge`, `mutate_practical_knowledge` (**new child**), `combine_practical_knowledge`, `supersede_practical_knowledge` with seed-material mutation (`sha256` namespace recipe). Fail closed with stable reason codes: `knowledge_genealogy_inactive`, `knowledge_genealogy_hop_cap`, `knowledge_genealogy_parent_cap`, `knowledge_genealogy_combination_requires_parents`, `knowledge_genealogy_cycle`, `knowledge_genealogy_mutation_disabled`, `knowledge_genealogy_combination_disabled`. Document library-level mutation/combination (no live loop trigger required).
  - Deliverable: Mutation distance tests; combination ≥2 parents; supersede sets active=False without DELETE; child-entry hop+1.
  - Files: `src/agents/cognition/practical_knowledge.py`, `tests/unit/test_practical_knowledge_lineage.py`
  - Logging: INFO success with entry_id + origin + hop_index + mutated; WARN/DEBUG rejects with reason_code only
  - Depends on: 3

- [x] Task 5: Capability-anchor string-parity map (kind → optional skill-domain token) without importing `world._skills`; parity test against `SkillDomain` values. Architecture isolation tests (analysis ↛ cognition; cognition ↛ analysis.knowledge_genealogy*; api ↛ analysis; no GlobalTechniqueRegistry under `src/world`).
  - Deliverable: Anchor map unit test; architecture isolation green.
  - Files: `src/agents/cognition/practical_knowledge.py`, `tests/architecture/test_v3_knowledge_genealogy_isolation.py`, `tests/unit/test_practical_knowledge_capability_anchor.py`
  - Logging: DEBUG anchor resolved/absent
  - Depends on: 3

<!-- Commit checkpoint: tasks 3-5 -->

### Phase 3: Compose, carry, audits, isolation

- [x] Task 6: Wire runtime subjective carry / checkpoint restore + audit emission + channel-off empty synthesize. Touch the full cultural/mentorship path set: `agents/cognition/models.py` (`SubjectiveSnapshot`, `CognitiveLoopProposal`, `CognitiveLoopResult` + `require_owner_*`); `loop.py` (`__slots__`, `__init__` kwarg bind, `_prepare_practical_knowledge`, proposal/result copy, `_last_*_audits`); `configuration.py` `build_cognitive_loop` pass-through; `run_control.py` `AgentRuntimeCheckpoint` field + `__post_init__`; `agent_runtime.py` slots/init/`_commit_practical_knowledge`/snapshot kwargs/commit call/`restore_runtime_checkpoint`/`export_runtime_checkpoint`/`export_practical_knowledge_audits`; prove channel-off skips ledger writes.
  - Deliverable: Carry/restore parity tests; audit duck-typing stable; mid-run admission blank ledger.
  - Files: listed above + `tests/unit/test_practical_knowledge_carry.py`
  - Logging: DEBUG entry_count on carry encode/decode
  - Depends on: 2, 4

- [x] Task 7: Implement uptake compose adapters for teaching (fold mentorship), imitation, written_record (fold durable+repositories), reconstruction, developmental, independent_discovery per flags + mode gates. DEBUG skip when source off. Never copy peer ledgers / peer entry_ids. Set `source_agent_id` from public cues only.
  - Deliverable: Compose unit tests per origin; skip-when-off tests; teaching sets teacher/source ids from public cue only.
  - Files: `src/agents/cognition/practical_knowledge.py`, `src/agents/cognition/loop.py`, `tests/unit/test_practical_knowledge_compose.py`
  - Logging: DEBUG `practical_knowledge_compose` origin + skip_reason; never log technique prose
  - Depends on: 4, 6

- [x] Task 8: Prove Observation / Perspective field sets never include technique catalogs or genealogy DAGs (pin via domain-contract / observation field-set tests — **do not** edit `_perception.py` or add inspection projections). Optional Perspective plumb test only if Perspective is extended (default: do not extend).
  - Deliverable: Negative field-set tests green.
  - Files: `tests/unit/test_practical_knowledge_observation_isolation.py`, `tests/unit/test_domain_contract_evolution_policy.py` (assert unchanged Observation keys)
  - Logging: none beyond existing
  - Depends on: 6

<!-- Commit checkpoint: tasks 6-8 -->

### Phase 4: Analysis DAG, queries, metrics, harvest

- [x] Task 9: Implement `KnowledgeGenealogyGraph` builder + four locked queries with deterministic sort, depth clamp, `death_ticks`/`as_of_tick` living filter, analysis peer `transmitted_from` join + unresolved counts. Optional `generation_index_by_agent` join.
  - Deliverable: Unit tests for each query; dual-emergence; living filter; unresolved edges; empty → ABSENT-friendly shapes.
  - Files: `src/analysis/knowledge_genealogy.py` (new), `tests/unit/test_knowledge_genealogy_queries.py`
  - Logging: DEBUG query_id + result_count; censoring_policy states analysis-only / never cognition
  - Depends on: 3, 6

- [x] Task 10: Implement holders / lineage / mutation metric computors with exact DTO summaries (counts/histograms only; living vs dead via `death_ticks`; mean `fingerprint_distance_q`).
  - Deliverable: Unit tests for each family empty/non-empty shapes.
  - Files: `src/analysis/knowledge_genealogy_metrics.py` (new), `tests/unit/test_knowledge_genealogy_metrics.py`
  - Logging: DEBUG family computed counts
  - Depends on: 9

- [x] Task 11: Register three metric families end-to-end (`MetricFamilyId`, `_spec_*`, builders, `MetricComputationInputs`, assemble/`_safe`, exports). Bump `METRIC_FAMILY_COUNT` 62→65 and update **all** hard-pinned count assertions in: `test_metric_specifications`, `test_cultural_feature_metrics`, `test_cultural_narrative_metrics`, `test_dependency_care_metrics`, `test_developmental_learning_metrics`, `test_historical_memory_metrics`, `test_mentorship_metrics`, `test_v3_durable_records_regression`, `test_v3_knowledge_repositories_regression` (docstring + count tests). Do not overload listed sibling families.
  - Deliverable: Specification + assemble tests; all count pins green in this commit.
  - Files: `src/analysis/specifications.py`, `src/analysis/metric_service.py`, `src/analysis/__init__.py`, listed test modules
  - Logging: DEBUG metric assemble family_id + source_count
  - Depends on: 10

- [x] Task 12: Harvest wiring end-to-end — `SimulationRunnerResultDocument.practical_knowledge_audits` + `__post_init__` validation; `runner.py` export + result construction; `agent_runtime.export_practical_knowledge_audits`; `composition.knowledge_genealogy_harvest_from_run` (derive `death_ticks` from events when layers/durable absent); collectors + `metric_collection.inputs_with_opt_in_metric_rows`; prove collectors attach rows when genealogy enabled.
  - Deliverable: Harvest unit tests; no `api`↔`analysis` import violations.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner.py`, `src/simulation/agent_runtime.py`, `src/experiments/composition.py`, `src/experiments/metric_collection.py`, `src/experiments/collectors.py`, `tests/unit/test_knowledge_genealogy_harvest.py`
  - Logging: DEBUG harvest counts by origin; WARN when genealogy enabled but rows empty
  - Depends on: 6, 10, 11

<!-- Commit checkpoint: tasks 9-12 -->

### Phase 5: Experiment AP + matrix

- [x] Task 13: Add `knowledge_genealogy_profile` and `experiment_ap_knowledge_genealogy` catalog entry (off V1 gate) with locked arm matrix **including `ap-lifecycle-survival`**; export from `experiments/__init__.py`; add `experiment-ap-knowledge-genealogy` to `OFF_GATE_MATRIX_EXPERIMENT_IDS`. Pin schema v35 + objects + flag on on-arms.
  - Deliverable: Catalog construction tests; arm ids stable; allowlist pin.
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, scenario helpers as needed, `tests/unit/test_experiment_ap_knowledge_genealogy.py`
  - Logging: INFO `experiment_ap_built` experiment_id + arm_id + schema_version; DEBUG flag/object presence
  - Depends on: 2, 12

- [x] Task 14: Arm assertions — independent discovery, teaching lineage, multi-parent DAG (direct ledger), mutation hop (direct ledger), dual emergence, written-record, reconstruction, lifecycle-survival, capability-join unmatched, channel-off, flags-off hash stability.
  - Deliverable: Executable arm proofs with stable failure messages citing arm_id.
  - Files: `tests/unit/test_experiment_ap_*.py`, flags-off hash stability extensions
  - Logging: test logs only
  - Depends on: 13, 7, 9, 11, 12

- [x] Task 15: Matrix finalize only — insert `knowledge_genealogy_on` **before** `knowledge_repositories_on`; accept v35; widen lifecycle/init needs sets with `V35` (cultural-only v35 must not synthesize lifecycle); extend finalize debug rule-name set; keep AO on v34 when genealogy absent. Do **not** re-own catalog allowlist (Task 13).
  - Deliverable: Finalize priority tests (`knowledge_genealogy_on` beats `knowledge_repositories_on`); durable+repository+genealogy → v35.
  - Files: `src/experiments/matrix_schema.py`, `tests/unit/test_matrix_schema_v35*.py`
  - Logging: DEBUG finalize selected schema_version reason (`knowledge_genealogy_on` / …)
  - Depends on: 1, 13

<!-- Commit checkpoint: tasks 13-15 -->

### Phase 6: Research UI + docs + regression pins

- [ ] Task 16: Research UI epistemic overlays + AnalyticsPanel discovery for `knowledge_genealogy_holders`, `knowledge_genealogy_lineage`, `knowledge_genealogy_mutation`: add to `PRIORITY_FAMILIES`, new `KNOWLEDGE_GENEALOGY_FAMILIES` Set, catalog filter + `selected` group, `ANALYTICAL_OVERLAYS` + `epistemic.test.ts` expects (`research_inference` badge only — no subjective ledger fields, no full genealogy browser).
  - Deliverable: Client unit tests for badge discovery; GraphsPanel genealogy browser remains absent.
  - Files: `clients/research-ui/src/epistemic.ts`, `clients/research-ui/src/epistemic.test.ts`, `clients/research-ui/src/views/AnalyticsPanel.svelte`
  - Logging: N/A in SPA
  - Depends on: 11

- [ ] Task 17: Mandatory docs via `/aif-docs` — architecture V3 seams + Downstream contract (v35 deepen, cultural `{v31..v35}`, no new flag, no write-pair, triple representation, cross-owner analysis join, no GlobalTechniqueRegistry), cognition-runtime ledger/compose, analysis-metrics families + four queries, DESCRIPTION + ARCHITECTURE + **ROADMAP** M7 updates.
  - Deliverable: Docs mention all locked pins; no contradictions with v3-12 repository blurb.
  - Files: `docs/architecture.md`, `docs/cognition-runtime.md`, `docs/analysis-metrics.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/ROADMAP.md`
  - Logging: N/A
  - Depends on: 1, 6, 9, 11, 13, 15, 16

- [ ] Task 18: Final regression — V1 gate + `test_v2_scientific_invariants` under V3 flags-off; `METRIC_FAMILY_COUNT=65`; command count 34; SEMANTIC 53; Alembic head `0017`; Experiment AO unchanged when genealogy absent; write-pair unchanged for genealogy-only; `OFF_GATE_MATRIX_EXPERIMENT_IDS` contains AP; architecture isolation green; no `GlobalTechniqueRegistry`; close verification pins table below for `/aif-verify`.
  - Deliverable: `tests/unit/test_v3_knowledge_genealogy_regression.py` green with pins; plan pins accurate.
  - Files: existing gate tests; new regression pin module; this plan file (pins only)
  - Logging: pytest output only
  - Depends on: 8, 14, 15, 16, 17

<!-- Commit checkpoint: tasks 16-18 -->

## Verification pins (summary)

| Pin | Value |
| --- | --- |
| Runner schema | `runner-config-v35` when `knowledge_genealogy` present (`v35_requires_knowledge_genealogy`) |
| Prerequisite objects | `cultural_feature_provenance` + `knowledge_genealogy` |
| Optional compose | teaching(+mentorship) / written_record(+durable/repos) / imitation / reconstruction / developmental / independent_discovery |
| Cultural schemas | `{v31, v32, v33, v34, v35}` |
| V3 flag | No new flag; deepens `cultural_historical_memory` |
| Write-pair | Unchanged by genealogy-only (still V14/v11 when repositories active) |
| `AgentCommand` count | 34 (unchanged) |
| SEMANTIC count | 53 (unchanged) |
| `METRIC_FAMILY_COUNT` | 65 (+3) |
| Metric families | `knowledge_genealogy_holders@1`, `knowledge_genealogy_lineage@1`, `knowledge_genealogy_mutation@1` |
| Researcher queries | `who_currently_knows`, `who_taught`, `oldest_surviving_lineage_origin`, `independent_emergence_count` |
| Cross-owner edges | Analysis join only; live `parent_entry_ids` owner-local |
| `content_key` | `tech:{technique_token}` (kind-free, source-free) |
| Experiment | `experiment-ap-knowledge-genealogy` (off V1 gate) |
| Profile | `knowledge_genealogy_profile` |
| AP arms | `ap-channel-off`, `ap-independent-discovery`, `ap-teaching-lineage`, `ap-multi-parent-dag`, `ap-mutation-hop`, `ap-dual-emergence`, `ap-written-record`, `ap-reconstruction`, `ap-lifecycle-survival`, `ap-capability-join`, `ap-flags-off` |
| Alembic | head stays `0017` |
| Triple representation | objective capability ≠ subjective knowledge ≠ research lineage |
| Forbidden | `GlobalTechniqueRegistry`, society encyclopedia, Observation technique catalog, peer ledger copy, kinship auto-inheritance, cultural compose merge |
| Matrix finalize | `knowledge_genealogy_on` before `knowledge_repositories_on` (Task 15) |
| Reject codes (core) | `knowledge_genealogy_without_cultural_flag`, `knowledge_genealogy_requires_cultural_provenance`, `knowledge_genealogy_requires_v35`, `v35_requires_knowledge_genealogy`, `v35_requires_cultural_provenance`, `knowledge_genealogy_mode_invalid`, `knowledge_genealogy_inactive`, `knowledge_genealogy_hop_cap`, `knowledge_genealogy_parent_cap`, `knowledge_genealogy_combination_requires_parents`, `knowledge_genealogy_cycle`, plus nested policy codes |

## Out of scope

- Hard-coded GlobalTechniqueRegistry / society encyclopedia / schools-as-institutions
- Owning `institutional_economy` or `multi_polity_migration`
- Kinship cultural / knowledge inheritance handoff
- New AgentCommand / SEMANTIC types / event write-pair for genealogy
- Collapsing `ObjectiveSkillLedger` or competence beliefs into the genealogy ledger
- Merging practical-knowledge into `SubjectiveCulturalBelief` / cultural compose key
- Live peer `entry_id` parent pointers
- Overloading mentorship single-parent lineage as the DAG store
- Alembic `0018+`, `/v2` HTTP, Godot knowledge-map chrome
- Research UI GraphsPanel full interactive genealogy browser (Analytics discovery sufficient)
- Live loop auto-mutation/combination triggers (library + direct AP arms sufficient)

## Implementation notes for `/aif-implement`

- Prefer new `agents/cognition/practical_knowledge.py` + `analysis/knowledge_genealogy.py` over inventing world technique packages.
- Keep Experiment AO and replay-v14 paths green when genealogy object absent.
- Owner-local multi-parent DAG is mandatory for combination; cross-owner edges are analysis-only.
- Seed-material `sha256` mutation only — no wall-clock; no shared RNG stream that moves unrelated experiment hashes.
- Structured logs: metadata only (ids, counts, hops, origins, reason codes) — never technique prose or fingerprints as payload surrogates.
- `who_currently_knows` filters living + active; `include_dead_holders` scopes historical / `who_taught` / holders dead counts only.
- Bind the genealogy **spec** into the cognitive loop, not a bare boolean.
