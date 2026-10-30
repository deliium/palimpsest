# Phase 9: Documentation and Final Verification

Plan: [index.md](index.md)
Tasks: 19-20
Depends on: Phase 8 (Tasks 17-18)

## Objective

Publish the analytical contract for researchers and operators, correct every
count and claim touched by V4-02, and certify completion with explicit evidence.
Documentation is part of the deliverable, not an afterthought.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `docs/v4-architecture.md` | context table (69), `### societal_resilience` (159) | Context documentation extended in Task 1; finalized here. |
| `docs/research-api.md` | versioning policy, route catalogue | Must document the four new GET routes and credential. |
| `docs/architecture.md` | downstream plan contract sections | Must add the V4-02 downstream contract. |
| `docs/development.md` | verification command table (31-59), client build section (132) | Must add the new commands and panel checks. |
| `README.md` | documentation index | Must link the new page. |
| `.ai-factory/ARCHITECTURE.md` | V4-01 seam, capability ownership, pins | Must record the 14-context map, 140 families, and unchanged pins. |
| `.ai-factory/DESCRIPTION.md` | V4-01 paragraph (184-203) | Must add a V4-02 paragraph and correct the metric count. |
| `.ai-factory/ROADMAP.md` | M8 section (118-130) | Owned by `$aif-roadmap`; this phase reports the needed update instead of editing it. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `docs/macro-societies.md` | create | Analytical contract, evidence lanes, identities, lineage, limits, non-goals. |
| `docs/v4-architecture.md` | modify | Final context description, map v2, layer separation. |
| `docs/research-api.md` | modify | Four GET routes, credential, cursor semantics, disabled state. |
| `docs/architecture.md` | modify | V4-02 downstream contract and authority boundaries. |
| `docs/development.md` | modify | New verification commands and client panel checks. |
| `README.md` | modify | Documentation index entry. |
| `.ai-factory/ARCHITECTURE.md` | modify | V4-02 seam section, 140 families, unchanged pins. |
| `.ai-factory/DESCRIPTION.md` | modify | V4-02 paragraph and counts. |

## Task 19: Execute the mandatory documentation checkpoint

### Intent

The most likely failure of an analytical identity feature is that a reader
mistakes a candidate for an entity. Documentation must state the opposite in
every place a researcher looks.

### Implementation Steps

1. Create `docs/macro-societies.md` with these sections:
   - **What a macro-society is** — an analysis-output label over detached
     evidence; never an entity, never a command target, never a world fact.
   - **Three layers** — objective population structure (counts only), owner-scoped
     subjective identity claims, analytical candidates with `msoc-` ids; a table
     of what each layer may and may not contain.
   - **Evidence lanes** — the nine lanes, their source rows, and the rule that an
     absent lane is reported as absent, never as zero.
   - **Detection policy** — `macro-society-identity.v1` constants, per-lane
     clustering, cross-lane agreement, overlapping membership, fragmented and
     contested statuses, and the explicit statement that membership is not a
     partition.
   - **Stable identity** — creation-time content fingerprint, why ids survive
     churn, when new ids are minted, and why an id is not a world id.
   - **Lineage** — `continued`, `transformed`, `split`, `merge`, `dissolved`,
     `emerged`; forward-only edges; the rule that split children and merge
     results receive new ids.
   - **Limits** — window, candidate, member, edge, byte, and page caps.
   - **Publication and access** — opt-in completed-run publication, filesystem
     layout, quota, `SUBJECTIVE_DEBUG` credential, disabled state.
   - **Non-goals** — no nation/state/polity/civilization entity, no global
     registry, no cognition feedback, no Godot contract change, no capacity
     claim.
2. Update `docs/v4-architecture.md`: finalize the `### macro_society_identity`
   section, state the map version is `v4-context-map-v2`, and list the fourteen
   contexts consistently.
3. Update `docs/research-api.md`: add the four routes with method, path,
   credential, query parameters, cursor behaviour, 404/503 codes, and a statement
   that responses contain counts, ids, and statuses only.
4. Update `docs/architecture.md`: add a "Downstream V4 macro-society contract"
   section stating ownership (`analysis` calculators, `simulation` artifact
   contract, `experiments` bridge, `persistence` store, `api` read adapter) and
   the invariants a later V4 plan must preserve.
5. Update `docs/development.md`: add the macro-society unit/architecture
   commands, the filesystem/store command, the Research UI build/test commands,
   and a note that the benchmark lane is opt-in and makes no capacity claim.
