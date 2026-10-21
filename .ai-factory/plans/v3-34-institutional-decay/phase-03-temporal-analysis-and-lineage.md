# Phase 3: Temporal analysis and transformed lineage

Plan: [index.md](index.md)
Tasks: 7–9
Depends on: Tasks 4–6

## Objective

Classify observed institution-like lifecycles and preserve evidence-backed transformed/split/reappearing lineage without creating a global institution registry or feeding analytical truth into cognition.

## Current-Code Evidence

| Path | Symbols / sections | Why it matters |
|---|---|---|
| `src/analysis/institution_emergence.py` | `InstitutionLaneRow`, `compute_institution_candidates`, `_candidate_id` | Existing candidates hash evidence content and currently collect structural lanes into one bundle; unsuitable as stable temporal IDs. |
| `src/analysis/institutional_persistence.py` | `compute_institutional_persistence`, `_survival_curve` | Existing persistence is interval-based, not a lifecycle/lineage state machine or censored survival estimator. |
| `src/analysis/offices.py` | `harvest_office_rows`, `align_office_roles` | Exact function/context matching, duplicate-owner ambiguity, partial coverage. |
| `src/analysis/institutional_memory.py` | `_align_channels`, `_cross_occupant_counts`, `_build_edges` | Actual ordered acquisition/source-path evidence differs from declared testimony. |
| `src/analysis/technique_lifecycle.py` | `classify_technique_lifecycle`, `technique_lineage_diffusion` | Detached deterministic lifecycle precedent; do not import its technology semantics into institutions. |
| `src/experiments/composition.py` | `institution_*_rows_from_*` | Outer composition owns cross-boundary projection. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/analysis/institutional_decay.py` | create | Detached rows, coverage, window aggregation and lifecycle classification. |
| `src/analysis/institution_lineage.py` | create | Temporal episode identities, lineage edges and validation. |
| `src/analysis/__init__.py` | modify | Explicit public exports. |
| `src/experiments/composition.py` | modify | Convert new owner exports and existing detached event/office/memory evidence to analysis-owned rows. |
| `tests/unit/test_institutional_decay_analysis.py` | create | Window/state/coverage semantics. |
| `tests/unit/test_institution_lineage.py` | create | Transform/split/reappearance/ambiguity DAG cases. |
| `tests/unit/test_institutional_decay_composition.py` | create | Typed source projection, real evidence path and native provenance. |

## Task 7: Build detached temporal evidence without conflating candidates

### Intent

Keep owner-local evidence distinct, preserve intermediate samples, and avoid fabricating lifetimes from the final snapshot or the legacy all-structural-rows bundle.

### Implementation Steps

1. Define analysis-owned `InstitutionTemporalRow`, `InstitutionWindowRow`, `InstitutionLifecycleResult`, `InstitutionContextEvidenceRow`, and strict input validators in `analysis/institutional_decay.py`. Temporal rows preserve per-update sufficient statistics: actor cohorts, supporter/root pairs, accepted action keys, performed-procedure flags, unique transition/entry sets, source intervals and identity witnesses. Window rows contain the resulting numerators/denominators/ratios and availability. Do not import cognition classes or pass a precomputed rolling ratio as a raw input.
2. Add `institution_decay_rows_from_ledgers(...)` and `institution_decay_context_from_events(...)` to `experiments/composition.py`, which may consume public cognition/simulation contracts. Preserve each owner/local-pattern binding and sample tick. Source equality, not enumeration order, determines duplicate identity. Reject conflicting duplicates; canonical-sort legitimate rows by `(owner, local_pattern, tick)`.
3. Group **within owner** by the stable pattern binding, not legacy content-derived candidate ID. Preserve all distinct concurrent patterns; do not reuse `compute_institution_candidates`' global structural bundle as a temporal entity. Optional office links require exact function/context and a unique local match; ambiguous matches carry exclusions instead of merging.
4. Build trailing four-**observation/update-tick** windows `[t-3, t]` exactly once from raw samples, using Task 5's explicit set/denominator formulas. For confirmation compare `[t-7, t-4]` and `[t-3, t]`, never overlapping windows that reuse the same raw updates. Preserve native source intervals separately; an observation timestamp is not an action timestamp. A complete window needs all four updates, observed native scope, and no pruning boundary intersecting its required sample/source interval. Assess pruning per pattern and interval, not from `pruned_count > 0` alone. Missing samples, hidden scope, absent mode, unresolvable binding and dead-owner intervals do not become zero. Keep partial counts but exclude them from collapse confirmation.
5. Cross-owner knowledge continuity uses existing institutional-memory detached paths: a later owner's actual acquisition after the role transition plus an observed carrier/delivery path. Declared same-root frames alone cannot prove transfer. Report cross-owner continuity separately from Task 5's owner-local retained-knowledge measure. Do not automatically equate independently named owner patterns.
6. Project objective context retrospectively only: native death/entry/termination, resource/production/public-good failures, physical record loss/damage, and observed action participation. Scope these to an evidence-linked native target/location and interval; keep unmatched events unassigned. Existing event types only; no arbitrary string scraping or global causal labels.

### Required Interfaces and Contracts

`compute_institutional_decay(rows, *, as_of_tick, context_rows=()) -> InstitutionLifecycleResult` is pure, deterministic and analysis-only. It rejects future rows instead of reading beyond the supplied high-water mark. A final ledger with no samples is insufficient for temporal conclusions; return absent/partial, not a generated history.

### Requirement Evidence

User tracking and lineage requirements; architecture analysis-only joins; existing office/memory alignment and pruning rules; source-code evidence that legacy candidate IDs and bundles are not temporal identities.

### Error Handling and Logging

Safe errors for malformed spans, future evidence, invalid primitive types, owner/scope mixing and conflicting duplicates. DEBUG row/window/exclusion counts. Never log primitive source hashes or claim payloads as surrogates.

### Tests

`test_institutional_decay_composition.py`: real completed runtime sample projection; occurrence/projection aliases and ambiguous dedup exclusion; two simultaneous local patterns remain separate; same label/different contexts; ambiguous office matches; unordered inputs; cross-owner declared-only versus actual delivery; final-only snapshot; future input rejection. `test_institutional_decay_analysis.py`: complete/partial/gapped windows, observation/source timing, interval-specific pruning, disabled/empty/unknown and exact known-answer set aggregation. In one four-update fixture, keep cohort `{A,B,C}` visible throughout, two independently evidenced supporters `{A,B}`, accepted actions by `{A,C}` (including a duplicated projection and repeated A action), and procedure performance in three updates: support `2/3`, participation `2/3`, repetition `3/4`. Assert action duplication does not alter any result. For a changed-cohort adjacent window, assert decline is recomputed on the common cohort, not from a misleading difference of raw ratios. Distinct transition sets prove succession `1/2` and retained knowledge `2/3`; repeated carried records do not inflate either denominator.

### Acceptance Criteria

No synthetic time series, global bundle collapse, or false zero from missing data. All conclusions retain a source interval, scope and coverage denominator.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_decay_composition.py tests/unit/test_institutional_decay_analysis.py tests/unit/test_institutional_memory_analysis.py -q`

