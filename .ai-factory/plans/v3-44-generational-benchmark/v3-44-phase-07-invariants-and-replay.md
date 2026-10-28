# Phase 7: Scientific boundaries and replay qualification

Plan: [index.md](index.md)
Tasks: 14–16
Depends on: Tasks 1–13

## Objective

Prove the requested generational and replay invariants against real benchmark artifacts. Explicitly separate objective replay, deterministic cognitive rerun, process-local subjective fork continuation and captured lineage reproduction.

## Current-Code Evidence

| Path | Symbols / tests | Why it matters |
| --- | --- | --- |
| `src/simulation/replay.py` | `ReplayService.replay` | Objective fold, not subjective restart |
| `src/simulation/runner.py` | `capture_fork_checkpoint`, `from_fork_checkpoint`, `export_finalized_research_boundary` | Complete supported in-process state; deterministic-fake fork guard |
| `tests/unit/test_new_agent_bootstrap_replay_determinism.py`, `tests/unit/test_kinship_death_persistence.py` | creation and dead-edge parity | Existing event/genealogy reconstruction |
| `tests/unit/test_observer_authority.py`, `tests/architecture/test_observer_isolation.py` | layouts change coordinates only; observer cannot commit | Presentation noninterference |
| `tests/integration/test_llm_recording_replay.py` | `test_record_then_replay_identical_structured_output` | Existing test proves provider output, not whole cognitive-run replay |
| `src/llm/recording/provider.py`, `src/llm/recording/store.py` | `RecordingLLMProvider`, `FilesystemRecordingStore`, `LookupMode` | Real offline recording boundary |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `tests/unit/test_v3_generational_scientific_invariants.py` | create | Explicit executable invariant matrix |
| `tests/architecture/test_v3_benchmark_isolation.py` | create | Trust/import/no-seeding gates |
| `tests/unit/test_v3_benchmark_replay.py` | create | Real benchmark objective/fork/capture parity |
| `tests/integration/test_v3_benchmark_persistence.py` | create | SQL append-only/restart/history/capture checks |
| `tests/integration/test_v3_benchmark_llm_replay.py` | create | Full independent-run recorded cognition replay |
| `src/experiments/civilization_benchmark_evidence.py` | modify | Replay receipt selectors, no live truth inputs |

## Task 14: Gate all generational scientific invariants

### Intent

A suite must expose behavioral violations, not only inspect class names or count catalog entries.

### Implementation Steps

1. Add parameterized real-execution checks linked to case IDs and named invariants. Reuse short mechanism prefixes to keep default tests bounded, with full smoke executions in Task 22.
2. Measure new-owner stores before first cognition and founder stores after experience; assert no arbitrary cross-owner content/identity aliases. Assert all later acquired history has perception, actual delivery or current interpreted-record provenance. Include a deliberately leaking service test double to prove the guard can fail.
3. Count cognitive invocations and admission attempts across objective death boundaries; dead owners stop acting, while historical queries, genealogy and their records remain available. Verify last-holder loss, actual no-contact isolation, physical-only migration and possession-versus-legitimacy separation.
4. Run identical seed/identity twins with capture and observer off/on/failing, radically different presentation coordinates and read/seek requests. Assert canonical objective exports and subjective source inventories identical; only presentation coordinates differ.
5. Add AST/import-linter-compatible tests forbidding private world imports, truth/history-store access from cognition, observer/client mutation routes and benchmark fixture ledger writes. Behavioral tests remain authoritative where AST checks alone are insufficient.

### Required Interfaces and Contracts

Required invariant IDs: `blank_slate`, `valid_historical_channels`, `dead_stop_acting`, `physical_record_persistence`, `false_records_legal`, `technology_loss_possible`, `auditable_knowledge_lineage`, `subjective_roles`, `possession_not_legitimacy`, `isolated_knowledge`, `engine_migration`, `coordinates_nonsemantic`, `observer_read_only`. Every ID has positive/negative test coverage and source-referenced receipts.

