# Implementation Plan: V3-09 Cultural Transmission Provenance

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-06

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Owns the reserved `cultural_historical_memory` V3 flag so researchers can track emergent, transmissible cultural features with provenance without a society-wide Culture controller.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-09-cultural-transmission.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; suggested stem `v3-09-cultural-transmission`; git.create_branches=false so stem is description slug (branch-derived naming disabled)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; scope is explicitly v3-09 under M7 so linkage uses M7
INFO [aif-improve] refined 2026-10-06: exact nested policies, belief/audit field tables, hop_index, transmission/cognition wiring, flag×object gates, feature→source map, task deps

## Compatibility contract

This plan **owns** reserved **`V3CapabilityFlags.cultural_historical_memory`**. It introduces a dual research representation — agent-subjective cultural beliefs versus researcher-analytical cultural traits — with transmission provenance, mutation, and recombination. Culture remains emergent from owner-scoped state and public transmission; there is **no** global Culture object that automatically controls agents.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents receive immutable per-agent `Observation` / `Perspective` only. `WorldEvent` records remain immutable and append-only. Subjective state stays outside the objective fold. Godot remains read-only. Deterministic replay continues. No scripted civilization / culture_emerged outcomes.
2. Flag ownership: add `cultural_historical_memory` to `_V3_OWNED_CAPABILITY_FLAGS`. Keep `generational_population` and `kinship_inheritance` owned. Do **not** own `multi_polity_migration`, `institutional_economy`, or `multi_hop_testimony_tracking`.
3. Flags-off / channel-off = prior baseline. With all V3 flags off, or with `cultural_historical_memory=False` / provenance object absent, trajectories and `exact_trajectory_hash` match the pre-plan baseline for AE–AK where applicable. V2 Experiment S (`cultural_transmission@1` teaching metric) stays unchanged.
4. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2/V3 versions in the same change that adds a write version.
5. **No global Culture object.** Forbidden: `Culture`, `SocietyCulture`, world-snapshot culture keys, encyclopedia/culture_pack downloads, automatic society-wide influence that bypasses agent uptake.
6. **Dual representation (locked).** Distinguish and never collapse:
   - **Agent subjective cultural belief** — owner-scoped, fallible, may be wrong/incomplete/mutated; lives in cognition ledgers only.
   - **Researcher analytical cultural trait** — analysis-only aggregation/clustering after the run; never imported by cognition, never written into agent stores, never a WorldEngine law.
7. **No internal-state copy.** Transmission never copies another agent's cultural ledger, semantic beliefs, naming/norm/convention/narrative ledgers, mentorship lineage, developmental ledger, relationships, goals, or SelfModel. Uptake forms fresh owner-scoped evidence from public acts / observations / artifacts only.
8. **Do not overload `cultural_transmission@1`.** That family remains the V2 teaching/skill advice metric (Experiment S). This plan adds sibling metric families for feature provenance / trait diffusion / mutation-recombination.
9. Preserve v3-02–v3-08 locks: blank-slate deny-list; closed Observation `lifecycle` object; ELDER ≠ leader; related ≠ affection; no parent→caregiver hardwiring; developmental/mentorship never society-inject; Alembic head `0017` by default; kinship cultural inheritance handoff stays deferred under `kinship_inheritance`.
10. Optional tracing/analysis/observer presentation stay outside the objective fold / `EvidenceManifest`.
11. Closed `AgentCommand` count stays **26** unless a later need proves a new command is required (default: reuse existing Talk/Ask/Tell, teaching acts, artifact perception, and practice paths).

## Goal

Introduce a **research-oriented cultural feature substrate** that tracks transmissible cultural features without promoting them to objective laws.

Closed cultural feature kinds:

- `practice`
- `narrative_element`
- `term`
- `production_technique`
- `social_expectation`
- `symbolic_association`

Closed transmission provenance channels:

- `observation`
- `teaching`
- `communication`
- `artifact`
- `imitation`
- `independent_rediscovery`

Support **mutation** and **recombination** of feature fingerprints across hops (`hop_index`; root uptake = `0`).

Deliver:

