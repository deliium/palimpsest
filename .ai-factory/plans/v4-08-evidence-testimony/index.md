<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-08 Evidence and Testimony

Mode: ultra
Branch: main
Created: 2026-11-04
Plan identifier: `v4-08-evidence-testimony`
Status: planned; not implemented

## Original Request

v4-08 evidence and testimony

Naming requirement:

Use `v4-08-evidence-testimony`.

Create a general social evidence model.

Potential evidence sources:

- witness testimony
- written record
- artifact
- physical state
- prior agreement
- reputation
- remembered event

Evidence != truth.

Witnesses may misremember.

Records may be wrong.

Artifacts may be misinterpreted.

Track:

source
provenance
chain of custody where applicable
confidence
agent interpretation
contradictions

Agents should evaluate evidence according to their own beliefs and trust models.

Provide research tooling to compare evidence with objective history without leaking truth into cognition.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose/browser, Godot regression, Research UI, benchmark regression, and
  static gates, with coverage enabled for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG flow/counts, INFO milestones,
  WARN incomplete evidence/truncation, ERROR safe codes.
  `PALIMPSEST_LOG_LEVEL` controls operational verbosity. Never log source
  content, subject tokens, party sets, witness identities, evidence ids,
  contradiction text, custody tokens, confidence values, private content,
  payload surrogates, prompts, credentials, tokens, DSNs, memories, embeddings,
  utterance bodies, labels, or artifact payloads.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 23.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-08-evidence-testimony`; the ultra bundle directory
  is `.ai-factory/plans/v4-08-evidence-testimony/`, phase files use
  `phase-NN-<slug>.md`, and `index.md` is the canonical entrypoint.
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only. No implementation, commit, roadmap edit, or branch
  creation occurs in this invocation.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-08 deepens the already-declared owner-scoped `legal_disputes` V4
context with a general social evidence ledger covering source, provenance,
chain of custody, confidence, interpretation, contradictions, witness testimony,
and owner-relative trust evaluation, while keeping objective comparison
detached and adding no capability flag, runner schema, command, event, observer
semantic type, write pair, `/v2` route, or migration. The roadmap's next-plan
order is a priority, not a technical dependency: this work claims no unowned
flag and deepens an already-implemented context. This plan does not edit or
close the roadmap; `$aif-roadmap` must register V4-08 in M8.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Capability ownership", "Important V3 seams", "Versioned
Extension Contract", V4-01 through V4-07 seams) and `.ai-factory/RULES.md`
constrain every edit; `.ai-factory/DESCRIPTION.md` and `.ai-factory/ROADMAP.md`
describe current state; completed V3 mediation, structured-commitment,
subjective-value, institution, office, organization, operation, collective
agency, formal-rule, durable-record, archive, and V4-07 dispute code plus the
`tests/architecture/test_*organization*`, `test_formal_rule_boundaries`,
`test_dispute_boundaries`, and `test_v4_*` suites govern compatibility. V4-08
creates no capability flag and no new context: it deepens the existing
`legal_disputes` flag.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-08 deepens the declared `legal_disputes` context; no other V4 flag, `runner-config-v57`, new root field, or per-agent runner key is added | Original Request "evidence and testimony"; `.ai-factory/ARCHITECTURE.md` "Capability ownership"; `src/simulation/v4_architecture.py` 136-149; `src/simulation/runner_models.py` 305-325, 1114-1163, 7594 | Task 2/3 tests; Task 20 pins; Task 24 `v57` absence |
| The user-requested evidence work may land before `infrastructure_networks`; it claims no unowned flag and deepens an already-implemented owner-scoped context, so roadmap ordering is a priority rather than a technical dependency | `.ai-factory/ROADMAP.md` "Next plans" under M8; `src/simulation/v4_architecture.py` 136-149; `src/simulation/runner_models.py` 320-325 | Task 2 test; Task 24 audit |
| The evidence ledger is active exactly when `legal_disputes` is enabled on `runner-config-v56`; the flag remains the third owned V4 flag | `src/simulation/v4_architecture.py` 136-149; `src/simulation/runner_models.py` 320-325; `src/simulation/runner.py` 1014, 2670 | Task 2/3/9 tests |
| A dispute remains an owner belief; V4-08 adds a separate general evidence ledger rather than rewriting `dispute-resolution-snapshot-v1` | Original Request; `.ai-factory/ARCHITECTURE.md` Key Principle 1; `src/agents/cognition/legal_disputes.py` 33-44 | Task 4/14/20 tests |
| Seven source kinds are representable: witness testimony, written record, artifact, physical state, prior agreement, reputation, remembered event, plus closed `unknown` | Original Request "Potential evidence sources"; `src/world/artifacts.py` 78-117; `src/agents/cognition/structured_commitments.py` 88-202; `src/agents/cognition/reputation.py` 49-73; `src/memory/models.py` 579-743 | Task 1/6/21 tests |
| Every source carries an owner-visible provenance channel, a reference anchor, and an opaque correlation only; no `WorldEvent`, `WorldState`, or event store is carried | `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime", "Memory, testimony, and subjective concepts"; `src/world/observations.py` 231-280; `src/memory/models.py` 447-503 | Task 4/6/7/20 tests |
| Evidence is never truth; no `truth`, `verified`, `authenticated`, `forged`, `guilty`, `liable`, or `winner` field or result exists | Original Request "Evidence != truth"; `.ai-factory/ARCHITECTURE.md` Key Principle 1 | Task 1/8/12/20 tests |
| A witness may misremember; conflicting remembered evidence is retained without ground-truth correction | Original Request "Witnesses may misremember"; `src/memory/models.py` 2657-2882 | Task 6/7/12/21 tests |
| A record may be wrong; record integrity is an owner belief, not an objective truth predicate | Original Request "Records may be wrong"; `src/world/artifacts.py` 110-117 | Task 6/7/12 tests |
| An artifact may be misinterpreted; interpretation is a closed owner belief, never objective meaning | Original Request "Artifacts may be misinterpreted"; `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts" | Task 5/6/8 tests |
| Chain of custody is recorded only for artifact, written-record, and physical-state sources; it is an owner belief with `complete_belief`/`incomplete_belief`/`conflicting_belief`/`not_applicable`/`unknown` | Original Request "chain of custody where applicable"; `src/world/artifacts.py` 314-527; `src/world/repositories.py` 148-278 | Task 4/7/12/21 tests |
| Confidence is the owner's subjective confidence in the source as understood, quantized, never a probability of truth | Original Request "confidence"; `src/memory/models.py` 596; `src/social/relationships.py` 176-209 | Task 1/4/13 tests |
| Agents evaluate evidence from their own direct experience, relationship trust, reputation, office authority, rule authority, or institution membership only | Original Request "their own beliefs and trust models"; `src/social/relationships.py` 56-66, 305-459; `src/agents/cognition/reputation.py` 320-459; `src/agents/cognition/offices.py`; `src/agents/cognition/institutions.py` | Task 8/20/21 tests |
| Direct and communicated testimony are distinct; shared roots are never independent corroboration | `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts"; `src/agents/cognition/legal_disputes.py` 1286-1342; `src/world/communications.py` 222-313 | Task 5/6/8/12/21 tests |
| Contradictions are retained as owner beliefs and never reconciled into one truth; an owner preference is explicit and revisable | Original Request "contradictions"; `src/agents/cognition/mediation.py` 599-682 | Task 8/12/21 tests |
| Detached analysis may compare evidence rows with committed objective history (`consistent`, `unresolved`, `inconsistent`, `not_applicable`); that comparison never reaches cognition, prompts, memory, world state, stop selectors, or observer semantics | Original Request "compare evidence with objective history without leaking truth into cognition"; `.ai-factory/ARCHITECTURE.md` Key Principle 1, "analysis is read-only" | Task 10/12/13/20/21 tests |
| Objective counts, owner rows, and analytical candidates remain three separate types with hard leakage checks | `.ai-factory/ARCHITECTURE.md` Key Principle 1; `src/analysis/dispute_layers.py` 414-456; `src/analysis/formal_rule_layers.py` 218-247 | Task 12/20 tests |
| The metric catalog grows from 154 to 157 by appending `evidence_source_structure@1`, `evidence_provenance_continuity@1`, and `evidence_objective_alignment@1`; the first 154 keep id, order, version, and value keys | `src/analysis/specifications.py` 52-53, 229-231, 7205-7207 | Task 13/20/24 pin checks |
| `evidence-testimony-snapshot-v1` is a new independent artifact; dispute, organization, and formal-rule snapshots remain byte-verifiable and unchanged | `.ai-factory/ARCHITECTURE.md` "Use accepted-set and exact-key-set schema evolution"; `src/simulation/dispute_codec.py`; `src/simulation/organization_codec.py`; `src/simulation/formal_rule_codec.py` | Task 14/20/24 snapshot tests |
| Access is six GET-only `/v1/simulations/{run_id}/evidence...` routes requiring `SUBJECTIVE_DEBUG`; the dispute, organization, and formal-rule route sets keep their paths | `docs/research-api.md`; `src/api/routes/dispute.py` 50, 372-647; `src/api/routes/formal_rule.py` | Task 18/20 route tests; Task 21 API reads |
| Cursors bind to the publication digest and query fingerprint; changed run/filter/publication/digest fails with 400 and expiry with 410 | `src/api/dispute_cursor.py` 26, 76-135; `src/simulation/dispute_ports.py` 50-308 | Task 15/18/21 cursor tests |
| Publication is opt-in, post-completion, atomic, quota-bounded, and isolated from scientific status; new CLI flags and env root follow the formal-rule/dispute precedent | `src/experiments/formal_rule_publication.py`; `src/experiments/dispute_publication.py`; `src/research_runner/dispute_composition.py` 65-216 | Task 16/17/21 receipts and failure-isolation tests |
| No SQL migration, new event, command, observer semantic type, write pair, `/v2` route, or `observer-protocol-v2` is added; Alembic stays `0017`, events 22, codec v20, commands 43, semantics 73 | `.ai-factory/ARCHITECTURE.md` requirements 4-6; `src/simulation/versioning.py` 77-90 | Task 20/24 pins |
| Evidence rows flow through `MetricComputationInputs`, `experiments.collectors`, and `analysis.metric_service`; the new families are emitted by real completed-run assembly | `.ai-factory/ARCHITECTURE.md` "analysis is read-only"; `src/analysis/metric_service.py` 1629-1706; `src/experiments/collectors.py` 829-849 | Task 10/13 tests; Task 21 metric assembly |
| The carried ledger reaches `Perspective` through `build_perspective` and `SimulationRunnerResult` validates ordered ledger sequences | `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime"; `src/simulation/perception.py` 161, 373; `src/simulation/runner_models.py` 6381, 6697-6709 | Task 9 tests; Task 20 carry scan |
| Required lanes must execute; a missing prerequisite is reported `unexecuted` with a prerequisite, never as a skip-pass | Plan Settings "Testing: yes; full strategy"; `docs/development.md`; `tests/compose/acceptance.py` | Task 22 three-state receipt; Task 24 audit |
| The roadmap is owned by `$aif-roadmap` and is not edited here | `.ai-factory/ARCHITECTURE.md` requirement 7 | Task 23/24 `git status` |

### Supported combinations and availability transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| Default runner config, all V4 flags off | V4-07-equivalent behavior | No evidence ledger, no metric, no publication, no route data | Task 3/9/21 flags-off tests |
| `legal_disputes` enabled on v4 or v55 | Unchanged config | `v4_capability_requires_v56` before construction | Task 2 test |
| `legal_disputes` enabled on v56 without `formal_rules` | Valid run | Evidence ledger works; rule-authority basis is `none`; no rule invented | Task 2/8 test |
| `legal_disputes` enabled on v56 with `formal_rules` | Valid run | Rule-authority basis resolves against the owner's own formal-rule ledger | Task 8/21 test |
| Flag on v56, enabled ledger with zero sources | Valid run | Metrics `PRESENT` with zero counts and explicit coverage; no fabricated source | Task 13 test |
| Owner asserts a source through existing `Talk`/`Tell` | Attributed source | `evs-` record; provenance `communicated`; no world change | Task 5/6/21 tests |
| Witness testifies first-hand | Direct testimony | `evw-` with `channel=direct`; `independently_evidenced` only when the root is distinct | Task 5/6/12 tests |
| Retold testimony sharing a root | Communicated testimony | `channel=communicated`; shared root is not independent corroboration | Task 5/6/12 tests |
| Owner observes an artifact or record | Observed source | `evs-` with `provenance=direct_observation`; opaque reference only | Task 6/7/20 tests |
| Owner recalls a remembered event | Remembered source | `evs-` with `provenance=remembered`; owner-local memory id retained | Task 6/7/21 tests |
| Owner cites a durable record | Record source | Integrity is a belief (`intact`/`damaged`/`partially_lost`/`destroyed_belief`/`uncertain`) | Task 6/7/12 tests |
| Owner cites a prior agreement | Agreement source | References the owner's own commitment interpretation; no collection | Task 6/8 tests |
| Owner cites reputation | Reputation source | References the owner's own reputation band; no shared score | Task 6/8 tests |
| Owner interprets a source | Interpreted item | `evi-` with closed `supports`/`contradicts`/`ambiguous`/`insufficient`/`irrelevant`/`unknown` | Task 5/6/21 tests |
| Owner retracts an interpretation | Retained row | Item status `retracted`; history preserved; no deletion | Task 4/6 tests |
| Two sources disagree | Retained contradiction | `evx-` with `status=unresolved`; both rows kept | Task 8/12/21 tests |
| Owner prefers one side | Owner preference | `owner_prefers_first`/`owner_prefers_second`; still not truth | Task 8/20 tests |
| Artifact custody claimed at ticks 3 and 7 | Custody chain | Links sorted; contiguous chain `complete_belief`; gap `incomplete_belief` | Task 7 tests |
| Two custody claims at one tick disagree | Conflicting custody | `conflicting_belief`; both retained | Task 7/12 tests |
| Non-portable source (reputation/remembered event) | No custody chain | `not_applicable`; no fabricated link | Task 7 test |
| Trusted witness via relationship | Evaluation | `relationship_trust` basis with bounded weight | Task 8/21 tests |
| No trust information | Neutral evaluation | `none` basis, neutral confidence, `evidence_trust_basis_missing` notice | Task 8 test |
| Speaker claims another party's testimony | Attributed declaration | Actor remains the verified speaker; forged witness rejected | Task 5/20 tests |
| Objective history supports a source | Researcher-only alignment | `consistent` count increments; agent ledger and prompt unchanged | Task 10/12/13/21 tests |
| Objective history contradicts a source | Researcher-only alignment | `inconsistent` count increments; agent ledger unchanged; no verdict | Task 10/12/13/20 tests |
| Source kind has no objective referent | Researcher-only alignment | `not_applicable`; never counted as consistent | Task 12 test |
| Candidate exceeds 64 sources or 32 items | Deterministic truncation | `evidence_truncated`; no silent drop | Task 4/14/16 tests |
| Snapshot exceeds 8192 sources / 16384 items / 4 MiB | No publication | `evidence_testimony_size_limit` | Task 14/16 tests |
| Duplicate publication id with different bytes | Existing publication untouched | `evidence_testimony_publication_exists` | Task 17 test |
| `PALIMPSEST_EVIDENCE_ROOT` unset | API state unset | 503 `evidence_testimony_disabled`; CLI receipt `disabled` | Task 18/21 tests |
| Cursor reused with same filter/run/publication/digest | Same page | 200; digest matches | Task 15/18 test |
| Cursor reused with changed filter/run/publication/digest | No page served | 400 `evidence_testimony_cursor_invalid`; expired 410 | Task 15/18 test |
| Run incomplete or publication failed | Scientific result unchanged | Receipt `unavailable`/`failed` only | Task 16/17/21 test |
| Required Compose/browser/Godot/benchmark lane with a missing prerequisite | No green certification | Recorded `unexecuted` with prerequisite | Task 22/24 |

## Architecture and Decisions

1. **One existing flag, one deepening.** V4-08 adds no V4 flag, context,
   `runner-config-v57`, runner root field, or per-agent runner key. The
   owner-scoped evidence ledger is active exactly when `legal_disputes` is
   enabled on the accepted `runner-config-v56` seam.
2. **Evidence is an owner belief, not truth.** Every row belongs to one owner
   and describes what that owner observed, remembered, heard, read, inferred, or
   evaluated. There is no objective evidence registry, proof engine, verifier,
   authenticator, or truth predicate.
3. **Source kinds are closed, with an explicit unknown.** Witness testimony,
   written record, artifact, physical state, prior agreement, reputation,
   remembered event, and `unknown` are the only source kinds.
4. **Provenance is mandatory and owner-visible.** Each source records a closed
   provenance channel, an owner-visible reference anchor, a separate opaque
   correlation token, the tick, and an optional attributed actor. The
   correlation token is used only for researcher-only alignment and is never
   dereferenced or treated as a `WorldEvent`.
5. **Custody is a belief chain.** Chain of custody is recorded only for
   artifact, written-record, and physical-state sources, as ordered owner
   beliefs about holder, custodian, location, integrity, and witnessing. It is
   never an objective audit trail.
6. **Confidence is owner confidence.** A single quantized confidence plus
   separate contradiction references describe how much the owner relies on the
   source. Confidence never means probability of truth.
7. **Interpretation is closed.** Owners interpret a source as supporting,
   contradicting, ambiguous, insufficient, irrelevant, or unknown with respect
   to a subject token. The model stores no free text and no objective meaning.
8. **Contradictions coexist.** A contradiction links two owner-local references
   with a closed kind and an owner preference status. Retaining both is the
   default; preferring one is an explicit, revisable belief.
9. **Testimony is not corroboration by repetition.** Direct and communicated
   testimony are distinct, shared roots are not independent, and a speaker can
   never attribute testimony to another party.
10. **Trust is owner-relative.** Evaluation may use only the owner's direct
    experience, relationship trust, reputation bands, office authority, rule
    authority, or institution membership. There is no global trust score and no
    peer ledger read.
11. **Misremembering, wrong records, and misinterpretation are legal.** The
    ledger retains the owner's version and never corrects it against objective
    history. Detached analysis classifies alignment for researchers only.
12. **Three layers, three types.** Objective rows are aggregate counts of
    committed facts. Subjective rows use safe owner tokens and owner-local
    reference counts. Analytical rows use `evid-` candidates. Leakage is a hard
    failure.
13. **No objective alignment in cognition.** `consistent`, `unresolved`,
    `inconsistent`, and `not_applicable` exist only in detached analysis and
    never reach prompts, memory, world state, stop selectors, or observer
    semantics.
14. **No command path.** Evidence helpers never construct, submit, resolve, or
    execute an `AgentCommand`; every physical effect remains an ordinary
    admitted command.
15. **A new snapshot, not a rewrite.** `evidence-testimony-snapshot-v1` is
    independent. `dispute-resolution-snapshot-v1`, organization v1/v2/v3, and
    `formal-rule-snapshot-v1` remain decodable and byte-verifiable.
16. **Metrics append only.** 154 → 157. The first 154 families keep id, order,
    version, and value keys; the append updates every hard-coded catalog pin.
17. **Deterministic by construction.** Sorted ordering, content-addressed ids,
    canonical JSON digests, quantized floats, integer trust weights, no
    `hash()`, no UUID, and no wall-clock domain values.
18. **Read-only surfaces.** Six GET routes under `/v1` require
    `SUBJECTIVE_DEBUG`; the Research UI renders server fields without deriving
    truth, authenticity, guilt, liability, or a winning account.
19. **Cursors bind to the publication digest.** Every paged route binds run,
    publication, digest, filter, and offset through a signed cursor.
20. **Publication is opt-in and non-interfering.** A storage or composition
    failure changes only the receipt, never the scientific result.
21. **No automatic generalization.** V4-08 implements no `diplomacy`,
    `organized_conflict`, `science`, `infrastructure_networks`, market, supply
    chain, epidemic, ecological, disaster, resilience, or macro-society
    behavior.
22. **Existing evidence-like contracts are composed, not duplicated.** Domain
    ledgers (mediation, formal rules, offices, institutions, organizations,
    reputation, relationships, commitments, memory) keep their own evidence
    types; the general model references them by closed anchor kind and opaque
    owner-local id.

### Context declaration

| Context | Flag | Authority | Owning packages | Prerequisites | Existing mechanism | Event strategy |
| --- | --- | --- | --- | --- | --- | --- |
| `legal_disputes` (deepened) | `legal_disputes` (already owned) | owner-scoped | `agents.cognition`, `simulation` | `formal_rules` (declared; optional at runtime) | memory, records, artifacts, commitments, reputation, relationships, offices, institutions, formal rules, mediation, disputes | reuse |

Supporting packages without authority: `analysis` (detached rows/metrics),
`experiments` (harvest/publication bridge), `persistence` (filesystem store),
`api` (read-only routes), `research_runner` (opt-in CLI producer), and the
Research UI client.

### Compatibility pins

Default runner/result `v4`/`v2`; latest feature runner `v55`; accepted runner adds
`v56` only; events `EVENT_SCHEMA_REPLAY_V22` (22); codec `v20`; commands 43;
observer semantic types 73; metric families **157 (V4-08 change)**; Alembic
`0017`; `/v1`; `observer-protocol-v1`; observer layout `observer-layout-v1`;
observer capabilities 4 advertised / 6 reserved; four reserved write pairs
(events 23-26 / codecs `v21`-`v24`); `prepare_parallel=False`; six GET
organization routes, six GET formal-rule routes, six GET dispute routes, and six
GET evidence routes; six cursor purposes per context; snapshots
`organization-snapshot-v1`/`v2`/`v3`, `formal-rule-snapshot-v1`,
`dispute-resolution-snapshot-v1`, and `evidence-testimony-snapshot-v1`; stores
`organization-store-v1`, `formal-rule-store-v1`,
`dispute-resolution-store-v1`, and `evidence-testimony-store-v1`; 14 V4
contexts / 12 flags / **3 owned flags**.
`institutional_economy` and `multi_hop_testimony_tracking` remain unowned and
fail closed. `/version` is unchanged; `organization_rows` remains reserved.

## Phase Index

1. [Phase 1: Contract and Seam](phase-01-contract-and-seam.md) — Tasks 1-3
2. [Phase 2: Owner-Scoped Evidence Beliefs](phase-02-evidence-beliefs.md) — Tasks 4-9
3. [Phase 3: Detached Analysis, Candidates, and Metrics](phase-03-detached-analysis.md) — Tasks 10-13
4. [Phase 4: Evidence-Testimony Snapshot v1](phase-04-snapshot-v1.md) — Tasks 14-15
5. [Phase 5: Composition and Durable Publication](phase-05-composition-publication.md) — Tasks 16-17
6. [Phase 6: Read-Only API and Research UI](phase-06-read-only-surfaces.md) — Tasks 18-19
7. [Phase 7: Invariants, End-to-End Evidence, and Regression](phase-07-invariants-and-regression.md) — Tasks 20-22
8. [Phase 8: Documentation and Final Verification](phase-08-docs-and-verification.md) — Tasks 23-24

## Cross-Phase Dependencies

- All phases assume the completed V2/V3 mediation, structured-commitment,
  subjective-value, institution, office, organization, operation, collective
  agency, formal-rule, durable-record, archive, and V4-07 dispute stacks are
  present; V4-08 does not rewrite them, but Tasks 20/22 must keep their suites
  green.
- Task 2 depends on Task 1: the ownership pin uses the frozen vocabulary and
  context seam.
- Task 3 depends on Task 2: the cognition mode and policy reference the owned
  flag.
- Task 4 depends on Task 3: records use the policy, ids, and limits.
- Task 5 depends on Task 4: `ev_v1` frames encode the record vocabulary.
- Task 6 depends on Tasks 4-5: the update consumes the frame parser and records.
- Task 7 depends on Task 6: provenance and custody consume materialized sources.
- Task 8 depends on Tasks 6-7: evaluations consume sources, items, custody
  chains, and the owner context.
- Task 9 depends on Tasks 4-8: runtime carry and deliberation need records,
  frames, provenance, custody, and evaluations.
- Task 10 depends on Task 9: harvest reads exported ledgers and objective events.
- Task 11 depends on Task 10: detection/identity consumes normalized rows.
- Task 12 depends on Tasks 10-11: layers and alignment consume rows, candidates,
  and identity assignments.
- Task 13 depends on Tasks 10-12: the three families read summary/layers.
- Task 14 depends on Tasks 10-13: the snapshot mirrors rows/counts and metric
  provenance.
- Task 15 depends on Task 14: paging selects typed snapshot records.
- Task 16 depends on Tasks 13 and 15: the composer needs analysis and ports.
- Task 17 depends on Tasks 14-16: the store serves snapshots and cursor pages,
  and the CLI producer calls the Task 16 composer.
- Task 18 depends on Task 17: the API reads the committed store.
- Task 19 depends on Task 18: the panel consumes the six routes and detail
  fields.
- Task 20 depends on Tasks 2-19: the suite asserts every authority claim.
- Task 21 depends on Tasks 6-19: the E2E uses the real update, command
  admission, trust evaluation, publication, and surfaces.
- Task 22 depends on Tasks 20-21: regression runs after the invariant/E2E gates.
- Task 23 depends on Tasks 2-22: documentation describes verified surfaces.
- Task 24 depends on Tasks 22-23: final certification needs receipts and docs.

## Tasks

### Phase 1: Contract and Seam
- [x] Task 1: Freeze the evidence-testimony vocabulary and identity grammar ([details](phase-01-contract-and-seam.md#task-1-freeze-the-evidence-testimony-vocabulary-and-identity-grammar))
- [x] Task 2: Pin the legal_disputes deepening seam ([details](phase-01-contract-and-seam.md#task-2-pin-the-legal_disputes-deepening-seam)) (depends on 1)
- [x] Task 3: Add the cognition evidence mode and policy seam ([details](phase-01-contract-and-seam.md#task-3-add-the-cognition-evidence-mode-and-policy-seam)) (depends on 2)

### Phase 2: Owner-Scoped Evidence Beliefs
- [x] Task 4: Define evidence records and ledger invariants ([details](phase-02-evidence-beliefs.md#task-4-define-evidence-records-and-ledger-invariants)) (depends on 3)
- [x] Task 5: Add bounded ev_v1 evidence speech frames ([details](phase-02-evidence-beliefs.md#task-5-add-bounded-ev_v1-evidence-speech-frames)) (depends on 4)
- [x] Task 6: Collect sources, testimony, and interpretations ([details](phase-02-evidence-beliefs.md#task-6-collect-sources-testimony-and-interpretations)) (depends on 4, 5)
- [x] Task 7: Derive provenance and chain-of-custody beliefs ([details](phase-02-evidence-beliefs.md#task-7-derive-provenance-and-chain-of-custody-beliefs)) (depends on 6)
- [x] Task 8: Evaluate evidence and retain contradictions ([details](phase-02-evidence-beliefs.md#task-8-evaluate-evidence-and-retain-contradictions)) (depends on 6, 7)
- [x] Task 9: Carry the ledger through cognition and runtime ([details](phase-02-evidence-beliefs.md#task-9-carry-the-ledger-through-cognition-and-runtime)) (depends on 4-8)

### Phase 3: Detached Analysis, Candidates, and Metrics
- [x] Task 10: Harvest evidence rows and objective anchors ([details](phase-03-detached-analysis.md#task-10-harvest-evidence-rows-and-objective-anchors)) (depends on 9)
- [x] Task 11: Detect candidates and derive forward-only lineage ([details](phase-03-detached-analysis.md#task-11-detect-candidates-and-derive-forward-only-lineage)) (depends on 10)
- [x] Task 12: Project layers and researcher-only objective alignment ([details](phase-03-detached-analysis.md#task-12-project-layers-and-researcher-only-objective-alignment)) (depends on 10, 11)
- [x] Task 13: Add three metric families and raise the catalog to 157 ([details](phase-03-detached-analysis.md#task-13-add-three-metric-families-and-raise-the-catalog-to-157)) (depends on 10-12)

### Phase 4: Evidence-Testimony Snapshot v1
- [x] Task 14: Define evidence-testimony-snapshot-v1 and its codec ([details](phase-04-snapshot-v1.md#task-14-define-evidence-testimony-snapshot-v1-and-its-codec)) (depends on 10-13)
- [x] Task 15: Add paging, read ports, and cursor support ([details](phase-04-snapshot-v1.md#task-15-add-paging-read-ports-and-cursor-support)) (depends on 14)

### Phase 5: Composition and Durable Publication
- [x] Task 16: Compose completed-run snapshots and receipts ([details](phase-05-composition-publication.md#task-16-compose-completed-run-snapshots-and-receipts)) (depends on 13, 15)
- [x] Task 17: Add the atomic filesystem store and CLI producer ([details](phase-05-composition-publication.md#task-17-add-the-atomic-filesystem-store-and-cli-producer)) (depends on 14-16)

### Phase 6: Read-Only API and Research UI
- [ ] Task 18: Add six GET routes, schemas, settings, and app wiring ([details](phase-06-read-only-surfaces.md#task-18-add-six-get-routes-schemas-settings-and-app-wiring)) (depends on 17)
- [ ] Task 19: Add the read-only Research UI evidence view ([details](phase-06-read-only-surfaces.md#task-19-add-the-read-only-research-ui-evidence-view)) (depends on 18)

### Phase 7: Invariants, End-to-End Evidence, and Regression
- [ ] Task 20: Add the evidence boundary and determinism suite ([details](phase-07-invariants-and-regression.md#task-20-add-the-evidence-boundary-and-determinism-suite)) (depends on 2-19)
- [ ] Task 21: Add the evidence end-to-end scenario ([details](phase-07-invariants-and-regression.md#task-21-add-the-evidence-end-to-end-scenario)) (depends on 6-19)
- [ ] Task 22: Execute the full V1-V4 regression and qualification lanes ([details](phase-07-invariants-and-regression.md#task-22-execute-the-full-v1-v4-regression-and-qualification-lanes)) (depends on 20, 21)

### Phase 8: Documentation and Final Verification
- [ ] Task 23: Execute the documentation checkpoint ([details](phase-08-docs-and-verification.md#task-23-execute-the-documentation-checkpoint)) (depends on 2-22)
- [ ] Task 24: Perform final V4-08 verification ([details](phase-08-docs-and-verification.md#task-24-perform-final-v4-08-verification)) (depends on 22, 23)

## Verification Receipt (Tasks 22 and 24)

To be completed by Task 22 and audited by Task 24. Every required lane must be
recorded as exactly one of `executed_passed`, `executed_failed`, or
`unexecuted`. An `unexecuted` lane carries its missing prerequisite and blocks
certification; it is never a skip-pass.

| Lane | State | Evidence |
| --- | --- | --- |
| Python unit + architecture with coverage | `unexecuted` | Pending Task 22; no implementation exists at planning time |
| Focused V4-08 suite | `unexecuted` | Pending Task 22 |
| V4/organization/formal-rule/dispute regression selection | `unexecuted` | Pending Task 22 |
| Documentation parity | `unexecuted` | Pending Task 22 |
| Ruff | `unexecuted` | Pending Task 22 |
| Mypy | `unexecuted` | Pending Task 22 |
| Import-linter | `unexecuted` | Pending Task 22 |
| Integration (`-m "integration and not scale"`) | `unexecuted` | Pending Task 22; requires a disposable `pgvector/pgvector:pg17` database named `palimpsest_test` |
| Integration including scale | `unexecuted` | Pending Task 22; requires the 100,000-tick generational/scale lane |
| Docker Compose config | `unexecuted` | Pending Task 22 |
| Compose/browser acceptance | `unexecuted` | Pending Task 22; requires the pinned API image and Playwright chromium |
| Godot 4.7.2 regression | `unexecuted` | Pending Task 22; requires `GODOT_BIN` |
| Benchmark/scale lane | `unexecuted` | Pending Task 22; requires the multi-hour 100,000-tick harness |
| Research UI tests | `unexecuted` | Pending Task 22 |
| Research UI type/static checks | `unexecuted` | Pending Task 22 |
| Research UI build | `unexecuted` | Pending Task 22 |

Certification outcome: **not certified** until every required lane is
`executed_passed`.

## Commit Plan

Proposed implementation checkpoints; no commit is made by planning.

1. After Tasks 1-3: `feat(v4): deepen the legal-disputes evidence contract`
2. After Tasks 4-6: `feat(v4): record owner-scoped evidence sources`
3. After Tasks 7-9: `feat(v4): evaluate evidence without a truth oracle`
4. After Tasks 10-13: `feat(v4): analyze evidence and objective alignment`
5. After Tasks 14-17: `feat(v4): publish evidence-testimony-snapshot-v1`
6. After Tasks 18-19: `feat(v4): serve read-only evidence surfaces`
7. After Tasks 20-24: `test(v4): enforce evidence-testimony invariants`

## Blocking Conditions and Non-Goals

- Adding a new V4 flag, `runner-config-v57`, a new context, a runner root field,
  or a per-agent runner key to make this plan work is a blocking scope
  violation. Stop and re-plan.
- Creating an EvidenceOracle, TruthEngine, ProofEngine, Authenticator, Verifier,
  ChainOfCustodyAuthority, Polygraph, LieDetector, WitnessAuthority, EvidenceRegistry,
  global evidence registry, verdict, guilt, liability, authenticity, or binding
  finding is forbidden.
- Letting `WorldEngine`, perception, admission, stop selectors, memory, prompts,
  observer semantics, or the Godot client read an evidence ledger is forbidden.
- Letting an evidence helper return, construct, submit, or resolve an
  `AgentCommand`, move a resource, or execute a physical action is forbidden.
- Treating a source, testimony, record, artifact, custody claim, confidence,
  interpretation, evaluation, or contradiction as objective truth, proof,
  authenticity, permission, prohibition, guilt, liability, or a binding finding
  is forbidden.
- Inferring a source, testimony, interpretation, contradiction, or evaluation
  from silence, an unobserved act, or another owner's ledger is forbidden.
- Reconciling conflicting memories, records, or interpretations into one
  authoritative account is forbidden. Analysis may classify alignment for
  researchers only.
- Reading a peer owner's relationship, reputation, commitment, rule, office,
  institution, organization, or evidence ledger to evaluate evidence is
  forbidden.
- Adding a new event, command, observer semantic type, write pair, artifact
  kind, durable-record genre, `/v2` route, `observer-protocol-v2` serving, or SQL
  migration is forbidden.
- Rewriting the V3 mediation, structured-commitment, subjective-value,
  institution, office, durable-record, or V4 organization/formal-rule/dispute
  contracts is forbidden; evidence is additive.
- Weakening an existing pin or assertion (catalog counts, Alembic `0017`,
  replay v22, codec v20, command count, observer semantic count, context count)
  is forbidden. The only intentional pin changes are 154 → 157 metric families,
  the addition of six evidence routes alongside the six organization, six
  formal-rule, and six dispute routes, and new evidence snapshot/store schemas.
- Claiming prevalence, emergence probability, predictive power, accuracy,
  reliability of witnesses in general, moral correctness, or a composite
  evidence-quality score is forbidden.
- Editing `.ai-factory/ROADMAP.md` or closing M8 is out of scope;
  `$aif-roadmap` owns that.
- Changing the Godot client, observer protocol, observer capabilities, or
  `/version` is out of scope; the Research UI is the only client change.
- Enabling V4 flags in matrix lanes is out of scope; `experiments.matrix_schema`
  keeps its rejection gate.
- Full qualification requires a disposable PostgreSQL/pgvector instance,
  Docker, a real browser driver, and the pinned Node/pnpm and Godot toolchains.
  A missing prerequisite leaves the lane unexecuted and blocks certification; it
  never becomes a skip-pass.
- Do not implement any other V4 context (`diplomacy`, `organized_conflict`,
  `infrastructure_networks`, `supply_chains`, `markets_credit`, `science`,
  `epidemics`, `ecological_feedback`, `disasters`, `societal_resilience`,
  `macro_society_identity`, or another organization/formal-rule/dispute
  extension) in this plan.

## Definition of Done

- All 24 indexed tasks have verified completion evidence; only this index holds
  task progress checkboxes.
- `legal_disputes` remains the third owned V4 flag on `runner-config-v56`; no
  `v57`, new flag, context, root field, or per-agent runner key exists.
- The context registry validates at 14 contexts, 12 flags, and
  `v4-context-map-v2`; the analysis-only set and four reservations are unchanged.
- A general owner-scoped evidence ledger exists with seven requested source
  kinds plus `unknown`, mandatory provenance, optional custody chains,
  confidence, closed interpretation, contradictions, and owner-relative
  evaluation.
- Evidence is never truth: no objective proof, authenticity, verdict, guilt,
  liability, or winner field or result exists; witnesses may misremember,
  records may be wrong, and artifacts may be misinterpreted.
- Testimony independence is explicit; shared roots never count as independent
  corroboration; a speaker cannot attribute testimony to another party.
- Evaluation uses only the owner's direct experience, relationship trust,
  reputation bands, office authority, rule authority, or institution membership.
- Detached analysis may compare evidence rows with committed objective history
  (`consistent`, `unresolved`, `inconsistent`, `not_applicable`); agents never
  receive that comparison, and no verdict/guilt/liability value exists.
- Objective counts, owner rows, and analytical candidates remain separate with
  hard leakage checks; analysis never creates or changes a dispute,
  formal-rule, organization, office, institution, or mediation candidate.
- The metric catalog is exactly 157 with three appended families; the first 154
  are unchanged, and real completed-run assembly emits all three documents.
- `evidence-testimony-snapshot-v1` is canonical, bounded, immutable after
  publication; dispute, organization, and formal-rule snapshots remain
  decodable and byte-verifiable.
- Public evidence contracts are exported from `agents.cognition`, `analysis`,
  `experiments`, `simulation`, and `api.routes`; tests narrow shared `object`
  result fields before attribute access.
- Six GET-only `/v1` evidence routes require `SUBJECTIVE_DEBUG`, have an
  explicit `evidence_testimony_disabled` state, and are consumed by a read-only
  Research UI view.
- Cursor reuse works on every paged evidence route; changed
  filter/run/publication/digest fails with 400 and expiry with 410.
- `WorldEngine` never reads an evidence ledger; a socially contested but
  physically possible command is still admitted, and a physically impossible
  command is still rejected.
- The boundary suite proves owner-only authority, absence of truth oracles,
  evidence registries, trust oracles, command construction, peer-ledger reads,
  and world-ledger reads; no new commands/events/migrations are added;
  observer/migration pins are unchanged.
- The full V1-V4 regression lanes and static gates execute and pass; any
  unexecuted required lane is reported with its blocker and is not certified.
- Documentation states what evidence controls (a belief), what it never controls
  (objective action or truth), how provenance, custody, confidence,
  interpretation, contradictions, testimony independence, and trust evaluation
  work, how objective comparison stays researcher-only, and every count matches
  the code.
- `docs/evidence-testimony.md` is the canonical contract; `docs/analysis-metrics.md`
  documents the three families, `docs/research-ui.md` documents the panel, and
  README plus `docs/disputes.md` link the new contract.
