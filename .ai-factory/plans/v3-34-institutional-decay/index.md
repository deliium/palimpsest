<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V3-34 Institutional Decay

Mode: ultra
Branch: main (stay on current branch; automatic branch creation disabled)
Created: 2026-10-21
Canonical stem: `v3-34-institutional-decay`
Status: implemented and verified (2026-10-21); all 15 tasks complete

## Original Request

v3-34 institutional decay

Plan naming requirement:

Canonical plan artifact MUST begin `v3-`.

Suggested stem:

v3-34-institutional-decay

Allow persistent institutions to weaken or disappear.

Potential mechanisms:

loss of legitimacy  
failure of succession  
population loss  
resource collapse  
missing records  
role abandonment  
competing institution  
cultural change

Do not script collapse events.

Track:

support  
participation  
procedure repetition  
succession continuity  
knowledge continuity

Allow institutions to:

emerge  
stabilize  
transform  
split  
collapse  
reappear

Provide lineage tracking across transformed institutions.

## Settings

- Testing: yes; network-free deterministic tests, Hypothesis invariants and compatibility gates; keep coverage enabled.
- Logging: verbose, metadata-only; no payloads or payload-surrogate fingerprints.
- Docs: yes; mandatory `$aif-docs` completion checkpoint.
- Language: English; preserve technical terms.
- Git: enabled; base `main`; stay on current branch; no worktree; no automatic implementation/commit/push. Skip push prompt when a later authorized commit occurs.
- Workflow: slug plan ID; normal verification. All task checkboxes live only in this index.
- Research: no research artifact was available or used. Algorithm thresholds below are explicit design decisions for this plan, not externally validated causal claims.

## Roadmap Linkage

Milestone: "M7 — V3 Generational Civilization"
Rationale: Deepen owner-scoped institutional continuity with evidence-based weakening and retrospective lineage, without owning the remaining `institutional_economy` flag or scripting institutional outcomes.

M7 stays open; M6's `multi_hop_testimony_tracking` is unrelated and stays unimplemented. Planning changes only this bundle, not the roadmap or source requirements.

## Requirements Reconciliation

Authority: user scope plus repository `AGENTS.md`, project axioms/base rules and architecture trust/versioning boundaries. The roadmap indicates scope, not an executable institutional model. Sources agree on non-scripted emergence and owner-scoped beliefs; the design below makes those constraints concrete.

