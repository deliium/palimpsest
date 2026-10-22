# Phase 5: Long-horizon cost control and detached communities

Plan: [index.md](index.md)
Tasks: 13–15
Depends on: Tasks 1–12

## Objective

Remove avoidable quadratic history copying and large duplicate hash documents, while preserving complete evidence and sampling multiple communities outside simulation authority.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/simulation/engine.py` | `_EngineSnapshot` histories; `_prepare_tick_candidate` 3349–3357; `export_events`; public boundary event append paths | Each committed tick copies all earlier events/resolutions into new tuples. |
| `src/simulation/runner.py` | `_finalize_and_acknowledge` 2658–2666 | Full-list receipt deduplication independently makes active-tick bookkeeping quadratic. |
| `src/simulation/engine.py` | `_fold_teaching_ledger` 4236–4267 | Teaching intentionally reads prior history; replacing the container must preserve Sequence behavior and order. |
| `src/simulation/replay.py` | snapshot history consumers 153, 260 | Explicit exports/restores still require complete event sequences. |
| `src/simulation/inspection.py` | event history access 760 | Inspection must not accidentally lose old events. |
| `src/simulation/runner_serialization.py` | exact/replica trajectory hashes 11418–11452 | Current hashing builds a complete second JSON representation. |
| `src/experiments/composition.py` | `society_emission_inputs_from_snapshot`, residence/interaction helpers | Existing detached community input adapters. |
| `src/experiments/composition.py` | `society_residence_rows_from_regional_input` 2227–2266 | Existing projection assigns first_tick=0 and body-ID person keys; it is not a trailing-window/agent-ID projection. |
| `src/analysis/society_emergence.py` | `compute_candidate_communities` 379–394, 476–489 | Empty living inputs may infer nodes from rows; clustering coverage is not source-evidence completeness. |
| `src/analysis/society_emergence.py` | `compute_candidate_communities` | Communities are analytical candidates, not engine entities. |
| `src/experiments/collectors.py` | society input path | Some existing collector paths omit journey/evidence detail; do not reuse incomplete inputs as full audits. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/simulation/_history.py` | create | Private immutable chunked ordered sequence, preserving complete history. |
| `src/simulation/engine.py` | modify | Structural-sharing history append in all snapshot paths. |
| `src/simulation/runner.py` | modify | Indexed finalized-receipt idempotency, including checkpoint carry and recovery. |
| `src/simulation/replay.py`, `src/simulation/inspection.py` | modify | Explicit boundary materialization and generic ordered-sequence reads. |
| `src/simulation/runner_serialization.py` | modify | Streaming canonical trajectory hashing with identical bytes. |
| `src/experiments/generational_sampling.py` | create | Detached longitudinal regional/community sampler and one trusted stop criterion. |
| `src/experiments/generational_artifacts.py` | modify | Detached sample references and evidence coverage. |
| `tests/unit/test_engine_history_sequence.py`, `tests/unit/test_streaming_trajectory_hashes.py`, `tests/unit/test_generational_sampling.py` | create | Storage, hash, sample/criterion equivalence. |

## Task 13: Replace cumulative history tuple copying with immutable chunks

### Intent

Avoid O(total prior events) allocation on every tick without deleting history or changing authoritative evidence.

### Implementation Steps

1. Add private `HistorySequence[T]` implementing `collections.abc.Sequence`. Each immutable node stores the prior node, a new immutable tuple chunk, total length, and absolute chunk tick range. Empty append returns self; nonempty append is O(size of new chunk), not a copy of the prefix.
2. Implement ordered iterative traversal with an explicit node stack, integer indexing including negatives, slicing returning tuples, reverse iteration, length, and explicit `to_tuple()`. Do not recurse once per tick. Indexing may be linear; full exports are explicitly linear. Do not implement misleading constant-time random access claims.
3. Change private `_EngineSnapshot` histories to this type. Replace every cumulative append path: normal candidate prepare, external boundary event paths, admitted population entry, extension/fold paths, bootstrap, and restoration. Preserve candidate immutability: aborted candidates cannot alter the committed history prefix.
4. Keep `prior_event_window` as the original current/prior-tick tuple; cognition observation content must not change. Existing teaching gets a complete ordered Sequence. Same-tick boundary-event sequencing must use existing event order and ID counters, including after restore.
5. At public event export and replay serialization boundaries explicitly materialize tuples where the public contract requires them. Inspection may iterate the Sequence. Never expose the private history type through public facades, snapshots, or codecs.
6. Verify the Task 8 finalized-tick ID set removes the per-tick prefix scan in `_finalize_and_acknowledge`, including empty ticks now using that path. Membership is O(1); rebuilding once from a supported checkpoint is O(retained receipts), never per tick. Keep full public receipt tuples and existing hash inputs. Include runner bookkeeping in the structural complexity proof rather than claiming event-container optimization alone makes long runs practical.

