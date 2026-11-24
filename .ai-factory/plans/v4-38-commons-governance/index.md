<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-38 Commons Governance

Mode: ultra  
Branch: main  
Created: 2026-11-24

## Original Request
v4-38 commons governance

Naming requirement:

Use `v4-38-commons-governance`.

Create scenarios where multiple agents/groups share finite renewable resources.

Do not implement mandatory commons governance.

Allow emergence of:

- restrictions
    
- monitoring
    
- sanctions
    
- access claims
    
- rotation
    
- cooperation
    
- overuse
    

Use existing norms, formal rules and institutions.

Measure resource sustainability and cooperation.

## Settings
- Testing: yes
- Logging: verbose, metadata-only
- Docs: yes

## Roadmap Linkage
Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"  
Rationale: Deepens owned ecology and owner-scoped social governance without claiming `disasters` or closing M8.

## Requirements Reconciliation
Authority: Original Request defines feature scope; `AGENTS.md`, `.ai-factory/RULES.md`, and `.ai-factory/ARCHITECTURE.md` define authority and versioning; executable v61 contracts and `docs/overexploitation.md` refine the ecology baseline. Roadmap and architecture summary pins lag v61 and are not executable requirements.

| Supported combination / decision | Source | Verification |
|---|---|---|
| v61 with ecology, including existing social modes if enabled: unchanged control; no commons state or speech producer | Original Request; `docs/overexploitation.md` — Configuration | Existing V4-37 fixture and byte/replay regressions |
| Explicit v62 with exact commons spec, valid v61 prerequisites, formal rules, deterministic norms and institution concepts: empty owner state until qualifying evidence; no world changes for equal commands | Original Request; `ARCHITECTURE.md` — Versioned Extension Contract | Task 1 gate matrix; Tasks 3–4 real runner, pending and replay tests |
| v62 missing any prerequisite or with invalid nodes, or legacy schema with new key: reject before running; no state or effects | `RULES.md`; `runner_models.py` v61 gate precedent | Task 1 rejection and legacy codec fixtures |
| Monitoring: visible stock change is direct evidence; peer account is testimony, not a witnessed draw. Access claims, turns, rules, and sanctions never enter physical admission | Original Request; `ARCHITECTURE.md` — Memory, testimony, and subjective concepts; `world._perception` audience rules | Tasks 2–4 gaps, disputed claims, and physically admissible noncompliance |
| Pair only within a single `ExperimentDefinition` layout; compare layouts separately | Original Request; `src/experiments/models.py` — `ExperimentDefinition.__post_init__` | Tasks 5 and 7 real definition construction and matched replicate blocks |
| Capture optional; complete zero, partial, unavailable, and disabled remain distinct; controlled mechanisms and autonomous results are not pooled | Original Request; `docs/overexploitation.md` — Controlled demonstration | Tasks 5–8 twin, gap, and seed pairing tests |

## Architecture and Decisions
- Existing V4-37 physical model is unchanged: no new commands, events, perception fields, replay pair, migrations, flags, `/v1` routes or UI scope. V62 is an opt-in cognition/config seam; v1–v61 remain accepted as before. Active ecology still uses event 29 / codec `v27` / projector `v2`.
- Owner-local resource-keyed evidence complements existing norms, formal rules and institution concepts; there is no policy authority, objective membership, turn scheduler, sanction executor, or group actor. The scenario's research rosters never enter cognition.
- Initial lane: locally visible water stocks and ordinary `Drink`. Monitoring is of stock quantity, not attribution of peers' physical actions. Support, refusal, self-reports and procedural disagreement travel inside existing addressed speech.
- Publish programmatic detached sustainability and cooperation reports only; no global metric-catalog additions or capture-to-cognition feedback.

## Phase Index
1. [Phase 1: Activation and evidence](phase-01-activation-and-evidence.md) — Tasks 1–2
2. [Phase 2: Voluntary social behavior](phase-02-voluntary-social-behavior.md) — Tasks 3–4
3. [Phase 3: Scenarios and measurement](phase-03-scenarios-and-measurement.md) — Tasks 5–7
4. [Phase 4: Documentation and verification](phase-04-documentation-and-verification.md) — Task 8

## Cross-Phase Dependencies
- Task 2 depends on 1; 3 depends on 2; 4 depends on 3.
- Task 5 depends on 4; 6 depends on 5 and the state/evidence contracts of 2–4; 7 depends on 5–6; 8 depends on 1–7.

