[← Development](development.md) · [Back to README](../README.md) · [Persistence →](persistence.md)

# Long-Horizon Scalability

Measured scale behavior for multi-generation V3 runs, bounded historical
queries and read-only clients. The plan is `v3-43-long-horizon-scalability`;
production source revision for the measurements below is `3930540` (2026-10-27),
with benchmark instrumentation and composition evidence added after it. The
2026-10-28 remediation note in the plan index records the retirement and cadence
measurements produced against base revision `1c5c18c`.

> **No universal maximum is claimed.** The verified envelope stops at the
> workloads and horizons that actually completed with exact correctness. The
> latest 100k evidence-rich and flags-off lanes did not complete under the
> configured budget; the generational 100k lane completed ticks but ended with
> zero living owners, which is a throughput result, not sustained capacity.

## V4 scale contract

V4-01 adds a deterministic partition/budget contract in `simulation.scale` and an
opt-in measurement lane, but **no measured capacity**. Partition mapping only is
measured; see [V4 scale contract](v4-scale.md). The envelope statements on this
page remain the only verified throughput evidence.

## Verified Envelope

| Lane | Horizon | Status | Repetitions | Completed ticks | Verified boundary |
| --- | ---: | --- | ---: | ---: | ---: |
| Generational | 10k | `verified` | 4 | 10,000 | 9,999 |
| Evidence-rich | 10k | `verified` | 4 | 10,000 | 9,999 |
| Flags-off control | 10k | `tested_incomplete` | 0 | 2,225 | 2,224 |
| Generational | 100k | `completed_ticks_population_extinct` | 0 | 100,000 | 99,999 |
| Evidence-rich | 100k | `tested_incomplete` | 0 | 90,765 | 90,764 |
| Flags-off control | 100k | `tested_incomplete` | 0 | 8,158 | 8,157 |

The latest 2026-10-30 V3-44 re-run retained generational/evidence-rich 10k
completion and a truthfully incomplete flags-off 10k control at 2,189 ticks.
The generational 100k lane completed 100,000 ticks in 1,196.68 s with 5
cohorts, 9 births, 9 deaths and 0 living owners at the final boundary; do not
read that as long-term survival or dense 100k support. Evidence-rich stopped at
90,765 ticks and the flags-off control at 8,158. Historical-query measurements
passed separately.

The earlier 10k generational repetitions used the identical scientific run ID
`v3-43-generational-ticks-10000-seed-23` in separate disposable databases.
Observed wall times were 130.8–146.3 s; evidence-rich was 166.0–182.1 s.
Completed 10k artifacts report 5 cohorts, 9 births, 9 deaths, 5,241/5,243
events, 71,838 SQL calls, 40,204 SQL rows and **0 cognitive invocations after
death**. The earlier 100k attempts reached their 300 s budget; no dense-100k support,
throughput promise or population capacity follows from any 100k run.

Two additional repetitions per 10k lane failed before execution with
`worker_error_RunnerConstructionError` (four failed artifacts total). They are
retained under `task19-10k-rep3` and surfaced in the envelope as
`failed_attempts`/`failure_reasons`; they are setup failures, not scientific
results, and do not invalidate the four completed repetitions.

`measured_through_horizon=10000` is verified-through coverage, not a hard
maximum. Process RSS enforcement was `unenforced`; SQL byte counters and the
workload's event/snapshot byte fields were unavailable.

### Provenance

The envelope row revision is derived from each measurement artifact's
`environment.source_revision` when the artifacts agree. The retained 10k
artifacts predate this capture, so their rows use the envelope revision
`3930540` and carry an explicit limitation. New supervised runs record
`PALIMPSEST_SOURCE_REVISION` and the PostgreSQL server version; the worker
reports `unavailable` rather than failing if the version query cannot run.
The remediation composition and cadence evidence were produced at `1c5c18c`.

## Composition Trials

The envelope carries explicit off/on composition rows separate from capacity
rows. They do not certify a horizon or throughput.

| Name | Off | On | Scope |
| --- | --- | --- | --- |
| Retirement | 9 resident owners retained, 0 retired, 0 frozen bytes | 0 resident owners, 9 retired, 7,367,840 B reachable frozen-state estimate | 10,000 ticks, single paired trial |
| Capture spool | default in-memory capture; capture-off performs no spool I/O | append-only filesystem spool, streamed canonical publication | test-level |
| Physical paging | sealed v1 lineage/civilization publications | v2 authenticated directories, bounded roots and deep pages | test-level |

