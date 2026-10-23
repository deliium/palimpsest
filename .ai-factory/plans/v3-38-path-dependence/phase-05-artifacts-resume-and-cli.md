# Phase 5: Verifiable lineage artifacts, restart policy and CLI

Plan: [index.md](index.md)
Tasks: 13–15
Depends on: Tasks 1–12

## Objective

Expose a usable research workflow whose sealed artifacts bind every result to a verified prefix, intervention, assignment and execution identity. Restart must never pretend objective replay reconstructs subjective experience.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|---|---|---|
| `src/experiments/generational_artifacts.py` | `GenerationalRunArtifactStore`, `write_completion` | Atomic, fsync-backed strict artifact patterns. |
| `src/experiments/generational_archive.py` | `open_generational_archive`, `build_manifest_payload` | Existing manifest exact keysets cannot be silently widened. |
| `src/experiments/generational_adoption.py` | `verify_completed_archive` | Adopt only verified completed results. |
| `src/experiments/cultural_metric_artifacts.py` | `read_cultural_pair`, `verify_cultural_pair` | Bounded canonical readers and digest checks. |
| `src/experiments/matrix_runner.py` | `MatrixBatchRunner` resume and `durable_origin_rerun_unsupported` | Existing matrix resume is not subjective restart. |
| `src/research_runner/generational_composition.py` | `PostgresHistoricalBoundaryReader` | Actual journal/snapshot-backed reference, unlike synthetic unit reader. |
| `src/research_runner/cli.py` | `build_parser`, `_cmd_run`, `_cmd_resume`, `_cmd_generational` | CLI surface and exit/error conventions. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/experiments/path_dependence_artifacts.py` | create | Strict sibling codecs, atomic store, hash-bound completion. |
| `src/experiments/path_dependence_resume.py` | create | Verified adoption and deterministic prefix reconstruction. |
| `src/research_runner/path_dependence_reconstruction.py` | create in Task 14 | Isolated concrete public-port repositories for deterministic parent reconstruction; not test helpers. |
| `src/experiments/path_dependence_runner.py` | modify | Artifact lifecycle/restart integration. |
| `src/research_runner/path_dependence_composition.py` | create | Concrete repository/session/factory composition, detached aggregation loader. |
| `src/research_runner/cli.py` | modify | `path-dependence` commands. |
| `src/experiments/coordinator.py`, `src/experiments/matrix_runner.py`, `src/experiments/matrix_expand.py` | modify / exercise | Grouped-execution rejection paths from Task 8; verify CLI cannot bypass them. |
| `tests/unit/test_path_dependence_artifacts.py`, `tests/unit/test_path_dependence_resume.py`, `tests/unit/test_path_dependence_cli.py` | create | Tampering, restarts and CLI contracts. |

## Task 13: Seal explicit intervention lineage and outcome artifacts

### Intent

Make lineage tamper-evident and scientifically interpretable without changing legacy generational manifests or SQL lineage schemas.

### Implementation Steps

1. Add strict bounded codecs for the five sibling schemas named in Task 1. Store under `<artifact-root>/<ensemble-id>/ensemble.json`, `prefixes/<parent-id>/<attempt-id>/fork-<F>/prefix.json`, and `branches/<child-id>/<attempt-id>/preparation.json`, `branch.json`, `outcomes.json`, `completion.json` or `failure.json`; store comparisons under `comparisons/<comparison-id>.json`. Canonical decimal F is part of both the path and artifact identity; two boundaries of one parent never overwrite each other. All path components are validated stable filesystem-safe IDs. Branch preparation, final branch record, completion and failure use discriminated `path-dependence-branch-v1` documents with `kind='preparation'|'result'|'completion'|'failure'`, each with a separate exact keyset. Prefix documents use `path-dependence-prefix-v1` and `kind='eligible'|'ineligible'`; an unsealed/missing prefix is not a completed eligibility assessment. Completion binds the branch and outcomes digests plus objective terminal head/result references. No generic arbitrary path references or unversioned key widening.
2. Ensemble document seals full spec, config fingerprint, source revision/artifact digest, treatment-blind slot table, assignment algorithm/seed, provider restrictions, selectors/windows and planned block membership before execution. Prefix document binds actual F/revision, objective head/bootstrap/snapshot hashes, complete-state digest/version, source/seed/provider identity, optional common setup schedule and eligibility result. It is a prefix-source artifact, not a fake completed generational run.
3. Branch document binds root/prefix references, child run/attempt IDs, all requested interventions, immutable slot assignment, requested/effective/committed treatment ledger, pre-treatment state witness, seed-channel manifests/alignment, actual stop reason/terminal progress, exact outcome evidence refs and coverage. Outcomes bind all domain rows and bounded evidence chunks. Comparison binds spec and ordered completed-input digests plus formula/selector/numerical versions.
4. Use canonical UTF-8 sorted JSON with finite numbers only, exact keysets, bounded depth/bytes/counts, duplicate-key rejection, content digests and atomic tempfile-write/fsync/rename/directory-fsync. Reject symlinks, absolute references, `..`, conflicting rewrites and incomplete seals. Never overwrite a completed attempt; identical re-publication is idempotent.
5. Loader independently derives EXPECTED ensemble/spec/parent/child identities from the root spec and slot table, then checks every linked artifact against them. Never accept a sidecar's self-reported fingerprint as its own expected value. Cross-check objective completion through actual journal/replay ports and digest-bound result references, not a synthetic boundary reader.
6. Existing generational archives may remain sibling references if produced, but do not change `generational-run-manifest-v1` keys or make `verify_completed_archive` accept new recipes implicitly. The new store owns the path-dependence prefix/branch recipe and completion rules. SQL `BranchLineage` remains unchanged; new protocol lineage lives explicitly in these research artifacts and is not falsely represented as a legacy intervention kind.
7. Freeze the write-state protocol: immutable ensemble/slot assignment first; run parent to a coherent F and seal eligible/ineligible prefix; for each eligible slot atomically publish preparation with expected original child RunId and prefix digest BEFORE materializing that child; execute; publish evidence chunks, outcomes and result; publish completion LAST after all objective verification. On a technical failure publish failure with last durable tick/stage/committed status, not completion. If failure publication itself crashes, the original preparation plus actual repository existence classifies the slot as partial. Every transition is recoverable from sealed files and repository state; no mutable root status is trusted as proof. Completion and technical failure are mutually exclusive, including `runner_stop_is_failure` reasons such as finalization or historical-artifact failure; adopter rechecks that classifier. A genuine early scientific stop may complete with explicit censored requested endpoints.
8. Path/decode verification distinguishes missing publication from corruption: missing unsealed inputs are incomplete; existing malformed/conflicting seals are hard errors. An absent original child run can still launch once after prefix reconstruction; an existing unsealed child run is partial and non-restartable in v1. The loader validates exactly the predeclared scientific RunId, never a substituted successful rerun. Keep actual attempt/source metadata separate from the scientific state digest.

### Required Interfaces and Contracts

`PathDependenceArtifactStore`, `verify_path_dependence_branch(expected, references, repositories) -> VerifiedPathDependenceBranch`, `load_path_dependence_comparison_inputs(...)`. Integrity digests belong in restricted research artifacts; payload digests must not be logged as content surrogates. Unknown/partial outcomes can coexist with verified objective completion, but never an unverified objective run.

### Requirement Evidence

User explicit intervention lineage; strict schema compatibility and append-only history; V3-37 artifact-verification patterns.

### Error Handling and Logging

`artifact_identity_mismatch`, `artifact_hash_mismatch`, `artifact_path_unsafe`, `artifact_conflict`, `branch_unsealed`, `objective_completion_unverified`. INFO artifact-kind/status/count, ERROR safe code. Do not log raw paths containing credentials, raw JSON, content or digest surrogates.

### Tests

`test_path_dependence_artifacts.py`: golden round trip for every discriminated kind; two F values under one parent/attempt with independent prefix paths and digests; mutation of each identity/parent/F/schedule/window/digest; wrong root expected fingerprint; parent-child substitutions; substituted child RunId; preparation before objective creation; interrupted writes at every seal boundary; no completion for any `runner_stop_is_failure` result; conflicting failure/completion rejected; early scientific stop with censored endpoints; incomplete vs corrupt seal; changed objective terminal hash; duplicate keys, NaN/Infinity, huge/deep input; symlink/path escapes; identical vs conflicting re-publication; legacy archives still decode exactly.

### Acceptance Criteria

No branch or outcome can be transplanted into a different ensemble/prefix/arm without rejection, and comparison reads no unsealed/unverified branch.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_path_dependence_artifacts.py tests/unit/test_cultural_metric_artifacts.py tests/unit/test_generational_matrix_adoption.py -q`

