# Implementation Plan: V3-08 Intergenerational Teaching and Mentorship

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-06

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Extends M7 generational work after developmental learning so agents form persistent mentor/apprentice relationships and multi-hop teaching lineages without kinship auto-handoff or society-wide culture stores.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-08-intergenerational-mentorship.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; suggested stem `v3-08-intergenerational-mentorship`; git.create_branches=false so stem is description slug (branch-derived naming disabled)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; scope is explicitly v3-08 under M7 so linkage uses M7

## Compatibility contract

This plan **does not own a new `V3CapabilityFlags` slot**. It deepens owned **`generational_population`** with an opt-in mentorship channel that extends V2 `TeachingInteractionMode` into persistent mentor/apprentice bonds and multi-generation teaching lineages. It must preserve V1/V2 and AE–AJ behavior when the new channel is off / defaults are passthrough.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents receive immutable per-agent `Observation` / `Perspective` only. `WorldEvent` records remain immutable and append-only. Subjective state stays outside the objective fold. Godot remains read-only. Deterministic replay continues. No scripted civilization / mentor-caste outcomes.
2. Flag ownership unchanged. Keep `generational_population` and `kinship_inheritance` owned. Do **not** own `multi_polity_migration`, `institutional_economy`, `cultural_historical_memory`, or `multi_hop_testimony_tracking`.
3. Flags-off / channel-off = prior baseline. With all V3 flags off, or with lifecycle on but `mentorship` absent/passthrough, trajectories and `exact_trajectory_hash` match the pre-plan baseline for AE–AJ where applicable.
4. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2/V3 versions in the same change that adds a write version.
5. **No internal-state copy.** Mentorship never copies another agent's competence model, advice store, semantic beliefs, world-model hypotheses, naming/norm/convention/narrative ledgers, developmental ledger, relationships, goals, or SelfModel into a learner. Transmission uses public teaching acts + owner-scoped uptake only (same three-store discipline as V2 teaching, generalized to closed content kinds).
6. **No kinship cultural inheritance handoff.** Parent→child knowledge transfer stays deferred under the `kinship_inheritance` flag slot. Mentorship bonds may form across any agents (including different `generation_index`); kinship edges do not auto-create bonds or transfer content.
7. **WorldEngine does not mint mentor roles.** No profession / teacher / apprentice / elder_teacher labels; no world-snapshot mentorship keys by default. Bonds and lineages are owner-scoped (or analysis-joined from audits).
8. Preserve v3-02–v3-07 locks: blank-slate deny-list; closed Observation `lifecycle` object; ELDER ≠ leader; related ≠ affection/trust/loyalty; no parent→caregiver hardwiring; developmental learning never society-injects; Alembic head `0017` by default.
9. Preserve V2 teaching locks: no new `AgentCommand`; acts attach as one empty `CommunicationRelation` on Talk/Ask/Tell; offers refolded from events; analysis-only audits; teaching may transmit incorrect information.
10. Optional tracing/analysis/observer presentation stay outside the objective fold / `EvidenceManifest`.
11. Closed `AgentCommand` count stays **26** unless a later need proves a new command is required (default: reuse Talk/Ask/Tell + existing skill/practice paths).

## Goal

Extend V2 teaching into **persistent mentor/apprentice relationships** so agents sustain long-running teaching bonds and multi-hop chains (Alice → Bob → Carol → David) that may transmit closed content kinds:

- practical skills
- factual beliefs
- causal hypotheses
- vocabulary
- production recipes
- social practices
- stories
- warnings

Deliver:

