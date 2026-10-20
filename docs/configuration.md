# Configuration

[← Previous Page](physical-simulation.md) · [Back to README](../README.md) · [Next Page →](development.md)

All application settings use the **`PALIMPSEST_`** prefix only. Environment variables override a project-root `.env` file (the directory that contains `pyproject.toml`). Missing `.env` is allowed. Importing packages does not read required secrets or connect to PostgreSQL.

## Settings

| Variable | Purpose |
| --- | --- |
| `PALIMPSEST_ENVIRONMENT` | `local` (console logs), `test`, or `production` (JSON logs) |
| `PALIMPSEST_LOG_LEVEL` | Only application log-level setting: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `PALIMPSEST_API_HOST` / `PALIMPSEST_API_PORT` | Bind metadata for operators; Uvicorn in Docker listens on `0.0.0.0:8080` |
| `PALIMPSEST_DATABASE_URL` | Async SQLAlchemy URL, **`postgresql+asyncpg://` only**. Required at runtime startup, not at import |
| `PALIMPSEST_TEST_DATABASE_URL` | Disposable integration-test URL; database **name** must contain `palimpsest_test` and must not be `postgres` / `template0` / `template1` |
| `PALIMPSEST_POOL_SIZE` / `PALIMPSEST_MAX_OVERFLOW` / `PALIMPSEST_POOL_TIMEOUT_SECONDS` | Async pool bounds (`pool_pre_ping` is always on) |
| `PALIMPSEST_DEFAULT_RUN_SEED` | Optional composition default. Always copied into `SimulationRunConfig`; never an implicit global RNG |
| `PALIMPSEST_LLM_*` | Disabled-by-default provider settings. See [LLM providers](llm-providers.md) |
| `PALIMPSEST_API_*` | Research API bind, capability credentials, stream queue/heartbeat/poll, debug gate. See [Research API](research-api.md) |

Booleans are rejected as integer settings. Invalid environments, pool bounds, seeds, and non-asyncpg URLs fail validation. Credentials are `SecretStr` and are stripped from `repr`, validation errors, and logs. LLM base URLs and API keys never appear in `SettingsError`, `repr`, or `bootstrap_fields()` (only `has_llm_base_url` / `has_llm_api_key` and enum/count diagnostics).

Alembic loads its URL from validated settings (never from `alembic.ini`). If both `PALIMPSEST_DATABASE_URL` and `PALIMPSEST_TEST_DATABASE_URL` are set and disagree, migration settings fail closed. Integration fixtures bind Alembic to the validated disposable test DSN so a conflicting runtime URL cannot divert the upgrade.

Copy `.env.example` to `.env` for local overrides. Do not commit `.env`.

## Logging

`configure_logging` is idempotent: one owned handler named `palimpsest`, UTC timestamps, exception rendering, isolated context variables. Unrelated handlers are preserved. `uvicorn.access` is set to WARNING so access lines do not duplicate application request records.

| Event | Level | Logger |
| --- | --- | --- |
| `logging_configured` | DEBUG | `infrastructure.logging` |
| `settings_loaded` | DEBUG | `infrastructure.settings` |
| `engine_created`, `session_opened`, `session_closed`, `readiness_check_started`, `engine_disposing`, `engine_disposed` | DEBUG | `infrastructure.database` |
| `request_started`, `request_completed` | DEBUG | `api.request` — `method`, `status`, `duration_ms`, `request_id` only (route templates logged by handlers; never raw paths/query strings) |
| `run_configured` | DEBUG | `simulation.run` — `run_id`, `derivation_version`, `scope` (never seed) |
| `logging_ready` | INFO | `infrastructure.logging` |
| `app_started`, `app_stopping`, `app_stopped` | INFO | `infrastructure.lifecycle` |
| `database_ready` | INFO | `infrastructure.database` |
| `migration_started`, `migration_completed` | INFO | `infrastructure.migrations` — `revision`, `mode` |
| `malformed_request_id` | WARNING | `api.request` — reason only, never the raw inbound value |
| `readiness_check_failed` | WARNING | `infrastructure.database` |
| `replay_mismatch` | WARNING | `simulation.run` |
| `setup_failed` | ERROR | `infrastructure` |
| `transaction_failed` | ERROR | `infrastructure.database` |
| `unhandled_failure` | ERROR | `api.request` |
| `invalid_setup` | ERROR | `simulation.run` |

### Correlation and provenance

