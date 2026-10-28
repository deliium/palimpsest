# Phase 1: Benchmark contracts and valid generational composition

Plan: [index.md](index.md)
Tasks: 1–3
Depends on: none

## Objective

Define a separate, executable V3 benchmark contract and reproducible small worlds. Do not change the locked V2 catalog or turn research outcomes into pass conditions.

## Current-Code Evidence

| Path | Symbols | Why it matters |
| --- | --- | --- |
| `src/experiments/benchmark_suite.py` | `BenchmarkScenarioSpec`, `BENCHMARK_SCENARIO_COUNT` | Existing V2 registry is exactly 16; invariant strings are descriptive, not executable |
| `src/experiments/generational_comparison_base.py` | `generational_comparison_base`, `assert_comparable_generational_pair` | Existing v55 composition and comparison checks |
| `src/simulation/new_agent_initialization.py` | `SpeciesDefaultsPack`, `species_defaults_for`, `_SPECIES_DEFAULTS` | Existing packs enable only selected modes and never copy content |
| `src/simulation/runner_serialization.py` | runner config codecs | v55 is a selected lower-family root with the later cognition keyset, not an arbitrary union |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/experiments/civilization_benchmark_models.py` | create | Frozen typed contracts, checks and results |
| `src/experiments/civilization_benchmark_suite.py` | create | Ordered 30-case registry and discovery |
| `src/experiments/civilization_benchmark_base.py` | create | Atomic v55 builder and profile constants |
| `src/experiments/__init__.py` | modify | Explicit public exports only |
| `src/simulation/new_agent_initialization.py` | modify | Explicit opt-in content-empty civilization learner pack |
| `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py` | modify | New profile's v55-only validation, using existing initialization seam |
| `tests/unit/test_v3_benchmark_registry.py`, `tests/unit/test_v3_benchmark_base.py`, `tests/unit/test_v3_benchmark_newborn_profile.py` | create | Contract and compatibility tests |

## Task 1: Define the executable thirty-scenario registry

### Intent

Every numbered user scenario must have its own discoverable ID and testable evidence contract, even where worlds/builders are shared.

### Implementation Steps

1. Introduce `V3BenchmarkSpec`, `V3BenchmarkRecipe`, `V3BenchmarkCheck`, `V3BenchmarkRunResult`, `V3BenchmarkSuiteResult` as frozen, defensively detached dataclasses. Use exact typed enum selectors rather than parsing English descriptions.
2. Set suite ID `v3-generational-civilization-benchmark-v1`; scenario IDs `v3-bench-01-blank-slate` through `v3-bench-30-multigeneration-fork` with the exact order/table in Phases 3–6. Implement `list_v3_benchmark_scenarios()`, `get_v3_benchmark_scenario(id)`, `build_v3_benchmark_scenario(id, *, seed, profile, lane)`.
3. Each spec records request number, required specs/modes, execution kind (`independent` or `grouped`), mechanism/research lanes, evidence selectors, bounded schedule ID/version, comparison axis, non-goals and required capture lanes. Explicitly set off-V1-gate status.
4. Define separate fields: execution status, invariant checks, mechanism coverage, evidence availability, observed phenomenon, publication status and comparison. Execution statuses: `completed`, `failed`, `timed_out`, `not_run`; coverage: `exercised`, `not_exercised`, `not_applicable`; evidence: `complete`, `partial`, `unavailable`; phenomenon: `detected`, `not_detected`, `unknown`, `not_applicable`. Never derive a passing invariant from an unavailable metric.

### Required Interfaces and Contracts

`V3BenchmarkCheck` contains selector ID/version, status (`pass`, `fail`, `unexecuted`), reason code, qualified source references, boundary/window, eligible numerator/denominator and coverage. No raw memory, dialogue or credentials in results. Scenario validation rejects duplicates, unordered collections, unknown selectors, non-finite budgets and unsupported lane/execution combinations. Do not add runner JSON fields, HTTP routes, metrics or capability slots.

### Requirement Evidence

Original Request — scenarios 1–30 and Scientific constraints; `.ai-factory/ARCHITECTURE.md` — Versioned Extension Contract; `docs/v2-benchmark-suite.md` — null outcomes.

### Error Handling and Logging

Fail preflight with bounded codes (`unknown_scenario`, `invalid_profile`, `unsupported_execution_kind`, `missing_selector`). DEBUG logs scenario/profile IDs and check counts; INFO suite start/completion; ERROR safe reason codes. Follow `PALIMPSEST_LOG_LEVEL`; no payload logging.

### Tests

Assert exact 30-ID order and uniqueness, one-to-one request coverage, executable selector registration, immutable nested values, unknown-case rejection and unchanged 16 V2 entries. A null phenomenon with complete evidence passes a valid invariant; unavailable evidence cannot pass its required check. Mandate-language checks are test-only and are not a runtime natural-language parser.

### Acceptance Criteria and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_v3_benchmark_registry.py tests/unit/test_benchmark_suite_registry.py -q` passes. Every case names its required measurement and does not mandate government, money, religion, myth or institutions.

