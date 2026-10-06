# Implementation Plan: V3-07 Developmental Learning and Socialization

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-06
Improved: 2026-10-06 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Continues M7 generational work after blank-slate bootstrap and dependency care so mid-run agents acquire domain knowledge gradually from experience and social exposure without society-wide injection or a new V3 flag.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-07-developmental-learning.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; suggested stem `v3-07-developmental-learning`; git.create_branches=false so stem is description slug (branch-derived naming disabled)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; scope is explicitly v3-07 under M7 so linkage uses M7
INFO [aif-improve] applied refinement: species_default_developmental_v1 modes-on/content-empty; BLANK_SLATE_SUBJECTIVE_STORES + deny-list aliases; v29 matrix finalize before dependency_care + needs_lifecycle/init; reject present+disabled mode; AgentRuntime carry mirrors cultural_narratives (CognitiveLoopResult→_commit→checkpoint); rate compose dependency learning_rate_zero→lifecycle→base×source; ledger rows without predictive_world_model, uplift only when flag on; DevelopmentalAcquisitionAudit harvest; AJ arm matrices + teacher/learner mode bundles; MetricFamilyId +3; no CausalProvenanceKind widen; Task deps 4←1, 8/9/14←2, 13←8+12

## Compatibility contract

This plan **does not own a new `V3CapabilityFlags` slot**. It deepens owned **`generational_population`** with an opt-in developmental-learning channel that composes existing owner-scoped learning modes for newly created (and optionally staged) agents. It must preserve V1/V2 and AE–AI behavior when the new channel is off / defaults are passthrough.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents receive immutable per-agent `Observation` / `Perspective` only. `WorldEvent` records remain immutable and append-only. Subjective state stays outside the objective fold. Godot remains read-only. Deterministic replay continues. No scripted civilization / enculturation outcomes.
2. Flag ownership unchanged. Keep `generational_population` and `kinship_inheritance` owned. Do **not** own `multi_polity_migration`, `institutional_economy`, `cultural_historical_memory`, or `multi_hop_testimony_tracking`.
3. Flags-off / channel-off = prior baseline. With all V3 flags off, or with lifecycle on but `developmental_learning` absent/passthrough, trajectories and `exact_trajectory_hash` match the pre-plan baseline for AE–AI where applicable.
4. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2/V3 versions in the same change that adds a write version.
5. **No society-wide knowledge injection.** Mid-run agents remain blank-slate at admit (`assert_blank_slate_subjective_state`); this plan never copies another agent's ledgers, world model, narratives, naming, norms, conventions, skills, beliefs, relationships, or goals into a new owner.
6. **No cultural inheritance handoff engine.** Parent→child knowledge transfer stays deferred under the `kinship_inheritance` flag slot. Learning here is post-admit acquisition via configured sources only.
7. **WorldEngine does not mint cultural facts.** Objective skills/artifacts/lifecycle may still update as today; developmental knowledge content is owner-scoped and subjective (or analysis-joined). Analysis metrics never feed cognition.
8. Preserve v3-02–v3-06 locks: blank-slate deny-list; closed Observation `lifecycle` object; ELDER ≠ leader; related ≠ affection/trust/loyalty; no parent→caregiver hardwiring; Alembic head `0017` by default.
9. Optional tracing/analysis/observer presentation stay outside the objective fold / `EvidenceManifest`.
10. Closed `AgentCommand` count stays **26** unless a later need proves a new command is required (default: reuse existing Move/Search/Talk/Ask/Tell/Teach/artifact/skill paths).

## Goal

Implement learning trajectories for newly created agents so they gradually acquire owner-scoped knowledge of:

- locations
- resources
- hazards
- skills
- social actors
- vocabulary
- norms
- stories
- practices

Sources may include (closed, configurable enable set):

- direct observation
- instruction
- imitation
- communication
- external artifacts
- experimentation

Deliver:

- Exact `developmental_learning` root sibling on **`runner-config-v29`** (deepens `generational_population`; no new V3 flag)
- Closed `species_default_developmental_v1` (modes-on, content-empty) for mid-run learners
- Owner-scoped developmental knowledge ledger with **acquisition provenance** per entry
- Metadata-only `DevelopmentalAcquisitionAudit` harvest for analysis
- Configurable per-domain learning rates composed with stage `learning_rate_factor`, dependency-care `learning_rate_zero`, and optional `CognitiveBudgetMode`
- Divergence property: different teachers / environments ⇒ different world models / ledgers for different new agents
- Analysis metrics proving acquisition coverage, source mix, and cross-agent divergence
- Off-gate Experiment AJ comparing isolated vs socialized vs artifact-assisted learning

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` remains the only authority over objective physical reality and objective skill/lifecycle mutations.
2. Agents receive immutable agent-specific `Observation` only; they never receive a society encyclopedia, shared culture blob, or another agent's private cognition.
3. `WorldEvent` records remain immutable; authoritative history stays append-only.
4. Subjective developmental knowledge may be wrong, incomplete, or teacher-biased and never folds into objective replay identity.
5. LLM output remains non-authoritative.
6. No scripted “culture_transferred / language_known / map_known / norms_inherited / stories_implanted” booleans at birth or admit.
7. Godot remains read-only; this plan does **not** add school/nursery presentation chrome.
8. Runs remain reproducible where claimed (explicit seeds, deterministic streams, deterministic fakes / recorded LLM paths).

### Capability ownership (locked)

1. Remain on owned `generational_population`. Enabling developmental learning requires the lifecycle channel on (`generational_population=True`) plus exact `developmental_learning` config on `runner-config-v29`.
2. Do **not** claim `cultural_historical_memory` (society-wide / language-evolution / historical-memory ownership stays for a later plan).
3. Do **not** implement kinship cultural inheritance handoff under `kinship_inheritance`.
4. Other unowned V3 flags still fail closed.
5. When `developmental_learning` is absent / passthrough defaults: AE–AI bit-identity matches pre-plan for the same roster and seeds (no new developmental ledger writes from this channel).
6. Run-level `predictive_world_model` remains a V2 flag: developmental ledger rows for locations/resources/hazards **do not require** it; CausalWorldModel uplift runs only when that flag is enabled.

### Scope split (locked)

| This plan (v3-07) | Deferred |
| --- | --- |
| Post-admit gradual acquisition with provenance | Society-wide `cultural_historical_memory` flag ownership |
| Compose existing V2 learning modes under developmental rates | Kinship cultural inheritance / estate knowledge handoff |
| Isolated / socialized / artifact-assisted experiment arms | Natural-language free-form curriculum |
| Configurable rates + cognitive-budget coupling | Full Research UI / Godot schooling chrome |
| Divergence proofs across teachers/environments | Owning remaining V3 flag slots |
| `species_default_developmental_v1` capacity pack | Widening `CausalProvenanceKind` beyond observation/memory |

### Runner configuration versioning (locked)

Introduce `RUNNER_SCHEMA_VERSION_V29 = "runner-config-v29"`:

- Exact root key set = **v28 accepted roots** ∪ sibling root object **`developmental_learning`**. Preserve v27/v28 flag-conditional gates (kinship-only forbids lifecycle/init/dependency_care/developmental_learning; generational requires lifecycle/init rules as today). Do **not** treat “full v28” as an unconditional copy of every optional root.
- Default write remains `runner-config-v4` when all V3 flags are off and no existing mode requires a higher schema.
- `developmental_learning` present ⇒ `schema_version == runner-config-v29` and `generational_population=True` with exact `population_lifecycle` (stable reject `developmental_learning_requires_v29` / `developmental_learning_requires_lifecycle`). Object present with `developmental_learning_mode=disabled` is **rejected** (`developmental_learning_mode_invalid`) — use absent object for off.
- Mid-run blank-slate admits still follow v25+ `new_agent_initialization` rules when used. Developmental stage children still require v26-compatible lifecycle encoding when non-default.
- `generational_population=False` forbids non-empty `developmental_learning` (reject `developmental_learning_without_lifecycle_flag`).
- Decode of v23–v28 synthesizes no `developmental_learning` object (absent ≡ channel off / passthrough).
- Widen **every** mode allowlist currently capped at `v28` to also accept `v29`.
- Gate rewrite: `generational_population=True` accepts `{v24,v25,v26,v27,v28,v29}`; `kinship_inheritance=True` still accepts `{v27,v28,v29}` (v29 may carry kinship + dependency_care + developmental_learning together when lifecycle flag is on).
- `experiments/matrix_schema.py` finalize/allowlist accepts `v29`; **priority if-elif** inserts `developmental_learning_on` **before** `dependency_care_on` so present developmental_learning selects `v29`; widen `needs_lifecycle` / `needs_init` sets to include `v29` when `generational_population`; AE stays v24; AF v25; AG v26; AH v27; AI v28; default finalize stays `v4` when V3 flags off.
- Update `simulation/compatibility.py` version matrix row for v29 (**no new event-schema write-pair** — keep agreed-or headed by dependency-care → kinship → provenance → lifecycle → …).

### DevelopmentalLearningSpec (exact root sibling — locked)

Root key `developmental_learning` exact children:

| Key | Role |
| --- | --- |
| `enabled_domains` | Ordered frozen list of closed domain ids (subset of the closed set below; empty forbidden when object present — use absent object for off) |
| `enabled_sources` | Ordered frozen list of closed source ids (subset of the closed set below; empty forbidden when object present) |
| `domain_rates` | Exact map domain_id → rate object (must cover every `enabled_domains` entry exactly once) |
| `source_weights` | Exact map source_id → weight in `(0, 1]` (must cover every `enabled_sources` entry exactly once) |
| `applicability` | Closed id: `mid_run_new_agents` (default) \| `lifecycle_learning_stage` \| `all_live_agents` |
| `cognitive_budget_coupling` | Exact object gating interaction with `CognitiveBudgetMode` |
| `developmental_learning_mode` | Closed id: must be `deterministic` when object present — **not** a `V3CapabilityFlags` bit and **not** a new `AgentCognitionSpec` enum |
| `learner_species_defaults_id` | Closed id: default `species_default_developmental_v1` (must be registered); AJ/profile may pin this via `new_agent_initialization.species_defaults_id` |
| `max_entries_per_domain` | Positive int hard cap per owner/domain (deterministic eviction when exceeded) |
| `divergence_salt_policy` | Closed id: `owner_stream` (default) — acquisition RNG / tie-breaks use owner-scoped streams only |

**Closed domain ids (exact):**

| Id | Meaning (owner-scoped) | Primary existing seam to compose |
| --- | --- | --- |
| `locations` | Place familiarity / topology | Developmental ledger always; CausalWorldModel uplift iff `predictive_world_model` |
| `resources` | Resource presence / harvest affordances | Ledger + optional world-model / search pathways |
| `hazards` | Danger / exposure regularities | Ledger + optional world-model hazard episodes |
| `skills` | Competence beliefs vs objective skill ledger | `SkillLearningMode` |
| `social_actors` | Directed familiarity / ToM-lite of others | relationships + optional `advanced_social_inference` |
| `vocabulary` | Terminology ledger entries | `SemanticNamingMode` |
| `norms` | Social-norm ledger entries | `SocialNormMode` |
| `stories` | Narrative lineage entries | `CulturalNarrativeMode` |
| `practices` | Convention / habitual practice entries | `SocialConventionMode` (+ teaching when instruction source on) |

Forbidden domain aliases: `culture_pack`, `encyclopedia`, `society_memory`, `inherited_language`, biology/role tokens (`student`, `elder_teacher` as domain ids).

**Closed source ids (exact):**

| Id | Meaning |
| --- | --- |
| `observation` | Direct perception this tick / reconstructed own observation |
| `instruction` | Teaching-interaction / structured instruct path |
| `imitation` | Observed peer successful action → candidate practice/skill update |
| `communication` | Talk/Ask/Tell testimony forming fresh owner traces (never copy sender stores) |
| `artifact` | `ArtifactInterpretationMode` meaning formation from objective marks |
| `experimentation` | Own failed/succeeded trials updating hypotheses |

Forbidden sources: `society_download`, `parent_memory_copy`, `global_dictionary`, `analysis_feedback`.

**`domain_rates[domain_id]` exact keys:**

| Key | Role |
| --- | --- |
| `base_rate` | Float in `(0, 1]` — acquisition probability / mass multiplier before stage factor |
| `stage_compose` | Closed id: `multiply_lifecycle_learning_rate` (default) \| `ignore_lifecycle` |
| `min_exposures` | Non-neg int before first durable entry may form |
| `confidence_floor` | Float in `[0, 1]` for first write |

**`cognitive_budget_coupling` exact keys:**

| Key | Role |
| --- | --- |
| `mode` | `ignore` \| `respect_enforced` (default `respect_enforced`) |
| `acquisition_cost_units` | Non-neg int charged against tick budget ledger when an acquisition attempt runs under `CognitiveBudgetMode.ENFORCED` |
| `degrade_policy` | Closed id: `skip_acquisition` (default) \| `reduce_rate` — never skip the closed `AgentCommand` |

**Effective rate composition order (locked):**

1. If dependency-care marks `learning_rate_zero` for the entity → effective rate `0`
2. Else if `stage_compose=multiply_lifecycle_learning_rate` → multiply by lifecycle `learning_rate_factor` (and objective `learning_rate_by_entity` when present)
3. Multiply by `base_rate` × `source_weights[source]`
4. Apply cognitive-budget `degrade_policy` last (may skip or reduce)

### Species defaults (locked)

Register closed `species_default_developmental_v1` in `new_agent_initialization` species registry:

- Fresh `AgentCognitionSpec` for the new owner with **modes on / content empty** for the AJ learner bundle: `SkillLearningMode.DETERMINISTIC`, `TeachingInteractionMode.DETERMINISTIC`, `SemanticNamingMode.DETERMINISTIC`, `SocialNormMode.DETERMINISTIC`, `SocialConventionMode.DETERMINISTIC`, `CulturalNarrativeMode.DETERMINISTIC`, `ArtifactInterpretationMode.DETERMINISTIC` (and world-model cognition mode enabled only when the run’s `predictive_world_model` flag is on — pack itself must not invent run-level V2 flags).
- Ledgers/stores start empty; blank-slate assert still passes (`developmental_knowledge=0` plus existing store zeros).
- `species_default_v1` remains unchanged (all modes default DISABLED) so AF/AE bit-identity stays intact when AJ is not selected.
- `developmental_learning.learner_species_defaults_id` + AJ `new_agent_initialization.species_defaults_id` pin the developmental pack.

### Subjective ledger & provenance (locked)

Introduce owner-scoped `DevelopmentalKnowledgeLedger` under `agents/cognition/developmental_learning.py` (**not** `world/` / `social/` authority):

- Exact entry fields (minimal): `domain_id`, `concept_key` (stable opaque id / digest — never free-form society text), `source_id`, `confidence`, `acquired_tick`, `teacher_agent_id` (optional; instruction/imitation/communication only), `evidence_refs` (opaque EventId / communication id / artifact id tokens only), `policy_version`
- Every write records **acquisition provenance**. Missing provenance is a hard fail.
- Mode-vs-content: channel/modes may be enabled at admit; ledger **content** starts empty.
- Extend `BLANK_SLATE_SUBJECTIVE_STORES` + `BlankSlateStoreCounts` with `developmental_knowledge`; extend forbidden inheritance / deny-list aliases with `society_download`, `culture_pack`, `encyclopedia`, `language_pack` (already partially present — keep closed).
- **Runtime carry (exact pattern, mirror `cultural_narratives`):** `CognitiveLoopResult.developmental_knowledge` → `AgentRuntime._commit_developmental_knowledge` → `AgentRuntime._developmental_knowledge` → runtime checkpoint restore; also plumb `CognitiveLoopProposal` / `SubjectiveSnapshot` optional fields if naming/narrative siblings require them for parity.
- Do **not** widen `CausalProvenanceKind` (`observation`/`memory` only); developmental sources live on ledger `source_id`.
- No Alembic `0018`.

### Cognition wiring (locked)

1. Read mode only from `developmental_learning.developmental_learning_mode`. Do **not** add `DevelopmentalLearningMode` to `AgentCognitionSpec`.
2. When channel absent: no developmental ledger writes; existing modes behave unchanged.
3. When present/`deterministic`: after blank-slate admit (per `applicability`), run acquisition hook in `CognitiveLoop` / runtime finalization that selects domains/sources, applies effective rates, respects budgets, and delegates to existing mode updaters when those modes are on; if a required mode for an enabled domain is off, skip with stable DEBUG reason (no silent encyclopedia).
4. Ledger provenance rows for locations/resources/hazards always eligible under observation/experimentation sources; CausalWorldModel hypothesis updates only when `predictive_world_model=True`.
5. Teaching / communication / artifacts remain existing paths; developmental policy only modulates what the **receiver** may acquire.
6. Anti-hardcode: no elder→dependent teacher rule; no kinship edge ⇒ knowledge transfer.
7. Must not import analysis metric APIs or another agent's private cognition.

### Acquisition audits (locked)

Emit metadata-only `DevelopmentalAcquisitionAudit` rows (mirror `SkillAudit` / teaching audits): owner id, domain, source, teacher present/id token, tick, acquired bool, confidence band, reason code — **never** concept payloads / free text. Harvest at runtime finalize or experiment collector; analysis metrics consume audits only.

### Observation (locked)

1. No Observation wire widening required for channel-off.
2. Do **not** add society knowledge payloads to Observation.
3. Live/restored observation parity remains the hard gate; developmental ledger is subjective carry, not Observation.

### Analysis metrics (locked)

Register analysis-only families (never imported by cognition):

| Family id | Version string | Core signals |
| --- | --- | --- |
| `developmental_acquisition` | `developmental_acquisition@1` | Per-agent domain coverage, mean confidence, time-to-first-entry, exposures-to-acquisition |
| `developmental_source_mix` | `developmental_source_mix@1` | Share of entries by `source_id`; teacher entropy when teachers present |
| `developmental_divergence` | `developmental_divergence@1` | Pairwise ledger (/ optional world-model) distance between mid-run agents under matched seeds but different teachers/environments |

Follow `skill_learning@1` registration via harvested audits. Do **not** overload `knowledge_diffusion` / `cultural_transmission` for these signals. Keep `all_metric_specifications` / `frozenset(MetricFamilyId)` tests green (**+3** family ids).

### Experiment AJ (locked)

- Catalog arm `experiment-aj-developmental-learning` on **runner-config-v29**, off the V1 gate.
- Profile: `developmental_learning_profile` requiring `generational_population=True` + exact `developmental_learning` + lifecycle + `new_agent_initialization.species_defaults_id=species_default_developmental_v1`.
- **Teacher (bootstrap) mode bundle:** enable the DETERMINISTIC modes required by the arm’s domains (at least teaching + communication strategy as needed; naming/norm/convention/narrative/artifact/skill as listed per arm). Teachers are not blank-slate.
- **Learner (mid-run) pack:** `species_default_developmental_v1` only.
- Arms (minimal set):

| Arm | `enabled_sources` | `enabled_domains` (min) | Extra |
| --- | --- | --- | --- |
| `aj-isolated` | `observation`, `experimentation` | `locations`, `resources`, `hazards`, `skills` | No peers / teaching off for learners’ social sources; blank-slate at admit |
| `aj-socialized` | `+ instruction`, `imitation`, `communication` | `+ social_actors`, `vocabulary`, `norms`, `stories`, `practices` | ≥2 teacher cohorts; prove ledger divergence across learners |
| `aj-artifact` | `observation`, `artifact` (± experimentation) | `vocabulary`, `practices`, `locations` (min) | `ArtifactInterpretationMode.DETERMINISTIC` + placed marks; no society download |
| `aj-budget-stress` (optional) | subset of socialized/artifact | subset | `CognitiveBudgetMode.ENFORCED` tight limits |
| `aj-channel-off` | — | — | lifecycle on, **no** `developmental_learning` object |

- Optional: enable run-level `predictive_world_model` on a socialized/artifact sub-arm when testing world-model uplift; default AJ arms may stay flag-off and still prove ledger divergence.
- Prove: flags-off / channel-off hashes stable; V1 gate + `test_v2_scientific_invariants` green under V3 flags-off; SEMANTIC count stays **43**.
- Matrix allowlist includes AJ without enabling on default batches.

### Observer (locked)

- Default: **no** new semantic event types (SEMANTIC count stays **43**).
- Protocol stays `observer-protocol-v1`. No school/teacher chrome.

### Out of scope

- Owning `cultural_historical_memory`, `multi_polity_migration`, `institutional_economy`, `multi_hop_testimony_tracking`
- Kinship cultural inheritance / memory handoff
- Society-wide shared culture store or global vocabulary table
- Widening `CausalProvenanceKind` for developmental sources (use ledger `source_id`)
- Scripted successful socialization mandates
- New `AgentCommand` kinds by default
- New event-schema / codec write-pair by default
- Alembic `0018`
- Full Research UI / Godot schooling dashboards
- Auto-writing SelfModel “role=student/teacher” from WorldEngine
- New `AgentCognitionSpec` developmental enum / teaching-style runner schema bump for the mode

## Commit Plan

- **Commit 1** (after tasks 1–4): `feat(v3): add developmental-learning contracts, species pack, and runner-config-v29`
- **Commit 2** (after tasks 5–8): `feat(v3): owner-scoped developmental ledger with provenance and rate/budget gates`
- **Commit 3** (after tasks 9–11): `feat(v3): compose domain acquisition adapters without society injection`
- **Commit 4** (after tasks 12–15): `feat(v3): developmental audits, metrics, and Experiment AJ`
- **Commit 5** (after tasks 16–17): `docs(v3): developmental learning seams and flags-off regression proofs`

## Tasks

### Phase 1: Domain & config contracts

- [x] Task 1: Add developmental domain/source contracts and blank-slate extension
  - Deliverable: Frozen closed `DevelopmentalDomainId` / `DevelopmentalSourceId`, rate/weight types, empty `DevelopmentalKnowledgeLedger` + provenance entry types. Extend `BLANK_SLATE_SUBJECTIVE_STORES` **and** `BlankSlateStoreCounts` with `developmental_knowledge`. Extend forbidden inheritance / deny-list aliases with `society_download`, `culture_pack`, `encyclopedia` (keep existing `language_pack` / map deny names). No society pack types. Package under `agents/cognition/` — **not** `world/` authority.
  - LOGGING: DEBUG on empty ledger construct `{owner_id, domain_count=0}`; ERROR with stable `code=` on provenance-less write attempts; never log concept payloads / free text.
  - Files: `src/agents/cognition/developmental_learning.py`, `src/agents/cognition/__init__.py`, `src/simulation/new_agent_initialization.py`, `tests/unit/test_developmental_learning_contracts.py`
  - Depends on: —

- [x] Task 2: Register `species_default_developmental_v1` (modes-on, content-empty)
  - Deliverable: Closed species pack enabling the learner mode bundle in Design Decisions while every subjective ledger/store count remains 0 at admit. Keep `species_default_v1` unchanged. Unit-test: pack enables modes; blank-slate assert passes; unknown id still fails closed.
  - LOGGING: DEBUG `species_defaults_resolved species_defaults_id=species_default_developmental_v1 agent_id=…`; never log peer store copies.
  - Files: `src/simulation/new_agent_initialization.py`, `tests/unit/test_species_default_developmental_v1.py`
  - Depends on: Task 1

- [x] Task 3: Introduce `DevelopmentalLearningSpec` / runner-config-v29 (no new V3 flag)
  - Add `RUNNER_SCHEMA_VERSION_V29`; exact root = **v28 accepted roots** ∪ `{developmental_learning}` preserving flag-conditional kinship-only vs lifecycle gates; encode/decode exact keys including `learner_species_defaults_id`; reject forbidden domain/source/role keys; reject present+`disabled` (`developmental_learning_mode_invalid`); require `generational_population=True` + exact `population_lifecycle` (+ init rules when mid-run admits apply); widen allowlists capped at v28 → v29.
  - Matrix finalize: insert `developmental_learning_on` **before** `dependency_care_on`; widen `needs_lifecycle` / `needs_init` for v29; AE–AI finalize versions unchanged; update compatibility matrix (no new write-pair).
  - Fail closed still for unowned V3 flags. Do **not** add a new flag to `_V3_OWNED_CAPABILITY_FLAGS`. Mode stays under `developmental_learning` only (no `AgentCognitionSpec` enum).
  - LOGGING: INFO on schema select `{schema_version, generational_population, enabled_domains, enabled_sources, developmental_learning_mode, applicability, learner_species_defaults_id}`; stable reject codes.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/runner.py`, `src/experiments/matrix_schema.py`, `tests/unit/test_runner_config_v29_*.py`, extend `tests/unit/test_v3_scaffolding_gate.py`
  - Depends on: Task 1, Task 2