- Exact `mentorship` root sibling on **`runner-config-v30`** (deepens `generational_population`; no new V3 flag)
- Owner-scoped mentorship bond ledger + taught-content lineage (teacher, learner, content, attempts, learning evidence, confidence, lineage)
- Uptake that **never copies internal state**; incorrect teaching remains legal; learners may **revise/mutate** what they were taught
- Metadata-only mentorship audits for analysis
- Analysis metrics for **transmission fidelity** and **mutation** across hops / generations
- Off-gate Experiment AK comparing ephemeral teaching vs persistent mentorship vs multi-generation re-teach chains

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` remains the only authority over objective physical reality and objective skill/lifecycle mutations.
2. Agents never receive another agent's private cognition, stores, or a society encyclopedia.
3. `WorldEvent` records remain immutable; authoritative history stays append-only.
4. Taught content may be wrong, incomplete, or teacher-biased and never folds into objective replay identity.
5. LLM output remains non-authoritative (may only choose already-allowed act/content tokens when provider path is enabled).
6. No scripted “mentor_assigned / apprentice_graduated / culture_preserved / lineage_faithful” booleans.
7. Godot remains read-only; this plan does **not** add schoolhouse / mentor-chrome presentation.
8. Runs remain reproducible where claimed (explicit seeds, deterministic streams, deterministic fakes / recorded LLM paths).

### Capability ownership (locked)

1. Remain on owned `generational_population`. Enabling mentorship requires the lifecycle channel on (`generational_population=True`) plus exact `mentorship` config on `runner-config-v30`.
2. Do **not** claim `cultural_historical_memory`.
3. Do **not** implement kinship cultural inheritance handoff under `kinship_inheritance`.
4. Other unowned V3 flags still fail closed.
5. When `mentorship` is absent / passthrough defaults: AE–AJ bit-identity matches pre-plan for the same roster and seeds (no new mentorship ledger writes from this channel).
6. V2 `TeachingInteractionMode` remains the public-act substrate. Mentorship **composes** teaching; it does not replace `AdviceStore` / skill teaching fold. Channel-off leaves Experiments S/T and AJ teaching paths unchanged.
7. Run-level `predictive_world_model` remains a V2 flag: causal-hypothesis content kind uplifts only when that flag is enabled; mentorship rows for other kinds do not require it.

### Scope split (locked)

| This plan (v3-08) | Deferred |
| --- | --- |
| Persistent mentor/apprentice bonds from public teaching history | Kinship cultural inheritance / estate knowledge handoff |
| Multi-hop taught-content lineage with learner mutation | Society-wide `cultural_historical_memory` / language evolution |
| Closed content kinds over existing owner-scoped stores | Natural-language free-form curriculum |
| Fidelity + mutation metrics; Experiment AK | Full Research UI / Godot mentorship dashboards |
| Compose V2 teaching + optional v3-07 developmental `instruction` source | Owning remaining V3 flag slots |
| Optional bond bias toward repeated partners | Hardwired elder→child mentor assignment |

### Runner configuration versioning (locked)

Introduce `RUNNER_SCHEMA_VERSION_V30 = "runner-config-v30"`:

- Exact root key set = **v29 accepted roots** ∪ sibling root object **`mentorship`**. Preserve v27–v29 flag-conditional gates (kinship-only forbids lifecycle/init/dependency_care/developmental_learning/mentorship; generational requires lifecycle/init rules as today). Do **not** treat “full v29” as an unconditional copy of every optional root.
- Default write remains `runner-config-v4` when all V3 flags are off and no existing mode requires a higher schema.
- `mentorship` present ⇒ `schema_version == runner-config-v30` and `generational_population=True` with exact `population_lifecycle` (stable reject `mentorship_requires_v30` / `mentorship_requires_lifecycle`). Object present with `mentorship_mode=disabled` is **rejected** (`mentorship_mode_invalid`) — use absent object for off.
- `generational_population=False` forbids non-empty `mentorship` (reject `mentorship_without_lifecycle_flag`).
- Decode of v23–v29 synthesizes no `mentorship` object (absent ≡ channel off / passthrough).
- Widen **every** mode allowlist currently capped at `v29` to also accept `v30`.
- Gate rewrite: `generational_population=True` accepts `{v24,v25,v26,v27,v28,v29,v30}`; `kinship_inheritance=True` still accepts `{v27,v28,v29,v30}` (v30 may carry kinship + dependency_care + developmental_learning + mentorship together when lifecycle flag is on).
- `experiments/matrix_schema.py` finalize/allowlist accepts `v30`; **priority if-elif** inserts `mentorship_on` **before** `developmental_learning_on` so present mentorship selects `v30`; widen `needs_lifecycle` / `needs_init` sets to include `v30` when `generational_population`; AE stays v24; AF v25; AG v26; AH v27; AI v28; AJ v29; default finalize stays `v4` when V3 flags off.
- Update `simulation/compatibility.py` version matrix row for v30 (**no new event-schema write-pair** — keep agreed-or headed by dependency-care → kinship → provenance → lifecycle → …).

### MentorshipSpec (exact root sibling — locked)

Root key `mentorship` exact children:

| Key | Role |
| --- | --- |
| `enabled_content_kinds` | Ordered frozen list of closed content-kind ids (subset of the closed set below; empty forbidden when object present — use absent object for off) |
| `bond_policy` | Exact object controlling how durable mentor/apprentice bonds form and decay |
| `lineage_policy` | Exact object controlling taught-content lineage, hop caps, and mutation |
| `partner_bias` | Exact object modulating communicate/teach partner preference from bond strength |
| `mentorship_mode` | Closed id: must be `deterministic` when object present — **not** a `V3CapabilityFlags` bit and **not** a new `AgentCognitionSpec` enum |
| `requires_teaching_interaction` | Bool; default `true` — when true, every agent participating in bonds must have `TeachingInteractionMode.DETERMINISTIC` (fail closed `mentorship_requires_teaching`) |
| `max_bonds_per_owner` | Positive int hard cap on active bonds per owner (deterministic eviction when exceeded) |
| `max_lineage_entries_per_owner` | Positive int hard cap on taught-content lineage rows per owner |
| `applicability` | Closed id: `all_live_agents` (default) \| `mid_run_new_agents` \| `lifecycle_learning_stage` |

**Closed content-kind ids (exact):**

| Id | Meaning (owner-scoped uptake) | Primary existing seam to compose |
| --- | --- | --- |
| `practical_skills` | Skill advice / competence / objective practice via V2 teaching acts | `TeachingInteractionMode` + `SkillLearningMode` |
| `factual_beliefs` | Semantic belief evidence from structured Tell / explain-style claims | existing belief revision + trust-aware testimony (fresh evidence only) |
| `causal_hypotheses` | Private causal hypotheses | `predictive_world_model` uplift only when flag on; else skip with stable DEBUG |
| `vocabulary` | Terminology ledger entries | `SemanticNamingMode` |
| `production_recipes` | Crafting/building/production practice claims (closed domain tokens only) | skill domains + optional convention practice |
| `social_practices` | Convention / habitual practice entries | `SocialConventionMode` (+ norms when enabled) |
| `stories` | Narrative lineage entries | `CulturalNarrativeMode` |
| `warnings` | Hazard / caution advice rows (owner-scoped; may be false) | teaching advice + optional developmental/hazard seams |

Forbidden content-kind aliases: `culture_pack`, `encyclopedia`, `society_memory`, `inherited_language`, role tokens (`mentor`, `apprentice`, `elder_teacher` as content ids), `full_self_model_copy`.

**`bond_policy` exact keys:**

| Key | Role |
| --- | --- |
| `form_after_successful_acts` | Non-neg int — min delivered teaching acts between pair before a bond may form |
| `min_trust` | Float in `[0, 1]` — listener’s projected trust toward partner floor |
| `reinforce_on_learning_evidence` | Bool — reinforce bond strength when learner records learning evidence |
| `decay_per_tick` | Float in `[0, 1]` — deterministic strength decay when no teaching act in window |
| `offer_window_extend` | Non-neg int — optional extend of teaching `offer_window` for bonded pairs only (0 = no extend) |
| `symmetric` | Bool — default `false` (directed mentor→apprentice); `true` allows mutual bonds as two directed edges |

**`lineage_policy` exact keys:**

| Key | Role |
| --- | --- |
| `max_hop_depth` | Positive int hard cap (default ≤ 8) for Alice→… chains |
| `record_attempts` | Bool — record teaching attempts even when uptake fails |
| `allow_learner_mutation` | Bool — default `true`; learner may revise content fingerprint / confidence after uptake |
| `mutation_requires_evidence` | Bool — default `true`; mutation only after owner evidence (observation/practice/experiment) |
| `confidence_inherit_mode` | Closed id: `learner_trust_scaled` (default) \| `fresh_floor` — never copy teacher confidence verbatim |

**`partner_bias` exact keys:**

| Key | Role |
| --- | --- |
| `mode` | `ignore` \| `prefer_bonded` (default `prefer_bonded`) |
| `communicate_weight` | Float in `[0, 1]` added to communicate float term toward bonded partners (mirrors `teaching_response_weight` style) |
| `content_kind_affinity` | Bool — prefer teaching content kinds already present on the bond |

### Subjective mentorship ledger & lineage (locked)

Introduce owner-scoped types under `agents/cognition/mentorship.py` (**not** `world/` / `social/` authority):

**`MentorshipBond` (exact minimal fields):**

| Field | Role |
| --- | --- |
| `partner_agent_id` | Other agent id (opaque) |
| `role` | Closed id: `mentor` \| `apprentice` (owner’s role toward partner — **not** a world profession label) |
| `content_kinds` | Frozen subset of enabled kinds for this bond |
| `strength` | Quantized float in `[0, 1]` |
| `formed_tick` | Tick |
| `last_teaching_tick` | Tick |
| `policy_version` | Mentorship policy version string |

**`TaughtContentLineageEntry` (exact minimal fields — tracks required dimensions):**

| Field | Role |
| --- | --- |
| `teacher_agent_id` | Teacher |
| `learner_agent_id` | Learner (owner) |
| `content_kind` | Closed content-kind id |
| `content_key` | Stable opaque concept id / digest — never free-form society text |
| `content_fingerprint` | Opaque digest of learner’s current representation (mutable) |
| `parent_lineage_id` | Optional prior lineage id (Bob→Carol cites Alice→Bob) |
| `lineage_root_id` | Root id for the chain |
| `hop_index` | Non-neg int (Alice→Bob = 0 or 1 consistently; document choice in code) |
| `attempt_count` | Teaching attempts observed for this content |
| `learning_evidence_count` | Successful uptake / practice / belief-mass events |
| `confidence` | Learner’s confidence (not teacher’s) |
| `mutated` | Bool — true after learner revision |
| `acquired_tick` / `last_updated_tick` | Ticks |
| `evidence_refs` | Opaque EventId / communication id tokens only |
| `policy_version` | Policy version |

- Every write records provenance via `teacher_agent_id` + `evidence_refs` + lineage ids. Missing teacher/content_kind/content_key is a hard fail.
- **Runtime carry (exact pattern, mirror developmental / cultural_narratives):** `CognitiveLoopResult.mentorship` → `AgentRuntime._commit_mentorship` → `AgentRuntime._mentorship` → runtime checkpoint restore; also plumb `CognitiveLoopProposal` / `SubjectiveSnapshot` optional fields for parity.
- Extend `BLANK_SLATE_SUBJECTIVE_STORES` + `BlankSlateStoreCounts` with `mentorship_bonds` and `taught_content_lineage` (or a single `mentorship` compound count — prefer two counters for deny-list clarity).
- Extend forbidden inheritance / deny-list aliases with `mentor_pack`, `apprentice_download`, `lineage_clone` (keep existing society aliases).
- Do **not** widen `CausalProvenanceKind`; mentorship sources live on lineage rows.
- No Alembic `0018`.

### Transmission rules (locked)

1. **Public acts only.** Mentorship uptake piggybacks delivered Talk/Ask/Tell teaching relations (and existing demonstrate / practice_together / explain / request_instruction folds). Do not parse utterance text for pedagogy.
2. **No silent copy.** Receiving never assigns the teacher’s believed level, support/counter, objective skill, semantic belief payload, world-model hypothesis object, naming/norm/convention/narrative entry, developmental ledger row, or relationship profile into the learner. Learner forms **fresh** owner-scoped evidence / advice / ledger rows.
3. **Incorrect information is legal.** A teacher with false beliefs may produce false bands / false fingerprints; analysis measures misinformation / mutation — never engine “truth correction.”
4. **Learner modification.** When `allow_learner_mutation=true`, after uptake the learner may change `content_fingerprint` / `confidence` (and optional child domain entry) when `mutation_requires_evidence` is satisfied. Set `mutated=true`. Re-teaching the mutated content to a third agent creates a new hop with `parent_lineage_id` pointing at the mutator’s entry.
5. **Multi-generation chains.** Alice → Bob → Carol → David is modeled as lineage hops (`lineage_root_id` stable; `hop_index` increments; `parent_lineage_id` links). Exceeding `max_hop_depth` drops with stable `reason_code=mentorship_hop_cap`.
6. **Bond formation.** Bonds form only from observed successful teaching acts + trust floor — never from kinship edges, lifecycle stage alone, or WorldEngine assignment.
7. **Anti-hardcode:** no elder→dependent mentor rule; no parent→child auto-bond; ELDER ≠ mentor.

### Cognition wiring (locked)

1. Read mode only from `mentorship.mentorship_mode`. Do **not** add `MentorshipMode` to `AgentCognitionSpec`.
2. When channel absent: no mentorship ledger writes; V2 teaching and v3-07 developmental learning behave unchanged.
3. When present/`deterministic`: after applicability gate, run mentorship hooks in `CognitiveLoop` / runtime finalization that (a) update bonds from teaching audits/acts, (b) record lineage attempts/evidence, (c) apply partner_bias to communicate selection, (d) delegate content-kind uptake to existing mode updaters when those modes/flags are on; if a required mode for an enabled content kind is off, skip with stable DEBUG reason.
4. Compose with `developmental_learning` when both present: developmental `instruction` source may cite mentorship `teacher_agent_id`; rates still follow v3-07 composition order; mentorship does not bypass blank-slate admit.
5. Must not import analysis metric APIs or another agent's private cognition.
6. Import walls: `agents/cognition/mentorship.py` must not import `world._teaching` / `world._skills` / `world._state`. World teaching policy remains in `world/_teaching.py` and must not import `agents`.

### Mentorship audits (locked)

Emit metadata-only `MentorshipAudit` rows (mirror `TeachingAudit` / `DevelopmentalAcquisitionAudit`):

- owner id, partner id token, role, content_kind, hop_index, attempt/evidence counts, confidence band, mutated bool, tick, reason code
- **Never** content payloads / free text / fingerprints as log/audit payload surrogates beyond opaque truncated tokens if already used elsewhere for digests

Harvest at runtime finalize or experiment collector; analysis metrics consume audits (+ optional lineage export) only.

### Observation (locked)

1. No Observation wire widening required for channel-off.
2. Do **not** add mentor/apprentice payloads to Observation.
3. Live/restored observation parity remains the hard gate; mentorship ledger is subjective carry, not Observation.

### Analysis metrics (locked)

Register analysis-only families (never imported by cognition). Do **not** overload `cultural_transmission@1`, `developmental_*`, or `cultural_narrative_lineage@1` for mentorship chain signals — add siblings (v3-07 pattern).

| Family id | Version string | Core signals |
| --- | --- | --- |
| `mentorship_fidelity` | `mentorship_fidelity@1` | Per-root / per-hop fidelity of learner fingerprint vs ancestor at hop 0; mean fidelity by hop_index; belief/advice match rates for skill/belief kinds; misinformation when teacher claim contradicts objective where defined |
| `mentorship_mutation` | `mentorship_mutation@1` | Mutation rate by hop; mean hop depth; chain count (Alice→…→David); fingerprint churn; share of mutated re-teach edges |
| `mentorship_bonds` | `mentorship_bonds@1` | Active bond counts, mean strength, directed reciprocity, content-kind coverage per bond, generation_index cross-bond share when lifecycle records present |

Follow skill/developmental registration via harvested audits. Keep `all_metric_specifications` / `frozenset(MetricFamilyId)` tests green (**+3** family ids; `METRIC_FAMILY_COUNT` 47 → **50**).

### Experiment AK (locked)

- Catalog arm `experiment-ak-intergenerational-mentorship` on **runner-config-v30**, off the V1 gate.
- Profile: `intergenerational_mentorship_profile` requiring `generational_population=True` + exact `mentorship` + lifecycle + teaching DETERMINISTIC on participants; may compose `developmental_learning` on learner arms.
- Arms (minimal set):

| Arm | Mentorship | Teaching | Extra |
| --- | --- | --- | --- |
| `ak-ephemeral` | absent / channel-off | DETERMINISTIC | Baseline V2 teaching; no bonds/lineage |
| `ak-bonded` | on; single-hop bonds | DETERMINISTIC | Prove durable bonds + partner bias; no forced kinship |
| `ak-chain` | on; `max_hop_depth` ≥ 3 | DETERMINISTIC | Seed Alice→Bob→Carol→David re-teach path; prove lineage hops + mutation |
| `ak-mutation` | on; `allow_learner_mutation=true` | DETERMINISTIC | Learner revises fingerprint before re-teaching; mutation metrics nonzero |
| `ak-false-teaching` | on | DETERMINISTIC | Teacher with false high-band claims; fidelity/misinformation signals |
| `ak-channel-off` | — | as needed | lifecycle on, **no** `mentorship` object |

- Prove: flags-off / channel-off hashes stable; V1 gate + `test_v2_scientific_invariants` green under V3 flags-off; SEMANTIC count stays **43**.
- Matrix allowlist includes AK without enabling on default batches.

### Observer (locked)

- Default: **no** new semantic event types (SEMANTIC count stays **43**).
- Protocol stays `observer-protocol-v1`. No mentor/apprentice chrome.

### Out of scope

- Owning `cultural_historical_memory`, `multi_polity_migration`, `institutional_economy`, `multi_hop_testimony_tracking`
- Kinship cultural inheritance / memory handoff
- Society-wide shared culture store or global vocabulary table
- WorldEngine-authoritative mentor edges / new event write-pair
- New `AgentCommand` kinds by default
- Alembic `0018`
- Full Research UI / Godot schooling dashboards
- Auto-writing SelfModel “role=mentor/apprentice” from WorldEngine
- New `AgentCognitionSpec` mentorship enum
- Replacing V2 `AdviceStore` or deleting Experiments S/T

## Commit Plan

- **Commit 1** (after tasks 1–4): `feat(v3): add mentorship contracts and runner-config-v30`
- **Commit 2** (after tasks 5–8): `feat(v3): owner-scoped mentorship bonds and taught-content lineage`
- **Commit 3** (after tasks 9–12): `feat(v3): compose content-kind uptake without internal-state copy`
- **Commit 4** (after tasks 13–16): `feat(v3): mentorship audits, fidelity/mutation metrics, and Experiment AK`
- **Commit 5** (after tasks 17–18): `docs(v3): intergenerational mentorship seams and flags-off regression proofs`

## Tasks

### Phase 1: Domain & config contracts

- [x] Task 1: Add mentorship content-kind / bond / lineage contracts and blank-slate extension
  - Deliverable: Frozen closed `MentorshipContentKindId`, `MentorshipBond`, `TaughtContentLineageEntry`, empty ledgers. Extend `BLANK_SLATE_SUBJECTIVE_STORES` **and** `BlankSlateStoreCounts` with mentorship counters. Extend forbidden inheritance / deny-list aliases (`mentor_pack`, `apprentice_download`, `lineage_clone`). Package under `agents/cognition/mentorship.py` — **not** `world/` authority.
  - LOGGING: DEBUG on empty ledger construct `{owner_id, bond_count=0, lineage_count=0}`; ERROR with stable `code=` on provenance-less / hop-cap writes; never log content payloads / free text.
  - Files: `src/agents/cognition/mentorship.py`, `src/agents/cognition/__init__.py`, `src/simulation/new_agent_initialization.py`, `tests/unit/test_mentorship_contracts.py`
  - Depends on: —

- [x] Task 2: Add `MentorshipSpec` exact root sibling and `runner-config-v30` acceptance
  - Deliverable: Exact key-set validation for `mentorship` (`enabled_content_kinds`, `bond_policy`, `lineage_policy`, `partner_bias`, `mentorship_mode`, …). Rejects: `mentorship_requires_v30`, `mentorship_requires_lifecycle`, `mentorship_without_lifecycle_flag`, `mentorship_mode_invalid`, `mentorship_requires_teaching`. Export `RUNNER_SCHEMA_VERSION_V30`. Widen allowlists v29→v30; generational/kinship gates accept v30.
  - LOGGING: INFO on accepted v30 mentorship channel `{content_kind_count, bond_policy_form_after, max_hop_depth}`; WARN/ERROR on reject codes (metadata only).
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/__init__.py`, `tests/unit/test_runner_config_v30_mentorship.py`, `tests/unit/test_compatibility_matrix.py`
  - Depends on: 1

