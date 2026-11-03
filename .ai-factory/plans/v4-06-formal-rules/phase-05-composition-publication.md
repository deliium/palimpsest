# Phase 5: Composition and Durable Publication

Plan: [index.md](index.md)
Tasks: 15-16
Depends on: Phase 3 / Task 12, Phase 4 / Task 14, and Phase 5 / Task 15

## Objective

Compose a completed run's detached formal-rule analysis into a canonical
`formal-rule-snapshot-v1`, publish it atomically through an opt-in filesystem
store, and expose the producer through the existing research CLI. Publication
must never change the scientific result.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/organization_harvest.py` | harvest 59-138 | Reads exported ledgers from `SimulationRunnerResult`. |
| `src/experiments/organization_publication.py` | result 118; draft helpers 139-800; build 801; finalize 1016; publish 1086; receipt 1104 | Composition/finalization/receipt pattern. |
| `src/research_runner/organization_composition.py` | options 34-61; publish 65-135 | Opt-in, post-completion, receipt-isolated pattern. |
| `src/persistence/organization_filesystem.py` | store schema 39; atomic write 70-105; publisher 120+; quotas | Atomic single-commit store pattern. |
| `src/research_runner/cli.py` | options read 955-962; publish block 1228-1258; argparse 1426-1428 | CLI integration point. |
| `src/infrastructure/settings.py` | roots 218-222; validators 250-270; safe summary 584 | Root and secret-safe settings pattern. |
| `src/simulation/runner_models.py` | `RunnerStopReasonCode`; `runner_stop_is_failure` | Completion gate for publication. |
| `tests/unit/test_organization_agency_publication.py` | publication/receipt tests | Test precedent. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/formal_rule_harvest.py` | create | Completed-run harvest. |
| `src/experiments/formal_rule_publication.py` | create | Snapshot composition, finalize, publish, receipt. |
| `src/research_runner/formal_rule_composition.py` | create | Opt-in producer options and publish function. |
| `src/research_runner/cli.py` | modify | Read options, publish after completion, write receipt. |
| `src/persistence/formal_rule_filesystem.py` | create | Atomic read/publication store with quotas. |
| `src/infrastructure/settings.py` | modify | `formal_rule_root`, cursor key field, validators, safe summary. |
| `tests/unit/test_formal_rule_publication.py` | create | Composition, receipts, failure isolation. |
| `tests/unit/test_formal_rule_filesystem.py` | create | Atomicity, quotas, duplicates, read. |
| `tests/unit/test_formal_rule_settings.py` | create | Root/secret defaults, blank root, short-secret rejection, safe summary. |
| `tests/unit/test_formal_rule_cli.py` | create | CLI flags and receipt output. |

## Task 15: Compose completed-run snapshots and receipts

### Intent

Turn detached analysis into one immutable publication value and a metadata-only
receipt, without importing API or persistence into experiments.

### Implementation Steps

1. Create `src/experiments/formal_rule_harvest.py`:
   - `FormalRuleHarvest(run_id, input_revision, generated_tick, rows, windows,
     assignment, analysis, layers, summary, coverage, truncation)`.
   - `build_completed_run_formal_rule_harvest(runner_result, *, run_id,
     input_revision, generated_tick)`:
     - read `runner_result.formal_rule_ledgers`;
     - call `harvest_formal_rule_rows`, `build_formal_rule_windows`,
       `detect_formal_rule_candidates`, `assign_formal_rule_identities`,
       `derive_formal_rule_lineage`, `project_formal_rule_layers`,
       `summarize_formal_rules`;
     - return a harvest with explicit coverage/truncation.
