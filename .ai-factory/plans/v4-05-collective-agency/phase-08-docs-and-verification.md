# Phase 8: Documentation and Final Verification

Plan: [index.md](index.md)
Tasks: 22-23
Depends on: Phase 7 / Tasks 19-21

## Objective

Document the verified V4-05 surfaces and counts, then perform final
certification against every plan invariant. Documentation is mandatory; final
certification is withheld for any required lane that is `unexecuted`.

## Current-Code Evidence

| Path | Symbols / sections | Why it matters |
|------|--------------------|----------------|
| `docs/organizations.md` | "Operational state" 47-93; identity 108-119 | Add a V4-05 collective-agency section |
| `docs/collective-decisions.md` | V3-31 owner-scoped decisions | Distinguish V3-31 from V4-05 without rewriting V3-31 |
| `docs/architecture.md` | V4 seams and pin tables | Add the V4-05 seam and update counts |
| `docs/v4-architecture.md` | `organizations` section 77-88; context map | Add the V4-05 collective-agency layer and snapshot v3 |
| `docs/v4-migration-sequence.md` | current state 11-34 | State that V4-05 adds no migration stage |
| `docs/research-api.md` | organization reads 30 | Add the sixth route and cursor fix |
| `docs/research-ui.md` | Organizations panel | Add the collective-agency section |
| `docs/configuration.md` | organization settings | State no new setting/flag |
| `docs/analysis-metrics.md` | metric families | 148 with two new families |
| `docs/development.md` | test commands | Add V4-05 focused commands |
| `README.md` | documentation index | Add `docs/collective-agency.md` |
| `.ai-factory/DESCRIPTION.md` | V4-04 paragraph | Add the V4-05 paragraph |
| `.ai-factory/ARCHITECTURE.md` | V4-04 seam | Add the V4-05 seam; do not edit the roadmap |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `docs/collective-agency.md` | create | Full V4-05 contract: pipeline, beliefs, implementation, refusal, sabotage, provenance, limits |
| `docs/organizations.md` | modify | Link and summarize collective agency |
| `docs/collective-decisions.md` | modify | Clarify V3-31 vs V4-05 |
| `docs/architecture.md` | modify | V4-05 seam and pins |
| `docs/v4-architecture.md` | modify | Organizations section, context map, and V4-05 layer |
| `docs/v4-migration-sequence.md` | modify | State no new stage/migration |
| `docs/research-api.md` | modify | Sixth route and cursor behavior |
| `docs/research-ui.md` | modify | Collective-agency section |
| `docs/configuration.md` | modify | No new flag/mode/schema; `organizations` only |
| `docs/analysis-metrics.md` | modify | 148 families |
| `docs/development.md` | modify | V4-05 focused commands |
| `README.md` | modify | Documentation index |
| `.ai-factory/DESCRIPTION.md` | modify | V4-05 paragraph |
| `.ai-factory/ARCHITECTURE.md` | modify | V4-05 seam and metric pin |
| `.ai-factory/plans/v4-05-collective-agency/index.md` | modify | Task checkboxes and verification receipt |

## Task 22: Execute the documentation checkpoint

### Intent

Make the documentation describe what actually exists, with every count matching
the code. The documentation must state what a collective decision controls (a
belief), what it never controls (objective action), how disagreement works, how
failure works, and how provenance is recorded.

### Implementation Steps

