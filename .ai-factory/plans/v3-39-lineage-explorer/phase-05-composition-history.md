# Phase 5: Capture composition and historical discovery

Plan: [index.md](index.md)  
Tasks: 9–10  
Depends on: Tasks 1–8

## Objective
Provide a concrete supported producer for the artifacts and bounded snapshot/root discovery for consumers.

## Current-Code Evidence

| Path | Symbols / sections | Relevance |
|---|---|---|
| `src/research_runner/cli.py` | `_cmd_generational`, matrix execution composition | Trusted CLI, not HTTP, owns experiment execution options. |
| `src/research_runner/generational_composition.py` | Generational dependency composition | Outer layer can wire persistence and experiment services. |
| `src/experiments/generational_execution.py:70–97,119–178,233–278` | `GenerationalExecutionContext`, `execute_generational_assignment` | Actual runner/recorder installation, recipe configurator, archive completion and arm collection owner. |
| `src/experiments/composition.py` | Harvest conversion functions | Trusted detached cross-owner analysis composition. |
| `src/api/simulation_manager.py` | `owner_runtime_checkpoint` | In-process state is not a durable historical fallback. |

## Files to Change
Create `src/research_runner/lineage_composition.py`, `src/simulation/lineage_catalog.py`, `tests/unit/test_lineage_composition.py`, and `tests/unit/test_lineage_catalog.py`. Modify `src/research_runner/cli.py`, `src/experiments/generational_execution.py`, and `src/experiments/lineage_publication.py`. Existing `src/research_runner/generational_composition.py` supplies archival dependencies; do not add a redundant runner-construction path there.

## Task 9: Wire an opt-in trusted producer and analytical publication

### Intent / Implementation Steps
1. Add `--lineage-root`, `--lineage-cadence` (positive integer, default 1), `--lineage-max-publications` (default 1,000), and `--lineage-max-bytes` (default 268435456) to the existing `generational` command. Options other than the root require the root. Root absent means zero lineage extraction or files. Validate before run execution and pass typed options, never add fields to runner configuration.
2. `research_runner.lineage_composition` creates separate filesystem reader/publisher capabilities and a per-run installer for the neutral `simulation.lineage_capture.LineageCaptureSession`. Add optional `lineage_installer: Callable[[SimulationRunner], LineageCaptureSession] | None = None` to `GenerationalExecutionContext`; its installer type alias belongs to `experiments.lineage_publication`, while the session type is imported from simulation. Thread the field from `_cmd_generational` into the existing `execute_generational_assignment`, not a new loop. Invoke the installer after `SimulationRunner.from_config` returns and before the initial `runner.run()`, separately from the recipe configurator and cultural recorder. Do not overload `context.configurator`: its non-None branch suppresses the default generational arbiter. Preserve that branch's behavior and archive/factory/criterion dependencies. Root absent makes the installer None.
   Construct the complete session before binding its sink; the setter is the final installer action so a failed setup cannot leave a half-installed callback. Wrap optional runtime lineage setup in its own ordinary-exception warning boundary (`lineage_capture_setup_failed`) and continue scientific execution with lineage unavailable. Malformed explicit CLI option combinations remain preflight errors, while runtime root/lock/storage failure is observational. Do not let installer exceptions enter the outer scientific archive failure handler; propagate cancellation normally.
3. The runner sink publishes owner/objective families. After successful scientific completion, select the final fully captured boundary from session receipts. Obtain detailed mentorship inputs by paging the exact committed owner `mentorship` publications and reading their Task 1 typed metadata, through a bounded read session supplied by outer composition. Do not use `result.mentorship_audits`, which lacks content and lineage IDs, and do not query a live checkpoint as fallback. Merge retained historical entry records with their correct archived/observed status; no row may be relabeled as observed later than its source boundary.
   Practical-knowledge audits, narrative ledgers and institutional-decay ledgers can use the existing completed result only when their detailed source revision is valid at the chosen B. Extract institution temporal rows with `institution_decay_rows_from_ledgers`. If capture stopped before the final result and a B-valid source revision is unavailable, mark that analytical family unavailable instead of backdating the final state. Bound input row counts before graph construction; keep pruning/uncaptured history explicit. Analytical mentorship/knowledge/technology/narrative/institution publication remains trusted, detached and outside cognition/query paths.
4. Preserve source run ID and capture baseline; scope namespaces keep analytical publications separate from subjective publications. Final analytical results are not backdated to intermediate boundaries. Reject simultaneous writers to a run/scope and conflicting publication identities.
5. Report capture health in an adjacent `lineage-capture-status-v1` document and CLI metadata summary without changing runner-result serialization or process exit code for an otherwise successful simulation. A failed requested capture is clearly warned and never described as a complete export.
6. Do not implement automatic retroactive subjective backfill from replay, metric totals, `owner_runtime_checkpoint`, or sealed archives. Programmatic publishers can ingest only detailed, versioned detached sources with a declared original boundary. No general untrusted artifact import endpoint.
7. In `execute_generational_assignment`, keep best-effort lineage final publication/status writing outside the scientific archive completion/failure decision. Run it after `session.write_completion(result)` for successful scientific runs and before returning the collected arm. Catch ordinary lineage export/read/write errors into capture-health warnings; never let them enter the enclosing generational failure writer, change result/exit code, suppress the recipe arbiter or replace a valid scientific completion. If the scientific run failed, retain previously committed lineage snapshots with their finalized boundary/coverage, but do not label analytical completion successful. Propagate cancellation; do not fabricate a completed lineage status.