| Decision / supported behavior | Source path and section | Verification evidence |
|---|---|---|
| Canonical bundle begins `v3-`; no prefix/branch creation | Original Request — naming; `.ai-factory/config.yaml` — git/workflow | Bundle path and integrity validation; git branch unchanged. |
| Weakening is private cognition, not an objective institution entity or forced destruction | Original Request — weaken/disappear; `.ai-factory/ARCHITECTURE.md` — Authority, Memory/testimony, Important V3 seams | New isolation tests; runtime confidence/speech change without command/event additions. |
| Preserve existing v1 concept/office decay when new mode is off | `src/agents/cognition/institution_concepts.py` — `_decay`, `_record_evidence`; `src/agents/cognition/offices.py` — `_decay`; architecture — optional-channel parity | Legacy/off-path comparison and fingerprints; BF/BG/BJ and V1/V2 gates. |
| New `institutional_decay_mode`, exact v54, same-owner concepts prerequisite; no new capability flag | Architecture — accepted-set/exact-key-set; `runner_models.py` — v53 prerequisites; `runner_serialization.py` — exact keysets | `test_runner_config_v54.py`, v53 and compatibility tests. |
| Five dimensions stay separate, unknown is not zero | Original Request — Track; `docs/institutional-memory.md` — channels/learning/limitations; `analysis/institution_emergence.py` — missing lanes absent | Dimension/coverage tests, denominator tests, no health scalar. |
| Loss of records does not erase acquired knowledge; successor recognition does not transfer content | `docs/institutional-memory.md` — Learning and use, Limitations; `tests/unit/test_institutional_memory_invariants.py` | Existing invariants plus new carrier-loss/succession/provenance cases. |
| Absence of sight is not vacancy, population extinction or collapse | `src/agents/cognition/offices.py` — `_process_availability`; architecture — owner-safe perception | Hidden/unobserved/dead-owner censoring and no false vacancy tests. |
| All six requested outcomes; lineage across structural changes without identity-by-label | Original Request — outcomes/lineage; `offices.py` — stable ID, revisions, predecessor; architecture — analysis-only cross-owner joins | Lifecycle fixtures, explicit predecessor/structural transform, split/reappearance DAG and ambiguity tests. |
| Potential mechanisms are ordinary evidence/context, not a collapse scheduler | Original Request — mechanisms/no script; architecture — no scripted institutions; BJ scenario — opportunity-only arms | BK structural-only arbiter; no forced outcome; descriptive mechanism evidence panels. |
| Legacy content-derived candidates cannot serve as stable temporal institution IDs | `analysis/institution_emergence.py` — `_candidate_id`, structural bundle; `analysis/institutional_persistence.py` — interval occupancy | New scoped episode ID stability and two-concurrent-pattern tests; old metric semantics unchanged. |
| Bounded histories/checkpoints remain subjective and outside objective replay | Architecture — checkpoint/event fold; `agent_runtime.py`, `runner.py` — staged commit/preflight; `docs/institutional-memory.md` — restart limitations | Continuation equality, atomic preflight, pruning/coverage and result wire-key tests. |
| Runtime carry traverses every actual perspective boundary | `src/simulation/perception.py` — `build_perspective`; `src/agents/cognition/contracts.py` — `Perspective.to_snapshot`; `agent_runtime.py` — perspective construction | Task 5 boundary validation; Task 6 real two-tick commit/carry and export/apply continuation, without synthetic snapshot injection. |
| Recognition must be reachable from empty native state without arbitrary social attachment | `institution_concepts.py` — `_freeze`, separate role/procedure grouping, `_social_draft`; `social_norms.py` — `_lineage`, `_apply_shared_upkeep` | Native shared-source binding table and public loop maintenance→recognition→weakening→renewal proof; unchanged off-path grouping. |
| Store raw quantities and aggregate once with explicit observed-cohort denominators | `world/observations.py` — occurrence provenance versus contribution projection; `.ai-factory/patches/2026-10-09-14.46.md` — named metric quantity must survive projection | Known-answer five-dimension fixture; cross-view aliases; common-cohort comparisons; no double windowing or population-support claim. |
| Stable lineage identity does not depend on the moving sample ring | Phase 1 — retained bounds/witnesses; existing stable office ID/predecessor contracts | Absolute inception/activity/revision witnesses, explicit pruned predecessor stubs and interval-local completeness; pruning-boundary restore/ID tests. |
| Detailed graph/trajectory output respects scalar-only metric values | `src/analysis/models.py` — `MetricDocument` value validation; `src/analysis/serialization.py` — `_encode_values`, `_decode_values` | Four versioned canonical JSON-string fields; real outer codec/inner payload roundtrip; shared schema unchanged. |
| Metrics + experiment additive; no migration/API/client scope | Architecture — version pins/dependencies; DESCRIPTION — V3-33 current baseline | Families 126→129; BK off gate; commands 43, semantics 73, migration 0017 and replay/API/protocol tests unchanged. |

### Supported combination matrix

`C` = same-owner institution concepts; `D` = decay; `O` = offices; `M` = institutional memory. Other existing optional modes/specs compose only through their inherited exact family rules. Each accepted row has strict enum/key validation and source-owner checks.

