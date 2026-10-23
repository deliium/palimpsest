# Phase 1: Contracts and complete fork state

Plan: [index.md](index.md)
Tasks: 1–3
Depends on: none

## Objective

Define a bounded historical-contingency protocol and close the known objective/subjective state-copy gaps before adding experiments.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|---|---|---|
| `src/simulation/branch_service.py` | `rematerialize_snapshot`, lines 377–477 | Both constructors omit kinship edges, dependency registers, and repositories. |
| `src/simulation/persistence.py` | `WorldSnapshot`, lines 603–639 | Complete objective field inventory. |
| `src/memory/service.py` | `InMemoryMemoryService.capture_transaction_state`, lines 105–124 | Traces alone omit reconstructions, derivation edges, access idempotency. |
| `src/memory/belief_service.py` | `capture_transaction_state`, lines 160–175 | Belief revision histories and operation receipts matter. |
| `src/social/service.py` | `capture_transaction_state`, lines 117–132 | Relationship history and operation state matter. |
| `src/simulation/subjective_state.py` | `SubjectiveOwnerSnapshot`, `InMemorySubjectiveStateService`, `SubjectiveOwnerBundle` | Read snapshots are not continuation checkpoints; commit revision/receipts also matter. |
| `src/simulation/agent_runtime.py` | `SequentialInvocationIds`; runtime slots 416–495; `export_runtime_checkpoint` 3256 | Count-only checkpoints omit deduplication sets, invocation counters, legacy stores and cultural completeness witnesses. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/experiments/path_dependence_models.py` | create | Frozen experiment, slot, intervention, window and lineage contracts. |
| `src/experiments/path_dependence_serialization.py` | create | Strict experiment-spec codec and canonical identity. |
| `src/simulation/branch_service.py` | modify | Field-complete snapshot rematerialization. |
| `src/memory/fork_state.py`, `src/social/fork_state.py` | create | Typed detached service-state values. |
| `src/memory/service.py`, `src/memory/belief_service.py`, `src/social/service.py` | modify | Public owner-checked state export/import. |
| `src/memory/models.py` | modify | Detached export/import for legacy `MemoryStore` and `BeliefStore`, preserving existing contracts. |
| `src/memory/__init__.py`, `src/social/__init__.py` | modify | Export new explicit contracts. |
| `src/simulation/subjective_state.py` | modify | Atomic complete owner fork-state export/import. |
| `tests/unit/test_path_dependence_models.py`, `tests/unit/test_fork_owner_state.py` | create | Validation and complete state isolation. |
| `tests/unit/test_simulation_branch_reproducibility.py` | modify | Snapshot field preservation regression. |

## Task 1: Define historical-contingency experiment contracts

### Intent

Make intervention scope, experimental units, windows and lineage explicit independently of runner JSON. This is a trusted experiment recipe, not a new capability flag.

### Implementation Steps

1. Introduce `PathDependenceSpec`, `PathDependenceArm`, `ScheduledCommandIntervention`, `OutcomeSelector`, `OutcomeWindow`, `BranchSlot`, and `PathDependenceLineage` in the new models file. Use frozen, defensively detached values, exact integer validation (reject booleans), finite numeric bounds, and stable IDs.
2. `PathDependenceSpec` fields: schema `path-dependence-spec-v1`, experiment ID `historical_contingency@1`, full accepted v55 base config, ordered numeric seeds, `replicates_per_seed`, ordered `fork_ticks`, absolute `horizon_tick`, arms, explicit ordered contrasts `(control_arm_id,treatment_arm_id)`, windows/selectors, `assignment_seed`, `max_interventions_per_arm`, `common_setup`, and composition-only capture policy. `common_setup` is one ordered absolute-tick command schedule shared by the entire parent timeline; descriptors permit existing `Move`, `Take`, `Eat`, `Drink`, `Sleep`, `Give` and `Wait`, never direct state edits or speech/belief injection. Reject duplicate actor/tick slots; cap setup at 4096 commands independently of the child treatment budget. Every common-setup tick must lie in `[0,min(F))`, including when several F values are configured, so setup never continues into an earlier branch's treatment window. F=0 requires empty setup. Require at least two distinct arm IDs and one contrast; permit one numeric seed but mark it descriptive. Duplicate numeric seeds remain allowed and never increase inferential n.
3. Every fork tick defines a separate star contrast from the same parent timeline, not an independent statistical replicate. Nested branch trees, adaptive outcome-driven interventions, config mutations, memory/belief patches, and alternate seed treatments are out of scope. Reject them rather than routing through the legacy closed `ResearchInterventionKind` catalog. After an attempt has created a durable child run, v1 never substitutes a new RunId into that planned slot; technical failure stays failed/missing. A new-identity rerun requires a separately declared ensemble.
4. Each arm has `schedule_by_fork_tick`, an immutable ordered mapping from every configured F to an action tuple. Actions are closed tagged descriptors: `give(item_id,recipient_entity_id)` or `wait`, each with explicit actor ID, absolute tick and intervention ID. An empty tuple means untouched policy at that F. Require exactly the spec's F keyset, ticks in `[F,H)`, unique `(tick,actor)` keys, at most four actions per arm/F by default, explicit cap no greater than 16, and identical unchanged runner configs across arms. Actor/recipient resolution is frozen from pre-treatment state, not chosen from later favorable outcomes.
5. Define half-open analytical action windows `[start,end)`, endpoint boundary samples at exact `end`, and generation-index windows resolved against absolute admitted-cohort progress. Every window explicitly names its `fork_tick`; never reset child ticks or generations to zero. Require windows to start at/after their F and end at/before H. The same parent can supply multiple F values but stays one seed block. V1 generation windows require an explicit absolute tick cap and exact observed cohort boundaries; an unobserved generation endpoint is censored, not replaced by the tick cap.
6. Define exact-key-set JSON encoding with bounded document/collection sizes, duplicate-key/nonfinite rejection and a canonical SHA-256 spec fingerprint. Store full command descriptors only in research artifacts, not operational logs. Do not use callables as persisted intervention definitions.
7. Freeze v1 protocol limits: at most 1024 seed entries, 32 replicas per seed entry, eight F values, 16 arms, 64 selectors/windows and 8192 planned children. Reject products exceeding the child cap before allocating slots. Spec/manifest documents are at most 16 MiB and depth 32; artifact evidence chunks at most 16 MiB each and 1024 chunks per branch. Per collected boundary cap 2048 owners and 50000 normalized rows; exceeding these limits marks capture partial/fails the required capture policy instead of silently truncating. These are protocol constants, not new environment variables.

### Required Interfaces and Contracts

- `decode_path_dependence_spec(payload: bytes) -> PathDependenceSpec`; `encode_path_dependence_spec(spec) -> bytes`; `path_dependence_spec_fingerprint(spec) -> str`.
- Lineage fields: ensemble/spec identity, parent scientific ID, parent attempt, parent boundary tick/revision/commit hash/snapshot hash, complete-state digest, child scientific ID/attempt, opaque slot ordinal, arm ID, action-schedule digest, assignment seed/policy, numeric seed/seed ordinal/replicate, provider identity, code/source identity, and channel-lineage digest. Root parent ID and ancestry list are retained even though v1 depth is exactly one.
- New sibling artifacts are `path-dependence-ensemble-v1`, `path-dependence-prefix-v1`, `path-dependence-branch-v1`, `path-dependence-outcomes-v1`, `path-dependence-comparison-v1`. Their detailed storage contracts are in Phase 5. No runner v56, result schema, world command/event, replay marker, metric family or SQL migration is introduced.

### Requirement Evidence

User request: early-intervention ensembles, common history, explicit lineage, repeated-seed comparison. `.ai-factory/ARCHITECTURE.md` — Versioned Extension Contract and trust boundaries.

### Error Handling and Logging

Stable validation codes: `unsupported_base`, `invalid_fork_window`, `duplicate_intervention`, `intervention_budget_exceeded`, `unknown_arm`, `unsupported_intervention`. DEBUG records schema, counts and stage; WARN/ERROR records code and safe experiment ID. Never log command payloads, raw JSON or subjective-state digests.

### Tests

`test_path_dependence_models.py`: exact codec round trip; malformed/unknown keys; booleans as ticks/seeds; duplicate arm/action IDs; missing contrast arms; out-of-window actions; cap overflow; ordered schedules; common-setup command tags/cap/duplicate slots/min(F) cutoff; F=0 with nonempty setup rejected; single/duplicate numeric seeds; unsupported runner/config changes; two F values retaining one root block; unsupported automatic replacement/retry fields rejected.

### Acceptance Criteria

Every accepted experiment has a deterministic bounded schedule and unambiguous sample/contrast identities; unsupported combinations fail before prefix execution.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_path_dependence_models.py -q`

