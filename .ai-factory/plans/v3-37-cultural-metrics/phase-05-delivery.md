# Phase 5: CLI, representative end-to-end gates and documentation

Plan: [index.md](index.md)  
Tasks: 13–15  
Depends on: Tasks 1–12

## Objective

Expose opt-in reproducible capture/comparison and verify the complete data path on real project scenarios, then document interpretation and limitations.

## Current-Code Evidence

| Path | Symbols | Why it matters |
|---|---|---|
| `src/research_runner/cli.py` | `build_parser`, `_cmd_run`, `_cmd_resume`, `_cmd_aggregate` | Existing matrix CLI owns filesystem composition, not HTTP. |
| `src/experiments/generational_comparison_scenario.py` | `generational_comparison_scenario` | Real paired record/lifespan/migration/teaching/memory treatments. |
| `src/experiments/generational_comparison_base.py` | `generational_comparison_base`, `assert_comparable_generational_pair` | Existing v55 experiment seam, minimum horizon 8. |
| `tests/fixtures/matrices/v2-benchmark-suite.json` | existing matrix artifact | Representative legacy matrix compatibility check. |
| `tests/unit/test_research_runner_cli.py` | `_write_matrix`, `test_cli_run_and_status` | Network-free CLI fixture pattern. |
| `docs/experiments.md` | matrix CLI and generational-comparison sections | Currently correctly states no paired CI support; add new opt-in path without rewriting legacy meaning. |

## Files to Change

Modify `src/research_runner/cli.py`, `src/research_runner/composition.py` where dependency construction belongs, `tests/unit/test_research_runner_cli.py`, `docs/experiments.md`, `README.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`; create `docs/cultural-evolution-metrics.md`, `tests/unit/test_cultural_metrics_end_to_end.py`, `tests/fixtures/cultural_metrics/known-lineage-v1.json` and `tests/fixtures/matrices/v3-cultural-metrics.json`. Add a focused architecture test in `tests/architecture/test_cultural_metrics_boundaries.py`.

## Task 13: Expose opt-in capture and comparisons through the matrix CLI

### Intent

Researchers can request new evidence and uncertainty artifacts without changing simulation configuration versions.

### Implementation Steps

1. Add run/resume flags `--cultural-metrics`, `--cultural-max-frames` (default 10000), `--cultural-max-rows` (default 1000000), `--cultural-baseline-boundary` (default 0), and `--cultural-end-boundary` (default omitted, resolving to the actual last finalized boundary). Validate positive exact integer caps, nonnegative exact baseline, explicit end greater than baseline, and requested boundaries not greater than the configured tick horizon. Reject explicitly supplied cultural options without capture enabled. Do not shift a missing/empty baseline or an endpoint not reached because of early stop. Pass `CulturalCaptureOptions` and its `CulturalAnalysisWindow` via dependency composition to both normal and generational execution; persist requested/resolved bounds in the evidence identity.
2. Add aggregate flags `--cultural-summary`, repeatable `--cultural-contrast CONTROL:TREATMENT`, and `--confidence` (default 0.95). Contrasts/confidence explicitly supplied require `--cultural-summary`. Validate unique distinct known condition IDs and the exactly-one-declared-factor contrast contract from Task 12; never select all role combinations implicitly or accept hidden extra config differences. Parse a single colon delimiter, rejecting malformed/empty condition IDs. Aggregate consumes precomputed windowed measurements; it does not reinterpret the baseline from available artifacts.
3. When requested, write `cultural-metric-comparison.json` atomically from the Task 12 loader/builder. Existing `aggregate.json` and optional `metric-summary.json` continue their original schemas. Standalone aggregate reads verified cell artifacts, not the empty `arm_results=()` list.
4. A requested summary with no cultural artifacts writes an explicit empty/unknown summary with exclusion counts and safe warning; malformed/stale artifacts produce nonzero failure and no replacement of a prior valid summary. Requested contrasts missing an arm yield an insufficient-evidence contrast, not invented zeros. Fail early on configuration/design mismatch.
5. Document and test resume: opt-in capture cannot be backfilled for completed cells without evidence. Apply Task 11's validator to initial skip, worker skip, archive adoption and fresh completion. Fail capture-required preflight for missing/mismatched cap/window identity before dispatching pending work; preserve existing objective completions. A sealed archive with lost cultural capture is not permission for a rerun. Require a new manifest/run identity for full cultural data, and reuse matching verified artifacts byte-for-byte.

### Required Interfaces and Contracts

No new environment variables, provider construction, API endpoints or client build changes. CLI exit codes follow existing argparse/validation conventions. Paths remain under the requested manifest root. Flags do not alter runner JSON or factor expansion identity.

### Requirement Evidence

