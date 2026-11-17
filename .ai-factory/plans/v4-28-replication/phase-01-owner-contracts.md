# Phase 1: Owner-scoped replication contracts

Plan: [index.md](index.md)
Tasks: 1–4
Depends on: none

## Objective

Represent repeatable designs, attempts, results, uncertainty, and social interpretations without a shared scientific truth store.

## Current-Code Evidence

| Path | Symbols / behavior | Significance |
| --- | --- | --- |
| `src/agents/cognition/experimentation.py` | `ExperimentHypothesis`, `ExperimentLedger`, `HypothesisCondition`, `HypothesisClaim`, `derive_hypothesis_status` | Existing owner hypotheses remain separate; `supported` is not truth. |
| `src/agents/cognition/experimentation.py` | `observed_condition_tokens`, `conditions_hold`, `compile_scientific_test` | Reuse observation-only conditions and ordinary testing. |
| `src/agents/cognition/production.py` | `observed_experiment_operand_ids` | Operand identity comes from current observation, not another owner's ledger. |
| `src/world/experimentation.py` | `ExperimentOperator`, `ExperimentProcessToken`, `ExperimentOutcomeClass` | Closed executable vocabulary and five categorical results. |
| `src/agents/cognition/scientific_hypothesis_communication.py` | `_claim_token` | Includes concrete operands/prediction but omits conditions; unsuitable as a design key. |
| `src/agents/cognition/collective_decision_actions.py` | `COLLECTIVE_TOPIC_COMMANDS` | Does not include `Experiment`; do not widen collective execution. |

## Files to Change

Create `src/agents/cognition/replication.py`, `replication_designs.py`, and `replication_interpretation.py`; add their intentional public exports in `src/agents/cognition/__init__.py`. Create `tests/unit/test_replication_models.py`, `test_replication_designs.py`, and `test_replication_interpretation.py`. All names introduced below are new unless cited in the evidence table.

## Task 1: Define frozen design identity and lineage

### Intent

Freeze what was repeated instead of inferring equivalence from current, mutable hypotheses.

### Implementation Steps

1. Introduce locked `ReplicationPolicy` / `default_replication_policy()` with version `scientific-replication.v1`. Owner caps: 32 designs, 128 attempts, 128 recipient-specific outbox entries, three send attempts/message/recipient, 256 result reports, 256 interpretations, 256 delivery receipts, 32 collaborations, eight participant claims/collaboration, 32 revisions/interpretation, and 16 bounded notice codes. Reject bool-as-int, nonfinite values, unknown enums, and altered locked defaults.
2. Add frozen `ExperimentDesign` with exact fields `design_token`, `origin_token`, `parent_design_token`, `source_hypothesis_token`, `source_trial_token`, `created_tick`, `operator`, `process_token`, `operand_a_selector`, `operand_b_selector`, `predicted_outcome`, `conditions`. Optional parent/second selector/prediction are explicit nulls; conditions are an ordered unique `HypothesisCondition` tuple (at most eight).
3. A selector is `(family, kind, binding_mode, exact_entity_id?)`. Families are `item`, `resource`, `structure`, `artifact`; modes are `exact` and `same_kind`. `same_kind` uses observed enum/kind tokens, never names or a hidden recipe catalog. Exact IDs are executable reference data received in testimony, not proof of visibility or permission.
4. Add `freeze_experiment_design(owner_id, hypothesis, trial, observation)` in `replication_designs.py`. Freeze only an owner's actually observed, completed test for which current/retained owner-safe operand descriptors are available. Missing descriptors yield `design_unavailable`; do not infer them from world events. Preserve the source's conditions and predicted result.
5. Canonicalize selectors and sort conditions by slot. The design hash preimage is exactly `{"policy_version":"scientific-replication.v1","design":<all eleven other ExperimentDesign fields>}`: exclude `design_token` itself. Use enum value strings, explicit nulls, condition objects `{slot,value_token}`, ASCII JSON, sorted keys, compact separators, no floats and no trailing newline. Hash those bytes with SHA-256; `design_token="rdes-"+digest[:32]`. Include parent/source identity and conditions; exclude receiver-local IDs, confidence, current status, and transport delivery IDs. Recompute on receipt before constructing a design; do not attempt a self-referential hash.
6. `adopt_replication_design` retains the transmitted origin/design tokens but creates a receiver-owned receipt and local handle. No sender hypothesis, evidence array, or mutable object is copied. A revision is a new design with a parent token, not mutation of the prior design.