- [x] Task 3: Matrix finalize priority and profile scaffolding for v30
  - Deliverable: Insert `mentorship_on` **before** `developmental_learning_on` in matrix finalize; widen `needs_lifecycle` / `needs_init`; add profile stub `intergenerational_mentorship_profile` (catalog arm in Task 15).
  - LOGGING: DEBUG finalize choice `schema=runner-config-v30 reason=mentorship_on`.
  - Files: `src/experiments/matrix_schema.py`, related profile modules, unit tests
  - Depends on: 2

- [x] Task 4: Docs architecture seam note (stub) for mentorship channel
  - Deliverable: Short Downstream V3 note that v30 mentorship deepens `generational_population`, composes V2 teaching, defers kinship handoff / `cultural_historical_memory`. Full docs checkpoint remains Task 17.
  - LOGGING: n/a (docs only); if logging helper scripts exist, keep silent.
  - Files: `docs/architecture.md` (V3 extension seams), optionally `docs/cognition-runtime.md` pointer
  - Depends on: 2

### Phase 2: Bonds, lineage, runtime carry

- [x] Task 5: Implement bond formation / decay / caps
  - Deliverable: Deterministic bond form after `form_after_successful_acts` + `min_trust`; reinforce on learning evidence; `decay_per_tick`; `max_bonds_per_owner` eviction. Directed roles `mentor`/`apprentice` are owner-scoped only.
  - LOGGING: DEBUG bond form/reinforce/decay `{owner_id, partner_id, strength_band, reason_code}`; never log free text.
  - Files: `src/agents/cognition/mentorship.py`, unit tests for bond lifecycle
  - Depends on: 1

