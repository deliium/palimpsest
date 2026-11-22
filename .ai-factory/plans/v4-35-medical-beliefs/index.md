<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-35 Medical Beliefs

Mode: ultra  
Plan ID: `v4-35-medical-beliefs`  
Branch: `main` (unchanged)  
Created: 2026-11-22

## Original Request
v4-35 medical beliefs

Naming requirement:

Use `v4-35-medical-beliefs`.

Allow agents to build subjective disease explanations.

Examples may involve:

contact  
food  
weather  
location  
incorrect supernatural/cultural explanations

Agents may try interventions according to beliefs.

WorldEngine evaluates objective physical effects.

Track:

belief  
treatment/intervention  
outcome  
interpretation  
transmission

Allow ineffective practices to persist socially.

## Settings
- Testing: yes
- Logging: verbose (metadata only)
- Docs: yes (mandatory `$aif-docs` checkpoint)

## Roadmap Linkage
Milestone: "M8 — V4 Open-Ended Civilizations"  
Rationale: Deepens the owned `epidemics` context without claiming either remaining reserved capability or closing M8.

## Requirements Reconciliation

Authority: The original request defines the behavior; `.ai-factory/RULES.md` and `.ai-factory/ARCHITECTURE.md` constrain how it can be implemented. `docs/disease-mechanics.md` describes the inherited V4-34 contract. The new optional cognition feature does not extend or retune the underlying fictional disease model.

| Decision / supported combination | Source path and section | Verification evidence |
|---|---|---|
| Off by default; v58 stays byte- and fingerprint-stable; v59 adds the exact spec without or with the supported instrument sibling and changes cognition identity, not scenario identity. Missing prerequisites fail closed before runtime construction. | `.ai-factory/ARCHITECTURE.md` — Versioned Extension Contract; `docs/disease-mechanics.md` — Configuration | Config and codec matrix; paired fixture from the actual V4-34 builder; full pin sweep |
| Only consecutive owner observations support local associations, not diagnosis. Testimony can establish conflicting explanations, including cultural ones. Cue absence/unknown is not objective recovery. | Original Request — explanations; `docs/disease-mechanics.md` — Perception and reads; `.ai-factory/RULES.md` — Axioms | Reducer, owner isolation, gap and malformation tests |
| On + belief + own cue can produce an ordinary action after existing command selection; overrides, denial, and missing receipts stay distinct. Engine effects remain ordinary command effects; cue outcome and interpretation stay subjective. | Original Request — intervention and effects; `.ai-factory/ARCHITECTURE.md` — Objective authority and runtime | Priority, applied/rejected/overridden command tests, post-commit recovery twins and tampered state rejection |
| On + delivered claim may update a cue-free receiver; same-root repetition is not new evidence. A no-effect practice can retain support and relay after negative feedback. | Original Request — persistence and transmission; `.ai-factory/ARCHITECTURE.md` — Memory, testimony, and subjective concepts | Three-owner admission/delivery scenario; negative feedback, repeated root and conflict tests |
| Off, capture-disabled, and aborted runs provide no export; an intact finalized capture returns five lanes. Gaps or caps are partial, never evidence of no activity. | Original Request — tracking; `.ai-factory/ARCHITECTURE.md` — Requirements for later changes | Detached completed-run export, terminal abort, capped receipt join and capture/no-capture twins |

## Architecture and Decisions

- Use the existing owner-only `unwell` observation and ordinary local context. Keep objective effect, owner observation and interpretation as distinct evidence, with no feedback from research to live cognition.
- Use an owner-local ledger, bounded addressed speech and one command per tick. `Move`, `Sleep` and marked `Wait` model changing location, resting and a ritual pause. None is assigned a new disease effect.
- Runner v59 opts in, pending finalization v6 carries the bounded candidate, and fork integrity conditionally includes its digest. Pending recovery is not full subjective restart. Disease replay stays 24/`v22`; no new command, event, route, observer field, registered metric family, client surface or migration.
- The detached five-lane evidence export is opt-in and programmatic. This feature contains no real pathogen models, real treatments, or real-world efficacy claims.

## Phase Index
1. [Phase 1: Activation and owner state](phase-01-contracts.md) — Tasks 1–2
2. [Phase 2: Actions, testimony and recovery](phase-02-runtime.md) — Tasks 3–4
3. [Phase 3: Tracking, experiment and release gates](phase-03-validation.md) — Tasks 5–6

## Cross-Phase Dependencies
- Task 3 depends on Tasks 1 and 2: it needs the activation gate and row contracts.
- Task 4 depends on Task 3: it persists the actual bound candidate.
- Task 5 depends on Task 4: it reads only finalized owner evidence.
- Task 6 depends on Task 5: end-to-end verification uses the native fixture, capture and controls.

## Tasks

### Phase 1: Activation and owner state
- [x] Task 1: Add the opt-in runner contract ([details](phase-01-contracts.md#task-1-add-the-opt-in-runner-contract))
- [x] Task 2: Define owner evidence and belief updates ([details](phase-01-contracts.md#task-2-define-owner-evidence-and-belief-updates))

### Phase 2: Actions, testimony and recovery
- [x] Task 3: Route interventions and testimony through ordinary commands ([details](phase-02-runtime.md#task-3-route-interventions-and-testimony-through-ordinary-commands)) (depends on 1, 2)
- [x] Task 4: Persist candidates with the existing finalization protocol ([details](phase-02-runtime.md#task-4-persist-candidates-with-the-existing-finalization-protocol)) (depends on 3)

### Phase 3: Tracking, experiment and release gates
- [x] Task 5: Export detached evidence and register the paired experiment ([details](phase-03-validation.md#task-5-export-detached-evidence-and-register-the-paired-experiment)) (depends on 4)
- [x] Task 6: Prove social persistence and document the boundary ([details](phase-03-validation.md#task-6-prove-social-persistence-and-document-the-boundary)) (depends on 5)

## Commit Plan
- **Commit 1** (after Tasks 1–3): `feat(cognition): add opt-in medical beliefs and testimony`
- **Commit 2** (after Tasks 4–6): `feat(experiments): preserve and track medical belief evidence`

## Definition of Done
- Existing runner/replay and flags-off trajectories remain compatible, including owner and observer redaction.
- The five lanes are queryable in detached evidence without collapsing action application, cue outcome or subjective interpretation.
- The controlled test shows a practice with no modeled treatment effect can reach another owner after explicit negative feedback, without scripting emergence in the paired experiment.
- Coverage-enabled and static checks, documentation checkpoint and any unexecuted environmental lanes are recorded.
