# Phase 7: Scientific scenarios, regression gates, and documentation

Plan: [index.md](index.md)
Tasks: 25–28
Depends on: Tasks 1–24

## Objective

Demonstrate another agent/community repeating work, preserve honest disagreement/uncertainty, and lock compatibility without asserting emergence or truth.

## Current-Code Evidence

| Path | Symbols / behavior | Significance |
| --- | --- | --- |
| `src/experiments/scientific_hypotheses_scenario.py` | `scientific_hypotheses_scenario`, three arms, v56/min64 ticks | Adjacent registered scenario pattern. |
| `src/experiments/catalog.py` | `experiment_scientific_hypotheses`, `OFF_GATE_MATRIX_EXPERIMENT_IDS` | New scenario stays off V1 A–E. |
| `tests/unit/test_scientific_hypotheses_end_to_end.py` | `_config`, real runner/store/routes | Representative existing real artifact/fixture, not only synthetic rows. |
| `tests/unit/test_experiment_aq.py` | controlled ordinary experimentation fixtures | Deterministic laws, success is not knowledge. |
| `tests/unit/test_runner_finalization.py` | v1 command/pending expectations | Preserve legacy bytes; add v2 coexistence tests. |
| `tests/unit/test_scientific_hypotheses_pins.py` | 250-family baseline, other scientific pins | Append suffix, keep historical six algorithms. |
| `docs/development.md` | Python/static/UI/integration gates | Coverage stays enabled; prerequisites recorded honestly. |

## Files to Change

Create `src/experiments/replication_scenario.py`, `tests/unit/test_replication_scenario.py`, `test_replication_end_to_end.py`, `test_replication_determinism.py`, `test_replication_pins.py`; extend catalogue/facades and relevant architecture tests. Create `docs/scientific-replication.md`; update precise related sections in `README.md`, `AGENTS.md`, `docs/scientific-hypotheses.md`, `docs/experiments.md`, `docs/configuration.md`, `docs/persistence.md`, `docs/development.md`, `.ai-factory/DESCRIPTION.md`, and `.ai-factory/ARCHITECTURE.md` through the mandatory documentation checkpoint.

## Task 25: Register a bounded scientific replication experiment

### Intent

Provide repeatable research composition over existing capabilities, without scripting scientific belief as an outcome.

### Implementation Steps

1. Add `scientific_replication@1`, builder `scientific_replication_scenario(base, seed_matrix=None, max_ticks=64)` with minimum 64 ticks; use existing v56 science/bounded-experimentation and cultural prerequisites, no new spec/root field.
2. Four declared arms: `replication-baseline` (science off); `replication-individual` (science on, normal individual inquiry); `replication-community` (science on plus existing deterministic communication); `replication-conflicting-conditions` (community with explicitly declared material/condition differences in its controlled fixture). Preserve seed/world/comparison identity wherever unchanged; mark communication/material differences as declared treatments, not independent one-factor proof.
3. Reuse the actual V4-27 controlled tool/harvest law and owner-safe tool setup for a representative source/receiver path. Give each participant its own reachable material for same-kind binding; do not teleport the source tool.
4. For controlled mechanism tests only, schedule ordinary Wait/Talk/Tell/Experiment commands through existing trusted test arbiters and normal admission. The source first performs a real test, then shares its observed frozen design/result; no borrowed private ledgers or preinstalled scientific evidence.
   Build the representative complete design as actual `CommunicationRelation` objects under the shared 256-character object cap; assert it fits the eight-part/1,752-byte wire contract and is delivered intact. Do not use a larger local cap to make a synthetic frame pass.
5. Declare that exact deterministic law/operand-kind combinations cannot spontaneously yield arbitrary new outcomes. Conflicting-condition arm uses valid different materials/explicit parent-linked protocol variation; classifications retain not-comparable qualification. A separate false-report mechanism fixture uses ordinary attributed speech to demonstrate conflicting testimony about a common design—never fakes a committed experiment result.
6. Register scenario/facade/off-gate discovery and metric composition. Unassisted runs may produce no delivery, no participation, or no replication; retain those as known-empty/partial/unexecuted mechanism evidence, not fabricated emergence.

### Required Interfaces and Contracts

No guaranteed discovery, agreement, scientific community or N-replication truth. No new law mechanics, RNG, command, event, group actor or V4 flag. Scientific replication is within-run social procedure; cross-run live evidence import is not introduced.

