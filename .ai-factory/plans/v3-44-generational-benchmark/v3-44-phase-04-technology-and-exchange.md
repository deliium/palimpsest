# Phase 4: Technology, succession, commitments and exchange

Plan: [index.md](index.md)
Tasks: 8–9
Depends on: Tasks 1–7

## Objective

Implement scenarios 8–15 without a technology tree, inheritance law, automatic debt collection or hard-coded money.

## Current-Code Evidence

| Path | Symbols / cases | Why it matters |
| --- | --- | --- |
| `src/experiments/catalog.py` | `experiment_aq_bounded_experimentation`, `experiment_ar_technique_lifecycle`, `experiment_as_possession_succession`, `experiment_at_structured_commitments`, `experiment_au_subjective_exchange`, `experiment_av_exchange_functions` | Existing physical laws and subjective/economic specs |
| `tests/unit/test_technique_lifecycle_states.py` | locally extinct/globally lost, rediscovery new root | Existing detached classification oracle, not an autonomous discovery proof |
| `tests/unit/test_cultural_technology_continuity.py` | intact records preserve knowledge; unknown archives censor loss | Loss needs complete evidence |
| `tests/unit/test_possession_succession_classify.py` | claims conflict without winner; Take changes holder only | Possession and legitimacy are distinct |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/experiments/civilization_benchmark_technology.py` | create | Cases 08–11 |
| `src/experiments/civilization_benchmark_exchange.py` | create | Cases 12–15 |
| `src/experiments/civilization_benchmark_suite.py` | modify | Builder/selector entries |
| `tests/unit/test_v3_benchmark_technology.py`, `tests/unit/test_v3_benchmark_exchange.py` | create | Real valid-channel histories and classifier controls |

## Task 8: Exercise discovery, diffusion, loss and independent rediscovery

### Intent

Keep objective production/discovery, subjective practical knowledge, archival survival and executable competence distinct. Matching content is not shared ancestry.

### Implementation Steps

1. Compose bounded experimentation, knowledge genealogy, cultural provenance and technique lifecycle using existing `example_experiment_law` and public spec constructors. Provide physical operands/opportunities but no initial technique/skill ledger entries. Controlled `Experiment` commands cite only possessed/co-located valid operands; later knowledge comes from actual result perception.
2. Register four separate case IDs below, sharing the physical law but not a single all-or-nothing scenario. For diffusion, require an entrant recipient and actual teaching/delivery or interpreted record lineage. For loss, sample complete living-holder and cited archive inventories before/after actual holder deaths and record destruction.
3. For rediscovery, preserve a period of verified complete loss, then give an unexposed owner ordinary experimentation opportunities. Do not relink its new root merely because resulting content matches old content. Missing exposure evidence precludes an independence claim.
4. Evaluate existing detached lifecycle/continuity metrics and qualified knowledge/technology lineage captures. Include practical-technique mutation/recombination selectors from existing knowledge-genealogy uptake audits in case 09: retain changed technique identity, all source parents and actual recipient exposure. Test supported deterministic mutated-copy or recombination uptake policies without directly seeding knowledge; mutation may be absent in autonomous runs. Cultural-trait mutation alone is not evidence of technology mutation. Add benchmark evidence selectors in `experiments` that compose existing results; no new global technique registry or metric family.

### Required Interfaces and Contracts

| # / suffix | Mechanism check | Research estimand / control |
| --- | --- | --- |
| 08 `technology-discovery` | Applied experimentation, law-governed physical outcome and owner acquisition with firsthand source; invalid operands rejected | Discovery attempts/outcomes and acquisition; experimentation opportunities absent/present |
| 09 `technology-diffusion` | Separate owner/cohort learns via actual delivery/reading with auditable parent root; competence measured separately | Holder spread and transmission channels; social opportunity absent/present |
| 10 `technology-loss` | Last living holders die; no surviving cited record under complete archive search; lifecycle can classify loss | Living extinction versus global loss; record preservation absent/present |
| 11 `technology-rediscovery` | Prior verified loss then independent firsthand root with no uptake from old root; same content does not merge identities | Rediscovery incidence/latency; later experimentation opportunity absent/present |

Applied experiment coverage is required in controlled fixtures; autonomous discovery/rediscovery is not required. A controlled fixture which cannot reach the specified loss interval is incomplete, not evidence that technology cannot be lost. Keep policy-level positive-loss/rediscovery fixtures explicitly separate from real-world execution evidence.

### Requirement Evidence

Original Request scenarios 8–11 and replay/knowledge-lineage invariants; `tests/unit/test_lineage_subjective_sources.py` — equal content keys remain independent roots; `docs/lineage-explorer.md` — qualified families and coverage.

### Error Handling and Logging

Unknown archive search prevents global-loss assertion (`loss_censored`); a missing lineage segment prevents independence claims. DEBUG counts of holders/records/root edges, INFO statuses, WARN partial evidence, ERROR provenance contradictions. No technique text or record marks in logs.

### Tests and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_v3_benchmark_technology.py tests/unit/test_technique_lifecycle_states.py tests/unit/test_cultural_technology_continuity.py -q`.