- [x] Task 4: Wire channel-active flag into runner/runtime without behavior change
  - Pass `DevelopmentalLearningSpec` into runner → `AgentRuntime` / `CognitiveLoop` bind context; expose channel-active boolean; channel-off allocates nothing and writes no developmental entries. Reserve `_developmental_knowledge = None` carry slot (no commits yet). Unit-test construction logging and reject paths.
  - LOGGING: INFO `{developmental_learning_active, domain_count, source_count}` at construction.
  - Files: `src/simulation/runner.py`, `src/simulation/agent_runtime.py`, `src/agents/cognition/loop.py` (bind only), unit tests
  - Depends on: Task 3

### Phase 2: Ledger, rates, budgets

- [x] Task 5: Implement provenance-enforcing ledger writes + runtime checkpoint carry
  - Deliverable: Append/update API rejecting missing `source_id` / evidence refs; enforce `max_entries_per_domain` with deterministic eviction. **Carry path (locked):** `CognitiveLoopResult.developmental_knowledge` → `AgentRuntime._commit_developmental_knowledge` → `_developmental_knowledge` → checkpoint restore (mirror `_commit_cultural_narratives`); plumb `CognitiveLoopProposal` / `SubjectiveSnapshot` fields if sibling ledgers require them. Twin-run bit-identity for ledger bytes under fixed seeds.
  - LOGGING: DEBUG on write `{owner_id, domain, source, teacher_present, confidence}` (metadata only); WARN on eviction; ERROR on provenance violations; DEBUG carry `{owner_id, entry_count, tick}`.
  - Files: `src/agents/cognition/developmental_learning.py`, `src/agents/cognition/models.py`, `src/simulation/agent_runtime.py`, checkpoint restore sites, `tests/unit/test_developmental_ledger_provenance.py`
  - Depends on: Task 1, Task 4