The retirement pair reused the same seed, configuration and scenario
fingerprints; events, births, deaths and cohort counters were identical
(`5,241` events, `9` births, `9` deaths). Frozen bytes are a capped
reachable-object lower bound, not an RSS measurement. Spool and paging rows cite
focused test node identifiers and are labelled `test-level`; they are not
benchmark measurements.

## Checkpoint Cadence

`tests/integration/test_long_run_checkpoints.py` writes
`task9-cadence/checkpoint-cadence.json` for a 600-tick deterministic history.
All variants produced identical projection hashes and `1,855` events.

| Cadence | Snapshots | Run ms | Snapshot read ms | Seek ms |
| ---: | ---: | ---: | ---: | ---: |
| off | 1 | 12,856 | 2.46 | 717.0 |
| 100 | 7 | 12,457 | 3.88 | **70.0** |
| 500 | 2 | 11,976 | 1.26 | 468.1 |
| 1000 | 1 | 11,760 | 1.27 | 873.1 |

Cadence `100` is recommended for seek-heavy research workloads in this
scenario: it reduced seek latency by an order of magnitude with comparable run
time. The deterministic default policy is unchanged; this is one measured
scenario, not a universal tuning rule.

## Historical Query Measurements

Traceable JSON artifacts are written beneath the caller's
`PALIMPSEST_SCALE_BENCH_OUTPUT` root (see the commands below) and are not
committed; regenerate them by re-running the lanes.

| Lane | Workload | Result |
| --- | --- | --- |
| Synthetic log | 10,100 events, 41 pages at limit 250 | write 1,554.8 ms; paging 1,057.4 ms; 30 warm indexed late-event lookups p50 0.58 ms / p95 1.37 ms |
| Generational query | 30 warm alternating seeks + replay | cold seek 2.98 ms; replay p50 4.30 ms / p95 16.90 ms |
| Lineage paging | 3,000 nodes / 2,999 edges | publish 8,824.9 ms; 30 catalogue pages in 3,036.0 ms; adjacency 34.3 ms, 20 physical reads against a 128-read budget |

The synthetic and lineage lanes are not scientific simulations. Query numbers
are backend/domain measurements, not browser frame times.

## Reproduction

Prerequisites:

- A disposable PostgreSQL/pgvector database whose name contains
  `palimpsest_test`, exposed as `PALIMPSEST_TEST_DATABASE_URL`.
  The supervised driver creates a uniquely named `palimpsest_test_*` database
  per repetition and migrates it, so repeated runs keep identical scientific
  run IDs in separate storage; the configured role needs `CREATE DATABASE` and
  pgvector extension privileges.
- Explicit wall-time, RAM and disk budgets. Use separate databases or output
  namespaces for repetitions and baseline/candidate comparison.
- Pinned Godot 4.7.2 from `clients/godot-observer/export/pins.env` for client
  protocol tests.
- A built current API/observer image and Playwright for real-browser evidence.

