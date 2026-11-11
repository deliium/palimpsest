<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-20 Market-Like Institutions

Mode: ultra
Branch: main
Created: 2026-11-11
Plan identifier: `v4-20-market-like-institutions`

## Original Request

v4-20 market institutions

Naming requirement:

Use `v4-20-market-like-institutions`.

Enable repeated trade gatherings and exchange venues to become socially expected institutions.

Do NOT create a global Market class with authoritative prices.

Possible emergence pattern:

agents repeatedly trade at location  
→ expectations form  
→ records/roles emerge  
→ market-like institution persists

Support:

meeting expectations  
brokers if emergent  
exchange records  
market schedules as social conventions

Detect market-like persistence analytically.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose/browser, Godot regression (existing suites only), Research UI,
  benchmark regression, and static gates, with coverage enabled for Python
  lanes.
- Logging: verbose, metadata-only. Bounded DEBUG ledger/venue/market counts and
  selected status tokens, INFO activation/publication/build milestones, WARN
  truncation/partial coverage/unresolved anchors/malformed frames, ERROR safe
  codes. `PALIMPSEST_LOG_LEVEL` controls operational verbosity. Never log venue
  labels, location sets, counterparty sets, role refs, record anchors,
  inventories, observation bodies, utterance bodies, owner claims, cursor keys,
  credentials, tokens, DSNs, memories, embeddings, or payload surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 23.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning or implementation unless the user explicitly asks.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-20-market-like-institutions`; the ultra bundle
  directory is `.ai-factory/plans/v4-20-market-like-institutions/`, phase files
  use `phase-NN-<slug>.md`, and `index.md` is the canonical entrypoint. Python
  and artifact tokens use `market_institutions` / `market-institutions-*`
  because identifiers cannot contain hyphens; the human-readable feature name
  is "market-like institutions".
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only in this invocation. No implementation, commit, roadmap
  edit, or branch creation occurs while planning.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-20 claims the already-declared `markets_credit` V4 context and
deepens existing exchange, speech, office, organization, record, and
convention seams into owner-scoped market-like institution beliefs with
detached persistence analytics, adding no global Market class, authoritative
price, money, credit, debt, planner, quota, or automatic allocation. This plan
does not edit or close the roadmap; `$aif-roadmap` must register V4-20 in M8,
record that the owned V4 flag count moves from seven to eight, and also register
the currently unregistered V4-17 travel-network, V4-18 trade-network, and V4-19
supply-chain landings.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Versioned Extension Contract", V4-01 through V4-19 seams)
and `.ai-factory/RULES.md` constrain every edit; `.ai-factory/DESCRIPTION.md` and
`.ai-factory/ROADMAP.md` describe current state; the source paths below define
the concrete contracts. No requirement source is edited by this plan.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-20 owns the declared `markets_credit` V4 context; contexts stay 14, flags 12, owned 8, unowned 4; no new context, flag slot, `runner-config-v57`, root field, or per-agent key | Original Request; `src/simulation/v4_architecture.py:212-228`; `src/simulation/runner_models.py:327-337,1147`; `src/simulation/compatibility.py:155-165` | Task 3/12/22/25 |
| The registry declares `authority=OWNER_SCOPED`, owners `("agents.cognition","simulation")`, `uses_existing_events=True`, and prerequisites `SUPPLY_CHAINS`/`ORGANIZATIONS`; prerequisites are planning order and never a runtime gate | Original Request; `v4_architecture.py:88-106,212-228` | Task 3/22/25 |
| No new command, event, observer semantic type, replay marker, codec marker, write pair, API version, or Alembic migration; commands 43, semantics 73, replay max `EVENT_SCHEMA_REPLAY_V27`/`v25`, Alembic `0017` | Original Request; `src/world/actions.py:911-955`; `src/world/events.py:2456-2564,3167,3960`; `src/simulation/versioning.py:42-115`; `src/observer/version.py` | Task 3/22/25 |
| No global Market class, authoritative price, money, currency, credit, debt, credit limit, score, ranking, severity, recommendation, allocation, quota, or central planner; the registry's non-goals are preserved verbatim | Original Request; `v4_architecture.py:224-227`; `RULES.md` axioms | Task 1/2/5/8/9/11/22/24 |
| Exchange stays `NegotiateExchange` and `ExchangeCompleted`; analysis reads the committed occurrence origin for the venue and keeps no item ids, kinds, bundles, or valuations | Original Request; `src/world/actions.py:758-760,883-908`; `src/world/events.py:2456-2564`; `src/analysis/trade_networks_events.py:172-176,477` | Task 2/6/20 |
| The market institution ledger is owner-scoped and bounded; it stores only own-observed exchange counts, counterparty tokens, expectation, schedule, role, record, and notice values; no peer ledger or world state is read | Original Request; `src/agents/cognition/organization_operations.py:1427-1510,2708-2760`; `AGENTS.md`/`ARCHITECTURE.md` authority rules | Task 2/3/4/22 |
| Meeting expectations, schedules, role claims, and record anchors travel as bounded `mkt_v1` frames inside existing `Talk`/`Ask`/`Tell`; no new speech command or convention situation is added | Original Request; `src/agents/cognition/organization_operations_communication.py:63-88,207-303,486-537` | Task 4/22 |
| Brokers are emergent owner beliefs referencing an existing office role signature or `orgc-` concept; no broker actor, fee, commission, or enforcement exists | Original Request; `src/agents/cognition/offices.py:399-421`; `src/agents/cognition/organization_concepts.py:31-34,373` | Task 2/8/22 |
| A venue is a logical location with at least two completed exchanges and two distinct parties in one 32-tick window; recurrence and persistence use locked thresholds and integer milli ratios | Original Request; `src/analysis/trade_networks_policy.py:55-120`; `src/analysis/trade_networks_detection.py:172-266` | Task 5/7/10/11 |
| Market candidates are contemporaneous components of venues connected by shared participants; identity is content-addressed `mktc-`, and lineage is forward-only across every consecutive window including empty windows | Original Request "market-like institution persists"; `src/analysis/trade_networks_identity.py:63-244` | Task 7/9/10/20 |
| Owner expectation/role/record lanes are detached and token-only; when an input family is absent its coverage is `missing` and no row is fabricated; alignment is researcher-only and never reaches cognition | Original Request; `src/experiments/migration_displacement_harvest.py:399-435`; `src/simulation/migration_displacement_export.py:311-342` | Task 8/10/13/21/22 |
| Four metric families append 204 → **208**; the first 204 ids, order, versions, and value keys stay unchanged, and every suite and docs pin is swept in the same change | `src/analysis/specifications.py:53,270-275,8723-8808,9353-9610`; 84 test files pin `204` at plan time | Task 11/12/22/24 |
| Snapshot is a sibling `market-institutions-snapshot-v1` with store `market-institutions-store-v1`, two dual-gated settings, window-bound cursors, and seven GET-only routes failing closed with `market_institutions_disabled`; it is not a runner/result/replay/SQL schema | `src/simulation/trade_networks_models.py`; `src/simulation/trade_networks_codec.py`; `src/simulation/trade_networks_ports.py`; `src/persistence/trade_networks_filesystem.py`; `src/infrastructure/settings.py:248-249,422-431`; `src/api/app.py:480-507` | Task 14/15/16/17 |
| No Godot overlay is added: market-like institutions are detached analytical structures; the presentation client is unchanged and its existing suite is the regression gate | Original Request; Phase 5 objective; `clients/godot-observer/tests/run_protocol.gd` | Task 18/22/25 |
| Publication is programmatic and post-completion; no CLI producer and no runner flag is added | `src/experiments/trade_networks_publication.py:309-361`; V4-18 has no CLI producer | Task 16/25 |
| Off-gate experiment `market_institutions@1` is registered and never enters the V1 A–E gate | `src/experiments/catalog.py:244-246,2795-2834,5652-5667` | Task 19/25 |
| Documentation covers the page, README, ARCHITECTURE, DESCRIPTION, `docs/architecture.md`, `docs/configuration.md`, `docs/analysis-metrics.md`, and `docs/research-api.md`; roadmap registration stays with `$aif-roadmap` | ARCHITECTURE requirement 7; `.ai-factory/ROADMAP.md`; `docs/trade-networks.md` | Task 23/24/25 `git status` |

### Supported combinations and coverage transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| `markets_credit` off | No market mode, policy, ledger, or snapshot field | Legacy trajectories and checkpoints byte-identical; no metric input | Task 3/20 |
| `markets_credit` on, v56 | Deterministic market mode and locked policy per agent | Ledger allocated; no write pair activated; no v57 | Task 3/22 |
| Own-observed `ExchangeCompleted` one tick behind the observation | Occurrence facts only | Venue observation count increments; expectation `weak` then `expected` | Task 2 |
| Same exchange folded twice | Existing observation replaced | Counts, digest, and ledger bytes unchanged | Task 2 |
| Exchange observed with a stale source tick (gap > 1) | No count increment | Notice `market_venue_stale`; no fabricated venue | Task 2 |
| Own `ExchangeProposed`/`ExchangeWithdrawn` | Attempt counts | Meeting-attempt evidence; no venue belief by itself | Task 2/6 |
| Two completions and two parties at one location in one window | Gathering | Venue row with `single_gathering` on first activity | Task 7 |
| One completion or one party | Below threshold | No gathering, no venue belief increment | Task 7 |
| Three active windows at one location, recurrence ≥ 500 milli | Persistent venue | Status `market_like_persistent`, `market_like=true` | Task 7/10 |
| Two active windows plus an `expected`/`strong` owner row | Expectation row | `expected_venue_count` increments; the objective venue status is unchanged | Task 8/10 |
| No current activity after prior activity | Dormant row | Status `dormant`; lineage may `dissolve` | Task 7/9 |
| Two venues sharing a participant in one window | Market cluster | `mktc-` identity from sorted venue ids | Task 7/9 |
| Two consecutive windows share ≥ 500 milli of the smaller venue set | Same market identity | `continued` (equal) or `transformed` (reroute) | Task 9 |
| One previous market, two successors | Forward lineage | `split`; parents never rewritten | Task 9 |
| Two previous markets, one successor | Forward lineage | `merge`; parents never rewritten | Task 9 |
| One or more empty windows | Empty-window lineage | `dissolved` then `emerged`; never a silent `continued` | Task 9/21 |
| No owner ledger exported | Objective rows only | `expectation`/`role`/`record` coverage `missing`; no fabricated rows | Task 8/13 |
| Owner ledger exported | Token-only owner rows | Expectation/role/record rows; recognized only for office/organization basis | Task 8/13 |
| Broker-like participation without office/organization anchor | Claimed role | `recognized=false`; no broker actor or fee | Task 8 |
| Schedule claim with unknown venue label | No venue change | Notice `market_venue_unresolved` | Task 4 |
| Row or cap exceeded | Deterministic prefix | `coverage="partial"` plus one bounded truncation notice | Task 2/7/8/14/21 |
| Snapshot dual gate unset | No reader | 503 `market_institutions_disabled` on all seven routes | Task 15/17 |
| Corrupt snapshot payload | No data | 500 `market_institutions_store_corrupt` | Task 15/17 |
| Paged route with `window_index` | Filter-bound cursor | Only matching rows; cursor for another window rejected 400 | Task 14/17 |
| Publication disabled by the caller | No artifact | Nothing written; scientific status unchanged | Task 16 |
| Another unowned V4 flag | Unchanged | `capability_unimplemented`; fixtures repointed to `science` | Task 3/12/22 |
| Env-gated lane missing prerequisite | No green certification | `unexecuted` plus prerequisite | Task 25 |

No blocking open questions: every material decision is fixed below.

## Architecture and Decisions

1. **Own the declared seam, not a new one.** V4-20 claims `markets_credit`,
   which already declares owner-scoped authority, existing events, and the
   non-goals "no money object, price index, or ledger authority" and "no central
   bank or enforced debt". Counts become 14 contexts / 12 flags / 8 owned / 4
   unowned. The name `markets_credit` is inherited; V4-20 implements market-like
   institutions only, not credit, banking, or debt.
2. **Exchange is untouched.** `NegotiateExchange` and `ExchangeCompleted` keep
   their fields and admission. Analysis attributes a completion to the
   authoritative `occurrence.origin_location_id`; cognition uses the owner's
   current location only for own-observed facts and never reads event bodies.
   V4-20 does not initiate trade, create demand, or value goods; exchange offers
   remain V3-18 behavior.
3. **One owner-scoped ledger.** `MarketInstitutionLedger` keeps bounded venue
   beliefs with observations, expectation, schedules, roles, records, and
   notices. It stores no inventories, item ids, valuations, prices, peer state,
   or world state. Owner-local ids are `mktb-`; analysis ids are `mkt-ven-` and
   `mktc-`.
4. **Expectations are earned.** One observation yields `weak`; two yield
   `expected`; two plus a schedule of confidence ≥ 500 yields `strong`. A claim
   or a peer frame alone never mints a venue or a strong expectation.
5. **Schedules are social beliefs.** `recurring_interval` and
   `periodic_window` beliefs are owner-scoped, bounded, and active only by an
   integer tick rule. They are not world timers, calendars, or events, and no
   V3 convention situation is widened.
6. **Attendance is one hop.** The only command-producing path replaces `Wait`
   with one `Move` to an observed exit whose destination is an expected or
   persistent venue. There is no pathfinding, multi-hop travel, `Transport`,
   `Flee`, lookahead, or global catalog read.
7. **Brokers emerge, never exist.** A broker is an owner belief with role kind
   `broker` and basis `office` or `organization`; only those bases can set
   `recognized=true`. No broker actor, fee, commission, discount, or enforcement
   field exists. Analysis reports broker-like participation as counts.
8. **Records are anchors.** Exchange records are opaque references to existing
   durable records or repositories; the ledger never dereferences or asserts
   their truth, and analysis never reconstructs record text.
9. **Evidence is committed events plus detached owner rows.** Venues,
   gatherings, participation, and market clusters come from committed events.
   Own-observed ledger evidence is deduplicated by `(venue_id, source_tick)` and
   accepts only the normal one-tick prior window; a larger gap is stale.
   Expectations, role claims, and record anchors come from exported owner
   ledgers. No `WorldState`, runtime, store, or API object is read by analysis.
10. **Venue and market identities are deterministic.** Venue ids are
    content-addressed by location; market ids are content-addressed by the
    sorted venue set. Market continuity is expressed only by forward-only
    lineage over venue-set overlap, including empty windows.
11. **Persistence is described, not scored.** The status set is
    `single_gathering`, `recurring_gathering`, `market_like_persistent`,
    `dormant`. There is no score, rank, severity,
    recommendation, or suggested action.
12. **Alignment is researcher-only.** Expectation alignment is
    `consistent`/`unresolved`/`inconsistent`/`not_applicable` and never reaches
    cognition, prompts, memory, world state, stop selectors, or observer
    semantics.
13. **Bounded everything.** Exchanges, attempts, venues, gatherings,
    participation, expectations, roles, records, markets, and lineage truncate
    deterministically with `coverage="partial"` and one bounded notice. A venue
    emits one dormant row, never an unbounded tail. Caps are policy values, not
    magic numbers in detectors.
14. **Snapshot and read-only surfaces.** `market-institutions-snapshot-v1` is a
    canonical sibling with digest and publication id and no wall-clock field;
    `market-institutions-store-v1` is atomic, quota-bounded, idempotent, and
    corruption-safe; cursors bind `window_index`; seven GET-only dual-gated
    routes serve it. Publication is programmatic and post-completion.
15. **Clients and pins.** The Research UI adds one read-only panel; Godot gets
    no overlay. Four metrics append 204 → 208, every suite and docs pin is
    swept, and `market_institutions@1` stays off the V1 gate. `$aif-roadmap`
    registers V4-17, V4-18, V4-19, and V4-20 in M8 and records eight owned
    flags.

### Locked market-like institution summary

| Dimension | Locked behavior |
| --- | --- |
| Policy | `market-institutions.v1` (cognition and analysis share the version token) |
| V4 ownership | `markets_credit` owned; 14 contexts / 12 flags / 8 owned / 4 unowned |
| Runner schema | `runner-config-v56` only; no v57, no new root/per-agent field |
| Exchange primitives | Unchanged `NegotiateExchange` and `ExchangeCompleted`; venue is `occurrence.origin_location_id` |
| Cognition ledger | `mktb-` owner-local venue beliefs; 8 venues, 64 observations, 4 schedules, 8 roles, 8 records per venue |
| Expectation levels | `none`, `weak`, `expected`, `strong`; strong requires ≥ 2 observations and a schedule ≥ 500 milli |
| Schedule cadences | `single_occurrence`, `recurring_interval`, `periodic_window`, `unknown`; interval 1-512, phase 0-511 |
| Local plan | Replace `Wait` with one `Move` to an observed exit for an expected/persistent venue; no lookahead |
| Role kinds | `broker`, `host`, `organizer`, `unknown`; recognized only for `office`/`organization` basis |
| Record kinds | `exchange_record`, `attendance_record`, `agreement_record`, `unknown`; opaque anchors only |
| Window | 32 ticks; index `tick // 32`; at most 512 windows |
| Venue identity | `mkt-ven-` content address of the location token |
| Market identity | `mktc-` content address of the sorted venue-id set |
| Venue statuses | `single_gathering`, `recurring_gathering`, `market_like_persistent`, `dormant`; expectations are a separate row family |
| Lineage | Consecutive windows incl. empty; overlap ≥ 500 milli; emerged/continued/transformed/split/merge/dissolved |
| Alignment | `consistent` ≥ 750 milli, `inconsistent` < 250 milli, else `unresolved`; `not_applicable` without a schedule |
| Thresholds | Gathering ≥ 2 exchanges and ≥ 2 parties; persistent ≥ 3 windows and recurrence ≥ 500 milli |
| Broker-like | ≥ 3 exchanges, ≥ 2 counterparties, ≥ 2 active windows |
| Caps | Exchanges 200,000; attempts 200,000; venues 8,192; gatherings 8,192; participation 8,192; expectations 4,096; roles 4,096; records 4,096; markets 1,024; locations 4,096; lineage 16,384; dormant rows 1 per venue |
| Snapshot | `market-institutions-snapshot-v1`; store `market-institutions-store-v1`; 16 publications / 8 MiB; no wall-clock field |
| Routes | 7 GET-only under `SUBJECTIVE_DEBUG`; default limit 100; max 500; `market_institutions_disabled` when unset |
| Catalog | 204 → 208 families; suite and docs pins swept to 208 |
| Clients | Research UI panel; no new Godot overlay |
| Experiment | `market_institutions@1`, off the V1 gate |
| Pins | 43 commands; 73 observer semantics; replay-v27/codec `v25` max; Alembic `0017`; `/v1`; `observer-protocol-v1` |

