# Phase 6: Documentation, pins and verification handoff

Plan: [index.md](index.md)
Tasks: 21–24
Depends on: Tasks 1–20

## Objective

Document the scientific contract, retain truthful historical version information,
and close implementation only against executed checks and explicit limitations.

## Current-Code Evidence

| Path | Section / pattern | Why it matters |
| --- | --- | --- |
| `docs/scientific-hypotheses.md` | confidence, analysis, limits | Existing support ratios are not predictive calibration. |
| `docs/scientific-replication.md` | frozen designs and categorical uncertainty | Models deepen science without erasing replication semantics. |
| `docs/measurement-instruments.md` | display versus sampled truth, v57/pending v3 | Coexistence retains fallible instrument and replay semantics. |
| `docs/development.md`, `pyproject.toml` | verification and coverage | Exact commands and network-free default tests. |
| `.ai-factory/DESCRIPTION.md` | V4-29 current pins | Latest opt-in runner v57, 45 commands, 256 families before this plan. |
| `.ai-factory/ARCHITECTURE.md` | versioned extension table and V4-29 seam | Baseline replay table is stale relative to the measurement seam. |
| `.ai-factory/ROADMAP.md` | M8 scope and ownership | Link the work without claiming completion of remaining reserved contexts. |

## Files to Change

| Path | Action | Responsibility |
| --- | --- | --- |
| `docs/scientific-models.md` | create | End-to-end scientific-model contract. |
| `README.md`, `AGENTS.md` | modify | Documentation index entries only. |
| `docs/configuration.md`, `docs/development.md`, `docs/experiments.md`, `docs/research-ui.md`, `docs/persistence.md` | modify | Focused activation, checks, experiment, panel and codec sections. |
| `docs/scientific-hypotheses.md`, `docs/scientific-replication.md`, `docs/measurement-instruments.md`, `docs/architecture.md` | modify | Focused cross-links and current-seam clarification. |
| `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md` | modify during implementation | Current V4-30 context and accurate version/metric pins. |
| `tests/unit/test_scientific_models_pins.py` | create | Current catalog and unchanged command/protocol/ownership pins. |
| `tests/unit/test_measurement_pins.py`, `test_replication_pins.py`, `test_scientific_hypotheses_pins.py` | modify only where current-count assertions require | Preserve legacy fixture/schema assertions. |
| `tests/architecture/test_v4_architecture_invariants.py` | modify only where current-count assertions require | Keep authority and no-magic-actor assertions. |
| This bundle's `index.md` | modify during implementation | Progress and bounded verification results; no new bundle files. |

## Task 21: Complete the mandatory documentation checkpoint

### Implementation Steps

1. Invoke `$aif-docs` during implementation for the configured mandatory
   documentation checkpoint. Document the implemented contract in
   `docs/scientific-models.md`, not a new long README section.
2. Cover activation, model-hypothesis derivation, two candidate algorithms,
   exact probability/calibration/Brier formulas, issuance/commit/target/receipt
   chronology, source/model revisions, paired comparison and minimum samples.
3. Explicitly state: resource is observed net quantity change, production is a
   categorical existing experiment outcome, disease unavailable pending a real
   observable owned seam, and observations/predictive probabilities are not
   objective truth. Existing hypothesis confidence remains support ratio.
4. Document caps, pinned pending history, terminal retention/watermarks, missing
   versus zero, no action and right-censoring, science-off compatibility,
   pending v4/leaf v1, independent snapshot/store versions and programmatic
   publication. No full durable subjective restart or performance capacity claim.
   Include nested caps, reference-closed truncation, source lifecycle,
   composition-only result exports, artifact-run versus publication 404s,
   section-specific filters, signed-publication pinning and closed receipt states.
5. Add the eight routes, settings, safe errors, UI labels, off-gate arms and
   exact reproduction commands. Add focused cross-links in the listed docs,
   README and `AGENTS.md` documentation tables. Do not rewrite unrelated prose
   or historical feature landing records.

### Errors, Logging and Tests

Documentation examples must use safe placeholders, never credentials, live DSNs
or authoritative law dumps. Check every new internal link, route count, version
and command against implementation. No claim of superiority from one seed.

### Acceptance Criteria and Verification

Documentation distinguishes hypothesis support, predictive confidence,
calibration and observed performance, and accurately describes all limitations.

- `git diff --check`
- Manual cross-check of `docs/scientific-models.md` against Tasks 1–20 and
  route/client/schema definitions.
- Run any existing docs/pin checks discovered by relevant filename/symbol;
  do not introduce a new docs tool dependency.

## Task 22: Update current pins without rewriting historical contracts

### Implementation Steps

1. Add current V4-30 context to DESCRIPTION and ARCHITECTURE after implementation
   exists. Current metric catalog becomes 262; commands remain 45, observer
   semantic types 73, V4 contexts 17, flags 12 with nine owned/three unowned.
   Keep `v4-context-map-v6`; no new context or flag is added.
2. Default runner/result stay v4/v2; latest opt-in runner v57. Preserve accepted
   feature-selected result v3. Measurements select event28/v26, travel event27/v25,
   infrastructure event23/v21 and older active selections as before.
   Pending default remains v1; predictive candidates use v4 independently.
   Alembic stays `0017`; `/v1` and `observer-protocol-v1` remain stable.
