# Development

[← Previous Page](configuration.md) · [Back to README](../README.md) · [Next → Long-horizon scalability](long-horizon-scalability.md)

## Locked environment

```bash
uv sync --frozen --python 3.12.14
```

Do not omit `--frozen` in development or containers. The reference interpreter is **3.12.14**.

## WorldEngine

`simulation.WorldEngine` is the sole public mutation authority. Construct it from `SimulationRunConfig` (required seed) and immutable `WorldBootstrap`, then:

1. `observe()` → `ObservationBatch` with an engine-issued `TickToken` (projections from tick-start state + prior committed window)
2. Route one observation per agent via `observation_for(AgentId)` / `AgentRuntime` (or `build_perspective` + `CognitiveLoop`)
3. Submit an ordered sequence of `ActionSubmission(token, AgentId, AgentCommand)`
4. `resolve_tick(...)` → `TickResult` and atomic commit to tick N+1

`AgentRuntime` owns per-agent start/active/terminal lifecycle, cognition invocation, memory-update hooks, and submission construction from the engine token. See [Cognition and agent runtime](cognition-runtime.md).

Equivalent bootstrap + seed + ordered submissions must produce identical ticks, revisions, resolutions, objective events, observations, and replay fingerprints. Physical rules and autonomous physiology participate in every committed tick. Perception never invents facts or forms memories. See [Architecture](architecture.md) and [Physical simulation](physical-simulation.md).

## Tests

Default pytest excludes live infrastructure:

```bash
uv run --frozen --python 3.12.14 pytest
# equivalent addopts: -m "not integration and not compose"
```