- Owned flag `cultural_historical_memory` (default off; fail-closed until this plan lands)
- Exact `cultural_feature_provenance` root sibling on **`runner-config-v31`**
- Owner-scoped subjective cultural-belief ledger + provenance rows (no global Culture)
- Analysis-only analytical cultural traits + provenance/diffusion/mutation metrics
- Composition with existing V2 modes (naming, narrative, norms, conventions, teaching, artifacts) as optional uptake sources — without replacing those modes
- Off-gate Experiment AL comparing channel-off vs provenance-on vs multi-channel mutation/recombination arms

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` remains the only authority over objective physical reality; cultural features are never world rules.
2. Agents never receive another agent's private cultural ledger, a society encyclopedia, or analysis trait documents.
3. `WorldEvent` records remain immutable; authoritative history stays append-only.
4. Subjective cultural beliefs may be wrong, incomplete, mutated, or recombined and never fold into objective replay identity.
5. Analytical cultural traits are researcher constructs only; they must not bias live cognition.
6. LLM output remains non-authoritative.
7. No scripted `culture_emerged` / `tradition_established` / `trait_must_diffuse` booleans.
8. Godot remains read-only; this plan does **not** require culture-map chrome (optional metadata presentation deferred).
9. Runs remain reproducible where claimed (explicit seeds, deterministic streams, deterministic fakes / recorded LLM paths).

### Capability ownership (locked)

1. Own `cultural_historical_memory`. Enabling requires `cultural_historical_memory=True` plus exact `cultural_feature_provenance` on `runner-config-v31`.
2. Flag may enable **without** `generational_population` (parallel to kinship-only independence). When lifecycle is also on, analysis may join `generation_index` for multi-generation diffusion — agents still do not receive analytical traits.
3. Do **not** implement kinship cultural inheritance handoff under `kinship_inheritance`.
4. Other unowned V3 flags still fail closed.
5. When flag is off / object absent: AE–AK bit-identity matches pre-plan for the same roster and seeds (no new cultural-feature ledger writes from this channel).
6. V2 modes remain the public substrates where applicable. This channel **composes** them; it does not replace `AdviceStore`, narrative/naming/norm/convention ledgers, or mentorship lineage.
7. Do **not** claim that enabling this flag auto-enables V2 modes; compose skips with DEBUG when a source mode is off.

### Flag × object gate matrix (locked)

| Config shape | Allowed? | Reject / notes |
| --- | --- | --- |
| `cultural_historical_memory=False`, object absent | Yes (off) | Passthrough; no ledger writes |
| `cultural_historical_memory=False`, object present | No | `cultural_feature_without_flag` |
| `cultural_historical_memory=True`, object absent | No | `cultural_feature_requires_flag` (object required when flag on) |
| Flag on + object on `runner-config-v31` | Yes | `cultural_feature_mode` must be `deterministic`; `disabled` → `cultural_feature_mode_invalid` |
| Object on schema ≠ v31 | No | `cultural_feature_requires_v31` |
| Schema `v31` without object | No | `v31_requires_cultural_feature_provenance` |
| **Cultural-only** (flag on; `generational_population=False`) | Yes | Forbid `population_lifecycle`, `new_agent_initialization`, `dependency_care`, `developmental_learning`, `mentorship` with `cultural_only_forbids_*` / existing `*_without_lifecycle_flag` codes |
| **Kinship-only + cultural** (`kinship_inheritance` on, lifecycle off, cultural on) | Yes | Kinship-only still forbids lifecycle siblings; **must allow** `cultural_feature_provenance` (do not add cultural to kinship-only forbid list) |
| **Generational + cultural** | Yes | Lifecycle/init rules as today; cultural object may co-exist with mentorship/developmental on v31 |
| Mentorship / developmental without lifecycle | No | Unchanged existing rejects |

### Scope split (locked)

| This plan (v3-09) | Deferred |
| --- | --- |
| Own `cultural_historical_memory` with dual subjective/analytical representation | Natural-language free-form culture / language evolution authority |
| Closed feature kinds + provenance channels + mutation/recombination | Kinship cultural inheritance / estate knowledge handoff |
| Owner-scoped subjective cultural beliefs | Global Culture / society memory store controlling agents |
| Analysis-only analytical traits + provenance metrics; Experiment AL | Full Research UI / Godot culture atlases |
| Compose V2 naming/narrative/norms/conventions/teaching/artifacts as sources | Owning `multi_polity_migration` / `institutional_economy` |
| Optional join with lifecycle generation_index in analysis | New event-schema write-pair / Alembic `0018` |

### Dual representation (locked)

| Layer | Type name | Package | Feeds cognition? | Feeds WorldEngine? |
| --- | --- | --- | --- | --- |
| Agent subjective | `SubjectiveCulturalBelief` (+ ledger) | `agents.cognition.cultural_features` | Yes (owner-scoped bias only, policy-gated) | No |
| Researcher analytical | `AnalyticalCulturalTrait` | `analysis` only | **Never** | **Never** |

Rules:

- Subjective beliefs carry feature kind, opaque `content_key` / `content_fingerprint`, confidence, provenance channel, `parent_belief_ids`, `hop_index`, mutation/recombination flags, evidence refs.
- Analytical traits are computed post-run from harvested audits / owner ledger snapshots: shared fingerprint clusters, channel mix, hop depth, recombination graphs, optional generation spread.
- Never promote an analytical trait into a subjective belief automatically.
- Never treat either as an objective law or Observation authority field.

### Runner configuration versioning (locked)

Introduce `RUNNER_SCHEMA_VERSION_V31 = "runner-config-v31"`:

- Exact root key set = **v30 accepted roots** ∪ sibling root object **`cultural_feature_provenance`**. Preserve prior flag-conditional gates (kinship-only forbids lifecycle/init/dependency_care/developmental_learning/mentorship — **not** cultural). Cultural-only forbids those same lifecycle siblings (see gate matrix).
- Default write remains `runner-config-v4` when all V3 flags are off and no existing mode requires a higher schema.
- `cultural_feature_provenance` present ⇒ `schema_version == runner-config-v31` and `cultural_historical_memory=True` with exact object (stable reject `cultural_feature_requires_v31` / `cultural_feature_requires_flag`). Object present with `cultural_feature_mode=disabled` is **rejected** (`cultural_feature_mode_invalid`) — use absent object for off.
- `cultural_historical_memory=False` forbids non-empty `cultural_feature_provenance` (reject `cultural_feature_without_flag`).
- Decode of v23–v30 synthesizes no `cultural_feature_provenance` object (absent ≡ channel off / passthrough).
- Widen **every** mode allowlist currently capped at `v30` to also accept `v31`.
- Gate rewrite: `cultural_historical_memory=True` accepts `{v31}` (exact object required). `generational_population=True` accepts `{v24…v31}` when lifecycle present; `kinship_inheritance=True` accepts `{v27…v31}` with prior kinship-only forbids preserved (cultural object allowed alongside kinship when both flags on, including kinship-only+cultural on v31).
- `experiments/matrix_schema.py` finalize/allowlist accepts `v31`; **priority if-elif** inserts `cultural_feature_on` **before** `mentorship_on` so present cultural object selects `v31`; widen `needs_*` sets appropriately; AE stays v24 … AK v30; AL uses v31; default finalize stays `v4` when V3 flags off.
- Update `simulation/compatibility.py` version matrix row for v31 (**no new event-schema write-pair**).

### CulturalFeatureProvenanceSpec (exact root sibling — locked)

Root key `cultural_feature_provenance` exact children:

| Key | Role |
| --- | --- |
| `enabled_feature_kinds` | Ordered frozen list of closed feature-kind ids (non-empty when object present) |
| `enabled_provenance_channels` | Ordered frozen list of closed channel ids (non-empty when object present) |
| `mutation_policy` | Exact nested object (below) |
| `recombination_policy` | Exact nested object (below) |
| `uptake_compose` | Exact nested object (below) |
| `bias_policy` | Exact nested object (below) |
| `cultural_feature_mode` | Closed id: must be `deterministic` when object present — **not** a new `AgentCognitionSpec` enum |
| `max_beliefs_per_owner` | Positive int hard cap (deterministic eviction when exceeded) |
| `max_evidence_refs` | Positive int hard cap per belief |
| `applicability` | Closed id: `all_live_agents` (default) \| `mid_run_new_agents` |

Forbidden aliases in feature-kind / channel parsing: `culture_pack`, `encyclopedia`, `society_memory`, `global_culture`, `tradition_law`, `myth_object`, `language_authority`.

**`mutation_policy` exact keys:**

| Key | Role |
| --- | --- |
| `allow_mutation` | Bool — default `true` |
| `mutation_requires_evidence` | Bool — default `true`; mutation only after owner evidence |
| `max_token_edits` | Non-neg int hard cap on fingerprint token edits per mutation (default `1`, max `8`) |
| `rng_namespace` | Stable id — default `cultural_features`; seed-derived stream for deterministic edit choice |

**`recombination_policy` exact keys:**

| Key | Role |
| --- | --- |
| `allow_recombination` | Bool — default `true` |
| `max_parents` | Int in `[2, 4]` — default `2` |
| `min_token_overlap` | Float in `[0, 1]` — default `0.5`; parents must share enough fingerprint tokens |

**`uptake_compose` exact keys (locked defaults):**

| Key | Default | Role |
| --- | --- | --- |
| `naming` | `false` | When true + `SemanticNamingMode.DETERMINISTIC`, may form `term` |
| `narrative` | `false` | When true + `CulturalNarrativeMode.DETERMINISTIC`, may form `narrative_element` / contribute to `symbolic_association` |
| `norms` | `false` | When true + `SocialNormMode.DETERMINISTIC`, may form `social_expectation` |
| `conventions` | `false` | When true + `SocialConventionMode.DETERMINISTIC`, may form `practice` / `social_expectation` |
| `teaching` | `false` | When true + `TeachingInteractionMode.DETERMINISTIC`, may form mapped kinds via channel `teaching` |
| `artifacts` | `false` | When true + `ArtifactInterpretationMode.DETERMINISTIC`, may form `symbolic_association` / `term` via channel `artifact` |
| `mentorship` | `false` | When true + mentorship channel on, teacher ids may appear as evidence metadata only (never clone lineage rows) |

Defaults are **all `false`**. Experiment AL arms explicitly enable the compose bits they need. Skip with DEBUG when a compose bit is true but the underlying mode/flag is off.

**`bias_policy` exact keys:**

| Key | Role |
| --- | --- |
| `mode` | `ignore` (default) \| `prefer_aligned_features` |
| `communicate_weight` | Float in `[0, 1]` — default `0.0`; added to communicate float term when mode prefers |
| `content_affinity` | Bool — default `false`; prefer closed content tokens matching high-confidence beliefs |

Provide `example_cultural_feature_provenance_spec()` in `runner_models.py` for tests and Experiment AL (mirror `example_mentorship_spec`).

### Feature-kind → source mapping (locked)

| Feature kind | Primary provenance channels | Compose sources (when `uptake_compose` bit on) |
| --- | --- | --- |
| `practice` | `observation`, `imitation`, `teaching`, `communication` | `conventions`, `teaching`, `mentorship`→`social_practices` |
| `narrative_element` | `communication`, `teaching`, `observation` | `narrative`, `teaching`/`mentorship`→`stories` |
| `term` | `communication`, `teaching`, `artifact` | `naming`, `teaching`/`mentorship`→`vocabulary`, `artifacts` |
| `production_technique` | `observation`, `imitation`, `teaching` | `teaching`/`mentorship`→`production_recipes` |
| `social_expectation` | `observation`, `communication`, `teaching` | `norms`, `conventions`, `teaching`/`mentorship`→`social_practices` |
| `symbolic_association` | `artifact`, `communication`, `observation` | `artifacts` (interpreted marks) + optional `narrative` tokens; **no** free-form myth prose |

If an enabled feature kind has no enabled channel and no enabled compose path that can form it, skip with DEBUG `cultural_feature_kind_unsatisfiable` (do not fail runner construction unless the enabled-kinds list is empty).

### Subjective ledger (locked)

Package: `agents/cognition/cultural_features.py` (not `world/`).

`CulturalFeatureKindId` / `CulturalTransmissionChannelId` StrEnums — the closed sets above.

**`SubjectiveCulturalBelief` (exact minimal fields):**

| Field | Role |
| --- | --- |
| `belief_id` | Stable opaque id for this owner row |
| `owner_agent_id` | Owner |
| `feature_kind` | Closed feature-kind id |
| `content_key` | Stable opaque concept id / digest — never free-form society text |
| `content_fingerprint` | Opaque digest of owner’s current representation (mutable) |
| `channel` | Closed provenance channel id for the forming/updating event |
| `confidence` | Owner confidence band / quantized float |
| `parent_belief_ids` | Ordered frozen tuple of prior belief ids (empty for root / independent rediscovery) |
| `hop_index` | Non-neg int; **root uptake / independent rediscovery = `0`** (`CULTURAL_FEATURE_FIRST_HOP_INDEX`); child of parent at `h` → `h+1` (recombination uses `max(parent hops)+1`) |
| `mutated` | Bool |
| `recombined` | Bool |
| `evidence_refs` | Opaque EventId / communication id tokens only |
| `acquired_tick` / `last_updated_tick` | Ticks |
| `policy_version` | Policy version string |

**`CulturalFeatureLedger`:** owner-scoped tuple of beliefs + caps (`max_beliefs_per_owner`).

**`CulturalFeatureAudit` (metadata-only, same module):** owner id, feature_kind, channel, hop_index, mutated, recombined, parent_count, confidence band, digest id token, tick, reason code — never content payloads / free text.

- `empty_cultural_feature_ledger(owner_id)` for blank-slate admits.
- Extend `BLANK_SLATE_SUBJECTIVE_STORES` **and** `BlankSlateStoreCounts` with `cultural_features` (deny-list aliases: `culture_pack`, `global_culture`, `society_culture`, `encyclopedia_download`).
- **Runtime carry (exact pattern, mirror mentorship):** `CognitiveLoopResult.cultural_features` → `AgentRuntime._commit_cultural_features` → `AgentRuntime._cultural_features` → checkpoint restore; also plumb `CognitiveLoopProposal` / `Perspective` / `SubjectiveSnapshot` optional fields; `export_cultural_feature_audits` on runtime + runner.
- `independent_rediscovery`: legal when an owner forms a matching fingerprint with empty `parent_belief_ids` and channel `independent_rediscovery` (analysis may later cluster with peers).
- Exceeding hop cap (if a max hop is derived from mutation policy token edits chain depth, default soft cap **8**) drops with `reason_code=cultural_feature_hop_cap`.

### Mutation and recombination (locked)

- **Mutation:** when `mutation_policy.allow_mutation`, a learner may alter fingerprint tokens (≤ `max_token_edits`) before storing / re-transmitting; set `mutated=true`; retain parent refs; use seed-derived stream from `rng_namespace`.
- **Recombination:** when `recombination_policy.allow_recombination` and ≥2 same-kind parents meet `min_token_overlap`, create a child fingerprint with `recombined=true`, ordered `parent_belief_ids` (≤ `max_parents`), `hop_index = max(parent.hop_index)+1`.
- Incorrect / distorted beliefs remain legal.
- Never copy parent object identity across owners — only digest tokens + provenance metadata.

### Transmission rules (locked)

1. **Public acts / observations only.** Uptake reads the owner’s `Observation` / delivered communications / teaching relations / artifact interpretation cues — never another agent’s private ledger.
2. **No silent copy.** Receiving never assigns another owner’s belief objects, mentorship lineage rows, naming/norm/convention/narrative entries, developmental rows, or relationship profiles into the learner. Learner forms **fresh** `SubjectiveCulturalBelief` rows.
3. **Incorrect information is legal.** Distorted fingerprints and false associations are allowed; analysis measures mutation/diffusion — never engine “truth correction.”
4. **Learner modification.** Mutation/recombination follow the locked policies; re-transmission of a mutated belief creates a child hop.
5. **No global Culture.** WorldEngine does not mint culture edges, tradition laws, or society-wide feature tables.
6. **Anti-hardcode:** no kinship→culture auto-handoff; no elder→culture-bearer rule; ELDER ≠ culture authority.
7. Do not parse free-form utterance text for culture; use closed structured tokens / digests only.

### Cognition wiring (locked)

1. Read mode only from `cultural_feature_provenance.cultural_feature_mode`. Do **not** add a cultural mode to `AgentCognitionSpec`.
2. When channel absent: no cultural-feature ledger writes; V2 modes and v3-08 mentorship behave unchanged.
3. When present/`deterministic`: after applicability gate, run hooks in `CognitiveLoop` / runtime finalization that (a) form/reinforce beliefs from enabled channels, (b) apply mutation/recombination when policy allows, (c) apply `bias_policy` to communicate/practice selection, (d) delegate compose adapters when `uptake_compose` bits and underlying modes are on; skip with stable DEBUG otherwise.
4. Must not import analysis metric APIs, `AnalyticalCulturalTrait`, or another agent’s private cognition.
5. Import walls: `agents/cognition/cultural_features.py` must not import `world._*` authority modules or `analysis.*`. Analysis may duck-type audit rows by type name / fields (mentorship_metrics pattern).

### Analytical traits (locked)

- `AnalyticalCulturalTrait` in `analysis/` only: trait_id, feature_kind, cluster fingerprint, carrier_count, channel_histogram, mean `hop_index` / mutation / recombination rates, optional generation spread when lifecycle records present.
- Computed from harvested `CulturalFeatureAudit` rows and/or owner ledger snapshots.
- Must not be imported by `agents`, `world`, `simulation` cognition paths, or `api` live loops.
- Never overload `cultural_transmission@1`, `cultural_narrative_lineage@1`, or mentorship metrics for these signals.

### Analysis metrics (locked)

| Family id | Version string | Signal |
| --- | --- | --- |
| `cultural_feature_provenance` | `cultural_feature_provenance@1` | Channel mix; per-kind counts; independent_rediscovery share; evidence coverage |
| `cultural_trait_diffusion` | `cultural_trait_diffusion@1` | Analytical trait carrier counts; geographic/social spread proxies from public evidence; mean hop; optional generation_index spread |
| `cultural_feature_mutation` | `cultural_feature_mutation@1` | Mutation rate; recombination rate; mean parent arity; fingerprint churn |

Keep `all_metric_specifications` / `frozenset(MetricFamilyId)` tests green (**+3** family ids; `METRIC_FAMILY_COUNT` 50 → **53**).

### Experiment AL (locked)

- Catalog arm `experiment-al-cultural-transmission-provenance` on **runner-config-v31**, off the V1 gate.
- Profile: `cultural_transmission_provenance_profile` in `src/experiments/catalog.py` (export from `experiments/__init__.py`) requiring `cultural_historical_memory=True` + exact `cultural_feature_provenance`; may compose selected V2 modes and optional lifecycle.
- Arms (minimal set):

| Arm | Flag / object | Extra |
| --- | --- | --- |
| `al-channel-off` | flag off / object absent | Baseline; no cultural-feature ledger |
| `al-belief-only` | on; `bias_policy.mode=ignore`; compose all false | Prove subjective beliefs + provenance rows via observation/communication channels only |
| `al-multi-channel` | on; ≥3 provenance channels enabled | Observation + communication + teaching (or artifact) mix |
| `al-mutation` | on; `mutation_policy.allow_mutation=true` | Mutated re-transmit; mutation metric nonzero |
| `al-recombination` | on; recombination allow | Two-parent recombine; recombination metric nonzero |
| `al-analytical` | on | Prove analytical traits appear in analysis only; cognition never sees them |
| `al-flags-off` | all V3 off | Hash stability vs pre-plan |

- Prove: flags-off / channel-off hashes stable; V1 gate + `test_v2_scientific_invariants` green under V3 flags-off; SEMANTIC count stays **43**.
- Matrix allowlist includes AL without enabling on default batches.

### Observer (locked)

- Default: **no** new semantic event types (SEMANTIC count stays **43**).
- Protocol stays `observer-protocol-v1`. No culture-map chrome required.

### Out of scope

- Owning `multi_polity_migration`, `institutional_economy`, `multi_hop_testimony_tracking`
- Kinship cultural inheritance / memory handoff
- Society-wide shared Culture store or global vocabulary/tradition table that controls agents
- WorldEngine-authoritative culture edges / new event write-pair
- New `AgentCommand` kinds by default
- Alembic `0018`
- Full Research UI / Godot culture atlases
- Auto-writing SelfModel “role=culture_bearer” from WorldEngine
- New `AgentCognitionSpec` cultural enum
- Replacing V2 Experiment S / `cultural_transmission@1` or deleting mentorship/narrative metrics
- Natural-language free-form myth/law authority

## Commit Plan

- **Commit 1** (after tasks 1–4): `feat(v3): own cultural_historical_memory with runner-config-v31 contracts`
- **Commit 2** (after tasks 5–8): `feat(v3): owner-scoped cultural feature beliefs and provenance`
- **Commit 3** (after tasks 9–12): `feat(v3): compose V2 uptake sources with mutation and recombination`
- **Commit 4** (after tasks 13–16): `feat(v3): analytical traits, provenance metrics, and Experiment AL`
- **Commit 5** (after tasks 17–18): `docs(v3): cultural transmission provenance seams and flags-off regression proofs`

## Tasks

### Phase 1: Domain & config contracts

- [x] Task 1: Add cultural feature kind / channel / belief / audit contracts and blank-slate extension
  - Deliverable: Frozen closed `CulturalFeatureKindId`, `CulturalTransmissionChannelId`, exact `SubjectiveCulturalBelief` fields (including `content_key`, `content_fingerprint`, `hop_index` with `CULTURAL_FEATURE_FIRST_HOP_INDEX=0`), `CulturalFeatureLedger`, metadata-only `CulturalFeatureAudit`. Extend `BLANK_SLATE_SUBJECTIVE_STORES` **and** `BlankSlateStoreCounts` with `cultural_features`. Extend forbidden inheritance / deny-list aliases (`culture_pack`, `global_culture`, `society_culture`, `encyclopedia_download`). Package under `agents/cognition/cultural_features.py` — **not** `world/` authority. No `Culture` type anywhere in domain packages.
  - LOGGING: DEBUG on empty ledger construct `{owner_id, belief_count=0}`; ERROR with stable `code=` on provenance-less / cap / hop-cap writes; never log feature prose / free text / fingerprints as payload surrogates beyond short digest ids already used elsewhere.
  - Files: `src/agents/cognition/cultural_features.py`, `src/agents/cognition/__init__.py`, `src/simulation/new_agent_initialization.py`, `tests/unit/test_cultural_feature_contracts.py`
  - Depends on: —

- [x] Task 2: Own `cultural_historical_memory` and add exact `CulturalFeatureProvenanceSpec` + nested policies + `runner-config-v31`
  - Deliverable: Add flag to `_V3_OWNED_CAPABILITY_FLAGS`. Exact key-set validation for root + nested `mutation_policy` / `recombination_policy` / `uptake_compose` / `bias_policy` / `applicability`. Implement flag×object gate matrix (cultural-only forbids; kinship-only **allows** cultural; `v31_requires_cultural_feature_provenance`). Rejects include: `cultural_feature_requires_v31`, `cultural_feature_requires_flag`, `cultural_feature_without_flag`, `cultural_feature_mode_invalid`, `cultural_only_forbids_lifecycle_spec`, `cultural_only_forbids_new_agent_init`, plus kind/channel/policy validation codes. Export `RUNNER_SCHEMA_VERSION_V31` and `example_cultural_feature_provenance_spec()`. Widen allowlists v30→v31; update generational/kinship/cultural gates.
  - LOGGING: INFO on accepted v31 cultural channel `{feature_kind_count, channel_count, mutation_allowed, recombination_allowed, applicability}`; WARN/ERROR on reject codes (metadata only).
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/__init__.py`, `src/simulation/runner.py` (owned-flag allow path), `tests/unit/test_runner_config_v31_cultural_features.py`, `tests/unit/test_compatibility_matrix.py`
  - Depends on: 1

