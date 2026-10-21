# Phase 6: Detached continuity and provenance metrics

Plan: [index.md](index.md)
Tasks: 11
Depends on: Tasks 1–10

## Objective
Measure information persistence, acquisition and source continuity without installing a global institution or teaching ground truth to agents.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|---|---|---|
| `src/analysis/offices.py` | `harvest_office_rows`, `align_office_roles`, `OfficeAlignment` | Cross-owner alignment is detached function/context inference with ambiguity. |
| `src/analysis/mediation.py` | `harvest_mediation_rows`, snapshot coverage and metric functions | Pattern for owner exports, partial histories and absence. |
| `src/analysis/metric_service.py` | `MetricComputationInputs` (207), `assemble_metric_documents` | Optional rows route to detached metric families. |
| `src/analysis/specifications.py` | `MetricFamilyId`, `_spec_conflict_mediation`, specification builders | Explicit formulas, denominator, coverage and evidence stages. |
| `src/experiments/collectors.py` | owner ledger harvesting (642–665) | Analysis composition belongs outside simulation. |
| `src/world/events.py` | `WorldEvent`, `Talked`/`Asked`/`Told`, `ArtifactCreated`/`ArtifactModified`/`ArtifactCopied` | Actor is on the event; recipient and artifact revision/lineage are on details. Record content is not in artifact event details. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/analysis/institutional_memory.py` | create | Typed detached snapshots, provenance edges, alignment and two metric computations. |
| `src/analysis/metric_service.py` | modify | Optional institutional inputs and dispatch. |
| `src/analysis/specifications.py` | modify | Register two exact metric specifications. |
| `src/analysis/__init__.py` | modify | Public metrics/harvest exports. |
| `src/experiments/collectors.py` | modify | Completed-result harvesting only. |
| `tests/unit/test_institutional_memory_metrics.py` | create | Known answers, denominator/ambiguity/coverage cases. |
| `tests/unit/test_institutional_memory_analysis.py` | create | Alignment and provenance classification. |

## Task 11: Add institutional memory continuity and provenance analysis

### Intent
Describe source-carrying continuity and losses across occupants without equating titles, matching claims or repeated root declarations with verified information transfer.

### Implementation Steps
1. Introduce `InstitutionalMemorySnapshot`, entry/channel/use/occupant-claim rows and `InstitutionalMemoryTransferEdge`; `harvest_institutional_memory_rows(ledgers)` freezes only completed exported values. Occupant-change evidence comes from the owner's retained `InstitutionalOccupantClaim` rows, not from office snapshot digests or an objective occupant registry. Preserve disabled/absent versus enabled-empty versus partial. Add optional `institutional_memory_rows` to `MetricComputationInputs`, default `None`; collector uses `is not None`, not truthiness.
2. Align role channels after the run using detached office function/context evidence, following `align_office_roles`; never local ID/label/occupant equality alone. Procedure alignment requires matching retained anchors, otherwise exclude. Multiple local candidates per owner/alignment produce ambiguity, not a selected best candidate.
3. Build candidate transfer edges from actual delivery receipts or observed artifact/revision/native copy lineage, with separate declared parent/root edges. Edge statuses: `observed_carrier_path`, `declared_only`, `ambiguous`, `unresolved`, `pruned`. Apply the exact row/join rules below; a declared parent may suggest candidates but never alone establish a path. No global mutable knowledge DAG is returned to cognition. An analytical path is not proof that content is true or office authority exists.
4. Add exactly two v1 families: `institutional_memory_continuity@1` and `institutional_memory_provenance@1` (catalog 124→126). Continuity keys: `enabled_owner_count`, `bound_channel_count`, `entry_count`, `record_acquisition_count`, `transmission_acquisition_count`, `teaching_acquisition_count`, `partial_entry_count`, `ignored_entry_count`, `consulted_entry_count`, `cross_occupant_opportunity_count`, `cross_occupant_acquired_count`, `ambiguous_alignment_count`, `excluded_alignment_count`, `partial_coverage`, `as_of_tick`.
5. Continuity opportunity denominator is uniquely aligned role windows with a locally evidenced attributed occupant change and retained source information before change; acquisition numerator requires a distinct later claimed occupant-owner with a receipt after the change and an unambiguous carrier path. These remain analyses of attributed role claims, never verified office occupancy. Procedure-only channels without occupant evidence contribute entry/acquisition/provenance counts but not cross-occupant opportunities. No change window/source coverage → zero opportunity count and no fabricated success rate; keep rates out of v1 keys. Report record survival separately in detached test assertions; survival is not acquisition.
6. Provenance keys: `entry_count`, `observed_carrier_edge_count`, `declared_only_edge_count`, `ambiguous_edge_count`, `unresolved_edge_count`, `pruned_edge_count`, `independent_root_count`, `conflicting_claim_count`, `partial_coverage`, `as_of_tick`. Independent root count uses observed distinct source paths, never independent root strings alone. Conflict counts require same aligned context and subject/predicate with differing objects; disagreement is not an error label. Do not add cognition-facing `truth`/`verified` fields.
7. Both specifications use bounded exported owner snapshots plus detached objective carrier/delivery evidence when available. Add optional `institutional_memory_carrier_rows` and `institutional_memory_identity_rows` inputs, default `None`, populated in experiments after completion from existing event/result contracts, not from cognition. Keep absent input distinct from a complete empty event window. Use specification formula/value-key equality tests. Empty/no data is `ABSENT`; pruned/ambiguous necessary evidence yields `PARTIAL`; quantize numeric output with existing helpers.
8. Route harvest and computation through the existing collector/metric service without imports from `simulation` into `analysis` internals or analysis into live cognition. Do not add SQL tables or an API endpoint; existing metric catalog discovery exposes registered families.

### Required Interfaces and Contracts
`compute_institutional_memory_continuity(rows, *, run_id, input_revision, tick=0, carrier_rows=None, identity_rows=None, office_rows=()) -> MetricDocument`; analogous `compute_institutional_memory_provenance`. Analytical alignment/joins are researcher-only. Keep snapshots/rows owner-tagged and source references detached. Never infer a failed transfer solely from absent/pruned evidence.

### Exact Detached Row and Join Contract

- Define frozen `InstitutionalIdentityRow(agent_id, entity_id, first_tick, last_tick=None)`; both IDs are stable strings in distinct namespaces, never compared as though interchangeable. Collector harvests initial identities from assignment agent specs (first tick 0) and admitted identities from actual `AgentInitializationRecorded` events: detail `agent_id` maps to detail `body_id.value`, starting at that event's tick. This is explicit objective identity evidence, not a claim inferred from cultural lineage. Legacy/snapshot-only dynamic owners lacking such a binding remain unresolved with partial identity coverage. Conflicting entity→agent bindings at the relevant tick remain unresolved. Do not assume every dynamic agent is in initial config or invent a runner-result identity field.
- Define frozen `InstitutionalCarrierRow(run_id, event_id, tick, sequence, kind, actor_entity_id, recipient_entity_id=None, artifact_id=None, content_revision=None, parent_artifact_id=None, source_artifact_id=None)`. A missing optional value is unknown. No mark, frame root or content digest is invented for an artifact event. The carrier extractor accepts completed `WorldEvent` values only outside live cognition and returns deterministic rows ordered by `(tick, sequence, event_id)`.
- Implement `institutional_memory_carrier_rows_from_events(events)` with explicit public detail types. For `Talked`, `Asked`, `Told`, project event actor plus detail recipient. For `ArtifactCreated`, `ArtifactModified`, `ArtifactAnnotated`, `ArtifactDamaged`, `ArtifactPartiallyLost`, project detail artifact ID/revision; for `ArtifactCopied`, use child ID/revision and native parent/source IDs. Ignore unrelated types and never duck-type `details.actor_id` (there is no such field). Destruction can close availability but never supply lost body facts. No event-detail content field is assumed for artifacts.
- Snapshot entry rows retain owner/entry/channel IDs, acquisition tick/channel, declared root/parent, exact source event ID if present, artifact/revision if observed, and partial/reference-state flags. Use rows retain owner/local entry/invocation/tick/disposition. Extract these fields from the ledger, not from nearby aggregate counts. Dedup source evidence by `(run_id,event_id)` for native events, by `(owner_id,entry_id,revision)` for entries and by `(owner_id,invocation_id,entry_id,disposition)` for uses; conflicting same-key rows are errors, not arbitrary winners.
- A speech edge needs receiver entry source event ID matching one delivery row, recipient entity resolving to that receiver, actor entity resolving to the source owner, and source-owner effective `transmission_attempt`/`teaching_attempt` use at the event tick referencing an already acquired entry. Acquisition at that same tick is valid when present in the prepared tick-start ledger (observation/learning precedes action resolution); never require an artificial extra-tick delay. If multiple source uses match, classify ambiguous. A mere equal declared root is insufficient. A delivered `Ask` may establish delivery evidence, but no inferred institutional attempt is created when production left it undecorated.
- A record edge needs a receiver-acquired exact artifact/revision and a completed creation/revision/copy row at or before exposure; require source-owner effective `recording_attempt` at creation tick for an attributed writer→reader path. An event confirms carrier/revision, not marks or truth. `CopyRecord` follows native parent/source lineage; if source revision at copy time cannot be established, mark that leg partial/unresolved rather than assuming the latest revision. Passive reading has no native read event; its learning receipt remains an owner-exported acquisition, not a fabricated world event. Bootstrap/snapshot-only records without an event/author-use path still count as acquisitions but have unresolved writer edges.
- Cross-occupant opportunity key is `(alignment_key, prior_actor_agent_id, successor_actor_agent_id, transition_tick)` from nonoverlapping, uniquely resolved local occupant claims; duplicate owner reports collapse to one key. Exclude overlapping incompatible claims, missing start/end bounds, ambiguous role alignment and unresolved identities from numerator/denominator and increment exclusion/ambiguity counts with partial coverage. Distinct source paths or facts do not multiply one occupant-change opportunity. Numerator increments at most once per opportunity when the successor-owner acquires after the change through a matched source path.
- For `independent_root_count`, cluster native artifact-copy descendants and matched retransmission/teaching paths back to their earliest retained observed source entries. Never increment for a new outer envelope origin, repeated observed delivery of one source, or a fresh declared root alone. Unknown origin makes that component unresolved/partial, not independently rooted. A transmission cycle adds delivery edges without adding a new independent root. Conflicting facts are counted only within uniquely aligned contexts after these source/provenance distinctions.
- Every test in this task must collect and pass before BJ exists. Use synthetic known-answer rows plus already available BF/BI completed results here. The future BJ scenario must not be imported, conditionally skipped, or referenced as required setup in Task 11 tests; its collector end-to-end check belongs exclusively to Task 12.

### Requirement Evidence
Original request — provenance across occupants, incomplete/wrong/damaged/ignored memory. Architecture — analysis can retrospectively join evidence but must not feed live beliefs.

### Error Handling and Logging
Invalid row types/owners/counters fail closed with code-only analysis errors; unsupported alignment remains excluded/partial, not a crash or guessed match. Logs contain row/edge/count/availability metadata only; no payload, facts or source digests.

### Tests
Known-answer A record→B read→C teaching; record surviving without any learner; successor without access; matching titles with different contexts; multiple same-owner candidates; claimed forged root with no delivery; outer-envelope origin changed without an independent source; cyclic retransmission; wrong/conflicting claims; native copy lineage vs declared lineage; zero denominators; None/empty/pruned snapshots; ignored vs consulted counts; actor/entity IDs intentionally different; admitted identity not present in initial config; contested/overlapping occupant windows; duplicate owner reports; conflicting duplicate rows; snapshot-only carrier with unresolved author. Use current BF/BI results for empty/missing-channel collector compatibility. BJ end-to-end assertions are added and run in Task 12 only.

### Acceptance Criteria
Metrics distinguish availability, acquisition and provenance, and do not claim correctness or successful succession from title/label equality. Family count increases only by two.

### Verification
`uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_memory_metrics.py tests/unit/test_institutional_memory_analysis.py tests/unit/test_opt_in_metric_composition.py --cov=analysis --cov=experiments --cov-report=term -q`

Expected: this task's tests collect and pass independently of the future BJ scenario. Task 12 later proves the new real-scenario integration using the completed interfaces.

## Phase Risks and Mitigations
- Without complete role-change/source windows, continuity is not measurable. Mitigation: explicit opportunity denominators and partial/unresolved outputs, no scripted success.
- Repeated claims can fabricate apparent roots. Mitigation: observed path evidence and declared-only categories remain separate.

## Phase Completion Checklist
- Verify Task 11 and mark it only in index.
- Commit checkpoint 3 follows Tasks 9–11.