- [x] Task 6: Implement taught-content lineage with hop linking and mutation
  - Deliverable: Record teacher/learner/content/attempts/evidence/confidence/lineage fields; `parent_lineage_id` + `lineage_root_id` + `hop_index`; hop cap; learner mutation path when policy allows; incorrect teaching legal.
  - LOGGING: DEBUG lineage write `{content_kind, hop_index, mutated, attempt_count, evidence_count, reason_code}`; ERROR on missing provenance.
  - Files: `src/agents/cognition/mentorship.py`, `tests/unit/test_mentorship_lineage.py`
  - Depends on: 1, 5

- [x] Task 7: Runtime / checkpoint carry for mentorship ledgers
  - Deliverable: Mirror developmental/cultural_narratives: proposal → result → `_commit_mentorship` → runtime field → checkpoint export/restore. Blank-slate admits still zero.
  - LOGGING: DEBUG commit `{owner_id, bond_count, lineage_count}`; WARN on checkpoint shape mismatch codes.
  - Files: `src/agents/cognition/loop.py`, `src/simulation/agent_runtime.py`, `src/simulation/run_control.py`, related snapshot types, unit tests
  - Depends on: 1, 6

- [x] Task 8: Partner bias in communicate / teaching selection
  - Deliverable: When `partner_bias.mode=prefer_bonded`, add `communicate_weight` toward bonded partners (integer votes still win); optional content-kind affinity. Mode `ignore` is passthrough.
  - LOGGING: DEBUG bias applied `{partner_id, weight_band, reason_code=bond_prefer}` / skip reasons.
  - Files: `src/agents/cognition/deliberation.py` (or existing compare-pair site), `src/agents/cognition/teaching.py` / selection hooks, unit tests
  - Depends on: 5, 7