- [x] Task 3: Matrix finalize priority and `cultural_transmission_provenance_profile` stub
  - Deliverable: Insert `cultural_feature_on` **before** `mentorship_on` in matrix finalize; widen needs sets; add `cultural_transmission_provenance_profile` in `src/experiments/catalog.py` and export from `experiments/__init__.py` (catalog arms in Task 15).
  - LOGGING: DEBUG finalize choice `schema=runner-config-v31 reason=cultural_feature_on`.
  - Files: `src/experiments/matrix_schema.py`, `src/experiments/catalog.py`, `src/experiments/__init__.py`, unit tests
  - Depends on: 2

- [x] Task 4: Docs architecture seam note (stub) for cultural_historical_memory ownership
  - Deliverable: Short Downstream V3 note that v31 owns `cultural_historical_memory`, dual subjective/analytical representation, no global Culture, defers kinship handoff / NL language authority. Update the V3 seams table row that currently says cultural is unowned. Full docs checkpoint remains Task 17.
  - LOGGING: n/a (docs only)
  - Files: `docs/architecture.md` (V3 extension seams + Downstream V3 contract pins), optionally `docs/cognition-runtime.md` pointer
  - Depends on: 2

### Phase 2: Subjective ledger, provenance, runtime carry

- [x] Task 5: Implement belief formation with closed provenance channels and hop_index
  - Deliverable: Deterministic upsert/reinforce for beliefs from public evidence; require a channel in `enabled_provenance_channels`; `independent_rediscovery` when no foreign parent (`hop_index=0`); child hops increment; evidence ref caps; `max_beliefs_per_owner` eviction.
  - LOGGING: DEBUG belief form/reinforce `{owner_id, feature_kind, channel, hop_index, mutated, recombined, reason_code}`; never free text.
  - Files: `src/agents/cognition/cultural_features.py`, `tests/unit/test_cultural_feature_provenance.py`
  - Depends on: 1