- [x] Task 6: Rate composition with lifecycle + dependency-care zeros
  - Pure helpers implementing the locked composition order: dependency `learning_rate_zero` → lifecycle `learning_rate_factor` / `learning_rate_by_entity` → `base_rate` × source weight; honor `stage_compose` and `min_exposures`. Unit-test matrix including v3-06 learning-blocked case.
  - LOGGING: DEBUG `{owner_id, domain, base_rate, lifecycle_factor, source_weight, learning_rate_zero, effective_rate}`.
  - Files: `src/agents/cognition/developmental_learning.py`, `tests/unit/test_developmental_rate_compose.py`
  - Depends on: Task 5

- [x] Task 7: Cognitive budget coupling
  - When `cognitive_budget_coupling.mode=respect_enforced` and agent `CognitiveBudgetMode.ENFORCED`, charge `acquisition_cost_units` and apply `degrade_policy` without skipping the closed command. `ignore` leaves budgets untouched. Unit-test skip_acquisition vs reduce_rate.
  - LOGGING: DEBUG on budget decision `{owner_id, remaining, cost, policy, acquired}`; never log prompts/payloads.
  - Files: `src/agents/cognition/developmental_learning.py`, budget ledger integration site, `tests/unit/test_developmental_budget_coupling.py`
  - Depends on: Task 5, Task 6

