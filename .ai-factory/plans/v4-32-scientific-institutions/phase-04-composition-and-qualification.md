# Phase 4: Qualify real composition and document the evidence limits

Plan: [index.md](index.md)  
Tasks: 10–12  
Depends on: Phases 1–3

## Objective

Show existing agent-mediated mechanisms can sustain institutional practice without injecting a scientific institution, and separate controlled mechanism evidence from autonomous observations.

## Current-Code Evidence

| Path | Existing seam |
|---|---|
| `src/experiments/scientific_models_scenario.py` and `src/experiments/competing_theories_scenario.py` | `scientific_models_scenario`, accepted v56/v57 science fixtures, seed and finite stop controls |
| `src/experiments/catalog.py` | `experiment_competing_theories` off-gate factory pattern |
| `src/simulation/runner.py` | `run_tick`, `finish_run`, `set_intervention_arbiter`, `export_finalized_research_boundary` |
| `tests/integration/test_competing_theories_runner.py` | Real in-memory runner through filesystem and authorized API |
| `docs/development.md` | Frozen Python, coverage-enabled gates, optional external lanes |

## Files to Change

| Path | Action | Responsibility |
|---|---|---|
| `src/experiments/scientific_institutions_scenario.py`, `src/experiments/scientific_institutions_capture.py` | Create | Declared opportunities and explicit bounded runner driver |
| `src/experiments/catalog.py` | Modify | Off-gate experiment factory |
| `tests/unit/test_scientific_institutions_scenario.py`, `tests/integration/test_scientific_institutions_runner.py` | Create | Existing runner compatibility and end-to-end qualification |
| `tests/architecture/test_scientific_institutions_boundaries.py` | Create | Import, type, write-authority and compatibility gates |
| `README.md`, `docs/scientific-institutions.md`, `docs/configuration.md`, `docs/development.md` | Add/update through docs checkpoint | User-facing behavior, operational contract and commands |

## Task 10: Compose a bounded experiment without seeding institutions

1. Define off-gate `scientific_institutions@1`, a 96-tick explicit seed-matrix scenario. Reuse `scientific_models_scenario`’s v56 production and v57 measurement-coexistence configurations, physical rules and safe bounded law. Add existing cultural provenance, durable records, repositories and collective-project specs through their validated config factories; enable deterministic communication and teaching on the same founders, and `organizations` alongside `science`. Keep initialization content-empty; no seeded roles, theory, mandates, experiment reports, organization identity or archive contents. Generic physical opportunities (materials, tools, and places) are permissible. Choose the archive lane by existing `knowledge_repositories` spec, not by a new flag.
2. Register `experiment_scientific_institutions` using the adjacent catalog factory conventions; no change to A–E or default scenario selection. Conditions: `institutions-combined-v56` (base required channels), `institutions-org-off` (matched v56 but `organizations=False`, still runs science), `institutions-science-off` (matched v56 but `science=False`, bounded experimentation may still generate physical receipts), `institutions-instruments-v57` (combined configuration plus the existing instrument spec). Paired within a schema where layouts are identical; treat v57 tool availability as a declared coexistence opportunity, not an inferred causal contrast. Optional disabled coverage is unavailable, not negative evidence.
3. Add `run_with_scientific_institution_capture` in the new capture module. Use `initialize_finalized_boundary`, then the same `run_tick` stop/abort/max-tick rules as `SimulationRunner.run`. Capture the tick-zero baseline from Task 2 and export nonterminal full windows before the next tick. At successful termination call `finish_run` once with its real stop reason **before** exporting a full terminal endpoint: `runner._detached_boundary_inputs(allow_terminal=True)` rejects a terminal receipt without a finished result. No second `run_tick` after stopping; no success publication on an aborted, failed or cancelled run. Catch capture failures only around capture, not around execution/finish or process cancellation. Check cheap tick/owner/event bounds before the rich export, strip it immediately and drop raw references. Return a typed result, coverage status and detached material; the caller can invoke Task 7 explicitly. No runtime sink or automatic publication. Test that disabled/unsupported capture performs no rich exports and leaves scientific execution unchanged.
4. INFO record experiment ID, condition and number of captured boundaries; DEBUG caps and detached row counts; no raw config, law payload, marks or owner data.

