# Simulation Runner

[← Architecture](architecture.md) · [Back to README](../README.md)

## Role

`SimulationRunner` owns configuration-driven run construction and the V1 tick lifecycle. It builds world bootstrap, cognition loops, and one `AgentRuntime` per registration from an immutable `SimulationRunnerConfig`, then advances only the authoritative `WorldEngine` (or durable `PersistentSimulationService`).

## Identities

- **Durable `RunId`:** storage/correlation identity; unique per arm/process.
- **`StochasticIdentity` + seed + scenario:** comparison identity for paired experiment arms. Equal values produce equal objective RNG streams across different durable run IDs and cognitive conditions.
- Cognition/experiment fingerprints never enter objective world RNG scopes.

Derivation version **v3** requires an explicit stochastic identity and fails closed on absence/mismatch during replay.

## Configuration

`SimulationRunnerConfig` is frozen and versioned. Strict canonical JSON codecs reject unknown fields, duplicate keys, non-finite numbers, credentials, and unsupported versions. Separate fingerprints cover:

- full runner specification
- scenario/world
- cognitive condition
- provider settings (adapter kind/model/request knobs only; no secrets)

Use `SimulationRunner.from_config(...)` with injected factories/ports. The runner must not import environment settings, SQLAlchemy, or API code.

## Tick lifecycle

1. Cognition **prepare**: perception → planning → proposed command + scientific artifacts (no command-dependent memory intents yet).
2. Trusted intervention may select the effective command.
3. Runtime **bind**: memory/internal-state completion for the effective command; at most one submission; pending subjective finalization recorded.
4. Objective **commit** via the single authority path.
5. Subjective **finalize** (idempotent). Post-objective failure stops before the next tick and remains recoverable; never roll back a committed tick.

Scheduling is sequential in bootstrap registration order. Concurrent cognition is out of scope for V1.

## Stop and results

Stop policies cover max ticks and closed failure modes. Results are versioned machine-readable documents with stop reason, tick counts, config fingerprint prefixes, and exact vs replica-normalized trajectory hashes. Seeds, credentials, prompts, and raw provider output stay out of logs and result documents.

## Recovery and inspection

Committed objective ticks with interrupted subjective finalization rehydrate without rerunning cognition. Inspection and replay use detached projections — never live `WorldEngine` mutation. See [Research API](research-api.md) and [Persistence](persistence.md).

## LLM reproducibility

External LLM runs are reproducible only with deterministic fakes or recorded validated outputs. Exact reproducibility requests require fake/recorded provider mode. Credentials remain composition concerns and never enter canonical specs or hashes.

## Tests

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_simulation_runner_construction.py \
  tests/unit/test_simulation_runner.py \
  tests/unit/test_runner_results.py \
  tests/unit/test_simulation_runner_e2e.py -q
```
