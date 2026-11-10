# Phase 4: Collection and Publication

Plan: [index.md](index.md)
Tasks: 13-16
Depends on: Phase 3 (Tasks 10-12)

## Objective

Wire the analysis into completed runs, then publish it as an opt-in, canonical
sibling artifact with an atomic filesystem store, dual-gated settings, and a
production composition entry point. This is not a runner, result, replay, or SQL
schema.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/experiments/trade_networks_completed_run.py` | builder 118-169; helpers 172-182 | Completed-run builder shape |
| `src/experiments/collectors.py` | `assemble_arm_metric_bundle` 190; events 287-290; trade block 288-327; `collect_catalog_metrics` 1124-1150 | Collector attachment point |
| `src/analysis/metric_service.py` | `MetricComputationInputs` 371; `assemble_metric_documents` 459 | Carrier field and assembly |
| `src/simulation/runner_models.py` | `skill_audits` 6375; `organization_operation_ledgers` 6394; `final_infrastructure_assets` 6364; `SkillAuditSide.OBJECTIVE` 777-781 | Detached objective inputs |
| `src/analysis/organization_operations.py` | `OrganizationProcedureActionRow` 302-330; `OrganizationOperationHarvestRows` 414-453; `harvest_organization_operation_rows` 814-858; `harvest_organization_operation_snapshot` 861-869 | Exact claim extraction path |
| `src/simulation/trade_networks_models.py` | version 44-45; records 149-404; snapshot 455-501 | Snapshot model shape |
| `src/simulation/trade_networks_codec.py` | canonical 61-99; encode 124; decode 244 | Canonical codec shape |
| `src/simulation/trade_networks_paging.py` | `MAX_PAGE_LIMIT=500` 38; selections 41-99; page functions 173-283 | Paging shape |
| `src/simulation/trade_networks_ports.py` | purposes 27-35; fingerprint 87; match 121; protocols 133-144 | Cursor/ports shape |
| `src/persistence/trade_networks_filesystem.py` | store version 32; options 39-47; publish 132-172; atomic write 83-94; reader 187-235 | Atomic store |
| `src/experiments/trade_networks_publication.py` | compose 148-263; build 266-306; publish 309-362 | Publication contract |
| `src/research_runner/infrastructure_composition.py` | options 29-43; publish 56-84 | Production composition |
| `src/research_runner/cli.py` | 1628-1655 | CLI wiring |
| `src/infrastructure/settings.py` | trade root/key 248-249; validator 420-429; diagnostics 781-792 | Settings pattern |
| `src/simulation/__init__.py` | trade exports 1203+ | Facade pattern |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/experiments/supply_chain_completed_run.py` | create | Completed-run builder and detached-input helpers |
| `src/experiments/collectors.py` | modify | Attach `supply_chain_analysis` |
| `src/simulation/supply_chain_models.py` | create | Canonical `supply-chains-snapshot-v1` records |
| `src/simulation/supply_chain_codec.py` | create | Canonical codec |
| `src/simulation/supply_chain_paging.py` | create | Six page selections with `window_index` |
| `src/simulation/supply_chain_ports.py` | create | Cursor purposes, fingerprint, ports |
| `src/simulation/__init__.py` | modify | Facade exports for snapshot/codec/paging/ports |
| `src/persistence/supply_chain_filesystem.py` | create | `supply-chains-store-v1` |
| `src/infrastructure/settings.py` | modify | Two settings + validation + diagnostics |
| `.env.example` | modify | Document the two variables |
| `src/experiments/supply_chain_publication.py` | create | Compose/build/publish/document |
| `src/research_runner/supply_chain_composition.py` | create | Publisher options and publish entry |
| `src/research_runner/cli.py` | modify | Opt-in publication flag |
| `tests/unit/test_supply_chain_collector.py` | create | Collector wiring tests |
| `tests/unit/test_supply_chain_snapshot.py` | create | Model/codec/paging tests |
| `tests/unit/test_supply_chain_store.py` | create | Store/atomicity/quota tests |
| `tests/unit/test_supply_chain_settings.py` | create | Settings validation tests |
| `tests/unit/test_supply_chain_publication.py` | create | Publication contract tests |