| Input / validation | Stored subjective state | Output / next behavior | Side effects / invariants | Verification |
|---|---|---|---|---|
| Legacy schema, D off | No decay ledger | Existing concept/office behavior and schema selection | No disabled fingerprint/trajectory change | Off-path equality, v53/BJ and V1/V2 tests. |
| v54, D on + C on, O/M off | Owner decay/concept pair; O/M dimensions disabled | Channel attrition, support/participation/procedure counts; ratios only with evidence | No fabricated succession/knowledge failure | Concepts-only config/runtime case. |
| v54, D+C+O, M off | Pair plus existing office state | Local support/succession evidence where uniquely bound | No global occupant; no content inheritance | Office config, contested/absent occupant tests. |
| v54, D+C+M, O off | Pair plus existing procedural memory state | Knowledge measurements where local channels bind | Missing records do not delete entries | Procedure-memory config and carrier-loss tests. |
| v54, D+C+O+M | Separate same-owner ledgers | All five dimensions when opportunities exist; otherwise unknown/not applicable | One-update O/M assessment lag; ordinary commands only | All-enabled runtime/continuation/collector path. |
| Mixed enabled/disabled owners | State only for enabled owners | Separate histories and coverage; no union of subjective state | Another owner's C/O/M cannot satisfy prerequisites | Mixed-owner config and preflight tests. |
| D on without local C, old schema with D on/key, or v54 without any D | Rejected before execution | Safe validation code | No silent schema promotion or mode stripping | v54 negative matrix. |
| Memory profile `species_default_institutional_memory_v1` on v53/v54 | Empty existing office/memory content; decay remains disabled for admitted learner | Ordinary blank-slate acquisition | No automatic parent/office-history copying | Profile and newborn copy-denial cases. |
| Same owner/tick identical update; conflicting repeat or decreasing tick | Identical retained pair and raw evidence/witnesses; conflicting/backward update rejected | No repeated loss/sample | No observer-driven advancement | Idempotence/time reversal tests. |
| Missing/hidden/gapped/pruned evidence or no transition opportunity | Retain known facts; coverage/exclusion metadata | Unknown/partial/not applicable/right-censored as appropriate | Never convert missing data into collapse | Window, pruning and censoring tests. |
| Prior stable + two covered low/no-renewal windows | No world mutation; detached classification only | Confirmed scoped collapse at confirmation time | No scripted shock, backdated knowledge or inferred universal extinction | Collapse hysteresis/prefix tests. |
| Structural replacement/split or reappearance with sufficient lineage evidence | Immutable past episodes plus new DAG nodes/edges in research output | Transform/split/reappearance edges | Labels alone and multiple plausible matches do not prove lineage | Lineage identity/matching/ambiguity tests. |
| Initial samples evicted; retained identity witness exists | Stable absolute IDs plus explicit partial/stub references, not lifecycle labels in cognition | Surviving identity is preserved; unobserved prior states remain unknown | No ordinal reset, fabricated prior stability or permanent censoring of later complete intervals | 16-pattern eviction/restore and interval-specific coverage tests. |
| Structured research graph/trajectory in a metric | Versioned canonical JSON **string** inside scalar `values` | Real encode/decode plus inner JSON parsing | No nested maps/lists in shared `MetricDocument`, wire-schema/API change or live-cognition use | Known-answer codec tests for all three families. |

### Existing artifact discrepancies

- ROADMAP's dated recent-V3 section still reports 103 metric families; DESCRIPTION/ARCHITECTURE's V3-33 seam reports 126. Use the explicitly current 126 baseline and executable catalog, not historical roadmap counts.
- ARCHITECTURE's “Current baseline through V3-32” heading already contains v53/V3-33 data. Preserve history and update the current baseline heading during the implementation documentation checkpoint.
- DESCRIPTION contains historical earlier counts alongside its later V3-33 section. Do not rewrite historical facts into current pins.

These are dated-summary discrepancies, not conflicting behavioral requirements. No unresolved requirement conflict or blocking open question remains.

## Architecture and Decisions