### Phase 3: Content-kind composition (no internal copy)

- [x] Task 9: Wire practical_skills + production_recipes + warnings via V2 teaching acts
  - Deliverable: Mentorship records attempts/evidence around existing demonstrate/explain/practice_together/request_instruction; advice/belief/objective stores remain separate; no copy of teacher levels. Recipes map to closed crafting/building/production domain tokens; warnings to hazard caution advice rows.
  - LOGGING: DEBUG uptake `{content_kind, act, band, reason_code}`; misinformation stays analysis-side.
  - Files: `src/agents/cognition/mentorship.py`, teaching integration points, `src/world/_teaching.py` only if offer_window_extend needs a pure policy hook (no agents import), unit tests
  - Depends on: 6, 7

- [x] Task 10: Wire factual_beliefs + causal_hypotheses uptake adapters
  - Deliverable: Fresh belief evidence from structured testimony only; causal hypotheses update only when `predictive_world_model=True`, else skip DEBUG `causal_hypotheses_requires_flag`. Never clone teacher belief/hypothesis objects.
  - LOGGING: DEBUG `{content_kind, accepted|discounted|skipped, reason_code}`.
  - Files: belief / world-model integration modules under `agents/cognition/`, unit tests
  - Depends on: 6, 7

- [x] Task 11: Wire vocabulary + social_practices + stories adapters
  - Deliverable: Compose `SemanticNamingMode`, `SocialConventionMode` / norms, `CulturalNarrativeMode` for mentorship-enabled kinds; learner may mutate fingerprints before re-teaching; skip when mode off.
  - LOGGING: DEBUG mode skip / write `{content_kind, mode_on, mutated, reason_code}`.
  - Files: naming/convention/narrative integration, unit tests
  - Depends on: 6, 7

