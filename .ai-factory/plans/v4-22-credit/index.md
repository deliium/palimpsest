<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: Credit Relationships

Mode: ultra
Branch: main
Created: 2026-11-11
Plan identifier: `v4-22-credit`

## Original Request

v4-22 credit

Naming requirement:

Use `v4-22-credit`.

Extend promises/debts into credit relationships.

Support agreements such as:

receive resources now  
repay later

Potential terms:

principal-like amount  
repayment amount  
conditions  
deadline  
collateral-like commitment where emergent

Do not implement banks.

Allow:

repayment  
default  
renegotiation  
forgiveness  
dispute

Credit decisions should depend on subjective trust and expectations.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose/browser, Godot regression (existing suites only), Research UI,
  benchmark regression, and static gates, with coverage enabled for Python
  lanes.
- Logging: verbose, metadata-only. Bounded DEBUG ledger/claim/performance/
  distribution counts and selected status tokens, INFO activation/publication/
  build milestones, WARN truncation/partial coverage/malformed frames/unresolved
  anchors/overdue rows, ERROR safe codes. `PALIMPSEST_LOG_LEVEL` controls
  operational verbosity. Never log owner tokens, counterparty sets, anchors,
  item kinds, quantities, trust values, willingness/confidence values, ratios,
  record anchors, cursor keys, credentials, tokens, DSNs, memories, embeddings,
  or payload surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 21.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning or implementation unless the user explicitly asks.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-22-credit`; the ultra bundle directory is
  `.ai-factory/plans/v4-22-credit/`, phase files use `phase-NN-<slug>.md`, and
  `index.md` is the canonical entrypoint. Python and artifact tokens use
  `credit_relationships` / `credit-relationships-*` because identifiers cannot
  contain spaces or slashes; the feature name is "credit relationships".
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only in this invocation. No implementation, commit, roadmap
  edit, or branch creation occurs while planning.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-22 deepens the already-owned `markets_credit` V4 context and the
V3-17 promise/debt seam into owner-scoped credit relationships, adding no new V4
context, flag slot, runner schema, command, event, money, bank, or enforceable
debt. `$aif-roadmap` registered V4-22 in M8 on 2026-11-12, re-confirmed V4-17
through V4-21, and recorded that eight V4 flags remain owned and four remain
unowned. This plan does not close M8 or edit other milestones.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Versioned Extension Contract", V3-17, V3-18, V4-01 through
V4-21 seams) and `.ai-factory/RULES.md` constrain every edit;
`.ai-factory/DESCRIPTION.md` and `.ai-factory/ROADMAP.md` describe current state;
the source paths below define the concrete contracts. No requirement source is
edited to create this plan; the landing in Task 21 records the implemented seam
in the descriptive project documents, while the roadmap remains owned by
`$aif-roadmap`.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-22 deepens the already-owned `markets_credit` context; contexts stay 14, flags 12, owned 8, unowned 4; no new context, flag slot, `runner-config-v57`, root field, or per-agent runner key | Original Request "Do not implement banks"; `src/simulation/v4_architecture.py:212-228`; `src/simulation/runner_models.py:152,1128-1179` | Task 1/3/20/23 |
| `markets_credit` stays `OWNER_SCOPED` with owners `("agents.cognition","simulation")`, `uses_existing_events=True`, prerequisites `SUPPLY_CHAINS`/`ORGANIZATIONS`, and non-goals "no central bank or enforced debt"; prerequisites are planning order, never a runtime gate | Original Request; `v4_architecture.py:212-228` | Task 1/20/23 |
| Credit cognition activates only when `markets_credit` is enabled **and** the V3-17 `structured_commitments` spec is present; otherwise no ledger, no `crd_v1`, and V3-17/V4-20/V4-21 behavior is unchanged | Original Request "Extend promises/debts into credit relationships"; `src/simulation/runner_models.py:5117-5193`; `src/simulation/runner.py:875-917,1473-1490` | Task 3/17/18 |
| V3-17 `CommitmentInterpretation` rows with kind `debt`/`future_exchange` seed proposed/open credit candidates and remain supporting evidence; `crd_v1` acts refine terms, status, and repayment | Original Request; `src/world/structured_commitments.py:16-39`; `src/agents/cognition/structured_commitments.py:89-234` | Task 2/6/17 |
| V3-18 `subjective_valuation` is composed by the optional V4-21 price seam; the direct willingness inputs are owner trust, repayment history, and V4-21 price confidence. Valuation and price rows are never debt, money, a credit score, or an objective price | Original Request "Credit decisions should depend on subjective trust and expectations"; `src/agents/cognition/subjective_value.py:51-128`; `src/agents/cognition/emergent_prices.py:565-695` | Task 2/8/19 |
| Subjective trust comes from the owner's directed `RelationshipDimension.TRUST`, mapped from signed `[-1,1]` to integer `[0,1000]`; missing profiles use `500` trust with `200` confidence | Original Request; `src/social/relationships.py:56-67`; `src/agents/cognition/communication.py:88-109` | Task 2/3/19 |
| Owner representation is one bounded `CreditRelationshipLedger`: direction, item-kind principal/repayment terms, conditions, deadline, collateral-like claim, revisions, acts, status, trust, willingness, confidence, counts, notices; no item ids, inventories, peer state, money, or world state | Original Request "principal-like amount ... collateral-like commitment"; `src/agents/cognition/emergent_prices.py:282-695` | Task 1/2/20 |
| Credit acts (`propose`, `accept`, `decline`, `repay`, `default`, `renegotiate`, `forgive`, `dispute`, `withdraw`) travel as bounded `crd_v1` frames inside existing `Talk`/`Tell`; no new speech command, command field, or V3 convention situation is added | Original Request "repayment/default/renegotiation/forgiveness/dispute"; `src/agents/cognition/emergent_prices_communication.py:52-351`; `src/agents/cognition/deliberation.py:1405-1417` | Task 4/20/23 |
| The only behavioural effect is one optional `crd_v1` relation attached to an already-selected `Talk`/`Tell`; no command is created or replaced, and exchange/credit admission never reads credit beliefs | Original Request; `src/world/_rules.py`; `.ai-factory/ARCHITECTURE.md` "Anti-Patterns" | Task 4/18/20 |
| Physical principal and repayment remain ordinary `Give`/`ExchangeCompleted` commands; a credit row never moves an item, collects a debt, or grants permission | Original Request "receive resources now / repay later"; `src/world/actions.py` (`Give`, `NegotiateExchange`); `src/world/events.py:639-656,2515-2564` | Task 2/6/18/20 |
| Analysis evidence is committed `Talked`/`Told` `crd_v1` relations plus committed `Given` transfers and detached owner export rows; no `WorldState`, runtime, store, API object, or peer ledger is read | Original Request; `src/world/events.py:639-656,708-764`; `src/analysis/emergent_prices_events.py:155-331` | Task 5/6/9/19 |
| Performance outcomes and repayment-ratio distributions are descriptive; `proposed` and `agreed` samples stay separate; a distribution with fewer than four samples is `insufficient_samples`, never a claimed ratio | Original Request; `src/analysis/emergent_prices_detection.py:77-222` | Task 7/8/10/19 |
| Researcher-only alignment compares owner repayment beliefs with committed claim/transfer evidence (`consistent`/`unresolved`/`inconsistent`/`not_applicable`) and never reaches cognition, prompts, memory, world state, observer semantics, or stop selectors | Original Request; `src/analysis/emergent_prices_expectations.py:50-395` | Task 8/9/19 |
| Four metric families append 212 -> **216**; the first 212 ids, order, versions, and value keys stay unchanged, and every active suite/docs pin is swept in the same change | `src/analysis/specifications.py:53,286-289,8921-8965,9269-9310,9814-9818`; `src/analysis/metric_service.py:397,2586-2614` | Task 10/11/20/22 |
| Snapshot is a sibling `credit-relationships-snapshot-v1` with store `credit-relationships-store-v1`, two dual-gated settings, window-bound cursors, and seven GET-only routes failing closed with `credit_relationships_disabled`; it is not a runner/result/replay/SQL schema | `src/simulation/emergent_prices_models.py`; `src/simulation/emergent_prices_codec.py`; `src/simulation/emergent_prices_ports.py`; `src/persistence/emergent_prices_filesystem.py`; `src/infrastructure/settings.py:256-258,463-470`; `src/api/app.py:568-595` | Task 12/13/14/15 |
| No Godot overlay is added: credit is an owner/analytical structure; the presentation client is unchanged and its existing suite is the regression gate | Original Request; `.ai-factory/ARCHITECTURE.md` V3-40 through V3-42 seam | Task 16/20/23 |
| Publication is programmatic and post-completion; no CLI producer and no runner flag is added | `src/experiments/emergent_prices_publication.py:100-362`; V4-20/V4-21 have no CLI producer | Task 14/23 |
| Off-gate experiment `credit_relationships@1` composes `markets_credit`, `structured_commitments`, and `subjective_valuation` and never enters the V1 A-E gate | `src/experiments/catalog.py:2800-2835,5691-5707`; `src/experiments/emergent_prices_scenario.py:38-145` | Task 17/23 |
| Documentation covers `docs/credit-relationships.md`, README, ARCHITECTURE, DESCRIPTION, `docs/architecture.md`, `docs/configuration.md`, `docs/analysis-metrics.md`, `docs/research-api.md`, and cross-links in `docs/emergent-prices.md` and `docs/market-like-institutions.md`; roadmap registration stays with `$aif-roadmap` | ARCHITECTURE requirement 7; `.ai-factory/ROADMAP.md`; `docs/emergent-prices.md` | Task 21/22/23 `git status` |

### Supported combinations and coverage transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| `markets_credit` off, commitments on | V3-17 only | No credit mode, ledger, `crd_v1`, metric input, or snapshot field; legacy bytes unchanged | Task 3/17 |
| `markets_credit` on, commitments off | V4-20/V4-21 only | Credit mode disabled; empty ledger; existing experiments unchanged | Task 3/17 |
| `markets_credit` on, commitments on | Deterministic credit mode and locked policy | `cred-` ledger allocated; no write pair, schema, or v57 | Task 2/3/20 |
| Owner proposes terms with a valid anchor | `proposed` | Row stores direction, terms, due, condition, collateral claim, trust, willingness | Task 2/4 |
| Receiver accepts | `accepted`/`open` | Owner-local status only; no command, transfer, or enforcement | Task 2/4 |
| Receiver declines or proposer withdraws | `declined`/`withdrawn` | Row retained; no item moves | Task 2 |
| Partial repayment claim | `partially_repaid` | Paid quantity increases, capped at repayment quantity | Task 2/7 |
| Full repayment claim | `repaid` | Paid quantity equals repayment quantity | Task 2/7 |
| Default claim before deadline | Rejected unless self-declared by debtor | `credit_claim_rejected`; no status change | Task 2 |
| Default claim at/after deadline | `defaulted` | Owner belief only; no collection, penalty, or command | Task 2/4 |
| Renegotiation claim | Terms revised, revision appended | Prior terms retained; status remains `proposed` or `open`; no enforcement | Task 2/4 |
| Forgiveness claim | `forgiven` | Obligation retained as history; no item moves | Task 2/4 |
| Dispute claim | `disputed` | Credit dispute stays owner-local; it does not open a legal dispute | Task 2/4 |
| Open row beyond deadline plus 8 ticks | `expired` | `credit_overdue` notice; a later claim may move it | Task 2 |
| Same claim folded twice | Existing row unchanged | Counts, confidence, willingness, and ledger bytes unchanged | Task 2 |
| No owner ledgers exported | Objective claim/performance evidence | Owner/alignment coverage `missing`; no fabricated `credo-` row | Task 8/14 |
| Owner row with no matching performance | Owner row retained | Alignment `not_applicable`; analytical rows unchanged | Task 8 |
| Fewer than four agreed samples | `insufficient_samples` | Distribution row with counts and no invented quantile | Task 7/10 |
| Four or more agreed samples | `available` | Quantiles, IQR, dispersion, sample count, five bin shares | Task 7/10 |
| Identical proposed and agreed ratios | Two distributions retained | Separate `proposed`/`agreed` sample sources; never pooled | Task 7 |
| Repayment ratio above 64,000 milli | `out_of_range` | No ratio sample; excluded and counted | Task 7 |
| `crd_v1` frame from an unrelated predicate | Ignored | No claim folded; no error | Task 4/6 |
| Malformed/oversize `crd_v1` frame | Dropped | One bounded warning count; simulation continues | Task 4/19 |
| Row or cap exceeded | Deterministic prefix | `coverage="partial"` plus one bounded truncation notice | Task 2/6/7/8/12/19 |
| Snapshot dual gate unset | No reader | 503 `credit_relationships_disabled` on all seven routes | Task 13/15 |
| Corrupt snapshot payload | No data | 500 `credit_relationships_store_corrupt` | Task 13/15 |
| Paged route with `window_index` | Filter-bound cursor | Only matching rows; cursor for another window rejected 400 | Task 12/15 |
| Publication disabled by the caller | No artifact | Nothing written; scientific status unchanged | Task 14 |
| Another unowned V4 flag | Unchanged | `capability_unimplemented`; fixtures repointed to `science` | Task 3/11/20 |
| Env-gated lane missing prerequisite | No green certification | `unexecuted` plus prerequisite | Task 23 |

No blocking open questions: every material decision is fixed below.

## Architecture and Decisions

1. **Deepen, do not claim.** V4-22 deepens the owned `markets_credit` context on
   the accepted `runner-config-v56` seam. It adds no V4 context, flag slot,
   `runner-config-v57`, root field, per-agent runner key, command, event,
   observer semantic type, write pair, `/v2` route, or migration. Counts remain
   14 contexts / 12 flags / 8 owned / 4 unowned.
2. **Extend V3-17, do not replace it.** `StructuredCommitmentLedger` remains the
   owner's reading of public promise/debt speech. Credit interprets `debt` and
   `future_exchange` rows as proposed/open credit candidates; it never rewrites
   commitments or treats one as a contract.
3. **Credit is a belief, not a contract.** A credit row records what one owner
   believes about receive-now/repay-later terms. No row is shared, objective, or
   enforceable, and no owner reads another owner's ledger.
4. **One bounded owner ledger.** `CreditRelationshipLedger` stores rows keyed by
   a symmetric `crd-` anchor with direction, item-kind terms, due tick,
   condition, collateral-like claim, revisions, claims, status, trust,
   willingness, confidence, counts, and notices. Row ids are owner-local
   `cred-`; no item id, inventory, peer state, or world state is stored.
5. **Terms are item quantities, not money.** Principal and repayment are
   `ItemKind` plus integer quantities; the repayment ratio in integer milli is
   descriptive. No money, currency, legal tender, interest, APR, principal
   balance, or credit limit exists.
6. **Willingness is fixed.** `willingness = (trust*500 + history*300 +
   price_confidence*200) // 1000`; missing trust is 500, missing history is 500,
   missing price confidence is 500. Confidence is the exact integer formula in
   Task 2 and never becomes a score or ranking.
