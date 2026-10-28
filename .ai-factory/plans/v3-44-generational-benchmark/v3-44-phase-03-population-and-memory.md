# Phase 3: Population, teaching and historical memory scenarios

Plan: [index.md](index.md)
Tasks: 6–7
Depends on: Tasks 1–5

## Objective

Implement scenarios 1–7 as actual engine/cognition trajectories with retained owner-qualified evidence. Physical record survival, subjective belief and objective truth remain different outcomes.

## Current-Code Evidence

| Path | Symbols / cases | Why it matters |
| --- | --- | --- |
| `src/experiments/catalog.py` | `experiment_ae_generational_population`, `experiment_af_new_agent_bootstrap`, `experiment_ai_dependency_caregiving`, `experiment_ak_intergenerational_mentorship`, `experiment_al_cultural_transmission_provenance`, `experiment_am_historical_memory_layers`, `experiment_an_durable_records` | Existing mechanism configurations and collectors |
| `src/agents/cognition/developmental_learning.py` | `apply_developmental_acquisition` | Gradual owner-scoped acquisition |
| `tests/unit/test_caregiving_bias_emergence.py` | parent edge does not force care; non-kin/shared care cases | No hard-coded parent obligation |
| `tests/unit/test_artifact_memory_boundary.py` | scene memory omits marks; interpretation hook gating | No automatic record download |
| `tests/unit/test_durable_record_resolution.py` | copy/damage/loss/destroy | Physical record persistence mechanisms |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/experiments/civilization_benchmark_population.py` | create | Cases 01–04 |
| `src/experiments/civilization_benchmark_memory.py` | create | Cases 05–07 |
| `src/experiments/civilization_benchmark_suite.py` | modify | Register builders and selectors |
| `tests/unit/test_v3_benchmark_population.py`, `tests/unit/test_v3_benchmark_memory.py` | create | Valid-channel mechanism runs and unavailable/null cases |

## Task 6: Exercise blank entry, care, teaching and cultural mutation

### Intent

Prove learning mechanisms without granting inherited knowledge or treating social care and cultural change as guaranteed.

### Implementation Steps

1. Implement the four rows below using Phase 1 atomic v55 composition. Record exact stage/lifespan/supply and spawn schedules in the recipe; founders begin with physical resources and empty subjective stores. Controlled opportunities start with ordinary firsthand experience before any communication.
2. For mechanism lane, issue bounded legal commands via Phase 2 scheduling. Select actual entrant recipients from admitted IDs; never assume a name prefix is proof of entry or generation. Require qualifying source events and actual addressed delivery for teaching/transmission evidence.
3. For research lane, remove command overrides. Compare opportunity/channel on versus off with identical schedules and world identity. Use ordinary policies, not assigned caregiver/teacher/cultural roles. Measure exposure, acquisition and non-acquisition separately.
4. Fold finalized capture through existing collectors and cultural evidence. Preserve donor/recipient owner IDs, parent roots, channel, acquisition time, mutation/recombination policy/version and confidence/coverage. A later matching label is not a proven transmission edge.

### Required Interfaces and Contracts

| # / scenario ID suffix | Config / mechanism recipe | Required structural evidence | Research outcome / contrast |
| --- | --- | --- | --- |
| 01 `blank-slate` | Lifecycle + explicit init + kinship when parent links are tested; entrant binds after founder activity | All real newcomer stores empty before first cognition; distinct IDs; genealogy does not copy memories; later acquisitions cite valid exposure | Acquisition latency and source fractions; developmental learner versus default learner, no positive acquisition requirement |
| 02 `dependent-care` | Dependency-care spec; dependent deficits, co-located non-kin and kin opportunities; legal `Feed`/`Transport` and unattended control prefix | Applied care changes only eligible physical needs/placement; self-satisfaction denial; independent/shared care and neglect legal | Care/neglect frequencies and unmet-need outcomes; care cognition off/on, no mandated parental care |
| 03 `intergenerational-teaching` | Developmental learning + mentorship + deterministic skill/teaching modes; founder gains firsthand skill, communicates/teaches entrant | Applied delivery; fresh recipient acquisition and competence audits with source lineage; no `Teach` world command or copied donor state | Teaching attempts, successful uptake, skill retention; teaching opportunity absent/present |
| 04 `cultural-mutation` | Cultural provenance + declared deterministic mutation/recombination policy and developmental learner | At least two real owner/cohort acquisitions through valid channels; mutation marker, when produced, cites source roots; no inserted cultural ledger | Fidelity/mutation/recombination measures and null change; uptake-channel contrast |

Controlled tests can use policy-level positive/negative fixtures to verify mutation arithmetic separately. Such fixtures are labeled synthetic policy evidence, never end-to-end emergence. Mutation is not required in every autonomous run; valid acquisition/provenance remains required mechanism coverage.

### Requirement Evidence

Original Request scenarios 1–4 and generational invariants; `tests/unit/test_new_agent_blank_slate_guard.py`; `tests/unit/test_dependency_care_actions_replay.py`; `docs/experiments.md` — generational treatments.

### Error Handling and Logging

Reject foreign-owner sources; missing pre-cognition sample or unused required milestone fails coverage. Missing capture is unknown, not no-learning. DEBUG exposure/acquisition counts, INFO case status, WARN incomplete capture, ERROR invariant codes only; no content.

### Tests

Actual newcomer snapshots; deliberate leaking test double; parent/non-parent/shared/no care; recipient mode off; repeated same-root testimony cannot inflate support; mutation/recombination lineage; no exposure means no acquisition; paired policy-off passthrough. Tests exercise positive and negative policy detection without demanding a positive research effect.

### Acceptance Criteria and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_v3_benchmark_population.py tests/unit/test_v3_developmental_learning_regression.py -q` passes. Cases 01–04 report eligible evidence and distinguish learning from copying.

