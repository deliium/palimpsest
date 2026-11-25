<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-40 Societal Resilience

Mode: ultra  
Branch: main  
Created: 2026-11-25

## Original Request

v4-40 resilience

Naming requirement:

Use `v4-40-resilience`.

Measure response to shocks through:

- population recovery
    
- migration
    
- resource recovery
    
- institution continuity
    
- knowledge retention
    
- technology loss
    
- cooperation
    
- inequality
    
- trade network recovery
    
- infrastructure recovery
    

Avoid one universal resilience score.

Provide multi-dimensional time series.

## Settings

- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"  
Rationale: This is the remaining detached `societal_resilience` analysis explicitly listed under M8; it does not close all of M8.

## Requirements Reconciliation

Authority: The original request defines the outcome and prohibitions. `.ai-factory/RULES.md`, `.ai-factory/ARCHITECTURE.md`, and `AGENTS.md` govern implementation. The roadmap identifies scope; V4-39 code and `docs/disasters.md` define actual shock and replay behavior. Historical metric counts in the M8 scaffolding note are not current pins; the dated V4-39 architecture baseline and current roadmap landing agree on 275. No separate research requirements source was found.

| Decision / supported combination | Source path and section | Verification evidence |
|---|---|---|
| Ten same-clock panels, with separate measures and no scalar resilience index, ranking or recommendation. | Original Request; architecture, authority separation. | Exact ten-dimensional report golden and schema rejection of extra score fields (Tasks 4–6). |
| Applied receipts anchor windows and the immediate state point; skipped, no-effect, planned-but-unreached, and inert control schedules do not. Co-tick applied receipts share one anchor; overlapping shocks censor comparisons. Schedule disposition is independent of episode status. | `docs/disasters.md` — Scope and Configuration; `src/world/events.py` — `DisasterResolved`; original request's response-to-shocks scope. | Boundary/overlap truth table and actual drought/control/skipped/not-reached qualification (Tasks 1, 7). |
| Capture off or unsupported: ordinary run only; enabled with optional channels absent: ordinary run plus separate unavailable lanes; enabled-empty and fully observed: known-zero counts where defined; capture gaps or unsupported projections: no imputations. | Architecture — optional channels, ownership, finalized evidence boundaries; `src/simulation/runner_models.py` — `FinalizedTickReceipt`. | Skip/on/off parity, void-vs-missing, caps, cohort extinction/dropout, no fabricated recovery (Tasks 2–7). |
| One completed programmatic artifact may be produced from a real v63 run. No new authority, legacy schema change, catalog registration, SQL migration, route, or observer protocol change. | M8 next plans; `src/simulation/v4_architecture.py` — `SOCIETAL_RESILIENCE`; architecture — V4-39 baseline. | Strict codec, import boundaries, flags-off compatibility, V4-39 real runner fixture, pinned baseline (Tasks 6–7). |

## Architecture and Decisions

- `simulation` provides a narrow finalized evidence export; trusted `experiments` opts in and runs once; pure `analysis` builds detached panels and canonical report bytes. No access from world rules, cognition, memory, prompts, stop selection, observer, clients or API.
- Scope: run-level shock response with region-direction and stock-unit breakdowns. One eight-tick pre window and eight eight-tick follow-up windows per applied shock tick, plus a separate immediate state point after the shock tick. Flows use half-open intervals; stock-like measures use the exclusive-end boundary. Immediate changes compare to the preceding boundary, not the pre-window aggregates. Publish raw values, explicit coverage and denominators, and comparable signed changes without labeling them good or bad.
- Deliver a canonical programmatic `societal-resilience-report-v1` sibling; callers may save it. No automatic persistence, HTTP, frontend, new experiment registry entry, or universal score. Use existing `disasters@1` as the real verification specimen, not as a claim of causality.
- V4-39 is the upstream dependency; use its current worktree contract and do not overwrite or roll back its changes. Legacy accepted pairs and pins remain untouched. No blocking design question remains for this v1 scope.

## Phase Index

1. [Phase 1: Shock clocks and finalized evidence](phase-01-evidence.md) — Tasks 1–3
2. [Phase 2: Ten independent resilience time series](phase-02-series.md) — Tasks 4–5
3. [Phase 3: Research report, qualification, and docs](phase-03-report.md) — Tasks 6–8

## Cross-Phase Dependencies

- Tasks 1 and 2 define independent window and point contracts; Task 3 joins them with finalization receipts.
- Tasks 4 and 5 consume the sealed input from Task 3 and share the Task 4 measure shape.
- Task 6 requires Tasks 4 and 5; Task 7 qualifies the Task 6 public path against the existing experiment; Task 8 documents the verified contract.

## Tasks

### Phase 1: Shock clocks and finalized evidence

- [x] Task 1: Define committed shocks and window coverage ([details](phase-01-evidence.md#task-1-define-committed-shocks-and-window-coverage))
- [x] Task 2: Export narrow finalized boundary evidence ([details](phase-01-evidence.md#task-2-export-narrow-finalized-boundary-evidence))
- [x] Task 3: Seal capture without steering execution ([details](phase-01-evidence.md#task-3-seal-capture-without-steering-execution)) (depends on 1, 2)

### Phase 2: Ten independent resilience time series

- [ ] Task 4: Reduce physical and network response ([details](phase-02-series.md#task-4-reduce-physical-and-network-response)) (depends on 3)
- [ ] Task 5: Reduce owner-scoped and distributional response ([details](phase-02-series.md#task-5-reduce-owner-scoped-and-distributional-response)) (depends on 3, 4)

### Phase 3: Research report, qualification, and docs

- [ ] Task 6: Build and encode the detached report ([details](phase-03-report.md#task-6-build-and-encode-the-detached-report)) (depends on 4, 5)
- [ ] Task 7: Qualify against V4-39 and keep compatibility pinned ([details](phase-03-report.md#task-7-qualify-against-v4-39-and-keep-compatibility-pinned)) (depends on 6)
- [ ] Task 8: Document use, comparability, and limits ([details](phase-03-report.md#task-8-document-use-comparability-and-limits)) (depends on 7)

## Commit Plan

- **Commit 1** (after Tasks 1–3): `feat(resilience): capture finalized shock evidence`
- **Commit 2** (after Tasks 4–8): `feat(resilience): report multidimensional shock response`

## Definition of Done

- Real committed shock data yields ten independent aligned panels in canonical bytes; no composite score exists.
- A no-shock control, a skipped shock, an unreached schedule, co-tick and repeated shocks, a truncated run, a capture gap, a disabled channel and a fully observed empty channel remain distinguishable.
- An immediate state dip remains visible even if it has recovered by the first complete follow-up window. Capture never materializes whole engine history.
- Measurements disclose scope, units, comparison basis and denominators; lack of recovery is a valid outcome, not a failed fixture.
- Run execution, replay, compatibility pins, study inputs, and all trust boundaries are unchanged with capture absent or present.
- Verified focused and full local coverage runs plus static checks are recorded; docs checkpoint and roadmap status reflect the actual implementation without broad certification claims.
