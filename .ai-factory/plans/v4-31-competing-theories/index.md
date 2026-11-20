<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-31 Competing Theories

Mode: ultra  
Branch: main (no branch created)  
Created: 2026-11-19  
Plan ID: `v4-31-competing-theories`

## Original Request
v4-31 competing theories

Naming requirement:

Use `v4-31-competing-theories`.

Support multiple incompatible scientific explanations.

Agents/groups may support different models.

Track:

support networks  
evidence cited  
predictions  
failures  
communication  
teaching

Do not centrally select a winning theory.

Allow socially popular but inaccurate theories.

Allow accurate minority theories.

## Settings
- Testing: yes
- Logging: verbose (metadata only)
- Docs: yes

## Roadmap Linkage
Milestone: "M8 — V4 Open-Ended Civilizations"  
Rationale: Deepens owned `science` without claiming any remaining reserved V4 context or completing M8.

## Requirements Reconciliation

Authority: The Original Request defines behavior; `.ai-factory/RULES.md` and `.ai-factory/ARCHITECTURE.md` define authority/version boundaries; `docs/scientific-models.md` defines the V4-30 compatibility contract. `.ai-factory/ROADMAP.md` M8 provides scope, not precedence or gating. V4-30’s two predictors are two estimators of one hypothesis, not rival explanations; the new sidecar is additive.

| Decision / supported combination | Source and persisted/observable behavior | Verification evidence |
|---|---|---|
| Science off; science on (v56-family, including v57 with measurement) | Architecture version contract and scientific models §Activation: off leaves no theory state or output; on adds owner state and versioned pending v5, never changes measurement/world codec selection | Tasks 4, 8, 9: old bytes, real v56/v57 configs and legacy gates |
| Prepared, submitted, committed or recovered | `AgentRuntime.bind_effective_command` and runner pending-record decode: only the final loop result is submitted, only addressed observations count as delivery, and v4/v5 outbox records pass the version gate and identity verification before finalization | Tasks 3–4, 8: real submitted frame and recovery, no fabricated receipts or duplicate installation |
| Identical observable context; different forecast categories | Original Request and scientific models §Performance: rival accounts retain distinct IDs, enter a frozen same-outcome contest; other contexts stay separate and same forecast is not rival evidence | Tasks 1, 2, 5: rival vs non-rival and prior-commit tests |
| Scored, unobserved, pending or not comparable | Scientific models §Issuance, commitment, target and receipt: only exact owner observation scores. Missing/not comparable remains explicit; never counts as failure | Tasks 2, 5, 8: timing, censored outcomes and paired comparison |
| Own evidence, addressed support, teaching, hearsay or non-delivery | Original Request and Architecture §Memory, testimony, and subjective concepts: preserve independently attributed citations, endorsements and receipt edges; no implied endorsement, skill grant or verified foreign source | Tasks 1, 3, 5, 8: duplicates, echoes, supervised actual delivery, same-root rejection |
| High/low social support with high/low predictive accuracy | Original Request: neither axis updates the other; both common-but-inaccurate and accurate-minority remain representable, and disjoint recipient cohorts may support different rivals | Tasks 3, 5, 8: controlled coexistence, retained failure history and no winner |
| Owner history ends, is unavailable, or crosses a retained window boundary | Architecture §Requirements for later changes: append-only history and explicit evidence gaps; preserve historical support, but do not present stale stances as current or missing owners as opposition | Tasks 5–6, 8: separate denominators, explicit coverage and cross-window closure |
| Published, absent, disabled, invalid or truncated research artifact | Architecture §Dependency Rules and scientific models §Publication, store and reads: detached and GET-only, gated, snapshot-pinned, explicit availability | Tasks 6–8: bounded canonical snapshots, auth before reads and real-run publication |

