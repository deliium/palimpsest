# Phase 4: Detached lineage, comparisons, and metrics

Plan: [index.md](index.md)
Tasks: 13–16
Depends on: Tasks 1–12

## Objective

Publish descriptive replication evidence while preserving objective occurrences, owner testimony, and analytical comparisons as separate layers.

## Current-Code Evidence

| Path | Symbols / behavior | Significance |
| --- | --- | --- |
| `src/analysis/scientific_hypotheses_contract.py` | layer/coverage/availability enums, token minting, leakage assertions | Pattern for separated, metadata-safe analytical contracts. |
| `src/analysis/scientific_hypotheses_analysis.py` | `harvest_scientific_hypotheses_analysis`, counts-oriented digest | Do not use its digest as full replication identity. |
| `src/analysis/scientific_hypotheses_policy.py` | `ScientificHypothesesPolicy` | Existing 32-tick windows, 512-window bound, minimum 3 samples. |
| `src/experiments/scientific_hypotheses_completed_run.py` | `scientific_hypothesis_facts`, `build_completed_run_scientific_hypotheses_analysis` | Trusted bridge from owner exports and events. |
| `src/analysis/specifications.py` | `MetricFamilyId`, closed value keys, registration | Append six families, preserve first 250. |
| `src/analysis/metric_service.py` | `MetricComputationInputs`, `assemble_metric_documents` | Optional detached input, no live science feedback. |
| `src/experiments/collectors.py` | `assemble_arm_metric_bundle` | Completed-run composition only. |

## Files to Change

Create `src/analysis/replication_contract.py`, `replication_rows.py`, `replication_policy.py`, `replication_analysis.py`, `replication_metrics.py`, and `src/experiments/replication_completed_run.py`. Modify analysis metric service/specifications, experiment collectors and intentional facades. Create `tests/unit/test_replication_layers.py`, `test_replication_analysis.py`, `test_replication_metrics.py`, `test_replication_completed_run.py`, `test_replication_analysis_properties.py`.

## Task 13: Define detached facts, scoped identities, and layer guards

### Intent

Carry trial-level evidence before aggregation instead of reverse-engineering it from published hypothesis counts.

### Implementation Steps

1. Define neutral frozen `ReplicationDesignFact`, `ReplicationAttemptFact`, `ReplicationReportFact`, `ReplicationInterpretationFact`, `ReplicationCollaborationFact` and `ReplicationExecutionFact`. Analysis imports no cognition classes; the experiment bridge maps them explicitly.
2. Objective execution receipts come only from committed `ExperimentResolved` occurrences: qualified event token, source tick, performer token, categorical outcome, operator/process metadata that committed events actually expose. Never read private law rows or infer a claimed replication link from a matching event count.
3. Owner fact rows carry pseudonymous participant token, design payload digest, lineage references, source/root tokens, condition tokens, uncertainty kind/alternatives, submission reference and claimed participation/appraisals. Tokenize raw agents/entities/events using run-scoped namespaces in the trusted bridge. Do not publish raw owner IDs, operand IDs, condition values that are agent IDs, or message bodies.
4. Separate output types: `ReplicationObjectiveRow`, `ReplicationOwnerReportRow`, `ReplicationComparisonRow`, `ReplicationCoverageRow`. Objective rows contain observed facts only; owner rows contain claims only; comparisons contain derived qualifications only. Add hard field/type leakage assertions.
5. Published design records contain operator/process, family/kind selector modes, tokenized condition values and immutable lineage—not executable raw entity references. Research publications are not messages cognition can adopt.
6. Identity uses full canonical row/payload content. Namespace trial, participant, design and report references separately; use the exact schema/mapping contract below, not independently minted IDs at each publication stage. No equality assumption from legacy `claim_token`. Distinct committed events prove distinct executions, not statistically independent samples.

### Required Interfaces and Contracts

New `ReplicationAnalysis` has exact fields `policy_version`, `designs`, `attempts`, `executions`, `reports`, `comparisons`, `interpretations`, `collaborations`, `coverage`, `notices`. Each collection is an immutable tuple of the matching output row type below; notices are bounded closed reason codes. Policy version `scientific-replication.v1`; window size 32, maximum 512 windows, minimum 3 samples; caps 64 participants, 4,096 designs/attempts/execution rows, 8,192 reports/interpretations/comparison edges, and 2,048 owner collaboration rows per analysis. Publication merges executions/reports into the tagged `results` tuple without discarding either lane.

### Exact Detached Fact and Identity Contract

