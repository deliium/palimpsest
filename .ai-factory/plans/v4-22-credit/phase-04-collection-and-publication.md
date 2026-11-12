# Phase 4: Collection and Publication

Plan: [index.md](index.md)
Tasks: 12-14
Depends on: Phase 3 (analysis, metrics, owner input contract)

## Objective

Publish completed-run credit analysis as a canonical sibling snapshot, store it
atomically, and expose it through a read model. This phase adds no runner or
result schema, no SQL migration, no write pair, and no CLI producer.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/emergent_prices_models.py` | constants 33-46, summary and row records 73-545 | Exact canonical sibling snapshot pattern |
| `src/simulation/emergent_prices_codec.py` | payload 68-98, digest 100-110, finalize 113-130, strict decode 133-231 | Exact digest/publication/round-trip pattern |
| `src/simulation/emergent_prices_ports.py` | purposes 24-32, summary/publication/cursor 35-73, fingerprint 76-110, reader/publisher 113-130 | Exact purpose-bound cursor and port pattern |
| `src/simulation/emergent_prices_paging.py` | purposes 26-42, `page_emergent_prices` 45-86 | Exact stable paging pattern |
| `src/persistence/emergent_prices_filesystem.py` | store version 37, options 45-54, atomic write 90-101, lock 104-115, reader/publisher 118-293 | Exact atomic store and corruption behavior |
| `src/infrastructure/settings.py` | price fields 256-258, validator 463-470, summary 859-868 | Exact dual-gated settings pattern |
| `src/simulation/emergent_prices_export.py` | owner rows 50-120, `price_owner_export` remainder | Token-only owner export precedent |
| `src/experiments/emergent_prices_completed_run.py` | 34-165 | Completed-run composition and membership join |
| `src/experiments/emergent_prices_publication.py` | compose 100-265, publish 267-332, harvest 334-362 | Exact publication lifecycle |
| `src/experiments/collectors.py` | price collector 378-408 | Exact completed-run collector wiring |
| `src/simulation/runner_models.py` | result ledger field 6400 and validation 6902-6929 | Result export point (already extended in Phase 1) |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/simulation/credit_relationships_models.py` | create | Canonical `credit-relationships-snapshot-v1` records |
| `src/simulation/credit_relationships_codec.py` | create | Canonical encode/digest/finalize/strict decode |
| `src/simulation/credit_relationships_ports.py` | create | Purposes, cursor, fingerprint, reader/publisher |
| `src/simulation/credit_relationships_paging.py` | create | Purpose-bound stable paging |
| `src/simulation/credit_relationships_export.py` | create | Token-only owner export rows |
| `src/simulation/__init__.py` | modify | Public snapshot exports |
| `src/persistence/credit_relationships_filesystem.py` | create | Atomic `credit-relationships-store-v1` |
| `src/infrastructure/settings.py` | modify | Root/cursor-key settings and validators |
| `src/experiments/credit_relationships_completed_run.py` | create | Completed-run analysis composition |
| `src/experiments/credit_relationships_publication.py` | create | Snapshot compose/publish/harvest |
| `src/experiments/collectors.py` | modify | Inject credit analysis into `MetricServiceInputs` |
| `src/experiments/__init__.py` | modify | Public publication exports |
| `src/analysis/metric_service.py` | no change | Input field added in Phase 3 Task 10 |

## Task 12: Add credit snapshot models, codec, ports, and paging

### Intent

Define the canonical read model and its strict wire format before the store,
API, or UI depends on field names.

### Implementation Steps

1. Create `src/simulation/credit_relationships_models.py` with constants:
   `CREDIT_RELATIONSHIPS_SNAPSHOT_VERSION =
   "credit-relationships-snapshot-v1"`,
   `CREDIT_RELATIONSHIPS_SNAPSHOT_POLICY = "credit-relationships.v1"`,
   `CREDIT_RELATIONSHIPS_PUBLICATION_PREFIX = "cred-pub-"`,
   `CREDIT_RELATIONSHIPS_MAX_RELATIONSHIPS = 2_048`,
   `CREDIT_RELATIONSHIPS_MAX_CLAIMS = 4_096`,
   `CREDIT_RELATIONSHIPS_MAX_PERFORMANCES = 2_048`,
   `CREDIT_RELATIONSHIPS_MAX_DISTRIBUTIONS = 4_096`,
   `CREDIT_RELATIONSHIPS_MAX_COUNTERPARTIES = 1_024`,
   `CREDIT_RELATIONSHIPS_MAX_ALIGNMENTS = 4_096`,
   `CREDIT_RELATIONSHIPS_MAX_WINDOWS = 512`,
   `CREDIT_RELATIONSHIPS_ARTIFACT_MAX_BYTES = 8_388_608`.
