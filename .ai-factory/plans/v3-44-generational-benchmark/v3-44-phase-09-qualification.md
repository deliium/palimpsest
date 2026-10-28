# Phase 9: Regression, research execution and completion evidence

Plan: [index.md](index.md)
Tasks: 21–23
Depends on: Tasks 1–20

## Objective

Run the full regression and benchmark matrix, publish qualified scientific results and document exactly what is certified. Do not equate completing this suite with silently owning deferred flags or universal scale support.

## Current-Code Evidence

| Path | Symbols / sections | Why it matters |
| --- | --- | --- |
| `docs/development.md` | verification commands / opt-in markers | Default pytest excludes DB and Compose tests |
| `tests/unit/test_v1_regression_gate.py` | `_CATALOG_BUILDERS`, flags-off catalog | A–E/reference gate is not all V1 tests |
| `tests/unit/test_v2_scientific_invariants.py`, `tests/architecture/test_benchmark_suite_isolation.py` | V2 boundaries and benchmark isolation | Keep legacy scientific gates unchanged |
| `src/analysis/cultural_metric_comparison.py`, `src/experiments/path_dependence_comparison.py` | seed-block comparisons | Existing estimands and missing-pair semantics |
| `tests/benchmarks/test_v3_long_horizon.py`, `tests/benchmarks/test_v3_historical_queries.py` | V3-43 supervised lanes | Separate performance qualification from civilization science |
| `docs/long-horizon-scalability.md` | Verified Envelope / Workload Distinctions | 10k verified, dense 100k incomplete; no universal capacity |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/experiments/civilization_benchmark_comparison.py` | create | Compose existing seed-block estimators and deterministic outcome summaries |
| `tests/unit/test_v3_benchmark_comparison.py` | create | Null/zero/missing-pair/seed-block arithmetic |
| `tests/benchmarks/test_v3_civilization_benchmark.py` | create | Bounded suite execution and qualification receipts |
| `docs/v3-benchmark-suite.md` | create via `$aif-docs` | Reproduction, cases, limits, scientific interpretation |
| `docs/development.md`, `docs/experiments.md`, `README.md` | modify via `$aif-docs` | Commands and documentation index |
| `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md` | narrowly update after verification | New suite/profile seams and unchanged version pins |

## Task 21: Execute all V1 and V2 regression lanes without silent skips

### Intent

Run the whole default test collection plus opt-in persistence/Compose/client lanes, not just files named `test_v1_*` or `test_v2_*`.

### Implementation Steps

1. Discover current first-party test collection with pytest and record test counts/markers. Run all default tests (unit, architecture and applicable typecheck fixtures) with coverage; explicitly include legacy benchmark and V1/V2 scientific gates. Default configuration omits integration/Compose, so they need separate commands.
2. Run all non-scale integration tests against disposable PostgreSQL/pgvector; run all Compose tests against the built image with required prerequisites configured. Include the refactored image-backed `test_research_ui_wiring.py` with authenticated real matrix data: no local frontend output or unauthenticated external server may be required for that release lane. Scale integration tests are a separate lane in Task 22, not silently counted as passing.
3. Run Ruff, mypy, import-linter, the entire pinned Godot registry and all Research UI tests/check/build. Do not alter old assertions/count pins to make failures disappear. When an actual regression is found, produce a minimal failing regression test and bounded fix in the responsible module; a larger capability/architecture change becomes a reported blocker, not scope creep.
4. Record each command, source revision/configuration, exit status, collected/passed/failed/skipped counts, coverage and prerequisite reason. A skipped required lane is unexecuted; no global pass until it executes. Preserve logs as bounded metadata summaries and reference full runner output externally.

### Required Interfaces and Contracts

Compatibility pins remain: default runner v4/result v2, feature runner v55, 43 commands, 73 observer semantics, 136 metric families, selected replay-v22/codec-v20, Alembic 0017, `/v1`, `observer-protocol-v1`. New benchmark siblings/profile do not change these counts. V2 catalog remains 16 cases; V3 catalog is separately 30.

### Requirement Evidence

Original Request — Run all V1 and V2 regression suites and completion criteria; `pyproject.toml` — pytest marker exclusions; `.ai-factory/ARCHITECTURE.md` — compatibility baseline.

### Error Handling and Logging

Failures and skips remain separate. Never log DSNs/secrets or dump excluded generated files/lockfiles. DEBUG command/lane counts, INFO summaries, ERROR lane/reason codes. Do not disable coverage or broadly suppress warnings.

### Tests and Verification

```bash
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term -m 'integration and not scale'
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term -m compose
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src tests
uv run --frozen --python 3.12.14 lint-imports
```

Configure `PALIMPSEST_TEST_DATABASE_URL`, image/browser prerequisites and any explicit Compose smoke variables from Task 20. Run pinned Godot and pnpm commands from Phase 8 as part of this same evidence manifest. Integration tests named recording replay are network-free but still require explicit marker selection.

### Acceptance Criteria

All required V1/V2/backward-compatibility and client lanes actually execute and pass; any environment-bound unexecuted lane blocks full certification and is listed explicitly.

## Task 22: Run deterministic smoke and predeclared small-statistical research qualification

### Intent

Provide real scientific outcomes with honest nulls and measured reproducibility, not a green registry-only test or a scripted civilization demo.

### Implementation Steps

1. Add a benchmark harness using the Phase 2 CLI/executor with supervision and per-run isolated storage. For all 30 cases execute seed-23 mechanism smoke and research smoke, plus exact-identity deterministic twins in separate namespaces. Cases 01–28 research smoke is unassisted; cases 29–30 research smoke is explicitly `grouped_intervention`, retaining BN prefix controls and assigned treatments. Require actual cohort turnover and `ticks_committed == declared_horizon` for full generational lanes; unexpected generation/extinction/threshold stops fail horizon coverage even if the runner classifies them as nonfailure. Short fixture prefixes remain separately labeled. Use a positive wall-time budget (initial qualification 300 seconds per case assignment); timed-out/incomplete results do not count as completed.
2. Execute research profiles for numeric seeds `(11, 23, 37, 53, 71)`, one replicate each, with matched arms and predeclared contrasts. Do not add seeds, extend horizons or select best outcomes after inspecting results. Treat numeric seeds as independent blocks, not agents, ticks, generations, descendants or duplicate seed labels.
3. Reuse existing cultural/path-dependence estimators for eligible scalar contrasts; implement a thin benchmark comparison composer rather than a new universal culture/institution score. Validate materialized treatment scopes and mode/profile evidence first: founder-only mode effects use fixed founder IDs and eligible lifetime windows, unchanged entrant modes are not labeled off, and profile changes are composite treatments with every changed mode declared. Whole-population downstream summaries from founder-only manipulations remain descriptive. For other selectors report per-seed outcomes and descriptive summaries; Student-t intervals over paired seed deltas only when the actual assumptions and complete paired blocks apply. N=1 is descriptive; fewer than two complete paired blocks has no interval. Record missing/ineligible blocks and original denominators; do not silently exclude them from suite completion.
4. Report pointwise intervals without directional/significance gates, family-wise causal claims or posthoc selection. Zero differences, no institution/money/myth/government/religion and no observed divergence are valid outcomes when evidence is complete. Mixed stochastic alignment is explicit. Legacy p05/p95 stays a percentile range, not a confidence interval.
5. Re-run V3-43 supervised 10k/100k scale and historical-query lanes with coverage enabled under explicit resource budgets. Reuse source workload definitions rather than substituting a small fixture for a dense run. Preserve verified/incomplete/unexecuted distinctions and report resource enforcement honestly. No dense-100k completion or broad supported-limit claim follows from a timeout; incomplete predeclared stress attempts are acceptable qualified limitations, not successful workloads.
6. Verify all retained suite/source artifacts using `civilization-benchmark verify --require-complete`; produce a completion matrix mapping every user criterion to exact passing checks, measured outcome/coverage and known limitations. Source revision and artifacts must match the release candidate. Presentation/browser status from Task 20 is part of the matrix.

### Required Interfaces and Contracts

Research comparisons never feed cognition, stop selectors, treatments or prompts. Benchmark metadata does not enter runner JSON. Scientific null ≠ unexercised mechanism ≠ unavailable evidence ≠ failed execution. Long-running reproducibility is certified only for completed measured workloads, with full provenance; synthetic paging/log lanes are labeled non-scientific.

### Requirement Evidence

Original Request — Scientific constraints, scenarios 29–30, long-running auditability and V3 completion criteria; `docs/cultural-evolution-metrics.md`; `docs/historical-contingency.md`; `docs/long-horizon-scalability.md`.

### Error Handling and Logging

Supervisor reports timeout/resource exhaustion with last verified boundary and incomplete status. Never convert killed workers into zeros or infer absent institutions from failed capture. Log aggregate counts/progress/reason codes; metadata-only artifacts retain IDs and source references, not private content.

### Tests and Verification

```bash
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_v3_benchmark_comparison.py -q
uv run --frozen --python 3.12.14 palimpsest-matrix civilization-benchmark run --profile smoke --lane mechanism --output /tmp/opencode/v3-44/mechanism --timeout-seconds 300 --code-revision "$PALIMPSEST_V3_SOURCE_REVISION" --source-artifact-digest "$PALIMPSEST_V3_SOURCE_ARTIFACT_DIGEST"
uv run --frozen --python 3.12.14 palimpsest-matrix civilization-benchmark run --profile smoke --lane research --output /tmp/opencode/v3-44/smoke --timeout-seconds 300 --code-revision "$PALIMPSEST_V3_SOURCE_REVISION" --source-artifact-digest "$PALIMPSEST_V3_SOURCE_ARTIFACT_DIGEST"
uv run --frozen --python 3.12.14 palimpsest-matrix civilization-benchmark run --profile research --lane research --output /tmp/opencode/v3-44/research --timeout-seconds 300 --code-revision "$PALIMPSEST_V3_SOURCE_REVISION" --source-artifact-digest "$PALIMPSEST_V3_SOURCE_ARTIFACT_DIGEST"
uv run --frozen --python 3.12.14 palimpsest-matrix civilization-benchmark verify --output /tmp/opencode/v3-44/research --require-complete
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term -m 'integration and scale' tests/benchmarks/test_v3_civilization_benchmark.py -q
```

Set `PALIMPSEST_V3_SOURCE_REVISION` and `PALIMPSEST_V3_SOURCE_ARTIFACT_DIGEST` to the verified revision and canonical digest of the actual source artifact used for these runs; these are reproduction-driver variables forwarded as explicit arguments, not new application settings. Never substitute a random digest or assume the current dirty tree equals HEAD. For a verified clean source snapshot, replace the digest argument with `--source-clean` and retain the revision; never supply both. Test-local identities are explicitly synthetic test evidence, not release-source attestations. Container qualification derives the same CLI identity from verified build labels and works without Git metadata.

Run existing V3-43 10k/100k/query commands from `docs/long-horizon-scalability.md` with explicit `--cov --cov-report=term` retained and separate output roots. The new harness uses `integration` + `scale` markers for expensive runs, not default unit collection. Unit tests cover zero effects, constant deltas, missing pairs, duplicate seeds, invalid non-finite data, n=1, founder versus entrant scope, composite profiles, early nonfailure stops and complete versus partial evidence.

### Acceptance Criteria

All 30 mechanisms have bounded coverage evidence, all declared research profiles have completed matched blocks or explicit blocking statuses, and no positive civilization outcome is required. Scale attempts are separately qualified; actual supported claims do not exceed the completed envelope.

## Task 23: Document the qualified V3 completion contract and perform final verification

### Intent

Make benchmark reproduction and limits usable without changing roadmap ownership or overstating completion.

### Implementation Steps

1. Invoke `$aif-docs` as the mandatory documentation checkpoint. Create `docs/v3-benchmark-suite.md` with the 30-case mapping, profiles/seeds/budgets and full stopping selectors, controlled versus autonomous lanes, founder/entrant treatment scopes and composite initializer contrasts, new content-empty learner pack, terminal-safe inspection and recording/fork boundaries, explicit source-identity arguments/image labels, result schema/availability, comparison assumptions and exact commands. Index it from README and relevant development/experiment pages.
2. Document normal release steps as published image + container runtime + browser only. Separate developer pinned Godot/pnpm/Playwright tooling from end-user prerequisites. Include `/research/` and Godot entrypoints, safe credential handling and capture/debug opt-in requirements.
3. Publish a compact verified completion matrix derived from Task 22 artifacts, not manually asserted outcomes. State source revision, completed regression/client/replay/scale lanes, unexecuted gates, null results and measured limits. Reference external result roots without committing secrets/private recordings/generated bulk evidence.
4. Narrowly refresh DESCRIPTION/ARCHITECTURE for the separate benchmark registry, profile and release bundle. Retain current version/count pins and deferred capability ownership. Route any roadmap registration/closure through `$aif-roadmap` or user decision; do not edit milestone status automatically.
5. Run `$aif-verify` against this explicit ultra entrypoint after implementation, and the standalone rules gate if available. Inspect targeted diffs/status to confirm unrelated `.uid` work remains untouched. Mark tasks complete only after evidence, not after writing documentation.

### Required Interfaces and Contracts

“V3 benchmark-qualified” means the requested mechanisms, invariants, reproducibility and presentation gates actually pass with honest nulls. It does not assert every societal phenomenon emerged, universal 100k capacity, durable subjective restart, recorded-LLM forks, `institutional_economy` ownership, deferred kinship knowledge handoff or M6 completion. M7 cannot be automatically closed merely because this suite is complete; unresolved roadmap slots remain visible.

### Requirement Evidence

Original Request — all V3 completion criteria; `.ai-factory/ROADMAP.md` — M6/M7 open items; `.ai-factory/ARCHITECTURE.md` — milestone owner command and compatibility rules. This reconciles final-suite qualification with explicitly unowned capabilities; neither is silently rewritten.

### Error Handling and Logging

Missing environment evidence is listed as a blocker/unexecuted gate, not a footnote beneath a global pass. Documentation errors and stale source revisions block final certification. Logs retain only counts/paths/status and redacted codes.

### Tests and Verification

Run the existing documentation link checks discovered by filename/README references, full commands from Task 21, artifact verification from Task 22 and explicit-plan `$aif-verify`. Validate every requirement row has a real test/artifact source. No code/test execution result is invented or inferred from this planning invocation.

### Acceptance Criteria

Documentation accurately describes executed results and honest limitations, zero-install deployment is proven, all bundle tasks have verified receipts and no deferred flag/milestone is silently claimed complete.

## Phase Risks and Mitigations

- A fully green unit suite can hide DB/browser skips: retain separate required gate statuses and prohibit aggregate green on unexecuted required lanes.
- A completion label can overclaim science: maintain outcome/coverage/execution separation and list deferred ownership independently.

## Phase Completion Checklist

- Verify Tasks 21–23; update only index progress.
- Preserve qualified incomplete stress attempts and all required-gate blockers in the final handoff.