| Command | What it covers |
| --- | --- |
| `uv run --frozen --python 3.12.14 pytest` | Unit + architecture (no Docker, no PostgreSQL) |
| `uv run --frozen --python 3.12.14 pytest tests/unit/physical -q` | Physical conservation, physiology, scale, seed proofs |
| `uv run --frozen --python 3.12.14 pytest tests/unit/test_openai_compatible*.py tests/unit/test_llm_*.py tests/unit/test_fake_llm_provider.py -q` | Provider codec/transport, prompts, factory, fake |
| `uv run --frozen --python 3.12.14 pytest tests/architecture/test_llm_provider_isolation.py -q` | LLM import/signature/logging isolation |
| `uv run --frozen --python 3.12.14 pytest tests/unit/test_world_perception*.py tests/unit/test_perception_event_isolation.py -q` | Visibility, noninterference, event audience, routing isolation |
| `uv run --frozen --python 3.12.14 pytest tests/unit/test_cognition_*.py tests/unit/test_agent_runtime.py tests/unit/test_imagination_engine.py tests/unit/test_motivation_appraisal.py tests/unit/test_fear_of_death.py tests/unit/test_intention_selection.py tests/unit/test_action_planner.py tests/unit/test_subjective_risk_*.py tests/unit/test_v1_*memory*.py tests/unit/test_memory_reconstruction*.py tests/unit/test_memory_llm_reconstruction.py tests/unit/test_memory_drift_analysis.py tests/unit/test_reconstruction_analysis_service.py tests/unit/test_semantic_belief_*.py tests/unit/test_subjective_*.py tests/unit/test_self_model_development.py tests/architecture/test_cognitive_loop_isolation.py tests/architecture/test_memory_isolation.py tests/architecture/test_social_isolation.py tests/architecture/test_analysis_isolation.py -q` | Cognition + subjective deliberation + beliefs/relationships + reconstructive memory + drift analysis isolation |
| `uv run --frozen --python 3.12.14 pytest tests/unit/test_compatibility_matrix.py tests/unit/test_v2_*.py tests/unit/test_v1_regression_gate.py tests/unit/test_alembic_head_pin.py -q` | Compatibility matrix, golden configs, flags-off gate, Alembic `0017` pin |
| `uv run --frozen --python 3.12.14 pytest tests/unit/test_runner_config_v4_flags.py tests/unit/test_runner_config_v56.py tests/unit/test_v4_scaffolding_gate.py tests/unit/test_v4_versioning_reservations.py tests/unit/test_v4_migration_plan.py tests/unit/test_v4_scale_contracts.py tests/unit/test_observer_capability_manifest.py tests/unit/test_observer_scale_mirror.py -q` | V4-01 scaffolding: closed unowned flags, accepted-but-unemitted v56, fail-closed gate, reservations, migration order, scale contract, observer capabilities |
| `uv run --frozen --python 3.12.14 pytest tests/architecture/test_v4_architecture_invariants.py tests/architecture/test_v4_context_registry.py -q` | V4 architecture invariants: pins, authority, magic-actor scan, read-only clients |
| `PALIMPSEST_V4_SCALE_IDS=10000 uv run --frozen --python 3.12.14 pytest tests/benchmarks/test_v4_scale_contract.py -q` | Opt-in V4 partition measurement lane (unset skips; no capacity claim) |
| `uv run --frozen --python 3.12.14 pytest -m integration tests/integration/test_agent_runtime_world_engine.py -q` | In-memory AgentRuntime ↔ WorldEngine (no Postgres) |
| `PALIMPSEST_TEST_DATABASE_URL=... uv run --frozen --python 3.12.14 pytest -m integration tests/integration/test_episodic_memory_pgvector.py tests/integration/test_memory_concurrency.py tests/integration/test_migrations.py tests/integration/test_subjective_state_persistence.py tests/integration/test_experiment_repository.py -q` | Opt-in Postgres episodic + subjective + experiment records + migration head `0017` |
| `uv run --frozen --python 3.12.14 pytest -m integration` | Disposable Postgres via `PALIMPSEST_TEST_DATABASE_URL` |
| `PALIMPSEST_TEST_DATABASE_URL=... uv run --frozen --python 3.12.14 pytest -m "integration and scale" tests/benchmarks/ -q` | Long-run scale harness (deterministic fake cognition; default 1k/10k ticks; `PALIMPSEST_SCALE_BENCH_EXTENDED=1` adds 50k; optional `PALIMPSEST_SCALE_BENCH_TICKS`). Also covers observer catch-up / seek / multi-observer isolation scenarios in `tests/benchmarks/test_observer_scale_scenarios.py`. |
| `PALIMPSEST_TEST_DATABASE_URL=... uv run --frozen --python 3.12.14 pytest -m "integration and scale" tests/integration/test_generational_scale.py -q` | Opt-in 100000-tick generational durability gate: cohorts, gaps, snapshot/history cadence, exact hashes, historical seek parity, deterministic twin, indexed receipt membership. A skipped database gate is not a passing durability check. |
| `PALIMPSEST_TEST_DATABASE_URL=... PALIMPSEST_RETIREMENT_TICKS=10000 uv run --frozen --python 3.12.14 pytest -m "integration and scale" tests/benchmarks/test_retirement_composition.py -q` | Opt-in retirement off/on composition pair: identical scientific counters, resident vs retired owner counts, capped frozen-state estimate; writes `task5-retirement/composition/`. |
| `PALIMPSEST_SCALE_BENCH_OUTPUT=... uv run --frozen --python 3.12.14 pytest -m "integration and scale" tests/integration/test_long_run_checkpoints.py::test_checkpoint_cadences_measure_identical_histories -q` | Checkpoint cadence sweep at 600 ticks; writes `task9-cadence/checkpoint-cadence.json`. |
| `uv run --frozen --python 3.12.14 pytest -m compose` | Compose file checks and optional stack smoke |
| `"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd` | Pinned Godot 4.7.2 protocol suite (48 suites, expects `godot_protocol_tests failed=0`) |
| `cd clients/research-ui && pnpm test && pnpm check && pnpm build` | Research UI tests, type/Svelte checks, production build |
| `uv run --frozen --python 3.12.14 ruff check src tests` | Lint |
| `uv run --frozen --python 3.12.14 mypy src tests` | Strict typing |
| `uv run --frozen --python 3.12.14 pytest tests/unit/test_packaging.py` | Wheel install / package discovery |

Integration tests **fail** in CI if `PALIMPSEST_TEST_DATABASE_URL` is missing; locally they **skip** with a warning. The URL must name a disposable `palimpsest_test` database. Unsafe names (`postgres`, `template0`, `template1`) are rejected before migration. `CREATE EXTENSION vector` requires privilege; limitation skips locally with WARNING.

