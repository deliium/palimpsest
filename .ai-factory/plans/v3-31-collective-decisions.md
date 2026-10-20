# Implementation Plan: V3-31 Collective Decisions

Branch: `main` (planning only; no branch creation)
Created: 2026-10-20
Refined: 2026-10-20 — configuration boundary, result transport, final-command attribution, delivery confirmation, bounded replay protection, influence comparison, and temporal coverage.
Canonical plan: `.ai-factory/plans/v3-31-collective-decisions.md`
Mode: full

## Settings

- Testing: yes — unit, property, architecture, configuration, continuation, experiment, and regression coverage.
- Logging: verbose — metadata-only DEBUG transitions, INFO composition/collection summaries, safe WARN rejection codes; controlled by `PALIMPSEST_LOG_LEVEL`.
- Docs: yes — mandatory `/aif-docs` checkpoint during implementation.
- Git: enabled; `git.create_branches: false`; remain on the existing branch.
- Scope: generic, opt-in collective deliberation and coordination, not a political-system simulator.
- Defaults source: `.ai-factory/config.yaml` (`testing=yes`, `logging=verbose`, `docs=yes`, `link_roadmap=true`, `milestone=auto`).

## Roadmap Linkage

Milestone: "M6 — Remaining V2 Capability Flags (in progress)"
Rationale: Configured `auto` linkage selects the first incomplete roadmap milestone, M6; this plan actually contributes to the later M7 generational-civilization goal and must not claim to complete M6 or own its remaining flag.

Related milestone: "M7 — V3 Generational Civilization (in progress)".
The roadmap itself is not changed by this command; any correction to automatic linkage belongs to the roadmap/configuration owner workflow.

## Goal and boundaries

Provide reusable primitives for proposing a shared course of action, expressing support or opposition, delegating a bounded preference, withdrawing support, and coordinating individual attempts. Track proposals, positions, influence, outcomes, compliance, and disagreement without installing democracy, monarchy, councils, elections, voting weights, quorums, binding majorities, or authoritative leaders.

**A collective decision is a revisable, locally understood course of action, not a new world permission.** Discussion can produce coordination, incompatible interpretations, refusal, abandonment, failed execution, or no decision. None is an error merely because consensus did not emerge. Repeated procedures may supply evidence to existing institution cognition later; this plan must neither manufacture institutions nor require office/institution cognition to be enabled.

### Architecture decision

Use a new owner-scoped `CollectiveDecisionLedger` under `agents.cognition`, with a locked `collective-decisions.v1` policy, and a bounded recipe over existing `CommunicationRelation` atoms transported by `Talk`/`Ask`/`Tell`. Do not add six world commands or an objective proposal/decision registry.

- Existing communication is recipient-scoped, **not** a broadcast to everyone colocated. Participants learn through their own delivered observations, memories, and further testimony. No silent widening of communication audiences.
- A shared proposal reference identifies a *claimed proposal lineage*, not a canonical social entity. Keep owner-local interpretation identity separate from originator/reference identity; provenance and source confidence remain explicit.
- Verified speaker/delivery fields prove who said something to whom, not that the proposal exists as described, that a third party endorses it, or that its terms are true.
- Coordinated execution emits one ordinary `AgentCommand` per actor/tick through existing runtime admission. WorldEngine alone adjudicates resources, movement, eligibility, death, project progress, and effects.
- No new world event, observation wire field, replay/codec marker, observer semantic type, protocol identifier, HTTP endpoint, SQL table, or Alembic revision is needed for this architecture.
- Runtime carry, in-memory checkpoint continuation/fork parity, and detached experiment export are in scope. Durable SQL restart and new API/debug projections of this ledger are explicitly out of scope; do not imply they already exist.
- Prepared subjective changes and post-objective finalization are not action-resolution or delivery receipts. Record attempted speech/action separately; confirm delivery/effects only from later owner-visible evidence. Detached analysis may inspect committed effects without feeding them back into cognition.

### Code-grounded baseline

| Concern | Current seam and constraint |
| --- | --- |
| Speech | `src/world/communications.py`: bounded `CommunicationContent` / `CommunicationRelation`, `communication.v1`, 32 relation/concept caps; no wire extension required. |
| Audience | `src/world/_perception.py::_project_communication`: sender/listener/private-recipient projection; do not modify for this feature. |
| Subjective precedent | `src/agents/cognition/offices.py`, `institution_concepts.py`, `structured_commitments.py`: owner-scoped immutable ledgers, evidence, update functions, communication hooks. |
| Planner | `src/agents/cognition/deliberation.py`: multi-criteria selection and sequential speech decorators; define explicit precedence rather than silently overwriting another mode's utterance. |
| Physical follow-through | `src/agents/cognition/collective_projects.py` and existing world commands; `OpposePublicGood` is potentially destructive and must never implement verbal opposition. |
| Runtime | `src/agents/cognition/models.py`, `loop.py`; `src/simulation/agent_runtime.py`, `run_control.py`, `runner.py`. |
| Configuration | `src/simulation/runner_models.py`, `runner_serialization.py`: current latest `runner-config-v50`, exact keysets and feature-specific version gates. |
| Cognition configuration | `src/agents/cognition/configuration.py`: cognition-owned modes/policies, validation, factory and fingerprint payload; runner composition translates simulation modes into cognition modes, never the reverse import. |
| Result transport | `src/simulation/runner_models.py::SimulationRunnerResult` and result construction in `runner.py`: collectors read completed result fields, not runner export methods directly. |
| Analysis | `src/analysis/offices.py`, `specifications.py`, `metric_service.py`; detached rows assembled through `src/experiments/collectors.py`. |
| Experiments | `src/experiments/offices_succession_scenario.py`, `catalog.py`, `matrix_schema.py`; next proposed experiment BH. |
| Checkpoint caveat | `tests/unit/test_offices_checkpoints.py` explicitly tests continuation, **not durable restart**; subjective SQL/inspection does not automatically carry newer ledgers. |

