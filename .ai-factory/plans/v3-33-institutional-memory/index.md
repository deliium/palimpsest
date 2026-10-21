<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V3-33 Institutional Memory

Mode: ultra
Branch: main (existing branch; no branch/worktree created)
Created: 2026-10-21
Plan identifier: `v3-33-institutional-memory`
Status: implemented in working tree; verification fixes applied 2026-10-21

## Original Request

v3-33 institutional memory

Plan naming requirement:

Use `v3-` as plan prefix.

Suggested stem:

v3-33-institutional-memory

Implement persistent information channels associated with long-lived social roles or procedures.

Examples:

trade ledger  
archive  
project record  
decision record  
succession history

Do not implement telepathic institution memory.

Information must exist through:

physical records  
artifacts  
procedural transmission  
teaching

New role occupants must learn/access information.

Allow institutional memory to be:

incomplete  
wrong  
damaged  
ignored

Track provenance across occupants.

## Settings

- Testing: yes; focused unit/property/architecture tests, actual engine/runner/replay/collector paths and full default regression suite; keep coverage enabled.
- Logging: verbose, metadata-only. DEBUG owner IDs, modes, counts and safe reason codes; no facts, marks, message/memory bodies, labels, content-derived roots/digests or exception payloads.
- Docs: yes; mandatory `$aif-docs` implementation checkpoint.
- Language: English UI/artifacts; preserve English technical terms.
- Git: enabled; base `main`; `create_branches=false`; do not switch branches or alter preexisting changes; skip push prompt after future commits.
- Workflow: slug plan naming, normal verification; explicit bundle path is required because other plans coexist on `main`.
- Research: no research artifact/bundle available or used. This plan's requirements come from the request, project rules and current-code evidence.
- Scope of this invocation: write plan bundle only; no implementation, source-doc changes, branch creation or test execution.

## Roadmap Linkage

Milestone: "M7 — V3 Generational Civilization"

Rationale: Extend long-lived role/procedure continuity with externally carried, locally learned information without scripting institutions or claiming the remaining V3 flag.

M7 remains open. `institutional_economy` stays unowned; `multi_hop_testimony_tracking` remains M6 and unowned. This plan does not complete deferred kinship cultural handoff. Roadmap registration/status edits belong to `$aif-roadmap`, not this planning invocation.

## Requirements Reconciliation

Authority: repository `AGENTS.md` and `.ai-factory/RULES.md`/`rules/base.md` constrain all work; the Original Request defines feature scope; `.ai-factory/ARCHITECTURE.md` defines package/authority/compatibility requirements. Current code supplies executable carrier contracts, not permission to add hidden features. Historical roadmap/count summaries are scope/history, not current wire pins.

