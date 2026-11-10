<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-18 Trade Networks

Mode: ultra
Branch: main
Created: 2026-11-09
Plan identifier: `v4-18-trade-networks`

## Original Request

v4-18 trade networks

Naming requirement:

Use `v4-18-trade-networks`.

Build analytics and mechanics for sustained inter-location/inter-society exchange.

Do not implement centralized trade routing.

Use individual/organizational exchanges.

Track flows of:

- food
    
- materials
    
- tools
    
- records
    
- durable exchange media
    

Derive:

trade corridors  
trade dependence  
major exchange locations  
cross-society flows

Allow trade networks to emerge, disappear and reroute.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose/browser, Godot regression, Research UI, benchmark regression, and
  static gates, with coverage enabled for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG flow/counts, INFO milestones,
  WARN unresolved origin/truncation/partial coverage, ERROR safe codes.
  `PALIMPSEST_LOG_LEVEL` controls operational verbosity. Never log person sets,
  item/artifact bodies, `trd-` payload bodies, observation bodies, prompts,
  credentials, tokens, DSNs, memories, embeddings, utterance bodies, or payload
  surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 20.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning or implementation unless the user explicitly asks.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-18-trade-networks`; the ultra bundle directory is
  `.ai-factory/plans/v4-18-trade-networks/`, phase files use
  `phase-NN-<slug>.md`, and `index.md` is the canonical entrypoint.
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only in this invocation. No implementation, commit, roadmap
  edit, or branch creation occurs while planning.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-18 deepens the owned objective-world seams
`infrastructure_networks`, `regions_migration`, and the
V3 exchange/valuation seam with event-sourced trade-network analytics for
sustained individual and organizational exchange, without adding a V4 flag or
centralized routing. This plan does not edit or close the roadmap;
`$aif-roadmap` must register V4-18 in M8 and record the deepening ownership.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Capability ownership", "Versioned Extension Contract",
V4-01 through V4-17 seams) and `.ai-factory/RULES.md` constrain every edit;
`.ai-factory/DESCRIPTION.md` and `.ai-factory/ROADMAP.md` describe current
state; `src/world/events.py`, `src/world/actions.py`, `src/world/values.py`,
`src/world/artifacts.py`, `src/world/regions.py`, `src/world/infrastructure.py`,
`src/analysis/exchange_functions.py`,
`src/analysis/civilization_overlays.py`,
`src/analysis/inter_society_relations_*.py`,
`src/analysis/infrastructure_networks_analysis.py`,
`src/simulation/versioning.py`, `src/simulation/v4_architecture.py`, and
`src/experiments/collectors.py` define the concrete contracts.
`tests/architecture/test_v4_architecture_invariants.py` and related boundary
suites govern compatibility.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-18 deepens `infrastructure_networks` + `regions_migration` + the V3 exchange seam; adds **no** V4 context/flag; keeps 14 contexts / 12 flags / six owned; reuses accepted `runner-config-v56`; adds no `runner-config-v57` | Original Request; `v4_architecture.py` 184-332; `runner_models.py` 307-336/8107-8165 | Task 1/6/19/22 |
| No new command, event, observer semantic type, replay marker, codec marker, write pair, or Alembic migration; replay stays `EVENT_SCHEMA_REPLAY_V27` / `v25`; commands 43; semantics 73; Alembic 0017 | `events.py` 68-91/3939-3961; `versioning.py` 90-100; `observer/version.py` 11-167; Original Request | Task 8/19/22 |
| No centralized trade routing, planner, quota, automatic allocation, price, money, currency, or global trade registry; individual `NegotiateExchange`/`Give`/`TransferArtifact` plus journeys remain the only mechanics | Original Request; `v4_architecture.py` `SUPPLY_CHAINS` non-goals 232-244; `exchange_functions.py` 10-43; `RULES.md` axioms | Task 1/2/19/20 |
| Trade evidence is reconstructed from committed events only: `ExchangeCompleted`, `Given`, `ArtifactCreated/Moved/Copied`, `ResourceHarvested`, `ItemCrafted`, `Searched`, consumption events, and journey events; no `WorldState` read | `events.py` 1032-1073/1105-1133/1401-1600/2485-2564; `_operations.py` 1787-1800; `metric_service.py` 300-380 | Task 2/3/17 |
| Corridor = an observed edge between consecutive locations of the same item or artifact; same-location transfers are local, never corridors; no graph plan or shortest path is computed | Original Request; `exchange_functions.py` 85-120; `civilization_overlays.py` 408-469 | Task 3/17 |
| Closed flow classes: `food`, `materials`, `tools`, `records`, `durable_exchange_media`, `other`; media requires a generic item with at least two completed transfers across at least two distinct counterparties and no observed consumption | Original Request; `values.py` 81-94; `resource_profile.py` 16-48; `artifacts.py` 78-124 | Task 1/2/22 |
| Dependence is observed exchange dependence: imported / (imported + locally originated), per location, window, and flow class; it is never a consumption or welfare claim | Original Request; `exchange_functions.py` 46-75; `civilization_overlays.py` 408-469 | Task 3/7/20 |
| Major exchange location requires at least 2 corridors and at least 3 transfers in one 32-tick window; no composite score or ranking | Original Request; `inter_society_relations_contract.py` 46-53; `migration_displacement_policy.py` 33-70 | Task 1/3/7 |
| Trade networks are connected components of the corridor graph; forward-only lineage records `emerged`, `continued`, `transformed` (rerouted), `split`, `merge`, `dissolved` | Original Request; `migration_displacement_identity.py` 159-252 | Task 4/7/17 |
| Cross-society flows read contemporaneous `msoc-` candidates; no society is minted; overlapping membership is legal and no partition is created; absent candidates produce `missing` coverage | `inter_society_relations_detection.py` 47-180; `macro_society_detection.py` 93-130 | Task 5/7 |
| Snapshot is a new sibling `trade-networks-snapshot-v1` with its own atomic filesystem store and two dual-gated settings; it is not a runner/result/replay schema | `inter_society_relations_models.py`; `persistence/inter_society_relations_filesystem.py`; `settings.py` 225-265/390-425 | Task 10/11/12 |
| Seven GET-only `/v1/simulations/{run_id}/trade-networks...` routes require `SUBJECTIVE_DEBUG` and fail closed with `trade_networks_disabled` | `api/routes/inter_society_relations.py` 41-90/275-330; `api/dependencies.py` 182-191 | Task 13 |
| Six metric families append 192 -> **198**; prior 192 ids/order/versions/value keys stay unchanged | `specifications.py` 52-53/9011-9205 | Task 7/8/19/20 |
| Observer semantics stay **73**; no new semantic type or alias is added | `observer/version.py` 11-167 | Task 19/22 |
| Off-gate experiment `trade_networks@1` registered; not on the V1 gate | `catalog.py` 2799-2832/5610-5647 | Task 9/16/22 |
| Roadmap owned by `$aif-roadmap` | ARCHITECTURE requirement 7 | Task 21/22 `git status` |

### Supported combinations and coverage transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| No exchange/artifact/movement events | Empty transfer evidence | Evidence coverage `missing`; metrics unknown/absent; snapshot summary zero | Task 2/6/7 |
| Exchange at one location, item previously created there | Local transfer | No corridor; local supply counted; dependence denominator includes it | Task 2/3/7 |
| Exchange at L1 then the same item at L2 | Item trajectory L1 -> L2 | Corridor L1->L2; directed class counts; reroute candidate | Task 2/3/4 |
| Reverse trajectory L2 -> L1 | Reverse corridor | Distinct directed corridor; same undirected network component | Task 1/3/4 |
| Gift of an item at a later location | Transfer evidence | One-way flow; no exchange function claim; corridor only when previous location differs | Task 2/3 |
| Gift of a crafted or harvested item | Recipe/item-kind index | Correct food/material/tool class instead of `other` | Task 2/9 |
| Portable artifact moved/copied between locations | Record trajectory | `records` class flow; copy counted as local supply; no semantic content read | Task 2/3 |
| Generic item transferred once, not consumed | `other` class | Not media; counted for completeness | Task 1/2 |
| Generic item transferred twice between the same two parties | `other` class | Not media; distinct-party breadth not met | Task 1/2 |
| Generic item transferred at least twice across at least two distinct counterparties, never consumed | `durable_exchange_media` | Media class assigned retrospectively; no money/currency label | Task 1/2/20 |
| Generic item consumed by eat/craft/build/store | `other` class | Media classification rejected permanently | Task 1/2 |
| Transfer with unknown item kind and no recipe mapping | `other` class | Notice `trade_networks_unknown_item_kind`; coverage `partial` | Task 2/6 |
| No `msoc-` candidates supplied | Cross-society rows empty | Cross-society coverage `missing`; other five families unaffected | Task 5/6/7 |
| Contemporaneous `msoc-` candidates supplied | Cross-society pairs with dominant location anchors | Legal overlap; no society minted; no partition | Task 5/7 |
| `msoc-` candidate spans multiple 32-tick windows | Candidate expanded across overlapping windows | Flows counted in each covered window; candidate identity unchanged | Task 5/9 |
| Two windows share at least half of the smaller corridor set | Same network identity | `continued` or `transformed`; changed corridors = reroute | Task 4/7 |
| One previous network overlaps two current networks | Forward lineage | `split`; parents never rewritten | Task 4 |
| Two previous networks overlap one current network | Forward lineage | `merge`; parents never rewritten | Task 4 |
| Previous network has no successor | Forward lineage | `dissolved`; network disappears | Task 4/17 |
| Current network has no predecessor | Forward lineage | `emerged`; network appears | Task 4/17 |
| One or more empty windows separate observations | Empty-window lineage | `dissolved` then `emerged`; never silently `continued` | Task 4/17 |
| Network persists through continued/transformed transitions | Sustained network | Sustained counts retained; no score | Task 4/7 |
| Operational `TRADE_POST` asset at an exchange location | Venue evidence | Location row marks the venue; analytics valid without it | Task 3/7/9/10 |
| Row or window caps exceeded | Deterministic prefix retained | `coverage="partial"` plus bounded notice; no silent truncation | Task 3/6/10 |
| Snapshot dual gate unset | No reader | 503 `trade_networks_disabled` | Task 13 |
| Corrupt snapshot payload | No data | 500 `trade_networks_store_corrupt` | Task 11/13 |
| Paged route with `window_index` filter | Filter-bound cursor | Only matching window rows; mismatched cursor rejected | Task 10/13 |
| Infrastructure/travel inactive | Exchange evidence still analyzed | No trade-post/route enrichment; analytics remain valid | Task 6/9/17 |
| Another unowned V4 flag | Unchanged | `capability_unimplemented` | Task 19 |
| Env-gated lane missing prerequisite | No green certification | `unexecuted` + prerequisite | Task 22 |

No blocking open questions: every material decision is fixed below.

## Architecture and Decisions

1. **Deepen, do not add.** V4-18 owns no new V4 context or flag. It extends the
   owned `infrastructure_networks` context, the V3 `multi_polity_migration` /
   `regions_migration` seam, and the V3 `resource_exchange_profile` /
   `subjective_valuation` exchange seam. Counts
   remain 14 contexts / 12 flags / six owned.
2. **Reuse-only mechanics.** Individual `NegotiateExchange` and `Give` commands,
   artifact `deposit`/`claim`/`give`, inventory-carrying journeys, storage, and
   trade-post capacity remain the only mechanics. Organizational exchange is a
   composition of ordinary individual commands; no organization actor,
   treasury, quota, allocation, price, money, or central route planner exists.
3. **No new write pair.** V4-18 adds no event, command, observer semantic type,
   replay marker, codec marker, or SQL migration. Replay remains
   `EVENT_SCHEMA_REPLAY_V27` / `v25` when the travel-network channel is active;
   infrastructure-only runs keep 23/`v21` and regions-only 21/`v19`.
4. **Event-sourced analysis.** `analysis.trade_networks_*` reconstructs item and
   artifact trajectories from committed events only. It never imports
   `WorldState`, `WorldEngine`, `ActionSubmission`, experiments, API,
   persistence, observer, or cognition.
5. **Corridor definition.** A corridor is a directed edge between the
   consecutive observed locations of the same item or artifact. Reverse
   trajectories mint distinct directed corridors; the network graph unions both
   directions into one undirected component. A same-location transfer is local
   and produces no corridor. No shortest path, route plan, quota, or automatic
   allocation is computed.
6. **Closed flow taxonomy.** `food`, `materials`, `tools`, `records`,
   `durable_exchange_media`, and `other`. Food/materials/tools map from an
   explicit item-kind index built from exchange bundles, optional detached item
   ids, and recipe ids resolved through a detached production-catalog mapping;
   records map from artifact custody/copy movement; media is a retrospective
   classification of generic items with at least two completed
   transfers across at least two distinct counterparties and no observed
   consumption. No currency or money object is created.
7. **Dependence.** For each location, window, and flow class, dependence is
   `imported / (imported + locally_originated)` in integer milli, rounded down,
   with an explicit denominator. It is observed exchange dependence, never a
   consumption, welfare, or scarcity claim.
8. **Major exchange locations.** A location is major when its corridor degree is
   at least 2 and its transfer count is at least 3 in a 32-tick window. An
   optional detached set of operational `TRADE_POST` locations marks venue-backed
   exchange locations; it never changes exchange admission. The output is a
   boolean/count, never a score or ranking.
9. **Networks and lineage.** Every consecutive policy window from the first to
   the last observed window is evaluated, including empty windows. Each window's
   corridor graph yields connected components; a component is a trade network
   with a content-addressed `trd-net-` id. Forward-only lineage uses corridor-set
   overlap (shared corridors divided by the smaller corridor set) of at least
   500 milli; `transformed` means the network rerouted, and
   `continued`/`transformed` transitions contribute sustained-network counts.
10. **Cross-society flows.** Cross-society rows join exchange participants to
    contemporaneous `msoc-` candidates, expand each candidate across every
    overlapping 32-tick window, and count flows between different candidates.
    Rows retain a deterministic dominant exchange location for each society so
    read-only clients can anchor them. Existing `msoc-` identities are read only;
    overlap is legal and no partition or new society is created.
11. **Bounded analysis.** `MAX_TRADE_TRANSFER_ROWS`, `MAX_TRADE_CORRIDORS`,
    `MAX_TRADE_NETWORKS`, `MAX_TRADE_WINDOWS`, and row caps fail closed by
    deterministic truncation with `coverage="partial"` and a safe notice.
12. **Snapshot and read-only surfaces.** `trade-networks-snapshot-v1` is a
    sibling artifact with canonical JSON, digest, publication id, paging, an
    atomic filesystem store, and seven GET-only routes under
    `SUBJECTIVE_DEBUG`. Network rows carry lineage status and predecessor/
    successor ids; paged routes accept an optional `window_index` filter bound
    into the cursor fingerprint. It is not a runner, result, replay, or SQL
    schema.
13. **Six metrics.** Append `trade_corridor_structure@1`,
    `trade_flow_composition@1`, `trade_location_centrality@1`,
    `trade_dependence@1`, `cross_society_trade_flows@1`, and
    `trade_network_lineage@1`; catalog 192 -> 198. No composite score.
14. **Off-gate experiment.** `trade_networks@1` is a trusted, reproducible
    experiment over existing flags and is never on the V1 gate.
15. **Roadmap not edited here.** `$aif-roadmap` owns milestone registration.

### Locked trade-network summary

| Dimension | Locked behavior |
| --- | --- |
| Policy | `trade-networks.v1` |
| Window | 32 ticks; window index `tick // 32`; at most 512 windows |
| Coverage | `complete` / `partial` / `missing`, tracked separately for evidence, cross-society, and lineage, with an aggregate summary |
| Flow classes | `food`, `materials`, `tools`, `records`, `durable_exchange_media`, `other` |
| Item kind index | Exchange bundle kinds, optional detached item ids, recipe ids via detached production catalog |
| Media rule | Generic item, at least 2 completed transfers, at least 2 distinct counterparties, no observed consumption |
| Corridor | Directed consecutive locations for one item/artifact; reverse is a distinct corridor |
| Flow roles | `imported_count`/`exported_count` are non-disjoint location-role counts; `cross_location_count` is the distinct transfer count |
| Dependence | `imported / (imported + locally_originated)`, integer milli, denominator retained |
| Major location | `corridor_degree >= 2` and `transfer_count >= 3`; optional operational trade-post marker |
| Network | Connected component over undirected corridor union; `trd-net-` content address |
| Lineage | Every consecutive policy window, including empty windows; corridor-set overlap >= 500 milli (shared corridors / smaller corridor set); emerged/continued/transformed/split/merge/dissolved |
| Sustained | At least 2 adjacent windows linked by continued/transformed; counts only, no score |
| Cross-society | `msoc-` candidates expanded across overlapping windows; dominant location anchors; overlap legal; no partition |
| Caps | Transfers 200,000; corridors 4,096; networks 1,024; windows 512; cross-society pairs 2,048; lineage edges 16,384 |
| Snapshot | `trade-networks-snapshot-v1`; network lineage status; `window_index` filters; seven GET-only routes |
| Catalog | 192 -> 198 families |
| Pins | 43 commands; 73 observer semantics; replay-v27 / codec `v25`; Alembic `0017`; `/v1`; `observer-protocol-v1` |

