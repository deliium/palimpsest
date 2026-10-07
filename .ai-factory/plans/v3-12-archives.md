# Implementation Plan: V3-12 Archives and Knowledge Repositories

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-07
Improved: 2026-10-07 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Deepens the already-owned `cultural_historical_memory` surface by letting agents gather durable records into WorldEngine-owned persistent repositories that outlive creators and can decay — without hard-coding a LibraryInstitution or forcing cultural labels onto Observation.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-12-archives.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; suggested stem `v3-12-archives`; git.create_branches=false so stem is description slug (branch-derived naming disabled)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; scope is explicitly v3-12 under M7 so linkage uses M7
INFO [aif-improve] refined 2026-10-07: SEMANTIC 53 pin; clean MaintainRepository(mode); custody interaction matrix; durable/layers gates `{v33,v34}`; exact metric DTO + harvest tables; Research UI Analytics discovery; Phase 5 computors→register→harvest; inaccessible helper API; observer contracts/project files; deps 2/3/7/9; uptake_compose.repositories exact keyset; append-only scale note

## Compatibility contract

This plan **deepens** already-owned **`V3CapabilityFlags.cultural_historical_memory`** (v3-09; analysis deepen v3-10; durable records v3-11). It adds **knowledge repositories**: WorldEngine-owned physical collection containers that hold membership of durable records, with access, maintenance, organization metadata, and retrieval — while cultural labels (archive / library / sacred records / family records / trade ledger) remain **subjective perception only**.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents receive immutable per-agent `Observation` / `Perspective` only. `WorldEvent` records remain immutable and append-only. Subjective state stays outside the objective fold. Godot remains read-only. Deterministic replay continues. No scripted civilization / library_emerged / archive_must_persist outcomes.
2. Flag ownership unchanged: keep `cultural_historical_memory`, `generational_population`, and `kinship_inheritance` owned. Do **not** own `multi_polity_migration`, `institutional_economy`, or `multi_hop_testimony_tracking`. **No new V3 capability flag.**
3. Flags-off / channel-off / repository-object-absent = prior baseline. With all V3 flags off, or with `cultural_historical_memory=False` / `cultural_feature_provenance` absent / `durable_records` absent / `knowledge_repositories` absent, trajectories and `exact_trajectory_hash` match the pre-plan baseline for AE–AN where applicable. V2 Experiment Z and V3 Experiment AL/AM/AN metric families stay unchanged (sibling families only).
4. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2/V3 versions in the same change that adds a write version.
5. **No LibraryInstitution (locked).** Do not introduce hard-coded institution classes, roles (`librarian`, `archivist`), society-wide catalogs, or a global Archive controller that auto-corrects content or assigns cultural labels.
6. **Objective primitives only (locked).** Engine state models: storage location/container, record membership, access gates, maintenance/decay state, organization metadata (index tokens), retrieval mutations. Forbidden objective labels: `library`, `archive`, `sacred`, `family_records`, `trade_ledger` as authoritative kind enums forced onto Observation.
7. **Subjective cultural framing (locked).** Agents may perceive a collection as archive / library / sacred records / family records / trade ledger via existing cultural-feature / naming / interpretation channels — fresh owner-scoped beliefs only; never world-imposed truth.
8. **Creator survival (locked).** Founder/creator death does **not** delete the repository, clear membership, or auto-correct member marks. Orphaned repositories remain legal.
9. **Decay is physical + epistemic (locked).** Repositories decay through destruction, neglect, inaccessible location, missing/corrupt indexing, and member record degradation (compose with v3-11 integrity). Decay never "corrects" marks toward world truth.
10. **Repository history is analysis-facing (locked).** Membership, access, maintenance, and index-change history is harvestable for analytical tools; never fed back into live cognition as authoritative encyclopedias.
11. **Preserve v3-02–v3-11 locks:** blank-slate deny-list; closed Observation `lifecycle`; ELDER ≠ leader; related ≠ affection; no parent→caregiver hardwiring; no global Culture; no internal-state copy; Alembic head `0017` by default; kinship cultural inheritance handoff stays deferred; historical layers stay analysis-only; durable marks ≠ truth; written information ≠ objective truth.
12. **`api` must not import `analysis`.** Persist metric docs offline; serve via existing `MetricReadService` / inspection projections only.
13. Closed `AgentCommand` count moves **29 → 34** (adds `EstablishRepository`, `DepositRecord`, `RetrieveRecord`, `MaintainRepository`, `IndexRepository`). SEMANTIC count moves **47 → 53** (six repository semantic types: established / deposited / retrieved / maintained / indexed / neglected).
14. **Append-only history (scale).** Repository membership/access/index/neglect events increase authoritative row volume. Bound growth via write cadence and inspection limits only — never `DELETE` on `world_events` / snapshots / stream rows (`reject_history_mutation` stays). Long-run Experiment AO arms may document optional checkpoint presets (see v2-long-experiment-scalability); science payloads stay complete and uncoalesced.

## Goal

Implement physical mechanisms enabling agents to gather durable records into persistent WorldEngine-owned repositories that:

| Objective primitive | Role |
| --- | --- |
| Storage location/container | Repository entity anchored at a location (optionally tied to a structure id when present) |
| Records | Ordered/set membership of durable `artifact_id`s (channel requires v3-11 durable records) |
| Access | Deterministic colocation/hold/capacity gates; optional closed access mode (`open` / `colocated_only` / `founder_list`) — not institutional roles |
| Maintenance | Integrity/decay state updated by maintain actions or neglect timers |
| Organization metadata | Imperfect index tokens (can be empty, incomplete, or corrupted) — not a truth catalog |
| Retrieval | Deposit / retrieve mutations that move artifact placement between repository custody and agent hold / location |

Agents may subjectively frame the same container as archive, library, sacred records, family records, or trade ledger depending on culture — without the engine asserting those labels.

Repositories survive creators and decay through destruction, neglect, inaccessible location, missing indexing/knowledge, and member-record degradation.

Expose repository history (establish / membership / access / maintenance / index / destroy) to analytical tools via sibling metric families and Experiment AO.

Deliver:

