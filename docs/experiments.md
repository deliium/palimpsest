# Experiments Framework

[← Generational runner](generational-runner.md) · [Back to README](../README.md) · [V2 benchmark suite →](v2-benchmark-suite.md)

## Trust boundary

The `experiments` package is trusted outer orchestration. It may coordinate public `simulation` and read-only `analysis` contracts. Domain packages (`world`, `agents`, `agents.cognition`, `memory`, `social`) and `simulation` must never import `experiments` or receive collectors, truth specifications, objective snapshots, or analysis results.

Objective instrumentation is post-commit observation only. Collectors never flow back into cognition, memory formation, prompts, or action selection.

## Catalog (A–Q)

| ID | Treatment |
| --- | --- |
| A | Exact/reference memory vs V1 reconstructive vs opt-in `RECONSTRUCTIVE_V2` |
| B | Imagination (future simulation) disabled vs enabled |
| C | Mortality disabled vs enabled (non-lethal physical rules overlay) |
| D | Controlled curiosity / safety / belonging / status drive profiles |
| E | Inject one controlled false `Tell` through ordinary communication; measure propagation without exposing the objective truth label to agents |
| F | Sleep consolidation `DISABLED` (`runner-config-v4`) vs `DETERMINISTIC` (`runner-config-v5`), shared seed and scenario. Not on the V1 regression gate |
| G | Reflection `DISABLED` (`runner-config-v4`) vs `DETERMINISTIC` (`runner-config-v6`), shared seed and scenario, default interval. Not on the V1 regression gate |
| H | Identity `extended_self_model` off vs on, both arms `runner-config-v4`, scenario `identity-divergence-v1`. One agent gets repeated search success and the other a failed flee. Not on the V1 regression gate |
| I | Causal world model `predictive_world_model` off vs on, both arms `runner-config-v4`, shared seed and scenario. Comparison metric `causal_world_model@1` runs after the run. Not on the V1 regression gate |
| J | Prospective imagination `DISABLED` (`runner-config-v4`) vs `DETERMINISTIC` (`runner-config-v7`), shared seed and scenario. Comparison metric `prospective_imagination@1` runs after the run. Not on the V1 regression gate |
| K | Counterfactual reasoning `DISABLED` (`runner-config-v4`) vs `DETERMINISTIC` (`runner-config-v8`), shared seed and scenario. Comparison metric `counterfactual_reasoning@1` runs after the run. Not on the V1 regression gate |
| N | Communication strategy `DISABLED` (`runner-config-v4`) vs `DETERMINISTIC` (`runner-config-v9`), shared seed and scenario. Trust comparison. Not on the V1 regression gate |
| O | Same arm shape as N, for deception labels. Not on the V1 regression gate |
| P | Same arm shape as N, for information cascades. Not on the V1 regression gate |
| Q | Reputation `DISABLED` (`runner-config-v4`) vs `DETERMINISTIC` (`runner-config-v10`), shared seed and scenario. Comparison metric `distributed_reputation@1` is analysis-only and is not run by the catalog. Not on the V1 regression gate |
| R | Skill learning `DISABLED` (`runner-config-v4`) vs `DETERMINISTIC` (`runner-config-v11`), shared seed and scenario. Comparison metric `skill_learning@1` is analysis-only and is not run by the catalog. Not on the V1 regression gate |
| S | Teaching `DISABLED` on `runner-config-v11` with skill learning `DETERMINISTIC`, vs both modes `DETERMINISTIC` on `runner-config-v12`. Shared seed, scenario, and stochastic identity. Comparison metric `cultural_transmission@1` is analysis-only and is not run by the catalog. Not on the V1 regression gate |
| T | Same mode pair and shared identity as S, for skill specialization. `cultural_transmission@1` stays off the V1 regression gate |

Builders share scenario, seed, and stochastic identity across paired arms; only declared treatment dimensions differ. Condition/config fingerprints change when treatments change.

**Experiment A** has three arms (`a-reference`, `a-reconstructive`, `a-reconstructive-v2`). The V1 regression gate uses `experiment_a_memory_v1_arms()` / `EXPERIMENT_A_V1_CONDITION_IDS` so only the two V1 arms run — a broken V2 path cannot fail V1 `exact_trajectory_hash` baselines. V2 audits are harvested in-run, composed via `map_recall_audits_to_dynamics_report`, and never agent-visible.

