# Phase 2: Detect repeat practice and track lineage

Plan: [index.md](index.md)  
Tasks: 4–6  
Depends on: Phase 1

## Objective

Classify persistent science-like practice without defining new institutional actors or making scientific outcomes, social approval, or simple co-presence stand in for practice.

## Current-Code Evidence

| Path | Existing seam |
|---|---|
| `src/analysis/organization_identity.py` | `OrganizationIdentityAssignment` attaches candidate IDs to existing organization identities |
| `src/analysis/organization_lineage.py` | `derive_organization_lineage`, `validate_organization_lineage`; lineage over detached observations |
| `src/analysis/institutional_decay.py` | Existing institution lifecycle evidence is analyst-side; not a source of authority or identity for science |
| `src/analysis/metric_service.py` | `competing_theories_analysis` optional sibling dispatch |

## Files to Change

| Path | Action | Responsibility |
|---|---|---|
| `src/analysis/scientific_institutions_detection.py` | Create | Window-local association, status, corroboration and denominators |
| `src/analysis/scientific_institutions_lineage.py` | Create | Independent practice episodes and transitions |
| `src/analysis/scientific_institutions_metrics.py` | Create | Three descriptive families |
| `src/analysis/metric_service.py`, `src/analysis/specifications.py` | Modify | Optional dispatch and metadata registration |
| `tests/unit/test_scientific_institutions_{detection,lineage,metrics}.py` | Create | Thresholds, temporal and evidence invariants |

## Task 4: Detect persistent practice

1. Implement `detect_scientific_practice(windows)` under locked policy `scientific-institutions.v1`. Group by unique `(existing org ID, practice key, window)`. An organization and experiment are associated only via eligible actor participation from Task 3. Require the carrier-service actor also to map uniquely to that candidate. Deduplicate executions by event ID; count carrier service once at organization/window scope. Different activity families within that organization may reference the same service as structural context; don't sum it across families or claim the artifact contains that family's results. An ambiguous cross-organization receipt is never a deciding vote.
2. Define `supported` as ≥1 distinct committed deliberate execution and ≥1 matched committed carrier-service receipt in a complete window for that organization, with a typed durable carrier that survives to window end. For repository service require a live repository and the specific durable member to survive to the window end; a retrieval may remove membership and is not evidence of continuing custody. Emit keyed rows for joined executions and previously observed org/practice keys where that org is present in the current window; do not invent practice keys in a complete-empty window or infer keys from future windows. `observed_only` = joined execution without matched service; `not_observed` = known key, complete lanes, no joined execution; `unavailable` = mandatory coverage gap for a known key. The window grid carries complete-empty and missing states even when there are no keyed rows.
3. On the second of two adjacent full `supported` windows, label the later one `stable` only if the same practice key and existing org ID exist on both sides, share at least one exact surviving typed carrier, and the union includes at least two distinct eligible actors with committed linked practice or carrier-service actions. Keep the earlier window `supported`; do not backdate. A later window that meets the same rule against its immediate predecessor remains `stable`. Repeated service may share a durable carrier/root, but must have different committed action IDs; copied testimony never adds a vote. Store optional behavior descriptions as separate counts and witnesses, not as thresholds or truth.
4. Emit `unassigned`/`ambiguous` counts outside candidates, denominator of complete windows and coverage by lane. Do not emit fabricated zero for missing coverage. Debug log counts and status codes only at the experiment bridge; keep detection pure.

**Acceptance and tests:** `test_scientific_institutions_detection.py` requires a positive two-window case, and negative cases for solo work, same-window bursts, one failed or missing window, one nonmatching key, substituted carrier, conflicting or repeated testimony, destructive end-of-window loss, and ambiguous overlapping organizations. Test available-but-empty optional lanes versus disabled modes, equal-tick deterministic input permutations, and prefix invariance when adding a future window. Evidence: manifest reconciliation operating matrix and architecture authority contract.

## Task 5: Derive forward-only institutional lineage

