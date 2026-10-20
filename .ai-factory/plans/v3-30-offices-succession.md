# Implementation Plan: V3-30 Offices and Succession

Branch: main (current branch; `git.create_branches: false`)
Created: 2026-10-19
Mode: full
Status: planned; no implementation performed

## Settings
- Testing: yes — deterministic unit, property, runtime, experiment, compatibility, and architecture coverage.
- Logging: verbose — metadata-only; controlled by `PALIMPSEST_LOG_LEVEL`.
- Docs: yes — mandatory `/aif-docs` checkpoint during implementation.
- Canonical plan: `.ai-factory/plans/v3-30-offices-succession.md`; retain the `v3-` prefix in subsequent feature plan artifacts.
- Scope: opt-in owner-scoped office concepts, recognition and disputed succession, runtime checkpoint carry, detached measurements, and one off-gate experiment. No predefined office types, objective office registry, enforceable authority, or new capability flag.

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags (in progress)"
Rationale: Configured `plan_default_milestone=auto` selects the first incomplete milestone, M6; this is administrative linkage only, not a claim that this V3 feature completes M6 or owns a V2 flag.

Feature context: "M7 — V3 Generational Civilization (in progress)" is the substantive home for offices and succession. Do not close M6 or M7 from this plan; `multi_hop_testimony_tracking` and `institutional_economy` remain unowned and fail closed. Roadmap editing remains outside this planning command.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M6 — Remaining V2 Capability Flags (in progress)
INFO [aif-plan] full mode confirmed; no branch/worktree creation; resolved plan file: .ai-factory/plans/v3-30-offices-succession.md (format=slug)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-improve] refinement approved: added Task 0 for pre-change baselines; strengthened empty-state recognition, retrieved-episode inputs, trust/identity attribution, opt-in newborn capability, and detached cross-owner alignment; 13 tasks total, original task ids retained.

## Goal and Acceptance Contract

Represent the distinction between **“Bob is influential”** and **“there is a persistent recognized role that Bob currently occupies.”** A role is recognized by particular agents, not declared legitimate by the engine. Its identity can survive a changed occupant, disputed succession, vacancy, or revised duties. It can also disappear.

Each owner's office concept tracks:
1. A stable role concept and owner-local identity independent of occupant, supporters, label, and growing evidence.
2. Recognized duties grounded in existing actions/functions and a particular context.
3. Expected authority as revisable beliefs about requests, coordination, access expectations, or deference — never objective permissions.
4. Current occupant beliefs: zero, one, or several competing candidates, including uncertainty, rejection, and perceived vacancy. Never a globally authoritative `current_occupant`.
5. Supporters: attributed endorsements with owner-local evidence and confidence; no access to supporters' private ledgers.
6. Succession history: prior occupant claims, perceived death/departure or relinquishment, proposed replacements, disputes, abandonment, and role revisions with provenance.

Required outcomes after a perceived occupant loss: select a replacement, split over replacements, abandon the role, or change the role. None is mandatory or globally synchronized. Owners may disagree about the role itself, its duties, its authority, whether an occupant left, and who should replace them.

## Current Implementation Evidence

- `src/agents/cognition/institution_concepts.py` provides owner-scoped `InstitutionConceptLedger`, locked `institution-concepts.v1`, and six recognition channels. Existing role grouping includes the actor, and concept ids depend on evidence anchors: neither is an appropriate persistent office id. `_SUCCESSION_OCCURRENCES` does not implement the required succession lifecycle.
- The institution module explicitly forbids `office` fields. Add a separate subjective office module; do not relax existing world/repository/institution guards wholesale. General institution concepts remain valid without offices, and office concepts need not require enabling the general institution mode.
- `src/agents/cognition/loop.py`, `models.py`, `contracts.py`, `src/simulation/perception.py`, `agent_runtime.py`, `run_control.py`, and `runner.py` carry existing private ledgers across prepared updates, results, and runtime checkpoints.
- `src/agents/cognition/deliberation.py` decorates already-selected communications with institution relations. Later narrative decoration can replace those relations; office speech needs explicit precedence tests, not merely another untested decorator.
- `src/experiments/composition.py` and `src/analysis/institution_emergence.py` / `institutional_persistence.py` provide detached analytical patterns. A different actor resuming a function after death is not proof of a recognized office transfer.
- Current maximum runner schema is v49; default write is v4. `institution_concept_mode` currently requires exactly v49, so v50 composition must widen that gate explicitly. Schema sets and mode allowlists are distributed across `runner_models.py` and `runner_serialization.py`; matrix precedence lives in `experiments/matrix_schema.py`.
- Current pins: 43 commands, 73 observer semantic types, 117 metric families, accepted replay through `EVENT_SCHEMA_REPLAY_V22`, codec through `v20`, Alembic `0017`; Experiment BF is latest. Reserve v50 and Experiment BG, subject to recheck at implementation start.
- Existing institution tests establish in-memory runtime checkpoint equality, not an encoded durable subjective-state format or process-restart guarantee. Do not present objective replay as reconstructing private office beliefs.