Compose tests never run in the default suite. The smoke test uses a unique Compose project name and `PALIMPSEST_API_PUBLISH_PORT`, captures **redacted** logs on failure, and always `down --volumes --remove-orphans` for that project only.

Set `PALIMPSEST_TEST_DEBUG=1` for concise test-harness DEBUG on stderr.

## Migrations

Alembic does **not** store a database URL in `alembic.ini`. `alembic/env.py` loads validated settings (`PALIMPSEST_DATABASE_URL`, or the test URL for integration).

```bash
./scripts/migrate.sh
# or:
export PALIMPSEST_DATABASE_URL='postgresql+asyncpg://palimpsest:palimpsest@127.0.0.1:5432/palimpsest'
uv run --frozen --python 3.12.14 alembic upgrade head
```

Revision `0001` enables `pgvector`. Revision `0002` creates the append-only simulation event store. Revisions `0003`/`0004` add physical state and occurrence context. Revision `0005` adds owner-scoped episodic memory tables. Revision `0006` adds reconstruction/derivation provenance (append-only reconstruction tables; selective content immutability on traces). Revision `0007` adds semantic beliefs and directed relationship profiles (append-only revisions; outside `AUTHORITATIVE_TABLES`). Revision `0008` adds social transmission provenance columns on memory traces and belief evidence. Revision `0009` adds runner pending-finalization/outbox tables. Revision `0010` adds append-only experiment definition/assignment/result records. Current head is **`0010`**. Downgrade of `0001` is a documented no-op for the extension. Never use `metadata.create_all()`.

## Local run scripts

Convenience wrappers live under `scripts/` (repo root as cwd):

| Script | Equivalent |
| --- | --- |
| `./scripts/up.sh` | Same pull path as `./run.sh` |
| `./scripts/down.sh` | `docker compose down` |
| `./scripts/api.sh` | Compose `db` → `alembic upgrade head` → host Uvicorn `--reload` |
| `./scripts/migrate.sh` | `uv run --frozen --python 3.12.14 alembic upgrade head` |

`api.sh` and `migrate.sh` create `.env` from `.env.example` when missing and ensure a development `PALIMPSEST_DATABASE_URL` is set. They still honor an already-exported URL or an existing `.env`.

## Local API

Runtime requires `PALIMPSEST_DATABASE_URL`. Preferred:

```bash
./scripts/api.sh
```

Factory entrypoint without the wrapper:

```bash
uv run --frozen --python 3.12.14 uvicorn api.app:create_app --factory --host 127.0.0.1 --port 8080
```

`GET /health` returns exactly `{"status":"ok"}` without querying PostgreSQL. Unsupported methods return 405. `X-Request-ID` is accepted when safe, otherwise generated.

## Docker Compose

The normal start pulls a published image. It does not install Godot, open the editor, install export templates, export the client, or copy web files.

```bash
./run.sh
# or: ./scripts/up.sh
# or: docker compose up -d
```

When the stack is ready the script prints `INFO startup_ready url=http://127.0.0.1:8080/`. Open that page. `PALIMPSEST_API_PUBLISH_PORT` changes the host port. `./run.sh --open` launches a browser when `xdg-open` or `open` exists.

`./run.sh` does not build. If the release image is not published yet, the pull fails and the message points at `./run-dev.sh`. That contributor command builds `compose.dev.yaml` with the pinned editor inside the image export stage. It exports `PALIMPSEST_REVISION` from `git rev-parse HEAD`, or `unknown` when git cannot provide a revision. The image stores that value, and `GET /version` reports it as `revision`.

```bash
./run-dev.sh
docker build --target observer-export --output type=local,dest=clients/godot-observer/build/web .
```

The second command extracts the web files without opening the editor. A URL `/?run_id=<id>` starts that session. The query never carries a token. A missing or mismatched observer protocol is `[observer.protocol] parse_failed reason_code=unsupported_observer_protocol`. When the page supplies a run id, the client logs `[observer.session] web_run_id_applied run_id=%s`.

Order: database health → one-shot `alembic upgrade head` → API. The API image runs Uvicorn as uid **1001** on port 8080. Healthcheck uses Python `urllib`, not `curl`. Host `./scripts/api.sh` leaves `PALIMPSEST_PRESENTATION_WEB_ROOT` unset, so it does not mount the export.