- [x] Task 12: Compose with developmental_learning instruction source (optional co-enable)
  - Deliverable: When both v29 developmental_learning and v30 mentorship present, instruction acquisitions may cite mentorship teacher ids; blank-slate admit unchanged; no society download. Channel isolation: either alone still works.
  - LOGGING: DEBUG compose `{developmental_on, mentorship_on, teacher_present}`.
  - Files: `src/agents/cognition/developmental_learning.py` (minimal hook), mentorship compose tests
  - Depends on: 9, 10, 11

### Phase 4: Audits, metrics, experiment

- [x] Task 13: MentorshipAudit harvest on SimulationRunnerResult
  - Deliverable: Metadata-only audits; export helper analogous to teaching/developmental audits; not on result document schema.
  - LOGGING: INFO harvest `{audit_count}` at finalize; DEBUG per-row suppressed in hot paths unless verbose flag; never payloads.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner.py`, unit tests
  - Depends on: 7, 9

- [x] Task 14: Register mentorship_fidelity / mentorship_mutation / mentorship_bonds metrics
  - Deliverable: Three new `MetricFamilyId` members; `METRIC_FAMILY_COUNT` 47→50; specifications + compute modules; Alice→…→David hop fidelity/mutation proofs in unit tests. Do not overload `cultural_transmission@1`.
  - LOGGING: analysis modules stay metadata-safe; tests assert availability bands.
  - Files: `src/analysis/mentorship_metrics.py` (or split files), `src/analysis/specifications.py`, `src/analysis/metric_service.py`, `src/analysis/__init__.py`, unit tests
  - Depends on: 13

- [x] Task 15: Experiment AK catalog arms and matrix allowlist
  - Deliverable: `experiment-ak-intergenerational-mentorship` with locked arms (`ak-ephemeral`, `ak-bonded`, `ak-chain`, `ak-mutation`, `ak-false-teaching`, `ak-channel-off`); off V1 gate; matrix allowlist only.
  - LOGGING: INFO experiment build `{experiment_id, arm_id, schema_version}`.
  - Files: `src/experiments/catalog.py`, profile modules, `tests/unit/test_mentorship_catalog_arm.py`
  - Depends on: 3, 14

- [x] Task 16: Flags-off / channel-off regression proofs
  - Deliverable: V1 gate + `test_v2_scientific_invariants` green under V3 flags-off; AE–AJ hashes stable when mentorship absent; SEMANTIC count **43**; mentorship import-linter walls green.
  - LOGGING: test logs only on failure; use stable assert messages with `code=` where applicable.
  - Files: `tests/unit/test_v3_mentorship_regression.py`, architecture/import-linter configs if needed
  - Depends on: 2, 15

### Phase 5: Documentation checkpoint

- [x] Task 17: Mandatory docs via `/aif-docs` for mentorship seams
  - Deliverable: Document v30 `mentorship` channel, content kinds, no-copy rule, lineage/mutation, Experiment AK, deferred kinship handoff. Update DESCRIPTION/ARCHITECTURE summaries as required by docs skill.
  - LOGGING: n/a
  - Files: `docs/architecture.md`, `docs/cognition-runtime.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md` as needed
  - Depends on: 16

- [x] Task 18: Close plan verification checklist notes
  - Deliverable: Ensure plan tasks checkbox-ready for `/aif-verify`; list exact reject codes, metric ids, experiment id, and SEMANTIC/METRIC_FAMILY_COUNT pins in a short “Verification pins” subsection at end of this plan file if anything drifted during implement (implementer updates pins only — no new scope).
  - LOGGING: n/a
  - Files: this plan file (pins only), optionally `docs/architecture.md`
  - Depends on: 17

## Verification pins (as implemented)

| Pin | Value |
| --- | --- |
| Runner schema | `runner-config-v30` when `mentorship` present (`v30_requires_mentorship`) |
| V3 flag owned | none new; deepen `generational_population` |
| Event write-pair | none (subjective only) |
| Alembic head | `0017` |
| `AgentCommand` count | 26 |
| SEMANTIC count | 43 |
| `METRIC_FAMILY_COUNT` | 50 (+3) |
| Experiment | `experiment-ak-intergenerational-mentorship` (off V1 gate) |
| Metric families | `mentorship_fidelity@1`, `mentorship_mutation@1`, `mentorship_bonds@1` |
| AK arms | `ak-channel-off`, `ak-ephemeral`, `ak-bonded`, `ak-chain`, `ak-mutation`, `ak-false-teaching` |
| Reject codes | `mentorship_requires_v30`, `mentorship_requires_lifecycle`, `mentorship_without_lifecycle_flag`, `mentorship_mode_invalid`, `mentorship_requires_teaching`, `mentorship_hop_cap`, `mentorship_partner_bias_mode_invalid`, `mentorship_max_hop_invalid`, `mentorship_confidence_inherit_invalid`, `mentorship_profile_*` |
| Lineage hop | first hop `hop_index=0` (`LINEAGE_FIRST_HOP_INDEX`) |