## Phase Index

1. [Phase 1: Analysis Contract and Evidence](phase-01-analysis-contract-and-evidence.md) — Tasks 1-3
2. [Phase 2: Identity and Cross-Society Harvest](phase-02-identity-and-cross-society.md) — Tasks 4-6
3. [Phase 3: Metrics and Collection](phase-03-metrics-and-collection.md) — Tasks 7-9
4. [Phase 4: Snapshot and Publication](phase-04-snapshot-and-publication.md) — Tasks 10-12
5. [Phase 5: Read-Only Surfaces](phase-05-read-only-surfaces.md) — Tasks 13-15
6. [Phase 6: Experiment and End-to-End](phase-06-experiment-and-e2e.md) — Tasks 16-18
7. [Phase 7: Invariants and Pins](phase-07-invariants-and-pins.md) — Task 19
8. [Phase 8: Documentation and Verification](phase-08-docs-and-verification.md) — Tasks 20-22

## Cross-Phase Dependencies

- Tasks 2-3 depend on Task 1.
- Tasks 4-6 depend on Tasks 2-3 (Task 5 also needs `msoc-` candidates from the
  existing macro-society seam).
- Tasks 7-8 depend on Tasks 3-6 (Task 7 also on Task 3; Task 8 on Task 7).
- Task 9 depends on Tasks 6-8.
- Tasks 10-12 depend on Tasks 4-9 (Task 10 on Tasks 4-8; Task 11 on Task 10;
  Task 12 on Tasks 9-11).
