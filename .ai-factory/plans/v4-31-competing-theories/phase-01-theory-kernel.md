# Phase 1: Theory kernel

Plan: [index.md](index.md)  
Tasks: 1–2  
Depends on: none

## Objective

Keep incompatible, falsifiable owner explanations side by side and score frozen predictions on the same observed case without assigning scientific authority to social support.

## Current-Code Evidence

| Path | Symbols / contract | Why it matters |
|---|---|---|
| `src/agents/cognition/scientific_models.py` | `ScientificModelLedger`, frozen model/case values | Existing owner-local scientific source; do not change its candidate set or retained metrics |
| `src/agents/cognition/scientific_model_derivation.py`, `scientific_model_prediction.py`, `scientific_model_observation.py` | Derivation, issuance and settlement split | Reuse admitted owner cases and normalized outcomes; do not inspect objective state |
| `docs/scientific-models.md` | Model hypotheses; Two candidate predictors; Issuance, commitment, target and receipt | Timings, exact visibility and supported outcome states |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/agents/cognition/competing_theories.py` | Create | Frozen value types, pure candidate/contrast/support/citation transitions and bounds |
| `src/agents/cognition/competing_theory_forecasts.py` | Create | Issue and settle explicit theory-level forecast cases |
| `tests/unit/test_competing_theories_kernel.py`, `tests/unit/test_competing_theories_forecasts.py` | Create | State, identity, evidence and accuracy invariants |

## Task 1: Define owner explanations and citations

### Intent

Represent why two explanations differ, without confusing a different display name, model revision, or source with a rival theory.

### Implementation Steps

1. Add frozen `TheoryContext(target_kind, location_id, origin_season, resource_kind, unit)`; for `season` require null resource kind/unit; for `resource_regeneration` require both and label the target **net visible quantity direction**. Validate against existing target alphabets and normalized context; horizon is fixed at two. Refuse other targets, including production and unavailable targets, rather than reporting them as empty evidence. A resource entity ID is a local case binding, not part of a transferable context.
2. `TheoryClaim(context, account, predicted_category)` has two account types: `continuity` (current season persists/resources stay unchanged) and `recurrence` (a previously observed matching two-tick transition recurs). For continuity require the context season/unchanged category. For recurrence derive at most one claim per newly scored, earlier-issued owner case of the same context; require the observed category to differ from continuity. The first local candidate comes from an eligible V4-30 season/resource case; no data creates an account for another owner. Both are bounded explanatory rules, not physical causes. Hash a version-prefixed canonical encoding of the closed tuple for `thy-` identity; separately qualify all mutable rows by run and owner; neither author nor followers change claim identity. Rivalry means identical context and unequal predicted category, not just unequal account. Do not collapse claims by their source or social support.
3. Add `CompetingTheoryLedger`, `TheoryCitation`, `TheoryStance`, `TheorySocialReceipt`, `TheoryCoverage`. Citation fields: local claim ID, owner tick, closed polarity (`supports`, `contradicts`, `context_only`), kind (`own_observation`, `own_scored_case`, `delivered_claim`, `declared_pointer`), and opaque provenance/root ref. Only locally resolved owner evidence qualifies as observation or scored case. Testimony pointers do not resolve foreign evidence or become observed records. Deduplicate exact rows and count unique roots separately from received reports. Unknown/no-root reports never count as independent; retain both polarities.
4. Provide pure `apply_theory_updates(ledger, ...)`: append claim/citation facts and stance revisions (`support`, `withdraw`); at most one active supported claim per context per owner, retaining the old revision on switch. Unknown is not opposition; never infer support from contact, delivery, teaching, group membership, or a hit. The runtime policy in Task 3 issues explicit local changes. Use stable canonical traversal and deterministic duplicate handling. Use 32 claims per owner, 256 citations, 128 stance revisions, 256 social receipts, 256 terminal cases and 64 pending cases; max four claims per issued bundle. Refuse new admissions at cap except oldest terminal cases may be pruned by `(target_tick, case_id)`; apply closure checks before mutation and keep saturating metadata-only refusal/eviction counters and first retained tick. Never evict a pending case or a referenced claim. No raw propositions or free text.
5. For each local recurrence retain the opaque seed outcome token and its source tick as owner provenance, not as part of claim identity. Attach the seed citation atomically when deriving the local claim, even if the claim was previously learned through speech. Use a self-contained opaque pointer so later base/terminal-case pruning does not dangle a required row reference. A score is an independent case fact: a full citation ledger must not block settlement; count refused citations and keep the actual score. Never classify the seed as a scored prediction of the newly derived theory.

### Required Interfaces and Contracts

Constructors take frozen owner-safe values only; opaque refs carry no event bodies. Theory keys and rivalry are pure and order-independent. Canonical/strict transport and persistence are Tasks 3–4; typed policies never import `simulation` or `analysis`. Historical owner rows are not a world registry.

### Requirement Evidence

`index.md` Original Request: incompatible explanations, cited evidence and differing support. `.ai-factory/ARCHITECTURE.md` “Memory, testimony, and subjective concepts”: one owner, distinct provenance, shared roots not independent.

### Error Handling and Logging

Invalid typed values fail validation; runtime candidate refusal is an unchanged transition plus bounded coverage, never a tick failure. Pure code does not log; composition may emit safe counts/reason codes only.

### Tests

`test_competing_theories_kernel.py`: stable keys across owners/insertion orders, distinct within-context rivals vs non-comparable contexts, two owner stances can disagree, duplicate/echo provenance, contradiction retention, malformed context, cap refusal and closure.

### Acceptance Criteria and Verification

Typed equal claims match across owners but neither citations nor support cross implicitly. `uv run --frozen --python 3.12.14 pytest -q tests/unit/test_competing_theories_kernel.py` passes.

## Task 2: Freeze predictions and record observed failures

### Intent

Measure predictive performance independently of who supports a theory.

### Implementation Steps

1. Add pure `issue_theory_case(ledger, base_case)` and `settle_theory_case(ledger, base_case_outcome)`. Issue only on a just-admitted V4-30 season/resource case, with same owner, opaque base-case ID, horizon, unit, bound entity and canonical category alphabet. Select matching claims by their first local registration `(tick, id)` up to four (count truncation); sort frozen output rows by theory ID. Include unsupported rivals. No claim enters after issuance. No changes to the V4-30 case. With no eligible claims or exhausted pending capacity, record coverage and do not backfill.
2. Freeze each theory’s categorical forecast and a probability vector using the existing 2:1 rule and largest-remainder allocation (sum 1000 milli), not owner trust or V4-30 empirical weights. Save claim ID, predicted category, ordered probabilities and timing; commit with ordinary owner finalization at `t`, score only at `t+2`. A season uses the normalized season outcome; a resource uses the exact same resource entity/location/unit/visibility outcome produced by V4-30.
3. Settle on eligible observed outcome only: `hit` or `failure` means category matches or differs; retain observed category, opaque owned outcome ref, integer Brier numerator and terminal tick. Map other V4-30 outcome statuses losslessly to non-scoring terminal statuses; unresolved at run stop stays `pending`. Reject mismatched owner, case ID, target tick or alphabet; never infer failure from absence, a support withdrawal or a late testimony. Append local supports/contradicts citations for actual scores, without triggering an automatic stance reversal.
4. Normalize only the admitted `ForecastCase` fields: `conditions` slots `season` and `location` are required and must match the owner observation at issue; use `reference_resource_kind`, `unit_token` and exact opaque `target_ref` for resource case binding. Do not parse the colon-delimited `target_ref` into identifiers. At settlement require the same owner and base case, the exact target-time owner observation, and the same resource kind even for V4-30's `unchanged` case (its current check is conditional on change). For a missing or incompatible target kind/unit/location, retain non-scoring coverage; do not change V4-30. A chance observation may yield a candidate seed but never strengthen a different entity's assertion of continuity.
5. Freeze a training cutoff strictly before issue (`source_observed_tick < issued_observation_tick`). A new seed discovered at the current boundary may enter the ledger now, but its locally derived recurrence cannot enter a case until the next issue tick. Preserve first local provenance separately from first registration so receiving a claim does not falsely mark it locally derived. At exact target time, if the previously admitted base case cannot be recovered, mark bounded `base_case_unavailable` coverage rather than reconstruct an outcome; an ended run before the target still leaves pending cases.

### Required Interfaces and Contracts

Each retained case is a self-contained frozen contest plus outcome, and an issued row and its source ticks never change. Completed theory states do not depend on V4-30 retaining the base case forever. Only owner-visible settled outcomes enter the scorer. No loss-to-support edge; no loss-to-command edge.

### Requirement Evidence

`index.md` Original Request: predictions and failures, inaccurate majority and accurate minority. `docs/scientific-models.md` “Issuance, commitment, target and receipt” and “Performance”: time order and missingness rules.

### Error Handling and Logging

Treat unsupported target, non-comparability, horizon miss, and refusal as distinct bounded reasons. On conflicting duplicate settle, preserve the first terminal row and refuse the conflict; do not log evidence content.

### Tests

`test_competing_theories_forecasts.py`: two rivals tested on same observation and one fails; support swap cannot change prediction/score; ties in allocation deterministic; unknown outcomes and pending not in observed denominator; late/foreign/duplicate settle; same-tick seed cannot enter frozen case; exact target kind on unchanged resource; missing/trimmed base case; full citation cap still settles; no retroactive insertion or partial overflow.

### Acceptance Criteria and Verification

Same matched cases expose independent hit/failure records, including for unsupported claims. `uv run --frozen --python 3.12.14 pytest -q tests/unit/test_competing_theories_kernel.py tests/unit/test_competing_theories_forecasts.py` passes.

## Phase Risks and Mitigations

- A resource change may look like a causal discovery: label it net visible change in types, evidence and UI, and keep both accounts explicitly fallible.
- Popularity can leak into sampling: match by context and stable registration order, test invariance when only social inputs change on an already issued case, and expose truncation rather than claiming complete coverage.

## Phase Completion Checklist

- Kernel contracts and focused tests are green.
- Update only the Task 1–2 checkboxes in `index.md`.
