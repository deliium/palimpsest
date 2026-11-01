# Phase 8: Documentation and Final Verification

Plan: [index.md](index.md)
Tasks: 22-23
Depends on: Phase 7 / Tasks 19-21

## Objective

Document the operational model with the same precision as its negative space,
keep every count aligned with code, and perform the final V4-04 certification
against every authority, compatibility, and evidence requirement.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `docs/organizations.md` | what it is/is not 9-44; aspects 29-44; membership 46-57; identity 59-68; lineage 70-75; configuration 77-84; publication 86-101; limits 103-115; non-claims 117-121 | Add the operational section and update artifact/route/limit counts. |
| `README.md` | documentation index 80-90 | Update the Organizations row. |
| `.ai-factory/DESCRIPTION.md` | V4-03 paragraph 226-247 | Add a V4-04 paragraph and the 146 pin. |
| `.ai-factory/ARCHITECTURE.md` | baseline pin table 177-193; V4-03 seam 598-627 | Add the V4-04 seam and update the metric pin. |
| `docs/v4-architecture.md` | context table 58; organizations body 77-84; V4-01 non-goals 278 | Update the body without adding a `###` context heading. |
| `docs/architecture.md` | metric pin 269, 289 | Update 144 → 146 and add the downstream operation contract. |
| `docs/configuration.md` | organizations paragraph 310 | State that operations extend the same flag and require no new mode. |
| `docs/research-api.md` | organization route line 30 | Add the fifth route, v2 artifact, and cursor/disabled behavior. |
| `docs/research-ui.md` | organizations panel line 220 | Add the operations view. |
| `docs/analysis-metrics.md` | metric family documentation | Add the two families and their availability rules. |
| `docs/development.md` | organization commands 608-611 | Add the new test files/lanes. |
| `tests/unit/test_organization_docs.py` | doc parity/count tests | Extend or add a sibling V4-04 docs test. |
| `tests/architecture/test_v4_context_registry.py` | 170-177 | Doc parity requires exactly 14 context headings. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `docs/organizations.md` | modify | Operational state, objective/subjective separation, disagreement, provenance, v2, five routes, limits. |
| `README.md` | modify | Update the Organizations documentation row. |
| `.ai-factory/DESCRIPTION.md` | modify | V4-04 paragraph; metric 146; pins otherwise unchanged. |
| `.ai-factory/ARCHITECTURE.md` | modify | V4-04 seam; metric 146; no-actor/no-teleport statement. |
| `docs/v4-architecture.md` | modify | Organizations body; no new `###` heading. |
| `docs/architecture.md` | modify | Pin 146; downstream operation contract. |
| `docs/configuration.md` | modify | Same flag, no new mode/v57; evidence behavior. |
| `docs/research-api.md` | modify | Five GET routes, v2 artifact, cursors/disabled state. |
| `docs/research-ui.md` | modify | Operations panel view. |
| `docs/analysis-metrics.md` | modify | Two new families. |
| `docs/development.md` | modify | New test commands and lanes. |
| `tests/unit/test_organization_operations_docs.py` | create | Doc/count/negative-space parity. |

## Task 22: Execute the documentation checkpoint

### Intent

Make the operational model comprehensible and prevent drift. The docs must say
what an organization controls (a belief), what it never controls (objective
custody), how disagreement remains legal, and how provenance is recorded.

### Implementation Steps

1. Run the project documentation workflow (`$aif-docs`) for this plan. If the
   command is unavailable, perform the same edits manually and record the
   fallback in the task receipt.
2. In `docs/organizations.md`, add an **Operational state** section:
   - the eight domains: resource control, storage, record keeping, admission,
     departure, role assignment, procedure action, internal commitment;
   - the sidecar ledger keyed by `orgc-`, with policy
     `organization-operations.v1`;
   - objective possession (`holder_id`, `location_id`,
     `custodian_repository_id`, `stored_quantity`) is separate from subjective
     control and legitimacy doctrine;
   - no teleport, no executor, no resource pool, no treasury, no roster;
   - all physical effects remain ordinary `Give`/`Take`/`Store`/`Inscribe`/
     `DepositRecord`/etc. selected and submitted by agents;
   - admission/departure/role assignment are claims, never permissions;
   - disagreement about membership, authority, resource legitimacy, or procedures
     is retained as `disputed`/`contest_count` and never blocks operation;
   - provenance: `orgd-` decisions and `orga-` actions in the owner ledger,
     published as `orgop-` records with authority basis/provenance code;
   - no new flag or per-agent mode; `organizations` on `runner-config-v56`
     enables both concept and operation state.