```bash
# 10k supervised lanes (about 10 minutes at a 300 s lane budget).
PALIMPSEST_TEST_DATABASE_URL="$PALIMPSEST_TEST_DATABASE_URL" \
PALIMPSEST_SCALE_BENCH_TICKS=10000 \
PALIMPSEST_SCALE_BENCH_LANES='v1-control,generational,evidence-rich,historical-query' \
PALIMPSEST_SCALE_BENCH_TIMEOUT_SECONDS=300 \
PALIMPSEST_SCALE_BENCH_OUTPUT=/tmp/opencode/v3-43-scale/task19-10k \
PALIMPSEST_SOURCE_REVISION="$(git rev-parse --short HEAD)" \
uv run pytest -m 'integration and scale' \
  tests/benchmarks/test_v3_long_horizon.py -q --cov-report=

# 100k attempt. Expect truthful timed_out lanes; do not convert them to support.
PALIMPSEST_SCALE_BENCH_TICKS=100000 \
PALIMPSEST_SCALE_BENCH_OUTPUT=/tmp/opencode/v3-43-scale/task19-100k \
uv run pytest -m 'integration and scale' \
  tests/benchmarks/test_v3_long_horizon.py -q --cov-report=

# Query/lineage measurements (writes JSON artifacts).
PALIMPSEST_SCALE_BENCH_OUTPUT=/tmp/opencode/v3-43-scale/task19-historical \
uv run pytest -m 'integration and scale' \
  tests/benchmarks/test_v3_historical_queries.py -q --cov-report=

# Historical safety acceptance.
uv run pytest -m integration tests/integration/test_v3_historical_query_safety.py \
  --cov=api --cov=simulation --cov=persistence --cov-report=term

# Retirement composition pair (active/resident vs frozen owners).
PALIMPSEST_TEST_DATABASE_URL="$PALIMPSEST_TEST_DATABASE_URL" \
PALIMPSEST_RETIREMENT_TICKS=10000 \
PALIMPSEST_RETIREMENT_OUTPUT=/tmp/opencode/v3-43-scale/task5-retirement \
uv run pytest -m 'integration and scale' \
  tests/benchmarks/test_retirement_composition.py -q --cov-report=

# Checkpoint cadence sweep (writes task9-cadence/checkpoint-cadence.json).
PALIMPSEST_SCALE_BENCH_OUTPUT=/tmp/opencode/v3-43-scale \
uv run pytest -m 'integration and scale' \
  tests/integration/test_long_run_checkpoints.py::test_checkpoint_cadences_measure_identical_histories -q

# Envelope validation and generation.
uv run pytest tests/unit/test_v3_scale_support.py --cov-report=term
PALIMPSEST_SCALE_ENVELOPE_ROOT=/tmp/opencode/v3-43-scale \
PALIMPSEST_SOURCE_REVISION=3930540 \
uv run python -m tests.benchmarks.v3_support

# Include the real retirement pair written by the composition benchmark.
PALIMPSEST_SCALE_ENVELOPE_ROOT=/tmp/opencode/v3-43-scale \
PALIMPSEST_SOURCE_REVISION=1c5c18c \
PALIMPSEST_SCALE_COMPOSITION_PATH=/tmp/opencode/v3-43-scale/task5-retirement/composition/composition.json \
uv run python -m tests.benchmarks.v3_support

# Clients.
"${GODOT_BIN}" --headless --editor --path clients/godot-observer --quit
"${GODOT_BIN}" --headless --path clients/godot-observer \
  --script res://tests/run_protocol.gd
npm --dir clients/research-ui run check
npm --dir clients/research-ui test
```

`pnpm` equivalents are `pnpm --dir clients/research-ui check` and `test` when
pnpm is installed; this environment used npm with the same package scripts.

## Workload Distinctions

| Lane | Meaning |
| --- | --- |
| Sparse control | Flags-off execution with sparse durability. Never certifies dense history. |
| Generational | Sustained population lifecycle, cohort admission/death and retirement. |
| Evidence-rich | Capture/provenance-heavy execution; only complete capture can certify this lane. |
| Synthetic log | Deliberately large journal/lineage sizes, labelled non-scientific. |
| Query/browser | Separate latency and client evidence; backend latency is not browser FPS. |

## Historical Storage and Replay

- Objective events, commits, snapshots, outbox records and cognition traces are
  append-only. Optimization never authorizes `DELETE`, `TRUNCATE`, partition
  detachment or provenance removal.
- Checkpoints and cold archives accelerate reads. They do not shrink immutable
  history to a constant or make a snapshot authoritative over source rows.
- Offline history export is an explicit copy:

  ```bash
  uv run palimpsest-matrix history-export --run-id <run_id> \
    --output /tmp/opencode/v3-43-scale/archive
  uv run palimpsest-matrix history-verify \
    --archive /tmp/opencode/v3-43-scale/archive --full
  ```

  Verification checks immutable objects, coverage and sampled replay. Export
  does not mutate SQL history; archive users are read-only and archives are
  never opened automatically as an API failover tier.
- Bounded replay verifies canonical event payload and commit hashes, preserves
  eventless ticks and prior-event windows, and keeps full public exports
  available at their cumulative cost.
- Durable restart supports objective and captured historical reads. Full
  subjective continuation from SQL is not claimed; process-local fork state is
  not a durable subjective restart.

## Runtime Retirement and Forks

`RuntimeRetentionPolicy` is composition-only and defaults off. When enabled,
only objectively dead, terminal, fully finalized and fork-capable owners are
retired. Retirement keeps a complete frozen owner record, all objective and
captured history, full exports and the fork roster, while releasing live
cognition/services and removing the owner from active scheduling. Unsupported
bundles stay live and increment an explicit unsupported count. No agent is
deleted to satisfy a benchmark.

## Analytical Views and Incremental Metrics