## Task 13: Wire completed-run analysis and experiment collectors

### Intent

Make every completed run with the channel active produce the analysis from
committed events plus detached objective inputs, without reading run-side state.

### Implementation Steps

1. Create `src/experiments/supply_chain_completed_run.py`:
   - `supply_chain_recipe_specs(config)`: read
     `config.agents[0].cognition.production_catalog`, verify every agent's
     `production_catalog_digest` matches, and map
     `production_chain_stages(catalog)` to `SupplyRecipeSpec`;
   - `supply_chain_skill_levels(runner_result)`: keep `SkillAudit` rows whose
     `side is SkillAuditSide.OBJECTIVE`, mapping `level` as-is;
   - `supply_chain_infrastructure(runner_result)`: keep
     `final_infrastructure_assets` whose `status.value == "operational"`,
     grouping kinds by `location_id.value`;
   - `supply_chain_organization_claims(runner_result)`: call
     `harvest_organization_operation_rows` on
     `organization_operation_ledgers`, then iterate each bundle's
     `.procedures` (not a flat row list), group by `organization_id`, and
     project `SupplyOrganizationClaim` with `command_kinds`, `actor_tokens`
     (from `actor_id`, sorted unique), tick span, and `claim_count`. There is no
     recipe id and no location to project;
   - `build_completed_run_supply_chain_analysis(runner_result=None, *,
     committed_events, run_id, recipe_specs=None, policy=None,
     window_tick=None, skill_levels=None, infrastructure=None,
     organization_claims=None)`.
2. `committed_events is None` raises `ValueError("supply_chain_requires_events")`.
   Empty recipe specs let analysis report `missing` recipe coverage plus
   `unknown_recipe`; never fabricate recipes.
3. `src/experiments/collectors.py`: add a supply-chain block immediately after
   the trade block (288-327). Do **not** test for a
   `runner_result.supply_chain_analysis` field — none exists by design. Build
   from `arm.assignment.runner_config`, `arm.runner_result`, and `events`, then
   `inputs = replace(inputs, supply_chain_analysis=analysis)`. Catch
   `Exception` and log `supply_chain_collector_failed code=<safe_code>`; log
   `supply_chain_collector_missing_events` when events are absent.
4. Keep `collect_catalog_metrics`/`collect_for_experiment` unchanged.

### Required Interfaces and Contracts

- Only committed events plus detached inputs are read.
- Recipe specs come from the run's own config; skill/infrastructure/
  organization inputs come from `runner_result` exports.
- A failed enrichment never fails metric collection; analysis stays `None` and
  metrics report `missing`.

### Requirement Evidence

- `trade_networks_completed_run.py` 118-182; `collectors.py` 190/288-327;
  `runner_models.py` 6364/6375/6394/777-781;
  `organization_operations.py` 302-330/414-453/814-869.
- Supported combinations: events only, catalog only, full inputs, each optional
  input missing, collector exception, foreign/absent `supply_chain_analysis`
  attribute.

### Error Handling and Logging

- `INFO supply_chain_completed_run stages=<n> edges=<n> coverage=<value>`.
- `WARN supply_chain_recipe_catalog_mismatch`.
- `WARN supply_chain_collector_missing_events`;
  `ERROR supply_chain_collector_failed code=<code>`.
- Never log item names, skill rows, organization claims, or event bodies.

### Tests

- `tests/unit/test_supply_chain_collector.py`:
  `test_builder_requires_events`, `test_recipe_specs_from_config`,
  `test_digest_mismatch_sets_notice`, `test_objective_skill_rows_only`,
  `test_operational_assets_only`,
  `test_organization_claims_iterate_bundles`,
  `test_organization_claim_has_no_recipe_or_location`,
  `test_collector_attaches_analysis`,
  `test_collector_does_not_read_nonexistent_result_field`,
  `test_collector_survives_failure`,
  `test_metrics_report_missing_without_analysis`.