## Task 0 Baseline Evidence (captured 2026-10-20, pre-change)

Capture command (run from repo root against unchanged pre-office code):

```bash
PYTHONPATH=src uv run --frozen --python 3.12.14 python /tmp/opencode/capture_baseline.py
```

Inputs: `institutionalization_scenario(seed=23, max_ticks=8)`, one seed
(`ExperimentSeedMatrix(seeds=(23,))`), `replicates_per_seed=1`, coordinator
`materialize_assignments` identities below, all active BF channels unchanged.
Pinned canonical bytes: `tests/fixtures/runner_configs/bf_baseline_v4.json`
(v4 flags off) and `tests/fixtures/runner_configs/bf_institution_off_v43.json`
(v43 composed, institution mode off).

| Arm | run_id | schema | config sha256 == fingerprint | exact trajectory | replica-normalized |
| --- | --- | --- | --- | --- | --- |
| `bf-baseline` | `institutionalization@1-bf-baseline-s0-r0` | `runner-config-v4` | `85c14cdb8e183d450817b3e026608a2d39d40ba29e9cccf4e2a809980a229334` | `64ed8635aa6693b464d0e9b2464e7ce49933d7659d47ab81deb213caaa0ce7fa` | `3f46af72669b7b81cd1a33b83453dfd827c0994a0b55a145ef62ba32079458b0` |
| `bf-institution-off` | `institutionalization@1-bf-institution-off-s0-r0` | `runner-config-v43` | `37c5aeca380da4ccede0a2d995da77baad17a614b0f3e8a0c8731e9ae5d427f4` | `b6df301a327f6ff086f473f6ee798b5dbffc8cf778f78ed546665c1e1cb18161` | `5c2d0efdf45a6352ac58b33c41ef563c44fe564573cdad98f18423231ded69d1` |

Pre-change slot/pin recheck (current code): max runner schema `runner-config-v49`,
default write `runner-config-v4`, metric families `117`, commands `43`, observer
semantic types `73`, replay through `EVENT_SCHEMA_REPLAY_V22`, codec through
`v20`, Alembic head `0017`, latest experiment `BF`. Existing BF/v2 golden
fixtures remain unchanged. Later BG arms must reuse these literal hashes and
fixture bytes; a missing baseline is a blocker, not a retrospective capture.

## Design and Boundaries

### Separate owner-scoped office ledger

Create `src/agents/cognition/offices.py` with frozen, bounded `OfficeConceptLedger`, `OfficeConcept`, duty/authority belief rows, occupant claims, attributed support rows, and succession/revision records under locked policy `offices-succession.v1`. Public exports live in the cognition facade, not `world` or base `agents`. Closed enums describe evidence and belief transitions, not social ranks or predefined jobs.

Allocate an office id once from deterministic owner identity plus a stable inception discriminator (first qualifying evidence/context and an owner-local collision discriminator). Store it thereafter; never rehash the changing occupant/evidence set into identity. A separate mutable-by-revision role signature describes function/context. Same labels in different contexts do not automatically merge; different labels do not automatically split one office. Cross-owner referents are communication testimony, not a global office key. All counters/discriminators must survive checkpoint/fork.

Recognition requires recurring function evidence **and** distinct evidence of role-directed expectation or endorsement independent of a particular person's influence. Repetition by Bob alone is insufficient. A succession belief must reference the persistent role, not just similar actions by two actors. Independence is provenance-aware: repeated retellings from one root cannot manufacture supporters or promote a role. Policy bounds, thresholds, decay, tie handling, and truncation semantics are locked and tested.

Recognition must be reachable from content-empty ledgers. Recurring observed functions may ground a tentative role proposal before recognition; a proposal is not proof of an office, authority, occupant legitimacy, or peer support. Candidate-role speech and fresh receiver interpretation provide a bootstrap path without requiring an already-recognized office or seeding one in the experiment. Independent qualifying evidence is still required for promotion.

Keep duties/authority revisions and succession records immutable within retained history. Bound records and evidence deterministically, exposing pruned counts/coverage rather than silently implying a complete history. Preserve role inception and causal references needed by retained succession records. Minor duty/authority changes retain identity with revisions; a materially different function creates a new concept with an owner-believed predecessor link. Never silently recycle an abandoned id.

