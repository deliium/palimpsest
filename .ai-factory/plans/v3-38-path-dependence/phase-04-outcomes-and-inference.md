# Phase 4: Seven outcome domains and seed-block inference

Plan: [index.md](index.md)
Tasks: 10–12
Depends on: Tasks 1–9

## Objective

Measure seven separate outcome domains and compare predeclared branch protocols using paired differences across independent numeric-seed blocks. No single-run causal conclusion or composite civilization score is produced.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|---|---|---|
| `src/analysis/cultural_metric_comparison.py` | `_t_interval` 395–410; `_seed_block_values` 413; `_build_contrast` | Existing repeated-seed numerical policy, not a general outcome decoder. |
| `src/analysis/social_norm_metrics.py` | `compute_emergent_social_norms`, `compute_norm_persistence` | Existing behavioral/belief measures and missingness. |
| `src/analysis/relationship_metrics.py` | `compute_relationship_stability`, values 201–241 | Mean absolute change can be unavailable without intervals. |
| `src/analysis/institutional_persistence.py` | `compute_institutional_persistence_metric`, lines 190–269 | Zero persistent candidates is PARTIAL, empty rows ABSENT. |
| `src/analysis/objective_metrics.py` | `compute_resource_inequality`, `compute_cooperation` | Resource Gini/Theil and applied-action cooperation, not moral goodness. |
| `src/analysis/cultural_narrative_survival.py`, `src/analysis/cultural_technology_continuity.py` | `compute_cultural_narrative_survival`, `compute_cultural_technology_continuity` | Exact baseline/endpoint, gaps and archival provenance. |
| `src/experiments/cultural_evidence.py`, `src/experiments/cultural_metric_artifacts.py` | `install_cultural_recorder`, `verify_cultural_pair` | Existing opt-in cultural capture and artifact verification. |
| `src/experiments/composition.py` | `norm_belief_rows_from_ledgers` 1279; six `institution_*_rows_from_*` adapters 3646–4017 | Reuse established detached projections instead of introducing parallel classifiers. |
| `src/analysis/relationship_metrics.py` | `compute_relationship_stability` 81–137 | Accepts `window_end` only; caller must prepare the exact start/predecessor and exclude later revisions. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/simulation/fork_checkpoint.py`, `src/simulation/runner.py` | modify | Read-only finalized scientific owner snapshot projection, no hidden-state exposure to cognition. |
| `src/experiments/path_dependence_evidence.py` | create | Bounded finalized collection and detached adapters. |
| `src/experiments/cultural_evidence.py`, `src/simulation/cultural_evidence.py` | modify | Explicit start-at-F recorder/baseline and coverage contracts, preserving default tick-zero behavior. |
| `src/experiments/composition.py` | modify only where an existing adapter needs a narrow public extension | Reuse norm and institution lanes; no duplicate inference algorithms. |
| `src/analysis/path_dependence_models.py` | create | Outcome rows, selector keys and comparison models. |
| `src/analysis/path_dependence_outcomes.py` | create | Closed seven-domain scalar selector registry. |
| `src/analysis/seed_block_statistics.py` | create | Public reusable Student-t numerical helper. |
| `src/analysis/cultural_metric_comparison.py` | modify | Delegate numerical helper with byte-equivalent output policy. |
| `src/analysis/path_dependence_comparison.py` | create | Explicit paired/block comparison. |
| `src/analysis/__init__.py` | modify | Public detached APIs. |
| `tests/unit/test_path_dependence_evidence.py`, `tests/unit/test_path_dependence_outcomes.py`, `tests/unit/test_path_dependence_comparison.py` | create | Coverage, selectors and statistical oracles. |

## Task 10: Collect bounded finalized evidence with exact coverage

### Intent

Collect what was actually executed without making experimental analytics part of live agent behavior or mistaking a restored prefix for fully captured cultural history.

### Implementation Steps

1. Introduce `FinalizedResearchOwnerSnapshot` projection and public runner export at complete boundaries containing owner identity, current public memory/belief/relationship rows and histories needed by registered metrics, plus only relevant norm/institution/practical-knowledge/narrative ledgers. Reuse `export_social_norm_ledgers`, `export_institution_concept_ledgers`, existing runtime cultural exports and owner-bundle readers internally; the new wrapper supplies owner/mode/coverage identity missing from tuple-only exports, rather than implementing a second ledger store. It is a detached scientific export, not a cognition perspective, and contains no engine token or mutable services. Use typed public contracts; do not expose raw private `_AgentBundle` or hidden fork-state dictionaries to analysis.
2. `PathDependenceEvidenceRecorder` collects F baseline, every configured cadence boundary and exact requested endpoints after all finalizations. Preserve owner admissions/deaths/generation labels from finalized population progress; export committed events and action resolutions for each requested action window. Feed detached owner data through experiment adapters into existing analysis inputs.
3. Add public `CulturalEvidenceRecorder.start_at_boundary(F)` defining the first allowed capture, rejecting earlier/duplicate baselines and accepting the restored F frame exactly once. Construct it before fork restoration and pass it as the Task 4 factory's `cultural_sink`; the factory publishes F after all owner state/coverage witnesses are restored. Keep existing tick-zero recorder behavior unchanged. Do not call `install_cultural_recorder` on an already-started restored runner or clear `_cultural_missing_prefix_through` privately. Mark pre-F history outside scope while certifying F-onward complete coverage; known-fresh-empty remains complete, restored-unknown remains unknown. Baseline-dependent narrative/technology comparisons use F; no claim of initial-founder-to-end continuity without pre-F capture. Missing boundary, disabled mode, terminated/missing owner and capacity truncation retain distinct status codes.
4. Bound sample cadence, maximum owners/rows/window length and total recorder memory from spec limits; keep only requested boundary samples and requisite revision/event windows, not every full checkpoint at every tick. Spill canonical detached research rows to immutable artifact chunks when limits require it; enforce manifest chunk counts/byte limits. Never truncate and still report complete coverage.
5. Record per-domain expected/observed owners, windows, endpoints, generation coverage, left/right censoring, and status. Extinction has an observed zero population but does not imply zero trust, inequality or narrative retention. Technical failure and early terminal stop are not known-zero endpoints. Pre-treatment prefix ineligibility has its own denominator.

### Required Interfaces and Contracts

`collect_path_dependence_boundary(runner, boundary, recorder)` is composition-only. Analysis receives immutable rows, never runners/clients/services. Collection cannot affect commands, stops, RNG, prompts, memories or replay events. Capture on/off must leave objective and subjective trajectories identical.

### Requirement Evidence

User seven outcomes; ARCHITECTURE analysis isolation; V3-37 explicit coverage semantics and existing restored-prefix caveat.

### Error Handling and Logging

Codes: `outcome_capture_partial`, `outcome_endpoint_missing`, `outcome_capture_limit`, `outcome_projection_invalid`. INFO domain/status counts, DEBUG safe row/byte counts. No owner contents, relationships, narratives, intervention parameters or content hashes in logs. Invalid capture does not rewrite successful objective history.

### Tests

`test_path_dependence_evidence.py`: factory-to-recorder real lifecycle with sink installed before restoration, exactly one F baseline and F+1 next, F=0 without duplicate initialization publication, missing-prefix status scoped to `[F,H]`, fresh-empty vs restored-missing channels, exact endpoint rather than nearest sample, admitted/dead owner coverage, disabled channels, gaps, early stop, extinction, recorder limits, capture-on/off trajectory equivalence, no analysis input reaches live cognition.

### Acceptance Criteria

Each domain has an independently auditable evidence/coverage record, and missing prefix/endpoint state can never become an observed zero.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_path_dependence_evidence.py tests/unit/test_cultural_metrics_end_to_end.py -q`

