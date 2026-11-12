<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: Accounting Ledgers

Mode: ultra
Branch: main
Created: 2026-11-12

## Original Request

v4-23 accounting

Naming requirement:

Use `v4-23-accounting-ledgers`.

Extend external records with accounting-like artifacts.

Support records of:

- exchanges
    
- debts
    
- inventories
    
- organizational resources
    
- contributions

Records may be:

correct  
wrong  
outdated  
fraudulent  
damaged

Do not make ledger content objective truth.

Allow agents/institutions to use ledgers as evidence.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose/browser, Godot regression (existing suites only), Research UI,
  benchmark regression, and static gates, with coverage enabled for Python
  lanes.
- Logging: verbose, metadata-only. Bounded DEBUG record/entry/flow/alignment
  counts and selected status tokens, INFO activation/publication/router
  milestones, WARN truncation/partial coverage/malformed frames/unresolved
  records/oversize rows, ERROR safe codes. `PALIMPSEST_LOG_LEVEL` controls
  operational verbosity. Never log owner tokens, record tokens, counterparty
  tokens, organization tokens, item kinds, quantities, assessments, valuations,
  confidence values, anchors, cursor keys, digests, credentials, DSNs, memories,
  embeddings, or payload surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 21.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning or implementation unless the user explicitly asks.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-23-accounting-ledgers`; the ultra bundle directory
  is `.ai-factory/plans/v4-23-accounting-ledgers/`, phase files use
  `phase-NN-<slug>.md`, and `index.md` is the canonical entrypoint. Python and
  artifact tokens use `accounting_ledgers` / `accounting-ledgers-*` because
  identifiers cannot contain spaces or slashes; the feature name is "accounting
  ledgers".
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only in this invocation. No implementation, commit, roadmap
  edit, or branch creation occurs while planning.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-23 deepens the already-owned `organizations` V4 context and the
V3-11 durable-records seam into owner-scoped accounting interpretations, adding
no new V4 context, flag slot, runner schema, command, event, money, objective
ledger, or enforceable book of record. `$aif-roadmap` registered V4-22 in M8 on
2026-11-12 and recorded eight owned V4 flags with four unowned. This plan does
not close M8 or edit other milestones.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Versioned Extension Contract", V3-11, V3-17, V3-18, V4-03,
V4-04, V4-08, V4-20 through V4-22 seams) and `.ai-factory/RULES.md` constrain
every edit; `.ai-factory/DESCRIPTION.md` and `.ai-factory/ROADMAP.md` describe
current state; the source paths below define the concrete contracts. No
requirement source is edited to create this plan; the landing in Task 21 records
the implemented seam in the descriptive project documents, while the roadmap
remains owned by `$aif-roadmap`.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-23 deepens the already-owned `organizations` context; contexts stay 14, flags 12, owned 8, unowned 4; no new context, flag slot, `runner-config-v57`, root field, or per-agent runner key | Original Request; `src/simulation/v4_architecture.py:98-127`; `src/simulation/runner_models.py:307-339,1128-1179` | Task 1/3/20/23 |
| `organizations` stays `OWNER_SCOPED` with owners `("agents.cognition","social","simulation")`, `uses_existing_events=True`, prerequisites `()`, and its existing non-goals; prerequisites are planning order, never a runtime gate | `src/simulation/v4_architecture.py:110-127`; `src/simulation/compatibility.py:155-166` | Task 1/20/23 |
| Accounting cognition activates only when `organizations` is enabled **and** the V3-11 `durable_records` spec is present; the durable channel keeps its existing prerequisites (`cultural_historical_memory`, `cultural_feature_provenance`); otherwise no ledger, no `acc_v1`, and V3-11/V4-03/V4-04/V4-22 behavior is unchanged | Original Request "Extend external records"; `src/simulation/runner_models.py:3552-3824,7860,8930-8975`; `src/simulation/runner.py:1024-1037,1492-1514,2934,6806,7206` | Task 3/17/18 |
| External accounting artifacts reuse existing durable-record genres, artifact kinds, relation tokens, `Inscribe`/`Amend`/`CopyRecord`, and artifact events; no new genre, kind, command, event, or write pair is added | Original Request "accounting-like artifacts"; `src/world/artifacts.py:21-24,97-127,255-311,314-527`; `src/world/events.py:1400-1704` | Task 1/2/4/20 |
| An accounting-like record is any durable-capable artifact with at least one `acc_v1` relation triple; marks and prose are never parsed; unknown triples are ignored with a bounded count | Original Request "Do not make ledger content objective truth"; `src/world/artifacts.py:255-311` | Task 1/2/4 |
| One owner keeps one bounded `AccountingLedger` of five record kinds (`exchange`, `debt`, `inventory`, `organizational_resource`, `contribution`), six directions, record assessments, revisions, evidence refs, confidence, counts, and notices; no item ids, inventories, peer state, money, or world state | Original Request "exchanges/debts/inventories/organizational resources/contributions"; `src/agents/cognition/credit_relationships.py:84-103,457-834` | Task 1/2/20 |
| Record assessments (`unassessed`, `consistent`, `contradicted`, `outdated`, `suspected_fraudulent`, `damaged`) are owner beliefs; `correct`/`wrong`/`fraudulent` never become objective truth, verdict, or fraud finding | Original Request "records may be correct/wrong/outdated/fraudulent/damaged"; `src/agents/cognition/evidence_testimony.py:118-198` | Task 1/2/8/22 |
| Bounded `acc_v1` frames (16 parts, 320 characters, at most one relation) travel inside existing `Talk`/`Tell`; no new speech command, command field, or V3 situation is added | Original Request "Allow agents/institutions to use ledgers as evidence"; `src/agents/cognition/credit_relationships_communication.py:200-268`; `src/agents/cognition/deliberation.py:1418-1432` | Task 4/20/23 |
| Accounting content may extend an **already-selected** `Inscribe` command only; the verb, kind, class, and recipient are unchanged, and no command is created, replaced, or biased | Original Request "Extend external records"; `src/agents/cognition/artifacts.py:498-535`; `src/world/actions.py:347-392` | Task 4/18/20 |
| Evidence use is a pure candidate bridge into the existing V4-08 ledger; no automatic write, no evidence schema change, and no accounting truth in the evidence record | Original Request "use ledgers as evidence"; `src/agents/cognition/evidence_testimony.py:1643-1706,1768-1778,2266-2272` | Task 2/8/19 |
| Analysis evidence is committed record/artifact, transfer, contribution, and `Talked`/`Told` `acc_v1` events plus detached owner export rows; no `WorldState`, runtime, store, API object, or peer ledger is read | `src/world/events.py:639-764,1400-1704,2591-2718`; `src/analysis/credit_relationships_events.py` | Task 5/6/9/19 |
| Accounting analysis is descriptive only: counts, integer quantity sums, milli shares, and distributions; no balance, total value, solvency, score, ranking, or audit authority | Original Request "Do not make ledger content objective truth"; `src/analysis/credit_relationships_detection.py:77-222` | Task 7/8/10/19 |
| Researcher-only alignment compares owner entries with committed record/transfer evidence (`consistent`/`unresolved`/`inconsistent`/`not_applicable`) and never reaches cognition, prompts, memory, world state, observer semantics, or stop selectors | Original Request; `src/analysis/credit_relationships_expectations.py:50-395` | Task 8/9/19 |
| Four metric families append 216 -> **220**; the first 216 ids, order, versions, and value keys stay unchanged, and every active suite/docs pin is swept in the same change | `src/analysis/specifications.py:53,286-293,8971-9019,9278-9306,9397-9438,9733,9946-9949`; `src/analysis/metric_service.py:34-40,403-405,2623-2651` | Task 10/11/20/22 |
| Snapshot is a sibling `accounting-ledgers-snapshot-v1` with store `accounting-ledgers-store-v1`, two dual-gated settings, window-bound cursors, and seven GET-only routes failing closed with `accounting_ledgers_disabled`; it is not a runner/result/replay/SQL schema | `src/simulation/credit_relationships_models.py:33-37,469-533`; `src/persistence/credit_relationships_filesystem.py:37-112`; `src/infrastructure/settings.py:260-263,478-487,885-897`; `src/api/app.py:599-625,838` | Task 12/13/14/15 |
| No Godot overlay is added: accounting is an owner/analytical structure; the presentation client is unchanged and its existing suite is the regression gate | Original Request; `.ai-factory/ARCHITECTURE.md` V3-40 through V3-42 seam | Task 16/20/23 |
| Publication is programmatic and post-completion; no CLI producer and no runner flag is added | `src/experiments/credit_relationships_publication.py:100-379`; V4-20/V4-21/V4-22 have no CLI producer | Task 14/23 |
| Off-gate experiment `accounting_ledgers@1` composes `organizations`, `durable_records`, and optional `structured_commitments`/`subjective_valuation`/`evidence_testimony` and never enters the V1 A-E gate | `src/experiments/catalog.py:2800-2837,5711-5729`; `src/experiments/credit_relationship_scenario.py:41-152` | Task 17/23 |
| Documentation covers `docs/accounting-ledgers.md`, README, ARCHITECTURE, DESCRIPTION, `docs/architecture.md`, `docs/configuration.md`, `docs/analysis-metrics.md`, `docs/research-api.md`, `docs/v4-architecture.md`, `docs/cognition-runtime.md`, and cross-links in `docs/organizations.md`, `docs/evidence-testimony.md`, and `docs/credit-relationships.md`; roadmap registration stays with `$aif-roadmap` | `.ai-factory/ARCHITECTURE.md` requirement 7; `.ai-factory/ROADMAP.md`; `docs/credit-relationships.md` | Task 21/22/23 `git status` |

### Supported combinations and coverage transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| `organizations` off, `durable_records` on | V3-11 records only | No accounting mode, ledger, `acc_v1`, metric input, or snapshot field; record bytes unchanged | Task 3/17 |
| `organizations` on, `durable_records` absent | V4-03/V4-04 only | Accounting disabled; empty ledger; existing organization behavior unchanged | Task 3/17 |
| Both present | Deterministic accounting mode and locked policy; the durable channel already satisfies its own cultural/provenance prerequisites | `acct-`/`acce-` ledger allocated; no write pair, schema, or v57 | Task 2/3/20 |
| Record with valid `acc_v1` triples | `direct_record` claim | One entry per accepted triple; quantity 1..64; no truth field | Task 2/4 |
| Record without `acc_v1` triples | Untouched record | Ignored; no entry, no error | Task 2 |
| Malformed or oversize relation | Ignored | One bounded invalid-token count; simulation continues | Task 1/2/4 |
| Record observed damaged/partially lost | `damaged` assessment | Owner appraisal only; no item or record mutation | Task 2 |
| Record disagrees with an observed committed transfer | `contradicted` assessment | Owner belief only; no correction command | Task 2/6 |
| Record older than a newer observed revision | `outdated` assessment | Prior terms retained; revision appended | Task 2 |
| Two same-anchor records disagree, or a trusted `dispute_entry` claim | `suspected_fraudulent` assessment | Belief only; never a fraud finding | Task 2/8 |
| Communicated `acc_v1` claim | `communicated` claim | Receiver folds its own claim with reduced confidence; no ledger copy | Task 2/4 |
| Entry with no matching record/transfer | Owner row retained | Alignment `not_applicable`; analytical rows unchanged | Task 8 |
| No owner ledgers exported | Objective record/flow evidence | Owner/alignment coverage `missing`; no fabricated `acco-` row | Task 8/14 |
| Fewer than four samples | `insufficient_samples` | Distribution row with counts and no invented quantile | Task 7/10 |
| Four or more samples | `available` | Counts, five quantiles, IQR, dispersion, five bin shares | Task 7/10 |
| Quantity above 64 | `out_of_range` | No quantity sample; excluded and counted | Task 7 |
| Selected command is `Talk`/`Tell` | Optional one `acc_v1` relation | Same command class, verb, and recipient | Task 4 |
| Selected command is `Inscribe` | Optional accounting content | Same command class, kind, and recipient; at most 8 relations | Task 4/18 |
| Selected command is neither | Unchanged | No accounting attachment | Task 4 |
| Row or cap exceeded | Deterministic prefix | `coverage="partial"` plus one bounded truncation notice | Task 2/6/7/8/12/19 |
| Snapshot dual gate unset | No reader | 503 `accounting_ledgers_disabled` on all seven routes | Task 13/15 |
| Corrupt snapshot payload | No data | 500 `accounting_ledgers_store_corrupt` | Task 13/15 |
| Paged route with `window_index` | Filter-bound cursor | Only matching rows; cursor for another window rejected 400 | Task 12/15 |
| Publication disabled by the caller | No artifact | Nothing written; scientific status unchanged | Task 14 |
| Another unowned V4 flag | Unchanged | `capability_unimplemented`; fixtures repointed to `science` | Task 3/11/20 |
| Env-gated lane missing prerequisite | No green certification | `unexecuted` plus prerequisite | Task 23 |

No blocking open questions: every material decision is fixed below.

## Architecture and Decisions

1. **Deepen, do not claim.** V4-23 deepens the owned `organizations` context on
   the accepted `runner-config-v56` seam. It adds no V4 context, flag slot,
   `runner-config-v57`, root field, per-agent runner key, command, event,
   observer semantic type, write pair, `/v2` route, or migration. Counts remain
   14 contexts / 12 flags / 8 owned / 4 unowned.
2. **Records stay objective; accounting stays belief.** V3-11 artifacts keep
   their existing genres, integrity, lineage, and damage semantics. The
   accounting ledger interprets observed records; it never rewrites a record,
   never repairs damage, and never asserts what a record means.
3. **One bounded owner ledger.** `AccountingLedger` stores entries keyed by an
   owner-local `acct-` anchor with kind, direction, item kind, quantity,
   organization/counterparty tokens, assessment, integrity, confidence,
   revisions, evidence refs, counts, and notices. Row ids are `acce-`; no item
   id, inventory count, structure quantity, peer state, or world state is stored.
4. **Five record kinds.** `exchange`, `debt`, `inventory`,
   `organizational_resource`, and `contribution` are the only kinds. They are
   descriptive categories, not permissions, balances, or ownership.
5. **Assessments are appraisals.** `consistent`, `contradicted`, `outdated`,
   `suspected_fraudulent`, and `damaged` record what one owner believes about a
   record. `consistent` is not truth; `suspected_fraudulent` is not proven fraud;
   `damaged` reflects observed integrity but remains a belief.
6. **Accounting artifacts are existing records.** An accounting-like artifact is
   any durable-capable artifact carrying at least one `acc_v1` relation triple.
   The grammar is compact (`<entry_code>_<item_kind>`, `<direction_code><quantity>`)
   and validated against the existing 32-character artifact token rule. No new
   genre, kind, event, or command exists.
7. **Speech is the only new transport.** `acc_v1` frames carry one entry act and
   terms inside existing `Talk`/`Tell`. One optional relation may be attached to
   an already-selected utterance; the command is not created or replaced.
8. **Inscription extends, never replaces.** Accounting content may be attached to
   an already-selected `Inscribe`; the verb, kind, class, and recipient stay
   identical. No command is selected because of accounting.
9. **Evidence is opt-in.** `accounting_evidence_candidates` returns at most four
   owner-scoped candidates using existing evidence DTOs. The cognition stage may
   fold them; nothing writes automatically, and the evidence schema is unchanged.
   "Institutions" use ledgers only through owner agents whose entries carry
   `accorg-` tokens; no institution actor, shared ledger, or organization
   cognition exists.
10. **Analysis is committed-only.** Record, transfer, contribution, and speech
    evidence comes from committed events; owner rows come from token-only detached
    exports. Live cognition, runtimes, stores, and API objects are never read.
11. **Descriptive, not adjudicative.** Counts, integer quantity sums, and milli
    shares are reported. No balance, total value, net worth, solvency, score,
    ranking, audit, or reconciliation authority exists.
12. **Alignment is researcher-only.** Owner-versus-evidence alignment is
    `consistent`/`unresolved`/`inconsistent`/`not_applicable` and never reaches
    cognition, prompts, memory, world state, observer semantics, or stop
    selectors.
13. **Bounded everything.** Records, entries, claims, revisions, evidence,
    transfers, contributions, owner rows, flows, counterparties, alignments, and
    snapshot families have independent caps with deterministic prefixes,
    `coverage="partial"`, and one bounded notice per family.
14. **Sibling artifact and read-only surfaces.** `accounting-ledgers-snapshot-v1`
    is canonical with digest and publication id and no wall-clock field;
    `accounting-ledgers-store-v1` is atomic, quota-bounded, idempotent, and
    corruption-safe; cursors bind `window_index`; seven GET-only dual-gated
    routes serve it. Publication is programmatic and post-completion. The
    Research UI adds one read-only panel; Godot gets no overlay.
15. **Catalog and pins.** Four metrics append 216 -> 220, every active pin is
    swept, `accounting_ledgers@1` stays off the V1 gate, and `$aif-roadmap`
    registers V4-23 and re-confirms V4-17 through V4-22.

### Locked accounting summary

| Dimension | Locked behavior |
| --- | --- |
| Policy | `accounting-ledgers.v1` (cognition and analysis share the token); communication `accounting-ledgers-communication.v1` |
| V4 ownership | `organizations` owned; 14 contexts / 12 flags / 8 owned / 4 unowned |
| Runner schema | `runner-config-v56` only; no v57, no new root/per-agent runner key |
| Activation | `organizations` **and** V3-11 `durable_records` (the durable channel keeps its own `cultural_historical_memory` + `cultural_feature_provenance` prerequisites); otherwise disabled |
| Record input | Durable-capable artifacts with `acc_v1` relation triples; existing genres only |
| Optional inputs | V3-17 commitments, V3-18 valuations, V4-08 evidence, V3-20/21 contributions |
| Cognition ledger | `acct-` anchors / `acce-` rows; 32 entries, 16 claims/entry, 8 revisions/entry, 8 evidence/entry, 8 counterparties, 8 notices |
| Entry kinds | `exchange`, `debt`, `inventory`, `organizational_resource`, `contribution` |
| Directions | `inflow`, `outflow`, `holding`, `receivable`, `payable`, `contribution` |
| Assessments | `unassessed`, `consistent`, `contradicted`, `outdated`, `suspected_fraudulent`, `damaged` |
| Observed integrity | `intact`, `damaged`, `partially_lost`, `unknown` |
| Claim sources | `direct_record`, `communicated`, `derived`, `unknown`; communicated confidence is `max(0, frame_confidence - 200)` |
| Acts | `declare_entry`, `cite_record`, `affirm_entry`, `dispute_entry`, `correct_entry`, `retract_entry` (locked transition table in Task 2) |
| Quantities | Item kind plus integer 1..64; valuation 0..64,000 milli; confidence 0..1,000 milli |
| Speech frame | `acc_v1`, 16 parts, 320 characters, 32 relations, one relation per `Talk`/`Tell` |
| Inscription | Optional merged content on an already-selected `Inscribe`; preserves existing marks/relations, total relations <= 8, genre from `accounting_record_genre` |
| Analysis sources | objective record/transfer/contribution events, committed claims, token-only owner rows; never pooled with objective counts |
| Window | 32 ticks; index `tick // 32`; at most 512 windows |
| Distribution | sample count, min/p25/median/p75/max, IQR, dispersion, five bin shares in milli; min 4 samples |
| Analysis cap | 200k per event family; owner 4,096; entries 4,096; records 2,048; counterparties 1,024; flows 4,096; alignments 4,096; conditions 1,024 |
| Alignment | consistent <= 250 milli gap, inconsistent >= 750, else unresolved |
| Snapshot | `accounting-ledgers-snapshot-v1`; store `accounting-ledgers-store-v1`; 16 publications / 8 MiB; no wall-clock field |
| Routes | 7 GET-only under `SUBJECTIVE_DEBUG`; default limit 100; max 500; `accounting_ledgers_disabled` when unset |
| Catalog | 216 -> 220 families; first 216 unchanged; active suite and docs pins swept to 220 |
| Clients | Research UI panel; no new Godot overlay |
| Experiment | `accounting_ledgers@1`, off the V1 gate |
| Pins | 43 commands; 73 observer semantics; replay-v27/codec `v25`; Alembic `0017`; `/v1`; `observer-protocol-v1` |