- [x] Task 6: Implement mutation and recombination paths
  - Deliverable: Policy-gated mutation (≤ `max_token_edits`, `rng_namespace` stream) before store/re-transmit; recombination from ≥2 same-kind parents with `min_token_overlap`; `hop_index = max(parents)+1` on recombine; parent refs retained; incorrect beliefs legal; hop cap `cultural_feature_hop_cap`.
  - LOGGING: DEBUG `{feature_kind, mutated, recombined, parent_count, hop_index, reason_code}`; ERROR on policy violations with stable codes.
  - Files: `src/agents/cognition/cultural_features.py`, `tests/unit/test_cultural_feature_mutation.py`
  - Depends on: 5

- [x] Task 7: Runtime / checkpoint carry for cultural feature ledgers
  - Deliverable: Plumb `cultural_features` through `CognitiveLoopProposal` / `CognitiveLoopResult` (`contracts.py` / `models.py` / `loop.py`) → `AgentRuntime._commit_cultural_features` → `_cultural_features` → checkpoint export/restore (`run_control.py`) → `Perspective` (`perception.py`) → `export_cultural_feature_audits` on runtime + runner. Blank-slate admits still zero.
  - LOGGING: DEBUG commit `{owner_id, belief_count}`; WARN on checkpoint shape mismatch codes.
  - Files: `src/agents/cognition/loop.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/models.py`, `src/simulation/agent_runtime.py`, `src/simulation/run_control.py`, `src/simulation/perception.py`, `src/simulation/runner.py`, related snapshot types, unit tests
  - Depends on: 1, 6