Current code pins: 43 closed commands, 73 observer semantic types, 119 metric families, latest objective channel pair replay-v22/codec `v20`, Alembic `0017`, default runner write `v4`. Earlier description/architecture paragraphs contain stale lower counts; use implemented contracts and tests rather than copying those counts. Existing conditional write-pair selection must remain unchanged, not globally forced to replay-v22.

## Domain contract

### Proposal and evidence

- A proposal contains stable owner-local identity; claimed originator/reference; a bounded revision identity; topic; observable context; proposed existing action/target/terms; optional finite tick window; and bounded evidence/revision history. Do not repurpose world `ProposalId` (authority-pipeline identity) for this subjective concept.
- Topics cover `collective_project`, `resource_allocation`, `migration`, `shared_defense`, `storage`, and `norm_enforcement`. These describe subject matter, never government types, jurisdictions, membership, or moral correctness. World IDs are referenced only when known through the owner's observations; unknown testimony references remain unresolved.
- Proposals originate from the owner's goals, feasible futures, observed opportunities, or interpreted testimony, not seed-specific names, fixture-agent roles, private peer state, or experiment truth.
- Distinguish draft, attempted speech, delivered speech evidence, perceived coordination, observed follow-through, and closure. Sending a draft or receiving a rejected command cannot fabricate delivered support.
- Preserve materially different revisions and competing proposals. Supporting an old revision does not silently endorse changed terms. Same visible label or similar topic is insufficient to merge proposals.
- Keep evidence order deterministic, cap all collections, expose pruning/partial-coverage metadata, and prevent eviction from resurrecting withdrawn support or replayed old speech (bounded tombstone/watermark policy).
- Lock finite actionable and evidence-retention horizons in `collective-decisions.v1`. Missing proposal windows receive a finite policy default; they never create indefinitely actionable support/delegation. Use engine-issued observation/provenance ticks and receiver first-seen ticks for admissibility, not speaker-declared timestamps. Retain deduplication/retraction state throughout the active reference horizon; if capacity would force early eviction of that protection, retire the affected reference and reject its reactivation through the horizon. After the horizon, old references/revisions remain non-actionable; renewed coordination requires a fresh proposal reference and fresh expression, not replay of the retired one. Never claim unlimited replay protection with finite state: reject references outside the admissible horizon or with insufficient freshness evidence, and report this exclusion explicitly.

### Six acts

| Act | Meaning | Does not mean |
| --- | --- | --- |
| `propose` | Offer bounded terms/action for a shared course. | Binding plan, known electorate, or command over others. |
| `support` | Speaker expresses a revisable position on an identified revision. | Resource contribution, irrevocable promise, vote, or guaranteed compliance. |
| `oppose` | Speaker expresses disagreement with those terms. | Sabotage, punishment, physical attack, or `OpposePublicGood`. |
| `delegate` | Speaker expresses a bounded, proposal/revision-scoped preference to follow another's recommendation. | Transfer of action tokens, items, permissions, autonomous proxy speech, office legitimacy, or added votes. |
| `withdraw_support` | Speaker retracts their own prior support or delegation, identified explicitly by reference. | Deleting history, changing someone else's position, or vetoing others' action. |
| `coordinate` | Suggest a bounded action/target/window and report a claimed course or outcome. | Binding resolution, automatic world execution, or proof that all recipients agreed. |

Delegate only one hop in this version; no transitive delegation, support multiplication, or cycles. A local explicit contrary position overrides delegated preference; expiry or withdrawal removes its behavioral influence. An absent, dead, unreachable, or unknown delegate cannot issue a new recommendation on another's behalf. Reports about third-party acts remain reports, not direct endorsements. Silence/absence is unknown, never consent or opposition.

### Positions, influence, outcomes, compliance, disagreement

