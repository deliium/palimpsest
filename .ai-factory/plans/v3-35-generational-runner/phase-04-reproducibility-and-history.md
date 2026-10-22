# Phase 4: Reproducibility manifests and historical checkpoints

Plan: [index.md](index.md)
Tasks: 10–12
Depends on: Tasks 1–9

## Objective

Persist enough non-secret input identity and finalized historical references to reproduce and inspect a multi-generation experiment, without claiming full subjective restart.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/simulation/randomness.py` | `StreamScope`, `derive_stream_seed`, `objective_stream_identity` 33–131 | Named, versioned streams; v3 world streams use stochastic identity. |
| `src/simulation/engine.py` | demographic scope 2475–2505; weather scope 4270–4305 | Demography still includes durable run ID; environment uses the world stream machinery. |
| `src/simulation/new_agent_initialization.py` | `new_agent_init_stream` 1045–1069 | Initialization is run-ID-scoped. |
| `src/simulation/lifespan_distribution.py` | `lifespan_distribution_stream` | Assigned lifespans also retain run-ID scope. |
| `src/agents/cognition/practical_knowledge.py` | `mutate_practical_knowledge` 956–1035 | Innovation-related mutation uses deterministic SHA-256 material, not a shared random draw. |
| `src/simulation/runner.py` | `_knowledge_genealogy_loop_kwargs`; `RecordingStoreSettings`; `_commit_tick` | Root seed feeds knowledge policy; recording storage is composition-only; checkpoint cadence already exists. |
| `src/llm/recording/store.py` | `RecordingStore`, `CorrelationKey` 54–87 | Recording lookup identity includes namespace and request correlation. |
| `src/llm/recording/provider.py` | `_lookup` 305–359, `_result_from_record` 384–420 | Store retrieval precedes prompt/schema/output validation; only provider success can establish consumed validated output. |
| `tests/architecture/boundary_checker.py` | `ALLOWED_IMPORTS` 54–81 | Neither experiments nor research_runner may directly import llm; provider metadata must cross a simulation-owned port. |
| `src/persistence/sqlalchemy.py` | `SqlAlchemySimulationRunRepository.create_run` 125–141 | Recreating a durable RunId conflicts even if a new artifact attempt directory is used. |
| `src/research_runner/composition.py` | `resolve_package_version`, `resolve_code_revision` | Existing source revision is optional; new exact artifacts require stronger provenance. |
| `src/simulation/evidence.py` | `EvidenceManifest`, high-water readers | Analytical source cutoffs must match the objective commit. |
| `tests/integration/test_long_run_checkpoints.py` | cadence and historical seek tests | Reuse actual durable snapshots, not a new storage engine. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/simulation/generational_seeds.py` | create | Pure seed-lineage description from actual stream inputs. |
| `src/experiments/generational_artifacts.py` | create | Versioned manifest/history/result artifact models, strict codecs, append-only filesystem store and observer. |
| `src/llm/recording/models.py`, `src/llm/recording/provider.py`, `src/llm/recording/factory.py`, `src/llm/recording/__init__.py` | modify | Provider-owned successful replay-consumption callback with payload-free DTO. |
| `src/simulation/generational_control.py`, `src/simulation/__init__.py` | modify | Neutral recording-usage DTO/port and public adapter boundary. |
| `src/simulation/runner.py` | modify | Map provider replay-consumption metadata to the neutral sink; preserve default provider composition. |
| `src/research_runner/generational_composition.py` | create | Runtime/source identity, existing durable adapters, replay/history reader composition. |
| `tests/unit/test_generational_seed_manifest.py`, `tests/unit/test_generational_artifacts.py`, `tests/unit/test_generational_recording.py` | create | Identity, filesystem integrity, and recording tests. |
| `tests/integration/test_generational_history.py` | create | Real database checkpoint/replay/history tests. |

## Task 10: Record actual seed lineage and external LLM replay identity

### Intent

Preserve determinism rather than silently replace existing RNG semantics under an old derivation version.

### Implementation Steps

