# Phase 3: Completed-Run Inputs, Snapshot, Store, and Publication

Plan: [index.md](index.md)
Tasks: 9-12
Depends on: Phase 2 (Tasks 5-8)

## Objective

Wire real completed runs into the analysis, define the canonical
`social-mobility-snapshot-v1` artifact with a bounded atomic store, and publish
it programmatically after successful completion. After this phase the collector
injects a non-empty analysis, the snapshot round-trips byte-identically, and the
store survives quota and corruption cases.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/economic_inequality_completed_run.py` | `economic_inequality_recipe_mappings` (61-91), `build_completed_run_economic_inequality_analysis` (143-208) | Completed-run bridge shape, catalog mapping, generation/society joins |
| `src/experiments/collectors.py` | `assemble_arm_metric_bundle` (190-196), economic guard (474-537) | Exact injection point, activation condition, try/except isolation |
| `src/simulation/economic_inequality_models.py` | version constants (26-33), `EconomicInequalitySummaryRecord` (111-145), `EconomicInequalitySnapshot` (254-313), `empty_*` (316-339) | Snapshot model and cap conventions |
| `src/simulation/economic_inequality_codec.py` | canonical bytes (87-97), digest (100-110), finalize (122-132), encode (135-147), decode (186-263) | Canonical, digest-addressed, strict decode |
| `src/simulation/economic_inequality_paging.py` | purpose map (22-47), `page_economic_inequality` (59-113) | Purpose filter, window filter, strict after-key |
| `src/simulation/economic_inequality_ports.py` | cursor token (18-20), purposes (21-29), cursor (32-51), fingerprint (54-75), protocols (78-85) | Cursor and port contracts |
| `src/persistence/economic_inequality_filesystem.py` | store version (37), options (45-54), `_Publisher` (129-198), `_Reader` (201-227), factories (230-250) | Atomic state.json + lock + quota + idempotent publish |
| `src/infrastructure/settings.py` | root (268), cursor key (269-271), cursor validator (509-518), `empty_presentation_root_is_unset` (313-334), bootstrap flags (942-954) | Dual-gate settings and blank-root normalization |
| `src/experiments/economic_inequality_publication.py` | receipt (48-62), `compose_*` (73-162), `publish_*` (165-225), `build_*_harvest_result` (228-243) | Publication receipt and never-raise contract |
| `src/simulation/__init__.py` | economic exports (507-541, 1586-1591, 1663-1666, 2004-2011) | Facade export pattern |
| `src/experiments/__init__.py` | economic imports (286-294), `__all__` entries (711, 721, 754, 891) | Bridge export pattern |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/social_mobility_completed_run.py` | create | Completed-run builder and recipe mappings |
| `src/experiments/collectors.py` | modify | Kinship+outcome-gated injection with isolated failure |
| `src/simulation/social_mobility_models.py` | create | Snapshot records, snapshot, empty helper, caps |
| `src/simulation/social_mobility_codec.py` | create | Canonical JSON, digest, finalize, encode/decode |
| `src/simulation/social_mobility_paging.py` | create | Purpose map, page function, sort keys |
| `src/simulation/social_mobility_ports.py` | create | Cursor, purposes, fingerprint, reader/publisher protocols |
| `src/simulation/__init__.py` | modify | Export snapshot/codec/paging/port symbols |
| `src/persistence/social_mobility_filesystem.py` | create | Atomic store, quotas, reader/publisher factories |
| `src/infrastructure/settings.py` | modify | Root, cursor key, validator list, bootstrap flags |
| `src/experiments/social_mobility_publication.py` | create | Compose/publish/harvest result |
| `src/experiments/__init__.py` | modify | Export completed-run and publication symbols |
| `tests/unit/test_social_mobility_completed_run.py` | create | Bridge mapping and activation |
| `tests/unit/test_social_mobility_collector.py` | create | Collector injection and failure isolation |
| `tests/unit/test_social_mobility_snapshot.py` | create | Model/cap/round-trip tests |
| `tests/unit/test_social_mobility_codec.py` | create | Canonical/digest/decode tests |
| `tests/unit/test_social_mobility_paging.py` | create | Purpose/window/cursor tests |
| `tests/unit/test_social_mobility_ports.py` | create | Cursor/fingerprint tests |
| `tests/unit/test_social_mobility_store.py` | create | Store/quota/idempotency/corruption |
| `tests/unit/test_social_mobility_settings.py` | create | Settings and bootstrap flags |
| `tests/unit/test_social_mobility_publication.py` | create | Compose/publish receipts |

