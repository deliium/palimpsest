# Phase 4: Collection and Publication

Plan: [index.md](index.md)
Tasks: 12-14
Depends on: Phase 3 / Tasks 9-10

## Objective

Publish completed-run accounting ledgers as a canonical sibling snapshot through
an atomic, quota-bounded, idempotent filesystem store gated by two
`PALIMPSEST_` settings. No runner, result, replay, SQL, or CLI schema changes.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/simulation/credit_relationships_models.py` | snapshot version 33-35; policy 36; publication prefix 37; snapshot 469-533; caps | Canonical document template. |
| `src/simulation/credit_relationships_codec.py` | digest 94; finalize 109; encode 122; decode 155 | Canonical JSON, duplicate-key rejection, byte-identical re-encode. |
| `src/simulation/credit_relationships_paging.py` | defaults 23-24; `page_credit_relationships` 45 | Purpose-bound paging with `window_index`. |
| `src/simulation/credit_relationships_ports.py` | cursor token 23; purposes 26-34; cursor 61; fingerprint 78; reader/publisher 116/129 | Cursor binds `window_index` and query fingerprint. |
| `src/simulation/credit_relationships_export.py` | owner row 56; export 126 | Token-only owner export pattern. |
| `src/persistence/credit_relationships_filesystem.py` | store version 37; quotas 43-46; atomic write 85-96; lock 99-112; idempotent 154-163; corruption 243-280 | Atomic store template. |
| `src/experiments/credit_relationships_publication.py` | receipt 64; harvest 79; compose 100; publish 311; entrypoint 379 | Post-completion publication template. |
| `src/experiments/credit_relationships_completed_run.py` | 28 | Completed-run analysis bridge. |
| `src/experiments/__init__.py` | 233-239, 692-694, 858-860 | Export pattern. |
| `src/infrastructure/settings.py` | credit root 260; cursor 261-263; validator 478-487; dual gate 885-897 | Dual-gate settings template. |
| `src/api/app.py` | credit attach 599-625; include 838 | Reader wiring point used by Phase 5. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/simulation/accounting_ledgers_models.py` | create | Snapshot document and row families. |
| `src/simulation/accounting_ledgers_codec.py` | create | Canonical encode/decode/digest/finalize. |
| `src/simulation/accounting_ledgers_paging.py` | create | Purpose-bound paging. |
| `src/simulation/accounting_ledgers_ports.py` | create | Cursor and reader/publisher protocols. |
| `src/simulation/accounting_ledgers_export.py` | create | Token-only owner export. |
| `src/simulation/__init__.py` | modify | Public exports. |
| `src/persistence/accounting_ledgers_filesystem.py` | create | Atomic store. |
| `src/infrastructure/settings.py` | modify | Dual-gate settings and validators. |
| `src/experiments/accounting_ledgers_publication.py` | create | Compose/publish/entrypoint. |
| `src/experiments/accounting_ledgers_completed_run.py` | create | Completed-run bridge. |
| `src/experiments/__init__.py` | modify | Public exports. |

---

## Task 12: Add accounting snapshot models, codec, ports, and paging

### Intent

Define the canonical sibling artifact and its read contract: versioned document,
strict codec, digest/publication id, purpose-bound cursor that binds
`window_index`, and deterministic paging.

### Implementation Steps

1. `src/simulation/accounting_ledgers_models.py`:
   - `ACCOUNTING_LEDGERS_SNAPSHOT_VERSION = "accounting-ledgers-snapshot-v1"`.
   - `ACCOUNTING_LEDGERS_POLICY_VERSION = "accounting-ledgers.v1"`.
   - `ACCOUNTING_LEDGERS_PUBLICATION_PREFIX = "acct-pub-"`.
   - Row dataclasses: `AccountingSnapshotEntry`, `AccountingSnapshotRecord`,
     `AccountingSnapshotCondition`, `AccountingSnapshotFlow`,
     `AccountingSnapshotCounterparty`, `AccountingSnapshotAlignment`.
     Every row carries a deterministic id token (`acce-`, `accr-`, `accf-`,
     `acccp-`, `acca-`) plus a `window_index`; conditions are keyed by
     `(condition, window_index)`.
   - `AccountingLedgersSummary` with per-family counts and coverage.
   - `AccountingLedgersSnapshot` with `run_id`, `schema_version`,
     `policy_version`, `summary`, six row tuples, `digest=""`,
     `publication_id=""`; no wall-clock field.
   - Caps: entries 4_096, records 2_048, conditions 1_024, flows 4_096,
     counterparties 1_024, alignments 4_096, windows 512, artifact max bytes
     8_388_608.
