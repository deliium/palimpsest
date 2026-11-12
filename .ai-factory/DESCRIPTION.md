# Palimpsest

## Overview

Palimpsest is a Python 3.12+ modular monolith for reproducible, discrete, text-based multi-agent AI society experiments. The current V1 surface establishes package boundaries, typed domain contracts, an authoritative deterministic `WorldEngine` tick loop with agent-specific perception, an explicit async `CognitiveLoop` and per-agent `AgentRuntime`, owner-scoped episodic `MemoryService` with reconstructive recall and append-only reconsolidation (in-memory and PostgreSQL/pgvector), deterministic subjective imagination/motivation/intention policies (independent drives, structured goals, opportunity-based fear of death, multi-criteria selection → one closed `AgentCommand`), schema-versioned event persistence and replay, experiment-only memory-drift analysis, configuration, an HTTP liveness API, observability, and containers. A provider-neutral async LLM boundary returns only strict structured output plus normalized metadata; LLM provider lifecycle composition in the API remains deferred. V2 scaffolding adds a version compatibility matrix, `runner-config-v3` with default-off reserved capability flags (owned `extended_self_model` and `short_term_emotional_state` may enable; unowned flags still fail closed), and regression gates so V1 experiments and replay stay executable — without new social/cognitive behavior in the scaffolding plan.

## Core Features

- Bounded packages for world authority, agents, cognition strategies/`CognitiveLoop`, memory (including reconstructive recall and semantic beliefs), social envelopes and directed relationship profiles, LLM trust boundaries, simulation/`WorldEngine`/`AgentRuntime`/`SimulationRunner`/`SubjectiveStateService`, trusted `experiments` catalog (A–E on the V1 gate; F–Z / AA–AD, `experiment-matrix-v1` batches, and the V2 benchmark suite / observer-graphical / scientific-invariant gates off that gate) plus canonical five-agent reference scenario, `research_runner` matrix CLI composition (no HTTP), persistence adapters, analysis ports (events + drift), API, and infrastructure
- Typed immutable agent-facing `Observation` contracts, private world authority (`World` / `WorldState` / rules / perception / operations), and versioned event/export codecs (replay-v4 occurrence context)
- Deterministic `PerceptionService` projecting one observation per agent from tick-start state plus prior committed events; cognition routed via `AgentRuntime` / `build_perspective`
- Explicit async cognitive pipeline with replaceable stage protocols, scientific boundary records, reconstructive memory stage, emergent `SelfModel`, production subjective imagination/motivation/deliberation policies, deterministic fakes, and fail-closed runtime lifecycle
- Eleven independent drives, hierarchical goals (`GOAL_MODEL_VERSION` 3 / `GoalBoard` / `goals.v1`), opportunity-based mortality appraisal (no permanent reward / no death_penalty), and multi-criteria intention selection compiling one non-authoritative `AgentCommand`
- Subjective reconstructive recall (`MemoryRecallRequest` → `ReconstructedMemory`) with deterministic and optional LLM-backed policies; non-destructive reconsolidation and lineage outside authoritative replay
- Semantic beliefs with append-only revisions/evidence, asymmetric relationship dimensions (no friend/enemy/leader labels), and atomic owner-scoped subjective commits
- Async `LLMProvider` with immutable `LLMRequest`/`LLMResult`, strict `StructuredOutput`, versioned prompt resources (including `reconstructive_memory/v1` and `reflection/v1`), a configurable OpenAI-compatible HTTP adapter (no vendor SDKs), and an optional `llm.recording` record/cache/replay layer (composition-only store settings; default remains `deterministic_fake`)
- Deterministic seed-derived RNG streams (including explicit stochastic/comparison identity), logical clock, namespaced IDs, and live/restored observation parity
- Configuration-driven `SimulationRunner` with staged prepare/bind/finalize cognition, versioned experiment result documents, default write `runner-config-v4` with default-off `CognitionTraceSpec`, and `V2CapabilityFlags` (all default off; owned flags `advanced_social_inference`, `predictive_world_model`, `extended_self_model`, and `short_term_emotional_state` may enable; `multi_hop_testimony_tracking` still fails closed with `capability_unimplemented`). `runner-config-v5` is consolidation-only. `runner-config-v6` is emitted only when some agent's `ReflectionMode` is not `DISABLED`; that mode defaults to `DISABLED` and is not a capability flag. `runner-config-v9` is emitted only when some agent's `CommunicationStrategyMode` is `DETERMINISTIC` and every `ReputationMode` is `DISABLED`. `runner-config-v10` is emitted only when some agent's `ReputationMode` is `DETERMINISTIC`. `runner-config-v11` is emitted only when some agent's `SkillLearningMode` is `DETERMINISTIC`. `runner-config-v12` is emitted only when some agent's `TeachingInteractionMode` is `DETERMINISTIC`. These modes default to `DISABLED` and none is a capability flag. `runner-config-v14` is emitted only when an `EnvironmentalDynamicsSpec` is set. That spec defaults to absent and is not a capability flag. `TerritorialClaimMode` defaults to `DISABLED`, and `runner-config-v15` is emitted only when some agent's mode is `DETERMINISTIC`; that mode is not a capability flag. `ArtifactInterpretationMode` defaults to `DISABLED`, and `runner-config-v19` is emitted only when some agent's mode is `DETERMINISTIC`; that mode is not a capability flag. `SemanticNamingMode` defaults to `DISABLED`, and `runner-config-v20` is emitted only when some agent's mode is `DETERMINISTIC`; Experiment AA and `emergent_semantic_naming@1` stay off the V1 gate. `CulturalNarrativeMode` defaults to `DISABLED`, and `runner-config-v21` is emitted only when some agent's mode is `DETERMINISTIC`; Experiment AB and `cultural_narrative_lineage@1` stay off the V1 gate
- `PALIMPSEST_` settings (including disabled-by-default `PALIMPSEST_LLM_*`), structured logging (no observation/communication/memory/belief/relationship/LLM payloads), async SQLAlchemy lifecycle, Alembic + pgvector bootstrap (migration head `0017` for memory embedding HNSW; `0016` event filter indexes; `0015` research branch lineage; cognition-trace tables remain non-authoritative; V2 capability flags remain runner JSON only)
- FastAPI research API: `/health`, versioned `/v1` simulation control/inspection/replay, resumable WebSocket stream from durable outbox; capability credentials (`PALIMPSEST_API_*`); debug disabled by default; LLM provider lifecycle composition remains deferred
- Optional read-only presentation client: Godot 4.7 Compatibility under `clients/godot-observer/` (not a Python package). The API serves the prebuilt file tree from `PALIMPSEST_PRESENTATION_WEB_ROOT` and does not import the client. `GET /version` reports the application version, `observer-protocol-v1`, the export engine, and the backend revision.
- Optional researcher SPA under `clients/research-ui/` (Svelte; not a Python package), served at `/research/` from `PALIMPSEST_RESEARCH_WEB_ROOT` (mounted before Godot `/`). Inspect run index, subjective projections/graph summaries, matrix FS (`PALIMPSEST_RESEARCH_MATRIX_ROOT`), epistemic chrome, and V3-42 generational research surfaces: generation/tick navigation, population/demographic/cohort views, qualified genealogy/teaching/knowledge/technology-diffusion lineage, culture/vocabulary/semantic/narrative history, migration/society/economy/collective-project views, institution/office/lineage views, and credential-free seven-dimension Godot focus links. Read-only cultural artifact and retained semantic-history GETs add no capture channel; inferred groups/norms, semantic drift and institution lifecycle stay analytical.

## Tech Stack

- **Programming language:** Python >=3.12 (reference pin 3.12.14)
- **Package manager / build:** uv + Hatchling (`src` layout, committed `uv.lock`)
- **Client build:** pinned Node 24.22.1 + pnpm 10.34.9 image stage; the runtime image ships prebuilt Godot Web and Svelte SPA trees with no Node, pnpm, editor or export templates
- **Framework:** FastAPI + Uvicorn
- **Validation:** Pydantic v2 + pydantic-settings (LLM structured-output contracts only; domain packages stay Pydantic-free)
- **Database:** PostgreSQL 17 with pgvector
- **ORM / migrations:** SQLAlchemy 2 async + Alembic + asyncpg (migration head `0017` for memory embedding HNSW; subjective/cognition-trace tables remain non-authoritative)
- **Logging:** structlog (infrastructure); stdlib logging inside `llm` (metadata-only)
- **HTTP client:** httpx (runtime; OpenAI-compatible LLM transport and tests)
- **Scientific computing (analysis metrics):** NumPy >=2, pandas >=2, SciPy >=1.11, NetworkX >=3 (canonical quantized metric output; not unconstrained BLAS/platform bit identity)
- **Testing:** pytest, pytest-asyncio, Hypothesis, import-linter, Ruff, mypy

## V3 scaffolding