2. Add records with exact fields:
   - `CreditSummaryRecord(window_tick, window_count, relationship_count,
     claim_count, performance_count, distribution_count, counterparty_count,
     alignment_count, claim_event_count, transfer_event_count,
     evidence_coverage, owner_coverage, relationship_coverage,
     performance_coverage, distribution_coverage, counterparty_coverage,
     alignment_coverage, coverage, truncated)`;
   - `CreditRelationshipRecord(relationship_id, window_index, owner_token,
     counterparty_token, direction, anchor_token, principal_kind,
     principal_quantity, repayment_kind, repayment_quantity,
     repayment_ratio_milli, due_tick, condition, collateral_kind,
     collateral_quantity, status, confidence_milli, expectation_milli,
     trust_milli, claim_count, coverage)`;
   - `CreditClaimRecord(claim_id, window_index, event_token, actor_token,
     counterparty_token, act, direction, anchor_token, principal_kind,
     principal_quantity, repayment_kind, repayment_quantity, paid_quantity,
     opened_tick, due_tick, condition, collateral_kind, collateral_quantity,
     confidence_milli, coverage)`;
   - `CreditPerformanceRecord(performance_id, window_index, anchor_token,
     claim_count, repay_claim_count, default_claim_count, forgive_claim_count,
     dispute_claim_count, renegotiate_claim_count, observed_transfer_count,
     repaid_quantity, principal_quantity, repayment_quantity, outcome,
     coverage)`;
   - `CreditDistributionRecord(distribution_id, window_index, principal_kind,
     repayment_kind, sample_source, sample_count, min_ratio_milli,
     p25_ratio_milli, median_ratio_milli, p75_ratio_milli, max_ratio_milli,
     iqr_milli, dispersion_milli, bin_shares_milli, status, coverage)`;
   - `CreditCounterpartyRecord(counterparty_token, window_index,
     relationship_count, owner_count, claim_count, repay_claim_count,
     default_claim_count, forgive_claim_count, dispute_claim_count,
     observed_transfer_count, coverage)`;
   - `CreditAlignmentRecord(alignment_id, window_index, owner_token,
     anchor_token, alignment, owner_status, analytical_outcome,
     owner_paid_quantity, declared_repayment_quantity,
     observed_transfer_count, gap_milli, coverage)`.
3. Validate every token with `require_stable_id`, every count with
   `require_exact_nonneg_int`, every enum with a closed set, and
   `due_tick: int | None` with non-negative value when present.
4. Add `CreditRelationshipsSnapshot(run_id, schema_version, policy_version,
   summary, relationships, claims, performances, distributions,
   counterparties, alignments, digest="", publication_id="")`. Validate row
   types, unique ids within each family, row caps, `bin_shares_milli` length 5
   and sum 1000 when `status=available`, and quantile ordering.
5. Add `empty_credit_relationships_snapshot(run_id)` with every coverage
   `missing` and zero counts.
6. Create `credit_relationships_codec.py` with:
   - `_row_payload` converting enums to `.value` and tuples to lists;
   - canonical payload keys in this exact order: run_id, schema_version,
     policy_version, summary, relationships, claims, performances,
     distributions, counterparties, alignments, digest, publication_id;
   - `credit_relationships_artifact_digest(snapshot)` over canonical JSON with
     blank digest/publication id, `sort_keys=True`, compact separators,
     `ensure_ascii=True`, `allow_nan=False`, one trailing newline, prefix
     `sha256:`;
   - `finalize_credit_relationships_snapshot(snapshot)` assigning digest and
     `cred-pub-<16 hex>`;
   - `encode_credit_relationships_snapshot(snapshot) -> bytes` with the final
     newline and max-byte guard;
   - `decode_credit_relationships_snapshot(data) -> CreditRelationshipsSnapshot`
     with duplicate-key rejection, exact schema/policy match, digest
     verification, unknown-field rejection, and row validation.
7. Create `credit_relationships_ports.py` with
   `CREDIT_RELATIONSHIPS_CURSOR_TOKEN =
   "palimpsest.credit_relationships.cursor.v1"`,
   purposes `summary`, `relationships`, `claims`, `performances`,
   `distributions`, `counterparties`, `alignment`;
   `CreditRelationshipsSummary`, `CreditRelationshipsPublication`,
   `CreditRelationshipsCursor`, `credit_relationships_query_fingerprint`,
   `CreditRelationshipsReader`, `CreditRelationshipsPublisher`.
   Cursor validates purpose, non-empty fingerprint, `window_index` in
   `[0, 512)`, and tuple after-key.
