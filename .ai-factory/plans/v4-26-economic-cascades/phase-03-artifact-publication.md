# Phase 3: Completed-Run Inputs, Snapshot, Store, and Publication

Plan: [index.md](index.md)
Tasks: 9-12
Depends on: Phase 2 (Tasks 5-8)

## Objective

Bridge completed runs into the cascade analysis, define the canonical bounded
`economic-cascades-snapshot-v1` document with store `economic-cascades-store-v1`,
and publish it atomically after scientific completion. Publication stays
programmatic: no CLI producer and no runner flag is added.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/supply_chain_completed_run.py` | `supply_chain_recipe_specs` (50-83), `supply_chain_infrastructure` (111-129), `build_completed_run_supply_chain_analysis` (181-228) | Exact completed-run recipe/infrastructure extraction to reuse |
| `src/experiments/collectors.py` | `assemble_arm_metric_bundle` (190), economic gate (474-519), social gate (538-584) | Feature gate and `replace(inputs, ...)` injection pattern |
| `src/simulation/economic_inequality_models.py` | version constant (26), caps (29-33), record classes (112-299) | Snapshot model template |
| `src/simulation/economic_inequality_codec.py` | canonical JSON (71-97), digest (100-110), publication id (113-119), size cap (135-147), strict decode (186-209) | Codec template |
| `src/simulation/economic_inequality_ports.py` | cursor token/purposes (18-29), cursor (32-51), fingerprint (54-75), protocols (78-85) | Ports template |
| `src/simulation/economic_inequality_paging.py` | default/max (16-17), purpose map (22-47), page function (59-100) | Paging template |
| `src/persistence/economic_inequality_filesystem.py` | store version (37), atomic write (90-101), flock (104-115), idempotency (147-163), quotas (164-175), reader (205-227) | Atomic store template |
| `src/experiments/economic_inequality_publication.py` | compose (73-162), publish receipts (165-225), harvest result (228-237) | Publication bridge template |
| `src/infrastructure/settings.py` | root/key fields (268-275), root validators (317-339), key validators (514-534), bootstrap (958-982) | Dual-gate settings pattern |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/economic_cascades_completed_run.py` | create | Completed-run builder and detached input extraction |
| `src/experiments/collectors.py` | modify | Feature gate and analysis injection |
| `src/experiments/__init__.py` | modify | Export completed-run and publication symbols |
| `src/simulation/economic_cascades_models.py` | create | Snapshot records, caps, `empty_*` |
| `src/simulation/economic_cascades_codec.py` | create | Canonical encode/decode, digest, publication id |
| `src/simulation/economic_cascades_paging.py` | create | Purpose-bound paging |
| `src/simulation/economic_cascades_ports.py` | create | Cursor, fingerprint, reader/publisher protocols |
| `src/simulation/__init__.py` | modify | Re-export snapshot symbols |
| `src/persistence/economic_cascades_filesystem.py` | create | Atomic filesystem store |
| `src/infrastructure/settings.py` | modify | Root, cursor key, validators, bootstrap flags |
| `src/experiments/economic_cascades_publication.py` | create | Compose, publish, harvest receipt |
| `tests/unit/test_economic_cascades_completed_run.py` | create | Real event/recipe fixture bridge |
| `tests/unit/test_economic_cascades_collector.py` | create | Gate and injection |
| `tests/unit/test_economic_cascades_snapshot.py` | create | Records and caps |
| `tests/unit/test_economic_cascades_codec.py` | create | Round-trip, canonical, corruption |
| `tests/unit/test_economic_cascades_paging.py` | create | Cursors and window binding |
| `tests/unit/test_economic_cascades_ports.py` | create | Fingerprints and purposes |
| `tests/unit/test_economic_cascades_store.py` | create | Atomicity, idempotency, quotas |
| `tests/unit/test_economic_cascades_settings.py` | create | Dual gate and validation |
| `tests/unit/test_economic_cascades_publication.py` | create | Receipt mapping |

## Task 9: Wire completed-run inputs and collector injection

### Intent
Feed the analysis from a finished run without reading private world state. The
bridge must supply detached recipe specs, operational and destroyed
infrastructure facts, route transitions, and labor joins from the runner result
and committed events only.