Compatibility foundation for generational civilization plans: reserved default-off `V3CapabilityFlags` (`generational_population`, `kinship_inheritance`, `multi_polity_migration`, `institutional_economy`, `cultural_historical_memory`) on accepted `runner-config-v23`+ (= full v22 keyset ∪ sibling `v3_capability_flags`); default write stays `runner-config-v4` when all V3 flags are off. **Owned:** `generational_population` (plans v3-02/v3-03/v3-04/v3-06/v3-07/v3-08) enables on `runner-config-v24|v25|v26|v27|v28|v29|v30|v31|v32` with exact `population_lifecycle` (lifespan, stages, demographic policy, max population — no biology; v26 adds stage capability effects, gradual aging, lifespan distributions). Mid-run entry uses `WorldEngine.admit_population_entry` + blank-slate `NewAgentInitialization` bind; lifecycle-only write pair `(EVENT_SCHEMA_REPLAY_V9, codec v6)`; with explicit v25+ init, `(EVENT_SCHEMA_REPLAY_V10, codec v7)` + sibling `AgentInitializationRecorded`. Developmental effects are objective/ephemeral only (ELDER ≠ leader; no SelfModel auto-writes). v3-06 deepens the same flag with sibling `dependency_care` on **`runner-config-v28`+** (no new V3 flag): configurable DEPENDENT need deficits, self-satisfy denials, unmet-need consequences, minimal `Feed`/`Transport`, optional caregiving cognition bias (`caregiving_cognition_mode` under that object only), write-pair `(EVENT_SCHEMA_REPLAY_V12, codec v9)`, Experiment AI — never hard-codes parent→caregiver; neglect/shared/non-kin care are legal. v3-07 deepens the same flag with sibling `developmental_learning` on **`runner-config-v29`** (no new V3 flag): owner-scoped gradual acquisition with provenance (`species_default_developmental_v1` modes-on/content-empty), rate/budget compose, metadata audits + metrics, Experiment AJ — never society injection or kinship knowledge handoff; no new event write-pair. v3-08 deepens the same flag with sibling `mentorship` on **`runner-config-v30`** (no new V3 flag): owner-scoped mentor/apprentice bonds + taught-content lineage composed from V2 teaching acts, fidelity/mutation/bonds metrics, Experiment AK — never copies peer internal state; kinship cultural handoff stays deferred; no new event write-pair. **Also owned:** `cultural_historical_memory` (v3-09; deepened by v3-10/v3-11/v3-12/v3-13) on **`runner-config-v31|…|v35`** + exact `cultural_feature_provenance`: owner-scoped subjective cultural beliefs (`SubjectiveCulturalBelief`) with closed feature kinds, provenance channels, hop_index, mutation/recombination; analysis-only `AnalyticalCulturalTrait` + three metric families; optional compose from V2 naming/narrative/norms/conventions/teaching/artifacts; Experiment AL — no global Culture controller; kinship cultural inheritance handoff still deferred. v3-10 adds sibling `historical_memory_layers` on **`runner-config-v32`** (optional on v33–v35; no new V3 flag): analysis-only Assmann living/communicative/cultural layers, transitions, and three researcher queries + metric families; Experiment AM — never agent knowledge / Observation / SelfModel. v3-11 adds sibling `durable_records` on **`runner-config-v33|v34|v35`** (no new V3 flag): physical genres/lineage/imperfect copy/annotate/damage/tombstone on WorldEngine artifacts; write-pair `(EVENT_SCHEMA_REPLAY_V13, codec v10)`; marks ≠ truth; Experiment AN + three sibling metric families (`durable_record_lineage@1`, `durable_record_fidelity@1`, `durable_record_survival@1`). v3-12 adds sibling `knowledge_repositories` on **`runner-config-v34|v35`** (requires durable + provenance; no new V3 flag; no LibraryInstitution): WorldEngine-owned containers, membership, access, maintenance/decay, imperfect index, retrieval; write-pair `(EVENT_SCHEMA_REPLAY_V14, codec v11)`; cultural archive/library labels stay subjective; Experiment AO + three sibling metric families (`knowledge_repository_survival@1`, `knowledge_repository_access@1`, `knowledge_repository_organization@1`). v3-13 adds sibling `knowledge_genealogy` on **`runner-config-v35`** (requires provenance; no new V3 flag; no write-pair bump): owner-scoped practical-knowledge ledger with multi-parent transmission DAG, mutation/combination, analysis-only genealogy queries + three sibling metric families (`knowledge_genealogy_holders@1`, `knowledge_genealogy_lineage@1`, `knowledge_genealogy_mutation@1`); Experiment AP — triple representation (objective capability ≠ subjective knowledge ≠ research lineage); cross-owner edges analysis-only; no `GlobalTechniqueRegistry` / society encyclopedia. **Also owned:** `kinship_inheritance` (v3-05) for objective genealogy on `runner-config-v27|…|v35` + exact `kinship` (parent→child edges; derived sibling/ancestor/descendant; write-pair replay-v11/codec v8; default perception `none`; Experiment AH). Related ≠ trust/affection/loyalty. Cultural inheritance handoff deferred under the same flag. Other V3 flags still fail closed at `SimulationRunner.from_config` with `capability_unimplemented`. Alembic head stays `0017` (flags/lifecycle/init/kinship/dependency_care/developmental_learning/mentorship/cultural/layers/durable/repositories/genealogy remain runner JSON + event/snapshot/subjective payloads). v3-14 adds `runner-config-v36` plus exact `bounded_experimentation` (cultural flag and provenance required; no new V3 flag; write-pair replay-v15/codec v12 only while that channel is active). v3-15 adds `runner-config-v37` plus exact `technique_lifecycle` (cultural flag, provenance, and knowledge genealogy required; no new V3 flag; no write-pair bump). v3-16 adds optional `possession_succession` on `runner-config-v38` only (no new V3 flag; `custody_mechanism=corpse`; write-pair replay-v16/codec v13 only while that channel is active). Death leaves items on the corpse. A later `Take` changes the holder. A claim does not. `kinship_inheritance` still does not grant inheritance rights, and kinship knowledge or cultural handoff stays deferred. v3-17 adds optional `structured_commitments` on `runner-config-v39` (no new flag; `DeclareCommitment` is speech and the engine does not collect a debt; write-pair replay-v17/codec v14 only while that channel is active). v3-18 adds optional `subjective_valuation` on `runner-config-v40` (no new flag; a reservation is a private belief; `NegotiateExchange` `accept` moves named items; write-pair replay-v18/codec v15 only while that channel is active; codec v15 still carries v14 payloads; `exchange_offers` has no reservation field). v3-20 adds optional `collective_projects` on `runner-config-v42` only (no new flag; five closed kinds; `StartCollectiveProject` and `ContributeCollectiveProject`; write-pair `(EVENT_SCHEMA_REPLAY_V19, "v17")` only while that channel is active). A contribution tail records who worked. It is not a leader. `institutional_economy` stays unowned. Command count is 43. Semantic count is 73. Protocol id stays `observer-protocol-v1`. Experiments AE–BF stay off the V1 gate. Seams: `docs/architecture.md`. Milestone: **M7 — V3 Generational Civilization** (`.ai-factory/ROADMAP.md`).

Public goods deepen collective projects on `runner-config-v43` without a new capability flag. While `public_goods` is active, the write pair is exactly `(EVENT_SCHEMA_REPLAY_V20, "v18")`; channel-off collective projects keep `(EVENT_SCHEMA_REPLAY_V19, "v17")`. The closed command count is **43**, observer semantic count is **73**, and metric catalog count is **117**. Experiment AX (`public_goods@1`) stays off the V1 gate. A benefit event is not an access grant and not a moral role.

**Committed V3 state through v3-29 (2026-10-19):** v3-19 adds `resource_exchange_profile` on `runner-config-v41` (replay-v18/codec v16, Experiment AV); v3-20 adds exact `collective_projects` on `runner-config-v42` (replay-v19/codec v17, Experiment AW); v3-21 adds exact `public_goods` on `runner-config-v43` (replay-v20/codec v18, Experiment AX); v3-22 owns `multi_polity_migration` with `regions_migration` on `runner-config-v44` (replay-v21/codec v19, Experiment AY); v3-23 adds analysis-only candidate communities (`society_emergence@1`, `society_divergence@1`, `society_isolation@1`; Experiment AZ); v3-24 adds the neutral `cultural_contact` sibling on `runner-config-v45` (replay-v22/codec v20, `ContactRecorded`, six contact metric families, Experiment BA); v3-25 adds owner-scoped symbolic composition modes on `runner-config-v46` (active v44/v45 root with per-agent `symbolic_language_mode`; no new root sibling) and Experiment BB; v3-26 adds bounded owner-scoped sense history to naming and symbolic ledgers plus analysis-only `semantic_stability@1`, `semantic_drift@1`, and `semantic_divergence@1` (Experiment BC; no new command, event, flag, or write-pair); v3-27 adds owner-scoped cross-cultural translation on `runner-config-v47` (active v44/v45/v46 family roots with per-agent `translation_mode`; `translation_learning@1`, `cross_group_translation@1`, `translation_influence@1`; Experiment BD; no new command, event, observer semantic type, write-pair, or migration); v3-28 adds owner-scoped multi-generational historical narratives on `runner-config-v48` (`generational_narratives@1`; three families; Experiment BE; no new command, event, observer semantic type, write-pair, or migration); v3-29 adds opt-in owner-scoped institution concepts on `runner-config-v49` plus detached analytical `institution_emergence@1` and `institutional_persistence@1` (Experiment BF; no new command, event, observer semantic type, write-pair, or migration; `institutional_economy` stays unowned). Closed command count is **43**, observer semantic types are **73**, metric families are **117**, and Alembic head stays `0017`. `institutional_economy` remains unowned and fails closed.

