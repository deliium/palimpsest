<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-41 Collapse and Recovery

Mode: ultra
Branch: main
Created: 2026-11-25

## Original Request

v4-41 collapse dynamics

Naming requirement:

Use `v4-41-collapse-recovery`.

Do not create a CivilizationCollapsed boolean as the causal mechanism.

Define analytical collapse indicators from combinations of:

- population decline
    
- institutional failure
    
- knowledge loss
    
- trade disruption
    
- infrastructure decay
    
- migration
    
- conflict
    
- production decline
    

Allow:

recovery  
fragmentation  
successor societies  
institutional continuity  
technology loss

Track lineage across societal fragmentation.

## Settings

- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"  
Rationale: V4-41 is detached M8 research composition, adjacent to V4-40; it adds no world or societal authority and does not close M8.

## Requirements Reconciliation

Authority: The Original Request controls feature scope. `.ai-factory/RULES.md`, `.ai-factory/rules/base.md`, `AGENTS.md` and `.ai-factory/ARCHITECTURE.md` govern boundaries. `.ai-factory/ROADMAP.md` identifies milestone scope; its historical pins do not supersede the V4-40 baseline. Existing code controls what constitutes positive evidence. No separate research requirements source is active.

| Decision / supported combination | Source | Verification evidence |
|---|---|---|
| Combine eight transparent dimensions in a sustained rule; single-axis stress and missing evidence cannot confirm collapse; no world boolean, scalar score or causal diagnosis. | Original Request; `.ai-factory/ARCHITECTURE.md` — Key Principles, V4-40 seam | Per-axis, group, baseline, missingness and prefix tests (3–4). |
| Capture off, supported on without a shock, and supported on with an actual shock preserve the same respective trajectories; unsupported or failed capture must not steer execution. | `.ai-factory/ARCHITECTURE.md` — Versioned Extension Contract; `docs/societal-resilience.md` — Programmatic capture | Real v63 fixture, no-disasters control, and injected failure parity (2, 8). |
| Recovery is possible on observed evidence but not assumed after a gap; fragmentation, successor continuity and technology loss are independent of collapse/recovery. | Original Request; `src/analysis/resilience_social.py`; `src/analysis/macro_society_detection.py` | Recovery, ongoing/censored, split/merge without collapse and collapse without split, continuity and technique loss tests (3–6). |
| Successors use contemporaneous, qualified overlap and a forward-only graph. Ambiguous overlap stays visible even if it masks every possible link. Sustained branch-local technique absence requires two verified continuation windows, not absence at a split endpoint. | Original Request; `.ai-factory/ARCHITECTURE.md` — Objective authority and runtime; `src/analysis/macro_society_lineage.py` | Unequal split, multi-step lineage, all links masked, sibling retention, missing middle, and scoped-link fixtures (5–6). |
| Institutional lapse and technology loss are observed proxies. A living source off, a missing owner, a dead carrier and true observed absence are not interchangeable. | `docs/societal-resilience.md` — Coverage distinctions and Interpretation limits; `AgentRuntime.export_resilience_owner_keys` | Denominator, changed-holder, branch-vs-run and missing-middle tests (3, 6). |

## Architecture and Decisions

- `experiments` reads bounded finalized evidence; `analysis` builds a canonical programmatic report after ordinary execution. Capture is default-off; a disaster is not a prerequisite, anchor or inferred cause. No world behavior, cognition, authoritative ‘collapse’ state, global societal registry, stop-policy hook, API, client, SQL, runner/replay format or metric catalog changes.
- The eight indicator clocks are run-wide and fixed-region measures of physical presence and scoped evidence, not a census of analytical societies. The societal layer is an independent temporal graph of evidence-supported observations and successors. Attach temporal/geographic context when substantiated; a regional trajectory never transfers a status to a successor.
- Use 32-tick windows, a frozen comparison baseline during candidate/active episodes, a two-window confirmation rule, explicit coverage, and hysteresis. A report provides `collapse-recovery.v1` policy and comparisons, not a universal definition of collapse.
- Distinguish uninterrupted same-owner recognition, retention by a successor, same-key reobservation, loss within a branch, and missing evidence. No apparent absence establishes irreversible technology extinction.
- Baseline unchanged: runner v4 default / v63 latest opt-in; result v2 default; 45 commands / 73 observer semantics / 275 metric families; 12 owned V4 flags; `/v1`, `observer-protocol-v1`, Alembic `0017`; feature-selected world replay as before.