- Tasks 13-15 depend on Tasks 10-12 (Task 14 on Task 13; Task 15 on Task 13).
- Tasks 16-18 depend on Tasks 9-15 (Task 17 on Task 16; Task 18 on Task 17).
- Task 19 depends on Tasks 1-18.
- Tasks 20-22 depend on Task 19; Task 21 also depends on Task 20, and Task 22
  depends on Tasks 17-21.

## Tasks

### Phase 1: Analysis Contract and Evidence
- [x] Task 1: Lock `trade-networks.v1` policy and flow taxonomy ([details](phase-01-analysis-contract-and-evidence.md#task-1-lock-trade-networksv1-policy-and-flow-taxonomy))
- [x] Task 2: Extract objective transfer and local-supply evidence ([details](phase-01-analysis-contract-and-evidence.md#task-2-extract-objective-transfer-and-local-supply-evidence)) (depends on 1)
- [x] Task 3: Detect corridors, dependence, exchange locations, and networks ([details](phase-01-analysis-contract-and-evidence.md#task-3-detect-corridors-dependence-exchange-locations-and-networks)) (depends on 1, 2)

### Phase 2: Identity and Cross-Society Harvest
- [x] Task 4: Mint deterministic trade identities and forward-only lineage ([details](phase-02-identity-and-cross-society.md#task-4-mint-deterministic-trade-identities-and-forward-only-lineage)) (depends on 3)
- [x] Task 5: Derive cross-society trade flows from msoc candidates ([details](phase-02-identity-and-cross-society.md#task-5-derive-cross-society-trade-flows-from-msoc-candidates)) (depends on 2, 3)
- [x] Task 6: Compose the bounded `TradeNetworksAnalysis` harvest ([details](phase-02-identity-and-cross-society.md#task-6-compose-the-bounded-tradenetworksanalysis-harvest)) (depends on 2, 3, 4, 5)

### Phase 3: Metrics and Collection
- [x] Task 7: Add six trade-network metric calculators ([details](phase-03-metrics-and-collection.md#task-7-add-six-trade-network-metric-calculators)) (depends on 3, 4, 5, 6)
- [x] Task 8: Append six trade-network families to 198 ([details](phase-03-metrics-and-collection.md#task-8-append-six-trade-network-families-to-198)) (depends on 7)
- [x] Task 9: Wire completed-run analysis and experiment collectors ([details](phase-03-metrics-and-collection.md#task-9-wire-completed-run-analysis-and-experiment-collectors)) (depends on 6, 7, 8)

### Phase 4: Snapshot and Publication
- [x] Task 10: Add `trade-networks-snapshot-v1` models codec ports and paging ([details](phase-04-snapshot-and-publication.md#task-10-add-trade-networks-snapshot-v1-models-codec-ports-and-paging)) (depends on 4, 5, 6, 7, 8)
- [x] Task 11: Add atomic filesystem store and settings ([details](phase-04-snapshot-and-publication.md#task-11-add-atomic-filesystem-store-and-settings)) (depends on 10)
- [x] Task 12: Compose and publish completed-run trade-network snapshots ([details](phase-04-snapshot-and-publication.md#task-12-compose-and-publish-completed-run-trade-network-snapshots)) (depends on 9, 10, 11)

### Phase 5: Read-Only Surfaces
- [x] Task 13: Add seven GET-only dual-gated trade-network API routes ([details](phase-05-read-only-surfaces.md#task-13-add-seven-get-only-dual-gated-trade-network-api-routes)) (depends on 10, 11, 12)
- [x] Task 14: Add Research UI trade-network API client and panel ([details](phase-05-read-only-surfaces.md#task-14-add-research-ui-trade-network-api-client-and-panel)) (depends on 13)
- [x] Task 15: Add Godot trade-network overlay and fixtures ([details](phase-05-read-only-surfaces.md#task-15-add-godot-trade-network-overlay-and-fixtures)) (depends on 13)

### Phase 6: Experiment and End-to-End
- [x] Task 16: Register off-gate `trade_networks@1` experiment ([details](phase-06-experiment-and-e2e.md#task-16-register-off-gate-trade_networks1-experiment)) (depends on 9)
- [x] Task 17: Add in-process trade-network end-to-end coverage ([details](phase-06-experiment-and-e2e.md#task-17-add-in-process-trade-network-end-to-end-coverage)) (depends on 16)
- [x] Task 18: Add determinism property bounds and leakage coverage ([details](phase-06-experiment-and-e2e.md#task-18-add-determinism-property-bounds-and-leakage-coverage)) (depends on 17)

### Phase 7: Invariants and Pins
- [x] Task 19: Enforce architecture invariants and pin sweeps ([details](phase-07-invariants-and-pins.md#task-19-enforce-architecture-invariants-and-pin-sweeps)) (depends on 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18)

### Phase 8: Documentation and Verification
- [x] Task 20: Documentation via `$aif-docs` ([details](phase-08-docs-and-verification.md#task-20-documentation-via-aif-docs)) (depends on 19)
- [x] Task 21: Add documentation pin and negative parity checks ([details](phase-08-docs-and-verification.md#task-21-add-documentation-pin-and-negative-parity-checks)) (depends on 20)
- [x] Task 22: Required-gate verification certification ([details](phase-08-docs-and-verification.md#task-22-required-gate-verification-certification)) (depends on 17, 18, 19, 20, 21)

## Verification Receipt

Recorded 2026-11-10. Every lane is either green with its exact command or
explicitly `unexecuted` with the missing prerequisite.

| Lane | Command | Result | Prerequisite / note |
| --- | --- | --- | --- |
| Python unit + architecture (coverage) | `uv run pytest tests/unit tests/architecture --cov=src --cov-report=term -q` | **10,174 passed**, 79% coverage | Complete |
| Trade-network focused | `uv run pytest tests/unit/test_trade_networks_*.py tests/architecture/test_trade_networks_boundaries.py -q` | **179 passed** | Complete |
| Docs parity | `uv run pytest tests/unit/test_trade_networks_docs.py tests/unit/test_infrastructure_docs.py tests/unit/test_travel_network_docs.py -q` | **18 passed** | Complete |
| Static — Ruff | `uv run ruff check src tests` | **All checks passed** | Complete |
| Static — mypy | `uv run mypy src tests` | **Success: no issues found in 2,364 files** | Complete |
| Static — import-linter | `uv run lint-imports` | **25 contracts kept, 0 broken** | Complete |
| Integration (non-scale) | `uv run pytest tests/integration -m "not scale" -q` | **48 passed, 60 skipped, 5 deselected** | PostgreSQL-marked lanes skipped without a disposable `palimpsest_test` database |
| Trade integration | `uv run pytest tests/integration/test_trade_networks_store_api.py -q -m integration` | **2 passed** | Complete; DB-free |
| Compose configuration | `docker compose config` | **exit 0** | Complete; secrets not printed |
| Research UI tests | `cd clients/research-ui && npx vitest run` | **291 passed / 60 files** | Complete |
| Research UI typecheck | `cd clients/research-ui && npx svelte-check --tsconfig ./tsconfig.app.json` | **0 errors, 0 warnings** | Complete |
| Godot regression | pinned editor + `tests/run_protocol.gd` | **unexecuted** | `GODOT_BIN` and export templates are not installed in this environment |
| Compose/browser acceptance | attested image + real browser harness | **unexecuted** | No attested release image or browser harness is available in this environment |
| Benchmark/scale regression | scale hardware + disposable PostgreSQL | **unexecuted** | No scale database/hardware is available; in-process determinism, ordering, and cap bounds are covered by unit lanes |

Additional note: an unrelated pre-existing nondeterminism in
`agents.cognition.institutional_memory` receipt ordering (a set converted to a
tuple) was fixed so the full gate is reproducible across hash seeds.

Roadmap: `git status --porcelain .ai-factory/ROADMAP.md` is empty. No commit was
created.

## Commit Plan

- **Commit 1** (after tasks 1-3): `feat(analysis): add trade-network evidence and corridor detection`
- **Commit 2** (after tasks 4-9): `feat(analysis): add trade-network identity, metrics, and collection`
- **Commit 3** (after tasks 10-12): `feat(simulation): publish trade-network snapshots`
- **Commit 4** (after tasks 13-18): `feat(research): add trade-network surfaces and experiment`
- **Commit 5** (after tasks 19-22): `test,docs: certify trade-network pins and required gates`

Commit checkpoints are suggestions only. Do not commit during `$aif-implement`
unless the user explicitly authorizes commits.

## Definition of Done

- V4-18 adds no V4 context or flag; 14 contexts / 12 flags / six owned remain.
- No centralized trade routing, planner, quota, allocation, price, money,
  currency, or global trade registry exists; individual and organizational
  exchanges remain ordinary commands.
- Committed exchange, gift, artifact, production, and journey events produce
  bounded transfer and local-supply evidence; recipe/item-kind evidence
  classifies produced and gifted food, materials, and tools; coverage is tracked
  independently for evidence, cross-society, and lineage.
- Corridors are directed; reverse trajectories are distinct corridors but one
  undirected network. Dependence, venue-backed major locations, cross-society
  flows with dominant location anchors, and forward-only lineage across every
  window (including empty gaps) follow the locked `trade-networks.v1` policy and
  caps. Sustained-network counts are retained without a score.
- Six metric families append to exactly 198; the first 192 ids, order,
  versions, and value keys stay unchanged.
- `trade-networks-snapshot-v1` round-trips canonically; network rows carry
  lineage status and predecessor/successor ids; paged routes accept a
  `window_index` filter bound into the cursor fingerprint; the atomic filesystem
  store enforces duplicate, count, byte, and corruption safety.
- Seven GET-only dual-gated routes fail closed with `trade_networks_disabled`;
  the Research UI and Godot observer render only read-only trade rows and skip
  unresolved society anchors.
- Off-gate `trade_networks@1` is registered and never appears on the V1 gate.
- Commands stay 43; observer semantics stay 73; replay-v27/codec `v25` stays the
  maximum; Alembic stays `0017`; `/v1` and `observer-protocol-v1` stay.
- The in-process E2E uses real `WorldEngine` admission, real exchanges, and real
  journeys; determinism and leakage guards pass.
- Docs land with positive and negative parity checks; required gates are
  certified or explicitly `unexecuted` with prerequisites; roadmap untouched.