## Task 14: Resume by verified adoption or deterministic reconstruction

### Intent

Recover expensive experiments honestly while keeping durable subjective restart out of scope.

### Implementation Steps

1. For a fully sealed valid child, adopt its exact completion/evidence without rerunning or reopening it. Validate root spec, source, provider, assignment, prefix and objective lineage first. Changed spec/source/provider is a conflict, not a reason to quietly rerun in place.
2. For a planned child whose ORIGINAL scientific RunId does not exist in objective repositories, a verified eligible sealed prefix permits reconstructing the parent from tick zero using the same deterministic fake/provider/config/setup/identity in a NEW reconstruction attempt and isolated repositories. Re-execute normal cognition to F; objective-only event replay does not recreate owner stores. Compare the rebuilt complete-state digest and original parent prefix commits at every stored F. Only exact match permits use of the new process-local checkpoint and launch of that never-created child. Missing/corrupt prefix seals, unsupported state or unavailable original history block the group; do not infer an expected subjective digest from objective replay or certify a new F after the original parent crashed before sealing it.
3. Preserve the original scientific parent reference in lineage; record `reconstructed_from_prefix` and new attempt provenance. Never append duplicate prefix commits to the original parent run. Existing durable parent evidence stays read-only. Concrete composition provides an isolated in-memory reconstruction journal or isolated attempt namespace, never an overwrite of the original durable origin.
4. If the original child run exists without a verified completion, classify the planned slot `failed_partial` / `durable_child_partial`. Do not append to it, delete/reset it, or substitute a fresh RunId. Preserve its preparation/failure references and count its outcomes as missing. Resume may still execute other never-created planned slots. The only automatic adoption is exact existing completion; a new-identity rerun requires an explicitly new ensemble and cannot fill this slot in an existing comparison. Rejected/missed Give in a valid completed branch is scientific exposure evidence, not a technical retry trigger.
5. If reconstruction fails, stochastic/provider support is absent or digest differs, stop the affected group with `prefix_reconstruction_mismatch`; retain other verified branches for explicitly incomplete/descriptive inspection. Comparison may report qualified complete-pair estimates with failed/missing counts but must never claim the entire requested design completed. No silent seed replacement or rerun-until-success, no automatic technical retry of an existing durable child, and no success-selection across attempts.
6. Resume aggregation can run entirely from completed artifacts and read-only objective verification; it must not construct live providers or rerun capture. Respect legacy sealed archives and do not infer missing capture from replay.
7. Introduce concrete isolated repositories in `src/research_runner/path_dependence_reconstruction.py` NOW, rather than leaving Task 14 dependent on Task 15's later implementation. Implement the existing run/journal/snapshot public ports needed by `PersistentSimulationService` and `ReplayService`, with real commit/hash/snapshot semantics, no shared mutable maps with production adapters and no import of `tests.*`. They are process-local reconstruction adapters only; original durable history is read-only, and logical parent RunId/config remain original. Inject via the existing context ports. A callback-based store supplied from experiments must not reach into concrete repository internals.

