<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-33 Scientific Knowledge Diffusion

Mode: ultra  
Branch: main  
Created: 2026-11-21  
Plan ID: `v4-33-science-diffusion`

## Original Request

v4-33 scientific knowledge diffusion

Naming requirement:

Use `v4-33-science-diffusion`.

Track how scientific hypotheses/models move through:

teaching  
records  
organizations  
migration  
cross-society communication

Support:

mutation  
misunderstanding  
translation  
loss  
rediscovery

Connect V3 knowledge genealogy with V4 scientific evidence.

## Settings

- Testing: yes
- Logging: verbose, metadata only
- Docs: yes (mandatory `$aif-docs` checkpoint)
- Existing branch and worktree retained; planning only.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"  
Rationale: deepens owned science and joins existing V3/V4 carrier evidence without changing world authority or claiming a reserved context.

## Requirements Reconciliation

Authority: the Original Request sets feature scope; `.ai-factory/RULES.md`, `.ai-factory/rules/base.md` and the current V4-32 baseline in `.ai-factory/ARCHITECTURE.md` constrain implementation. The roadmap identifies the milestone, not a requirement to claim another flag. No separate research brief was found.

| Decision / supported combination | Source path and section | Verification evidence |
|---|---|---|
| Capture off or core science gate off: ordinary execution, no new documents or publication. Capture on with missing optional lanes: report per-lane availability. Terminal export happens after finish; cap cutoffs seal only trusted prefixes. | `.ai-factory/ARCHITECTURE.md` — Key Principles, V4-27 and V4-32 seams; `src/simulation/runner.py` — `_detached_boundary_inputs` | Tasks 1–2, 7, 10: terminal ordering, cap atomicity and capture parity; science-off control; optional lanes do not gate core capture. |
| Addressed science speech alone proves delivery; linked native hypothesis receipt proves uptake. Teaching requires exact advice occurrence; qualified relays preserve the previous receipt, not ownership. A model reference or read does not install a model. | Original Request; `src/agents/cognition/scientific_hypothesis_communication.py` and `src/agents/cognition/scientific_model_derivation.py` refine the observable scope. | Tasks 3, 5, 10: native uptake, model description, record relay, invalid relay, and local derivation. |
| Exact recorded carrier revision and owner reading can join V3 written knowledge; physical service, same technique, shared roots or endpoint reports cannot prove uptake. | Original Request; `.ai-factory/ARCHITECTURE.md` — Important V3 seams; `src/analysis/knowledge_genealogy.py` — qualified lineage. | Tasks 3–4, 10: real admitted record to V3 entry; malformed, guessed and ambiguous negatives. |
| Organization mediation needs an exact carrier service witness; arrival can carry a prior local version without transferring it, with confirmation only when qualified. Cross-society claims require unique assignments in absolute, complete, as-of windows. | Original Request; `.ai-factory/ARCHITECTURE.md` — V4-02, V4-14 and V4-32 seams. | Tasks 4–5, 10: before/after qualification, exact instance service, missing/overlapping membership, and actual context builders. |
| Mutation and misunderstanding require witnessed differences; translation requires a unique bound source constituent in a real application. Loss needs explicit closure of known holders and carriers; independent rediscovery needs a distinct root and complete prior exposure coverage. | Original Request; `.ai-factory/ARCHITECTURE.md` — Memory, testimony, and subjective concepts; V4-32 non-backdated lineage. | Tasks 4–5, 10: divergent read, bound/ambiguous translation, copied carrier survival, reacquisition vs independent root, coverage removal. |
| Publish an opt-in immutable metadata-only snapshot; use GET-only debug-gated reads. V56 and V57 stay exact; legacy/flags-off bytes and existing version pins stay unchanged except append-only metric count. | `.ai-factory/ARCHITECTURE.md` — Dependency Rules, Versioned Extension Contract; `.ai-factory/RULES.md` — Axioms. | Tasks 6–11: canonical bytes, store fault, paging, real v56/v57 evidence and invariant gates. |

## Architecture and Decisions

- **Authority:** `experiments` captures finalized neutral evidence and is the analysis-to-artifact bridge. `analysis` computes lineage without access to live services; `simulation` houses only neutral publication contracts; persistence publishes atomically; API and Research UI read. No analysis feeds perception, cognition, prompts, admission, stop selectors, memory, or observer semantics.
- **Evidence:** Keep world occurrences, an owner's subjective evidence, and analyst conclusions separate. IDs are run- and owner-qualified; content fingerprints are comparison keys, not identity, and are never exposed. A bounded marker in existing speech and record triples describes a frozen source version; its interpretation never installs a model or rewrites V3.
- **Scope:** Tracks hypotheses and model representations; no automatic marker production, automatic assimilation of models, scripted societal outcomes, authoritative science registry, cross-run joins, or truth verdict. Existing hypothesis speech remains supported; absent carrier evidence remains unresolved. No new command, event, capability flag/context, runner/result/pending version, replay pair, migration, API major, or Godot overlay.
- **Pins:** default runner/result v4/v2, v57 opt-in, 45 commands, 73 observer semantic types, 17 contexts/12 flags (9 owned), `v4-context-map-v6`, replay 27/`v25` travel and 28/`v26` instruments, Alembic `0017`, `/v1`, `observer-protocol-v1`; metrics append 271 → 275.

