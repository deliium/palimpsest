# Phase 8: Documentation and Final Verification

Plan: [index.md](index.md)
Tasks: 24-25
Depends on: Phase 7

## Objective

Turn the implemented contracts into canonical documentation and audit the
entire V4-11 bundle. Documentation must state what treaties control (a belief),
what they never control (objective action, permission, truth, enforcement, or
a binding agreement), how versions and lineage work, how records,
participants, recognized representatives, institutional memory, and agent
beliefs compose, and every current count must match the code.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `docs/diplomacy.md` | 1-230 | Canonical V4-10 contract; add treaty sections and update counts. |
| `docs/analysis-metrics.md` | 41, 554-600 | Catalog count and diplomacy family documentation. |
| `docs/research-api.md` | 242-256 | Diplomacy route table. |
| `docs/research-ui.md` | 270-277 | Diplomacy panel description. |
| `docs/architecture.md` | 565-567, 596, 659-682 | Current pins and V4-10 seam. |
| `docs/v4-architecture.md` | 15, 340-352 | Four-owned/eight-unowned statement and V4-10 diplomacy section. |
| `docs/configuration.md` | 310-312, 455-465 | Four-owned/eight-unowned statement and diplomacy settings. |
| `docs/disputes.md` | 225 | Current 164 pin. |
| `docs/evidence-testimony.md` | 211 | Current 164 pin and V4-10 reference. |
| `docs/delegation-representation.md` | 137 | Current 164 pin. |
| `README.md` | 91 | Diplomacy documentation index row. |
| `.ai-factory/ARCHITECTURE.md` | 184, 204-206, 848-877 | Pin table, ownership list, V4-10 seam. |
| `.ai-factory/DESCRIPTION.md` | 375-424 | V4-09/V4-10 descriptions and pins. |
| `tests/unit/test_diplomacy_docs.py` | 1-80 | Existing documentation parity checks. |
| `docs/development.md` | test command table | Verification commands for Task 25. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `docs/diplomacy.md` | modify | Add treaty contract, versions/lineage, records/institutional memory, recollections/alignment, non-enforcement, API/UI, and 168 pins. |
| `docs/analysis-metrics.md` | modify | Add four treaty families and update 168. |
| `docs/research-api.md` | modify | Add two treaty routes and update eight-route count. |
| `docs/research-ui.md` | modify | Document the treaties view. |
| `docs/architecture.md` | modify | Add V4-11 seam and update current pins 168. |
| `docs/v4-architecture.md` | modify | Add V4-11 treaty section and keep historical 160 -> 164. |
| `docs/configuration.md` | modify | Confirm no new settings and update 168. |
| `docs/disputes.md` | modify | Update current 164 -> 168. |
| `docs/evidence-testimony.md` | modify | Update current 164 -> 168 and V4-11 reference. |
| `docs/delegation-representation.md` | modify | Update current 164 -> 168. |
| `docs/organizations.md` | modify | Link the treaty contract and confirm organizations remain an anchor source, not a treaty authority. |
| `README.md` | modify | Extend the Diplomacy row with treaties/versions/recollections and snapshot v2. |
| `.ai-factory/ARCHITECTURE.md` | modify | Add V4-11 seam and update pin/ownership text to 168. |
| `.ai-factory/DESCRIPTION.md` | modify | Add V4-11 paragraph and update pins to 168. |
| `tests/unit/test_diplomacy_docs.py` | modify | Add treaty doc sections, 168 pin, v2 snapshot, eight routes. |
| `tests/unit/test_treaty_docs.py` | create | Dedicated treaty documentation parity. |
| `index.md` | modify | Fill Task 24/25 progress and final certification receipt. |

## Task 24: Execute the documentation checkpoint

### Intent

Document the verified contract, not an aspirational one. Every statement must
match code and tests. Historical revision statements keep their original
numbers; only current pins move to 168.

### Implementation Steps

