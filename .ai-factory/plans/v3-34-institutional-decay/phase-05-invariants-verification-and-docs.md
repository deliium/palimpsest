# Phase 5: Invariants, verification and documentation

Plan: [index.md](index.md)
Tasks: 13–15
Depends on: Tasks 1–12

## Objective

Prove default-off compatibility, owner/privacy/authority isolation, honest lifecycle evidence, and reproducibility; publish the model and its limitations through the mandatory documentation checkpoint.

## Current-Code Evidence

| Path | Symbols / sections | Why it matters |
|---|---|---|
| `tests/architecture/test_v3_institution_emergence_analysis_only.py` | institution boundary tests | Analytical classifications cannot enter cognition. |
| `tests/architecture/test_v3_institutional_memory_isolation.py` | owner/input boundary tests | No shared institutional mind or objective event access. |
| `tests/unit/test_institutional_memory_invariants.py` | carrier loss, succession, owner separation | Existing learned-knowledge invariants must survive decay. |
| `tests/unit/test_v1_regression_gate.py` | canonical A–E/reference gate | Legacy experiment behavior remains executable. |
| `tests/unit/test_v2_scientific_invariants.py` | optional feature scientific gates | Default-off scientific boundaries remain enforced. |
| `docs/development.md` | verification commands | Pinned `uv run --frozen --python 3.12.14`; keep coverage enabled. |
| `.ai-factory/ARCHITECTURE.md` | versioned extension contract | Accepted-set schemas, read-only observer, no routine migration. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `tests/architecture/test_v3_institutional_decay_isolation.py` | create | Authority/import/owner/logging isolation. |
| `tests/unit/test_institutional_decay_invariants.py` | create | Deterministic properties and default-off parity. |
| `tests/unit/test_institutional_decay_runtime.py` | modify | Representative behavior/failure/recovery assertions. |
| `tests/unit/test_institution_lineage.py` | modify | High-water/prefix and graph properties. |
| `tests/unit/test_compatibility_matrix.py` | modify | Final accepted/write identities. |
| `docs/institutional-decay.md` | create | Model, algorithms, coverage, lineage and limitations. |
| `README.md` | modify | Add one documentation index entry only. |
| `docs/configuration.md` | modify | v54 exact keys/prerequisites/combinations and profiles. |
| `docs/architecture.md` | modify | New subjective seam versus detached lifecycle analysis. |
| `docs/experiments.md` | modify | BK arms and neutral outcomes. |
| `docs/analysis-metrics.md` | modify | Three new metric families, thresholds and denominators. |
| `docs/development.md` | modify | Focused verification commands and unchanged pins. |
| `docs/institutional-memory.md` | modify | v54 profile acceptance and knowledge-retention clarification. |
| `.ai-factory/DESCRIPTION.md` | modify during implementation completion | Concise V3-34 baseline update, not historical section rewrites. |
| `.ai-factory/ARCHITECTURE.md` | modify during implementation completion | Latest feature version/129-family baseline and new seam. |

## Task 13: Add isolation and scientific invariant gates

### Intent

Make the most tempting shortcuts executable failures: analysis-as-truth, hidden populations-as-zero, carrier loss-as-forgetting and scripted collapse.

### Implementation Steps

1. Add architecture checks modeled on institution-memory isolation: cognition decay module signatures/imports must not accept `WorldState`, engine/snapshots, `WorldEvent`, event repositories, metric/lifecycle documents, cross-owner batches or outer adapters. Analysis modules import no cognition/persistence/API; simulation imports no analysis/experiments/observer. Cross-package imports use declared public facades/submodules.
2. Add forbidden-field/type checks for objective institution registries, predefined institution types and collapse commands/events. Keep the test scoped to new surfaces rather than banning harmless documentation/negative assertions across the repository.
3. Property-test same-owner input determinism, unrelated hidden-agent noninterference, input ordering, independent-channel attrition, bounded finite strengths, cap determinism, no cross-owner/newborn content transfer, and snapshot detachment. Trace actual runtime carry through `build_perspective` and `Perspective.to_snapshot`, including foreign-owner and disabled-None boundaries; a hand-built snapshot is not sufficient. Test a foreign owner's record mutation cannot change this owner's output.
4. Prove carrier disappearance does not delete learned facts; office vacancy/abandonment is not inferred from lack of visibility; no successor obtains knowledge without reading/delivery; hidden/dead observers create unknown/censored data rather than zero support/collapse.
5. Prove enabled histories/graphs are prefix-causal: computing as of tick T never uses later evidence; future evidence cannot retroactively make an earlier transformation/collapse confirmed at T. Under equivalent retained evidence, surviving node IDs remain identical before/after sample eviction and checkpoint restore. Pruned predecessor stubs cannot prove a formerly stable/collapsed state or exact knowledge handoff; unrelated old pruning does not censor a newly complete window forever. Missing early evidence may legitimately change availability, never renumber surviving episodes or invent an emergence at the ring-buffer start.
6. Capture logs through cap/error/update/analysis paths with payload sentinels. Allow only IDs needed for safe operation, ticks, modes, policy versions, counts and reason codes; reject prompts, labels, claim content, source/anchor/root fingerprints and graph/sample dumps.

