# Implementation Plan: V3-23 Multiple Societies

Branch: main (current branch; `git.create_branches: false`)
Created: 2026-10-17
Mode: full

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes — mandatory `/aif-docs` checkpoint during implementation.
- Artifact naming: every plan artifact produced for this feature begins `v3-`; canonical file is `.ai-factory/plans/v3-23-multiple-societies.md`.
- Implementation scope: analytical detection of candidate societies/communities in long-running, spatially/socially separated populations; cross-community divergence measurement; isolation audit. **No Nation/Country/polity entities, no new capability flag, no new commands.**

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Lets demographically separated populations be compared as candidate societies using only owned V2/V3 primitives, keeping all society labels analytical and every authority/epistemic boundary intact.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] full mode confirmed; git.create_branches=false; resolved plan file: .ai-factory/plans/v3-23-multiple-societies.md (format=slug)
INFO [aif-plan] plan_default_milestone=auto surfaces M6 first; explicit V3 scope uses M7, following v3-22 precedent; this plan does not close M6
INFO [aif-plan] RESEARCH.md absent and skill-context/aif-plan/SKILL.md contains context-budget rules only; research_influenced_plan=false

## Goal

Support long-running populations that become spatially and socially separated, and let researchers ask — **after the run**, from detached evidence only — whether candidate societies/communities have emerged and how they differ. Different isolated populations may independently develop vocabulary, norms, technology, stories, institutions, and trade patterns; the analysis must detect such divergence without any new world authority, without Nation/Country/polity entities, and without allowing isolated communities to magically share information. Everything detected is an analytical candidate, never an agent-visible fact.

## Current Implementation Evidence

- Regions/journeys (v3-22, `runner-config-v44`, replay-v21/codec v19): `src/world/regions.py` immutable specs; `src/world/_travel.py` discrete journeys; regional perception reveals only the observer's own region label and opt-in adjacent-destination metadata. Experiment AY / `regional_migration@1` / `regional_population@1` / `regional_destination_beliefs@1` exist.
- Emergence ledgers (all owner-scoped on `AgentRuntimeState`, no capability flags): `GroupLedger` (group_formation.py), `NormLedger` (social_norms.py), `ConventionLedger` (social_conventions.py), `TerminologyLedger` (semantic_naming.py), `NarrativeLedger` (cultural_narratives.py), `CulturalFeatureLedger` (cultural_features.py, v3-09), `PracticalKnowledgeLedger` (practical_knowledge.py, v3-13). Analysis must **not** import these ledger types (enforced by `tests/architecture/test_v3_historical_memory_analysis_only.py`); analysis consumes derived/analytical rows via `experiments.composition`.
- Trade/institution primitives: `ExchangeProposed/Withdrawn/Completed` events + `NegotiateExchange` (v3-18, runner-config-v40); collective-project and public-good events/commands (v3-20/v3-21, runner-config-v43).
- Community detection already exists for trust: `src/analysis/network_metrics.py::compute_group_community_structure` (networkx `greedy_modularity_communities`, canonicalized labels); candidate cluster logic in `group_formation_metrics.py`; divergence comparators (`js_divergence`, `_mean_divergence`) in cultural/behavioral metric modules; `query_independent_emergence_count` in `knowledge_genealogy.py`.
- Metric catalog: `src/analysis/specifications.py`, `METRIC_CATALOG_VERSION = "metric-catalog-v1"`, `METRIC_FAMILY_COUNT = 94`; assembly in `src/analysis/metric_service.py`; collection in `src/experiments/metric_collection.py`.
- Isolation today: communication requires living colocated participants and visibility (`_evaluate_communication`, `_rules.py`); perception is strictly location-scoped with `remote_weather`/`remote_topology` OMITTED; artifacts require colocation/holding. There is no code path by which spatially isolated agents share information — this plan must add the **audit** that proves it per run, not a new channel.
- Baseline: 43 command variants, 69 observer semantic types, Alembic `0017`, replay-v21/codec v19 max, latest experiment AX/AY. Recheck these selectors before implementation if other feature work lands first.

## Compatibility and Authority Contract