## V2 scaffolding

Additive substrate plus optional cognition execution trace: `simulation.compatibility` version matrix; default write `runner-config-v4` with default-off `V2CapabilityFlags` and `CognitionTraceSpec`; `runner-config-v5` only when consolidation is enabled; `runner-config-v6` only when `ReflectionMode` is not `DISABLED` (Experiment G stays off the V1 gate); Alembic head `0017` for memory embedding HNSW (`0016` event filter indexes; `0015` research branch lineage; cognition-trace tables remain non-authoritative; flags remain runner JSON only); `/v1` + `palimpsest.v1` stable (no `/v2` routes yet); domain-contract evolution rules without wire changes; V1 regression gate for catalog A–E + reference scenario (flags-off and tracing-off). Opt-in environmental dynamics are not a capability flag: `runner-config-v14` is emitted only when an `EnvironmentalDynamicsSpec` is set, and Experiment U (`environmental_dynamics@1`) stays off that gate. `TerritorialClaimMode` defaults to `DISABLED`: `runner-config-v15` is emitted only when that mode is `DETERMINISTIC`, and Experiment V (`spatial_control@1`, policy `territorial-claims.v1`) stays off that gate. `GroupFormationMode` defaults to `DISABLED`: `runner-config-v16` is emitted only when that mode is `DETERMINISTIC`, and Experiment W (`emergent_group_formation@1`, policy `group-formation.v1`) stays off that gate. `SocialNormMode` defaults to `DISABLED`: `runner-config-v17` is emitted only when that mode is `DETERMINISTIC`, and Experiment X (`emergent_social_norms@1`, policy `social-norms.v1`) stays off that gate. `SocialConventionMode` defaults to `DISABLED`: `runner-config-v18` is emitted only when that mode is `DETERMINISTIC`, and Experiment Y (`persistent_social_conventions@1`, policy `social-conventions.v1`) stays off that gate. WorldEngine-owned information artifacts (`mark`/`sign`/`note`/`map`/`record`/`memorial`) are objective marks only; meaning is opt-in via `ArtifactInterpretationMode` (default `DISABLED`, not a capability flag). `runner-config-v19` is emitted only when that mode is `DETERMINISTIC`. Replay-v8 / codec `v5` write only when artifacts are active at run start; default event write stays replay-v5. Experiment Z (`external_artifact_memory@1`) stays off the V1 gate. Experiment AA (`emergent_semantic_naming@1`) stays off the V1 gate. Catalog A–Z plus AA–AB; A–E remain on the gate. Later V2 plans must follow the downstream checklist in `docs/architecture.md`. Register M5/V2 milestones via `/aif-roadmap`.

## Architecture Notes

Modular monolith with explicit bounded packages under `src/`. Domain modules do not import infrastructure; the API composition root wires adapters. `simulation.WorldEngine` is the sole public mutation authority; private world modules prepare candidates and project observations only. `observer` is a read-only presentation package: it adapts committed facts into frames and must not commit ticks. Cognition never receives `WorldState` or another agent's observation. Agents, memory, cognition, and reconstruction APIs may carry opaque `EventId` correlation only — never `WorldEvent` or event stores. Structured `Talk`/`Ask`/`Tell` proves delivery only; declared lineage is testimony; each receiver forms a fresh communicated `MemoryTrace`. Read-only `analysis` may join objective events with subjective reconstruction and social-transmission evidence after the fact. The `llm` package is import-closed against world/simulation/API/infrastructure, forbids vendor SDKs, and never converts results into commands—future cognition must translate validated decision schemas into fresh `AgentCommand` values and use normal admission. Cross-module imports use package facades / `__all__`. Import-linter and AST boundary checks enforce dependency rules.

## Architecture

Detailed architecture guidelines live in `.ai-factory/ARCHITECTURE.md`.

**Pattern:** Structured Modules (Technical Layer / Bounded Packages), adapted to the existing package layout with enforced domain and authority boundaries.

## Non-Functional Requirements

- **Logging:** Configurable via `PALIMPSEST_LOG_LEVEL`; structured, secret-safe, UTC operational timestamps; LLM and memory/reconstruction logs stay metadata-only
- **Error handling:** Fail closed on invalid settings and ambiguous migration targets; LLM errors expose only safe codes/status/attempts
- **Security:** Credentials are `SecretStr`; DSNs/prompts/bodies are never logged; non-root container user
- **Reproducibility:** Explicit simulation seeds; no global RNG or wall-clock domain defaults; LLM retries use injected sleep/monotonic clocks; exact external LLM reconstructive recall needs recorded outputs or stubs
- **Testing:** Unit/architecture by default; integration and Compose are opt-in markers; LLM tests are network-free with deterministic fakes

Generational historical narratives (V3-28) extend the owner-scoped narrative ledger under the gated `cultural-narratives.v2` policy. Witness, retelling, opaque record, transition, source-loss, and descriptive-theme provenance stay owner-scoped; no truth field exists. `runner-config-v48` is emitted only when the optional `generational_narratives` run-level spec is present and requires exact cultural provenance, population lifecycle, `generational_population`, and a deterministic narrative mode. Detached analysis adds three families (112 → 115): `generational_narrative_continuity@1`, `narrative_source_loss@1`, and `narrative_historical_alignment@1`. Experiment BE (`generational_narratives@1`) is off-gate. Commands stay 43, observer semantic types 73, replay `EVENT_SCHEMA_REPLAY_V22`, codec `v20`, Alembic `0017`.

Institution emergence (V3-29) adds an opt-in per-agent `institution_concept_mode` (`runner-config-v49`) and an owner-scoped `InstitutionConceptLedger` with six closed pattern channels (`role_recognition`, `procedure_recurrence`, `social_expectation`, `legitimacy_belief`, `succession_observed`, `generational_continuity`) under locked policy `institution-concepts.v1`. Concepts are private beliefs; no institution type, state, government, religion, court, police, corporation, or political party exists anywhere, and no objective office registry exists. Detached analysis adds `institution_emergence@1` and `institutional_persistence@1` (families 115 → 117), classifying temporary coordination versus persistent institution-like structure from role, procedure, expectation, legitimacy, succession, and cross-generational continuity evidence. Experiment BF (`institutionalization@1`) is off-gate. No new command, event, observer semantic type, write-pair, codec marker, or migration; replay stays `EVENT_SCHEMA_REPLAY_V22`, codec `v20`, commands 43, semantic types 73, Alembic `0017`, and `institutional_economy` remains unowned.

Subjective offices (V3-30) add an opt-in per-agent `office_succession_mode` (`runner-config-v50`) and an owner-scoped `OfficeConceptLedger` under locked policy `offices-succession.v1`. An office is a persistent recognized role with stable owner-local identity independent of occupant, supporters, label, and growing evidence; duties and expected authority are revisable beliefs, never world permissions. Occupant claims may be vacant, uncertain, contested, lost, relinquished, or disputed; no `current_occupant` is globally authoritative. Recognition requires recurring function evidence plus independent role-directed expectation or endorsement, and same-root retellings cannot manufacture support. The new explicit `species_default_offices_v1` initialization profile enables empty office cognition for admitted newborns; existing species profiles remain office-disabled. Detached analysis adds `office_continuity@1` and `office_succession@1` (families 117 → 119) with owner-local evidence, detached function/context role alignment, ambiguity/exclusion denominators, and explicit partial coverage. Experiment BG (`offices_succession@1`) is off-gate. No new command, event, observer semantic type, replay/codec marker, or migration; replay stays `EVENT_SCHEMA_REPLAY_V22`, codec `v20`, commands 43, semantic types 73, Alembic `0017`, default runner write `v4`, and `institutional_economy` remains unowned.

Collective decisions (V3-31) add an opt-in per-agent `collective_decision_mode` (`runner-config-v51`) and an owner-scoped `CollectiveDecisionLedger` under locked policy `collective-decisions.v1`. Six acts (`propose`, `support`, `oppose`, `delegate`, `withdraw_support`, `coordinate`) travel as bounded relations inside existing `Talk`/`Ask`/`Tell` speech. Positions, one-hop delegations, retractions, claimed outcomes, descriptive compliance, and local influence attribution remain private beliefs; there is no objective proposal registry, electorate, quorum, majority, binding resolution, or authoritative leader. Detached analysis adds `collective_decision_process@1`, `collective_decision_outcomes@1`, and `collective_decision_disagreement@1` (families 119 → 122), and Experiment BH (`collective_decisions@1`) stays off-gate. No new command, event, observer semantic type, replay/codec marker, migration, or newborn profile; replay stays `EVENT_SCHEMA_REPLAY_V22`, codec `v20`, commands 43, semantic types 73, Alembic `0017`, and default runner write `v4`.