2. `src/simulation/accounting_ledgers_codec.py`:
   - `accounting_ledgers_artifact_digest`, `finalize_accounting_ledgers_snapshot`,
     `encode_accounting_ledgers_snapshot`, `decode_accounting_ledgers_snapshot`.
   - Canonical JSON (`sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=True`,
     `allow_nan=False`) plus trailing newline; UTF-8.
   - Decode rejects duplicate keys, wrong top-level key set, schema/policy
     mismatch, digest mismatch, non-canonical re-encode, and > 8 MiB.
   - Decode recomputes every per-family count and `truncated` from the row
     tuples and rejects a disagreement with
     `accounting_ledgers_snapshot_summary_mismatch`; a hand-edited summary can
     never be published.
3. `src/simulation/accounting_ledgers_ports.py`:
   - `ACCOUNTING_LEDGERS_CURSOR_TOKEN = "palimpsest.accounting_ledgers.cursor.v1"`.
   - Purposes: `summary`, `entries`, `records`, `conditions`, `flows`,
     `counterparties`, `alignment`.
   - `AccountingLedgersCursor(purpose, fingerprint, after_key, window_index)`.
   - `accounting_ledgers_query_fingerprint(...)` binds `run_id`,
     `publication_id`, `digest`, `purpose`, `limit`, `window_index`.
   - Reader/publisher protocols.
4. `src/simulation/accounting_ledgers_paging.py`:
   - `ACCOUNTING_LEDGERS_PAGE_DEFAULT = 100`,
     `ACCOUNTING_LEDGERS_PAGE_MAX = 500`.
   - `page_accounting_ledgers(rows, *, purpose, limit, after_key, window_index)`:
     filter by `window_index` when present, sort by `(window_index, id)`, cut the
     deterministic prefix, return the next key.
   - `window_index` validated `0..511`; a cursor for another window is rejected
     by the caller (Phase 5).
5. `src/simulation/accounting_ledgers_export.py`:
   - `AccountingOwnerRow` with `owner_token`, `entry_token`, `record_token`,
     `entry_kind`, `direction`, `item_kind`, `quantity`, `assessment`,
     `confidence_milli`, `first_tick`, `last_tick`, `window_index`.
   - `accounting_owner_export(ledgers)` hashes owner/counterparty ids to tokens;
     never imports `analysis`.

### Required Interfaces and Contracts

- Snapshot has no wall-clock field and no objective truth/balance field.
- Digest is `"sha256:" + sha256(canonical_payload)`; publication id is
  `"acct-pub-" + digest_without_prefix[:16]`.
- Cursor binds `window_index`; a cross-window cursor is invalid.
- All row ids are deterministic and owner-local tokens.

### Requirement Evidence (when reconciliation applies)

- Original Request; `.ai-factory/ARCHITECTURE.md` — sibling artifacts are not
  runner/result schemas.
- `src/simulation/credit_relationships_models.py` and codec.

### Error Handling and Logging

- Non-canonical payload → `accounting_ledgers_snapshot_noncanonical`.
- Oversize → `accounting_ledgers_snapshot_oversize`.
- Dup key → `accounting_ledgers_snapshot_duplicate_key`.
- `INFO accounting_ledgers_snapshot_finalized rows=%s` (total only).

### Tests

