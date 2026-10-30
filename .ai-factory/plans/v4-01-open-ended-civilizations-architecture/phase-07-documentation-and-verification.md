# Phase 7: Documentation and Verification

Plan: [index.md](index.md)
Tasks: 16-17
Depends on: Phase 6 (Tasks 14-15)

## Objective

Publish the V4 architecture, versioning, migration, and scale contracts as
first-party documentation, reconcile every stale statement that V4-01
supersedes, and certify the bundle and source with a final verification pass.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `README.md` | documentation index | V4 pages must be discoverable. |
| `docs/architecture.md` | "See Also" and downstream checklists | V4 seam link. |
| `docs/configuration.md` | lines 305-309 state there is no `runner-config-v56` | Must be replaced with the accepted-v56 scaffolding paragraph. |
| `docs/development.md` | command table (37-51); stale "migration head `0010`" at line 45 | Add V4 commands/env vars and correct the stale head. |
| `docs/persistence.md` | head `0017` rule (146, 155) | Link the migration sequence; keep the head pin. |
| `docs/long-horizon-scalability.md` | measured-envelope discipline | Link the V4 scale contract without adding a capacity claim. |
| `.ai-factory/ARCHITECTURE.md` | V3-44 seam (513-539), baseline table (179-193) | Add the V4-01 seam and keep the current pins. |
| `.ai-factory/DESCRIPTION.md` | V3-44 paragraph (167-182) | Add the V4-01 architecture paragraph. |
| `.ai-factory/ROADMAP.md` | M7 (95-116) | Read-only for this plan; M8 registration belongs to `$aif-roadmap`. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `docs/v4-architecture.md` | modify | Finalize the decision record from Task 2. |
| `docs/v4-versioning.md` | create | Version surfaces, compatibility, deprecation, reservations. |
| `docs/v4-migration-sequence.md` | create | Ordered stages, triggers, current head, authority impact. |
| `docs/v4-scale.md` | create | Partition/budget contracts, measurement lane, no capacity claim. |
| `docs/configuration.md` | modify | v56 scaffolding; remove the "no v56" claim. |
| `docs/development.md` | modify | New commands/env vars; fix the stale migration head. |
| `docs/architecture.md` | modify | V4 seam, context-map link, and scoped V3-36 pin sentence. |
| `docs/historical-contingency.md` | modify | Runner pin row: latest feature v55, accepted scaffolding v56. |
| `docs/simulation-runner.md` | modify | Accepted range v1-v56; V4 flags scaffolded/unowned. |
| `docs/research-api.md` | modify | Accepted versions and the refined `/version` non-goal. |
| `docs/persistence.md` | modify | Link the migration sequence; keep `0017`. |
| `docs/long-horizon-scalability.md` | modify | Link the scale contract; no new measured claim. |
| `README.md` | modify | Documentation index entries. |
| `.ai-factory/ARCHITECTURE.md` | modify | V4-01 seam section and current pin sentence. |
| `.ai-factory/DESCRIPTION.md` | modify | V4-01 architecture paragraph. |

## Task 16: Execute the mandatory documentation checkpoint

### Intent

Documentation is part of the V4-01 deliverable. The version policy, migration
sequence, and scale budget are only useful if a later implementer can find them,
and the old "there is no v56" statement would actively mislead.

### Implementation Steps

1. Create `docs/v4-versioning.md`:
   - Table of every surface: default runner write, latest feature runner,
     accepted runner range, runner result, event schema, codec, observer
     protocol, observer layout, metric catalog, Alembic head, commands, observer
     semantic types.
   - Rules: additive first; exact-key versions; accepted-set discipline; legacy
     decode preserved; a new write version co-lands admission, codec, replay,
     and tests.
   - Reserved write pairs from `V4_WRITE_PAIR_RESERVATIONS` and the rule that a
     reservation is not an implementation.
   - Observer negotiation: `/version` fields, advertised vs reserved
     capabilities, v1-only serving, when `observer-protocol-v2` may be served.
   - Deprecation window policy and the ban on silently widening an existing
     schema identifier.
2. Create `docs/v4-migration-sequence.md`:
   - The six stages from `V4_MIGRATION_SEQUENCE` in order, with trigger,
     prerequisites, owner, and authority impact.
   - Current state: head `0017`, no stage applied, `next_revision() == "0018"`.
   - Rule: a stage may be implemented only when its trigger is proven and its
     prerequisite flags are owned; V4-01 owns none.