Conflict mediation (V3-32) adds an opt-in per-agent `mediation_mode` (`runner-config-v52`) and an owner-scoped `MediationLedger` under locked policy `mediation.v1`. Six acts (`hear_dispute`, `request_accounts`, `propose_compromise`, `vouch`, `mediate`, `recommend_restitution`) plus seven response kinds and three auxiliary role expressions travel as bounded relations inside existing `Talk`/`Ask`/`Tell` speech. Cases, accounts, recommendations, responses, authority appraisal, attempts, and outcomes remain private beliefs; there is no court, verdict, binding settlement, global dispute registry, or forced transfer. Voluntary follow-through compiles only an owner's independently selected, exact supported undertaking (initially `Give`); unsupported terms remain discussion. Detached analysis adds `conflict_mediation@1` and `mediation_role_emergence@1` (families 122 → 124), and Experiment BI (`mediation_opportunities@1`) stays off-gate. No new command, event, observer semantic type, replay/codec marker, API route, or migration; replay stays `EVENT_SCHEMA_REPLAY_V22`, codec `v20`, commands 43, semantic types 73, Alembic `0017`, and default runner write `v4`.


Institutional memory (V3-33) adds opt-in per-agent `institutional_memory_mode`
on `runner-config-v53`, with an owner-local `InstitutionalMemoryLedger` under
locked policy `institutional-memory.v1`. Role channels use stable local office
IDs; procedure channels use locally evidenced anchors. Bounded `im_v1` frames
travel in artifact marks or one existing speech relation. Acquisition requires
current visible interpretation or actual addressed delivery; teaching requires
receiver mode. Ignored, partial, damaged, and conflicting entries remain legal.
Runtime checkpoints preserve one owner's ledger; admission transfers no content.
The explicit `species_default_institutional_memory_v1` profile is v53-only and
starts empty. Detached analysis adds `institutional_memory_continuity@1` and
`institutional_memory_provenance@1` (families 124 → 126); Experiment BJ
(`institutional_memory@1`) is off-gate. No new command, event, observer semantic,
write-pair, migration, API route, or capability flag is added, and
`institutional_economy` remains unowned.


Institutional decay (V3-34) adds opt-in per-agent `institutional_decay_mode` on
`runner-config-v54`, with an owner-local decay sidecar under locked policy
`institutional-decay.v1`. Fresh evidence renews only the channels it supports;
unrefreshed channels lose 0.04 per executed update. The paired adjusted concept
ledger is committed through ordinary deferred finalization, traverses the
owner-safe perspective/snapshot path, and is preserved by supported runtime
checkpoints. Admission copies nothing and the v53 institutional-memory learner
profile remains decay-disabled. Detached analysis adds
`institutional_decay@1`, `institution_lifecycle@1`, and `institution_lineage@1`
(families 126 → 129), with lifecycle hysteresis and absolute-witness lineage.
Experiment BK (`institutional_decay@1`) is off-gate. No new command, event,
observer semantic, write-pair, migration, API route, or capability flag is
added, and `institutional_economy` remains unowned.

Generational runner (V3-35) adds `runner-config-v55` and `runner-result-v3` for
multi-generation experiments over the owned `generational_population` seam.
`generational_interval_entry` labels admitted cohorts by absolute tick; v55
requires explicit lifecycle, initialization, finite tick horizon, disabled
runtime-terminal stopping, and the owned population flag. Stop selectors,
historical inspection (not subjective restart), seed lineage, validated LLM
replay identity, and immutable generational manifests are owned by that plan.
No new command, event, observer semantic, SQL migration, or capability flag is
added; default writes remain v4/v2.

Generational experiments (V3-36) add closed experiment presets over the existing
`runner-config-v55` seam: lifespan, learning model, teaching frequency, record
availability, memory architecture, innovation rate, migration, resource
scarcity, population size, institution support, and cognitive architecture.
Experiment BM (`generational_comparison@1`) builds five paired control/treatment
comparisons that share seed, stochastic identity, world layout, founder roster,
stop horizon, generation schedule, and initialization. Matrix factors reuse the
same applicators, preserve v55, and reject contradictory combinations. Detached
`generational_cohort_comparison@1` folds finalized `PopulationProgress` and
raises the metric catalog from 129 to 130. V3-36 adds no capability flag,
runner schema (no v56), command, event, observer semantic, write-pair, API route,
or migration, and does not own `institutional_economy`.


Cultural evolution metrics (V3-37) add opt-in, composition-only capture of owner-scoped cultural inventories and six detached analytical families (`cultural_trait_dynamics@1`, `cultural_evolution_transmission@1`, `cultural_population_structure@1`, `cultural_narrative_survival@1`, `cultural_vocabulary_differentiation@1`, `cultural_technology_continuity@1`), raising the metric catalog from 130 to 136. New siblings are `cultural-evolution-evidence-v1`, `cultural-cell-metrics-v1`, and `cultural-metric-comparison-v1`; capture is never a runner-config field or capability flag. Repeated-seed Student-t intervals and explicit one-factor paired contrasts operate on verified completed cell artifacts; legacy `matrix-metric-summary-v1` p05/p95 ranges remain descriptive. No new command, event, observer semantic, replay/codec marker, API route, migration, runner/result schema, or capability ownership is added; default writes remain runner v4/result v2, replay stays `EVENT_SCHEMA_REPLAY_V22`/`v20` for feature-selected runs, commands stay 43, observer semantic types stay 73, and Alembic head stays `0017`.


Historical contingency experiments (V3-38) add Experiment BN / `historical_contingency@1` as a trusted grouped research protocol. A common generational prefix is sealed at finalized boundary F, complete owner state is captured in-process, independent replay children receive small ordinary commands, and detached outcomes cover norms, relationships, institutions, technology, cultural narratives, inequality, and cooperation. Sibling `path-dependence-*-v1` artifacts carry lineage, prefix, branch, outcome, and comparison identity; repeated numeric seeds define independent blocks and single-run causality is never claimed. No capability flag, runner schema (no v56), command/event, observer semantic, API route, migration, or metric family is added; default writes remain runner v4/result v2 and latest feature runner stays v55. Full subjective resume remains unsupported: completed children may be adopted, while an unused planned child requires deterministic prefix reconstruction after process loss.


Historical lineage explorer (V3-39) adds a read-only, evidence-scoped query
backend over existing generational, knowledge, cultural and institutional
evidence. Eight families (genealogy, mentorship, technology, knowledge, record,
narrative, institution, office succession) share qualified identities, bounded
snapshot-pinned traversal and purpose-specific signed cursors. Optional
default-off capture publishes immutable `lineage-snapshot-v1` sibling artifacts
through a filesystem read model with cumulative per-run quotas; it never feeds
cognition or world state. Objective genealogy/record queries use inspection;
subjective and analytical queries use subjective debug. No command, event,
observer semantic, metric family, runner/result schema, SQL migration, capability
ownership or API version is added; default writes remain runner v4/result v2,
Alembic head stays `0017`, commands 43, observer semantic types 73, metric
families 136, replay-v22/codec v20 when selected, `/v1` and
`observer-protocol-v1`.

Long-horizon scalability (V3-43) adds benchmark-only measurement, supervision
and envelope tooling under `tests/benchmarks`, optional composition-only runtime
retirement for fully finalized dead owners, verified offline history archives,
append-only evidence spools, and versioned physical lineage/civilization index
layouts. Original events, commits, snapshots, provenance and published history
remain immutable and queryable; derived analytical views and spools never feed
cognition. The verified envelope covers 10k generational and evidence-rich lanes;
dense 100k attempts remain incomplete and real-browser playback is unverified.
No command, event, observer semantic, metric family, runner/result schema,
capability ownership, SQL migration or API version is added; current pins remain
runner v4/result v2, latest feature runner v55, 43 commands, 73 observer semantic
types, 136 metric families, Alembic `0017`, `/v1` and `observer-protocol-v1`.

The V3-44 generational civilization benchmark adds a separate thirty-case
registry (`v3-generational-civilization-benchmark-v1`), domain-specific bounded
v55 fixtures, a controlled mechanism lane plus an unassisted or declared grouped
research lane, immutable `civilization-benchmark-run-v1`/`-suite-v1` sibling
artifacts, a thin seed-block comparison composer, and a production CLI harness
under `research_runner`. The `v3-bench` IDs and the v55-only content-empty
`species_default_civilization_learner_v1` pack are benchmark composition, not new
scientific schemas: default runner/result stay v4/v2, latest feature runner stays
v55, commands stay 43, observer semantic types stay 73, metric families stay 136,
Alembic head stays `0017`, and `institutional_economy` and
`multi_hop_testimony_tracking` remain unowned. Research nulls are retained as
explicit `unexecuted` checks; no emergence of government, money, religion, myth
or institutions is required. The 2026-10-30 qualification measured all thirty
mechanisms, 150 predeclared research runs, deterministic twins, and truthful
10k/100k envelope limits (generational 100k completed ticks with an extinct
final population; evidence-rich 100k incomplete).

