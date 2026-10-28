# Phase 6: Narratives, subjective institutions and grouped history

Plan: [index.md](index.md)
Tasks: 12–13
Depends on: Tasks 1–11

## Objective

Implement scenarios 24–30 with sourced role/narrative evidence and real common-prefix replay children. A controlled social stimulus is not proof that an institution spontaneously emerged.

## Current-Code Evidence

| Path | Symbols / cases | Why it matters |
| --- | --- | --- |
| `src/experiments/generational_narratives_scenario.py` | `generational_narratives_scenario`, `generational_narrative_arbiter` | Owner narrative and optional records |
| `src/experiments/institutionalization_scenario.py` | `institutionalization_scenario` | Existing BF arbiter does not itself create positive institution evidence |
| `src/experiments/offices_succession_scenario.py`, `src/experiments/institutional_memory_scenario.py`, `src/experiments/institutional_decay_scenario.py` | scenario builders | Existing mode/spec composition, not a guaranteed role trajectory |
| `src/experiments/path_dependence_runner.py` | `PathDependenceBatchRunner`, `PathDependenceExecutionContext` | Genuine common-prefix full-state child execution |
| `src/experiments/path_dependence_scenario.py` | `historical_contingency_scenario`, `PrefixEligibility` | Shipped Give/Wait founder opportunity, smoke F=4/H=36 |
| `src/experiments/path_dependence_catalog.py` | `require_independent_execution`, `GroupedExecutionRequired` | Grouped protocol must not use independent-cell routing |
| `tests/unit/test_path_dependence_replay_parity.py` | same-identity continuation; mutated hidden state detection | Full-state restoration oracle |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/experiments/civilization_benchmark_institutions.py` | create | Cases 24–28 |
| `src/experiments/civilization_benchmark_forks.py` | create | Cases 29–30 grouped adapters |
| `src/experiments/civilization_benchmark_execution.py`, `src/experiments/civilization_benchmark_suite.py` | modify | Grouped dispatch and result normalization |
| `src/experiments/path_dependence_runner.py` | modify | Optional child capture lifecycle hooks with defaults preserving old behavior |
| `src/research_runner/civilization_benchmark_composition.py` | modify | Genuine repositories/publication for child histories |
| `tests/unit/test_v3_benchmark_institutions.py`, `tests/unit/test_v3_benchmark_forks.py` | create | Controlled/null/provenance and grouped execution tests |

## Task 12: Exercise narrative survival, roles, succession, persistence and decay

### Intent

Evidence can sustain social roles and institutions beyond individual lives, but no objective role registry or prescribed form of civilization is permitted.

### Implementation Steps

1. Compose cases below using v55 and existing narrative, office, concept, institutional-memory and decay policies. Enable new entrant modes only through the explicit content-empty pack, never by copying a founder config/state.
2. For controlled role fixtures, schedule ordinary recurring work/teaching/project activity and independent addressed role-directed expectation/endorsement expressions in existing communication relations. Use actual independent source roots. Repeated influence or repeated retellings from one root alone must not manufacture role recognition.
3. Observe actual natural occupant deaths, owner-local vacancy/dispute/succession claims and later role activity; retain stable owner-local office identity across claim revisions. Contested/vacant roles are valid. Never pick a globally authoritative occupant or enforce duties/authority.
4. Retain institutional memory only through visible interpreted records/actual delivery. For decay, stop relevant evidence opportunities in a declared window and let the existing 0.04-per-update policy/lifecycle hysteresis operate; do not delete concept entries, fake a collapse tick or infer collapse from missing capture.
5. Test positive detector semantics with separately labeled detached evidence fixtures, plus actual valid-channel controlled execution and autonomous null-capable runs. A controlled successful succession remains a mechanism demonstration, not an autonomous institutionalization result. Cases 25 and 28 use founder-roster-scoped concept/decay mode comparisons: keep the same newborn profile in both arms, verify its actual modes at admission, and estimate direct mode effects only over the fixed founders' eligible lifetime windows. Later entrant/population outcomes remain descriptive. Case 27 compares institutional-memory acquisition opportunities (record/teaching exposure), not a falsely population-wide memory-mode switch; any deliberate initializer-profile contrast is labeled composite rather than single-mode.

### Required Interfaces and Contracts

| # / suffix | Controlled coverage | Research result / contrast |
| --- | --- | --- |
| 24 `narrative-after-witnesses` | Actual eyewitness experience → fresh retellings/record interpretation → all direct witness deaths → later owner narrative with lineage | Surviving, changed or absent narratives; record/retelling opportunities contrast; no mandatory myth |
| 25 `persistent-role` | Recurring function and independent role-directed evidence processed by owner policies; repeated personal influence alone is negative control | Candidate role recognition/persistence and disagreement; role cognition off/on |
| 26 `office-succession` | Objective death; stable owner-local role and vacant/contested/new-occupant claims tied to valid evidence | Role continuity/succession or no succession; support opportunities absent/present |
| 27 `institutional-persistence` | Actual cohort turnover and later role/procedure acquisition via ordinary channels; no content inherited at entry | Cross-generation concept/office/memory persistence with coverage; memory channels absent/present |
| 28 `institutional-decay` | Evidence renewal/nonrenewal windows and owner policy updates; source receipts retained through disappearance | Transformation, decay, collapse or no candidate; decay off/on; missing windows censored |

No government, religion, court, leader class or objective institutional permissions. Institutional analytical labels do not become agent beliefs automatically. A case without a candidate can pass research execution but cannot claim positive persistence/decay coverage; required controlled policy/transition checks must still execute.

### Requirement Evidence

Original Request scenarios 24–28 and scientific constraints; `tests/unit/test_offices_recognition.py`, `tests/unit/test_offices_succession.py`; `.ai-factory/ARCHITECTURE.md` — V3-33/V3-34 seams.

### Error Handling and Logging

Same-root support is dependent testimony; missing owner histories yield explicit partial availability. Keep `institution_complete_search=False` when the source cannot prove exhaustive absence. DEBUG counts/window IDs, INFO scenario status, ERROR safe ownership/lineage violations; no role labels or narratives.

### Tests and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_v3_benchmark_institutions.py tests/unit/test_offices_recognition.py tests/unit/test_offices_succession.py -q`.