### Implementation Steps
1. Create `src/experiments/economic_cascades_completed_run.py`:
   - `cascade_recipe_specs(runner_result)` delegates to
     `supply_chain_recipe_specs(runner_result.runner_config)` and returns its
     tuple unchanged; never rebuild a catalog.
   - `cascade_infrastructure_facts(runner_result)` reads
     `runner_result.final_infrastructure_assets` and maps each asset to
     `(location_token, kind_token, operational)` where `operational` is true
     only when status is `operational`; destroyed and damaged assets are
     retained with `operational=False`.
   - `cascade_route_facts(committed_events)` maps each
     `RouteConditionChanged` to `(origin_token, destination_token, status)`,
     keeping the latest row per ordered edge.
   - `cascade_labor_joins(committed_events, stages)` maps each actor token that
     appears as a stage actor to the sorted recipe ids it completed; emit
     `(actor_token, recipe_ids)` tuples. This join stays private to the builder
     and is never serialized. The completed-run fixture must assert that the
     same agent's stage `actor_token` equals its `Died.body_id`; if the tokens
     diverge, drop the join and report `unresolved` instead of inventing an
     identity map.
   - `cascade_supply_stages(committed_events, recipe_specs)` calls
     `supply_evidence_from_events` with the existing detached policy and returns
     the stage observations; no skill, organization, or infrastructure argument
     is fabricated.
   - `build_completed_run_economic_cascades_analysis(runner_result=None, *,
     committed_events, run_id, recipe_specs=None, stages=None,
     infrastructure=None, routes=None, labor_joins=None, policy=None,
     window_tick=None) -> EconomicCascadesAnalysis`:
     raises `ValueError("economic_cascades_requires_events")` when
     `committed_events is None`; validates `run_id` with `require_stable_id`;
     fills missing inputs from the helpers above; calls
     `harvest_economic_cascades_analysis`.
2. In `src/experiments/collectors.py::assemble_arm_metric_bundle`, add a gate
   after the social-mobility block:
   - require `committed_events` is not `None` and the runner config carries the
     owned `supply_chains` V4 flag (read through the existing public runner
     config field; do not import simulation internals);
   - lazily import the builder, call it with the run id and events, and
     `replace(inputs, economic_cascades_analysis=analysis)`;
   - on exception, log WARN `economic_cascades_collection_failed` and continue
     with no analysis.
3. Export the builder and helpers from `src/experiments/__init__.py`.
4. Do not add a runner root field, per-agent key, CLI producer, or runner flag.

### Required Interfaces and Contracts
- The bridge reads only `runner_result.runner_config`,
  `runner_result.final_infrastructure_assets`, and committed events. The declared
  `ProductionCatalog` is read only through `supply_chain_recipe_specs` and
  immediately mapped to `SupplyRecipeSpec`.
- Recipe structure still comes from `SupplyRecipeSpec`; no `ProductionRecipe`
  import.
- Actor tokens in stage observations and `Died.body_id` must share the objective
  entity token space; the fixture proves it. No agent-id translation or identity
  map is invented, and divergent tokens drop the join.
- Collection failure never aborts metric assembly.

### Requirement Evidence
- Original Request objective evidence sources.
- `src/experiments/supply_chain_completed_run.py:40-83,181-228`.
- `.ai-factory/ARCHITECTURE.md` analysis isolation and off-path rules.

### Error Handling and Logging
- INFO `economic_cascades_completed_run windows=<n> chains=<n>`.
- WARN `economic_cascades_collection_failed`,
  `economic_cascades_recipe_catalog_mismatch`,
  `economic_cascades_missing_events`.
- ERROR `economic_cascades_completed_run_invalid` with a code only.
- Never log event payloads, recipe contents, tokens, or infrastructure rows.

### Tests
- `tests/unit/test_economic_cascades_completed_run.py`: a v56 fixture with a
  supply-chain catalog, real events including depletion/closure/destruction/
  death/tool crafting; recipe extraction; destroyed asset retained as
  non-operational; route latest-per-edge; labor join sorted; the same agent's
  stage `actor_token` equals its `Died.body_id`; divergent tokens drop the join;
  missing events raises.
- `tests/unit/test_economic_cascades_collector.py`: gate off → no analysis;
  gate on → injected analysis; builder failure → WARN and unchanged bundle.

### Acceptance Criteria
- A completed run with supply-chain evidence produces a non-empty analysis.
- A run without `supply_chains` produces no cascade input and no metric docs.
- No private world object is read.

### Verification
- `uv run pytest tests/unit/test_economic_cascades_completed_run.py tests/unit/test_economic_cascades_collector.py -q`
- Expected result: pass.

## Task 10: Add snapshot models, codec, paging, and ports