V4-01 (V4 scaffolding, 2026-10-30) adds the open-ended-civilization architecture
seam without mechanics. `simulation.v4_architecture` declares thirteen contexts
(twelve closed unowned `V4CapabilityFlags` plus analysis-only
`societal_resilience`) with four authorities, owning packages, prerequisites, and
non-goals; no organization, market, polity, institution, or civilization actor
exists. `runner-config-v56` is accepted as the v55 keyset plus one exact
`v4_capability_flags` sibling, is never emitted automatically, and every enabled
V4 flag fails closed at `SimulationRunner.from_config`. `simulation.versioning`
reserves four future write pairs (events 23-26, codecs `v21`-`v24`) for the four
objective contexts that need new events; `simulation.migration_plan` orders six
evidence-gated stages while Alembic head stays `0017`. `observer.capabilities`
lets `GET /version` advertise protocol/layout/capability names additively without
exposing flag values, and `simulation.scale` plus `observer.scale` define
deterministic partitioning, declarative budgets, and presentation-only
multi-scale levels. Both clients consume the additive contract and stay read-only.
Default runner/result remain v4/v2, latest feature runner v55, commands 43,
observer semantic types 73, metric families 136, replay-v22/codec v20,
`/v1`, and `observer-protocol-v1`; `institutional_economy` and
`multi_hop_testimony_tracking` remain unowned. V4-01 claims no capacity and adds
no V4 social mechanic.

V4-02 (macro-society analytical identity, 2026-10-30) implements the
analysis-only `macro_society_identity` context. `analysis.macro_society_*`
declares nine evidence lanes, deterministic cross-lane candidate detection with
legal overlap, fragmented and contested statuses, creation-evidence `msoc-`
identities, forward-only split/merge lineage, three strictly separated layers,
and four metric families (`macro_society_structure@1`,
`macro_society_identity_alignment@1`, `macro_society_lineage@1`,
`macro_society_membership_dispute@1`), raising the catalog from 136 to 140.
`simulation.macro_society_*` defines the bounded canonical
`macro-society-snapshot-v1` document and ports; `experiments.macro_society_publication`
maps completed-run harvests; `persistence.macro_society_filesystem` stores them
atomically with quotas; four GET-only `/v1` routes require `SUBJECTIVE_DEBUG` and
return `macro_society_disabled` when unconfigured; the Research UI adds a
read-only Macro-societies panel. No capability flag, runner schema, command,
event, observer semantic type, API version, or migration is added: runner
v4/v55/v56, result v2/v3, commands 43, observer semantic types 73, metric
families 140, replay-v22/codec v20, `/v1`, `observer-protocol-v1`, and Alembic
`0017` remain the pins. `institutional_economy` and
`multi_hop_testimony_tracking` remain unowned.


V4-03 (general organization model, 2026-10-30) owns the `organizations` V4
context as the first flagged V4 capability on the accepted `runner-config-v56`
seam. An organization is an owner-scoped belief about a recurring collective
structure: perceived members, roles, shared goals, referenced resources,
procedures, records, internal commitments, identity concepts, and bounded
history. `agents.cognition.organization_concepts` implements a closed
`organization-concepts.v1` ledger; explicit and disputed claims travel as bounded
`org_v1` relations inside existing `Talk`/`Tell` speech. `analysis.organization_*`
harvests exported ledgers, detects overlapping cross-owner candidates, mints
stable `org-` identities, projects three layers, derives forward-only lineage, and
adds four metric families (140 -> 144). `simulation.organization_*` defines the
bounded canonical `organization-snapshot-v1` and read/publication ports;
`experiments.organization_*` is the only analysis-to-artifact bridge;
`persistence.organization_filesystem` stores snapshots atomically with quotas;
four GET-only `/v1/simulations/{run_id}/organizations` routes require
`SUBJECTIVE_DEBUG` and return `organization_disabled` when unconfigured; the
Research UI adds a read-only Organizations panel. No organization actor, roster,
treasury, resource pool, registry, command, event, observer semantic type, runner
schema, API version, or SQL migration is added. Pins remain runner v4/v55/v56,
result v2/v3, commands 43, observer semantic types 73, metric families 146,
replay-v22/codec v20, `/v1`, `observer-protocol-v1`, and Alembic `0017`;
`institutional_economy` and `multi_hop_testimony_tracking` remain unowned.

V4-04 (organization operational state, 2026-11-01) extends the owned
`organizations` context on `runner-config-v56` with an owner-scoped operation
sidecar keyed by existing `orgc-` concept ids under locked policy
`organization-operations.v1`. Eight domains are recorded as owner beliefs:
resource control, storage, record keeping, membership admission, membership
departure, role assignment, procedure action, and internal commitment.
Objective possession stays `holder_id`/`location_id`/
`custodian_repository_id`/`stored_quantity`; no objective ownership field is
added. No organization object can teleport a resource or execute an action: all
physical effects remain ordinary agent commands. Admission, departure, and role
assignment are claims with provenance, never permissions; disagreement stays
`disputed` with `contest_count` and never blocks the organization. Owner-local
`orgd-` decisions and `orga-` actions publish as deterministic `orgop-` records.
Detached analysis adds `organization_operations@1` and
`organization_operation_authority@1` (144 -> 146) and joins operations to
existing `org-` candidates without creating, splitting, merging, or dissolving
one. `simulation.organization_*` adds canonical `organization-snapshot-v2`
while keeping v1 decodable and byte-verifiable; `experiments.organization_*`
composes v2 after completion; `persistence.organization_filesystem` serves
v1/v2; five GET-only `/v1` routes require `SUBJECTIVE_DEBUG`; the Research UI
adds a read-only operations view. No new flag, runner schema, command, event,
observer semantic type, write pair, `/v2` route, or migration is added. Pins:
runner v4/v55/v56, result v2/v3, commands 43, observer semantic types 73,
metric families 146, replay-v22/codec v20, `/v1`, `observer-protocol-v1`,
Alembic `0017`; `institutional_economy` and `multi_hop_testimony_tracking`
remain unowned.

V4-05 (organization collective agency, 2026-11-02) deepens the owned
`organizations` context on `runner-config-v56` with a third owner-scoped sidecar
keyed by existing `orgc-` concept ids under locked policy
`organization-agency.v1`. Proposals, positions, abstention, amendments,
recognized procedures, collective decision records, per-actor implementation,
compliance, refusal, and owner-attributed sabotage are beliefs about a recognized
process, never an organization will, super-agent, quorum, binding resolution, or
permission. Bounded `org_ca_v1` claims travel inside existing `Talk`/`Tell`; no
global OrganizationLLM and no organization executor exists, and every physical
effect remains an ordinary agent command. Detached analysis adds
`organization_collective_agency@1` and `organization_collective_implementation@1`
(metric families 148) and joins agency rows to existing `org-` candidates without
creating or changing identity. `simulation.organization_*` adds canonical
`organization-snapshot-v3` while v1/v2 stay decodable; six GET-only `/v1` routes
require `SUBJECTIVE_DEBUG`; the Research UI adds a read-only collective-agency
view. No new flag, runner schema, command, event, observer semantic type, write
pair, `/v2` route, or migration is added. Pins: runner v4/v55/v56, result v2/v3,
commands 43, observer semantic types 73, metric families 151, replay-v22/codec
v20, `/v1`, `observer-protocol-v1`, Alembic `0017`.

V4-06 (formal social rules, 2026-11-03) owns the `formal_rules` V4 context on the
accepted `runner-config-v56` seam; it claims the already-declared flag and adds
no additional flag slot, runner schema, root field, or per-agent runner key. A formal rule is one owner's belief about a socially
recognized constraint with scope, proponents, recognized authority, written
representation anchors, expected sanctions, exceptions, historical versions,
and status. The progression `habit → expectation → norm → documented →
recognized_enforcement` is monotone and versioned. `WorldEngine` never reads the
ledger: a socially prohibited but physically possible command is still admitted,
and a physically impossible command is still rejected by existing rules.
Bounded `fr_v1` claims travel inside existing `Talk`/`Tell`; `follow`, `violate`,
`challenge`, `reinterpret`, and `ignore` are declarations, never objective
compliance findings. Competing systems coexist without precedence. Detached
analysis adds `formal_rule_development@1`, `formal_rule_authority@1`, and
`formal_rule_response@1` (metric families 148 → 151), canonical
`formal-rule-snapshot-v1`, an atomic filesystem store, six GET-only
`/v1/simulations/{run_id}/formal-rules` routes under `SUBJECTIVE_DEBUG`, and a
read-only Research UI Formal rules panel. Pins: runner v4/v55/v56, result v2/v3,
commands 43, observer semantic types 73, metric families 151, replay-v22/codec
v20, `/v1`, `observer-protocol-v1`, Alembic `0017`; `institutional_economy` and
`multi_hop_testimony_tracking` remain unowned.