## Phase Index

1. [Phase 1: Freeze qualified science evidence](phase-01-evidence.md) — Tasks 1–2
2. [Phase 2: Attribute carriers and derive diffusion lineage](phase-02-lineage.md) — Tasks 3–5
3. [Phase 3: Publish bounded research artifacts and metrics](phase-03-publication.md) — Tasks 6–8
4. [Phase 4: Research UI, executable evidence, and release checks](phase-04-validation.md) — Tasks 9–12

## Cross-Phase Dependencies

- Task 3 needs Task 2 for exact finalized evidence. Task 4 needs Task 3's qualified carrier occurrences; Task 5 needs Task 4's V3 and context inputs.
- Tasks 6–7 need Task 5's derived output. Task 8 needs verified storage from Task 6.
- Tasks 9 and 10 both need Task 6's snapshot/identity contract and Task 8's routes. Task 10 also needs Task 7's availability contract for the science-off assertion. Task 11 gates Tasks 9–10; Task 12 records Task 11's outcomes.

## Tasks

### Phase 1: Freeze qualified science evidence

- [x] Task 1: Define qualified evidence and version keys ([details](phase-01-evidence.md#task-1-define-qualified-evidence-and-version-keys))
- [x] Task 2: Capture finalized boundaries and project V4 sources ([details](phase-01-evidence.md#task-2-capture-finalized-boundaries-and-project-v4-sources)) (depends on 1)

### Phase 2: Attribute carriers and derive diffusion lineage

- [x] Task 3: Project speech, teaching and records ([details](phase-02-lineage.md#task-3-project-speech-teaching-and-records)) (depends on 2)
- [x] Task 4: Join V3 genealogy, organizations, migration and cross-society context ([details](phase-02-lineage.md#task-4-join-v3-genealogy-organizations-migration-and-cross-society-context)) (depends on 3)
- [x] Task 5: Fold trajectory changes, loss and rediscovery ([details](phase-02-lineage.md#task-5-fold-trajectory-changes-loss-and-rediscovery)) (depends on 4)

### Phase 3: Publish bounded research artifacts and metrics

- [x] Task 6: Implement canonical sidecar storage ([details](phase-03-publication.md#task-6-implement-canonical-sidecar-storage)) (depends on 5)
- [x] Task 7: Append four detached metric families ([details](phase-03-publication.md#task-7-append-four-detached-metric-families)) (depends on 5)
- [x] Task 8: Serve read-only snapshots and pinned pages ([details](phase-03-publication.md#task-8-serve-read-only-snapshots-and-pinned-pages)) (depends on 6)

### Phase 4: Research UI, executable evidence, and release checks

- [x] Task 9: Build the read-only Science diffusion view ([details](phase-04-validation.md#task-9-build-the-read-only-science-diffusion-view)) (depends on 6, 8)
- [ ] Task 10: Prove the mechanism with an off-gate experiment ([details](phase-04-validation.md#task-10-prove-the-mechanism-with-an-off-gate-experiment)) (depends on 6, 7, 8)
- [ ] Task 11: Verify authority, compatibility and deterministic behavior ([details](phase-04-validation.md#task-11-verify-authority-compatibility-and-deterministic-behavior)) (depends on 9, 10)
- [ ] Task 12: Complete the docs checkpoint ([details](phase-04-validation.md#task-12-complete-the-docs-checkpoint)) (depends on 11)

## Commit Plan

- After Tasks 1–5: `feat: derive scientific knowledge diffusion from finalized evidence`
- After Tasks 6–8: `feat: publish scientific diffusion snapshots and metrics`
- After Tasks 9–12: `feat: expose and qualify scientific diffusion research views`

## Definition of Done

- All five channels and five transformations have explicit evidence semantics and negative tests; partial evidence never becomes a confirmed transfer, loss, or rediscovery.
- Actual admitted runs prove native teaching/uptake, a qualified model-reference relay into a durable record, an exact V3 written-record bridge through the read-only API, and carriage confirmed after migration qualification. Positive organization, society, and translation tests exercise the actual source builders or interpreter; report composed tests separately from unassisted outcomes.
- Capture and reader defaults are inert, sidecar twins are canonical, and privacy, compatibility, regression, docs and UI gates have recorded outcomes.
- Unassisted results and unavailable evidence stay separate from controlled mechanism evidence. Unexecuted gates are reported, not certified.