### Required Interfaces and Contracts

This is an internal container optimization with bit-identical event and resolution order. It is not history truncation, bounded-memory storage, a new event schema, or permission to delete persistent rows. Total engine memory still grows with all historical objective events/bodies.

### Requirement Evidence

User very long horizons; concrete tuple-copy evidence; architecture append-only/replay invariants; C1/C7/C10.

### Error Handling and Logging

Retain existing errors for unsupported sequence inputs and index bounds. No per-event logs; DEBUG aggregate chunk/event counts at explicit diagnostic checkpoints only.

### Tests

Sequence laws, empty chunks, negative indexing/slicing, 100000 single-item appends without recursion, structural sharing of old snapshots, aborted candidate isolation, boundary-admission event order, restore then append, teaching outputs and observation parity, and exact exported bytes before/after container replacement. Instrument runner receipt membership under N and 2N ticks: assert one indexed lookup per finalized boundary and no iteration over the historical receipt prefix; include checkpoint reindexing and repeated in-process recovery.

### Acceptance Criteria

Committing a tick never reconstructs the entire historical event/resolution tuple or scans the finalized-receipt prefix for idempotency; explicit full exports remain complete and compatible.

### Verification

`uv run --frozen pytest --cov --cov-report=term-missing tests/unit/test_engine_history_sequence.py tests/unit/test_checkpoint_restoration.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py -q`

Expected: sequence and legacy authority/determinism gates pass.

## Task 14: Stream canonical hashes without dropping retained evidence

### Intent

Prevent the final result hash from constructing a second giant list/dictionary/JSON payload for long experiments.

### Implementation Steps

1. Add an internal trajectory JSON byte iterator in `runner_serialization.py`. Emit exactly the existing sorted-key canonical document prefix, each canonically encoded tick receipt separated by commas, and the existing suffix. Exact mode includes run ID; normalized mode keeps its current exclusion rules.
2. Feed bytes incrementally to SHA-256. Do not hash independent chunks and concatenate their digests, change separators/key order, or introduce a new hash identity.
3. Keep `exact_trajectory_hash` and `replica_normalized_trajectory_hash` public signatures and results unchanged. Allow internal iteration without rebuilding a list of encoded receipts; maintain the existing zero-receipt fallback in result-document construction.
4. Preserve complete attempt/finalized/goal receipts and audit outputs for now. Do not introduce a sparse result that silently invalidates metrics or count fields. Document costs: O(total historical state/evidence) retained memory, one explicit final export, and potentially history-scanning optional channels such as teaching.
5. Add instrumentation tests counting per-receipt encoding and peak temporary allocations with fixed synthetic receipts. Use shape/operation-count assertions as correctness gates; do not use flaky wall-clock ratios as default unit-test failures.

### Required Interfaces and Contracts

Byte-equivalent hashes are mandatory for legacy and new runs. Long horizon means no artificial tick limit and improved transient/copy costs, not infinite-resource execution. Append-only storage and audit retention remain intact.

### Requirement Evidence

User long horizons and reproducible metadata; existing exact/replica hash implementation; C1/C9/C10.

### Error Handling and Logging

Invalid receipt fails with the existing safe serialization error. DEBUG hash mode and receipt count only; no encoded resolutions, fingerprints used as content surrogates, or memory evidence in logs.

### Tests

Golden comparison against the current canonical full-document algorithm for empty/one/many receipts, escaping/unicode IDs, denied/applied actions, differing run IDs, and receipts from a real AY generational run. Ensure counts stay totals, not sample counts.

### Acceptance Criteria

Hashes are unchanged and no full encoded tick list or full JSON byte string is built in the hash path.

### Verification

`uv run --frozen pytest --cov --cov-report=term-missing tests/unit/test_streaming_trajectory_hashes.py tests/unit/test_generational_result_codec.py -q`

Expected: golden hash and allocation-shape cases pass.

## Task 15: Sample cohorts, migration, and candidate communities outside simulation

### Intent

Support historical multi-community experiments without equating regions/cohorts with societies or feeding analysis into cognition.

### Implementation Steps