3. Clarify stale current-baseline rows found during warmup only in current-context
   sections; do not globally replace historical 43-command or old family counts.
   Source landing records keep their dated meaning. No application schema
   changes are justified merely to make documentation counts uniform.
4. Add `test_scientific_models_pins.py` for the six-family suffix and unchanged
   surfaces. Update relevant current-catalog assertions discovered via focused
   symbol search; preserve the first 256 specification records exactly.
5. Route milestone registration/status notes through the roadmap owner workflow
   (`/aif-roadmap`, if available) or report a user handoff if unavailable.
   Do not directly close M8 or declare an unowned flag implemented.
   Planning itself does not modify source requirements or the roadmap.

### Errors, Logging and Tests

If implementation disproves an asserted pin, stop and reconcile explicitly;
never mask it by mass-replacing expected values. Metadata logs remain safe.

### Acceptance Criteria and Verification

Current-context artifacts agree on V4-30 pins while legacy accepted payloads
and dated historical counts remain intact.

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_scientific_models_pins.py tests/unit/test_measurement_pins.py tests/unit/test_replication_pins.py tests/unit/test_scientific_hypotheses_pins.py tests/unit/test_alembic_head_pin.py -q`

## Task 23: Execute the final regression and quality gates

### Implementation Steps

1. Run the focused suites from each phase, then the complete default Python
   suite with branch coverage. Fix only failures caused by this scope; record
   unrelated failures without discarding unfamiliar user changes.
2. Run full Ruff, strict mypy, import-linter and Research UI tests/check/build.
   Do not disable coverage, remove assertions, widen private imports, or lower
   security validation to obtain a green gate.
3. Run the two real filesystem/runner integration tests explicitly under the
   integration marker. Run relevant existing science/measurement recovery
   integration lanes if their prerequisites are available.
   Confirm immutable results, real collector/builder, all six families, actual
   app-factory attachment, two windows, old-publication cursor continuation and
   actual blank-slate probes are exercised. Route-only mocks/direct metric calls
   do not prove these seams.
4. Full PostgreSQL, Compose/browser, pinned Godot and scale/benchmark lanes are
   conditional certification lanes. Consult only the relevant development-doc
   sections at execution time. Execute where provisioned and record exact
   failure/skip prerequisites otherwise; no Godot change is required by V4-30.
5. Verify the complete user-request trace: structured models derive from
   hypotheses, predictions precede outcomes, confidence is explicit, observed
   results are preserved, calibration and revisions exist, and comparison uses
   identical eligible cases.

### Exact Verification Commands

- `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term -q`
- `uv run --frozen --python 3.12.14 ruff check src tests`
- `uv run --frozen --python 3.12.14 mypy src tests`
- `uv run --frozen --python 3.12.14 lint-imports`
- `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term -m integration tests/integration/test_scientific_models_runner.py tests/integration/test_scientific_models_store_api.py -q`
- `pnpm --dir clients/research-ui test`
- `pnpm --dir clients/research-ui check`
- `pnpm --dir clients/research-ui build`
- `git diff --check`

### Errors, Logging and Tests

Capture bounded summaries, counts and exit statuses, not full coverage dumps or
payload logs. Test failures remain failures; unavailable optional infrastructure
remains unexecuted. Disposable database safety is non-negotiable.

### Acceptance Criteria

All mandatory local gates pass; conditional lane status is explicit and no
certification claim exceeds the executed evidence.

## Task 24: Record implementation outcome and unresolved limitations

### Implementation Steps

1. Verify every Task N acceptance criterion and indexed dependency, then update
   task checkboxes only after its verification passes. Keep exactly one progress
   ledger in `index.md`.
2. Append a bounded `## Implementation Verification` section to the index with
   tested revision identifier, commands/status/counts, representative artifact
   identity, deterministic twin/recovery result and current limitations.
   Do not add `verification.md` or other orphan files to this ultra bundle.
3. Explicitly retain disease unavailability, net-resource-change confounding,
   categorical production scope, retained-cohort scoring, observation-selection
   limits, programmatic publication and any unexecuted browser/scale lanes.
4. Report implementation complete separately from full certification. Do not
   claim scientific discovery, truth, causal validity, improved performance,
   epidemic support, global model consensus or civilization capacity.
5. Stop and hand off to `$aif-verify` with this explicit bundle path. Do not
   auto-commit, push, create branches or begin unrelated remaining M8 work.

### Errors, Logging and Tests

An incomplete required task is left unchecked with a concrete blocker. A failed
mandatory gate cannot be described as passed. No extra logs or application
changes are needed for this record.

### Acceptance Criteria and Verification

The index is a truthful self-contained handoff: completed work, test evidence
and remaining limits are distinguishable and reproducible.

- Check task-to-phase mapping and that only the index has progress checkboxes.
- `git diff --check`
- Review the resulting implementation summary against executed command results.

## Phase Risks and Mitigations

- Stale summary counts can cause broad churn: touch current pins narrowly and
  leave dated feature narratives intact.
- Green local tests can be mistaken for release certification: separate
  mandatory and conditional evidence in the final record.
- Existing plan discovery is ambiguous on `main`: always pass the explicit
  `v4-30-scientific-models/index.md` path to downstream skills.

## Phase Completion Checklist

- Mandatory docs checkpoint, current pins and local quality gates are complete.
- Conditional evidence and limitations are recorded without overclaiming.
- Only `index.md` tracks task completion.