## Architecture and Decisions
- Use the existing fictional season and net visible resource-change observations. V4-31 introduces two closed explanatory accounts (continuity vs observed recurrence), not physical laws; no production theories or unsupported target classes in this increment. No universal theory verdict, composite score, group actor, raw cross-owner ledger, new command, objective event, migration, V4 context or capability flag. A `Talk`/`Tell` payload extension can change science-on speech; flags-off behavior and the world protocol remain unchanged.
- Each owner has a ledger; explanatory identity comes from content, while receipts, support and forecasts retain owner provenance. An owner-local prior seeds disagreement; addressed endorsements can move support without rewriting the independent case history. “Group support” is a retrospective network of explicit supporters and observed social edges, not an independent group decision.
- `CognitiveLoop` builds the sidecar from owner observations plus existing V4-30 case transitions. Committed owner state alone advances the ledger; v5 pending recovery is not a world replay version or a general durable subjective restart. No new runner field; use the owned `science` prerequisite chain.
- The post-run bridge tokenizes owner exports before detached analysis. Publish an independent research snapshot and append six metric families (262 → 268), without modifying the V4-30 metrics. UI reports the two axes and denominator coverage separately.
- No research artifact influenced the plan. Older historical counts are landing notes; preserve the dated V4-30 baseline for all unchanged pins.
- Refinement (2026-11-20): verified the outbox gate, speech binding, V4-30 forecast rotation, and detached read seams against current code; separate representative compatibility runs from the season-only controlled proof.

## Phase Index
1. [Phase 1: Theory kernel](phase-01-theory-kernel.md) — Tasks 1–2
2. [Phase 2: Runtime and testimony](phase-02-runtime-and-testimony.md) — Tasks 3–4
3. [Phase 3: Detached research](phase-03-detached-research.md) — Tasks 5–6
4. [Phase 4: Delivery and verification](phase-04-delivery-and-verification.md) — Tasks 7–9

## Cross-Phase Dependencies
- Task 2 depends on Task 1 for typed claims, contexts, and provenance.
- Task 3 depends on Tasks 1–2 for local updates and independent matched forecasts; Task 4 depends on Task 3 for the complete staged ledger.
- Task 5 depends on Task 4 for frozen completed-run owner exports; Task 6 depends on Task 5 for derived retained facts.
- Task 7 depends on Task 6 for read ports. Task 8 depends on Tasks 3–7 for the real runner-to-reader proof; Task 9 depends on Task 8 for documented scope and verification.

## Tasks

### Phase 1: Theory kernel
- [x] Task 1: Define owner explanations and citations ([details](phase-01-theory-kernel.md#task-1-define-owner-explanations-and-citations))
- [x] Task 2: Freeze predictions and record observed failures ([details](phase-01-theory-kernel.md#task-2-freeze-predictions-and-record-observed-failures)) (depends on 1)

### Phase 2: Runtime and testimony
- [x] Task 3: Track support, communication, and teaching ([details](phase-02-runtime-and-testimony.md#task-3-track-support-communication-and-teaching)) (depends on 1, 2)
- [x] Task 4: Integrate finalization and recovery ([details](phase-02-runtime-and-testimony.md#task-4-integrate-finalization-and-recovery)) (depends on 3)

### Phase 3: Detached research
- [x] Task 5: Build support networks and performance views ([details](phase-03-detached-research.md#task-5-build-support-networks-and-performance-views)) (depends on 4)
- [x] Task 6: Publish a bounded snapshot and verified read model ([details](phase-03-detached-research.md#task-6-publish-a-bounded-snapshot-and-verified-read-model)) (depends on 5)

### Phase 4: Delivery and verification
- [x] Task 7: Serve and render read-only theory evidence ([details](phase-04-delivery-and-verification.md#task-7-serve-and-render-read-only-theory-evidence)) (depends on 6)
- [x] Task 8: Prove disagreement and coexistence in a completed run ([details](phase-04-delivery-and-verification.md#task-8-prove-disagreement-and-coexistence-in-a-completed-run)) (depends on 3, 4, 5, 6, 7)
- [x] Task 9: Document contracts and execute the compatibility gate ([details](phase-04-delivery-and-verification.md#task-9-document-contracts-and-execute-the-compatibility-gate)) (depends on 8)

## Commit Plan
- **Commit 1** (after Tasks 1–4): `feat(science): track and persist competing owner explanations`
- **Commit 2** (after Tasks 5–9): `feat(research): expose competing theory evidence and coexistence checks`

## Definition of Done
- Incompatible accounts coexist in the same context, different owners and detached support communities support different accounts, and matched cases retain predictions and failures independently of stance.
- Support, citation roots, communication, and teaching remain attributable, bounded, and distinct. Controlled evidence demonstrates a popular inaccurate account and an accurate minority; autonomous runs may show neither.
- No global registry/decision, rank, winner, truth inference, new world mutation path or analysis feedback. Scientific and social outcomes remain decoupled.
- Deterministic legacy, recovery and completed-run read checks pass; coverage and unexecuted environmental lanes are reported; the mandatory docs checkpoint is complete.