- **Positions:** owner-relative assessments of each known actor's expressed stance, evidence channel, terms revision, uncertainty, and ordering. Own preference and observed expression are different fields. Direct and reported evidence remain distinguishable; conflicting evidence can remain unresolved rather than being globally adjudicated.
- **Influence:** retain bounded local decision-attribution records with source act, before/after classification, and evidence strength. Compare the same prepared candidate set under the same deterministic selection/planning rules with only the collective-decision preference/execution bias disabled; reuse already-prepared inputs rather than invoking cognition, memory, RNG, or providers again. Distinguish preference change, surviving final-command change, and later observed execution; if the final pipeline overwrites the choice, do not attribute that execution to the discarded decision. Report unavailable attribution when a side-effect-free comparator is unsupported. This is a local algorithmic comparison, not proof of real-world causal influence or an alternative historical trajectory. Social trust/recognized roles may influence appraisal only through existing owner-safe projections; no universal influence/power scalar or office-based veto. Exposure or endorsement counts alone do not establish influence.
- **Outcomes:** distinguish claimed course, locally adopted course, attempted execution, observed completion/failure, abandonment/expiry, disputed outcome, and unknown. A `coordinate` claim can be wrong. No numeric support threshold produces a binding winner; existing multi-criteria deliberation chooses the owner's action under safety/feasibility gates.
- **Compliance:** a descriptive match between an explicit actor-scoped supported/coordinated course and that actor's observable action within its window. Record match, observable contrary action, infeasible/blocked attempt, and unknown/no coverage separately. No obligation from mere receipt, no punishments or automatic sanctions, no moral classification. Death/unreachability/resource denial do not automatically count as defiance.
- **Disagreement:** preserve differences in terms, positions, proposed execution, and perceived outcomes; observers may disagree about whether agreement occurred. Cross-owner comparison is detached analysis only.
- **Temporal coverage:** distinguish a disabled channel from an enabled channel with zero proposals; export enabled-owner and observation-window coverage independently of ledger truthiness. Bounded final histories are partial unless complete retention is established. A run ending before the next delivery observation or before an execution window closes is right-censored, not failed/noncompliant. Detached objective effects can establish that an action occurred without establishing that a particular owner saw or accepted it. No final synthetic cognition tick or retrospective rewrite of owner beliefs is allowed.

### Topic execution adapters

Use a small typed allowlist mapping known terms to existing commands; this is an execution adapter, not a political procedure. Do not deserialize arbitrary commands from speech or invent unavailable physics.

| Topic | Allowed grounding/follow-through |
| --- | --- |
| Collective projects | Existing visible/legal project start/contribution and maintenance attempts. Support itself contributes nothing. |
| Resource allocation | Owner-controlled `Give` or existing exchange attempts involving explicitly identified known items/recipients. No common-pool controller or forced collection. |
| Migration | Existing observable route/destination and independently admitted movement/journey steps; no group teleport, border authority, or automatic roster migration. |
| Shared defense | Existing help, movement, warning communication, or other already-admitted protective choices. Do not introduce defense factions, armies, privileged attack rights, or new combat mechanics. |
| Storage | Existing storage/project and portable-item operations within current physical semantics; no virtual collective inventory or automatic storage ownership/access. |
| Norm enforcement | Discussion, refusal, warnings, and already-legal individual responses based on the owner's norm beliefs; no new police/court/sanction system or world-valid norm truth. |

Where the world does not expose enough evidence or a legal adapter for a term, retain the discussion with explicit `unsupported_action`/`unknown` execution status; do not fabricate successful allocation, defense, storage, or enforcement. Include at least project, item allocation, and migration end-to-end execution cases; exercise all six topics at contract/communication boundaries.

## Compatibility contract

1. Add `CollectiveDecisionMode` (`DISABLED`, `DETERMINISTIC`) and `AgentCognitionSpec.collective_decision_mode`, default disabled; this is not a capability flag. `institutional_economy` and `multi_hop_testimony_tracking` remain unowned/fail-closed.
2. Introduce `runner-config-v51` with exact cognition keyset `v50 ∪ {collective_decision_mode}` and the same root shape as its composable predecessor. Require at least one enabled collective-decision agent for v51; old schemas reject the new key and non-disabled mode. Entirely disabled compositions continue selecting their prior writer, default v4.
3. Widen applicable older-feature and initialization gates to accept v51 without relaxing historical exact keysets or allowing orphaned lifecycle/cultural/region siblings. Decisions work without offices/institutions, projects, or migration enabled; only relevant physical adapters require their channels.
4. Update schema selection/fingerprints and matrix composition consistently. Do not require an unrelated V3 flag solely to enable this cognition mode.
   - Add a cognition-owned mode/policy field and validation/factory/fingerprint handling in `src/agents/cognition/configuration.py`; translate from the simulation mode at runner composition. Disabled fields must preserve historical fingerprints on the existing compatibility path, rather than unconditionally changing all cognition fingerprints.
5. Disabled mode is a strict passthrough: no ledger, proposal generation, parsing influence, audit, changed command, extra objective state, or additional random-stream consumption.
6. No new automatic newborn knowledge/profile in this plan. Existing initialization profiles remain unchanged and decision-disabled; require explicit future initialization ownership before enabling this mode for admitted newborns.
7. No objective write-pair/count changes: commands 43, semantic types 73, Alembic `0017`, `communication.v1` and `observer-protocol-v1` unchanged. Analysis adds exactly three families, 119 → 122, as specified below.

## Commit Plan

- **Commit 1** (Tasks 1–3): `feat(cognition): add collective decision contracts and speech primitives`
- **Commit 2** (Tasks 4–6): `feat(simulation): integrate opt-in collective deliberation and continuation`
- **Commit 3** (Tasks 7–9): `feat(analysis): measure collective decisions in reproducible experiments`
- **Commit 4** (Tasks 10–12): `test(v3): enforce collective decision boundaries and document usage`

## Tasks

### Phase 1: Owner-scoped primitives