| Decision / supported behavior | Source path and section | Verification evidence |
|---|---|---|
| Information survives through material carriers or actual transmission, not a shared institutional mind. | Original Request — carrier requirements; `.ai-factory/ARCHITECTURE.md` — Memory, testimony, and subjective concepts | Tasks 6, 10, 13: hidden-record and unseen-peer noninterference, A→record→B→teaching→C receipts. |
| Role/procedure association is local; accession gives no knowledge or access rights. | Original Request — new occupants must learn/access; architecture Important V3 seams | Tasks 5, 9, 10: stable local channel ID, fresh successor, failed founder-list retrieval despite office claims. |
| Physical records contain bounded marks, not verified institutional facts. | `src/world/artifacts.py` — `ArtifactContent`; `src/world/communications.py` — declared transmission | Tasks 1–2, 6: real carrier bounds, false claims retained as attributed claims. |
| Incomplete/wrong/damaged/ignored information is legal; no truth correction. | Original Request — fallibility list; `.ai-factory/RULES.md` — owner memory/trust axioms | Tasks 2, 6, 7, 13: truncation, conflicting edits, ignored entries and no reconstruction from lineage. |
| Provenance crosses occupants via actual native carrier/delivery evidence plus separately declared lineage. | Original Request — provenance; architecture testimony/analysis boundaries | Tasks 1, 6, 10, 11: fresh local entry IDs, observed vs declared edges, ambiguity and pruning. |
| No new objective office/institution registry, world command/event, observer semantic or forced transfer. | Architecture — V3-29 through V3-32 seams, Requirements for later changes | Tasks 3, 7, 13–14: command/semantic pins 43/73 and boundary tests. |
| Default-off per-agent `institutional_memory_mode`; new write surface v53 only. | Architecture — accepted-set/exact-key-set extension contract; existing v52 mode pattern | Tasks 3–4: old-schema rejection, mixed owners, v53 exact keys and v4/legacy parity. |
| Repository admission is not reading confidentiality. | `src/world/_perception.py` — `_project_artifact`; existing repository access checks | Task 10 proves current visible marks/retrieval distinction; no perception or permission rewrite. |
| Existing teaching advice is not arbitrary institutional content; add a separate bounded speech consumer. | `src/agents/cognition/teaching.py` — `record_teaching`; `src/world/_teaching.py` — skill effects | Tasks 2, 6: actual delivered `im_teach` frame, no copied skill/AdviceStore widening. |
| Runtime continuation and durable external-memory persistence are separate guarantees. | `tests/unit/test_offices_checkpoints.py` — explicit runtime-only contract; durable-record replay tests | Task 9 proves runtime checkpoint parity; Task 10 proves real objective record replay and fresh-owner acquisition. |
| Explicit admitted learners start with enabled cognition and empty content; old profiles remain unchanged. | Original Request — new occupants must learn/access; `src/simulation/new_agent_initialization.py` — closed species-default registry and copy denials | Tasks 3, 9–10, 13: v53-only new profile, actual admission, no inheritance and subsequent acquisition. |
| Selection/use receipts follow the effective command; institutional teaching/ignore must be reachable through production policies. | `src/agents/cognition/models.py` — `ActionPlan`; `src/agents/cognition/loop.py` — `_planner_options`, `complete` | Tasks 7–8, 12–13: typed plan selection, legacy planner compatibility, real teaching/ignore paths and intervention suppression. |
| Institutional frame lineage and the outer utterance envelope are separate namespaces. | `src/world/communications.py` — `retell_utterance` speaker-chain rejection; current multi-channel decorators | Tasks 1–2, 7, 11, 13: preserve envelope, cyclic retransmission and no manufactured independent roots. |

### Supported Combinations

Each row defines accepted inputs, retained state/output and side effects; the cited task supplies a corresponding executable test. Optional channel gates are local, never auto-enabled.

| ID | Inputs / selectors | State, next output and invariants | Verification |
|---|---|---|---|
| C1 | New mode disabled on any already accepted historical config | No new ledger, audit, consultation, parsing or command change; old encoding/fingerprint/trajectory retained. | Tasks 3–4, 13; V1/V2 gates. |
| C2 | v53 with ≥1 enabled owner and that owner's office mode on | Valid role-capable mode; enabled-empty ledger until actual local recognition/evidence; other owners may be disabled. | Tasks 3, 5, 8. |
| C3 | v53 with enabled owner and its institution mode on, office mode off | Procedure-capable mode; only retained procedure-recurrence evidence binds channels; no fake office. | Tasks 3, 5. |
| C4 | Both local role/procedure modes on; optional mediation/decision/narrative modes | Separate local bindings, deterministic preparation and one command; no global registry or automatic merge. | Tasks 3, 5, 7–8. |
| C5 | New mode + artifact interpretation on + current visible revision with a decodable frame | Fresh local record entry from interpreted surviving marks; source metadata only if observed. | Tasks 6, 10. |
| C6 | No interpretation / hidden or destroyed carrier / stale reading / repository alone | No new record acquisition; previously learned entries may remain. Role/access claim changes nothing. | Tasks 6, 10, 13. |
| C7 | Addressed `im_transmit`; `im_teach` with teaching mode on/off | Transmission needs actual delivered frame and resolved speaker; teaching additionally requires receiver mode. Without teaching mode ignore teaching frame. New entries remain attributed and personal, not objective skill. | Tasks 2, 6, 10. |
| C8 | Valid partial/wrong/conflicting frame or locally ignored entry | Surviving facts only; preserve competing claims/provenance and partial coverage; ignored entries not consulted or retransmitted. No correction against authoritative events. | Tasks 2, 6–7, 13. |
| C9 | Claimed successor/new admitted agent, no content exposure | New owner starts without predecessor entries or implicit founder privileges. Existing newborn profiles keep new mode off; explicit v53 learner profile enables empty cognition only. Later content still requires the newcomer's actual exposure/delivery. | Tasks 3, 9–10, 13. |
| C10 | Same owner restored from supported runtime checkpoint; objective record restored by existing replay | Owner checkpoint retains own state; objective restored observation matches live carrier marks. Fresh learners still require access. These are distinct tests, not a claim of durable restoration of every subjective ledger. | Tasks 9–10. |
| C11 | Enabled mode on v52 or older; v53 all mode-off; enabled owner with neither local role/procedure mode; unowned capability flag enabled | Fail closed with explicit schema/dependency/capability error before execution. Never silently promote or enable another channel. | Tasks 3–4, 12. |
| C12 | Explicit learner profile on v53 with existing lifecycle/admission prerequisites and enabled initial owner; same profile on v52 or older | v53 admits a new empty, office/read/teach-capable learner. Old versions reject the profile; old profiles are unchanged. No entry, role identity or access privilege is inherited. | Tasks 3, 9–10, 13. |
| C13 | New mode with old-signature injected planner; typed consult/teach/transmit/record/ignore selection; effective command replaced before complete | Filter new kwargs through `_planner_options`; validate local selection. Commit ignore/consult receipts only through completion; changed commands cannot claim carrier emission. | Tasks 7–8, 13. |
| C14 | Institutional claim retransmitted with an already decorated envelope or back to a previous speaker | Preserve native envelope; frame keeps declared institutional root. No `retell_utterance` decorator crash, overwritten attribution or additional independent source count. | Tasks 2, 7, 11, 13. |

