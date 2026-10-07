# Implementation Plan: V3-11 Durable Records and Copying

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-07
Improved: 2026-10-07 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Deepens the already-owned `cultural_historical_memory` surface by extending V2 WorldEngine information artifacts into durable, copyable, damageable records whose physical marks persist across authors' deaths without becoming objective truth.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-11-durable-records.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; suggested stem `v3-11-durable-records`; git.create_branches=false so stem is description slug (branch-derived naming disabled)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; scope is explicitly v3-11 under M7 so linkage uses M7
INFO [aif-improve] refined 2026-10-07: v32/v33 schema split + layers-on-v33; runner/engine `durable_records_active` co-land; event/codec v13/v10 ACCEPTED sets; exact event/metric DTO tables; matrix finalize order; composition harvest fields; Research UI overlays; append-only scale note; cultural gate `{v31,v32,v33}` rewrite

## Compatibility contract

This plan **deepens** already-owned **`V3CapabilityFlags.cultural_historical_memory`** (v3-09; analysis deepen v3-10). It extends the V2 WorldEngine-owned information-artifact channel into **durable records**: typed physical carriers with author, creation tick, imperfect copies, parent/source lineage, edits, annotations, damage, partial loss, and destruction — while keeping interpretation subjective and written marks non-authoritative as truth.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents receive immutable per-agent `Observation` / `Perspective` only. `WorldEvent` records remain immutable and append-only. Subjective state stays outside the objective fold. Godot remains read-only. Deterministic replay continues. No scripted civilization / archive_emerged outcomes.
2. Flag ownership unchanged: keep `cultural_historical_memory`, `generational_population`, and `kinship_inheritance` owned. Do **not** own `multi_polity_migration`, `institutional_economy`, or `multi_hop_testimony_tracking`. **No new V3 capability flag.**
3. Flags-off / channel-off / durable-object-absent = prior baseline. With all V3 flags off, or with `cultural_historical_memory=False` / `cultural_feature_provenance` absent / `durable_records` absent, trajectories and `exact_trajectory_hash` match the pre-plan baseline for AE–AM where applicable. V2 Experiment Z (`external_artifact_memory@1`) and V3 Experiment AL/AM metric families stay unchanged (sibling families only).
4. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2/V3 versions in the same change that adds a write version.
5. **Records are physical; meaning is subjective (locked).** Objective state stores marks, relations, genre, lineage ids, integrity, and revision counters only — never `meaning`, `truth`, `interpretation`, presentation fields, or researcher narrative.
6. **Written information ≠ objective truth (locked).** Engine admission never validates mark tokens against world facts. False, incomplete, and distorted records remain legal and may outlive their authors.
7. **Copying is not necessarily perfect (locked).** Copy fidelity follows `DurableRecordsSpec.copy_fidelity_policy`; perfect copies are one mode, not the default assumption.
8. **Preserve v3-02–v3-10 locks:** blank-slate deny-list; closed Observation `lifecycle`; ELDER ≠ leader; related ≠ affection; no parent→caregiver hardwiring; no global Culture; no internal-state copy; Alembic head `0017` by default; kinship cultural inheritance handoff stays deferred; historical layers stay analysis-only (never agent knowledge).
9. **`api` must not import `analysis`.** Persist metric docs offline; serve via existing `MetricReadService` / inspection projections only.
10. Closed `AgentCommand` count moves **26 → 29** (adds `CopyRecord`, `AnnotateRecord`, `DamageRecord`). SEMANTIC count moves **43 → 47** (adds copy / annotate / damage / partial-loss semantic types; destruction reuses / extends `ARTIFACT_DESTROYED` with tombstone lineage).
11. **Append-only history (scale).** Durable copy/annotate/damage events increase authoritative row volume. Bound growth via write cadence and inspection limits only — never `DELETE` on `world_events` / snapshots / stream rows (`reject_history_mutation` stays). Long-run Experiment AN arms may document optional checkpoint presets (see v2-long-experiment-scalability); science payloads stay complete and uncoalesced.

## Goal

Extend V2 symbolic artifacts (`mark` / `sign` / `note` / `map` / `record` / `memorial`) into a durable-record substrate that researchers and agents can create, copy imperfectly, edit, annotate, damage, partially lose, and destroy — while maintaining lineage and treating content as fallible physical marks.

Closed durable-record genres (objective kind labels, not meanings):

| Genre id | Typical use (research framing only) |
| --- | --- |
| `warning` | Hazard / prohibition marks |
| `instruction` | Procedural / how-to marks |
| `map` | Spatial / relational marks (distinct from V2 `ArtifactKind.MAP` portability rules — see Design) |
| `story` | Narrative mark sequences |
| `agreement` | Pact / claim marks between parties |
| `inventory_record` | Possession / stock marks |
| `genealogy` | Kin / descent marks (≠ world kinship graph authority) |
| `chronicle` | Ordered event marks over ticks |

Each durable record instance supports:

- `author_id` (creating body; immutable)
- `created_tick`
- copies (new artifact ids with parent/source lineage)
- `parent_artifact_id` / copy generation
- edits (`Amend` + revision)
- annotations (append-only annotation revisions)
- damage / partial loss / destruction (integrity + optional tombstone)

Deliver:

- Exact optional root sibling `durable_records` on **`runner-config-v33`**
- WorldEngine fields + commands + events for lineage, imperfect copy, annotate, damage, partial loss, tombstone destroy
- ObservedArtifact / inspection extensions (objective fields only)
- Owner-scoped interpretation remains via existing `ArtifactInterpretationMode` (no new cognition mode enum on `AgentCognitionSpec`)
- Sibling analysis metric families (do not overload `external_artifact_memory@1`, `cultural_feature_*`, or historical-memory families)
- Off-gate Experiment AN comparing channel-off vs durable-on across perfect/imperfect copy, author-death persistence, damage/partial-loss, and false-record survival arms

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` remains the only authority over objective physical records; cognition never mutates `WorldState.artifacts` directly.
2. Agents never receive another agent's private interpretation ledger, a society archive download, or analysis metric documents as facts.
3. `WorldEvent` records remain immutable; authoritative history stays append-only.
4. Objective marks never auto-download into episodic memory (V2 boundary preserved); interpretation stays opt-in via `ArtifactInterpretationMode`.
5. Record genres and integrity states are **not** truth labels. A `genealogy` genre record does not write `world.kinship` edges; a `chronicle` does not rewrite history.
6. Author death does **not** delete, correct, or invalidate records. Orphaned false records remain legal.
7. LLM output remains non-authoritative.
8. No scripted `archive_must_persist` / `true_history_restored` booleans.
9. Godot remains read-only; this plan requires objective observer fields for new integrity/lineage tokens but **not** private-reading chrome.
10. Runs remain reproducible where claimed (explicit seeds, deterministic streams, deterministic fakes / recorded LLM paths).

### Scope split (locked)

| This plan (v3-11) | Deferred |
| --- | --- |
| Objective durable genres, lineage, imperfect copy, damage/tombstone | Engine fact-checking / canonical history |
| Opt-in interpretation distortion on damaged records | Godot private-reading chrome |
| Sibling analysis metrics + Experiment AN | Research UI GraphsPanel lineage browser |
| Compose optional cultural uptake from durable genres | Kinship cultural inheritance handoff |
| `runner-config-v33` + replay-v13 / codec v10 write-pair | Alembic `0018+`; `/v2` HTTP |
| V2 Experiment Z unchanged when durable absent | Owning `multi_hop_testimony_tracking` |

**Rationale for cultural flag coupling:** durable records deepen the same M7 `cultural_historical_memory` seam as v3-09/v3-10 (artifact + provenance compose). V2-only artifact runs (`runner-config-v19`, Experiment Z) stay valid **without** cultural flag or `durable_records`.

### Capability / ownership (locked)

1. **No new V3 flag.** Enabling durable records requires already-owned `cultural_historical_memory=True` plus exact `cultural_feature_provenance` **and** exact `durable_records` on `runner-config-v33`.
2. **`historical_memory_layers` on v33 is optional.** v32 remains **layers-only** (`v32_requires_historical_memory_layers` unchanged). v33 **always** requires `durable_records`; may also carry `historical_memory_layers` for combined AM+AN matrix cells. Update live gate `historical_memory_requires_v32` → accept schema `{v32, v33}` when layers object present; layers on v31/v32-only without durable stay illegal on v33 schema without durable object.
3. Do **not** implement kinship cultural inheritance handoff.
4. Other unowned V3 flags still fail closed.
5. When durable object absent: AE–AM bit-identity matches pre-plan for the same roster and seeds; V2 artifact channel (v19) behavior unchanged.
6. Durable channel may compose with V2 `ArtifactInterpretationMode` / artifact bootstrap; do **not** claim that enabling durable auto-enables interpretation — omit object / keep mode `DISABLED` for objective-only arms.
7. Cognition compile of new commands requires `ArtifactInterpretationMode.DETERMINISTIC` **and** durable channel on (mirror V2 Inscribe compile gate). World admission of scripted/test submissions may accept commands when channel on regardless of mode (same V2 pattern).

### Flag × object gate matrix (locked)

| Config shape | Allowed? | Reject / notes |
| --- | --- | --- |
| Cultural flag off, durable absent | Yes (off) | Passthrough |
| Durable object present, cultural flag off | No | `durable_records_without_cultural_flag` |
| Durable object present, `cultural_feature_provenance` absent | No | `durable_records_requires_cultural_provenance` |
| Cultural flag on + provenance on **v31/v32**, durable absent | Yes | Pre-plan AL/AM behavior |
| Cultural flag on + provenance + durable on **v31 or v32** | No | `durable_records_requires_v33` |
| Cultural flag on + provenance + durable on **v33** | Yes | Durable channel enabled |
| Durable object on schema ≠ v33 | No | `durable_records_requires_v33` |
| Schema `v33` without durable object | No | `v33_requires_durable_records` |
| Schema `v33` + durable + provenance absent | No | `durable_records_requires_cultural_provenance` |
| Durable `mode=disabled` present | No | `durable_records_mode_invalid` — omit object for off |
| Cultural-only on v33 (lifecycle off) + durable | Yes | Widen `_cultural_only` to `{v31,v32,v33}`; forbid lifecycle siblings with existing rejects |
| Generational + cultural + durable on v33 | Yes | Author-death persistence arms |
| Kinship-only + cultural + durable on v33 | Yes | Genealogy *genre* ≠ kinship graph writes |
| Layers + durable on v33 | Yes | Layers remain analysis-only; may join artifact lineage in harvest |
| Mentorship / developmental without lifecycle | No | Unchanged existing rejects |

### Runner schema (locked)

Introduce `RUNNER_SCHEMA_VERSION_V33 = "runner-config-v33"`:

- Exact root key set = **v32 accepted roots** ∪ sibling **`durable_records`** (v32 roots already include optional `historical_memory_layers`).
- `durable_records` present ⇒ `schema_version == runner-config-v33` and `cultural_historical_memory=True` with exact `cultural_feature_provenance` + exact durable object.
- Decode v23–v32 synthesizes `durable_records=None` (absent ≡ durable channel off).
- Gate rewrite: `cultural_historical_memory=True` accepts `{v31, v32, v33}`. Rewrite live `cultural_feature_requires_v31` message to cover `{v31,v32,v33}` (keep or alias reject id — pin in Task 1). Rewrite `_cultural_only` to `{v31,v32,v33}`.
- Widen every mode/lifecycle/kinship/cultural allowlist capped at v32 to include v33.
- Default write stays `runner-config-v4` when all V3 flags are off.
- **Matrix finalize (Task 17 only):** insert `durable_records_on` **before** `historical_memory_on` (v33 beats v32); widen `needs_lifecycle` / `needs_init` with `V33`; AN on v33; AM on v32 when durable absent; AL on v31 when layers/durable absent. Task 1 must **not** edit finalize priority.

### Serialization contract (locked)

Mirror v32 pattern in `runner_serialization.py`:

- `_RUNNER_ROOT_KEYS_V33_*` = corresponding v32 frozenset ∪ `"durable_records"`
- Exact child keyset `_DURABLE_RECORDS_KEYS` matching nested policy tables below
- `_encode_durable_records` / `_decode_durable_records` with `_require_keys` (no silent extras)
- Encode: `schema_version == V33` requires provenance + durable present; layers optional
- Decode: v23–v32 → `durable_records=None`
- DEBUG log present/absent on decode (metadata only)

### Runtime channel flags (locked)

Mirror v3-06 dependency-care pattern:

1. `durable_records_active = config.durable_records is not None` at run start (runner `from_config` / engine bootstrap).
2. Pass `durable_records_active=` into **both** `checkpoint_schema_for_production` and `engine.select_checkpoint_schema` (agreed-or chain — same bug class as v3-06 if only one is updated).
3. Add `WorldEngine._durable_records_channel_active` (or equivalent) parallel to lifecycle/kinship channel flags; durable world commands reject with `durable_records_inactive` when false.
4. When `durable_records_active`, set `engine._artifacts_enabled = True` (durable mutations are artifact-state mutations even if V2 `artifacts_enabled` was false). Log DEBUG when auto-enabling artifact state for durable-only configs.
5. Checkpoint priority when durable on: **`durable_records_active` → `(EVENT_SCHEMA_REPLAY_V13, "v10")`** ahead of dependency-care `(V12, v9)` — combined-arm regression required (Task 19).

### `DurableRecordsSpec` (locked)

Root sibling object; omit for off. Exact keys (reject extras / missing):

| Key | Type / values | Role |
| --- | --- | --- |
| `durable_records_mode` | `deterministic` only | Present object implies on; `disabled` rejected |
| `enabled_genres` | Non-empty frozenset of closed genre ids | Which genres Inscribe/Copy may create |
| `copy_fidelity_policy` | Exact nested object | Imperfect-copy rules |
| `integrity_policy` | Exact nested object | Damage / partial loss / tombstone |
| `annotation_policy` | Exact nested object | Annotation caps |
| `lineage_policy` | Exact nested object | Parent / generation caps |
| `perception_mode` | `marks_and_meta` (default) \| `marks_only` | Whether Observation projects lineage/integrity meta |
| `rng_namespace` | Token string | Seed-derived stream for mutation/damage (`durable_records`) |

**`copy_fidelity_policy` exact keys:**

| Key | Role |
| --- | --- |
| `default_fidelity` | `perfect` \| `deterministic_mutation` \| `lossy` |
| `max_mark_edits` | Non-neg int (default `2`) — token drops/swaps when not perfect |
| `max_relation_edits` | Non-neg int (default `1`) |
| `preserve_genre` | Bool (default `true`) — if false, genre may degrade per closed table |
| `copy_requires_hold_or_colocation` | Bool (default `true`) |

**`integrity_policy` exact keys:**

| Key | Role |
| --- | --- |
| `allow_damage` | Bool (default `true`) |
| `allow_partial_loss` | Bool (default `true`) |
| `tombstone_on_destroy` | Bool (default `true`) — retain destroyed row for lineage |
| `partial_loss_min_marks_remaining` | Non-neg int (default `0`) |

**`annotation_policy` exact keys:**

| Key | Role |
| --- | --- |
| `max_annotations_per_record` | Positive int (default `8`) |
| `annotations_survive_author_death` | Bool (default `true`) |

**`lineage_policy` exact keys:**

| Key | Role |
| --- | --- |
| `max_copy_generation` | Positive int (default `8`) |
| `track_source_on_edit` | Bool (default `true`) — edits keep same artifact id; lineage unchanged |
| `destroyed_parent_blocks_copy` | Bool (default `true`) |

Provide `example_durable_records_spec()` in `runner_models.py` for tests and Experiment AN.

### Domain model (locked)

Package: extend `world/artifacts.py` (and private ops/rules/events/perception/replay). Do **not** invent a parallel global Archive store.

**`DurableRecordGenre` (StrEnum):** `warning`, `instruction`, `map`, `story`, `agreement`, `inventory_record`, `genealogy`, `chronicle`.

**`RecordIntegrity` (StrEnum):** `intact`, `damaged`, `partially_lost`, `destroyed`.

**`InformationArtifact` additive fields** (channel-on encode; channel-off omit / synthesize defaults):

| Field | Role |
| --- | --- |
| `record_genre` | `DurableRecordGenre \| None` — required non-None when durable channel on and kind is in durable-capable set |
| `parent_artifact_id` | `EntityId \| None` — source for copies; `None` for originals |
| `source_artifact_id` | `EntityId \| None` — root of copy lineage (original); equals self for originals |
| `copy_generation` | Non-neg int — `0` original; child = parent+1 |
| `integrity` | `RecordIntegrity` — default `intact` |
| `annotation_revisions` | Non-neg int — increments on `AnnotateRecord` |
| `lost_mark_count` | Non-neg int — cumulative marks removed by damage/partial loss |

**Durable-capable `ArtifactKind` set (locked):** `{RECORD, NOTE, MAP, MEMORIAL, SIGN}` when channel on. `MARK` stays V2-only ephemeral glyph (no durable genre). Portability rules unchanged: portable kinds may be held; fixed kinds location-only.

**Genre vs `ArtifactKind.MAP`:** `DurableRecordGenre.MAP` may attach to `ArtifactKind.MAP` or `ArtifactKind.RECORD`. Genre never overrides portability.

**Forbidden field names** (extend existing set): `truth`, `verified`, `canonical_history`, `meaning`, `interpretation`, plus existing presentation forbids.

### Commands (locked)

Add three commands to the closed union (**26 → 29**):

1. **`CopyRecord(artifact_id, hold=False, fidelity_override=None)`**
   - Creates a new `InformationArtifact` with fresh id, `parent_artifact_id=source`, `source_artifact_id=root`, `copy_generation=parent+1`, `author_id=actor`, `created_tick=now`.
   - Content derived by fidelity policy (perfect / deterministic_mutation / lossy).
   - Reject: unknown, destroyed parent when blocked, generation cap, not colocated/held, genre not enabled, channel off (`durable_records_inactive`).

2. **`AnnotateRecord(artifact_id, content)`**
   - Appends annotation marks/relations into a dedicated annotation slot **or** merges into content per implementation choice locked below: **merge into `ArtifactContent` with revision bump + `annotation_revisions += 1`** (no separate free-text store). Marks remain tokens only.
   - Reject: destroyed integrity, annotation cap, not colocated/held, channel off.

3. **`DamageRecord(artifact_id, mode)`** where `mode ∈ {damage, partial_loss, destroy}`
   - `damage`: set integrity `damaged` (content may drop ≤ policy edits); emit damage event.
   - `partial_loss`: drop marks toward `partial_loss_min_marks_remaining`; set `partially_lost`; emit partial-loss event.
   - `destroy`: if `tombstone_on_destroy`, set integrity `destroyed` and clear placement for interaction but retain row for lineage; else hard-remove like V2 `Erase`. Emit destroy/tombstone event.
   - `Erase` remains legal; when durable channel on and tombstone policy true, `Erase` aliases destroy-with-tombstone (single code path). When channel off, `Erase` keeps V2 hard-remove.

Reuse `Inscribe` / `Amend` / `TransferArtifact` with gates:

- `Inscribe` when durable on **and** kind durable-capable: require `record_genre` via extended command field `record_genre: DurableRecordGenre | None = None` (None illegal when durable on + durable-capable kind; ignored/rejected when channel off).
- Prefer extending `Inscribe` with optional `record_genre` rather than a fourth command (keeps count at 29).
- `Amend` increments `content_revision`; does not change `parent_artifact_id` / `author_id` / `created_tick`.

### Events / write-pair (locked)

Co-land **`EVENT_SCHEMA_REPLAY_V13`** + persistence codec **`v10`** when durable channel is active at run start.

**Co-land in one change (Task 7):** `EVENT_SCHEMA_REPLAY_V13` constant; extend `SUPPORTED_EVENT_SCHEMA_VERSIONS`, `REPLAYABLE_*`, `_ARTIFACT_EVENT_SCHEMAS`, `_DEPENDENCY_CARE_EVENT_SCHEMAS`, and sibling frozensets so **v13 accepts all v12 detail types** plus new durable details; `ACCEPTED_PERSISTENCE_CODEC_VERSIONS` + `journal.py` dual-key decode for **`v10`** artifact snapshot fields; `world/_replay.py`; `simulation/serialization.py`; `simulation/compatibility.py` matrix row; **both** checkpoint selectors.

New detail types (effect-complete on schema 13; illegal below):

| Detail | Domain kind token | Payload fields (exact) |
| --- | --- | --- |
| `ArtifactCopied` | `artifact_copied` | `child_artifact_id`, `parent_artifact_id`, `source_artifact_id`, `fidelity_mode`, `copy_generation`, `content_revision`, `record_genre` |
| `ArtifactAnnotated` | `artifact_annotated` | `artifact_id`, `annotation_revisions`, `content_revision`, `integrity` |
| `ArtifactDamaged` | `artifact_damaged` | `artifact_id`, `prior_integrity`, `next_integrity`, `lost_mark_count_delta`, `content_revision` |
| `ArtifactPartiallyLost` | `artifact_partially_lost` | `artifact_id`, `marks_remaining`, `lost_mark_count`, `content_revision`, `integrity` |
| `ArtifactDestroyed` (v13+) | `artifact_destroyed` | existing fields + `tombstone: bool`, `integrity` (`destroyed` when tombstone) |

**Write-pair priority (locked):**

`durable_records_active` → `(EVENT_SCHEMA_REPLAY_V13, "v10")`; else dependency-care → `(V12, "v9")`; else kinship → `(V11, "v8")`; … (remainder unchanged from `docs/architecture.md`).

SEMANTIC observer types: add `ARTIFACT_COPIED`, `ARTIFACT_ANNOTATED`, `ARTIFACT_DAMAGED`, `ARTIFACT_PARTIALLY_LOST` → **43 → 47**; map domain kind tokens in `observer/version.py` + `simulation/causal_debugger.py` (mirror existing artifact_created pattern).

### Perception / Observation (locked)

Extend `ObservedArtifact` when durable channel on and `perception_mode=marks_and_meta`:

- Existing: `entity_id`, `kind`, `author_id`, `created_tick`, `content`, `content_revision`, placement
- Additive: `record_genre`, `parent_artifact_id`, `source_artifact_id`, `copy_generation`, `integrity`, `annotation_revisions`, `lost_mark_count`

`marks_only`: project content + kind + genre only (no lineage/integrity meta).

Destroyed tombstones: **not** projected on ordinary Observation (agents cannot "see" destroyed records), but remain in world snapshot / inspection / analysis harvest. Occurrence `public_facts` may include `artifact_id`, `artifact_kind`, `content_revision`, `record_genre`, `integrity` (no mark payloads).

Domain encode always includes `artifacts` (possibly empty) — unchanged discipline. Additive fields omit when channel off (decode synthesizes defaults).

### Interpretation / cognition (locked)

1. Keep `ArtifactInterpretationMode` as the opt-in private reading path. Distortion rules remain; extend deterministically: when `integrity != intact`, force `distorted=True` and apply at least the V2 relation-drop rule (even if visibility/fatigue clean).
2. Do **not** add a durable mode to `AgentCognitionSpec`.
3. Compile `CopyRecord` / `AnnotateRecord` / `DamageRecord` / genre-bearing `Inscribe` only when interpretation mode is `DETERMINISTIC` and durable channel on.
4. Cultural-feature uptake channel `artifact` may treat durable genres as compose sources when v3-09 `uptake_compose.artifacts` is on — still fresh owner-scoped beliefs; never copy peer ledgers.
5. Genealogy/chronicle genres never auto-write kinship edges or historical-layer labels.
6. Extend `apply_artifact_interpretation_update` to pass through `observed_revision` parity when durable meta changes integrity without content revision bump (damage may bump revision — pin one rule in Task 10: **damage/partial_loss increment `content_revision`**; annotate/amend already do).

**Genre → cultural compose (when v3-09 `uptake_compose.artifacts` on):**

| `DurableRecordGenre` | Typical `CulturalFeatureKindId` | Channel |
| --- | --- | --- |
| `warning` | `symbolic_association` | `artifact` |
| `instruction` | `practice` | `artifact` |
| `map` | `symbolic_association` | `artifact` |
| `story` | `narrative_element` | `artifact` |
| `agreement` | `social_expectation` | `artifact` |
| `inventory_record` | `practice` | `artifact` |
| `genealogy` | `symbolic_association` | `artifact` (never writes `world.kinship`) |
| `chronicle` | `narrative_element` | `artifact` |

Skip with DEBUG `cultural_feature_kind_unsatisfiable` when compose bit on but cultural channel off.

### Author death / false persistence (locked)

1. On `Died`, do not cascade-delete or auto-correct artifacts authored by the dead body.
2. Held artifacts: existing death/drop policy applies (deposit to location if any); integrity unchanged.
3. Analysis/Experiment AN must prove a false/distorted record (seeded wrong marks) remains present and lineage-reachable after author death.
4. Annotations survive author death when `annotations_survive_author_death=true` (default).

### Analysis metrics (locked)

Sibling families (bump `METRIC_FAMILY_COUNT` **56 → 59**):

| Family id | Version string | Signal |
| --- | --- | --- |
| `durable_record_lineage` | `durable_record_lineage@1` | Copy-tree depth; generation histogram; parent/source coverage; tombstone share |
| `durable_record_fidelity` | `durable_record_fidelity@1` | Perfect vs mutated vs lossy copy rates; mean mark/relation edit distance parent→child |
| `durable_record_survival` | `durable_record_survival@1` | Records intact after author death; damaged/partial/destroyed counts; false-record persistence rate (seeded mismatch vs world facts — analysis-only truth spec) |

Do **not** overload `external_artifact_memory@1`, cultural-feature families, or historical-memory families.

**Harvest row shape (extend `artifact_objective_rows_from_artifacts`):** add optional keys `record_genre`, `parent_artifact_id`, `source_artifact_id`, `copy_generation`, `integrity`, `annotation_revisions`, `lost_mark_count`, `author_id`, `created_tick` — duck-typed only; never import `world.artifacts` from analysis.

**MetricComputationInputs additions:** `durable_record_rows`, `durable_record_event_rows` (copied/annotated/damaged/partial/destroyed), `death_ticks_by_body`, optional `false_record_expectations` (Experiment AN arm only — analysis truth spec).

`api` must not import `analysis`. Harvest via `experiments.composition` + collectors.

### Experiment AN — arm matrix (locked)

- Catalog: `experiment_an_durable_records` / id `experiment-an-durable-records` on **runner-config-v33**, off the V1 gate.
- Profile: `durable_records_profile` requiring schema==v33 + `cultural_historical_memory=True` + exact `cultural_feature_provenance` + exact `durable_records`; reject unowned V3 flags.

| Arm | Schema | Durable | Extra | Expected |
| --- | --- | --- | --- | --- |
| `an-channel-off` | v31 | absent | cultural provenance on | No durable families required; V2 Z-like baseline |
| `an-perfect-copy` | v33 | on | `default_fidelity=perfect` | Child marks == parent; generation=1; lineage family populated |
| `an-imperfect-copy` | v33 | on | `deterministic_mutation` or `lossy` | Child ≠ parent; fidelity family shows edits; lineage intact |
| `an-author-death` | v33 | on | lifecycle on; kill author mid-run | Record remains; survival family > 0; no auto-correct |
| `an-false-persist` | v33 | on | seed false marks; author dies | False record still present; analysis mismatch flag; no engine truth fix |
| `an-damage-loss` | v33 | on | DamageRecord damage→partial_loss→destroy tombstone | Integrity transitions; tombstone retained; Observation omits destroyed |
| `an-annotate-edit` | v33 | on | Annotate + Amend | annotation_revisions and content_revision bump; author immutable |
| `an-flags-off` | v4 | absent | all V3 off | Hash stability vs pre-plan |

- Prove: flags-off / durable-off hashes stable; V1 gate + `test_v2_scientific_invariants` green under V3 flags-off; architecture isolation green; SEMANTIC **47**; command count **29**; Alembic head `0017`.
- Matrix allowlist includes AN without enabling on default batches.

### Architecture isolation (locked)

- `agents` / `agents.cognition` must not import analysis durable-metric modules.
- Analysis must not import private `world._*` authority modules (duck-type harvest rows).
- `api` / cognition paths must not import `analysis`.
- No truth/verified fields on `InformationArtifact`, `ObservedArtifact`, or interpretation ledgers.
- Forbidden string aliases rejected in runner decode (`canonical_archive`, `true_history`, `society_library`, …).
- World tree: no global Archive / Library controller classes that auto-correct marks.

### Docs (locked — mandatory)

Update (no “optional” hedges):

- `docs/architecture.md` — V3 seams row + Downstream V3 contract (v33 deepens cultural; cultural flag accepts `{v31,v32,v33}`; write-pair V13/v10; no new flag)
- `docs/physical-simulation.md` — durable genres, commands, integrity, copy fidelity, tombstones
- `docs/analysis-metrics.md` — three new families
- `docs/cognition-runtime.md` — durable records objective; interpretation still opt-in; written marks ≠ truth
- `docs/observer.md` — new semantic types + integrity/lineage observer fields
- `.ai-factory/DESCRIPTION.md` — V3 scaffolding blurb for v33 durable records
- `.ai-factory/ARCHITECTURE.md` — allowlists / owned-flag notes for v33

## Commit Plan

- **Commit 1** (after tasks 1–2): `feat(v3): add durable_records runner-config-v33 gates`
- **Commit 2** (after tasks 3–5): `feat(world): durable record model, commands, and integrity`
- **Commit 3** (after tasks 6–8): `feat(world): imperfect copy, annotate, damage events and replay-v13`
- **Commit 4** (after tasks 9–11): `feat(simulation): perception, interpretation distortion, checkpoint codec v10`
- **Commit 5** (after tasks 12–14): `feat(analysis): durable record lineage fidelity survival metrics`
- **Commit 6** (after tasks 15–17): `feat(experiments): Experiment AN durable records`
- **Commit 7** (after tasks 18–21): `docs(v3): durable records seams` + verification pins

## Tasks

### Phase 1: Schema, serialization, and gates

- [x] Task 1: Add `RUNNER_SCHEMA_VERSION_V33`, `DurableRecordsSpec` (+ nested policy models), `SimulationRunnerConfig.durable_records`, `example_durable_records_spec()`, exact encode/decode + `_DURABLE_RECORDS_KEYS` / v33 root frozensets, and full reject-code set. **Rewrite** cultural provenance / `_cultural_only` / `_HISTORICAL_MEMORY_CULTURAL_SCHEMAS` to `{v31,v32,v33}`. Widen layers gate: `historical_memory_layers` allowed on `{v32,v33}`; keep `v32_requires_historical_memory_layers` when schema==v32 and layers absent; add `v33_requires_durable_records` when schema==v33 and durable absent. Widen every allowlist capped at v32 to include v33. Update `compatibility.py` v33 row with write-pair `(EVENT_SCHEMA_REPLAY_V13, codec v10)` when durable active. **Do not** edit matrix finalize priority here (Task 17 owns that).
  - Deliverable: Config round-trip tests for present/absent durable; reject rows from flag×object matrix including durable-on-v32, v33+durable-only (layers absent), v33+durable+layers; decode v23–v32 synthesizes durable=None; forbidden aliases rejected.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `tests/unit/test_durable_records_spec.py`, `tests/unit/test_runner_config_v33*.py`
  - Logging: DEBUG decode present/absent; INFO/raise stable reject codes on fail-closed; never log mark/relation payloads
  - Depends on: none

- [x] Task 2: Config enable/skip + runner/engine channel wiring. Validate durable in `__post_init__` / `from_config`; compute `durable_records_active`; bind `WorldEngine` durable channel flag + force `_artifacts_enabled` when durable on; pass `durable_records_active` into checkpoint schema selection at bootstrap (full wiring completed in Task 7). Prove cultural flag ownership unchanged; unowned V3 flags fail closed; passthrough when object absent (AE–AM hash-stable fixtures).
  - Deliverable: Unit tests for enable/skip, channel-off command reject, artifacts_enabled auto-true when durable-only config.
  - Files: `src/simulation/runner.py`, `src/simulation/runner_models.py`, `src/simulation/engine.py`, `tests/unit/test_durable_records_from_config.py`
  - Logging: INFO `durable_records_enabled` with genre_count + default_fidelity + tombstone_on_destroy; DEBUG skip when absent; DEBUG `durable_artifacts_enabled_for_channel`
  - Depends on: 1

<!-- Commit checkpoint: tasks 1-2 -->

### Phase 2: Domain model and commands

- [x] Task 3: Add `DurableRecordGenre`, `RecordIntegrity`, and additive `InformationArtifact` fields with validation (lineage, integrity, annotation_revisions, lost_mark_count). Extend forbidden content field names. Keep V2 constructors valid when durable fields defaulted/None.
  - Deliverable: Unit tests for legal/illegal placements, genre/kind combos, lineage caps at model layer.
  - Files: `src/world/artifacts.py`, `src/world/__init__.py`, `tests/unit/test_information_artifacts.py` (extend), `tests/unit/test_durable_record_model.py`
  - Logging: DEBUG `durable_artifact_constructed` genre + integrity + copy_generation + mark_count (no token dumps)
  - Depends on: 1

- [x] Task 4: Extend `Inscribe` with optional `record_genre`; add `CopyRecord`, `AnnotateRecord`, `DamageRecord` to `AgentCommand` union; update `_COMMAND_TYPES`, `require_agent_command`, `agent_command_tag`, and domain-contract evolution pins (**26 → 29**). Extend `simulation/serialization.py` + finalization command codec paths for new command shapes (mirror Inscribe/Amend encoding).
  - Deliverable: Constructor reject tests for hold/genre/mode; closed-count pin updated; command JSON round-trip tests.
  - Files: `src/world/actions.py`, `src/world/__init__.py`, `src/simulation/serialization.py`, `tests/unit/test_domain_contract_evolution_policy.py`, `tests/unit/test_durable_record_commands.py`
  - Logging: DEBUG command_constructed tags; ERROR stable reason codes
  - Depends on: 3

- [x] Task 5: Private operations/rules admit and mutate durable fields through `WorldEngine` only. Wire `COMMAND_RULE_MATRIX` / operation arms for Copy/Annotate/Damage; Inscribe genre path; Erase→tombstone when policy on. Colocation/hold/cap checks reuse artifact reason codes; add durable-specific codes (`durable_records_inactive`, `durable_genre_disabled`, `durable_copy_generation_cap`, `durable_parent_destroyed`, `durable_annotation_cap`, `durable_integrity_destroyed`).
  - Deliverable: Resolution tests for create/copy/annotate/damage/partial_loss/destroy tombstone; channel-off rejects new commands.
  - Files: `src/world/_operations.py`, `src/world/_rules.py`, `src/simulation/engine.py` (effect arms as needed), `tests/unit/test_durable_record_resolution.py`
  - Logging: INFO `durable_record_*` success with artifact_id + genre + integrity; WARN/DEBUG rejects with reason_code only
  - Depends on: 4

<!-- Commit checkpoint: tasks 3-5 -->

### Phase 3: Imperfect copy, events, replay

- [x] Task 6: Implement deterministic copy fidelity transforms (perfect / deterministic_mutation / lossy) using seed-derived `StreamScope` from `rng_namespace`. Mutation may drop/swap mark tokens and drop trailing relations within policy caps; never invent free-form text; never "correct" marks toward world truth.
  - Deliverable: Property/unit tests: perfect identity; mutation bounded; lossy reduces marks; same seed ⇒ same child content.
  - Files: `src/world/artifacts.py` or `src/world/durable_copy.py`, `tests/unit/test_durable_record_copy_fidelity.py`
  - Logging: DEBUG `durable_copy_fidelity` mode + parent_mark_count + child_mark_count + edit_counts; never log tokens
  - Depends on: 5

- [x] Task 7: Land `EVENT_SCHEMA_REPLAY_V13`, detail types with exact payload tables above, extend `ArtifactDestroyed` for tombstone, serialization encode/decode, full ACCEPTED frozenset co-land, and agreed write-pair selection in **both** `checkpoint_schema_for_production` and `engine.select_checkpoint_schema` (`durable_records_active` → V13/v10 ahead of dependency-care).
  - Deliverable: Event construction + schema-gate tests; illegal on < v13; combined-arm test stub proving V13 selected when durable+dependency_care both active.
  - Files: `src/world/events.py`, `src/simulation/serialization.py`, `src/simulation/engine.py`, `src/simulation/persistence.py`, `src/simulation/compatibility.py`, `src/simulation/service.py`, `tests/unit/test_durable_record_events.py`, `tests/unit/test_durable_record_write_pair.py`
  - Logging: DEBUG event_encoded kind + schema_version; ERROR invalid_event_schema_version
  - Depends on: 2, 5, 6

- [x] Task 8: Replay/apply path for new details + tombstone rows; journal/snapshot encode of additive artifact fields on codec **v10** (`ACCEPTED_PERSISTENCE_CODEC_VERSIONS`); dual-key decode for v9 and below synthesizing durable defaults (`record_genre=None`, `integrity=intact`, `copy_generation=0`, lineage ids None).
  - Deliverable: Replay golden tests for copy→annotate→damage→partial_loss→destroy; restore parity live vs restored; v9 snapshot restores with synthesized defaults.
  - Files: `src/world/_replay.py`, `src/simulation/journal.py`, `src/simulation/persistence.py`, `tests/unit/test_durable_record_replay.py`
  - Logging: DEBUG replay_apply detail_type + artifact_id; WARN skip malformed additive fields with stable code
  - Depends on: 7

<!-- Commit checkpoint: tasks 6-8 -->

### Phase 4: Perception, interpretation, observer

- [ ] Task 9: Extend `ObservedArtifact` + perception projection for genre/lineage/integrity per `perception_mode`; omit destroyed tombstones from agent Observation; update frozen observation field pins.
  - Deliverable: Perception tests for marks_and_meta vs marks_only; tombstone invisible to agents; held/ground rules unchanged.
  - Files: `src/world/observations.py`, `src/world/_perception.py`, `tests/unit/test_durable_record_perception.py`, `tests/unit/test_domain_contract_evolution_policy.py`
  - Logging: DEBUG observed_artifact_projected integrity + copy_generation (no content dumps)
  - Depends on: 3, 5

- [ ] Task 10: Interpretation distortion when `integrity != intact`; compile gates for new commands when mode `DETERMINISTIC` + durable on; deliberation allowlist updates; optional `agents/cognition/cultural_features.py` compose hook from durable genres (table above) when cultural channel on; prove mode `DISABLED` does not compile durable commands.
  - Deliverable: Unit tests for forced distortion; compile allow/deny matrix; cultural compose skips when cultural off.
  - Files: `src/agents/cognition/artifacts.py`, `src/agents/cognition/deliberation.py`, `src/agents/cognition/cultural_features.py` (compose only), `src/simulation/agent_runtime.py` / runner bind as needed, `tests/unit/test_durable_record_interpretation.py`
  - Logging: DEBUG interpretation_distorted reason=`record_integrity`; INFO compile_skip reason codes
  - Depends on: 4, 9

- [ ] Task 11: Observer/presentation: extend `ObserverArtifact` in `observer/contracts.py` + `observer/project.py` with optional genre/integrity/lineage fields (objective only); SEMANTIC types **43 → 47** in `observer/version.py`; causal-debugger labels for new detail kinds; no private-reading chrome. Protocol stays `observer-protocol-v1`.
  - Deliverable: Observer unit tests for new fields/types; presentation forbids still hold.
  - Files: `src/observer/contracts.py`, `src/observer/project.py`, `src/observer/version.py`, `src/simulation/causal_debugger.py`, `tests/unit/test_artifact_observer.py` (extend), semantic catalog pins
  - Logging: N/A beyond existing observer metadata logs
  - Depends on: 7, 9

<!-- Commit checkpoint: tasks 9-11 -->

### Phase 5: Analysis metrics + harvest

- [ ] Task 12: Implement lineage / fidelity / survival computors with exact DTO fields (`DurableRecordLineageSummary`, `CopyFidelitySummary`, `RecordSurvivalSummary` — counts/histograms only, no mark payloads); duck-type harvest rows; no cognition imports. False-record persistence uses analysis-only truth spec (seeded expected marks vs observed marks) — never feeds cognition.
  - Deliverable: Unit tests for each family empty/non-empty shapes.
  - Files: `src/analysis/durable_record_metrics.py`, `tests/unit/test_durable_record_metrics.py`
  - Logging: DEBUG family computed counts; censoring_policy states analysis-only / never cognition
  - Depends on: 1, 8

- [ ] Task 13: Register three metric families end-to-end (`MetricFamilyId`, `_spec_*`, builders, `MetricComputationInputs`, assemble/`_safe`, exports). Bump `METRIC_FAMILY_COUNT` 56→59. Do not overload listed sibling families.
  - Deliverable: Specification + assemble tests; exclusion-set updates for A–E gate.
  - Files: `src/analysis/specifications.py`, `src/analysis/metric_service.py`, `src/analysis/__init__.py`, `tests/unit/test_metric_specifications.py`
  - Logging: DEBUG metric assemble family_id + source_count
  - Depends on: 12

- [ ] Task 14: Harvest wiring — extend `artifact_objective_rows_from_artifacts` with durable meta keys; map copy/damage/annotate/destroy event rows, death ticks, optional cultural audits into `MetricComputationInputs` via `experiments.composition` / collectors. Optional join for `historical_memory_layers@1` harvest when layers+v33 co-enabled (lineage edges only — no layer label injection). Prove collectors attach rows when durable enabled.
  - Deliverable: Harvest unit tests; no `api`↔`analysis` import violations.
  - Files: `src/experiments/composition.py`, `src/experiments/metric_collection.py`, `tests/unit/test_durable_record_harvest.py`
  - Logging: DEBUG harvest counts by source kind; WARN when durable enabled but artifact rows empty
  - Depends on: 8, 12, 13

<!-- Commit checkpoint: tasks 12-14 -->

### Phase 6: Experiment AN + matrix

- [ ] Task 15: Add `durable_records_profile` and `experiment_an_durable_records` catalog entry (off V1 gate) with locked arm matrix; export from `experiments/__init__.py`. Pin schema v33 + objects + flag on on-arms.
  - Deliverable: Catalog construction tests; arm ids stable.
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, scenario helpers as needed, `tests/unit/test_experiment_an_durable_records.py`
  - Logging: INFO `experiment_an_built` experiment_id + arm_id + schema_version; DEBUG flag/object presence
  - Depends on: 2, 14

- [ ] Task 16: Arm assertions — perfect/imperfect copy, author-death, false-persist, damage-loss, annotate-edit, channel-off, flags-off hash stability; prove tombstones absent from Observation; prove genealogy genre does not write kinship edges.
  - Deliverable: Executable arm proofs with stable failure messages citing arm_id.
  - Files: `tests/unit/test_experiment_an_*.py`, flags-off hash stability extensions
  - Logging: test logs only
  - Depends on: 15

- [ ] Task 17: Matrix finalize + allowlist ownership — insert `durable_records_on` **before** `historical_memory_on` (v33 highest); accept v33; widen lifecycle/init needs sets with `V33`; include AN on allowlist without default V1 batches; keep AM on v32 when durable absent; keep AL on v31 when layers/durable absent.
  - Deliverable: Finalize priority tests (`durable_records_on` beats `historical_memory_on`); allowlist pin.
  - Files: `src/experiments/matrix_schema.py`, `tests/unit/test_matrix_schema_v33*.py`, matrix allowlist tests
  - Logging: DEBUG finalize selected schema_version reason (`durable_records_on` / …)
  - Depends on: 1, 15

<!-- Commit checkpoint: tasks 15-17 -->

### Phase 7: Research UI + docs + regression pins

- [ ] Task 18: Research UI epistemic overlays + AnalyticsPanel discovery for `durable_record_lineage`, `durable_record_fidelity`, `durable_record_survival` (`research_inference` badge only — no subjective ledger fields). Mirror Experiment AM overlay pattern.
  - Files: `clients/research-ui/src/epistemic.ts`, `clients/research-ui/src/epistemic.test.ts`, `clients/research-ui/src/views/AnalyticsPanel.svelte`, related client tests
  - Logging: N/A in SPA
  - Depends on: 13

- [ ] Task 19: Mandatory docs via `/aif-docs` — architecture V3 seams + Downstream contract (v33 deepen, cultural `{v31,v32,v33}`, write-pair V13/v10, no new flag), physical-simulation durable commands/integrity/copy, analysis-metrics families, cognition-runtime note (marks ≠ truth; author-death persistence), observer semantic types, DESCRIPTION + ARCHITECTURE artifacts.
  - Files: `docs/architecture.md`, `docs/physical-simulation.md`, `docs/analysis-metrics.md`, `docs/cognition-runtime.md`, `docs/observer.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`
  - Logging: N/A
  - Depends on: 1, 7, 13, 15, 18

- [ ] Task 20: Final regression — V1 gate + `test_v2_scientific_invariants` under V3 flags-off; architecture isolation (`tests/architecture/test_v3_durable_records_isolation.py` mirroring v3-10 dual-rep walls); `METRIC_FAMILY_COUNT=59`; command count 29; SEMANTIC 47; Alembic head `0017`; Experiment Z unchanged when durable absent; durable+dependency_care write-pair V13; append-only DELETE still rejected.
  - Files: existing gate tests; `tests/unit/test_v3_durable_records_regression.py` (SEMANTIC/command pins)
  - Logging: pytest output only
  - Depends on: 7, 10, 11, 13, 16, 17, 19

- [ ] Task 21: Close plan verification pins — ensure checkbox-ready for `/aif-verify`; keep the Verification pins table below accurate (implementer updates pins only — no new scope).
  - Files: this plan file (pins only), optionally `docs/architecture.md`
  - Logging: N/A
  - Depends on: 20

<!-- Commit checkpoint: tasks 18-21 -->

## Verification pins (target)

| Pin | Value |
| --- | --- |
| Runner schema | `runner-config-v33` when `durable_records` present (`v33_requires_durable_records`) |
| Cultural flag | already owned `cultural_historical_memory` (no new flag); accepts `{v31,v32,v33}` |
| Event write-pair | `(EVENT_SCHEMA_REPLAY_V13, codec v10)` when durable active |
| Alembic head | `0017` |
| `AgentCommand` count | 29 (+ `CopyRecord`, `AnnotateRecord`, `DamageRecord`) |
| SEMANTIC count | 47 (+ copied / annotated / damaged / partially_lost) |
| `METRIC_FAMILY_COUNT` | 59 (+3) |
| Experiment | `experiment-an-durable-records` (off V1 gate) |
| Profile | `durable_records_profile` |
| Metric families | `durable_record_lineage@1`, `durable_record_fidelity@1`, `durable_record_survival@1` |
| Genres | `warning`, `instruction`, `map`, `story`, `agreement`, `inventory_record`, `genealogy`, `chronicle` |
| Integrity | `intact`, `damaged`, `partially_lost`, `destroyed` |
| AN arms | `an-channel-off`, `an-perfect-copy`, `an-imperfect-copy`, `an-author-death`, `an-false-persist`, `an-damage-loss`, `an-annotate-edit`, `an-flags-off` |
| Reject codes (core) | `durable_records_without_cultural_flag`, `durable_records_requires_cultural_provenance`, `durable_records_requires_v33`, `v33_requires_durable_records`, `durable_records_mode_invalid`, `durable_records_inactive`, plus nested / runtime durable_* codes; cultural gate message covers `{v31,v32,v33}` |
| Matrix finalize | `durable_records_on` before `historical_memory_on` |
| Forbidden | truth/verified fields; global Archive controller; genealogy genre → kinship writes; marks as objective truth; auto-delete on author death; in-DB history DELETE |

## Non-goals

- Owning `multi_polity_migration`, `institutional_economy`, or `multi_hop_testimony_tracking`
- Natural-language document bodies / OCR / free-form books
- Engine-side fact-checking or "canonical history" correction
- Global Culture / society library that agents auto-download
- Kinship cultural inheritance handoff
- Making historical memory layers into agent knowledge
- Alembic `0018+` (flags/records stay runner JSON + event/snapshot payloads)
- `/v2` HTTP or observer protocol rename
- Godot private-interpretation chrome or Research UI GraphsPanel archive browser (metrics/Analytics discovery sufficient; richer UI deferred)
- Biology, mating, or scripted civilizational archives

## Implementation notes for `/aif-implement`

- Prefer extending `world.artifacts` + private ops over a new top-level package.
- Keep V2 Experiment Z and replay-v8 paths green when durable object absent.
- When both V2 artifacts and durable are active, one write schema (v13) must accept prior artifact detail types (same pattern as v8 accepting production/environment details).
- Seed-derived RNG only for copy mutation / lossy transforms — no wall-clock.
- Structured logs: metadata only (ids, counts, reason codes, genres, integrity) — never mark/relation token payloads.