- Exact optional root sibling `knowledge_repositories` on **`runner-config-v34`**
- WorldEngine repository entity + commands + events (write-pair replay-v14 / codec v11)
- ObservedRepository projection (objective fields only; no cultural label enum)
- Optional cultural uptake compose (subjective framing) — never Observation-forced labels
- Sibling analysis metric families (do not overload durable_record_* / cultural_feature_* / historical_memory_*)
- Research UI Analytics discovery badges for the three families (full archive browser deferred)
- Off-gate Experiment AO comparing channel-off vs repository-on across creator-death, neglect, inaccessible, missing-index, and degradation arms

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` remains the only authority over objective repository state; cognition never mutates repository membership directly.
2. Agents never receive another agent's private cultural framing of a repository, a society library download, or analysis metric documents as facts.
3. `WorldEvent` records remain immutable; authoritative history stays append-only.
4. Objective repository state never auto-downloads into episodic memory; interpretation/framing stays opt-in via existing cultural / artifact interpretation channels.
5. Repository organization metadata is **not** truth. An index claiming "genealogy complete" does not write `world.kinship` edges; an index chronicle does not rewrite history.
6. Founder death does **not** delete, correct, or invalidate repositories or member records.
7. LLM output remains non-authoritative.
8. No scripted `library_must_form` / `archive_must_persist` / `true_catalog_restored` booleans.
9. Godot remains read-only; this plan requires objective observer fields for repository tokens but **not** private "library chrome" that asserts cultural labels.
10. Runs remain reproducible where claimed (explicit seeds, deterministic streams, deterministic fakes / recorded LLM paths).

### Scope split (locked)

| This plan (v3-12) | Deferred |
| --- | --- |
| Objective repository container, membership, access, maintenance, index, retrieval | Hard-coded LibraryInstitution / librarian roles |
| Subjective cultural framing via existing channels | Owning `institutional_economy` |
| Sibling analysis metrics + Experiment AO | Research UI GraphsPanel full archive browser |
| Research UI Analytics discovery badges | Richer archive chrome |
| Compose optional cultural uptake of framing labels | Kinship cultural inheritance handoff |
| `runner-config-v34` + replay-v14 / codec v11 write-pair | Alembic `0018+`; `/v2` HTTP |
| Durable-on prerequisite (v33 object required on v34) | Repositories without durable channel |
| Member degradation via v3-11 integrity | Engine fact-checking of index vs marks |

**Rationale for cultural + durable coupling:** repositories deepen the same M7 `cultural_historical_memory` seam and physically collect v3-11 durable records. V2-only artifact runs and AN durable-only runs stay valid **without** `knowledge_repositories`.

### Capability / ownership (locked)

1. **No new V3 flag.** Enabling repositories requires already-owned `cultural_historical_memory=True` plus exact `cultural_feature_provenance` **and** exact `durable_records` **and** exact `knowledge_repositories` on `runner-config-v34`.
2. **`historical_memory_layers` on v34 is optional** (same as v33). v32 remains layers-only; v33 remains durable-required; v34 **always** requires `knowledge_repositories` (+ durable + provenance).
3. Do **not** implement kinship cultural inheritance handoff.
4. Other unowned V3 flags still fail closed.
5. When repository object absent: AE–AN bit-identity matches pre-plan for the same roster and seeds; V2/V3 artifact/durable behavior unchanged.
6. Do **not** claim that enabling repositories auto-enables interpretation or cultural uptake — omit object / keep modes `DISABLED` for objective-only arms.
7. Cognition compile of new repository commands requires `ArtifactInterpretationMode.DETERMINISTIC` **and** repository channel on (mirror durable Inscribe compile gate). World admission of scripted/test submissions may accept commands when channel on regardless of mode.

### Flag × object gate matrix (locked)

| Config shape | Allowed? | Reject / notes |
| --- | --- | --- |
| Cultural flag off, repository absent | Yes (off) | Passthrough |
| Repository object present, cultural flag off | No | `knowledge_repositories_without_cultural_flag` |
| Repository object present, `cultural_feature_provenance` absent | No | `knowledge_repositories_requires_cultural_provenance` |
| Repository object present, `durable_records` absent | No | `knowledge_repositories_requires_durable_records` |
| Cultural + provenance + durable on **v33**, repository absent | Yes | Pre-plan AN behavior |
| Cultural + provenance + durable + repository on **v31/v32/v33** | No | `knowledge_repositories_requires_v34` |
| Cultural + provenance + durable + repository on **v34** | Yes | Repository channel enabled |
| Repository object on schema ≠ v34 | No | `knowledge_repositories_requires_v34` |
| Schema `v34` without repository object | No | `v34_requires_knowledge_repositories` |
| Schema `v34` without durable object | No | `v34_requires_durable_records` |
| Durable object on schema **v34** (with repository) | Yes | Rewrite live `durable_records_requires_v33` → accept `{v33, v34}` (keep reject id or alias — pin in Task 1) |
| Layers object on **v34** (with durable + repository) | Yes | Widen `_HISTORICAL_MEMORY_LAYER_SCHEMAS` / cultural schemas to include v34 |
| Repository `mode=disabled` present | No | `knowledge_repositories_mode_invalid` — omit object for off |
| Cultural-only on v34 (lifecycle off) + durable + repository | Yes | Widen `_cultural_only` to `{v31,v32,v33,v34}` |
| Generational + cultural + durable + repository on v34 | Yes | Creator-death survival arms |
| Layers + durable + repository on v34 | Yes | Layers remain analysis-only |
| Mentorship / developmental without lifecycle | No | Unchanged existing rejects |

### Runner schema (locked)

Introduce `RUNNER_SCHEMA_VERSION_V34 = "runner-config-v34"`:

- Exact root key set = **v33 accepted roots** ∪ sibling **`knowledge_repositories`**.
- `knowledge_repositories` present ⇒ `schema_version == runner-config-v34` and cultural flag on with exact provenance + durable + repository objects.
- Decode v23–v33 synthesizes `knowledge_repositories=None` (absent ≡ repository channel off).
- Gate rewrite: `cultural_historical_memory=True` accepts `{v31, v32, v33, v34}`. Rewrite cultural provenance / `_cultural_only` / `_HISTORICAL_MEMORY_CULTURAL_SCHEMAS` / `_HISTORICAL_MEMORY_LAYER_SCHEMAS` / durable allowlists capped at v33 to include v34.
- **Durable gate co-rewrite (Task 1):** `durable_records` present ⇒ schema ∈ `{v33, v34}`; keep `v33_requires_durable_records` when schema==v33 and durable absent; add `v34_requires_durable_records` + `v34_requires_knowledge_repositories`.
- Default write stays `runner-config-v4` when all V3 flags are off.
- **Matrix finalize (Task 17 only):** insert `knowledge_repositories_on` **before** `durable_records_on` (v34 beats v33); widen `needs_lifecycle` / `needs_init` with `V34`; AO on v34; AN on v33 when repository absent; AM on v32 when durable/repository absent; AL on v31 when layers/durable/repository absent. Task 1 must **not** edit finalize priority.

### Serialization contract (locked)

Mirror v33 pattern in `runner_serialization.py`:

- `_RUNNER_ROOT_KEYS_V34_*` = corresponding v33 frozenset ∪ `"knowledge_repositories"`
- Exact child keyset `_KNOWLEDGE_REPOSITORIES_KEYS` matching nested policy tables below
- `_encode_knowledge_repositories` / `_decode_knowledge_repositories` with `_require_keys` (no silent extras)
- Encode: `schema_version == V34` requires provenance + durable + repository present; layers optional
- Decode: v23–v33 → `knowledge_repositories=None`
- DEBUG log present/absent on decode (metadata only)
- Reject forbidden aliases: `library_institution`, `global_archive`, `society_library`, `canonical_catalog`, `true_history_index`, …

### Runtime channel flags (locked)

Mirror durable-records pattern:

1. `knowledge_repositories_active = config.knowledge_repositories is not None` at run start.
2. Pass `knowledge_repositories_active=` into **both** `checkpoint_schema_for_production` and `engine.select_checkpoint_schema` (agreed-or chain — same bug class as v3-06/v3-11 if only one is updated).
3. Add `WorldEngine._knowledge_repositories_channel_active`; repository commands reject with `knowledge_repositories_inactive` when false.
4. When repository channel on, durable channel must already be on (config gate); force `_artifacts_enabled = True` (already true under durable).
5. Checkpoint priority when repository on: **`knowledge_repositories_active` → `(EVENT_SCHEMA_REPLAY_V14, "v11")`** ahead of durable `(V13, v10)`.
6. Extend `select_checkpoint_schema` / `checkpoint_schema_for_production` agreed-or chain with `knowledge_repositories_active` → V14/v11 (mirror durable V13/v10 block in `engine.py`).

### `KnowledgeRepositoriesSpec` (locked)

Root sibling object; omit for off. Exact keys (reject extras / missing):

| Key | Type / values | Role |
| --- | --- | --- |
| `knowledge_repositories_mode` | `deterministic` only | Present object implies on; `disabled` rejected |
| `access_policy` | Exact nested object | Who may deposit/retrieve |
| `capacity_policy` | Exact nested object | Max members / max establishes |
| `maintenance_policy` | Exact nested object | Neglect timers / decay |
| `index_policy` | Exact nested object | Index caps / corruption |
| `perception_mode` | `container_and_meta` (default) \| `container_only` | Whether Observation projects index/maintenance meta |
| `rng_namespace` | Token string | Seed-derived stream for neglect/index corruption (`knowledge_repositories`) |

**`access_policy` exact keys:**

| Key | Role |
| --- | --- |
| `default_access_mode` | `open` \| `colocated_only` \| `founder_list` |
| `deposit_requires_colocation` | Bool (default `true`) |
| `retrieve_requires_colocation` | Bool (default `true`) |
| `founder_list_survives_death` | Bool (default `true`) — dead founders remain on list; list does not auto-expand |

**`capacity_policy` exact keys:**

| Key | Role |
| --- | --- |
| `max_repositories` | Positive int (default `8`) |
| `max_members_per_repository` | Positive int (default `32`) |
| `max_index_entries` | Non-neg int (default `64`) |

**`maintenance_policy` exact keys:**

| Key | Role |
| --- | --- |
| `neglect_ticks` | Positive int (default `24`) — ticks without `MaintainRepository` before neglect onset |
| `allow_destruction` | Bool (default `true`) |
| `inaccessible_blocks_access` | Bool (default `true`) — when status `inaccessible`, deposit/retrieve reject |
| `neglect_corrupts_index` | Bool (default `true`) — deterministic index token drops on neglect |

**`index_policy` exact keys:**

| Key | Role |
| --- | --- |
| `index_optional` | Bool (default `true`) — empty index is legal |
| `max_entries_per_index_op` | Positive int (default `4`) |
| `allow_corrupt_entries` | Bool (default `true`) — index may reference missing / destroyed members |

Provide `example_knowledge_repositories_spec()` in `runner_models.py` for tests and Experiment AO.

### Domain model (locked)

Package: new `world/repositories.py` (plus private ops/rules/events/perception/replay wiring). Do **not** invent `LibraryInstitution` or a parallel global Archive store outside WorldEngine snapshot state.

**`WorldState`:** add `repositories: Mapping[EntityId, KnowledgeRepository]` (empty when channel off). Encode on codec v11; synthesize empty on ≤v10 decode.

**`RepositoryStatus` (StrEnum):** `intact`, `neglected`, `inaccessible`, `destroyed`.

**`RepositoryAccessMode` (StrEnum):** `open`, `colocated_only`, `founder_list`.

**`KnowledgeRepository` fields (objective only):**

| Field | Role |
| --- | --- |
| `repository_id` | `EntityId` |
| `location_id` | `EntityId` — storage location (required) |
| `structure_id` | `EntityId \| None` — optional link to an existing structure at that location (not a StructureKind.LIBRARY) |
| `founder_ids` | Ordered unique `EntityId` tuple — creators; immutable after establish (no auto kinship expand) |
| `established_tick` | Non-neg int |
| `access_mode` | `RepositoryAccessMode` |
| `status` | `RepositoryStatus` — default `intact` |
| `member_artifact_ids` | Ordered unique tuple of durable artifact ids in custody |
| `index_entries` | Ordered tuple of `RepositoryIndexEntry` (may be empty/corrupt) |
| `last_maintained_tick` | Non-neg int |
| `neglect_streak` | Non-neg int |

**`RepositoryIndexEntry` fields:**

| Field | Role |
| --- | --- |
| `entry_id` | Opaque token / EntityId |
| `artifact_id` | `EntityId \| None` — may be None or dangling when corrupt/missing |
| `label_tokens` | Frozen mark-token tuple (organization metadata only; not meaning) |
| `revision` | Non-neg int |

**Custody rule (locked):** When an artifact is a repository member, placement is repository custody: `holder_id=None`, `location_id=repository.location_id`, and additive `custodian_repository_id: EntityId | None` on `InformationArtifact` (required non-None when member; omit/None when channel off). Member artifacts remain subject to v3-11 integrity independently.

### Custody × existing artifact commands (locked)

When `custodian_repository_id is not None`:

| Command | Behavior |
| --- | --- |
| `DepositRecord` / `RetrieveRecord` / `IndexRepository` / `MaintainRepository` | Normal repository path |
| `Take` / `Drop` / `Give` / `TransferArtifact` | **Reject** `repository_custody_blocks_transfer` — must `RetrieveRecord` first |
| `Erase` | **Reject** `repository_custody_blocks_erase` — destroy via `MaintainRepository(mode=destroy)` (orphans members) or retrieve-then-erase |
| `Amend` / `AnnotateRecord` | **Allowed** if actor passes deposit access gate + colocation/hold-equivalent (custodian counts as colocated at repository location); bumps content/annotation revisions; membership unchanged |
| `CopyRecord` | **Allowed** if access + colocation; child is **not** auto-deposited (fresh artifact outside custody unless subsequent Deposit) |
| `DamageRecord` | **Allowed** if access + colocation; integrity changes on member; membership unchanged; does not change repository status |
| `Inscribe` | Unrelated (creates new artifacts); no auto-deposit |

### Commands (locked)

Add five commands to the closed union (**29 → 34**):

1. **`EstablishRepository(location_id, access_mode=None, structure_id=None)`**
   - Creates `KnowledgeRepository` with `founder_ids=(actor,)`, empty members/index, `status=intact`, `established_tick=now`, `last_maintained_tick=now`.
   - `access_mode=None` ⇒ use `access_policy.default_access_mode`.
   - Reject: channel off, capacity cap, unknown location, actor not colocated, structure mismatch / wrong location.

2. **`DepositRecord(repository_id, artifact_id)`**
   - Moves durable artifact into membership + sets `custodian_repository_id`; requires access gate + colocation/hold per policy; capacity check.
   - Reject: not durable-capable / no genre, destroyed repository, inaccessible, access denied, already member, artifact already in another repository, destroyed artifact integrity when policy blocks (`repository_member_destroyed`).

3. **`RetrieveRecord(repository_id, artifact_id, hold=True)`**
   - Removes membership; clears `custodian_repository_id`; places into actor hold (if portable + hold) or repository `location_id` floor.
   - Reject: not member, access denied, inaccessible, channel off, non-portable hold request (`repository_retrieve_hold_invalid`).

4. **`MaintainRepository(repository_id, mode="maintain")`** where `mode ∈ {maintain, destroy}`
   - `maintain`: sets `last_maintained_tick=now`, clears neglect streak; may restore `neglected` → `intact`; does **not** restore `destroyed` / `inaccessible`; does **not** auto-heal member mark integrity.
   - `destroy`: when `allow_destruction`, status → `destroyed`; clear custody on all members (remain at `location_id`, integrity unchanged); retain repository row for history; emit maintained event with mode=destroy.
   - Reject: channel off, destroyed already (for maintain), `allow_destruction=false` on destroy, access denied, not colocated.

5. **`IndexRepository(repository_id, entries)`**
   - Appends/replaces index entries within caps; may introduce incomplete or corrupt references when `allow_corrupt_entries`.
   - Index writes allowed for any actor who passes the **deposit** access gate (not a separate librarian role).
   - Reject: destroyed repository, index cap, channel off, access denied, `max_entries_per_index_op` exceeded.

### Events / write-pair (locked)

Co-land **`EVENT_SCHEMA_REPLAY_V14`** + persistence codec **`v11`** when repository channel is active at run start.

**Co-land in one change (Task 7):** `EVENT_SCHEMA_REPLAY_V14` constant; extend `SUPPORTED_EVENT_SCHEMA_VERSIONS`, `REPLAYABLE_*`, artifact/durable/dependency frozensets so **v14 accepts all v13 detail types** plus new repository details; `ACCEPTED_PERSISTENCE_CODEC_VERSIONS` + journal dual-key decode for **`v11`** repository snapshot fields; `world/_replay.py`; `simulation/serialization.py`; `simulation/compatibility.py` matrix row; **both** checkpoint selectors + agreed-or chain.

New detail types (effect-complete on schema 14; illegal below):

| Detail | Domain kind token | Payload fields (exact) |
| --- | --- | --- |
| `RepositoryEstablished` | `repository_established` | `repository_id`, `location_id`, `structure_id`, `founder_ids`, `access_mode`, `established_tick` |
| `RepositoryMemberDeposited` | `repository_member_deposited` | `repository_id`, `artifact_id`, `member_count`, `actor_id` |
| `RepositoryMemberRetrieved` | `repository_member_retrieved` | `repository_id`, `artifact_id`, `member_count`, `actor_id`, `hold` |
| `RepositoryMaintained` | `repository_maintained` | `repository_id`, `mode` (`maintain`\|`destroy`), `prior_status`, `next_status`, `last_maintained_tick` |
| `RepositoryIndexed` | `repository_indexed` | `repository_id`, `index_entry_count`, `revision_bump` |
| `RepositoryNeglected` | `repository_neglected` | `repository_id`, `neglect_streak`, `prior_status`, `next_status`, `index_entries_dropped` |

Autonomous neglect may emit `RepositoryNeglected` from WorldEngine tick step when channel on (deterministic; no agent command) — mirror environmental dynamics style, not cognition.

**Write-pair priority (locked):**

`knowledge_repositories_active` → `(EVENT_SCHEMA_REPLAY_V14, "v11")`; else durable → `(V13, "v10")`; else dependency-care → `(V12, "v9")`; … (remainder unchanged).

SEMANTIC observer types: add `REPOSITORY_ESTABLISHED`, `REPOSITORY_MEMBER_DEPOSITED`, `REPOSITORY_MEMBER_RETRIEVED`, `REPOSITORY_MAINTAINED`, `REPOSITORY_INDEXED`, `REPOSITORY_NEGLECTED` → **47 → 53**.

### Perception / Observation (locked)

Add `ObservedRepository` when repository channel on:

- Always: `repository_id`, `location_id`, `status`, `member_count`, `access_mode`
- `container_and_meta`: also `structure_id`, `founder_ids` (truncated if needed), `index_entry_count`, `last_maintained_tick`, `neglect_streak`, optional visible index entry_ids (counts preferred; no full label_token dumps)
- `container_only`: id, location, status, member_count only

**Never project:** cultural frame labels (`library`, `sacred`, …), analysis history, truth flags.

Destroyed repositories: **not** projected on ordinary Observation; retained in snapshot / inspection / analysis.

Domain encode includes `repositories` (possibly empty) when channel on; omit when off (decode synthesizes empty).

Visible member artifacts at repository location: continue projecting as `ObservedArtifact` with optional `custodian_repository_id` when durable perception includes them; agents do not get a free "download all marks" beyond existing artifact perception rules.

### Subjective framing / cognition (locked)

1. Do **not** add a repository mode to `AgentCognitionSpec`.
2. Compile new repository commands only when `ArtifactInterpretationMode.DETERMINISTIC` and repository channel on.
3. Extend `CulturalFeatureUptakeCompose` exact keyset with **`repositories: bool = False`** (update `_CULTURAL_FEATURE_UPTAKE_COMPOSE_KEYS` + encode/decode; accepted-set discipline — all cultural provenance encodes include the key). Framing kinds map to existing `CulturalFeatureKindId` values (`symbolic_association`, `practice`, …) with DEBUG skip when unsatisfiable. Prefer this over overloading `artifacts`.
4. Agents may name/frame repositories via existing `SemanticNamingMode` / narrative channels — still owner-scoped; never writes objective `repository.kind=library`.
5. Index tokens never auto-write kinship edges or historical-layer labels.

### Decay mechanisms (locked)

| Decay path | Mechanism |
| --- | --- |
| Destruction | `MaintainRepository(mode=destroy)` when `allow_destruction`; status `destroyed`; members lose custody and remain at `location_id` with integrity unchanged; repository row retained for history |
| Neglect | After `neglect_ticks` without maintain, status → `neglected`; optional deterministic index corruption (`neglect_corrupts_index`) |
| Inaccessible location | Test/experiment helper **`WorldEngine.mark_repository_inaccessible(repository_id, *, reason_code="repository_location_sealed")`** (channel-on only; not a cognition command; not a scripted civilization outcome). Sets status `inaccessible`; access blocked when `inaccessible_blocks_access`. Optional clear helper for arms that re-open access. |
| Missing indexing | Empty or incomplete `index_entries` is legal; retrieval by id still works if actor knows `artifact_id`; discovery without index is harder (analysis measures coverage) |
| Record degradation | Member artifacts remain subject to v3-11 `DamageRecord` / integrity; neglected repositories do **not** auto-damage members in this plan (compose arms may damage separately) |

### Creator survival (locked)

1. On founder `Died`, do not cascade-delete repositories or membership.
2. `founder_list` access continues to recognize dead founders' ids when `founder_list_survives_death=true` (default) — living non-founders still denied unless mode is `open` / colocated rules.
3. Experiment AO must prove repository + members persist after founder death.

### Analysis metrics (locked)

Sibling families (bump `METRIC_FAMILY_COUNT` **59 → 62**):

| Family id | Version string | Signal |
| --- | --- | --- |
| `knowledge_repository_survival` | `knowledge_repository_survival@1` | Repositories intact after founder death; neglected/inaccessible/destroyed counts; orphaned-member retention |
| `knowledge_repository_access` | `knowledge_repository_access@1` | Deposit/retrieve success vs deny rates; access_mode mix; inaccessible block rate |
| `knowledge_repository_organization` | `knowledge_repository_organization@1` | Index coverage vs membership; corrupt/dangling entry rate; neglect-driven index drop; history sequence length |

Do **not** overload `durable_record_*`, cultural-feature families, or historical-memory families.

**Exact DTO summaries (counts/histograms only — no mark/label_token payloads):**

| DTO | Fields (exact) |
| --- | --- |
| `RepositorySurvivalSummary` | `repository_count`, `intact_count`, `neglected_count`, `inaccessible_count`, `destroyed_count`, `surviving_after_founder_death_count`, `orphaned_member_count` |
| `RepositoryAccessSummary` | `deposit_success_count`, `deposit_deny_count`, `retrieve_success_count`, `retrieve_deny_count`, `inaccessible_block_count`, `access_mode_histogram` (mapping mode→count) |
| `RepositoryOrganizationSummary` | `member_count_total`, `index_entry_count_total`, `index_coverage_ratio`, `dangling_index_entry_count`, `neglect_index_drop_count`, `history_event_count` |

**Harvest row shape (`repository_objective_rows_from_repositories`):** keys `repository_id`, `location_id`, `structure_id`, `status`, `access_mode`, `member_count`, `index_entry_count`, `founder_ids`, `established_tick`, `last_maintained_tick`, `neglect_streak` — duck-typed only; never import `world.repositories` from analysis.

**Event harvest keys:** `event_kind`, `tick`, `repository_id`, `artifact_id`, `actor_id`, `prior_status`, `next_status`, `mode`, `member_count`, `index_entry_count`, `index_entries_dropped`.

**MetricComputationInputs additions:** `repository_objective_rows`, `repository_event_rows`, `founder_death_ticks`, optional `inaccessible_expectations` (Experiment AO arms only — analysis truth/spec hooks, never cognition).

**Analytical history exposure (locked):** Metric documents and Experiment AO collectors expose chronological repository event sequences (ids, ticks, status transitions, membership deltas, index counts) for researcher tools — counts and ids only; no mark payloads.

`api` must not import `analysis`. Harvest via `experiments.composition` + collectors.

### Experiment AO — arm matrix (locked)

- Catalog: `experiment_ao_knowledge_repositories` / id `experiment-ao-knowledge-repositories` on **runner-config-v34**, off the V1 gate.
- Profile: `knowledge_repositories_profile` requiring schema==v34 + cultural flag + provenance + durable + repository objects; reject unowned V3 flags.

| Arm | Schema | Repository | Extra | Expected |
| --- | --- | --- | --- | --- |
| `ao-channel-off` | v33 | absent | durable on | No repository families required; AN-like baseline |
| `ao-establish-deposit` | v34 | on | open access | Establish + deposit; membership + survival family populated |
| `ao-creator-death` | v34 | on | lifecycle on; kill founder | Repository + members remain; survival family > 0 |
| `ao-neglect-decay` | v34 | on | short `neglect_ticks` | Status neglected; index drops when policy on; organization family shows corruption |
| `ao-inaccessible` | v34 | on | `mark_repository_inaccessible` mid-run | Deposit/retrieve deny; access family shows blocks |
| `ao-missing-index` | v34 | on | never IndexRepository | Members present; index coverage 0; retrieve-by-id still works for knowing actor |
| `ao-record-degrade` | v34 | on | DamageRecord on member | Member integrity damaged; repository status may stay intact; compose durable survival + repository harvest |
| `ao-custody-block` | v34 | on | Take/Transfer while custodian | Reject `repository_custody_blocks_transfer`; retrieve then take succeeds |
| `ao-subjective-frame` | v34 | on | `uptake_compose.repositories=true` | Owner-scoped cultural belief may form; Observation has no library label |
| `ao-flags-off` | v4 | absent | all V3 off | Hash stability vs pre-plan |

- Prove: flags-off / repository-off hashes stable; V1 gate + `test_v2_scientific_invariants` green under V3 flags-off; architecture isolation green; SEMANTIC **53**; command count **34**; Alembic head `0017`.
- Matrix allowlist includes AO without enabling on default batches.

### Architecture isolation (locked)

- `agents` / `agents.cognition` must not import analysis repository-metric modules.
- Analysis must not import private `world._*` authority modules.
- `api` / cognition paths must not import `analysis`.
- No `LibraryInstitution`, `GlobalArchive`, or cultural-label enums on `KnowledgeRepository` / `ObservedRepository`.
- Forbidden string aliases rejected in runner decode.
- World tree: no institution controller that auto-assigns librarians or corrects catalogs.

### Docs (locked — mandatory)

Update (no “optional” hedges):

- `docs/architecture.md` — V3 seams row + Downstream V3 contract (v34 deepens cultural; cultural flag accepts `{v31..v34}`; write-pair V14/v11; durable gates `{v33,v34}`; no new flag; no LibraryInstitution)
- `docs/physical-simulation.md` — repository entity, commands, custody matrix, decay paths, inaccessible helper
- `docs/analysis-metrics.md` — three new families + DTO/history exposure
- `docs/cognition-runtime.md` — repositories objective; framing subjective; marks/indexes ≠ truth
- `docs/observer.md` — new semantic types + ObservedRepository fields
- `.ai-factory/DESCRIPTION.md` — V3 scaffolding blurb for v34 knowledge repositories
- `.ai-factory/ARCHITECTURE.md` — allowlists / owned-flag notes for v34

## Commit Plan

- **Commit 1** (after tasks 1–2): `feat(v3): add knowledge_repositories runner-config-v34 gates`
- **Commit 2** (after tasks 3–5): `feat(world): knowledge repository model, custody, and commands`
- **Commit 3** (after tasks 6–8): `feat(world): repository decay, index, events and replay-v14`
- **Commit 4** (after tasks 9–11): `feat(simulation): repository perception, compile gates, observer, codec v11`
- **Commit 5** (after tasks 12–14): `feat(analysis): knowledge repository survival access organization metrics`
- **Commit 6** (after tasks 15–17): `feat(experiments): Experiment AO knowledge repositories`
- **Commit 7** (after tasks 18–21): `docs(v3): knowledge repositories seams` + Research UI discovery + verification pins

## Tasks

### Phase 1: Schema, serialization, and gates

- [x] Task 1: Add `RUNNER_SCHEMA_VERSION_V34`, `KnowledgeRepositoriesSpec` (+ nested policy models), `SimulationRunnerConfig.knowledge_repositories`, `example_knowledge_repositories_spec()`, exact encode/decode + `_KNOWLEDGE_REPOSITORIES_KEYS` / v34 root frozensets, and full reject-code set. **Rewrite** cultural provenance / `_cultural_only` / `_HISTORICAL_MEMORY_CULTURAL_SCHEMAS` / `_HISTORICAL_MEMORY_LAYER_SCHEMAS` to include v34. **Rewrite** durable gate: `durable_records` accepts schema `{v33, v34}` (update `durable_records_requires_v33` message/allowlist); keep `v33_requires_durable_records`; add `v34_requires_durable_records`, `v34_requires_knowledge_repositories`, and repository reject codes from the flag×object matrix. Widen every allowlist capped at v33 to include v34. Update `compatibility.py` v34 row with write-pair `(EVENT_SCHEMA_REPLAY_V14, codec v11)` when repository active. **Do not** edit matrix finalize priority here (Task 17 owns that).
  - Deliverable: Config round-trip tests for present/absent repository; reject rows including repository-on-v33, v34 without durable, v34 without repository, durable-on-v34+repository legal; decode v23–v33 synthesizes repository=None; forbidden aliases rejected.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `tests/unit/test_knowledge_repositories_spec.py`, `tests/unit/test_runner_config_v34*.py`
  - Logging: DEBUG decode present/absent; INFO/raise stable reject codes on fail-closed; never log index/mark payloads
  - Depends on: none

- [x] Task 2: Config enable/skip + runner/engine channel wiring. Validate repository in `__post_init__` / `from_config`; compute `knowledge_repositories_active`; bind `WorldEngine` repository channel flag; pass `knowledge_repositories_active` into checkpoint schema selection at bootstrap (full wiring completed in Task 7). Prove cultural/durable ownership unchanged; unowned V3 flags fail closed; passthrough when object absent (AE–AN hash-stable fixtures).
  - Deliverable: Unit tests for enable/skip, channel-off command reject.
  - Files: `src/simulation/runner.py`, `src/simulation/runner_models.py`, `src/simulation/engine.py`, `tests/unit/test_knowledge_repositories_from_config.py`
  - Logging: INFO `knowledge_repositories_enabled` with max_repositories + neglect_ticks + default_access_mode; DEBUG skip when absent
  - Depends on: 1

<!-- Commit checkpoint: tasks 1-2 -->

### Phase 2: Domain model and commands

- [x] Task 3: Add `RepositoryStatus`, `RepositoryAccessMode`, `RepositoryIndexEntry`, `KnowledgeRepository`, `WorldState.repositories`, and additive `InformationArtifact.custodian_repository_id` (channel-on). Extend forbidden field names. Keep V2/V3 constructors valid when repository fields defaulted/None.
  - Deliverable: Unit tests for legal/illegal placements, custody invariants, founder immutability, capacity at model layer.
  - Files: `src/world/repositories.py`, `src/world/artifacts.py`, `src/world/_state.py` (or WorldState owner), `src/world/__init__.py`, `tests/unit/test_knowledge_repository_model.py`
  - Logging: DEBUG `repository_constructed` status + member_count + index_count (no token dumps)
  - Depends on: 1

- [x] Task 4: Add `EstablishRepository`, `DepositRecord`, `RetrieveRecord`, `MaintainRepository` (mode maintain\|destroy), `IndexRepository` to `AgentCommand` union; update `_COMMAND_TYPES`, `require_agent_command`, `agent_command_tag`, and domain-contract evolution pins (**29 → 34**). Extend `simulation/serialization.py` + finalization command codec paths.
  - Deliverable: Constructor reject tests; closed-count pin updated; command JSON round-trip tests.
  - Files: `src/world/actions.py`, `src/world/__init__.py`, `src/simulation/serialization.py`, `tests/unit/test_domain_contract_evolution_policy.py`, `tests/unit/test_knowledge_repository_commands.py`
  - Logging: DEBUG command_constructed tags; ERROR stable reason codes
  - Depends on: 3

- [x] Task 5: Private operations/rules admit and mutate repository state through `WorldEngine` only. Wire `COMMAND_RULE_MATRIX` / operation arms for establish/deposit/retrieve/maintain/index; custody placement updates; access gates; capacity caps; **custody × artifact command matrix** (Take/Drop/Give/Transfer/Erase reject; Amend/Annotate/Copy/Damage allowed per locked table). Reason codes: `knowledge_repositories_inactive`, `repository_capacity`, `repository_access_denied`, `repository_inaccessible`, `repository_destroyed`, `repository_not_member`, `repository_already_member`, `repository_index_cap`, `repository_not_colocated`, `repository_custody_blocks_transfer`, `repository_custody_blocks_erase`, `repository_member_destroyed`, `repository_retrieve_hold_invalid`.
  - Deliverable: Resolution tests for establish/deposit/retrieve/maintain/destroy; custody-block tests; channel-off rejects.
  - Files: `src/world/_operations.py`, `src/world/_rules.py`, `src/simulation/engine.py`, `tests/unit/test_knowledge_repository_resolution.py`, `tests/unit/test_knowledge_repository_custody.py`
  - Logging: INFO `repository_*` success with repository_id + status + member_count; WARN/DEBUG rejects with reason_code only
  - Depends on: 4

<!-- Commit checkpoint: tasks 3-5 -->

### Phase 3: Decay, index, events, replay

- [x] Task 6: Implement neglect tick progression and optional index corruption using seed-derived `StreamScope` from `rng_namespace`. Implement **`WorldEngine.mark_repository_inaccessible`** (+ optional clear) for Experiment AO arms. Destroy path clears custody, retains repository tombstone row + history.
  - Deliverable: Unit tests: neglect after N ticks; maintain resets; destroy orphans members at location; inaccessible blocks access; same seed ⇒ same index drops.
  - Files: `src/world/repositories.py`, `src/world/_operations.py`, `src/simulation/engine.py`, `tests/unit/test_knowledge_repository_decay.py`
  - Logging: DEBUG `repository_neglect_tick` streak; INFO status transitions; never log index tokens
  - Depends on: 5

- [x] Task 7: Land `EVENT_SCHEMA_REPLAY_V14`, detail types with exact payload tables above, serialization encode/decode, full ACCEPTED frozenset co-land, and agreed write-pair selection in **both** `checkpoint_schema_for_production` and `engine.select_checkpoint_schema` (`knowledge_repositories_active` → V14/v11 ahead of durable), including agreed-or chain update.
  - Deliverable: Encode/decode + replay round-trip tests; combined durable+repository write-pair regression stub.
  - Files: `src/world/events.py`, `src/world/_replay.py`, `src/simulation/serialization.py`, `src/simulation/compatibility.py`, `src/simulation/engine.py`, `src/simulation/persistence.py`, `src/simulation/service.py`, `tests/unit/test_repository_events_replay_v14.py`, `tests/unit/test_repository_write_pair.py`
  - Logging: DEBUG schema selected V14/v11; never log payloads
  - Depends on: 2, 5, 6

- [x] Task 8: Snapshot / checkpoint codec `v11` fields for `WorldState.repositories` map + artifact `custodian_repository_id`; dual-key decode for ≤v10 synthesizing empty repositories / `custodian_repository_id=None`. Replay/apply path for new repository details.
  - Deliverable: Checkpoint restore parity tests live vs restored; v10 snapshot restores with synthesized empty repositories.
  - Files: `src/world/_replay.py`, `src/simulation/journal.py`, `src/simulation/persistence.py`, `tests/unit/test_repository_checkpoint_v11.py`, `tests/unit/test_repository_replay.py`
  - Logging: DEBUG custody_count + repository_count on encode/decode
  - Depends on: 3, 7

<!-- Commit checkpoint: tasks 6-8 -->

### Phase 4: Perception, cognition compile, observer

- [ ] Task 9: Project `ObservedRepository` per perception_mode; omit destroyed; extend inspection DTOs with objective repository rows (no cultural labels); optional `custodian_repository_id` on ObservedArtifact when meta on.
  - Deliverable: Perception tests for container_only vs container_and_meta; destroyed omitted from Observation but present in inspection.
  - Files: `src/world/observations.py`, `src/world/_perception.py`, `src/simulation/inspection.py`, `tests/unit/test_knowledge_repository_perception.py`
  - Logging: DEBUG observed_repository_count; never log index tokens
  - Depends on: 3, 5

- [ ] Task 10: Cognition compile gates for repository commands (interpretation DETERMINISTIC + channel on); extend `CulturalFeatureUptakeCompose` with exact `repositories` key (default false) + encode/decode; prove Observation never carries library/archive/sacred labels.
  - Deliverable: Compile allow/deny tests; cultural uptake unit test with subjective framing only; uptake key round-trip.
  - Files: `src/agents/cognition/` compile/deliberation paths, `src/agents/cognition/cultural_features.py`, `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `tests/unit/test_knowledge_repository_cognition_compile.py`
  - Logging: DEBUG compile_skip reason codes; cultural uptake DEBUG skips
  - Depends on: 4, 9