2. Create `src/experiments/formal_rule_publication.py`:
   - `FormalRuleHarvestResult(snapshot, publication_id, snapshot_digest,
     candidate_count, rule_count, version_count, coverage, receipt)`.
   - `build_formal_rule_harvest_result(harvest)`:
     - map detached rows to `FormalRuleCandidateRecord`,
       `FormalRuleRecord`, `FormalRuleVersionRecord`,
       `FormalRuleObjectiveRow`, `FormalRuleWindowRecord`,
       `FormalRuleLineageEdgeRecord`;
     - cap candidates/rules/versions deterministically and set coverage
       `partial` plus a truncation reason; set `provenance_code` to `empty`,
       `ok`, `partial`, or `truncated` accordingly;
     - build `FormalRuleSnapshotRef` and `FormalRuleSnapshot`;
     - call `_finalize`.
   - `_finalize(snapshot)` sets `publication_id=""`, computes the `frule-pub-`
     id, replaces the snapshot with the published id, encodes, decodes, compares
     bytes, computes the derived digest, and returns the result. Any mismatch
     raises `FormalRuleArtifactError("formal_rule_digest_mismatch")`.
   - `publish_formal_rule_snapshot(built, publisher)` calls the injected
     publication port exactly once.
   - `formal_rule_publication_document(built)` returns a safe receipt:
     `status`, `schema_version`, `policy_version`, `candidate_count`,
     `rule_count`, `version_count`, `coverage`, `publication_id`, and optionally
     `snapshot_digest`; no ids beyond the publication id, no owner ids, no scope
     digests, no action tokens.
3. Do not import `api`, `persistence`, `research_runner`, or `simulation`
   runtime/engine. Only public `simulation.formal_rule_*` contracts and
   `analysis` modules are allowed.
4. Publication is opt-in: an absent root returns `disabled` before any harvest.
5. Publication is post-completion: a `None` or failure stop reason returns
   `unavailable` with `formal_rule_run_incomplete` and no artifact.
6. A composition/storage failure returns `failed` with a safe code and leaves
   the runner result unchanged.
7. Add `tests/unit/test_formal_rule_publication.py`:
   - `test_empty_ledgers_publish_an_empty_v1_snapshot`
   - `test_snapshot_round_trip_and_digest`
   - `test_candidate_rule_and_version_caps_set_partial_coverage`
   - `test_receipt_is_metadata_only`
   - `test_disabled_root_returns_disabled`
   - `test_incomplete_run_returns_unavailable`
   - `test_failure_changes_only_the_receipt`
   - `test_publication_does_not_import_api_or_persistence`

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class FormalRuleHarvestResult:
    snapshot: FormalRuleSnapshot
    publication_id: str
    snapshot_digest: str
    candidate_count: int
    rule_count: int
    version_count: int
    coverage: FormalRuleCoverage
    receipt: Mapping[str, object]