All facts are frozen neutral DTOs in `replication_rows.py`; analysis must not import cognition models. Tokens are bounded nonempty strings, optional references are explicit nulls, ticks/counts are exact nonnegative integers, conditions are sorted unique `(slot, token)` pairs, and enums use the closed Phase 1 vocabularies. No free-text notice/proposition field is permitted. The trusted bridge validates raw input before mapping it.

| Fact | Exact fields |
| --- | --- |
| `ReplicationDesignFact` | `design_token`, `source_design_digest`, `origin_token`, `parent_design_token`, `source_hypothesis_token`, `source_trial_token`, `created_tick`, `operator`, `process_token`, `operand_a_selector`, `operand_b_selector`, `predicted_outcome`, `conditions` |
| `ReplicationAttemptFact` | `attempt_token`, `participant_token`, `design_token`, `source_trial_token`, `collaboration_token`, `hypothesis_token`, `request_tick`, `submission_tick`, `observation_tick`, `operand_a_token`, `operand_b_token`, `condition_snapshot`, `condition_comparison`, `state`, `result_root_token`, `reason_codes` |
| `ReplicationReportFact` | `local_report_token`, `origin_report_token`, `participant_token`, `performer_claim_token`, `design_token`, `attempt_token`, `source_trial_token`, `result_root_token`, `report_tick`, `measurement`, `declared_measurement_basis`, `condition_snapshot`, `collaboration_token`, `delivery_token`, `provenance_kind`, `claim_digest` |
| `ReplicationInterpretationFact` | `interpretation_token`, `participant_token`, `design_token`, `origin_report_token`, `local_report_token`, `invitation_token`, `collaboration_token`, `revision_index`, `revision_tick`, `appraisal`, `condition_comparison`, `source_appraisal`, `uncertainty_notice`, `reason_codes` |
| `ReplicationCollaborationFact` | `collaboration_token`, `participant_token`, `invitation_token`, `design_token`, `source_trial_token`, `inviter_token`, `group_claim_token`, `status`, `created_tick`, `updated_tick`, `participant_declarations` |
| `ReplicationExecutionFact` | `execution_token`, `result_root_token`, `participant_token`, `execution_tick`, `operator`, `process_token`, `operand_a_token`, `operand_b_token`, `outcome` |

Selector records are exact `{family, kind, binding_mode, exact_entity_token}`; optional exact targets are tokenized, never raw executable IDs. Measurements retain exact Phase 1 fields with receiver-relative `basis`; `declared_measurement_basis` separately preserves what a communicated source claimed. Declaration records are exact `{participant_token, act, tick, delivery_token}` and prove the attributed speech only. Attempt/source-draft actor body bindings are validated in runtime; the trusted bridge also checks them against run registration evidence/configured agent bindings before associating an objective execution. Missing dynamic registration evidence yields an unresolved participant/execution link, never a guessed `agent-` ↔ `body-` string conversion.

Use one bridge-owned identity map for the whole analysis, and the same map for every referencing field. A public token is `<prefix>-` plus 32 SHA-256 hex characters of canonical ASCII JSON `["scientific-replication.v1", run_id, namespace, original_reference]`. Do not hash an already normalized public token again.

| Namespace / prefix | Original reference and all consumers |
| --- | --- |
| `design` / `rpd` | Received/frozen wire design token; design rows, parent references, attempts, reports, interpretations, invitations |
| `trial` / `rpt` | Wire `rtrl` root; founding source, invited source, child result root, execution fact, every comparison |
| `execution` / `rpe` | Actual committed event ID; objective receipt, optional report association, comparison source/child execution |
| `participant` / `rpp` | Validated registered agent ID; report owner, actual performer, interpretation owner, declarations |
| `entity` / `rpen` | Raw entity ID in operand/location/exact-selector references |
| `hypothesis` / `rph` | Owner-qualified local hypothesis ID or declared source hypothesis token; no condition-based inference |
| `report` / `rpr` | Immutable wire origin report token, preserved across receivers |
| `local_report` / `rplr` | Owner-qualified local report handle/content version; receiver-specific evidence and appraisals |
| `attempt` / `rpa` | Owner-qualified attempt ID |
| `invitation` / `rpi` | Immutable invitation ID; replies and participant declarations |
| `collaboration` / `rpc` | Invitation ID, not owner-local collaboration ordinal; source and recipient rows share a qualified context |
| `origin`, `group`, `delivery`, `interpretation` | Their explicit opaque/raw references, with distinct `rpo`, `rpg`, `rpdl`, `rpin` prefixes; owner-qualify local interpretation IDs |

