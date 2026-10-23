# Phase 6: Scientific acceptance gates and documentation

Plan: [index.md](index.md)
Tasks: 16–18
Depends on: Tasks 1–15

## Objective

Demonstrate a real forked multigeneration experiment, preserve existing compatibility/authority contracts, and document the limits of historical-contingency interpretation.

## Current-Code Evidence

| Path | Symbols / sections | Why it matters |
|---|---|---|
| `tests/unit/test_cultural_metrics_end_to_end.py` | Real generational matrix capture/comparison | Representative existing composition fixture. |
| `tests/unit/test_v1_regression_gate.py`, `tests/unit/test_v2_scientific_invariants.py` | Scientific regression gates | New recipe must not change flags-off behavior. |
| `tests/architecture/test_v3_generational_experiments_isolation.py` | Bounded-package checks | No experiments→concrete persistence or analysis→simulation authority. |
| `docs/development.md` | Verification commands, lines 26–54 | Coverage/default unit vs opt-in infrastructure conventions. |
| `docs/generational-runner.md` | Historical inspection and identity limitations | Durable world history is not full cognitive restart. |
| `docs/cultural-evolution-metrics.md` | Repeated seed blocks and provenance | Existing pointwise cultural statistics contract. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `tests/unit/test_path_dependence_end_to_end.py` | create | Real smoke ensemble and inferential oracle. |
| `tests/integration/test_path_dependence_execution.py` | create | PostgreSQL replay forks and recovery. |
| `tests/architecture/test_path_dependence_boundaries.py` | create | Imports/authority/logging/no new family/schema gates. |
| `tests/unit/test_compatibility_matrix.py`, `tests/unit/test_v1_regression_gate.py` | modify only where needed | Explicit no-default-change assertions, not weakened goldens. |
| `docs/historical-contingency.md` | create | Workflow, semantics, formulas and reproducible examples. |
| `docs/experiments.md`, `docs/generational-runner.md`, `docs/cultural-evolution-metrics.md`, `docs/configuration.md`, `docs/development.md`, `README.md` | modify | Focused integration/discovery/verification links. |
| `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md` | modify during implementation docs checkpoint | Add V3-38 bounded seam without changing current contract pins. |

## Task 16: Prove the full historical-contingency experiment workflow

### Intent

Test real composition, not only manifest-shaped mocks or a visually divergent pair.

### Implementation Steps

1. Create a bounded real smoke ensemble using Task 8's exact `bn-food-opportunity-v1` fixture, deterministic fake, F=4/H=36, at least three predeclared distinct numeric seeds, two replicas, share/withhold/untouched arms and one additional bounded compound schedule. Verify initial holder/inventory, co-location, regenerative resources, empty cognition ledgers, common setup and maximum generation 16 in the production spec, not by patching a running engine. Include both successful and rejected intervention cases in explicitly declared fixtures without seed/outcome cherry-picking; all scientific branches preserve ordinary admission. No test may silently repair an ineligible F.
2. Execute prefix→snapshot→child replay→complete owner restore→command intervention→multiple new cohorts→outcome capture→sealing→verified comparison. Require exact common prefix and complete state witness per pair; parent hashes unchanged; at least two post-F cohort transitions and founder turnover in the smoke profile. Require no nonzero social divergence; equal/unknown outcomes are scientifically legal.
3. Exercise all seven outcome domains with real computed output or explicit qualified unknown; separate synthetic hand-computed inference tests verify nonzero arithmetic. Load one representative existing BM configuration/cultural capture fixture through this path to catch compatibility assumptions. Now that Tasks 10–12 exist, extend Task 6's same-RunId isolated no-treatment restore proof to exact full outcome evidence and projected metric parity, including nonempty legacy beliefs, runtime deduplication, fresh-empty cultural channels and complete/disabled/missing six-lane institution evidence. Do not add a backwards dependency from Task 6 to these collectors.
4. Add PostgreSQL integration test using existing disposable `palimpsest_test` fixture conventions. Materialize actual child chains, restore replay head, verify prior-event observations and exactly one F recorder baseline, complete branches and adopt them after process loss. Reconstruct a sealed parent prefix to launch a different PLANNED slot whose original child RunId has never been created; a child interrupted after run creation must instead remain failed-partial/missing, with no replacement RunId. Verify two F values have different prefix artifact paths and both survive adoption; never append duplicate commits to the parent. Validate no fabricated `_BoundaryReader` hashes enter production artifacts and every failure stop class cannot create a completion seal.
5. Add opt-in long profile F=100/H=1100 with several predeclared seeds and bounded population, proving horizon/stop configuration permits multiple generations. Report prefix ineligibility explicitly; the mandatory eligible `bn-food-opportunity-v1` fixture with sealed shared setup and fixed physical rules must exercise tick-100 admitted transfer versus withholding. Assert at least two post-F cohort transitions and eventual founder turnover without requiring norms/institutions/technology to emerge. This is an execution/scalability check under a declared benign physical fixture, not a claim of historical effects or realistic ecology.