1. Run the `$aif-docs` checkpoint and create `docs/collective-agency.md` with:
   - **What a collective decision is:** an owner-scoped belief about a proposal,
     positions, a recognized procedure, and a recognized outcome. It is not an
     organization will, a super-agent, a binding resolution, a quorum, or a
     permission.
   - **Pipeline:** proposal → discussion → support/opposition/abstention →
     amendment → recognized procedure → collective decision record → individual
     implementation/compliance. Discussion is the ordered sequence of bounded
     position/amendment claims, not a free-text chat transcript and not a
     separate command or event stream.
   - **No super-agent:** no global OrganizationLLM, no shared prompt, no
     organization-owned cognition; each owner's cognition forms its own
     proposal/position.
   - **No execution:** every physical effect is an ordinary `AgentCommand`
     selected and submitted by an agent; the organization cannot teleport,
     grant, or execute.
   - **Supported acts:** proposals, supporters, opponents, abstention,
     amendments, recognized outcomes, compliance, refusal, sabotage.
   - **Failure:** `unimplemented` when actors are observed and do not act;
     `unknown` when visibility is insufficient; silence is never refusal or
     sabotage.
   - **Refusal/sabotage:** explicit evidence requirements; sabotage is an owner
     attribution, never an objective fact.
   - **Disagreement:** `contested` decisions are retained; both sides stay
     visible; no consensus gate. Support/opposition/abstention counts are
     current-revision positions; superseded revisions remain evidence but do
     not inflate current counts.
   - **Provenance:** `orgp-`, `orgpm-`, `orgcd-`, `orgci-`, `orgcev-` owner-local;
     `orgcpd-`/`orgcpi-` published; `org-` analytical. V4-04 `orgd-` operational
     decisions and `orga-` operational actions remain a different sidecar; V4-05
     `orgcd-`/`orgci-` records are collective-agency decisions and
     implementations, not replacements for V4-04.
   - **Limits:** 32 proposals/64 positions/32 amendments/32 decisions/64
     implementations per concept; 64 decisions per candidate; 32
     implementations per decision; 4096 decisions/8192 implementations per
     snapshot; 4 MiB snapshot; 2 MiB response.
   - **Pins:** 148 metric families, six GET routes, snapshot v1/v2/v3, 43
     commands, 22 events, 73 observer semantic types, `v20`, Alembic `0017`,
     runner v4/v55/v56, no v57.
2. Update `docs/organizations.md` with a short "Collective agency" section
   linking to the new page; keep the V4-04 operational section intact.
3. Update `docs/collective-decisions.md` to state:
   - V3-31 remains the owner-scoped proposal/position/outcome ledger;
   - V4-05 is organization-keyed and adds recognized procedure, decision records,
     implementation tracking, refusal, and sabotage;
   - V4-05 does not modify V3-31.
4. Update `docs/architecture.md` with a `### V4-05 collective agency seam`
   section: one owned flag, third sidecar keyed by `orgc-`, no command/event/
   migration, owner-only inputs, snapshot v3, six routes, 148 families.
5. Update `docs/v4-architecture.md`:
   - Extend the `organizations` section from V4-03/V4-04 to include the V4-05
     collective-agency sidecar, owner beliefs, implementation tracking, refusal,
     and sabotage attribution.
   - Keep the context-map row and version surfaces synchronized; snapshot v3 is
     additive and no new context/flag exists.
   - Update `docs/v4-migration-sequence.md` to state that V4-05 adds no migration
     stage, no write pair, and no Alembic revision.
6. Update `docs/research-api.md`:
   - Organization reads are six GET routes under
     `/v1/simulations/{run_id}/organizations[/candidates|/lineage|/operations|/collective-agency]`.
   - New publications are `organization-snapshot-v3`; v1/v2 remain readable.
   - Cursors bind to the publication digest; reuse works after the fix; changed
     filter/run/publication/digest → 400; expired → 410.
   - `503 organization_disabled` when unconfigured.
7. Update `docs/research-ui.md` with the read-only collective-agency section,
   filters, nested implementations, and the sabotage caveat.
8. Update `docs/configuration.md`: no new flag, mode, runner schema, or setting;
   `organizations` on `runner-config-v56` enables the sidecar.
9. Update `docs/analysis-metrics.md`: 148 families; describe
   `organization_collective_agency@1` and
   `organization_collective_implementation@1`; no composite agency score.
10. Update `docs/development.md` with the focused commands:
    `pytest tests/unit/test_organization_agency_*.py tests/architecture/test_organization_agency_boundaries.py -q`.
11. Update `README.md` documentation index with `docs/collective-agency.md`.
12. Update `.ai-factory/DESCRIPTION.md` with a V4-05 paragraph and current pins.
13. Update `.ai-factory/ARCHITECTURE.md` with the V4-05 seam and 148-family pin.
14. Do not edit `.ai-factory/ROADMAP.md`; `$aif-roadmap` owns it.
15. Add `tests/unit/test_organization_agency_docs.py` asserting:
    - the new doc exists and contains the pipeline terms;
    - the organization docs mention v3 and v1/v2 compatibility;
    - `docs/v4-architecture.md` names V4-05 and snapshot v3;
    - `docs/v4-migration-sequence.md` says no V4-05 migration stage is added;
    - the API docs mention six routes and cursor digest binding;
    - the metrics docs mention 148 and both family names;
    - no doc claims objective ownership, a global OrganizationLLM, a binding
      resolution, or organization-executed commands.

### Required Interfaces and Contracts

