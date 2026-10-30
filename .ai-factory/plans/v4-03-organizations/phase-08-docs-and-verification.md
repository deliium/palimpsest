# Phase 8: Documentation and Final Verification

Plan: [index.md](index.md)
Tasks: 21-22
Depends on: Phase 7 / Tasks 19-20

## Objective

Document what an organization is and is not, how the nine aspects are formed,
how membership and lineage behave, and how researchers inspect them. Then perform
the final V4-03 certification against every authority, compatibility, and
documentation requirement.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `README.md` | documentation index | New page must be linked. |
| `.ai-factory/DESCRIPTION.md` | V4-02 paragraph 205-223 | Add the V4-03 paragraph and update the metric count. |
| `.ai-factory/ARCHITECTURE.md` | pin table 177-193; V4-02 seam 578-595 | Add the V4-03 seam and change metric families to 144. |
| `docs/v4-architecture.md` | `### organizations` section | Update the owned statement; keep exactly 14 `###` headings. |
| `docs/configuration.md` | feature gates | Document `v4_capability_flags.organizations` on v56. |
| `docs/research-api.md` | `/v1` route index | Add the four GET routes and `SUBJECTIVE_DEBUG`. |
| `docs/development.md` | verification commands | Add the organization-focused gates. |
| `tests/architecture/test_v4_context_registry.py` | 170-177 | Doc parity: every context id and 11 required sections. |
| `tests/architecture/test_v4_architecture_invariants.py` | 273-290 | Doc parity for V4 architecture. |
| `.ai-factory/ROADMAP.md` | M8 | Must remain unedited; `$aif-roadmap` owns it. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `docs/organizations.md` | create | Complete organization contract and researcher guide. |
| `README.md` | modify | Link the new page in the documentation index. |
| `.ai-factory/DESCRIPTION.md` | modify | Add V4-03 paragraph; metric 144; pins unchanged otherwise. |
| `.ai-factory/ARCHITECTURE.md` | modify | Add V4-03 seam; metric 144; no-actor/no-treasury statement. |
| `docs/v4-architecture.md` | modify | Owned organizations statement; no new `###` heading. |
| `docs/configuration.md` | modify | Document the flag, v56 requirement, and prerequisites. |
| `docs/research-api.md` | modify | Document four GET routes, credential, disabled state, cursors. |
| `docs/development.md` | modify | Add organization-focused verification commands. |
| `docs/architecture.md` | modify | Update the metric pin 140 -> 144; add a downstream V4 organization contract beside the macro-society one. |
| `docs/research-ui.md` | modify | Add the Organizations panel to the panel/route table. |
| `docs/macro-societies.md` | modify | Add a See-also cross-link distinguishing macro-society candidates from organization concepts. |
| `tests/unit/test_organization_docs.py` | create | Documentation/count parity tests. |

## Task 21: Execute the documentation checkpoint

### Intent

Make the feature comprehensible and prevent documentation drift. The docs must
state the negative space as clearly as the positive one: no actor, no roster, no
treasury, no organization-owned cognition.

### Implementation Steps

1. Run the project's documentation workflow (`$aif-docs`) for this plan. If the
   command is unavailable in the session, perform the same edits manually and
   record the fallback in the task receipt.
2. Create `docs/organizations.md` with these sections:
   - **What an organization is:** an owner-scoped belief about a recurring
     collective structure, composed of perceived members, roles, shared goals,
     referenced resources, procedures, records, internal commitments, identity
     concepts, and bounded history.
   - **What it is not:** not a `WorldEngine` entity, not a global registry, not a
     roster, not a treasury, not a resource pool, not a command source, not an
     independent cognition engine, not a hard-coded Government/Church/
     Corporation/Army/University/Guild.
   - **Nine aspects:** one table mapping each aspect to its belief type and its
     allowed anchor; state explicitly that resources and records are references,
     and commitments are interpretations.
   - **Membership:** `explicit`, `perceived`, `disputed`, `unknown`, `former`;
     `ongoing` vs `temporary`; overlap is legal; no exclusive partition.
   - **Identity:** owner-local `orgc-` ids are minted from creation evidence;
     analytical `org-` ids are detached; publication ids are `org-edge-`.
   - **Lineage:** `continued`, `transformed`, `split`, `merge`, `dissolved`,
     `emerged`; forward-only; split/merge mint new ids.
   - **Configuration:** `v4_capability_flags.organizations` on
     `runner-config-v56`; no v57; existing V3 modes supply evidence; absent
     evidence yields an empty ledger.
   - **Publication and inspection:** opt-in CLI options, snapshot schema,
     four GET routes, `SUBJECTIVE_DEBUG`, disabled state.
   - **Limits:** 4 MiB snapshot, 2048 candidates, 512 members, 512 windows,
     16384 edges, 500 rows per page; member truncation is explicit.
   - **Non-claims:** no capacity, prevalence, emergence probability, predictive
     power, or civilization score.