## Phase Index

1. [Phase 1: Contract and Owner-Scoped Market Cognition](phase-01-contract-and-owner-ledger.md) — Tasks 1-4
2. [Phase 2: Analysis Evidence and Detection](phase-02-analysis-evidence-and-detection.md) — Tasks 5-7
3. [Phase 3: Expectations, Identity, Metrics, and Pins](phase-03-expectations-identity-metrics.md) — Tasks 8-12
4. [Phase 4: Collection and Publication](phase-04-collection-and-publication.md) — Tasks 13-16
5. [Phase 5: Read-Only Surfaces](phase-05-read-only-surfaces.md) — Tasks 17-18
6. [Phase 6: Experiment and End-to-End](phase-06-experiment-and-e2e.md) — Tasks 19-21
7. [Phase 7: Invariants and Pins](phase-07-invariants-and-pins.md) — Task 22
8. [Phase 8: Documentation and Verification](phase-08-docs-and-verification.md) — Tasks 23-25

## Cross-Phase Dependencies

- Task 2 depends on Task 1 (policy, enums, ids).
- Task 3 depends on Tasks 1-2 (ledger type and carry contract).
- Task 4 depends on Tasks 1-3 (frames, activation, ledger).
- Task 6 depends on Task 5 (policy, rows, window helpers).
- Task 7 depends on Task 6 (evidence rows).
- Task 8 depends on Tasks 5-7 (venues and participation to join).
- Task 9 depends on Task 7 (market candidates to link).
- Task 10 depends on Tasks 6-9 (evidence, detection, join, lineage).
- Task 11 depends on Task 10 (analysis object and locked keys).
- Task 12 depends on Task 11 (catalog count and ownership set).
- Task 13 depends on Tasks 3, 10, and 11 (result ledgers, analysis, metrics).
- Task 14 depends on Tasks 10 and 11 (row families and counts).
- Task 15 depends on Task 14 (snapshot codec).
- Task 16 depends on Tasks 13-15 (builder, snapshot, store).
- Task 17 depends on Tasks 14-16 (snapshot, store, publication).
- Task 18 depends on Task 17 (routes and schemas).
- Task 19 depends on Tasks 3-4, 11, and 13 (flag, catalog, metrics, collector).
- Task 20 depends on Tasks 16, 17, and 19 (publication, API, scenario).
- Task 21 depends on Task 20 (stable E2E fixtures).
- Task 22 depends on Tasks 1-21 (all pins).
- Task 23 depends on Task 22 (pins before prose).
- Task 24 depends on Task 23 (docs to pin).
- Task 25 depends on Tasks 20-22 and 24 (gates and docs).