7. **Trust is read-only.** Credit reads the directed relationship trust
   dimension and stores a bounded projection. It never writes relationships,
   reputation, norms, or memory.
8. **Price expectations are optional.** When V4-21 price mode is active, the
   matching price row's confidence contributes to willingness. When it is
   absent, credit still works with trust and history. V3-18 valuation is
   composed only to enable that optional price seam; it adds no direct
   willingness term.
9. **Speech is the only behavioural effect.** `crd_v1` frames carry acts and
   terms inside existing `Talk`/`Tell`. One optional relation may be attached to
   an already-selected utterance; no command is created, replaced, or biased.
10. **Acts are declarations.** Repayment, default, renegotiation, forgiveness,
    and dispute are owner claims. They never move an item, collect a debt,
    impose a penalty, open a legal dispute, or grant permission. Physical
    principal/repayment remains an ordinary `Give`/`ExchangeCompleted`.
11. **Evidence is committed or detached.** Analysis reconstructs claims from
    committed speech and transfers from committed `Given` events, then joins
    token-only owner exports. It never reads live cognition or world state.
12. **Distributions, not one ratio.** Every group reports sample count, five
    quantiles, IQR, dispersion, and five bin shares in integer milli, or
    `insufficient_samples`. `proposed` and `agreed` samples are never pooled.