- `uv run pytest tests/unit/test_supply_chain_collector.py -q`.

### Acceptance Criteria

- A run with events and config attaches a non-empty analysis.
- Removing events leaves metrics valid with `missing` coverage.
- A raising builder never breaks the metric bundle.

### Verification

- `uv run pytest tests/unit/test_supply_chain_collector.py -q` → all pass.

## Task 14: Add `supply-chains-snapshot-v1` models codec ports and paging

### Intent

Define the canonical read model before storage/transport, with a purpose-bound
cursor that binds the optional `window_index` filter.

### Implementation Steps

1. `src/simulation/supply_chain_models.py`:
   - `SUPPLY_CHAIN_SNAPSHOT_VERSION = "supply-chains-snapshot-v1"`,
     `SUPPLY_CHAIN_SNAPSHOT_POLICY = "supply-chains.v1"`;
   - caps 4096/16384/4096/4096/4096/2048/512/16384;
   - records `SupplyStageRecord`, `SupplyDependencyRecord`,
     `SupplyChainRecord`, `SupplyLineageRecord`, `SupplyBottleneckRecord`,
     `SupplyLocationRecord`, `SupplyOrganizationRecord`,
     `SupplyChainSummaryRecord`;
   - `SupplyChainSnapshot` with `schema_version`, `policy`, `run_id`,
     `window_tick`, `summary`, the seven row tuples, `coverage`, `digest`,
     `publication_id`. **No `created_tick`**: the snapshot is derived from
     committed ticks, never wall-clock metadata;
   - `empty_supply_chain_snapshot(run_id, *, window_tick=0)`.
   Records are frozen/slots, reject forbidden keys, and store coverage as a
   string token.
2. `src/simulation/supply_chain_codec.py`: canonical payload/JSON, digest,
   publication id, finalize, encode, decode. Canonical JSON is
   `sort_keys=True, separators=(",", ":")`, UTF-8. Decode rejects digest
   mismatch (`supply_chain_snapshot_digest_mismatch`) and unknown version
   (`supply_chain_snapshot_version_unsupported`).
3. `src/simulation/supply_chain_paging.py`: `MAX_PAGE_LIMIT = 500`; selection
   dataclasses for stages, dependencies, chains, bottlenecks, locations,
   organizations (`purpose`, `after_key`, `limit`, `window_index`, `rows`,
   `next_key`); six page functions filtering by `window_index` before slicing;
   keys `(window_index, stable_row_token)`.
4. `src/simulation/supply_chain_ports.py`: six cursor purposes; summary,
   publication, cursor types; `supply_chain_query_fingerprint(run_id, purpose,
   limit, window_index)`; `supply_chain_cursor_matches`; reader/publisher
   protocols.
5. `src/simulation/__init__.py`: facade imports/exports for the four new
   modules mirroring the trade block at 1203+.

### Required Interfaces and Contracts

- `window_index` is part of the cursor fingerprint; a cursor for window 3 is
  rejected for window 4.
- No snapshot record accepts price/cost/score/rank/severity/recommendation/
  quota/allocation keys.
- Paging is pure; `publication_id` is SHA-256 over canonical payload + digest.

### Requirement Evidence

- `trade_networks_models.py` 44-501; `trade_networks_codec.py` 61-244;
  `trade_networks_paging.py` 38-283; `trade_networks_ports.py` 27-144;
  `simulation/__init__.py` 1203+.
- Supported combinations: empty/full snapshot, page with/without filter, stale
  window cursor, unknown version, digest mismatch.

### Error Handling and Logging

- `WARN supply_chain_snapshot_decode_rejected code=<code>`.
- `DEBUG supply_chain_snapshot_finalized rows=<n> digest=<prefix8>`.
- No payload bodies in logs.