### Evidence, disagreement, and succession

Use only the owner's immutable observation, observed identity projection, own recalled memories, own relevant ledgers, and delivered structured testimony. Missing actors, remote deaths, departures, or non-observation do not establish vacancy. Observed departure may reduce confidence that someone is available without proving relinquishment. False death/departure reports remain fallible communicated evidence and can be contradicted; return of a presumed absent occupant is representable.

Remembered evidence comes from the prepared `RetrievedMemoryContext` reconstructions/reference episodes through episode facts, not raw `SubjectiveSnapshot.memories`, ranked-hit trace payloads, or a fresh unbudgeted recall. Pass this context explicitly to the office updater and bound episode processing under the existing retrieval/budget contract. Preserve remembered contradictions instead of correcting them against objective history.

Occupancy is a set of claims with support/opposition and epistemic status. A derived owner-preferred candidate is optional and non-authoritative; ties remain disputed. Support counts are attributed beliefs with evidence, not headcounts from global private states. Owner endorsement, attributed peer endorsement, and actual peer private belief are distinct. Abandonment means this owner ceases recognizing the role; it does not delete anyone else's concept or erase retained succession history.

Project speaker trust from the owner's directed relationships at the cognition boundary, following reputation/territorial preparation; the office policy receives neutral owner-local values. The world-verified speaker is not necessarily the alleged supporter. Preserve previously evidenced occupant entity references in the private ledger when those entities leave the current `OwnerSafeSocialIdentity.counterparts`; never resolve an absent person by consulting the full registration map. Unknown alleged identities remain unresolved testimony. Deduplicate verified repeated delivery and owner-known shared roots, but do not treat a changed declared source chain as verified independent corroboration or claim perfect multi-hop source tracking.

Implement deterministic update paths for replacement, rival candidates, abandonment, and revision from evidence. Do not branch on experiment arm names, character names, seed-specific identities, predefined offices, age/kinship entitlement, or a mandated voting/hereditary rule. Continuity across generations requires transmission and local reconstruction, not inheritance of private ledgers. A newborn starts empty.

### Communication and behavior

Use existing structured `Talk`/`Tell` relations for role descriptions, duties/authority expectations, endorsements, contested occupancy, relinquishment, and replacement proposals. Specify exact relation shapes and owner-local referent resolution before implementation; unknown/ambiguous referents defer rather than mutate an arbitrary office. Receivers create fresh local evidence and never copy sender ledger rows. Delivery proves speech, not legitimacy. Bare `COMMUNICATE` does not auto-testify on behalf of an office.

Live policy may select role-related speech and provide a bounded subjective bias among already-admissible existing actions using recognized duties or a preferred occupant. It must not force obedience or bypass physiology, goals, budgets, communication eligibility, or normal world admission. Demonstrate at least a role-directed communication/action difference when enabled; a ledger that is only exported is insufficient. Leave full elections, law, taxation, policing, and enforcement out of scope.

### Versioning, runtime, and analysis

- Add per-agent `OfficeSuccessionMode` and cognition-side `CognitionOfficeSuccessionMode`, `DISABLED`/`DETERMINISTIC`, with `office_succession_mode` on `runner-config-v50`. v50 is emitted/required only when at least one owner enables this mode. `_COGNITION_KEYS_V50` extends v49; root siblings follow the existing family without a new offices root spec. v50 supports institution mode and earlier compatible channels. v49 exact keys and disabled-mode baseline bytes remain unchanged.
- Thread freshly prepared office state through perspective/snapshot/proposal/result, deferred runtime commit, checkpoint export/restore/fork, runner outcome and owner-ordered exports. Failed/aborted ticks do not leak proposed changes. Preserve disabled-owner emptiness and blank-slate initialization.
- Newborn capability is separately opt-in: add a closed `species_default_offices_v1` initialization profile for v50, enabling office cognition with empty office content. Keep both existing species-default profiles unchanged. Admission must use the selected fresh profile, not a parent's cognition or ledger. Reject the new profile on older schemas; the existing v50 requirement for at least one initially enabled owner remains in force. A newborn on an unchanged profile remains office-disabled and must not be counted as an enabled learner.
- Guarantee runtime-checkpoint continuation and fork parity, including future ids and subsequent decisions. Do not add a world event, observation field, replay/codec bump, or migration for subjective offices. If durable process restart is requested or a concrete persistence seam is needed, document the missing encoded subjective contract and obtain a scoped follow-up decision; do not silently alter objective codecs.
- Add detached `office_continuity@1` and `office_succession@1` metric families (117 → 119). Analysis-owned rows preserve owner/source distinctions, context alignment, temporal revisions, disputes, abandonment, pruning and coverage. Composition can join committed death/departure facts after the run, but those joins never feed live cognition.
- Measure recognized-role continuity across occupant changes and duty revisions separately from actor recurrence/influence. Report replacement, disagreement, unresolved vacancy, abandonment and role-change counts with explicit denominators. No globally legitimate winner, majority-is-truth rule, or automatic merge by label. Missing evidence is unknown/absent, not zero; local pruning is partial coverage. Existing institution metrics retain their semantics and 117-family baseline documents remain valid.
- For cross-owner disagreement, analysis may align independently created local roles by detached function/context evidence, retaining owner ids, alignment confidence, evidence coverage, and ambiguous/unmatched cases. Owner-local ids are not shared keys; identical labels or occupants alone cannot establish equivalence. Alignment is analytical inference, never a canonical office registry. Compute dispute denominators only from sufficiently aligned, contemporaneous claims and expose excluded/ambiguous counts.
- No new UI, HTTP API, Godot protocol, or semantic event type is required. New metrics use existing generic read paths. Any subjective projection must remain owner-scoped and behind existing debug permissions; analytical rows retain analytical-inference provenance.