Expected: isolated evidence projection and honest coverage checks pass.

## Task 8: Classify emergence, stabilization, weakening and collapse

### Intent

An analytical collapse is a confirmed end of previously persistent activity **within a stated evidence scope**, not a world event, universal fact or trigger.

### Implementation Steps

1. Define `InstitutionLifecycleState` with `EMERGING`, `STABLE`, `WEAKENING`, `COLLAPSED`; define transition kinds independently, including `TRANSFORMED`, `SPLIT`, `REAPPEARED` from Task 9. A scope may be `UNKNOWN`/`RIGHT_CENSORED` in availability, not a falsely observed lifecycle state.
2. Lock analytical policy `institutional-lifecycle.v1`: window 4 ticks; confirmation requires two adjacent, nonoverlapping complete windows; strong ratio threshold `0.50`, low ratio threshold `0.10`, renewal floor `0.30`; values are quantized before comparisons. These are descriptive research thresholds, not world rules or runner tuning keys.
3. Emerging means a locally recognized pattern with fresh structural practice in a covered window. Stable requires recognized evidence in both windows, at least two available core measures (support, participation, procedure repetition) at/above `0.50`, and fresh participation or repeated procedure. If too few core denominators exist, report emerging/partial rather than fabricating stability. Succession and knowledge are additional continuity evidence, never prerequisites for an institution with no transition opportunity.
4. Weakening requires prior stable history and a decline of at least `0.10` in one comparable core measure or legitimacy strength relative to its previous complete window, with no simultaneous classification of collapse. Retain individual declines/increases: improvement in one dimension does not cancel another dimension's loss. A pruned prior window cannot establish a decline.
5. Collapse requires prior confirmed stability, two adjacent complete windows with at least two comparable core measures at/below `0.10` (including participation or procedure repetition), no available core ratio above `0.30`, and no fresh associated practice during the confirmation interval. If scope visibility, temporal continuity, denominators or history are incomplete, censor rather than collapse. Missing institutional records alone, an unobserved population, or disputed succession alone can never satisfy this rule.
6. Collapse is confirmed only at the second window end, not backdated as known earlier. Store last-active source/observation ticks and confirmation tick separately. A no-collapse run is valid. End of run is right-censored; observer death or loss of registered runtime terminates coverage, not the institution. Population/resource decline can remove actual practice opportunities but no timer or named shock changes the state by itself. Complete windows after an old pruning boundary can again establish fresh local stability; they cannot prove an unavailable earlier stable/collapsed interval. An identity witness or predecessor stub is not a lifecycle-state latch. Report unknown prior state when that evidence is gone, rather than resetting identity or claiming a new institution emerged just because the sample ring moved.
7. Cause output is a **nonexclusive evidence-association panel**, not causal identification: `legitimacy_decline`, `succession_discontinuity`, `population_loss`, `resource_failure`, `record_unavailability`, `role_abandonment`, `competing_pattern`, `cultural_change`. Associate only when a decline interval overlaps locally bound evidence (or detached objective context for population/resource/record tags). Include the evidence class, interval, and unknown/excluded counts. Competing pattern requires a distinct growing pattern with shared function/context and resolved participant overlap; cultural change requires actual locally evidenced norm/convention/semantic revision. Neither tag automatically weakens or collapses anything.
8. Keep historical BF persistence metrics unchanged; publish the new state model in new families. Do not rename the old interval occupancy curve as Kaplan–Meier or silently reinterpret its output.