## Task 11: Register exact scalar outcomes for all requested domains

### Intent

Reuse existing algorithms without coercing arbitrary metrics into cultural `rows_json` or inventing authoritative norms/institutions.

### Implementation Steps

1. Implement a closed registry in `analysis/path_dependence_outcomes.py`. The initial selectors below are required; additional selector strings are rejected. Selector identity includes algorithm version, units, population, resource measure/dimension/representation, denominator, window, baseline policy, capture policy, code revision and numerical-library versions.
2. Use the following existing algorithms and exact output keys. Each row explicitly identifies subjective vs objective vs analytical evidence:

| Selector ID | Existing source / key | Eligibility and interpretation |
|---|---|---|
| `norms.active_beliefs` | `compute_emergent_social_norms` → `active_belief_count` | Aggregate owner norm-belief rows at endpoint; requires complete enabled-owner coverage; complete empty ledger gives known zero through adapter coverage, not absent-data substitution. |
| `norms.belief_persistence` | `compute_norm_persistence` → `belief_persistence` | At least two complete chronological readings; report interval count. |
| `relationships.mean_abs_delta` | `compute_relationship_stability` → `mean_abs_delta` | Directed relationship revisions and death caps over exact window; no intervals means unavailable, not stable-zero. |
| `institutions.persistent_candidates` | `compute_institution_candidates` + `compute_institutional_persistence` + metric encoder → `persistent_institution_like_count` | Detached candidate classifier only. Accept zero under full candidate-search evidence even if legacy document labels PARTIAL/ABSENT; encode explicit complete-empty-search witness. Without it, unknown. |
| `technology.living_retention` | `compute_cultural_technology_continuity` → overall `living_retention` measurement | F practical-knowledge baseline, exact endpoint, no arbitrary trait selection; disabled/unknown baseline not zero. |
| `narratives.endpoint_persistence` | `compute_cultural_narrative_survival` → overall `endpoint_persistence` measurement | F baseline, endpoint coverage, fixed declared narrative representation. No first-nonempty baseline. |
| `inequality.resource_gini` | `compute_resource_inequality` → `gini` | Full endpoint living population and explicit existing `ResourceMeasureId`; initial preset uses `inventory_count` (number of possessed portable items per living agent, known empty inventory = 0), never subjective value or a wealth score. |
| `inequality.resource_theil` | Same → `theil_t` | Same denominator and known holdings; empty living population unavailable. |
| `cooperation.applied_rate` | `compute_cooperation` → `coop_occurrence_rate` | Applied action evidence over `[start,end)`; denominator is the existing algorithm's action population, not inferred altruism. No opportunities means unavailable unless existing definition proves a zero. |