Categorical condition values such as weather/day phase remain closed vocabulary tokens. Entity-valued location/counterpart slots use the map; opaque action/concept values are namespaced hashed condition tokens rather than exposed content. The original design digest is opaque source identity, not a digest recomputable from the privacy-projected design row. Artifact canonical integrity is computed independently over the full projected snapshot.

`replication_facts` returns only normalized facts; `harvest_replication_analysis` consumes normalized facts and execution facts and does not re-tokenize them. Build `ReplicationExecutionFact` only from actual committed `ExperimentResolved` details in the trusted completed-run bridge. Construct the declared wire trial reference from actor/event identity using the public pure reference helper, then map it once. A claimed root matching a real occurrence does not validate the report's content.

### Error Handling and Logging

Invalid typed inputs fail closed. Source tokens with no matching event remain declared-only, not authentic. Cap overflow produces partial coverage with retained/excluded counts. DEBUG layer/row counts, WARN cap code; never raw IDs, conditions or content digests.

### Tests / Acceptance / Verification

`test_replication_layers.py` checks all forbidden cross-layer fields, token namespaces, raw-ID canaries, equal-count/different-content identity, malformed facts and caps. Run `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_replication_layers.py -q`.

## Task 14: Reconstruct replication edges and qualified outcome comparisons

### Intent

Distinguish declared replication, distinct execution, protocol variation and genuine missing evidence.

### Implementation Steps

1. Implement `harvest_replication_analysis(executions, facts, policy)` as a deterministic pure fold over finalized neutral inputs. Sort by absolute tick, qualified event/row token; assign fixed 32-tick windows. It accepts already-normalized facts, never raw cognition ledgers; the completed-run bridge owns the single normalization pass.
2. Link source trial → child attempt only from explicit frozen source/design references. Edges retain `repeat`, `adapted`, `unknown`; missing parents/sources stay unresolved. Do not infer a relation because two hypotheses have equal labels, predictions or operands.
3. Qualify evidence with `execution_backed`, `declared_only`, `duplicate_source`, `unresolved`, `unavailable`. Validate attempt correlation against event performer/tick/operator/operands in the detached bridge. Mark multiple possible matches ambiguous; never choose whichever makes replication look successful.
4. Compare known condition snapshots: `matched`, `different`, `unknown`. Source/child result categories remain individual facts. Derived relation is `compatible`, `conflicting`, `inconclusive`, or `not_comparable` using Phase 1 rules, never a hypothesis verdict.
5. Preserve observed category difference even when condition difference or missing uncertainty prevents an exact comparison. Emit separate `category_difference` and qualification, not a misleading binary replication-success rate.
6. Group/collaboration rows summarize actual attributed declarations and linked individual executions. Optional group claim tokens cannot create a society/group identity, merge participant ledgers, or upgrade claims into membership.
7. Coverage counts expected/exported participants, submitted/observed/unresolved attempts, missing source/condition/uncertainty, repeated roots and excluded overflow. Retained owner caps prohibit claiming whole-run completeness without retention proof.

### Required Interfaces and Contracts

`complete`, `partial`, `missing` coverage and `available`, `insufficient_samples`, `unavailable` availability are distinct. Unknown samples stay out of compatible/conflicting denominators and have explicit exclusion counts. No causal/statistical independence assertion follows from distinct owner IDs or trials.

### Exact Analytical Row Contract

Every output record has `row_token`, `window_index`, `layer`. A row token is the full-content digest specified in Phase 5, with closed `record_type` values `design`, `attempt`, `execution`, `report`, `comparison`, `interpretation`, `collaboration`, `coverage` and excluding `row_token` itself; append the exact fields below. Implement this pure identity function in the analysis contract and independently verify it in the simulation codec without an analysis import. Canonicalize arrays before hashing. Preserve different claimed content with distinct row tokens even when it names the same origin report.

