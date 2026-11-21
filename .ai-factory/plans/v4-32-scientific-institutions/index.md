<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-32 Scientific Institutions

Plan ID: `v4-32-scientific-institutions`  
Mode: ultra  
Branch: `main` (existing; no branch or worktree created)  
Created: 2026-11-21

## Original Request
v4-32 scientific institutions

Naming requirement:

Use `v4-32-scientific-institutions`.

Allow organization/institution primitives to support persistent science-like practices.

Potential emergent features:

- experimenters
    
- record keepers
    
- teachers
    
- replication expectations
    
- archives
    
- shared instruments
    

Do NOT introduce predefined University or Academy classes.

Detect stable scientific practice analytically.

Track institutional lineage.

## Settings

- Testing: yes
- Logging: verbose, metadata only
- Docs: yes — mandatory `$aif-docs` checkpoint

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"  
Rationale: Deepens the existing `science` and `organizations` contexts through composition and a detached read model, without adding an actor, registry, or capability slot.

## Requirements Reconciliation

Authority: the original request defines scope; `AGENTS.md` and `.ai-factory/RULES.md`/`rules/base.md` govern code and verification; `.ai-factory/ARCHITECTURE.md` governs versioning and authority; the roadmap supplies linkage, not a behavioral or version contract. Older historical counts do not replace the documented V4-31 pins. No separate research artifact was selected.

| Decision / supported combination | Source and interpretation | Verification evidence |
|---|---|---|
| No predefined university/academy, mandatory profession, live science-institution ledger, authority, command, or scripted emergence | Original Request; architecture “Key Principles”; compose existing `OrganizationConceptLedger`, offices/institutional memory, speech, archives and physical facts | Architecture/import gate; admitted controlled actions; autonomous no-intervention proof |
| `science` and `organizations` on; bounded experimentation + predictive model per existing science gate; durable records and cultural provenance on; v56 without instruments, v57 with instruments | Architecture “Capability ownership” and V4-27–31 seams; this plan's detector applicability contract, **not** a new runner validation restriction | Actual runner construction, default/legacy pin tests, positive two-window coverage, optional v57 signals |
| Either owned flag off, or durable records unavailable: analysis unavailable, runner behavior unchanged. Existing configurations remain valid | Same architecture; no assumption that `science=False` implies no objective experimentation | Paired controls and representative existing science configuration |
| Repository, teaching, institutional-memory and instrument channels optional; unresolved or partial signals never fill missing evidence or count for qualification | Original Request says potential; existing modes, `docs/scientific-replication.md`, `docs/measurement-instruments.md`, architecture owner/physical distinction | Base vs optional channels; delivered vs inferred teaching; actual shared measurement and archive service |
| Two adjacent supported complete windows and exact anchors; no backdating, and no lineage through a coverage gap | Original Request stable practice and lineage; architecture detached analysis; explicit operational definition in Phase 2 | Positive, burst/solo, ambiguity, lost carrier, covered absence, gap, turnover, handoff, split/merge and prefix tests |
| Fresh organization participation is independently timed in v1 by an admitted contribution on the exact project goal referenced in the supporting owner concept | `src/world/_perception.py` and `src/agents/cognition/organization_concepts.py`: repeated observation refreshes owner context, not the action that supports it | Early controlled live context proof; old contributions and unrelated projects fail qualification |
| Opt-in completed-run research read model only; configured/absent/unauthorized/empty/corrupt distinguished | Architecture outer composition and V4-31 publication precedent | Snapshot/store/gated GET and Svelte tests |

## Architecture and Decisions

- **Practice can persist through existing channels.** Ordinary agents execute experiments; observed artifacts and repos provide durable carriers; owner-recognized roles/procedures, teaching and replication agreements stay local and contestable. Shared instrument use is observed use of a physical item, never a permission or claim that the item was used in a specific trial.
- **Three distinct layers.** Committed actions and custody are facts; memberships, procedures and expectations are owner claims; stability, practice-role descriptions and lineage are analytical results. No analytical output flows back into cognition, replay, admission, stop policy, memory or observer semantics.
- **Conservative base detector.** Within 32-tick windows require a deliberate admitted execution and service on a live, exactly anchored durable carrier by uniquely attributable organization participants. Require the same organization, activity family and surviving carrier in two consecutive complete windows plus two distinct contributing actors. Report optional signals and a coverage denominator independently. A stable label is evidence of repeat practice, not proof of science quality, a causal culture, or a particular institutional type.
- **Institutional lineage.** Track `sci-inst-` analytical episodes separately from organization identities. Record continuation, lapse and unknown continuity. Confirm marked handoffs, splits and merges only with an existing org transition and observed sustained successor practice on the same typed carrier. No gap bridging or cross-run links.
- **Scope and pins.** Explicit bounded in-process research capture/publication; one snapshot/store v1; read-only `/v1` pages and Svelte panel. No new capability/context, runner/result or pending format, SQL migration, world event/codec, command or Godot overlay. Keep 45 commands, 73 observer semantic types, 17 V4 contexts, 12 V4 flags (nine owned), Alembic `0017`, default runner/result v4/v2, opt-in v57 and existing replay selection; append exactly three detached metric families (268 → 271).