## Task 2: Build bounded and comparable v55 benchmark worlds

### Intent

Historical catalog builders are templates, not safe overlays: several replace schema versions, rosters or flags. Compose each benchmark atomically and validate it through real codecs.

### Implementation Steps

1. Add `build_v3_benchmark_base(*, seed, profile, scenario_id)` using the AY/generational comparison physical-world pattern. Construct v55 with explicit population lifecycle, initialization, finite max ticks and runtime-terminal stopping disabled. Set `GenerationalRunSpec(max_generation_index=None, stop_on_extinction=False, population_threshold=None, experiment_criteria=(), criterion_cadence_ticks=1)` explicitly; preserve deterministic configured history sampling separately. Do not inherit comparison-base generation cap 6, BN cap 16, or the default extinction stop. Add optional specs in the owning recipe, never with dictionary key injection.
2. Freeze profiles: `smoke` seed 23, 96-tick horizon, four founders, one entrant every eight ticks, generation length 16, lifespan 24, population cap 12; `research` seeds `(11, 23, 37, 53, 71)`, 192 ticks, same entry/stage policy and population cap. These are fixture budgets, not a supported scale claim. Use initial age/physical setup explicitly where witnesses or successors must overlap; record every departure from the base in the recipe.
3. Maintain separate `visual` profile: seed 23, 160 ticks, six founders, cap 16; controlled opportunity schedule specified in Phase 8. No seed search or automatic horizon extension. Each scenario's unit mechanism fixture can use a shorter exact prefix, declared as such rather than relabeling it a completed multi-generation research run.
4. Reuse owned specs and policy helpers from catalog AE–BK, but construct final `SimulationRunnerConfig` in one place. Round-trip every supported combination through encode/decode; compare canonical fingerprints. Keep legacy v4 flags-off regression fixtures separate.
5. Build paired arms with same seed, stochastic identity, layout, founder roster, cohort schedule and stopping horizon; vary exactly the declared opportunity or mode axis. Record cases with intentional schedule/layout differences as descriptive contrasts, not one-factor paired effects. Per-agent mode comparisons use `treatment_scope=founder_roster`: toggle only founder specs, retain the exact same newborn profile in both arms, and restrict direct mode-effect estimands to those founders' observed lifetimes. Whole-population downstream summaries are labeled descriptive. Never call such a control population-wide mode-off. For deliberate initializer comparisons use `treatment_scope=initializer_profile` and `contrast_kind=composite_profile`; default/developmental/civilization packs change several modes, so those contrasts are not isolated single-mode effects.

### Required Interfaces and Contracts

Return immutable configuration plus recipe metadata; metadata stays outside runner JSON. Each contrast declares `treatment_scope`, `contrast_kind`, fixed founder IDs, initializer profile ID per arm and exact manipulated fields. Opportunity contrasts use `treatment_scope=run_opportunity`, `contrast_kind=single_factor` only when the materialized configs differ on that declared opportunity alone. Never enable unowned `institutional_economy` or `multi_hop_testimony_tracking`. v55 must retain root omission semantics and all older accepted configurations. Supplies/resources and experiment laws are declared physical setup, not learned knowledge. No preseeded social labels, technique ledgers, institutions or inherited subjective entries.

### Requirement Evidence

Original Request — small deterministic/statistical scenarios, population turnover; `src/experiments/generational_axes.py` — existing axis applicators; `.ai-factory/ARCHITECTURE.md` — accepted-set discipline.

### Error Handling and Logging

Preflight rejects impossible spawn locations, missing prerequisites, mismatched pairs, profile budget violations and schema downgrade. Log only selector/profile IDs, roster counts, horizon and reason codes; fingerprints belong in scientific artifacts, not operational payload-surrogate logs.

