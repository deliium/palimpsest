# Implementation Plan: V3-32 Conflict Mediation

Branch: `main` (planning only; no branch creation)
Created: 2026-10-20
Refined: 2026-10-20 — exact restitution compilation, concrete authority projections, role bootstrap and update ordering, preflight restore validation, metric correspondence, and pre-change baseline evidence. Second pass: documentation coverage, metric-pin sweep, BI naming/schema legality, speech-wire and mixed-mode boundaries, result-transport and compatibility-scope clarity.
Canonical plan: `.ai-factory/plans/v3-32-mediation.md`
Mode: full

## Settings

- Testing: yes — contracts, properties, communication, runtime continuation, architecture, experiments, and regressions.
- Logging: verbose — metadata-only DEBUG transitions, INFO composition/collection counts, safe WARN rejection codes; controlled by `PALIMPSEST_LOG_LEVEL`.
- Docs: yes — mandatory `/aif-docs` checkpoint during implementation.
- Git: enabled; `git.create_branches: false`; retain current branch and existing work.
- Defaults: `.ai-factory/config.yaml`: testing=yes, logging=verbose, docs=yes, link_roadmap=true, milestone=auto.
- Scope: optional subjective third-party conflict mediation, not adjudication, law, or compulsory settlement.

## Roadmap Linkage

Milestone: "M6 — Remaining V2 Capability Flags (in progress)"
Rationale: Configured `auto` selects the first incomplete milestone, M6; mediation actually contributes to M7 and must not claim to complete M6 or own its remaining capability.

Related milestone: "M7 — V3 Generational Civilization (in progress)".
Do not edit the roadmap or configuration to correct this linkage during this task.

## Goal and architecture

Let agents recognize disputes involving other agents, hear competing accounts, offer compromises, vouch, mediate, and recommend voluntary restitution. Each participant independently interprets the dispute, evaluates the mediator, and chooses whether to respond or act. Refusal, ignoring, unresolved disagreement, partial settlement, and renewed conflict are valid outcomes.

Use an immutable owner-scoped `MediationLedger` in `agents.cognition`, locked policy `mediation.v1`, and bounded namespaced relations inside existing `Talk`/`Ask`/`Tell`. The six acts are social reasoning/speech primitives, not six additional world commands. No `Judge` profession, predefined mediator class, court, jurisdiction, verdict, privileged action, or global dispute/settlement registry is introduced.

- WorldEngine remains sole objective mutation authority. Speech delivery proves speech, not truth, consent, settlement, or legitimacy.
- Cognition sees only its own immutable observation, prepared retrieved memories, and owner-safe subjective projections. Never read another agent's accounts, relationships, beliefs, or ledger directly.
- Shared dispute references identify claimed lineages; owner-local interpretation identities remain separate. A common reference or label is not proof that observers describe the same conflict.
- Communication remains recipient-private, not a broadcast. Learning both accounts requires actual opportunities and separate deliveries; refusal and inaccessible participants remain possible.
- Physical follow-through uses existing individually admitted commands. A mediator cannot transfer another's property, collect restitution, impose commitments, or execute another actor's action.
- Runtime carry, in-memory checkpoints/forks, and detached experiment export are in scope. Durable SQL restart, new API/debug projections, observer UI work, and migrations are not.

### Code-grounded baseline

| Concern | Existing seam |
| --- | --- |
| Subjective ledger/update pattern | `src/agents/cognition/collective_decisions.py`, `offices.py`, `institution_concepts.py` |
| Speech recipe | `collective_decision_communication.py`; existing `world.communications` caps relations at 32 |
| Roles | `OfficeFunction.CONFLICT_MEDIATION`, `OfficeDutyKind.MEDIATE`; authority remains a private belief |
| Social appraisal | `reputation.py`, `social_norms.py`, directed relationships in cognition snapshots |
| Configuration | `src/simulation/runner_models.py`, `runner_serialization.py`; latest schema v51 |
| Cognition composition | `configuration.py`, `contracts.py`, `models.py`, `loop.py`, `deliberation.py` |
| Runtime/export | `src/simulation/agent_runtime.py`, `run_control.py`, `runner.py`, `runner_models.py`, `perception.py` |
| Detached measurement | `src/analysis/collective_decisions.py`, `offices.py`, `specifications.py`, `metric_service.py` |
| Collection/catalog | `src/experiments/collectors.py`, `collective_decisions_scenario.py`, `catalog.py`, `matrix_schema.py` |

Current pins: 43 commands, 73 observer semantic types, 122 metric families, replay-v22/codec `v20` for the latest active objective channel, Alembic `0017`, default runner writer v4. Preserve conditional historical write-pair selection rather than forcing the latest pair globally. Proposed unused additions are runner-config-v52 and Experiment BI; recheck availability before implementation.

## Domain contract

### Disputes, accounts, and recommendations