### Tests

- `tests/unit/test_supply_chain_snapshot.py`:
  `test_round_trip_is_canonical`, `test_digest_is_stable`,
  `test_snapshot_has_no_wall_clock_field`,
  `test_decode_rejects_digest_mismatch`, `test_decode_rejects_unknown_version`,
  `test_records_reject_forbidden_keys`, `test_empty_snapshot_is_valid`,
  `test_page_without_filter`, `test_page_with_window_filter`,
  `test_cursor_binds_window`, `test_cursor_rejects_other_window`,
  `test_paging_is_pure`, `test_summary_counts_match_rows`,
  `test_simulation_facade_exports`.
- `uv run pytest tests/unit/test_supply_chain_snapshot.py -q`.

### Acceptance Criteria

- Encode→decode yields equal snapshot and digest.
- A window-bound cursor fails for another window.
- No record accepts a scoring field.

### Verification

- `uv run pytest tests/unit/test_supply_chain_snapshot.py -q` → all pass.

## Task 15: Add atomic filesystem store and dual-gated settings

### Intent

Publish snapshots safely and keep them opt-in. Readers must not exist unless
both root and cursor-key settings are present.

### Implementation Steps

1. `src/persistence/supply_chain_filesystem.py`:
   - `SUPPLY_CHAIN_STORE_VERSION = "supply-chains-store-v1"`;
   - `SupplyChainPublisherOptions(max_publications=16, max_bytes=8_388_608)`;
   - `_Publisher.publish` is idempotent for an identical publication id,
     enforces publication and byte quotas
     (`supply_chain_store_quota_exceeded`), and writes payload plus
     `state.json` via `_atomic_write` under an `fcntl.flock` guard;
   - reader methods `summary`, `read_page`, `list_publications`,
     `read_snapshot`; corrupt payload → `SupplyChainStoreCorrupt`;
   - factories `create_supply_chain_reader`, `create_supply_chain_publisher`.
2. `src/infrastructure/settings.py`: add `supply_chains_root` and
   `supply_chains_cursor_key` (after 248-249); extend validation (420-429) for
   ≥32 UTF-8 bytes and treat a partial gate as disabled without error; add
   names-only diagnostics (781-792).
3. `.env.example`: add both variables with empty values and a comment.

### Required Interfaces and Contracts

- Store version `supply-chains-store-v1`; snapshots immutable once published.
- Duplicate publish of the same id is a no-op success.
- Partial dual gate yields no reader, not a startup error.
- Store errors propagate.

### Requirement Evidence

- `trade_networks_filesystem.py` 32-241; `settings.py` 248-249/420-429/781-792;
  ARCHITECTURE "Requirements for later changes" item 5.
- Supported combinations: both configured, neither, one only, duplicate,
  quota, corrupt payload.

### Error Handling and Logging

- `ERROR supply_chain_store_quota_exceeded` (limits/counts only).
- `WARN supply_chain_store_corrupt publication_id=<id>`.
- `INFO supply_chain_snapshot_published publications=<n> bytes=<n>`.
- Never log payloads, DSNs, or cursor keys.

### Tests

- `tests/unit/test_supply_chain_store.py`:
  `test_publish_then_read`, `test_duplicate_publish_is_idempotent`,
  `test_publication_quota`, `test_byte_quota`,
  `test_corrupt_payload_fails_closed`, `test_atomic_write_replaces_state`,
  `test_list_publications_is_ordered`.
- `tests/unit/test_supply_chain_settings.py`:
  `test_root_and_key_enable_reader`, `test_neither_disables`,
  `test_root_only_disables`, `test_key_only_disables`,
  `test_short_key_rejected`, `test_env_names_are_prefixed`,
  `test_secrets_not_in_diagnostics`.
- `uv run pytest tests/unit/test_supply_chain_store.py tests/unit/test_supply_chain_settings.py -q`.