1. `docs/diplomacy.md`:
   - Keep the existing V4-10 sections and update the intro to say diplomacy
     now includes multi-party treaty commitments. Preserve the existing
     phrases that the V4-10 docs tests assert, including "owner-scoped belief",
     "never a polity", "treaty store", "envoy registry", "bilateral
     relationship score", "binds nobody", "diplomacy.v1", "diplomacy-snapshot-v1",
     and "diplomacy-store-v1".
   - Add `## Treaties` covering:
     - a treaty is an owner belief about a multi-party commitment;
     - examples and `TreatySubjectKind` values;
     - participants and the owner self-party;
     - `msoc-` identities are analysis-only and never parties;
     - recognized representatives: principal direct, recognized envoy with
       `negotiate`/`decide` and long-running duration, self-claim never counts;
     - `apparently_accepted` requires every participant's declaration and
       binds nobody;
     - no `TreatyStore`, `TreatyAuthority`, `WarState`, `CeasefireState`,
       polity, border, citizenship, or binding agreement.
   - Add `## Versions and lineage`:
     - immutable versions, contiguous indices, parent DAG;
     - `original`, `amendment`, `renewal`, `accession`, `withdrawal`,
       `suspension`, `termination`;
     - renewal only supersedes after the new version is accepted;
     - rejected renewal leaves the old version active;
     - two treaties may coexist.
   - Add `## Records and institutional memory`:
     - `record_refs` are opaque durable-record anchors;
     - `institutional_memory_refs` are opaque owner-local entry IDs;
     - no automatic write into either ledger;
     - no truth/authenticity.
   - Add `## Recollection and misremembering`:
     - bases: durable record, institutional memory, communicated testimony,
       narrative, direct participation;
     - stances: remember, reinterpret, ignore, renew;
     - misremembering is researcher-only alignment
       (`consistent`/`unresolved`/`inconsistent`/`not_applicable`);
     - no truth/lie/guilt field in cognition;
     - a recollection never creates a local treaty or version.
   - Add `## Speech` for `trt_v1`: 22 fields, 832 characters, chunked into at
     most four ordered relations, verified speaker, peer provenance/mandate
     are claims, `dip_v1` unchanged.
   - Add `## Non-enforcement`:
     - a ceasefire does not block an attack;
     - an access agreement grants no access;
     - a trade agreement moves nothing;
     - a territorial understanding changes no boundary;
     - a mutual-aid treaty performs no aid;
     - impossible commands remain impossible for physical reasons only.
   - Update `## Publication and API` to v2/v1, eight routes, treaty pages.
   - Update `## Metrics` to 168 and the four treaty families.
   - Update `## Research UI` with the treaties view.
2. `docs/analysis-metrics.md`:
   - Update line 41 to 168.
   - Update the section heading at line 554 to
     `## Diplomacy and treaty families (catalog 168)`.
   - Add a `## Treaty families` section after the diplomacy families with the
     four family IDs, exact value keys, denominators, and no-score statement.
3. `docs/research-api.md`:
   - Update the diplomacy route table to eight rows, adding:
     `GET /v1/simulations/{run_id}/diplomacy/treaties` and
     `GET /v1/simulations/{run_id}/diplomacy/treaties/{treaty_id}`.
   - State v1/v2 snapshot support and `diplomacy_disabled`.
4. `docs/research-ui.md`:
   - Extend the Diplomacy panel section with the read-only treaties view,
     versions, lineage, recollections, and no score/winner/legitimacy.
5. `docs/architecture.md`:
   - Add a `### V4-11 treaties seam` section after V4-10.
   - Update current 164 pins to 168 at 565, 596, and 659. Leave the historical
     V4-10 sentence at 677 ("catalog 160 -> 164") unchanged.
   - State the four owned flag set remains `organizations`, `formal_rules`,
     `legal_disputes`, `diplomacy`; eight unowned.
   - State no `runner-config-v57`, event, command, observer semantic, write
     pair, `/v2` route, or migration.
   - Add a matching V4-11 treaty section to `docs/v4-architecture.md` after
     its V4-10 diplomacy section. Keep the historical `160 -> 164` sentence at
     line 350 and the four-owned/eight-unowned statement at line 15. State
     the current catalog is 168.