### Requirement Evidence

Original Request — Generational invariants (all thirteen items); `.ai-factory/RULES.md`; `.ai-factory/ARCHITECTURE.md` — authority boundaries.

### Error Handling and Logging

Any contradiction fails with invariant ID and safe qualified reference; missing evidence is unexecuted, not pass. Negative tests use expected failure without leaking fixture content. Logs are counts/IDs/reason codes only.

### Tests and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_v3_generational_scientific_invariants.py tests/architecture/test_v3_benchmark_isolation.py tests/unit/test_observer_authority.py -q`.

### Acceptance Criteria

Every requested invariant is exercised by actual state/actions and fails under a deliberately invalid fixture where practical. No check depends solely on a name-based deny-list.

## Task 15: Qualify objective replay and captured subjective lineage separately

### Intent

Do not claim practical-knowledge or technology lineage is reconstructible from objective events when it lives in separate captured owner evidence.

### Implementation Steps

1. For benchmark cases 01, 02, 06, 09–11, 18, 26 and 30, retain canonical live observations/state at admission, death, journey start/arrival, witness extinction and selected cohort boundaries. Restore through `ReplayService` from bootstrap and from durable checkpoints; compare objective state, creation provenance, genealogy, physical records, prior-event observation windows and event-prefix folds.
2. Run deterministic-fake experiments twice with identical scientific identities in isolated stores. Compare canonical command/admission/result/source inventories. At the final boundary use Task 4's terminal-safe research projection after `finish_run`, before resources close; do not call a terminal fork checkpoint or use a prior boundary. Assert matching result/projection boundaries and result-stage identities. For in-process fork twins, compare complete runtime/owner snapshots at supported nonterminal boundaries and subsequent results, including retired-owner state from V3-43. Mutate a detached child snapshot in a negative test and detect mismatch without touching parent state.
3. Rebuild technology/knowledge lineage views from verified retained subjective/cultural/lineage artifacts; compare qualified nodes/edges/root identities and availability. Compare deterministic rerun capture separately. Never reconstruct missing owner knowledge from objective event exports or collapse equal-content independent roots.
4. Integration tests use a disposable PostgreSQL/pgvector database containing `palimpsest_test`. Restart read services without a live runner and query real benchmark history/publications. Verify append-only guards, parent/child run lineage and record history; deleted/tampered sidecars must produce explicit missing/corrupt results, not repaired truth.
5. Bind replay receipts to source revision, config/recipe, seed/stochastic identity, event/commit high-water and publication reference. No durable subjective resume claim is permitted.

### Required Interfaces and Contracts

Replay receipt kinds: `objective_fold`, `deterministic_rerun`, `in_process_fork`, `captured_lineage_rebuild`. Birth/death/genealogy parity is objective; practical technology lineage parity requires captured owner evidence or a deterministic rerun. Every result names which guarantee passed. Feature-selected replay-v22/codec-v20 remains distinct from older accepted pairs.

### Requirement Evidence

Original Request — Replay invariants; `docs/persistence.md`; `docs/historical-contingency.md`; `docs/lineage-explorer.md`; `docs/long-horizon-scalability.md` — historical copies and no subjective resume.

### Error Handling and Logging

Tampered commit, missing source, stale publication, mismatched owner/root and wrong child identity fail closed with safe codes. Capture absent remains unavailable, not empty lineage. Log boundary/count/status metadata only.

