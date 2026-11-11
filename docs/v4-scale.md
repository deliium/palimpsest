# V4 Scale Contract

V4-01 defines how a future large population is partitioned for execution and how
per-tick budgets are expressed. It does not wire partitioning into the engine, it
does not aggregate anything on the server, and it makes no capacity claim.

## Partition contract

`simulation.scale.stable_partition(agent_ids, partitions=N)` is a pure function of
the versioned namespace (`palimpsest-scale-partition-v1`) and each agent id:

1. `blake2b(f"{namespace}\x00{agent_id.value}", digest_size=8)`,
2. `int.from_bytes(digest, "big") % partitions`.

Properties:

- deterministic across processes (no `hash()`, no global state, no wall clock),
- order-preserving inside each partition and partitions returned in index order,
- lossless and duplicate-free,
- duplicate ids are rejected (`duplicate_agent_id`),
- `partitions` must be between 1 and 4096 (`scale_partitions_invalid`).

Changing `SCALE_PARTITION_NAMESPACE` changes every assignment and therefore
requires a contract version bump.

## Budgets

`ScaleBudget` declares `max_population`, `max_commands_per_tick`, and
`max_observer_rows`. Limits are positive integers, and `max_population` may not
exceed `100000`. `validate_scale_budget(budget, population)` fails closed with
`scale_budget_exceeded` above the declared population.

Budgets are declarative in V4-01: nothing enforces them at runtime, and passing
one to a future runner is a later plan's decision.

## Measurement lane

`tests/benchmarks/test_v4_scale_contract.py` is opt-in and unit-marked:

```bash
PALIMPSEST_V4_SCALE_IDS=10000 uv run --frozen --python 3.12.14 pytest tests/benchmarks/test_v4_scale_contract.py -q
```

With the variable unset the lane skips with an explicit reason and measures
nothing. When set, it partitions `scale-agent-NNNNNN` ids into 16 partitions,
verifies membership and per-id assignment against the single-id contract, checks
digest stability, and logs one `v4_scale_contract_measured` record with counts,
elapsed time, balance, and a digest prefix. It writes no artifact.

This lane measures **partition mapping only**. It is not a release gate and it is
not evidence about tick throughput, memory, or civilization capacity. The
existing [long-horizon scalability](long-horizon-scalability.md) page remains the
only source of measured envelope statements, and V4-01 adds no new number to it.

## Presentation levels

Multi-scale presentation is a client-side vocabulary only
(`observer.scale`): `agent`, `cohort`, `settlement`, `region`, `civilization`,
with population thresholds and per-level row caps. The server performs no
aggregation and exposes no LOD contract; both clients choose a level locally.

Current catalog: 208 metric families; 43 commands; 73 observer semantic types; Alembic `0017`.