6. Update `README.md` documentation index with the new page.
7. Update `.ai-factory/DESCRIPTION.md` with a V4-02 paragraph: analysis-only
   context, four new metric families (136 → 140), stable `msoc-` ids, split/merge
   lineage, `macro-society-snapshot-v1`, and unchanged pins (runner v4/v55/v56,
   commands 43, observer semantic types 73, replay v22, codec v20, Alembic 0017,
   `/v1`, `observer-protocol-v1`).
8. Update `.ai-factory/ARCHITECTURE.md`: add a "V4-02 macro-society identity
   seam" section, change the family count to 140, and record that
   `V4_CONTEXT_MAP_VERSION` is now `v4-context-map-v2` while the V4-01 historical
   text remains.
9. Route the roadmap update to its owner: state in the phase output that
   `$aif-roadmap` must add V4-02 to M8 and that this plan does not edit
   `.ai-factory/ROADMAP.md`.
10. Run `grep -rn "136" README.md docs .ai-factory/ARCHITECTURE.md .ai-factory/DESCRIPTION.md`
    and confirm every surviving mention is historical or explicitly superseded.

### Required Interfaces and Contracts

- No document claims macro-societies are objective, exclusive, or authoritative.
- Counts are exact: 140 metric families, 14 V4 contexts, 43 commands, 73
  observer semantic types, 4 reserved write pairs, Alembic `0017`.
- Documentation language is English with technical terms preserved.

### Error Handling and Logging

- Documentation only; no runtime behavior.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_v4_context_registry.py tests/unit/test_metric_specifications.py -q`
  (doc heading parity and catalog count).
- Manual check: every route documented in `docs/research-api.md` exists in
  `src/api/routes/macro_society.py` and vice versa.

### Acceptance Criteria

- `docs/macro-societies.md` answers: what it is, what it is not, how it is
  detected, how identity is stable, and how lineage is formed.
- Every count matches the code.
- The roadmap owner command is named, not performed.

### Verification

- `grep -c "macro_society_identity" docs/v4-architecture.md .ai-factory/ARCHITECTURE.md`
  is at least one per file.
- `grep -n "140" docs/macro-societies.md .ai-factory/DESCRIPTION.md .ai-factory/ARCHITECTURE.md`
  finds the count where claimed.

## Task 20: Perform final V4-02 verification

### Intent

Close the plan with a claim-by-claim audit so no unverified statement survives.

### Implementation Steps

1. Re-run the complete gate set from Task 18 and record results in a receipt
   table.
2. Verify the Definition of Done in `index.md` line by line, citing the test,
   command, or artifact for each item.
3. Verify the negative claims explicitly:
   - `grep -rn "v4_capability_flags\." src/analysis/macro_society_* src/simulation/macro_society_*` → no matches.
   - `grep -rn "class \(Nation\|Country\|Civilization\|Government\|Society\|Polity\|Tribe\|Empire\|State\)\b" src/analysis src/simulation` → no matches.
   - `uv run --frozen --python 3.12.14 pytest tests/unit/test_alembic_head_pin.py -q` → passes, head `0017`.
   - `git status --short alembic/` → empty.
   - `grep -rn "observer-protocol-v2" src` → only the reserved constant.
4. Confirm no `runner-config-v57` and no new event schema or codec version was
   introduced.
5. Confirm the catalog pin is exactly 140 everywhere.
6. Record the final artifact list: created modules, tests, docs, and the plan
   bundle itself.
7. Report any unexecuted required lane with its prerequisite; do not certify it.

### Required Interfaces and Contracts

- The audit references observable evidence only.
- No claim of capacity, prevalence, or emergence is made.

### Error Handling and Logging

- Verification only; failures block completion and are reported with the owning
  task.

### Tests

- The complete Task 18 lane set.
- The negative-claim greps above.

### Acceptance Criteria

- Every Definition of Done item has a citation.
- Every required lane is executed or explicitly unexecuted with a prerequisite.
- No unverified claim remains in the plan or the documentation.

### Verification

- Receipt table complete and reproducible.
- Expected result: all executed lanes pass; negative claims hold.

## Phase Risks and Mitigations

- Risk: documentation drifts from the implemented constants.
  Mitigation: Task 19 cites the contract module as the single source and adds a
  doc-parity assertion where the existing architecture test already does this.
- Risk: a count claim is repeated from an older document.
  Mitigation: explicit grep sweep for `136` and for context counts.

## Phase Completion Checklist

- Every Task 19-20 acceptance criterion is satisfied.
- Documentation states the analytical, non-authoritative nature of macro-societies.
- Final verification receipts and the negative-claim audit are recorded.
- `index.md` task checkboxes are updated immediately after verified completion.