### Required Interfaces and Contracts

All end-to-end artifacts must be decoded by strict production loaders. Database integration may skip locally without infrastructure, but a skip is a verification gap, not a passing durability proof. Never mutate real databases or name production DBs in tests.

### Requirement Evidence

User complete tick-100/multigeneration/statistical example; planning skill requirement for representative existing artifacts and real integration evidence.

### Error Handling and Logging

Tests capture logs and assert no secrets, food-command payloads, subjective content or complete-state digest surrogates. Integration failures retain bounded artifact references and reason codes only.

### Tests

New `test_path_dependence_end_to_end.py` and `test_path_dependence_execution.py`; named long test `test_tick_100_multigeneration_ensemble` marked `integration` and `scale`. Include interrupted child and tampered root/prefix cases.

### Acceptance Criteria

Production loaders reproduce correct independent block counts and qualified outputs from real forked replay children; same-seed extra branches do not increase n.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_path_dependence_end_to_end.py -q`

With `PALIMPSEST_TEST_DATABASE_URL` configured to a disposable database:

`uv run --frozen --python 3.12.14 pytest -m integration tests/integration/test_path_dependence_execution.py -q`

`uv run --frozen --python 3.12.14 pytest -m 'integration and scale' tests/integration/test_path_dependence_execution.py -k tick_100 -q`

## Task 17: Enforce scientific, authority and compatibility regression gates

### Intent

Ensure the feature adds an experiment protocol, not a hidden simulation behavior or a relaxed trust boundary.

### Implementation Steps

1. Add AST/import and public-contract tests: experiments use public simulation fork ports; analysis has no runner, event-store, DB or mutable-world access; simulation does not import experiments/analysis; `research_runner` does not import API or `tests.*`; clients remain read-only/unmodified. Assert no provider SDK or global RNG additions. Verify facade exports and Ruff's grouped `__all__` ordering in the same change as new contracts. Test grouped BN discovery separately from standard `ExperimentDefinition`, exclusion from `OFF_GATE_MATRIX_EXPERIMENT_IDS`, and coordinator/matrix guards before manifest/provider side effects on fresh AND resume/adoption paths.
2. Pin no new world commands (43), observer semantic types (73), metric families (136), Alembic (`0017`), runner latest (`v55`), default runner/result (`v4`/`v2`), stable API/protocol and feature-selected replay-v22/codec-v20. Do not make replay-v22 universal or discard legacy accepted versions. New artifact schemas are siblings, not runner versions/capability flags.
3. Preserve unowned `multi_hop_testimony_tracking` and `institutional_economy` fail-closed behavior. Ensure capture off/no recipe leaves V1 and V2 trajectories unchanged and `prepare_parallel=False` remains untouched. Test concurrent parent/child resources cannot alias, though initial batch execution is serial.
4. Run full unit/architecture, formatting/lint, strict type and import-linter gates with coverage retained. Fix implementation defects in scope; do not weaken unrelated tests, alter goldens to hide divergence, or claim skipped infrastructure tests passed.

### Required Interfaces and Contracts

No new runtime dependency, migration, HTTP route, client semantics or external LLM support is implied. The legacy shallow runtime checkpoint API retains its documented limitations; only the new complete factory advertises cognitive continuation.

### Requirement Evidence

ARCHITECTURE — package allowlists, extension contract, default-off behavior; root AGENTS.md exclusions/test coverage.

### Error Handling and Logging

No production logging is added by architecture tests. Failure output uses bounded symbol/path/status evidence, not raw state. Technical failures block completion; report infrastructure skips separately.

### Tests

`test_path_dependence_boundaries.py`: forbidden imports/private access, pins, fake-only restriction, parent/sibling isolation, no payload logs, no new flag ownership. Existing `test_v1_regression_gate.py`, `test_v2_scientific_invariants.py`, compatibility and Alembic head pins remain green.

### Acceptance Criteria

All default and scientific invariant gates pass without relaxing authority or replay compatibility; missing database validation is explicitly recorded as unverified.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/architecture/test_path_dependence_boundaries.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/unit/test_compatibility_matrix.py tests/unit/test_alembic_head_pin.py -q`