Cover zero candidate, same-root false corroboration, competing successors, false death testimony contradicted by live return, actual occupant death, entrant blank then learned role evidence, nonrefresh/renewal, incomplete decay windows and owner-local identity retention. No positive emergence assertion in autonomous tests.

### Acceptance Criteria

Cases 24–28 distinguish real social recognition from physical state and retain evidence through turnover. Controlled recognition transitions and null research both have truthful status.

## Task 13: Execute founder perturbations and multigeneration grouped forks

### Intent

Implement actual replay forks, not identical independent config arms or a scripted divergent outcome.

### Implementation Steps

1. Register `v3-bench-29-founder-contingency` and `v3-bench-30-multigeneration-fork` as grouped-only. Adapt existing BN `PathDependenceSpec`, closed Give/Wait interventions, contrast selectors and sibling artifacts. Case 29 uses the shipped food opportunity with F=4/H=96 and the Phase 1 smoke lifecycle. Case 30 uses F=12/H=96, entry interval 2, generation length 4, lifespan 24 and cap 12, so several admitted cohort labels already exist before the fork while the founder remains alive. This faster cohort schedule is an explicit recipe override, identical in both children. Research uses H=192 and the same eligibility design.
2. Validate F/H and existing food-opportunity eligibility before treatment assignment. Reconstruct the BN design atomically: update base `stop_policy.max_ticks`, `horizon_tick`, post-fork window endpoints and every fork-relative schedule consistently. Explicitly set `max_generation_index=None`, `stop_on_extinction=False`, `population_threshold=None` and no custom stop criteria; never inherit BN smoke cap 16 or comparison cap 6. Preserve the reserved item and founder/recipient co-location through the declared BN pre-fork Wait schedule covering every tick before the chosen F; do not change eligibility after observing outcomes. Record the exact fixture identity and actor/item witness in the design artifact. Grouped interventions remain bounded Give/Wait ordinary commands. If the declared fixture is ineligible, fail its mechanism coverage rather than choose another actor or search a seed.
3. Seal parent prefix, capture complete process-local owner/runtime state, restore independent child engines and apply small commands through normal admission. Verify parent hash/history immutable before/after both children. Include a same-command/same-identity child twin proving restoration parity before interpreting any contrast.
4. Add optional pre-run child installer and post-completion finalizer hooks to `PathDependenceExecutionContext`, default `None`. Install actual lineage/civilization capture before each child continues; existing post-run child observer is insufficient for reconstructing missed owner histories. Isolate sinks per child; expose publication receipts to benchmark reports. Use Task 4's terminal-safe finalized research exporter in the existing post-run child observer, before `aclose`; never request a terminal fork checkpoint or substitute F/H-1 as the endpoint. Child capture/observer failure cannot alter scientific execution.
5. Use existing seven-domain detached outcome and seed-block comparison machinery. Report distances/contrasts including zero; do not assert that the small intervention must create divergent societies. Preserve slot, arm, parent/child, stochastic and evidence identities; do not merge independent runs into a fake family.

