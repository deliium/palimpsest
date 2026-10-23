# Phase 4: Catalog, artifacts and repeated-run inference

Plan: [index.md](index.md)  
Tasks: 10–12  
Depends on: Tasks 1–9

## Objective

Integrate six additive metric families and preserve evidence artifacts; provide genuine repeated-seed confidence intervals without changing legacy percentile summaries.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|---|---|---|
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT=130`, `MetricFamilyId`, `validate_metric_catalog` | Closed catalog and explicit formula/denominator contracts. |
| `src/analysis/metric_service.py` | `MetricComputationInputs`, `assemble_metric_documents`, `documents_compatible` | Optional evidence dispatch and document compatibility. |
| `src/experiments/coordinator.py` | `ExperimentArmResult`, coordinator execution | Arm metadata and actual seed/replicate identity. |
| `src/experiments/matrix_runner.py` | `run_one_assignment`, `MatrixBatchDependencies` | Matrix composition, metrics persistence and valid-completion resume. |
| `src/experiments/generational_execution.py` | `execute_generational_assignment` | Separate archived generational execution path must also capture evidence. |
| `src/experiments/matrix_manifest.py` | `write_metric_documents`, `read_metric_documents`, `has_valid_completion_fingerprints` | New artifacts must bind to actual completed cells. |
| `src/analysis/matrix_metric_summary.py` | `MatrixMetricCellRef`, `build_matrix_metric_summary` | Current seed field is unused; percentile range is not a CI. |
| `src/analysis/distribution_summary.py` | `summarize_distribution`, `proportion_confidence_interval` | Existing distribution and exact binomial methods must retain meaning. |
| `src/experiments/matrix_expand.py` | `expand_matrix` | Cells retain seed ordinal, replicate index and factor/config identity. |
| `src/simulation/generational_seeds.py` | `build_generational_seed_manifest`, `SeedChannelLineage` | Some sampled channels use durable run identity; shared numeric seed/stochastic identity does not prove all random streams are shared. |
| `src/experiments/generational_artifacts.py` | `_load_json_object`, `_assert_safe_tree`, `_atomic_write` | Duplicate-aware decoding, symlink rejection and idempotent/conflict-safe writes are existing artifact patterns, not optional hardening. |

## Files to Change

Modify `src/analysis/specifications.py`, `src/analysis/metric_service.py`, `src/analysis/__init__.py`, `src/experiments/collectors.py`, `src/experiments/coordinator.py`, `src/experiments/matrix_runner.py`, `src/experiments/generational_execution.py`, `src/experiments/metric_collection.py` and explicit experiment facade exports. Create `src/analysis/cultural_evolution_metrics.py`, `src/analysis/cultural_metric_comparison.py`, `src/experiments/cultural_metric_artifacts.py`, `src/experiments/cultural_metric_comparison.py`; reuse/extend `src/experiments/cultural_evidence_serialization.py` created in Task 3. Create tests named below. Extend manifest interfaces/adapters only with the new sibling artifact methods, preserving existing documents.

## Task 10: Register six versioned metric families

### Intent

Make the new panel discoverable and serializable without widening the shared metric document schema.

### Implementation Steps

1. Add six `MetricFamilyId` entries: `cultural_trait_dynamics`, `cultural_evolution_transmission`, `cultural_population_structure`, `cultural_narrative_survival`, `cultural_vocabulary_differentiation`, `cultural_technology_continuity`. Each algorithm version is `1`; catalog count becomes 136. Keep `metric-catalog-v1` and legacy algorithms accepted, following existing additive-catalog convention.
2. Add specifications defining source stages, eligible populations, baseline cohort, numerators/denominators, deceased policy, complete-empty/missing semantics, gaps and formulas exactly as Tasks 4–9 specify. Subjective inventories use `BELIEF_REVISION_TESTIMONY`; objective population/kinship/record facts additionally use `OBJECTIVE_EVENT_STATE`. Do not label beliefs objective or add new evidence stages.
3. Introduce `assemble_cultural_evolution_documents(inputs)` in `analysis.cultural_evolution_metrics`. All six families use a shared envelope: scalar values `policy_version`, `window_start`, `window_end`, `measurement_count`, `rows_json`, `evidence_manifest_digest`. The digest is supplied from Task 3's normalized evidence codec, never computed from metric documents. `rows_json` is a canonical JSON array of Task 1's exact-key measurement objects, sorted by their complete scientific selector tuple (null selectors sort before strings; group IDs are sorted tuples), compact separators, sorted keys, no NaN and quantized numeric output. Validate a row's formula/units/denominator combination against an explicit registry before encoding. No nested containers are put directly into `MetricDocument.values`, and no arbitrary JSON numeric field is a comparison candidate.
4. A document may be PARTIAL while particular measurement rows are complete. Derive document availability/coverage from eligible underlying inventories/opportunities, not from nonnull output count. Each row retains its own coverage, counts and reasons. With no capture input omit these families entirely. With explicit attempted but failed capture emit applicable unknown/partial documents; do not fabricate a full empty panel.
5. Add optional `cultural_evolution: CulturalEvolutionInputs | None = None` to `MetricComputationInputs`. Route it through `experiments.metric_collection` and collector dispatch. Preserve all previous inputs/outputs when absent. Use public facade exports for cross-package imports; analysis never imports experiments or cognition implementations.
6. Update catalog-cardinality assertions only: locate exact `130`/family-count assertions in relevant `tests/unit/test_*metrics.py`, `test_metric_specifications.py`, `test_generational_cohort_metrics.py`, and catalog consumers under `tests/architecture`. Do not bulk-replace unrelated numbers or historical documentation.

### Required Interfaces and Contracts

The six-document panel is not a seventh aggregate culture score. The evidence manifest digest binds each document to its source sidecar. Canonical structured detail stays inside a versioned JSON string; the existing metric codec and schema version remain unchanged. No new HTTP route, observer semantic type or automatic subjective debug exposure.

### Requirement Evidence

User requests separate measures/provenance; architecture Versioned Extension Contract requires additive compatibility. Verify capture-none, complete capture, partial capture, and independent channel combinations.

### Error Handling and Logging

Invalid family/measurement structure fails with a safe code. Logs expose document/measurement counts and availability only, never `rows_json` or evidence digests.

### Tests

Create `tests/unit/test_cultural_evolution_metric_service.py`: all six catalog specs, no capture omission, mixed enabled channels, scalar-only codec round-trip, canonical permutation, Task 3 evidence-digest binding before any file write, measurement-level availability in partial document, exact row-schema/unit/denominator validation and legacy default output equivalence. Extend catalog tests to 136. A metric can be assembled wholly in memory without Task 11's store code or a placeholder digest.

### Acceptance Criteria and Verification

Catalog validates at 136; all old family algorithms and codec round-trips remain unchanged. Run `uv run pytest tests/unit/test_cultural_evolution_metric_service.py tests/unit/test_metric_specifications.py --cov=analysis --cov=experiments --cov-report=term`.

## Task 11: Persist and propagate agent-level evidence artifacts

### Intent

Provenance must remain inspectable after the runner and in-memory ledgers are gone.

### Implementation Steps

1. Introduce composition setting `CulturalCaptureOptions(enabled=False, max_frames=10000, max_rows=1000000, analysis_window=CulturalAnalysisWindow())` in experiments. Pass it explicitly through coordinator execution, `MatrixBatchDependencies` and `GenerationalExecutionContext`; never add it to `runner-config-v55` or generational execution recipes. Install a fresh recorder per run, including both ordinary and archived generational matrix execution. Merge runner-owned capture status before leaving each runner context. Preserve requested/resolved window identity even when the requested endpoint is missing.
2. Add optional `cultural_evolution_evidence` to `ExperimentArmResult`, a detached experiment-owned capture bundle. Carry it through every arm reconstruction before and after `collect_for_experiment`; do not add it to `SimulationRunnerResult` or its codec. Collectors build Task 3 inputs after the run and attach them to metric computation.
3. Reuse Task 3's strict `cultural-evolution-evidence-v1` codec and digest; do not create another serializer or derive evidence identity from computed metric values. Persist normalized rows/pointers/coverage, not raw ledgers. Preserve capture failure and window metadata. No text labels, raw fingerprints, prompts or message bodies. Implement filesystem operations in `experiments.cultural_metric_artifacts`, separate from pure codec validation.
4. Add matrix sidecars `cells/<cell_id>.cultural-evidence.json` and `cells/<cell_id>.cultural-metrics.json`. The latter is `cultural-cell-metrics-v1`: cell/matrix/config fingerprints, run ID, capture-policy identity, evidence digest, and six ordinary encoded MetricDocuments. It is the bound envelope consumed by new comparison code; existing `.metrics.json` remains unchanged and can continue containing catalog documents.
5. In `experiments.cultural_metric_artifacts`, atomically write evidence first and bound metrics second, then let existing cell completion proceed. The capture-enabled branch must run BEFORE `store.write_completion`, outside the legacy best-effort `matrix_metric_sidecar_skip` exception handler. Validate matrix/cell/config/run identities, source revision, evidence digest, capture caps and requested analysis window. A complete, well-formed artifact may truthfully report partial/failed capture; scientific unavailability is not an I/O corruption. Never silently ignore a requested artifact write failure.
6. For standalone coordinator callers expose canonical bytes via `encode_cultural_evolution_evidence` and `encode_cultural_cell_metrics` where a matrix cell exists; caller owns the output directory. For archived generational cells write sibling cultural files in the matrix cell store; do not silently widen sealed generational manifests or immutable archive schemas.
7. Truncation/failure/gaps persist through artifact round-trip. Matrix resume reuses verified matching sidecars, including truthful partial/failed-capture results, rather than attempting to improve their coverage by rerunning objective history. A retry may create a fresh recorder only when existing retry rules permit objective re-execution and no sealed/valid objective result forbids it. Existing cultural files must still match byte-for-byte or fail with artifact conflict; retry ownership does not authorize overwriting divergent evidence. No partial captured history is reconstructed from checkpoints or invented for adopted runs.
8. Apply the completion decision table below at ALL current paths: initial `already_valid` scan, worker `has_valid_completion`, verified generational archive adoption, and fresh execution. Centralize the cultural validator to avoid four divergent checks. Matching objective completion plus missing/mismatched cultural evidence is a requested-research failure, never authorization to rerun or overwrite objective completion. Preflight existing completed cells before dispatching pending work. On newly executed artifact failure with an already sealed generational archive, record a safe cell research error and leave the archive intact; later archive adoption cannot pretend it can recover the lost capture. Require a fresh manifest/run identity for full recapture.
9. Harden all new envelope and embedded measurement/evidence JSON decoders: reject duplicate keys at every nesting level, NaN/Infinity, unknown keys/versions, invalid UTF-8, excessive nesting and oversized bytes before deserialization. Defaults: evidence file <=64 MiB, cell metrics <=64 MiB, comparison <=64 MiB, nested `rows_json` <=16 MiB and JSON depth <=32. Before `json.loads`, check byte size and use a bounded lexical nesting scan that respects quoted strings/escapes; then use duplicate-aware `object_pairs_hook` and rejected nonfinite constants plus exact typed validation. Apply the same checks when decoding the embedded JSON string. An oversized complete payload fails the artifact operation; never silently truncate a serialized JSON string. Keep limits explicit in codec constants and tests.
10. Validate every cell filename segment; reject symlinks in the root/cells path and target files before reads/writes, verify resolved containment under the manifest root, and use same-directory temporary files plus atomic replacement. Reuse existing public artifact helpers if available; otherwise implement equivalent local helpers without importing another module's private functions. Identical content is idempotent; a different complete evidence/metric pair is a conflict, not an overwrite. To recover an interrupted two-file write, accept the already written evidence only if it exactly matches the intended digest and write the missing metrics; never delete a divergent or user-owned artifact.

### Required Interfaces and Contracts

An in-memory metric detail evidence ID resolves to a sidecar entry with owner/local source identity and revision. New sidecars are opt-in, separate from objective replay and durable subjective restart. Readers enforce exact key sets, duplicate awareness, explicit size/depth limits and safe paths under the store root. Failure diagnostics do not reveal offending duplicate keys or payload fragments. No database migration or archive manifest version change.

### Completion Decision Table

| Objective state / requested capture | Cultural state | Required action |
|---|---|---|
| Capture off, any existing valid completion/adoption | Any/none | Preserve legacy behavior; do not require/read new cultural artifacts. |
| Valid completion or adoptable archive, capture on | Verified matching pair | Skip/adopt objective work and reuse exact cultural bytes. |
| Valid completion, capture on | Missing pair or cap/window mismatch | Fail capture-required preflight with `cultural_capture_missing` or `cultural_capture_policy_mismatch`; preserve objective completion; no rerun. |
| Adoptable sealed archive without cell completion, capture on | Missing pair | Do not create a capture-valid cell completion or rerun the sealed archive; record requested-research failure. |
| Any completed/adoptable objective state, capture on | Corrupt/conflicting pair | Fail verification with `cultural_artifact_invalid`; preserve existing history and artifacts. |
| Fresh successful execution, capture on | Matching partial/failed-capture evidence and valid metric pair | Write truthful pair, then objective cell completion; metrics remain partial/unknown as appropriate. |
| Fresh successful execution, capture on | File/encoding/size failure | No new capture-valid completion; record research failure. Preserve any already sealed archive; exclude cell from cultural comparison. |
| Failed objective execution | Any captured evidence | No successful cell completion or cultural comparison eligibility. |

### Requirement Evidence

User: provenance to underlying agent evidence; architecture: analytical evidence outside objective fold and append-only authority. Verify old completion/no capture, matching capture, mismatched policy, missing evidence and failed-write cases.

### Error Handling and Logging

Artifact corruption or write failure fails the research artifact operation/cell completion, not an already committed world tick. Do not catch and silently mark a corrupted artifact valid. Log filenames through safe cell IDs and reason codes only; never payloads or fingerprint surrogates.

### Tests

Create `tests/unit/test_cultural_metric_artifacts.py`: round-trip, provenance resolution, digest mismatch, unknown schema/fields, partial capture, manifest/config/run mismatch, idempotent writes, resume reuse, legacy completed cell missing capture, truncated artifacts and cap/window mismatch. Exercise every completion path in the table, including worker skip and sealed-archive adoption, with a runner spy proving no forbidden rerun. Inject failure between evidence/metrics/completion writes and after archive completion. Test duplicate keys in outer/nested JSON, NaN, excessive depth/bytes, symlinked roots/cells/files, path traversal, conflicting artifacts and interrupted-write idempotency. Extend existing matrix-sidecar tests without changing v1 golden bytes.

### Acceptance Criteria and Verification

Saved metrics retain resolvable evidence after releasing runtime objects, and no stale cell evidence is compared. Run `uv run pytest tests/unit/test_cultural_metric_artifacts.py tests/unit/test_experiment_matrix_metric_sidecars.py --cov=experiments --cov-report=term`.

## Task 12: Implement repeated-seed means, confidence intervals and paired contrasts

### Intent

Distinguish uncertainty across repeated simulations from within-run census variation and empirical percentile ranges.

### Implementation Steps

1. Create pure `build_cultural_metric_comparison(cells, *, comparisons=(), confidence=0.95)` in analysis. `CulturalComparisonCell` retains cell/condition ID, seed value, seed ordinal, replicate index, stochastic identity, actual channel lineage, recording/provider comparability identity, factor levels, config/source fingerprints, validated documents and evidence digest. Outer loader in experiments verifies Task 11 bound artifacts and valid completion fingerprints before constructing these inputs. For v55 use public `build_generational_seed_manifest` and its actual `SeedChannelLineage`; for other versions report only evidenced identities from their configured stream/provider contracts and mark unproven alignment unknown. Never infer durable-run-ID stream equality from a shared stochastic identity.
2. Decode `rows_json` duplicate-aware and extract Task 1's exact typed `CulturalMeasurement` rows, not arbitrary numeric fields or arbitrary JSON. Match on family/algorithm, policy, stable formula `measurement_id`, dimension/representation, scope/partition/group selectors, population basis, exact requested/resolved window, units and `denominator_code`; never match on unique row IDs. Include code revision and scientific-library versions in the compatibility identity; different known/unknown revisions or different library-version maps cannot silently pool. Run-local trait/lineage/group IDs are excluded from cross-run pooling unless the requested group selector is a stable declared region/stratum; never join unrelated traits by local IDs.
3. Produce comparisons for population-summary measurements: persistence shares, richness/diversity, edge fidelity/mutation/classification shares, vocabulary/group divergence and technology/narrative retention/loss. Per-trait prevalence remains an auditable within-run series; do not average different trait identities into a prevalence score. Match requested endpoints exactly, never nearest tick. Different horizons/window policies must produce separate compatibility groups or an explicit incompatibility error for a requested contrast.
4. Use only row-level complete, finite values by default; exclude unavailable/partial rows with cell IDs and reason counts. A PARTIAL document may contain eligible complete rows. Missing sidecars and zero opportunities are excluded, never zero-imputed. Reject duplicate cell IDs, duplicate condition/ordinal/replicate slots, algorithm/policy/units mismatch in a requested comparison and nonfinite values.
5. Collapse all repeated seed ordinals/replicates sharing the same numeric seed within a condition into one seed-block mean before inference. Report raw eligible cell count, duplicate/repeat count, block membership and independent seed-block count. Do not derive new simulation seeds or pretend replicas of one seed create independent samples. Provider modes/recording identities must be comparable; unrecorded nondeterministic providers may be summarized descriptively but receive no inferential CI (`uncontrolled_provider_variation`).
6. For n distinct seed-block values, compute arithmetic mean and sample SD (`ddof=1`). For n>=2 use two-sided Student-t mean CI: mean ± `scipy.stats.t.ppf((1+confidence)/2, n-1) * sd/sqrt(n)`. Method `student_t_seed_block_mean`; record confidence, df, n, assumptions and library versions. No RNG/bootstrap or new dependency. For n=1 mean is present, SD/CI null with `insufficient_independent_seeds`; n=0 all null. A zero-SD n>=2 CI is degenerate at the mean. Do not clip a t interval to [0,1].
7. Explicit control/treatment condition IDs select paired seed-block contrasts. In v1 a requested contrast must differ in exactly ONE declared matrix factor level; all other factor selections must match. Verify this from `MatrixCell.factor_levels`, then re-materialize both expected conditions through the existing `expand_matrix`/`apply_factor_levels` path from the same matrix base and compare complete canonical config fingerprints. This replaces an unspecified hand-written field whitelist: only changes actually produced by that selected registered applicator are allowed, including its required coupled fields. Reject zero/multiple-factor contrasts with `comparison_factor_mismatch`; do not strip arbitrary runner fields to make configs match. Existing generational comparability checks remain in force for BM-derived inputs. Pair eligible cells by `(seed_ordinal, replicate_index)` within that same matrix, additionally checking equal numeric seed and compatible provider/design identities.
8. Compute treatment-minus-control per complete pair, then average all pair differences within numeric seed blocks, and apply the same t interval to these block deltas. Report complete pair IDs, unmatched cells, exclusions and effective seed count. Missing one arm excludes that pair; do not substitute independent-arm means. Multiple conditions sharing a role require explicit IDs, not automatic role-based cross products.
9. Emit canonical sibling `cultural-metric-comparison-v1`: input matrix fingerprint, confidence/method, per-condition summaries, explicitly requested contrasts, exact compatibility selectors, block memberships, contributing cell/document/evidence references and exclusions. Do not change `matrix-metric-summary-v1`, `matrix-aggregate-v1`, or label their p05/p95 range a CI. No p-values, composite culture score, multiple-testing claims or automatic causal claims.
10. Report per contrast `pairing_basis=seed_ordinal_replicate` and `shared_stream_status=shared|mixed|unknown`, with channel-level alignment metadata. A sampled channel scoped to different durable run IDs is not shared even with equal seed; reserved/ignored or absent channels do not create an alignment violation. `mixed` still permits a descriptive paired seed-block difference and its seed-block t interval when the v1 controlled-provider/design criteria hold; pairing is a blocking convention, not a promise of common random numbers. For provider eligibility accept deterministic fake or validated immutable replay usage; live/record/cache without that proof and untracked custom factories remain descriptive-only. Do not call RECORD/CACHE deterministic merely because a recording directory exists. No stream, seed, run ID or simulation config is modified to improve pairing.

### Required Interfaces and Contracts

CI unit is an independently sampled seed block, not an agent, tick, acquisition edge or trait. Within-run frequencies are censuses over observed inventories; they get no binomial CI by default. Existing exact binomial helper remains available for its original Bernoulli estimands only. Confidence must be finite and strictly between 0 and 1. Canonical output uses sorted deterministic reduction and 12-place quantization at export only.

### Requirement Evidence

User: confidence intervals/repeated-run comparison; source contracts: duplicate seeds allowed and replicate indices do not derive fresh random seeds. Test identity, pairing, availability and n=0/1/2+ combinations.

### Error Handling and Logging

Use stable codes `comparison_incompatible`, `duplicate_comparison_cell`, `invalid_confidence`, `uncontrolled_provider_variation`; expose incomplete-pair exclusions in result, not exception prose. Metadata logs include included/excluded cell, block and pair counts only.

### Tests

Create `tests/unit/test_cultural_metric_comparison.py`: hand-computed [1,2,3] mean/SD/t interval; one/zero seeds; constant values; duplicate seed ordinals and deterministic replicas not inflating n; shuffled cells; paired deltas differing from unpaired means; missing arms; many conditions per role; algorithm/units/denominator/window/code/library mismatches; nonfinite and boolean rejection; complete rows in partial documents; live/record/cache and custom-factory provider proof; 95% confidence validated against SciPy reference. Test a valid one-factor rematerialized pair including coupled fields, forbidden extra config mutation, multi-axis rejection, shared stochastic identity with sampled run-ID-scoped channels, and absent/reserved channel alignment. Confirm pairing reports mixed/unknown rather than claiming common random numbers. No significance/coverage promises from one small fixture.

### Acceptance Criteria and Verification

New summaries contain actual mean confidence intervals and trace every statistical unit to completed cells and evidence. Run `uv run pytest tests/unit/test_cultural_metric_comparison.py tests/unit/test_matrix_metric_summary.py tests/unit/test_distribution_summary.py --cov=analysis --cov=experiments --cov-report=term`; v1 summary bytes remain unchanged.

## Phase Risks and Mitigations

- Pseudoreplication: numeric seed blocking and explicit effective n, with no inference over agents/ticks.
- Incompatible scientific designs: explicit factor selection and schema/policy/window matching.
- Proliferating artifact schemas: sibling additive envelopes only; no sealed legacy schema widening.

## Phase Completion Checklist

Tasks 10–12 satisfy all acceptance criteria; update only `index.md` task checkboxes.