- A case stores stable owner-local identity, claimed dispute reference/origin, known parties (at least two distinct others for a third-party mediation attempt), subject/context, bounded account/recommendation revisions, finite action windows, evidence provenance, and uncertainty. Hearing/reporting a dispute does not require every party to be known or present; unresolved identities make targeted intervention non-actionable.
- Cases arise from owner-visible conflicting claims, incompatible intentions, observed contention, or recalled evidence, not researcher scenario labels, names, preloaded conflicts, or access to peer state. Support at least item allocation/possession, commitments, and project/resource contention where existing evidence is available; do not invent combat or law mechanics.
- Accounts are attributed assertions with direct-versus-reported basis, receiver first-seen tick, trusted observation provenance, optional opaque occurrence references, and explicit contradictions. They are never authoritative findings of fault. Requests cannot compel answers or expose private memories.
- Recommendation revisions identify proposed actor/action/known targets and bounded terms/window. Acceptance is actor- and revision-specific; no retroactive acceptance when terms change. Competing recommendations and disputed settlement claims may coexist.
- Distinguish awareness, attempted inquiry, delivered account, proposed terms, expressed response, attempted follow-through, observed effect, and claimed/observed closure. A prepared cognition result is not a delivery or action receipt.
- Case state may remain unresolved, partially addressed, declined, expired, abandoned, apparently settled, disputed, or reopened. Reopening requires fresh owner-visible evidence, not replay of stale recommendations.
- All collections and histories are bounded with deterministic ordering, finite reference/admissibility horizons, pruning counters, and partial-coverage metadata. Retain deduplication/revision protection through actionable windows; retire a reference if caps cannot preserve that protection. Speaker timestamps do not refresh old authority or replayed consent. No claim of infinite replay protection with finite state.

### Six supported acts

| Act | Meaning | Explicit non-effect |
| --- | --- | --- |
| `hear_dispute` | Attend to an owner-visible dispute/account and optionally acknowledge it. | No omniscient discovery, summons, compulsory hearing, or acceptance of the account as true. |
| `request_accounts` | Ask a reachable party for its attributed account about an identified case. | No forced reply, private-state read, or automatic account from an absent party. |
| `propose_compromise` | Suggest bounded revised terms for independently chosen actions. | No agreement, binding allocation, or silent acceptance by other parties. |
| `vouch` | Attribute one's own bounded endorsement of a person, account, or proposed undertaking with evidence basis. | No truth certificate, guaranteed performance, copied reputation, or endorsement by the named third party. |
| `mediate` | Offer or continue third-party facilitation and relay attributed competing positions. | No verdict, casting vote, global resolution, or permission to control participants. |
| `recommend_restitution` | Suggest a voluntary actor-specific restorative action using existing affordances. | No authoritative debt, fine, culpability finding, forced transfer, or automatic structured commitment. |

Account replies, acceptance, refusal, deferral, withdrawal, and settlement claims use a closed bounded response/status recipe associated with these acts, not extra world commands. Verified observed speaker establishes who expressed a direct response; a mediator's report that another party accepted remains testimony. Silence is unknown, not consent or refusal. Ignoring is a legal behavioral choice; analysts must distinguish observable non-uptake from unobservable motive.

Lock the response vocabulary in `mediation.v1`: `account`, `accept`, `refuse`, `defer`, `counterpropose`, `withdraw`, and `claim_settlement`. Bind each response to case and, where applicable, recommendation revision and the speaker's own proposed undertaking. Counterproposals create new terms/revisions, never mutate another actor's accepted undertaking. Account replies carry attributed bounded claims, not private memory objects. Partial acceptance must name the accepted undertaking; it does not accept an entire multi-party package or establish bilateral agreement.

Keep role-directed expressions separate from recommendation responses: `invite_mediator`, `endorse_role`, and `withdraw_role_endorsement` are bounded auxiliary relations associated with a mediation act, not extra world commands or mandatory stages. They name the function/context and relevant actor; endorsement by a named third party is direct only when that party is the verified speaker. An invitation is evidence of requested assistance, not necessarily enduring role endorsement. Define a maximum-size valid recipe within the existing atom/token caps and a deterministic overflow fallback that emits no truncated actionable recommendation or false response.

### Authority appraisal and participant autonomy

Maintain evidence-backed, recipient-relative appraisal rather than a universal authority score or automatic role privilege:

1. **Relationships:** the recipient's directed trust, familiarity, affinity and relevant relationship dimensions toward mediator/parties; do not symmetrize.
2. **Reputation:** recipient-held reputation by relevant function and provenance, with uncertainty and same-root deduplication; a vouch is testimony, not an automatic positive award.
3. **Accepted roles:** the recipient's actual recognition/endorsement of a facilitation role and expected duties; neither a mediator's self-claim nor an `OfficeFunction` enum grants acceptance.
4. **Norms:** recipient-held expectations concerning procedure, reciprocity, account-taking and restoration; no universal fairness rule or world-valid norm.
5. **Institutional beliefs:** recipient-held legitimacy/procedure beliefs, including contested or absent legitimacy; no world institution registry.