## Commit Plan

Suggestions for implementation only; this planning command creates no commits.
- **Commit 1** (tasks 0–3): `feat(v3): add subjective offices and evidence-based succession`
- **Commit 2** (tasks 4–7): `feat(v3): wire office cognition and checkpoint continuity`
- **Commit 3** (tasks 8–12): `feat(v3): measure office continuity and validate succession outcomes`

## Tasks

### Phase 0 — Pre-change baseline evidence

- [x] **Task 0: Capture coordinator-materialized baselines before implementation.**
  - Files: record concise baseline evidence in this plan; pin regression fixtures/assertions in `tests/unit/test_experiment_bg.py` and `tests/unit/test_runner_config_v50.py` as they are introduced. Do not create production office code before this preflight is complete.
  - Capture exact trajectory hashes from existing coordinator-materialized flags-off and composed mode-off configurations, fixing seed, run identity, arm identity, tick count and all active channels. Preserve exact legacy configuration bytes or canonical fixture bytes and their fingerprints. Recheck runner/experiment slots, metric counts and compatibility pins against current code; record the runnable capture command and inputs, not merely an unrepeatable digest.
  - Acceptance: later BG baseline/control arms reuse the captured configurations and materialization identity; hashes are literal pinned pre-change values, not recomputed expectations from changed code. An unavailable baseline is an explicit blocker, not a reason to invent or capture it retrospectively. Preserve existing BF fixtures unchanged.
  - Logging: capture safe command/results, configuration version, counts and regression artifact hashes only; no credentials, private ledgers, utterances or full operational configuration dumps.
  - Dependencies: none.

### Phase 1 — Contracts, evidence, and policy

- [x] **Task 1: Define stable office identity and owner-scoped belief contracts.**
  - Files: new `src/agents/cognition/offices.py`, `src/agents/cognition/__init__.py`; new `tests/unit/test_offices_contracts.py`.
  - Implement frozen rows and exact validation for all six tracked surfaces, provenance, bounded history, inception/collision state, role revisions and owner validation. Keep occupant claims separate from role identity; distinguish vacant, uncertain, and contested. Lock policy id/constants, reject malformed owners/foreign evidence/nonfinite strengths/unsupported policies, and define safe cap handling.
  - Acceptance: id remains fixed under evidence growth, supporter changes, renamed labels, replacement and minor revision; same-label different-context roles remain separate; caps expose partial coverage; deterministic ids match across processes. Influence-only inputs cannot construct a recognized role through the recognition policy.
  - Logging: pure constructors remain silent; boundary DEBUG reason codes/counts only, no duty/label/evidence content or content-derived digest payloads.
  - Dependencies: 0.

- [x] **Task 2: Implement recognition, duties, authority, and attributed support updates.**
  - Files: `src/agents/cognition/offices.py`; new `tests/unit/test_offices_recognition.py`.
  - Build an evidence adapter from owner-safe observations, prepared `RetrievedMemoryContext` episode facts, and local norm/convention/institution inputs where enabled. Define explicit function/context matching and endorsement relations. Track expectations separately from successful physical behavior. No dependency on general institution mode; do not reuse actor-bound institution ids as office ids. Define tentative role proposals grounded in recurrence, before recognition, so the sender/receiver policy does not require an already-recognized office to bootstrap.
  - Accept neutral owner-local speaker-trust projections from loop preparation. Keep verified speakers, self-endorsement, alleged supporters and independently evidenced supporters distinct. Preserve known occupant references across absence without expanding the current identity projection from global registration state; unknown alleged identities remain unresolved.
  - Acceptance: repeated influence without role-directed evidence stays personal; independent role recognition promotes; same-root repetitions do not inflate independent support; conflicting duties/authority expectations remain revisable; unknown attribution cannot become a known supporter. Exercise reconstructed contradictory evidence, exact-reference episodes, empty recall and bounded episode processing; never fall back to raw snapshot memories or ranked-hit traces.
  - Logging: DEBUG update source counts, accepted/rejected counts and safe reasons; metadata only.
  - Dependencies: 1.