## Tasks

### Phase 1: Contract and Owner-Scoped Market Cognition
- [x] Task 1: Lock `market-institutions.v1` contract, policy, and identifiers ([details](phase-01-contract-and-owner-ledger.md#task-1-lock-market-institutionsv1-contract-policy-and-identifiers))
- [x] Task 2: Add the owner-scoped market institution ledger ([details](phase-01-contract-and-owner-ledger.md#task-2-add-the-owner-scoped-market-institution-ledger)) (depends on 1)
- [x] Task 3: Own the `markets_credit` flag and thread activation ([details](phase-01-contract-and-owner-ledger.md#task-3-own-the-markets_credit-flag-and-thread-activation)) (depends on 1, 2)
- [x] Task 4: Add `mkt_v1` speech frames and local attendance planning ([details](phase-01-contract-and-owner-ledger.md#task-4-add-mkt_v1-speech-frames-and-local-attendance-planning)) (depends on 1, 3)

### Phase 2: Analysis Evidence and Detection
- [x] Task 5: Lock the `market-institutions.v1` analysis contract and caps ([details](phase-02-analysis-evidence-and-detection.md#task-5-lock-the-market-institutionsv1-analysis-contract-and-caps))
- [x] Task 6: Extract bounded exchange-gathering evidence ([details](phase-02-analysis-evidence-and-detection.md#task-6-extract-bounded-exchange-gathering-evidence)) (depends on 5)
- [x] Task 7: Detect venues, market clusters, and broker-like participation ([details](phase-02-analysis-evidence-and-detection.md#task-7-detect-venues-market-clusters-and-broker-like-participation)) (depends on 6)

### Phase 3: Expectations, Identity, Metrics, and Pins
- [x] Task 8: Join detached expectations, roles, records, and alignment ([details](phase-03-expectations-identity-metrics.md#task-8-join-detached-expectations-roles-records-and-alignment)) (depends on 5, 7)
- [x] Task 9: Mint market identities and forward-only lineage ([details](phase-03-expectations-identity-metrics.md#task-9-mint-market-identities-and-forward-only-lineage)) (depends on 7)
- [x] Task 10: Compose the bounded `MarketInstitutionsAnalysis` harvest ([details](phase-03-expectations-identity-metrics.md#task-10-compose-the-bounded-marketinstitutionsanalysis-harvest)) (depends on 7, 8, 9)
- [x] Task 11: Add four market metric families to 208 ([details](phase-03-expectations-identity-metrics.md#task-11-add-four-market-metric-families-to-208)) (depends on 10)
- [x] Task 12: Sweep suite-wide ownership and catalog pins ([details](phase-03-expectations-identity-metrics.md#task-12-sweep-suite-wide-ownership-and-catalog-pins)) (depends on 11)

### Phase 4: Collection and Publication
- [x] Task 13: Wire completed-run analysis and experiment collectors ([details](phase-04-collection-and-publication.md#task-13-wire-completed-run-analysis-and-experiment-collectors)) (depends on 3, 10, 11)
- [x] Task 14: Add `market-institutions-snapshot-v1` models, codec, ports, and paging ([details](phase-04-collection-and-publication.md#task-14-add-market-institutions-snapshot-v1-models-codec-ports-and-paging)) (depends on 10, 11)
- [x] Task 15: Add the atomic filesystem store and dual-gated settings ([details](phase-04-collection-and-publication.md#task-15-add-the-atomic-filesystem-store-and-dual-gated-settings)) (depends on 14)
- [x] Task 16: Compose and publish completed-run market snapshots ([details](phase-04-collection-and-publication.md#task-16-compose-and-publish-completed-run-market-snapshots)) (depends on 13, 14, 15)

### Phase 5: Read-Only Surfaces
- [x] Task 17: Add seven GET-only dual-gated market API routes ([details](phase-05-read-only-surfaces.md#task-17-add-seven-get-only-dual-gated-market-api-routes)) (depends on 14, 15, 16)
- [x] Task 18: Add the Research UI market client and panel ([details](phase-05-read-only-surfaces.md#task-18-add-the-research-ui-market-client-and-panel)) (depends on 17)

### Phase 6: Experiment and End-to-End
- [x] Task 19: Register off-gate `market_institutions@1` ([details](phase-06-experiment-and-e2e.md#task-19-register-off-gate-market_institutions1)) (depends on 3, 4, 11, 13)
- [x] Task 20: Add in-process market-institution end-to-end coverage ([details](phase-06-experiment-and-e2e.md#task-20-add-in-process-market-institution-end-to-end-coverage)) (depends on 16, 17, 19)
- [x] Task 21: Add determinism, property bounds, and leakage coverage ([details](phase-06-experiment-and-e2e.md#task-21-add-determinism-property-bounds-and-leakage-coverage)) (depends on 20)

### Phase 7: Invariants and Pins
- [x] Task 22: Enforce architecture invariants and pin sweeps ([details](phase-07-invariants-and-pins.md#task-22-enforce-architecture-invariants-and-pin-sweeps)) (depends on 1-21)

### Phase 8: Documentation and Verification
- [x] Task 23: Documentation via `$aif-docs` ([details](phase-08-docs-and-verification.md#task-23-documentation-via-aif-docs)) (depends on 22)
- [x] Task 24: Add documentation pin and negative parity checks ([details](phase-08-docs-and-verification.md#task-24-add-documentation-pin-and-negative-parity-checks)) (depends on 23)
- [x] Task 25: Required-gate verification certification ([details](phase-08-docs-and-verification.md#task-25-required-gate-verification-certification)) (depends on 20, 21, 22, 24)

## Commit Plan

- **Commit 1** (after tasks 1-4): `feat(cognition): own markets_credit and add owner-scoped market institution beliefs`
- **Commit 2** (after tasks 5-7): `feat(analysis): reconstruct exchange venues and market-like participation`
- **Commit 3** (after tasks 8-12): `feat(analysis): add expectation joins, market lineage, metrics, and pin sweep`
- **Commit 4** (after tasks 13-18): `feat(simulation): publish market-institution snapshots and read surfaces`
- **Commit 5** (after tasks 19-25): `test,docs: certify market-like institution experiment and required gates`

Commit checkpoints are suggestions only. Do not commit during `$aif-implement`
unless the user explicitly authorizes commits.

## Definition of Done

- V4-20 owns `markets_credit`; 14 contexts / 12 flags / 8 owned / 4 unowned; no
  `runner-config-v57`, root field, or per-agent key; no credit, banking, or debt
  behavior is implemented.
- Exchange commands and events are unchanged; `NegotiateExchange` and
  `ExchangeCompleted` remain the only exchange primitives. V4-20 adds no trade
  initiation, demand, price, or allocation mechanism.
- The owner-scoped ledger stores bounded venue beliefs with expectation,
  schedule, role, record, and notice values; it stores no price, money, credit,
  debt, inventory, item id, valuation, peer state, or world state.
- Own-observed exchange evidence accepts only the normal one-tick prior window
  and is idempotent by `(venue_id, source_tick)`; a repeat fold never changes
  counts or ledger bytes.
- A broker exists only as an owner belief with an office or organization basis;
  no broker actor, fee, commission, or enforcement exists.
- Schedules are owner beliefs carried in `mkt_v1` frames; no world timer,
  calendar, event, or new V3 convention situation exists.
- Local planning replaces only `Wait` and returns only one existing `Move` to an
  observed exit; there is no pathfinding, lookahead, or global planner.
- Analysis reconstructs venues, gatherings, participation, and market clusters
  from committed events only and joins detached owner rows without reading
  `WorldState`, runtimes, stores, or API objects.
- A venue requires two exchanges and two parties in a window; persistence uses
  the locked three-window and 500-milli recurrence thresholds and emits counts
  and closed tokens only. A venue emits at most one dormant row.
- Exchange and attempt evidence, participation, and every row family are
  independently capped; truncation is deterministic and never reported as
  complete.
- Market lineage is forward-only across every consecutive window, including
  empty windows, with emerged/continued/transformed/split/merge/dissolved.
- Expectation, role, and record coverage is `missing` when the detached input is
  absent; no edge or row is fabricated.
- Four metric families append to exactly 208; prior ids/order/versions/value
  keys are unchanged; every suite pin is swept from 204 to 208 and no test
  expects `markets_credit` to be unowned.
- `market-institutions-snapshot-v1` round-trips canonically with no wall-clock
  field; `market-institutions-store-v1` is atomic, quota-bounded, idempotent,
  and corruption-safe; cursors bind the `window_index` filter.
- Seven GET-only dual-gated routes fail closed with
  `market_institutions_disabled`, default limit 100, max 500, `window_index`
  ≤ 511; the Research UI panel is read-only; no new Godot overlay exists.
- Publication is programmatic and post-completion; no CLI producer or runner
  flag is added.
- Off-gate `market_institutions@1` is registered and absent from the V1 gate.
- Commands stay 43; observer semantics stay 73; replay-v27/codec `v25` stay the
  maximum; Alembic stays `0017`; `/v1` and `observer-protocol-v1` stay.
- The in-process E2E uses real `WorldEngine` admission, real commands, real
  events, a real snapshot, and a real API read.
- Determinism across hash seeds, cap-bound properties, and leakage guards pass.
- Docs cover the page, README, ARCHITECTURE, DESCRIPTION,
  `docs/architecture.md`, `docs/configuration.md`, `docs/analysis-metrics.md`,
  and `docs/research-api.md`, with positive and negative parity checks; required
  gates are certified or explicitly `unexecuted`; the roadmap is untouched and
  its follow-up registration is stated.

## Verification Receipt

Verified 2026-11-11 after `$aif-verify` remediation. Roadmap was not modified.
V4-17, V4-18, V4-19, and V4-20 registration remains with `$aif-roadmap`.

| Lane | Command | Result | Prerequisite / note |
| --- | --- | --- | --- |
| Python unit + architecture (coverage) | `uv run pytest tests/unit tests/architecture -q --cov=src --cov-report=term` | **10,659 passed, 0 skipped, 0 failed; 79% coverage** | Local Python 3.12 |
| Focused market + pins + boundaries | `uv run pytest tests/unit/test_market_institutions_*.py tests/unit/test_supply_chain_pins.py tests/architecture/test_market_institutions_*.py -q` | **221 passed, 1 deselected** | Integration test deselected by the default marker |
| Docs parity | `uv run pytest tests/unit/test_market_institutions_docs.py -q` | **8 passed** | Local |
| Ruff | `uv run ruff check src tests` | **All checks passed** | Local |
| mypy | `uv run mypy src tests` | **Success: no issues in 2,470 files** | Local |
| Import-linter | `uv run lint-imports` | **25 kept, 0 broken** | Local |
| Integration (non-scale) | `uv run pytest tests/integration -m "not scale" -q` | **53 passed, 60 skipped, 5 deselected** | DB-backed cases skipped: `PALIMPSEST_TEST_DATABASE_URL` unset |
| Market store/API integration | `uv run pytest tests/integration/test_market_institutions_store_api.py -q -m integration` | **1 passed** | DB-free |
| Compose config | `docker compose config` | **exit 0** | Local Docker Compose |
| Research UI tests | `cd clients/research-ui && ./node_modules/.bin/vitest run` | **62 files, 298 tests passed** | Pinned Node/pnpm dependencies installed |
| Research UI types | `cd clients/research-ui && ./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json` | **0 errors, 0 warnings** | Same |
| Godot regression | `${GODOT_BIN} --headless --path clients/godot-observer --script res://tests/run_protocol.gd` | **unexecuted** | `GODOT_BIN` unset; pinned Godot 4.7.2 editor/export templates unavailable |
| Compose/browser acceptance | Attested-image Compose + headed browser harness | **unexecuted** | No attested image or headed browser harness in this environment |
| Benchmark/scale | `tests/benchmarks` scale lanes | **unexecuted** | Scale hardware and disposable PostgreSQL unavailable |

Notes: the focused Python lane, integration market suite, static gates, Research
UI suite, and Compose configuration were re-run after remediation. Env-gated
lanes are recorded as `unexecuted`, not green. No test was skipped or marked
xfail to manufacture a passing lane.