3. Update `README.md` to link `docs/organizations.md` in the documentation index.
4. Update `.ai-factory/DESCRIPTION.md` with a V4-03 paragraph:
   owner-scoped organization concepts, detached analysis, four families
   (140 -> 144), `organization-snapshot-v1`, four GET routes, Research UI panel;
   pins runner v4/v55/v56, result v2/v3, commands 43, observer semantic types 73,
   replay-v22/codec v20, `/v1`, `observer-protocol-v1`, Alembic `0017`; no
   capability beyond `organizations`; `institutional_economy` and
   `multi_hop_testimony_tracking` still unowned.
5. Update `.ai-factory/ARCHITECTURE.md`:
   - change the metric pin from 140 to 144;
   - add a `### V4-03 organizations seam` section describing the owned
     owner-scoped context, the nine aspects, the detached analysis, the artifact,
     and the no-actor/no-treasury/no-peer-cognition rules;
   - keep the existing V4-01/V4-02 text.
6. Update `docs/v4-architecture.md` `### organizations` body and the surrounding
   current-state text:
   - update the context table row for `organizations` from "deferred to V4-02+"
     to "V4-03 implementation";
   - owned by V4-03 on `runner-config-v56`;
   - collective action remains objective work plus owner-scoped membership
     beliefs;
   - no organization actor, roster, treasury, pool, registry, or independent
     cognition;
   - references to roles, records, procedures, and commitments remain beliefs;
   - update the V4-01 non-goals line so it says V4-01 does not implement
     organizations (not that no V4 plan may);
   - add an `organizations` link beside the macro-society See-also link.
   Do not add a `###` heading; exactly 14 context headings must remain.
7. Update `docs/architecture.md`:
   - change the current pin from 140 to 144;
   - add a "Downstream V4 organization contract" beside the macro-society
     contract: owner-scoped belief, nine aspects, no actor/treasury/registry,
     identity/lineage, three layers, artifact independence, and the 144 pin.
8. Update `docs/configuration.md` with the flag, the v56 requirement, the
   evidence prerequisites, and the "empty evidence is valid" rule.
9. Update `docs/research-api.md` with the four routes, the `SUBJECTIVE_DEBUG`
   requirement, disabled/error codes, cursor semantics, and the read-only rule.
10. Update `docs/research-ui.md` with an Organizations panel row and a short
    description of the read-only summary/candidates/lineage view.
11. Update `docs/development.md` with the organization-focused commands:
    `tests/unit/test_organization_*.py`,
    `tests/architecture/test_organization_boundaries.py`,
    `tests/unit/test_organization_end_to_end.py`,
    the organization CLI test, and the Research UI panel test.
12. Update `docs/macro-societies.md` with a See-also cross-link that states the
    distinction: a macro-society candidate is a large society-like cluster; an
    organization concept is a narrower recurring collective structure.
13. Add `tests/unit/test_organization_docs.py`:
    - `docs/organizations.md` exists and contains every required heading;
    - README links it;
    - DESCRIPTION mentions 144 and V4-03;
    - ARCHITECTURE mentions 144 and the V4-03 seam;
    - `docs/architecture.md` mentions 144 and the downstream organization
      contract;
    - `docs/research-ui.md` lists the Organizations panel;
    - `docs/v4-architecture.md` still has exactly 14 `### ` context headings and
      every context id;
    - no doc claims a global organization registry, treasury, capacity, or
      prevalence;
    - all counts in the docs match `METRIC_FAMILY_COUNT`, context count, and
      capability flag count.

### Required Interfaces and Contracts

- Documentation language is English; technical terms remain unchanged.
- Every count matches code: 14 contexts, 12 flags, 144 metric families, 43
  commands, 73 observer semantic types, replay 22, codec v20, Alembic `0017`.
- The roadmap is not edited; Task 21 records the required M8 update text for
  `$aif-roadmap` instead.
- No documentation claims objective organization identity or independent
  cognition.

### Requirement Evidence

- Plan Settings: "Docs: yes; mandatory `$aif-docs` checkpoint".
- `.ai-factory/ARCHITECTURE.md` requirement 7: roadmap ownership.
- Original request: "Do NOT create hard-coded classes"; "An Organization must not
  receive an independent omniscient cognition engine."

### Error Handling and Logging

- No production logging change.
- Record `WARN [docs]` only if the docs command is unavailable; a missing
  mandatory checkpoint blocks Task 22.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_docs.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_v4_context_registry.py tests/architecture/test_v4_architecture_invariants.py -q`
- Expected: pass.

### Acceptance Criteria

- A complete organization guide exists and is linked.
- All counts match code.
- The negative space (no actor/registry/treasury/independent cognition) is
  explicit.
- The roadmap is untouched.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_docs.py -q`
- `git status --short .ai-factory/ROADMAP.md`
- Expected: docs test passes; roadmap status is empty.

## Task 22: Perform final V4-03 verification

### Intent