V4-07 (structured dispute resolution, 2026-11-03) owns the third V4 capability
flag, `legal_disputes`, on the accepted `runner-config-v56` seam; it adds no
`runner-config-v57`, root field, per-agent runner key, command, event, observer
semantic type, write pair, `/v2` route, or migration. A dispute is one owner's
belief about separately attributed claims, counterclaims, testimony, evidence
references, rule references, mediation and authority references, and proposed or
declared resolutions. It is never a shared case file, court, judgment, verdict,
or binding settlement, and no objective justice oracle or global dispute
registry exists. `WorldEngine` never reads a dispute ledger: a socially disputed
but physically possible command is still admitted, and a physically impossible
command is still rejected by existing rules. Direct and communicated testimony
are distinct, shared roots are never independent corroboration, and rule
references resolve only against the owner's formal-rule ledger (`orphaned` or
`version_mismatch` otherwise; `legal_disputes` may run without `formal_rules`).
Mediation links are beliefs, not binding decisions, and resolutions are
proposals: `apparently_accepted` requires every named party's active declaration
and still binds nobody, while acceptance requires a proposal observed in a prior
committed tick. Detached analysis adds `dispute_claim_structure@1`,
`dispute_testimony_independence@1`, and `dispute_resolution_alignment@1` (metric
families 151 → 154), canonical `dispute-resolution-snapshot-v1`, an atomic
`dispute-resolution-store-v1` filesystem store, six GET-only
`/v1/simulations/{run_id}/disputes` routes under `SUBJECTIVE_DEBUG`, and a
read-only Research UI disputes view. Researcher-only objective alignment
(`supported`, `unresolved`, `inconsistent`, `not_applicable`) never reaches
cognition, prompts, memory, world state, observer semantics, or stop selectors.
Pins: runner v4/v55/v56, result v2/v3, commands 43, observer semantic types 73,
metric families 157, 14 V4 contexts, 12 V4 flags, replay-v22/codec v20, `/v1`,
`observer-protocol-v1`, Alembic `0017` with no `0018`; four V4 flags are owned
(`organizations`, `formal_rules`, `legal_disputes`, `diplomacy`) and eight remain
unowned.

V4-08 (evidence and testimony, 2026-11-04) deepens the owned `legal_disputes`
context with a general owner-scoped evidence ledger; it adds no capability flag,
`runner-config-v57`, root field, per-agent runner key, command, event, observer
semantic type, write pair, `/v2` route, or migration. Seven requested source
kinds (witness testimony, written record, artifact, physical state, prior
agreement, reputation, remembered event) plus closed `unknown` carry mandatory
provenance, an optional custody-belief chain, quantized confidence, closed
interpretation, retained contradictions, and owner-relative trust evaluation.
Evidence is never truth: witnesses may misremember, records may be wrong, and
artifacts may be misinterpreted, and no truth/authenticity/verdict/guilt/
liability/winner field or oracle exists. Direct and communicated testimony are
distinct and shared roots are never independent corroboration. Bounded `ev_v1`
claims travel inside existing `Talk`/`Ask`/`Tell`; `WorldEngine` never reads the
ledger. Detached `analysis.evidence_testimony_*` derives stable `evid-`
candidates, keeps objective counts, owner rows, and analytical candidates in
three separated layers, and classifies researcher-only objective alignment
(`consistent`, `unresolved`, `inconsistent`, `not_applicable`) that never
reaches cognition. Canonical `evidence-testimony-snapshot-v1`,
`evidence-testimony-store-v1`, six GET-only `/v1/simulations/{run_id}/evidence`
routes under `SUBJECTIVE_DEBUG`, and a read-only Research UI Evidence panel are
added. Three metric families (154 → 157) are appended. Pins: runner v4/v55/v56,
result v2/v3, commands 43, observer semantic types 73, metric families 157,
14 V4 contexts, 12 V4 flags, replay-v22/codec v20, `/v1`,
`observer-protocol-v1`, Alembic `0017` with no `0018`; four V4 flags are owned
(`organizations`, `formal_rules`, `legal_disputes`, `diplomacy`) and eight remain
unowned.

V4-09 (delegation and representation, 2026-11-04) deepens the owned
`organizations` context with an owner-scoped representation ledger under
`delegation-representation.v1`; it adds no capability flag,
`runner-config-v57`, root field, per-agent runner key, command, event, observer
semantic type, write pair, `/v2` route, or migration. Principals are closed to
`agent`, `organization`, `settlement`, `coalition`, and `unknown`. Recognition is
derived from principal acts, independent support, or office/decision/written
bases; a self-claim alone stays `claimed`, and rejection, contestation, and
revocation are retained. Bounded `rep_v1` frames travel inside existing
`Talk`/`Ask`/`Tell`. Detached analysis adds three appends
(`representation_mandate_structure@1`,
`representation_recognition_support@1`, `representation_scope_alignment@1`)
raising the metric catalog from 157 to **160** (V4-10 raises it to **164**), plus
`delegation-representation-snapshot-v1`, a `delegation-representation-store-v1`
filesystem store, six GET-only `/v1` representation routes under
`SUBJECTIVE_DEBUG`, and a read-only Research UI Representation panel.
Pins: runner v4/v55/v56, result v2/v3, commands 43, observer semantic types 73,
metric families 184, 14 V4 contexts, 12 V4 flags, replay-v22/codec v20, `/v1`,
`observer-protocol-v1`, and Alembic `0017` with no `0018`; four V4 flags are
owned (`organizations`, `formal_rules`, `legal_disputes`, `diplomacy`) and eight
remain unowned.

V4-10 (inter-society diplomacy, 2026-11-04) owns the fourth V4 capability flag,
`diplomacy`, on the accepted `runner-config-v56` seam; it adds no
`runner-config-v57`, root field, per-agent runner key, command, event, observer
semantic type, write pair, `/v2` route, or migration. One owner's retained
`DiplomaticRelation` records group ordered party sets with the owner self-party,
contacts, envoys, negotiations, proposals, promises, agreement views, disputes,
shared projects, declarations, misrepresentation observations, terminations, and
conflicts under `diplomacy.v1`. Organization/coalition anchors resolve only
against the owner's `orgc-` concepts, settlement anchors only against visible
regions, and missing anchors stay unresolved. Envoy standing is derived from the
representation ledger and recomputed at read time; a self-claim stays `claimed`,
and revoked/rejected/contested/expired/superseded authority is retained.
`apparently_accepted` requires every party's own declaration and binds nobody.
Bounded `dip_v1` frames travel inside existing `Talk`/`Ask`/`Tell`, and
`WorldEngine` never reads the ledger. Detached analysis derives six independent
inter-society lanes, `dip-` candidates, read-only `org-`/`msoc-` joins, three
separated layers, and researcher-only envoy alignment. Four families append
(`diplomatic_contact_structure@1`, `diplomatic_instrument_outcomes@1`,
`diplomatic_envoy_alignment@1`, `inter_society_relation_lanes@1`), raising the
catalog from 160 to **164**. `diplomacy-snapshot-v1` and
`diplomacy-store-v1` publish opt-in and atomically; six GET-only
`/v1/simulations/{run_id}/diplomacy` routes require `SUBJECTIVE_DEBUG` and fail
closed with `diplomacy_disabled`; the Research UI adds a read-only panel.
Pins: runner v4/v55/v56, result v2/v3, 43 commands, 73 observer semantic types,
184 metric families, 14 V4 contexts, 12 V4 flags, replay-v22/codec v20, `/v1`,
`observer-protocol-v1`, and Alembic `0017` with no `0018`; four V4 flags are
owned (`organizations`, `formal_rules`, `legal_disputes`, `diplomacy`) and eight
remain unowned.

V4-11 (treaties and ceasefires, 2026-11-05) deepens the owned `diplomacy` context
on the accepted `runner-config-v56` seam; it adds no flag, context, runner
schema/root field, command, event, observer semantic type, write pair, `/v2`
route, or migration. Treaties are owner beliefs with ordered participants,
immutable parent-linked versions (`original`, `amendment`, `renewal`,
`accession`, `withdrawal`, `suspension`, `termination`), participant
declarations, later-generation recollections, opaque durable-record and
institutional-memory anchors, and retained terminations and conflicts. Seven
requested subject kinds plus closed `unknown` are descriptive categories, never
permissions or world states. Recognized representatives derive from the owner
representation ledger; principals count directly, an envoy needs recognized
`negotiate`/`decide` standing and covering scope, and `apparently_accepted`
binds nobody. `trt_v1` travels in existing speech as at most four ordered chunks
(22 fields, 832 characters); `dip_v1` remains 15 fields and 320 characters.
Detached analysis appends four families (164 -> **168**) and classifies
recollection alignment for researchers only. `diplomacy-snapshot-v2` is
canonical, v1 remains decodable, `diplomacy-store-v1` is unchanged, and eight
GET-only diplomacy routes require `SUBJECTIVE_DEBUG`. `WorldEngine`, perception,
admission, stop selectors, memory, prompts, observer semantics, and Godot never
read a treaty ledger. Pins: runner v4/v55/v56, result v2/v3, 43 commands, 73
observer semantic types, 184 metric families, 14 V4 contexts, 12 V4 flags,
replay-v22/codec v20, `/v1`, `observer-protocol-v1`, Alembic `0017`; five V4
flags are owned and seven remain unowned.