- [x] Task 8: Optional bias_policy in selection (passthrough by default)
  - Deliverable: When `bias_policy.mode=prefer_aligned_features`, add float/integer vote weight toward communicate/practice partners or closed content tokens matching high-confidence beliefs (`communicate_weight`, `content_affinity`); mode `ignore` is passthrough. Never inject analytical traits.
  - LOGGING: DEBUG bias applied `{partner_or_token_band, weight_band, reason_code}` / skip reasons.
  - Files: deliberation / teaching / practice selection hooks as needed, unit tests
  - Depends on: 5, 7

### Phase 3: Compose existing uptake sources (no internal copy)

- [x] Task 9: Wire observation + imitation + communication channels
  - Deliverable: Form beliefs from observed practices/utterances without copying peer ledgers; imitation uses public practice evidence only; communication uses delivered Talk/Ask/Tell structured content tokens; respect feature→source mapping for `practice` / `social_expectation` / etc.
  - LOGGING: DEBUG uptake `{channel, feature_kind, hop_index, reason_code}`.
  - Files: `src/agents/cognition/cultural_features.py`, observation/communication integration points, unit tests
  - Depends on: 6, 7

- [x] Task 10: Wire teaching + mentorship compose (optional)
  - Deliverable: When `uptake_compose.teaching` / `mentorship` true and those channels/modes are on, record provenance `teaching` (mentorship teacher ids as evidence metadata only); never clone mentorship lineage rows — map mentorship content kinds → feature kinds per locked table (stories→narrative_element, vocabulary→term, social_practices→practice/social_expectation, production_recipes→production_technique).
  - LOGGING: DEBUG compose skip/write `{teaching_on, mentorship_on, mapped_kind, reason_code}`.
  - Files: cultural_features + thin hooks near teaching/mentorship, unit tests
  - Depends on: 6, 7

