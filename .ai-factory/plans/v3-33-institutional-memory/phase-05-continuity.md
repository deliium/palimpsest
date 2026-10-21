# Phase 5: Continuity without inherited minds

Plan: [index.md](index.md)
Tasks: 9–10
Depends on: Tasks 1–8

## Objective
Prove separately that owner state continues through supported runtime checkpoints and that external records survive occupants through existing objective persistence/replay.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|---|---|---|
| `src/simulation/run_control.py` | `AgentRuntimeCheckpoint` (584) | Optional owner ledgers with validation; not a new world snapshot. |
| `src/simulation/runner.py` | `export_runtime_checkpoint`, `apply_runtime_checkpoint`, `export_mediation_ledgers` | Existing continuation and results seams. |
| `src/simulation/new_agent_initialization.py` | `SUBJECTIVE_COPY_DENY_LIST`, species defaults registry | Newborns start without predecessor subjective knowledge. |
| `src/simulation/runner_models.py` | existing office-profile gates near 7160 and 9126 | New profile acceptance must be version-gated in initial config and admission composition. |
| `tests/unit/test_offices_checkpoints.py` | module contract and continuation cases | Explicitly runtime checkpoint parity, not durable restart. |
| `src/world/artifacts.py` | `InformationArtifact` author/parent/root/revision/integrity | Objective carrier survives author/occupant loss independently of learning. |
| `tests/unit/test_durable_record_resolution.py`, `tests/unit/test_durable_record_replay.py` | copy/damage/destruction and public replay cases | Existing physical persistence semantics to compose, not replace. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/simulation/run_control.py` | modify | Optional checkpoint ledger and ownership validation. |
| `src/simulation/agent_runtime.py` | modify | Prevalidated restore and export. |
| `src/simulation/runner.py` | modify | Runner restore checks, terminal ledger retention and export. |
| `src/simulation/runner_models.py` | modify | `SimulationRunnerResult.institutional_memory_ledgers`. |
| `src/simulation/new_agent_initialization.py` | modify | Subjective copy denials and explicit empty institutional-memory learner profile; existing profiles unchanged. |
| `src/simulation/__init__.py` | modify | Deliberate public profile constant export. |
| `tests/unit/test_runner_config_v53.py` | modify | New profile strict round-trip/dependency/legacy rejection cases. |
| `tests/unit/test_institutional_memory_checkpoints.py` | create | Restore, fork, fail-before-partial-apply cases. |
| `tests/unit/test_institutional_memory_continuity.py` | create | Engine carrier persistence and successor acquisition scenarios. |

## Task 9: Preserve supported owner checkpoints and blank-slate admission

### Intent
Continuation of the same owner is not transfer into a new occupant.

### Implementation Steps
1. Extend `AgentRuntimeCheckpoint` with `institutional_memory: object | None = None` and exact owner validation. Export the actual retained typed ledger, including channel inception, entries, ignores, provenance, use history, receipts and pruning counters.
2. In runtime and runner checkpoint application validate all incoming owner IDs, mode compatibility, typed ledgers, local links, counters and references for every runtime before any state is assigned. Disabled runtime plus non-None ledger is an error, not silently enabled state. Preserve existing earlier checkpoint fields/defaults.
3. Add runtime commit/restore fields and `SimulationRunner.export_institutional_memory_ledgers()` with deterministic agent order. Add result tuple and ordered exact-type/owner validation beside mediation ledgers. Retain departed/deceased owners' exported ledgers for detached provenance without making them available to living peers.
4. Add `institutional_memory`, `institutional_memory_entries`, `institutional_memory_ledgers` to subjective-copy denials and never copy them on newborn initialization. Keep every existing species profile byte/behavior-equivalent, including `species_default_offices_v1`.
5. Introduce explicit `SPECIES_DEFAULT_INSTITUTIONAL_MEMORY_V1 = "species_default_institutional_memory_v1"` and `_species_default_institutional_memory_v1(agent_id)` in `new_agent_initialization.py`. Add it to `_KNOWN_SPECIES_DEFAULT_IDS`, `_SPECIES_DEFAULTS` and deliberate exports. The pack enables exactly `office_succession_mode`, `institutional_memory_mode`, `artifact_interpretation_mode`, and `teaching_interaction_mode` as deterministic, leaving other modes at prior defaults. It constructs fresh default drives and empty subjective contents for that newborn; no office, channel, entry, identity binding or skill content is inherited. Artifact/teaching modes are abilities to interpret public input, not guaranteed access or learning.
6. Add v53-only profile gates in both `runner_models.py` initialization-validation paths alongside the existing office-profile special cases. Older schemas reject this profile with `institutional_memory_profile_requires_v53` even though the registry now recognizes its name. Existing lifecycle/new-agent initialization prerequisites still apply; do not add a root field or event/codec version. This explicit profile is the only new admission opt-in; merely claiming a role or choosing an old profile cannot enable the mode. Preserve v53's requirement for an enabled initial institutional-memory owner.
7. Test checkpoint continuation with the same run/owner and research fork copies preserving detachment and deterministic future receipts; successor identity is a different owner and starts empty. Applying predecessor state to successor fails. Separately admit a real new agent using the new profile and continue its runtime through recognition and actual content acquisition; pack construction alone is insufficient evidence.

### Required Interfaces and Contracts
This task covers the repository's existing in-process/runtime checkpoint abstraction, not a new durable subjective snapshot codec. Do not add SQL columns or claim full process-restart cognition persistence. Objective record bytes remain durable through existing event/snapshot codecs; Task 10 verifies that separate guarantee. Durable reconstruction of every legacy subjective ledger is outside this plan.

### Requirement Evidence
Original request — provenance across occupants without telepathy. `tests/unit/test_offices_checkpoints.py` explicitly distinguishes supported runtime continuation from durable restart.

### Error Handling and Logging
Owner/mode/reference errors fail before partial restore. Metadata logs expose run/owner IDs, counts and reason codes only. No serialization through `repr`, pickle or arbitrary object import.

### Tests
Populated runtime round trip, uninterrupted vs resumed next ticks, detached fork mutation, ignored/partial/pruned state, mixed owners, disabled/type/foreign-owner rejection with earlier runtime unchanged, terminal ledger retention, predecessor→successor rejection and newborn deny-list cases. New profile: canonical config round trip, v52 rejection, old-profile parity, fresh independent packs for two owners, and actual admitted learner initially empty then acquiring through its own runtime. Do not force office/knowledge content into the pack or require natural emergence in a short benchmark; use controlled public evidence in the mechanism test.

### Acceptance Criteria
Checkpoint continuation retains the same owner's learned information; no succession/admission operation transfers it to another owner.

### Verification
`uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_memory_checkpoints.py tests/unit/test_runner_config_v53.py tests/unit/test_offices_checkpoints.py tests/unit/test_mediation_checkpoints.py --cov=simulation --cov=agents.cognition --cov-report=term -q`

## Task 10: Prove external carrier survival, loss and later learning

### Intent
Persistent institutional information exists outside a particular occupant through actual records and through chains of teaching/transmission.

### Implementation Steps
1. Build an in-memory WorldEngine test harness using existing artifact/durable-record/repository configuration and normal action submissions. Occupant A inscribes known local claims; another actor copies/deposits/retrieves or annotates through actual commands. A dies or relinquishes a subjective role; retain physical record/native author provenance.
2. Export and rehydrate the world with the existing event/export/replay APIs used by durable-record tests, not a hand-built `ObservedArtifact`. Compare canonical owner observations before/after restore, including source revision/native lineage when that perception mode exposes it.
3. Initial successor B has its own recognition and an empty institutional ledger. Before access/delivery B has no information even after recognizing/claiming the role. On actual current observation+interpretation B creates a new local entry. B may retransmit/teach or write a new selected record; C creates another local entry from a later delivery/read, with declared versus native source provenance separated.
4. Cover inaccessible foreign-held/nonlocal carriers, damaged/truncated marks, lossy/wrong copies, amendments/conflicting editions, complete destruction/tombstones, ignored acquired information, and repository destruction with orphaned surviving members. Previously learned information remains personal and can survive record loss; a fresh successor cannot read hidden tombstone data.
5. Exercise both repository access dimensions explicitly: founder-list retrieval/mutation may fail for B while colocated marks remain observable under existing perception. Verify that no office/succession claim changes that admission result. Conversely, no visibility means no acquisition, whatever the repository or office name.
6. Use a separate teaching-only chain with no physical record: actual delivered `im_teach` A→B→C, A unavailable before final delivery. B can pass on only what B acquired; missing facts remain missing. No peer ledger access is available to the production update call.
7. Include the newly admitted profile-enabled successor in a real read/teaching test, distinguishing birth/admission tick, local role-recognition evidence, source-exposure tick, and first acquired entry. Do not manually assign an acquired ledger or replace the learner's update function. Old-profile newborns remain disabled as a separate negative control.

### Required Interfaces and Contracts
No production changes to `world._perception`, repository access, artifact damage or objective event fold. Existing physical codec/write-pair selection must accept the chosen feature combination; retain old versions unchanged. Tests must use actual public engine/export APIs, copying the setup pattern from relevant existing record tests rather than bypassing admission.

### Requirement Evidence
Index C5–C11 and original request examples. Persistent carrier survival ≠ process-restart preservation of every owner's subjective state.

### Error Handling and Logging
Normal action rejections remain structured reasons. Test assertions do not print full payloads or leak hidden content through production logs. Malformed source content yields partial/no uptake, never a recovery fetch.

### Tests
Add the scenarios above to `test_institutional_memory_continuity.py`; include a representative existing durable-record/repository fixture and unchanged replay observation window. Known-answer B/C fact subsets and source channels must be asserted, not merely ledger nonemptiness.

### Acceptance Criteria
At least one actual physical record survives A and replay, B learns only upon exposure, and C's later knowledge has a concrete carrier/delivery path. Loss, error and non-uptake remain possible.

### Verification
`uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_memory_continuity.py tests/unit/test_durable_record_resolution.py tests/unit/test_durable_record_perception.py tests/unit/test_knowledge_repository_custody.py --cov=world --cov=simulation --cov=agents.cognition --cov-report=term -q`

## Phase Risks and Mitigations
- An object checkpoint can hide missing persistence coverage. Mitigation: keep runtime and objective replay assertions separate and state the durable-subjective non-goal in docs.
- Physical damage does not remove artifact relations. Mitigation: factual body lives in marks only; tests assert no content recovery from lineage/metadata.

## Phase Completion Checklist
- Verify Tasks 9–10 and update index only.