`uv run --frozen --python 3.12.14 pytest`

`uv run --frozen --python 3.12.14 ruff check src tests`

`uv run --frozen --python 3.12.14 mypy src tests`

`uv run --frozen --python 3.12.14 lint-imports`

## Task 18: Document reproducibility, interpretation and the new experiment seam

### Intent

Make it hard to mistake an illustrative branch narrative for a causal result, or an objective replay seek for a complete subjective restart.

### Implementation Steps

1. Invoke `$aif-docs` at the mandatory implementation checkpoint. Create `docs/historical-contingency.md` with exact CLI/schema examples for a smoke profile and F=100/H=1100 food transfer versus no-transfer recipe, including the declared benign `bn-food-opportunity-v1` physical fixture, separate common-setup vs child-treatment budgets, eligibility, exact smoke/long stopping controls, founder/entrant mode table, prefix convention, absolute cohort windows, boundary-qualified prefix paths, full lineage tree and preparation/result/completion/failure publication order. Do not describe these fixture conditions as defaults for arbitrary social experiments.
2. Explain same-owner fork cloning vs blank-slate newborn admission; full runtime deduplication/legacy-store/fresh-empty coverage state vs narrow legacy checkpoints; complete in-process state vs durable objective history; fake-only provider support; deterministic parent reconstruction ONLY for unused planned child slots after process loss; completed-result adoption; and existing partial durable children remaining failed/missing. No replacement scientific RunId or automatic retry is supported in v1; starting a new-identity run requires an explicitly new ensemble. Explain unsupported external replay provider state and how failed/missed/rejected actions differ. Show an intentionally ineligible prefix and an intentionally singleton descriptive output.
3. Publish the exact paired/block Student-t formula, numeric-seed unit, duplicate-seed/replica/F dependence rules, independent n, exclusions, complete-pair conditioning, pointwise multiple-outcome warning and mixed run-ID channel limitation. Explicitly state no causal claim from a single run and no automatic causal claim from a significant interval.
4. Document each of seven domains/selector IDs/units/denominators/zero policies, narrative/technology F baseline, extinct/partial endpoints and analytical institution limits. Do not call resource Gini “wealth” or cooperation “altruism.” No global society/norm/institution registry exists.
5. Add links in README, experiments and generational runner pages; clarify composition-only spec/capture in configuration; add verification commands and integration prerequisites in development. Add focused V3-38 seam notes to DESCRIPTION/ARCHITECTURE preserving the baseline pins. Do not bulk rewrite historical counts or close M6/M7.
6. Roadmap linkage is M7, but actual milestone edits/registration are owned by `$aif-roadmap`; request that checkpoint through its owner workflow rather than changing roadmap requirements during planning or marking M7 complete.

### Required Interfaces and Contracts

Documentation must describe shipped restrictions, not deferred nested trees/live LLM/causal-identification promises. All snippets are tested against the production strict decoder/parser; examples carry declared setup and nonsecret configuration only.

### Requirement Evidence

User no-single-run-causality requirement; confirmed Docs=yes/M7 preference; ARCHITECTURE roadmap ownership.

### Error Handling and Logging

Docs changes add no runtime logging. Examples must contain no credentials, raw subjective payloads or content-derived operational digest logs. Failed snippet validation blocks docs completion.

### Tests

Extend `test_path_dependence_cli.py` and `test_path_dependence_models.py` to decode the documented example spec and parse commands. Verify all new README/docs links, seven selectors and singleton/no-causality warnings manually.

### Acceptance Criteria

A researcher can reproduce the protocol and distinguish eligibility, treatment realization, branch lineage, repeated-seed statistics and interpretive limitations without reading implementation code.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_path_dependence_models.py tests/unit/test_path_dependence_cli.py -q`

`uv run --frozen --python 3.12.14 palimpsest-matrix path-dependence run --help`

Manual: verify README → historical-contingency links, example artifact tree, formulas, skip disclosure and unchanged baseline pins.

## Phase Risks and Mitigations

- Long-run validation can be expensive: unit smoke proves logic; opt-in actual PostgreSQL/tick-100 gate proves durability and scale separately.
- Documentation drift can overclaim support: tested strict examples and explicit deferred-scope section are required.

## Phase Completion Checklist

- Tasks 16–18 satisfy their gates; infrastructure skips remain explicit gaps.
- Mandatory docs checkpoint completed and only `index.md` task checkboxes updated.