- [x] Task 11: Wire artifact + naming/narrative/norm/convention compose (optional)
  - Deliverable: Follow locked feature→source map. `symbolic_association` forms only from `artifacts` (interpreted marks) and optional `narrative` tokens — never free-form myth prose. Naming→term; narrative→narrative_element; norms/conventions→social_expectation / practice. Skip when compose bit or mode off (`cultural_feature_kind_unsatisfiable` DEBUG when kind enabled but unsatisfiable).
  - LOGGING: DEBUG mode skip / write `{source_mode, feature_kind, reason_code}`.
  - Files: cultural_features + thin compose adapters, unit tests
  - Depends on: 6, 7

- [x] Task 12: Prove dual-representation boundary (subjective ≠ analytical)
  - Deliverable: Architecture/unit tests that `AnalyticalCulturalTrait` modules are not importable from cognition; subjective ledger types are not written by analysis; no `Culture` symbol in `world` / engine snapshots. (Requires Task 14 types/modules to exist.)
  - LOGGING: test failure messages with stable `code=` where applicable.
  - Files: `tests/architecture/` or unit boundary tests, import-linter contracts if needed
  - Depends on: 7, 11, 14

### Phase 4: Audits, analytical traits, metrics, experiment

- [x] Task 13: CulturalFeatureAudit harvest on SimulationRunnerResult
  - Deliverable: Harvest metadata-only audits via `export_cultural_feature_audits` (mirror mentorship); attach on runner finalize; not on result document schema. Unit tests cover ledger→audit after commit (compose channels covered in Tasks 9–11).
  - LOGGING: INFO harvest `{audit_count}` at finalize; never payloads.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner.py`, `src/simulation/agent_runtime.py`, unit tests
  - Depends on: 7

- [x] Task 14: Register analytical traits + three metric families
  - Deliverable: `AnalyticalCulturalTrait` + compute helpers using audit `hop_index` for mean hop; three new `MetricFamilyId` members; `METRIC_FAMILY_COUNT` 50→53; specifications + compute modules; unit tests for provenance/diffusion/mutation. Do not overload `cultural_transmission@1`.
  - LOGGING: analysis modules stay metadata-safe; tests assert availability bands.
  - Files: `src/analysis/cultural_feature_metrics.py` (or split), `src/analysis/specifications.py`, `src/analysis/metric_service.py`, `src/analysis/__init__.py`, unit tests
  - Depends on: 13

- [x] Task 15: Experiment AL catalog arms and matrix allowlist
  - Deliverable: `experiment-al-cultural-transmission-provenance` with locked arms (`al-channel-off`, `al-belief-only`, `al-multi-channel`, `al-mutation`, `al-recombination`, `al-analytical`, `al-flags-off`); wire through `cultural_transmission_provenance_profile`; off V1 gate; matrix allowlist only.
  - LOGGING: INFO experiment build `{experiment_id, arm_id, schema_version}`.
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, `tests/unit/test_cultural_feature_catalog_arm.py`
  - Depends on: 3, 14

- [x] Task 16: Flags-off / channel-off regression proofs
  - Deliverable: V1 gate + `test_v2_scientific_invariants` green under V3 flags-off; AE–AK hashes stable when cultural channel absent; SEMANTIC count **43**; cultural-feature import-linter walls green; Experiment S unchanged; cultural-only and kinship+cultural gate unit proofs.
  - LOGGING: test logs only on failure; use stable assert messages with `code=` where applicable.
  - Files: `tests/unit/test_v3_cultural_features_regression.py`, architecture/import-linter configs if needed
  - Depends on: 2, 15

### Phase 5: Documentation checkpoint

- [x] Task 17: Mandatory docs via `/aif-docs` for cultural transmission provenance seams
  - Deliverable: Document owned `cultural_historical_memory`, v31 `cultural_feature_provenance`, dual representation, closed kinds/channels, hop_index, mutation/recombination, Experiment AL, no global Culture, deferred kinship handoff / NL authority. Update DESCRIPTION/ARCHITECTURE summaries as required by docs skill.
  - LOGGING: n/a
  - Files: `docs/architecture.md`, `docs/cognition-runtime.md`, `docs/analysis-metrics.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md` as needed
  - Depends on: 16

- [x] Task 18: Close plan verification checklist notes
  - Deliverable: Ensure plan tasks checkbox-ready for `/aif-verify`; list exact reject codes, metric ids, experiment id, and SEMANTIC/METRIC_FAMILY_COUNT pins in a short “Verification pins” subsection at end of this plan file if anything drifted during implement (implementer updates pins only — no new scope).
  - LOGGING: n/a
  - Files: this plan file (pins only), optionally `docs/architecture.md`
  - Depends on: 17

## Verification pins (as implemented)

| Pin | Value |
| --- | --- |
| Runner schema | `runner-config-v31` when `cultural_feature_provenance` present (`v31_requires_cultural_feature_provenance`) |
| V3 flag owned | `cultural_historical_memory` (new ownership) |
| Event write-pair | none (subjective + analysis only) |
| Alembic head | `0017` |
| `AgentCommand` count | 26 |
| SEMANTIC count | 43 |
| `METRIC_FAMILY_COUNT` | 53 (+3) |
| Experiment | `experiment-al-cultural-transmission-provenance` (off V1 gate) |
| Profile | `cultural_transmission_provenance_profile` |
| Metric families | `cultural_feature_provenance@1`, `cultural_trait_diffusion@1`, `cultural_feature_mutation@1` |
| Feature kinds | `practice`, `narrative_element`, `term`, `production_technique`, `social_expectation`, `symbolic_association` |
| Provenance channels | `observation`, `teaching`, `communication`, `artifact`, `imitation`, `independent_rediscovery` |
| Hop index | root / independent rediscovery = `0` (`CULTURAL_FEATURE_FIRST_HOP_INDEX`) |
| Dual types | `SubjectiveCulturalBelief` (cognition) ≠ `AnalyticalCulturalTrait` (analysis-only) |
| Forbidden | global `Culture` object / society culture controller |
| AL arms | `al-channel-off`, `al-belief-only`, `al-multi-channel`, `al-mutation`, `al-recombination`, `al-analytical`, `al-flags-off` |
| Reject codes (core) | `cultural_feature_requires_v31`, `cultural_feature_requires_flag`, `cultural_feature_without_flag`, `cultural_feature_mode_invalid`, `v31_requires_cultural_feature_provenance`, `cultural_only_forbids_lifecycle_spec`, `cultural_only_forbids_new_agent_init`, `cultural_feature_hop_cap` |
