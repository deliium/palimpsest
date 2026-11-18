# Phase 4: Owner-scoped measurement evidence

Plan: [index.md](index.md)
Tasks: 13–16
Depends on: Tasks 9–12

## Objective

Let agents retain and communicate readings, form revisable and possibly incorrect reliability beliefs, and choose ordinary instrument actions without importing physical error parameters or treating measurements as verified experimental outcomes.

## Current-Code Evidence

| Path | Symbols / evidence | Why it matters |
|---|---|---|
| `src/agents/cognition/experimentation.py` | `ExperimentLedger`, `score_remembered_experiment`, `observed_condition_tokens` | Existing scoring consumes categorical `experiment_resolved`; do not route measurement readings into it. |
| `src/agents/cognition/replication.py` | `ReplicationMeasurement`, `ReplicationResultReport`, `ReplicationInterpretation` | Existing uncertainty is categorical; retain that schema unchanged. |
| `src/agents/cognition/replication_interpretation.py` | `source_appraisal_for_trust`, `_appraise` | Social trust is not instrument reliability. |
| `src/agents/cognition/loop.py` | `_prepare_evidence`, `_remember_experiments`, science Wait replacement around 7632 | Separate evidence bridge and lowest-priority action seam. |
| `src/agents/cognition/evidence_testimony.py` | `EvidenceObservedReference`, `apply_evidence_update` | An observed anchor supports provenance, not truth. |
| `src/agents/cognition/scientific_hypothesis_communication.py` | provisional `hyp_v1` adoption | Testimony does not borrow sender evidence mass. |
| `src/agents/cognition/replication_codec.py` | strict bounded `rep_v1` | Introduce a distinct bounded measurement relation, not a widened replication document. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/agents/cognition/measurement.py` | create | Frozen owner reading/report/reliability ledger, pure ingestion and comparison. |
| `src/agents/cognition/measurement_communication.py` | create | Closed `msr_v1` relations and delivered-testimony ingestion. |
| `src/agents/cognition/measurement_actions.py` | create | Observation-only candidate compilation and evidence projection. |
| `src/agents/cognition/models.py`, `src/agents/cognition/loop.py`, `src/agents/cognition/__init__.py` | modify | Candidate state, owner perspective and action/evidence integration. |
| `tests/unit/test_measurement_ledger.py`, `tests/unit/test_measurement_communication.py`, `tests/unit/test_measurement_loop.py`, `tests/unit/test_measurement_evidence.py` | create | Owner isolation, mistaken confidence and no-outcome-promotion tests. |
| `tests/architecture/test_measurement_boundaries.py` | create | Agent inputs forbid physical instrument/reference state. |

## Task 13: Add a bounded owner reading and reliability ledger

### Intent

Preserve what was observed separately from how much the owner trusts the instrument.

### Implementation Steps

1. Introduce `MeasurementEvidence`, `MeasurementReport`, `InstrumentReliabilityBelief`, `MeasurementBeliefRevision`, and `MeasurementLedger` in `agents.cognition.measurement`. Use policy `measurement-beliefs.v1`.
2. An acquired evidence record stores a frozen display, actual acquisition basis (`own_observation` or `communicated`), opaque source event/delivery IDs, declared source root, observed tick and owner-visible condition tokens. No target truth, physical state record, `WorldEvent`, engine service or ground-truth error is accepted.
3. Reliability beliefs are keyed by the owner's observed instrument ID and quantity. Store expected display resolution, an optional owner-estimated error band, confidence milli, locally observed wear/adjustment cues, append-only revisions and evidence references. Unknown error remains `None`, never zero.
4. Implement the index's exact initial appraisal/comparison policy. Interpret same-target/same-unit/matching-observed-condition readings as apparent agreement or disagreement only. Cross-tick temperature/amount changes can mislead the policy; never classify consistency as accuracy.
5. Enforce per-owner retention: 128 reading/report rows combined, 64 reliability beliefs, 512 revisions, and 1024 processed-root receipts. Deterministically evict oldest display rows by `(observed_tick,id)`; retain bounded root receipts. When receipts fill, refuse new ingestion with `measurement_receipt_cap`, rather than forgetting deduplication identity. Dangling display references become explicit unavailable anchors.
6. Preserve disagreement and contradictory revisions. Two owners may appraise the same instrument differently; no consensus merge or globally shared reliability value.

### Required Interfaces and Contracts

`ingest_measurement_observations(ledger, observation) -> MeasurementLedger` and `compare_measurement_evidence(ledger, evidence) -> MeasurementLedger` are pure. Their inputs are owner-safe DTOs only. Receiving a report never creates a direct measurement.

### Requirement Evidence

Original Request: agents may misunderstand reliability and measurements are evidence, not truth. Architecture: owner privacy, opaque event correlation and append-only subjective lineage.

### Error Handling and Logging

Owner mismatch and invalid units fail closed; malformed public facts are rejected with safe codes. Retention is explicit in ledger notices. Logs include owner ID/count/acquisition basis, never displays, target quantities or belief content.

### Tests

Initial unknown error; quantization versus inferred accuracy distinction; overconfidence in a consistently biased instrument; two owners with conflicting confidence; legitimate environmental change misappraised without truth correction; owner mismatch; no peer state copying; duplicate-root idempotence; caps, deterministic eviction and unavailable references.

### Acceptance Criteria

At least one deterministic test demonstrates an objectively inaccurate instrument becoming subjectively trusted without any objective reliability field entering cognition.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_ledger.py tests/architecture/test_measurement_boundaries.py --cov=agents.cognition --cov-report=term-missing -q`