Test applied/rejected experimentation, diffusion to a real entrant, supported practical-knowledge mutation/recombination with all source parents, zero post-death actions, archived-only knowledge, uncited record not rescuing a technique, unknown archives censoring loss, rediscovery separate roots and forged parent rejection. Replay checks are completed in Task 15.

### Acceptance Criteria

Cases 08–11 can independently pass mechanism/provenance coverage while reporting detected, absent or unknown research outcomes honestly.

## Task 9: Exercise inheritance claims, delayed commitments, barter and exchange functions

### Intent

Economic patterns must arise through claims, decisions and normal transfers, not automatic law or universal currency.

### Implementation Steps

1. Compose succession, commitments, valuation and resource-exchange-profile specs in separate recipes. Use physical inventories, consumption needs and future opportunities as setup; do not insert legitimacy, valuation or acceptance-memory rows. Initially equivalent agents may form different owner-local assessments.
2. Drive controlled death/custody, claim speech and ordinary `Take` through engine admission. Compare holder events with owner legitimacy assertions; genealogy is context only and never grants a transfer right.
3. For commitments, declare bounded undertakings with explicit due windows; produce a legal fulfillment path through `Give`/supported service and a violation path by omission or incompatible action. Use actual delivered declarations and action outcomes, not only planned milestones. No automatic collections or commitment inheritance on death.
4. For barter, use existing `NegotiateExchange` offer/counteroffer/accept protocol; assert atomic named-item movements or legitimate failure. For candidate medium-of-exchange, permit repeated acceptance/re-exchange of an ordinary item under its declared physical profile; classify exchange-function evidence after the run, not by naming an item money.

### Required Interfaces and Contracts

| # / suffix | Mechanism evidence | Research output / contrast |
| --- | --- | --- |
| 12 `inheritance-practices` | Death opens custody; competing claims and admitted transfers remain separate; owner-local succession beliefs sourced | Descriptive claim/practice patterns and disagreement; succession cognition opportunities off/on |
| 13 `long-term-commitments` | Declaration → due window → applied fulfillment or nonfulfillment; event sources survive promisor/observer turnover | Fulfilled/violated/unresolved fractions by eligible promises; fulfillment opportunities absent/present |
| 14 `subjective-barter` | Negotiation revisions and atomic exchange or rejection; owner-local values need not agree | Agreement rate, counteroffers and subjective value disagreements; valuation cognition off/on |
| 15 `candidate-exchange-medium` | Repeated accepted/re-exchanged item episodes have ordinary custody and valid offers; no special command/rights | Exchange-function indicators with denominators; resource profile/opportunity contrast, no mandatory money |

Controlled successful transfer tests prove the mechanism, not an emergent inheritance custom or currency. In research lane all overrides are absent and positive institutions/money/practices are not gates. Resource-profile contrast intentionally changes a declared physical parameter; report it as such.

### Requirement Evidence

Original Request scenarios 12–15 and possession-versus-legitimacy invariant; `.ai-factory/ARCHITECTURE.md` — Important V3 seams.

### Error Handling and Logging

Reject nonexistent/dead actors, absent items, stale offers and invalid due windows; do not retry to fabricate agreement. A promise not yet due is censored/unresolved, not violated. DEBUG offer/claim counts, INFO case outcomes, ERROR safe admission/invariant codes; no quoted propositions/valuations.

### Tests and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_v3_benchmark_exchange.py tests/unit/test_death_corpse_custody.py tests/unit/test_possession_succession_classify.py -q`.

Test contested kin/nonkin claims, no automatic heir transfer, fulfillment and violation across multiple generation boundaries, actor death before due window, barter agreement/rejection/stale inventory, atomic rollback and repeated acceptance versus no acceptance. Null medium-of-exchange pattern remains a valid measured outcome.

### Acceptance Criteria

Cases 12–15 produce sourced histories without assigning objective legitimacy, debt enforcement, money or economy capability ownership.

## Phase Risks and Mitigations

- A direct test ledger seed would shortcut acquisition: ban it in benchmark modules and inspect schedule/source receipts.
- Sparse missing history can resemble extinction or violation: require complete eligible windows and distinguish censorship.

## Phase Completion Checklist

- Verify Tasks 8–9; update index only.
- Technology and economy outcomes remain owner/evidence-qualified.