### Error Handling and Logging

Invalid horizon or incompatible prerequisites fail with safe scenario validation codes. INFO scenario/arm counts and completion/coverage status only; no design or report payloads.

### Tests / Acceptance / Verification

`test_replication_scenario.py`: exact four arms, v56 prerequisites, seed preservation, off-gate registration, explicit composite treatments, invalid horizon, source/receiver reachable tools and legal nulls. Run with coverage plus `tests/unit/test_experiment_aq.py` and existing science activation/scenario tests located by filename.

## Task 26: Exercise real source → receiver → community → publication paths

### Intent

Verify the actual feature contract, not only DTO round trips.

### Implementation Steps

1. Extend/reuse `_config` and the real scientific-hypothesis end-to-end fixture without changing its legacy expected wire artifact. Add a controlled source test, observed source result, complete design delivery, receiver participation, receiver ordinary Experiment with its own tool, observed measurement and attributed result delivery back to the inviter. Do not preload reply outboxes: acceptance/result processing must produce them. Assert sender/public delivery echoes and ordinary recipient selection drive the return path.
2. Include third participant with a different directed trust appraisal; participants independently interpret common testimony. Assert no global consensus state and no copying of source hypothesis/evidence IDs.
3. Publish the completed replication snapshot through the real filesystem adapter; read all eight HTTP routes with subjective-debug credentials and inspect all pages. Assert lineage, source/child execution references, conditions, uncertainty and appraisals survive one-time token mapping. Include both objective execution receipts and owner report variants, without conflating a reported discrepancy with differing physical outcomes.
4. Add conflict cases: original reported success vs receiver observed failure; exact current category difference retained; adapted conditions marked not comparable; uncertainty unreported vs explicit alternative set; missing source result; source report contradicted by detached evidence without correcting cognition.
5. Repeat reports and tests at 1/2/8/128 counts in pure bounded fixtures: no truth field/promotion exists, testimony adds no support mass, and existing direct-test support statuses remain subjective. Exhaust caps explicitly rather than quietly increasing them.
6. Deterministic twins compare command/event exports, complete sidecar serialization, metric documents and snapshot bytes. Fork prefix/child and retired-owner cases preserve independent continuation and historical evidence. Include a max-hypotheses=1 delayed-result case to prove pending references survive admission pressure and recovery.

### Required Interfaces and Contracts

At least one end-to-end fixture must run real `SimulationRunner` + normal admission and use the representative V4-27 tool/harvest setup. Analytical mocks alone cannot satisfy this task. Do not claim statistically independent replications from deterministic twins or repeated messages.

### Error Handling and Logging

Fault cases must return the exact safe codes and preserve prior committed data. Capture logs and assert secret/content canaries absent.

### Tests / Acceptance / Verification

Run `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_replication_end_to_end.py tests/unit/test_replication_determinism.py tests/unit/test_replication_analysis_properties.py tests/unit/test_scientific_hypotheses_end_to_end.py -q`. Both real execution and explicit conflicting social interpretations must be demonstrated.

## Task 27: Complete the mandatory documentation checkpoint

### Intent

Document semantics, operational limits and recovery honestly so later features do not mistake replication for proof.

### Implementation Steps

1. Invoke `$aif-docs` as the implementation checkpoint. Write `docs/scientific-replication.md`: activation, frozen lineage vs local hypothesis identity, exact/same-kind bindings, conditions, categorical measurements and unknown error, result/report/attempt distinctions, social appraisals, duplicates/shared roots, conflicts, bounded capacities and legal nulls.
2. Document `rep_v1` exact fields/kinds/parts/byte limits and all-or-nothing delivery; unchanged `hyp_v1`; Talk/Tell-only piggybacking; individual participation and no group executor.
3. Document pending finalization v2/nested state versions and v1 compatibility, commit/abort/fork/retirement semantics, missing legacy state, and the continuing absence of complete durable subjective restart.
4. Document snapshot/store v1, programmatic opt-in publication, both gated settings, all eight routes/filter/pinning/errors, page limits, API read-only authority and UI uncertainty/coverage semantics.
5. Add new page to README and AGENTS documentation indexes, cross-link existing science/experiments/configuration/persistence/development sections. Update only current DESCRIPTION/ARCHITECTURE baseline tables/append V4-28; preserve dated historical counts and old accepted versions.
6. Current pins become 256 metric families, 17 contexts, 12 V4 flags, nine owned/three unowned, 43 commands, 73 observer semantic types, replay-v27/v25, Alembic0017, `/v1`, observer-protocol-v1; default runner/result v4/v2; existing feature v55/v56. Mention new subjective pending v2 separately, not as a world replay bump.
7. Do not edit roadmap/source axioms as a side effect of planning/implementation. Milestone progress belongs to `$aif-roadmap`; M8 is not closed by this feature.