Optional Research UI: `pnpm --dir clients/research-ui build` then set `PALIMPSEST_RESEARCH_WEB_ROOT` to `clients/research-ui/dist`. `compose.dev.yaml` passes through `PALIMPSEST_RESEARCH_WEB_ROOT` / `PALIMPSEST_RESEARCH_MATRIX_ROOT`. Opt-in compose checks: `pytest -m compose tests/compose/test_research_ui_wiring.py`. Smoke against a running stack: set `PALIMPSEST_COMPOSE_RESEARCH_SMOKE_URL=http://127.0.0.1:8080` when dist is mounted. See [Research UI](research-ui.md). V2 benchmark matrix artifacts and scientific/zero-install gates: [V2 benchmark suite](v2-benchmark-suite.md).

The database image stays digest-pinned. The API image is `PALIMPSEST_API_IMAGE` or `ghcr.io/deliium/palimpsest:0.1.0`. Application install uses `uv sync --frozen --no-dev --no-editable`. Contributor builds set `network: host` so `uv` can resolve PyPI when the Docker bridge DNS is unavailable. Manual image builds on the same hosts may need `docker build --network=host`.

Release builds carry source attestations. `docker build` accepts `PALIMPSEST_REVISION` plus at most one of `PALIMPSEST_SOURCE_CLEAN=true` or `PALIMPSEST_SOURCE_ARTIFACT_DIGEST=<sha256>`. The build fails when both are supplied, when an attestation has no non-`unknown` revision, or when the digest is not 64 lowercase hex characters; omitting both still builds, but the image is explicitly unattested (`source-clean=false`, empty digest). The values become the `org.opencontainers.image.revision`, `io.palimpsest.source-clean` and `io.palimpsest.source-artifact-digest` labels, which the benchmark producer forwards as `--code-revision` and `--source-artifact-digest`. A revision string alone is never proof of clean source.

Development passwords in `compose.yaml` are **non-production**. Expanded `docker compose config` output is **not secret-safe**. Production extension-privilege design is deferred.

```bash
docker compose config --quiet
uv run --frozen --python 3.12.14 pytest -m compose
./scripts/down.sh
```

## Generational runner verification

Routine feature gates (no PostgreSQL):

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_runner_config_v55.py \
  tests/unit/test_generational_models.py \
  tests/unit/test_generational_population_runner.py \
  tests/unit/test_generational_stopping.py \
  tests/unit/test_generational_criteria.py \
  tests/unit/test_generational_artifacts.py \
  tests/unit/test_generational_sampling.py \
  tests/unit/test_experiment_bl.py \
  tests/unit/test_generational_execution.py \
  tests/unit/test_generational_cli.py -q
uv run --frozen --python 3.12.14 palimpsest-matrix generational --help
```

Durability and history require a validated disposable `palimpsest_test`
database:

```bash
PALIMPSEST_TEST_DATABASE_URL=... uv run --frozen --python 3.12.14 pytest \
  -m integration tests/integration/test_generational_history.py -q
PALIMPSEST_TEST_DATABASE_URL=... uv run --frozen --python 3.12.14 pytest \
  -m 'integration and scale' tests/integration/test_generational_scale.py -q
```

Historical replay is objective inspection, not subjective restart. Exact
external-LLM reproduction needs deterministic fakes or validated recordings;
source revision plus a clean assertion/digest and the registered execution
recipe are archive inputs. See [Generational runner](generational-runner.md).

## Generational observer verification

Focused Python gates for the demographic/lineage projections:

```bash
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term \
  tests/unit/test_observer_demographics.py \
  tests/unit/test_observer_population_replay.py \
  tests/unit/test_observer_demographic_api.py \
  tests/unit/test_lineage_participants.py \
  tests/unit/test_lineage_participant_api.py \
  tests/unit/test_lineage_filesystem.py \
  tests/unit/test_lineage_api.py \
  tests/unit/test_lineage_pagination.py \
  tests/unit/test_godot_observer_fixtures.py \
  tests/unit/test_godot_protocol_mirror.py \
  tests/unit/test_observer_export_pins.py \
  tests/architecture/test_godot_generational_boundaries.py \
  tests/architecture/test_observer_isolation.py \
  tests/architecture/test_lineage_explorer_boundaries.py -q