Project these through a small immutable owner-safe appraisal contract; missing/disabled sources stay unavailable, not fabricated approval. Mediation works without office, institution, reputation, or norm modes enabled; those modes enrich appraisal when available. Preserve component provenance and dissent rather than collapsing everything into binding social rank.

Use actual source shapes rather than speculative common attributes. `ReputationProfile` has target-scoped `reliability`, `harm`, `generosity`, and `competence` dimensions, not function-indexed reputation; preserve their independence and evidence basis. Match `NormBelief.pattern`, `expectation`, `context`, `status`, and counterpart scope explicitly to the recommendation/procedure. Match an `OfficeConcept` by function, context, occupant/supporter evidence and recognition status. `InstitutionConcept` provides `group_key`, anchors, evidence and six pattern strengths, not a mediator/office field: require a documented owner-evidenced contextual link before using its legitimacy/procedure channels. An unrelated recognized institution, norm, or office must not increase mediator appraisal. Unresolvable links remain unavailable; do not invent broad authority or rewrite source ledgers to manufacture a match.

Recipients use these factors with their own goals, evidence, feasibility and existing critical vetoes. They may accept some terms, counterpropose, defer, reject, ignore, withdraw, or comply for reasons unrelated to mediation. Accepted roles/norms/institutions bias deliberation only; no configured factor forces acceptance. Repeated mediation does not automatically create a role, and apparent success does not automatically award reputation.

### Voluntary follow-through and role emergence

- A typed allowlist compiles only the acting owner's selected recommendation into an existing legal action, initially owner-controlled `Give` of known items, ordinary communication, and supported project contributions. Unsupported terms remain discussion with `unsupported_action`/unknown follow-through; never deserialize arbitrary commands or invent repayment physics.
- Compile a selected undertaking through a recommendation-specific typed path that preserves its exact actor, recipient, item/project, quantity or other supported terms, revision and window. Do not implement `Give` by merely biasing `ActionDirection.FEED`: the current generic feasibility path checks for food/water and its compiler emits `Feed`, not `Give`. An unsupported term is non-actionable rather than silently replaced by another item, target, care action, project, or arbitrary feasible command. Reconcile the emitted final command after all late exchange/project/artifact decorators before recording an attempt or attribution.
- Recommendations do not bypass feasibility, custody, colocation, survival priorities, admission, lifecycle or project capability gates. One actor emits one final command per tick. A blocked or superseded attempt is not refusal or fulfilled restitution.
- Track local offer/acceptance/recognition evidence across distinct disputes and ticks. Existing office cognition may receive neutral owner-visible mediation-function evidence, never a fabricated `mediated` world event or an automatic success tag. Explicit endorsement can ground a role expectation; repeated self-claims and same-root retellings cannot manufacture independent recognition.
- Keep recurring activity, repeated selection by others, accepted responsibility/expected duties, stable recognized role, and institutional legitimacy distinct. Existing office/institution modes may form revisable beliefs from sufficient evidence; stable-role analysis must not create these beliefs or enable their modes.
- If reporting local influence, compare the same prepared candidates with mediation bias removed without extra recall, RNG, provider calls, or alternative world execution. Record whether the difference survives final command composition; unavailable comparisons remain unavailable, not causal proof.

#### Recognition bootstrap and stage ordering

Existing office speech requires an already-recognized office, and the current office parser consumes office-specific predicates; the unused `mediated` occurrence mapping is not a mediation implementation. Provide a small owner-scoped adapter from delivered mediation-function and role-directed evidence to the existing office update seam. Function evidence establishes that facilitation was offered/performed as observed or reported, never that it succeeded; preserve these distinctions and source roots. A first valid invitation/endorsement must be consumable before any office is recognized. Do not depend on `office_communicate_utterance` to bootstrap it.

At tick preparation, first extract neutral evidence from the current owner's delivered observation and already-prepared recall, then update existing optional institutional/office recognition once from admissible prior/current evidence, then project authority and prepare mediation deliberation. Newly planned mediation, self-evaluated success, and emitted-but-not-yet-observed speech cannot feed same-tick recognition. If institutional integration uses a later recognition result, defer that input to the next snapshot rather than iterating these stages to a self-confirming fixed point. Deduplicate the same evidence if it also appears through recall or an auxiliary office relation. Disabled modes remain unallocated. Test the bootstrap using public delivery/update paths, not a preconstructed recognized ledger.

## Compatibility contract