Expected: owner privacy, bounded retention and mistaken beliefs pass.

## Task 14: Add bounded measurement testimony without borrowed accuracy

### Intent

Measurements can be reported and misunderstood without becoming shared observations or replication truth.

### Implementation Steps

1. Add a closed multipart `msr_v1` codec in `measurement_communication.py`, mirroring the bounded part framing of existing `rep_v1` rather than changing it. One report occupies1–4 `CommunicationRelation(subject="msr_v1", predicate="part", object=frame)` values in one existing Talk/Tell. Each frame object is ≤256 ASCII characters. No Ask auto-response, new command or unbounded text parser.
2. Canonical document exact keys: `v`, `report_id`, `instrument_id`, `target_id`, `quantity`, `unit`, `value_kind`, `display`, `nominal_division`, `sample_tick`, `declared_root`, `speaker_confidence_milli`; `v=1`. Serialize compact sorted-key JSON with `ensure_ascii=True`, no NaN. Keep full original IDs: support ASCII `[A-Za-z0-9:_-]{1,128}`, including real64-character engine IDs and68-character `msr:` reading tokens. Unit uses the index's closed fixed/resource token rules. Do not shorten/hash source IDs. Maximum document876 bytes; genuinely unrepresentable units/IDs/oversized documents skip optional emission with `measurement_report_unrepresentable`.
3. Compute a32-hex group token from the first32 characters of SHA256(document).hexdigest(), for framing integrity only—not a substituted source identity or authenticity proof. Split the ASCII document into219-character payload chunks. Frame is `<group>|<index>|<total>|<chunk>` with1-based single-digit index/total and total≤4:37 header characters plus219 payload fits256. Require complete delivery of all parts in one utterance; no cross-tick assembly. Identical duplicate parts are idempotent; conflicting duplicates, bad digest, missing parts, mixed groups, unsupported versions/keys, noncanonical integers and scalar/category mismatches reject the report atomically.
4. Ingest only actual addressed Talk/Tell delivery from the observation. Authenticate speaker from the delivery envelope, not a claimed ID. Preserve declared root/tick/confidence as testimony; actual basis is communicated and delivery event is new provenance.
5. Same declared-root retellings can be retained as attributed reports but cannot increase independent support or owner's reliability confidence. A claimed unknown root is not looked up in event stores.
6. Keep `hyp_v1`, `rep_v1`, `ev_v1` and existing utterance limits unchanged. Emit at most one complete measurement report per selected speech command, only when all its parts fit remaining relation/character budgets. Never emit a partial report or replace a selected verb, recipient or required original relation.

### Required Interfaces and Contracts

`encode_measurement_report(report) -> tuple[CommunicationRelation, ...]` (empty when unrepresentable), `decode_measurement_report(relations) -> report DTO`, and `ingest_measurement_communication(ledger, delivered) -> ledger`. Source IDs remain full-sized fields inside the document; a framing digest is never used to look up objective history. Neither sender confidence nor display precision is an accuracy certificate.

### Error Handling and Logging

Closed malformed/oversize/unrepresentable codes; no payload echo. Dropped report logs count, owner ID and reason only. Do not reject an otherwise legal speech command merely because an optional measurement addition will not fit.

### Tests

Boundary lengths and1–4 part roundtrips; all five quantities; signed temperature; real64-character IDs from `derive_event_id` / `derive_entity_id` and68-character request-derived reading IDs; complete end-to-end delivery with an actual generated event root, not only short handcrafted IDs. Cover malformed integers, conflicting category/unit, spoofed speaker, nonrecipient isolation, unknown declared roots, same-root relay, conflicting reports, missing/reordered/identical-or-conflicting duplicate parts, digest mismatch, oversize documents, local IDs genuinely >128, and coexistence with science/replication relations under the enclosing budget.

### Acceptance Criteria