Create `tests/unit/test_accounting_ledgers_snapshot.py`,
`tests/unit/test_accounting_ledgers_codec.py`,
`tests/unit/test_accounting_ledgers_paging.py`, and
`tests/unit/test_accounting_ledgers_export.py`:
- canonical round-trip and byte equality;
- digest/publication id stability;
- duplicate key, wrong schema, digest mismatch, non-canonical, oversize;
- summary/row disagreement rejected with the summary-mismatch code;
- paging filter/sort/cursor at boundaries;
- export contains tokens only and no raw owner/item ids.

Command: `uv run pytest tests/unit/test_accounting_ledgers_snapshot.py tests/unit/test_accounting_ledgers_codec.py tests/unit/test_accounting_ledgers_paging.py tests/unit/test_accounting_ledgers_export.py -q`.

### Acceptance Criteria

- The snapshot round-trips canonically with no wall-clock field.
- Cursors bind the window filter.
- Owner export leaks no raw identifiers.

### Verification

- The command above — expected: pass.

---

## Task 13: Add the atomic filesystem store and dual-gated settings

### Intent

Persist publications atomically and idempotently with quotas and corruption
safety, and expose two default-off settings that fail closed when either half is
missing.

### Implementation Steps

1. `src/persistence/accounting_ledgers_filesystem.py`:
   - `ACCOUNTING_LEDGERS_STORE_VERSION = "accounting-ledgers-store-v1"`.
   - Files: `state.json`, `store.lock`, `<publication_id>.json`.
   - `_atomic_write` via `tempfile.mkstemp` + `os.fsync` + `os.replace`.
   - `fcntl.flock(LOCK_EX)` around publish.
   - `AccountingLedgersPublisherOptions(max_publications=16, max_bytes=8_388_608)`.
   - Idempotent republish when bytes match; conflicting bytes raise
     `accounting_ledgers_publication_exists`.
   - `_load_state` maps bad JSON/version/shape to
     `accounting_ledgers_store_corrupt`.
   - `read_snapshot(run_id, publication_id=None)` selects the lexicographically
     last publication when unspecified.
2. `src/infrastructure/settings.py`:
   - `accounting_ledgers_root: Path | None = None` beside 260.
   - `accounting_ledgers_cursor_key: SecretStr | None` beside 261-263.
   - `validate_accounting_ledgers_cursor_key` beside 478-487 requiring at least
     32 UTF-8 bytes.
   - bootstrap fields beside 885-897:
     `has_accounting_ledgers_root`, `has_accounting_ledgers_cursor_key`,
     `accounting_ledgers_enabled`, `accounting_ledgers_cursor_enabled`.
3. No default root path; both default `None`.
4. Log `INFO accounting_ledgers_store_ready` (no path) and
   `WARN accounting_ledgers_store_corrupt`.

### Required Interfaces and Contracts

```python
ACCOUNTING_LEDGERS_STORE_VERSION = "accounting-ledgers-store-v1"

class AccountingLedgersPublisherOptions:
    max_publications: int = 16
    max_bytes: int = 8_388_608
```

