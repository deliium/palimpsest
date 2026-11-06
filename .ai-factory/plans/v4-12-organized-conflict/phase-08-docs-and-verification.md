# Phase 8: Documentation and Final Verification

Plan: [index.md](index.md)
Tasks: 25-26
Depends on: Phase 7

## Objective

Replace stale counts with verified counts, document the exact organized-conflict
contract and its non-goals, link the new surfaces, and certify only lanes that
actually executed. The roadmap remains owned by `$aif-roadmap`.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `docs/diplomacy.md` | authority 24-36; vocabulary 37-66; detached analysis 151-166; metrics 168-183; publication/API 185-207; non-goals 218-226; treaties 228-280 | Canonical-contract structure to mirror |
| `docs/analysis-metrics.md` | catalog 168 line 41; diplomacy families 554-600 | Count and family documentation |
| `docs/research-api.md` | diplomacy routes 242-270; settings/errors 255-259 | Route documentation |
| `docs/research-ui.md` | diplomacy panel 270-278; treaties 280-288 | UI documentation |
| `docs/v4-architecture.md` | context rows 64-65; diplomacy 133-138; V4-10 341-352; V4-11 356-365 | Context/seam documentation |
| `docs/architecture.md` | 168 pins 565, 596, 659, 711; V4-10 seam 663-684; V4-11 688-713 | Architecture counts and seams |
| `docs/configuration.md` | flag ownership and env settings | Configuration documentation |
| `.ai-factory/ARCHITECTURE.md` | baseline table 179-188; capability ownership 196-208; V4-11 seam 881-904 | AI context counts and seam |
| `.ai-factory/DESCRIPTION.md` | V4-11 section 426-448 | Project description count |
| `tests/unit/test_diplomacy_docs.py` | 60-63 closed cardinality | Doc parity pattern |
| `tests/unit/test_treaty_docs.py` | 74-78 pins; 103-134 stale-claim guard | Doc sweep pattern |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `docs/organized-conflict.md` | create | Canonical contract |
| `docs/analysis-metrics.md` | modify | 172 and four families |
| `docs/research-api.md` | modify | Six routes and settings |
| `docs/research-ui.md` | modify | Read-only conflict view |
| `docs/v4-architecture.md` | modify | V4-12 seam and five owned flags |
| `docs/architecture.md` | modify | 172 counts and V4-12 seam link |
| `docs/configuration.md` | modify | Flag ownership, modes, env keys |
| `docs/diplomacy.md` | modify | Link to the conflict contract |
| `README.md` | modify | Link the canonical contract |
| `.ai-factory/ARCHITECTURE.md` | modify | Five owned flags, 172 families, V4-12 seam |
| `.ai-factory/DESCRIPTION.md` | modify | V4-12 section and current pins |
| `tests/unit/test_organized_conflict_docs.py` | create | Documentation parity |
| `tests/unit/test_organized_conflict_catalog.py` | modify | No current 168 guard |
| `tests/architecture/test_organized_conflict_boundaries.py` | modify | Doc/count pins |

## Task 25: Execute the documentation checkpoint

### Intent

Document what organized conflict controls and, more importantly, what it never
controls, so later readers do not mistake a plan for a war state or an
interpretation for truth.

### Implementation Steps

1. Create `docs/organized-conflict.md` with sections:
   - Status and ownership: `organized_conflict` is owned by V4-12 on
     `runner-config-v56`; it requires `diplomacy`.
   - Authority: coordination is one owner's belief; physical effects are ordinary
     `WorldEngine` admission; no war state, army, registry, or hierarchy.
   - The eight operations and their exact command matrix.
   - Defense: `Help`/`Attack`/`Move`; no mitigation.
   - Resource capture: `Take` from ground/corpse, voluntary `Give`; no living
     seizure or ownership transfer.
   - Structure attack: `OpposePublicGood` on completed public-good projects;
     no generic structure damage.
   - Route blocking: endpoint presence and attack/flee; routes are never closed.
   - Movement groups: independent `Move`/`Transport`; no group command.
   - Retreat: `Flee`; assistance: `Help`/`Feed`/`Transport`.
   - `ocf_v1`: 12 fields, 256 characters, one relation, trust rules.
   - Owner ledger: rows, IDs, digest, ordered pipeline, caps.
   - Detached detection: exact thresholds, three classes, event inputs.
   - Differing interpretations: retained, never reconciled.
   - Researcher-only alignment and forbidden scores.
   - Snapshot/store/API/UI.
   - Non-goals and explicit absences.
2. Update `docs/analysis-metrics.md`:
   - catalog 168 -> 172;
   - document the four families, their value keys, denominators, and empty/
     unknown cases;
   - keep historical 160 -> 164 -> 168 statements.
3. Update `docs/research-api.md`:
   - six organized-conflict routes;
   - `SUBJECTIVE_DEBUG`;
   - 503 `organized_conflict_disabled`;
   - 400 cursor invalid, 410 expired, 404 unknown;
   - `PALIMPSEST_ORGANIZED_CONFLICT_ROOT` and
     `PALIMPSEST_ORGANIZED_CONFLICT_CURSOR_KEY`.
4. Update `docs/research-ui.md`:
   - conflict panel and tab;
   - neutral labels;
   - no authority/score/winner derivation.
5. Update `docs/v4-architecture.md`:
   - `organized_conflict` owned by V4-12;
   - five owned / seven unowned;
   - V4-12 seam section;
   - no new flag/context/schema.
6. Update `docs/architecture.md`:
   - all current 168 pins -> 172;
   - V4-12 seam and six routes;
   - keep historical revision statements.
7. Update `docs/configuration.md`:
   - `organized_conflict` ownership and diplomacy prerequisite;
   - run-level mode is not a per-agent key;
   - env keys.