### Required Interfaces and Contracts

`classify_path_dependence_resume(...) -> adopt_completed/reconstruct_for_uncreated_slot/failed_partial/blocked` and `reconstruct_prefix(...)`. The classification table is exhaustive: valid completion→adopt; sealed eligible prefix + absent child run→reconstruct/launch once; existing child run without valid completion→failed_partial; corrupt artifacts or missing expected prefix→blocked; sealed ineligible prefix→retain ineligible without reconstruction. Durable world continuation remains existing infrastructure; complete subjective state is process-local and regenerated deterministically only for unused slots. Initial fake-only restriction makes this promise testable.

### Requirement Evidence

Current generational objective-inspection-not-subjective-restart contract; user reproducibility/lineage; explicit independent-block membership policy.

### Error Handling and Logging

`resume_spec_conflict`, `prefix_reconstruction_mismatch`, `durable_child_partial`, `prefix_unsealed`, `capture_unrecoverable`. INFO adopted/reconstructed/never-created/failed-partial counts; WARN partial/missing reason; ERROR safe stage/code. Partial artifacts stay available but unsealed; no deletion/reset of user data, no new scientific child IDs allocated during resume.

### Tests

`test_path_dependence_resume.py`: completed adoption without provider calls; crash before prefix seal blocks; after prefix seal and before child creation reconstructs for the exact original RunId; preparation present but no child exists permits one launch; any run creation during fork materialization makes the unsealed child failed-partial; after action commit and before outcome/completion writes remains failed-partial; other unused slots can proceed; same logical parent reconstructed in isolation with real-contract repositories and equal runtime idempotency/coverage digest; altered hidden owner state fails digest; substitution of a new child ID rejected; no retry on rejected Give; no double-count or best-attempt selection; aggregation never repairs missing cultural evidence.

### Acceptance Criteria