3. Create `docs/v4-scale.md`:
   - Partition contract, namespace, budget fields, determinism rule, and the
     `PALIMPSEST_V4_SCALE_IDS` measurement lane.
   - Explicit statement: V4-01 measures partition mapping only; it makes no
     civilization-capacity or 10k/100k claim. Cite the existing V3 measured
     envelope link rather than restating numbers.
4. Update `docs/v4-architecture.md`:
   - Link the three new pages.
   - Add a "current implementation status" line: V4-01 scaffolding, no mechanics.
5. Update `docs/configuration.md`:
   - Replace the sentence "There is no `runner-config-v56`." with a paragraph:
     v56 is accepted only for the closed `v4_capability_flags` sibling; all flags
     are unowned and fail closed; default write remains v4; latest feature
     runner remains v55; no behavior or migration.
   - Keep the Experiment BM/v55 text otherwise unchanged.
6. Update `docs/development.md`:
   - Add the V4 scaffolding verification commands and the twelve-flag gate.
   - Document `PALIMPSEST_V4_SCALE_IDS`.
   - Fix the stale "migration head `0010`" reference to `0017`.
   - Add the Godot suite count expectation (48) and the Research UI commands.
7. Update `docs/architecture.md` `## See also` with the V4 architecture page, and
   add a short V4 boundary paragraph that points at the context registry.
8. Update `docs/persistence.md` with a link to `v4-migration-sequence.md` and an
   explicit "head remains `0017` in V4-01" sentence.
9. Update `docs/long-horizon-scalability.md` with a link to `v4-scale.md` and a
   statement that V4-01 adds no measured capacity.
10. Reconcile every current-tense V3 pin statement that V4-01 supersedes:
    - `docs/historical-contingency.md` runner pin row: replace
      "Latest `runner-config-v55`; no runner v56" with "Latest feature runner
      `runner-config-v55`; accepted scaffolding `runner-config-v56`".
    - `docs/architecture.md` V3-36 "current baseline" paragraph: append one
      sentence that V4-01 later accepts v56 and that the paragraph's "no v56"
      statement is scoped to V3-36.
    - `docs/simulation-runner.md`: change the accepted range to
      `runner-config-v1`…`v56`, state that v56 is accepted-only scaffolding, and
      add a short `V4CapabilityFlags` paragraph (default off, unowned, fail
      closed at construction).
    - `docs/research-api.md`: update the accepted runner range to
      `v1`…`v56`, and replace the `/version` non-goal with: V2/V3 kept the
      payload minimal; V4-01 advertises protocol/layout/capability metadata
      additively and still exposes no capability-flag values or configuration
      payloads.
    - `README.md` Simulation runner row: "V2/V3/V4 capability flags".
11. Update `README.md` documentation index with the four V4 pages, and correct
    the stale persistence head `(0010)` in the Experiments row to `(0017)`.
12. Update `.ai-factory/ARCHITECTURE.md`:
    - Add a `### V4-01 open-ended civilizations architecture seam` section
      describing the context registry, closed unowned flags, accepted v56,
      reservations, migration sequence, observer capabilities, and scale
      contracts.
    - State that V4-01 adds no command, event, observer semantic type, metric
      family, write-pair, API route, migration, or behavior.
    - Note that historical "no v56" sentences inside the V3 seam sections are
      scoped to those plans and are not current pins.
    - Keep the existing pin table unchanged.
13. Update `.ai-factory/DESCRIPTION.md` with one V4-01 paragraph after the V3-44
    paragraph. Do not edit `.ai-factory/ROADMAP.md`; record the provisional M8
    label in the plan only.
14. Run a relative-link check over every touched page and fix all broken links.
15. Verify the doc/registry parity test still passes after edits.

### Required Interfaces and Contracts

- Documentation uses English, preserves technical terms, and never promises
  emergent outcomes.
- Every version number in docs must match the executable pins.
- No new measured capacity, benchmark, or milestone-close claim.
- The roadmap remains owned by `$aif-roadmap`.

### Requirement Evidence

- Original Request: "Define: ... compatibility strategy, feature flags,
  migration sequence".
- `docs/configuration.md` stale v56 statement; `docs/development.md` stale head.
- `.ai-factory/ARCHITECTURE.md` versioned extension contract.

### Error Handling and Logging

