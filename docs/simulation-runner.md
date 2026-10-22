# Simulation Runner

[← Architecture](architecture.md) · [Back to README](../README.md) · [Generational runner →](generational-runner.md)

## Role

`SimulationRunner` owns configuration-driven run construction and the V1 tick lifecycle. It builds world bootstrap, cognition loops, and one `AgentRuntime` per registration from an immutable `SimulationRunnerConfig`, then advances only the authoritative `WorldEngine` (or durable `PersistentSimulationService`).

## Identities

- **Durable `RunId`:** storage/correlation identity; unique per arm/process.
- **`StochasticIdentity` + seed + scenario:** comparison identity for paired experiment arms. Equal values produce equal objective RNG streams across different durable run IDs and cognitive conditions.
- Cognition/experiment fingerprints never enter objective world RNG scopes.

Derivation version **v3** requires an explicit stochastic identity and fails closed on absence/mismatch during replay.

## Configuration

`SimulationRunnerConfig` is frozen and versioned (`runner-config-v4` write default
when every V2/V3 flag and V3 root is inactive; `runner-config-v1`…`v55` remain
decodable; generational runs use `runner-result-v3`, while legacy result v1/v2
stay accepted). Strict canonical JSON codecs reject unknown fields, duplicate keys,
non-finite numbers, credentials, and unsupported versions. Separate fingerprints
cover:

- full runner specification (`runner_config_fingerprint`)
- scenario/world
- cognitive condition
- provider settings (adapter kind/model/request knobs only; no secrets)

Run-level `V2CapabilityFlags` ride in `runner-config-v3+` (all default off).
Legacy v1/v2 payloads decode to default-off flags. Owned flags
(`advanced_social_inference`, `predictive_world_model`, `extended_self_model`,
`short_term_emotional_state`) may be enabled. `multi_hop_testimony_tracking`
is still unowned and fails closed at construction (`capability_unimplemented`).
`predictive_world_model` off is a passthrough: no hypotheses, no command bias,
and no world-model audit. `advanced_social_inference` off is a passthrough:
no mind hypotheses, no epistemic ledger, no command bias, and no mind audit.
When that flag is on, the same owner-scoped mind also keeps a flat epistemic
ledger (`max_depth` default 2, hard cap 3). Speech-act selection may judge a
belief as new, already known, secret, uncertain, or contradictory. Secret is
not a stored attitude. One agent does not receive another agent's private
cognition. Experiment M stays off the V1 regression gate.

`CommunicationStrategyMode` defaults to `DISABLED` and is not a capability flag.
`runner-config-v9` is accepted and is emitted only when some agent's mode is
`DETERMINISTIC`. That document carries every `runner-config-v8` cognition key
plus `communication_strategy_mode`. `DETERMINISTIC` is rejected on v1–v8, and
v9 is rejected when every agent's mode is `DISABLED`. A non-disabled
counterfactual mode is accepted on v8 or v9. A non-disabled communication
strategy is accepted on v9 or v10. `runner-config-v10` is accepted and is
emitted only when some agent's `ReputationMode` is `DETERMINISTIC`. That
document carries every `runner-config-v9` cognition key plus `reputation_mode`.
`DETERMINISTIC` reputation is rejected on v1–v9, and v10 is rejected when
every agent's reputation mode is `DISABLED`. `runner-config-v11` is accepted and is
emitted only when some agent's `SkillLearningMode` is `DETERMINISTIC`. That
document carries every `runner-config-v10` cognition key plus `skill_learning_mode`
and the locked rate keys. Reputation and the earlier cognition modes are accepted
on v11. `DETERMINISTIC` skill learning is rejected on v1–v10, and v11 is rejected
when every agent's skill mode is `DISABLED`. `runner-config-v12` is accepted and is
emitted only when some agent's `TeachingInteractionMode` is `DETERMINISTIC`.
That document carries every `runner-config-v11` cognition key plus
`teaching_interaction_mode` and the locked teaching weight keys. Skill learning
and the earlier cognition modes are accepted on v12. The write default stays
`runner-config-v4`. Experiments N, O, and P pair a disabled v4 arm with a
deterministic v9 arm. Experiment Q pairs a disabled v4 arm with a deterministic
v10 arm. Experiment R pairs a disabled v4 arm with a deterministic v11 arm.
Experiments S and T pair teaching off on v11 with both skill learning and
teaching on v12. Those experiments stay off the V1 regression gate.
`v1_regression_profile` still checks flags and tracing only. No capability
flag was added for reputation, skill learning, or teaching. `distributed_reputation@1`,
`skill_learning@1`, and `cultural_transmission@1` are analysis-only.

