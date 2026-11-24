# Phase 3: Scenarios and measurement

Plan: [index.md](index.md)  
Tasks: 5–7  
Depends on: Phase 2

## Objective
Run matched shared-stock scenarios and quantify stock condition and cooperation without mistaking correlation, testimony or scripted controls for autonomous emergence.

## Current-Code Evidence

| Path | Symbols | Why it matters |
|---|---|---|
| `tests/unit/test_overexploitation_feedback.py` | `_feedback_config`, `_pressure_schedule`, `_rest_schedule` | Real managed-water fixture and stock/mechanism controls |
| `src/experiments/catalog.py`, `src/experiments/medical_beliefs_scenario.py` | `base_runner_config_from_scenario`, `OFF_GATE_MATRIX_EXPERIMENT_IDS`, `medical_beliefs_scenario` | Paired off-gate catalog precedent |
| `src/experiments/models.py` | `ExperimentDefinition.__post_init__`, `_scenario_layout` | All arms in one definition must share the same scenario or resource-stripped layout |
| `src/experiments/overexploitation_history.py`, `src/analysis/overexploitation_history.py` | `history_tick_from_tick_result`, `history_from_tick_results`, `OverexploitationHistoryRow` | Verified pressure coverage and integer stock quantities |
| `src/simulation/runner.py`, `src/simulation/engine.py` | `run`, `run_tick`, `finish_run`, `engine.last_tick_result` | Finalized-boundary and committed objective evidence |
| `src/world/events.py`, `src/simulation/lifecycle.py` | `Drunk`, `TickResult.resolutions` | Distinguish exact node draws, held-item drinks, and attempted actions |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/experiments/commons_governance_scenario.py` | Create | Typed world/config builders and paired experiment definition |
| `src/experiments/{catalog,__init__}.py` | Modify | Off-gate registration and public experiment entry point |
| `src/simulation/{runner,commons_governance_evidence}.py` | Modify/create | Optional neutral finalized-boundary sink and read-only DTOs |
| `src/experiments/commons_governance_capture.py` | Create | Integrate runner evidence and existing ecology history, seal one report |
| `src/analysis/commons_governance_metrics.py` | Create | Pure per-stock summaries and paired seed comparison |
| `tests/unit/test_commons_governance_{scenario,metrics,capture,experiment}.py` | Create | Config, detached metrics, parity and real runner tests |

## Task 5: Register paired shared-stock scenarios

### Intent
Give several agents repeated opportunities to compete for or share finite renewable stock without assigning an arrangement.

### Implementation Steps
1. Build two independent definitions in `commons_governance_scenario.py`: `commons_governance@1` for `shared-pool` and `commons_governance_two_pools@1` for `two-pools`. Expose `experiment_commons_governance` and `experiment_commons_governance_two_pools` alongside adjacent catalog builders; place both IDs in `OFF_GATE_MATRIX_EXPERIMENT_IDS` and export both builders. No V1 gate change or modification to `ExperimentDefinition` validation. Use production DTOs, not imports from tests.
2. Use two layouts: `shared-pool` has one managed pool at a common location with four living founders; `two-pools` has two adjacent locations, each with one pool and two founders, walkable in both directions. Give the second layout detached analytical cohorts of two based on starting location. Both stocks remain open to all physically eligible agents and cohort labels are not passed to the runner or its agents.
3. Start each managed WATER node at baseline and maximum 4.0, renewal 1.0, ecological damage floor 0.5, recovery 0.1, allowance 0. Use V4-37 unit multiplier and supply-chain catalog conventions; no shortages, disease, alternative water supply or random layouts in these arms. Use deterministic baseline cognition, formal rules and deterministic social norm and institution modes in **both** arms, with ordinary co-presence and usable speech. No preloaded policy, norm, rule, claim, role, relationship, agreement, or turn. Start each founder with equal nonurgent thirst need in the planner's ordinary scale; ordinary physiology operates thereafter.
4. Emit exactly two conditions per definition: `shared-pool-off` and `shared-pool-on`, or `two-pools-off` and `two-pools-on`. Give each definition its own `paired_world_group`. Within each layout require the same starting world, founders, config other than version and exact commons sibling, stochastic identity, and 64-tick horizon. Use fixed seeds `(34, 35, 36, 37, 38)` unless the caller supplies an existing typed seed matrix. Never place layouts in the same definition or pair across layouts.

### Required Interfaces and Contracts
Control is v61; treatment is v62 with the configured stock IDs. Off-gate production scenario receives no arbiter, forced wait, or schedule; only seed/layout/ordinary cognition drive it. Compatible with the existing experiment catalog and programmatic capture on both arms.

### Requirement Evidence
Original Request — multiple agents/groups and finite renewable resources; `docs/overexploitation.md` — the existing checked water stock and withdrawal units.

### Error Handling and Logging
Bad base/seed-matrix type, duplicate scenario IDs, or mismatched same-layout pair fail before launch. INFO only experiment ID, arm/layout counts and horizon.

### Tests
Construct both actual `ExperimentDefinition`s, assert two arms and distinct world groups, and verify both catalog IDs/off-gate exports. Assert exact pair equality after removing selector/version, positive renewal, finite caps, and no seeded governance/schedules. Construct all four runner configs via `SimulationRunner.from_config`; include a regression showing an attempt to combine those layouts into one existing definition fails validation.

### Acceptance Criteria
Both layouts produce deterministic, normally runnable scenarios with stock sharing at each managed pool and feasible cross-cohort travel in the second.

### Verification
`uv run --frozen --python 3.12.14 pytest tests/unit/test_commons_governance_scenario.py tests/unit/test_v1_regression_gate.py -q`

## Task 6: Project sustainability and cooperation evidence

### Intent
Produce a detached, denominator-aware report with separate objective and subjective evidence.

### Implementation Steps
1. Add an opt-in, pre-start runner sink, `set_commons_governance_boundary_sink`, fed immutable neutral DTOs at normal fully finalized boundaries. Use `TickResult` and just-finalized owner transition deltas, following the one-way boundary pattern in `SimulationRunner`; ensure disabled runs skip construction of capture rows. Preserve the run result, stop reason and ordinary commit if a sink fails. Implement `run_with_commons_governance_capture` as an experiments wrapper calling `run()` once and sealing after it returns a terminal result; propagate runner exceptions unchanged. Capture both v61 controls selected by explicit research stock IDs and v62 treatments; require the selection to match treatment config. Reject attachment after execution starts; no durable capture/resume promise.
2. Capture finalized deltas before terminal-owner retirement can remove them; stage rows before publication and publish each complete boundary only after owner finalization succeeds. Do not backfill from current ledgers on retry: if the runner cannot recover an exact staged boundary in-process, seal at the first gap. Deduplicate by absolute boundary tick. Cap at 512 ticks, 100,000 committed events and 16,384 owner transition rows; check capacity for the full boundary before appending, with sticky cap/failure status. Return the original terminal result and trusted prefix even on an unsuccessful terminal outcome, marked `partial` if a trustworthy prefix exists and `unavailable` otherwise. Expose expected vs usable ticks/owner boundaries and never interpolate. Report `disabled`, `unavailable`, `partial` and `complete` per lane, with `inapplicable` for the v61 social lane. Complete enabled zero activity is zero; a zero denominator is undefined.
3. Run existing overexploitation history adapter once per selected stock/window. For objective sustainability: initial/end/minimum stock, mean end-stock / baseline, withdrawal and actual renewal totals, renewal / withdrawal, tick counts above threshold (`withdrawal > threshold`), at damage cap, with increasing damage, and with literal zero end stock, mean and terminal damage / baseline. Report counts/covered stock-ticks and raw integer tenths. Separate ordinary `resource_depleted` denials with nonzero stock from literal zero; use correctly attributed source and explicit reason only. Include terminal living founders and sum/mean finalized owner thirst observations where available, with coverage, so reduced extraction does not imply improved welfare.
4. For objective joint use, count distinct founders per pool, attributed `Drunk` by exact `source_id` excluding held-item drinks, two-or-more user ticks, and managed-stock targeted draw attempts where the **effective command** identifies its source. Cross-check summed successful known debits against receipts; retain unattributed residuals instead of guessing. Do not interpret shared use or low draw as cooperation.
5. Subjective cooperation: count independently supported arrangements, opposition and contested heads, monitor checks, access claims, criticism delivered, and verified **explicit voluntary deferrals / non-overridden draws considered with `wait_expected`** (including urgent draws that proceed). Include owner-labeled turn opportunities and owner-matching receipts as separate series; report complementary alternating acts only where supported by matching nonconflicting self-reports; do not label a missed turn as defection. Count support / distinct delivered eligible proposal-recipient opportunities, with delivery identities deduplicated once per `(proposal, addressed receiver)`. Count one actual deferral per `(owner,tick,node)`. Keep analyst-only group labels and observed/mechanism/owner-claim buckets separate; no composite cooperation or sustainability score.
6. Return frozen report `commons-governance-report-v1` with canonical ordering by stock, tick, owner and proposal where applicable; each ledger lane includes reason codes and its denominators. Analysis receives detached primitive/typed row values only and does not import experiments or concrete runner services.

### Required Interfaces and Contracts
Sustainability and joint-use measures are comparable across matched arms on common complete windows. Governance-specific measures are attribution-limited, treatment descriptive and never fabricated for controls. Keep explicit proposed-versus-effective decision stage in denominators; preserve rejected attempt status and separation of observer and research lanes.

### Requirement Evidence
Original Request — measure sustainability and cooperation; `docs/overexploitation.md` — transition, history coverage and denial/zero distinction.

### Error Handling and Logging
Disable capture after first passive sink error; preserve original result. Return closed cap/gap/invalid-scope reasons with DEBUG or WARN aggregate counts only, never rows, speech, observations or private identifiers.

### Tests
Test exact integer example, damaged-at-floor vs incremental damage, no renewal/no withdrawals, zero denominators, two stocks, attribution gaps, owner duplicate/drop, report coverage, invalid scope, disabled vs complete-empty, partial prefix and capture failure twin. Use the actual V4-37 drawdown fixture as an end-to-end objective measure oracle.

### Acceptance Criteria
No sustainability number requires inference from a missing tick; no cooperation number is inferred from lower extraction or successful message submission.

### Verification
`uv run --frozen --python 3.12.14 pytest tests/unit/test_commons_governance_metrics.py tests/unit/test_commons_governance_capture.py tests/unit/test_overexploitation_history.py -q`

## Task 7: Separate controlled proofs and autonomous comparisons

### Intent
Verify the mechanisms without claiming that scripted behavior emerged, and make null autonomous results publishable.

### Implementation Steps
1. Add test-only mechanism lanes: repeated draws versus idle/recovery; delivered rest support then a legal override draw against a private arrangement; competing claim or stance; turn opportunities with complementary reports and a separate missing-slot negative; and grounded criticism versus silence. In one real-runner negotiation, use the test arbiter only to establish prior evidence. At the decisive tick use a deterministic test planner proposing `Drink` and no effective-command override. Assert the unassisted adapter changes it to `Wait`, the engine receives `Wait`, and finalized capture records one deferral. Verify abstaining or opting out does not remove access. No scheduled commands in production builders.
2. Repeat autonomous twins on seed 34 for both definitions and compare canonical evidence, world events and stop outputs after excluding run IDs and operational timestamps. Run both definitions for all predeclared seeds in a documented programmatic batch. Report matched identity with layout, numeric seed, replicate ordinal, stochastic identity, declared horizon and canonical config fingerprint excluding only the tested selector and version. Match exact off/on replicates before computing differences; reject duplicate arm identities and exclude incomplete or mismatched pairs with reasons. Average paired differences within numeric seed, then report median/range across seed blocks with n; replicas are not independent seed blocks. Evaluate only common complete lanes and keep complete nulls, early stops, and capture gaps distinct.
3. Do not set an adoption, sanction, cooperation or sustainability improvement threshold as a test gate. A complete null is valid; controlled mechanism failures are not. Describe measured utilization, cooperation and exposure as separate outcomes; do not claim that governance caused changes unless the inference is limited to the declared paired treatment effect.

### Required Interfaces and Contracts
`compare_commons_governance_reports` accepts validated neutral matched reports, returns per-layout descriptive summaries and provenance. It rejects mismatched selectors or arms, retains unavailable comparisons, and does not merge mechanism and autonomous lanes.

### Requirement Evidence
Original Request — allow, not require, emergence; `docs/overexploitation.md` — controlled mechanism proof is not autonomous prevalence.

### Error Handling and Logging
Duplicate ambiguous pairing, mixed schedules or unknown lane may not silently enter comparison. Log seeded-pair counts and reason codes only.

### Tests
Use deterministic well-formed null, mismatched conditions, duplicate numeric seed, missing arm, early-stop coverage, cross-layout and capture-lane examples. Test ordinary runner replay and deterministic twins; controlled tests must not assert a null as a mechanism success.

### Acceptance Criteria
An independent implementer can reproduce both controlled and autonomous lanes and tell exactly what was measured and what was not.

### Verification
`uv run --frozen --python 3.12.14 pytest tests/unit/test_commons_governance_experiment.py -q`

## Phase Risks and Mitigations
- Risk: a schedule, absence of observed damage, missing data or a testimony count is reported as emergence. Mitigation: tag lanes, validate matches, preserve gaps and publish separate stock, participation, and subjective measures.

## Phase Completion Checklist
- All three tasks meet their criteria; run the focused suite with coverage and update only the index.