13. **Alignment is researcher-only.** Owner-versus-evidence alignment is
    `consistent`/`unresolved`/`inconsistent`/`not_applicable` and never reaches
    cognition, prompts, memory, world state, observer semantics, or stop
    selectors.
14. **Bounded everything.** Claims, revisions, rows, counterparties, events,
    owner rows, performances, distributions, counterparties, alignments, and
    snapshot families have independent caps with deterministic prefixes,
    `coverage="partial"`, and one bounded notice per family.
15. **Snapshot and read-only surfaces.** `credit-relationships-snapshot-v1` is
    a canonical sibling with digest and publication id and no wall-clock field;
    `credit-relationships-store-v1` is atomic, quota-bounded, idempotent, and
    corruption-safe; cursors bind `window_index`; seven GET-only dual-gated
    routes serve it. Publication is programmatic and post-completion. The
    Research UI adds one read-only panel; Godot gets no overlay. Four metrics
    append 212 -> 216, every active pin is swept, and `credit_relationships@1`
    stays off the V1 gate. `$aif-roadmap` registers V4-22 and re-confirms
    V4-17 through V4-21.

### Locked credit summary

| Dimension | Locked behavior |
| --- | --- |
| Policy | `credit-relationships.v1` (cognition and analysis share the version token) |
| V4 ownership | `markets_credit` owned; 14 contexts / 12 flags / 8 owned / 4 unowned |
| Runner schema | `runner-config-v56` only; no v57, no new root/per-agent runner key |
| Activation | `markets_credit` **and** V3-17 `structured_commitments`; otherwise disabled |
| Promise input | V3-17 `CommitmentInterpretation` with kind `debt`/`future_exchange`; seeds proposed/open candidates and remains evidence |
| Valuation input | V3-18 `subjective_valuation` enables the optional V4-21 price seam; no direct willingness term |
| Price input | V4-21 `PriceExpectationRow` confidence for the matching kind pair; optional |
| Trust input | Directed `RelationshipDimension.TRUST` mapped to integer `[0,1000]` |
| Cognition ledger | `cred-` owner-local rows; 32 rows, 16 claims/row, 8 revisions/row, 8 counterparties |
| Directions | `owner_debtor`, `owner_creditor` |
| Acts | `propose`, `accept`, `decline`, `repay`, `default`, `renegotiate`, `forgive`, `dispute`, `withdraw` |
| Statuses | `proposed`, `accepted`, `open`, `partially_repaid`, `repaid`, `defaulted`, `forgiven`, `disputed`, `withdrawn`, `declined`, `expired` |
| Conditions | `on_receipt`, `by_deadline`, `after_return`, `shared_witness`, `unspecified` |
| Collateral claims | `none`, `item_pledge`, `service_pledge`, `custody_pledge`, `reputation_pledge`, `unspecified` |
| Expectation levels | `none`, `weak`, `expected`, `strong`; strong requires confidence >= 750 milli and a prior repayment |
| Willingness | Integer 0-1000: trust 500 + history 300 + price confidence 200, floored by 1000 |
| Speech frame | `crd_v1`, 16 parts, 320 characters, one relation per `Talk`/`Tell` |
| Local behavior | Optional one-relation attachment only; no command replaced |
| Analysis sources | `proposed`, `agreed`; never pooled |
| Window | 32 ticks; index `tick // 32`; at most 512 windows |
| Distribution | sample count, min/p25/median/p75/max, IQR, dispersion, five bin shares in milli; min 4 samples per source |
| Performance outcomes | `active`, `partially_repaid`, `repaid`, `defaulted`, `forgiven`, `disputed`, `expired`, `insufficient_evidence` |
| Alignment | consistent <= 250 milli gap, inconsistent >= 750, else unresolved |
| Caps | Claims 200k/200k events; owner 4,096; claims 4,096; relationships 8,192; performances 8,192; distributions 8,192; counterparties 1,024; alignments 4,096 |
| Snapshot | `credit-relationships-snapshot-v1`; store `credit-relationships-store-v1`; 16 publications / 8 MiB; no wall-clock field |
| Routes | 7 GET-only under `SUBJECTIVE_DEBUG`; default limit 100; max 500; `credit_relationships_disabled` when unset |
| Catalog | 212 -> 216 families; first 212 unchanged; active suite and docs pins swept to 216 |
| Clients | Research UI panel; no new Godot overlay |
| Experiment | `credit_relationships@1`, off the V1 gate |
| Pins | 43 commands; 73 observer semantics; replay-v27/codec `v25`; Alembic `0017`; `/v1`; `observer-protocol-v1` |