- [x] **Task 3: Implement fallible occupant-loss and succession transitions.**
  - Files: `src/agents/cognition/offices.py`; new `tests/unit/test_offices_succession.py`.
  - Add evidence-driven loss/availability appraisal, replacement claims, competing successors, owner abandonment, duty revision and predecessor-linked role change. Append history without overwriting prior claims. Consume only observed/remembered/communicated evidence; do not read `WorldEvent` or global rosters. Verify the exact existing perception kinds used by positive cases and pin that mapping. Resolve previously known occupants from retained owner evidence when they are absent from current counterpart bindings, without treating absence itself as loss evidence.
  - Acceptance: known-answer tests cover death, departure without relinquishment, explicit relinquishment, uncertain loss, replacement, split, abandonment, minor/major revision, false death testimony and return. Include later succession testimony about a formerly visible occupant absent from the current identity projection. In every case others may retain different beliefs, and no automatic kinship/age entitlement appears.
  - Logging: DEBUG transition counts and safe reason codes; no private claim text or alleged social verdicts.
  - Dependencies: 2.

- [x] **Task 4: Add structured role communication and fresh receiver interpretation.**
  - Files: `src/agents/cognition/offices.py`, `src/agents/cognition/deliberation.py`; new `tests/unit/test_offices_communication.py`.
  - Define exact relation recipes and cross-owner referent testimony, using existing utterance primitives. Implement tentative role proposals, endorsements, disputes and succession proposals with trust/provenance, duplicate protection and unknown-reference deferral. Candidate speech must not assert recognized status or invent supporters. Integrate communication precedence so institution/narrative decorators cannot silently erase selected office speech. A third-party endorsement claim is speaker testimony, not verified speech by the alleged supporter; changed declared lineage alone cannot create independent support.
  - Acceptance: drive the public update/planner, actual structured speech and receiver interpretation path from empty office ledgers through a tentative proposal to recognition after sufficient independent evidence; no hand-seeded recognized row. Contradictory messages produce separate local claims; no sender state copy; trust affects uptake; one message cannot create consensus; role references survive an occupant change; forged supporter/source claims and duplicate delivery cannot manufacture verified corroboration; no new command or wire field; bare communication remains non-testimonial.
  - Logging: DEBUG communication/interpretation counts and rejection reasons; never utterances, labels or fingerprints as content surrogates.
  - Dependencies: 3.

### Phase 2 — Versioned configuration and live runtime

- [x] **Task 5: Add default-off modes and exact runner-config-v50 support.**
  - Files: `src/agents/cognition/configuration.py`, `src/simulation/runner_models.py`, `runner_serialization.py`, `compatibility.py`, `runner.py`, `new_agent_initialization.py`, package facades; new `tests/unit/test_runner_config_v50.py`.
  - Add mirrored enums, policy wiring/fingerprints, mode mapping, v50 keysets and bidirectional version gates. Widen institution mode's exact-v49 gate to v49/v50 and all applicable prior mode/version allowlists without weakening unknown-key rejection. Add the explicitly selected `species_default_offices_v1` profile id to the closed initialization registry, gated to v50; profile construction/admission follows in Task 7. Preserve every older accepted keyset, both existing species-default profiles, default v4 write shape and replay/codec selection.
  - Acceptance: v50 on/round-trip/reverse-gate tests; mixed enabled/disabled owners; v49 plus office key rejects; v50 with no enabled office mode rejects; v50 composes institution, narrative, regional and lifecycle modes; the new initialization profile round-trips only on v50, with older schemas rejecting it; existing golden configurations remain byte-identical to Task 0 fixtures.
  - Logging: INFO mode/schema setup counts; DEBUG safe validation reasons, never serialized config bodies.
  - Dependencies: 0, 1.