## Tasks
### Phase 1: Activation and evidence
- [x] Task 1: Add exact opt-in v62 config ([details](phase-01-activation-and-evidence.md#task-1-add-exact-opt-in-v62-config))
- [x] Task 2: Fold bounded owner-local commons evidence ([details](phase-01-activation-and-evidence.md#task-2-fold-bounded-owner-local-commons-evidence)) (depends on 1)

### Phase 2: Voluntary social behavior
- [x] Task 3: Compose existing social ledgers and voluntary responses ([details](phase-02-voluntary-social-behavior.md#task-3-compose-existing-social-ledgers-and-voluntary-responses)) (depends on 2)
- [x] Task 4: Wire runtime finalization and checkpoint parity ([details](phase-02-voluntary-social-behavior.md#task-4-wire-runtime-finalization-and-checkpoint-parity)) (depends on 3)

### Phase 3: Scenarios and measurement
- [x] Task 5: Register paired shared-stock scenarios ([details](phase-03-scenarios-and-measurement.md#task-5-register-paired-shared-stock-scenarios)) (depends on 4)
- [x] Task 6: Project sustainability and cooperation evidence ([details](phase-03-scenarios-and-measurement.md#task-6-project-sustainability-and-cooperation-evidence)) (depends on 2–5)
- [x] Task 7: Separate controlled proofs and autonomous comparisons ([details](phase-03-scenarios-and-measurement.md#task-7-separate-controlled-proofs-and-autonomous-comparisons)) (depends on 5–6)

### Phase 4: Documentation and verification
- [x] Task 8: Document and verify the feature and compatibility gates ([details](phase-04-documentation-and-verification.md#task-8-document-and-verify-the-feature-and-compatibility-gates)) (depends on 1–7)

## Commit Plan
- **Commit 1** (Tasks 1–4): `feat: add voluntary owner-scoped commons governance`
- **Commit 2** (Tasks 5–8): `feat: measure commons sustainability and cooperation in paired experiments`

## Definition of Done
- Two separate paired experiment definitions exercise finite shared-stock layouts. No action schedule, seeded policy, entitlement or required social outcome exists in the autonomous lane.
- Controlled tests exercise all seven requested possibilities, including contested/ignored arrangements and physically admissible draws against a claimed restriction or turn; autonomous zero emergence is valid.
- Sustainability and cooperation report separate, auditable numerators, denominators and coverage, including uncontrolled overuse, welfare trade-offs and ambiguous social evidence.
- Capture parity, legacy config/bytes and live/replayed objective behavior pass their gates. Documentation distinguishes implemented, verified and unexecuted lanes.

## Verification Receipt

| Lane | Command | Result | Prerequisite / note |
| --- | --- | --- | --- |
| Focused feature + pins | `uv run --frozen --python 3.12.14 pytest tests/unit/test_commons_governance_*.py tests/unit/test_overexploitation_*.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/unit/test_alembic_head_pin.py tests/architecture/test_v4_architecture_invariants.py -q` | green: 196 passed | coverage left enabled |
| Default pytest | `uv run --frozen --python 3.12.14 pytest -q` | green: 13302 passed, 5 skipped, 180 deselected | includes historical next-schema pin bump to v63 |
| Static: Ruff | `uv run --frozen --python 3.12.14 ruff check src tests` | green: all checks passed |  |
| Static: mypy | `uv run --frozen --python 3.12.14 mypy src tests` | green: no issues in 3150 files |  |
| Static: import boundaries | `uv run --frozen --python 3.12.14 lint-imports` | green: 25 kept, 0 broken |  |
| Integration durable replay | `uv run --frozen --python 3.12.14 pytest -m integration tests/integration/test_overexploitation_durable_replay.py -q` | unexecuted | no disposable `palimpsest_test` / `PALIMPSEST_TEST_DATABASE_URL` in this environment |
| Compose / Godot / browser / scale | — | unexecuted / out of scope | no new API, UI, Godot, or Compose surface |

Docs: `docs/commons-governance.md` plus README/AGENTS/configuration/overexploitation links. Factual pins updated in `.ai-factory/DESCRIPTION.md` and `.ai-factory/ARCHITECTURE.md` (latest feature runner v62; pending v7; eleven owned V4 flags / only `disasters` unowned). M8 roadmap entries added for V4-36–V4-38 without closing M8. Integration durable replay remains unexecuted without `PALIMPSEST_TEST_DATABASE_URL`. Commits not created (await explicit request).