1. **Subjective versus analytical authority.** New owner-local `institutional_decay_mode` defaults disabled. Enabled cognition uses fresh-evidence, channel-specific attrition under locked `institutional-decay.v1`; old concept/office policies remain unchanged when disabled. Collapse, transformation, split and reappearance classifications/graphs are **detached analysis**, never commands or world entities.
2. **Concrete behavioral seam.** Adjust ordinary `InstitutionConceptLedger` strengths/status on the enabled path before existing office inference/planning. Existing recognized-concept speech may cease/resume; no forced command, universal resignation, property transfer, permission change or reward scalar. Continued autonomous participation remains possible even when an owner stops recognizing an institution-like pattern.
3. **Fresh evidence and reachable recognition.** Enabled-only native grouping binds compatible role/procedure evidence and exactly source-matched owner norm evidence to one structural pattern. Repeated accepted shared upkeep can reach the existing three-channel recognition threshold from empty state; arbitrary minimum-group attachment and preconstructed recognized concepts are not substitutes. Canonical action keys deduplicate projection/occurrence views separately from per-channel belief credit; synthetic recall strings are not native memory evidence. Legacy grouping is unchanged when off.
4. **Raw evidence, one aggregation, honest availability.** Track the five dimensions through per-update sufficient statistics, then calculate four-update windows once in analysis. Actor ratios describe a stable resolved **observed cohort**, not all population or objective eligibility. Adjacent-window declines use a common cohort. Source ticks remain distinct from observation/update ticks; absent data is not zero. Six concept strengths are not renamed into five measures. Learned entries survive carrier loss; turnover does not copy knowledge.
5. **Cyclic dependency avoided.** Concept preparation reads prior owner offices/memory, not their just-prepared results. Source windows disclose this one-update lag; no preparation-order rewrite or cross-owner batch.
6. **Complete carry and bounded evidence.** The sidecar traverses runtime → `build_perspective` → `Perspective` → `to_snapshot` → loop → deferred commit, plus actual checkpoint export/apply. Raw samples/receipts remain outside objective replay. Track per-pattern sample and separate receipt pruning boundaries; old pruning does not poison later complete windows. Factual identity/activity witnesses survive the ring but cannot prove an unavailable prior stable/collapsed state. No final-state interpolation, new wire result field, subjective DB table or whole-run history promise is introduced.
7. **Pruning-safe scoped lineage.** Owner/group/actual inception binds a pattern despite mutable concept IDs. Native action/target components support unique structural matching. Episode IDs use retained **absolute activity-span and structural-revision witnesses, never retained-history ordinals**. Explicit predecessor stubs preserve known IDs when full evidence is pruned. Confirmed transform/split/return needs sufficient retained evidence; pure growth may yield a separate continuation link without merging historical IDs. Cross-owner alignment preserves dissent, not a global institution registry.
8. **Versioning.** New exact v54 cognition keyset adds only `institutional_decay_mode`; roots remain the v53 family. Default write stays v4; memory mode/profile accept v53/v54 without weakening same-owner validation. No new V2/V3 capability slot; `institutional_economy` stays unowned.
9. **Research output without a shared-schema change.** Three families: `institutional_decay@1`, `institution_lifecycle@1`, `institution_lineage@1` (126→129). Counts/ratios remain scalars; structured output uses versioned canonical `dimension_trajectories_json`, `mechanism_evidence_json`, `episodes_json`, and `lineage_graph_json` string values. Real metric codec roundtrips preserve these payloads. BK has paired off/on and existing record/teaching/limited controls; synthetic fixtures prove rare classifications, not mandatory experiment collapse.
10. **No scope expansion.** No scripted collapse/creation schedule, shock DSL, economic institutions, automatic institutional inheritance, new newborn profile, court/state/government category, migration, API route, observer semantic/protocol bump, UI visualization, LLM prompt/provider change, dependency or broad refactor.

### Locked numerical and retention decisions

| Decision | Value / interpretation |
|---|---|
| Subjective policy | `institutional-decay.v1`; per-channel unrefreshed loss 0.04 per executed update, unit clamp, 0.000001 quantum |
| Retention | 16 patterns, 256 raw samples and 512 receipts per owner; per-pattern sample/receipt boundaries; bounded current/previous factual activity witnesses survive sample eviction |
| Window clock / aggregation | Observation/update ticks, with native source intervals retained separately; raw sufficient statistics → one four-update window; actor ratios use a stable observed cohort and decline comparisons a common cohort |
| Analysis policy | `institutional-lifecycle.v1`; two adjacent nonoverlapping complete windows `[t-7,t-4]`, `[t-3,t]` for stability/collapse confirmation; pruning evaluated against each interval |
| Strong / low / renewal thresholds | 0.50 / 0.10 / 0.30 on comparable available core ratios; no single health score |
| Weakening | Prior stable history plus at least 0.10 comparable-window decline in a core measure or legitimacy strength |
| Collapse | Prior stable, two complete low windows, at least two core measures low including practice, no core ratio >0.30 and no fresh associated practice; confirm at second window end |
| Structural lineage | Same context/function; at least two shared structural anchors and Jaccard ≥0.50 plus repeated successor practice, or explicit local office predecessor with practice; ambiguity never broken by arbitrary choice |
| Episode identity | Versioned owner/scope + local-pattern ID + retained absolute activity-span start + structural-revision witness; no ordinal or moving-window index; pruned ancestors become explicit stubs |
| Detailed metric payloads | Four schema-tagged canonical JSON-string values; scalar summaries; unchanged shared metric model/codec schema |
| Unchanged pins | Commands 43; observer semantics 73; latest channel-selected replay V22/codec v20; Alembic 0017; `/v1`; `observer-protocol-v1`; `prepare_parallel=False` |