1. Implement `GenerationalHistoricalSampler` in `experiments/generational_sampling.py`. At requested history boundaries read an immutable evidence snapshot clamped to the finalized commit/high-water marks. Reuse low-level regional event/journey and community analysis contracts, but do not directly treat `society_emission_inputs_from_snapshot` or its first_tick=0 residence projection as a trailing-window implementation. The new sampler owns the windowed projection, leaving legacy cumulative adapters unchanged.
2. Emit detached regional residence/cohort/generation counts, in-transit totals, journey departures/arrivals/deaths, and `compute_candidate_communities` output with algorithm/version, evidence coverage, and window bounds. Missing required dimensions/edges must be marked partial or unavailable, not zero or a full isolation audit.
3. At B define W=max(0, B-window_ticks) and the half-open event window [W,B). Reconstruct state at W from bootstrap plus the prefix through W-1 (or a verified authoritative snapshot and journal fold), then replay events W through B-1 in their original committed sequence. Do not discard the prefix before initializing resident/alive/transit state. Derive actual residence intervals clipped to W and each person's entry tick; departure suspends residence, arrival establishes the new region, death ends eligibility. Carry routes already in transit at W so an in-window arrival is explained. Community nodes are living-at-B persons only; filter historical edges/residence to those nodes, and pass empty rows/edges when living is empty so the analysis fallback cannot resurrect dead persons.
4. Maintain an explicit detached registration mapping for founders and entrants between agent_id and body_id from existing registration/entry facts. Society person IDs use body IDs as the existing analysis contracts do; lifecycle/cohort joins use the mapping, never string-prefix guesses or equality of unlike IDs. Persist both identity roles where needed in protected analytical artifacts. Community identity is sample-local; do not claim persistent group identity across windows or write community output into world/cognition.
5. Provide trusted criterion `community_count_at_least@1` (`criterion_id="community_count_at_least"`, `version="1"`) with exact params `{count, window_ticks}`. Require count>=1, window>0 and active regions. Production requires durable scientific evidence, a read-only snapshot reader, and the full detached registration mapping; reject missing dependencies before creation. Define source completeness from objective prefix/window continuity and requested evidence high-water availability, independent of `SocietyEmissionResult.coverage` (which measures clustered-person coverage and may be partial with perfectly known singleton agents). B<window_ticks is warmup/incomplete. Match only when source coverage is complete and candidate-community count meets the threshold; missing sources/warmup return unmatched with `coverage_complete=false`. Preserve separate availability flags for divergence/isolation dimensions so their absence does not falsely make complete community input incomplete. It closes over the reader/sampler, never the runner.
6. Cache only the current boundary sample so a criterion and history observer at B reuse identical evidence. Do not accumulate a second in-memory longitudinal result list; persist one immutable artifact per sampled boundary and reference it in the history index.

### Required Interfaces and Contracts

Neutral migration remains normal agent command/journey execution; the runner does not teleport agents or manufacture contact. Spawn distribution is not migration. An analytical stop can end an experiment externally, but cannot change the simulated beliefs or actions leading to that boundary.

### Requirement Evidence

User migration/multiple-community/cohort requirements; existing AY/AZ contracts and snapshot composition; architecture analysis isolation; C6/C7/C8.

### Error Handling and Logging

Unknown criterion/params fail preflight; snapshot cutoff mismatch is an artifact/criterion error. DEBUG boundary, window, coverage flags and counts only. Never log member lists, evidence propositions or subjective digests.

### Tests

Two isolated candidate communities using the real AZ topology; actual contact journeys; generation/cohort joins with deliberately different agent/body IDs including an entrant; entrant halfway through a window; departed/arrived/died persons; journey crossing W; obsolete pre-W interactions excluded; prefix residence correctly carried; future events excluded; empty living roster yields zero candidates; complete singleton evidence distinguished from missing evidence; warmup/partial sources do not falsely stop. Verify transit conservation, criterion/history cache identity and no community feedback into cognition/world.

### Acceptance Criteria

Historical sampling reports multiple communities as detached hypotheses with truthful evidence coverage and consistent temporal boundaries.

### Verification

`uv run --frozen pytest --cov --cov-report=term-missing tests/unit/test_generational_sampling.py tests/unit/test_society_composition.py tests/unit/test_experiment_ay.py tests/unit/test_experiment_az.py -q`

Expected: longitudinal sampling, migration conservation, and existing regional/community tests pass.

## Phase Risks and Mitigations

- Changing a private history representation touches restore/admission paths: exhaustive sequence and export parity tests are mandatory.
- Complete history is still used by some optional channels: disclose remaining costs rather than prune evidence or overpromise constant RAM.
- Existing collector paths differ in temporal/evidence completeness: use the snapshot composition at an explicit boundary and mark partial coverage.

## Phase Completion Checklist

- Tasks 13–15 meet acceptance criteria and commands pass.
- Update only the index progress ledger.