1. Add simulation-owned `MediationMode` and cognition-owned equivalent (`DISABLED`, `DETERMINISTIC`), per-agent `mediation_mode`, and locked policy `mediation.v1`. Translate at runner composition; cognition never imports simulation configuration.
2. Add exact `runner-config-v52` cognition keyset `v51 ∪ {mediation_mode}` with existing composable root shapes; require at least one enabled mediation agent. Historical schemas reject the new key/non-disabled mode. Disabled compositions retain their prior writer and historical fingerprints, including default v4 bytes.
3. Extend applicable older-feature version gates, notably collective decisions currently requiring exactly v51 and offices accepting v50/v51. Preserve historical exact keysets and all lifecycle/cultural/region sibling constraints. Standalone mediation needs no unrelated feature flag or root spec.
4. Disabled is strict passthrough: no ledger, parsing, generation, bias, audit, additional RNG use, or changed command. Reject a checkpoint containing non-`None` mediation state for a mediation-disabled owner, using a safe closed reason, before any cursor/runtime mutation. A missing/`None` field in historical checkpoints remains accepted; enabled owners initialize empty state through normal preparation. Never restore enabled state and rely on a later tick to clear it.
5. Existing newborn initialization profiles remain mediation-disabled/content-empty. Update new-agent field validation as necessary, without adding automatic knowledge, a new profile, or parent-to-child ledger copying.
6. No new capability ownership; `institutional_economy` and `multi_hop_testimony_tracking` remain fail-closed. No new command/event/observation wire shape, SQL table, replay/codec marker, observer semantic type, API route, protocol rename, or Alembic revision.
7. Add exactly two detached metric families below: 122 → 124; commands stay 43 and observer semantic types 73.

## Detached measurement

Define versioned analysis-only families with immutable analysis-owned rows harvested after the run:

- **`conflict_mediation@1`:** distinct observed/claimed disputes; mediation offers, inquiries/accounts, compromises, vouches and restitution recommendations; actor/revision-specific responses; ignored/declined/deferred/unknown uptake; attempted versus observed follow-through; unresolved/partial/disputed/apparently settled outcomes. Report recurring mediator participation across distinct independently grounded disputes, not raw message frequency. Deduplicate roots and cross-owner copies; preserve uncertain case alignment and visibility exclusions. Association between exposure and outcome is not causal mediation effectiveness.
- **`mediation_role_emergence@1`:** recurrence across windows/cases, independent party invitations/endorsements, expected duties/procedures, persistence of recipient recognition, contested recognition and loss of support. Classify transient assistance, repeated mediator activity, candidate recognized role, and stable recognized role only with declared versioned thresholds and sufficient temporal/independent-support coverage. Repeat activity alone cannot satisfy stable-role criteria; no requirement that a stable role emerge.

Keep owner-local recognition distinct from detached cross-owner alignment by function/context. A role may persist despite unsuccessful recommendations; acceptance of one recommendation is not role recognition. Office/institution channels disabled or empty do not imply their presence. Export enabled-owner/window coverage independently of ledger truthiness; publish denominators, exclusions, ambiguity, pruning and censoring. Stopping before a reply observation/action window closes is right-censored, not failure. No synthetic final cognition tick or analytical feedback into agents.

Effect matching must preserve the exact actor, recipient, named item/project, supported terms and action window of an identified recommendation revision. A physically similar action outside that scope is not fulfilled restitution. Keep objective correspondence separate from direct/claimed acceptance and from subjective settlement; even a matched transfer does not prove agreement or conflict resolution. Do not multiply one effect into multiple fulfilled recommendations: unresolved competing matches remain ambiguous unless explicit correspondence evidence disambiguates them.

Specify metric value keys, numerators, denominators, distinct-case/root definitions and recognition-window requirements before implementation. Use known-answer fixtures with exact counts and classifications, not only family presence or nonnegative counters. Bounded final histories cannot prove uninterrupted recognition or run-wide recurrence without sufficient retained coverage; expose observed lower bounds/partial or unavailable classifications when pruning hides required windows. Snapshot-equivalent inputs and empty/missing channels must produce the documented availability and coverage states.

## Commit Plan

- **Commit 1** (Tasks 1–3): `feat(cognition): add subjective conflict mediation and speech contracts`
- **Commit 2** (Tasks 4–6): `feat(simulation): integrate opt-in mediation and checkpoint continuation`
- **Commit 3** (Tasks 7–9): `feat(analysis): measure mediation recurrence and emergent roles`
- **Commit 4** (Tasks 10–12): `test(v3): verify voluntary mediation and document its boundaries`

## Tasks

### Phase 1: Owner-scoped contracts and speech