Catalog builders emit current write schema (`runner-config-v4`) with all `V2CapabilityFlags` / `V3CapabilityFlags` default-off and `CognitionTraceSpec` disabled. Use `experiments.catalog.v1_regression_profile(config)` to assert the V1-equivalent profile (raises `v1_regression_flags_enabled` if any V2 flag is on, or `v1_regression_trace_enabled` if tracing is enabled). Use `v3_scaffolding_profile` for all V3 flags off, and `v2_regression_profile` (V3-off + V1 regression rules; does not require every V2 cognition mode `DISABLED`). Capability flags and tracing are configuration identifiers only; they do not change experiment-definition schema (`experiment-definition-v1`). Matrix finalize selects `runner-config-v55` first when `generational_run` is present, then the highest active feature family; default finalize stays `v4` when all flags are off.

Network-free regression gate: `tests/unit/test_v1_regression_gate.py` (short ticks, catalog A–E + reference scenario). Experiments F, G, H, I, J, K, N, O, P, Q, and R are additive and are not part of that gate. The default config write stays `runner-config-v4`. `runner-config-v5` is emitted only when some agent's consolidation mode is not `DISABLED`. `runner-config-v6` is emitted only when some agent's reflection mode is not `DISABLED`, and that document may also carry consolidation. `runner-config-v8` is emitted only when some agent's counterfactual mode is not `DISABLED`, and that document may also carry consolidation, reflection, and prospective imagination. `runner-config-v9` is emitted only when some agent's communication strategy mode is `DETERMINISTIC` and every reputation mode is `DISABLED`. That document carries the v8 cognition keys plus `communication_strategy_mode`. A non-disabled strategy is also accepted on `runner-config-v10`. `runner-config-v10` is emitted only when some agent's reputation mode is `DETERMINISTIC`, and that document carries every v9 cognition key plus `reputation_mode`. Reputation and the earlier cognition modes are also accepted on `runner-config-v11`. `runner-config-v11` is emitted only when some agent's skill-learning mode is `DETERMINISTIC`. That document carries every v10 cognition key plus `skill_learning_mode` and the locked rate keys. No capability flag was added for skill learning. `v1_regression_profile` is unchanged. Experiment G checks a shared objective hash through the reflection tick and an audit on the deterministic arm only. It does not preload the decision-divergence memories, and it does not require a later command to change.

## Reference scenario (V1 gate)

`experiments.reference_scenario.build_reference_scenario()` builds the canonical five-agent / 48-tick fixture used by end-to-end proofs:

- Connected camp/spring/grove/ridge map with regenerating food and water
- Reconstructive memory + imagination enabled; deterministic-fake provider
- Sparse milestone arbiter (extract/drink/eat/tell/colocate/lethal attack) with a bounded override budget
- Early scheduled death proving N+1 terminal status and no later applied actions
- Public receipts/projections only in Task 20 tests (no `runner.engine` / `WorldState`)

Wire the arbiter with `SimulationRunner.set_intervention_arbiter(...)` before `run()`.

## Experiment E

The story enters as a normal structured `Tell` at a configured tick/source/recipient. The utterance has no `is_false` marker. A separate analysis-only `StoryTruthSpec` and intervention fingerprint identify the controlled treatment. Multi-hop lineage uses parent/root communication IDs on declared transmission metadata.

## Persistence

Append-only experiment records (Alembic `0010`, reconciled with run-control membership in `0011`):

- `experiment_definitions` — schema version, payload hash, definition fingerprint
- `experiment_assignments` — condition × seed ordinal × replicate → run ID
- `experiment_results` — one immutable final result per assigned run

Identical re-writes are idempotent; divergent reuse conflicts. SQLAlchemy adapter: `persistence.create_experiment_record_repository(...)`. In-memory port: `InMemoryExperimentRecordRepository`. The `experiments` package never imports SQLAlchemy.

## Coordinator

`ExperimentCoordinator` materializes assignments in condition × seed × replicate order and runs one fresh `SimulationRunner` per arm. Optional story intervention arbiter binds before pending subjective state is created.

## Experiment matrices (`experiment-matrix-v1`)

Additive research batch orchestration over catalog applicators. Matrix documents expand into existing `experiment-definition-v1` arms + `SimulationRunnerConfig`; they do **not** bump runner-config schema sets or own `multi_hop_testimony_tracking`. Matrix batch runs stay **off** the V1 regression gate.