3. Update the membership/identity/configuration/publication/limits sections:
   - artifact `organization-snapshot-v2`; v1 remains readable;
   - five GET-only routes under `/v1/simulations/{run_id}/organizations`:
     summary, candidates, candidate detail, lineage, operations;
   - limits: 64 operations per candidate, 4096 snapshot operations, 256 total
     operation records per owner ledger, existing 4 MiB/2048/512/512/16384/500
     limits unchanged;
   - truncation/expiry codes `operations_truncated`,
     `operation_anchor_unresolved`, and `operation_expired` are explicit.
4. Update `README.md`'s Organizations row to mention operational state, v2, and
   five routes.
5. Update `.ai-factory/DESCRIPTION.md` with a V4-04 paragraph:
   owner-scoped operations, eight domains, provenance, detached analysis, two
   families (144 → 146), `organization-snapshot-v2`, five GET routes, Research UI
   view; pins runner v4/v55/v56, result v2/v3, commands 43, observer semantic
   types 73, replay-v22/codec v20, `/v1`, `observer-protocol-v1`, Alembic `0017`;
   no new flag/mode; `institutional_economy` and
   `multi_hop_testimony_tracking` remain unowned.
6. Update `.ai-factory/ARCHITECTURE.md`:
   - change the metric pin 144 → 146;
   - add a `### V4-04 organizations operations seam` section after V4-03,
     describing the sidecar, eight domains, objective/subjective separation,
     no-teleport rule, disagreement, provenance, v2 artifact, five GET routes,
     and no new flag/command/event/migration;
   - keep V4-01/V4-02/V4-03 text intact.
7. Update `docs/v4-architecture.md`:
   - update the `organizations` context row from "V4-03 implementation" to
     "V4-03/V4-04 implementation";
   - update the organizations body: operational beliefs, no actor/treasury/
     registry, objective possession separate, disagreement legal;
   - update the V4-01 non-goals line only if it still implies V4-01 implements
     organizations;
   - do not add a `###` heading; exactly 14 context headings remain;
   - add an operations cross-link beside the organization link.
8. Update `docs/architecture.md`:
   - change the pin 144 → 146;
   - add a "Downstream V4 organization operations contract" beside the V4-03
     contract: sidecar keyed by `orgc-`, eight domains, no teleport/executor,
     objective/subjective separation, disagreement, provenance, v1/v2 artifact,
     five GET routes, 146 pin.
9. Update `docs/configuration.md`: the same `organizations` flag on
   `runner-config-v56` enables operations; there is no `runner-config-v57`, no
   `organization_operations_mode`, and no new root field; absent evidence yields
   an empty operation ledger.
10. Update `docs/research-api.md`:
    - five GET-only organization routes, all `SUBJECTIVE_DEBUG`;
    - the operations route filters by `domain` and `organization_id`, with
      purpose-bound cursors;
    - v2 artifact, v1 readable; `organization_disabled` when the root is unset;
    - no write route, no `/v2`, no new capability.
11. Update `docs/research-ui.md`: add the Operations view (summary tile, domain
    filter, provenance table, contested badge) and state that no client-side
    derivation occurs.
12. Update `docs/analysis-metrics.md`: document
    `organization_operations@1` and `organization_operation_authority@1`, their
    exact value keys, denominators, and `ABSENT`/`PARTIAL` rules.
13. Update `docs/development.md` with the new commands:
    `tests/unit/test_organization_operations_*.py`,
    `tests/architecture/test_organization_operations_boundaries.py`,
    the operations E2E test, the API/UI tests, and the two metric tests.