Rebuildable `v3-analytical-view-v2` checkpoints are disposable sidecars, not
authoritative tables or cognition inputs. A sealed checkpoint stores the boundary
state plus the exact digest of the derived rows; final rows are recomputed and
verified on resume instead of being stored twice. Legacy `v1` checkpoints remain
readable. Only population comparison and
cultural trait dynamics have exact incremental paths; the other cultural
families remain exact batch/global calculators with separate limits. Trait rows
are finalized only after the complete window's trait union is known, so late
trait appearance produces earlier zero rows rather than a truncated history.

## Client Paging and Playback

- Godot keeps one in-flight request plus one desired target, bounded
  civilization caches and explicit unavailable/timeout layers. Catch-up pages
  continue by exclusive cursor; a full page is not EOF. LOD/coalescing changes
  presentation only; the semantic digest is identical across full, reduced,
  snap and aggregate modes.
- Research UI drains one buffered page suffix before advancing a cursor,
  reports `limited`/queue saturation explicitly, and applies a bounded request
  pool. Marker discovery uses explicit continuation rather than a silent page
  ceiling. Lineage publication discovery resolves the exact requested boundary
  and reports `scan_limited` instead of substituting the first snapshot.
- Clients keep in-memory caps only. There is no localStorage/IndexedDB private
  historical cache and no new write authority.
- The real-browser playback gate was **not executed** for the current client
  builds in this environment. No browser FPS, heap or interactive smoothness
  claim is made.

## Investigation Disposition

| Option | Disposition |
| --- | --- |
| Snapshot strategy | Measured off/100/500/1000 at 600 ticks; cadence 100 recommended for seek-heavy workloads in that scenario; default unchanged. |
| Cold historical storage | Verified copy-only segmented export and read-only adapter. |
| Partitioning | Deferred; no destructive tiering or partition detach. |
| Indexes | Existing SQL indexes plus versioned physical lineage/civilization range indexes. |
| Materialized views | Disposable exact analytical sidecars only. |
| Incremental metrics | Population comparison and trait dynamics; remaining families stay batch/global. |
| Lineage compression | Lossless content-addressed pages; every edge and witness retained. |
| Bounded hot state | Active ordinal scheduling, frozen retired owners, bounded reads/spool/cache. |
| Pagination/streaming | SQL keysets, exclusive cursors, physical pages, streamed verification/publication. |
| Batch analytics | Pinned evidence sessions with explicit global-family budgets. |

## Safe Operation

- Use disposable databases containing `palimpsest_test`; never point benchmarks
  at a shared or production database.
- Give long runs explicit time, RAM and disk budgets. A `timed_out` artifact is
  evidence, not a pass.
- Keep capture optional and default off. Capture failure is reported separately
  from science failure; a completed run with failed required capture is not a
  complete evidence-rich result.
- Treat cold archives as additional storage. Monitor cumulative objective,
  genealogy, record, trace and snapshot growth rather than assuming constant
  memory or disk.
- Verify archive hashes before relying on an offline copy. Corrupt or tampered
  archives fail closed.
- Continue limited queries explicitly: drain Research UI continuations or run
  another scan action; do not reinterpret `scan_limited` as absence.
- If a required environment is missing, record the gate as unexecuted instead of
  converting it into a support claim.

## Known Limitations

- No dense 100k completion; verified-through is 10k for the measured lanes.
- The retained 10k lanes include two failed construction attempts per lane
  (`worker_error_RunnerConstructionError`). They are recorded in the envelope,
  not counted as completed repetitions.
- The retained 10k artifacts did not capture `source_revision` or the
  PostgreSQL server version; rows use the envelope revision and say so. New runs
  record both.
- Process RSS enforcement is unenforced in this environment.
- SQL byte counters and some workload byte fields are unavailable.
- Historical and lineage query rows are single measurements, not repeatable
  claims.
- Composition trials are one 10k retirement pair and test-level spool/paging
  checks; they do not certify capacity.
- The checkpoint cadence comparison is one 600-tick scenario; the recommended
  cadence is advisory and does not change defaults.
- Real-browser observer playback is unverified for the current client builds.
- Living population is zero at the end of the measured generational lanes; this
  is a completed history with extinction, not a steady-state population
  capacity claim.

## See Also

- [Generational runner](generational-runner.md) — v55 configuration, cohorts,
  archives and historical inspection.
- [Persistence](persistence.md) — append-only history, codecs, checkpoints and
  replay.
- [Research UI](research-ui.md) — paging controls, coverage and scope safety.
- [Read-only observer](observer.md) — bounded playback and catch-up semantics.