1. Add `build_generational_seed_manifest(config, run_id)` in `generational_seeds.py`. Record root seed, derivation version, stochastic identity, durable run ID, physical-rules fingerprint, schedule policy ID/canonical params fingerprint, initialization profile/distribution identity, and a closed channel table for world, demography, agent initialization, lifespan, innovation, environment, and LLM.
2. For each channel record the actual algorithm/version, namespace, identity selector, and scope-field names. World/environment use existing objective identity; demography, initialization, and lifespan retain run ID; innovation uses root-seed material plus its configured namespace/entry/tick SHA-256 scheme. `draw_usage` is one of `absent`, `reserved_ignored`, `deterministic_hash`, or `sampled`: lifecycle consult currently derives and draws a reserved demographic value even when a disabled/fixed/new deterministic policy ignores it. Record `reserved_ignored`, not zero engine draws. Do not invent unused independent subsystem seeds, remove existing reserved draws, or claim universal paired-run parity.
3. Preserve all existing seed derivation functions and scope contents. Audit active stochastic sites in the affected channels, and add tests that no global RNG/wall clock/hash defaults enter the new schedule, criteria, or metadata identity. A future cross-run seed unification would require a separate versioned change.
4. Add provider-owned frozen `ReplayConsumption` and optional synchronous `on_replay_consumed: Callable[[ReplayConsumption], None]` to the public `llm.recording` factory. In `_lookup`, construct the validated result first; invoke the callback only after digest compatibility and `_result_from_record` validation succeed. Emit namespace, current request correlation (agent/tick/component/request ID), lookup mode, cache key, record integrity digest (`sha256(encode_exchange_record_bytes(record))` computed inside llm), and prompt/schema identity only. No request/response objects or payload fields cross this callback. Store retrieval, prompt mismatch, invalid stored response, and replay miss must not emit success evidence.
5. Define neutral `RecordingUsageEvidence` and `RecordingUsageSink.put_usage(evidence) -> None` in `simulation/generational_control.py`; add optional `recording_usage_sink` to `RunnerDependencyFactories`. `simulation.runner` owns the adapter from `ReplayConsumption` to that DTO and passes its callback to normal recording-provider construction. Experiments persists only these DTOs through `GenerationalRunArtifactStore`; it never imports llm, decorates RecordingStore, or accesses exchange records. Research composition supplies the sink without a direct llm import. Preserve the existing two-argument custom provider_factory for ordinary/legacy library execution; exact archival contexts reject custom provider factories with `untracked_custom_provider` rather than guess successful-use reporting. Standard fake/replay composition is supported. Callback persistence failures raise a safe provider configuration error before the result is accepted; never fall back live.
6. Exact mode admits fake or replay only. Record logical recording artifact ID, namespace, lookup mode, request correlation convention, used-record count, and canonical usage-index digest. Never serialize root filesystem paths, API keys, endpoints, request/response payloads, or provider credentials into metadata. Verify replay usage and prompt/schema versions on reproduction; missing/drifted records fail closed.
7. Persist one immutable usage file keyed by the SHA-256 of canonical `(agent_id, tick, component, request_id, lookup_mode)` within this run. Duplicate same-key/same-evidence writes are idempotent; conflicts fail. Completion hashes the canonically sorted usage rows, not callback arrival order or mutable numeric ordinals. Count unique consumed request identities; retain failed/aborted run usage as incomplete evidence. Concurrent independent owner calls may complete in any order without changing the usage index or its digest. Store payloads remain provider-owned.

### Required Interfaces and Contracts

Same seed + same complete run identity/config/source + fake or the same validated replay records is the reproduction contract. Same stochastic identity with a different durable run ID guarantees only channels that actually use objective identity. LLM replay is an artifact dependency, not a seed guarantee. Innovation seed management does not add automatic innovation triggers or content.

### Requirement Evidence

User six-channel determinism/reproducibility requirements; actual stream functions cited above; C8/C9. Existing broad docs identity prose must be qualified in the documentation task, not implemented as an unversioned RNG change.

### Error Handling and Logging

Manifest mismatch and recording drift produce stable safe error codes; no live fallback. Logs contain channel names, versions, counts, and present/missing flags only; recording/cache/content digests belong in protected artifacts, never operational logs.

### Tests

Same complete identity reproduces seed descriptions and trajectory; different run IDs expose expected demographic/init/lifespan identity differences; extra draws in a disposable stream do not perturb unrelated named streams; absent lifecycle avoids its consult, while deterministic enabled lifecycle policies preserve the existing reserved ignored draw; innovation mutation repeatability/different seed. Drive the real RecordingLLMProvider through successful replay, miss, prompt/schema drift, and invalid stored response: only accepted validated outputs emit usage evidence. Reverse concurrent callback completion order and assert identical canonical usage rows/digest. Cover duplicate/conflicting usage identity, callback failure, custom-provider preflight, architecture boundaries, and no credentials/payloads in metadata or logs.