### Required Interfaces and Contracts

`ReplicationLedger(owner_id, policy_version, source_drafts, designs, attempts, reports, collaborations, interpretations, outbox, receipts, notices)` is a separate frozen sidecar; do not widen `ExperimentLedger` or its legacy codecs. `ReplicationSourceDraft` retains at most 32 pre-action owner-safe procedure/selector/condition snapshots for original science tests until their actor-visible result can freeze a source design; never reconstruct a consumed operand from hidden state. `ReplicationOutboxEntry` records recipient entity, message kind/token, design/invitation reference, prerequisite design-message token, proposed tick, attempted tick/count, observed-delivery event reference, and status (`pending`, `proposed`, `attempted`, `delivery_observed`, `delivery_unknown`, `unsendable`, `cancelled`); checkpoint it as behavior-significant owner state. `empty_replication_ledger(owner_id)` and `require_owner_replication_ledger(ledger, owner_id)` enforce identity. Local row IDs include owner identity; transmitted design tokens do not change on adoption. Unknown parents remain unresolved opaque references. Detect self-parent/cycles among locally known designs; unknown ancestry is not fabricated or recursively looked up.

For non-design references define one public pure `replication_ref(namespace, *values)` helper in `replication_designs.py`: SHA-256 of canonical ASCII JSON `[policy_version, namespace, *values]`, first 32 hex characters, prefixed with the closed namespace. Use `rorg` (origin), `rhyp` (hypothesis), `rtrl` (trial), `rrep` (original report), `rlrep` (receiver-local report), `ratt` (attempt), `rinv` (invitation), `rint` (interpretation), `rgcl` (optional group claim), and `rpart` (performer claim). Include owner ID in owner-local IDs; trial references use `(actor_entity_id, source_event_id)`. The message digest has its separate Task 5 algorithm. These namespaces are references, not authenticity claims.

Source drafts and attempts retain the acting owner's `actor_entity_id` from the pre-action observation, validated against the runtime's body binding before commit. This enables the trusted completed-run bridge to qualify an execution without guessing an agent/body ID convention.

### Requirement Evidence

Original Request: “experiment design lineage”, repeating others' work. Architecture §§Memory/testimony, Versioned Extension Contract: owner scope and immutable contracts.

### Error Handling and Logging

Invalid local constructors raise safe typed validation errors; untrusted inputs are dropped at Phase 2. At capacity retain existing rows and reject new rows with a notice; never evict referenced designs. DEBUG counts/reason codes only; never log design bodies, condition values, or identity digests as content surrogates.

### Tests / Acceptance / Verification

Test stable full-payload identity, ordering normalization, condition-only/parent-only identity changes, adopted origin retention, wrong-owner rejection, unknown parents, cycle rejection, immutability, and caps. Verify with `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_replication_models.py tests/unit/test_replication_designs.py -q`. No shared ledger or truth field exists.

## Task 2: Model attempts, measurements, and conflicting result reports

### Intent

Keep intent, admitted experimentation, observed result, and reported result distinguishable.

### Implementation Steps

1. Add `ReplicationAttempt`: owner-local token, design token, source trial token, optional collaboration token, local hypothesis ID, request/submission ticks, operand bindings, actual observed condition snapshot, condition comparison, and lifecycle state.
2. States are `planned`, `proposed`, `observed`, `rejected`, `unresolved`, `cancelled`. Only an actor-visible matching resolution can yield `observed`. A proposal or missing result is never a failure result.
3. Add `ReplicationMeasurement`: `outcome` (one existing outcome or absent), `resolution="outcome_class"`, `uncertainty_kind` (`unreported`, `declared_set`), sorted unique `possible_outcomes`, and `basis` (`own_observation`, `communicated`, `unknown`). For `unreported`, alternatives are empty and never imply zero uncertainty. For a declared set, require 1–5 outcomes and membership of a present reported outcome.
4. Add immutable `ReplicationResultReport`: owner-local report token, immutable `origin_report_token`, design/attempt/source-trial references, source root token, observed delivery reference if communicated, measurement, `declared_measurement_basis`, observed/reported condition snapshot, performer claim token, and optional collaboration claim. `declared_measurement_basis` preserves the source's measurement-basis enum; receiver-relative `measurement.basis` is always normalized to `communicated` for incoming speech. Local observation and communicated claims remain different provenance kinds. The origin report identity is preserved across receiver-local adoption; different content claiming the same origin is retained under separate local versions keyed by canonical content digest.
5. Direct categorical readouts default to `unreported` uncertainty: the public engine reports a category, not a calibrated measurement error. An owner can retain a declared alternative set as its appraisal, but cannot invent numeric sensor precision, error bars, probability, or ground-truth reliability.
6. Retain inconsistent reports side by side. Same origin/root/report re-delivery is one reported source, not a new trial. Contradictory reports under the same claimed source are retained as disputed versions and do not multiply independent evidence.