User repeated-run comparison/CI; architecture research_runner no-HTTP rule. Supported combinations: legacy run/aggregate, capture enabled, generational capture enabled, summary only, summary with explicit contrasts, resume with absent/mismatched capture.

### Error Handling and Logging

Use safe validation codes, no raw input JSON/exception bodies. INFO reports output type/counts; DEBUG reports inclusion/exclusion counts; WARN reports insufficient evidence or capture gaps.

### Tests

Extend CLI tests for parser combinations, explicit-option-without-capture rejection, bad confidence/caps/windows, nonzero baseline, early stop before explicit end, unknown/self/multifactor contrast, independent normal/generational composition, summary loading completed sidecars, missing/stale/corrupt artifacts, cap/window mismatch on resume, sealed-archive reuse rejection and absence of new artifacts without opt-in. Assert rejected completed-cell capture does not call a runner factory or mutate its objective completion. Use monkeypatch only at expensive execution boundaries; retain one real execution in Task 14.

### Acceptance Criteria and Verification

Both old and new CLI workflows work and new statistical output is correctly labeled. Run `uv run pytest tests/unit/test_research_runner_cli.py tests/unit/test_cultural_metric_artifacts.py --cov=research_runner --cov=experiments --cov-report=term` and `uv run palimpsest-matrix aggregate --help`.

## Task 14: Add hand-calculated and real-scenario end-to-end gates

### Intent

Test numerical truth on controlled evidence and integration on real scenarios without scripting cultural emergence into production.

### Implementation Steps

1. Commit `tests/fixtures/cultural_metrics/known-lineage-v1.json`, a strict normalized evidence fixture with three owners, at least three complete boundaries, two generations, explicit unrelated teacher and parent links, a mutation edge, disappearing/reappearing traits, branching narrative, vocabulary split and living-loss-with-record technology case. Include expected hand-calculated measurements outside production inputs in the test module. It must exercise all 14 user-requested measurement areas. Include initially empty inventories followed by a predefined nonzero analysis baseline, plus a fixed-pair convergence counterexample; test that selecting boundary 0 instead produces null empty-baseline cohort retention, not automatic rebasing.
2. Build `tests/fixtures/matrices/v3-cultural-metrics.json` from the existing generational comparison base/preset applicators, with at least three distinct seeds (23, 24, 25), two explicitly paired record-availability conditions and the existing minimum 8-tick horizon. Preserve the actual v55 keyset and shared founder/world/generation identities; use real scenario configurations, not test-only semantic world events.
3. Run the fixture through real CLI execution with capture, metric collection, canonical evidence/metric sidecars and standalone aggregate/contrast. Natural behavior need not express all cultural phenomena: assert correct observed/unknown/absent results and provenance, not nonzero fidelity or institutional emergence. The known-lineage fixture establishes numeric coverage separately.
4. Repeat with the same seed matrix in a fresh temporary root and compare canonical metric/evidence/comparison artifacts after excluding only documented run-root-independent metadata. Run IDs generated from the same assignment must match; no wall-clock fields may enter cultural artifacts.
5. Execute an existing committed `tests/fixtures/matrices/v2-benchmark-suite.json` decode/expansion path and the existing V1/scientific-invariant tests with capture disabled. Verify default runner v4/v2 writes, feature-selected v55/v3 writes, 43 commands, 73 observer semantics, replay-v22/codec-v20 accepted taxonomy and migration head unchanged. Do not require every run to write the latest replay pair.
6. Add architecture tests prohibiting analysis/experiments imports in the new simulation export module, world mutation imports in new analysis modules and new culture-score/authority shortcuts. Existing import-linter remains the main package-boundary gate. Assert capture evidence never appears in cognition perspectives, prompts, world events, observer frames or default HTTP debug schemas.
7. Drive actual crash-hook plus runtime checkpoint export/restore and pending-finalization recovery, with entrants admitted at the recovery boundary. Compare available contemporaneous frames to the equivalent uninterrupted run, and assert incomplete history remains explicitly censored. Never use a hand-built restored snapshot as a substitute for the public restore path. Also exercise production matrix skip/adoption paths with missing/corrupt cultural sidecars and an artifact-write fault after sealed archive completion, proving no forbidden objective rerun and no cultural-valid completion.

### Required Interfaces and Contracts

Tests use network-free deterministic providers and temporary artifact roots. No SQL/Docker requirement for the default suite. Do not claim exact external LLM reproducibility without recorded outputs. Reproducibility is sorted/quantized output per existing numerical policy, not arbitrary-platform BLAS identity.

### Requirement Evidence

Every user measurement maps to a controlled fixture assertion; the real BM-derived artifact exercises actual composition and compatibility. Confidence tests verify independent seed count and hand-calculated CI, not an empirical coverage guarantee from three seeds.