- [ ] Task 11: Observer/presentation: extend `observer/contracts.py` + `observer/project.py` with `ObservedRepository` / objective fields; SEMANTIC map **47 → 53** in `observer/version.py`; causal debugger kind maps for six repository domain kinds; no Godot cultural chrome. Protocol stays `observer-protocol-v1`.
  - Deliverable: SEMANTIC length pin tests; mapper coverage; presentation forbids still hold.
  - Files: `src/observer/contracts.py`, `src/observer/project.py`, `src/observer/version.py`, `src/simulation/causal_debugger.py`, `tests/unit/test_repository_observer.py`, `tests/unit/test_v3_knowledge_repositories_regression.py` (partial)
  - Logging: none beyond existing observer metadata
  - Depends on: 7, 9

<!-- Commit checkpoint: tasks 9-11 -->

### Phase 5: Analysis metrics + harvest

- [ ] Task 12: Implement survival / access / organization computors with exact DTO fields (`RepositorySurvivalSummary`, `RepositoryAccessSummary`, `RepositoryOrganizationSummary` — counts/histograms only, no mark payloads); duck-type harvest rows; no cognition imports. History sequences are id/tick/status only.
  - Deliverable: Unit tests for each family empty/non-empty shapes.
  - Files: `src/analysis/knowledge_repository_metrics.py` (new), `tests/unit/test_knowledge_repository_metrics.py`
  - Logging: DEBUG family computed counts; censoring_policy states analysis-only / never cognition
  - Depends on: 1, 8