- [x] **Task 1: Define immutable mediation contracts and bounded policy.**
  - Create `src/agents/cognition/mediation.py`; export through `src/agents/cognition/__init__.py`. Implement case/reference identity, parties/accounts, six acts, recommendation revisions, responses, evidence, authority components, attempt/outcome records and `MediationLedger` under `mediation.v1`.
  - Lock finite horizons/caps and freshness/retirement rules. Validate exact enums/types, finite numbers, logical ticks, ownership, ambiguous references and detached immutable values. Derive identities from explicit owner/seed/evidence material, never labels, wall-clock or Python `hash()`.
  - Define the seven response kinds and three auxiliary role-expression kinds specified above, including actor/revision/undertaking scope, partial acceptance, new-reference counterproposals, withdrawal targets and role-context references. Preserve exactly six primary acts. Size maximum valid accounts/recommendations/responses against existing speech limits; an oversized actionable recipe is rejected atomically, never truncated into different terms.
  - Add `tests/unit/test_mediation_contracts.py`, including forged ownership, unknown actors, unsafe reprs, invalid windows/caps and materially distinct revisions.
  - Logging: constructors remain pure; caller DEBUG counts/ticks and closed rejection codes only, never accounts, terms, labels or content fingerprints.
  - Dependencies: none.

- [x] **Task 2: Implement dispute detection, accounts and authority appraisal.**
  - In `mediation.py`, add pure deterministic updates from owner observations/prepared recall and owner-safe relationship/reputation/role/norm/institution projections. Generate third-party opportunities only from actual evidence; preserve partial and contradictory accounts.
  - Implement actor/revision-specific responses, voluntary withdrawal, expiry/reopening, unknown outcomes, root deduplication and protection-cap retirement. Keep self-authored attempts distinct from observed expression/effects.
  - Implement explicit source-to-appraisal mappings from existing reputation dimensions, norm context/expectation/counterparts, recognized office function/context/occupant evidence, and institution anchors/group/evidence. Preserve directional relationships and component provenance. Test real source-shaped inputs, unrelated contexts and unresolved links; do not add function-specific reputation fields or rely on generic `function`/`context_key` attributes absent from source contracts.
  - Add `tests/unit/test_mediation_updates.py` and `test_mediation_authority.py`: each of the five authority sources independently affects relevant appraisal; unavailable channels stay absent; trusted mediators can still be rejected; opposing parties can assess the same mediator differently. Include reorder/duplicate/pruning/replay and private-peer perturbation properties.
  - Logging: DEBUG transition/count/reason metadata and WARN invalid external boundary codes; no subjective payloads.
  - Dependencies: Task 1.

- [x] **Task 3: Transport six acts and responses over existing speech.**
  - Create `src/agents/cognition/mediation_communication.py`: namespaced versioned relation recipe, case/revision/actor/party references, attributed accounts, bounded terms and response fields inside existing communication caps. Reject malformed recognized recipes without breaking unrelated conversation.
  - Do not modify `src/world/communications.py` wire shapes (`communication.v1`, relation/concept caps) or `_perception.py` audiences. A mediation-disabled recipient treats structured mediation relations as ordinary unparsed communication: no ledger mutation, no reply, and no inferred account. Add enabled→disabled and disabled→enabled delivery cases, and keep the existing relation content when composing decorators.
  - Authenticate direct actors from observed speaker metadata, not payload claims; relayed acceptances/accounts/vouches remain testimony. Preserve recipient scope. If capacity/precedence blocks the chosen act, record no successful expression.
  - Confirm expression only on later owner-visible delivered evidence. Inquiry may receive no answer; rejected speech and runs ending before delivery confirmation remain attempts/unknown.
  - Encode/decode all closed response and auxiliary role-expression kinds from Task 1. Include an actual account request→delivered reply→receiver-local update sequence; revision-scoped partial acceptance/counterproposal/withdrawal; and first invitation/endorsement without an existing recognized office. Declared third-party roles/acceptances remain reports. Prove maximum valid recipes fit and overflow preserves neither partial terms nor a spurious successful act.
  - Add `tests/unit/test_mediation_communication.py`: all six acts and responses, actor spoofing, hostile/oversized recipes, ordinary conversation passthrough, no broadcast, unrelated decorator composition and rejected delivery.
  - Logging: DEBUG encode/parse counts and safe rejection codes; never log relation atoms or content-derived identifiers.
  - Dependencies: Tasks 1–2.

### Phase 2: Optional runtime behavior

- [x] **Task 4: Add exact v52 configuration and feature composition.**
  - Before changing configuration, fingerprints or runtime behavior, capture immutable pre-change configuration and trajectory references from the existing baseline/control paths using fixed seed, tick count and explicit run identity. Use coordinator-materialized conditions for coordinator hashes, since condition/run identity contributes to the digest. Preserve existing BH pins unchanged and record the exact reproduction inputs for BI reuse; never regenerate expected hashes after a behavior change merely to make tests pass.
  - Update `src/simulation/runner_models.py`, `runner_serialization.py`, `compatibility.py`, public facades, `src/agents/cognition/configuration.py`, and `src/experiments/matrix_schema.py` for modes, locked policy, factory wiring, exact keysets, writer selection and fingerprints.
  - Treat `compatibility.py` narrowly: its runner row already tracks `RUNNER_SCHEMA_VERSION` (still `v4`) and derives accepted restores from `SUPPORTED_RUNNER_SCHEMA_VERSIONS`; v50/v51 added no per-version matrix rows. Add v52 to the supported-version set and mirror expectations instead of inventing a lone matrix entry.
  - Audit office/institution/collective-decision and other applicable version gates plus `src/simulation/new_agent_initialization.py`; preserve old behavior and default-off newborn profiles. Reconfirm v52, `mediation_opportunities@1`, `conflict_mediation@1`, and `mediation_role_emergence@1` IDs are unused.
  - Add `tests/unit/test_runner_config_v52.py` and extend cognition/matrix/compatibility tests: exact missing/unknown fields, invalid enums, old schema rejection, enabled requirement, standalone and mixed owners, composed social/project/region/lifecycle modes, old writer selection and historical byte/fingerprint stability.
  - Logging: INFO selected schema/enabled-owner counts, DEBUG validation codes; errors never dump configuration.
  - Dependencies: Task 1.