```

The pinned Godot suite is the same two-pass sequence used above; registered
suites now include `test_generational_http`, `test_demographic_models`,
`test_lineage_models`, `test_generational_session`, `test_lineage_session`,
`test_generational_view`, and `test_generational_navigation`.

Published-image acceptance requires Docker and Playwright:
`tests/compose/test_observer_browser.py` remains the V2 smoke, and the
generational suite is expected to run against the same built image with
separate inspection/debug credentials and a test-owned lineage volume. `start_bl_generational`
starts the unmodified real Experiment BL condition (seed 23, horizon 16) and
asserts two nonfounder generations and committed stage changes through the API;
BL uses regional locations, so it is an API/scientific proof rather than a
Godot-layout browser run. `start_generational` starts a layout-compatible
reference-location generational run for the exported-browser assertions. The
producer creates a separate controlled durable v55 run with a trusted ordinary
Feed command, projects its objective genealogy, and publishes explicitly
constructed mentorship/knowledge fixtures for the same run/boundary; those
fixtures are labeled as presentation evidence, not emergent-learning proof. A skipped image,
browser, or editor prerequisite is an unexecuted gate and must be reported as
such.

## Regional migration verification

Focused reproduction and contract checks:

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_experiment_ay.py tests/unit/test_regional_migration_observer.py tests/unit/test_regional_demographics.py tests/unit/test_runner_config_v44.py -q
uv run --frozen --python 3.12.14 pytest -m integration tests/integration/test_regional_travel_persistence.py tests/integration/test_episodic_memory_pgvector.py -q
```

The integration command requires `PALIMPSEST_TEST_DATABASE_URL` targeting a
validated disposable `palimpsest_test` database; a skipped database gate is not
a passing durability check. Use the checksum-pinned **Godot 4.7.2** editor from
`clients/godot-observer/export/pins.env`, as in the observer-image workflow:

```bash
"${GODOT_BIN}" --headless --editor --path clients/godot-observer --quit
"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd
```

Set `GODOT_BIN` to that executable. The editor pass registers global classes on
a fresh checkout. The registered regional suite checks parsing, reduction,
origin-anchored rendering, capacity wait, arrival/end, and backward frame seek.
Full Ruff, mypy, import-linter, architecture, V1/V2 compatibility, and pytest
gates are still required before declaring the feature verified. Run status and
unresolved failures belong to the active implementation plan.

## Long-horizon scale gates

Long-horizon runs are opt-in and budgeted; see
[Long-horizon scalability](long-horizon-scalability.md) for the verified envelope
and exact artifacts.

```bash
PALIMPSEST_SCALE_BENCH_TICKS=10000 \
PALIMPSEST_SCALE_BENCH_LANES='v1-control,generational,evidence-rich,historical-query' \
PALIMPSEST_SCALE_BENCH_TIMEOUT_SECONDS=300 \
uv run pytest -m 'integration and scale' tests/benchmarks/test_v3_long_horizon.py
uv run pytest -m 'integration and scale' tests/benchmarks/test_v3_historical_queries.py
uv run pytest -m integration tests/integration/test_v3_historical_query_safety.py
uv run pytest tests/unit/test_v3_scale_support.py
```

A `timed_out` or `failed` worker is a recorded result, not a pass. Dense
evidence-rich 100k completion is not claimed; the generational 100k lane can
complete ticks with an extinct final population, which is a throughput result
only.

## V3 generational civilization benchmark

The thirty-case suite and its qualification harness are documented in
[V3 benchmark suite](v3-benchmark-suite.md).

```bash
uv run --frozen --python 3.12.14 pytest -q   tests/unit/test_v3_benchmark_comparison.py

PALIMPSEST_V3_SOURCE_REVISION=<revision> \
PALIMPSEST_V3_SOURCE_ARTIFACT_DIGEST=<sha256> \
PALIMPSEST_V3_BENCHMARK_ROOT=/tmp/palimpsest/benchmark \
uv run --frozen --python 3.12.14 pytest -m 'integration and scale' \
  tests/benchmarks/test_v3_civilization_benchmark.py -q
```