3. Compose existing public adapters in `path_dependence_evidence.py`, not copies: `norm_belief_rows_from_ledgers` for the `belief_rows` part of norm inputs; `institution_role_rows_from_events`, `institution_procedure_rows_from_events`, `institution_expectation_rows_from_channel_rows`, `institution_legitimacy_rows_from_norm_and_possession_rows`, `institution_succession_rows_from_events`, and `institution_continuity_rows_from_channel_rows` for the six institution lanes. Collect their actual inputs: committed events, existing teaching/channel rows, norm and possession-assessment rows, deaths and absolute generation labels. Missing inputs mark their lane unavailable, not an observed empty lane. An enabled concept ledger by itself does not establish complete six-lane analytical coverage. The complete-empty-search witness records requested lanes, complete input spans, observed owner counts, successful adapter/classifier execution and exact search window; only that evidence allows known-zero candidates. Use the current candidate/persistence algorithms and their identity construction; do not synthesize subject matches from a label.
4. For relationship rows, select the final known revision strictly before `start` as at most one predecessor per directed edge, then all revisions in `[start,end)`, ordered by existing `(tick,ordinal)` identity; exclude every later revision, cap deaths at the actual event tick and call `compute_relationship_stability(window_end=end-1)`. Predecessors establish the initial value but do not add pre-start revision deltas. Complete history with no in-window eligible delta returns unavailable for `mean_abs_delta`, not zero. Do not rely on a nonexistent `window_start` argument. For norm persistence build chronological documents at the predeclared cadence using the same population/coverage policy; do not infer persistent beliefs from an absent document. Translate half-open action windows to existing inclusive-window functions explicitly (`end-1`); boundary-state endpoints remain `end`. Resource rows use all registered living bodies at the exact endpoint and `inventory_count` with known empty inventories zero, preserving unknown holder coverage.
5. For cultural metrics, select exactly one overall measurement with a full matching key; duplicate/missing/trait-only/group-unanchored rows are errors or unknown as appropriate. Never average variant- or owner-specific rows to invent a population measure.
6. Emit `PathDependenceOutcomeRow` with selector key, finite value or null, availability, coverage, censoring, evidence references and safe reason code. Document per-selector zero eligibility. Do not change legacy `MetricDocument` or catalog count (136); these are comparison projections, not new metric families.