### Required Interfaces and Contracts

The page explicitly says no calibrated numeric error bars exist in the current categorical experiment surface, no N-count establishes truth, source independence is limited, and community appraisals may disagree.

### Error Handling and Logging

Examples use placeholders, not real credentials/DSNs. Show safe operational reason codes; no sample private reports from user runs.

### Tests / Acceptance / Verification

Validate every referenced path/route/version/setting against implementation, run `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_replication_metrics.py tests/unit/test_scientific_hypotheses_pins.py tests/architecture/test_replication_invariants.py -q`, and review the new page plus README index. Existing historical sections must not be mass-rewritten to the newest counts.

## Task 28: Lock pins and run implementation completion gates

### Intent

Deliver executable compatibility and scientific boundary guarantees, not an unsupported certification claim.

### Implementation Steps

1. Add `test_replication_pins.py` and extend `tests/architecture/test_replication_invariants.py` for 256-family ordered prefix/suffix, unchanged world/API pins, no v57/0018, existing ownership and absence of scientific truth/group executor. Rerun the current-catalog pin migration already completed in Task 15; this task is not the first point at which earlier verification gates become passable. Preserve historical fixture counts.
2. Add explicit compatibility checks for default-v1 and science-transition-v2 pending codecs, exact-key rejection, original v1 fixture bytes, legacy pending fail-closed behavior, science-off byte identity, and no result JSON field widening.
3. Run the focused replication/science suite, full unit+architecture suite, static/import checks, UI tests/check/build, and the feature's real-store integration lane below. Fix feature-caused failures; do not lower coverage or remove unrelated assertions.
4. Run relevant pre-existing non-scale integration/Compose/browser/benchmark lanes only with their documented prerequisites and explicit valid disposable DB targets. Record actual execution in the implementation verification workflow; missing prerequisites remain unexecuted, not passed. No new capacity or stochastic-emergence benchmark claim is required by this plan.

### Required Interfaces and Contracts

Commands (run from repository root):

```bash
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_replication_*.py tests/architecture/test_replication_*.py tests/unit/test_scientific_hypotheses_*.py tests/architecture/test_scientific_hypotheses_*.py -q
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/unit/test_compatibility_matrix.py tests/unit/test_runner_config_v56.py tests/unit/test_v4_scaffolding_gate.py tests/unit/test_alembic_head_pin.py tests/unit/test_runner_finalization.py -q
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit tests/architecture -q
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src tests
uv run --frozen --python 3.12.14 lint-imports
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term -m integration tests/integration/test_replication_store_api.py -q
pnpm --dir clients/research-ui test
pnpm --dir clients/research-ui check
pnpm --dir clients/research-ui build
```

### Error Handling and Logging

Summarize command failures safely; never dump excluded artifacts, `.env`, DSNs or subjective payloads. Do not change dependency lockfiles or add packages unless an explicitly reviewed need arises; none is planned.

### Tests / Acceptance / Verification

All mandatory local commands pass with coverage enabled; original 250 metric algorithms/keys remain intact; new six families and all five requested replication dimensions are exercised. Env-gated lanes are truthfully distinguished. Use `$aif-verify` after implementation; this planning invocation does not run tests or start implementation.

## Phase Risks and Mitigations

- A deterministic fixture cannot honestly manufacture variable physical outcomes: use declared condition variation or attributed false testimony, preserving provenance.
- Documentation drift: update current pins only and describe the new subjective codec separately.
- Unexecuted operations gates: withhold broad certification, never relabel them successful.

## Phase Completion Checklist

- Tasks 25–28 satisfy real-world-boundary tests, documentation checkpoint and mandatory local gates.
- Progress is checked only in `index.md` after verification.