1. `WorldEngine` remains the sole objective mutation authority. This plan adds **no** domain behavior: no new commands, no new events, no new perception fields, no new capability flag, no runner-config bump beyond what composition of existing channels already requires (v44 regions + owned cultural/economic channels). Default flags-off runs are byte-identical to baseline.
2. No Nation, Country, Polity, Society, or Community entity is created anywhere — not in `world`, not in `agents`, not in persistence. "Society" and "community" are analysis-output labels only, like existing group-cluster labels.
3. Analysis stays read-only and detached; it imports no persistence and no subjective ledger types. All joining of objective events with subjective-derived rows happens in `src/experiments/composition.py`.
4. Detection results never flow into cognition, memory, prompts, admission, or observations. Analytical labels are never rendered as agent-visible truth (existing research-ui epistemic chrome rule: `analytical_inference`).
5. Isolation is an audited property, not a new mechanism: the analysis reports cross-community transmission evidence (communication edges, testimony hops, narrative lineage hops, knowledge-genealogy edges, artifact copy/diffusion rows) and flags any edge whose evidence implies information transfer without a physical journey. The engine's existing eligibility rules remain the only authority; this plan does not relax or extend them.
6. Divergence is measured per dimension (vocabulary, norms, conventions, technology/practical knowledge, stories/narratives, institutions/projects/public goods, trade/exchange) using existing digest/quantized-distribution conventions (`js_divergence`-style comparators, quantize per `src/analysis/numerical.py`). Identical seeds in separated regions may legitimately converge — convergence is a reported result, not an error.
7. Unknown/missing evidence stays unknown (`MetricAvailability` present/absent/partial/unknown); no zeros are inferred for missing channels. Coverage and denominators are exposed.
8. Keep Alembic `0017`, `/v1`, replay/codec boundaries, and command/semantic counts unchanged. If implementation uncovers a concrete incompatible consumer contract, record it in the plan log rather than silently widening a wire contract.

## Design Decisions

### Candidate community detection (analysis-only)

- New module `src/analysis/society_emergence.py`. A **candidate community** is a set of living person IDs produced post-run from three detached evidence lanes, each optional: (a) sustained residence — derived from existing regional population folding (`fold_regional_history` / boundary rows) using configured residence logic, never raw travel noise; (b) interaction graph — union of existing communication edges (`_communication_edges_from_events`), exchange occurrences, collective-project participation, and teaching/mentorship edges; (c) trust graph — the existing nonnegative trust projection already used by `compute_group_community_structure`.
- Community detection runs per analysis snapshot over the union graph restricted to living persons, using the already-supported `networkx.community.greedy_modularity_communities` algorithm (recorded in `library_versions`, quantized per numerical policy). Spatially separated subpopulations with no interaction edges become separate components and therefore separate candidate communities; do not force a single global community. Canonicalize community labels exactly like `canonicalize_community_labels` (deterministic ordering, content-derived ids, sha256 — never owner PII or narrative text).
- Persons with zero edges are singletons/coverage gaps, not errors. Persons appearing in multiple lanes are deduplicated by person id before clustering. Dead persons are excluded from end-state communities but remain in temporal divergence folds.
- Output DTOs: `CandidateCommunityRow` (community_id, person_ids digest-list, lane coverage, residence-region linkage, tick range), `SocietyEmissionResult` (communities, singletons, coverage). All ids/digests only — no labels, narratives, or content payloads.

### Cross-society divergence families

- New module `src/analysis/society_divergence.py`. For each pair of candidate communities (and each community vs. global baseline), compute per-dimension divergence from existing derived rows:
  - **vocabulary**: terminology-ledger digest distributions via composition harvest rows (reuse naming metric row shape);
  - **norms / conventions**: habit/norm belief digest distributions (reuse `cultural_channel_rows_from_norm_beliefs` / convention habit rows);
  - **technology**: practical-knowledge / technique digest distributions from knowledge-genealogy harvest rows; independent-emergence counts reuse `query_independent_emergence_count` semantics;
  - **stories**: narrative-lineage cluster digests (reuse `cultural_narrative_metrics` row shapes);
  - **institutions**: collective-project/public-good participation distributions per community;
  - **trade**: exchange counterparty/item-kind distributions per community (kinds/digests only, no content).
- Each dimension yields a quantized divergence value with numerator/denominator coverage, one `MetricDocument` per family; families: `society_emergence@1`, `society_divergence@1`, `society_isolation@1`. Absent channel → availability `absent` for that dimension, not zero.
- Divergence is symmetric and pair-scoped; `compare_metric_documents` remains the run-over-run comparison path and is unchanged.

### Isolation audit