### Error Handling and Logging

Add caplog checks with canary labels/fingerprints/messages proving payloads are absent from success and failure logs. Fixture validation failures must reveal safe codes only.

### Tests and Verification

Run `uv run pytest tests/unit/test_cultural_metrics_end_to_end.py tests/architecture/test_cultural_metrics_boundaries.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py --cov=analysis --cov=experiments --cov=simulation --cov-report=term`.

Then run `uv run pytest --cov --cov-report=term`, `uv run ruff check src tests`, `uv run ruff format --check src tests`, `uv run mypy`, and `uv run lint-imports`. Report pre-existing failures separately; do not weaken exclusions, disable coverage or edit unrelated code to conceal them.

### Acceptance Criteria

All 14 areas have formula/provenance assertions; actual matrix execution produces replay-safe auditable artifacts and genuine seed-block CIs when sufficient complete measurements exist. Default and legacy gates pass unchanged apart from explicit catalog-count assertions.

## Task 15: Complete mandatory documentation and implementation handoff

### Intent

Make the metrics scientifically interpretable and their limits difficult to overlook.

### Implementation Steps

1. Invoke `$aif-docs` as the mandatory implementation documentation checkpoint. Create `docs/cultural-evolution-metrics.md` covering all six families and 14 requested areas: exact estimands, dimensions, formulas, baseline cohorts, attribution, uncertainty, censoring, complete-empty semantics and agent-level provenance resolution.
2. Document `ledger_carriage` versus psychological possession, local/global extinction versus archival survival, intergenerational versus kin-vertical, exact representational fidelity versus truth, vocabulary versus semantics, and technology knowledge versus performability. Include a three-seed CI example and state t assumptions, effective sample size, duplicate-seed blocking, controlled-provider limitations and no multiple-testing/significance claims. Distinguish paired seed blocking from common-random-number alignment, and explain sampled run-ID-scoped channels. Explain exact baseline/endpoint selection, empty-baseline null shares and fixed-pair convergence denominators.
3. Update `docs/experiments.md` with capture/summary/one-factor-contrast CLI examples (including an explicit nonzero baseline), all three new artifact schema names, byte/depth limits, opt-in resume restrictions and the explicit fact that legacy p05/p95 remains a percentile range. Document no recapture from sealed objective archives, immutable conflicting sidecars and failure-status propagation. Link the new guide from README's documentation index; do not bulk-load or rewrite unrelated docs.
4. Update current-context sections of `.ai-factory/DESCRIPTION.md` and `.ai-factory/ARCHITECTURE.md` through V3-37: six new analytical families, catalog 136, no new capability ownership, runner/result/replay/command/observer/API/SQL versions unchanged. Preserve dated historical counts elsewhere.
5. Keep M7 open. This plan does not own `institutional_economy`, deferred kinship handoff or M6 testimony tracking. Route any milestone-note update through `$aif-roadmap` if available/requested; do not independently close milestones or change source requirements during implementation.
6. Record final verification commands/results, omitted optional integration checks and known coverage limits in the implementation handoff. Recheck the original-request mapping in the index before marking Task 15 complete.

### Required Interfaces and Contracts

English artifacts, technical terms preserved. No automatic implementation commit/push; commit messages in index are suggested checkpoints. No new external statistical dependency is needed (SciPy is already a runtime dependency).

### Error Handling and Logging

Documentation must not include real private payloads; use synthetic IDs/labels only. Report unavailable owner commands rather than pretending to have run them. No production logging changes in this task.

### Tests and Verification

Check new Markdown links resolve and CLI examples match `uv run palimpsest-matrix run --help` / `uv run palimpsest-matrix aggregate --help`. Re-run `uv run pytest tests/unit/test_metric_specifications.py tests/unit/test_cultural_metric_comparison.py --cov=analysis --cov-report=term`; confirm count 136 and documented interval method match executable output. Run `$aif-verify` against this explicit bundle after implementation.

### Acceptance Criteria

Mandatory docs checkpoint completed, every measurement has its denominator/availability/provenance explained, and final context never suggests this work owns a new cultural authority or capability flag.

## Phase Risks and Mitigations

- Natural experiments may have sparse cultural evidence: use explicit availability assertions in real runs and hand-calculated normalized fixtures for numerical correctness.
- Old docs describe narrower summary support: clearly distinguish the new opt-in sibling path from unchanged legacy summaries.
- Catalog expansion touches many pins: update exact current-cardinality tests only, not historical counts or unrelated numeric literals.

## Phase Completion Checklist

Tasks 13–15 satisfy acceptance criteria; whole-project checks and docs checkpoint are recorded; progress is updated only in `index.md`.