## Task 7: Exercise memory layers and true or false surviving records

### Intent

Knowledge can outlive witnesses through communication and physical records, but age and inscription never turn testimony into truth.

### Implementation Steps

1. Implement cases 05–07 with existing historical-layer and durable-record specs. Declare a simple physical occurrence witnessed by a limited founder set, a predeclared proposition and analysis-only truth reference. Use `StoryTruthSpec`/analysis truth contracts only in trusted experiment/analysis composition, never in cognition, observations, marks or prompts.
2. Schedule one firsthand event, addressed retelling to a nonwitness, optional further retelling to an admitted cohort and natural lifespan deaths. Identify the actual direct-witness set from perception/delivery evidence, not all agents alive at the event. Evaluate living/communicative/cultural classifications at exact finalized windows.
3. For record cases, use legal `Inscribe` and optionally `CopyRecord`/repository commands. Read only through current visible interpreted records or actual addressed delivery; do not insert episodic traces from the event archive. Wait for all recorded direct witnesses to die while later owners remain alive. Track record identity, holder/location, revisions, integrity and physical lineage.
4. Add a destructive physical control using legal `DamageRecord`/destruction behavior and an interpretation-disabled control. False record claims deliberately disagree with the detached truth spec but contain no `is_false` marker in agent-facing data. The engine must preserve those marks without correcting their meaning.

### Required Interfaces and Contracts

| # / suffix | Controlled mechanism | Required evidence | Autonomous measurement |
| --- | --- | --- | --- |
| 05 `memory-layers` | Firsthand event → delivered retellings → living-witness extinction → later reception | Owner-scoped fresh traces and channel/root lineage; exact witness-death boundary; layer classifier uses retained evidence | Layer survival/coverage; retelling opportunities present/absent |
| 06 `record-after-witnesses` | Inscription before witness deaths; later entrant interprets surviving physical record | Physical record survives; dead author stops acting; recipient cites actual current record reading; damaged/destroyed control cannot magically restore it | Record/knowledge retention beyond lifetimes; records available/unavailable |
| 07 `false-record` | False inscription with analysis-only expected value; later valid reading and optional transmission | Physical marks persist even when false; belief can remain false/uncertain; no truth correction channel | Misinformation persistence/uptake or rejection; accurate versus false declared record content is an explicit content treatment, not a truth label in cognition |

Episodic traces, record marks, retained practical knowledge and historical-layer classification have separate selectors. A physically intact but unread record does not prove learned knowledge; a false record need not convince everyone to pass the mechanism test.

### Requirement Evidence

Original Request scenarios 5–7; `src/experiments/interventions.py` — truth remains analysis-only; `docs/cultural-evolution-metrics.md` — provenance and availability.

### Error Handling and Logging

No witnessed source, missing mortality window or failed inscription yields `not_exercised`, not success. Unknown reader inventory stays unknown. Logs contain record IDs/counts and safe reason codes only, never marks, claims or witness memory.

### Tests

Record author/all witnesses dead; entrant blank then exposed; accurate/false marks survive; intact-unread versus destroyed records; disabled interpretation; retelling same-root lineage; invalid objective truth lookup architecture regression; complete-empty versus missing capture.

### Acceptance Criteria and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_v3_benchmark_memory.py tests/unit/test_artifact_memory_boundary.py tests/unit/test_durable_record_resolution.py -q` passes. The benchmark demonstrates surviving physical information without granting omniscient history.

## Phase Risks and Mitigations

- A controlled retelling can be mistaken for spontaneous culture: persist lane and override receipts in every result.
- Witnesses may survive a planned tick: use objective death events and actual witness identities; never force analytical extinction by hiding a living holder.

## Phase Completion Checklist

- Verify Tasks 6–7; update index only.
- Every positive claim references an actual source/recipient and finalized boundary.