## Phase Index

1. [Phase 1: Contracts and configuration](phase-01-contracts-and-configuration.md) — Tasks 1–3
2. [Phase 2: Subjective weakening and runtime continuity](phase-02-subjective-weakening-and-runtime.md) — Tasks 4–6
3. [Phase 3: Temporal analysis and transformed lineage](phase-03-temporal-analysis-and-lineage.md) — Tasks 7–9
4. [Phase 4: Metrics and Experiment BK](phase-04-metrics-and-experiment-bk.md) — Tasks 10–12
5. [Phase 5: Invariants, verification and documentation](phase-05-invariants-verification-and-docs.md) — Tasks 13–15

## Cross-Phase Dependencies

- Task 2 depends on Task 1; Task 3 depends on Tasks 1–2.
- Task 4 depends on Tasks 1–3; Task 5 depends on Task 4; Task 6 depends on Tasks 4–5.
- Task 7 depends on Tasks 5–6; Task 8 depends on Task 7; Task 9 depends on Tasks 7–8.
- Task 10 depends on Tasks 8–9; Task 11 depends on Tasks 6–10; Task 12 depends on Tasks 2, 5–6 and 10–11.
- Task 13 depends on Tasks 1–12; Task 14 depends on Task 13; Task 15 depends on Task 14.
- Task 5 introduces/validates perspective plumbing and initializes the runtime slot; Task 6 adds commit/checkpoint state and the actual two-tick runtime carry proof. Analytical pruning/ID assertions run in Tasks 7–9, not prematurely in Task 6. No dependency cycle or new task is needed.
- Read the full relevant phase before executing its tasks. Preserve default-off behavior at every checkpoint; do not enable an unfinished feature in the default runner.

## Tasks

### Phase 1: Contracts and configuration