Delivered testimony remains distinguishable from direct instrument use and cannot certify accuracy or manufacture independent corroboration.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_communication.py tests/unit/test_replication_communication.py tests/unit/test_replication_social_exchange.py --cov=agents.cognition --cov-report=term-missing -q`

Expected: bounded measurement reports and unchanged replication codecs pass.

## Task 15: Integrate candidate measurement state into the cognitive loop

### Intent

Instrument observations must be processed only for their owner and only committed by normal runtime finalization.

### Implementation Steps

1. Add optional `measurement_ledger` to owner perspective/snapshot contracts in cognition models. Constructor default is absent; do not allocate a ledger when the run spec is absent.
2. Inject only `measurement_enabled: bool` from trusted composition, not the physical spec, initial parameters or reference values. Read local `InstrumentAppearance` and actor reading occurrences from the observation.
3. Process direct observations and delivered `msr_v1` reports before measurement appraisal. Retain separate acquisition bases and deduplicate using source/delivery/root receipts.
4. Carry a detached proposed ledger in `CognitiveLoop`'s result using the existing proposed science-state pattern. Never install it during cognition; Phase 5 owns commit.
5. In memory proposal generation, record the experienced display/action as a reading, not a statement that the target has the displayed quantity. Recalled measurement evidence retains original basis/root and cannot re-increment confidence on every recall.
6. Do not send physical instrument configuration or an objective error comparison to LLM prompts, imagination, stop selectors or reconstructive recall.

### Required Interfaces and Contracts

Reading acquisition occurs in the next committed observation window, not when a command is merely proposed. An aborted action or rejected command cannot create a reading. Already committed observations can legitimately be remembered even if the owner's next proposed action is later replaced.

### Error Handling and Logging

Bad owner inputs fail closed before subjective installation. Logging records proposed counts, notices and safe IDs only. Optional ingestion failure must not silently fabricate an empty successful measurement.

### Tests

Science/spec off no allocations or command changes; one owner sees another's action but no display; rejected action no evidence; repeated observation/recall idempotence; reading memory distinct from target fact; candidate state invisible before finalize.

### Acceptance Criteria

The real cognitive loop retains qualified instrument evidence without reading world state or mutating committed subjective state prematurely.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_loop.py tests/unit/test_direct_observation_memory.py --cov=agents.cognition --cov-report=term-missing -q`

Expected: candidate-only processing and source distinctions pass.

## Task 16: Bridge physical evidence and compile conservative instrument actions

### Intent

Make instruments useful in ordinary cognition without turning readings into categorical experimental confirmations.

### Implementation Steps

1. Add `measurement_evidence_candidates(ledger, observation)` in `measurement_actions.py`. Supply only direct observed reading anchors to `_prepare_evidence`, following the existing accounting candidate bridge. When general evidence mode is disabled, keep the measurement ledger alone; do not enable `legal_disputes`.
2. Communicated readings use communicated source provenance, never `PHYSICAL_STATE` as if directly measured by the receiver. General evidence evaluations may be mistaken; they do not get instrument bias or sampled truth.
3. Add `compile_measurement_action(perspective, ledger) -> AgentCommand | None`. Use only eligible observed own-held instruments, visible local targets/references and the index's cadence/ordering. Preserve any already-selected non-Wait action; existing replication and hypothesis-test Wait replacements retain precedence.
4. Calibration candidates require an owner belief with confidence ≤300 and a reachable matching-unit reference; at most one calibration candidate every 16 logical ticks. Otherwise consider one measurement every four ticks. Sort instruments/targets by stable IDs; don't choose by hidden precision/bias.
5. Produce a normal `Measure`/`CalibrateInstrument` command only. No helper submits it, reads the current candidate world, changes a target, or directly installs a result.
6. Leave `score_remembered_experiment`, `apply_test_outcome`, categorical `ReplicationMeasurement` and existing replication comparisons unchanged. Instrument reading references may be available as qualified owner evidence, but no automatic hypothesis support, law discovery, numeric hypothesis predicate extension or N-count promotion is introduced.

### Required Interfaces and Contracts

Calibration compilation is based on fallible owner appraisal, not objectively stale calibration state. Every candidate can still be denied by normal engine admission. Reading evidence is useful without asserting causality or successful replication.

### Error Handling and Logging

Unavailable target/reference yields no candidate and a safe reason code, not fallback to a guessed ID. Respect the existing per-tick cognitive budget; no unbounded scanning. Log only candidate counts, selected tag and IDs.

### Tests

Wrong reliability beliefs alter calibration choice but never admission; earlier non-Wait and science actions preserved; exact four/16-tick cadence; stable tie order; no held tool/no target; communicated versus own source; measurement does not change categorical support counts; failure and legal null candidate.

### Acceptance Criteria

At least one real runner can autonomously propose an instrument action; no reading becomes a direct truth or categorical experiment verdict.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_evidence.py tests/unit/test_measurement_loop.py tests/unit/test_scientific_hypotheses_test_wiring.py tests/unit/test_replication_runtime.py --cov=agents.cognition --cov=simulation --cov-report=term-missing -q`

Expected: useful owner-safe candidates and unchanged science semantics pass.

## Phase Risks and Mitigations

- Agreement can be mistaken for accuracy: name appraisals explicitly, keep unknown error and test consistently biased tools.
- Memory recall can duplicate evidence: persistent bounded root receipts and exact-once ingestion.
- Existing science code can promote readings accidentally: explicit no-routing tests for categorical scoring.
- Optional reports can crowd out original speech: append only within remaining budgets, otherwise skip.

## Phase Completion Checklist

- Tasks 13–16 meet owner/privacy/provenance and bounded-work criteria.
- Update task progress solely in `index.md`.