## Task 9: Wire completed-run inputs and collector injection

### Intent
Prove the analysis runs on real completed runs, not just synthetic rows, and
guarantee a malformed optional seam cannot fail a completed run.

### Implementation Steps
1. Create `src/experiments/social_mobility_completed_run.py`:
   - `social_mobility_recipe_mappings(runner_config) -> tuple[Mapping[str,
     str], Mapping[str, str]]`: read
     `runner_config.agents[0].cognition.production_catalog`; when the catalog is
     empty, missing, or agents disagree, return `({}, {})`; otherwise map
     `recipe_id -> output item kind` and `recipe_id -> structure kind` using the
     catalog entries' declared outputs. Never guess.
   - `build_completed_run_social_mobility_analysis(runner_result, *,
     runner_config, committed_events, run_id, organization_operation_rows=(),
     policy=None, window_end=None) -> SocialMobilityAnalysis`:
     1. Reject `committed_events` that are not an ordered non-empty sequence of
        committed events with `social_mobility_invalid_input`.
     2. `identity_map = build_social_mobility_identity_map(
        runner_config=runner_config, events=committed_events)`. Founder mapping
        is configuration (`AgentRunnerSpec.agent_id`/`.entity_id`), not world
        state; mid-run mapping comes from committed identity events.
     3. `genealogy = harvest_social_mobility_genealogy(committed_events,
        identity_map=identity_map, policy=policy)`.
     4. When `organization_operation_rows` is empty, harvest from
        `runner_result.organization_operation_ledgers` via
        `analysis.organization_operations.harvest_organization_operation_rows`;
        otherwise use the supplied rows.
     5. `outcomes = harvest_social_mobility_outcomes(committed_events,
        identity_map=identity_map,
        practical_knowledge_audits=runner_result.practical_knowledge_audits,
        teaching_audits=runner_result.teaching_audits,
        organization_operation_rows=rows,
        recipe_output_kinds=..., recipe_structure_kinds=..., policy=policy)`.
     6. Return `harvest_social_mobility_analysis(genealogy=genealogy,
        outcomes=outcomes, policy=policy, window_end=window_end)`.
2. In `src/experiments/collectors.py`, after the economic-inequality block,
   add a sibling guard. Activation is both conditions:
   - `events is not None` and at least one committed `KinshipEdgeRecorded`;
   - an outcome channel: any of `flags.organizations`, `flags.markets_credit`,
     `flags.infrastructure_networks`, `flags.supply_chains`, or
     `runner_config.durable_records`,
     `runner_config.structured_commitments`,
     `runner_config.subjective_valuation` not `None`, or non-empty
     `runner_result.practical_knowledge_audits` / `teaching_audits` /
     `organization_operation_ledgers`.
   Otherwise log `social_mobility_collector_disabled` at DEBUG and leave the
   input `None`.
3. Inside the guard: lazy-import the builder, call it with
   `window_end=max(ticks - 1, 0)`, inject with
   `replace(inputs, social_mobility_analysis=analysis)`, log
   `social_mobility_collector_injected rows=<n>` at INFO.
4. Wrap the whole block in `try/except Exception`, log
   `social_mobility_collector_failed code=<reason_code or type name>` at ERROR,
   and never re-raise. Do not include tokens, generations, or quantities in the
   log.

### Required Interfaces and Contracts
- Builder signature is stable and keyword-only after `runner_result`.
- Collector mutation uses `dataclasses.replace`; no other input field changes.
- Activation requires genealogy evidence; economic evidence alone is not
  enough.
- The builder reconstructs the identity map from `runner_config` plus committed
  events; it never accepts a pre-tokenized owner list.

### Requirement Evidence
- Original Request "Use V3 genealogy and V4 economic/institutional data".
- `src/simulation/runner_models.py:AgentRunnerSpec` (7471-7485) for the founder
  `agent_id`/`entity_id` mapping.
- `.ai-factory/ARCHITECTURE.md` Key Principle 4 and the collector isolation
  contract (`src/experiments/collectors.py:531-537`).

### Error Handling and Logging
- DEBUG input counts and enabled/disabled token.
- INFO `social_mobility_collector_injected`.
- WARN `social_mobility_missing_kinship`.
- ERROR `social_mobility_collector_failed` safe code only.