- [x] **Task 6: Thread office updates through cognition and bounded behavior selection.**
  - Files: `src/agents/cognition/models.py`, `contracts.py`, `loop.py`, `deliberation.py`, `src/simulation/perception.py`, `agent_runtime.py`; new `tests/unit/test_offices_runtime.py`.
  - Carry freshly prepared office beliefs into deliberation and all proposal/result paths; commit only at the existing successful subjective finalization boundary. Pass the prepared `RetrievedMemoryContext` and projected speaker trust into the updater explicitly; do not copy `_prepare_institution_concepts()`'s raw `snapshot.memories` input. Resolve current speakers through the owner-safe identity projection, with unresolved trust handled by a locked conservative default. Add bounded role-directed communication/action influence using existing actions. Disabled mode is a strict passthrough and performs no office updates, selection bias or office logging.
  - Acceptance: a deterministic case changes a role-directed decision while personal-influence-only evidence does not activate office policy; stale snapshots are not used; failed finalization leaves committed ledger unchanged; rejected physical actions remain rejected regardless of expected authority. Runtime tests demonstrate that prepared recalled-episode contradictions and different owner-local trust values reach the policy, empty/limited recall cannot trigger an unbudgeted scan, and absent occupant references remain usable without global identity access.
  - Logging: enabled-owner DEBUG proposal/commit counts and policy reasons, INFO lifecycle setup only; no full snapshots or authority content.
  - Dependencies: 4, 5.

- [x] **Task 7: Preserve checkpoint/fork identity, exports and newborn isolation.**
  - Files: `src/simulation/agent_runtime.py`, `run_control.py`, `runner.py`, `runner_models.py`, `new_agent_initialization.py`; new `tests/unit/test_offices_checkpoints.py`, `tests/unit/test_offices_initialization.py`; `tests/architecture/test_v3_new_agent_blank_slate.py`.
  - Add validated office checkpoint fields, runtime carry/restore/rebase, owner-ordered `office_ledgers` results/export, and blank-slate deny-list/store-count entries. Persist inception/discriminator state and retained history metadata in the runtime checkpoint object; preserve old checkpoints with empty office state where applicable. Implement the fresh, content-empty `species_default_offices_v1` factory and exercise the real runner mid-run admission path (`species_defaults_for()` → fresh `AgentRunnerSpec` → `_cognition_config_for()`); never copy parent cognition or modify existing profile factories. Keep the new profile's unrelated modes at documented defaults, with only office capability enabled unless explicitly justified by dependencies.
  - Acceptance: use real runner checkpoint export/apply APIs; uninterrupted vs restored continuation matches later office ids, claims, histories and commands; forks detach values and diverge only from subsequent evidence; cross-owner checkpoints reject; deterministic owners export exactly one ledger each, including empty ledgers for enabled newborn learners; disabled owners export none. Admit a newborn under the explicit new profile, assert zero inherited offices at bind, then demonstrate independent acquisition through ordinary observations/messages. Existing profiles remain office-disabled with unchanged defaults. State explicitly that checkpoint tests cover runtime checkpoint objects, not durable process restart.
  - Logging: INFO checkpoint/export owner and row counts; DEBUG restore validation reasons; no ledger payloads.
  - Dependencies: 6.

- [x] **Task 8: Integrate matrix schema precedence and lock authority boundaries.**
  - Files: `src/experiments/matrix_schema.py`, `tests/unit/test_experiment_matrix_schema.py`, new `tests/architecture/test_v3_offices_isolation.py`; existing institution guard tests as needed.
  - Place office-mode v50 classification above institution v49 and test mixed-mode factors. Enforce no objective office/legitimacy registry, no cognition→analysis or private-world imports, no analysis imports of ledger/runtime/persistence, and no globally chosen occupant projection. Keep v3-29 institutional vocabulary guards intact except any precisely justified module-scoped accommodation.
  - Acceptance: on/off cells classify to exact expected schemas; architecture checks prove observer/API cannot grant authority from offices; existing guards and blank-slate tests pass without broad whitelists.
  - Logging: DEBUG matrix classification counts only; static checks produce no application logs.
  - Dependencies: 5, 7.

### Phase 3 — Detached evidence, experiment, documentation and gates

