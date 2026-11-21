# Phase 3: Publish bounded research artifacts and metrics

Plan: [index.md](index.md)  
Tasks: 6–8  
Depends on: Phase 2 / Task 5

## Objective

Make the detached result reproducibly inspectable without exposing scientific payloads or widening existing wire formats.

## Current-Code Evidence

| Path | Existing seam |
|---|---|
| `src/simulation/scientific_institutions_{models,codec,paging,ports}.py` | Canonical typed snapshot with read/publication ports and pure bounded page selection. |
| `src/experiments/scientific_institutions_publication.py`, `src/persistence/scientific_institutions_filesystem.py` | Trusted composer and atomic filesystem index; API never imports the producer. |
| `src/analysis/metric_service.py`, `src/analysis/specifications.py` | `MetricComputationInputs` optional science input and append-only specification catalog. |
| `src/api/app.py`, `src/api/routes/scientific_institutions.py`, `src/api/scientific_institutions_cursor.py`, `src/infrastructure/settings.py` | Startup attachment, `SUBJECTIVE_DEBUG`, purpose-bound cursors and paired settings. |

## Files to Change

| Path | Action | Responsibility |
|---|---|---|
| `src/simulation/science_diffusion_models.py`, `src/simulation/science_diffusion_codec.py`, `src/simulation/science_diffusion_paging.py`, `src/simulation/science_diffusion_ports.py` | Create | Closed read model and pure serialization/paging. |
| `src/experiments/science_diffusion_publication.py`, `src/persistence/science_diffusion_filesystem.py` | Create | Programmatic publication only; atomic bounded store. |
| `src/analysis/science_diffusion_metrics.py` | Create | Four descriptive metric families. |
| `src/analysis/metric_service.py`, `src/analysis/specifications.py` | Modify | Register optional calculation and versioned family IDs. |
| `src/api/routes/science_diffusion.py`, `src/api/science_diffusion_cursor.py` | Create | Read-only endpoints and cursor validation. |
| `src/api/app.py`, `src/api/routes/__init__.py`, `src/infrastructure/settings.py` | Modify | Reader wiring and paired opt-in settings. |

## Task 6: Implement canonical sidecar storage

1. Define `science-diffusion-snapshot-v1` and `science-diffusion.v1` with exact fields: version, policy_version, run_id, publication_id, input_revision, boundary_tick, coverage, versions, transmissions, changes, genealogy. Define exact typed section rows:
   - `coverage`: lane, start/end, state, reason, observed count.
   - `versions`: safe opaque owner/version keys, kind, revision index, first-observed boundary.
   - `transmissions`: safe optional from/to version keys, safe optional source/recipient owner keys, occurrence key, tick, confirmation boundary, stage, physical carrier keys, context flags and exclusions.
   - `changes`: change key, kind, from/to version keys where witnessed, optional carrier key, confirmation boundary, changed-field categories.
   - `genealogy`: transmission key, safe V3 node key, origin, relation and ambiguity state. Do not expose owner raw references, encoded claim text, claim or marker digests, model parameters, raw speech or private record content. Use run-qualified opaque keys hashed from qualified identities, not content alone. Validate foreign keys and chronology in both composer and verified decode; unknown links are explicit, not dangling.
2. `compose_science_diffusion_snapshot` in experiments accepts only successful or deliberately bounded-prefix captures, checks the run/config/assessment identity, and normalizes canonical output. Input revision hashes accepted normalized coverage + evidence, including availability, and is opaque. Publication ID is `sdf-` plus full SHA-256 of canonical document excluding publication ID; blob digest hashes the full canonical bytes. Sort each section by its clock then key; use compact sorted-key UTF-8 JSON without a trailing newline. Reject duplicate JSON keys, enum/type coercion, noncanonical bytes, dangling references, or changed IDs. In the composer and verified decoder enforce 8 MiB total, 16,384 rows total, at most 4,608 coverage rows and 16,384 rows per other individual section.
3. Implement `ScienceDiffusionSnapshotReader` and `ScienceDiffusionSnapshotPublisher` in `ScienceDiffusionFilesystem`. `science-diffusion-store-v1`: stage/fsync blob first; lock quota and idempotence checks plus atomic index replacement, then fsync directory. Readers open only a committed index and its referenced blob. Bound index reads to 64 KiB + one byte and blob reads to declared size + one byte after scope/path validation; reject symlinks and nonregular files. Verify strict index shape, size/digest and requested run/publication against decoded identities, then verify canonical bytes and recompute publication ID. Limits: 16 publications, 64 MiB cumulative indexed unique blob bytes per run; an exact repeat changes neither index nor latest. An unreferenced successfully staged blob after failed index replacement remains invisible; do not repair or delete on API reads. No SQL or backfill.

### Errors, tests, and acceptance

Stable codes `science_diffusion_snapshot_invalid`, `science_diffusion_store_corrupt`, `science_diffusion_publication_limit`; metadata-only logs, no raw data on failure. Test canonical twin bytes, duplicate JSON keys, bad rows/refs, correct hash with wrong embedded identity, hostile oversized index/blob, collision, aborted staged write, idempotence, cumulative quotas, and API-reader path isolation. Requirements: architecture §§ “Versioned Extension Contract” and V4-32 seam.