Certify the plan against its Definition of Done with explicit evidence, not a
summary claim. Any unexecuted required lane blocks certification.

### Implementation Steps

1. Verify all 22 task checkboxes in `index.md` are checked only after their
   acceptance criteria and verification commands passed.
2. Verify the bundle integrity:
   - exactly one `<!-- aif:plan-mode:ultra -->` marker;
   - every Phase Index link resolves;
   - every Task 1-22 appears exactly once in the index and once in a phase file;
   - no phase file contains a checkbox;
   - dependencies reference existing tasks;
   - no orphan phase file.
3. Verify authority and compatibility with direct commands:
   - `python -c` prints 14 contexts, 12 flags, `v4-context-map-v2`,
     `organizations` owned, the other eleven unimplemented;
   - metric catalog validates at 144;
   - event max 22, codec v20 accepted/v21 not, commands 43, semantic types 73,
     Alembic head 0017, no `0018_*.py`, no `runner-config-v57`;
   - four reservations unchanged; `organizations` is in the reuse set.
4. Verify negative space with greps:
   - no `OrganizationActor`, `GlobalOrganizationRegistry`,
     `OrganizationRegistry`, `WorldGovernment`, `CentralBank`, `Treasury`,
     `Ministry`, `InstitutionActor`, `CivilizationActor` class;
   - no `AgentCommand` in organization modules;
   - no `WorldState`/`WorldEngine`/`ActionSubmission` in organization cognition
     or analysis;
   - no peer-ledger parameter/attribute;
   - no organization-owned resource pool/treasury field;
   - no POST/PUT/PATCH/DELETE in the Research UI organization client;
   - no `analysis` import in persistence/API; no `agents.cognition` import in
     analysis.
5. Verify the artifact and surfaces:
   - `organization-snapshot-v1` encodes/decodes byte-identically;
   - publication id is stable and run-bound;
   - the filesystem store round-trips and rejects duplicates/quota/lock;
   - the four routes are GET-only and require `SUBJECTIVE_DEBUG`;
   - the disabled state is `organization_disabled`;
   - the CLI receipt is id-free and failure-isolated;
   - the Research UI panel renders available/empty/unavailable without
     derivation.
6. Verify the regression receipt from Task 20:
   - every required lane is `executed_passed` or explicitly `unexecuted` with a
     prerequisite;
   - no lane is reported as a skip-pass;
   - coverage was enabled on Python lanes.
7. Verify documentation:
   - `docs/organizations.md` exists and is linked;
   - every count matches code;
   - the roadmap is unmodified (`git status --short .ai-factory/ROADMAP.md` is
     empty);
   - no doc claims capacity, prevalence, or objective organization identity.
8. Record the final certification in the task receipt:
   `v4-03-organizations certified=true|false`, with the list of unexecuted lanes
   and blockers if any.
9. If any check fails, fix the implementation or record a blocking open question;
   do not mark the task complete.

### Required Interfaces and Contracts

- Final certification requires all 22 tasks complete.
- Unexecuted required lanes block certification.
- The only intentional pin changes are 140 -> 144 metric families; 14 contexts,
  12 flags, and `v4-context-map-v2` are unchanged from V4-02.
- The roadmap remains owned by `$aif-roadmap`.

### Requirement Evidence

- Plan Definition of Done.
- `.ai-factory/ARCHITECTURE.md` "Requirements for later changes".
- `.ai-factory/RULES.md` axioms.

### Error Handling and Logging

- Report safe codes/counts only; never dump payloads or secrets.
- A failed check names the file/symbol and expected/actual count.

### Tests

- Full suite and static gates from Task 20.
- `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term`
- Expected: pass; certification receipt complete.

### Acceptance Criteria

- All 22 tasks are checked with evidence.
- All pins and negative-space checks pass.
- The artifact, API, CLI, UI, and docs are verified.
- Any unexecuted lane is recorded and certification is withheld.

### Verification

- `uv run --frozen --python 3.12.14 pytest -q`
- `uv run --frozen --python 3.12.14 ruff check src tests`
- `uv run --frozen --python 3.12.14 mypy src tests`
- Expected: pass; final receipt `v4-03-organizations certified=true`.

## Phase Risks and Mitigations

- Risk: docs drift from code counts.
  Mitigation: `test_organization_docs.py` derives counts from code constants.
- Risk: the V4 architecture doc gains an extra `###` heading.
  Mitigation: edit only the existing organizations body; the registry test pins
  exactly 14 headings.
- Risk: a required lane is silently skipped at certification.
  Mitigation: three-state receipt and an explicit blocker list.
- Risk: the roadmap is edited by habit.
  Mitigation: Task 21 records the required update for `$aif-roadmap`; Task 22
  checks `git status`.

## Phase Completion Checklist

- Every Task 21-22 acceptance criterion is met.
- Documentation tests pass and every count matches code.
- The final certification is recorded with no skip-pass.
- `index.md` checkboxes are updated immediately after verified completion.