Expected: all validation/codec tests pass with coverage enabled by project configuration.

## Task 2: Preserve complete objective state during rematerialization

### Intent

Prevent generational forks from silently deleting genealogy, unmet needs, repositories or future added snapshot fields.

### Implementation Steps

1. Add a regression to the existing branch reproducibility test creating a snapshot with nonempty `kinship_edges`, `dependency_need_registers`, and `repositories`; demonstrate their loss before changing implementation.
2. Refactor `rematerialize_snapshot` to use `dataclasses.replace` on the frozen source value for run/config/snapshot/hash/predecessor changes, then recompute integrity using `hash_snapshot`. Preserve every other field, including journeys and all older production/artifact/project state.
3. Keep child chain recomputation and parent prefix immutability in `materialize_objective_fork`; never copy parent commit hashes as child hashes. Add a field-inventory assertion allowing only explicitly listed identity/hash differences.

### Required Interfaces and Contracts

Existing signature remains unchanged. Restoring the child must reproduce the parent's boundary observations and objective data before any treatment, modulo declared run-scoped envelope/hash differences. Prefix is strictly `event.tick < F`.

### Requirement Evidence

`WorldSnapshot` complete field inventory and existing objective fork contract; user common-history requirement.

### Error Handling and Logging

Retain existing safe validation/logging. Add counts only for preserved field families; failed integrity is a hard error, never an empty-field fallback.