- [x] Task 8: Blank-slate admit gate remains hard under developmental pack
  - Mid-run admit with channel on + `species_default_developmental_v1` still asserts empty developmental ledger + existing deny-list stores; modes may be enabled. Prove no society pack / peer ledger clone path exists in init pipeline.
  - LOGGING: keep blank-slate ERROR `subjective_copy_forbidden`; DEBUG assert success includes `developmental_knowledge`.
  - Files: `tests/architecture/test_v3_developmental_learning_invariants.py`, extend blank-slate / new-agent unit tests
  - Depends on: Task 2, Task 4, Task 5

### Phase 3: Domain acquisition adapters

- [x] Task 9: Observation + experimentation adapters (locations/resources/hazards)
  - Always eligible to write developmental ledger rows with provenance `observation` / `experimentation` when rates allow. CausalWorldModel / hypothesis uplift **only** when run `predictive_world_model=True`; when flag off, skip uplift with stable DEBUG reason (ledger still may grow). No silent encyclopedia. Requires learner pack modes/capacity from Task 2 for applicable agents.
  - LOGGING: DEBUG `{owner_id, domain, source, ledger_touch, world_model_uplift}`.
  - Files: `src/agents/cognition/developmental_learning.py`, `loop.py` / world_model hooks, unit tests
  - Depends on: Task 2, Task 6, Task 7