## Phase Index

1. [Phase 1: Contract and Owner-Scoped Accounting Cognition](phase-01-contract-and-owner-accounting-cognition.md) — Tasks 1-4
2. [Phase 2: Analysis Evidence and Detection](phase-02-analysis-evidence-and-detection.md) — Tasks 5-7
3. [Phase 3: Owner Joins, Metrics, and Pins](phase-03-owner-joins-metrics-pins.md) — Tasks 8-11
4. [Phase 4: Collection and Publication](phase-04-collection-and-publication.md) — Tasks 12-14
5. [Phase 5: Read-Only Surfaces](phase-05-read-only-surfaces.md) — Tasks 15-16
6. [Phase 6: Experiment and End-to-End](phase-06-experiment-and-e2e.md) — Tasks 17-19
7. [Phase 7: Invariants and Pins](phase-07-invariants-and-pins.md) — Task 20
8. [Phase 8: Documentation and Verification](phase-08-docs-and-verification.md) — Tasks 21-23

## Cross-Phase Dependencies

- Task 1 defines the contract consumed by every later task.
- Task 2 depends on Task 1 (policy, enums, ids, record grammar).
- Task 3 depends on Tasks 1-2 (ledger and carry contract).
- Task 4 depends on Tasks 1-3 (frames, activation, ledger).
- Task 5 depends on Task 1 (record grammar, token prefixes, policy vocabulary).
- Task 6 depends on Task 5 (contract, policy, rows, window helpers).
- Task 7 depends on Task 6 (record and claim evidence).
- Task 8 depends on Tasks 5-7 (owner inputs to join).
- Task 9 depends on Tasks 6-8 (evidence, detection, owner join).
- Task 10 depends on Task 9 (analysis object and locked keys).
- Task 11 depends on Task 10 (catalog count and ownership set).
- Task 12 depends on Tasks 9-10 (row families and counts).
- Task 13 depends on Task 12 (snapshot codec).
- Task 14 depends on Tasks 9-10 and 12-13 (analysis, snapshot, store).
- Task 15 depends on Tasks 12-14 (snapshot, store, publication).
- Task 16 depends on Task 15 (routes and schemas).
- Task 17 depends on Tasks 3-4, 10, and 14 (activation, metrics, collector).
- Task 18 depends on Tasks 14-17 (publication, API, experiment).
- Task 19 depends on Task 18 (stable E2E fixtures).
- Task 20 depends on Tasks 1-19 (all pins).
- Task 21 depends on Task 20 (pins before prose).
- Task 22 depends on Task 21 (docs to pin).
- Task 23 depends on Tasks 18-22 (gates and docs).