- [ ] Task 13: Register three metric families end-to-end (`MetricFamilyId`, `_spec_*`, builders, `MetricComputationInputs`, assemble/`_safe`, exports). Bump `METRIC_FAMILY_COUNT` 59→62. Do not overload listed sibling families.
  - Deliverable: Specification + assemble tests; exclusion-set updates for A–E gate.
  - Files: `src/analysis/specifications.py`, `src/analysis/metric_service.py`, `src/analysis/__init__.py`, `tests/unit/test_metric_specifications.py`
  - Logging: DEBUG metric assemble family_id + source_count
  - Depends on: 12

- [ ] Task 14: Harvest wiring — `repository_objective_rows_from_repositories` + event rows + founder death ticks into `MetricComputationInputs` via `experiments.composition` / collectors. Optional join when layers+v34 co-enabled (no layer label injection into repositories). Prove collectors attach rows when repository enabled.
  - Deliverable: Harvest unit tests; no `api`↔`analysis` import violations.
  - Files: `src/experiments/composition.py`, `src/experiments/metric_collection.py`, `src/experiments/collectors.py`, `tests/unit/test_knowledge_repository_harvest.py`
  - Logging: DEBUG harvest counts by source kind; WARN when repository enabled but rows empty
  - Depends on: 8, 12, 13