8. Update `.ai-factory/ARCHITECTURE.md`:
   - baseline metric families 172;
   - owned flags five, unowned seven;
   - V4-12 seam section with exact bounds and non-goals.
9. Update `.ai-factory/DESCRIPTION.md`:
   - V4-12 section after V4-11;
   - current pins 172, five owned, six routes, new snapshot/store.
10. Link `docs/diplomacy.md` and `README.md` to
    `docs/organized-conflict.md`.
11. Sweep every current `168` pin in tests/docs/.ai-factory to `172`; preserve
    historical statements and the first-168 order/digest.
12. Add `tests/unit/test_organized_conflict_docs.py` asserting:
    - canonical contract exists and names all eight operations;
    - 172 appears in the required docs;
    - six routes and six cursor purposes;
    - no current 168 pin remains;
    - historical revision statements remain;
    - no “war state”, “winner”, “legitimacy score”, or “enforcement” claim.
13. Run doc parity tests.

### Required Interfaces and Contracts

Documentation is descriptive, not normative. Every count, route, schema, flag,
and field must match code. Historical statements remain historical.

### Requirement Evidence

- Source: Original Request — all eight primitives, analytics, differing
  interpretations.
- Source: `.ai-factory/ARCHITECTURE.md` requirement 7 — roadmap ownership.
- Supported combinations: docs describe enabled/disabled, individual/coordinated/
  persistent, consistent/unresolved/inconsistent/not_applicable, and every
  non-goal.

### Error Handling and Logging

Docs only. No runtime logging.

### Tests

- `tests/unit/test_organized_conflict_docs.py`
- `tests/unit/test_organized_conflict_catalog.py`
- Command:
  `uv run pytest tests/unit/test_organized_conflict_docs.py tests/unit/test_organized_conflict_catalog.py -q`

### Acceptance Criteria

- `docs/organized-conflict.md` is the canonical contract.
- All current pins say 172; historical statements are intact.
- Six routes and the new snapshot/store are documented.
- Non-goals are explicit and match code.
- README and diplomacy docs link the contract.

### Verification

- Command above.
- Expected: all pass.

## Task 26: Perform final V4-12 verification

### Intent

Audit the entire bundle, the worktree, the counts, and the receipt. Certify only
what ran. Do not commit, edit the roadmap, or claim unexecuted lanes.

### Implementation Steps

1. Verify every indexed task checkbox matches a phase section and completion
   evidence; there are exactly 26 tasks.
2. Verify bundle integrity:
   - `<!-- aif:plan-mode:ultra -->` appears exactly once in `index.md`;
   - every Phase Index link exists and is relative;
   - every task maps to exactly one phase section;
   - no phase file contains checkboxes;
   - no orphan phase file.
3. Audit the worktree:
   - `git status --short`;
   - no `.ai-factory/ROADMAP.md` modification;
   - no branch or commit created by planning;
   - no unintended generated artifacts.
4. Audit the wire surface:
   - no `runner-config-v57`;
   - no new V4 flag or context;
   - commands 43, observer semantic types 73, replay 22, codec v20;
   - Alembic `0017`, no `0018`;
   - no `/v2` route, no `observer-protocol-v2`.
5. Audit ownership and counts:
   - 14 contexts, 12 flags, 5 owned, 7 unowned;
   - metric families 172;
   - eight diplomacy routes unchanged, six conflict routes;
   - snapshot/store schema strings exact.
6. Audit the receipt:
   - every lane has exactly one state;
   - every `unexecuted` lane names its prerequisite;
   - every `executed_passed` lane has a command and bounded evidence;
   - no `executed_failed` lane is hidden;
   - certification outcome is `not certified` when any required lane is
     unexecuted.
7. Re-run the focused suite and static gates if any file changed after Task 24.
8. Produce a final report with:
   - plan path and task count;
   - verified counts;
   - executed lanes and evidence;
   - unexecuted lanes and prerequisites;
   - certification outcome;
   - explicit statement that no implementation or commit was performed.
9. Stop. Do not invoke `$aif-implement`, `$aif-commit`, or `$aif-roadmap`.

### Required Interfaces and Contracts

The final report uses the exact lane states from the index receipt. It never
upgrades an unexecuted lane.

### Requirement Evidence

- Source: Plan Settings — normal verification with explicit complete
  required-gate certification.
- Source: `.ai-factory/ARCHITECTURE.md` requirements 1-7.
- Supported combinations: certified only when every required lane executed and
  passed; otherwise not certified with named blockers.

### Error Handling and Logging

- Report safe counts and codes only.
- Never include DSNs, tokens, payloads, prompts, or full logs.
- If an audit fails, report the exact file/assertion and stop.

### Tests

- Re-run the focused suite and static gates if needed.
- Command:
  `uv run pytest tests/unit/test_organized_conflict_*.py tests/architecture/test_organized_conflict_boundaries.py -q`
- Expected: all pass.

### Acceptance Criteria

- Bundle integrity passes.
- No roadmap, branch, commit, or implementation change was made by planning.
- Every pin and route count matches code.
- The receipt is honest and complete.
- Certification is withheld if any required lane is unexecuted.

### Verification

- Read the final report and compare it with `index.md`.
- Expected: task count, pins, routes, schemas, and lane states agree.

## Phase Risks and Mitigations

- Risk: a docs sweep changes historical counts.
  Mitigation: preserve historical statements and only sweep current pins.
- Risk: final verification claims a lane that did not run.
  Mitigation: exact one-state receipt and explicit prerequisites.
- Risk: the roadmap is edited by mistake.
  Mitigation: `git status` audit and explicit non-goal.
- Risk: a bundle link is broken after edits.
  Mitigation: integrity checks in Task 26.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