- [x] **Task 9: Add detached office continuity and succession measurements.**
  - Files: new `src/analysis/offices.py`; `src/analysis/__init__.py`, `specifications.py`, `metric_service.py`; `src/experiments/composition.py`, `collectors.py`; new `tests/unit/test_office_metrics.py`, `test_office_composition.py`; relevant metric catalog count pins.
  - Define analysis-owned immutable row DTOs; harvest owner-local office history/export rows at composition, preserving temporal claims and source attribution. Define detached cross-owner role alignment from function/context evidence, exposing confidence, temporal overlap and ambiguous/unmatched roles; never join by owner-local id, label or occupant alone. Compute disagreement only for sufficiently aligned contemporaneous claims and expose excluded-case counts. Optional post-run objective joins measure correspondence, never legitimacy. Register `office_continuity@1` and `office_succession@1`, explicit inputs and availability handling, numerical quantization and count 119. Do not substitute existing function-resumption heuristics for office-recognition evidence.
  - Acceptance: hand-built timelines give pinned continuity/replacement/dispute/abandonment/revision results; different roles with the same label or actor remain unmerged; independently named but context-aligned roles expose disputed occupants without a global winner; uncertain alignment stays unknown rather than disagreement or consensus. A personal-influence control is not an office; missing/pruned evidence has absent/partial coverage and explicit denominators; objective-only traces cannot manufacture recognized occupancy. Real exports and detached snapshot-equivalent inputs harvest identical rows; empty/disabled inputs have explicit availability and no fabricated zeros. Existing institution metrics remain unchanged.
  - Logging: INFO aggregate row/metric counts, DEBUG coverage/rejection reasons; no role text, subjective payloads or content digests.
  - Dependencies: 7, 8.

- [x] **Task 10: Build Experiment BG with office and succession contrasts.**
  - Files: new `src/experiments/offices_succession_scenario.py`; `src/experiments/catalog.py`, relevant facade; new `tests/unit/test_experiment_bg.py`.
  - Reserve `offices_succession@1` / BG in the off-gate catalog. Include a flags-off v4 golden baseline, matched composed office-mode-off control at its highest required lower schema, and mode-on v50 conditions varying observable continuity, loss, communication/support access and resources. Reuse Task 0's pre-change fingerprints and exact coordinator-materialized configuration identities; do not capture a new expected hash from changed code. Use existing physical/communication channels and deterministic policies; do not seed office ledgers, legitimate successors, desired consensus, or special actor scripts.
  - Acceptance: repeated fixed-seed runs match; role identity can outlive its occupant; mode-off owners remain empty; disagreement is preserved. Unit-level evidence fixtures prove all four allowed outcomes; the scientific scenario reports observed outcome distributions, including none, rather than demanding each outcome or success at every seed. Arbiters assert structure, privacy, availability and reproducibility, not political outcomes. Registration and matrix membership tests keep BG off the V1 gate.
  - Logging: INFO arm/seed/outcome counts, DEBUG safe arbiter checks; no transmitted claims or private concepts.
  - Dependencies: 9.

- [x] **Task 11: Complete the mandatory documentation checkpoint.**
  - Run `/aif-docs` for `docs/cognition-runtime.md`, `docs/simulation-runner.md`, `docs/configuration.md`, `docs/experiments.md`, `docs/analysis-metrics.md`, and relevant sections of `docs/architecture.md`; update `.ai-factory/DESCRIPTION.md` / `.ai-factory/ARCHITECTURE.md` to reflect the narrowly scoped new subjective office primitive. README index changes only if necessary.
  - Explain influence vs role, tentative proposals vs recognition, duties vs permissions, owner disagreement/support attribution, fallible lineage claims, four succession outcomes, false/unknown loss, retrieved-episode inputs, history bounds, v50 opt-in and the new explicit newborn profile. Document analytical role alignment and ambiguous-case denominators, metric coverage and runtime-checkpoint-only guarantees. Update the prior blanket “no office anywhere” description without weakening bans on objective institutions or predefined office categories. Include reproducible BG examples and unchanged compatibility pins.
  - Acceptance: examples execute, links resolve, terminology never implies global legitimacy, no unsupported durable restart claim, and no claim of flag/milestone ownership.
  - Logging: documentation work adds no application logs; summarize documentation validation failures only.
  - Dependencies: 10.

- [x] **Task 12: Verify regressions, scientific invariants and final pins.**
  - Files: focused implementation/test fallout only. Recheck reserved slots before finalizing; record any legitimate concurrent drift rather than overwriting unrelated work.
  - Run focused office suites, full default pytest including architecture, Ruff check/format check, mypy and import-linter, plus compatibility/golden configuration, V1 regression, V2 scientific invariants, metric catalog and Alembic pin tests. Retain coverage. Run registered observer regression tests according to `docs/development.md` if shared observer/metric plumbing is affected; do not change Godot semantics. Integration is opt-in and uses only disposable `palimpsest_test` databases if a touched adapter needs it.
  - Acceptance: final planned pins are runner max v50, families 119, commands 43, observer semantic types 73, replay through v22, codec through v20, Alembic 0017, default runner write v4; flags-off trajectories and older config bytes unchanged. Record exact commands/results and any unavailable environment gates; never mark an unrun gate passed.
  - Logging: test/build summaries only; use existing secret-safe diagnostics on failure.
  - Dependencies: 11.