### Required Interfaces and Contracts

`compute_path_dependence_outcomes(input: PathDependenceEvidence, selectors, windows) -> tuple[PathDependenceOutcomeRow,...]`. Use `analysis.numerical` quantization and finite checking. No composite score, sign-as-moral-quality interpretation or predefined institution type.

### Requirement Evidence

User norms/relationships/institutions/technology/narratives/inequality/cooperation list; existing algorithm definitions; V3-37 incompatible measurement safeguards.

### Error Handling and Logging

`unknown_outcome_selector`, `outcome_basis_mismatch`, `outcome_nonfinite`, `outcome_duplicate_measurement`. Missing scientific data is typed unknown, not a thrown corruption error; invalid identities/nonfinite data fail. Log selector IDs, counts and status only.

### Tests

`test_path_dependence_outcomes.py`: hand-built evidence for each required selector; compare against direct calls to the existing calculators AND public composition adapters; snapshot-equivalent nonempty input vs real runner exports; six-lane institution coverage with each lane missing in turn; PARTIAL institutional zero with/without complete-search witness; complete-empty vs missing norm state; relationship predecessor plus first in-window revision, pre-start deltas excluded, post-end revisions excluded, same-tick ordinals, death caps and no eligible deltas; extinct population; incompatible resource measures; no cooperation actions; culture baseline gaps; end/end-1 off-by-one; no JSON survival curves coerced to scalars. Synthetic nonempty cultural fixtures verify correct retention math, while empty demonstration baselines remain honestly unavailable.

### Acceptance Criteria