def build_completed_run_formal_rule_harvest(runner_result: object, *, run_id: str, input_revision: str, generated_tick: int) -> FormalRuleHarvest: ...
def build_formal_rule_harvest_result(harvest: FormalRuleHarvest) -> FormalRuleHarvestResult: ...
def publish_formal_rule_snapshot(built: FormalRuleHarvestResult, publisher: FormalRulePublicationPort) -> None: ...
def formal_rule_publication_document(built: FormalRuleHarvestResult) -> dict[str, object]: ...
```

- The snapshot is immutable after finalization.
- A receipt never contains owner-local ids, rule ids, scope digests, action
  tokens, artifact ids, or claim bodies.
- Truncation is explicit and never a silent drop.
- An empty run publishes a valid empty snapshot, not `absent`.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "analysis is read-only" and "V3-39/V4-02/V4-03
  publication seams".
- `experiments/organization_harvest.py` 59-138.
- `experiments/organization_publication.py` 118-1104.
- `simulation/runner_models.py` stop-reason helpers.

### Error Handling and Logging

- Digest mismatch: `formal_rule_digest_mismatch`.
- Size overflow: `formal_rule_size_limit`.
- Duplicate id: `formal_rule_publication_exists`.
- Incomplete run: `formal_rule_run_incomplete`.
- Storage failure: `formal_rule_publication_failed`.
- INFO: `formal_rule_publication_built candidates=%s rules=%s versions=%s`.
- WARN: `formal_rule_publication_failed reason=%s` with the safe code only.
- Never log ids, digests, anchors, or receipt bodies.

### Tests

- `uv run pytest tests/unit/test_formal_rule_publication.py -q`

### Acceptance Criteria

- A completed run composes exactly one canonical snapshot.
- An incomplete/failed run produces no artifact and an `unavailable` receipt.
- A storage/composition failure changes only the receipt.

### Verification

- `uv run pytest tests/unit/test_formal_rule_publication.py -q`
- `uv run lint-imports`

## Task 16: Add the atomic filesystem store and CLI producer

### Intent

Persist publications append-only with one atomic commit point and expose the
producer through the existing research CLI without changing scientific status.

### Implementation Steps

1. Create `src/persistence/formal_rule_filesystem.py`:
   - `_STORE_SCHEMA = "formal-rule-store-v1"`.
   - `FilesystemFormalRulePublisher` and `FilesystemFormalRuleReader`
     implementing the Task 14 ports.
   - `create_formal_rule_publisher(root, *, max_publications=16,
     max_artifact_bytes=8 * 1024 * 1024)` and
     `create_formal_rule_reader(root)` returning `None` for an unset root.
   - Atomic write via a temporary file, `fsync`, `os.replace`, and directory
     `fsync`, mirroring the organization store.
   - Single `state.json` commit point plus immutable per-publication payloads;
     no partial visibility.
   - Append-only: an existing publication id with different bytes raises
     `formal_rule_publication_exists` and leaves the existing artifact
     untouched.
   - Quotas: max publications, max artifact bytes, cumulative bytes; reject
     with `formal_rule_size_limit`.
   - Reader validates schema/digest and serves summary/candidates/candidate/
     rules/versions/lineage through the ports.
   - Reject path traversal and unsafe run/publication tokens with
     `formal_rule_invalid_value`.
2. Create `src/research_runner/formal_rule_composition.py`:
   - `FormalRuleProducerOptions(root, max_publications=16,
     max_artifact_bytes=8 * 1024 * 1024)`.
   - `producer_options_from_args(args)` reading `formal_rule_root`,
     `formal_rule_max_publications`, `formal_rule_max_bytes`.
   - `publish_formal_rule_harvest(runner_result, *, run_id, input_revision,
     generated_tick, options)`:
     - disabled root → `{"status": "disabled", "reason_code": "formal_rule_disabled"}`;
     - failed/incomplete stop → `unavailable`;
     - harvest/compose/publish in a guarded block;
     - `FormalRuleArtifactError` → `failed` with `exc.code`;
     - unexpected `ValueError`/`OSError` → `failed` with
       `formal_rule_publication_failed`;
     - success receipt from `formal_rule_publication_document`.
3. `src/research_runner/cli.py`:
   - read options next to the organization options at 955-962;
   - after the organization publication block, publish formal-rule harvest when
     enabled;
   - write `formal-rule-publication-<run_id>.json` under `args.artifact_root`;
   - print `formal_rule_publication_status`, `..._reason`, and
     `..._publication_id` when present.
   - A receipt-write `OSError` logs WARN and does not fail the run.
4. Argparse (near 1426-1428):
   - `--formal-rule-root` default `None`
   - `--formal-rule-max-publications` type `int` default `16`
   - `--formal-rule-max-bytes` type `int` default `8_388_608`
5. `src/infrastructure/settings.py`:
   - `formal_rule_root: Path | None = None`
   - `formal_rule_cursor_key: SecretStr | None = Field(default=None, repr=False)`
   - add `formal_rule_root` to `empty_presentation_root_is_unset`
   - add a `validate_formal_rule_cursor_key` field validator with the same
     at-least-32-UTF-8-bytes rule as `validate_organization_cursor_key`
     (285-320), so a short secret fails at settings construction, not at request
     time;
   - add `has_formal_rule_root` / `has_formal_rule_cursor_key` to the safe
     summary.
6. Do not add a runner config field, capability flag, SQL migration, or API
   route in this task.
7. Add `tests/unit/test_formal_rule_filesystem.py`:
   - `test_publish_is_atomic_and_reader_sees_one_state`
   - `test_duplicate_publication_with_different_bytes_is_rejected`
   - `test_publication_and_byte_quotas`
   - `test_reader_serves_six_page_kinds`
   - `test_path_traversal_and_unsafe_tokens_are_rejected`
   - `test_unset_root_returns_none`
8. Add `tests/unit/test_formal_rule_settings.py`:
   - `test_formal_rule_root_is_optional_and_blank_is_unset`
   - `test_short_formal_rule_cursor_key_is_rejected`
   - `test_valid_formal_rule_cursor_key_is_accepted`
   - `test_safe_summary_reports_root_and_secret_presence_without_values`
9. Add `tests/unit/test_formal_rule_cli.py`:
   - `test_cli_flags_are_opt_in_and_default_off`
   - `test_disabled_producer_returns_disabled`
   - `test_receipt_written_next_to_artifacts`
   - `test_receipt_write_failure_does_not_fail_run`
   - `test_scientific_result_is_unchanged_by_publication`

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class FormalRuleProducerOptions:
    root: Path | None
    max_publications: int = 16
    max_artifact_bytes: int = 8 * 1024 * 1024

    @property
    def enabled(self) -> bool: ...

def producer_options_from_args(args: object) -> FormalRuleProducerOptions: ...
def publish_formal_rule_harvest(runner_result: object, *, run_id: str, input_revision: str, generated_tick: int, options: FormalRuleProducerOptions) -> dict[str, object]: ...
```