### Required Interfaces and Contracts

No objective authority or economic capability ownership is added. The new sidecar is private owner state. Retrospective causal context is descriptive and cannot influence live agent choices.

### Requirement Evidence

Root `AGENTS.md`; project axioms; architecture authority/dependency/privacy rules; user no-scripted-collapse requirement; institutional-memory retention and office availability constraints.

### Error Handling and Logging

Tests assert safe reason codes and no payload-bearing errors. Incomplete evidence is a valid result, not an exception to be bypassed with a guessed institution state.

### Tests

`test_v3_institutional_decay_isolation.py`, `test_institutional_decay_invariants.py`, and prefix/graph properties in `test_institution_lineage.py`. Use deterministic fakes and Hypothesis with coverage enabled; no network, Docker or PostgreSQL.

### Acceptance Criteria

Every listed prohibited shortcut has an executable regression check. Legitimate empty, contradictory and censored outcomes remain accepted.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/architecture/test_v3_institutional_decay_isolation.py tests/unit/test_institutional_decay_invariants.py tests/unit/test_institution_lineage.py -q`

Expected: isolation, logging and property tests pass.

## Task 14: Verify representative continuation and legacy compatibility

### Intent

Demonstrate the whole feature on genuine existing experiment/runner composition, not merely synthetic numerical fixtures.

### Implementation Steps

1. Use the real BJ-derived BK record/teaching configuration to execute normal `SimulationRunner` with deterministic fakes. Check source receipt → concept update → sidecar commit → next invocation's `build_perspective`/`Perspective.to_snapshot` → runtime checkpoint/export → raw composition → one window aggregation → lifecycle/lineage → scalar metric documents → actual encode/decode with parsed JSON-string payloads. Assert coverage/native provenance, not mandatory collapse. Separately demonstrate empty-ledger shared-upkeep recognition → weakening → renewed recognition via the public update/loop path; no preconstructed recognized concept may stand in for reachability.
2. Compare uninterrupted and real checkpoint-export/apply continuation for commands, adjusted concepts, raw samples, receipts, absolute identity witnesses and metric fingerprints at equal evidence high-water. Include a failed prepare/finalization case, terminated owner and 16-pattern sample-eviction boundary. Assert surviving episode IDs are unchanged, predecessor loss becomes an explicit stub, known-answer ratios are not twice-windowed, and the old pruning counter does not poison a new complete interval. State clearly that runtime continuation is being verified, not newly claiming durable restart of every subjective store.
3. Run explicit off-path parity: default configs retain v4; v49–v53 exact keys/selection and disabled cognition fingerprints remain unchanged; BJ arms and existing institution/office/memory behavior retain their prior values. New absent catalog documents are the only expected metric bundle membership addition.
4. Run compatibility, V1 gate, V2 scientific invariants and existing institution/office/memory suites, then whole default pytest, Ruff, mypy and import-linter. Fix failures caused by this feature; report unrelated existing failures without altering unrelated user code or suppressing coverage.
5. Confirm unchanged command/observer counts, selected replay/codec pairs, migration head 0017, API/protocol identity, `prepare_parallel=False`, and fail-closed `institutional_economy`/`multi_hop_testimony_tracking`. Confirm no lockfile/dependency changes are needed.

### Required Interfaces and Contracts

Testing remains network-free by default. No integration database is required; if an independently justified DB check is later added, existing disposable `palimpsest_test` constraints apply. Do not add migration 0018 or widen wire result schemas just to make a test pass.

### Requirement Evidence

Architecture versioned extension/regression gates; `docs/development.md` commands; index supported combinations; representative BJ/BK evidence path.

### Error Handling and Logging

Record failures with command, safe output summary and scope. Do not hide failures by regenerating historical goldens, disabling coverage or weakening isolation tests.

### Tests and Verification

Run in this order, with the project's normal coverage settings:

1. `uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_decay_contracts.py tests/unit/test_runner_config_v54.py tests/unit/test_institutional_decay_updates.py tests/unit/test_institutional_decay_runtime.py tests/unit/test_institutional_decay_checkpoints.py tests/unit/test_institutional_decay_analysis.py tests/unit/test_institution_lineage.py tests/unit/test_institutional_decay_composition.py tests/unit/test_institutional_decay_metrics.py tests/unit/test_experiment_bk.py tests/unit/test_institutional_decay_invariants.py -q`
2. `uv run --frozen --python 3.12.14 pytest tests/unit/test_runner_config_v53.py tests/unit/test_experiment_bj.py tests/unit/test_compatibility_matrix.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/unit/test_alembic_head_pin.py tests/architecture -q`
3. `uv run --frozen --python 3.12.14 pytest`
4. `uv run --frozen --python 3.12.14 ruff check src tests`
5. `uv run --frozen --python 3.12.14 mypy src tests`
6. `uv run --frozen --python 3.12.14 lint-imports`

### Acceptance Criteria

All feature tests, compatibility/scientific/architecture gates, default full tests and static checks pass, or unrelated pre-existing failures are explicitly reported with evidence. The actual runtime-to-collector path and checkpoint continuation are tested. No required feature regression is waived.

## Task 15: Complete mandatory documentation and context checkpoint

### Intent

Publish exactly what weakens, what is only analytical, how lineage is inferred, and what the model cannot claim. Do not present thresholds as objective laws of institutional death.

### Implementation Steps

1. Invoke `$aif-docs` for the mandatory documentation checkpoint. Add `docs/institutional-decay.md` as the canonical page, with a concise link in README's documentation index.
2. Document v54 exact cognition keyset/prerequisite matrix and disabled parity; six strengths versus five dimensions; native shared-source binding and cold-start recognition; raw per-update evidence and **one** four-observation-tick aggregation; stable observed-cohort denominators/common-cohort comparisons, native source versus observation timing, 0.04 channel loss and analytical hysteresis. Explain interval-local pruning and one-update office/memory lag. Include exact known-answer ratio examples and illustrative stability→weakening→collapse and return timelines, not scripted runtime events.
3. Document transformation/split matching, absolute inception/activity/revision-based episode IDs (no sliding-history ordinal), continuation edges, ambiguous matches, explicit predecessor stubs, cross-owner dissent and actual knowledge handoff versus testimony. State the bounded-horizon limit: identity references may survive while full former lifecycle evidence is unavailable. Explain the four versioned canonical JSON-string research fields, scalar-only metric summaries and actual codec roundtrips without a shared-schema change. Show parent/child graph examples; label/occupant/anchor growth is not automatically transformation.
4. Document all eight potential mechanism associations and their limits: resource/population/record context remains detached, no shock schedule is added, record loss does not erase acquired knowledge, and end of observation is censoring. BK opportunity arms may produce no stable institution or collapse.
5. Update configuration, architecture, experiments, analysis metrics, development commands and institutional-memory profile acceptance at their named paths. Update DESCRIPTION/AI architecture current baseline to v54/129 families and add a concise V3-34 seam; preserve historical pins and sections as dated history. Do not rewrite the user request or source requirements.
6. Keep roadmap linkage to existing M7; this feature does **not** close M7 or own `institutional_economy`. If a milestone progress entry is desired, route it through `$aif-roadmap` per project rules; do not create/close roadmap milestones in the docs checkpoint. This planning invocation changes no roadmap file.
7. Verify all new README/docs links, commands, mode spellings, thresholds and count pins against implemented tests. Finish with a limitations statement: runtime continuation is supported, but no new durable institution registry/subjective database/restart guarantee is introduced; no client visualization or API endpoint is part of this plan.

### Required Interfaces and Contracts

English artifacts, preserved technical terms; tests/docs required, verbose metadata-only logging. Canonical plan remains under `v3-34-institutional-decay/`. Only the plan index owns progress checkboxes.

### Requirement Evidence

Configured mandatory docs policy; architecture roadmap ownership rule; user original request; implemented contracts and verification from Tasks 1–14. Historical source count discrepancies are dated explicitly, not silently flattened.

### Error Handling and Logging

Missing evidence/failed commands must be documented accurately; do not publish false success or claim every seed demonstrates collapse. No payloads in example operational logs.

### Tests

Documentation link/manual consistency review plus the feature/config/metric tests already named. No new documentation-only test framework or dependency.

### Acceptance Criteria

Mandatory `$aif-docs` checkpoint completed, all entry links resolve, configuration and metrics match implemented contracts, null/censored outcomes and inference limits are explicit. M7 remains open.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_runner_config_v54.py tests/unit/test_metric_specifications.py tests/unit/test_experiment_bk.py -q`

Manually verify the README index entry and all links in `docs/institutional-decay.md`; compare documented constants to policy/spec tests. Expected: passing tests, valid links and no contradictory current pins.

## Phase Risks and Mitigations

- Large suite execution may expose unrelated failures: retain exact commands and scope, do not weaken the gates or claim unrun checks passed.
- Research prose can overclaim collapse/causality: label scope, confirmation, coverage and descriptive associations throughout.
- Context baseline drift: update current V3-34 pins only during verified implementation completion, not in this planning invocation.

## Phase Completion Checklist

- Tasks 13–15 meet their acceptance criteria and verification is recorded.
- Documentation checkpoint is complete; no milestone or capability is falsely marked complete.
- Update progress only in `index.md` after verification.