## Phase Index

1. [Phase 1: Contract and Owner-Scoped Credit Cognition](phase-01-contract-and-owner-credit-cognition.md) — Tasks 1-4
2. [Phase 2: Analysis Evidence and Detection](phase-02-analysis-evidence-and-detection.md) — Tasks 5-7
3. [Phase 3: Owner Joins, Metrics, and Pins](phase-03-owner-joins-metrics-pins.md) — Tasks 8-11
4. [Phase 4: Collection and Publication](phase-04-collection-and-publication.md) — Tasks 12-14
5. [Phase 5: Read-Only Surfaces](phase-05-read-only-surfaces.md) — Tasks 15-16
6. [Phase 6: Experiment and End-to-End](phase-06-experiment-and-e2e.md) — Tasks 17-19
7. [Phase 7: Invariants and Pins](phase-07-invariants-and-pins.md) — Task 20
8. [Phase 8: Documentation and Verification](phase-08-docs-and-verification.md) — Tasks 21-23

## Cross-Phase Dependencies

- Task 1 defines the contract consumed by every later task.
- Task 2 depends on Task 1 (policy, enums, ids, terms).
- Task 3 depends on Tasks 1-2 (ledger and carry contract).
- Task 4 depends on Tasks 1-3 (frames, activation, ledger).
- Task 6 depends on Task 5 (contract, policy, rows, window helpers).
- Task 7 depends on Task 6 (claim and transfer evidence).
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