Representative real artifacts: existing BF/BI scenario configs for legacy round trips; existing durable-record/repository fixtures and public replay path for carrier continuity; new BJ completed-run output through the real collector/metric service. Synthetic ledger tests alone are insufficient.

## Architecture and Decisions

1. New cognition-owned modules: `institutional_memory.py` for local state/update, `institutional_memory_frames.py` for bounded public encoding, and `institutional_memory_actions.py` for consultation/selected-command decoration. Cross-package access uses deliberate public facades.
2. Owner-local channels bind stable office IDs or locally evidenced procedure anchors. Occupant changes do not reset a role's channel; no incoming sender ID is imported as a receiver's office/procedure identity. Unknown/ambiguous associations stay unbound.
3. Records carry up to three explicit claim triples in ≤16 legal marks. Speech carries a bounded whole-fact frame in an existing relation. Body facts are not duplicated into damage-resistant artifact relations. Public roots are declared references, never remote lookup keys.
4. Acquisition uses current visible artifact interpretation or actual addressed speech delivery. The new teaching consumer does not repurpose skill-domain `AdviceStore` or modify objective teaching effects. Current role recognition is not access to predecessor information.
5. Existing selected `Talk`/`Tell` can retransmit/teach acquired content; an already selected empty `Inscribe` can record it. A typed `InstitutionalMemorySelection` makes teach/transmit/consult/record/ignore explicit without forcing an intention. Default winning Talk/Tell uses teaching when that mode is enabled, otherwise transmission; skill-domain advice is independent. No automatic recordkeeping, utility bonus, procedure execution, transfer, quorum or mandatory compliance is added.
6. Optional owner state follows `Perspective`/`SubjectiveSnapshot` → `CognitiveLoopProposal` → `CognitiveLoopResult` → deferred runtime commit. `ActionPlan` carries the optional typed selection; `CognitiveLoop.complete` derives use/ignore effects against the effective command. `CommandPlanner.plan` gets optional keywords through `_planner_options`, preserving old injected planners; there is no existing `DecisionContext` class to extend. Frame decoration never rewrites the native utterance envelope or uses `retell_utterance` on it.
7. Persistence scope: existing objective record/event codecs plus supported runtime checkpoint continuation. Full durable restart serialization of all subjective ledgers is explicitly not introduced. Newborns/successors never inherit another owner's ledger. An explicit v53-only `species_default_institutional_memory_v1` pack enables empty office/read/teach/institutional cognition; old profiles remain unchanged. Admission alone supplies no content.
8. Add detached `institutional_memory_continuity@1` and `institutional_memory_provenance@1`, catalog 124→126; exact typed carrier/identity/entry/use rows, source matching, contested-window exclusions and deduplication rules are defined in Phase 6. Real carrier receipts and subjective occupant claims remain distinct, with ambiguity/pruning denominators; outer-envelope origins do not establish independent institutional sources.
9. Add Experiment BJ `institutional_memory@1`, off the V1 gate. Opportunity arms may produce no roles/records/transfer; mechanism tests separately prove possible A→B→C paths without forcing emergent outcomes.
10. Compatibility: default runner v4; institutional mode writes v53 with exact v52 cognition keys plus one per-agent mode. Reuse active lower-family roots and objective write-pair selection. Commands 43, observer semantics 73, maximum existing replay V22/codec v20, Alembic 0017, `/v1`, `observer-protocol-v1` and `prepare_parallel=False` unchanged.