- [x] **Task 1: Define immutable proposal, act, position, and evidence contracts.**
  - Create `src/agents/cognition/collective_decisions.py`; export public types through `src/agents/cognition/__init__.py`. Define the six acts, six topics, proposal/revision reference, evidence channels, owner-local ledger, position/delegation/retraction records, lifecycle/outcome claims, influence attribution, and bounded policy (`collective-decisions.v1`). Keep authoritative world proposal identity separate.
  - Validate exact types, finite bounded numbers, nonnegative logical ticks, ownership, ordered detached tuples, reference ambiguity, and caps. Specify stable ID derivation from explicit seed/owner/evidence identities, not wall-clock, Python `hash()`, display names, or cross-owner state. Make reprs metadata-safe.
  - Define finite default proposal/action horizons, admissible reference freshness, deduplication/retraction retention, and fail-closed retirement under protection-cap pressure. Define enabled-owner/window coverage metadata independently of proposal count. Keep sender testimony timestamps separate from trusted observation/provenance ticks.
  - Add `tests/unit/test_collective_decision_contracts.py` including all six topics and malformed/foreign-owner inputs.
  - Logging: pure constructors need no payload logs; safe rejection codes at callers, DEBUG owner/tick/count metadata only. Test repr/log redaction.
  - Dependencies: none.

- [x] **Task 2: Implement deterministic owner-local updates and provenance discipline.**
  - In `src/agents/cognition/collective_decisions.py`, implement proposal generation from owner-visible opportunities and pure update/appraisal functions over the owner's `Observation`, previous ledger, owner-safe cognition inputs, and memory evidence only. Parse no researcher labels or arbitrary free text.
  - Implement explicit stance changes, revision-sensitive support, self-authored withdrawal, one-hop delegation, conflicting testimony, expiry, stable ordering, idempotence, and bounded eviction/tombstones. Separate self preference from delivered expression; do not count forwarded claims as independent actor support.
  - Enforce Task 1's finite reference/admissibility contract: reject expired/retired reference reactivation, preserve withdrawal protection through the active horizon, and keep uncertain freshness non-actionable. Freshly delivered retellings of an expired proposal do not reset its execution window or become fresh direct support. A new independently expressed position may use a new valid proposal reference; it must not silently resurrect the old one.
  - Add `tests/unit/test_collective_decision_updates.py` with duplicate/reordered/late messages, same-root repetition, forged third-party positions, retraction before support, pruning then replay, competing revisions/proposals, absent evidence, expiry, and deterministic property tests.
  - Logging: DEBUG update/skip transitions with owner, tick, counts and closed reasons; WARN only invalid external boundary data. Never log terms, propositions, relation tokens, or content fingerprints.
  - Dependencies: Task 1.

- [x] **Task 3: Encode/decode the six acts over existing recipient-scoped speech.**
  - Create `src/agents/cognition/collective_decision_communication.py` with a namespaced closed relation recipe, explicit policy marker, actor/proposal/revision/act references, bounded term/action relations, delegation target, and withdrawal reference. Keep within existing 32-atom limits and reject incomplete/ambiguous recognized recipes without failing unrelated conversation.
  - Use verified observed speaker identity for direct acts; payload actors and declared roots are not authentication. A relayed proposal/support is testimony, even if its atoms imitate the origin. References alone cannot mutate another actor's expressed position.
  - Specify the multi-tick handshake: planning emits a draft/attempt; committed speech appears in the sender/recipient's later `ObservedCommunication` and only then confirms expression to that audience. Correlate opaque evidence and proposal/revision references without importing action resolutions or objective events into cognition. Test a rejected speech attempt never confirms delivery, and stopping before the confirmation observation leaves it unknown.
  - Add `tests/unit/test_collective_decision_communication.py`: all acts round-trip, ordinary conversation unaffected, hostile/oversized/mixed recipes, actor spoofing, altered terms, recipients isolated, no broadcast, and legal world delivery rejected when ineligible. No changes to `src/world/communications.py` wire shapes or `_perception.py` audiences.
  - Logging: DEBUG encode/parse counts and safe reason codes, INFO none per message; redact all speech and identifiers derived from content.
  - Dependencies: Tasks 1–2.

### Phase 2: Opt-in cognition and execution

- [x] **Task 4: Add exact v51 configuration and mode composition.**
  - Update `src/simulation/runner_models.py`, `runner_serialization.py`, `compatibility.py`, public simulation exports where required, and `src/experiments/matrix_schema.py` for `RUNNER_SCHEMA_VERSION_V51`, the mode, exact keysets, selection, decoding, canonical fingerprints, and older-feature v51 allowlists.
  - Update `src/agents/cognition/configuration.py` with a cognition-owned collective-decision mode, locked policy validation/defaults, factory propagation, and fingerprint handling; translate runner mode/policy in `src/simulation/runner.py` as the existing office composition does. Cognition must not import the simulation mode. Extend cognition configuration/factory tests for direct composition, invalid mode/policy combinations, enabled fingerprints, and preserved historical disabled fingerprints.
  - Audit applicable office/institution/region/lifecycle/initialization validators and matrix selectors; retain exact v49/v50 and earlier acceptance behavior. Do not add a root decision spec or capability flag. Validate proposed BH/catalog identifiers are still unused before registration.
  - Add `tests/unit/test_runner_config_v51.py`: golden round-trip, unknown/missing fields, wrong enums/types, new key rejected by v50, v51 requiring an enabled agent, standalone decisions, mixed agents, composed office/institution/project/region modes, old writer selection, and unchanged default v4 bytes. Extend relevant compatibility/matrix tests.
  - Logging: INFO selected schema/mode counts at composition; DEBUG validation codes; errors expose codes, not config payloads.
  - Dependencies: Task 1.