Restarted work adopts verified completion or proves equivalent prefix state before launching a never-created slot; no incomplete durable child is appended or replaced as if its subjective state and scientific identity survived process loss.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_path_dependence_resume.py tests/unit/test_generational_matrix_adoption.py -q`

## Task 15: Add researcher CLI composition and comparison commands

### Intent

Make ensemble execution, inspection and statistics reproducible without a new HTTP route or changes to the read-only clients.

### Implementation Steps

1. Extend parser with `palimpsest-matrix path-dependence run --spec <file> --artifact-root <dir>`, `resume --ensemble <dir>`, `inspect --ensemble <dir>`, and `compare --ensemble <dir>`. Spec contains seeds/schedules/windows; no ad-hoc post-hoc outcome overrides in compare. `inspect` and `compare` are read-only except atomic comparison artifact publication by compare.
2. `path_dependence_composition.py` creates PostgreSQL run/journal/snapshot repositories and branch materialization/replay ports using existing adapters and resource lifespans, but explicitly uses fork-capable in-memory owner services. Bind actual objective boundary references. Inject Task 14's isolated reconstruction repository implementations from `src/research_runner/path_dependence_reconstruction.py`; they implement existing public ports and are not imported by experiments/domain. No database state is copied through test helpers in production. CLI `resume` clearly reports failed-partial slots, never allocates replacement RunIds and only starts previously uncreated children after exact prefix reconstruction.
3. Validate DSN/settings through existing `PALIMPSEST_` infrastructure, require initialized disposable database only in tests, and keep credentials out of args/output/logs. Reject unsupported provider/adapters, missing objective repositories, unsafe artifact roots and excess branch budgets before execution.
4. `run/resume` print bounded ensemble IDs, counts, statuses and artifact locations. `compare` prints each declared contrast's independent n, descriptive mean/pointwise interval status, missing counts, coarse stream alignment and explicit no-causal-claim warning. Single seed emits “illustrative/descriptive; no confidence interval.” Do not print full owner records.
5. `inspect` traverses root→prefix→branch→requested/committed intervention→outcomes/comparison and reports eligibility/attempt/source/channel provenance. It cannot advance ticks. CLI exit codes follow existing parser convention; technical execution/verification failure is nonzero; valid descriptive singleton comparison succeeds with warning; all-ineligible prefixes succeed as a completed eligibility assessment with zero usable blocks and explicit status.
6. Connect `path-dependence` discovery to Task 8's separate typed grouped registry. Keep generic matrix `run/resume/aggregate` semantics unchanged. Exercise `require_independent_execution` in coordinator, matrix base resolution and batch entry before assignments, `store.create`, provider construction or skip/adoption paths. Reject attempts to route grouped historical-contingency catalog records or embedded grouped-identity configs through independent cell execution with `grouped_execution_required`, rather than silently simulating fresh histories. Do not change standard `ExperimentDefinition` shape or add BN to the independent-cell off-gate allowlist.

### Required Interfaces and Contracts

New path `src/research_runner/path_dependence_reconstruction.py` is introduced for concrete isolated reconstruction repositories and included in tests. No new runtime dependency, API import, SQL migration, `/v2` route, observer semantic or Godot/Svelte code. Retain `prepare_parallel=False`.

### Requirement Evidence

User statistical comparison/lineage needs; current CLI composition and no-HTTP research runner architecture.

### Error Handling and Logging

Map typed safe errors to existing CLI stderr conventions. INFO stage/counts, DEBUG safe timings; no DSNs, raw exceptions, schedules, memory payloads or digest surrogates. Graceful interruption closes child resources and leaves no false completion seal.

### Tests

`test_path_dependence_cli.py`: all help/parser paths; config/provider/database preflight; run→inspect→compare→resume fixture; singleton warning; all-ineligible result; tampered ensemble; subprocess failure code; no HTTP import; no credentials in stdout/stderr; fake repositories for unit tests and actual PostgreSQL adapter coverage in Phase 6.

### Acceptance Criteria

CLI produces an auditable lineage tree and correct repeated-seed statistics through production composition, with unsupported usage failing clearly.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_path_dependence_cli.py -q`

`uv run --frozen --python 3.12.14 palimpsest-matrix path-dependence --help`

## Phase Risks and Mitigations

- A hash-bound sibling may not be verified by old tools: historical-contingency loader owns full validation and does not broaden old decoder semantics.
- New-RunId retry would alter the scientific execution: v1 therefore never substitutes a partially written child. Failed/missing slots and complete-pair attrition remain explicit.

## Phase Completion Checklist

- Tasks 13–15 pass, including interruption/adoption tests.
- Progress only in `index.md`.