### Locked axes and levels

| Factor id | Level ids | Effect |
| --- | --- | --- |
| `memory_type` | `reference`, `reconstructive`, `reconstructive_v2` | `MemoryMode` |
| `mortality` | `disabled`, `enabled` | `MortalityMode` |
| `imagination` | `disabled`, `enabled` | `ImaginationMode` only |
| `reflection` | `disabled`, `deterministic` | `ReflectionMode` |
| `tom` | `off`, `on` | `advanced_social_inference` only |
| `resource_scarcity` | `scarce`, `abundant` | scenario resource quantities (layout preserved) |
| `seasonality` | `off`, `on` | clear / set `EnvironmentalDynamicsSpec` |
| `cognitive_budget` | `disabled`, `low_cost`, `high_cost` | `CognitiveBudgetMode` + AD presets |
| `lifespan` | `short`, `long` | lifecycle lifespan/stage presets (8/24 ticks) |
| `learning_model` | `practice_only`, `teaching_supported` | skill-learning and teaching modes |
| `teaching_frequency` | `low`, `high` | teaching offer/rate presets |
| `record_availability` | `absent`, `present` | durable-record sibling + cultural provenance |
| `innovation_rate` | `low`, `high` | acquisition-rate preset |
| `migration` | `isolated`, `connected` | regional template + owned migration flag |
| `population_size` | `small`, `large` | lifecycle capacity/entry rate only |
| `institution_support` | `off`, `on` | institution-concept and office-succession modes |
| `cognitive_architecture` | `v1_memory`, `full_v2` | registered mode preset, schema preserved |
| `generational_resource_scarcity` | `scarce`, `abundant` | proportional resource scaling on v55 |

The generational factors are valid only on an embedded `runner-config-v55` with explicit lifecycle, initialization, and `generational_run`. They never change `schema_version`, seed, scenario identity, roster, or generation schedule. Legacy `resource_scarcity` keeps its fixed territorial-layout contract; use `generational_resource_scarcity` for the proportional v55 treatment.

Constraints accept only `exclude_combos`. Expansion requires ≥2 conditions after filtering.

**Base config:** `expand_matrix` accepts an embedded `SimulationRunnerConfig` only. A `catalog` base id may appear in the matrix JSON schema, but expansion fail-closes with `catalog_base_unresolved` until a later plan wires catalog-builder resolution — embed the runner config instead.

### Schema finalize (highest-wins)

Factor applicators never set `schema_version`. After levels apply, the final compatibility gate rejects contradictory effective modes with `incompatible_factor_combination`. `finalize_matrix_cell_config` then selects `runner-config-v55` first when `generational_run` is present; otherwise it picks the first matching feature family (budget → `v22`, cultural narratives → `v21`, semantic naming → `v20`, artifact interpretation → `v19`, environmental dynamics → `v14`, reflection → `v6`, else `v4`). A generational factor on a non-v55 base fails with `generational_base_required`.

### `group_role` composition

1. Optional named `groups` overlay match → that role
2. Else `treatment` if any selected level is `treatment`
3. Else `control` if any is `control`
4. Else `neutral`

Labels are researcher metadata only — not world friend/enemy/leader roles.

### Resume and crash recovery

Filesystem store: `manifest.json` + `cells/<cell_id>.json` (+ completion sidecars). Validity requires matching matrix/cell/config fingerprints, schema versions, and `RunVersionIdentity`. On open, any cell `running` without a valid completion resets to `pending`. Divergent rewrite of the same matrix fingerprint fails closed. Process-local concurrency only (`max_concurrency`, default `1`); durable persistence requires serial execution. Durable cells with `max_ticks >= 1000` and checkpoints disabled emit WARN `[matrix] long_run_checkpoint_recommended cadence_ticks=100` — use `long_run_persistence_spec` / `long_run_checkpoint_policy` rather than in-DB snapshot DELETE.

### CLI (no HTTP)

Composition package `research_runner` (forbids `api`):