## Phase Index

1. [Phase 1: Finalized collapse evidence](phase-01-capture.md) — Tasks 1–2
2. [Phase 2: Indicators, collapse patterns and recovery](phase-02-indicators.md) — Tasks 3–4
3. [Phase 3: Fragmentation and successor lineage](phase-03-lineage.md) — Tasks 5–6
4. [Phase 4: Report, qualification and documentation](phase-04-report.md) — Tasks 7–9

## Cross-Phase Dependencies

- Task 2 seals Task 1 evidence; Task 3 measures it; Task 4 derives summaries from Task 3.
- Task 5 detects societal observations from Task 2 source evidence, independent of collapse classification. Task 6 annotates Task 5 links with Tasks 3–4 comparisons and episode context.
- Task 7 composes Tasks 3, 4 and 6 after Task 2 finishes; Task 8 qualifies the public entry point; Task 9 documents what actually passed.

## Tasks

### Phase 1: Finalized collapse evidence

- [x] Task 1: Define the detached evidence ([details](phase-01-capture.md#task-1-define-the-detached-evidence))
- [x] Task 2: Capture and seal a run once ([details](phase-01-capture.md#task-2-capture-and-seal-a-run-once)) (depends on 1)

### Phase 2: Indicators, collapse patterns and recovery

- [x] Task 3: Reduce eight independent indicators ([details](phase-02-indicators.md#task-3-reduce-eight-independent-indicators)) (depends on 2)
- [x] Task 4: Detect episodes with recovery and uncertainty ([details](phase-02-indicators.md#task-4-detect-episodes-with-recovery-and-uncertainty)) (depends on 3)

### Phase 3: Fragmentation and successor lineage

- [x] Task 5: Detect fragmentation and successor candidates ([details](phase-03-lineage.md#task-5-detect-fragmentation-and-successor-candidates)) (depends on 2)
- [x] Task 6: Annotate continuity across fragments ([details](phase-03-lineage.md#task-6-annotate-continuity-across-fragments)) (depends on 3, 4, 5)

### Phase 4: Report, qualification and documentation

- [x] Task 7: Build the canonical programmatic report ([details](phase-04-report.md#task-7-build-the-canonical-programmatic-report)) (depends on 3, 4, 6)
- [x] Task 8: Qualify real-run parity and boundary isolation ([details](phase-04-report.md#task-8-qualify-real-run-parity-and-boundary-isolation)) (depends on 7)
- [x] Task 9: Document the evidence and limits ([details](phase-04-report.md#task-9-document-the-evidence-and-limits)) (depends on 8)

## Commit Plan

- **Commit 1** (after Tasks 1–4): `feat(analysis): capture and classify collapse trajectories`
- **Commit 2** (after Tasks 5–9): `feat(analysis): report succession across societal fragmentation`

## Definition of Done

- Eight independently inspectable dimensions, explicit coverage, baseline comparisons and reversible episode annotations are available after completion.
- Verified vote combinations confirm collapse and recovery without imposing either outcome. Known-empty, unsupported, sparse and censored outcomes remain distinct.
- Forward-only graph records evidenced continuations, splits and successor links without bridging gaps, leaking claims, or conflating a divided society with a dead one.
- A supported split can preserve institutional recognition and lose technology in one branch while another retains it. Unknowns never masquerade as loss or recovery.
- Real-run capture off/on/failure preserves committed execution and legacy contracts. Canonical bytes and architecture tests pass, documentation checkpoint complete; no `CivilizationCollapsed` mechanism exists.

## Verification Receipt (2026-11-25)

Focused:

```text
uv run --frozen --python 3.12.14 pytest tests/unit/test_collapse_recovery*.py \
  tests/architecture/test_collapse_recovery_boundaries.py \
  tests/unit/test_v1_regression_gate.py \
  tests/unit/test_v2_scientific_invariants.py \
  tests/unit/test_alembic_head_pin.py -q
→ 104 passed (with docs pin modules)
```

Collapse surface alone: 64 passed.

Static: `ruff check` on collapse modules/tests clean; `mypy` on collapse
modules/capture clean; `lint-imports` 25 kept; `git diff --check` clean on
changed collapse surface.

Still out of changed surface / unexecuted: Compose, PostgreSQL disposable DB,
Godot, browser, and long-horizon scale profiles. Full local `pytest --cov`
not re-run in this session after the focused gate.