### Intent
Define the canonical, digest-addressed, wall-clock-free snapshot and the bounded
read contract so the API and store never invent fields.

### Implementation Steps
1. Create `src/simulation/economic_cascades_models.py`:
   - `ECONOMIC_CASCADES_SNAPSHOT_VERSION = "economic-cascades-snapshot-v1"`,
     `ECONOMIC_CASCADES_POLICY_VERSION = "economic-cascades.v1"`,
     `ECONOMIC_CASCADES_PUBLICATION_PREFIX = "ecasc-"`,
     `MAX_ECONOMIC_CASCADES_STATUS_ROWS = 1_024`,
     `MAX_ECONOMIC_CASCADES_CHAIN_ROWS = 2_048`,
     `MAX_ECONOMIC_CASCADES_BYTES = 8_388_608`.
   - Frozen validation records:
     `EconomicCascadeSummaryRecord` (`window_tick`, `window_count`,
     `coverage`, `availability`, `event_count`, `disruption_count`,
     `stage_count`, `dependency_edge_count`, `chain_count`,
     `linked_chain_count`, `disruption_kind_count`, `max_depth`),
     `EconomicCascadeDisruptionRecord` (`window_index`, `window_tick`, `kind`,
     `disruption_count`, `magnitude_total`, `subject_count`, `coverage`),
     `EconomicCascadeDependencyRecord` (`window_index`, `window_tick`,
     `upstream_token`, `downstream_recipe_token`, `kind`, `depth`,
     `evidence_count`),
     `EconomicCascadeChainRecord` (`chain_token`, `window_index`, `window_tick`,
     `disruption_kind`, `depth`, `lag_windows`, `shortfall_share_milli`,
     `state`, `coverage`),
     `EconomicCascadePropagationRecord` (`window_index`, `window_tick`,
     `disruption_kind`, `chain_count`, `linked_chain_count`,
     `unlinked_chain_count`, `unresolved_chain_count`, `mean_depth_milli`,
     `mean_lag_milli`, `downstream_stage_count`, `coverage`, `availability`),
     `EconomicCascadeCoverageRecord` (`window_index`, `window_tick`,
     `window_count`, `event_count`, `disruption_count`, `stage_count`,
     `dependency_edge_count`, `labor_join_count`, `chain_count`,
     `linked_chain_count`, `truncated`, `coverage`, `availability`).
   - `EconomicCascadesSnapshot` (`snapshot_version`, `policy_version`,
     `run_id`, `generated_from_tick`, `summary`, `disruptions`,
     `dependencies`, `chains`, `propagation`, `coverage`, `internal_digest`,
     `publication_id`) with row-count caps and no wall-clock field.
   - `empty_economic_cascades_snapshot(run_id=...)`.
2. Create `src/simulation/economic_cascades_codec.py`:
   - Canonical JSON with sorted keys, compact separators, no floats;
     reject non-canonical input before decode.
   - `finalize_economic_cascades_snapshot(snapshot)` blanks
     `internal_digest`/`publication_id`, computes SHA-256 over the canonical
     body, sets `internal_digest`, sets `publication_id =
     "ecasc-" + digest[:16]`.
   - `encode_economic_cascades_snapshot(snapshot)` enforces the byte cap and
     returns UTF-8 text; `decode_economic_cascades_snapshot(payload)` rejects
     unknown fields, version mismatch, digest mismatch, and oversize payload
     with closed codes.
3. Create `src/simulation/economic_cascades_paging.py`:
   - `DEFAULT_ECONOMIC_CASCADES_LIMIT = 100`,
     `MAX_ECONOMIC_CASCADES_LIMIT = 500`.
   - `ECONOMIC_CASCADES_PURPOSE_KEYS` maps purposes `disruptions`,
     `dependencies`, `chains`, `propagation`, and `coverage` to the snapshot row
     tuples; `windows` projects `(window_index, window_tick)` from the coverage
     rows; `summary` is not paged.
   - `page_economic_cascades_rows(snapshot, *, purpose, window_index=None,
     limit=100, after=None)` returns `(rows, next_key)` deterministically.
4. Create `src/simulation/economic_cascades_ports.py`:
   - `ECONOMIC_CASCADES_CURSOR_TOKEN = "economic-cascades-cursor"`,
     `ECONOMIC_CASCADES_CURSOR_PURPOSES` tuple, `EconomicCascadesCursor`
     (`purpose`, `window_index`, `after`, `query_fingerprint`),
     `economic_cascades_query_fingerprint(...)`, and
     `EconomicCascadesReader` / `EconomicCascadesPublisher` protocols.