### Acceptance Criteria

- Publishing twice leaves one publication.
- A short key raises a validation error.
- The cursor key never appears in diagnostics.

### Verification

- `uv run pytest tests/unit/test_supply_chain_store.py tests/unit/test_supply_chain_settings.py -q` → all pass.

## Task 16: Compose and publish completed-run supply-chain snapshots

### Intent

Provide the only analysis→artifact bridge and a production composition entry
point, so a completed run can publish without the API or simulation importing
experiments.

### Implementation Steps

1. `src/experiments/supply_chain_publication.py`:
   - `compose_supply_chain_snapshot(analysis, *, run_id)` type-checks
     `SupplyChainAnalysis`, maps every row family, builds the summary, finalizes;
   - `build_supply_chain_harvest_result(runner_result=None, *,
     committed_events, run_id, ...)` calls the Task 13 builder then composes;
   - `publish_supply_chain_snapshot(harvest, publisher)` returns
     `stored=False, reason="supply_chain_publication_missing"` for `None` or
     empty/missing snapshots, else publishes and returns
     `stored=True, reason="published"`; foreign types raise `TypeError`; store
     errors propagate;
   - `supply_chain_publication_document(harvest)` returns bounded metadata.
2. `src/research_runner/supply_chain_composition.py`:
   `SupplyChainProducerOptions` and `publish_supply_chain_harvest(harvest, *,
   options) -> tuple[bool, str]`; no `api` import.
3. `src/research_runner/cli.py`: add an opt-in `--publish-supply-chains <root>`
   flag (1628-1655 pattern), default off, publish only after successful
   scientific completion.
4. Export the new helpers from `src/experiments/__init__.py` in the trade block
   style.

### Required Interfaces and Contracts

- Publication never runs inside simulation, analysis, API, or persistence.
- Publication failure never changes scientific status.
- No event, command, migration, or runner/result schema is added.
- Publication is opt-in; default behavior unchanged.

### Requirement Evidence

- `trade_networks_publication.py` 148-379;
  `infrastructure_composition.py` 29-84; `cli.py` 1628-1655.
- Supported combinations: empty harvest, non-empty, duplicate, store failure,
  publication disabled.

### Error Handling and Logging

- `INFO supply_chain_publication_stored publications=<n> bytes=<n>`.
- `WARN supply_chain_publication_missing reason=<reason>`.
- `ERROR supply_chain_publication_failed code=<safe_code>` at the CLI boundary.
- No snapshot contents, cursor keys, or owner claims.

### Tests

- `tests/unit/test_supply_chain_publication.py`:
  `test_compose_requires_analysis`, `test_compose_maps_all_row_families`,
  `test_empty_harvest_is_not_stored`, `test_publish_stores_snapshot`,
  `test_publish_is_idempotent`, `test_store_error_propagates`,
  `test_document_has_bounded_fields`, `test_cli_flag_defaults_off`,
  `test_no_api_import` (AST scan).
- `uv run pytest tests/unit/test_supply_chain_publication.py -q`.

### Acceptance Criteria

- A non-empty analysis publishes exactly one snapshot with a stable digest.
- An empty analysis writes nothing and reports `publication_missing`.
- The CLI publishes only with the opt-in flag.

### Verification

- `uv run pytest tests/unit/test_supply_chain_publication.py -q` → all pass.

## Phase Risks and Mitigations

- Risk: collector reads a result field that will never exist.
  Mitigation: Task 13 removes the guard and tests its absence.
- Risk: organization claims are projected from fields the source lacks.
  Mitigation: Task 13 uses only `procedures` bundle fields, tested.
- Risk: cursor reuse across windows leaks rows.
  Mitigation: window in the fingerprint; mismatch rejected.
- Risk: publication enters the default path.
  Mitigation: composition-only, CLI opt-in, default-off test.

## Phase Completion Checklist

- Every Task 13-16 satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
