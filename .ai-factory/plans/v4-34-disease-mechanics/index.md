<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: v4-34-disease-mechanics

Mode: ultra  
Branch: main  
Created: 2026-11-22

## Original Request
v4-34 disease mechanics

Naming requirement:

Use `v4-34-disease-mechanics`.

Add optional objective disease mechanics.

Support configurable:

- exposure
    
- transmission
    
- latent/incubation-like state
    
- symptoms
    
- recovery
    
- mortality
    
- immunity where appropriate
    

WorldEngine knows objective infection state.

Agents do NOT.

Agents perceive symptoms/contact/events only.

Keep disease system sufficiently abstract for experimentation rather than medical realism.

Ensure deterministic seeded replay.

## Settings

- Testing: yes
- Logging: verbose (safe operational metadata only)
- Docs: yes

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations"  
Rationale: Own the declared `epidemics` capability and activate its reserved objective replay pair, without claiming the two remaining unowned flags.

## Requirements Reconciliation

Authority: The original request sets behavior; `.ai-factory/RULES.md` and `.ai-factory/ARCHITECTURE.md` constrain ownership, visibility, and compatibility. The executable context registry provides prerequisites; the roadmap establishes scope rather than payload definitions. The older count references in the roadmap are historical/stale; use the V4-33 architecture baseline. No research artifact supplied requirements.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| Disease off: existing config/flag rules, no private rows or cue, exact legacy version selection | Original Request; `.ai-factory/ARCHITECTURE.md` — Versioned Extension Contract | V1 golden runs, v56/v57 round trips, disease-off twins |
| Disease on: exact v58 spec + `epidemics=true` + valid infrastructure channel; older version, missing prerequisite, or flag/spec mismatch fails closed | Original Request; `src/simulation/v4_architecture.py` — `EPIDEMICS`; `src/simulation/runner_models.py` — capability checks | Strict config matrix, bootstrap validation, active-empty case |
| Enabled with inherited travel and/or instruments: keep their existing prerequisites; one reserved 24/`v22` pair carries all active sections; off retains 23/`v21`, 27/`v25`, or 28/`v26` as applicable | `src/simulation/versioning.py` — V4 pair reservations; `src/simulation/persistence.py` — pair selection | Test neither, travel only, instruments only, and both under 24/`v22`; preserve representative existing off-path artifacts |
| Latent → active; optional coarse symptom; active → death or recovery; recovery → susceptible or run-scoped immune | Original Request; `.ai-factory/RULES.md` — engine authority | Endpoint, ordering, duplicate-death, immunity and empty-tick tests |
| Objective rows only in engine/trusted persistence; owners may observe their symptom cue, ordinary co-presence and events; no diagnosis | Original Request; `.ai-factory/ARCHITECTURE.md` — Perception and Subjective Concepts | Owner/peer/remote noninterference and observer spill tests |
| Historical replay folds recorded effects without live policy; continuation requires a verified matching policy and the original seed | Original Request; `.ai-factory/ARCHITECTURE.md` — Key Principles; `src/simulation/persistence.py` — `WorldSnapshot` / `ReplayRequest` | Twin commits, checkpoint/tail restore without policy, rejection of mismatched policy, continued-run parity |

## Architecture and Decisions

- One fictional condition per enabled run. Exposure and transmission are abstract per-opportunity draws over discrete settled co-presence. No pathogens, real-world calibration, travel-path exposure, intervention optimizer, or automatic behavior response.
- Candidate updates are simultaneous, deterministic, and committed atomically. Disease uses a private sparse state plus a detached effect record. It does not add a command, cognition mode, ledger, metric family, dedicated route, or overlay.
- Projection is deliberately lossy: coarse owner-only `unwell` or absence, existing contact evidence, and an ordinary observable death event without diagnostic attributes. A symptom can be informative, but no agent receives the objective phase, immune status, source attribution, or confirmation of transmission.
- Keep `/v1`, `observer-protocol-v1`, result versions, 45 commands, 73 observer semantics, 275 metric families and Alembic `0017`. Own one existing flag (10 of 12 owned) and write v58 only when disease is configured. Preserve other accepted runner/replay/codec versions.