V4-12 (organized conflict, 2026-11-05) owns the fifth V4 capability flag,
`organized_conflict`, on the accepted `runner-config-v56` seam and requires
`diplomacy`; it adds no flag, context, runner schema/root field, per-agent key,
command, event, observer semantic type, write pair, `/v2` route, or migration.
One owner retains plans, participations, observations, interpretations,
outcomes, contradictions, terminations, and local episodes under
`organized-conflict.v1`. Eight closed operations (`coordinated_attack`,
`defense`, `movement_group`, `resource_capture`, `structure_attack`,
`route_blocking`, `retreat`, `assistance`) compile only to existing command
names; the deterministic `Wait` replacement is the only command-producing path.
`ocf_v1` is 12 fields and 256 characters inside existing `Talk`/`Ask`/`Tell`.
Detached detection consumes committed events only, keeps three separated layers,
classifies individual, coordinated, and persistent inter-group conflict with the
locked `organized-conflict-analysis.v1` thresholds, derives forward-only `oc-`
lineage, joins `org-`/`msoc-` read-only, and classifies researcher-only
alignment. Four families append (168 -> 172). `organized-conflict-snapshot-v1`
and `organized-conflict-store-v1` publish opt-in and atomically; six GET-only
`/v1/simulations/{run_id}/organized-conflict` routes require `SUBJECTIVE_DEBUG`
and fail closed with `organized_conflict_disabled`; the Research UI adds a
read-only conflict view. Pins: runner v4/v55/v56, result v2/v3, 43 commands, 73
observer semantic types, 184 metric families, 14 V4 contexts, 12 V4 flags,
replay-v22/codec v20, `/v1`, `observer-protocol-v1`, Alembic `0017`; five V4
flags are owned and seven remain unowned.


Borders and claims (V4-13) deepen the owned `organizations` context on the
accepted `runner-config-v56` seam without a new flag, context, runner schema,
command, event, observer semantic type, write pair, `/v2` route, or migration.
With deterministic territorial claims, one owner keeps a private
`borders-claims.v1` ledger over 1-8 sorted logical locations: domain claims,
observed boundary edges, boundary recognitions, access expectations, border
agreements, and retained disputes. Overlap is legal; agreements and access
expectations bind no command; no objective border, country owner, grid, polygon,
or registry exists. Bounded `bdr_v1` relations travel inside existing
`Talk`/`Ask`/`Tell`. Detached analysis keeps physical control, subjective claim,
agreement, and analytical control pattern in four separated layers, derives
forward-only `bord-` lineage, joins `org-`/`msoc-` read-only, and classifies
researcher-only alignment. Four families append (catalog 172 -> 176).
`borders-snapshot-v1` and `borders-store-v1` publish opt-in and atomically; six
GET-only `/v1/simulations/{run_id}/borders` routes require `SUBJECTIVE_DEBUG` and
fail closed with `borders_disabled`; the Research UI adds four read-only
sections; the presentation client adds four border overlays. Pins: runner
v4/v55/v56, result v2/v3, 43 commands, 73 observer semantic types, 180 metric
families, 14 V4 contexts, 12 V4 flags, replay-v22/codec v20, `/v1`,
`observer-protocol-v1`, Alembic `0017`; five V4 flags are owned and seven remain
unowned.

Migration and displacement (V4-14) deepen the owned `organizations` context and
the V3 regional-migration seam on the accepted `runner-config-v56` seam without
a new flag, context, runner schema, command, event, observer semantic type,
write pair, `/v2` route, or SQL migration. When `organizations`,
`multi_polity_migration`, and deterministic `regions_migration` cognition are
active, one owner keeps a private `migration-displacement.v1` ledger of intents,
routes, causes, clusters, integration beliefs, and wave observations. Physical
movement remains ordinary `Move`/`Transport`/`Flee` admission; beliefs never
grant refugee status, permission, enforcement, legitimacy, score, or
sovereignty. Bounded `mdp_v1` relations (thirteen semantic fields, fourteen
parts, 256 characters, at most four relations) travel inside existing
`Talk`/`Ask`/`Tell`. Detached analysis keeps objective movement, subjective
cause, analytical wave, and integration outcome in four separated layers,
derives forward-only `mig-` candidates, joins `org-`/`msoc-` read-only, and
classifies researcher-only alignment and closed `displacement_like` labels.
Four families append (catalog 176 -> 180).
`migration-displacement-snapshot-v1` and `migration-displacement-store-v1`
publish opt-in and atomically; six GET-only `/v1/simulations/{run_id}/migration`
routes require `SUBJECTIVE_DEBUG` and fail closed with
`migration_displacement_disabled`; the Research UI adds four read-only sections;
the presentation client adds four migration overlays on the existing three
evidence classes. Pins at landing: runner v4/v55/v56, result v2/v3, 43 commands,
73 observer semantic types, 180 metric families, 14 V4 contexts, 12 V4 flags,
replay-v22/codec v20, `/v1`, `observer-protocol-v1`, Alembic `0017`; five V4
flags are owned and seven remain unowned.

Inter-society relations (V4-15) deepen analysis-only `macro_society_identity`
without a new flag, context, runner schema, command, event, observer semantic
type, write pair, `/v2` route, Godot overlay, or migration. Detached analysis
forms ordered `isr-` society pairs over contemporaneous `msoc-` candidates,
projects eight domain panels (counts/coverage/availability only), windowed time
series, and vectorial comparison, and appends four metric families (catalog
180 -> 184) beside `inter_society_relation_lanes@1`.
`inter-society-relations-snapshot-v1` and `inter-society-relations-store-v1`
publish opt-in and atomically; six GET-only
`/v1/simulations/{run_id}/inter-society-relations` routes require
`SUBJECTIVE_DEBUG` and fail closed with `inter_society_relations_disabled`
unless both root and cursor-key settings are present; the Research UI adds a
read-only panel. No authoritative civilization relationship score exists.
Pins: runner v4/v55/v56, result v2/v3, 43 commands, 73 observer semantic types,
184 metric families, 14 V4 contexts, 12 V4 flags, replay-v22/codec v20, `/v1`,
`observer-protocol-v1`, Alembic `0017`; five V4 flags are owned and seven remain
unowned.

Infrastructure networks (V4-16) own `infrastructure_networks` on accepted
`runner-config-v56` (requires `collective_projects`; no `runner-config-v57`) and
activate reserved write pair event 23 / codec `v21`. Eight locked catalog kinds
persist as location-based `infra-` assets after collective-project completion,
with operational effects on travel, capacity, production, storage, and risk,
plus damage/repair/decay/destruction. Explicit public-good frozensets keep
infra-only kinds out of Use/Maintain/Oppose sets; `well`/`warning_post` still
need `public_goods` to start. Four metric families raise the catalog 184 → 188;
observer semantics stay 73 via aliases; Alembic stays `0017`; commands stay 43.
At V4-16 landing, dual-gated research surfaces publish
`infrastructure-networks-snapshot-v1` with six GET routes, a Research UI panel,
and Godot objective overlays. Off-gate experiment `infrastructure_networks@1`
is registered. Non-goals: automatic maintenance, grid planner, infrastructure
actor, civilization score, and `supply_chains` ownership. Landing pins: runner
v4/v55/v56, result v2/v3, 43 commands, 73 observer semantic types, 188 metric
families, 14 V4 contexts, 12 V4 flags,
replay-v23/codec v21 when the channel is active, `/v1`, `observer-protocol-v1`,
Alembic `0017`; six V4 flags are owned and six remain unowned.

Travel network (V4-17) deepens the owned `infrastructure_networks` context and
the V3 `multi_polity_migration` / `regions_migration` seam without adding a V4
context, flag, runner schema, command, or migration. Locked policy
`travel-network.v1` derives objective route conditions (duration, fatigue,
capacity, risk, infrastructure quality, seasonal availability, blockage) from
existing `RouteSpec`, adjacency, season, weather, hazards, and operational
infrastructure. `WorldState.travel_network` is a bounded ordered channel seeded
at bootstrap and recomputed at tick boundaries; `Move`, `Transport`, and `Flee`
enforce closed/restricted/capacity/risk through one condition. Adjacent
`VisibleExit` rows expose local route facts only, while owner-scoped destination
memories and `regional_migration` biases provide fallible bounded route-quality
planning. Travel-network runs activate deepening write pair event **27** / codec
**`v25`**; infrastructure-only runs keep 23/`v21` and regions-only 21/`v19`.
Infrastructure snapshot v2 carries route rows while v1 remains decodable, and
seven GET-only dual-gated infrastructure routes include `/routes`. Four metric
families append 188 -> 192 metric families; V4-18 later appends six families to 204; observer semantics stay 73, commands 43,
runner v4/v55/v56, result v2/v3, replay-v27/codec v25 when active, `/v1`,
`observer-protocol-v1`, and Alembic `0017`. Off-gate experiment
`travel_network@1` is registered; 14 V4 contexts / 12 flags / eight owned remain.