### Non-goals

No telepathy, omniscient archive, objective institution/office/proposal registry, verified history, inherited founder access, parent/teacher knowledge copy, global dictionary, executable institutional-procedure DSL, new world command/event, new client/API route, SQL migration, capability flag, institution-type taxonomy, or universal durable subjective restart project.

## Phase Index

1. [Phase 1: Owner-local information and carrier contracts](phase-01-contracts.md) — Tasks 1–2
2. [Phase 2: Exact opt-in configuration](phase-02-configuration.md) — Tasks 3–4
3. [Phase 3: Grounded acquisition and occupant provenance](phase-03-acquisition.md) — Tasks 5–6
4. [Phase 4: Voluntary use, recording and atomic runtime flow](phase-04-runtime.md) — Tasks 7–8
5. [Phase 5: Continuity without inherited minds](phase-05-continuity.md) — Tasks 9–10
6. [Phase 6: Detached continuity and provenance metrics](phase-06-analysis.md) — Task 11
7. [Phase 7: Reproducible opportunities and adversarial proofs](phase-07-experiments.md) — Tasks 12–13
8. [Phase 8: Documentation and final compatibility gate](phase-08-release.md) — Task 14

## Cross-Phase Dependencies

- Task 2 depends on 1: frames serialize bounded claims/provenance, not arbitrary ledger objects.
- Task 3 depends on 1–2; Task 4 depends on 3: runtime composition uses exact mode/policy contracts.
- Task 5 depends on 1–4; Task 6 depends on 5 and 2: acquisition produces locally bound, provenance-bearing entries.
- Task 7 depends on 5–6; Task 8 depends on 4–7: selected-command use and atomic state propagation must agree.
- Task 9 depends on 8; Task 10 depends on 6–9: continuity proofs distinguish owner restoration from external transmission.
- Task 11 depends on 9–10: detached analysis consumes actual exported entries/receipts, not live cognition.
- Task 12 depends on 3–11; Task 13 depends on 1–12. Task 11 tests must collect and pass before BJ exists; the BJ-specific collector test is created only in Task 12, with no skip/future import in earlier tests.
- Task 14 depends on 1–13: document and verify only the implemented surface.

## Tasks