### Tests
- `tests/unit/test_social_mobility_completed_run.py`: real-shaped runner result
  and events, recipe mapping present/absent/mismatched, empty events rejected,
  window end honored, and a founder parent plus a mid-run child resolve into
  one token space.
- `tests/unit/test_social_mobility_collector.py`: enabled path injects
  non-empty analysis; no-kinship and no-outcome paths stay `None`; a forced
  builder exception leaves other metric inputs intact.

### Acceptance Criteria
- Kinship-free runs produce no social-mobility input.
- A malformed optional seam never fails a completed run.
- Real runner result fields are the only source of audits.
- Founder and mid-run owners are translated consistently before pairing.

### Verification
- `uv run pytest tests/unit/test_social_mobility_completed_run.py tests/unit/test_social_mobility_collector.py -q`
- Expected result: pass.

## Task 10: Add snapshot models, codec, paging, and ports

### Intent
Define the canonical, wall-clock-free sibling artifact and its pure read
contracts before any store or route exists.

### Implementation Steps
1. Create `src/simulation/social_mobility_models.py`:
   - `SOCIAL_MOBILITY_SNAPSHOT_VERSION = "social-mobility-snapshot-v1"`.
   - `SOCIAL_MOBILITY_POLICY_VERSION = "social-mobility.v1"`.
   - `SOCIAL_MOBILITY_PUBLICATION_PREFIX = "socmob-pub-"`.
   - `MAX_SOCIAL_MOBILITY_DOMAIN_ROWS = 4_096`.
   - `MAX_SOCIAL_MOBILITY_GENERATION_ROWS = 1_024`.
   - `MAX_SOCIAL_MOBILITY_LAG_ROWS = 2_048`.
   - `MAX_SOCIAL_MOBILITY_SNAPSHOT_BYTES = 8_388_608`.
   - `SocialMobilitySummaryRecord`: `domain_row_count`, `generation_row_count`,
     `lag_row_count`, `window_count`, `owner_count`, `generation_count`,
     `genealogy_edge_count`, `pair_count`, `resolved_pair_count`,
     `unresolved_pair_count`, `domain_available_count`, `coverage`,
     `evidence_coverage`, `domain_coverage`, `generation_coverage`,
     `truncated`.
   - `SocialMobilityDomainRecord`: window index/tick, domain, measure,
     pair counts, four quantized statistics, persistence, coverage,
     availability.
   - `SocialMobilityGenerationRecord`: window index/tick, generation index,
     owner count, pair count, comparable, three shares, availability.
   - `SocialMobilityLagRecord`: window index/tick, generation lag, pair count,
     comparable, three shares, availability.
   - `SocialMobilityCoverageRecord`: window index/tick, generation count, owner
     count, genealogy edge count, pair counts, domain available count,
     truncated, coverage.
   - `SocialMobilitySnapshot`: `run_id`, `schema_version`, `policy_version`,
     `summary`, `domains`, `generations`, `lags`, `coverage`, `digest`,
     `publication_id`; enforce row caps, duplicate identity rejection, and
     schema-version equality.
   - `empty_social_mobility_snapshot(run_id)` with `missing` coverage.
2. Create `src/simulation/social_mobility_codec.py`:
   `canonical_social_mobility_json`, `social_mobility_digest`,
   `compute_social_mobility_publication_id`,
   `finalize_social_mobility_snapshot`,
   `encode_social_mobility_snapshot`, `decode_social_mobility_snapshot`.
   Canonical bytes: `sort_keys=True`, `separators=(",", ":")`,
   `ensure_ascii=True`, `allow_nan=False`, one trailing newline. Digest covers
   the payload with blank digest/publication id. Decode rejects unknown or
   duplicate keys, version/run mismatch, digest mismatch, summary mismatch, and
   noncanonical re-encoding.
3. Create `src/simulation/social_mobility_paging.py`:
   - `SOCIAL_MOBILITY_PAGE_DEFAULT = 100`,
     `SOCIAL_MOBILITY_PAGE_MAX = 500`.
   - `SOCIAL_MOBILITY_PURPOSE_DOMAINS`: `domains` = all six; `economy` =
     `resources`, `productive_assets`; `human_capital` = `skills`,
     `educational_access`; `standing` = `social_influence`,
     `organization_roles`; `generations`, `coverage`, `summary` = empty.
   - `page_social_mobility(*, domains=(), generations=(), lags=(),
     coverage=None, purpose, limit=100, after_key="", window_index=None)`
     returning `(rows, next_key)`; sort keys are
     `(window_index, domain.value)` and `(window_index, generation_index)` and
     `(window_index, generation_lag)`.