### Required Interfaces and Contracts

Add `record_replication_attempt`, `record_replication_measurement`, and `ingest_replication_report`, each returning a new ledger plus a bounded reason/notice. `source_trial_token` identifies what was repeated; design lineage and replication edges are separate relations. An absent original result permits a linked attempt but yields `source_result_missing`, not comparison success.

### Requirement Evidence

Original Request: conditions, results, measurement uncertainty, replication relationship, conflicting outcomes. `docs/scientific-hypotheses.md` §§Predicted result, Confidence distinguish outcome classes from confidence.

### Error Handling and Logging

Reject invalid sets and future/backward lifecycle transitions. Duplicates are idempotent. Full ledgers preserve historical rows and mark partial coverage. INFO state-transition counts; DEBUG drop reasons; no raw outcome reports, uncertainty bodies, or condition tokens in logs.

### Tests / Acceptance / Verification

Add model cases for all lifecycle states, missing result vs categorical failure, all five outcomes, unreported vs singleton uncertainty, malformed alternatives, duplicate roots, and coexisting contradictions. Run `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_replication_models.py -q`. Measurement uncertainty must not alias `confidence_milli` or `SubjectiveUncertainty`.

## Task 3: Define collaboration and owner-relative evidence interpretation

### Intent

Make community interpretation a cognitive/social process, not a count threshold or analytical feedback path.

### Implementation Steps

1. Add `ReplicationCollaboration` with invitation token, design token, source trial token, verified `inviter_entity_id`, optional opaque group claim, owner-local invitation status, participant declarations, and observed delivery provenance. The inviter comes from the actual delivered invitation speaker, not a payload field. Acts are `invite`, `participate`, `decline`; statuses are `pending`, `accepted`, `declined`, `attempted`, `completed`, `unresolved`. Acknowledgement expresses intention only. No global roster, group owner, or organization executor exists.
2. Add `ReplicationInterpretation` and append-only revisions: report references, local design reference, categorical appraisal (`compatible`, `conflicting`, `inconclusive`, `not_comparable`), condition comparison, uncertainty notice, source appraisal (`own_observation`, `trusted_testimony`, `contested_testimony`, `unknown`), and revision tick/reason.
3. `interpret_replication_evidence(owner_id, ledger, source_context)` uses only owner-retained measurements, delivered speech, and a safe directed relationship appraisal. Context contains the acting owner's normalized directed trust or an explicit unknown, never peer ledgers or objective alignment. Reuse the normalization in `loop._project_speaker_trust`: `(TRUST.value + 1) / 2`, clamped to `[0,1]`, but separately preserve whether a profile/dimension exists. Present trust at least 0.75 means `trusted_testimony`, at most 0.25 means `contested_testimony`, intermediate/missing means `unknown`. These are subjective locked-policy thresholds, not source reliability.
4. Deterministic policy: absent design/result or unknown conditions is inconclusive; changed known conditions is not comparable; equal known conditions and different recorded categories is conflicting; equal categories is compatible only at categorical resolution. Missing uncertainty always remains a notice. Declared alternative sets may qualify compatibility/ambiguity but never erase recorded category differences.
5. Own observation is retained independently of social trust. Trusted testimony may motivate an invitation/test and a revisable interpretation, not add sender evidence IDs to `ExperimentHypothesis`. Contested testimony remains visible. Repeated messages sharing one source do not strengthen the appraisal.
6. Do not call `apply_test_outcome` for communicated reports or replication counts. Own completed trials continue through the existing scientific evidence path exactly once. No new `true`, `proven`, `verified`, consensus, majority, N-replication promotion, or automatic knowledge uplift.
7. On a new accepted invitation stage a `participate` reply to its verified inviter; on an actual decline stage `decline` with a closed reason. Receipt duplicates stage neither another reply nor another test. A completed own replication stages its new `result` reply to that same inviter. A changed interpretation stages one `interpret` reply for the affected invitation/report audience. Task 7 supplies the exact queue transition/routing table; no helper initiates a new world speech command.