- Store schema is `formal-rule-store-v1`; snapshot schema remains
  `formal-rule-snapshot-v1`.
- The publisher is append-only and never rewrites a committed publication.
- The reader returns `None` when the root is unset; the API maps that to 503.
- The CLI producer is opt-in; no default artifact is written.

### Requirement Evidence

- `persistence/organization_filesystem.py` 39-120+.
- `research_runner/organization_composition.py` 34-135.
- `research_runner/cli.py` 955-962, 1228-1258, 1426-1428.
- `infrastructure/settings.py` 218-270, 584.

### Error Handling and Logging

- Unsafe token/path: `formal_rule_invalid_value`.
- Duplicate publication: `formal_rule_publication_exists`.
- Quota: `formal_rule_size_limit`.
- Read corruption: `formal_rule_digest_mismatch`.
- WARN: `formal_rule_publication_failed run_id=%s reason=%s`.
- INFO: `formal_rule_publication_published run_id=%s publication_id=%s
  candidates=%s rules=%s`.
- Never log snapshot payloads, scope anchors, rule content, or receipt bodies.

### Tests

- `uv run pytest tests/unit/test_formal_rule_filesystem.py tests/unit/test_formal_rule_settings.py tests/unit/test_formal_rule_cli.py -q`
- `uv run pytest tests/unit/test_organization_cli.py tests/unit/test_organization_filesystem.py -q`
  (adjust to actual names; keep the organization store/CLI green)

### Acceptance Criteria

- A publication is atomic, immutable, and quota-bounded.
- A duplicate id never overwrites bytes.
- The CLI producer is opt-in and cannot change the scientific result.
- No runner schema/migration/route is added.

### Verification

- `uv run pytest tests/unit/test_formal_rule_filesystem.py tests/unit/test_formal_rule_settings.py tests/unit/test_formal_rule_cli.py -q`
- `uv run mypy src/persistence/formal_rule_filesystem.py src/research_runner/formal_rule_composition.py src/infrastructure/settings.py`

## Phase Risks and Mitigations

- Risk: publication composition imports persistence/API and violates boundaries.
  Mitigation: experiments import only public simulation/analysis contracts; the
  publisher is injected.
- Risk: a failed publication mutates the runner result.
  Mitigation: the producer catches artifact/value/OS errors and returns a
  receipt only; the E2E asserts equality of the result before/after.
- Risk: the store exposes a partial `state.json`.
  Mitigation: write payloads first, then atomically replace `state.json` after
  `fsync`.
- Risk: a new env root is confused with a runner capability.
  Mitigation: it is a composition/read root only, never read by
  `SimulationRunner.from_config` or cognition.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
- Publication is opt-in, post-completion, atomic, and isolated from scientific
  status.
- No runner schema, migration, command, event, or write pair changed.