Invariants:
- A crash never leaves a partial `state.json`.
- Same publication id + identical bytes is a no-op.
- Quota exhaustion raises `accounting_ledgers_store_quota`.
- Settings are frozen and `extra="forbid"`.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/RULES.md` axiom 7 (`PALIMPSEST_` prefix, no import-time secrets)
  and axiom 8 (fail closed).
- `src/persistence/credit_relationships_filesystem.py`.

### Error Handling and Logging

- Quota: `accounting_ledgers_store_quota`; map to a receipt reason later.
- Corruption: `accounting_ledgers_store_corrupt`.
- Never log the root path, cursor key, or publication payload.

### Tests

Create `tests/unit/test_accounting_ledgers_store.py` and
`tests/unit/test_accounting_ledgers_settings.py`:
- publish/read, idempotent republish, conflicting bytes;
- quota exceeded; corrupt state; interrupted-write simulation (temp file left
  behind does not corrupt state);
- settings defaults off; root-only off; cursor-only off; both on; short key
  rejected; env names parsed.

Command: `uv run pytest tests/unit/test_accounting_ledgers_store.py tests/unit/test_accounting_ledgers_settings.py -q`.

### Acceptance Criteria

- Store is atomic, quota-bounded, idempotent, and corruption-safe.
- Both settings default off and fail closed independently.

### Verification

- The command above — expected: pass.
- `uv run lint-imports` — expected: 25 kept, 0 broken.

---

## Task 14: Compose and publish completed-run accounting snapshots

### Intent

Provide the only analysis-to-artifact bridge: compose the snapshot from a
completed-run analysis and publish it programmatically, with truthful receipts
and no runner/CLI coupling.

### Implementation Steps

1. `src/experiments/accounting_ledgers_completed_run.py`:
   - `build_completed_run_accounting_ledgers_analysis(*, run_id, events, owner_rows=(), policy=None)`
     delegating to Task 9.
2. `src/experiments/accounting_ledgers_publication.py`:
   - `AccountingLedgersReceipt` with `run_id`, `publication_id`, `digest`,
     `stored`, `reason_code`, `coverage`, `notices`; reason codes `published`,
     `publication_disabled`, `publication_missing`, `store_quota_exceeded`,
     `store_corrupt`.
   - `AccountingLedgersHarvest` with `run_id`, `analysis`, `snapshot`, `receipt`.
   - `compose_accounting_ledgers_snapshot(analysis, *, run_id)`: map analysis
     rows to snapshot rows with stable prefixes, set `truncated`, finalize.
   - `publish_accounting_ledgers_snapshot(snapshot, publisher)`: `coverage ==
     "missing"` → `publication_missing`; no publisher → `publication_disabled`;
     `ValueError` containing `quota` → `store_quota_exceeded`; containing
     `corrupt` → `store_corrupt`; never raises for disabled/missing.
   - `build_accounting_ledgers_harvest_result(...)` programmatic entrypoint.
3. `src/experiments/__init__.py`: export the public symbols.
4. Do not wire publication into the runner, CLI, or API.
5. Log `INFO accounting_ledgers_published stored=%s reason=%s` (no ids).

### Required Interfaces and Contracts

- Publication is post-completion only; scientific status is unchanged.
- A disabled caller writes nothing.
- A missing analysis produces `publication_missing`, not a fabricated artifact.
- Store errors are reported as receipt reason codes, not exceptions.

### Requirement Evidence (when reconciliation applies)

- Original Request; `.ai-factory/ARCHITECTURE.md` — `experiments` is the only
  analysis-to-artifact bridge.
- `src/experiments/credit_relationships_publication.py:100-379`.

### Error Handling and Logging

- Never raise for `publication_disabled`/`publication_missing`.
- Map quota/corruption to receipt codes.
- Never log run ids, publication payloads, or coverage row contents.

### Tests

Create `tests/unit/test_accounting_ledgers_publication.py` and
`tests/unit/test_accounting_ledgers_completed_run.py`:
- compose from a complete/partial/missing analysis;
- publish with a real fake publisher and with `None`;
- quota and corruption mappings;
- idempotent republish through the store;
- entrypoint returns a harvest and does not mutate scientific status.

Command: `uv run pytest tests/unit/test_accounting_ledgers_publication.py tests/unit/test_accounting_ledgers_completed_run.py -q`.

### Acceptance Criteria

- Publication is programmatic, post-completion, and truthful.
- No runner/CLI/API coupling is introduced.

### Verification

- The command above — expected: pass.
- `rg -n "accounting_ledgers_publication" src/simulation src/api src/research_runner` — expected: no output.

## Phase Risks and Mitigations

- Risk: a snapshot field implies objective book value.
  Mitigation: forbidden-name tests and a codec key-set assertion.
- Risk: publication leaks into the runner and changes scientific status.
  Mitigation: grep-based verification and a publication receipt that never
  touches `SimulationResult`.
- Risk: quota/corruption errors escape as exceptions.
  Mitigation: explicit receipt mapping and tests for both.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