- [x] **Task 5: Wire deliberation, influence attribution, and legal follow-through.**
  - Update `src/agents/cognition/models.py`, `loop.py`, `deliberation.py`, and create `src/agents/cognition/collective_decision_actions.py` for the allowlisted topic adapters. Inject policy/mode at composition, carry prepared ledger through proposal/result contracts, and apply only bounded preferences within existing feasibility/critical-veto/multi-criteria selection.
  - Implement autonomous proposal/stance/coordination opportunities and recipient selection grounded in owner goals/evidence. Define/test deterministic speech precedence with naming, translation, institution, office, norm, and convention decorators: one selected utterance, no lost/overwritten chosen act and no compound hidden extra commands. Never replace unrelated urgent survival behavior with mandatory discussion.
  - Use explicit proposal/revision/action scope; record whether evidence actually changed a choice. Execute one fresh allowed command through normal runtime admission; no arbitrary command decoding from relations. Keep support/opposition/delegation separate from physical attempts.
  - Add a side-effect-free decision-bias-disabled comparator over the same prepared inputs/candidates, with stable tie-breaking and no extra RNG/provider/memory calls. Retain separate preference-change and final-command-change attribution, and a closed unavailable reason when a planner cannot provide that comparison. Do not describe sequential before/after observations alone as causal evidence.
  - Reconcile proposed speech and execution attribution against the **final** compiled command after all late replacements: narrative and office speech, artifact inscription, possession, commitments, exchange, collective projects, and public goods. Make precedence explicit and limited to decisions-enabled behavior; do not refactor unrelated mode-off ordering. An overwritten act is deferred/cancelled, never emitted; an overwritten action is not credited as executed. Preserve unrelated urgent-action protections through the final command, not only initial selection.
  - Add `tests/unit/test_collective_decision_planning.py`: evidence changes a nonurgent choice, survival veto still wins, delegate advice can be refused, support can fail to lead to action, withdrawn support loses bias, discussion without execution, all six topic adapters, and project/allocation/migration follow-through. Assert `oppose` never emits `OpposePublicGood` or coerces third parties.
  - Exercise real planner composition with a late artifact/commitment/project replacement; assert ledger/audit classification matches the final command. Assert comparator calls consume no extra random draws, provider requests, or memory writes, and that preference change without final-command change is not counted as execution influence.
  - Logging: DEBUG source-act/action-class/choice-change and safe blocked reasons; no global power scores or policy payloads in logs.
  - Dependencies: Tasks 2–4.

- [x] **Task 6: Finalize runtime state and checkpoint/fork continuation safely.**
  - Update `src/simulation/agent_runtime.py`, `run_control.py`, `runner.py`, and `src/agents/cognition/models.py` for owned carry, prepared/finalized ledger handling, empty initial state, exact-type validation, and detached `export_collective_decision_ledgers()` in registration order.
  - Add ordered, defensively detached `collective_decision_ledgers` to `src/simulation/runner_models.py::SimulationRunnerResult`, validate exact ledger types/unique ownership, and populate it in `runner.py` result construction. Export mode-enabled owners and covered windows even when their ledgers contain no proposals; disabled owners remain absent. This is an internal detached result addition, not new fields on the versioned summary `SimulationRunnerResultDocument` or a promise of durable ledger serialization.
  - Follow existing runtime finalization semantics: failed admission/delivery cannot become delivered position evidence, pending subjective finalization is idempotent, and retries do not generate duplicate proposals/influence. Keep requested actions distinct from later observed results. Disabled mode carries/exports no decision state and rejects incompatible restored nonempty state rather than silently importing it.
  - `finalize_pending()` has no action-resolution receipt: commit observed-input appraisal and reconciled attempt state only, never promote it to delivered/effected because finalization ran. Confirmation comes from the next eligible owner observation; no confirmation is fabricated for terminal actors or a run ending at that boundary. Retry guarantees here concern the in-process pending object/checkpoint path, not durable `FinalizationCommand` rehydration, which does not carry the new ledger.
  - Add `tests/unit/test_collective_decision_checkpoints.py` and runtime cases for uninterrupted vs restored continuation, detached divergent forks, mixed-owner/order rejection, terminal/absent actors, failed submission/finalization retry, expiry across restore, and disabled-state absence. Explicitly label these **not durable restart** tests.
  - Leave `src/persistence/subjective_sqlalchemy.py` and SQL/debug projection contracts unchanged; do not claim support through the general subjective SQL service. Existing newborn profiles stay decision-disabled.
  - Logging: DEBUG owner/tick/state counts at prepare/commit/restore, INFO export/restore totals, safe WARN mismatch codes. Test no ledger content leaks.
  - Dependencies: Tasks 4–5.

### Phase 3: Read-only evidence and reproducible experiments