14. Add `tests/unit/test_organization_operations_docs.py`:
    - `docs/organizations.md` contains the operational headings and all eight
      domains;
    - README links the page and mentions operations;
    - DESCRIPTION mentions V4-04 and 146;
    - ARCHITECTURE mentions the V4-04 seam and 146;
    - `docs/architecture.md` mentions 146 and the downstream operation contract;
    - `docs/research-api.md` lists five routes and v2;
    - `docs/research-ui.md` lists the operations view;
    - `docs/v4-architecture.md` still has exactly 14 `### ` context headings;
    - no doc claims a global organization registry, treasury, objective
      ownership, capacity, prevalence, or a composite score;
    - every count matches `METRIC_FAMILY_COUNT`, context/flag counts, and route
      count.

### Required Interfaces and Contracts

- Documentation language is English; technical terms remain unchanged.
- Every count matches code: 14 contexts, 12 flags, 146 metric families, 43
  commands, 73 observer semantic types, replay 22, codec v20, Alembic `0017`,
  five GET organization routes.
- The roadmap is not edited; Task 22 records the required M8 update text for
  `$aif-roadmap`.
- No documentation claims objective organization identity, ownership, teleport,
  independent cognition, or capacity.

### Requirement Evidence

- Plan Settings: "Docs: yes; mandatory `$aif-docs` checkpoint".
- `.ai-factory/ARCHITECTURE.md` requirement 7: roadmap ownership.
- Original Request: objective/subjective separation, no teleport, disagreement,
  provenance.

### Error Handling and Logging

- No production logging change.
- Record `WARN [docs]` only if the docs command is unavailable; a missing
  mandatory checkpoint blocks Task 23.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_docs.py tests/unit/test_organization_docs.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_v4_context_registry.py tests/architecture/test_v4_architecture_invariants.py -q`
- Expected: pass.

### Acceptance Criteria

- A complete operational guide exists and is linked.
- All counts match code.
- The negative space is explicit.
- The roadmap is untouched.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_docs.py tests/unit/test_organization_docs.py -q`
- `git status --short .ai-factory/ROADMAP.md`
- Expected: docs tests pass; roadmap status is empty.

## Task 23: Perform final V4-04 verification

### Intent

Certify the plan against its Definition of Done with explicit evidence, not a
summary claim. Any unexecuted required lane blocks certification.

### Implementation Steps

1. Verify all 23 task checkboxes in `index.md` are checked only after their
   acceptance criteria and verification commands passed.
2. Verify bundle integrity:
   - exactly one `<!-- aif:plan-mode:ultra -->` marker;
   - every Phase Index link resolves;
   - every Task 1-23 appears exactly once in the index and once in a phase file;
   - no phase file contains a checkbox;
   - dependencies reference existing tasks;
   - no orphan phase file.
3. Verify authority and compatibility with direct commands:
   - 14 contexts, 12 flags, `v4-context-map-v2`, `organizations` owned, the other
     eleven unowned/fail-closed;
   - metric catalog validates at 146; the first 144 families unchanged;
   - event max 22, codec v20 accepted/v21 not, commands 43, semantic types 73,
     Alembic `0017`, no `0018_*.py`, no `runner-config-v57`;
   - four reservations unchanged; `organizations` in the reuse set.
4. Verify negative space with greps:
   - no `OrganizationActor`, `OrganizationTreasury`, `OrganizationRegistry`,
     `GlobalOrganizationRegistry`, `ResourcePool`, `WorldGovernment`,
     `CentralBank`, `Treasury`, `Ministry`, `InstitutionActor`,
     `CivilizationActor` class;
   - no `teleport`, `execute`, `execute_action`, `transfer_resources`, or
     `move_resources` in operation modules;
   - no `AgentCommand`/`WorldState`/`WorldEngine`/`ActionSubmission`/`EventStore`
     in operation cognition/analysis modules;
   - no peer-ledger parameter/attribute;
   - no organization-owned resource pool/treasury/roster field;
   - no `owner_id`/`ownership` field on objective `Item`, `Resource`, `Structure`,
     `InformationArtifact`, or `KnowledgeRepository`;
   - no POST/PUT/PATCH/DELETE in the Research UI organization client;
   - no `analysis` import in persistence/API; no `agents.cognition` import in
     analysis.