- `X-Request-ID`: inbound value must match `[A-Za-z0-9._-]{1,128}`; otherwise an operational hex id is generated. Echoed on success and error. Cleared after every request. **Not** a simulation id.
- Run logs may include `run_id`, `derivation_version`, `stream_scope` (purpose labels only). **Never log seeds** or draw values.
- Never log: bodies, `Authorization`, arbitrary query strings, wholesale settings, DSNs, credentials, prompts, raw LLM responses, memories, beliefs, communication content, embeddings, SQL parameters, vector values, **seeds**, or random draws.

`PALIMPSEST_TEST_DEBUG` may print concise test-harness DEBUG lines. Tests must not configure application logging during collection.

## Seeds, IDs, and clocks

- `SimulationRunConfig.seed` is required and non-negative (not a bool). Derivation-v2 runs also carry `PhysicalRules` (fingerprint participates in digests).
- Named streams: `create_named_stream(config, StreamScope(namespace, names))` via SHA-256. Distinct name tuples do not alias. Process-global `random` is untouched.
- Purpose labels for physical draws include `search_success`, `attack_hit`, `attack_damage`, `flee_success`, `flee_destination`, and `weather`.
- `derive_run_id` / `derive_scoped_id` / `derive_system_cause_id` use the same digest scheme.
- `LogicalClock` uses explicit `Tick` values. Domain contracts do not default to wall-clock or UUID factories.
- Exact LLM replay needs recorded responses or stubs (`LLM_REPLAY_REQUIREMENT = recorded_or_stub`). Satisfied by `deterministic_fake` or a `replay` recording store — see [LLM providers](llm-providers.md).

## Optional regions and migration (`runner-config-v44`)

Enable `v3_capability_flags.multi_polity_migration` together with the exact
`regions_migration` sibling. Both are required on v44. An object with the flag
off, a flag without the object, or the object on an older schema rejects. With
the channel absent, ordinary configurations still write v4 unless another
active feature selects a higher version.

| Required key | Shape and constraint |
| --- | --- |
| `regions` | Nonempty list of `{region_id, label}`; nonempty strings, unique IDs |
| `location_regions` | List of `{location_id, region_id}`; one membership per existing location; partial assignment allowed |
| `routes` | List of `{endpoint_a, endpoint_b, duration_ticks, fatigue_cost}`; existing undirected adjacent edges, no reverse duplicates |
| `max_arrival_wait_ticks` | Exact integer ≥ 0 |
| `residence_min_ticks` | Exact integer ≥ 1; analytical dwell threshold |
| `destination_memory_limit` | Exact integer ≥ 1; cap on the remaining recall budget |
| `destination_hop_limit` | Exact integer ≥ 1; bounded subjective route search |
| `cognition_mode` | `disabled` or `deterministic`; physics does not require cognitive bias |

Route duration is an exact integer ≥ 1; fatigue is finite and nonnegative.
Booleans do not count as integers. Memberships and routes may be empty. All
nested shapes reject unknown fields and null values; the wire supplies every
key explicitly. Encoding sorts regions/memberships by ID and edges by their
canonical endpoint pair. Absent optional sibling channels are omitted. Public
goods still require collective projects when composed with migration.

This executable example obtains a complete configuration with valid topology
and checks it through the real codec:

```python
from experiments.regional_migration_scenario import regional_migration_scenario
from simulation.runner_serialization import decode_runner_config, encode_runner_config

definition = regional_migration_scenario(seed=11, max_ticks=8)
config = definition.conditions[2].runner_config  # production-cognition arm
assert config.schema_version == "runner-config-v44"
assert decode_runner_config(encode_runner_config(config)) == config
```