- Documentation only; no runtime logging.
- Broken links and pin mismatches are failures.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_v4_context_registry.py tests/architecture/test_v4_architecture_invariants.py -q`
- Relative-link script over `README.md`, `docs/architecture.md`,
  `docs/configuration.md`, `docs/development.md`, `docs/persistence.md`,
  `docs/long-horizon-scalability.md`, `docs/historical-contingency.md`,
  `docs/simulation-runner.md`, `docs/research-api.md`, and the four V4 pages.
- `grep -rn "no runner v56" docs/` and
  `grep -rn "There is no runner-config-v56" docs/` return only explicitly
  scoped historical statements (none for configuration, simulation-runner,
  research-api, or the current architecture baseline).

### Acceptance Criteria

- All four V4 pages exist and are indexed.
- No page still asserts that `runner-config-v56` does not exist.
- All documented pins match code; 0 broken links.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_v4_context_registry.py -q`
- Link check exits 0.
- `grep -rn "no runner v56" docs/` and
  `grep -rn "There is no runner-config-v56" docs/` return no current-tense
  claim.

## Task 17: Perform final V4-01 verification

### Intent

Certify the bundle and the source with an explicit, reproducible final pass, and
state precisely what V4-01 does and does not claim.

### Implementation Steps

1. Bundle integrity:
   - Exactly one `<!-- aif:plan-mode:ultra -->` marker in `index.md`.
   - Every Phase Index link resolves to a direct child phase file.
   - Seventeen `## Task N` sections map one-to-one to the index checklist.
   - No phase file contains a checkbox; no orphan phase file exists.
   - Every dependency reference points to an existing task id.
   - Recompute the phase-link count and record it in the final summary.
2. Static gates on the final tree:
   - `uv run --frozen --python 3.12.14 ruff check src tests`
   - `uv run --frozen --python 3.12.14 mypy src tests`
   - `uv run --frozen --python 3.12.14 lint-imports`
   - `git diff --check`
3. Required test gates:
   - If Task 15 receipts exist and no code changed since their source digest,
     cite them with the digest delta and re-run only the default collection on
     the final tree.
   - If any code changed after Task 15, rerun the affected lanes from Task 15 in
     full. Documentation-only changes do not require a Compose rerun, but the
     final report must say so explicitly.
   - `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term --junitxml=<root>/final-default.xml`
4. Final source identity:
   - Record `git rev-parse HEAD`, `git status --porcelain`, and the deterministic
     tree digest.
   - Record the image identity only if a Compose lane was executed; otherwise
     state "image lane not re-executed; cited from Task 15".
5. Claim audit:
   - Confirm no V4 mechanic exists: grep for V4 flag reads outside the declared
     scaffolding files.
   - Confirm no V4 command/event/semantic/metric/migration/route was added.
   - Confirm no roadmap milestone was closed and no ML/LLM behavior changed.
   - Confirm the deferred items (`institutional_economy`,
     `multi_hop_testimony_tracking`, durable subjective resume, recorded/live
     LLM forks) remain deferred.
6. Write the final summary with: task count, bundle integrity result, static
   results, gate results with counts/skips, source digest, and explicit
   non-claims.
7. Only after all checks pass, mark Tasks 1-17 complete in `index.md`. If any
   check fails, leave the affected task unchecked and report the blocker.

### Required Interfaces and Contracts

- A skip is never counted as a required-gate pass.
- A required lane that cannot run leaves the task incomplete.
- No milestone closure, no capability ownership change, no behavior claim.
- The bundle remains the only task-progress source.

### Requirement Evidence

- Original Request: "Do not implement V4 social mechanics yet".
- `ULTRA-FORMAT.md` bundle integrity rules.

### Error Handling and Logging

- Report failures with the exact command, exit code, and first safe error line.
- Never paste private payloads or credentials into the summary.

### Tests

- The commands in Implementation Steps 2-3.

### Acceptance Criteria

- Bundle integrity passes with 17 tasks and 7 phases.
- Static and required test gates pass on the final source.
- The final summary states exactly what was verified and what remains deferred.

### Verification

- `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term`
- Expected: 0 failures; only explicitly documented opt-in skips remain.
- `git diff --check` exits 0.

## Phase Risks and Mitigations

- Risk: documentation drifts from code after the last code change.
  Mitigation: doc/registry parity is executable, and Task 17 runs it after all
  edits.
- Risk: a docs-only change is used to claim a full release certification.
  Mitigation: the final report separates code-source gates from documentation
  deltas and requires an explicit statement.
- Risk: the plan's provisional M8 label is mistaken for a roadmap edit.
  Mitigation: `.ai-factory/ROADMAP.md` is untouched; the summary names
  `$aif-roadmap` as the owner.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