### Tests

Extend `test_simulation_branch_reproducibility.py`: nonempty modern fields survive, parent values/hashes unchanged, live/restored observation parity including prior-event window, F=0 and F>0, latest feature-selected codec and representative legacy snapshot.

### Acceptance Criteria

The regression fails on the old implementation and passes after the fix; existing fork hash tests remain green.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_simulation_branch_reproducibility.py tests/unit/test_new_agent_fork_replay.py -q`

## Task 3: Export and restore complete owner service state

### Intent

Clone the same owner's historical state into an isolated child without giving it to peers or admitted newborns, and without confusing read-only snapshots with continuation state.

### Implementation Steps

1. Add immutable typed `MemoryForkState`, `BeliefForkState`, `RelationshipForkState` owned by their respective packages. Include all transaction-state members shown above, policies, owner identity, and state-format version; introduce public export/restore methods on the concrete in-memory services. Also add detached owner-checked export/import on legacy `MemoryStore` / `BeliefStore` in `memory/models.py`; `AgentRuntime` still reads the legacy belief store in `build_perspective` and writes `WRITE_BELIEF` intents into it, so semantic beliefs alone are insufficient. Keep legacy and semantic stores distinct; never promote one into the other. Do not expose private stores or untyped transaction tuples to experiments.
2. Memory state includes traces, reconstruction records, derivation edges and access-operation IDs; belief state includes current beliefs, full revision histories and operation receipts; relationship state includes current profiles, histories and operation receipts. Validate all contained owners, references and unique IDs before mutation. Reconstruct fresh mutable dictionaries/sets and new orchestration objects on restore; share only immutable values.
3. Add `SubjectiveOwnerForkState` and `InMemorySubjectiveOwnerBundle.export_fork_state()` / `restore_fork_state(state, *, parent_scope)` in `subjective_state.py`. Capture/import under the commit lock, including `InMemorySubjectiveStateService` revision and idempotency receipts. Validate the destination owner equals source owner; only run scope may change. Import must target a fresh bundle and commit atomically, never partially install services.
4. Preserve historical trace/reconstruction/receipt identities as immutable provenance. Rescope typed storage envelopes/receipt run IDs only where their contract names the current store run; do not recursively replace strings, rewrite testimony roots, or recompute old subjective evidence against world truth. Use a typed rebase function per envelope with exhaustive field tests.
5. Expose a fork-capable optional protocol instead of making PostgreSQL or third-party subjective adapters falsely claim support. Non-fork-capable bundles fail preflight. No pickle, generic object deepcopy, JSON serialization of private Python objects, or new durable subjective restart contract.

### Required Interfaces and Contracts

- Public exports are detached immutable values with redacted `repr`; services retain framework-free domain boundaries.
- Owner service export plus runtime ledgers (Phase 2) jointly define a complete checkpoint. Provider clients, locks and DB sessions are resources, never copied state.
- Fork capture is process-local. Resume for an unused planned slot reconstructs parent state by validated deterministic prefix re-execution, not by loading an objective archive alone; an existing partial durable child is never retried or replaced.

### Requirement Evidence

`RULES.md` axioms 1–6; ARCHITECTURE — owner-scoped memory and append-only lineage; state-copy limitations found in current services.

### Error Handling and Logging

Codes: `fork_state_unsupported`, `fork_owner_mismatch`, `fork_state_invalid`, `fork_destination_not_empty`. INFO start/completion with owner counts; DEBUG format versions/counts; ERROR safe code only. Never log state values, proposition text, history fingerprints or payload-bearing exceptions.

### Tests

New `test_fork_owner_state.py`: recall/reconstruction parity, reconsolidation lineage, belief/relationship revision histories, idempotent receipt replay and conflicting-op rejection, nonempty legacy `WRITE_BELIEF` state preserved and isolated from semantic beliefs, legacy memory-writer contents, mutation isolation parent/child/sibling, owner mismatch, partial-import rollback, import twice rejection, unsupported adapter, no newborn inheritance. Exercise real services, not only a stub bundle.

### Acceptance Criteria

Future owner operations on a same-scope restored service have the same outputs and revisions as uninterrupted execution, while child mutable state remains isolated.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_fork_owner_state.py tests/unit/test_simulation_branch_subjective_clone.py -q`

## Phase Risks and Mitigations

- A new service field could silently be omitted: state-member inventory and operation-parity tests must fail when behaviorally relevant state is added without a checkpoint update.
- Prefix content is sensitive: process-local state stays outside logs; persisted complete-state hashes are research artifacts only, never payload-surrogate operational logging.

## Phase Completion Checklist

- Tasks 1–3 meet acceptance criteria and focused tests pass.
- Only `index.md` task checkboxes are updated after verification.