- [x] Task 10: Social source adapters (instruction/imitation/communication)
  - Gate teaching / imitation / communicated-memory uplift for enabled social domains through developmental rates; provenance must capture optional `teacher_agent_id`. Never copy sender stores — fresh owner entries only. Skip domain if required mode off.
  - LOGGING: INFO on successful instructed acquisition `{owner_id, domain, teacher_id, source}` (ids only); DEBUG on discount/reject.
  - Files: `src/agents/cognition/developmental_learning.py`, hooks near `teaching.py` / communication finalize, unit tests
  - Depends on: Task 9

- [x] Task 11: Artifact-assisted adapter + cross-agent divergence proof
  - When `artifact` source enabled and `ArtifactInterpretationMode.DETERMINISTIC`, allow mark-derived acquisitions with provenance `artifact` + artifact id evidence. Fixture: two blank-slate learners, different teachers or artifact exposures, matched seeds otherwise → ledger inequality (feeds later divergence metric). Prove isolated arm cannot acquire teacher-only concepts.
  - LOGGING: DEBUG artifact acquisition metadata; INFO divergence proof summary counts only.
  - Files: artifact interpretation hook, `tests/unit/test_developmental_divergence.py`
  - Depends on: Task 9, Task 10

### Phase 4: Audits, metrics, experiment, docs