Enabled objective writes use replay schema 21 / codec `v19`; otherwise the
existing highest-active-channel selector applies. No new database migration,
environment variable, command, or HTTP prefix is introduced. For movement
semantics see [Physical simulation](physical-simulation.md#discrete-regional-journeys).

Regional DEBUG logs contain IDs, counts, versions, and safe admission/recall
reason codes. Committed travel logs identify start/arrival/end only after commit;
prepared candidates are not reported as committed. `PALIMPSEST_LOG_LEVEL`
controls application verbosity. Never log destination beliefs, testimony,
observations, seeds, or whole configurations.

## See also

- [Architecture](architecture.md)
- [LLM providers](llm-providers.md)
- [Physical simulation](physical-simulation.md)
- [Development](development.md)


## Optional cultural contact (`runner-config-v45`)

`cultural_contact` is a required sibling only on `runner-config-v45` and has the
exact shape `{"mode": "disabled" | "deterministic"}`. It requires
`regions_migration` and an enabled `multi_polity_migration` flag; contact on
pre-v45, v45 without contact, v45 without regions, and contact without the
migration flag reject with stable safe reason codes. Absent contact keeps the
prior highest-active schema. `mode=disabled` is accepted but emits no contact
behaviour. Contact-active runs use the `(replay-v22, codec v20)` write pair;
contact-off regional runs stay on `(replay-v21, codec v19)`.

## Optional bounded symbolic language (`runner-config-v46`)

`symbolic_language_mode` is a per-agent cognition mode with values `disabled`
and `deterministic` (default `disabled`). It is not a `V2CapabilityFlags` or
`V3CapabilityFlags` slot and adds no new root sibling. A deterministic symbolic
mode requires the same agent's `semantic_naming_mode=deterministic`; symbolic
mode on any schema below v46 rejects with `symbolic_language_requires_v46`, and
symbolic mode without naming rejects with
`symbolic_language_requires_semantic_naming`. Bounded sense history is an
additive part of these modes: it adds no capability flag, no runner-config key,
and no configurable cap. Each binding or composition retains at most 16 sense
records, and disabled modes create none. `runner-config-v46` is emitted
only when at least one agent is deterministic, and it requires at least one such
agent (`v46_requires_symbolic_language`).

v46 reuses the active family root: with contact absent it carries the v44
regions root; with contact present it carries the exact v45 root including
`cultural_contact`. It never implies contact, regions, public goods, or cultural
memory by itself. Disabled mode keeps the prior highest-active schema and the
default write remains `runner-config-v4`. Replay stays `replay-v22`, the
persistence codec stays `v20`, and `communication.v1` is unchanged.


## Translation mode

`translation_mode` defaults to `disabled`. `deterministic` requires
`runner-config-v47` and deterministic `semantic_naming_mode`; it is a per-agent
cognition treatment, not a capability flag. `runner-config-v47` adds only the
per-agent mode, reuses the active v44/v45/v46 family roots, and never implies
contact, regions, public goods, collective projects, or symbolic language.
Symbolic-only runs remain on `runner-config-v46`; the default write remains
`runner-config-v4`. All weights, thresholds, caps, and channel deltas are locked
in `translation.v1` and are not serialized in runner JSON.

## Optional generational narratives (`runner-config-v48`)

`generational_narratives` is an optional run-level sibling that alone selects
`runner-config-v48`. It requires all of:

- exact `cultural_feature_provenance`;
- exact `population_lifecycle`;
- `V3CapabilityFlags.generational_population`;
- at least one deterministic `cultural_narrative_mode`.

```yaml
generational_narratives:
  generational_narratives_mode: deterministic
  source_loss_policy: observed_evidence_only
  theme_policy: observed_kind_and_lineage
  max_witnesses: 8
  max_records: 8
  max_transitions: 16
  max_declared_chain: 8
```

`disabled` is rejected; omit the object for off. `durable_records`,
`knowledge_repositories`, `historical_memory_layers`, and regional siblings are
accepted when independently valid but are never implied. A run with lifecycle
and cultural narratives but without this object stays on its prior highest
schema and keeps the `cultural-narratives.v1` policy. Default writes stay `v4`.


## Optional institution concepts (`runner-config-v49`)

`runner-config-v49` is emitted only when some agent's
`institution_concept_mode` is `deterministic`, and it requires at least one such
agent. It adds no root sibling and no write-pair: the per-agent mode reuses the
active lower family roots. `disabled` allocates no ledger, keeps every run
byte-identical, and the default write remains `runner-config-v4`.

`institution_concepts` is owner-scoped, opt-in, and not a capability flag. It
requires no semantic naming mode. Concepts carry only six closed pattern-strength
channels and opaque evidence; there is no world dictionary and no institution
type.

## Optional office succession (`runner-config-v50`)

`runner-config-v50` adds only the per-agent `office_succession_mode`
(`disabled` default, `deterministic` opt-in) and the explicit
`species_default_offices_v1` initialization profile. V50 is required when any
owner enables offices and is rejected when no owner does. Institution mode may
be enabled or disabled on v50. V49 keeps its exact keyset; adding
`office_succession_mode` to v49 rejects. Default runner writes remain
`runner-config-v4`, and replay/codec/migration pins are unchanged. Existing
species profiles stay office-disabled; the office profile is v50-only and
starts with empty office content.
