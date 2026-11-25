<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: v4-39-disasters

Mode: ultra  
Branch: main (no branch created)  
Created: 2026-11-24

## Original Request
v4-39 disasters

Naming requirement:

Use `v4-39-disasters`.

Implement configurable rare objective shocks:

- flood-like event
    
- fire
    
- drought
    
- epidemic surge
    
- infrastructure destruction
    
- resource collapse
    

Do not use them as arbitrary narrative events.

All disasters must follow explicit configured physical mechanics/probabilities.

Support seeded reproducibility and controlled experiment injection.

## Settings

- Testing: yes
- Logging: verbose, allowlisted metadata only
- Docs: yes, mandatory `$aif-docs` checkpoint

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"  
Rationale: Owns the remaining reserved V4 disaster context and its objective replay seam.

## Requirements Reconciliation

Authority: Project rules govern architectural boundaries; the Original Request governs feature scope. The current architecture baseline and working compatibility contracts supply existing semantics. The roadmap assigns ownership, not mechanics. Its reservation is a compatibility obligation, not license to rewrite existing replay pairs.

| Decision / supported combination | Source path and section | Verification evidence |
|---|---|---|
| Feature off: no scheduling, state, draws, or new writes; legacy schemas and prior enabled channels preserve their existing write selections. | `.ai-factory/ARCHITECTURE.md` — Key Principles and Versioned Extension Contract | Task 4 legacy golden documents and representative completed runs; V1/V2/V3 gates. |
| Feature on: exact config, eligible physical targets, explicit bounded effects; no narrative, authoritative hazard labels in cognition, or arbitrary mutation hooks. | Original Request; `.ai-factory/RULES.md` axioms; `.ai-factory/ARCHITECTURE.md` authority rules | Tasks 1–4 validate closed inputs, eligible/ineligible effects, privacy, replay and rollback. |
| Spontaneous-only, scheduled-only and combined policies use the same mechanism; zero chance plus empty schedule is the inert control. Sources are disjoint per rule; due scheduled candidates resolve before spontaneous candidates in the same tranche. Replay applies recorded effects, not probabilities. | Original Request; `.ai-factory/ARCHITECTURE.md` reproducibility/version rules; `src/experiments/coordinator.py` assignment identity | Tasks 1 and 4 trigger/continuation vectors; Task 5 compares physical prefixes across distinct arm run IDs and bytes only in same-identity reruns. |
| Disaster activation requires ecology and environmental dynamics. Stock shocks target managed stocks. Infrastructure destruction additionally requires infrastructure; epidemic surge additionally requires active fictional disease. Existing sibling modes, including overexploitation and commons governance, may compose only through their existing prerequisites. | Original Request; `src/simulation/v4_architecture.py` disasters context; `.ai-factory/ARCHITECTURE.md` V4-34/V4-36–38 and objective authority; `docs/disease-mechanics.md` privacy contract | Tasks 2–5 cover each required combination and missing prerequisite; compose existing disease and two-pool commons fixtures. |
| `disasters` fills reserved event 26 / codec `v24`, not a new numeric maximum, migration, command, new client surface, or write authority for research code. Historical inspection is policy-free for disasters; live execution from restored state requires matching policy. Private receipts are excluded before public page selection and can still participate in journal verification. | `.ai-factory/ROADMAP.md` M8 Next Plans; `src/simulation/versioning.py` disaster reservation; `.ai-factory/ARCHITECTURE.md` compatibility and authority | Task 4 explicit allowance/rejection matrix, bounded/non-bounded recovery and persisted paging tests; Task 6 version and import gates. |

The V4 ownership list in `.ai-factory/ARCHITECTURE.md` omits `ecological_feedback`, but the same document's latest baseline, V4-36 in `.ai-factory/DESCRIPTION.md`, and the roadmap record it as owned. Task 6 corrects the enumeration after qualification; do not reclassify ecology or rewrite older historical pins.