- [x] Task 12: Harvest metadata-only `DevelopmentalAcquisitionAudit`
  - Define frozen audit type + append path at acquisition attempt/finalize (mirror skill/teaching audits). Never include concept text/payloads. Expose ordered harvest on run result / experiment collector for analysis.
  - LOGGING: DEBUG audit append `{owner_id, domain, source, acquired, reason_code}`; never log concept keys as free text if they encode payload (digest-only ok).
  - Files: `src/agents/cognition/developmental_learning.py`, runner/experiment harvest site, `tests/unit/test_developmental_acquisition_audit.py`
  - Depends on: Task 5, Task 9

- [x] Task 13: Register analysis metrics from audits
  - Add `developmental_acquisition@1`, `developmental_source_mix@1`, `developmental_divergence@1` with `MetricFamilyId` (+3), specifications, compute module consuming **audits/ledgers only**, metric_service wiring, unit tests. Cognition must not import these modules. Do not overload `knowledge_diffusion` / `cultural_transmission`.
  - LOGGING: INFO on metric compute `{run_id, family_id, agent_count}`; metadata only.
  - Files: `src/analysis/developmental_learning_metrics.py`, `src/analysis/specifications.py`, `src/analysis/__init__.py`, metric service wiring, `tests/unit/test_developmental_learning_metrics.py`
  - Depends on: Task 8, Task 11, Task 12