## Verification Commands

Use the pinned environment; do not inspect dependency directories or lockfile contents.

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_offices_contracts.py tests/unit/test_offices_recognition.py tests/unit/test_offices_succession.py tests/unit/test_offices_communication.py tests/unit/test_offices_runtime.py tests/unit/test_offices_checkpoints.py tests/unit/test_offices_initialization.py tests/unit/test_office_metrics.py tests/unit/test_office_composition.py tests/unit/test_runner_config_v50.py tests/unit/test_experiment_bg.py -q
uv run --frozen --python 3.12.14 pytest tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/unit/test_v2_golden_runner_configs.py tests/unit/test_compatibility_matrix.py tests/unit/test_metric_specifications.py tests/unit/test_alembic_head_pin.py -q
uv run --frozen --python 3.12.14 pytest
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 ruff format --check src tests
uv run --frozen --python 3.12.14 mypy src tests
uv run --frozen --python 3.12.14 lint-imports
```

## Verification Results (2026-10-20)

- Focused office/architecture suites: `74 passed` (contracts, recognition,
  succession, communication, runtime, checkpoints, initialization, metrics,
  composition, v50, BG, isolation, blank-slate).
- Focused regression pins: `50 passed` (`test_v1_regression_gate`,
  `test_v2_scientific_invariants`, `test_v2_golden_runner_configs`,
  `test_compatibility_matrix`, `test_metric_specifications`,
  `test_alembic_head_pin`).
- Full default suite: `4822 passed, 104 deselected` after updating established
  metric-family pins 117 -> 119 and office blank-slate entries.
- `ruff check src tests`: passed.
- `ruff format --check` on all touched files: passed. Repository-wide
  `ruff format --check src tests` still reports pre-existing unformatted files
  outside this plan's scope.
- `mypy` on all 22 touched source files: passed. Repository-wide
  `mypy src tests` still reports pre-existing test-suite typing debt.
- `lint-imports`: `25 kept, 0 broken`.
- Final pins: runner max `runner-config-v50`, default write `runner-config-v4`,
  metric families `119`, commands `43`, observer semantic types `73`, replay
  `EVENT_SCHEMA_REPLAY_V22`, codec `v20`, Alembic `0017`, Experiment BG
  (`offices_succession@1`). Flags-off v4 BG baseline bytes match the Task 0
  fixture; older golden configuration bytes were not rewritten.

## Post-Verification Remediation (2026-10-20)

- Implemented `WorldEngine.restore_runtime_cursor()` and called it from
  `SimulationRunner.apply_runtime_checkpoint()`. Restored continuation now
  matches uninterrupted office ids/claims for the tested horizon; objective
  events/snapshots remain a separate durable contract.
- Added `office_direction_preference()` and wired it into intention selection
  as a bounded filter among already-admissible undominated futures. Recognized
  perform/maintain/coordinate duties bias direction; influence-only proposals
  return `None`.
- Added owner-local norm/convention/institution expectation adapter (closed
  function + context + recognized marker only; foreign owners reject).
- Added office-vs-prior-narrative precedence, v50 narrative+lifecycle
  composition, perception-kind pinning, objective death correspondence joins,
  real-export vs detached snapshot harvest equivalence, varied BG support arm,
  and explicit newborn `AgentRunnerSpec` path tests.
- Re-verified: focused office/pin suites `133 passed`; full default suite
  `4831 passed, 104 deselected`; `ruff check src tests` passed; import-linter
  `25 kept, 0 broken`; mypy on changed source modules passed.
- Remaining accepted deviations: BG baseline reuses pre-change config bytes but
  not the BF run identity (new experiment id necessarily changes `run_id`);
  repository-wide format/mypy still carry pre-existing debt outside this plan;
  no executable documentation examples were added beyond the existing command
  snippets.

## Risks and Explicit Non-goals

- False emergence: actor recurrence, global popularity, repeated same-root testimony, or similar labels alone must not become office recognition or consensus.
- Identity drift: never derive persistent office identity from the current occupant or growing evidence; revisions and branches need explicit lineage.
- Omniscient succession: no remote-death/exit detection from global state, no peer belief reads, no automatic societal vacancy/replacement.
- Serialization overclaim: runtime checkpoints are not objective replay or guaranteed durable subjective restart. No migration or objective codec change is authorized by this plan.
- No default office roster, hereditary rank, mandatory vote, binding appointment, engine-enforced duty, new world permission, UI expansion, or ownership of `institutional_economy`.
