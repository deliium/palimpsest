# Phase 2: Active cognition and immutable retired-owner state

Plan: [index.md](index.md)
Tasks: 4–6
Depends on: Tasks 1–3

## Objective

Make routine cognition scheduling proportional to active owners rather than every owner ever admitted. Release dead owners' live cognitive/service graphs without deleting their memories, audits, provenance, identities or fork state. This is not a constant-process-memory claim: immutable objective history and frozen owner records still grow.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/simulation/runner.py` | tick loop 2938; `_sync_mid_run_population_entries` 5701; append 5860 | Historical runtime roster participates in every tick and admission refresh. |
| `src/simulation/agent_runtime.py` | terminal skip 2068; dead-self transition 2215; audit lists 552 | Skipping deliberation does not release the live object graph. |
| `src/simulation/runner.py` | `capture_fork_checkpoint` 3966–4045; cultural export 3611; final audit harvest 4646+ | All registered owners must remain exportable after retirement. |
| `src/simulation/fork_checkpoint.py` | `AgentRuntimeForkState`, `AUDIT_FIELD_NAMES` | Complete process-local continuation includes audits and idempotency state. |
| `src/simulation/subjective_state.py` | `SubjectiveOwnerForkState`, `ForkCapableSubjectiveOwnerBundle` | Existing immutable owner-state export is the freeze boundary, not objective replay. |
| `src/agents/cognition/loop.py`, `src/agents/cognition/fork_state.py`, `src/agents/cognition/budget.py` | loop export/restore 1340–1398; `TickBudgetLedger` 322 | Outer fork DTOs are frozen, but the budget ledger and translation application dictionaries are mutable leaves today. |
| `src/simulation/runner.py` | factory clones 569–625; `_AgentBundle` 1663; destination export 4231 | Policy cloning and every retained service/retriever field must be addressed, not only `bundle.bundle`. |
| `src/simulation/generational_progress.py` | `build_population_progress` | Rebuilds all body/cohort totals each finalized tick. |
| `src/simulation/_history.py` | `HistorySequence` | Append already shares structure; slicing still materializes the prefix. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/simulation/runner.py` | modify | Active ordinal index, safe retirement barrier, archived export routing, incremental progress integration. |
| `src/simulation/agent_runtime.py` | modify | Terminal-only freeze transition and frozen export delegates, preserving runtime identity/public accessors. |
| `src/simulation/retired_owners.py` | create | New frozen `RetiredOwnerRecord`, `RuntimeRetentionPolicy`, and read-only retired bundle adapter. |
| `src/simulation/subjective_state.py` | modify | Read-only frozen owner export/snapshot adapter using existing typed fork DTOs. |
| `src/agents/cognition/fork_state.py`, `src/agents/cognition/budget.py`, `src/agents/cognition/loop.py` | modify | Deeply detached process-local budget/translation fork leaves and fresh mutable restoration. |
| `src/simulation/generational_progress.py` | modify | New `PopulationProgressAccumulator`; retain full fold as oracle. |
| `src/simulation/engine.py`, `src/simulation/_history.py` | modify | Same-tick sequence metadata and bounded history-range helpers, without dropping history. |
| `src/simulation/__init__.py` | modify | Explicit public exports for composition-only policy, not engine internals. |
| `tests/unit/test_runner_active_owners.py`, `tests/unit/test_retired_owners.py`, `tests/unit/test_incremental_population_progress.py` | create | Scheduling, exact freeze/export, and incremental-fold regressions. |

## Task 4: Schedule only active runtime ordinals

### Intent

Remove an observed O(total admitted owners) traversal from the cognition loop without changing command order or terminal semantics.

### Implementation Steps

1. Maintain an insertion-ordered active ordinal registry alongside the complete `_runtimes` and registration roster. Initial ordinals equal registration positions; newly admitted owners get the same permanent ordinals as today. Never compact or reuse ordinals.
2. Iterate active ordinals for prepare/bind/finalize. An owner whose terminal transition is pending still receives the same final dead-self observation as the reference implementation. Remove the ordinal only after that transition and all pending finalizations have been acknowledged.
3. Preserve complete objective observations needed by capture. If a removed owner contributes grounding evidence, obtain the detached observation through the capture boundary path rather than invoking cognition. Do not turn missing owner observations into fabricated grounding.
4. Update entry synchronization and translator refresh to visit only owners whose mutable cognition can change; store generation/registration lookup maps at admission. Preserve addressable dead entity IDs in living owners' vocabularies; removal from scheduling is not social forgetting.
5. Rebuild the active registry from runtime status plus objective body/lifecycle bindings on recovery/fork restoration. Retain existing all-terminal stop decisions, including empty-population gaps and later admissions.

### Required Interfaces and Contracts

- Stable complete roster remains the source for registration order, results and forks; active ordinals are a derived execution index.
- No change to `prepare_parallel=False`, RNG ordering, owner invocation IDs or submission order. Never use set iteration order.
- A runtime terminal for an error is not assumed objectively dead. Existing error/stop behavior remains; freezing in Task 5 requires confirmed objective death.

### Requirement Evidence

User: dead owners must not stay in active cognition; immutable history. Architecture: owner scope and deterministic admission. Source: tick loop and process-local fork roster contract above.

### Error Handling and Logging

Fail closed on duplicate/missing ordinal or roster mismatch. DEBUG aggregate active/terminal/transition counts per sampled boundary; INFO retirement summaries. Do not log one terminal skip per historical owner per tick.

### Tests

`test_runner_active_owners.py`: living/dead mixed roster, same-tick death/admission, empty gap then admission, terminal error, cancelled pending finalization and recovery. Instrument prepare calls: increasing retired count with fixed living count must not increase prepare calls; compare exact events and invocation order with Task 3 oracle.

### Acceptance Criteria and Verification

`uv run pytest tests/unit/test_runner_active_owners.py tests/unit/test_runner_fork_checkpoint.py --cov=simulation --cov-report=term` passes; operation-count assertions prove retired owners are not scheduled.

## Task 5: Freeze dead-owner state and release live cognition graphs

### Intent

Avoid retaining unused `CognitiveLoop`, live memory indexes, mutable services and audit-list copies solely because their owner once existed.

### Implementation Steps

1. Add composition-only `RuntimeRetentionPolicy(retire_dead_owners: bool = False)` to `RunnerDependencyFactories` construction, slots/property and both cloning helpers `with_generational_control`/`with_criterion_factory`; propagate it through normal construction, fork construction and generational CLI composition. No runner JSON/capability flag. Default behavior and durable serialization stay unchanged. Enable explicitly in paired benchmark lanes after parity tests pass, with a real production-composition test proving clones do not reset the policy.
2. At a fully finalized safe boundary, require objective death, terminal runtime status, no unacknowledged owner finalizations, and fork-capable owner services. Export `AgentRuntimeForkState` and `SubjectiveOwnerForkState` exactly once. Capture the final cultural/lineage/civilization owner projection required by installed sinks before releasing live references.
3. Make fork-state leaves genuinely detached before treating the record as immutable. Introduce frozen `TickBudgetForkState` with owner/tick, canonical policy identity, used/exhausted/warned collections, started-at value, reflection/depth/first-exhausted fields. Add budget export/restore helpers that reconstruct fresh mutable containers using the destination loop's injected policy; they must not call the policy clock during capture/restore or retain the old ledger/callback graph. Freeze translation-application mappings into explicit immutable key/value tuples and restore new dictionaries. Audit other `object` leaves in `CognitiveLoopForkState` against their actual typed contracts; retain immutable values by reference, but reject unsupported live/mutable custom values rather than using pickle or generic executable-object deep copy. Preserve process-local fork compatibility through explicit leaf-type/version dispatch and tests; no durable runner/checkpoint schema bump.
4. Construct one frozen `RetiredOwnerRecord` containing permanent owner/body/ordinal identity, death and finalized boundary references, both complete detached fork DTOs, immutable audit exports, enabled-channel/mode metadata and cached owner projections. Reuse proven immutable DTO references rather than duplicating trace/audit tuples. This record is process-local; do not invent a durable full-subjective restart format. Retired cultural/civilization exports must not consult the released loop for mode enablement.
5. Add `AgentRuntime.freeze_terminal(record: RetiredOwnerRecord) -> None` on the existing object so `runner.runtimes` keeps its typed values and object identity. Strip live loop/service references only after successful record installation. Route `export_runtime_checkpoint`, `export_fork_state`, `export_lineage_owner_state`, `export_cultural_owner_state`, `export_civilization_owner_state`, `export_cultural_narratives` and every audit exporter to the frozen record; retain the full `AUDIT_FIELD_NAMES` inventory. Calling prepare on a frozen terminal runtime returns the same terminal outcome without allocating/restoring cognition; a mutation attempt fails closed.
6. Replace the frozen `_AgentBundle` value atomically with a retirement-safe bundle whose `bundle`, `memory_service`, `belief_service`, `relationship_service`, `subjective_state` and `memory_retriever` fields do not retain the released graph. Keep its original `runtime` identity. Provide typed read-only memory/belief/relationship views plus a rejecting commit adapter; the unused retriever is `None`. Match `snapshot()` active/tombstone filtering and ordering exactly, while full fork/history exports retain forgotten traces and all revisions. Exercise `export_regional_destination_traces` and final audit harvesting, which access service fields directly, as well as `bundle.snapshot()` and fork export. Transaction/mutation operations reject. External factory-owned services are not globally cleared or closed.
7. Fork capture combines active exports and frozen records in permanent registration order, satisfying the existing exact full-roster checks. Fork restore creates child-local owner services, budget ledgers and translation dictionaries, never aliases mutable parent/sibling state. Explicit fork/result materialization may be O(total history), and its peak is measured separately. A metadata-only recovered `AgentRuntimeCheckpoint` is not enough to synthesize a complete retired owner record; retirement after recovery requires the same complete owner-state exports or remains unsupported.
8. Keep non-fork-capable/custom bundles or unsupported mutable fork leaves live and report a safe `retirement_unsupported` count; never evict incomplete state. A required retention benchmark must distinguish these fallbacks and cannot advertise full retirement when they occur.

### Required Interfaces and Contracts

- `RetiredOwnerRecord` is frozen, owner-qualified and complete; final audit/provenance results must be byte-equivalent to the reference. No audit-field omission, forgotten-memory deletion or idempotency-key removal.
- Historical inspection uses frozen read exports in-process and existing persisted/captured evidence after restart. This plan does not fabricate uncaptured subjective history or claim durable subjective resume. Long-dead objective history and captured lineage remain queryable regardless of live runtime presence.
- Frozen records still consume memory. The supported envelope must state residual retained DTO/history cost; this task only bounds active cognition/service graphs by the living roster.

### Requirement Evidence

User: no provenance deletion and long-dead queryability. `fork_checkpoint.py` module contract; `SubjectiveOwnerForkState` exact fields; cultural capture requires deceased provenance sources.

### Error Handling and Logging

Freeze is atomic: on export/adapter failure, retain the original live bundle and log WARN with owner ID/reason code. Never discard the only copy to meet a memory budget. Frozen-state corruption fails exports/fork capture explicitly. DEBUG reports live graph/frozen record counts, not memory contents or hashes.

### Tests

`test_retired_owners.py`: weakref-compatible test loop/service sentinels prove owned live graphs become collectable without requiring production objects to support weak references; frozen exports retain all traces, reconstructions, beliefs, relationships, audits, operation IDs and ledger revisions; failed freeze preserves live object; retirement idempotency; other owners cannot read the record; final death-boundary capture; regional destination and final audit exports; custom unsupported factory fallback; historical queries after later generations. Extend `test_runner_fork_checkpoint.py` with dead owners, budget mode enabled and translation applications: mutating a restored child's counters/dictionaries must not alter parent or sibling exports. Assert capture/restore makes zero extra clock calls; active snapshots exclude the same tombstones while full history retains them; both factory clones preserve retention; metadata-only recovery cannot fabricate complete owner state.

### Acceptance Criteria and Verification

`uv run pytest tests/unit/test_retired_owners.py tests/unit/test_v3_scale_equivalence.py tests/unit/test_runner_fork_checkpoint.py --cov=simulation --cov=memory --cov-report=term` passes. The benchmark reports active object count separately from retained frozen bytes and demonstrates graph release, not merely fewer prepare calls.

## Task 6: Increment population progress and eliminate same-tick prefix scans

### Intent

Remove repeated recomputation while preserving the existing exact `PopulationProgress` and complete event history.

### Implementation Steps

1. Introduce `PopulationProgressAccumulator` keyed by stable owner/body and cohort/generation IDs. Bootstrap once from the full validated fold; process committed admissions and objective death transitions exactly once at finalized boundaries. Do not infer living status from runtime retirement.
2. Preserve canonical sorted cohort/generation rows on export and all validation errors from `build_population_progress`. If a complete `PopulationProgress` is requested each tick, output allocation remains proportional to cohort count; do not claim O(1) export. Cache unchanged rows and compute stop selectors from exact accumulated counters.
3. Rebuild accumulators from verified snapshot/lifecycle/body state after restore; detect boundary replay/idempotent application and reject gaps or conflicting duplicates. Keep derived counters outside objective event schemas.
4. Track next event sequence for the current admission/tick boundary in `WorldEngine` instead of scanning all events for same-tick population entries. Initialize from exact restored suffix/current cursor and preserve all within-tick ordering rules.
5. Add range/suffix traversal to `HistorySequence` using chunk tick metadata and reverse traversal where valid. Replace only same-tick/range callers proven by profiles. Retain structural sharing, complete iteration/export and legacy sequence laws. Audit teaching history use explicitly; do not prune history needed by teaching or replay.

### Required Interfaces and Contracts

Derived state must equal full recomputation after every boundary. No new event, command, replay/codec version or runner field. Objective bodies, genealogy edges, records and lifecycle history are not evicted in this phase.

### Requirement Evidence

User: population/history/event scaling without deletion. `generational_progress.py` full-fold invariants; `HistorySequence` complete-history contract.

### Error Handling and Logging

Reject duplicate/conflicting admissions, missing body bindings and boundary gaps with existing safe invariant codes. DEBUG changed-row/visited-chunk counts; no per-body payloads. Never silently fall back to an incorrect counter total.

### Tests

Hypothesis short histories covering admission/death, empty ticks, same-tick events and restore; accumulator equals full fold every tick. Sequence laws and exact slicing/range equivalence; retained old versions remain immutable. Operation counts demonstrate no full event-prefix scan for admission.

### Acceptance Criteria and Verification

`uv run pytest tests/unit/test_incremental_population_progress.py tests/unit/test_engine_history_sequence.py tests/unit/test_v3_scale_equivalence.py --cov=simulation --cov=world --cov-report=term` passes; Task 2 profiles show target operation reductions with unchanged canonical output.

## Phase Risks and Mitigations

- A dead owner can still be required by audits/forks: freeze complete typed state before releasing anything and retain exact export compatibility.
- Runtime identity/accessor behavior is public: retain the original `AgentRuntime`, exercise every export consumer, and keep retirement opt-in.
- Total objective/frozen history still grows: publish that fact; do not claim constant RSS or shrink subjective ledgers to hide growth.

## Phase Completion Checklist

- Tasks 4–6 satisfy exact parity and operation-count gates.
- Pending-finalization, fork and historical-query tests pass.
- Update task checkboxes only in `index.md`.