8. Create `credit_relationships_paging.py` with
   `CREDIT_RELATIONSHIPS_PAGE_DEFAULT = 100`,
   `CREDIT_RELATIONSHIPS_PAGE_MAX = 500`, purpose-to-row-type map, sort keys:
   - relationships: `(window_index, relationship_id)`;
   - claims: `(window_index, claim_id)`;
   - performances: `(window_index, performance_id)`;
   - distributions: `(window_index, distribution_id)`;
   - counterparties: `(window_index, counterparty_token)`;
   - alignment: `(window_index, alignment_id)`.
   Enforce row type, window filter, stable `>` after-key, and limit.
9. Export all public symbols from `simulation/__init__.py`.

### Required Interfaces and Contracts

```python
CREDIT_RELATIONSHIPS_SNAPSHOT_VERSION = "credit-relationships-snapshot-v1"
CREDIT_RELATIONSHIPS_SNAPSHOT_POLICY = "credit-relationships.v1"
CREDIT_RELATIONSHIPS_PUBLICATION_PREFIX = "cred-pub-"

def encode_credit_relationships_snapshot(snapshot) -> bytes: ...
def decode_credit_relationships_snapshot(data: bytes) -> CreditRelationshipsSnapshot: ...
def finalize_credit_relationships_snapshot(snapshot) -> CreditRelationshipsSnapshot: ...
```

- No wall-clock field, mutable default, or non-canonical float exists.
- The snapshot is a sibling artifact, not a runner/result/replay/SQL schema.
- `due_tick=None` serializes as JSON null and round-trips.

### Requirement Evidence

- Canonical snapshot/codec/ports/paging precedent:
  `src/simulation/emergent_prices_models.py`,
  `src/simulation/emergent_prices_codec.py`,
  `src/simulation/emergent_prices_ports.py`,
  `src/simulation/emergent_prices_paging.py`.
- Sibling artifacts never alter scientific schemas:
  `.ai-factory/ARCHITECTURE.md` V3-37 and V4-20 seams.

### Error Handling and Logging

- Encode/decode failures raise `ValueError("credit_relationships_snapshot_invalid")`
  or `"credit_relationships_snapshot_oversize"`.
- `WARN credit_relationships_snapshot_truncated family=%s cap=%s` logs counts.
- Never log run ids as tokens, anchors, owner tokens, item kinds, or ratios.

### Tests

- `tests/unit/test_credit_relationships_snapshot.py`: record validation; caps;
  empty snapshot; quantile/bin invariants; unique ids.
- `tests/unit/test_credit_relationships_codec.py`: canonical bytes; digest
  stability; publication id; round-trip; duplicate key/unknown field/schema
  mismatch/digest mismatch/oversize rejection; no wall-clock.
- `tests/unit/test_credit_relationships_paging.py`: each purpose; window filter;
  after-key; default/max limits; invalid purpose/limit/window.

### Acceptance Criteria

- A finalized snapshot round-trips to identical canonical bytes.
- The digest ignores the digest/publication fields and changes when any row
  changes.
- Decoding fails closed on any malformed or oversized payload.
- No row family accepts more than its cap.

### Verification

- `uv run pytest tests/unit/test_credit_relationships_snapshot.py tests/unit/test_credit_relationships_codec.py tests/unit/test_credit_relationships_paging.py -q`
- `uv run mypy src/simulation/credit_relationships_models.py src/simulation/credit_relationships_codec.py`
- Expected: all pass.

## Task 13: Add the atomic filesystem store and dual-gated settings

### Intent

Persist publications atomically with quotas and expose no reader unless both
gates are configured. Corruption must fail closed.

### Implementation Steps