5. Verify the artifact and surfaces:
   - v1 and v2 snapshots encode/decode byte-identically;
   - v2 publication id is stable and run-bound;
   - the filesystem store round-trips v1/v2 and rejects duplicates/quota/lock;
   - five routes are GET-only and require `SUBJECTIVE_DEBUG`;
   - the disabled state is `organization_disabled`;
   - cursors are purpose/filter/run/publication bound;
   - the CLI receipt is id-free and failure-isolated;
   - the Research UI renders available/empty/unavailable without derivation.
6. Verify operational invariants:
   - all eight domains are representable;
   - conflicting claims remain `disputed` with both sides;
   - `orgd-`/`orga-` ids are content-addressed and owner-local;
   - `orgop-` ids are content-addressed and publication-visible only;
   - split/merge leaves predecessor operations and empty children;
   - objective possession is unchanged by any organization belief.
7. Verify the regression receipt from Task 21:
   - every required lane is `executed_passed` or explicitly `unexecuted` with a
     prerequisite;
   - no lane is reported as a skip-pass;
   - coverage was enabled on Python lanes.
8. Verify documentation:
   - `docs/organizations.md` has the operational section and is linked;
   - every count matches code;
   - the roadmap is unmodified (`git status --short .ai-factory/ROADMAP.md` is
     empty);
   - no doc claims capacity, prevalence, objective ownership, or teleport.
9. Record the final certification in the task receipt:
   `v4-04-organization-operations certified=true|false`, with the list of
   unexecuted lanes and blockers if any.
10. If any check fails, fix the implementation or record a blocking open
    question; do not mark the task complete.

### Required Interfaces and Contracts

- Final certification requires all 23 tasks complete.
- Unexecuted required lanes block certification.
- The only intentional pin change is 144 → 146 metric families; 14 contexts, 12
  flags, 43 commands, 73 semantic types, replay 22, codec v20, and Alembic `0017`
  are unchanged.
- The roadmap remains owned by `$aif-roadmap`.
- The artifact adds `organization-snapshot-v2` while preserving v1 decoding; the
  API adds one GET route under `/v1`.

### Requirement Evidence

- Plan Definition of Done.
- `.ai-factory/ARCHITECTURE.md` "Requirements for later changes".
- `.ai-factory/RULES.md` axioms.

### Error Handling and Logging

- Report safe codes/counts only; never dump payloads or secrets.
- A failed check names the file/symbol and expected/actual count.

### Tests

- Full suite and static gates from Task 21.
- `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term`
- Expected: pass; certification receipt complete.

### Acceptance Criteria

- All 23 tasks are checked with evidence.
- All pins and negative-space checks pass.
- The artifact, API, CLI, UI, and docs are verified.
- Any unexecuted lane is recorded and certification is withheld.

### Verification

- `uv run --frozen --python 3.12.14 pytest -q`
- `uv run --frozen --python 3.12.14 ruff check src tests`
- `uv run --frozen --python 3.12.14 mypy src tests`
- Expected: pass; final receipt `v4-04-organization-operations certified=true`.

## Phase Risks and Mitigations

- Risk: docs drift from code counts.
  Mitigation: `test_organization_operations_docs.py` derives counts from code
  constants.
- Risk: the V4 architecture doc gains an extra `###` heading.
  Mitigation: edit only the existing organizations body; the registry test pins
  exactly 14 headings.
- Risk: a required lane is silently skipped at certification.
  Mitigation: three-state receipt and an explicit blocker list.
- Risk: the roadmap is edited by habit.
  Mitigation: Task 22 records the required M8 update for `$aif-roadmap`; Task 23
  checks `git status`.

## Phase Completion Checklist

- Every Task 22-23 acceptance criterion is met.
- Documentation tests pass and every count matches code.
- The final certification is recorded with no skip-pass.
- `index.md` checkboxes are updated immediately after verified completion.