### Phase 1
- [x] Task 1: Define owner-local channels, entries and provenance ([details](phase-01-contracts.md#task-1-define-owner-local-channels-entries-and-provenance)).
- [x] Task 2: Define bounded physical and speech frames ([details](phase-01-contracts.md#task-2-define-bounded-physical-and-speech-frames)) (depends on 1).

### Phase 2
- [x] Task 3: Add runner-config-v53 without changing old keysets ([details](phase-02-configuration.md#task-3-add-runner-config-v53-without-changing-old-keysets)) (depends on 1, 2).
- [x] Task 4: Add cognition-local configuration and composition ([details](phase-02-configuration.md#task-4-add-cognition-local-configuration-and-composition)) (depends on 3).

### Phase 3
- [x] Task 5: Ground channels and locally produced information ([details](phase-03-acquisition.md#task-5-ground-channels-and-locally-produced-information)) (depends on 1–4).
- [x] Task 6: Acquire records, procedural transmission and teaching ([details](phase-03-acquisition.md#task-6-acquire-records-procedural-transmission-and-teaching)) (depends on 2, 5).

### Phase 4
- [x] Task 7: Expose consultation and compile only selected existing actions ([details](phase-04-runtime.md#task-7-expose-consultation-and-compile-only-selected-existing-actions)) (depends on 5, 6).
- [x] Task 8: Integrate preparation, owner context and deferred commit ([details](phase-04-runtime.md#task-8-integrate-preparation-owner-context-and-deferred-commit)) (depends on 4–7).

### Phase 5
- [x] Task 9: Preserve supported owner checkpoints and blank-slate admission ([details](phase-05-continuity.md#task-9-preserve-supported-owner-checkpoints-and-blank-slate-admission)) (depends on 8).
- [x] Task 10: Prove external carrier survival, loss and later learning ([details](phase-05-continuity.md#task-10-prove-external-carrier-survival-loss-and-later-learning)) (depends on 6–9).

### Phase 6
- [x] Task 11: Add institutional memory continuity and provenance analysis ([details](phase-06-analysis.md#task-11-add-institutional-memory-continuity-and-provenance-analysis)) (depends on 9, 10).

### Phase 7
- [x] Task 12: Add Experiment BJ institutional-memory opportunities ([details](phase-07-experiments.md#task-12-add-experiment-bj-institutional-memory-opportunities)) (depends on 3–11).
- [x] Task 13: Prove nontelepathy, fallibility and invariants ([details](phase-07-experiments.md#task-13-prove-nontelepathy-fallibility-and-invariants)) (depends on 1–12).

### Phase 8
- [x] Task 14: Complete docs checkpoint and run full gates ([details](phase-08-release.md#task-14-complete-docs-checkpoint-and-run-full-gates)) (depends on 1–13).

## Commit Plan

- **Commit 1** (after Tasks 1–4): `feat(cognition): define opt-in institutional memory contracts and v53 config`
- **Commit 2** (after Tasks 5–8): `feat(cognition): learn and record role-associated information through public carriers`
- **Commit 3** (after Tasks 9–11): `feat(analysis): track institutional information continuity and provenance`
- **Commit 4** (after Tasks 12–14): `feat(experiments): add institutional memory opportunities and compatibility proofs`

Commit boundaries are implementation checkpoints, not instructions to stage unrelated user changes or automatically push.

## Definition of Done

- Every indexed task is implemented and verified; only this index holds progress checkboxes.
- Role/procedure information has concrete observation/read/delivery sources; successor status never transfers private entries or grants access.
- Actual engine records survive author/occupant loss and objective replay; runtime owner checkpoint parity is separately demonstrated.
- An actual admitted learner with the explicit new profile starts empty, then acquires through its own exposure/delivery. Existing profiles stay unchanged; no profile transfers predecessor content.
- Typed planner selection, effective-command completion, ignore/unignore and independent institutional teaching have production-path tests; old-signature injected planners still work. Retransmission preserves outer attribution and never manufactures independent sources.
- Partial, wrong, damaged, conflicting and ignored information have explicit test outcomes and retained provenance; source absence is not corrected from ground truth.
- New mode off leaves old config bytes/fingerprints, cognition and commands unchanged; accepted historical schemas remain accepted with original exact keys.
- Actual BJ runs and completed-result collectors exercise both new metric families without requiring emergence or successful handover.
- Full unit/architecture suite with coverage, Ruff, mypy, import-linter and mandatory docs checkpoint pass; unrelated baseline failures are reported, not hidden.
- No command/event/protocol/SQL changes or unowned capability ownership; M7 remains open.

## Risks, Gaps and Execution Notes

- No blocking requirement conflict identified. Historical descriptions quote 103/117 metric families and earlier ownership; current architecture and later description sections agree on V3-32/v52/124. Do not rewrite historical counts while implementing this feature.
- Existing repository visibility permits colocated reading independently of retrieval/mutation admission. Preserve and document that contract; confidentiality changes require separate scope.
- Existing practical-knowledge record uptake and institution memory/advice hooks are not sufficient content-grounded acquisition; implement the explicit consumer in Phase 3.
- Existing object checkpoints do not prove durable subjective process restart. Do not rename that limitation away; physical persistence/replay and actual successor learning are the promised persistent-channel mechanism.
- Numerous preexisting modified/untracked assistant/context files existed when planning began. Preserve them. This invocation adds only this new plan directory.
- For continuation, read this index and the complete current phase file; do not preload old plans or excluded context. Start implementation with the explicit path below.

## Next Command

`$aif-implement @.ai-factory/plans/v3-33-institutional-memory/index.md`

## Refinement Notes — 2026-10-21

Approved through `$aif-improve`: five substantive refinements and one dependency correction applied without changing the Original Request, task IDs or completion state. Added explicit empty admitted-learner profile/gates; typed `ActionPlan` selection and effective-command receipt flow; reachable institutional teaching/ignore paths; separate frame/envelope provenance; exact detached row/join/denominator contracts; moved all BJ-dependent metric verification into Task 12. Total remains 14 unstarted tasks across eight phases. No application code, source requirements or unrelated user files changed.