**Verification:** `uv run --frozen --python 3.12.14 pytest tests/unit/test_science_diffusion_snapshot.py tests/unit/test_science_diffusion_store.py -q`. A read returns only verified immutable snapshots.

## Task 7: Append four detached metric families

1. Add `science_diffusion_channels@1`, `science_diffusion_fidelity@1`, `science_diffusion_persistence@1`, and `science_diffusion_genealogy@1`. Append specification builders, names, exact scalar values and docs; catalog 271 → 275, no prior family changed. Channels: unique carrier occurrences by stage and per-lane counts (nonadditive context flags). Fidelity: comparable pairs as denominator, counts of observed mutation, divergent readings, and bound translations kept separate. Persistence: complete windows, scoped losses, confirmed observed loss, reuptake and independent rediscovery. Genealogy: eligible recipient carriers, exact links by origin, ambiguous and unresolved counts.
2. Add optional `MetricComputationInputs.science_diffusion_analysis`; it accepts a detached `DiffusionAssessment` via trusted experiment composition only. No input means no new documents. Required evidence: channels use science/speech/records plus the individual named channel for each contextual counter; fidelity uses comparable version/carrier fields plus translation for the translation count; persistence uses science/speech/records; genealogy uses knowledge genealogy and the associated carrier. Use covered eligible units over declared eligible units when both are countable, otherwise use observed/expected windows (not a fabricated eligible count). `PRESENT`: fully covered (including complete-empty observed zero). `PARTIAL`: meaningful surviving counts and required gaps. `UNKNOWN`: required evidence not observable; omit unsupported values. `ABSENT`: an individual named prerequisite is positively known inactive; never substitute unknown zero. Keep per-lane coverage in the sidecar even when family-level coverage is coarser. Use standard scalar metrics and input revision; no composite score. Update current count assertions via targeted search for `271`; preserve historical snapshots, historical pin prose and existing family offsets.

### Errors, tests, and acceptance

Reject wrong assessment type; metadata-only debug counts and family names. Tests: exact four families once, distinct denominators, incomplete coverage, one occurrence with multiple contexts, disabled metric computation emits no sidecars or placeholders. Requirements: original request; architecture §§ “Dependency Rules” and “Requirements for later changes.”

**Verification:** `uv run --frozen --python 3.12.14 pytest tests/unit/test_science_diffusion_metrics.py tests/unit/test_metric_specifications.py -q`.

## Task 8: Serve read-only snapshots and pinned pages

1. Pair `PALIMPSEST_SCIENCE_DIFFUSION_ROOT` with `PALIMPSEST_SCIENCE_DIFFUSION_CURSOR_KEY` (`SecretStr`, at least 32 UTF-8 bytes). Both absent: default off; exactly one or invalid key: fail settings validation; when both present attach reader/cursor through `api.app.create_app`. Share no signing purpose with other families.
2. Six GETs under `/v1/simulations/{run_id}/science-diffusion`: root summary (latest or explicit `publication_id`) and `/coverage`, `/versions`, `/transmissions`, `/changes`, `/genealogy`. Require `SUBJECTIVE_DEBUG` before semantic run/section/query validation or any storage read (use a route dependency; parse semantic cursor/query constraints after the gate). Follow existing capability headers. Read summary identity and publication IDs from one validated index selection, not separate latest/list calls. Section pages require explicit publication or valid cursor; default limit 50, max 100; return rows, publication/digest, section, `next_cursor`. Sign version, purpose/section, run, publication, digest, limit, exact stable last row key and expiration; reuse the project's injectable operational cursor clock and existing TTL convention. Resolve continuation to the exact key in the pinned section; missing key or changed request is 400, never a restart or redirect to latest.
3. Return 503 `science_diffusion_disabled`; explicit 404 codes `science_diffusion_run_not_found` / `science_diffusion_publication_not_found`; 400 for malformed, cross-purpose or changed query cursor; 410 expired (only after validating signature and scope); safe 500 for corrupt/unreadable artifacts. Selected indexed-but-missing blob is corrupt, not a missing publication. No route writes, repairs a store or imports analysis. Do not log cursor tokens, file paths or keys. Test paired settings through `create_app`, including the disabled composition, rather than assigning reader into `app.state`.

### Tests and acceptance

Add `tests/unit/test_science_diffusion_routes.py` for settings, authorization-before-read, absent/disabled/corrupt, pinned pages under new latest, cursor changes and expiration. Extend `tests/architecture/test_science_diffusion_boundaries.py` to forbid API/adapter/analysis cycles and any cognition, world, observer or client authority. Exercise the actual filesystem adapter via ASGI, not only a mocked reader.

**Verification:** `uv run --frozen --python 3.12.14 pytest tests/unit/test_science_diffusion_routes.py tests/architecture/test_science_diffusion_boundaries.py -q`.

## Phase Risks and Mitigations

- Read data may correlate owner behavior: it remains debug-gated and contains qualified tokens and closed metadata only.
- Filesystem quotas are fixed for the initial research envelope; cap and fail without displacing an earlier publication.

## Phase Completion Checklist

- Strict codec, quota, metric and paging tests pass; update progress only in `index.md`.