4. Create `src/simulation/social_mobility_ports.py`:
   `SOCIAL_MOBILITY_CURSOR_TOKEN = "palimpsest.social_mobility.cursor.v1"`,
   `SOCIAL_MOBILITY_PURPOSES` (summary, domains, economy, human_capital,
   standing, generations, coverage), `SocialMobilityCursor`, and
   `social_mobility_query_fingerprint(*, run_id, publication_id, digest,
   purpose, limit, window_index)`, plus `SocialMobilityReader` and
   `SocialMobilityPublisher` protocols.
5. Export all public names from `src/simulation/__init__.py`.

### Required Interfaces and Contracts
- No wall-clock, host, or request field appears anywhere in the snapshot.
- Every record identity is `(window_index, domain)` or
  `(window_index, generation_index)` or `(window_index, generation_lag)`.
- Decode returns a finalized snapshot with recomputed digest.
- Paging rejects an `after_key` that is not in the filtered set.

### Requirement Evidence
- `src/simulation/economic_inequality_codec.py` canonical/digest contract.
- `.ai-factory/ARCHITECTURE.md` read-only analytical artifact rules.

### Error Handling and Logging
- ERROR `social_mobility_snapshot_invalid`, `_oversize`, `_keys`,
  `_corrupt`, `_version`, `_run_mismatch`, `_digest_mismatch`,
  `_summary_mismatch`, `_noncanonical`.
- DEBUG row counts and byte size; WARN `social_mobility_snapshot_truncated`.

### Tests
- `tests/unit/test_social_mobility_snapshot.py`: caps, duplicate rejection,
  empty snapshot, version mismatch.
- `tests/unit/test_social_mobility_codec.py`: canonical bytes, digest
  stability, encode/decode round-trip, noncanonical rejection.
- `tests/unit/test_social_mobility_paging.py`: purpose filter, window filter,
  limit bounds, strict after-key.
- `tests/unit/test_social_mobility_ports.py`: purpose validation, fingerprint
  binding, cursor bounds.

### Acceptance Criteria
- Two identical snapshots encode to identical bytes.
- Every decode failure uses a stable code.
- Paging never leaks a row outside the purpose or window filter.

### Verification
- `uv run pytest tests/unit/test_social_mobility_snapshot.py tests/unit/test_social_mobility_codec.py tests/unit/test_social_mobility_paging.py tests/unit/test_social_mobility_ports.py -q`
- Expected result: pass.

## Task 11: Add the atomic store and dual-gated settings

### Intent
Persist snapshots atomically with cumulative quotas and expose exactly two
settings that gate reads, without adding any runner or SQL schema.

### Implementation Steps
1. Create `src/persistence/social_mobility_filesystem.py`:
   - `SOCIAL_MOBILITY_STORE_VERSION = "social-mobility-store-v1"`.
   - `SocialMobilityPublisherOptions(max_publications=16,
     max_bytes=8_388_608)` with positive-int validation.
   - `create_social_mobility_publisher(root, *, options=None)` and
     `create_social_mobility_reader(root)`.
   - Follow `state.json` + `store.lock` + `flock` + `mkstemp` + `fsync` +
     `os.replace`; identical republish is idempotent; differing digest for the
     same publication id fails.
   - Enforce per-publication and cumulative bytes and publication count.
   - Error codes: `social_mobility_publication_exists`,
     `social_mobility_store_quota_exceeded`, `social_mobility_store_corrupt`,
     `social_mobility_store_invalid_run_id`,
     `social_mobility_store_invalid_publication_id`,
     `social_mobility_store_missing`.
2. In `src/infrastructure/settings.py`:
   - Add `social_mobility_root: Path | None = None`.
   - Add `social_mobility_cursor_key: SecretStr | None = Field(default=None,
     repr=False)`.
   - Add `validate_social_mobility_cursor_key` requiring ≥32 UTF-8 bytes when
     set.
   - Add `"social_mobility_root"` to the `empty_presentation_root_is_unset`
     validator list.
   - Add bootstrap flags `has_social_mobility_root`,
     `has_social_mobility_cursor_key`, `social_mobility_enabled` (root and
     key), `social_mobility_cursor_enabled` (key only).
3. Cumulative quota test must publish at least three artifacts in one root and
   assert the cumulative byte limit, not only one oversized payload.