Trade networks (V4-18) deepen the owned `infrastructure_networks` context, the V3
`multi_polity_migration` / `regions_migration` seam, and the V3 exchange/valuation
seam without adding a V4 context, flag, runner schema, command, event, observer
semantic type, write pair, or migration. Locked `trade-networks.v1` reconstructs
transfer and local-supply evidence from committed events only; derives directed
corridors, observed exchange dependence, major exchange locations and venues,
cross-society flows over contemporaneous `msoc-` candidates, and forward-only
`trd-net-` network lineage. Six metric families append 192 -> **198**;
`trade-networks-snapshot-v1` and `trade-networks-store-v1` publish opt-in and
atomically; seven GET-only `/v1/simulations/{run_id}/trade-networks` routes
require `SUBJECTIVE_DEBUG` and fail closed with `trade_networks_disabled`; the
Research UI adds a read-only panel and the Godot observer adds four analytical
overlays. Off-gate experiment `trade_networks@1` is registered. No centralized
routing, planner, quota, allocation, price, money, currency, or registry exists.
Pins: runner v4/v55/v56, result v2/v3, 43 commands, 73 observer semantic types,
198 metric families, 14 V4 contexts, 12 V4 flags, eight owned, replay-v27/codec
`v25`, `/v1`, `observer-protocol-v1`, Alembic `0017`. Current pins: metric families 212; the current catalog is 212 families (catalog 212).

Supply chains (V4-19) own the declared `supply_chains` V4 context on the
accepted `runner-config-v56` seam and add no context, flag slot,
`runner-config-v57`, root field, per-agent key, command, event, observer
semantic type, write pair, or migration. `world.supply_chain` locks
`supply-chains.v1`, six chain recipes (`harvest_grain`, `mill_grain`,
`bake_bread`, `craft_plank`, `craft_tool_head`, `assemble_tool`), catalog
validation, and a +0.10 held-`STRIKE` harvest probability bonus. The legacy
six-recipe catalog and digest stay byte-identical. Detached analysis reconstructs
ten dependency edge kinds over resources, items, structures, storage, transport,
locations, infrastructure, organizations, tools, and skills, depth-bounded
chains, forward-only lineage including empty windows, and seven descriptive
bottleneck kinds. Six metric families append 198 → **204**.
`supply-chains-snapshot-v1` and `supply-chains-store-v1` publish opt-in and
atomically; seven GET-only `/v1/simulations/{run_id}/supply-chains` routes
require `SUBJECTIVE_DEBUG` and fail closed with `supply_chains_disabled`; the
Research UI adds a read-only panel and no Godot overlay. Off-gate experiment
`supply_chains@1` is registered. No central planner, optimizer, quota,
automatic allocation, price, money, currency, score, ranking, severity, or
recommendation exists. Pins: 43 commands, 73 observer semantic types, 204
metric families, 14 V4 contexts, 12 V4 flags, eight owned, replay-v27/codec
`v25`, `/v1`, `observer-protocol-v1`, Alembic `0017`.

Market-like institutions (V4-20) own the declared `markets_credit` V4 context on
the accepted `runner-config-v56` seam and add no context, flag slot,
`runner-config-v57`, root field, per-agent key, command, event, observer semantic
type, write pair, `/v2` route, or migration. One owner keeps a bounded
`market-institutions.v1` ledger of own-observed exchange venues, meeting
expectations, social schedules, emergent broker-like role claims, and opaque
record anchors. Exchange remains `NegotiateExchange`/`ExchangeCompleted`; no
price, money, credit, debt, allocation, quota, or planner exists. Bounded
`mkt_v1` relations travel inside existing speech; the only command-producing path
replaces `Wait` with one observed adjacent `Move`. Detached
`analysis.market_institutions_*` reconstructs gatherings, venues, market
candidates, participation, owner joins, researcher-only alignment, and
forward-only lineage from committed events only. Four families append the catalog
204 -> **208**. `market-institutions-snapshot-v1` and
`market-institutions-store-v1` publish opt-in and atomically; seven GET-only
`/v1/simulations/{run_id}/market-institutions` routes require `SUBJECTIVE_DEBUG`
and fail closed with `market_institutions_disabled`; the Research UI adds a
read-only panel and Godot adds no overlay. Off-gate experiment
`market_institutions@1` is registered. Pins: 43 commands, 73 observer semantic
types, 208 metric families, 14 V4 contexts, 12 V4 flags, eight owned / four
unowned, replay-v27/codec `v25`, `/v1`, `observer-protocol-v1`, Alembic `0017`.

Emergent prices (V4-21) deepen the owned `markets_credit` context and add no
context, flag slot, `runner-config-v57`, root field, per-agent key, command,
event, observer semantic type, write pair, `/v2` route, or migration. Price
cognition activates only when `markets_credit` and the V3-18
`subjective_valuation` spec are both present. One owner keeps a bounded
`emergent-prices.v1` ledger of item-kind expectations, unit sources, observed
exchange ratios, quotes, confidence, and notices. Bounded `prc_v1` relations
travel only inside existing `Talk`/`Tell`; no command is created or replaced, and
expectations never alter exchange admission. Detached
`analysis.emergent_prices_*` reconstructs paired ratios, completed and quoted
distributions, owner joins, market distributions through detached V4-20
memberships, and pairwise convergence from committed events and token-only
exports. Four families append the catalog 208 -> **212**; current catalog: 220 metric families. The sibling
`emergent-prices-snapshot-v1` / `emergent-prices-store-v1` artifact publishes
programmatically and atomically; seven GET-only
`/v1/simulations/{run_id}/emergent-prices` routes require `SUBJECTIVE_DEBUG` and
fail closed with `emergent_prices_disabled`; the Research UI adds a read-only
panel and Godot adds no overlay. Off-gate experiment `emergent_prices@1` is
registered. No money, currency, credit, debt, allocation, quota, planner, or
canonical price exists. Pins: 43 commands, 73 observer semantic types, metric families 220, 14 V4 contexts, 12 V4 flags, eight owned / four unowned,
replay-v27/codec `v25`, `/v1`, `observer-protocol-v1`, Alembic `0017`.

Credit relationships (V4-22) deepen the owned `markets_credit` context and add
no context, flag slot, `runner-config-v57`, root field, per-agent key, command,
event, observer semantic type, write pair, `/v2` route, or migration. Credit
cognition activates only when `markets_credit` and the V3-17
`structured_commitments` spec are both present. One owner keeps a bounded
`credit-relationships.v1` ledger of direction, item-kind principal/repayment
terms, conditions, deadlines, collateral-like claims, revisions, acts, status,
trust, willingness, and confidence. Bounded `crd_v1` frames travel inside
existing `Talk`/`Tell`; every act is a declaration and no command is created or
replaced. Detached `analysis.credit_relationships_*` reconstructs committed
claims and `Given` transfers, descriptive performances, separate
`proposed`/`agreed` repayment distributions, counterparty aggregates, and
researcher-only alignment. Four families append the catalog 212 -> **216**.
`credit-relationships-snapshot-v1` / `credit-relationships-store-v1` publish
programmatically and atomically; seven GET-only
`/v1/simulations/{run_id}/credit-relationships` routes require
`SUBJECTIVE_DEBUG`; the Research UI adds a read-only panel and Godot adds no
overlay. Off-gate experiment `credit_relationships@1` is registered. No bank,
money, interest, enforceable debt, credit score, or canonical credit exists.
Pins: 43 commands, 73 observer semantic types, 220 metric families, 14 V4
contexts, 12 V4 flags, eight owned / four unowned, replay-v27/codec `v25`,
`/v1`, `observer-protocol-v1`, Alembic `0017`.

V4-23 (accounting ledgers, 2026-11-12) deepens the owned `organizations`
context and the V3-11 durable-records seam without adding a V4 context, flag
slot, `runner-config-v57`, root field, per-agent key, command, event, observer
semantic type, write pair, `/v2` route, migration, or Godot overlay. Accounting
cognition activates only when `organizations` and the `durable_records` spec are
present; the durable channel keeps its cultural/provenance prerequisites. One
owner keeps a bounded `accounting-ledgers.v1` ledger of five descriptive record
kinds (`exchange`, `debt`, `inventory`, `organizational_resource`,
`contribution`), six directions, six owner appraisals, revisions, evidence refs,
confidence, counts, and notices. `consistent` is not truth and
`suspected_fraudulent` is not proven fraud. Accounting-like artifacts are
existing durable records carrying `acc_v1` relation triples; bounded `acc_v1`
frames travel inside existing `Talk`/`Tell`, and accounting content may extend an
already-selected `Inscribe` without changing its verb, kind, or recipient.
Evidence use is a pure candidate bridge into the existing V4-08 ledger. Detached
`analysis.accounting_ledgers_*` reconstructs committed records, transfers,
contributions, and speech, keeps three separated layers, and appends four metric
families (216 -> 220). `accounting-ledgers-snapshot-v1` and
`accounting-ledgers-store-v1` publish programmatically and atomically; seven
GET-only `/v1/simulations/{run_id}/accounting-ledgers` routes require
`SUBJECTIVE_DEBUG` and fail closed with `accounting_ledgers_disabled`; the
Research UI adds a read-only panel and Godot adds no overlay. Off-gate experiment
`accounting_ledgers@1` is registered. Pins: 220 metric families, 43 commands, 73
observer semantic types, 14 V4 contexts, 12 V4 flags, eight owned / four
unowned, replay-v27/codec `v25`, `/v1`, `observer-protocol-v1`, Alembic `0017`.