```bash
uv run palimpsest-matrix run --matrix matrix.json --manifest-root ./matrix-out
uv run palimpsest-matrix resume --matrix matrix.json --manifest-root ./matrix-out
uv run palimpsest-matrix status --manifest-root ./matrix-out
uv run palimpsest-matrix aggregate --matrix matrix.json --manifest-root ./matrix-out
uv run palimpsest-matrix aggregate --matrix matrix.json --manifest-root ./matrix-out --metric-summary
# opt-in cultural evidence and repeated-seed comparison
uv run palimpsest-matrix --code-revision "$PALIMPSEST_CODE_REVISION" run \
  --matrix matrix.json --manifest-root ./matrix-out --cultural-metrics
uv run palimpsest-matrix --code-revision "$PALIMPSEST_CODE_REVISION" aggregate \
  --matrix matrix.json --manifest-root ./matrix-out --cultural-summary \
  --cultural-contrast control-condition:treatment-condition --confidence 0.95
# or: python -m research_runner …
```

Optional `--print-fingerprint` prints the matrix fingerprint only. Never dump full configs or seeds by default. Collectors for matrix experiment ids use summary + trajectory + catalog fallback. Aggregates are `matrix-aggregate-v1` analysis-only documents.

Completed cells may write optional `cells/<cell_id>.metrics.json` sidecars (encoded `MetricDocument` payloads, sorted by family) when present/partial documents exist. `--metric-summary` reads those sidecars and writes sibling `metric-summary.json` (`matrix-metric-summary-v1`) beside the aggregate — never replacing it. Missing sidecars contribute no numeric rows (not zeros). Phenomenon indicator panels and metric summaries are analysis-only and stay off the V1 regression gate.

`RunVersionIdentity.code_revision` is optional metadata: pass `--code-revision` or set `PALIMPSEST_CODE_REVISION`. Empty is allowed for ordinary runs; generational archives require a nonempty revision. The CLI never invents a wall-clock surrogate.

Cultural capture adds `cells/<cell_id>.cultural-evidence.json`
(`cultural-evolution-evidence-v1`) and `cells/<cell_id>.cultural-metrics.json`
(`cultural-cell-metrics-v1`). `--cultural-summary` writes sibling
`cultural-metric-comparison.json` (`cultural-metric-comparison-v1`) from
verified completed artifacts. `--cultural-contrast CONTROL:TREATMENT` is
repeatable and must name known, distinct condition IDs; `--confidence` defaults
to `0.95`. Both require `--cultural-summary`. Legacy `aggregate.json`,
`metric-summary.json`, and `.metrics.json` schemas are unchanged. Capture is not
backfilled for completed cells: a missing/mismatched pair fails preflight, and a
sealed archive with lost capture is not rerun. Evidence and cell artifacts are
bounded to 64 MiB, embedded `rows_json` to 16 MiB, and JSON depth to 32;
duplicate keys, non-finite numbers, unknown fields, and symlinked or escaping
paths fail closed. Identical artifacts are idempotent; divergent content is a
conflict. The legacy `p05`/`p95` metric-summary fields remain empirical
percentile ranges, not confidence intervals. See
[Cultural evolution metrics](cultural-evolution-metrics.md).

## V2 benchmark suite

Composition/validation scenarios (`bench-01`…`bench-16`), observer graphical world, scientific invariants, and zero-install acceptance are documented in [V2 benchmark suite](v2-benchmark-suite.md). Example matrix fixture: `tests/fixtures/matrices/v2-benchmark-suite.json`. The suite stays off the V1 regression gate and does not own `multi_hop_testimony_tracking`.

## Experiment AY: Regional migration

AY (`regional_migration@1`) stays off the V1 gate. Its connected five-location graph spans three regions,
with local water/food and contrasting temperatures; the remote endpoint requires
multiple adjacent steps. Region labels do not determine costs or environments.

| Arm | Treatment |
| --- | --- |
| `ay-channel-off` | Exact nonregional baseline configuration |
| `ay-physics-only` | Regional durations/costs with destination bias disabled |
| `ay-accurate-evidence` | Production cognition learns from normal perception and owner-scoped memory; no command override or initial goal injection |
| `ay-false-stale-testimony` | Diagnostic encounter and historical false water report via admitted `Tell`; recipient decisions remain cognitive |
| `ay-visit-return` | Explicit diagnostic commands demonstrate a short interregional visit and return |
| `ay-blocked-arrival` | Explicit diagnostic departure toward a full destination demonstrates timeout |