### Acceptance Criteria

Every requested channel has truthful lineage metadata; no seed algorithm or old off-path trajectory was silently changed.

### Verification

`uv run --frozen pytest --cov --cov-report=term-missing tests/unit/test_generational_seed_manifest.py tests/unit/test_generational_recording.py tests/unit/test_llm_recording_provider.py tests/unit/test_llm_recording_isolation.py -q`

Expected: deterministic identity, recording isolation, and safe metadata cases pass.

## Task 11: Persist immutable experiment manifests and historical boundary index

### Intent

Bind configuration, source identity, demographic history, stopping, and actual durable checkpoints into one inspectable artifact set.

### Implementation Steps

1. Define the exact artifact field sets in the contract table below, including `generational-failure-v1` and `generational-recording-usage-v1`. Use strict decoders with duplicate/unknown/missing-field rejection. Persist the credential-free runner config separately; immutable manifest references its digest rather than embedding duplicate config. Record a versioned execution recipe including any trusted runner configurator/diagnostic intervention. Operational timestamps are excluded from these canonical payloads and may appear only in separate operational logs.
2. Exact artifact production requires nonempty source revision. Accept a supplied immutable source-artifact digest as extra provenance; document that revision alone does not identify uncommitted changes. The production CLI requires an explicit clean-source assertion or a source-artifact digest; unknown source state must not be labeled fully reproducible. Do not change legacy matrix revision defaults.
3. Filesystem layout: `<root>/<safe-run-id>/<safe-attempt-id>/manifest.json`, `config.json`, `history/<boundary>.json`, `recording-usage/<usage-key>.json`, and `completion.json` or `failure.json`. Standalone execution uses attempt ID `single`; matrix attempts use their existing absolute attempt ordinal. Attempt identity is storage metadata, not RNG material or scientific run identity. Store config separately and reference its digest from manifest; no raw subjective payloads in history/completion. Manifest references actual immutable source/recording artifacts, not absolute machine paths.
4. Use same-directory temporary file + fsync + atomic publish. Existing same-key/same-bytes writes are idempotent; differing bytes are an integrity error. Refuse existing completed run directories for a new execution; do not overwrite or delete earlier history. Reject unsafe path segments and symlink escapes.
5. When historical cadence is non-null, publish history after finalized boundaries on that cadence, realized generation changes when `sample_on_generation_change` is true, and termination. Include completed boundary B, last executed tick B-1, objective revision, journal commit hash, nearest authoritative snapshot ID/hash/next_tick, evidence manifest/high-water identity if analysis was sampled, population/cohort/generation progress, stop evidence, and optional detached community sample reference. When historical cadence is null, do not create a historical index or claim snapshot availability; completion still records final progress and reproducibility metadata.
6. At cadence boundaries require an actual snapshot at B. At non-cadence generation/terminal samples reference the nearest snapshot plus the journal fold target B; label this a historical sample, not a newly written checkpoint. Bootstrap reference is B=0. Deduplicate overlapping sampling reasons into one boundary document with sorted reason codes.
7. Write completion only after finishing the runner, all requested historical artifacts, recording usage, and final result are durable. Include result-v3 document, exact/normalized trajectory hashes, final progress, seed/source identities, and final artifact digests. A missing required artifact produces failure, never a successful best-effort completion.
8. If a matrix crash leaves a complete verified generational archive but no matrix completion sidecar, reconstruct only the missing matrix metadata after validating assignment/config/source/recipe/seed/recording identities and all referenced hashes. Do not rerun world or cognition. If no valid completed archive exists and the durable RunId already exists, return non-retryable `durable_origin_rerun_unsupported`; even a bootstrap-only existing run conflicts. Do not delete the run, silently change RunId, or claim subjective restart. A user may explicitly reproduce in a fresh isolated persistence destination with the same scientific identity. Non-durable origin retries remain allowed in new attempt directories.

### Required Interfaces and Contracts

Header and per-boundary files are immutable. History files describe objective replay and detached analytical sampling, not a serialized `RunnerRuntimeCheckpoint`. Checkpoints do not promise restored memories, modern cognition ledgers, idempotency sets, or mid-cell continuation. Required exact schemas:

| Document | Exact top-level fields |
| --- | --- |
| `generational-run-manifest-v1` | `schema_version`, `run_id`, `attempt_id`, `assignment`, `execution_recipe`, `config_ref`, `config_fingerprint`, `scenario_fingerprint`, `cognition_fingerprint`, `seed_manifest`, `source_identity`, `environment_identity`, `provider_identity`, `history_policy`, `manifest_hash` |
| `generational-history-v1` | `schema_version`, `run_id`, `boundary_tick`, `last_completed_tick`, `revision`, `objective_commit_hash`, `snapshot_ref`, `evidence_ref`, `population_progress`, `stop_evidence`, `sample_reasons`, `community_ref`, `payload_hash` |
| `generational-completion-v1` | `schema_version`, `run_id`, `manifest_hash`, `result_document`, `seed_manifest_hash`, `recording_usage_ref`, `history_refs`, `final_progress`, `source_identity`, `execution_recipe_hash`, `completion_hash` |
| `generational-failure-v1` | `schema_version`, `run_id`, `manifest_hash`, `boundary_tick`, `stage`, `reason_code`, `objective_committed`, `owners_finalized`, `stop_evidence`, `failure_hash` |
| `generational-recording-usage-v1` | `schema_version`, `run_id`, `agent_id`, `tick`, `component`, `request_id`, `lookup_mode`, `namespace`, `cache_key`, `record_integrity_hash`, `prompt_identity`, `response_schema_identity`, `payload_hash` |

Nested contracts are closed as well:

- `assignment`: `experiment_id`, `condition_id`, `condition_ordinal`, `replicate_index`, `seed_ordinal`, nullable `matrix_id` and `cell_id`.
- `execution_recipe`: stable `recipe_id`, `version`, frozen canonical JSON `params`, nullable paired `intervention_id`/`intervention_version`, and `intervention_params` (empty when no intervention). Callback identity must be registered/versioned; an arbitrary unrecorded configurator cannot claim exact reproduction.
- `source_identity`: `code_revision`, `source_clean`, nullable `source_artifact_digest`. Require revision and either clean assertion or immutable source digest. `environment_identity`: `package_version`, `python_implementation`, `python_version`, `platform`, sorted `dependency_versions` mapping.
- `config_ref` and `community_ref`: root-relative safe `path` and `sha256`; the latter is nullable. Snapshot reference: `snapshot_id`, `integrity_hash`, `next_tick`. `evidence_ref` is null or the existing canonical EvidenceManifest envelope including its objective commit and high-water identity. At B=0, last tick/commit/stop evidence may be null; snapshot reference still names bootstrap.
- `provider_identity`: `adapter_kind`, `model`, `recording_policy`, `exact_reproducibility`, nullable `recording_artifact_id`, `recording_namespace`, `lookup_mode`. Fake uses null recording fields; replay requires all. Credentials/endpoints/root paths are forbidden.
- `seed_manifest`: root `seed`, `derivation_version`, `run_id`, `stochastic_identity`, `physical_rules_fingerprint`, `schedule_fingerprint`, `initialization_identity`, and sorted `channels`. Each channel has `name`, `algorithm_version`, `namespace`, `identity_selector`, ordered `scope_fields`, and `draw_usage`. Initialization identity contains `profile_id`, `parameter_distributions_hash`, and `lifespan_distribution_hash`; resolve these through the actual config, not guessed seeds.
- `history_policy` copies Task 1's cadence/generation-change settings. `recording_usage_ref`: `count`, sorted safe `row_refs`, `sha256`; fake uses count 0 and an empty canonical index. `history_refs` is ordered by boundary and includes each safe path/digest. `prompt_identity` and `response_schema_identity` reuse the provider's payload-free public identity fields, mapped to closed DTOs at the simulation boundary.
- Progress/stop evidence use the Task 1 canonical codecs. All self-hash fields hash sorted-key UTF-8 JSON with that self-hash field omitted; preserve existing canonical number rules and reject NaN/infinity. No filesystem enumeration order, request completion order, timestamps, credentials or absolute paths enter a deterministic digest.

### Requirement Evidence

User run metadata/checkpoints; user's inspection/replay clarification; evidence high-water contract; C8/C9.

### Error Handling and Logging

Stable filesystem/integrity codes only. Artifact failure after finalized B records failure at B without attempting rollback or tick retry. INFO written boundary/count; never log full paths, criterion JSON, config, recording keys, or subject matter.

### Tests