- Every count in the docs matches the code and tests.
- The docs distinguish owner beliefs from objective action.
- The docs do not claim capacity, prevalence, emergence probability, or a
  composite civilization score.
- V3-31 documentation is clarified, not rewritten.
- The roadmap is untouched.

### Requirement Evidence

- Plan Settings "Docs: yes; mandatory `$aif-docs` checkpoint".
- `.ai-factory/ARCHITECTURE.md` "Documentation" and "See Also".
- Original Request: no super-agent, no global OrganizationLLM, implementation
  tracking, failure due to inaction.

### Error Handling and Logging

- Documentation tests fail closed on a missing file or a wrong count.
- No runtime logging changes.

### Tests

Run:
`uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_docs.py tests/unit/test_organization_operations_docs.py tests/unit/test_organization_docs.py -q`

### Acceptance Criteria

- The documentation is complete, accurate, and consistent with the code.
- Every count matches the verified pins.
- The roadmap is not edited.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_docs.py tests/unit/test_organization_docs.py -q`
- Expected: all tests pass.

## Task 23: Perform final V4-05 verification

### Intent

Certify V4-05 only when every required task has evidence and every required lane
has executed. Any missing prerequisite is recorded and blocks certification.

### Implementation Steps

1. Verify all 23 tasks in `index.md` are checked and each has a phase section
   with acceptance evidence.
2. Verify the bundle integrity:
   - `index.md` contains `<!-- aif:plan-mode:ultra -->` exactly once;
   - every Phase Index link exists;
   - every task maps to exactly one phase section;
   - dependencies point to existing tasks;
   - no orphan phase file;
   - no task checkbox in a phase file.
3. Verify the pins directly:
   - 148 metric families, two new families last;
   - 14 contexts / 12 flags / `v4-context-map-v2`;
   - events 22; codec `v20` accepted, `v21` not;
   - 43 commands; 73 observer semantic types;
   - Alembic `0017`, no `0018_*.py`;
   - no `runner-config-v57`;
   - six GET organization routes;
   - snapshot v1/v2/v3;
   - six cursor purposes;
   - `prepare_parallel=False`;
   - `organization_rows` reserved.
4. Verify V4-03/V4-04 compatibility:
   - existing concept/operation policy versions, ids, digests, statuses, and
     lineage tests green;
   - v1/v2 snapshot byte fixtures unchanged;
   - existing organization routes and metrics unchanged except the intentional
     six-route/148-family pins.
5. Verify the V1/V2 gates:
   - `tests/unit/test_v1_regression_gate.py` green;
   - `tests/unit/test_v2_scientific_invariants.py` green.
6. Record the final certification in `index.md`:
   - `certified=true` only if every required lane is `executed_passed`;
   - otherwise `certified=false` with the exact unexecuted prerequisite(s).
7. Confirm `git status` shows only V4-05 implementation, tests, docs, and the
   plan bundle; `.ai-factory/ROADMAP.md` is untouched.
8. Do not commit, push, or create a branch in this verification task unless the
   user explicitly asks.

### Required Interfaces and Contracts

- Certification is a claim about executed evidence, not intent.
- A lane with a missing prerequisite is `unexecuted` and blocks certification.
- No pin is weakened to make a test pass.
- The plan remains the implementation contract; the roadmap is owned elsewhere.

### Requirement Evidence

- Plan Settings "normal verification with explicit complete required-gate
  certification".
- `.ai-factory/ARCHITECTURE.md` requirements 1-7.
- V4-04 final verification receipt format.

### Error Handling and Logging

- Record safe reason codes and prerequisites for unexecuted lanes.
- Never include credentials, DSNs, prompts, memories, embeddings, or actor sets
  in the receipt.

### Tests

This task runs the Task 21 lanes and the focused V4-05 suites; it adds no new
test file.

### Acceptance Criteria

- All 23 tasks have verified evidence.
- All required lanes are executed and pass, or certification is withheld with
  explicit blockers.
- Documentation and pins match the code.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/architecture/test_organization_agency_boundaries.py -q`
- Expected: all tests pass; the final receipt is truthful.

## Phase Risks and Mitigations

- Risk: documentation drifts from code counts.
  Mitigation: `test_organization_agency_docs.py` asserts the exact counts and
  family names.
- Risk: a required lane is silently skipped.
  Mitigation: the receipt has three states and a named prerequisite for every
  `unexecuted` lane.
- Risk: the roadmap is edited by habit.
  Mitigation: Task 23 checks `git status` and explicitly excludes
  `.ai-factory/ROADMAP.md`.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