All seven domains yield valid scalar measurements or explicit unknown/partial results with exact evidence bases; none is silently omitted or represented by a generic culture score.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_path_dependence_outcomes.py tests/unit/test_objective_metrics.py tests/unit/test_social_norm_metrics.py tests/unit/test_relationship_metrics.py tests/unit/test_institution_emergence.py -q`

## Task 12: Compare paired protocols across independent seed blocks

### Intent

Prevent pseudo-replication and distinguish repeated-seed evidence from an illustrative branch story.

### Implementation Steps

1. Extract the existing `_t_interval` math into public `student_t_interval` in `analysis/seed_block_statistics.py`. Preserve cultural comparator behavior/rounding/status through its wrapper and golden tests. Use SciPy already in dependencies; add no dependency.
2. `build_path_dependence_comparison(request)` accepts only verified completed branch artifacts and explicit spec contrasts. Pair on `(root parent scientific identity, F, seed ordinal, replicate, intervention-protocol contrast, outcome key, window)`; control/treatment must share source checkpoint digest and unchanged base config. Untouched controls must also be fork children, not the unbranched prefix parent.
3. For each eligible matched slot calculate `d = treatment - control` BEFORE aggregation. Within each numeric seed average replicate/duplicate-parent paired differences for a fixed contrast/F/window/selector into one block. Distinct F values and intervention schedules remain separate contrasts unless the spec explicitly defines one equally weighted pooled protocol before execution; initial v1 does not expose pooled contrasts. Duplicate numeric seeds never add n. If external ancestry declares shared roots across different seed labels, coalesce at that broader root or reject false independence.
4. Across the n independent block means, report equal-weight mean, sample SD, SE, `df=n-1`, and two-sided pointwise 95% Student-t interval `mean ± t(.975,df)*SD/sqrt(n)`. n=0: all summaries null; n=1: descriptive mean only, SD/SE/CI/df null; n≥2 constant blocks: SD/SE zero and degenerate interval. Quantize only output, not intermediate paired/block arithmetic. Include raw branch count, paired slot count, independent block count and each block's membership.
5. Include requested/eligible/ineligible/failed/missing/censored counts by arm and per-selector exclusion reasons. Primary estimator uses all assigned arms with observed eligible outcomes, not applied-only actions. Describe it as a complete-pair estimate conditional on observed outcomes; explicitly warn about informative attrition and survivor bias. Never fill missing values with zero, use independent-arm fallback, or count agents/ticks/edges/generations as replicates.
   A planned slot has exactly one predeclared child scientific RunId. A failed/partial durable child remains missing; reject artifacts attempting to replace it with a different RunId even when parent/arm/seed labels match. Do not select a successful retry or silently add its result to the original block. A separately declared ensemble is a different protocol input, not an attempt of this one.
6. Compare full outcome keys, source revisions, provider bases and all channel manifests. Initial eligible provider is deterministic fake only. Unknown provider/source/ancestry or incompatible bases are descriptive-only or rejected for corruption. Mixed stream alignment is allowed but explicitly qualified; it is not advertised as common-random-number isolation.
7. Every document includes `causal_claim: false`, `single_run_is_illustrative: true`, interval method/assumptions, arm assignment policy and `multiplicity_policy: pointwise_exploratory_no_familywise_claim`. No p-values, winner ranking or automatic significance labels in v1. Seven domains/multiple windows/schedules do not support a familywise claim from marginal CIs. Large n does not automatically convert these simulation contrasts into real-world causal evidence.

### Required Interfaces and Contracts

Comparison is detached and pure. Source lineage verified in experiments is mandatory; analysis never opens filesystem paths or imports persistence. Named compound protocols have protocol-level estimates only. CI validity assumes independent seed blocks and sufficiently well-behaved block-mean sampling; report low n and heavy-tailed/sparse outcomes as interpretation limits.

### Requirement Evidence

User explicitly forbids single-run causal claims and requests repeated-seed/branch statistics; existing cultural numerical policy is refined for branch lineage rather than reused as an arbitrary cultural decoder.

### Error Handling and Logging

`comparison_lineage_mismatch`, `comparison_basis_mismatch`, `comparison_duplicate_branch`, `insufficient_independent_seeds`, `unverified_source`. INFO counts/method; DEBUG exclusions by reason; no payloads or per-agent data. Incompatibility never silently drops an entire arm.

### Tests

`test_path_dependence_comparison.py`: hand-computed paired means/t intervals; arithmetic pairing before blocking; unequal replicas; duplicate seeds; several F values not pooled; singleton, empty and constant samples; reordered inputs byte-identical; missing one arm; failed durable child excluded with denominator retained; substituted new-RunId result rejected; all rejected treatments retained by assignment; partial endpoints; institutional witnessed zero; shared parent across apparent seeds; later-pair alignment mismatch; wrong checkpoint/config/provider; no causal labels; pointwise multiplicity warning. Keep existing cultural comparison goldens unchanged.

### Acceptance Criteria

Hundreds of branches under one numeric seed still produce n=1 and no interval; two or more genuinely independent seed blocks produce the specified paired interval with auditable membership.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_path_dependence_comparison.py tests/unit/test_cultural_metric_comparison.py -q`

## Phase Risks and Mitigations

- Sparse institutions/cultural baselines create many unknown outcomes: expose exclusions and do not manufacture zeros or seed inventories.
- Multiple contrasts encourage cherry-picking: seal selectors/windows/schedules before execution and label all intervals pointwise exploratory.

## Phase Completion Checklist

- Tasks 10–12 pass; every requested domain is covered and independence rules are tested.
- Only `index.md` task checkboxes record progress.