- [x] Task 1: Define owner-local decay contracts and locked policy ([details](phase-01-contracts-and-configuration.md#task-1-define-owner-local-decay-contracts-and-locked-policy))
- [x] Task 2: Add exact runner-config-v54 and supported combinations ([details](phase-01-contracts-and-configuration.md#task-2-add-exact-runner-config-v54-and-supported-combinations)) (depends on 1)
- [x] Task 3: Compose cognition mode, policy and fingerprints ([details](phase-01-contracts-and-configuration.md#task-3-compose-cognition-mode-policy-and-fingerprints)) (depends on 1, 2)

### Phase 2: Subjective weakening and runtime continuity

- [x] Task 4: Implement fresh-evidence channel attrition ([details](phase-02-subjective-weakening-and-runtime.md#task-4-implement-fresh-evidence-channel-attrition)) (depends on 1, 2, 3)
- [x] Task 5: Measure five dimensions and integrate ordinary cognition ([details](phase-02-subjective-weakening-and-runtime.md#task-5-measure-five-dimensions-and-integrate-ordinary-cognition)) (depends on 4)
- [x] Task 6: Commit, checkpoint and export bounded owner histories ([details](phase-02-subjective-weakening-and-runtime.md#task-6-commit-checkpoint-and-export-bounded-owner-histories)) (depends on 4, 5)

### Phase 3: Temporal analysis and transformed lineage

- [x] Task 7: Build detached temporal evidence without conflating candidates ([details](phase-03-temporal-analysis-and-lineage.md#task-7-build-detached-temporal-evidence-without-conflating-candidates)) (depends on 5, 6)
- [x] Task 8: Classify emergence, stabilization, weakening and collapse ([details](phase-03-temporal-analysis-and-lineage.md#task-8-classify-emergence-stabilization-weakening-and-collapse)) (depends on 7)
- [x] Task 9: Track transformation, split and reappearance lineage ([details](phase-03-temporal-analysis-and-lineage.md#task-9-track-transformation-split-and-reappearance-lineage)) (depends on 7, 8)

### Phase 4: Metrics and Experiment BK

- [x] Task 10: Register three versioned metric families ([details](phase-04-metrics-and-experiment-bk.md#task-10-register-three-versioned-metric-families)) (depends on 8, 9)
- [x] Task 11: Integrate completed-run collection ([details](phase-04-metrics-and-experiment-bk.md#task-11-integrate-completed-run-collection)) (depends on 6, 7, 8, 9, 10)
- [x] Task 12: Add non-scripted Experiment BK ([details](phase-04-metrics-and-experiment-bk.md#task-12-add-non-scripted-experiment-bk)) (depends on 2, 5, 6, 10, 11)

### Phase 5: Invariants, verification and documentation

- [x] Task 13: Add isolation and scientific invariant gates ([details](phase-05-invariants-verification-and-docs.md#task-13-add-isolation-and-scientific-invariant-gates)) (depends on 1–12)
- [x] Task 14: Verify representative continuation and legacy compatibility ([details](phase-05-invariants-verification-and-docs.md#task-14-verify-representative-continuation-and-legacy-compatibility)) (depends on 13)
- [x] Task 15: Complete mandatory documentation and context checkpoint ([details](phase-05-invariants-verification-and-docs.md#task-15-complete-mandatory-documentation-and-context-checkpoint)) (depends on 14)

## Commit Plan

- **Commit 1** (Tasks 1–3): `feat(cognition): define gated institutional decay contracts`
- **Commit 2** (Tasks 4–6): `feat(cognition): add evidence-based institutional weakening`
- **Commit 3** (Tasks 7–9): `feat(analysis): track institutional lifecycles and lineage`
- **Commit 4** (Tasks 10–12): `feat(experiments): add institutional decay metrics and BK treatments`
- **Commit 5** (Tasks 13–15): `test(institutions): enforce decay invariants and document V3-34`

These are proposed implementation checkpoints, not authorization to commit in this planning session.

## Definition of Done

- Fresh evidence can sustain/recover a private pattern; loss of renewal can weaken recognition without any scripted collapse or new authoritative institution entity.
- Support, participation, procedure repetition, succession continuity and knowledge continuity are computed once from raw native evidence with explicit observed-cohort denominators, known-answer tests, provenance and unknown/partial states.
- Emerging, stable, transformed, split, collapsed and reappeared outcomes are representable and tested; collapse confirmation is scoped, hysteretic and censored on missing evidence.
- Stable absolute local/episode IDs and deterministic lineage DAG preserve supported transformations/splits/returns through sample eviction and checkpoint restore; pruned predecessors are stubs, not invented lifecycle/knowledge evidence.
- v54 is strict/default-off and composes only supported same-owner combinations; legacy configs, fingerprints, experiments, replay and API/observer identities remain compatible.
- Three versioned families and neutral BK treatments work through real completed-run evidence and actual metric codec roundtrips with schema-tagged JSON-string research fields; the shared scalar metric format stays unchanged. No experiment must manufacture collapse.
- Runtime checkpoint continuation is deterministic; source/sample caps and incomplete history are explicit. No new universal durable subjective restart promise is made.
- Focused/full tests, architecture/V1/V2 gates, Ruff, mypy and import-linter pass; mandatory documentation checkpoint is complete. No feature regression is waived.
- M7 and unowned capability flags remain open. Only this index owns task progress; all linked phases remain consistent.

## Refinement Notes — 2026-10-21

All five refinements approved by the user were applied in place; 15 tasks and all unchecked statuses are preserved:

1. Added the actual perspective carry path and real two-tick/restore proof, including `contracts.py` and `simulation/perception.py`.
2. Defined native source binding and an empty-ledger shared-upkeep recognition/weakening/renewal path instead of relying on arbitrary social association or constructed recognized concepts.
3. Replaced twice-windowed measurements with raw per-update sufficient statistics, explicit source aliases/cohort formulas, single aggregation and exact five-dimension known-answer tests.
4. Replaced sliding-history episode ordinals with retained absolute identity witnesses, explicit pruned predecessor stubs and interval-local coverage tests; bounded-history limitations remain explicit.
5. Specified versioned canonical JSON-string research fields and real encode/decode proofs compatible with the existing scalar-only metric format.

No new task, feature, branch, dependency package, migration, API or shared wire-schema change was added. Task-internal verification timing was clarified so runtime carry tests follow Task 6's commit work and analytical ID tests follow Tasks 7–9. The original request is preserved byte-for-byte; no application implementation or tests were run in this refinement invocation.

## Execution Entry

`$aif-implement @.ai-factory/plans/v3-34-institutional-decay/index.md`

Use the explicit entrypoint because this repository contains many plans and branch creation is disabled. Begin with Phase 1; this planning session does not start implementation.