The coordinator and matrix assignment runner attach the same deterministic
diagnostic arbiters; collectors only read detached outcomes. Scripts are
diagnostic treatments, not evidence of emergent migration. Population entry,
dependency care, and transport are separate composition factors; AY does not
require them. There is no civilization-success threshold.

Reproduce all arms with normal cognition and metrics:

```python
import asyncio
from experiments.coordinator import ExperimentCoordinator
from experiments.regional_migration_scenario import regional_migration_scenario

definition = regional_migration_scenario(seed=11, max_ticks=8)
results = asyncio.run(ExperimentCoordinator(definition).run_all())
assert len(results) == 6
```

Same seeds and configurations reproduce normalized trajectories and results.
For matrix operation use the existing [matrix workflow](#experiment-matrices-experiment-matrix-v1);
the registered experiment ID is `regional_migration@1` and v44 round-trips through
the matrix codec. Keep full config/factor identity when comparing arms.

### Regional evidence and denominators

- `regional_population@1`: completed-boundary **living** populations, person-ticks,
  entries, deaths, and assigned/unassigned coverage. Travellers waiting at origin
  count there; corpses are excluded from demographics but retain physical capacity.
- `regional_migration@1`: raw origin–destination crossings separately from
  dwell-qualified migrations. Arrivals, successful fleeing, and legacy movement
  effects count once per person; departure, failed flee, timeout, and same-region
  moves are not interregional arrivals. Transport counts each participant.
- `regional_destination_beliefs@1`: available owner evidence and post-run
  comparison coverage, never a destination oracle for cognition.

Initial placement/entry establishes residence without migration. A different
assigned-region boundary begins a candidate; the arrival boundary counts as
dwell tick 1 if alive and still present. At `residence_min_ticks`, emit one
migration from established residence and retain the candidate arrival tick.
Without prior residence, qualification establishes a baseline only. A short
visit followed by return cancels; a later return after qualification may qualify
as a return migration. A third region replaces the candidate. Unassigned
boundaries clear the candidate but retain residence; death cannot qualify dwell.

Population conservation is arrivals minus departures plus entries minus deaths,
with explicit assigned/unassigned transitions. Qualified migration need not equal
raw crossings. Missing subjective evidence and incomplete prefixes expose
coverage rather than invented zeros. Metric documents retain the numerical
policy, numerators, denominators, and observation coverage.

## Logging

DEBUG/INFO may include experiment/condition/run IDs, ordinals, counts, versions, and hash prefixes. Never log seeds, story content, truth labels, drive values, prompts, credentials, or canonical JSON payloads.

## Tests

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_experiment_definitions.py \
  tests/unit/test_experiment_interventions.py \
  tests/unit/test_experiment_coordinator.py \
  tests/unit/test_experiment_persistence_contracts.py \
  tests/unit/test_v1_regression_gate.py \
  tests/unit/test_v2_flag_defaults.py \
  tests/architecture/test_experiment_instrumentation_isolation.py -q
```

## See also

- [Physical simulation](physical-simulation.md#discrete-regional-journeys)
- [Configuration](configuration.md#optional-regions-and-migration-runner-config-v44)
- [Analysis metrics](analysis-metrics.md)

## Experiment AZ: Multiple societies (analytical only)

AZ (`multiple_societies@1`) stays off the V1 regression gate. It composes
existing region, journey, and communication channels with deterministic
naming, norms, conventions, narratives, artifact interpretation, subjective
valuation, exchange, collective projects, and public goods so long-running,
region-separated populations can be compared **after the run**. It creates no
Nation, Country, Polity, Society, or Community entity and adds no command,
event, perception field, or capability flag. The `runner-config-v44` channel
admits the same cultural mode keys as `v43`; this is channel composition, not a
new schema version.

| Arm | Treatment |
| --- | --- |
| `az-channel-off` | Exact nonregional `runner-config-v4` baseline |
| `az-isolated` | Two regions; co-located talk within each population, no interregional journey |
| `az-contact` | Same world plus one explicit diagnostic visit and post-arrival cross-contact |

The deterministic arbiter issues ordinary admitted commands; collectors never
feed evidence back to agents. Detection produces at least two candidate
communities, the isolation audit reports zero `unexplained` cross-community
edges in the reference configuration, and per-dimension divergence documents
are computable (missing channels stay `absent`, never zero).

Reproduce:

```python
import asyncio
from experiments.coordinator import ExperimentCoordinator
from experiments.multiple_societies_scenario import multiple_societies_scenario

definition = multiple_societies_scenario(seed=23, max_ticks=8)
results = asyncio.run(ExperimentCoordinator(definition).run_all())
assert len(results) == 3
```

### Analytical boundary

`analysis.society_emergence` clusters living persons from detached residence,
interaction, and trust lanes. `analysis.society_divergence` measures pair-scoped
Jensen–Shannon divergence per dimension. `analysis.society_isolation` classifies
cross-community evidence edges as `journey_explained` or `unexplained` using
logical ticks. These labels are researcher output only; they never enter
cognition, memory, prompts, admission, or observations. `unexplained > 0` is a
finding, not an auto-remediation.


## Experiment BB: Bounded compositional symbols

`compositional_symbols@1` exercises the owner-scoped composition layer off the
V1 gate. Arms: `bb-off` (v4 baseline, symbolic disabled), `bb-single` (one
population, naming plus symbolic deterministic), `bb-isolated` (two
region-separated populations without contact), and `bb-contact` (two
region-separated populations with owned contact). The non-run
`bb-unsupported` fixture asserts that symbolic mode without semantic naming
fails closed. The arbiter asserts structural facts only: off emits no
compositions, isolated populations cannot exchange composed messages, and
contact borrowing requires delivered communication. It never asserts
convergence, agreement, or a "better language".

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_experiment_bb.py -q
```

## Experiment BC: Longitudinal semantic drift

`semantic_drift@1` exercises bounded sense history and detached semantic
metrics off the V1 gate. Arms: `bc-off` (v4 baseline, naming and symbolic
disabled), `bc-stable` (one population, both modes deterministic),
`bc-isolated` (two region-separated populations without contact), `bc-contact`
(two region-separated populations with owned contact), and `bc-generation`
(generational population with a bounded lifespan and explicit blank-slate
bootstrap). The non-run `bc-unsupported` fixture asserts that symbolic mode
without semantic naming fails closed.

The arbiter asserts structural facts only: off arms have no sense history;
enabled histories are ordered, capped at 16 records, and never exceed the
recorded sense revision; isolated populations acquire no cross-group meaning
without delivered communication; generations start blank-slate. It never
asserts that drift, stability, or divergence "should" occur.

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_experiment_bc.py -q
```

## Experiment BA: Cultural contact

`cultural_contact@1` composes the owned regions/migration substrate with a
required neutral `cultural_contact` sibling on `runner-config-v45`. Contact
records only objective co-presence after a qualifying cross-region relocation
(a completed journey arrival or a successful cross-region `Fled`); it is not a
relationship, trust update, group identity, or policy.

Arms: `ba-channel-off` (v4 baseline), `ba-isolated` (contact recording enabled
but no cross-region journeys), `ba-contact-trade`, `ba-contact-teaching`,
`ba-contact-conflict-cooperation`, and `ba-contact-kinship` (explicit
absent-kinship assertion). Diagnostic command fixtures exercise the analytics;
the arbiter asserts structural evidence only (contact events, family coverage,
cross-community interaction counts, explicit kinship availability) and never
asserts that convergence, assimilation, war, or cooperation "succeeded".

Reproduce with the standard experiment coordinator:

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_experiment_ba.py -q
```


## Experiment BD — cross-cultural translation

`cross_cultural_translation@1` is registered off the V1 gate. Arms: `bd-off`,
`bd-naming-only`, `bd-shared-observation`, `bd-demonstration`,
`bd-repeated-teaching-artifact`, `bd-ambiguous-wrong`, plus the non-run
`bd-unsupported` fixture. The arbiter asserts only structural facts: off arms
emit no mappings or overlays; enabled mappings are bounded and monotonic;
isolated populations do not share mappings without a delivered/shared/artifact
channel; ambiguous mappings are not forced to one answer; wrong mappings are not
corrected; and no agent receives community labels or analysis results.

## Experiment BE — multi-generational historical narratives

Off-gate `generational_narratives@1` compares bounded owner-scoped lineage arms:

- `be-off` — V2 narrative-only on the prior schema, no lifecycle or
  generational spec;
- `be-witness-death`, `be-record-backed`, `be-record-loss`, `be-merge-edit`,
  `be-theme-coverage`, `be-objective-comparison`;
- `be-unsupported` — missing lifecycle/provenance/flag fails closed with
  `generational_narratives_requires_*`.

The arbiter asserts only structural facts: off arms carry no V2 fields; on arms
stay within witness/record/transition caps and require `runner-config-v48`.
All-witnesses-dead lineages remain in living carrier ledgers and are never
auto-retired. No arm injects objective truth, generation indices, metric rows,
founder worship, heroization, moral verdicts, or forced convergence.

## Experiment BF — analytical institution emergence

Off-gate `institutionalization@1` composes already-owned generational, kinship,
mentorship, repository, collective-project, public-good, norm, convention, and
exchange channels. Arms:

- `bf-baseline` — flags-off `runner-config-v4`, byte-identical to the pre-plan
  baseline trajectory;
- `bf-institution-off` — same composed channels on the highest active non-v49
  schema with `institution_concept_mode=disabled`;
- `bf-institution-on` — `runner-config-v49` with a deterministic owner-scoped
  `institution_concept_mode`.

The arbiter asserts structural facts only: at least one institution candidate is
computable, persistence documents emit for every candidate, owner-scoped concept
ids never cross owners, restored checkpoints match pre-save ledgers, and the
flags-off baseline keeps its trajectory. No government, religion, court, police,
corporation, or political party exists; candidates are opaque analytical pattern
bundles and persistence classifications.

```python
from experiments.coordinator import ExperimentCoordinator
from experiments.institutionalization_scenario import institutionalization_scenario

definition = institutionalization_scenario(seed=23, max_ticks=16)
results = await ExperimentCoordinator(definition).run_all()
```

## Experiment BG — subjective offices and succession

`offices_succession@1` is an off-gate experiment with a flags-off v4 golden
baseline, a composed office-mode-off control at v49, and v50 office-on arms.
It seeds no office, legitimate successor, desired consensus, or actor script.
Arms use the existing physical and communication channels; `office-on-contested`
is a matched repeat intended to expose divergence rather than force it. The
scenario reports whatever appears, including no recognized office, replacement,
split, vacancy, abandonment, or role change. Arbiter checks assert structure,
owner privacy, availability, and reproducibility, not political success.

## Experiment BH — collective decisions

`collective_decisions@1` is an off-gate experiment with an unchanged flags-off
v4 baseline, a composed decisions-off control at v49, decisions-on v51 arms, and
a matched opportunity-limited v51 arm. It seeds no opinions, delegates,
winners, institutions, or successful decisions. The scenario uses existing
physical and communication channels and reports whatever appears, including no
proposal, no consensus, disagreement, blocked attempts, noncompliance, or
silence. Arbitration checks structure, owner privacy, availability, and
reproducibility, never a political outcome.

## Experiment BI — mediation opportunities (`mediation_opportunities@1`)

Off the V1 gate. Arms cover the default-v4 baseline, a prior-schema
mediation-disabled control, mediation-on, relationship/reputation contrast,
accepted-role/norm/institution contrast, and an opportunity-limited condition.
No dispute, account, mediator occupation, acceptance, or settlement is seeded.
The mode-off arm uses the highest legal prior schema for the same non-mediation
modes. Detached metrics are `conflict_mediation@1` and
`mediation_role_emergence@1`; successful mediation is not required.


## Institutional memory opportunities (`institutional_memory@1`, BJ)

Experiment BJ is off the V1 A–E gate. Its six arms contrast the v4 baseline, a
v52 mediation/memory-off control, a v53 memory-on treatment, and record,
teaching, and limited-opportunity arms. No arm preseed roles, records, learned
entries, or successful handovers. Completed runs may export enabled-empty
owner ledgers; detached continuity and provenance metrics report whatever
occurred, including no acquisition. The changed material topology in extra
opportunity arms is labeled as such and is not a mode-only causal contrast.


## Institutional decay opportunities (`institutional_decay@1`, BK)

Experiment BK is off the V1 A–E gate. Six arms: `bk-baseline`, `bk-decay-off`
(v53 memory/office/concept composition), `bk-decay-on` (identical v54 plus
per-owner decay), `bk-record-opportunities`, `bk-teaching-opportunities`, and
`bk-limited-opportunities`. Off/on arms pair seed, world, agents and objective
conditions; only declared existing opportunities differ. No collapse, death,
resource shock, record destruction, abandonment or cultural-change tick is
scheduled. Zero stable institutions and zero collapses are valid outcomes.


## Experiment BL — generational runner (`generational_runner@1`)

Off the V1 A–E gate. BL composes the real AY regional world, routes, and
migration physics with an explicit demographic calendar rather than a synthetic
counter. Conditions are `bl-single-cohort` (demography disabled),
`bl-generational-unassisted` (advancing entries at several locations without a
migration order), and `bl-generational-contact` (the same entry schedule with
the declared AY diagnostic treatment). The unassisted arm has no forced
migration and no guaranteed isolation; isolated-community evidence comes from
the separate AZ sampler fixture.

The experiment replaces lifecycle, initialization, and generational settings on
the final config instead of assuming a base config preserves them. Modes stay
explicit and content-empty, and no founder state, parents, or knowledge is
copied to entrants. The catalog exposes `generational_runner@1`; run archives
and per-assignment recipes are owned by the generational execution layer, not a
new metric family. See [Generational runner](generational-runner.md) for the
archive schemas and CLI.


## Experiment BM — generational comparison (`generational_comparison@1`)

Off the V1 A–E gate. BM builds five independent paired comparisons over one
canonical AY-derived `runner-config-v55` base (`seed=23`, `max_ticks=12`,
minimum 8). Every pair shares seed, stochastic identity, world layout, founder
roster, stop horizon, generation schedule, and initialization; only the declared
axis differs.

| Pair | Control → treatment | Axis |
| --- | --- | --- |
| `bm-oral-vs-records` | `absent` → `present` | `record_availability` |
| `bm-short-vs-long-lifespan` | `short` → `long` | `lifespan` |
| `bm-isolated-vs-connected` | `isolated` → `connected` | `migration` |
| `bm-low-vs-high-teaching` | `low` → `high` | `teaching_frequency` |
| `bm-reference-vs-reconstructive-memory` | `reference` → `reconstructive` | `memory_architecture` |

Ten condition ids are produced in pair order:
`bm-oral-vs-records-{control,treatment}`,
`bm-short-vs-long-lifespan-{control,treatment}`,
`bm-isolated-vs-connected-{control,treatment}`,
`bm-low-vs-high-teaching-{control,treatment}`, and
`bm-reference-vs-reconstructive-memory-{control,treatment}`.
Build it with `experiments.generational_comparison_scenario` or the catalog
builder `experiment_bm_generational_comparison`.

### Closed comparison axes

| Axis | Level ids |
| --- | --- |
| `lifespan` | `short`, `long` |
| `learning_model` | `practice_only`, `teaching_supported` |
| `teaching_frequency` | `low`, `high` |
| `record_availability` | `absent`, `present` |
| `memory_architecture` | `reference`, `reconstructive` |
| `innovation_rate` | `low`, `high` |
| `migration` | `isolated`, `connected` |
| `resource_scarcity` | `scarce`, `abundant` |
| `population_size` | `small`, `large` |
| `institution_support` | `off`, `on` |
| `cognitive_architecture` | `v1_memory`, `full_v2` |

`build_generational_comparison(spec)` accepts independent pairs only; it is not
a Cartesian product. A pair that changes lifespan, capacity, or entry rate must
still preserve the declared schedule and pass the comparability gate. The gate
rejects mismatched seed, stochastic identity, scenario, resource identity,
roster, stop policy, schedule, lifecycle fixed fields, generational contract, or
initialization with stable `comparison_*` codes. Comparability requires a
passthrough lifespan distribution and a deterministic `none` initialization
distribution; run-ID-scoped channels are documented, not silently unified.

BM guarantees configuration, admitted generations, cohort rows, and
measurement. It does not guarantee that a durable record is created, a teaching
act occurs, migration happens, or an institution emerges; those depend on
cognition and horizon.

Detached analysis adds `generational_cohort_comparison@1`, which folds the
finalized `PopulationProgress` into generation/cohort counts and survival
shares. Legacy cross-arm comparison remains `matrix-metric-summary-v1` with
empirical `p05`/`p95` ranges. An opt-in sibling
`cultural-metric-comparison-v1` adds repeated-seed Student-t intervals and
explicit one-factor paired contrasts over verified cultural sidecars, without
turning the legacy percentile range into a confidence interval and without
claiming significance.