Known-answer payloads for every exact schema and nested identity; callback/intervention recipe drift; strict unknown/duplicate/missing-key rejection; unsafe path/symlink rejection; idempotent/conflicting duplicate; interrupted publish; snapshot/hash mismatch; cadence/generation deduplication; final non-cadence sample; failure prevents completion; missing source identity; canonical concurrent usage order. Simulate crash after archive completion but before matrix completion, adopt metadata without executing runner, and reject an incomplete archive with an existing durable RunId. Verify secret-safe artifacts/logs.

### Acceptance Criteria

A completed artifact set is self-identifying and verifiable without assuming mutable defaults; incomplete output cannot masquerade as completion.

### Verification

`uv run --frozen pytest --cov --cov-report=term-missing tests/unit/test_generational_artifacts.py -q`

Expected: integrity, source-identity, and failure cases pass.

## Task 12: Compose durable snapshot references and verify historical replay

### Intent

Use existing persistence and replay contracts rather than create a parallel checkpoint or subjective restart format.

### Implementation Steps

1. Introduce an outer `HistoricalBoundaryReader` protocol in `generational_artifacts.py`: `async reference(run_id, boundary_tick) -> HistoricalBoundaryReference`. It returns commit/revision, snapshot identity/next_tick, and optional exact evidence manifest; it may not silently substitute a later commit.
2. In `research_runner/generational_composition.py`, bind existing run/journal/snapshot/evidence repositories using public persistence factories and `SQLAlchemySessionFactory`, following `api/durable_runner.py` without importing API. Use snapshot repository `get_latest_at_or_before(run_id, Tick(B))` and authoritative journal data at B. Compare returned commit/revision to the finalized runner boundary.
3. Historical cadence equals existing `RunnerPersistenceSpec.checkpoint` cadence; no new snapshot writes outside the existing objective commit transaction. Bootstrap and cadence snapshots remain append-only. The observer reads those snapshots after owner finalization and writes only detached sidecars.
4. Require durable repository/journal/snapshot dependencies and history observer before creating a configured historical run. In-memory generational execution remains allowed when historical checkpoints are absent, but must not claim durable historical availability.
5. Add actual PostgreSQL integration fixtures with natural deaths, several admissions, migration, and empty-event commits. Seek to cadence and non-cadence samples with `ReplayService` / `scene_at_tick`; verify objective state, registration/lifecycle ledger, generation/cohort labels, and live/restored observations at the same boundary.
6. Keep historical replay read-only: do not call `open_durable` on a historical scene or apply runtime checkpoints. Explicitly assert that this path is not a full subjective process-restart proof.

### Required Interfaces and Contracts

No migration and no deletion/pruning of snapshots, events, or source evidence. Sparse cadence controls write frequency, not total storage growth. If authoritative snapshot extensions cannot preserve the existing lifecycle/initialization facts in the tested combination, treat that as a blocking invariant failure and fix the existing extension path before acceptance, without adding unversioned fields.

### Requirement Evidence

Inspection/replay scope decision; existing `RunnerCheckpointPolicy`; `ReplayService` historical versus continuation distinction; C7–C9.

### Error Handling and Logging

Missing/mismatched commit, snapshot or evidence cutoff fails the historical artifact, not the committed world. DEBUG snapshot selection uses safe IDs and tick counts. DB credentials/URLs are never logged.

### Tests

Bootstrap+cadence count; population death/entry snapshot fold; nearest-snapshot non-cadence inspection; eventless tick cursor; migration in transit and arrival; high-water exclusion of future evidence; no historical write reopening; snapshot parity with checkpoint cadence on/off.

### Acceptance Criteria

Every persisted history reference resolves to exactly the advertised objective boundary with the advertised demographics; no subjective restart claim is made.

### Verification

`uv run --frozen pytest --cov --cov-report=term-missing -m integration tests/integration/test_generational_history.py tests/integration/test_long_run_checkpoints.py tests/integration/test_regional_travel_persistence.py -q`

Expected: real integration tests pass against an explicitly disposable database whose name contains `palimpsest_test`; skips are not evidence of durable verification.

## Phase Risks and Mitigations

- Existing stream identity prose is broader than actual generational channels: record actual inputs and qualify documentation; do not silently alter derivation-v3.
- Source revision does not identify dirty code: require explicit clean-source assertion or a source artifact digest for the production exact manifest.
- Recording root/namespace is composition-only: keep logical artifact identity in the manifest and filesystem root outside it.
- Objective checkpoint commit precedes subjective finalization: sidecars publish only after finalization and retain the objective commit/high-water identities separately.

## Phase Completion Checklist

- Tasks 10–12 meet acceptance criteria and commands pass.
- Update only the index progress ledger.