1. Create `src/persistence/credit_relationships_filesystem.py`:
   - `CREDIT_RELATIONSHIPS_STORE_VERSION = "credit-relationships-store-v1"`;
   - `CreditRelationshipsPublisherOptions(max_publications=16,
     max_bytes=8_388_608)`;
   - `_STATE_FILE="state.json"`, `_LOCK_FILE="store.lock"`;
   - `_token` regex `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$` plus `..`, `/`, `\`
     rejection;
   - `_empty_state()`, `_load_state()` with JSON/version/shape validation and
     `ValueError("credit_relationships_store_corrupt")`;
   - `_atomic_write` using `mkstemp`, `fsync`, `os.replace`;
   - `_locked` using `fcntl.flock`;
   - `_summary(snapshot)` mapping the summary record;
   - `create_credit_relationships_reader(root)` and
     `create_credit_relationships_publisher(root, options=None)`;
   - publish writes `state.json` with publication id, digest, byte size, and
     snapshot payload; idempotent republish of the same digest returns the
     existing publication; quota/byte overflow raises
     `"credit_relationships_store_quota"`.
2. In `src/infrastructure/settings.py`, add:
   - `credit_relationships_root: Path | None = None`;
   - `credit_relationships_cursor_key: SecretStr | None = Field(default=None)`;
   - validator `validate_credit_relationships_cursor_key` requiring at least 32
     UTF-8 bytes;
   - summary booleans `has_credit_relationships_root`,
     `has_credit_relationships_cursor_key`,
     `credit_relationships_enabled`,
     `credit_relationships_cursor_enabled`.
3. Do not add a database URL, migration, table, or column.
4. Do not import persistence from simulation or analysis.

### Required Interfaces and Contracts

```python
CREDIT_RELATIONSHIPS_STORE_VERSION = "credit-relationships-store-v1"