- [x] **Task 7: Track outcomes/compliance without manufacturing agreement.**
  - Extend `src/agents/cognition/collective_decisions.py` and the loop hook for owner-visible outcome/compliance appraisals with explicit windows, actor/action/target/revision matching, evidence IDs, observed vs reported status, and partial coverage. Unsupported terms remain unresolved.
  - Add detached row harvesting in new `src/analysis/collective_decisions.py`: proposal, position, attribution, course claim, observed attempt/effect, compliance opportunity, and disagreement evidence. Accept exported immutable subjective rows and public detached objective evidence only; no runtime imports into analysis and no analysis inputs to cognition.
  - Specify matching predicates for the supported adapters; resource transfer/project completion/movement require matching existing event effects in analysis, never just the speech or intended command. Speech reports and objectively evidenced outcomes may disagree.
  - Preserve source ticks, first/last covered observations, proposal/action windows, pruning bounds, and final-command attribution in detached rows. Keep subjective delivery/effect confirmation separate from objective matching. Define eligibility and right-censoring for run end, death, missing future observations, and still-open action windows; these are unknown/partial coverage, not negative outcomes. Cap exports explicitly and report discarded history rather than claiming full-run counts from final snapshots.
  - Add `tests/unit/test_collective_decision_outcomes.py` for genuine matching/contrary behavior, wrong actor/target/revision/window, failed/infeasible action, death, no visibility, misleading success claims, and disagreement on the same delivered proposal. Missing evidence must not become noncompliance.
  - Logging: DEBUG appraisal classification/count/coverage reason; INFO harvest counts only. Never log action terms or norms.
  - Dependencies: Tasks 5–6.

- [x] **Task 8: Register three analytical metric families with explicit denominators.**
  - In `src/analysis/collective_decisions.py`, `specifications.py`, `metric_service.py`, and public exports, add exactly:
    - `collective_decision_process@1`: proposals/revisions, direct vs reported positions, withdrawals/delegations, coordination, and evidence-attributed preference/action changes; influence is not delivery frequency.
    - `collective_decision_outcomes@1`: claimed/adopted/attempted/effected/abandoned/disputed courses plus matched, contrary, blocked, and unknown compliance opportunities.
    - `collective_decision_disagreement@1`: within-owner contradictory evidence and detached cross-owner position/terms/outcome disagreement on aligned proposal revisions; silence is excluded, not dissent.
  - Align cross-owner rows by supported origin/proposal/revision evidence with ambiguity exclusions; no label-only alignment or canonical electorate. Report coverage, eligible denominators, unknown/excluded/pruned counts, deterministic quantization, provenance, and unavailable vs zero distinctly. No causal claim beyond recorded attribution; causal treatment effects belong to paired experiments.
  - Define metric input presence from enabled-owner/window metadata, not `if ledgers` or nonzero proposal counts: disabled is unavailable; enabled, fully covered, zero opportunities is an explicitly covered zero where the metric permits it; zero eligible denominators yield unavailable rates, not invented zero rates. Pruned histories are partial, and right-censored opportunities are excluded from matched/contrary rates with separate counts. Count preference change, final-command change, and observed execution separately using Task 5's comparator; unsupported comparison is unavailable, never inferred from message exposure.
  - Update `src/experiments/collectors.py` and related detached result assembly to collect post-run data; include all six requested tracking dimensions. Change metric-family pin 119 → 122 and only directly affected catalog assertions.
  - Add explicit optional collective-decision evidence inputs to `MetricComputationInputs` in `src/analysis/metric_service.py`, and connect Task 6's `SimulationRunnerResult` fields through collectors into those inputs. Test both immutable ledger exports and detached snapshot-equivalent inputs, including disabled, enabled-empty, pruned, and censored cases. A unit test of the harvester alone does not prove this transport works.
  - Add `tests/unit/test_collective_decision_metrics.py`; extend `tests/unit/test_metric_specifications.py`. Hand-computed fixture numerators/denominators must include a real disagreement, failed attempt, and unknown coverage, not tautological structure-only assertions.
  - Logging: INFO family/row/coverage totals, DEBUG exclusions with closed reasons; no cross-owner payload logs or cognition feedback.
  - Dependencies: Task 7.

- [x] **Task 9: Add off-gate Experiment BH with meaningful controls.**
  - Create `src/experiments/collective_decisions_scenario.py`; register `collective_decisions@1` / Experiment BH in `catalog.py` and relevant command/catalog exports, with tests in `tests/unit/test_experiment_bh.py`.
  - Include unchanged v4 baseline; a comparable decisions-off composed control on its legal prior schema; decisions-on v51; and decisions-on under a physically/evidentially restricted discussion condition (e.g. reduced delivery opportunity). V51 is not legal for an all-decisions-disabled arm under Task 4's contract. Keep non-treatment factors/seed-derived identity paired where possible; state remaining confounds rather than labeling a multi-factor contrast causal.
  - Offer observable project, allocation/storage, and migration opportunities and individual competing needs. Do not seed opinions, factions, delegates, winners, institutional roles, successful decisions, or preferred compliance outcomes. Optional institution-mode composition is a separate contrast; neither offices nor institutions are prerequisites.
  - Assert reproducible schemas/fingerprints/trajectories, owner isolation, all tracking exports, disabled-arm absence, correct partial-coverage semantics, and legal attempts. Use deterministic focused fixtures to exercise all six acts and both compliance/disagreement cases; autonomous experiment acceptance must allow no consensus, no institution, and zero proposals when no opportunity exists. Do not force rare emergence just to satisfy the arbiter.
  - Include a real multi-tick sender → engine delivery → recipient observation/update → planned ordinary action → committed effect → collector metric test. Exercise all six acts through the public update/communication path, not just enum constructors; assert one hand-computed influence/position change and actual disagreement/blocked/unknown outcome classifications. Use real runtime checkpoint export/import for continuation evidence and pin a concrete pre-change baseline trajectory hash using the coordinator-materialized run identity. Add run-ending-before-confirmation and history-cap cases without forcing autonomous emergence.
  - Logging: INFO arm/agent/tick/mode counts and safe collection summaries; DEBUG availability/exclusion reasons, no agent propositions or scripted success labels.
  - Dependencies: Tasks 4–8.