- [x] **Task 5: Integrate deliberation, voluntary follow-through and role evidence.**
  - Update cognition `contracts.py`, `models.py`, `loop.py`, `deliberation.py` and simulation composition/perception seams; create `src/agents/cognition/mediation_actions.py` for typed existing-action adapters. Carry ledger and neutral appraisal through prepared contexts/results with owner checks.
  - Select mediation and responses from owner goals/evidence without compulsory discussion or consent. Implement deterministic speech precedence with collective decisions, offices, institutions, norms, naming/translation and other decorators; test the final emitted command rather than an intermediate candidate.
  - Compile only an owner's independently selected supported recommendation. Validate target knowledge and physical feasibility. Cover third-party compromise and voluntary restitution end-to-end; blocked transfers and urgent survival choices must not fabricate compliance/refusal.
  - Implement exact recommendation-to-command compilation rather than a direction-only filter. A named non-food held item must compile to `Give(item_id=..., recipient_id=...)` using the actual existing command signature and admission semantics, not `FEED`/`Feed` or a substitute item. Validate supported project/communication terms similarly; test unavailable items, altered recipients, superseded revisions, expired windows, terms mismatch, and late decorators that replace the command. Attribute only a matching final command as an attempt.
  - Integrate neutral mediation-function evidence with `offices.py`/`institution_concepts.py` only where their existing update contracts need it. Require independent recurring function plus role-directed endorsement/expectation; do not turn speech into a fake successful `mediated` occurrence or allocate disabled ledgers.
  - Add the explicit recognition bootstrap adapter and preparation ordering described above. Feed admissible observed/remembered function plus invitation/endorsement evidence into office preparation before projecting mediation authority; do not require a previously recognized office. Keep current draft acts and success appraisal out of recognition, deduplicate dual speech/recall paths, and defer cyclic institutional inputs to the next snapshot. Prove delivered third-party evidence can yield recognition through the normal update path, while repetition/self-endorsement alone cannot.
  - Add `tests/unit/test_mediation_runtime.py`, `test_mediation_actions.py`, `test_mediation_role_composition.py`; cover autonomous third-party selection, all acts, counterproposal, refusal/ignore, contested authority, repeated assistance without stable recognition, and mixed enabled/disabled delivery behavior.
  - Logging: DEBUG selection/skip/final-command metadata and closed attribution reasons; no claims/accounts/terms or authority belief contents.
  - Dependencies: Tasks 2–4.

- [x] **Task 6: Preserve atomic carry, continuation and detached results.**
  - Update `src/simulation/agent_runtime.py`, `run_control.py`, `runner.py`, `runner_models.py` and cognition snapshot propagation: staged commits, owner validation, disabled clearing, terminal-owner handling, immutable checkpoint export/restore/forks, and completed `SimulationRunnerResult` mediation exports consumed by collectors. The export is an internal detached result field only: do not add fields to the versioned `SimulationRunnerResultDocument`, bump `RESULT_SCHEMA_VERSION`, or imply durable serialization; test the versioned document stays unchanged.
  - Carry enabled-owner/window coverage, attempts, pruning and unresolved/censored state independently of whether cases exist. Restore must not revive disabled/foreign/expired state or recommit a delivered recommendation. Do not advertise durable SQL restart.
  - Preflight every mediation checkpoint field for exact type, ownership, target-owner mode compatibility, policy/reference/window invariants and coverage consistency before `SimulationRunner.apply_runtime_checkpoint` advances the engine cursor or restores any owner. Direct `AgentRuntime.restore_runtime_checkpoint` must also validate its mediation field before changing agent/goals/status or other fields. Reject non-`None` mediation state for a disabled owner; accept absent historical fields. Keep expired historical evidence only as non-actionable retained history. A mediation-specific rejection must leave all runtime state and runner cursors unchanged; do not expand this into an unrelated restore-system rewrite.
  - Add `tests/unit/test_mediation_checkpoints.py`: uninterrupted/continued equality, idempotent restore, detached fork isolation, duplicate/foreign owners, empty enabled state, enabled-to-disabled restore, expiry and terminal owners.
  - Use actual export/apply round trips and failure snapshots, including a bad later owner's mediation field after a valid first owner, wrong exact ledger type, disabled target and direct-runtime restore. Assert no partial application, no revived actionability and no recomputed acceptance/role support after restore.
  - Logging: DEBUG commit/restore counts/reasons; INFO export summary counts; safe rejection codes without state dumps.
  - Dependencies: Tasks 4–5.