| Output record | Layer / additional fields |
| --- | --- |
| `ReplicationDesignRow` | `owner_scoped`; all design fact fields. It is a declared protocol, not an objective law. |
| `ReplicationAttemptRow` | `owner_scoped`; all attempt fact fields. Submission intent is not execution proof. |
| `ReplicationObjectiveRow` | `objective`; `row_kind="execution"` and all execution fact fields. |
| `ReplicationOwnerReportRow` | `owner_scoped`; `row_kind="report"`, all report fact fields, `associated_execution_token` (nullable reference only, not content verification). |
| `ReplicationInterpretationRow` | `owner_scoped`; all interpretation fact fields. One row per retained revision. |
| `ReplicationCollaborationRow` | `owner_scoped`; all collaboration fact fields. Context identity is not authoritative membership. |
| `ReplicationComparisonRow` | `detached_analysis`; `comparison_token`, `basis`, `participant_token`, `source_trial_token`, `attempt_token`, `source_execution_token`, `child_execution_token`, `source_report_token`, `child_report_token`, `source_outcome`, `child_outcome`, `design_token`, `parent_design_token`, `relation_kind`, `condition_comparison`, `category_difference`, `appraisal`, `evidence_qualification`, `excluded_reason`, `collaboration_token`. |
| `ReplicationCoverageRow` | `detached_analysis`; `expected_participants`, `exported_participants`, `submitted_count`, `observed_count`, `unresolved_count`, `missing_source_count`, `missing_condition_count`, `unreported_uncertainty_count`, `duplicate_source_count`, `excluded_overflow_count`, `coverage`, `availability`, `reason_codes`. |

Comparison `basis` is `execution` or `reported`. Execution rows compare committed source/child categories; reported rows compare the particular owner's retained source/child reports and carry that participant token. Nullable participant is allowed for an execution-only pair without a retained owner view. Never substitute one basis for missing data in the other. `category_difference` is a nullable boolean: null when either category is missing. Evidence qualifications use the closed Task 14 list; excluded reasons are `source_missing`, `result_missing`, `condition_unknown`, `condition_different`, `execution_ambiguous`, `report_execution_mismatch`, `retention_cap`, or null.

`source_outcome` and `child_outcome` are nullable existing outcome enum values selected from that row's stated basis. They allow the UI to display a qualified pair whose source execution/report is in an earlier window without fetching raw private evidence or manufacturing a missing category. Validate them against any corresponding records retained in this publication.

For metric results-family counts, use distinct execution-basis source/child pairs only; duplicate reports do not multiply the denominator. Known condition differences remain `not_comparable`; unknown conditions remain `inconclusive`; the paired categorical-conflict denominator excludes both. Preserve reported-basis conflicts separately in comparisons and owner interpretations rather than calling them differing physical outcomes.

### Error Handling and Logging

Empty verified inputs produce an available known-empty lane; missing events/exports produce unavailable or partial, not zero. Invalid external facts fail closed before partial publication. INFO window/coverage counts, DEBUG exclusion codes.

### Tests / Acceptance / Verification

`test_replication_analysis.py`, `test_replication_analysis_properties.py`: exact repeat with different same-kind tools; adapted design; unknown source; two conflicting categories retained; condition mismatch; unknown uncertainty; duplicated reports; distinct execution vs independent sample; partial owner export; insertion-order and split-window invariance. Run both files with coverage.

## Task 15: Append six descriptive replication metric families

### Intent

Expose independent research dimensions without a science-quality, consensus or truth score.

### Implementation Steps

1. Append, in this order, `scientific_replication_design_lineage@1`, `scientific_replication_conditions@1`, `scientific_replication_results@1`, `scientific_replication_uncertainty@1`, `scientific_replication_relationships@1`, and `scientific_replication_social_interpretation@1`.
2. Lock scalar value keys per family:
   - lineage: `design_count`, `root_count`, `child_count`, `unresolved_parent_count`;
   - conditions: `comparison_count`, `matched_count`, `different_count`, `unknown_count`, `matched_share_milli`;
   - results: `paired_count`, `compatible_count`, `conflicting_count`, `inconclusive_count`, `not_comparable_count`, `category_difference_count`;
   - uncertainty: `measurement_count`, `declared_set_count`, `unreported_count`, `ambiguous_set_count`, `unreported_share_milli`;
   - relationships: `attempt_count`, `repeat_count`, `adapted_count`, `execution_backed_count`, `declared_only_count`, `duplicate_source_count`, `unresolved_count`;
   - social interpretation: `interpretation_count`, `trusted_count`, `contested_count`, `unknown_source_count`, `disagreement_count`, `collaboration_count`, `participant_declaration_count`.