- `society_isolation@1` inspects all cross-community evidence edges (communication, testimony hops, narrative hops, knowledge-genealogy cross-owner edges, artifact copy rows) and classifies each as `journey_explained` (a completed arrival of at least one participant between the communities exists in objective relocation evidence before the edge's evidence time) or `unexplained` (no physical journey — a potential leak). Report counts and coverage; `unexplained > 0` is reported as a finding with reason codes, never auto-remediated and never fed back into the simulation. Timing uses logical ticks only.

### Experiment AZ (off the V1 regression gate)

- New `src/experiments/multiple_societies_scenario.py` + catalog builder `experiment_az_multiple_societies`: ≥2 region-separated populations (v44 regions), owned cultural/economic channels enabled (naming, norms, conventions, narratives, cultural provenance, knowledge genealogy, exchange, collective projects/public goods as appropriate), long tick budget, deterministic arbiter asserting: detection produces ≥2 candidate communities; isolation audit reports zero `unexplained` edges; divergence documents are computable per dimension. Register `multiple_societies@1` off the V1 gate, following AY precedent.

### Presentation and docs

- Research UI: candidate-society panel under existing `research_inference` chrome (`analytical_inference` epistemic label); no observer/Godot protocol change, no new semantic types.
- Docs: `docs/experiments.md` (Experiment AZ), `docs/architecture.md` (analytical-only boundary note), README index if pages are added.

## Commit Plan

Commit messages are suggestions for implementation; this planning command creates no commits.

- **Commit 1** (tasks 1–3): `feat(v3): add analytical candidate-society detection contracts and clustering`
- **Commit 2** (tasks 4–6): `feat(v3): compute cross-society divergence and isolation audit metrics`
- **Commit 3** (tasks 7–8): `feat(v3): wire composition harvests and experiment AZ scenario`
- **Commit 4** (tasks 9–10): `feat(v3): present analytical societies in research UI and docs`
- **Commit 5** (task 11): `feat(v3): reconcile gates for multiple societies analysis`

## Tasks

### Phase 1 — Detection contracts and clustering

- [x] **Task 1: Define candidate-society analysis contracts with exact validation.**
  - Files: create `src/analysis/society_emergence.py` (DTOs + validators); update `src/analysis/__init__.py` facade; update `src/analysis/specifications.py` (`SOCIETY_EMERGENCE` spec); create `tests/unit/test_society_emergence_contracts.py`.
  - Deliver frozen DTOs `CandidateCommunityRow` / `SocietyEmissionResult` with validated opaque IDs, sha256-derived canonical community labels, lane-coverage flags, and exact rejection of empty person sets, duplicate persons across communities, unknown persons, and content payloads. Quantize per `numerical.py`; reuse the existing `library_versions()` entry for `networkx.community.greedy_modularity_communities` (`src/analysis/numerical.py`) — assert it is present rather than adding a new registry key.
  - Acceptance: malformed rows reject with safe reason codes; canonical ordering round-trips; caller mutation cannot alter frozen rows; no ledger types imported (architecture test updated/extended).
  - Logging: DEBUG at validation boundaries with counts/IDs only; no labels or content. Pure constructors need no side-effect logs.
  - Dependencies: none.

- [x] **Task 2: Implement deterministic candidate-community clustering over detached lanes.**
  - Files: `src/analysis/society_emergence.py`; create `tests/unit/test_society_emergence_clustering.py`.
  - Implement `compute_candidate_communities(residence_rows, interaction_edges, trust_edges, living_person_ids, tick)` using `networkx.community.greedy_modularity_communities` over the union graph of the supplied lanes; disconnected components stay separate; zero-edge persons become singletons with coverage gaps; deduplicate persons across lanes before clustering.
  - Acceptance: known-answer graphs (two disconnected region-separated populations; one bridged population; empty lanes → all singletons) produce pinned community sets; identical inputs → identical canonical labels across processes (no `hash()`, explicit ordering).
  - Logging: DEBUG with node/edge counts and community count; INFO summary once per computation. No person-adjacent content.
  - Dependencies: 1.

- [x] **Task 3: Pin society-emergence metric document and catalog registration.**
  - Files: `src/analysis/society_emergence.py`, `specifications.py` (`METRIC_FAMILY_COUNT` 94 → 95), `metric_service.py` assembly inputs; update `tests/unit/test_metric_specifications.py`, `tests/unit/test_metric_service.py`, and **all 19 `tests/unit/*` files that hardcode `METRIC_FAMILY_COUNT == 94`** (there is no `test_metric_catalog.py`; `tests/unit/metric_fixtures.py::EXPECTED_FAMILY_COUNT` is dynamic and needs no change). Find them with `rg -l "METRIC_FAMILY_COUNT == 94" tests/unit`.
  - Emit `society_emergence@1` `MetricDocument` with availability/coverage and provenance; wire into `assemble_metric_documents` behind the fail-closed `_safe` wrapper; cross-version comparison still rejects.
  - Acceptance: catalog validation passes at the new count; flags-off/baseline runs emit `absent` availability without error; document fingerprint is stable for identical inputs.
  - Logging: INFO at assembly with family id + availability only.
  - Dependencies: 2.

### Phase 2 — Divergence and isolation

- [x] **Task 4: Implement per-dimension cross-society divergence computation.**
  - Files: create `src/analysis/society_divergence.py`; update `src/analysis/__init__.py`, `specifications.py`; create `tests/unit/test_society_divergence.py`.
  - Deliver `compute_society_divergence(communities, dimension_rows)` producing pair-scoped quantized divergences for the seven dimensions (vocabulary, norms, conventions, technology, stories, institutions, trade) from detached digest distributions; absent channel → `absent` availability per pair/dimension. **Comparator contract:** the existing JS-divergence math lives in *private* helpers (`_kl` / `_js_to_mixture` / `_mean_divergence` in `src/analysis/cultural_transmission_metrics.py:133-190`) — extract the core into a shared public helper in `src/analysis/numerical.py` (preferred; update `cultural_transmission_metrics` to consume it) or pin a deliberately duplicated comparator with known-answer tests in `society_divergence.py`; do **not** import `_`-private functions cross-module. Quantize per `numerical.py` policy.
  - Acceptance: known-answer distributions (identical, disjoint, partial-overlap) produce pinned quantized values; coverage denominators exposed; identical communities yield zero divergence; missing dimensions never coerce to zero.
  - Logging: DEBUG per pair/dimension with coverage counts; no digests of content, only counts.
  - Dependencies: 2.

- [x] **Task 5: Implement the cross-society isolation audit.**
  - Files: `src/analysis/society_divergence.py` (or sibling `society_isolation.py` if cleaner); update `specifications.py`; create `tests/unit/test_society_isolation.py`.
  - Classify every cross-community evidence edge (communication, testimony hops, narrative hops, knowledge-genealogy edges, artifact copy rows) as `journey_explained` or `unexplained` against objective relocation/arrival evidence ordered by logical tick; emit counts, coverage, and safe reason codes. `unexplained > 0` is a reported finding only.
  - Acceptance: synthetic runs with travel-then-contact yield all `journey_explained`; runs with no journeys yield zero cross-community edges or all `unexplained` when edges exist; edges before any possible journey are flagged; timing uses ticks only.
  - Logging: INFO audit summary (explained/unexplained counts); WARN with reason code only when unexplained edges exist. No content.
  - Dependencies: 2.

- [x] **Task 6: Register divergence and isolation metric families and assembly.**
  - Files: `src/analysis/society_divergence.py`, `specifications.py` (count 95 → 97 for `SOCIETY_DIVERGENCE`, `SOCIETY_ISOLATION`), `metric_service.py`; update `tests/unit/test_metric_specifications.py`, `tests/unit/test_metric_service.py`, and the same 19 hardcoded `== 94`→`== 97` unit files from Task 3 (`rg -l "METRIC_FAMILY_COUNT == 94" tests/unit`).
  - Emit `society_divergence@1` and `society_isolation@1` documents with pair coverage and provenance; assembly stays fail-closed and sorted; `METRIC_FAMILY_COUNT = 97`.
  - Acceptance: catalog count tests updated and green; unavailable lanes degrade to `absent`/`partial` without exceptions; fingerprints stable.
  - Logging: INFO at assembly with family ids + availability.
  - Dependencies: 4, 5.

### Phase 3 — Composition and experiment

- [x] **Task 7: Add composition harvest rows for society analysis.**
  - Files: `src/experiments/composition.py`; create `tests/unit/test_society_composition.py`.
  - Deliver `society_emission_inputs_from_context(...)` mapping snapshots/events into residence rows, interaction edges (communication, exchange, collective-project, teaching), **trust edges, and per-dimension digest rows** — reusing existing harvest helpers (`_communication_edges_from_events`, regional rows, knowledge/narrative/naming row shapes) without importing subjective ledger types.
  - **Trust-edge harvest (new):** no composition harvest for trust/relationship rows exists today (`RelationshipEdgeRow` is only constructed in tests, e.g. `tests/unit/test_reference_scenario_e2e.py:204` builds them from `reference_outcome.relationships`). Add a harvest projecting the runner-outcome relationship export into `RelationshipEdgeRow`s consumable by `network_metrics.build_signed_trust_digraph` / `nonnegative_undirected_projection` for trust lane (c).
  - Acceptance: detached inputs reproduce from a restored snapshot identically to live; manifest clamping respected; no persistence imports inside analysis modules.
  - Logging: DEBUG row counts per lane; INFO harvest completion.
  - Dependencies: 6.

- [x] **Task 8: Build Experiment AZ multiple-societies scenario and catalog entry.**
  - Files: create `src/experiments/multiple_societies_scenario.py`; update `src/experiments/catalog.py`, `src/experiments/__init__.py` as needed; create `tests/unit/test_experiment_az.py`.
  - Two or more region-separated populations on `runner-config-v44` with owned cultural/economic channels enabled; deterministic arbiter asserting ≥2 candidate communities, zero unexplained isolation edges, and computable per-dimension divergence; register `multiple_societies@1` off the V1 regression gate; matrix-compatible.
  - **Off-gate registration is concrete:** append `multiple_societies@1` to the `OFF_GATE_MATRIX_EXPERIMENT_IDS` frozenset in `src/experiments/catalog.py` (precedent: `regional_migration@1` is already a member) and assert membership in `tests/unit/test_experiment_az.py` (precedent: `tests/unit/test_experiment_ay.py:44`).
  - Acceptance: scenario runs deterministically from fixed seed; arbiter assertions hold on the reference configuration; experiment stays off the V1 gate and flags-off baseline is untouched.
  - Logging: INFO registration with arms/counts; DEBUG arbiter assertion results (counts only).
  - Dependencies: 7.

### Phase 4 — Presentation, docs, gates

- [x] **Task 9: Expose analytical societies in the Research UI.**
  - Files: new Svelte view under `clients/research-ui/src/views/` (e.g. `SocietiesPanel.svelte`) using the generic metric fetch in `clients/research-ui/src/api/client.ts`; epistemic chrome in `src/observer/research_ui_state.py` (`_ANALYTICAL_OVERLAYS` mapping) and `clients/research-ui/src/epistemic.ts`; router/view registration in `clients/research-ui/src/router.ts` / `App.svelte`; tests for the new view and epistemic mapping.
  - **No backend API change is required:** `GET /v1/simulations/{run_id}/metrics` and `/metrics/{metric_set_id}/{metric_family}` (`src/api/routes/inspection.py:670,689`) are family-agnostic via `MetricReadService` — the new families flow through the existing catalog/document endpoints once assembled. Render candidate communities and divergence/isolation documents under existing `research_inference` chrome with the `analytical_inference` epistemic label; no Godot/observer protocol change, no new semantic types, no objective-timeline labels.
  - Acceptance: UI panel lists communities/divergence with epistemic chrome; analytical results are never presented as agent-visible facts (existing rule enforced by test).
  - Logging: none new beyond existing read-path logging.
  - Dependencies: 6.

- [x] **Task 10: Documentation checkpoint.**
  - Files: `docs/experiments.md` (Experiment AZ), `docs/analysis-metrics.md` (new "Multiple-societies families (off the V1 gate)" section for `society_emergence@1` / `society_divergence@1` / `society_isolation@1`, matching the existing per-group convention), `docs/architecture.md` (analytical-only boundary note), `docs/research-ui.md` (new panel + read path), `docs/observer.md` if needed, README index per `/aif-docs`.
  - Document Experiment AZ, the three `society_*@1` families, the analytical-only boundary (no society entities, no agent-visible labels), and the isolation-audit semantics (`unexplained` is a finding, not an auto-fix).
  - Acceptance: docs match implementation; anchors/links valid; reproduction example for AZ runs.
  - Logging: N/A.
  - Dependencies: 8.

- [x] **Task 11: Gate reconciliation and final verification.**
  - Files: any fallout across tests; `pyproject`/lint configs unchanged unless required.
  - Run and reconcile: full pytest, architecture + import-linter checks (analysis must not import ledgers/persistence), Ruff, format, mypy, required six-file V1/V2 compatibility gate, registered Godot suite (unchanged expectations), disposable PostgreSQL/pgvector integration for AZ if persistence paths are exercised.
  - Acceptance: all required gates green or explicitly documented; command count stays 43, semantic count 69, Alembic head 0017, replay/codec boundaries unchanged.
  - Logging: N/A.
  - Dependencies: 9, 10.