### Tests and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_v3_benchmark_replay.py tests/unit/test_simulation_replay_determinism.py tests/unit/test_path_dependence_replay_parity.py -q`.

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term -m integration tests/integration/test_v3_benchmark_persistence.py -q` with `PALIMPSEST_TEST_DATABASE_URL` set to a disposable database.

### Acceptance Criteria

All requested objective replay boundaries match exactly; subjective lineage guarantees are backed by their real sources. Parent history remains unchanged after both child runs and read-service restart.

## Task 16: Replay recorded LLM cognition in a real independent generational run

### Intent

Prove configured recorded cognition, not merely a standalone provider call, while retaining the unsupported recorded-fork boundary.

### Implementation Steps

1. Build a short independent generational case with an owned LLM-consuming cognition stage (reconstructive memory using existing provider/factory settings). Execute through `execute_generational_assignment` with a real `GenerationalExecutionContext`, benchmark recipe, explicit source/recording identity and archive session. Start with empty stores; accumulate actual recallable experience and ensure at least one real provider request occurs after admitted cohort entry.
2. Use the normal `RunnerDependencyFactories` provider path with `provider_factory=None`, configured `recording_store_settings`, injected deterministic sleep/monotonic clocks and provider settings selecting RECORD plus the existing deterministic-fake adapter. RECORD requires `ExactReproducibilityMode.NOT_REQUIRED`; retain the actual provenance declaration rather than falsely marking recording deterministic. `_default_provider`/`_inner_provider_for_recording` then constructs the real `RecordingLLMProvider` around the fake inner provider, without bypassing archival usage tracking. Re-run from the initial config through the same archival path with the same scientific run/agent/request and recording identities, isolated world/archive attempt stores, and REPLAY mode with `ExactReproducibilityMode.REQUIRED`. Record the intentional provider-policy/config-fingerprint difference; compare scientific outputs and verify each archive against its own config rather than requiring identical RECORD/REPLAY config bytes. Instrument the existing default inner-provider seam only in the test to count/forbid `generate` fallback during replay; do not substitute a custom runner provider factory. Forbid all network transport.
3. Compare validated stage outputs, actual command/admission sequence, objective result and supported owner reconstruction/audit state. Compare scientific fields excluding operational durations; assert nonzero RECORD store entries, nonzero archived REPLAY usage receipts for real cognition requests and zero fallback calls. Verify source/provider/model/component/schema/prompt/request identity and both completed archives with existing verifiers, not only provider output equality.
4. Test missing record, altered component/schema/prompt identity and wrong namespace fail closed without live fallback or a completion artifact for failed science. Assert archival `with_generational_control` still rejects a custom `provider_factory` with `UNTRACKED_CUSTOM_PROVIDER`; do not weaken that guard to accommodate the test. Add a recorded/live provider fork rejection test; do not widen `from_fork_checkpoint` or BN allowlists.

### Required Interfaces and Contracts

This is independent recorded-cognition reproduction from the original start, not recorded-LLM fork continuation or durable subjective resume. Recording artifacts may contain private payloads and remain test-local or access-controlled; suite reports retain only safe references/usage identity. No recorded payloads enter operational logs or checked-in golden files.

### Requirement Evidence

Original Request — recorded LLM cognition can be replayed where configured; `tests/integration/test_llm_recording_replay.py`; `.ai-factory/ARCHITECTURE.md` — LLM trust boundary.

### Error Handling and Logging

Existing safe LLM configuration/replay error codes propagate into benchmark receipts. Never convert recording miss into deterministic-fake success. Log request counts/component IDs and safe codes only.

### Tests and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term -m integration tests/integration/test_v3_benchmark_llm_replay.py tests/integration/test_llm_recording_replay.py -q`.

### Acceptance Criteria

The production archival composition path demonstrably consumes recorded cognition outputs with positive archived usage receipts, no external calls and matching original scientific behavior. Custom untracked factories and unsupported recorded forks remain rejected.

## Phase Risks and Mitigations

- A zero-request run can give vacuous recording parity: require a positive usage count and post-entry request witness.
- Objective replay can falsely appear to prove cultural truth: keep four receipt kinds and test missing capture explicitly.

## Phase Completion Checklist

- Verify Tasks 14–16; update index only.
- Do not mark unavailable DB/LLM-stage checks passed merely because provider-only tests pass.