1. Implement `build_scientific_practice_lineage(assessment, organization_assignment, organization_lineage)`. Keep episode IDs separate from `org-` and owner concepts. Mint `sci-inst-` with canonical SHA-256 over policy namespace, run, org ID, practice key, first stable window and minimum qualifying typed carrier token. Do not include label, membership set, outcome or future evidence. Only stable observations get an episode ID.
2. Use the full window grid. Same-org continuation requires adjacent full stable windows, same key and exact common surviving carrier. A cross-org handoff requires a stable source at `w`, a new target org `supported` at `w+1`, a concrete upstream organization transition at `w+1` backed by candidate occurrences in both endpoint windows, and target `stable` at `w+2`. Require the same practice key and exact carrier in all three windows. Confirm the handoff only at `w+2`; store the intermediate supported observation as evidence, never rewrite it as stable. Use exact artifact IDs or the same repository ID; copied-record ancestry is provenance, not identity. Missing intermediate coverage blocks the edge.
3. For each handoff window and practice key compute degrees over all *confirmed cross-org* edges together. Classify 1→1 `succeeded`, out-degree >1 `split`, in-degree >1 `merged`, both `split_merged`; the target starts its own episode. Same-org adjacent `continued` edges are independent of those degrees and retain the episode ID. At the first stable window of a new episode, record `emerged` only if no handoff is confirmed at that window; use `reobserved_after_gap` only when the exact former same-key/org ID is observed again after unavailable coverage. If assignment changed the org ID during a gap, do not guess a former identity. At a complete boundary with no same-org continuation emit `lapsed` (local continuity stopped; a later handoff can still be separately confirmed). Missing/partial boundaries emit `continuity_unknown`; end of horizon does not imply lapse. Node identity is `(episode_id, window)`. Give each transition/boundary observation a `known_at_window`, including `w+2` for confirmed handoff and `w+1` for lapse or unknown after a stable window at `w`. Preserve exact carrier refs and upstream organization transition refs. Tests give split/merge edges separate qualifying carrier links rather than duplicate cross-candidate receipts.
4. Validate all references, strict time increase, unique edges, legal in/out cardinalities, same-run lineage and canonical sorting. Never assert cross-run, cross-fork or global identity. Report bounded counts, no graph payload in logs.

**Acceptance and tests:** `test_scientific_institutions_lineage.py` covers continuation, exact carrier with personnel turnover, organization succession, split, merge, simultaneous split/merge, mature-episode break then reobservation, complete-empty lapse, incomplete and terminal censoring, and no link on name/member overlap only. Assert an extended result filtered by `known_at_window` reproduces earlier nodes, statuses and already-known transition records. No new edge or amended boundary record may appear at an earlier knowledge window. Evidence: user's lineage requirement; architecture analysis isolation and append-only history.

## Task 6: Register descriptive metrics

1. Add `scientific_institution_practice@1` (window/status and eligible/ambiguous/unassigned counts), `scientific_institution_roles_and_carriers@1` (per-lane signal counts, distinct linked actors and exact carriers), and `scientific_institution_lineage@1` (transition/event counts and observed lengths in full windows). Use canonical integer values and documented denominators; use the project’s unavailable/partial convention rather than imputed counts.
2. Register in existing ordered metric registry and `metric_service.py`; add optional `scientific_institutions_analysis` alongside the competing-theory input, dispatch only for explicit supplied evidence. Feature-off does not change existing metric outputs/order. No score, truth rating, research-quality ranking, prevalence estimate or causal claim. Update current catalog contract 268 → 271 only; other compatibility pins unchanged.
3. Log safe DEBUG counts and omission reason, INFO one successful family count when explicitly computed. Value/aggregation functions are pure.

**Acceptance and tests:** `test_scientific_institutions_metrics.py` verifies exact family IDs, keys and counts in positive, complete-empty and unavailable cohorts, no invented metric on absent input, deterministic output and no modified legacy family descriptors. Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_scientific_institutions_{detection,lineage,metrics}.py -q`.

## Phase Risks and Mitigations

- Conservative thresholds miss solitary or poorly recorded work. Describe that as detector scope, not proof of absence of science.
- Existing organization lineage could skip empty windows; enforce adjacency and completeness independently for practice episodes.