### Phase 4: Boundaries, documentation, and gates

- [x] **Task 10: Enforce scientific isolation and nonpolitical semantics.**
  - Create `tests/architecture/test_v3_collective_decisions_isolation.py`; extend only directly relevant scaffolding/scientific invariant tests. Assert cognition cannot import events/stores/private world/analysis/persistence, and analysis exports cannot feed runtime decisions. Public facade imports only across bounded packages.
  - Add behavioral/noninterference tests in `tests/unit/test_collective_decision_invariants.py`: peer-private state perturbations do not affect another owner's output without a delivered/observed channel; duplicate/forged endorsements do not manufacture support; delegation does not multiply agency; withdrawal does not erase evidence; mode-off byte/trajectory parity; iteration-order/seed stability; caps and expiry through checkpoint/fork.
  - Demonstrate no objective government, electorate, office power, mandatory quorum, automatic resource redistribution, coercive migration, scripted institution, new sanctions, or broadcast. Existing institution concepts may receive only ordinary owner-visible repeated-procedure evidence; never promote a decision tally to an institution or office. Test decisions work with both modes disabled.
  - Logging: tests capture/redact proposal text, relation atoms, memory/norm content and content-derived fingerprints; runtime DEBUG stays limited to allowlisted metadata. Architecture tests add no noisy new runtime logger.
  - Dependencies: Tasks 1–9.

- [x] **Task 11: Document configuration, epistemic limits, and reproduction via `/aif-docs`.**
  - Update relevant sections of `docs/configuration.md`, `docs/cognition-runtime.md`, `docs/social-communication.md`, `docs/architecture.md`, `docs/experiments.md`, and `docs/development.md`; add a focused `docs/collective-decisions.md` and README index link if needed for readability.
  - Document all six acts/topics; recipe/policy; v51 opt-in and older writer compatibility; positions vs physical execution; one-hop nonbinding delegation; private audiences; disagreement/failed outcomes; metric denominators; BH reproduction; and explicit checkpoint-only, no SQL-restart/debug-API claims. Explain repeated procedure evidence can later contribute to institution concepts without defining political systems.
  - Document attempt-versus-next-observation confirmation, final-command reconciliation, finite replay/admissibility horizons, local comparator attribution limits, enabled-empty vs disabled data, and pruned/right-censored coverage. Do not label the internal runner-result ledger field as a serialized summary or durable export format.
  - Restrict stale-count corrections to touched relevant sections (119 → 122 families, current v50 → v51 extension); no broad historical docs cleanup, roadmap edits, or new infrastructure.
  - Logging: documentation must show safe metadata examples and `PALIMPSEST_LOG_LEVEL`; no real proposition/prompt/payload examples in operational logs. No new logging solely for docs.
  - Dependencies: Tasks 8–10.

- [x] **Task 12: Run the focused and full implementation acceptance gates.**
  - Execute the new suites and affected v49/v50/BF/BG, communication, project, migration, runtime, metric, matrix, configuration, checkpoint, and initialization suites first, preserving coverage. Run full unit/architecture, Ruff, mypy, import-linter, V1 regression, V2 scientific invariants, compatibility and Alembic pins afterwards. Fix regressions within the listed implementation/test files; do not weaken unrelated tests/count expectations.
  - Check default v4 and existing accepted-version encodings/trajectories unchanged; conditional objective replay/codec selection unchanged; commands 43; observer semantics 73; metric families 122; Alembic `0017`; protocol unchanged; unowned flags still fail closed. Exercise composed decisions-on live/restored observation parity and one-command admission.
  - Re-run paired BH from the same seeds and compare canonical exports, scientific metrics, and objective trajectories where claimed. Verify speech can influence a choice, noncompliance/disagreement can persist, and no successful collective outcome is required to pass.
  - Logging: retain bounded test/lint summaries and safe failing assertion/reason codes; never dump config, utterance, ledger, event-store or excluded artifact payloads. Mark checks complete only after running them; record blockers inline in this plan, not as a new report artifact.
  - Dependencies: Tasks 10–11.

## Verification commands