### Phase 3: Detached measurement and reproducible experiments

- [x] **Task 7: Harvest detached mediation and recognition rows.**
  - Create `src/analysis/mediation.py` with analysis-owned immutable DTOs/harvesters; collect completed result exports in `src/experiments/collectors.py` and legal outer composition seams as needed. Join committed effects only after execution; never import live cognition/runtime/persistence into analysis.
  - Separate attempted, delivered, reported, accepted, effected and recognized-role evidence; align distinct cases conservatively by detached context/party/function evidence with explicit ambiguous/unmatched exclusions. Export channel/window coverage for zero-case and pruned owners.
  - Carry exact actor/recipient/item-or-project/terms/revision/window fields needed for effect correspondence into detached rows; wire analysis-owned effect inputs through `MetricComputationInputs` and collectors, following the existing collective-decision effect seam. Keep matches, ambiguous competing recommendations, accepted responses and settlement claims distinct; one objective effect cannot silently fulfill multiple recommendations. Test harvesters with snapshot-equivalent values as well as real completed results.
  - Add `tests/unit/test_mediation_analysis.py`: same-root repetition, duplicate observer reports, disputed case alignment, pending delivery, incomplete windows and partial histories.
  - Logging: INFO harvested/covered/excluded row counts; DEBUG safe alignment reasons only.
  - Dependencies: Task 6.

- [x] **Task 8: Register recurrence and stable-role metric families.**
  - Implement the two defined families in `src/analysis/mediation.py`; update `specifications.py` (`METRIC_FAMILY_COUNT` 122 → 124), `metric_service.py`, `__init__.py`, catalog pins and applicable metric-input wiring. Update all 20 tests currently asserting `METRIC_FAMILY_COUNT == 122` (including `test_metric_specifications.py`, `test_public_good_metrics.py`, `test_regional_demographics.py`, `test_v3_durable_records_regression.py`, and the other `test_*_metrics.py`/regression pins) and assert the exact new values rather than deleting the pins.
  - Lock thresholds/window/support requirements in versioned specifications. Count distinct disputes and independent roots, not utterances or repeated self-endorsement. Preserve contested recognition, unavailable appraisal channels and right-censoring; no global mediator role or objective success oracle.
  - Specify exact value keys and formulas before coding. Add hand-calculated fixtures for duplicated observations of one case versus genuinely distinct cases; repeated activity versus independently recognized persistent role; exact and mismatched restitution effects; and overlapping recommendation ambiguity. Assert actual metric values/denominators, not only catalog inclusion. Test retention-boundary pruning and late run starts: hidden recognition windows cannot become proof of stable roles, and remaining recurrence counts must be labeled lower bounds/partial as appropriate.
  - Add `tests/unit/test_mediation_metrics.py` and extend `test_metric_specifications.py`: recurrent activity without role, independently recognized stable role, disputed/lost recognition, empty/disabled/unavailable/partial cases and canonical quantized output.
  - Logging: INFO availability/coverage/count summaries, DEBUG exclusion codes; no evidence payloads.
  - Dependencies: Task 7.

- [x] **Task 9: Add off-gate Experiment BI (`mediation_opportunities@1`).**
  - Create `src/experiments/mediation_scenario.py`; update `catalog.py`, `__init__.py`, matrix allowlists and `tests/unit/test_experiment_bi.py` following BH. Keep BI outside the V1 gate. Keep the experiment/scenario id `mediation_opportunities@1` distinct from the `conflict_mediation@1` metric family.
  - Provide default-v4 baseline, comparable mode-off, mediation-on, relationship/reputation contrast, accepted-role/norm/institution contrast, and opportunity-limited conditions. The mode-off arm must use the highest legal prior schema for the same non-mediation modes (default v4, or v51 when collective decisions are enabled), never v52 with mediation fully disabled. Do not preseed mediator occupations, settled disputes, acceptance or role ledgers; interventions set legitimate neutral opportunities/configuration, not outcomes.
  - Separate scripted protocol fixtures (exercise every act) from autonomous experiments (test emergence opportunities without requiring success). Ensure runs contain enough distinct disputes/windows for role detection when evidence supports it; no seed-specific branching or forced stable-role assertion.
  - Pin repeat-seed configuration/trajectory digests, off-path parity, recipient privacy, voluntary non-uptake, canonical metrics and matrix round-trip. Include a successful voluntary restitution fixture plus infeasible/refused cases without claiming successful mediation in every experiment.
  - Reuse Task 4's pre-change references under exactly the recorded execution identity; distinguish direct-run hashes from coordinator-materialized hashes. Exercise role bootstrap through actual public speech delivery/update, real checkpoint export/apply, final-command restitution and completed-result→collector→metric assembly. Constructor-only recognized roles, synthetic restore maps and family-presence checks do not satisfy these acceptance proofs.
  - Logging: INFO condition/schema/seed/coverage counts; DEBUG safe composition reasons; no scenario account/utterance dumps.
  - Dependencies: Tasks 5–8.

