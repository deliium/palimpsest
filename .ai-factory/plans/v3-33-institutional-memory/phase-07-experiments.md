# Phase 7: Reproducible opportunities and adversarial proofs

Plan: [index.md](index.md)
Tasks: 12–13
Depends on: Tasks 1–11

## Objective
Provide a reproducible off-gate experiment and causal tests proving no telepathy, while allowing zero institutional emergence or knowledge transfer.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|---|---|---|
| `src/experiments/institutionalization_scenario.py` | `institutionalization_scenario`, `_composed_channels` | BF composes ordinary opportunities, not preseeded institutions. |
| `src/experiments/mediation_scenario.py` | `mediation_opportunities_scenario`, `assert_mediation_structure` | BI's v4/prior-schema/on-arm, structural-only arbiter pattern. |
| `src/experiments/catalog.py` | `experiment_bi_mediation_opportunities` and registry near 2779 | Off-gate catalog registration. |
| `tests/unit/test_experiment_bi.py` | runner execution, collector, checkpoint and repeatability cases | Verify actual completed runs, not only scenario construction. |
| `tests/architecture/test_v3_offices_isolation.py` | owner/world/analysis boundary checks | Extend authority/isolation proof for the new mode. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/experiments/institutional_memory_scenario.py` | create | Experiment BJ opportunity arms and structural arbiter. |
| `src/experiments/catalog.py` | modify | `experiment_bj_institutional_memory`, off-gate ID registration. |
| `src/experiments/__init__.py` | modify | Public scenario/catalog export. |
| `tests/unit/test_experiment_bj.py` | create | Config, run, reproducibility and collector integration. |
| `tests/unit/test_institutional_memory_invariants.py` | create | Noninterference, loss, no transfer and deterministic properties. |
| `tests/architecture/test_v3_institutional_memory_isolation.py` | create | Domain/authority/logging isolation. |

## Task 12: Add Experiment BJ institutional-memory opportunities

### Intent
An experiment should expose material/transmission opportunities, not declare a trade office/archive or force successor learning into existence.

### Implementation Steps
1. Introduce `institutional_memory_scenario(*, seed=23, max_ticks=16, seed_matrix=None, base=None) -> ExperimentDefinition` and catalog wrapper `experiment_bj_institutional_memory`. Experiment ID is `institutional_memory@1`, label BJ, off V1 A–E gate.
2. Build from the representative BF/office composition and existing durable-record/repository example specs. Six arms: `bj-baseline` (unmodified v4 baseline), `bj-memory-off` (v52 with mediation enabled and identical objective carriers to treatment), `bj-memory-on` (v53, role cognition and institutional memory on), `bj-record-opportunities` (on plus deterministic artifact interpretation and existing records/repositories), `bj-teaching-opportunities` (on plus teaching mode, without physical records), `bj-limited-opportunities` (on, same material topology but fewer colocated living listeners and no portable readable records). In record/teaching opportunity arms explicitly select the new empty learner admission profile from Task 9; do not change default profile selection in the paired mode-only arms. Give each arm explicit existing spec dependencies; do not set an unowned flag or guarantee admission/learning.
3. Pair `bj-memory-off` with `bj-memory-on` on equal world/bootstrap/seed/stochastic identity and optional old cognition modes; only the new mode/schema differ. Additional opportunity arms need not share identical objective state; mark that difference in labels/definition, not as a causal mode-only contrast.
4. All institutional/office ledgers and factual institutional records start empty. Do not preseed recognized roles, successful handovers, institution types, office content, successor knowledge or compulsory action schedules. Scenario may provide ordinary materials, locations and enabled capabilities; acquired channels can remain absent.
5. Add `assert_institutional_memory_structure(*, ledgers, deterministic_owner_ids)` checking ownership, caps, local references, explicit source receipts and coverage only. Never require a minimum learned-fact count, continuing office, teaching outcome or error-free record.
6. Complete actual small runs from on/off arms; collect result ledgers and new metric documents. Test repeatability over two equal seeds/configs, config fingerprints, command/event results and local ledger output. Round-trip every arm through v53/legacy serialization as applicable.
7. Add the BJ-specific completed-result→collector→`assemble_metric_documents` end-to-end tests here, after both scenario and Task 11 interfaces exist. Assert both new families, explicit empty/partial availability and owner counts even if a run has no acquired entries. Do not put a future-scenario import or skip in Task 11's earlier test files.
8. Add a separate non-emergence mechanism test using real sender `CommandPlanner.plan`/`CognitiveLoop.complete`, an independently selected communicate intention and locally grounded entry. With institutional teaching mode on, the default selector returns `kind=teach` and stamps `im_teach` without skill-domain `AdviceStore` data; submit that actual command through the engine, give the addressed observation to the receiver loop and assert a fresh teaching-acquired entry. With teaching mode off, default selection emits `im_transmit`; a receiver with teaching off ignores actual `im_teach`. No test-only frame assembly substitutes for sender execution.

### Required Interfaces and Contracts
Optional `base` follows existing scenario semantics; explicit invalid type fails. Do not use `MilestoneInterventionArbiter` to force role or knowledge outcomes. Directly scripted evidence chains belong only to mechanism tests, not the claimed emergent production experiment.

### Requirement Evidence
Original examples are illustrative content uses, not institution classes. Architecture — experiments remain off-gate and must not script society or know agents' private state during decisions.

### Error Handling and Logging
Use bounded experiment metadata: arm count, ticks and agents. Unsupported historical-schema plus enabled-mode fixture fails with the expected v53 code; no silent fallback.

### Tests
Registration/off-gate test; all arm exact keys/profile choices and dependencies; no preseeded content; short enabled run exports typed owner order even with no entries; off/baseline export none; live result→collector→two metric documents; actual sender-planner/complete→engine→receiver teaching and transmission paths; seed repeatability; mixed mode owners; structural arbiter rejects foreign owner/dangling source; opportunity differences documented. Known empty/partial harvests must not be represented by an invented successful learning count.

### Acceptance Criteria
BJ executes reproducibly and reports whatever happened, including no institutional memory. The unchanged real BF/BI scenarios still run and their old configs remain decodable.

### Verification
`uv run --frozen --python 3.12.14 pytest tests/unit/test_experiment_bj.py tests/unit/test_experiment_bi.py tests/unit/test_experiment_bf.py tests/unit/test_institutional_memory_metrics.py --cov=experiments --cov=simulation --cov=analysis --cov-report=term -q`

## Task 13: Prove nontelepathy, fallibility and invariants

### Intent
Test the negative guarantees as causal boundaries, not only as absence of direct imports.

### Implementation Steps
1. Add paired noninterference tests: with B's observation, identity and prior ledger fixed, vary A's unseen office ledger, memories, hidden records and analytical history; B's proposed ledger/command must remain identical. No engine or all-owner source can be supplied to the new update interface.
2. Simulate office accession/contested succession with no record exposure or delivery: no inherited entry, source or knowledge. Add newcomers admitted through normal initialization under both an old profile (new mode remains disabled) and the explicit new learner profile (mode on, content empty). The latter must learn only after actual exposure/delivery and cannot read predecessor state. Ownership-spoofed checkpoints, teaching claims and sender IDs fail or remain declared only.
3. Damage/loss tests preserve exactly surviving full facts; no metadata/root/lineage reference restores missing body. Wrong valid transmitted/recorded claims remain wrong/competing; nobody silently corrects them from events. After source destruction, prior learners retain their own entries while fresh owners remain ignorant.
4. Hypothesis: bounded arbitrary frames and truncations; repeated receipt idempotence; mode-off passthrough; deterministic caps/reordering; learned subset never exceeds exposed full facts (except explicitly projected own evidence); no independently counted same-root retelling; no automatic transfer from parent/caregiver/teacher/office relation.
5. AST/import/signature tests reject world-private state, `WorldEvent`, event stores, analysis sources and infrastructure dependencies in the new cognitive modules. Verify analysis is never passed to the loop. Assert public facade exports deliberate and commands/observer semantics remain 43/73.
6. Capture logs/reprs for malicious content tokens, root/context digests and source payloads. Assert none appears; only approved safe metadata does. Ensure tests never require external network/LLM/Postgres.
7. Exercise the states whose reachability changed in this refinement through production paths: owner-planner ignore/unignore metadata → complete → deferred commit; `im_teach` emitted by a real winning sender plan → engine → receiver; and A→B→A institutional retransmission preserving each outer envelope while retaining one claimed institutional root. Assert an intervention replacing the proposed frame-carrying command cannot create an emission receipt.

### Required Interfaces and Contracts
Existing no-telepathy tests remain the baseline. Invariants distinguish actual current access, remembered learned facts, claimed lineage and analytical after-the-fact correlations. No inference that unobserved information is false or globally lost.

### Requirement Evidence
All Original Request prohibitions and index combinations C1–C11; `.ai-factory/RULES.md` axioms 1–6 and 10.

### Error Handling and Logging
Malformed public frames skip safely, programmer/owner violations fail closed; counters expose partial coverage. Property-test failure reports use bounded synthetic tokens, not operational secrets.

### Tests
New invariant and architecture files plus preexisting V1 gate, V2 scientific invariants, artifact-memory isolation, office/mediation isolation and checkpoint continuation.

### Acceptance Criteria
Telepathic accession, remote root lookup, hidden carrier leakage, implicit founder privileges and truth correction each have an explicit failing-path regression test.

### Verification
`uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_memory_invariants.py tests/architecture/test_v3_institutional_memory_isolation.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py --cov=agents.cognition --cov=simulation --cov=analysis --cov-report=term -q`

## Phase Risks and Mitigations
- A short run may produce no records/roles. Mitigation: structural experiment acceptance plus separate deterministic causal mechanism tests; never force emergence.
- Historical family-count pins may be stale. Mitigation: update only executable catalog assertions affected by the two additions; no unrelated historical rewrites.

## Phase Completion Checklist
- Verify Tasks 12–13; progress lives only in index.