### Phase 1: Contract and Owner-Scoped Credit Cognition
- [x] Task 1: Lock the credit relationship contract, policy, and identifiers ([details](phase-01-contract-and-owner-credit-cognition.md#task-1-lock-the-credit-relationship-contract-policy-and-identifiers))
- [x] Task 2: Add the owner-scoped credit relationship ledger ([details](phase-01-contract-and-owner-credit-cognition.md#task-2-add-the-owner-scoped-credit-relationship-ledger)) (depends on 1)
- [x] Task 3: Activate and carry credit relationships under markets_credit ([details](phase-01-contract-and-owner-credit-cognition.md#task-3-activate-and-carry-credit-relationships-under-markets_credit)) (depends on 1, 2)
- [x] Task 4: Add crd_v1 speech frames with bounded trust-sensitive attachment ([details](phase-01-contract-and-owner-credit-cognition.md#task-4-add-crd_v1-speech-frames-with-bounded-trust-sensitive-attachment)) (depends on 1-3)

### Phase 2: Analysis Evidence and Detection
- [x] Task 5: Lock the credit analysis contract, policy, and caps ([details](phase-02-analysis-evidence-and-detection.md#task-5-lock-the-credit-analysis-contract-policy-and-caps))
- [x] Task 6: Extract committed credit claims and transfer evidence ([details](phase-02-analysis-evidence-and-detection.md#task-6-extract-committed-credit-claims-and-transfer-evidence)) (depends on 5)
- [x] Task 7: Detect credit performances and repayment distributions ([details](phase-02-analysis-evidence-and-detection.md#task-7-detect-credit-performances-and-repayment-distributions)) (depends on 6)

### Phase 3: Owner Joins, Metrics, and Pins
- [x] Task 8: Join detached owner rows and researcher-only alignment ([details](phase-03-owner-joins-metrics-pins.md#task-8-join-detached-owner-rows-and-researcher-only-alignment)) (depends on 5-7)
- [x] Task 9: Compose the bounded CreditRelationshipsAnalysis harvest ([details](phase-03-owner-joins-metrics-pins.md#task-9-compose-the-bounded-creditrelationshipsanalysis-harvest)) (depends on 6-8)
- [x] Task 10: Append four credit metric families to 216 ([details](phase-03-owner-joins-metrics-pins.md#task-10-append-four-credit-metric-families-to-216)) (depends on 9)
- [x] Task 11: Sweep suite-wide ownership and catalog pins ([details](phase-03-owner-joins-metrics-pins.md#task-11-sweep-suite-wide-ownership-and-catalog-pins)) (depends on 10)

### Phase 4: Collection and Publication
- [x] Task 12: Add credit snapshot models, codec, ports, and paging ([details](phase-04-collection-and-publication.md#task-12-add-credit-snapshot-models-codec-ports-and-paging)) (depends on 9, 10)
- [x] Task 13: Add the atomic filesystem store and dual-gated settings ([details](phase-04-collection-and-publication.md#task-13-add-the-atomic-filesystem-store-and-dual-gated-settings)) (depends on 12)
- [x] Task 14: Compose and publish completed-run credit snapshots ([details](phase-04-collection-and-publication.md#task-14-compose-and-publish-completed-run-credit-snapshots)) (depends on 9, 10, 12, 13)

### Phase 5: Read-Only Surfaces
- [x] Task 15: Add seven GET-only dual-gated credit routes ([details](phase-05-read-only-surfaces.md#task-15-add-seven-get-only-dual-gated-credit-routes)) (depends on 12-14)
- [x] Task 16: Add the Research UI credit client and panel ([details](phase-05-read-only-surfaces.md#task-16-add-the-research-ui-credit-client-and-panel)) (depends on 15)

### Phase 6: Experiment and End-to-End
- [x] Task 17: Register off-gate credit_relationships@1 ([details](phase-06-experiment-and-e2e.md#task-17-register-off-gate-credit_relationships1)) (depends on 3-4, 10, 14)
- [x] Task 18: Add in-process credit end-to-end coverage ([details](phase-06-experiment-and-e2e.md#task-18-add-in-process-credit-end-to-end-coverage)) (depends on 14-17)
- [x] Task 19: Add determinism, property bounds, and leakage coverage ([details](phase-06-experiment-and-e2e.md#task-19-add-determinism-property-bounds-and-leakage-coverage)) (depends on 18)

### Phase 7: Invariants and Pins
- [x] Task 20: Enforce architecture invariants and pin sweeps ([details](phase-07-invariants-and-pins.md#task-20-enforce-architecture-invariants-and-pin-sweeps)) (depends on 1-19)

### Phase 8: Documentation and Verification
- [x] Task 21: Documentation via aif-docs ([details](phase-08-docs-and-verification.md#task-21-documentation-via-aif-docs)) (depends on 20)
- [x] Task 22: Add documentation pin and negative parity checks ([details](phase-08-docs-and-verification.md#task-22-add-documentation-pin-and-negative-parity-checks)) (depends on 21)
- [x] Task 23: Required-gate verification certification ([details](phase-08-docs-and-verification.md#task-23-required-gate-verification-certification)) (depends on 18-22)

## Commit Plan

- **Commit 1** (after tasks 1-4): `feat(cognition): add owner-scoped credit relationships`
- **Commit 2** (after tasks 5-7): `feat(analysis): reconstruct credit claims and repayment distributions`
- **Commit 3** (after tasks 8-11): `feat(analysis): add credit metrics and catalog sweep`
- **Commit 4** (after tasks 12-16): `feat(simulation): publish credit snapshots and read surfaces`
- **Commit 5** (after tasks 17-23): `test,docs: certify credit experiment and required gates`

Commit checkpoints are suggestions only. Do not commit during `$aif-implement`
unless the user explicitly authorizes commits.

## Definition of Done

- V4-22 deepens `markets_credit`; 14 contexts / 12 flags / 8 owned / 4 unowned;
  no new context, flag slot, `runner-config-v57`, root field, or per-agent runner
  key; no bank, money, currency, deposit, reserve, interest, enforceable debt,
  collection, or credit score is implemented.
- Credit cognition activates only when `markets_credit` and the V3-17
  `structured_commitments` spec are both present; every other combination leaves
  V3-17, V4-20, and V4-21 behavior unchanged.
- Commands and events are unchanged; no field, admission rule, quantity, price,
  or unit is added to `Give`, `NegotiateExchange`, `ExchangeProposed`,
  `ExchangeWithdrawn`, `ExchangeCompleted`, or `DeclareCommitment`.
- The owner-scoped ledger stores direction, item-kind principal/repayment terms,
  conditions, deadline, collateral-like claim, revisions, acts, status, trust,
  willingness, confidence, counts, and notices; it stores no item ids,
  inventories, peer state, world state, money, or enforceable debt.
- Repeated folding of the same claim set leaves counts, confidence, willingness,
  and ledger bytes unchanged.
- `crd_v1` frames are bounded, strict, and carried only inside existing
  `Talk`/`Tell`; malformed or oversize frames are dropped with bounded warnings.
- No command is created or replaced; credit beliefs never alter exchange
  admission, acceptance, counteroffers, `Give`, `Move`, `Wait`, or world state.
- Physical principal and repayment remain ordinary `Give`/`ExchangeCompleted`
  commands; a credit row never moves an item or collects a debt.
- Analysis reconstructs claims and transfers from committed events only and
  joins detached owner exports without reading `WorldState`, runtimes, stores,
  or API objects.
- Proposed and agreed samples stay separate; fewer than four samples is
  `insufficient_samples`; available distributions report counts, five
  quantiles, IQR, dispersion, and five bin shares in integer milli.
- Owner-versus-evidence alignment is researcher-only and never reaches
  cognition, prompts, memory, world state, observer semantics, or stop
  selectors.
- Evidence, owner rows, claims, revisions, performances, distributions,
  counterparties, alignments, and snapshot families are independently capped;
  truncation is deterministic and reported as `partial`, never complete.
- Four metric families append to exactly 216; prior ids/order/versions/value
  keys are unchanged; every active suite and docs pin is swept from 212 to 216
  and no test expects `markets_credit` to be unowned.
- `credit-relationships-snapshot-v1` round-trips canonically with no wall-clock
  field; `credit-relationships-store-v1` is atomic, quota-bounded, idempotent,
  and corruption-safe; cursors bind the `window_index` filter.
- Seven GET-only dual-gated routes fail closed with
  `credit_relationships_disabled`, default limit 100, max 500, `window_index` <=
  511; the Research UI panel is read-only; no new Godot overlay exists.
- Publication is programmatic and post-completion; no CLI producer or runner
  flag is added.
- Off-gate `credit_relationships@1` is registered and absent from the V1 gate.
- Commands stay 43; observer semantics stay 73; replay-v27/codec `v25` stay the
  maximum; Alembic stays `0017`; `/v1` and `observer-protocol-v1` stay.
- The in-process E2E uses real `WorldEngine` admission, real commands, real
  events, a real snapshot, a real store, and a real API read.
- Determinism across hash seeds, cap-bound properties, and leakage guards pass.
- Docs cover the page, README, ARCHITECTURE, DESCRIPTION,
  `docs/architecture.md`, `docs/configuration.md`, `docs/analysis-metrics.md`,
  `docs/research-api.md`, and cross-links in `docs/emergent-prices.md` and
  `docs/market-like-institutions.md`, with positive and negative parity checks;
  required gates are certified or explicitly `unexecuted`; the roadmap is
  updated with the V4-22 registration and the V4-17 through V4-21 re-confirmation.

## Verification Receipt

Filled by Task 23. No lane is green until its command and result are recorded
here.

| Lane | Command | Result | Prerequisite / note |
| --- | --- | --- | --- |
| Unit + architecture correctness | `uv run pytest tests/unit tests/architecture -q` | 11220 passed in 710.51s | Re-verified 2026-11-12 after Tasks 1-20. |
| Focused credit suites | `uv run pytest tests/unit/test_credit_relationships_*.py tests/architecture/test_credit_relationships_*.py -q` | 325 passed in 16.61s | Re-verified 2026-11-12; includes contract, ledger, activation, carry, communication, analysis, metrics, catalog, snapshot, store, API, experiment, E2E, determinism, bounds, leakage, invariants, boundaries, and docs parity. |
| Python coverage (focused) | `uv run pytest tests/unit/test_credit_relationships_*.py tests/architecture/test_credit_relationships_*.py -q --cov=src --cov-report=term` | 325 passed in 73.81s | Re-verified 2026-11-12; coverage enabled; whole-tree coverage 24% because the lane is focused. |
| Python coverage (full lane) | `uv run pytest tests/unit tests/architecture -q --cov=src --cov-report=term` | unexecuted | Timed out after 40 minutes at roughly 2% progress; no result was claimed. Focused coverage lane above passed with coverage enabled. Prerequisite: a longer dedicated budget or a reduced whole-tree instrumentation scope. |
| Static: Ruff | `uv run ruff check src tests` | pass | No findings. |
| Static: mypy | `uv run mypy src tests` | pass (2598 files) | No issues. |
| Static: import boundaries | `uv run lint-imports` | 25 kept, 0 broken | Contracts kept. |
| Integration (non-scale) | `uv run pytest tests/integration -m "not scale" -q` | 55 passed, 60 skipped, 5 deselected in 9.62s | Re-verified 2026-11-12; DB-free lanes; skipped cases require external services. |
| Credit store/API integration | `uv run pytest tests/integration/test_credit_relationships_store_api.py -q -m integration` | 1 passed in 3.24s | Re-verified 2026-11-12; real filesystem publish/read, idempotent republish, corrupt-store 500. |
| Compose config | `docker compose config` | pass | Configuration renders. |
| Research UI tests | `cd clients/research-ui && ./node_modules/.bin/vitest run` | 306 passed (64 files) | Re-verified 2026-11-12; includes the credit panel and disabled-state tests. |
| Research UI types | `cd clients/research-ui && ./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json` | 0 errors, 0 warnings | Re-verified 2026-11-12; complete UI tree. |
| Godot regression | `GODOT_BIN=~/.cache/palimpsest-godot/Godot_v4.7.2-stable_linux.x86_64 "$GODOT_BIN" --headless --path clients/godot-observer --script res://tests/run_protocol.gd` | pass: `godot_protocol_tests failed=0` | Re-verified 2026-11-12 with cached Godot 4.7.2; the editor bootstrap emits a pre-existing `infrastructure_overlay.gd`/`world_view.gd` parse warning, but the protocol suite passes and no Godot file changed. |
| Compose/browser acceptance | attested image + headed browser harness | unexecuted | Available `palimpsest-api:compose-*` images report `revision=unknown` and `source-clean=false`, so source identity fails closed with `source_revision_missing`; no attested image or headed harness is assumed. |
| Benchmark regression (non-scale) | `PALIMPSEST_V4_SCALE_IDS=100000 uv run pytest tests/benchmarks -m "not scale" -q` | 1 passed, 20 deselected in 3.47s | Re-verified 2026-11-12; the opt-in V4 partition-mapping lane ran with 100,000 IDs. |

The roadmap is updated: V4-22 is registered in M8 and V4-17 through V4-21
are re-confirmed; eight V4 flags remain owned and four remain unowned.

`git status` confirms an `.ai-factory/ROADMAP.md` change limited to the V4-22
registration and V4-17 through V4-21 re-confirmation, no
`alembic/versions/0018*` file, and no `clients/godot-observer/` source change.
The research UI panel, seven GET routes, snapshot/store, four metric families,
docs, and off-gate experiment are the only other V4-22 surfaces changed.