### Required Interfaces and Contracts

Window/state records expose thresholds/policy version, state/transition confirmation times, source counts, five dimension panels, legitimacy strength and coverage flags. All classifications are scoped analytical hypotheses. No analytical result is passed to runner cognition, prompts, memory or the engine.

### Requirement Evidence

User — emergence/stability/collapse without scripting; architecture — retrospective classifications, no objective institution registry; office absence and institutional knowledge-retention contracts limit negative inference.

### Error Handling and Logging

Invalid policy constants fail closed. Insufficient evidence produces availability/censoring, not exceptions or zeros. DEBUG state/transition counts; INFO completion counts; no per-pattern identities or source lists in operational logs.

### Tests

`test_institutional_decay_analysis.py`: emergence-only, sustained stability, legitimacy-only weakening, partially improving dimensions, stability then sustained collapse, single low window/no collapse, late confirmation/no future leakage, unknown scope, missing ratios, capped histories, all observers dead/right-censor, record loss with preserved knowledge, succession dispute without collapse, comparable opportunity denominators, no-collapse run. Use ordered synthetic evidence fixtures to prove each state without scripting runtime events; also evaluate real exported samples from Task 7.

### Acceptance Criteria

Every collapse has prior stability, two complete low/no-renewal windows and explicit confirmation/evidence scope. Associated mechanisms are descriptive, never scripted causes.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_decay_analysis.py tests/unit/test_institution_emergence.py -q`

Expected: threshold/hysteresis/censoring tests and legacy BF semantics pass.

## Task 9: Track transformation, split and reappearance lineage

### Intent

Preserve related histories while distinguishing continuity, structural change, branching and unrelated new emergence. Do not equate an institution's name, current supporters or evidence-content hash with its identity.

### Implementation Steps

1. Define `InstitutionEpisode`, `InstitutionEpisodeStub`, `InstitutionLineageEdge`, `InstitutionLineageResult` and `compute_institution_lineage(...)` in `analysis/institution_lineage.py`. Episode IDs hash a versioned canonical tuple of policy, owner/scope, retained local-pattern ID, **absolute activity-span start witness**, and structural-revision witness key. Do not use an episode ordinal, current sample index, retained-window start, aggregate content hash or a legacy synthetic first tick. Continuous activity keeps its persisted witness through buffer eviction; the first activity after eight fully covered inactive updates provides a distinct factual return witness. A `REAPPEARED` edge still requires analytical evidence of prior collapse and renewed recognition; the witness alone never proves collapse. New/returned episodes remain distinct DAG nodes without a cycle.
2. Stable local binding, anchor growth, occupant replacement, renamed labels and changed support alone are continuation of the same episode. An observed material office revision with explicit `predecessor_office_id`, or changed structural pattern satisfying the matching rule below, creates a linked episode rather than rewriting the parent. If native signature growth creates a distinct policy binding but unique evidence proves pure continuation, retain both absolute node identities with a `CONTINUED` edge; do not retroactively merge published node IDs or count that edge as transformation/split/reappearance. Same-binding continuation is not a self-edge.
3. Structural matching requires the same native context/function, at least two shared **structural component** anchors captured by Task 4, Jaccard overlap at least `0.50`, and repeated successor practice over a complete four-tick window. Do not compare only the legacy whole-sequence concept anchor: native procedures with changed sequences must still expose their shared components. Role/function components are actor-independent; participant sets remain separate evidence. Social expectation/legitimacy tokens, labels, shared declared roots and equal evidence hashes alone are insufficient. Explicit owner-local office predecessor evidence may replace the overlap test but still requires successor practice and time ordering.
4. Build the bipartite predecessor/successor match graph for adjacent covered windows, using only already-incepted predecessors. Remove same-binding continuation pairs from the new-child candidate set before counting children. A unique one-to-one match with structural replacement (at least one removed and one new structural anchor), or an evidenced changed role signature, yields `TRANSFORMED`; pure anchor growth remains continuation. One parent to two or more **new** successors yields `SPLIT` only when each child independently meets the match/practice test and has distinct structural anchors plus a distinct supported role-signature or nonidentical resolved participant set. Children can coexist with a continuing parent; do not require parent collapse or count the parent as its own child. Multiple plausible parents or indistinguishable children produce ambiguous candidate links, not arbitrary tie-breaking.
5. After a confirmed collapsed episode, repeated fresh practice can reestablish recognized/stable evidence using the same rules as new emergence. Same retained binding gives `REAPPEARED`; a changed binding needs the explicit predecessor or unique structural match above. Identical labels or independently reinvented practices without lineage evidence yield unrelated emergence, not a proven return. Keep retained knowledge versus lost/relearned knowledge visible in the edge evidence.
6. Retain edge kind, parent/child IDs, inception/confirmation times, binding method, source evidence references, and confidence class (`observed_local_predecessor`, `structural_match`, `ambiguous`, `unresolved`, `pruned`). When a referenced predecessor witness remains known but its samples are gone, emit `InstitutionEpisodeStub` with that same absolute ID and `pruned` coverage, not a fabricated fully observed parent or dangling ID. Such stubs/links do not count as confirmed transformation, split, prior collapse or knowledge transfer. Pruning changes evidence availability, never the surviving node's ID. Reject self-edges, backward/zero-order edges and cycles. Canonical-sort inputs/edges; no shared mutable owner state or full-history guarantee beyond retained evidence.
7. Cross-owner alignment is a detached optional view only: exact function/context with unique matches and overlapping coverage, plus actual provenance for knowledge transfer. Preserve separate owner episodes and dissent. A cross-owner similarity group is not a global authoritative identity; unresolved/pruned links remain visible and do not contribute to confirmed lineage counts.

### Required Interfaces and Contracts

Lifecycle states and lineage edge kinds are independent: a stable institution-like pattern may transform or split without collapsing; a collapsed pattern may never reappear. Exports form a deterministic DAG with immutable historical nodes. No new world events or communication semantics encode these analytical edges.

### Requirement Evidence

User — transform/split/reappear and lineage across transformed institutions; office stable identity/predecessor fields; architecture — owner identity and analysis-only cross-owner comparisons. New episode IDs explicitly replace use of mutable BF candidate hashes for this purpose, without changing BF metrics.

### Error Handling and Logging

Reject malformed/cyclic edges and future-dependent input; valid ambiguous matches remain reported exclusions. DEBUG edge-kind/ambiguity/pruning counts, never lineage payloads or labels.

### Tests

`test_institution_lineage.py`: stable IDs after added evidence, renaming/support/occupant change without transformation, explicit predecessor transformation, unique structural transformation, genuine two-child split, continued parent excluded from its child count, cross-binding growth continuation without retroactive node merging, insufficient/divergent anchors, multiple-parent ambiguity, label-only false matches, collapse→reappearance, independent reinvention, reacquisition with lost records and two owners disagreeing. Run more than 16 updates with 16 patterns to evict initial samples: surviving episode IDs must equal their pre-eviction IDs; pruned parent stubs retain IDs but cannot prove prior stability/collapse/knowledge handoff. A later complete window becomes usable despite historical pruning; unavailable prior state remains unknown. Restore a checkpoint at the pruning boundary and verify identical IDs/edges. Include native multi-kind `ObservedOccurrence` → Task 4 extraction → exported samples → lineage: parent components `{a,b,c,d}` and repeated child sets `{a,b}` / `{c,d}` each share two components and Jaccard 0.50; replacement `{a,b,c}` → `{a,b,d}` also has Jaccard 0.50. Letters denote actual digests from valid native kinds/targets, not parsed labels or invented event kinds. Property-test ordered episode DAGs, backward/cycle rejection, prefix causality and input-order invariance.

### Acceptance Criteria

All six requested lifecycle outcomes can be represented and independently verified; transformation/split/reappearance preserve parent evidence without fabricating global identity or content transfer.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_institution_lineage.py tests/unit/test_institutional_decay_analysis.py -q`

Expected: deterministic lineage/state tests pass, with ambiguous matches excluded from confirmed edges.

## Phase Risks and Mitigations

- Existing grouping is too coarse for temporal identity: introduce separate scoped temporal rows and leave old metric semantics intact.
- Incomplete evidence can resemble collapse: require full low/no-renewal windows; expose censoring and source coverage.
- Similar practices may be independent: lineage needs explicit local predecessor evidence or a unique structural/context match, never names alone.
- Thresholds are hypotheses: version and publish them; test boundaries rather than claiming an objective definition of an institution.

## Phase Completion Checklist

- Tasks 7–9 meet their acceptance criteria and all commands pass.
- Update only `index.md` progress after verification.