3. Attach standard algorithm/provenance/coverage metadata. Milli shares use integer floor `1000*n//d`, with explicit zero-denominator unavailability rather than a fabricated zero. No rates of objective truth, scientific merit, calibration or global reliability.
4. Add optional `MetricComputationInputs.replication_analysis`; absent input emits no new documents. Preserve IDs, order, algorithms and keys of all first 250 families; append to **256**.
5. In this same task migrate the existing current-catalog assertions in `tests/unit/test_scientific_hypotheses_pins.py`: current count becomes 256, while the six historical science families are asserted at fixed slice `[244:250]`, not `[-6:]`. Add the replication `[250:256]` suffix assertion in `test_replication_metrics.py`. Update current total assertions in `tests/unit/test_metric_specifications.py`, `test_cultural_evolution_metric_service.py` and the other current-catalog pin sites found by a targeted `METRIC_FAMILY_COUNT`/catalog-length search in first-party tests. Preserve historical fixture counts/algorithms. Do not defer this prerequisite to Task 28, because Task 27 runs the existing science pin gate.

### Required Interfaces and Contracts

Use standard `MetricDocument` contracts; no shared metric schema widening. Three-sample qualification refers to eligible paired measurements, not raw messages. Social disagreement is differing owner appraisals of a common retained report/design reference, not proof one owner is wrong.

### Error Handling and Logging

Unknown/missing input is unavailable; partial input remains partial. Computation logs IDs/counts/availability only, no row payloads or subjective values.

### Tests / Acceptance / Verification

`test_replication_metrics.py`: exact registry suffix, unchanged prefix digest, closed keys, denominator exclusions, all unavailable/partial cases, repeated roots, small samples and deterministic quantization. Run new metric tests plus `tests/unit/test_scientific_hypotheses_metric_service.py` with coverage.

## Task 16: Compose completed-run facts and collector inputs

### Intent

Make usable analytical evidence available from actual finalized owner exports and committed history.

### Implementation Steps

1. Add `replication_facts` and `build_completed_run_replication_analysis` in `experiments.replication_completed_run`. Inputs are completed result/config, committed events, explicit run identity and exported replication ledgers; retain source/child event associations before any aggregation.
   The bridge owns the one identity map above and builds execution facts from real events. Source drafts/attempts provide actor references, not objective authority; verify registration/body bindings. When a normalized fact set reaches metric assembly/publication, pass it unchanged rather than harvesting/tokenizing it again.
2. Map all frozen designs, condition snapshots, reports, uncertainties, participant declarations and interpretation revisions. Snapshot bounds/notice counters become coverage, never silently discarded.
3. Verify each purported own measurement against committed history in the trusted composition layer; a mismatch remains an owner claim and an analytical unresolved row. No correction is fed back to the owner ledger.
4. Extend `assemble_arm_metric_bundle` only when science is enabled and finalized exports are present. If analysis construction fails, preserve scientific completion and record unavailable analysis; do not substitute all-zero metrics.
5. Do not read `scientific-hypotheses-snapshot-v1` to reconstruct trials: it retains only latest-window hypothesis/evidence aggregation and cannot prove independent occurrences.

### Required Interfaces and Contracts

Analysis imports no experiments/cognition; experiments import public inner contracts and analysis but no concrete persistence/API. Capture/publication is programmatic and separate from scientific execution.

### Error Handling and Logging

Safe missing-export/committed-event mismatch/cap codes; no payload-bearing exception logging. Existing collector failure isolation remains intact.

### Tests / Acceptance / Verification

`test_replication_completed_run.py`: real runner exports with retired owner, source/child trial mapping, missing event, source false report, partial retention, collector absent/off behavior and content-stable twins. Add one registration/body-binding mismatch, raw→normalized→metric/publication single-pass identity, and a remapping test asserting every parent, report, attempt, interpretation, collaboration and execution reference resolves to its intended row or explicit unresolved status. Run with coverage plus existing scientific completed-run tests. Representative real execution must reach all six metric documents without bypassing normal admission.

## Phase Risks and Mitigations

- Distinct trials are not independent seed blocks: label occurrence evidence only; no inferential p-values/intervals.
- Raw owner identities: tokenize at the trusted bridge and test leakage through all serialized outputs.
- Missing capture becomes false zero: availability/coverage precede count interpretation.

## Exact Task Verification Commands

```bash
# Task 13
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_replication_layers.py -q
# Task 14
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_replication_analysis.py tests/unit/test_replication_analysis_properties.py -q
# Task 15
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_replication_metrics.py tests/unit/test_scientific_hypotheses_metric_service.py -q
# Task 16
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_replication_completed_run.py tests/unit/test_scientific_hypotheses_completed_run.py -q
```

## Phase Completion Checklist

- Tasks 13–16 satisfy layer separation and registry-prefix preservation.
- No analytical value is used as cognition input.
