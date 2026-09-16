# Persistence and Deterministic Replay

[← Development](development.md) · [Back to README](../README.md)

## Boundaries

- `simulation` owns immutable DTOs, repository **ports**, journal codecs, `PersistentSimulationService`, and `ReplayService`.
- `persistence` implements those ports with async SQLAlchemy. It may import only public `simulation` contracts and generic `infrastructure`.
- Domain packages and `simulation` never import SQLAlchemy. `infrastructure` stays domain-neutral.

## Objective history

Authoritative history is the ordered stream of replay-capable `WorldEvent` records plus per-tick commit rows (including eventless ticks). Payloads store committed effects, not instructions to re-run current rules. Subjective memory and LLM transcripts are outside this stream; cognition replay still needs recorded provider responses or stubs.

## Versions

| Constant | Role |
| --- | --- |
| `EVENT_SCHEMA_VERSION` | Replay-capable objective event envelope |
| `PROJECTOR_VERSION` | Private world projector compatibility |
| `PERSISTENCE_CODEC_VERSION` | Canonical JSON codec for manifests/snapshots/commits |
| `DERIVATION_VERSION` | Deterministic ID derivation |

Legacy schema-v1 audit events remain decodable for export but must not enter the authoritative log.

## Append-only store

Alembic revision `0002` creates experiments, experiment_runs, simulation_runs, tick_commits, world_events, world_snapshots, and normalized snapshot projection tables. Triggers reject `UPDATE`/`DELETE`/`TRUNCATE` on authoritative tables. Runtime roles should omit mutation privileges beyond `INSERT`/`SELECT`.

## Durable tick window

1. Prepare a detached candidate on `WorldEngine` (live state unchanged).
2. Append tick commit + events (+ optional snapshot) in one PostgreSQL transaction with advisory lock, predecessor checks, idempotency key, and commit-hash chain.
3. Finalize by swapping the in-memory snapshot only after commit success.

Adapter failure before commit leaves the engine unchanged. Crash after commit is recovered by replaying persisted history.

## Replay

`ReplayService` loads a run, selects a verified checkpoint at or before the target tick, validates versions and commit continuity, folds subsequent events, and accounts for eventless ticks via `committed_through_tick`. Recovery at the durable head is `CONTINUATION` (may `open_durable`); earlier targets are `READONLY`.

## Logging

Safe fields: run ID, tick/revision, record counts, version strings, hash prefixes, stable error codes. Never log seeds, full configs, event payloads, snapshot bodies, DSNs, SQL parameters, memories, or embeddings. Control verbosity with `PALIMPSEST_LOG_LEVEL`.

## Integration tests

Set `PALIMPSEST_TEST_DATABASE_URL` to a disposable database, then:

```bash
uv run --frozen --python 3.12.14 pytest -m integration tests/integration
```