<!-- Commit checkpoint: tasks 12-14 -->

### Phase 6: Experiment AO + matrix

- [ ] Task 15: Add `knowledge_repositories_profile` and `experiment_ao_knowledge_repositories` catalog entry (off V1 gate) with locked arm matrix (including `ao-custody-block`); export from `experiments/__init__.py`. Pin schema v34 + objects + flag on on-arms.
  - Deliverable: Catalog construction tests; arm ids stable.
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, scenario helpers as needed, `tests/unit/test_experiment_ao_knowledge_repositories.py`
  - Logging: INFO `experiment_ao_built` experiment_id + arm_id + schema_version; DEBUG flag/object presence
  - Depends on: 2, 14

- [ ] Task 16: Arm assertions — creator-death survival, neglect, inaccessible helper, missing-index, degrade compose, custody-block, subjective-frame (no Observation label), channel-off, flags-off hash stability.
  - Deliverable: Executable arm proofs with stable failure messages citing arm_id.
  - Files: `tests/unit/test_experiment_ao_*.py`, flags-off hash stability extensions
  - Logging: test logs only
  - Depends on: 15, 6, 10

- [ ] Task 17: Matrix finalize + allowlist ownership — insert `knowledge_repositories_on` **before** `durable_records_on`; accept v34; widen lifecycle/init needs sets with `V34`; include AO on allowlist without default V1 batches; keep AN on v33 when repository absent.
  - Deliverable: Finalize priority tests (`knowledge_repositories_on` beats `durable_records_on`); allowlist pin.
  - Files: `src/experiments/matrix_schema.py`, matrix allowlist modules, `tests/unit/test_matrix_schema_v34*.py`
  - Logging: DEBUG finalize selected schema_version reason (`knowledge_repositories_on` / …)
  - Depends on: 1, 15

