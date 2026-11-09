# Implementation Plan: V4-15 Inter-Society Relations

Branch: main
Created: 2026-11-08
Plan identifier: `v4-15-inter-society-relations`
Refined: 2026-11-08 (`$aif-improve` — settings/DI dual-gate, CLI flags,
`MetricComputationInputs` emit path, comparison query contract, Research UI
allow-list, docs surfaces, cultural field names, lanes disambiguation; removed
preparation-only Task 7)

## Original Request

v4-15 inter society relations

Naming requirement:

Use `v4-15-inter-society-relations`.

Add macro-level analytics for:

- cooperation
    
- hostility
    
- exchange
    
- migration
    
- trust proxies
    
- agreements
    
- conflict
    
- cultural similarity
    

These are researcher-derived metrics.

Do not expose one authoritative civilization relationship score to agents.

Support historical time series and comparison across society pairs.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose/browser, Godot regression, Research UI, benchmark regression, and
  static gates, with coverage enabled for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG flow/counts, INFO milestones,
  WARN unresolved references/truncation/partial coverage, ERROR safe codes.
  `PALIMPSEST_LOG_LEVEL` controls operational verbosity. Never log person sets,
  `msoc-`/`isr-` payload bodies beyond safe counts, domain panel bodies,
  observation bodies, prompts, credentials, tokens, DSNs, memories, embeddings,
  utterance bodies, or payload surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 22.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning or implementation unless the user explicitly asks.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-15-inter-society-relations`; the full plan file is
  `.ai-factory/plans/v4-15-inter-society-relations.md`.
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only in this invocation. No implementation, commit, roadmap
  edit, or branch creation occurs while planning.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-15 deepens the analysis-only `macro_society_identity` context with
researcher-only society-pair relation panels (eight evidence domains), four
metric families (180 -> 184), historical window time series, pair comparison,
`inter-society-relations-snapshot-v1`, an `inter-society-relations-store-v1`
filesystem store, six read-only routes, and a Research UI panel, without adding
a flag, context, runner schema, command, event, write pair, observer semantic
type, `/v2` route, Godot overlay kind, or migration. This plan does not edit or
close the roadmap; `$aif-roadmap` must register V4-15 in M8 and record the
inter-society relations deepening.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Capability ownership", "Versioned Extension Contract",
V4-01 through V4-14 seams, especially V4-02 macro-society and V4-10 diplomacy)
and `.ai-factory/RULES.md` constrain every edit; `.ai-factory/DESCRIPTION.md`
and `.ai-factory/ROADMAP.md` describe current state; completed V4-02/V4-10–V4-14
code plus `tests/architecture/test_v4_architecture_invariants.py`,
`test_v4_context_registry.py`, `test_macro_society_boundaries.py`,
`test_diplomacy_boundaries.py`, `test_analysis_isolation.py`, and related
boundary suites govern compatibility. V4-15 claims no new V4 flag and creates no
context; it deepens the analysis-only `macro_society_identity` context.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-15 adds no V4 flag, context, `runner-config-v57`, runner root field, or per-agent runner key; it deepens `macro_society_identity` | Original Request "researcher-derived metrics"; `.ai-factory/ARCHITECTURE.md` "Capability ownership"; `src/simulation/v4_architecture.py` 60-76, 301-327 | Task 1/19/23 tests |
| Activation is analysis-capture / opt-in publication only (`analysis_capture` seam); no capability flag gates harvest | `V4_ANALYSIS_CAPTURE_SEAM`; `docs/macro-societies.md`; `src/experiments/macro_society_publication.py` | Task 1/14/15 tests |
| Eight closed domain keys: `cooperation`, `hostility`, `exchange`, `migration`, `trust_proxy`, `agreement`, `conflict`, `cultural_similarity` | Original Request domain list | Task 1/2/19 tests |
| Cultural similarity panels use non-forbidden keys (`overlap_count`, `union_count`, `jaccard`, `*_mean_pairwise_similarity`, availability); never `score` or `*_score` | `src/analysis/diplomacy_contract.py` `DIPLOMACY_FORBIDDEN_RESULT_FIELDS`; `cultural_similarity` metric value keys | Task 1/2/8/19 tests |
| No authoritative civilization relationship score, composite, bilateral score, alliance/enmity score, or trust score exists anywhere; forbid-list mirrors and extends diplomacy | Original Request "Do not expose one authoritative civilization relationship score"; `src/analysis/diplomacy_contract.py` 73-96 | Task 1/8/19/20 tests |
| Agents never receive pair analytics via cognition, memory, prompts, Observation, admission, or stop selectors | `.ai-factory/ARCHITECTURE.md` Key Principle 1; macro_society non-goals | Task 8/19/20 tests |
| Society endpoints are existing analytical `msoc-` identities; pairs are canonically ordered (`a < b`) content-addressed `isr-` ids | Original Request "society pairs"; `src/analysis/macro_society_contract.py` `msoc-` prefix | Task 3/4 tests |
| Overlapping `msoc-` membership is legal; pairs may share members; no exclusive partition or nation entity | Original Request; `macro_society_identity` non-goals | Task 3/19 tests |
| Domain panels expose counts, coverage, and availability (`present`/`partial`/`absent`) only — never scalar relationship strength | Original Request analytics list; diplomacy lane "no bilateral relationship score" | Task 2/8/19 tests |
| Historical time series use fixed windows (`INTER_SOCIETY_RELATION_WINDOW_TICKS = 32`, matching `CIVILIZATION_FLOW_WINDOW_TICKS`) | Original Request "historical time series"; `src/analysis/civilization_overlays.py` 70 | Task 5/10/19 tests |
| Pair comparison compares domain-vector counts/availability between two pairs or two windows; it never ranks into one score | Original Request "comparison across society pairs" | Task 6/10/19 tests |
| Comparison GET uses explicit query operands: either `pair_a`+`pair_b` or `pair_id`+`window_a`+`window_b`; mixed/incomplete sets are 400 | Plan Architecture; borders/migration `Query(...)` precedent | Task 16/20 tests |
| Evidence is harvested read-only from committed events and existing analysis exports; V4-10–V4-14 stores are not rewritten | `.ai-factory/ARCHITECTURE.md` "analysis is read-only" | Task 2/14/19 tests |
| Three separated layers with a hard leakage guard: objective evidence rows, analytical pair candidates, comparison views | `.ai-factory/ARCHITECTURE.md` Key Principle 1; `src/analysis/macro_society_layers.py` | Task 3/19 tests |
| Four families append (`inter_society_relation_structure@1`, `inter_society_domain_evidence@1`, `inter_society_relation_timeseries@1`, `inter_society_pair_comparison@1`), raising the catalog 180 -> 184; they are additive and must not rename or reuse `inter_society_relation_lanes@1`; the first 180 keep id, order, version, and value keys | Original Request; `src/analysis/specifications.py` 53, 241, `_BUILDERS` | Task 7/18/22 tests |
| Metric emit gates on optional `MetricComputationInputs.inter_society_relations_analysis` (or harvest rows); empty/absent inputs yield empty value maps, not invented pairs | `src/analysis/metric_service.py` `MetricComputationInputs` + diplomacy/migration emit gates | Task 7 tests |
| `inter-society-relations-snapshot-v1` is a new canonical bounded snapshot; it does not rewrite macro-society, diplomacy, conflict, borders, or migration snapshots | `.ai-factory/ARCHITECTURE.md` accepted-set/exact-key-set; V4-02 snapshot precedent | Task 9/14/15/19 tests |
| API dual-gate: both `PALIMPSEST_INTER_SOCIETY_RELATIONS_ROOT` and `PALIMPSEST_INTER_SOCIETY_RELATIONS_CURSOR_KEY` (≥32 UTF-8 bytes) required; otherwise reader unset and routes return 503 `inter_society_relations_disabled` | `src/api/app.py` borders/migration attach 398-427; `src/infrastructure/settings.py` | Task 13/16/20 tests |
| Six GET routes under `/v1/simulations/{run_id}/inter-society-relations` require `SUBJECTIVE_DEBUG`, return 503 when disabled, and 404 for unknown published records; router is `include_router`'d from `src/api/app.py` | `docs/research-api.md`; `src/api/routes/macro_society.py`; `src/api/app.py` 582-591 | Task 16/19/20 tests |
| Cursors bind run, publication, digest, purpose, and filters; mismatch is 400 and expiry 410 | `src/simulation/macro_society_ports.py`; cursor modules for V4 stores | Task 11/16/20 tests |
| Publication is opt-in, post-completion, atomic, quota-bounded, and isolated from scientific status; CLI wires `--inter-society-relations-root` (+ max-publications/max-bytes) like borders/migration | `src/experiments/macro_society_publication.py`; `src/research_runner/cli.py` 1756-1764 | Task 14/15/20 tests |
| Research UI view id `inter-society-relations` is listed in `RESEARCH_UI_VIEWS` and `RUN_SCOPED_VIEWS` | `clients/research-ui/src/research/selection.ts` | Task 17 tests |
| The in-process E2E runs in the focused/unit lane with real harvest, publication, and all six routes; it is never reported as integration-only | Plan Settings; `tests/unit/test_macro_society_end_to_end.py` | Task 20/21 tests |
| Every current catalog-size 180 pin is swept to 184; historical revision statements and first-180 digests remain unchanged | `src/analysis/specifications.py:53` | Task 7 sweep; Task 22 re-run |
| No Godot overlay kinds are added; Research UI + API are the presentation surfaces | Original Request (no Godot ask); V4-02 precedent | Task 17/19/21 tests |
| The roadmap is owned by `$aif-roadmap` and is not edited here | `.ai-factory/ARCHITECTURE.md` requirement 7 | Task 21/23 `git status` |

### Supported combinations and availability transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| Default runner, root unset and/or cursor key unset | No ISR reader | 503 `inter_society_relations_disabled`; CLI receipt `disabled` when root unset | Task 13/15/16/20 |
| Root set, cursor key missing (or <32 bytes) | No ISR reader | 503; settings validation fails closed on short key | Task 13/16 |
| Completed run with fewer than two contemporaneous `msoc-` candidates | Empty pair inventory | Summary `pair_count=0`; domains `absent`; no invented pairs | Task 3/14/20 |
| Two non-overlapping `msoc-` candidates in one window with exchange evidence | One `isr-` pair | Domain `exchange` `present`; other domains per evidence | Task 2/3/20 |
| Two overlapping `msoc-` candidates | One legal pair | Overlap coverage recorded; no partition failure | Task 3/19 |
| Trust edges exist only inside one society | Pair retains | `trust_proxy` `absent` or `partial` by coverage rules; no civilization trust score | Task 2/7/19 |
| Cultural inventories missing for both societies | Pair retains | `cultural_similarity` `absent`; never coerced to zero `score` | Task 2/7 |
| Window series with three consecutive windows | Pair retains | Time-series rows for each window; deterministic digest | Task 5/10/20 |
| Compare two pairs via `pair_a`+`pair_b` | Comparison view | Per-domain deltas/coverage only; forbid composite | Task 6/16/19 |
| Compare same pair across windows via `pair_id`+`window_a`+`window_b` | Comparison view | Window-delta panels; no rank | Task 6/16 |
| Comparison query mixes pair operands with window operands, or omits a required half | No page | 400 `inter_society_relations_comparison_invalid` | Task 16/20 |
| Snapshot exceeds 4 MiB or row caps | No publication | `inter_society_relations_size_limit` receipt | Task 9/14 |
| Duplicate publication id with different bytes | Existing artifact untouched | `inter_society_relations_publication_exists` | Task 15 |
| Cursor reused with the same binding | Same page | 200; digest matches | Task 11/16 |
| Cursor reused after any binding change | No page served | 400 `inter_society_relations_cursor_invalid`; expiry 410 | Task 11/16 |
| Corrupt store payload | No false 404 | 500 `inter_society_relations_store_corrupt` | Task 15/16 |
| Run incomplete or publication failed | Scientific result unchanged | Receipt `unavailable`/`failed` only | Task 14/15/20 |
| In-process ISR E2E without PostgreSQL | No integration prerequisite | Runs in focused/unit lane | Task 20/21 |
| Required Compose/browser/Godot/benchmark/UI lane with a missing prerequisite | No green certification | Recorded `unexecuted` with prerequisite | Task 21/23 |
| Forbidden field name appears on any analysis/API/UI DTO | Hard failure | Leakage/forbid tests fail closed | Task 1/3/19 |

No blocking open questions: every material decision is fixed below.

## Architecture and Decisions

1. **No new flag, no new context.** V4-15 deepens analysis-only
   `macro_society_identity`; the 14 contexts, 12 flags, and `runner-config-v56`
   seam are unchanged. Context map stays `v4-context-map-v2`.
2. **Analysis-only authority.** Harvest, metrics, snapshot, store, routes, and
   Research UI never feed cognition, memory, prompts, admission, stop selectors,
   Observation, or Godot physics.
3. **Society endpoints are `msoc-`.** Pair analytics require contemporaneous
   macro-society candidates produced by the existing V4-02 detection/identity
   path (reused in-harvest). V4-15 does not mint nations or rewrite V4-02
   lineage semantics.
4. **Pairs are analytical.** An `isr-` candidate is a researcher label over an
   ordered `msoc-` pair plus window evidence. It is not a treaty, alliance,
   war, border, or shared belief.
5. **Eight domain panels, zero composite score.** Domains are closed and
   independent. Forbid-list blocks score/composite/trust/rank/valence fields.
   Cultural similarity uses Jaccard/count keys only.
6. **Trust proxies are counts.** Cross-membership directed `TRUST` edges
   contribute coverage/counts only. Person-level trust remains in
   `social.relationships`; it is never promoted to a civilization score.
7. **Time series are windowed.** Fixed `INTER_SOCIETY_RELATION_WINDOW_TICKS = 32`
   aggregates per pair per window; series are append-only researcher views.
8. **Comparison is vectorial.** Pair×pair or pair×window comparison returns
   per-domain deltas and availability — never a single relationship rank.
   HTTP comparison operands are explicit and mutually exclusive.
9. **Read-only joins.** Optional `org-`/`dip-`/`oc-`/`bord-`/`mig-` references
   resolve when available and stay unresolved otherwise; no store rewrite.
10. **Publication is opt-in with dual-gate API attach.** Both
    `PALIMPSEST_INTER_SOCIETY_RELATIONS_ROOT` and
    `PALIMPSEST_INTER_SOCIETY_RELATIONS_CURSOR_KEY` (≥32 UTF-8 bytes) are
    required to attach the reader (borders/migration pattern in `api/app.py`);
    post-completion atomic publish; scientific status isolated. CLI opt-in uses
    `--inter-society-relations-root` (+ max-publications/max-bytes).
11. **Pins.** Catalog 180 -> 184 only. New families are additive beside existing
    `inter_society_relation_lanes@1`. Commands 43, observer semantic types 73,
    Alembic `0017`, `/v1`, `observer-protocol-v1`, replay-v22/codec v20 remain.
12. **No Godot overlays.** Presentation is Research UI + GET routes only.

### Evidence mapping

| Domain key | Primary detached sources |
| --- | --- |
| `cooperation` | Contact dyadic cooperation/assistance; collective-project co-contribution across society memberships |
| `hostility` | Organized-conflict objective windows; diplomacy conflict lane; reciprocal harm events |
| `exchange` | `ExchangeCompleted` / exchange metrics inputs; diplomacy trade lane |
| `migration` | Regional journeys / migration-displacement objective movement between society residences |
| `trust_proxy` | Directed `TRUST` relationship edges whose endpoints belong to different `msoc-` members |
| `agreement` | Diplomacy/treaty accept/promise declarations; border agreement observations |
| `conflict` | `oc-` candidates and conflict action kinds joining both societies |
| `cultural_similarity` | Cultural/contact/semantic inputs recomputed over each society's member set as `overlap_count` / `union_count` / `jaccard` / `*_mean_pairwise_similarity` + availability — never a field named `score` |

### Package layout

- `src/analysis/inter_society_relations_contract.py`
- `src/analysis/inter_society_relations_layers.py`
- `src/analysis/inter_society_relations_evidence.py`
- `src/analysis/inter_society_relations_detection.py`
- `src/analysis/inter_society_relations_identity.py`
- `src/analysis/inter_society_relations_timeseries.py`
- `src/analysis/inter_society_relations_metrics.py`
- `src/analysis/metric_service.py` (optional `inter_society_relations_analysis` on `MetricComputationInputs` + emit gate)
- `src/analysis/specifications.py` (catalog 180 -> 184)
- `src/simulation/inter_society_relations_models.py`
- `src/simulation/inter_society_relations_codec.py`
- `src/simulation/inter_society_relations_ports.py`
- `src/simulation/inter_society_relations_paging.py`
- `src/experiments/inter_society_relations_completed_run.py`
- `src/experiments/inter_society_relations_publication.py`
- `src/persistence/inter_society_relations_filesystem.py`
- `src/research_runner/inter_society_relations_composition.py`
- `src/research_runner/cli.py` (flags + post-run publish path)
- `src/infrastructure/settings.py` (`inter_society_relations_root`, `inter_society_relations_cursor_key`)
- `src/api/app.py` (`_attach_inter_society_relations_reader`, `include_router`)
- `src/api/routes/inter_society_relations.py`
- `src/api/inter_society_relations_cursor.py`
- `clients/research-ui/src/api/interSocietyRelations.ts`
- `clients/research-ui/src/views/InterSocietyRelationsPanel.svelte`
- `clients/research-ui/src/research/selection.ts` (view allow-list)
- `clients/research-ui/src/views/RunOverview.svelte`
- `docs/inter-society-relations.md`
- `docs/research-api.md`, `docs/configuration.md`, `docs/research-ui.md`, `docs/analysis-metrics.md`

### Logging contract (all tasks)

- DEBUG: bounded flow steps and counts (pair_count, domain availability
  histogram, window length, page size) — never ids beyond hashed digests when
  required for diagnostics, and prefer counts only.
- INFO: harvest start/finish, publication success with byte size and pair_count,
  CLI enable/disable.
- WARN: partial coverage, unresolved joins, truncation, size-cap approach.
- ERROR: safe reason codes only (`inter_society_relations_*`).
- Control: `PALIMPSEST_LOG_LEVEL`.

## Commit Plan

- **Commit 1** (after tasks 1-4): `feat(analysis): add inter-society relation contract, evidence, and pair identity`
- **Commit 2** (after tasks 5-7): `feat(analysis): add ISR time series, comparison, and metric families (180->184)`
- **Commit 3** (after tasks 8-12): `feat(simulation): add inter-society-relations snapshot, ports, and paging`
- **Commit 4** (after tasks 13-17): `feat(research): wire ISR settings, store, CLI, API routes, and Research UI`
- **Commit 5** (after tasks 18-21): `test: cover ISR isolation, E2E, and pin sweeps`
- **Commit 6** (after tasks 22-23): `docs: document inter-society relations analytics`

Commit checkpoints are suggestions only. Do not commit during `$aif-implement`
unless the user explicitly authorizes commits.

## Tasks

### Phase 1: Contract and evidence

- [x] Task 1: Define closed ISR contract and forbid-list
  Create `src/analysis/inter_society_relations_contract.py` with closed domain
  keys (eight), availability enum (`present`/`partial`/`absent`), pair status
  vocabulary, `isr-` prefix helpers, error codes, and
  `INTER_SOCIETY_RELATIONS_FORBIDDEN_RESULT_FIELDS` extending the diplomacy
  forbid-list with `civilization_relationship_score`, `alliance_score`, and
  `enmity_score`. Pin cultural-similarity allowed value keys to
  `overlap_count`, `union_count`, `jaccard`, `*_mean_pairwise_similarity`, and
  availability — never `score` or `*_score`. Document that V4-15 deepens
  `macro_society_identity` without changing `V4_CONTEXT_MAP_VERSION` or context
  count. Add `tests/unit/test_inter_society_relations_contract.py`.
  LOGGING: DEBUG contract validation failures with reason codes only.
  Depends: none.

- [x] Task 2: Implement eight-domain evidence adapters
  Create `src/analysis/inter_society_relations_evidence.py` that harvests
  detached counts/tokens for each domain from committed events and existing
  analysis inputs (contact, exchange, conflict, migration, relationships,
  diplomacy/treaty/border exports, cultural inventories). Missing lanes report
  availability; never invent zeros-as-hostility. Cultural similarity emits only
  the Task 1 allowed keys. Add
  `tests/unit/test_inter_society_relations_evidence.py`.
  LOGGING: DEBUG per-domain row counts; WARN partial/absent coverage.
  Depends: 1.

- [x] Task 3: Detect pairs, project layers, mint `isr-` identities
  Create `inter_society_relations_{layers,detection,identity}.py`. Build
  contemporaneous `msoc-` pairs (`a < b`), project three separated layers with
  `assert_layer_separation`, and mint content-addressed `isr-` ids from window
  tick + ordered society ids + domain signature. Overlap is legal. Add unit
  tests for leakage, permutation stability, and `PYTHONHASHSEED` stability.
  LOGGING: DEBUG candidate/pair counts; ERROR on layer leak codes.
  Depends: 1, 2.
  <!-- Commit checkpoint: tasks 1-4 -->

- [x] Task 4: Wire harvest assembly from macro-society candidates
  Compose evidence + detection so harvest reuses V4-02 candidate production
  in-process (or accepts already-derived candidates) without requiring a prior
  macro-society publication artifact. Fewer than two candidates yields an empty
  pair set. Export a stable analysis object suitable for
  `MetricComputationInputs.inter_society_relations_analysis`. Add focused
  harvest tests.
  LOGGING: INFO harvest milestones with pair_count only.
  Depends: 3.

### Phase 2: Time series, comparison, metrics

- [x] Task 5: Implement windowed time series
  Create `src/analysis/inter_society_relations_timeseries.py` with
  `INTER_SOCIETY_RELATION_WINDOW_TICKS = 32`. Produce per-pair per-window domain
  panels. Series are deterministic and forward-only. Add unit tests.
  LOGGING: DEBUG window counts; WARN truncation at series caps.
  Depends: 3, 4.

- [x] Task 6: Implement pair comparison views
  Pure comparison of two pairs or two windows: per-domain count deltas and
  availability transitions only. Reject any composite/score output via
  forbid-list assertions. Add unit tests including mixed-absent domains.
  LOGGING: DEBUG comparison operand counts.
  Depends: 5.

- [x] Task 7: Append four metric families, emit gate, and sweep 180 -> 184
  Update `src/analysis/specifications.py` (`METRIC_FAMILY_COUNT`, enum,
  `_spec_*`, `_BUILDERS` tail) and `src/analysis/metric_service.py`. Families:
  `inter_society_relation_structure@1`, `inter_society_domain_evidence@1`,
  `inter_society_relation_timeseries@1`, `inter_society_pair_comparison@1`.
  These are additive beside existing `inter_society_relation_lanes@1` — do not
  rename or reuse that id. Add optional
  `MetricComputationInputs.inter_society_relations_analysis` and an
  `if inputs.inter_society_relations_analysis is not None:` emit path for all
  four families (empty-input → empty values, never invented pairs). Preserve
  first-180 identity. Sweep catalog-size pins from 180 to 184; leave historical
  revision prose unchanged. Add
  `tests/unit/test_inter_society_relations_metrics.py` and catalog tests.
  LOGGING: DEBUG metric empty-input paths.
  Depends: 4, 5, 6.
  <!-- Commit checkpoint: tasks 5-7 -->

### Phase 3: Snapshot and ports

- [x] Task 8: Guard runtime isolation
  Extend analysis-isolation / architecture coverage so ISR modules never import
  into cognition, world admission, prompts, or observer physics paths. Mirror
  asserts from `tests/architecture/test_macro_society_boundaries.py` and
  `test_analysis_isolation.py`: api/persistence must not import analysis;
  simulation must not import analysis/experiments; cognition never imports
  truth/metric symbols; no helper returns/constructs/submits `AgentCommand`;
  forbidden field names cannot appear on exported analysis rows. Prefer placing
  the durable feature suite in Task 18's boundaries file and keep this task as
  the early isolation smoke that unblocks ports.
  LOGGING: ERROR isolation violation codes in tests only.
  Depends: 1, 3.

- [x] Task 9: Define snapshot models and codec
  Create `src/simulation/inter_society_relations_{models,codec}.py` with
  `inter-society-relations-snapshot-v1` / `inter-society-relations-store-v1`,
  size caps (4 MiB), pair/window/series row caps, canonical encoding, and
  publication id derivation. Simulation models must not import analysis. Add
  codec strictness tests.
  LOGGING: DEBUG encode/decode byte sizes; ERROR reason codes.
  Depends: 3, 5, 6.

- [x] Task 10: Map analysis to snapshot DTOs
  In experiments (not analysis), map harvest/analysis outputs into snapshot
  DTOs including summary, pairs, domain panels, time series, and comparison
  tokens. Add mapping tests for empty and multi-window cases.
  LOGGING: DEBUG mapped row counts.
  Depends: 9.

- [x] Task 11: Ports, paging, and cursors
  Create `src/simulation/inter_society_relations_{ports,paging}.py` and
  `src/api/inter_society_relations_cursor.py`. Cursors bind run, publication,
  digest, purpose, and filters; mismatch 400; expiry 410. Add unit tests.
  LOGGING: WARN cursor invalid/expired codes.
  Depends: 9.
  <!-- Commit checkpoint: tasks 8-12 -->

- [x] Task 12: Facade exports
  Export new public symbols through package `__init__` facades
  (`analysis`, `simulation`, `experiments`, `persistence` as needed) without
  deep cross-package leaks. Update import-linter expectations if required by
  existing contracts.
  LOGGING: none beyond import failures.
  Depends: 9, 11.

### Phase 4: Settings, publication, API, UI

- [x] Task 13: Settings and dual-gate API attach
  Add `inter_society_relations_root: Path | None` and
  `inter_society_relations_cursor_key: SecretStr | None` to
  `src/infrastructure/settings.py` with ≥32-byte cursor-key validator and
  safe-summary `has_*` flags (never log secrets). Implement
  `_attach_inter_society_relations_reader` in `src/api/app.py` using the
  borders/migration dual-gate: if root is None or secret is None, set reader and
  codec to None (503 path). Wire dependency getters. Update
  `docs/configuration.md` in Task 22; add settings unit tests here.
  LOGGING: DEBUG attach enabled/disabled with booleans only.
  Depends: 11, 12.

- [x] Task 14: Completed-run harvest and publication bridge
  Create `src/experiments/inter_society_relations_{completed_run,publication}.py`
  following macro-society: opt-in, post-completion only, atomic publish,
  scientific status isolated (`unavailable`/`failed` receipts). Add publication
  tests for size limit and success paths.
  LOGGING: INFO publish success (bytes, pair_count); ERROR safe failure codes.
  Depends: 4, 10, 11.

- [x] Task 15: Filesystem store and CLI composition
  Create `src/persistence/inter_society_relations_filesystem.py` and
  `src/research_runner/inter_society_relations_composition.py` with
  `producer_options_from_args`. Wire `src/research_runner/cli.py`:
  `--inter-society-relations-root`, `--inter-society-relations-max-publications`
  (default 16), `--inter-society-relations-max-bytes` (default 8_388_608),
  options parse, and post-run publish/receipt print path mirroring
  borders/migration. Duplicate publication id with different bytes must leave
  the existing artifact untouched. Add filesystem and CLI tests.
  LOGGING: INFO store write; WARN quota; ERROR corrupt/exists codes.
  Depends: 13, 14.

- [x] Task 16: Six GET routes under `/v1`
  Create `src/api/routes/inter_society_relations.py` and
  `include_router` it from `src/api/app.py`: summary; pairs (paged); pair
  detail; pair time series; pair comparison; lineage/windows (paged). Require
  `SUBJECTIVE_DEBUG`; unset reader -> 503 `inter_society_relations_disabled`;
  unknown record -> 404; corrupt -> 500 `inter_society_relations_store_corrupt`.
  Comparison Query contract: either (`pair_a` and `pair_b`) XOR
  (`pair_id` and `window_a` and `window_b`); incomplete/mixed operands -> 400
  `inter_society_relations_comparison_invalid`. Add API tests mirroring
  `tests/unit/test_macro_society_api.py`.
  LOGGING: DEBUG request purpose codes; never log pair bodies.
  Depends: 11, 13, 15.

- [x] Task 17: Research UI panel
  Add `clients/research-ui/src/api/interSocietyRelations.ts`,
  `InterSocietyRelationsPanel.svelte`, RunOverview tab, and view id
  `inter-society-relations` to both `RESEARCH_UI_VIEWS` and `RUN_SCOPED_VIEWS`
  in `clients/research-ui/src/research/selection.ts`. Render eight domain
  panels, time series, and comparison without inventing a composite score
  chrome. Map `inter_society_relations_disabled` to unavailable. Add UI
  tests/types.
  LOGGING: client stays metadata-safe; no score widgets.
  Depends: 16.
  <!-- Commit checkpoint: tasks 13-17 -->

### Phase 5: Tests, docs, verification

- [x] Task 18: Boundary and pin regression suites
  Add `tests/architecture/test_inter_society_relations_boundaries.py` covering:
  no flag/context/`v57`; GET-only AST; forbid-list; layer separation; catalog
  184; additive families must not collide with
  `inter_society_relation_lanes`; Alembic `0017`; commands 43; observer
  semantic types 73; api/persistence must not import analysis; simulation must
  not import analysis/experiments; no `AgentCommand`/world-authority tokens.
  Extend `test_analysis_isolation.py` and V4 invariant suites as needed.
  LOGGING: N/A beyond test failure messages.
  Depends: 7, 8, 16.

- [x] Task 19: Determinism and forbid-list hardening
  Hypothesis/property tests for `isr-` stability, window series digests, and
  hard failure when forbidden field names appear on rows/metrics/snapshot DTOs
  (including cultural similarity keys).
  Depends: 3, 5, 6, 7, 9.

- [x] Task 20: In-process E2E in the unit lane
  Add `tests/unit/test_inter_society_relations_e2e.py` (or end_to_end) that runs
  real ticks/events sufficient to form two societies, harvests domains, publishes
  to a temp store with dual-gate settings, and hits all six routes including both
  comparison operand modes — without PostgreSQL and without labeling the test as
  integration-only.
  LOGGING: INFO E2E milestones with counts only.
  Depends: 13, 14, 15, 16.

- [x] Task 21: Full verification receipt
  Execute/record required lanes: unit+architecture with coverage; static
  (ruff/mypy/import-linter); Research UI; docs parity; integration;
  Compose/browser; Godot; benchmark/scale. Missing prerequisites ->
  `unexecuted` with reason. Certify pins: runner v4/v55/v56, result v2/v3,
  43/73/**184**, 14 contexts / 12 flags, replay-v22/codec v20, `/v1`,
  `observer-protocol-v1`, Alembic `0017`. Confirm ROADMAP.md untouched.
  Depends: 18, 19, 20.
  <!-- Commit checkpoint: tasks 18-21 -->

- [x] Task 22: `$aif-docs` checkpoint
  Create/update `docs/inter-society-relations.md`, index it from `README.md`,
  update `docs/analysis-metrics.md` for the four families (and disambiguate from
  `inter_society_relation_lanes@1`), update `docs/research-api.md` route/status
  tables, `docs/configuration.md` for root/cursor-key dual-gate, and
  `docs/research-ui.md` for the new panel. Add the V4-15 seam note to
  `.ai-factory/ARCHITECTURE.md` / `docs/architecture.md` /
  `.ai-factory/DESCRIPTION.md` (deepen `macro_society_identity`; four families;
  forbid composite score; six routes; dual-gate settings; no flag). Re-sweep
  catalog-size 180 -> 184 mentions that mean current pins. No ROADMAP edit.
  LOGGING: N/A.
  Depends: 7, 13, 16, 17.

- [x] Task 23: Final pin and non-edit audit
  Confirm absence of `runner-config-v57`, new V4 flag, new context, command,
  event, observer semantic type, write pair, SQL migration, Godot overlay kind,
  and ROADMAP.md changes. Record certification status in the plan progress
  notes during `$aif-implement` / `$aif-verify`.
  Depends: 21, 22.
  <!-- Commit checkpoint: tasks 22-23 -->

## Definition of Done

- Eight researcher-only domain panels exist for society pairs without any
  authoritative civilization relationship score.
- Historical window time series and pair comparison work via snapshot + API
  with an explicit comparison query contract.
- Metric catalog is 184 with four appended families; first 180 unchanged;
  `inter_society_relation_lanes@1` remains distinct.
- Dual-gate settings attach the reader; six `SUBJECTIVE_DEBUG` GET routes,
  CLI flags, and Research UI panel (allow-listed view id) ship; disabled/corrupt
  codes are stable.
- Isolation, forbid-list, and E2E tests are green in the unit lane.
- Docs checkpoint completed across feature, API, configuration, and Research UI
  pages; ROADMAP untouched (pending `$aif-roadmap`).
- Required verification lanes executed or honestly recorded `unexecuted`.

## Progress notes (Task 21 / 23)

Recorded 2026-11-09 during `$aif-implement` completion; refreshed 2026-11-09
during `$aif-verify` issue remediation.

| Lane | Result |
| --- | --- |
| Unit + architecture (ISR suites, docs parity, V4 invariants, analysis isolation) | passed (verify re-run: ISR focused `84`; broader pin selection `123`; ISR+`--cov` `69`) |
| Static: ruff ISR-touched `src`/`tests` | passed |
| Static: mypy ISR modules | passed (`17` files) |
| Static: import-linter | passed (`25` contracts kept) |
| Research UI: vitest `InterSocietyRelationsPanel` | passed (`2`) |
| Research UI: `svelte-check` (app tsconfig) | passed (`0` errors) |
| Docker Compose `config --quiet` | passed |
| Compose/browser acceptance | `unexecuted` — prerequisite: attested Compose/browser image stack |
| Integration (PostgreSQL) | `unexecuted` — prerequisite: `PALIMPSEST_TEST_DATABASE_URL` |
| Godot 4.7 protocol suite | `unexecuted` — prerequisite: `GODOT_BIN` (Godot 4.7.x) |
| Benchmark / integration-scale | `unexecuted` — prerequisite: `PALIMPSEST_TEST_DATABASE_URL` (+ scale markers) |

**Certification:** local required evidence green; full required-gate certification
**withheld** while the four env-gated lanes above remain `unexecuted`.

**Pins certified in code/docs:** runner v4/v55/v56, result v2/v3, commands 43,
observer semantic types 73, metric families **184**, 14 contexts / 12 flags,
replay-v22/codec v20, `/v1`, `observer-protocol-v1`, Alembic `0017` (no `0018`).

**Task 23 audit:** no `runner-config-v57`, no new V4 flag/context/command/event/
observer semantic/write pair/SQL migration/Godot overlay. `.ai-factory/ROADMAP.md`
**registers V4-15 under M8** (catalog **184**; verification receipt noted).
