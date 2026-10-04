# Scale benchmark baseline artifacts

Filled from a local disposable `palimpsest_test` run (2026-10-04).
Never commit seeds, payloads, or embeddings — counts and durations only.

| scenario | ticks | elapsed_ms | events | snapshots | events_per_sec | peak_rss_kb | catchup_ms | seek_ms | snapshot_write_proxy_ms | notes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| durable_fake_t200 | 200 | 3196.901 | 616 | 3 | ~193 | (see host) | (logged) | (logged) | cadence=100 | bootstrap+2 ckpts |
| durable_fake_no_ckpt | 50 | 838.452 | 154 | 1 | ~184 | (see host) | (logged) | (logged) | 0 | bootstrap only; seek folds from tick 0 |

Re-run:

```bash
PALIMPSEST_TEST_DATABASE_URL=postgresql+asyncpg://.../palimpsest_test \
  uv run --frozen --python 3.12.14 pytest -m "integration and scale" tests/benchmarks/ -q
```

Optional: `PALIMPSEST_SCALE_BENCH_TICKS=1000` / `PALIMPSEST_SCALE_BENCH_EXTENDED=1`.

## Top bottlenecks (task 2 — code + harness evidence)

1. **Sparse-checkpoint seek fold** — `src/simulation/replay.py` (`ReplayService.replay` / `scene_at_tick`): without cadence, seek falls back to bootstrap (`snapshot_next_tick=0`) and folds all intervening events; cost grows with target tick.
2. **Per-tick durable append + owner finalize** — `src/simulation/service.py` (`resolve_tick` / `append_tick`) and `src/simulation/runner.py` tick loop: wall time ≈ 15–17 ms/tick for the single-agent fake path; dominates long-run elapsed.
3. **Unbounded memory candidate materialization** — `src/persistence/memory_sqlalchemy.py` (`_load_filtered_traces` before `rank_traces`): loads the full filtered owner corpus into Python before ranking; latency and RSS grow with memory size (candidate cap lands in later tasks).

Pointers only; plan Verification notes stay out of band.