**Acceptance and tests:** `test_scientific_institutions_scenario.py` builds all configs via existing validators and asserts flags, schemas, empty initialization, fixed horizon, determinism, and no A–E registration. Assert capture at 0/32/64/96, including `finish_run` ordering at exactly 96; test a partial terminal tail, failed/cancelled run, capture-error and no-capture parity, and unsupported configuration without rich exports. Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_scientific_institutions_scenario.py -q`.

## Task 11: Qualify controlled and autonomous runs

1. Reuse Task 3's controlled fixture in `test_scientific_institutions_runner.py`. Use the existing intervention-arbiter seam with a declared command schedule (no checkpoint or ledger edits). In a shelter-free site start `SHARED_SHELTER` with two agents holding one eligible wood item and one tool each; use `CollectiveProjectsSpec(idle_ticks=64)`, because the default is four ticks. Keep exactly one accepted wood contribution per window so the project stays open (three labor required), from the actor who subsequently performs that window's execution and carrier service. Window 0: contribute, `Inscribe` the durable record and execute `vary_process`/`harvest`; window 1: the second actor contributes, performs the same activity key and `AnnotateRecord`s the same artifact. Provision an ordinary annotation access path and verify admission before asserting context; reserve observation ticks after these acts. Retain actual `ProjectCreated` and artifact IDs from committed receipts; do not count the opening actor's zero-labor starter or re-observed contributions as fresh `ProjectContributed`. Assert owner provenance and exact carrier/actor joins before asserting stability. A separate admitted deposit/retrieval fixture verifies archive context; do not count a retrieval that removes the member as surviving archive custody. No injected beliefs or bypass of physical admission.
2. Assert real-run evidence → analysis → digest → filesystem → authorized GET for stable practice. For live controlled capture, include a complete-empty or unsupported continuation and verify it differs from a dropped capture endpoint. Qualify lineage split/merge/succession on detached fixture rows in Task 5; do not claim the controlled world produced an institutional split or succession unless receipts establish it.
3. Execute the unassisted three v56 arms and v57 coexistence using at least one predeclared shared seed in this focused integration; assert completed/explicitly unavailable outcomes, deterministic twins for the combined arm and unchanged config/replay/checkpoints from capture. Autonomous stable count may be zero. No scripted command substitution in the autonomous lane. Test `science=False` or `organizations=False` as unsupported analysis even if some similar objective activity occurs. Add one quick constructed run using an existing competing-theory scenario config as compatibility input; absent durable prerequisites must cleanly report unavailable rather than upgrading schema or producing a zero. Optional broader multi-seed reports remain descriptive, not qualification requirements.
4. Debug record lane, comparison and result/coverage codes; never substitute a green log for an executed check. Capture state is not part of replay hash or stop policy.

**Acceptance and tests:** `uv run --frozen --python 3.12.14 pytest -q -m integration tests/integration/test_scientific_institutions_runner.py` passes without PostgreSQL. The positive controlled proof cannot be replaced with synthetic owner ledgers or a test that accepts either a positive or a null. An autonomous null does not fail the test.

## Task 12: Land authority gates and contributor documentation

1. Assert via `test_scientific_institutions_boundaries.py` that cognition, world, observer and clients cannot import analysis or publish snapshots; API uses only ports/adapters, and no new command, capability, semantic event, replay pair, SQL migration, pending or runner codec, client mutation, or predefined University/Academy class appears. Verify 271 metrics is the only intended catalog change, plus the separate read artifact/store versions. Update only current-catalog assertions affected by the append; retain historical and legacy pins.
2. Route docs through `$aif-docs` at the mandatory checkpoint. Explain existing ways to observe and sustain roles, procedures, records/archive, teaching, replication and instrument use; why co-occurrence is not causal or proof that a given record contains a given result; exact stability, gap and lineage rules; limits and output fields; dual settings and auth; how to run explicitly; and what controlled vs autonomous lanes establish. Archive may retain opaque written procedural memory but no automatic `rep_v1`/`msr_v1` recovery or authority is added. No operator logs in docs except safe examples. Roadmap closes only through the owner workflow, not this plan.
3. Before final verification, confirm each named task test exists and is collected (the broad suite does not prove omitted tests). Run `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit tests/architecture -q`, the focused integration command, `uv run --frozen --python 3.12.14 ruff check src tests`, `uv run --frozen --python 3.12.14 mypy src tests`, `uv run --frozen --python 3.12.14 lint-imports`, and the three Research UI commands in Task 9 on final edits. Confirm V1 and V2 scientific-invariant gates remain included. Environment-gated Compose/browser, Godot or long horizon lanes may be unexecuted; document as such, with no certification or capacity claim.

## Phase Risks and Mitigations

- Stable positive may be sensitive to organization-grounding timings. Use the typed committed action and post-action owner evidence as fixture assertions; do not relax the detector or seed a scientific organization.
- Regression evidence may be mistaken for an emergence result. Keep controlled and autonomous receipts explicitly separate.