<!-- Commit checkpoint: tasks 15-17 -->

### Phase 7: Research UI + docs + regression pins

- [ ] Task 18: Research UI epistemic overlays + AnalyticsPanel discovery for `knowledge_repository_survival`, `knowledge_repository_access`, `knowledge_repository_organization` (`research_inference` badge only — no subjective ledger fields, no full archive browser). Mirror Experiment AN/AM overlay pattern.
  - Deliverable: Client unit tests for badge discovery; GraphsPanel archive browser remains absent.
  - Files: `clients/research-ui/src/epistemic.ts`, `clients/research-ui/src/epistemic.test.ts`, `clients/research-ui/src/views/AnalyticsPanel.svelte`, related client tests
  - Logging: N/A in SPA
  - Depends on: 13

- [ ] Task 19: Mandatory docs via `/aif-docs` — architecture V3 seams + Downstream contract (v34 deepen, cultural `{v31..v34}`, durable gates `{v33,v34}`, write-pair V14/v11, no new flag, no LibraryInstitution), physical-simulation repository/custody/decay/inaccessible helper, analysis-metrics families + DTOs, cognition-runtime note, observer semantic types, DESCRIPTION + ARCHITECTURE artifacts.
  - Deliverable: Docs mention all locked pins; no contradictions with v3-11 durable blurb.
  - Files: `docs/architecture.md`, `docs/physical-simulation.md`, `docs/analysis-metrics.md`, `docs/cognition-runtime.md`, `docs/observer.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`
  - Logging: N/A
  - Depends on: 1, 7, 11, 13, 15, 18