Synthetic test identities are labeled; a real run requires exactly one explicit
source assertion. Mechanism suites can be verified with `--require-complete`;
research suites verify integrity while retaining legal nulls.

Published-image acceptance has two modes. Optional local runs skip a missing
Docker CLI, Playwright or `PALIMPSEST_API_IMAGE` with an explicit reason. Set
`PALIMPSEST_V3_ACCEPTANCE_REQUIRED=1` to make those prerequisites failures
instead, which is how the release gate is run:

```bash
PALIMPSEST_API_IMAGE=<source-matched-image> \
PALIMPSEST_V3_ACCEPTANCE_REQUIRED=1 \
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term -m compose -q
```

Two bounded stress probes are opt-in and are skipped by the default collection
(`PALIMPSEST_V3_PUBLICATION_SCALE_FRAMES`, `PALIMPSEST_V3_INCREMENTAL_SCALE_BOUNDARIES`):

```bash
PALIMPSEST_V3_PUBLICATION_SCALE_FRAMES=20000 \
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term \
  tests/benchmarks/test_cultural_publication_rss.py -q

PALIMPSEST_V3_INCREMENTAL_SCALE_BOUNDARIES=5000 \
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term \
  tests/benchmarks/test_incremental_trait_analysis.py -q
```

Both are synthetic measurement lanes. They are reported separately and are
never counted as required-gate passes or as 10k/100k scientific-scale
certification.

## See also

- [Long-horizon scalability](long-horizon-scalability.md)

- [Architecture](architecture.md)
- [V2 benchmark suite](v2-benchmark-suite.md)
- [V3 benchmark suite](v3-benchmark-suite.md)
- [Cognition and agent runtime](cognition-runtime.md)
- [Memory reconstruction](memory-reconstruction.md)
- [LLM providers](llm-providers.md)
- [Configuration](configuration.md)
- [Persistence](persistence.md)


## Cultural-contact verification

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_contact_contracts.py \
  tests/unit/test_runner_config_v45.py \
  tests/unit/test_contact_arrivals.py \
  tests/unit/test_contact_relocations.py \
  tests/unit/test_contact_events.py \
  tests/unit/test_contact_checkpoint.py \
  tests/unit/test_contact_perception.py \
  tests/unit/test_contact_observer.py \
  tests/unit/test_contact_memory.py \
  tests/unit/test_society_contact.py \
  tests/unit/test_contact_cultural_change.py \
  tests/unit/test_contact_hybrid_practice.py \
  tests/unit/test_contact_knowledge_transfer.py \
  tests/unit/test_contact_lexical_borrowing.py \
  tests/unit/test_contact_reputation_transfer.py \
  tests/unit/test_experiment_ba.py -q
```

## Symbolic-language verification

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_symbolic_language.py \
  tests/unit/test_symbolic_language_learning.py \
  tests/unit/test_symbolic_language_transmission.py \
  tests/unit/test_symbolic_language_runtime.py \
  tests/unit/test_symbolic_language_checkpoint.py \
  tests/unit/test_symbolic_language_rows.py \
  tests/unit/test_symbolic_composition_metrics.py \
  tests/unit/test_symbolic_distribution_metrics.py \
  tests/unit/test_symbolic_message_flow_metrics.py \
  tests/unit/test_runner_config_v46.py \
  tests/unit/test_symbolic_language_observer.py \
  tests/unit/test_experiment_bb.py -q
```

## Semantic-drift verification

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_semantic_sense_history.py \
  tests/unit/test_symbolic_sense_history.py \
  tests/unit/test_runner_ledger_export.py \
  tests/unit/test_runner_lifecycle_export.py \
  tests/unit/test_semantic_drift_rows.py \
  tests/unit/test_semantic_stability_metrics.py \
  tests/unit/test_semantic_drift_metrics.py \
  tests/unit/test_semantic_divergence_metrics.py \
  tests/unit/test_metric_specifications.py \
  tests/unit/test_metric_service.py \
  tests/unit/test_experiment_bc.py -q
```

Expected selectors: 43 commands, 73 observer semantic types, 124 metric families,
`runner-config-v47` as the latest accepted schema (v46 remains valid for
symbolic-only runs), `replay-v22`/codec `v20`, and Alembic `0017`.

Translation verification:

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_translation_contracts.py \
  tests/unit/test_runner_config_v47.py \
  tests/unit/test_translation_learning.py \
  tests/unit/test_translation_rows.py \
  tests/unit/test_experiment_bd.py \
  tests/unit/test_translation_overlay.py -q
```