def create_credit_relationships_reader(root: Path) -> CreditRelationshipsReader: ...
def create_credit_relationships_publisher(
    root: Path, options: CreditRelationshipsPublisherOptions | None = None
) -> CreditRelationshipsPublisher: ...
```

- Store layout: `<root>/<run_id>/state.json` plus `<root>/<run_id>/store.lock`.
- A corrupt state file raises exactly `credit_relationships_store_corrupt`.
- Quota overflow raises exactly `credit_relationships_store_quota`.
- Publication is atomic and idempotent for an identical digest.

### Requirement Evidence

- Atomic store/corruption/quota precedent:
  `src/persistence/emergent_prices_filesystem.py:37-293`.
- Dual-gated settings precedent:
  `src/infrastructure/settings.py:256-258, 463-470, 859-868`.
- No migration without a proven indexed-inspection need:
  `.ai-factory/ARCHITECTURE.md` "Requirements for later changes" 5.

### Error Handling and Logging

- Corrupt state logs `ERROR credit_relationships_store_corrupt` and raises.
- Quota logs `WARN credit_relationships_store_quota` and raises.
- Publish success logs
  `INFO credit_relationships_publication_completed stored=true`.
- Never log run ids, digests as payload surrogates, or snapshot content.

### Tests

- `tests/unit/test_credit_relationships_store.py`: publish/read/list; atomic
  replace; idempotent republish; quota; byte cap; corrupt state; traversal
  token rejection; reader on empty root.
- `tests/unit/test_credit_relationships_settings.py`: unset gates; root only;
  cursor key only; both; short key rejected; summary booleans.

### Acceptance Criteria

- No reader or cursor codec is created unless both settings are present.
- A crash between temp write and replace never exposes a partial state file.
- Corrupt or oversized stores fail closed with stable code strings.
- Republishing the same snapshot does not grow publication count or bytes.

### Verification

- `uv run pytest tests/unit/test_credit_relationships_store.py tests/unit/test_credit_relationships_settings.py -q`
- Expected: all pass.

## Task 14: Compose and publish completed-run credit snapshots

### Intent

Map one completed run's owner ledgers and committed events into analysis,
snapshot, and publication receipt, and inject the analysis into the experiment
metric collector. Publication stays programmatic and post-completion.

### Implementation Steps

1. Create `src/simulation/credit_relationships_export.py`:
   - `CreditOwnerRow(owner_token, window_index, anchor_token,
     counterparty_token, direction, principal_kind_token, principal_quantity,
     repayment_kind_token, repayment_quantity, paid_quantity, due_tick,
     condition, collateral_kind, collateral_quantity, status,
     confidence_milli, level, trust_milli, expectation_milli, claim_count,
     promise_count, first_tick, last_tick, coverage)`;
   - `credit_owner_export(ledgers)` reading `CreditRelationshipLedger` rows and
     emitting neutral strings/integers only;
   - compute `counterparty_token` as `credpeer-` plus the first 16 hex of
     SHA-256 over `row.counterparty_id.value`; the raw id is never exported;
   - no counterparty ids, item ids, raw claims, or digests.
2. Create `src/experiments/credit_relationships_completed_run.py`:
   - `build_completed_run_credit_relationships_analysis(runner_result, *,
     committed_events, run_id, policy=None, input_revision="rev-run",
     window_end=None)`;
   - require `committed_events`; read
     `runner_result.credit_relationship_ledgers`; call `credit_owner_export`;
   - map `CreditOwnerRow` to `CreditOwnerInput` and call
     `harvest_credit_relationships_analysis`;
   - log `WARN credit_completed_run_missing_ledgers` when absent and
     `DEBUG credit_completed_run owners=%s events=%s coverage=%s` otherwise.
3. Create `src/experiments/credit_relationships_publication.py`:
   - `CreditRelationshipsReceipt(run_id, publication_id, digest, stored,
     reason_code, coverage, notices)`;
   - `CreditRelationshipsHarvest(run_id, analysis, snapshot, receipt)`;
   - `compose_credit_relationships_snapshot(analysis, *, run_id)` mapping every
     family with `_latest` stable prefix caps and `truncated` flag;
   - `publish_credit_relationships_snapshot(snapshot, publisher)` returning
     `publication_missing`, `publication_disabled`, `store_quota_exceeded`,
     `store_corrupt`, or `published` without raising for disabled/missing;
   - `build_credit_relationships_harvest_result(runner_result, *,
     committed_events, run_id, publisher=None, policy=None,
     input_revision="rev-run", window_end=None)`.
4. In `src/experiments/collectors.py`, after the price collector, add:
   - `credit_enabled = events is not None and
     runner_config.v4_capability_flags.markets_credit and
     runner_config.structured_commitments is not None`;
   - build the completed-run analysis and
     `replace(inputs, credit_relationships_analysis=...)`;
   - log `DEBUG credit_relationships_collector_injected coverage=%s` or
     `ERROR credit_relationships_collector_failed code=%s`;
   - no effect when disabled.
5. In `src/experiments/__init__.py`, export the three public functions and
   receipt/harvest types.
6. Do not wire publication into the runner or a CLI; callers may invoke
   `build_credit_relationships_harvest_result` after successful completion.

### Required Interfaces and Contracts

```python
def build_credit_relationships_harvest_result(
    runner_result: object,
    *,
    committed_events: Sequence[object] | None,
    run_id: str,
    publisher: CreditRelationshipsPublisher | None = None,
    policy: CreditRelationshipsAnalysisPolicy | None = None,
    input_revision: str = "rev-run",
    window_end: int | None = None,
) -> CreditRelationshipsHarvest: ...
```

- Publication never changes scientific status.
- Missing events reject analysis; missing publisher returns a receipt, not an
  error.
- The collector is composition-only and never runs inside simulation/API.

### Requirement Evidence

- Publication lifecycle precedent:
  `src/experiments/emergent_prices_publication.py:100-362`.
- Collector pattern: `src/experiments/collectors.py:378-408`.
- Programmatic post-completion rule: V4-20/V4-21 seam documentation.

### Error Handling and Logging

- `ERROR credit_relationships_analysis_missing_events`.
- `WARN credit_snapshot_partial coverage=%s`.
- `INFO credit_relationships_publication_completed stored=%s
  reason_code=published`.
- Never log owner tokens, anchors, item kinds, ratios, or digests as payload.

### Tests

- `tests/unit/test_credit_relationships_export.py`: token-only rows; no
  counterparty ids; cap/coverage; empty ledgers.
- `tests/unit/test_credit_relationships_completed_run.py`: missing events
  rejected; missing ledgers warn; owner rows injected; window end.
- `tests/unit/test_credit_relationships_publication.py`: compose mapping,
  truncation, disabled/missing/quota/corrupt receipts, idempotent publish.
- `tests/unit/test_credit_relationships_collector.py`: enabled/disabled
  injection and failure isolation.

### Acceptance Criteria

- A completed run with no credit ledgers still yields an explicit missing
  analysis and a `publication_missing` receipt.
- Disabled publication writes nothing and leaves the run status unchanged.
- Every snapshot row maps one-to-one from an analysis row.
- No collector failure aborts metric emission.

### Verification

- `uv run pytest tests/unit/test_credit_relationships_export.py tests/unit/test_credit_relationships_completed_run.py tests/unit/test_credit_relationships_publication.py tests/unit/test_credit_relationships_collector.py -q`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: snapshot shape drifts from analysis rows.
  Mitigation: explicit field-by-field mapping and one-to-one row tests.
- Risk: store corruption surfaces as a 500 without a safe code.
  Mitigation: stable corruption/quota codes and API mapping in Phase 5.
- Risk: publication runs inside the simulation.
  Mitigation: experiments-only composition; no simulation import of
  experiments.
- Risk: owner export leaks counterparty ids.
  Mitigation: token-only export tests and a forbidden-field scan.

## Phase Completion Checklist

- Every Task 12-14 in this phase satisfies its acceptance criteria.
- Focused snapshot/codec/store/publication tests pass.
- `index.md` checkboxes are updated only after verified completion.