## Phase Index

1. [Phase 1: Compose existing practice evidence](phase-01-detached-evidence.md) — Tasks 1–3
2. [Phase 2: Detect repeat practice and track lineage](phase-02-detection-and-lineage.md) — Tasks 4–6
3. [Phase 3: Publish a bounded research view](phase-03-research-surface.md) — Tasks 7–9
4. [Phase 4: Qualify real composition and document the evidence limits](phase-04-composition-and-qualification.md) — Tasks 10–12

## Cross-Phase Dependencies

- Task 4 depends on Tasks 1–3 for typed evidence, exact contributor attribution and complete windows.
- Task 7 depends on Tasks 4–6 for stable rows, episode references and supported coverage semantics.
- Task 10 depends on Tasks 1–3 for bounded composition-only capture and is independent of publication. Task 11 depends on Tasks 8 and 10 for the real runner-to-authorized-read proof and extends the live context fixture introduced by Task 3. Task 12 also depends on the client work in Task 9.
- Task 12 depends on Task 11 so documented behavior and qualification match evidence actually obtained.

## Tasks

### Phase 1: Compose existing practice evidence

- [x] Task 1: Specify detached evidence and coverage ([details](phase-01-detached-evidence.md#task-1-specify-detached-evidence-and-coverage))
- [x] Task 2: Project finalized receipts ([details](phase-01-detached-evidence.md#task-2-project-finalized-receipts)) (depends on 1)
- [x] Task 3: Project organization context and optional practice signals ([details](phase-01-detached-evidence.md#task-3-project-organization-context-and-optional-practice-signals)) (depends on 1, 2)

### Phase 2: Detect repeat practice and track lineage

- [x] Task 4: Detect persistent practice ([details](phase-02-detection-and-lineage.md#task-4-detect-persistent-practice)) (depends on 1, 2, 3)
- [x] Task 5: Derive forward-only institutional lineage ([details](phase-02-detection-and-lineage.md#task-5-derive-forward-only-institutional-lineage)) (depends on 4)
- [x] Task 6: Register descriptive metrics ([details](phase-02-detection-and-lineage.md#task-6-register-descriptive-metrics)) (depends on 4, 5)

### Phase 3: Publish a bounded research view

- [x] Task 7: Define and publish canonical snapshots ([details](phase-03-research-surface.md#task-7-define-and-publish-canonical-snapshots)) (depends on 4, 5, 6)
- [x] Task 8: Add capability-gated read routes ([details](phase-03-research-surface.md#task-8-add-capability-gated-read-routes)) (depends on 7)
- [x] Task 9: Show practice and lineage in the Research UI ([details](phase-03-research-surface.md#task-9-show-practice-and-lineage-in-the-research-ui)) (depends on 8)

### Phase 4: Qualify real composition and document the evidence limits

- [x] Task 10: Compose a bounded experiment without seeding institutions ([details](phase-04-composition-and-qualification.md#task-10-compose-a-bounded-experiment-without-seeding-institutions)) (depends on 1, 2, 3)
- [x] Task 11: Qualify controlled and autonomous runs ([details](phase-04-composition-and-qualification.md#task-11-qualify-controlled-and-autonomous-runs)) (depends on 8, 10)
- [x] Task 12: Land authority gates and contributor documentation ([details](phase-04-composition-and-qualification.md#task-12-land-authority-gates-and-contributor-documentation)) (depends on 9, 11)

## Commit Plan

- Tasks 1–3: `feat(experiments): project detached institutional practice evidence`
- Tasks 4–6: `feat(analysis): detect persistent science practice and lineage`
- Tasks 7–9: `feat(research): publish and inspect scientific practice snapshots`
- Tasks 10–12: `test(experiments): qualify compositional scientific institutions`

## Definition of Done

- A controlled positive uses admitted runner actions and actual owner context, from finalized evidence through authorized read. A lack of autonomous emergence is valid, explicitly distinct from unavailable evidence.
- Complete-empty, partial, negative, ambiguous and stable windows remain distinct. Lineage is forward, deterministic, gap-aware and grounded by exact carrier and organization evidence.
- Optional emergent roles/practices remain descriptions, not preset actor classes or permissions. V1/V2 gates and disabled byte/behavior compatibility are retained.
- Each phase's focused commands and final applicable gates run, with honest `unexecuted` status for any environment-gated checks not run. Progress updates belong only in this index.