## Tasks

### Phase 1: Contract and Owner-Scoped Accounting Cognition
- [x] Task 1: Lock the accounting ledger contract, policy, and identifiers ([details](phase-01-contract-and-owner-accounting-cognition.md#task-1-lock-the-accounting-ledger-contract-policy-and-identifiers))
- [x] Task 2: Add the owner-scoped accounting ledger with record-anchor binding ([details](phase-01-contract-and-owner-accounting-cognition.md#task-2-add-the-owner-scoped-accounting-ledger-with-record-anchor-binding)) (depends on 1)
- [x] Task 3: Activate and carry accounting ledgers under organizations and durable records ([details](phase-01-contract-and-owner-accounting-cognition.md#task-3-activate-and-carry-accounting-ledgers-under-organizations-and-durable-records)) (depends on 1, 2)
- [x] Task 4: Add acc_v1 frames with bounded record-sensitive attachment ([details](phase-01-contract-and-owner-accounting-cognition.md#task-4-add-acc_v1-frames-with-bounded-record-sensitive-attachment)) (depends on 1-3)

### Phase 2: Analysis Evidence and Detection
- [x] Task 5: Lock the accounting analysis contract, policy, and caps ([details](phase-02-analysis-evidence-and-detection.md#task-5-lock-the-accounting-analysis-contract-policy-and-caps)) (depends on 1)
- [x] Task 6: Extract committed record, transfer, and contribution evidence ([details](phase-02-analysis-evidence-and-detection.md#task-6-extract-committed-record-transfer-and-contribution-evidence)) (depends on 5)
- [x] Task 7: Detect accounting entries, record conditions, and flow distributions ([details](phase-02-analysis-evidence-and-detection.md#task-7-detect-accounting-entries-record-conditions-and-flow-distributions)) (depends on 6)

### Phase 3: Owner Joins, Metrics, and Pins
- [x] Task 8: Join detached owner rows and researcher-only alignment ([details](phase-03-owner-joins-metrics-pins.md#task-8-join-detached-owner-rows-and-researcher-only-alignment)) (depends on 5-7)
- [x] Task 9: Compose the bounded AccountingLedgersAnalysis harvest ([details](phase-03-owner-joins-metrics-pins.md#task-9-compose-the-bounded-accountingledgersanalysis-harvest)) (depends on 6-8)
- [x] Task 10: Append four accounting metric families to 220 ([details](phase-03-owner-joins-metrics-pins.md#task-10-append-four-accounting-metric-families-to-220)) (depends on 9)
- [x] Task 11: Sweep suite-wide ownership and catalog pins ([details](phase-03-owner-joins-metrics-pins.md#task-11-sweep-suite-wide-ownership-and-catalog-pins)) (depends on 10)

### Phase 4: Collection and Publication
- [x] Task 12: Add accounting snapshot models, codec, ports, and paging ([details](phase-04-collection-and-publication.md#task-12-add-accounting-snapshot-models-codec-ports-and-paging)) (depends on 9, 10)
- [x] Task 13: Add the atomic filesystem store and dual-gated settings ([details](phase-04-collection-and-publication.md#task-13-add-the-atomic-filesystem-store-and-dual-gated-settings)) (depends on 12)
- [x] Task 14: Compose and publish completed-run accounting snapshots ([details](phase-04-collection-and-publication.md#task-14-compose-and-publish-completed-run-accounting-snapshots)) (depends on 9, 10, 12, 13)

### Phase 5: Read-Only Surfaces
- [x] Task 15: Add seven GET-only dual-gated accounting routes ([details](phase-05-read-only-surfaces.md#task-15-add-seven-get-only-dual-gated-accounting-routes)) (depends on 12-14)
- [x] Task 16: Add the Research UI accounting client and panel ([details](phase-05-read-only-surfaces.md#task-16-add-the-research-ui-accounting-client-and-panel)) (depends on 15)

### Phase 6: Experiment and End-to-End
- [x] Task 17: Register off-gate accounting_ledgers@1 ([details](phase-06-experiment-and-e2e.md#task-17-register-off-gate-accounting_ledgers1)) (depends on 3-4, 10, 14)
- [x] Task 18: Add in-process accounting end-to-end coverage ([details](phase-06-experiment-and-e2e.md#task-18-add-in-process-accounting-end-to-end-coverage)) (depends on 14-17)
- [x] Task 19: Add determinism, property bounds, and leakage coverage ([details](phase-06-experiment-and-e2e.md#task-19-add-determinism-property-bounds-and-leakage-coverage)) (depends on 18)

### Phase 7: Invariants and Pins
- [x] Task 20: Enforce architecture invariants and pin sweeps ([details](phase-07-invariants-and-pins.md#task-20-enforce-architecture-invariants-and-pin-sweeps)) (depends on 1-19)

### Phase 8: Documentation and Verification
- [x] Task 21: Documentation via aif-docs ([details](phase-08-docs-and-verification.md#task-21-documentation-via-aif-docs)) (depends on 20)
- [x] Task 22: Add documentation pin and negative parity checks ([details](phase-08-docs-and-verification.md#task-22-add-documentation-pin-and-negative-parity-checks)) (depends on 21)
- [x] Task 23: Required-gate verification certification ([details](phase-08-docs-and-verification.md#task-23-required-gate-verification-certification)) (depends on 18-22)

## Commit Plan

- **Commit 1** (after tasks 1-4): `feat(cognition): add owner-scoped accounting ledgers`
- **Commit 2** (after tasks 5-7): `feat(analysis): reconstruct accounting records and flows`
- **Commit 3** (after tasks 8-11): `feat(analysis): add accounting metrics and catalog sweep`
- **Commit 4** (after tasks 12-16): `feat(simulation): publish accounting snapshots and read surfaces`
- **Commit 5** (after tasks 17-23): `test,docs: certify accounting experiment and required gates`

Commit checkpoints are suggestions only. Do not commit during `$aif-implement`
unless the user explicitly authorizes commits.

## Definition of Done

- V4-23 deepens `organizations`; 14 contexts / 12 flags / 8 owned / 4 unowned;
  no new context, flag slot, `runner-config-v57`, root field, or per-agent runner
  key; no double-entry engine, objective ledger, money, currency, interest, bank,
  audit oracle, credit score, or enforceable book of record is implemented.
- Accounting cognition activates only when `organizations` and the V3-11
  `durable_records` spec are both present (the durable channel keeps its
  existing cultural/provenance prerequisites); every other combination leaves
  V3-11, V4-03, V4-04, V4-08, and V4-22 behavior unchanged.
- Commands and events are unchanged; no field, admission rule, quantity, price,
  or unit is added to `Inscribe`, `Amend`, `CopyRecord`, `AnnotateRecord`,
  `DamageRecord`, `Talk`, `Tell`, `Give`, or any artifact event.
- Accounting-like artifacts are existing durable records carrying `acc_v1`
  relation triples; no new genre, artifact kind, or event exists.
- The owner-scoped ledger stores five record kinds, six directions, assessments,
  revisions, evidence refs, confidence, counts, and notices; it stores no item
  ids, inventories, peer state, world state, money, or objective balances.
- Repeated folding of the same claim/record set leaves counts, confidence,
  assessments, and ledger bytes unchanged.
- `acc_v1` frames are bounded, strict, and carried only inside existing
  `Talk`/`Tell`; malformed or oversize frames are dropped with bounded warnings.
- Accounting content may extend an already-selected `Inscribe`; no command is
  created, replaced, or biased by accounting beliefs.
- Records may be correct, wrong, outdated, fraudulent-looking, or damaged only as
  owner appraisals; no field asserts truth, authenticity, fraud, or an objective
  balance.
- Agents and institutions can use ledgers as evidence only through the pure
  candidate bridge, wired after accounting preparation and before evidence
  evaluation; no automatic evidence write and no evidence schema change.
- Analysis reconstructs records, transfers, contributions, and `acc_v1` claims
  from committed events only and joins detached owner exports without reading
  `WorldState`, runtimes, stores, or API objects.
- Analysis reports counts, integer quantity sums, milli shares, and
  distributions; no balance, total value, solvency, score, ranking, or
  reconciliation authority exists; fewer than four samples is
  `insufficient_samples`.
- Owner-versus-evidence alignment is researcher-only and never reaches
  cognition, prompts, memory, world state, observer semantics, or stop
  selectors.
- Evidence, owner rows, entries, records, claims, revisions, contributions,
  flows, counterparties, conditions, alignments, and snapshot families are
  independently capped; truncation is deterministic and reported as `partial`,
  never complete.
- Four metric families append to exactly 220; prior ids/order/versions/value keys
  are unchanged; every active suite and docs pin is swept from 216 to 220 and no
  test expects `organizations` to be unowned.
- `accounting-ledgers-snapshot-v1` round-trips canonically with no wall-clock
  field; `accounting-ledgers-store-v1` is atomic, quota-bounded, idempotent, and
  corruption-safe; cursors bind the `window_index` filter.
- Seven GET-only dual-gated routes fail closed with
  `accounting_ledgers_disabled`, default limit 100, max 500, `window_index` <=
  511; the Research UI panel is read-only; no new Godot overlay exists.
- Publication is programmatic and post-completion; no CLI producer or runner
  flag is added.
- Off-gate `accounting_ledgers@1` is registered and absent from the V1 gate.
- Commands stay 43; observer semantics stay 73; replay-v27/codec `v25` stay the
  maximum; Alembic stays `0017`; `/v1` and `observer-protocol-v1` stay.
- The in-process E2E uses real `WorldEngine` admission, real `Inscribe`/`Tell`
  commands, real events, a real snapshot, a real store, and a real API read.
- Determinism across hash seeds, cap-bound properties, and leakage guards pass.
- Docs cover the page, README, ARCHITECTURE, DESCRIPTION,
  `docs/architecture.md`, `docs/configuration.md`, `docs/analysis-metrics.md`,
  `docs/research-api.md`, `docs/v4-architecture.md`, `docs/cognition-runtime.md`,
  and cross-links in `docs/organizations.md`, `docs/evidence-testimony.md`, and
  `docs/credit-relationships.md`, with positive and negative parity checks;
  required gates are certified or explicitly `unexecuted`; the roadmap is
  updated with the V4-23 registration and the V4-17 through V4-22
  re-confirmation.

## Verification Receipt

Filled by Task 23. No lane is green until its command and result are recorded
here.

| Lane | Command | Result | Prerequisite / note |
| --- | --- | --- | --- |
| Unit + architecture correctness | `uv run pytest tests/unit tests/architecture -q` | 11442 passed in 684.87s |  |
| Focused accounting suites | `uv run pytest tests/unit/test_accounting_ledgers_*.py tests/architecture/test_accounting_ledgers_*.py -q` | 222 passed in 13.06s |  |
| Python coverage (focused) | `uv run pytest tests/unit/test_accounting_ledgers_*.py tests/architecture/test_accounting_ledgers_*.py -q --cov=src --cov-report=term` | 222 passed; coverage command succeeded | focused lane; overall 21% is expected for a focused subset |
| Python coverage (full lane) | `uv run pytest tests/unit tests/architecture -q --cov=src --cov-report=term` | unexecuted | dedicated budget; focused coverage lane recorded instead |
| Static: Ruff | `uv run ruff check src tests` | All checks passed |  |
| Static: mypy | `uv run mypy src tests` | Success: no issues found in 2655 source files |  |
| Static: import boundaries | `uv run lint-imports` | 25 kept, 0 broken |  |
| Integration (non-scale) | `uv run pytest tests/integration -m "not scale" -q` | 56 passed, 60 skipped, 5 deselected |  |
| Accounting store/API integration | `uv run pytest tests/integration/test_accounting_ledgers_store_api.py -q -m integration` | 1 passed |  |
| Compose config | `docker compose config` | passed |  |
| Research UI tests | `cd clients/research-ui && ./node_modules/.bin/vitest run` | 66 files, 312 tests passed |  |
| Research UI types | `cd clients/research-ui && ./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json` | 0 errors, 0 warnings |  |
| Godot regression | `GODOT_BIN=~/.cache/palimpsest-godot/Godot_v4.7.2-stable_linux.x86_64 "$GODOT_BIN" --headless --path clients/godot-observer --script res://tests/run_protocol.gd` | godot_protocol_tests failed=0 |  |
| Compose/browser acceptance | attested image + headed browser harness | unexecuted | no attested image; source_revision_missing |
| Benchmark regression (non-scale) | `PALIMPSEST_V4_SCALE_IDS=100000 uv run pytest tests/benchmarks -m "not scale" -q` | 1 passed, 20 deselected |  |

The roadmap is updated by `$aif-roadmap`: V4-23 is registered in M8 and V4-17
through V4-22 are re-confirmed; eight V4 flags remain owned and four remain
unowned.

`git status` must confirm no `.ai-factory/ROADMAP.md` edit from this plan, no
`alembic/versions/0018*` file, no `clients/godot-observer/` source change, and no
`/v2` route. The Research UI panel, seven GET routes, snapshot/store, four metric
families, docs, and off-gate experiment are the only other V4-23 surfaces
changed.