### Tests

Parameterize all 30 recipes and lanes; assert codecs, exact prerequisites, generation schedule, living-population cap, no unsupported flags, shared stochastic identities and invalid compositions. Check all stop selectors explicitly, including generation/extinction/threshold/criteria selectors. In full bounded smoke acceptance require `ticks_committed == declared_horizon`, not merely a nonfailure stop reason; unit tests use short matching horizons. Instrument actual first admitted agents to verify their mode vectors/profile in both arms and detect a false population-wide off claim. Verify founder-only estimands exclude entrant-owned rows and initializer contrasts carry the composite label. Check that disabling capture changes no configuration fingerprint. Validate research seeds without running all full research experiments in default tests.

### Acceptance Criteria and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_v3_benchmark_base.py tests/unit/test_generational_comparison_base.py -q` passes. Every accepted recipe is an actual executable config; no builder silently downgrades v55.

## Task 3: Add an explicit blank civilization learner profile

### Intent

Current developmental, office and institutional-memory newborn profiles do not enable every mode needed for descendant symbolic/translation/institution experiments. Do not pretend descendants inherit founder modes or silently expand existing packs.

### Implementation Steps

1. Add closed ID `species_default_civilization_learner_v1`, a fresh factory and public constant in `new_agent_initialization.py`. Start with developmental-pack modes and explicitly enable deterministic symbolic language, translation, institution concepts, office succession, institutional memory and institutional decay. Leave all other defaults unchanged; never copy a founder spec or ledger.
2. Accept the new ID only for v55 with the required cultural provenance, generational initialization/lifecycle, and enabled owned population/cultural flags. Validate symbolic→naming, translation→naming, institutional memory→office/concept, decay→concept dependencies through existing checks. Add no new capability flag or schema version; this is a new versioned policy ID on the owned initialization seam, not a change to old policy semantics.
3. Select this pack only for benchmark recipes requiring these descendant modes. Use existing developmental and office profiles in other cases. Record the selected pack in existing creation/manifest provenance. Keep it identical across founder-mode off/on arms: changing founder modes never changes `species_defaults_for()` for entrants. Initializer-profile comparisons may deliberately choose different packs, but must declare a composite treatment and enumerate the actual mode differences; do not introduce more packs or mutate newborn modes after binding to manufacture a single-mode contrast.
4. Extend closed-ID exports and exact codec acceptance tests. Old packs, default configuration and old version acceptance sets must remain byte-equivalent. No broadening of the new policy into pre-v55 schemas.

### Required Interfaces and Contracts

`species_defaults_for(new_id, agent_id=...)` produces fresh owner-bound modes and baseline drives only. Episodic/semantic/goal/cultural/skill/knowledge/office/institution stores are empty. Enabling cognition modes does not supply a vocabulary, narrative, role, successor, institution or truth. Existing bounded policies remain unchanged.

### Requirement Evidence

Original Request — new agents learn rather than receive copied memories; scenarios 21–28. `src/simulation/new_agent_initialization.py:957–1007` — current mode-versus-content packs. This explicit additive profile closes a composition gap; it does not claim inheritance or economy capability ownership.

### Error Handling and Logging

Reject new pack on legacy versions or missing required specs with stable safe codes. DEBUG logs profile/owner IDs and enabled-mode counts; no drive distributions or content. Do not mutate or repair invalid input.

### Tests

New ID v55 valid/invalid prerequisites; all pre-v55 rejection; fresh owner identity across calls; exact enabled modes; every actual newborn store empty using Phase 2 instrumentation; old four pack outputs unchanged; admit/replay creation metadata retains new policy ID.

### Acceptance Criteria and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_v3_benchmark_newborn_profile.py tests/unit/test_new_agent_blank_slate_guard.py tests/unit/test_v3_benchmark_base.py -q` passes. No subjective content or mandatory social outcome is introduced.

## Phase Risks and Mitigations

- A new profile could widen legacy schemas: enforce v55-only selection and old-pack canonical twins.
- A long-lived founder could masquerade as intergenerational learning: record cohort/owner IDs and require actual entrant recipients in the relevant mechanism checks.

## Phase Completion Checklist

- Verify Tasks 1–3 and update only `index.md` task checkboxes.
- Keep compatibility failures blocking; do not downgrade a recipe to make it decode.