### Required Interfaces and Contracts

Expose frozen `ReplicationOwnerContext` with only the acting owner's safe source appraisals. Preserve owner disagreement with different interpretation rows, even if detached analysis can compare them. Group evidence is participants' attributed speech plus individual trials; source independence remains unestablished unless objective detached evidence supports distinct trial occurrences.

### Error Handling and Logging

Absent relationships yield unknown, not neutral-as-trusted. Saturated revision/participant caps add notices and retain old rows. DEBUG appraisal transition reason and counts only; no relationship dimensions, reports, or private interpretations in logs.

### Tests / Acceptance / Verification

`test_replication_interpretation.py`: two owners receive the same report with different source contexts and retain different social appraisals; trusted false testimony is possible; own contradictory observation survives; 1/2/8/128 repeated reports never create truth, confidence mass, or knowledge. Verify using the focused Phase 1 command plus `tests/unit/test_replication_interpretation.py`.

Also assert reply intents retain the verified inviter, duplicate acceptance is idempotent, and a claimed third-party/group participant cannot change the reply recipient.

## Task 4: Implement observation-only operand binding and comparison

### Intent

Permit another agent to repeat the procedure with its own equivalent materials without magical access to the originator's tool.

### Implementation Steps

1. Introduce `bind_replication_design(design, observation)` returning frozen operand bindings, actual observed conditions, and a reason. Enumerate only `observation.items/resources/structures/artifacts` already admitted by `observed_experiment_operand_ids`.
2. For exact mode require the exact entity currently observed and usable by ordinary action semantics. For same-kind mode filter the visible family/kind; items must be held by self or otherwise ordinarily reachable, never held by another owner. Sort candidates by stable entity ID. Two-operand operations require distinct IDs.
3. Reuse `conditions_hold` / `observed_condition_tokens` for matching; no fallback to world snapshots, hidden catalog laws, names, or analysis. Unknown requested slots are unsatisfied. Snapshot actual tokens at proposal, not after outcome.
4. Exact procedure replication preserves operator/process, selectors, prediction, and all declared conditions. A deliberate changed selector/condition creates a parent-linked new design and relation kind `adapted`; it is never silently called exact. Freeze source concrete bindings separately from kind-based protocol equivalence.
5. `compare_replication_conditions` returns `matched`, `different`, or `unknown` plus slot names only. Matching an incomplete condition list is not proof that every causally relevant condition is controlled.

### Required Interfaces and Contracts

`ReplicationBinding` is owner-safe and non-authoritative. `ReplicationRelationKind` is `repeat`, `adapted`, or `unknown`. Planning/binding never constructs authority tokens, executes effects, or accesses private world modules.

### Error Handling and Logging

No operands, consumed operand, foreign-held operand, unavailable slot, invalid operation shape, or cap returns a closed skip reason and no command. DEBUG reason/counts only; do not log bindings or condition values.

### Tests / Acceptance / Verification

`test_replication_designs.py`: source holds tool A, receiver holds equivalent tool B; receiver uses B, never A. Test exact-only failure, destroyed/consumed operands, deterministic tie-breaking, two-operand distinctness, missing conditions, and explicit adapted-child identity. Run the Phase 1 command. Binding does not guarantee engine admission.

## Phase Risks and Mitigations

- Identity conflation: freeze full design payload; existing `hyp_v1` tokens are references only.
- Measurement overclaim: categorical resolution and explicitly unreported error; numeric metrology is out of scope.
- Bounded retention: reject new records rather than silently rewriting referenced history; publish partial coverage later.

## Phase Completion Checklist

- Tasks 1–4 pass focused tests and match the contracts above.
- Only `index.md` carries task progress checkboxes.