### Phase 4: Boundaries, documentation and verification

- [x] **Task 10: Enforce autonomy, epistemic isolation and compatibility invariants.**
  - Add `tests/architecture/test_v3_mediation_isolation.py` and `tests/unit/test_mediation_invariants.py`; reuse existing collective-decision, office, institution and relationship isolation patterns.
  - Assert no world registry/Judge profession/forced transfer, no cross-owner memory read, no authority from enum/self-claim, no analysis feedback, no silent broadcast, no mandatory compliance, and no new objective/event/protocol/migration contracts. Verify private peer perturbations cannot change an owner's behavior absent delivered evidence.
  - Property-test bounded deterministic updates, duplicate/reordered/replayed speech, revision-specific acceptance, dedup eviction safety and stable-role evidence thresholds. Pin commands 43, semantic types 73, metrics 124 and unchanged historical write-pair selection.
  - Logging: capture logs/reprs in tests and assert account/terms/relation/fingerprint redaction; production emits no additional invariant payload logs.
  - Dependencies: Tasks 1–9.

- [x] **Task 11: Complete mandatory documentation checkpoint.**
  - Route changes through `/aif-docs`. Update relevant sections of `docs/social-communication.md`, `docs/configuration.md`, `docs/experiments.md`, `docs/architecture.md`, `docs/development.md`, and README index only where needed; update `.ai-factory/DESCRIPTION.md`/`ARCHITECTURE.md` with the implemented contracts.
  - Add a focused `docs/mediation.md` and a README index row, and extend `docs/analysis-metrics.md` (family definitions, denominators, availability/censoring, and the 122 → 124 total) and `docs/cognition-runtime.md` (owner-scoped ledger carry and checkpoint-versus-durable-restart limits). Sweep the `122` family-count pins in `docs/development.md` and `docs/analysis-metrics.md`.
  - Explain six acts, five recipient-relative authority inputs, optional source modes, nonbinding restitution, ignoring/refusal, owner-private disagreements, role-recognition evidence, v52/default-off compatibility, BI reproduction, metrics/censoring and checkpoint-versus-durable-restart limits. Keep unrelated historical material untouched.
  - Logging: document metadata-only diagnostics and `PALIMPSEST_LOG_LEVEL`; no new runtime logs for documentation.
  - Dependencies: Tasks 8–10.

- [x] **Task 12: Run verification and report evidence without overclaiming.**
  - Run new targeted tests, existing v51/collective-decision/office/institution/social-norm suites, compatibility/V1/scientific-invariant/head pins, full default coverage suite, Ruff, mypy and import-linter. Preserve coverage; default tests stay network/Docker-free.
  - Use `/aif-verify` against this explicit plan at completion. Report passes, failures, unavailable gates and residual limitations; never claim stable roles emerged solely because contract fixtures passed.
  - Logging: summarize command outcomes/coverage safely; bounded failure excerpts only, never raw subjective exports.
  - Dependencies: Tasks 10–11.

## Verification commands

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_mediation_*.py tests/unit/test_runner_config_v52.py tests/unit/test_experiment_bi.py tests/architecture/test_v3_mediation_isolation.py --cov -q
uv run --frozen --python 3.12.14 pytest tests/unit/test_collective_decision_*.py tests/unit/test_runner_config_v51.py tests/unit/test_experiment_bh.py tests/unit/test_office_*.py tests/unit/test_offices_*.py tests/unit/test_institution_*.py tests/unit/test_social_norms_*.py --cov -q
uv run --frozen --python 3.12.14 pytest tests/unit/test_compatibility_matrix.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/unit/test_alembic_head_pin.py tests/unit/test_metric_specifications.py --cov -q
uv run --frozen --python 3.12.14 pytest --cov
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src tests
uv run --frozen --python 3.12.14 lint-imports
```

## Completion criteria

- All six acts work through recipient-scoped speech and owner-local reasoning, including disputes between others.
- Relationships, reputation, accepted roles, norms and institutional beliefs supply genuine recipient-relative appraisal when available; none grants binding power.
- Agents can ignore, refuse or revise responses; recommendations alone never move resources or establish guilt/debt/settlement.
- Distinct repeated mediators and stable recognized roles are measured separately with independent evidence and temporal coverage; non-emergence remains valid.
- Default-off compatibility, authority boundaries, deterministic continuation and historical regressions remain intact; mandatory docs and verification evidence are complete.