### Required Interfaces and Contracts
- Store never logs paths, keys, digests, or payload bytes.
- Reader with no publication returns `social_mobility_store_missing`.
- Publisher never mutates a prior publication.

### Requirement Evidence
- `src/persistence/economic_inequality_filesystem.py` atomic/quota contract.
- `src/infrastructure/settings.py:empty_presentation_root_is_unset` blank-root
  rule.

### Error Handling and Logging
- INFO `social_mobility_store_ready` and publication accepted.
- WARN `social_mobility_store_quota`.
- ERROR corruption and safe codes only.

### Tests
- `tests/unit/test_social_mobility_store.py`: publish/read round-trip,
  idempotent republish, digest conflict, publication-count quota, cumulative
  byte quota across three publications, corrupt state, lock cleanup.
- `tests/unit/test_social_mobility_settings.py`: blank root becomes `None`,
  short cursor key rejected, bootstrap flags correct, secret not in repr.

### Acceptance Criteria
- Store is atomic, idempotent, quota-bounded, and corruption-safe.
- Both gate settings are required for `social_mobility_enabled`.

### Verification
- `uv run pytest tests/unit/test_social_mobility_store.py tests/unit/test_social_mobility_settings.py -q`
- Expected result: pass.

## Task 12: Compose and publish completed-run snapshots

### Intent
Map analysis rows to the canonical snapshot and publish it after successful
completion without a CLI producer, runner flag, or API write path.

### Implementation Steps
1. Create `src/experiments/social_mobility_publication.py`:
   - `SocialMobilityReceipt` with reason codes `published`,
     `publication_disabled`, `publication_missing`, `store_quota_exceeded`,
     `store_corrupt`.
   - `SocialMobilityHarvest(run_id, analysis, snapshot, receipt)`.
   - `compose_social_mobility_snapshot(analysis, *, run_id)`: map analysis
     rows only; derive `truncated` from partial coverage or truncation notices;
     include every row family in summary coverage; finalize digest and
     publication id; emit an empty finalized snapshot when there are no rows.
   - `publish_social_mobility_snapshot(snapshot, publisher)` mapping
     missing/disabled/quota/corrupt to receipts and never raising for
     publication failure.
   - `build_social_mobility_harvest_result(analysis, *, run_id, publisher)`.
2. Export the completed-run and publication builders from
   `src/experiments/__init__.py`.
3. No CLI producer, runner flag, or API write path is added.

### Required Interfaces and Contracts
- Snapshot rows derive only from `SocialMobilityAnalysis`.
- Publication id is deterministic from the frozen digest.
- Publication failure leaves scientific status untouched.

### Requirement Evidence
- `src/experiments/economic_inequality_publication.py` compose/publish contract.
- `.ai-factory/ARCHITECTURE.md` analysis-to-artifact bridge rule.

### Error Handling and Logging
- INFO `social_mobility_published rows=<n>`.
- WARN `social_mobility_publication_skipped`.
- ERROR `social_mobility_publication_failed` safe code only.

### Tests
- `tests/unit/test_social_mobility_publication.py`: row mapping, truncated
  derivation, empty analysis, all receipt reasons, no-raise behavior.

### Acceptance Criteria
- Compose→encode→decode is byte-identical.
- Every analysis row family appears in summary coverage.
- Publication failures are receipts, not exceptions.

### Verification
- `uv run pytest tests/unit/test_social_mobility_publication.py -q`
- Expected result: pass.

## Phase Risks and Mitigations
- Risk: collector guard runs before `runner_result` audits are available.
  Mitigation: place the guard after the economic block, where the runner result
  is already resolved, and test with the real result shape.
- Risk: snapshot growth from per-window domain rows.
  Mitigation: independent row caps plus the 8 MiB codec cap; a test publishes
  near-cap data.
- Risk: settings field name collision with existing roots.
  Mitigation: unique `social_mobility_*` names and a bootstrap-flag test.

## Phase Completion Checklist
- Every Task in this phase satisfies its acceptance criteria.
- `uv run pytest tests/unit/test_social_mobility_completed_run.py tests/unit/test_social_mobility_collector.py tests/unit/test_social_mobility_snapshot.py tests/unit/test_social_mobility_codec.py tests/unit/test_social_mobility_paging.py tests/unit/test_social_mobility_ports.py tests/unit/test_social_mobility_store.py tests/unit/test_social_mobility_settings.py tests/unit/test_social_mobility_publication.py -q` passes.
- `index.md` Task 9-12 checkboxes are updated after verification.
