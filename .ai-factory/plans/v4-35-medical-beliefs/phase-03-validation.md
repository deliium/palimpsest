# Phase 3: Tracking, experiment and release gates

Plan: [index.md](index.md)
Tasks: 5–6
Depends on: Phase 2

## Objective

Provide explicit research tracking and demonstrate that a practice with no modeled treatment effect can persist and travel socially.

## Current-Code Evidence

| Path | Symbols | Why it matters |
|---|---|---|
| `src/simulation/runner_models.py` | `FinalizedTickReceipt`, `ActionResolutionEvidence` | Researcher-visible committed command status |
| `src/simulation/runner.py` | `finish_run`, `export_competing_theory_ledgers` | Finalized owner ledger export precedent |
| `src/experiments/science_diffusion_capture.py` | `run_with_science_diffusion_capture` | Opt-in capture with truthful availability |
| `src/experiments/{catalog,disease_scenario}.py` | `OFF_GATE_MATRIX_EXPERIMENT_IDS`, `experiment_disease_mechanics`, `disease_mechanics_scenario` | Checked-in representative fixture and off-gate registration |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/simulation/runner.py` | modify | Detached terminal ledger export |
| `src/experiments/{medical_beliefs_capture,medical_beliefs_scenario}.py` | create | Bounded, opt-in capture and paired fixture |
| `src/experiments/{catalog,__init__}.py` | modify | Register and expose `medical_beliefs@1` |
| `tests/unit/test_medical_beliefs_{capture,scenario}.py`, `tests/architecture/test_medical_beliefs_boundaries.py` | create | Capture, paired trajectory, social persistence and authority assertions |
| `docs/medical-beliefs.md`, `README.md`, `AGENTS.md`, `docs/{configuration,disease-mechanics}.md`, `.ai-factory/{DESCRIPTION,ARCHITECTURE}.md` | create/modify | Documentation checkpoint, links, updated contract pins |

## Task 5: Export detached evidence and register the paired experiment

### Implementation Steps

1. Add `SimulationRunner.export_medical_belief_ledgers()` using the owner-export precedent. Order registration IDs before reading any checkpoints, take at most 128, and return expected count and any selected IDs with unavailable state alongside typed ledgers. Read medical sidecars directly from active or retained runtime state, not by freezing or exporting every owner. An intentionally uninvoked owner with an initialized empty ledger is distinguishable from unavailable state. A new experiments-only `run_with_medical_beliefs_capture(runner, *, capture=False)` snapshots the starting engine tick and runner cursor, then calls ordinary `run()` once. After `finish_run`, return a `MedicalBeliefsCaptureResult(result, status, evidence, reason_codes)` with evidence schema tag `medical-beliefs-evidence-v1`. Do not change result-document JSON or install a live sink.
2. An explicit active capture is `complete` only if the run finished at a finalized boundary with no coverage gap. A terminal `ABORTED` attempt, or a final engine/runner tick mismatch, is `unavailable` with a closed reason and no evidence: `run()` can still return a result after abort. Off and capture-disabled are also `unavailable`, with separate reason codes. An intact result with omitted/missing owners, capped roots, truncated history, nonzero starting engine tick or runner cursor, or missing attempt receipts is `partial`; leave missing records absent, not zero. Use `capture_failed` only for an exception in the capture path or invalid evidence, never catch or relabel a failure of `runner.run()`. Log safe codes, counts and run identity only. Return sorted immutable evidence; no SQL, HTTP, clients or global metric registry.
3. Preserve the lanes `belief`, `attempt`, owner-observed cue `outcome` (including unknown or open), `interpretation`, and receiver `transmission`. Separately join objective resolutions using `(owner, tick, effective command kind)`. Prebuild the bounded key set from retained attempts, then scan `result.finalized_tick_receipts` once, storing only exact matches for those keys; do not create an index over the whole run. A unique match preserves exact application status and request ref; none is `unknown`; duplicate matches for a retained attempt are `capture_failed`. `APPLIED` indicates ordinary command application, not physical arrival, a net state delta, or relief from the cue. Existing command rules govern fatigue, movement and waiting; capture never derives a treatment effect from a change of cue.
4. Add `medical_beliefs_scenario(base, *, seed_matrix=None)` and `experiment_medical_beliefs`, exposing `medical_beliefs@1` in the off-gate catalog. Take the existing `contact-enabled` `disease_mechanics_scenario` config verbatim as the paired base, keep its seeds and horizon and normal Wait fallback; `beliefs-off` remains v58, `beliefs-on` differs only by v59 and its spec. Reuse the existing catalog’s factory resolution path and do not add new matrix factor support. Prefix published/exported concepts with `medical-beliefs`; never reclassify the V4-34 experiment.

### Tests and verification

In `tests/unit/test_medical_beliefs_capture.py`, exercise opt-out, off, complete, partial, terminal abort returned as a result, raised run failure, capture-only failure, and bounded owner reads. Cover exact applied/rejected/missing/duplicate matches (including unrelated receipts), open attempts and received-vs-proposed distinctions. Assert capture/no-capture twins have identical objective histories and committed owner state. In `tests/unit/test_medical_beliefs_scenario.py`, use the repository disease scenario builder as the representative artifact; compare configs, gates and deterministic twins, and assert both runs keep the disease replay pair. Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_medical_beliefs_capture.py tests/unit/test_medical_beliefs_scenario.py tests/unit/test_disease_scenario.py -q`. Acceptance: offline evidence never becomes a live input or claims medical efficacy.