## Phase Index

1. [Phase 1: Activation and private state](phase-01-config-and-state.md) — Tasks 1–2
2. [Phase 2: Engine lifecycle and perception](phase-02-engine-and-perception.md) — Tasks 3–4
3. [Phase 3: Replay and read boundaries](phase-03-replay-and-read-boundaries.md) — Tasks 5–6
4. [Phase 4: Experiment, verification, and docs](phase-04-verification-and-docs.md) — Tasks 7–9

## Cross-Phase Dependencies

- Task 2 needs Task 1's typed spec; Task 3 needs both the spec and private state.
- Task 4 needs Task 3's cue/effect shapes. Task 3 verifies detached candidate behavior without storage. Task 5 needs Tasks 3–4 for effect order and projection parity and owns the durable-write rollback test. Introduce the schema marker alongside the event type in Task 3, but do not accept/write the pair until Task 5.
- Task 6 needs the private event shape from Task 3 and replay from Task 5. Tasks 7–8 exercise the complete path; Task 9 follows verified behavior.
- Keep public runner activation fail-closed until Task 6 lands. Tasks 1–5 may exercise the typed config and engine directly through trusted test composition; do not publish a run that presentation cannot safely read.

## Tasks

### Phase 1: Activation and private state
- [x] Task 1: Define the exact opt-in runner configuration ([details](phase-01-config-and-state.md#task-1-define-the-exact-opt-in-runner-configuration))
- [x] Task 2: Add private disease rows and detached state invariants ([details](phase-01-config-and-state.md#task-2-add-private-disease-rows-and-detached-state-invariants)) (depends on 1)

### Phase 2: Engine lifecycle and perception
- [x] Task 3: Advance the hidden lifecycle in one candidate pass ([details](phase-02-engine-and-perception.md#task-3-advance-the-hidden-lifecycle-in-one-candidate-pass)) (depends on 1, 2)
- [x] Task 4: Project symptom cues without exposing infection ([details](phase-02-engine-and-perception.md#task-4-project-symptom-cues-without-exposing-infection)) (depends on 3)

### Phase 3: Replay and read boundaries
- [x] Task 5: Activate reserved replay 24 and checkpoint codec v22 ([details](phase-03-replay-and-read-boundaries.md#task-5-activate-reserved-replay-24-and-checkpoint-codec-v22)) (depends on 3, 4)
- [ ] Task 6: Redact internal transitions across observer reads ([details](phase-03-replay-and-read-boundaries.md#task-6-redact-internal-transitions-across-observer-reads)) (depends on 3, 5)

### Phase 4: Experiment, verification, and docs
- [ ] Task 7: Register a paired synthetic experiment ([details](phase-04-verification-and-docs.md#task-7-register-a-paired-synthetic-experiment)) (depends on 6)
- [ ] Task 8: Verify durability, compatibility, and trust boundaries ([details](phase-04-verification-and-docs.md#task-8-verify-durability-compatibility-and-trust-boundaries)) (depends on 6, 7)
- [ ] Task 9: Complete the mandatory documentation checkpoint ([details](phase-04-verification-and-docs.md#task-9-complete-the-mandatory-documentation-checkpoint)) (depends on 8)

## Commit Plan

- **Commit 1** (after Tasks 1–5): `feat: add opt-in disease mechanics with deterministic replay`
- **Commit 2** (after Tasks 6–9): `feat: redact disease read projections and verify the experiment`

## Definition of Done

- All nine tasks satisfy their tests and acceptance criteria; implementation records exact verification commands and distinguishes unexecuted lanes.
- **Enabled:** accepted config drives each abstract transition; hidden condition state is restored exactly and never enters agent-facing observations. **Disabled:** prior golden artifacts and replay/runner selections remain unchanged.
- Docs and ownership pins reflect the implemented boundary; no SQL migration, new public route, or efficacy claim.