Run focused suites by their explicit new/affected filenames before the full gate; do not disable the configured coverage instrumentation.

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_runner_config_v51.py tests/unit/test_collective_decision_contracts.py tests/unit/test_collective_decision_updates.py tests/unit/test_collective_decision_communication.py tests/unit/test_collective_decision_planning.py tests/unit/test_collective_decision_checkpoints.py tests/unit/test_collective_decision_outcomes.py tests/unit/test_collective_decision_metrics.py tests/unit/test_collective_decision_invariants.py tests/unit/test_experiment_bh.py tests/architecture/test_v3_collective_decisions_isolation.py -q
uv run --frozen --python 3.12.14 pytest tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/unit/test_compatibility_matrix.py tests/unit/test_alembic_head_pin.py -q
uv run --frozen --python 3.12.14 pytest
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src tests
uv run --frozen --python 3.12.14 lint-imports
```

## Acceptance checklist

- All six acts and all six topics have typed, bounded, provenance-aware behavior; proposal generation and actual preference/action influence are exercised, not merely parsed.
- Proposals/positions/influence/outcomes/compliance/disagreement are exported with explicit uncertainty and coverage; dissent, withdrawal, failure, and no decision are legal results.
- Cognition-owned configuration is translated at runner composition; the detached result field reaches actual collectors/metric inputs, including enabled-empty channels.
- Final-command attribution survives late planner replacements; finalization alone never confirms delivery, and comparator evaluation adds no RNG/provider/memory side effects.
- Reference freshness/retraction protection has finite fail-closed retention rules; pruned histories and run-end confirmation/action windows report partial or right-censored coverage rather than false noncompliance.
- No majority, quorum, government/office privilege, collective inventory controller, forced actions, or hard-coded political institution has been introduced.
- Each actor still emits one ordinary admitted command; delivery proves speech only; claimed outcomes can differ from physical effects.
- Mode-off is unchanged; v51 is exact and composable; old schema acceptance and channel-based replay identities remain intact.
- Continuation/forks preserve bounded owner state without claiming durable database restart support.
- BH and three analytical families are reproducible and off the V1 gate; institution emergence remains optional and unscripted.
- Documentation checkpoint and verification gates complete before implementation is declared finished.

## Verification Results (2026-10-20)

- Focused collective-decision/configuration/architecture suites: `89 passed`
  (contracts, updates, communication, planning, checkpoints, outcomes, metrics,
  invariants, v51 configuration, Experiment BH, isolation).
- Regression pins: `50 passed` (`test_v1_regression_gate`,
  `test_v2_scientific_invariants`, `test_compatibility_matrix`,
  `test_alembic_head_pin`, `test_v2_golden_runner_configs`,
  `test_metric_specifications`).
- Full default suite: `4920 passed, 104 deselected` after updating established
  metric-family pins 119 -> 122.
- `ruff check src tests`: passed.
- `ruff format --check` on all touched Python files: passed.
- `mypy` on all 24 touched source files: passed.
- `lint-imports`: `25 kept, 0 broken`.
- Final pins: runner max `runner-config-v51`, default write `runner-config-v4`,
  metric families `122`, commands `43`, observer semantic types `73`, replay
  `EVENT_SCHEMA_REPLAY_V22`, codec `v20`, Alembic `0017`, Experiment BH
  (`collective_decisions@1`). Flags-off baseline fingerprint matches the
  previously pinned `85c14cdb...` bytes; older golden configurations unchanged.
- Checkpoint tests cover runtime checkpoint objects and forks, not durable
  process restart. No new command, event, observer semantic type, wire field,
  SQL table, migration, or newborn profile was added.

## Remediation After Verification (2026-10-20)

Closed the five verification blockers:

- Runtime influence attribution now records `preference_changed` /
  `final_command_changed` rows when the decision bias changes the candidate
  directions; unchanged candidates and overwritten commands are not credited.
- Final-command reconciliation uses the effective command in
  `CognitiveLoop.complete`, after late replacements, with explicit tests.
- Checkpoint coverage adds foreign-owner rejection, duplicate-owner rejection,
  idempotent re-apply, and expiry across restore.
- Detached analysis now joins committed effect rows to supported course
  windows (`objective_effect_count` / `objective_matched_count`) and the
  collector transports them.
- Experiment BH pins the v4 baseline exact trajectory hash
  `e8ab165eef7883405724f5a0260d88ffca47f19e62a00d85ac79668fe515f359` and adds
  a multi-stage delivery → support → preference → allowed action → effect →
  metric fixture.

Re-verified: focused suites `115 passed`; full default suite `4929 passed, 104
deselected`; `ruff check src tests` passed; all touched Python files formatted;
`mypy` on 12 changed source files passed; `lint-imports` `25 kept, 0 broken`.

### Follow-up (autonomous bootstrap)

- Enabled owners now generate one bounded local proposal from owner-visible
  opportunities when no actionable proposal exists, then reuse it instead of
  flooding the ledger. This provides the missing empty-ledger bootstrap through
  the same public communication/update path.
- Re-verified after the bootstrap: full default suite `4930 passed, 104
  deselected`; focused decision/BH suites `24 passed`; `ruff check` passed;
  touched files formatted; `mypy` passed; `lint-imports` `25 kept, 0 broken`.

### Warning closure

- Added a live multi-tick `WorldEngine` delivery test: sender proposes through
  an engine-admitted `Talk`, the recipient updates its local ledger, replies
  with structured support, and the sender receives and records that position.
- Added a terminal-actor checkpoint test: a terminal runtime retains its
  decision ledger and does not fabricate delivery/compliance confirmation.
- Retry behavior is covered by the existing idempotent checkpoint re-apply test.
- Final re-verification: full default suite `4932 passed, 104 deselected`;
  `ruff check` passed; all touched Python files formatted; `mypy` passed;
  `lint-imports` `25 kept, 0 broken`.