5. Re-export the public snapshot, codec, paging, and port symbols from
   `src/simulation/__init__.py`.

### Required Interfaces and Contracts
- Snapshot bytes are canonical and digest-addressed; no wall-clock field.
- Decode is strict: unknown fields, wrong version, or digest mismatch fail
  closed.
- Paging is pure and bound to the snapshot; a cursor never outlives its
  query fingerprint.
- Row caps are enforced in the model, not only in the codec.

### Requirement Evidence
- Original Request "Provide dependency/cascade analytics" (read model).
- `src/simulation/economic_inequality_models.py:26-339` and
  `src/simulation/economic_inequality_codec.py:71-209`.

### Error Handling and Logging
- WARN `economic_cascades_snapshot_capped`,
  `economic_cascades_snapshot_oversize`.
- ERROR `economic_cascades_snapshot_invalid` with a code only.
- Never log row contents, digests as payload surrogates, or run ids beyond the
  existing safe field.

### Tests
- `tests/unit/test_economic_cascades_snapshot.py`: record validation, caps,
  empty snapshot, no wall-clock key.
- `tests/unit/test_economic_cascades_codec.py`: canonical round-trip, digest
  stability, tamper rejection, unknown field rejection, oversize rejection.
- `tests/unit/test_economic_cascades_paging.py`: purpose keys, limit bounds,
  window binding, deterministic next key.
- `tests/unit/test_economic_cascades_ports.py`: fingerprint sensitivity to
  purpose/window/limit, cursor validation.

### Acceptance Criteria
- Snapshot round-trips byte-identically after one finalize.
- Corrupt or widened payloads are rejected, never partially read.
- No paging purpose can read another purpose's rows.

### Verification
- `uv run pytest tests/unit/test_economic_cascades_snapshot.py tests/unit/test_economic_cascades_codec.py tests/unit/test_economic_cascades_paging.py tests/unit/test_economic_cascades_ports.py -q`
- Expected result: pass.

## Task 11: Add the atomic store and dual-gated settings

### Intent
Persist publications safely and keep the reader off unless both settings are
present, matching every other V4 detached surface.

### Implementation Steps
1. Create `src/persistence/economic_cascades_filesystem.py`:
   - `ECONOMIC_CASCADES_STORE_VERSION = "economic-cascades-store-v1"`,
     `STATE_FILE = "state.json"`, `LOCK_FILE = "store.lock"`.
   - `EconomicCascadesPublisherOptions(max_publications=16,
     max_bytes=8_388_608)` with range validation.
   - Atomic commit: write a temp file in the run directory, `fsync`, then
     `os.replace`; the internal `state.json` is the publication index and the
     external copy is `root/<run_id>/<publication_id>.json`.
   - `flock` around state reads/writes.
   - Idempotency: same publication id and digest → `stored=False`; same id with
     a different digest → `economic_cascades_publication_exists`.
   - Quotas: per-snapshot byte cap, publication count, cumulative bytes;
     closed codes `economic_cascades_store_quota_exceeded`,
     `economic_cascades_store_corrupt`, `economic_cascades_publication_missing`.
   - Reader selects the latest publication when no id is supplied; corruption
     or missing state fails closed.
   - Public factories `economic_cascades_store_reader(root, ...)` and
     `economic_cascades_store_publisher(root, options=...)`.
2. In `src/infrastructure/settings.py`, add
   `economic_cascades_root: Path | None = None` and
   `economic_cascades_cursor_key: SecretStr | None = None`; register the root in
   the empty-string→`None` validator and the key in a ≥32-byte validator; add
   `has_economic_cascades_root`, `has_economic_cascades_cursor_key`,
   `economic_cascades_enabled`, and `economic_cascades_cursor_enabled` to
   `bootstrap_fields()`.
3. Keep `extra="forbid"` and the `PALIMPSEST_` prefix; no secret is required at
   import time.

### Required Interfaces and Contracts
- Environment names are `PALIMPSEST_ECONOMIC_CASCADES_ROOT` and
  `PALIMPSEST_ECONOMIC_CASCADES_CURSOR_KEY`.
- Store writes are atomic and lock-protected; a partial write is never visible.
- Settings default to `None`; the feature is off unless both are set.

### Requirement Evidence
- `src/persistence/economic_inequality_filesystem.py:37-250`.
- `src/infrastructure/settings.py:268-275,317-339,514-534,958-982`.