- [x] Task 14: Experiment AJ catalog arm + profile
  - Add `experiment-aj-developmental-learning` / `developmental_learning_profile` on v29 with locked arm matrices (isolated / socialized / artifact / optional budget-stress / channel-off); pin `species_default_developmental_v1` for learners; enable teacher mode bundles per Design Decisions; off V1 gate; matrix allowlist only.
  - LOGGING: INFO `experiment_aj_built` with schema/flag/domain/source/species summary.
  - Files: `src/experiments/catalog.py`, `tests/unit/test_developmental_learning_catalog_arm.py`
  - Depends on: Task 2, Task 3, Task 11, Task 13

- [ ] Task 15: Flags-off / channel-off regression proofs
  - Explicit proofs: V3 flags-off trajectory hashes unchanged; lifecycle-on without `developmental_learning` preserves AE–AI hashes; V1 gate + `test_v2_scientific_invariants` green; SEMANTIC count stays 43.
  - LOGGING: INFO on hash compare pass/fail codes only.
  - Files: `tests/unit/test_v3_developmental_learning_regression.py`, extend scaffolding gates
  - Depends on: Task 14

- [ ] Task 16: Docs checkpoint via `/aif-docs`
  - Update `docs/architecture.md` V3 seams: developmental learning channel, species pack, provenance, audit harvest, no society injection, Experiment AJ, `runner-config-v29` exact keys, composition with skill/teaching/naming/norm/convention/narrative/artifact/world-model/budget; `docs/cognition-runtime.md` runtime carry; DESCRIPTION V3 blurb as needed.
  - LOGGING: n/a for docs prose; keep operational log examples metadata-only.
  - Files: `docs/architecture.md`, `docs/cognition-runtime.md`, `.ai-factory/DESCRIPTION.md` as needed
  - Depends on: Task 15

- [ ] Task 17: Architecture invariant tests for anti-injection
  - AST/import or unit gates: developmental learning modules must not import analysis; init pipeline must not reference peer subjective stores; forbidden source/domain ids rejected; no `cultural_historical_memory` ownership claim; no `CausalProvenanceKind` widen required by this channel.
  - LOGGING: ERROR with stable codes on violations.
  - Files: `tests/architecture/test_v3_developmental_learning_invariants.py`
  - Depends on: Task 8, Task 15, Task 16

<!-- Commit checkpoint: tasks 1–4 → Commit 1; 5–8 → Commit 2; 9–11 → Commit 3; 12–15 → Commit 4; 16–17 → Commit 5 -->
