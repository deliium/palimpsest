[← Development](development.md) · [Back to README](../README.md) · [Persistence →](persistence.md)

# Long-Horizon Scalability

Measured scale behavior for multi-generation V3 runs, bounded historical
queries and read-only clients. The plan is `v3-43-long-horizon-scalability`;
production source revision for the measurements below is `3930540` (2026-10-27).
Benchmark-only generator and test changes made after that commit are identified
in the reproduction section.

> **No universal maximum is claimed.** The verified envelope stops at the
> workloads and horizons that actually completed with exact correctness. The
> 100k dense lanes did not complete under the configured budget.

## Verified Envelope

| Lane | Horizon | Status | Repetitions | Completed ticks | Verified boundary |
| --- | ---: | --- | ---: | ---: | ---: |
| Generational | 10k | `verified` | 4 | 10,000 | 9,999 |
| Evidence-rich | 10k | `verified` | 4 | 10,000 | 9,999 |
| Flags-off control | 10k | `tested_incomplete` | 0 | 2,225 | 2,224 |
| Generational | 100k | `tested_incomplete` | 0 | 22,769 | 22,768 |
| Evidence-rich | 100k | `tested_incomplete` | 0 | 15,825 | 15,824 |
| Flags-off control | 100k | `tested_incomplete` | 0 | 2,229 | 2,228 |

The 10k generational repetitions used the identical scientific run ID
`v3-43-generational-ticks-10000-seed-23` in separate disposable databases.
Observed wall times were 130.8–146.3 s; evidence-rich was 166.0–182.1 s.
Completed 10k artifacts report 5 cohorts, 9 births, 9 deaths, 5,241/5,243
events, 71,838 SQL calls, 40,204 SQL rows and **0 cognitive invocations after
death**. Every 100k lane reached its 300 s budget; no dense-100k support,
throughput promise or population capacity follows from these runs.

`measured_through_horizon=10000` is verified-through coverage, not a hard
maximum. Process RSS enforcement was `unenforced`; SQL byte counters and the
workload's event/snapshot byte fields were unavailable.

## Historical Query Measurements

Traceable JSON artifacts live under `/tmp/opencode/v3-43-scale/task19-historical/`.

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

# Envelope validation and generation.
uv run pytest tests/unit/test_v3_scale_support.py --cov-report=term
PALIMPSEST_SCALE_ENVELOPE_ROOT=/tmp/opencode/v3-43-scale \
PALIMPSEST_SOURCE_REVISION=3930540 \
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

Rebuildable `v3-analytical-view-v1` checkpoints are disposable sidecars, not
authoritative tables or cognition inputs. Only population comparison and
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
| Snapshot strategy | Deterministic policy retained; no new default and no cadence sweep in the Task 19 session. |
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
- Process RSS enforcement is unenforced in this environment.
- SQL byte counters and some workload byte fields are unavailable.
- Historical and lineage query rows are single measurements, not repeatable
  claims.
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
