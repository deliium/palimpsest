# Phase 3: Fragmentation and successor lineage

Plan: [index.md](index.md)
Tasks: 5–6
Depends on: Task 2 for Task 5; Tasks 3–5 for Task 6

## Objective

Keep historical societal candidates and evidence-backed succession separately from regional decline and recovery. A legitimate split can occur without any collapse episode, and a decline can have no detected split.

## Current-Code Evidence

| Path | Symbols / contract | Use |
|---|---|---|
| `src/analysis/macro_society_evidence.py`, `src/analysis/macro_society_detection.py` | `MacroSocietyWindowEvidence`, `detect_macro_society_candidates` | Deterministic window-local multi-lane candidate detection; membership may overlap. |
| `src/analysis/macro_society_identity.py`, `src/analysis/macro_society_lineage.py` | `assign_macro_society_identities`, `derive_macro_society_lineage` | Prior approach; Jaccard thresholds can miss unequal descendants, and adjacency is adjacency of supplied windows. Do not alter either module. |
| `src/simulation/macro_society_models.py` | `MacroSocietyWindowRecord`, `MacroSocietyCandidateRecord` | Published snapshot has final membership, not per-window rosters. Never reuse it to backfill lineage. |
| `src/analysis/institution_lineage.py`, `src/analysis/cultural_technology_continuity.py` | Owner-local institution lineage; living knowledge versus archive preservation | Identity and archive limits inform interpretation, not extra v1 inputs. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/analysis/collapse_recovery_lineage.py` | Create | Window-local candidate projection and conservative temporal graph. |
| `src/analysis/collapse_recovery_continuity.py` | Create | Cross-branch institution/knowledge annotations and scoped episode links. |
| `tests/unit/test_collapse_recovery_lineage.py` | Create | Graph completeness, supported combinations and ambiguity tests. |
| `tests/unit/test_collapse_recovery_continuity.py` | Create | Scoped joins and continuity/reobservation tests. |

## Task 5: Detect fragmentation and successor candidates

1. Implement `build_collapse_lineage(evidence: CollapseEvidence) -> CollapseLineage`. Build `MacroSocietyWindowEvidence` for each complete 32-tick window using union of living body IDs across its boundaries as the known roster. Use only communication, cooperative interaction and completed exchange edges from the Task 1 allowlist, weight 1, same tick/parties/lane deduplicated by the macro adapter. In `detect_macro_society_candidates` keep only rows corroborated by at least two included lanes; do not force members into a partition. Expose lane support and roster/ambiguity counts, not memberships. Keep window coverage independent from `lane_presence`: a valid empty roster or no candidate is `observed_empty`, missing contact attribution or incomplete clock is `unknown`. Never use a later roster. Filter candidate members to those demonstrably living at the end for transition witnesses; preserve candidate row and report both original/end-living counts. An end-living membership smaller than four cannot support a link.
2. Use a run-qualified, window-local observation ID: `cr-node-` + SHA-256 hex of canonical JSON `[run_id, window_start, candidate_key]`; caps 64 candidates per window, 256 links between two windows, checked before accepting the window or link batch. If a cap or detector validation fails mark that window/boundary unknown, never take the first rows and assume absence. Atomically retain matching edges and sorted coverage outcomes.
3. Between adjacent complete known windows, mark as ambiguous any shared body belonging to more than one eligible candidate on either side after end-living filtering. Build bipartite connected components using raw shared body counts `r`, retaining pairs when `r >= 2 and (2*r >= child_size or 4*r >= parent_size)`. Evaluate those same pairs using unambiguous count `s`: if any pair drops below that gate, label the component `ambiguous_transition` and emit no accepted edges (including when every pair was removed). Compute degrees in the surviving component. One-to-one is `continuation` only if `2*s >= max(parent_size, child_size)`. One-to-many is `split_successor` only if each child gets ≥half its end-living bodies as unambiguous witnesses from that parent and joint distinct witnesses cover ≥half of its end-living members. Many-to-one is `merge_successor` only if each parent contributes ≥half its members and joint witnesses cover ≥half of the child. Mixed many-to-many and failed shape checks yield `ambiguous_transition` with no edges. An isolated node on a known boundary has no qualifying predecessor/successor; do not use that disposition for masked or unknown transitions. Disappearance is neither collapse nor extinction.
4. Each edge includes node IDs, strictly advancing window bounds and witness counts/denominators, not members. Never bridge an observed-empty, unknown or censored window. Split children receive distinct successor nodes; later splits/merges connect via their exact historical endpoint IDs, permitting multi-generation traversal. A reappearing cluster following an observation gap is a new observation without a predecessor claim. No cycles, forward edge to later observation only, no cross-run matching.

**Logging:** composition emits DEBUG per-window candidate/ambiguity counts and WARNING for capped/invalid lineage with reason only. Do not log names, member IDs or raw events.

**Tests and acceptance:** `uv run --frozen --python 3.12.14 pytest tests/unit/test_collapse_recovery_lineage.py tests/unit/test_macro_society_lineage.py -q`. Include 12→8+4 unequal split at the graph layer, continuation, provable merge, split followed by merge, all qualified raw overlap masked, disjoint new candidate, complete empty vs unknown, cap failures, extinction bypassing the empty-roster detector, permutation stability and history prefix invariance. For a real detector fixture use eight living members in both windows: complete contact graphs on all eight in both communication and cooperative interaction in the parent window; two disconnected cliques of four in each lane in the next. Check one parent and exactly two successor nodes with four witnesses each. Do not infer a split from the macro detector's single-window status.

## Task 6: Annotate continuity across fragments

1. In `collapse_recovery_continuity.py` compare original source and destination end-boundary rosters for each accepted edge, using private joins only. For institutional continuity count baseline `(body_id, concept_id)` pairs carried by unambiguous shared bodies and continuously present from source end through destination end (inclusive). Distinguish continuous, interrupted/reobserved, not observed, and unassessable. Scope is same-owner recognition, not persistence of a recognized authority. Show denominator of original parent pairs; sibling-shared ambiguous witnesses never earn continuity credit, and deaths or departures may remove carriers without erasing the institution.
2. Compare parent baseline living technique union against each successor's end-boundary living union, with full owner coverage on both. Output counts of retained and not observed in this branch separately; no proof of transfer from same-key presence in a different holder. When all successors are known and institutional/technical source coverage permits, emit a split-wide union comparison, de-duplicated across overlapping branch outputs. Compare against run-wide living union at the same boundary to keep `observed_elsewhere` distinct. One endpoint establishes only `not_observed`.
3. To annotate `observed_branch_loss`, use the original parent technique union as the fixed basis for each split successor. Follow only uniquely accepted `continuation` edges starting at that successor; stop on any missing window, branch split, merge, or unresolved transition. Starting **after** the split destination end, evaluate each full continuation window with the intersection of its source and destination end-living rosters as the stable tracked cohort (minimum four and live throughout); require complete knowledge coverage at every boundary. Count absence only when the key is also absent from the full destination roster with complete coverage at window end. Require two adjacent windows of absence and the same tracked cohort in both; record confirmation on the second. Break the absence streak on cohort change, incomplete source or observed presence; do not backdate. This means sustained absence in the observed branch cohort, not extinction or a loss imposed on the successor. A key still observed in a sibling or elsewhere does not invalidate branch-local loss.
4. Associate the graph with a collapse episode only as context. Match the edge's destination end with the inclusive interval from episode onset through last assessed end. Run-scope attaches temporally only; region-scope also requires a strict majority of the full source end-living roster in that region at the prior boundary, with every source member's physical region known. Do not infer jurisdiction, attach successor inheritance of a collapse label, or mark a merge/split as recovered. An episode can recover while an institution or technology remains lost in another scope, and successors can continue despite an unresolved parent trajectory.
5. Coverage is `complete`, `partial`, or `unavailable` independently for each annotation; missing owners/keys withhold numeric claims but do not erase a supported structural edge. Edges link only observed candidate windows. Report counts and closed interpretation codes only; key and membership IDs stay internal. Emit branch-loss rows on the confirmation node with the split successor ID and both supporting window references; never retroactively change the original edge or node.

**Logging:** pure transform, no row logs; surface only annotation totals by coverage class at DEBUG.

**Tests and acceptance:** `uv run --frozen --python 3.12.14 pytest tests/unit/test_collapse_recovery_continuity.py -q`. Check same-holder continuity through a split vs changed-holder key retention; endpoint absence vs two-window branch loss with retention in a sibling; de-duplicated split aggregate; insufficient or changed cohort, missing middle, later merge, and owner source off preclude false confirmation. Test majority mapping vs tie/unmapped, collapse without fragmentation and fragmentation without collapse. No branch integrity data is visible to agents.

## Phase Risks and Mitigations

- Overlapping candidate membership can invent multiple successors. Use exclusive shared witnesses, group thresholds and explicit unresolved outcomes. No forced winner.
- Future membership or missing inventory can fabricate continuity. Join contemporaneous rows only and never close a gap.

## Phase Completion Checklist

- Validate independent coexistence of recovery, fragmentation and continuity; update Tasks 5–6 only in `index.md`.