### Error Handling and Logging
- INFO `economic_cascades_store_published publications=<n> bytes=<n>` on
  successful commit.
- WARN `economic_cascades_store_quota_exceeded`,
  `economic_cascades_publication_exists`.
- ERROR `economic_cascades_store_corrupt` with a code only.
- Never log paths, digests, publication ids, or payloads.

### Tests
- `tests/unit/test_economic_cascades_store.py`: atomic replace, idempotent
  republish, conflict on differing digest, count quota, byte quota, corrupt
  state, missing run, lock contention simulation.
- `tests/unit/test_economic_cascades_settings.py`: both unset, root only, key
  only, both set, short key rejection, empty root normalization, bootstrap
  flags.

### Acceptance Criteria
- Republishing the same digest is a no-op.
- A corrupt state file never yields rows.
- Both settings are required for `economic_cascades_enabled`.

### Verification
- `uv run pytest tests/unit/test_economic_cascades_store.py tests/unit/test_economic_cascades_settings.py -q`
- Expected result: pass.

## Task 12: Compose and publish completed-run snapshots

### Intent
Map the analysis to the snapshot and publish it after completion with explicit,
closed receipts. Publication is a caller decision; a disabled publication leaves
scientific status untouched.

### Implementation Steps
1. Create `src/experiments/economic_cascades_publication.py`:
   - `compose_economic_cascades_snapshot(analysis, *, run_id,
     generated_from_tick=None) -> EconomicCascadesSnapshot` mapping:
     summary from analysis counts; disruptions from episodes; dependencies from
     edges (generic upstream tokens and recipe tokens copied verbatim); chains
     from chain rows; propagation from propagation rows; coverage from the
     coverage row. Call `finalize_economic_cascades_snapshot`.
   - `publish_economic_cascades_snapshot(*, analysis, run_id, reader=None,
     publisher=None, enabled=True, options=None) -> EconomicCascadesPublicationReceipt`
     with statuses `publication_missing`, `publication_disabled`,
     `store_quota_exceeded`, `store_corrupt`, `published`. A disabled or
     missing analyzer writes nothing and reports the status; it never raises for
     an environment gate.
   - `build_economic_cascades_harvest_result(analysis, publication)` returning
     the analysis plus the publication receipt.
2. Call `publish_economic_cascades_snapshot` only from the programmatic
   completed-run path; do not add a CLI command, runner flag, or API write.
3. Export the public functions from `src/experiments/__init__.py`.

### Required Interfaces and Contracts
- Snapshot composition is pure; publication is the only side effect.
- Scientific status is never changed by publication.
- A quota or corruption failure is reported, never retried silently.
- No wall-clock value enters the snapshot.

### Requirement Evidence
- `src/experiments/economic_inequality_publication.py:73-237`.
- Original Request "Provide dependency/cascade analytics" (artifact publication).

### Error Handling and Logging
- INFO `economic_cascades_published publication=<status>` (status token only).
- WARN `economic_cascades_publication_disabled`,
  `economic_cascades_publication_quota_exceeded`.
- ERROR `economic_cascades_publication_failed` with a code only.
- Never log digests, ids, rows, or byte counts tied to subjects.

### Tests
- `tests/unit/test_economic_cascades_publication.py`: compose mapping, all five
  receipt statuses, disabled path writes nothing, quota path writes nothing,
  idempotent republish.

### Acceptance Criteria
- A composed snapshot validates and carries no wall-clock field.
- Every failure maps to one closed receipt status.
- Publication is never invoked by simulation or API code.

### Verification
- `uv run pytest tests/unit/test_economic_cascades_publication.py -q`
- Expected result: pass.

## Phase Risks and Mitigations
- Risk: the completed-run bridge reads world state or private runtime objects.
  Mitigation: it may read only the run's declared `ProductionCatalog` from
  runner config, final infrastructure assets, and committed events; a boundary
  test rejects `world._*` and `simulation._*` imports.
- Risk: store corruption returns partial rows.
  Mitigation: strict decode before row access and a corruption test per layer.
- Risk: publication side effects leak into scientific status.
  Mitigation: receipts are returned, not raised; a test asserts the runner
  result is unchanged.

## Phase Completion Checklist
- Tasks 9-12 acceptance criteria met.
- Targeted Phase 3 tests pass.
- No CLI producer, runner flag, or write path exists.
- `index.md` Tasks 9-12 checkboxes are updated after verification.