## Generational narrative verification

Focused suites:

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_generational_narrative_contracts.py \
  tests/unit/test_runner_config_v48.py \
  tests/unit/test_narrative_witnesses.py \
  tests/unit/test_narrative_source_loss.py \
  tests/unit/test_narrative_retellings.py \
  tests/unit/test_narrative_records.py \
  tests/unit/test_narrative_transitions.py \
  tests/unit/test_narrative_themes.py \
  tests/unit/test_generational_narrative_persistence.py \
  tests/unit/test_generational_narrative_rows.py \
  tests/unit/test_generational_narrative_harvest.py \
  tests/unit/test_generational_narrative_continuity_metrics.py \
  tests/unit/test_narrative_source_loss_metrics.py \
  tests/unit/test_narrative_historical_alignment_metrics.py \
  tests/unit/test_experiment_be.py \
  tests/unit/test_generational_narrative_overlay.py \
  tests/architecture/test_v3_generational_narratives_analysis_only.py
```

Also run the full pytest, Ruff, mypy, import-linter/architecture isolation, the
compatibility matrix, V1 regression and V2 scientific invariant gates, and the
BB/BC/BD experiment regressions. Confirm 43 commands, 73 observer semantic
types, 124 metric families, runner schema v49 only with the deterministic mode, replay v22 /
codec v20, and Alembic `0017`.


Institution verification:

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_institution_concepts_contracts.py \
  tests/unit/test_institution_concepts_loop.py tests/unit/test_institution_rows.py \
  tests/unit/test_institution_composition.py tests/unit/test_institution_emergence.py \
  tests/unit/test_runner_config_v49.py tests/unit/test_experiment_bf.py \
  tests/architecture/test_v3_institution_emergence_analysis_only.py -q
```

Expected: 43 commands, 73 observer semantic types, 124 metric families,
`runner-config-v49` only when a deterministic institution mode is present,
replay `EVENT_SCHEMA_REPLAY_V22`, codec `v20`, Alembic `0017`.


## Institutional decay focused checks

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_decay_contracts.py tests/unit/test_runner_config_v54.py tests/unit/test_institutional_decay_updates.py tests/unit/test_institutional_decay_runtime.py tests/unit/test_institutional_decay_checkpoints.py tests/unit/test_institutional_decay_analysis.py tests/unit/test_institution_lineage.py tests/unit/test_institutional_decay_composition.py tests/unit/test_institutional_decay_metrics.py tests/unit/test_experiment_bk.py tests/unit/test_institutional_decay_invariants.py -q
uv run --frozen --python 3.12.14 pytest tests/architecture/test_v3_institutional_decay_isolation.py -q
```

Pins remain commands 43, observer semantic types 73, metric families 130,
replay/codec V22/v20, Alembic `0017`, `/v1`, `observer-protocol-v1`,
`prepare_parallel=False`, default runner write `runner-config-v4`, and the
legacy result default `runner-result-v2`. New `runner-config-v55` /
`runner-result-v3` are feature-selected only. Older sections of this document
retain earlier metric counts as historical context.

## Generational experiment focused checks

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_experiment_bm.py tests/unit/test_experiment_bm_execution.py tests/unit/test_generational_matrix_factors.py tests/unit/test_generational_cohort_metrics.py tests/unit/test_generational_cohort_collectors.py -q
uv run --frozen --python 3.12.14 pytest tests/unit/test_generational_matrix_execution.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py -q
```

Expected: 130 metric families, BM's ten paired arms and matrix factors execute
on `runner-config-v55`, the comparison metric is present for generational arms
and absent for legacy arms, and default write/result, command, observer, replay,
and migration pins are unchanged.

## Historical contingency checks

`uv run pytest tests/unit/test_path_dependence_end_to_end.py -q` runs the fake-only smoke workflow. PostgreSQL path-dependence integration and the tick-100 scale profile are opt-in and reported as separate verification gaps when infrastructure is unavailable. See [Historical contingency](historical-contingency.md).