6. `docs/configuration.md`:
   - Confirm no new treaty setting; treaties activate with `diplomacy`.
   - Update 164 -> 168 at 310-312.
7. `docs/disputes.md`, `docs/evidence-testimony.md`,
   `docs/delegation-representation.md`:
   - Update current 164 pins to 168 and mention V4-11 where the sentence lists
     V4-10.
8. `README.md`:
   - Extend the Diplomacy row to include multi-party treaties, versions,
     lineage, recollections, `diplomacy-snapshot-v2`, and the eight routes.
9. `docs/organizations.md`:
   - Link the treaty contract and state that organization/coalition anchors
     are participant sources, not treaty authorities.
10. `.ai-factory/ARCHITECTURE.md`:
   - Update the baseline table to 168 and include the existing V4-10 four
     diplomacy families plus the four V4-11 treaty families.
   - Update the ownership list to four owned/eight unowned (already correct,
     keep it).
   - Add a V4-11 seam after V4-10 with the exact authority, record, version,
     recollection, snapshot, store, and API statements.
   - Update current V4-10 pin lines at 844 and 873 from 164 to 168. Leave the
     historical V4-10 statement at 868 ("catalog 160 -> 164") unchanged.
11. `.ai-factory/DESCRIPTION.md`:
    - Add a V4-11 paragraph after V4-10.
    - Update current pins at 392/421 to 168.
    - Keep the historical "157 to 160" and "160 to 164" statements.
12. `tests/unit/test_diplomacy_docs.py`:
    - Assert `docs/diplomacy.md` contains the treaty sections.
    - Assert the current catalog pin is 168.
    - Assert snapshot v2 and v1 support are documented.
    - Assert exactly eight diplomacy routes are documented.
13. Create `tests/unit/test_treaty_docs.py`:
    - Assert `docs/diplomacy.md`, `docs/analysis-metrics.md`,
      `docs/research-api.md`, `docs/research-ui.md`, `README.md`,
      `docs/architecture.md`, `docs/configuration.md`,
      `docs/disputes.md`, `docs/evidence-testimony.md`,
      `docs/delegation-representation.md`, and `docs/organizations.md`
      contain the current treaty statements.
    - Assert no current-pin doc line asserts 164.
    - Assert no current section says `diplomacy` is unowned, nine V4 flags
      remain unowned, or the catalog is 164.
    - Assert historical revision statements remain.
    - Assert no doc claims enforcement, truth, binding, score, or winner.
    - Assert treaty records are distinguished from the still-forbidden
      `TreatyStore` and `TreatyAuthority`.
14. Run the docs parity tests and the pin guard before marking the task
    complete.
15. Do not edit `.ai-factory/ROADMAP.md`; `$aif-roadmap` owns registration and
    milestone text.

### Required Interfaces and Contracts

- Documentation states what treaties control (a belief) and what they never
  control (objective action, permission, truth, enforcement, or a binding
  agreement).
- Documentation distinguishes owner beliefs, objective records, and detached
  analysis.
- Documentation explains `trt_v1`, version lineage, recollection stances, and
  researcher-only alignment.
- Every current count matches code: 168 families, 14 contexts, 12 flags, four
  owned, eight unowned, eight diplomacy GET routes, snapshot v1/v2, store v1.
- Historical revision statements keep their original numbers.
- README links the canonical contract.

### Requirement Evidence (when reconciliation applies)

- Plan Settings "Docs: yes; mandatory $aif-docs checkpoint".
- `.ai-factory/ARCHITECTURE.md` requirement 7: roadmap owned by
  `$aif-roadmap`.
- Original Request all clauses; docs must not narrow or overclaim them.

### Error Handling and Logging

- Docs tests fail on missing sections or stale current pins.
- No runtime logging changes.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_docs.py tests/unit/test_treaty_docs.py -q`
- `rg -n "== 164" tests` returns no current-pin match.
- Expected: all tests pass.

### Acceptance Criteria

- Canonical docs describe the verified treaty contract.
- Current pins are 168; historical statements remain.
- No doc claims enforcement, truth, binding, score, or winner.
- README, architecture, V4 architecture, description, metrics, API, and UI
  docs link the contract.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_docs.py tests/unit/test_treaty_docs.py tests/unit/test_diplomacy_catalog.py -q`