## Architecture and Decisions

- `WorldEngine` owns disaster evaluation inside the objective transaction. Stochastically triggered and scheduled candidates dispatch to one private world implementation; neither path bypasses target checks or physical clamps.
- V1 mechanics are bounded one-tick pulses: flood-like inundation and fire consume appropriate stocks, drought removes water stock, infrastructure destruction uses existing condition/durability, and resource collapse depletes a selected stock. Surges affect only the fictional condition's existing private progression. No long-lived hazard front, automatic spread, secondary disaster, new death mechanism, arbitrary script, or real-world hazard model.
- Rule probabilities are integer parts-per-million, default off. Rules are applied at most once, and scheduled rules have zero spontaneous probability. A policy may mix scheduled and spontaneous rules; disjoint keyed draws and objective eligibility determine outcomes. Existing recovery mechanisms run on their ordinary schedule.
- Journal typed objective effects, not a seed-only trigger. Historical fold needs no policy; live continuation verifies policy identity and deterministic boundaries. Keep hazardous and disease-private evidence out of ordinary observers and cognition.
- Implement task edits only; do not auto-start implementation or create a branch. No standalone research artifact influenced the design.

## Phase Index

1. [Phase 1: Objective Configuration](phase-01-configuration.md) — Task 1
2. [Phase 2: Physical Mechanics](phase-02-physical-mechanics.md) — Tasks 2–3
3. [Phase 3: Runtime, Replay and Recovery](phase-03-runtime-and-replay.md) — Task 4
4. [Phase 4: Experiments and Qualification](phase-04-experiments-and-qualification.md) — Tasks 5–6

## Cross-Phase Dependencies

- Tasks 2 and 3 depend independently on the immutable rule, candidate, and effect declarations from Task 1. Task 3's infrastructure/disease helpers do not require the stock reducer.
- Task 4 requires both effect families before enabling runner selection; keep the transitional integration fail-closed.
- Task 5 runs through Task 4, never through standalone policy mocks; Task 6 records results after all qualification gates.

## Tasks

### Phase 1: Objective Configuration
- [x] Task 1: Define the closed disaster policy and trigger contract ([details](phase-01-configuration.md#task-1-define-the-closed-disaster-policy-and-trigger-contract))

### Phase 2: Physical Mechanics
- [x] Task 2: Implement stock shock effects ([details](phase-02-physical-mechanics.md#task-2-implement-stock-shock-effects)) (depends on 1)
- [x] Task 3: Implement infrastructure and fictional disease effects ([details](phase-02-physical-mechanics.md#task-3-implement-infrastructure-and-fictional-disease-effects)) (depends on 1)

### Phase 3: Runtime, Replay and Recovery
- [x] Task 4: Activate objective execution and effect-complete replay ([details](phase-03-runtime-and-replay.md#task-4-activate-objective-execution-and-effect-complete-replay)) (depends on 1–3)

### Phase 4: Experiments and Qualification
- [x] Task 5: Qualify scheduled and seeded experiments ([details](phase-04-experiments-and-qualification.md#task-5-qualify-scheduled-and-seeded-experiments)) (depends on 4)
- [x] Task 6: Document contracts and run release gates ([details](phase-04-experiments-and-qualification.md#task-6-document-contracts-and-run-release-gates)) (depends on 5)

## Commit Plan

- After Tasks 1–3: `feat(world): define bounded disaster policies and physical effects`
- After Tasks 4–6: `feat(simulation): replay and qualify configured objective disasters`

## Definition of Done

- All six mechanisms, zero-probability and scheduled controls, seeded twins, restoration and next-tick observation noninterference are verified.
- Existing accepted documents and event schemas still decode; feature-off bytes and schema selection stay stable.
- Ownership is updated only after the objective, privacy, replay, compatibility, and experiment gates pass. No unsupported realism, throughput or causal claim is made.