## Task 6: Prove social persistence and document the boundary

### Implementation Steps

1. Add a controlled composition test in `tests/unit/test_medical_beliefs_scenario.py`, separate from the unchanged paired experiment. Derive a test-only variant of its `contact-enabled` configuration: place C with A and B, and put one ordinary visible `InformationArtifact` at that location using the artifact test fixture pattern. Keep the existing fictional disease policy unchanged. Use a test-only `Planner.plan` wrapper (delegate to deterministic baseline then replace just the command for the scripted owners/ticks), not an arbiter override or a fake medical result. Script A to deliver one valid cultural `ritual_pause` root to B on the first ordinary tick; leave B's baseline at `Wait` until B's first actual `unwell` observation, then propose baseline `Talk(B→C)` on B's next observation. Derive those checkpoints from the public owner observation passed to the test planner, not from any engine disease state. Require consecutive cue observations as a fixture assertion. B's onset artifact association and received testimony provide support. Assert bound and applied marked `Wait` at onset, `not_obviously_helped` at follow-up, an ordinary committed B→C delivery with the same declared root and negative outlook, and a receiver-side C row tied to that event. Test baseline `Wait` is not a ritual in the paired mode-off arm. Synthetic cue timelines remain unit-test-only; no paired-run prevalence or autonomous emergence claim.
2. In `tests/architecture/test_medical_beliefs_boundaries.py`, lock out imports of world disease internals, event stores and detached analytics in cognition; assert no new engine, observer, API or persistence schema mutation, and unchanged mode-off command/RNG path. Run existing replay/perception/redaction checks unchanged. Add no `truth`, diagnosis, patient classification, real treatment model, dosage, or new exposure/transmission policy.
3. At the mandatory `$aif-docs` checkpoint add `docs/medical-beliefs.md`, configuration and disease-mechanics cross-links, README and AGENTS index entries; update `.ai-factory/DESCRIPTION.md` and `.ai-factory/ARCHITECTURE.md` pins (latest runner v59, pending v6, 45 commands / 73 observer semantics / 275 metrics, event 24/`v22`, defaults v4/v2, `/v1`, observer protocol and Alembic unchanged). Distinguish objective application from cue and interpretation; document retention, no-capture default, opt-in example, controlled result limits and no real-world efficacy claims. Leave roadmap ownership with `$aif-roadmap`; M8 does not close.

### Error handling, tests and verification

Keep expected rejected actions and captured uncertainty typed, never exceptions with private payloads. Run from repo root:

```sh
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_medical_beliefs_*.py tests/unit/test_disease_*.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/architecture/test_medical_beliefs_boundaries.py tests/architecture/test_disease_boundaries.py tests/architecture/test_v4_architecture_invariants.py -q
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit tests/architecture -q
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src tests
uv run --frozen --python 3.12.14 lint-imports
```

Run the disposable-DB disease durability lane (`tests/integration/test_disease_durable_replay.py`) when its configured `palimpsest_test` database is available; otherwise record it as unexecuted. Record measured results and distinguish environmental limitations from passing tests. Acceptance: actual relay after a negative outcome, replay and owner redaction unchanged, docs cross-links valid and settings explicit.

## Phase Risks and Mitigations

- Survivorship or retention bias: report partial evidence, no inference from omitted owners or missing receipts.
- Guaranteed social adoption would script emergence: fixture proves the mechanism; paired experiment reports what occurred and retains nulls.

## Phase Completion Checklist

- Bounded recording and paired experiment pass without changing engine or observer behavior.
- Coverage-enabled regression and static gates are recorded, and docs checkpoint is complete.
- Update only the verified tasks in `index.md`.