- Expected: all tests pass.

## Task 25: Perform final V4-11 verification

### Intent

Audit the complete bundle, confirm every task is checked only after evidence,
and certify or withhold certification truthfully.

### Implementation Steps

1. Re-read `index.md` and every linked phase file. Confirm:
   - the ultra marker appears exactly once;
   - every Phase Index link exists;
   - every Task 1-25 appears once in the index checklist and once in a phase
     file;
   - dependencies point to existing task IDs;
   - no orphan phase file exists;
   - no phase file contains task checkboxes.
2. Verify the feature surface against the Definition of Done:
   - no new V4 flag/context/`v57`/runner root field/per-agent key;
   - 14 contexts / 12 flags / four owned / eight unowned;
   - treaty/version/declaration/recollection/lineage rows retained and
     validated;
   - `trt_v1` bounded; `dip_v1` unchanged;
   - ordered pipeline exact and idempotent;
   - no enforcement/command/truth/score/registry;
   - analysis three layers and researcher-only alignment;
   - catalog 168 with the first 164 preserved;
   - snapshot v2 + v1 decode; store v1;
   - eight GET routes; UI read-only;
   - no event/command/observer/write pair/`/v2`/migration.
3. Re-run the focused and static lanes from Task 23 after any file changed
   after the receipt was filled. In particular, run `mypy src tests` on the
   final tree, not an intermediate commit.
4. Audit the verification receipt: every required lane is
   `executed_passed`, `executed_failed`, or `unexecuted`; every unexecuted
   lane names its prerequisite; no skip is counted as a pass.
5. Confirm `git status` shows no `.ai-factory/ROADMAP.md` edit, no branch or
   worktree creation, and no unexpected generated artifact.
6. Set the final certification outcome:
   - `certified` only when every required lane is `executed_passed`;
   - `not certified` when any required lane is `executed_failed` or
     `unexecuted`.
7. Update only `index.md` task checkboxes and the final receipt. Do not change
   implementation or docs in this task.
8. Leave the plan bundle in place; `$aif-archive` owns archival.

### Required Interfaces and Contracts

- `index.md` is the only progress source.
- Certification is explicit and truthful.
- No lane is omitted or relabeled.
- Roadmap edits remain out of scope.

### Requirement Evidence (when reconciliation applies)

- Plan Settings "normal verification with explicit complete required-gate
  certification".
- `.ai-factory/ARCHITECTURE.md` verification and unexecuted-lane policy.

### Error Handling and Logging

- A missing lane or broken link fails final verification.
- A false pass is a certification violation.

### Tests

This task audits and may re-run Task 23 commands; it creates no new feature
tests.

### Acceptance Criteria

- The bundle is internally consistent.
- Every task has evidence.
- The receipt is complete and truthful.
- Certification is correct.

### Verification

- Bundle integrity checks from `ULTRA-FORMAT.md`.
- `git status` shows only intended V4-11 artifacts and no roadmap edit.
- Expected: `certified` only when all required lanes passed.

## Phase Risks and Mitigations

- Risk: Docs drift from code counts.
  Mitigation: docs parity tests and a stale-pin guard; current pins only.
- Risk: Historical statements are rewritten during the sweep.
  Mitigation: explicit allowlist for "160 -> 164", "157 -> 160", and the
  first-154 digest.
- Risk: The receipt claims certification with unexecuted lanes.
  Mitigation: Task 25 audits every lane and withholds certification.
- Risk: Final verification edits implementation.
  Mitigation: Task 25 changes only `index.md` progress/receipt.

## Phase Completion Checklist

- Every Task 24-25 acceptance criterion is met.
- Documentation is canonical and matches code.
- The bundle is internally consistent.
- The verification receipt is complete and truthful.
- Certification is explicit.
- `index.md` checkboxes are updated only after verification passes.