- [ ] Task 20: Combined-arm regression — repository + durable write-pair V14; repository + dependency_care still V14 when repository on; layers optional on v34; architecture isolation (`tests/architecture/test_v3_knowledge_repositories_isolation.py` mirroring durable dual-rep walls; no LibraryInstitution symbols).
  - Deliverable: Checkpoint selector priority tests + isolation green.
  - Files: `tests/unit/test_checkpoint_schema_knowledge_repositories.py`, `tests/architecture/test_v3_knowledge_repositories_isolation.py`
  - Logging: DEBUG selected pair
  - Depends on: 7, 13

- [ ] Task 21: Final regression — V1 gate + `test_v2_scientific_invariants` under V3 flags-off; `METRIC_FAMILY_COUNT=62`; command count 34; SEMANTIC 53; Alembic head `0017`; Experiment AN unchanged when repository absent; append-only DELETE still rejected; close verification pins table below for `/aif-verify`.
  - Deliverable: `tests/unit/test_v3_knowledge_repositories_regression.py` green with pins; plan pins accurate.
  - Files: existing gate tests; new regression pin module; this plan file (pins only)
  - Logging: pytest output only
  - Depends on: 10, 11, 14, 16, 17, 19, 20

<!-- Commit checkpoint: tasks 18-21 -->