### Required Interfaces and Contracts
`create_lineage_capture(options, reader, publisher)` returns a session/installer over separate read and publish ports; its neutral sink is installed through the runner setter. `publish_completed_lineage(harvest, receipts, reader, options, publisher)` is the separate analytical stage. The context field is optional Python composition, not runner JSON or an archival schema field. External factories can install the same neutral sink; API merely setting the read root does not start capture or import experiments. Existing CLI, recipe/arbiter and scientific archive behavior remains unchanged without these options. Read/publish quota failures are explicit; analytical publication has no reserved exemption from the cumulative run quota.

### Error Handling and Logging
Invalid combinations fail preflight with safe codes. Capture failure logs warnings; scientific runner failure behavior remains existing behavior. Log run IDs, enabled state, counts/caps and reason codes, not root paths or payloads.

### Tests / Acceptance / Verification
`test_lineage_composition.py`: invoke the actual `build_parser`/`_cmd_generational` dispatch using public `generational_runner_scenario(seed=23, max_ticks=4)` and condition `bl-generational-unassisted`, serialized with `encode_runner_config`. Follow `tests/unit/test_generational_cli.py::_write_inputs` and `test_generational_cli_runs_and_writes_archive` for the plain-generational recipe, `--code-revision abc123`, source-clean assertion and in-memory run; do not import that private test helper or replace production execution with a spy. Keep the real `execute_generational_assignment`, runner, installer, publisher and filesystem reader; inject only external resources. Assert parsed flags reach the new optional context field and published artifacts can be read by a fresh service. Exercise custom/default configurator/arbiter branches with the existing `test_generational_execution.py` assignment pattern, plus coexistence with cultural capture. Audit-only mentorship input must not be treated as a detailed chain; exact captured entry metadata must produce one. Also cover invalid flags, root-absent no-op, missing institution source, source-version mismatch, capture/analytical failure after valid scientific completion, no lineage-caused `failure.json`, cap exhaustion across restarts, fork namespace and unchanged runner result/CLI success status. Task 15 separately exercises the BM comparison scenario.

Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_lineage_composition.py tests/unit/test_generational_cli.py tests/unit/test_generational_execution.py --cov=simulation --cov=experiments --cov=persistence --cov-report=term-missing -q` and `uv run --frozen --python 3.12.14 palimpsest-matrix generational --help`. Acceptance: the actual CLI-to-execution path installs capture without suppressing existing recipe behavior; fresh readers do not depend on process-local state.

## Task 10: Resolve publications, catalogue roots, and retain honest coverage

### Intent / Implementation Steps
1. Implement `LineageCatalogService(reader)` with `families(run_id)`, `snapshots(scope, catalogue_ref, after, limit)`, and `roots(scope, snapshot, after, limit, native_kind=None, native_id=None)`. Every call opens or reuses the Task 2 budgeted read session. A run is known when its configured-root committed control/descriptor validates; SQL membership is not required for filesystem-generated experiments. No directory enumeration across unrelated runs.
2. Family catalogue is a fixed eight-family descriptor with available evidence classes, owner requirement, supported directions, hard limits, captured boundary and coverage/health. Do not enumerate owners or subjective family activation under objective-only authorization; API filtering occurs before reading restricted descriptors.
3. Root discovery returns ID/reference/type/status only. `native_id` requires the matching closed `native_kind`; reject either filter supplied alone. Exact lookup uses `lookup_nodes` and the Task 7 index, returning bounded qualified matches without scanning the unfiltered catalogue. Same native IDs in different analytical owners remain separate matches. Clients resolve Alice's stable `AgentId` through their existing roster; no natural-language search or name-based identity inference.
4. Omitted boundary pins the latest complete publication for that exact scope. Explicit B needs that exact snapshot. Missing metadata, disabled channel, capture not requested, skipped cadence and corruption have distinct codes/availability. No transparent replay/export/repair fallback in a GET.
5. Carry the original evidence window, baseline, pruning and unresolved ancestry into every result. A snapshot can be available and partial simultaneously. A known root with no edges is valid empty ancestry; a proven absent root is 404, while unavailable sources cannot prove absence.

### Required Interfaces and Contracts
Discovery pagination uses pinned immutable catalogue generations or snapshot-qualified node keys. Snapshot-catalogue continuation pins `run_commit_ref` and the scope catalogue generation, not a root or one graph publication. Node-catalogue continuation pins the snapshot and full native-kind/ID filter fingerprint. Page size 1–200; all discovery/control/index reads share the same 128-file/8-MiB request budget. Historical browsing is over captured finalized boundaries, not arbitrary inferred past beliefs. Owner-scoped APIs never leak another owner's root existence/counts.

### Error Handling and Logging
Unknown run or proven-absent root: `lineage_run_not_found`/`lineage_root_not_found`. Capture absent/disabled: valid unavailable descriptors, not fabricated zero. Corruption/storage outage: typed errors mapped in Task 14. No root labels, raw query values or cursor bodies in logs.

### Tests / Acceptance / Verification
`test_lineage_catalog.py`: exact versus latest boundary, skipped B, B=0, missing versus empty root, repeated native IDs across analytical owners, native-kind/ID filter pairing, direct lookup read counts independent of unrelated catalogue size, snapshot catalogue continuation after another publication, unknown run without scanning, shared control/index byte/read accounting, capture health versus immutable historical coverage, and no auto-build/repair callbacks. Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_lineage_catalog.py --cov=simulation --cov=persistence --cov-report=term-missing -q`. Acceptance: discovery is bounded and snapshot-stable without guessing identities or history.

## Phase Risks and Mitigations
- Operators expect API root setting to produce data: explicit reader-only setting and concrete producer command.
- Filesystem research runs lack SQL rows: validate artifact identity directly, do not reject valid runs solely for absent SQL membership.

## Phase Completion Checklist
- Producer, discovery and exact historical semantics verified; update only `index.md`.