`CognitiveBudgetMode` defaults to `DISABLED` and is not a capability flag.
`runner-config-v22` is accepted and is emitted only when some agent's mode is
`ENFORCED`. That document carries every `runner-config-v21` cognition key plus
nine flat budget keys (`cognitive_budget_mode` and eight numeric limits).
`ENFORCED` is rejected on v1–v21, and v22 is rejected when every agent's budget
mode is `DISABLED`. Cultural narratives remain encodable on `{v21, v22}`. Prior
mode allowlists that ended at v21 widen through v22. Experiment AD
(`experiment-ad-cognitive-budgets`) and analysis `cognitive_budget@1` stay off
the V1 regression gate. Budgets never skip emitting one closed `AgentCommand`.

`RegionsMigrationSpec` activates on `runner-config-v44` and requires the owned
`multi_polity_migration` flag with an enabled regions/migration spec. It stays
optional on later schemas. `runner-config-v45` is the v44 family root plus the
required neutral `cultural_contact` sibling (`mode` only); contact requires both
`regions_migration` and `multi_polity_migration`, and v45 is rejected without
contact. `runner-config-v46` is mode-only: it reuses the active v44/v45 family
root (no new root sibling) and adds per-agent `symbolic_language_mode`. The
result also exposes detached `terminology_ledgers`, `symbolic_ledgers`, and
`initial_lifecycle_records` tuples in owner order; these are not part of the
runner result document and do not change replay or the codec. A
deterministic symbolic mode requires the same agent's deterministic
`semantic_naming_mode` and v46, and v46 is rejected when every agent is
disabled. Contact-active runs use the `(replay-v22, codec v20)` write pair;
contact-off regional runs stay on `(replay-v21, codec v19)`. Absent contact or
symbolic modes keep the prior highest-active schema, so the default write
remains `runner-config-v4`.

Generational runs select `runner-config-v55` only when an exact
`generational_run` sibling is present; they require population lifecycle, the
owned `generational_population` flag, explicit initialization, a finite tick
horizon, and disabled runtime-terminal stopping. The cognition keyset remains
v54 and every institutional mode may be disabled. Generational results use
`runner-result-v3`; legacy result defaults stay v2. See
[Generational runner](generational-runner.md).

Top-level `CognitionTraceSpec` (default disabled) rides in `runner-config-v4` only.
Prior versions decode to a disabled spec. Tracing is **not** a capability flag;
when enabled it may change `config_fingerprint` but must not change
`exact_trajectory_hash` for the same seed/scenario under deterministic fakes
(including when budget mode is `DISABLED`).

### Fingerprint vs trajectory identity

| Identity | Stable across schema bumps with flags-off / tracing-off? |
| --- | --- |
| `config_fingerprint` | **No** — may change when schema/key set grows (V2/V3 flags, `cognition_trace`, intentional `runner-config-v23+` encode) |
| `exact_trajectory_hash` / objective commit identity | **Yes** — same seed, scenario, stochastic identity; V2/V3 flags off; tracing on or off |
| `replica_normalized_trajectory_hash` | **Yes** under the same conditions (run-derived IDs stripped) |

V3 scaffolding: the default write stays `runner-config-v4` when every
`V3CapabilityFlags` entry and V3 root is inactive. Enabling an owned flag/root
emits its matching schema version (v23+); unowned or illegal combinations still
fail closed at `SimulationRunner.from_config` with stable reason codes. Legacy
`v1`…`v43` decode synthesizes default-off V3 flags and roots without changing
objective trajectory identity.