## Verification pins (summary)

| Pin | Value |
| --- | --- |
| Runner schema | `runner-config-v34` when `knowledge_repositories` present (`v34_requires_knowledge_repositories`) |
| Prerequisite objects | `cultural_feature_provenance` + `durable_records` + `knowledge_repositories` |
| Durable schemas | `{v33, v34}` (`durable_records_requires_v33` allowlist widened) |
| Cultural schemas | `{v31, v32, v33, v34}` |
| V3 flag | No new flag; deepens `cultural_historical_memory` |
| Write-pair | `(EVENT_SCHEMA_REPLAY_V14, codec v11)` when repository active |
| `AgentCommand` count | 34 (+5) |
| SEMANTIC count | 53 (+6) |
| `METRIC_FAMILY_COUNT` | 62 (+3) |
| Metric families | `knowledge_repository_survival@1`, `knowledge_repository_access@1`, `knowledge_repository_organization@1` |
| Experiment | `experiment-ao-knowledge-repositories` (off V1 gate) |
| Profile | `knowledge_repositories_profile` |
| AO arms | `ao-channel-off`, `ao-establish-deposit`, `ao-creator-death`, `ao-neglect-decay`, `ao-inaccessible`, `ao-missing-index`, `ao-record-degrade`, `ao-custody-block`, `ao-subjective-frame`, `ao-flags-off` |
| Alembic | head stays `0017` |
| Inaccessible helper | `WorldEngine.mark_repository_inaccessible` |
| Forbidden | `LibraryInstitution`, global Archive controller, Observation cultural labels, custody bypass via Take/Transfer/Erase |
| Matrix finalize | `knowledge_repositories_on` before `durable_records_on` |
| Reject codes (core) | `knowledge_repositories_without_cultural_flag`, `knowledge_repositories_requires_cultural_provenance`, `knowledge_repositories_requires_durable_records`, `knowledge_repositories_requires_v34`, `v34_requires_knowledge_repositories`, `v34_requires_durable_records`, `knowledge_repositories_mode_invalid`, `knowledge_repositories_inactive`, `repository_custody_blocks_transfer`, `repository_custody_blocks_erase`, plus nested / runtime repository_* codes |

## Out of scope

- Hard-coded LibraryInstitution / librarian / archivist roles
- Owning `institutional_economy` or `multi_polity_migration`
- Kinship cultural inheritance handoff
- Engine fact-checking indexes against world truth
- Alembic `0018+`, `/v2` HTTP, Godot cultural "library" chrome
- Research UI GraphsPanel full archive browser (Analytics discovery sufficient; richer UI deferred)
- Repositories without durable_records channel
- Auto-damage of member records solely from repository neglect (compose via durable commands in arms)

## Implementation notes for `/aif-implement`

- Prefer new `world/repositories.py` + private ops over inventing institution packages.
- Keep Experiment AN and replay-v13 paths green when repository object absent.
- When repository + durable are active, one write schema (v14) must accept all prior durable/artifact detail types.
- Seed-derived RNG only for neglect index corruption — no wall-clock.
- Structured logs: metadata only (ids, counts, reason codes, status) — never mark/index token payloads.
- Custody is mandatory before physical transfer: RetrieveRecord then Take/Transfer.