## Lineage explorer checks

```sh
uv run --frozen --python 3.12.14 pytest tests/unit/test_lineage_* tests/architecture/test_lineage_explorer_boundaries.py
```

Capture and catalog tests use temporary filesystem roots; no PostgreSQL is required.

## Civilization overlay verification

Focused Python/API/architecture and producer gate:

```bash
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term \
  tests/unit/test_observer_civilization.py \
  tests/unit/test_observer_civilization_api.py \
  tests/unit/test_civilization_capture.py \
  tests/unit/test_civilization_publication.py \
  tests/unit/test_civilization_filesystem.py \
  tests/unit/test_civilization_cli.py \
  tests/unit/test_civilization_overlay_api.py \
  tests/unit/test_civilization_markers_api.py \
  tests/unit/test_civilization_fixtures.py \
  tests/unit/test_v1_regression_gate.py \
  tests/unit/test_v2_scientific_invariants.py \
  tests/architecture -q
```

Dense render/read load fixture (no PostgreSQL required):

```bash
uv run --frozen --python 3.12.14 pytest -m "integration and scale" \
  tests/benchmarks/test_civilization_playback.py -q
```

Published-image browser acceptance uses the same built image and a disposable
database. The civilization fixture mounts the Task 6 `compose.civilization.yaml`
override, a read-only host root, capability credentials, and the real 256-tick
`civ-real-` producer:

```bash
PALIMPSEST_API_IMAGE=<built-image> \
  uv run --frozen --python 3.12.14 pytest --cov --cov-report=term -m compose \
  tests/compose/test_observer_browser.py \
  tests/compose/test_observer_generational_browser.py \
  tests/compose/test_observer_civilization_browser.py -q
```

Pinned Godot 4.7.2 checks (the editor pass registers global classes on a fresh
checkout):

```bash
"${GODOT_BIN}" --headless --editor --path clients/godot-observer --quit
"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd
```

The civilization acceptance covers real/full versus aggregate LOD semantic
digests, warmed control-to-visible p95, a 50-seek request/cache bound,
capture-off objective playback, GET-only traffic, and inspection/debug
separation. Missing Docker, image, Playwright, or the pinned editor is an
unexecuted gate, not a pass. See
[Godot civilization overlays](godot-civilization-overlays.md#verification-handoff)
for the measured handoff and real-versus-constructed provenance.

## Generational Research UI verification (V3-42)

Run from the repository root:

```bash
pnpm --dir clients/research-ui check
pnpm --dir clients/research-ui test
pnpm --dir clients/research-ui build
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term \
  tests/architecture \
  tests/unit/test_v1_regression_gate.py \
  tests/unit/test_v2_scientific_invariants.py \
  tests/unit/test_research_ui_state.py \
  tests/unit/test_research_matrix_fs.py \
  tests/unit/test_research_cultural_api.py \
  tests/unit/test_semantic_history_api.py \
  tests/unit/test_semantic_history_projection.py \
  tests/unit/test_observer_population_replay.py \
  tests/unit/test_observer_demographic_api.py \
  tests/unit/test_lineage_api.py \
  tests/unit/test_civilization_overlay_api.py \
  tests/unit/test_benchmark_research_ui_artifacts.py -q
```

Optional pinned gates:

```bash
"${GODOT_BIN}" --headless --editor --path clients/godot-observer --quit
"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd
uv run --frozen --python 3.12.14 pytest -m compose \
  tests/compose/test_generational_research_ui_browser.py -q
```

The browser file skips unless `PALIMPSEST_COMPOSE_RESEARCH_SMOKE_URL` and
`PALIMPSEST_COMPOSE_RESEARCH_RUN_ID` point at a running prebuilt SPA. Godot
commands require the pinned 4.7.2 binary. Report unavailable prerequisites as
UNEXECUTED; do not treat them as passing.

Cultural browser proofs should use the trusted helpers for
`tests/fixtures/matrices/v3-cultural-metrics.json` and
`tests/fixtures/cultural_metrics/known-lineage-v1.json`. Constructed lineage,
civilization, teaching or institution presentation fixtures prove rendering
only, not emergent learning or institutions. Unit/mounted tests never write to
artifact roots; API reads keep filesystem bytes unchanged.