Golden `runner-config-v2` fixtures live under `tests/fixtures/runner_configs/`.

Use `SimulationRunner.from_config(...)` with injected factories/ports. The runner must not import environment settings, SQLAlchemy, or API code.

## Tick lifecycle

1. Cognition **prepare**: perception → planning → proposed command + scientific artifacts (no command-dependent memory intents yet).
2. Trusted intervention may select the effective command.
3. Runtime **bind**: memory/internal-state completion for the effective command; at most one submission; pending subjective finalization recorded.
4. Objective **commit** via the single authority path.
5. Subjective **finalize** (idempotent). Post-objective failure stops before the next tick and remains recoverable; never roll back a committed tick.

Scheduling is sequential in bootstrap registration order. Concurrent cognition is out of scope for V1.

## Stop and results

Stop policies cover max ticks and closed failure modes. Generational runs add
generation-horizon, extinction, inclusive population-threshold, and trusted
experiment-criterion selectors after the completed boundary; see
[Generational runner](generational-runner.md) for precedence and latching.
Results are versioned machine-readable documents with stop reason, tick counts,
config fingerprint prefixes, and exact vs replica-normalized trajectory hashes.
Seeds, credentials, prompts, and raw provider output stay out of logs and result
documents.

## Recovery and inspection

Committed objective ticks with interrupted subjective finalization rehydrate without rerunning cognition. Inspection and replay use detached projections — never live `WorldEngine` mutation. See [Research API](research-api.md) and [Persistence](persistence.md).

## LLM reproducibility

External LLM runs are reproducible only with deterministic fakes or recorded/replayed validated outputs. `ExactReproducibilityMode.REQUIRED` allows `deterministic_fake` and `replay` only (`live` / `record` / `cache` fail closed). Pass `RecordingStoreSettings` beside credentials on `RunnerDependencyFactories` for `record` / `cache` / `replay`; store settings never enter provider JSON or fingerprints. See [LLM providers](llm-providers.md) for modes, cache keys, wrap order, and fork/matrix namespace isolation.

## Tests

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_simulation_runner_construction.py \
  tests/unit/test_simulation_runner.py \
  tests/unit/test_runner_results.py \
  tests/unit/test_simulation_runner_e2e.py \
  tests/unit/test_v2_golden_runner_configs.py \
  tests/unit/test_v1_regression_gate.py -q
```


## Translation export

Enabled runs export owner-ordered `translation_ledgers` alongside terminology
and symbolic ledgers. The runner logs only ledger and mapping counts. Each
mapping holds digest-derived identity, bounded targets, evidence, applications,
status, fit, strength, and tick bounds; no raw foreign or own token is required
outside the owner ledger. Disabled runs export an empty tuple and remain
byte-identical.

## Owner-ordered subjective exports

`SimulationRunnerResult` exports owner-ordered `social_norm_ledgers`,
`social_convention_ledgers`, `possession_legitimacy_ledgers`, and
`institution_concept_ledgers` alongside terminology, symbolic, translation, and
cultural-narrative ledgers. Disabled owners contribute nothing, so flags-off
bytes are unchanged. `runner-config-v49` adds only the per-agent
`institution_concept_mode`; the reverse gate requires a deterministic mode.
Exports never flow back into cognition.

## Office checkpoint and export

`office_concept_ledgers` is owner-ordered in runner results. Enabled owners
export exactly one ledger each (including an empty ledger for an admitted
learner); disabled owners export none. Runtime checkpoints validate ledger
ownership, restore office state alongside other subjective ledgers, restore the
engine tick cursor for continuation parity, and reject cross-owner or duplicate
runtime state. Checkpoint round-trips are runtime-object equality and required
for fork isolation; they do not claim durable process restart or subjective
replay. Objective events and durable snapshots remain a separate contract. See `docs/configuration.md` for
`runner-config-v50` and `species_default_offices_v1`.