### Required Interfaces and Contracts

Case 29 measures founder-event path dependence; case 30 proves fork-after-cohort-entry continuation, subsequent turnover and later generation replay. Both require common-prefix identity and actual child lineage, but positive divergence is not a gate. Both `mechanism` and `research` lanes use the genuine grouped protocol: the mechanism lane additionally checks exact restoration/admission coverage, while the research lane estimates the predeclared interventions' outcomes across numeric seeds. Prefix controls and assigned Give/Wait treatments remain present in grouped research, explicitly labeled `grouped_intervention`; they are not unassisted emergence. Only static bounded star forks are planned, not nested/adaptive branches. Recorded/live LLM forks stay unsupported. Durable completed-child adoption is allowed; unused child reconstruction after process loss repeats the exact deterministic prefix, not a fabricated subjective resume.

### Requirement Evidence

Original Request scenarios 29–30 and Replay invariants; `docs/historical-contingency.md` — common prefix, eligibility, lineage and process-loss limits; `src/experiments/path_dependence_models.py` — Give/Wait and deterministic-fake allowlists.

### Error Handling and Logging

Ineligible prefix is explicit, not a failed causal outcome and not silently dropped from denominators. Wrong parent digest, mutated hidden state, grouped-as-independent routing and recording policy mismatch fail closed. Safe logs include parent/child IDs, F/H, counts and reason codes; no checkpoint/payload contents.

### Tests and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_v3_benchmark_forks.py tests/unit/test_path_dependence_replay_parity.py tests/unit/test_path_dependence_comparison.py -q`.

Test same-prefix/no-op twins; Give/Wait application receipts; unchanged parent; F=12 actual earlier cohort admissions and later deaths/generation entry; all stop selectors and design/window/horizon consistency; completed children reach exactly H=96/H=192 despite higher observed generation indices; terminal source projection is H, not an earlier checkpoint; source identity tamper; missing pair; zero difference; hooks off/on/fail; process-loss planned-child reconstruction; live/recorded provider rejection. Persistence and UI integration are later gates.

### Acceptance Criteria

Cases 29–30 retain true parent/child historical lineage and reproduce eligible multi-generation continuations without promising divergence or durable subjective restart.

## Phase Risks and Mitigations

- Existing BN eligibility assumes a founder food opportunity: lock an explicit pre-treatment fixture/actor witness and test it before running comparisons.
- Child post-run capture cannot recover past cognition: require pre-run capture installation and distinguish missing past evidence.

## Phase Completion Checklist

- Verify Tasks 12–13; update index only.
- Never weaken null-result semantics to satisfy a visual or scientific demonstration.
