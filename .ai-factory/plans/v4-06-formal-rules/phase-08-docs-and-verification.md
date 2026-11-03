# Phase 8: Documentation and Final Verification

Plan: [index.md](index.md)
Tasks: 22-23
Depends on: Phase 7 / Tasks 19-21

## Objective

Document the implemented formal-rule contract and run the final V4-06 audit.
Documentation must state what a rule controls (a belief), what it never controls
(objective action), how physical impossibility differs from social prohibition,
how competing systems/versions/responses work, and how every count matches the
code.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `docs/architecture.md` | V4-04 contract 506-530; V4-05 contract 532-547 | Adjacent contract-section pattern. |
| `docs/configuration.md` | v55 section 284-320; owned-flag sentence 307-313 | Must state two owned and ten unowned flags. |
| `docs/research-api.md` | line 30 routes/snapshot; line 53 unowned statement | Must add six formal-rule routes and correct ownership. |
| `docs/v4-architecture.md` | row 59; section 89-94; opening 5-13 | Exactly 14 `###` headings are asserted by `test_v4_doc_keeps_fourteen_context_headings`. |
| `docs/research-ui.md` | panel inventory | Add the formal-rules panel. |
| `.ai-factory/DESCRIPTION.md` | V4-05 section 276-294 | Add a V4-06 section and update pins. |
| `.ai-factory/ARCHITECTURE.md` | V4-05 seam 659-680; baseline table 177-193 | Add a V4-06 seam and update the current pin table. |
| `README.md` | documentation index | Add `docs/formal-rules.md`. |
| `tests/unit/test_organization_docs.py` | 35-55 | Reads DESCRIPTION/ARCHITECTURE/docs and asserts 14 context headings. |
| `tests/unit/test_organization_operations_docs.py` | 51-62 | Asserts metric counts in docs. |
| `tests/unit/test_formal_rule_docs.py` | new | Asserts the new doc, counts, routes, and ownership parity. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `docs/formal-rules.md` | create | Complete formal-rule contract, stages, dimensions, responses, competing systems, physical/social distinction, provenance, limits, surfaces, non-goals. |
| `docs/architecture.md` | modify | Add `## V4-06 formal-rules contract`; update pins. |
| `docs/configuration.md` | modify | Two owned flags, ten unowned; `formal_rules` on v56 only; cognition mode is internal. |
| `docs/research-api.md` | modify | Six formal-rule routes; ownership statement; disabled/cursor errors. |
| `docs/v4-architecture.md` | modify | Move `formal_rules` from deferred to owned; keep exactly 14 `###` headings. |
| `docs/research-ui.md` | modify | Add the formal-rules panel. |
| `docs/organizations.md` | modify | Cross-link the sibling formal-rules context; no behavior change. |
| `README.md` | modify | Documentation index entry. |
| `.ai-factory/DESCRIPTION.md` | modify | V4-06 section and pins. |
| `.ai-factory/ARCHITECTURE.md` | modify | V4-06 seam and baseline pins. |
| `tests/unit/test_organization_docs.py` | modify | Count/strings 148 → 151 and formal-rules link. |
| `tests/unit/test_organization_operations_docs.py` | modify | 148 → 151 assertions. |
| `tests/unit/test_formal_rule_docs.py` | create | Formal-rule doc sections, counts, route table, and ownership parity. |

## Task 22: Execute the documentation checkpoint

### Intent

Make the docs the authoritative explanation of what V4-06 does and does not do,
with every count and route matching the code.

### Implementation Steps

1. Create `docs/formal-rules.md` with these sections:
   - **What a formal rule is** — one owner's belief about a socially recognized
     constraint; never a world law, admission gate, permission, or objective
     prohibition.
   - **What it never controls** — physical possibility, command admission,
     custody, movement, harm, or resource transfer. Those remain `WorldEngine`
     rules and agent commands.
   - **Progression** — habit → expectation → norm → documented →
     recognized enforcement, monotone per owner rule, with version history.
   - **Dimensions** — scope anchors, proponents, recognized authority, written
     representation (observed durable record/revision/repository), expected
     sanction, exceptions, historical versions.
   - **Responses** — follow, violate, challenge, reinterpret, ignore as declared
     responses/claims; silence is never a violation.
   - **Competing systems** — overlapping systems coexist; no precedence,
     majority, quorum, or consensus gate.
   - **Physical vs social** — a worked example: a physically possible `Give`
     remains admitted under a prohibition belief; an impossible `Give` is
     rejected by existing rules with no rule attribution.
   - **Provenance** — owner-local `frs-`/`frl-`/`frv-`/`fre-`/`frp-`/`frr-`/
     `frx-` ids and published `frule-`/`frul-`/`fruv-`/`frule-edge-` records.
   - **Capture, publication, and reads** — opt-in CLI, `formal-rule-snapshot-v1`,
     six GET routes, `SUBJECTIVE_DEBUG`, disabled/cursor errors.
   - **Limits and non-goals** — bounded caps; no court, police, government,
     jurisdiction, global registry, rule engine, or sanction engine.
2. Update `docs/architecture.md` with a `## V4-06 formal-rules contract` section
   describing the owner-scoped ledger, analysis, snapshot, publication, API, and
   pins. Update the pin list to 151 families, two owned V4 flags, and six
   formal-rule routes.
3. Update `docs/configuration.md`:
   - `formal_rules` is owned on `runner-config-v56` only;
   - `formal_rule_mode` is internal cognition configuration, not a runner field;
   - the other ten V4 flags remain unowned and fail closed;
   - the opt-in CLI flags are `--formal-rule-root`,
     `--formal-rule-max-publications`, `--formal-rule-max-bytes`;
   - the API roots are `PALIMPSEST_FORMAL_RULE_ROOT` and
     `PALIMPSEST_FORMAL_RULE_CURSOR_KEY`.
4. Update `docs/research-api.md`:
   - list the six formal-rule routes and their response shapes;
   - state `SUBJECTIVE_DEBUG`, `formal_rule_disabled`, and cursor errors;
   - correct the line that says all V4 flags are unowned.
5. Update `docs/v4-architecture.md`:
   - move `formal_rules` from "deferred" to owned;
   - keep exactly fourteen `###` context headings and twelve flag names;
   - do not add a fifteenth context heading.
6. Update `docs/research-ui.md` and `README.md` to list the new panel/doc.
7. Update `.ai-factory/DESCRIPTION.md` and `.ai-factory/ARCHITECTURE.md`:
   - V4-06 summary: owned flag, owner-scoped ledger, stages, competing systems,
     physical/social distinction, three metric families (148 → 151), snapshot v1,
     six routes, UI panel;
   - pins: runner v4/v55/v56, result v2/v3, 43 commands, 73 observer semantic
     types, `metric families 151` (use this exact phrase where the existing
     parity test expects it), replay-v22/codec v20, `/v1`,
     `observer-protocol-v1`, Alembic `0017`, two owned / ten unowned V4 flags.
8. Update docs tests:
   - `tests/unit/test_organization_docs.py` 39-55: replace the hard-coded
     `"metric families 148"` string with `151`, keep the 14-context / 12-flag
     assertion, and add a `docs/formal-rules.md` link assertion;
   - `tests/unit/test_organization_operations_docs.py` 51-62: replace the
     `METRIC_FAMILY_COUNT == 148` and `"148"` doc assertions with `151`;
   - add `tests/unit/test_formal_rule_docs.py` asserting:
     - `docs/formal-rules.md` contains the required sections;
     - `README.md` links the doc;
     - `.ai-factory/DESCRIPTION.md` contains `V4-06` and
       `metric families 151`;
     - `.ai-factory/ARCHITECTURE.md` contains the V4-06 seam and
       `metric families 151`;
     - `docs/architecture.md` contains the V4-06 contract and 151;
     - `docs/research-api.md` lists exactly six `/formal-rules` routes;
     - `docs/v4-architecture.md` keeps exactly 14 `###` headings and 12 flags;
     - no current V4-06 paragraph says "all V4 flags are unowned" or
       "every V4 flag is unowned";
     - the current ownership sentence names exactly two owned flags
       (`organizations`, `formal_rules`) and ten unowned;
     - the dated V4-05/V3 historical sections may retain their old counts.
9. Do not edit `.ai-factory/ROADMAP.md`; `$aif-roadmap` owns the milestone entry.
10. Do not claim prevalence, capacity, emergence probability, or predictive
    power.

### Required Interfaces and Contracts

- Every count in docs equals `METRIC_FAMILY_COUNT`, the route table, the context
  registry, or the flag set.
- The docs explicitly distinguish physical impossibility from social
  prohibition.
- The docs explicitly state that responses are declarations, not objective
  compliance.
- The docs explicitly state competing systems have no precedence.
- `docs/v4-architecture.md` keeps exactly 14 `###` headings.

### Requirement Evidence

- Original Request all dimensions.
- `.ai-factory/ARCHITECTURE.md` requirement 7 (roadmap ownership).
- `docs/architecture.md` 506-547 (adjacent contract style).
- `tests/unit/test_organization_docs.py` 35-55.

### Error Handling and Logging

- Docs work emits no runtime logs.
- If a docs test fails, fix the text or the code count; never weaken the
  assertion.
- Missing docs checkpoint is a plan failure, not a warning.

### Tests

- `uv run pytest tests/unit/test_organization_docs.py tests/unit/test_organization_operations_docs.py tests/unit/test_formal_rule_docs.py -q`
- `grep -R "metric families 148" -n .ai-factory docs README.md` → every match is
  in an explicitly dated V4-05/V3 historical section; no current V4-06 pin or
  current-count sentence still says 148.

### Acceptance Criteria

- A reader can answer what a rule controls, what it never controls, how
  competing systems work, and how physical/social constraints differ.
- Every current count matches the code.
- No roadmap edit.
- No unsupported empirical claim.

### Verification

- `uv run pytest tests/unit/test_organization_docs.py tests/unit/test_organization_operations_docs.py tests/unit/test_formal_rule_docs.py -q`
- `git diff --stat` shows only intended docs/tests.
- Expected: all docs tests pass; no roadmap diff.

## Task 23: Perform final V4-06 verification

### Intent

Audit the bundle, the code, the pins, the docs, and the receipt; certify only
what actually executed.

### Implementation Steps

1. Verify every `index.md` task checkbox is checked and maps to exactly one
   `## Task N` section in a linked phase file.
2. Run the final focused suite:
   - `uv run pytest tests/unit/test_formal_rule_*.py tests/architecture/test_formal_rule_boundaries.py -q`
   - `uv run pytest tests/unit tests/architecture --cov`
   - `uv run ruff check src tests`
   - `uv run mypy src tests`
   - `uv run lint-imports`
3. Verify cross-surface pins with exact commands:
   - `uv run python -c "from analysis.specifications import METRIC_FAMILY_COUNT; assert METRIC_FAMILY_COUNT == 151"`
   - `uv run python -c "from simulation.runner_models import _V4_OWNED_CAPABILITY_FLAGS as f; assert f == {'organizations','formal_rules'}"`
   - `uv run python -c "from simulation.v4_architecture import V4_CONTEXTS; assert len(V4_CONTEXTS) == 14"`
   - `uv run python -c "from simulation.versioning import V4_WRITE_PAIR_RESERVATIONS as r; assert len(r) == 4"` (use the actual exported name if different)
   - `grep -R "runner-config-v57" -n src tests` → no matches outside existing
     negative assertions that pin the schema version's absence
   - `find alembic/versions -maxdepth 1 -name '0018_*.py'` → no output
   - `grep -R "observer-protocol-v2" -n src/api src/observer` → no serving path
4. Verify organization surfaces are unchanged:
   - six GET organization routes;
   - organization snapshot v1/v2/v3 decode/encode tests;
   - organization metric families remain the six before the new tail.
5. Verify the verification receipt in `index.md`:
   - every row has a state and evidence;
   - no `unexecuted` required lane is described as passed;
   - the known-flake note is included only if it reproduced;
   - the receipt names the exact commands and prerequisites.
6. Verify the repository state:
   - `git status --short` shows only intended implementation/docs/plan files;
   - `.ai-factory/ROADMAP.md` is unchanged;
   - no branch or worktree was created;
   - no lockfile contents were edited intentionally.
7. Update `index.md`:
   - check all 23 boxes only after their verification passes;
   - fill `## Verification Receipt` with the final table;
   - add a short `Post-verification closure` paragraph listing any residual
     unexecuted prerequisite.
8. If any required lane is `unexecuted` or `executed_failed`, do not certify the
   plan. Record the blocker and stop.

### Required Interfaces and Contracts

- Certification requires every required lane to be `executed_passed`.
- An unexecuted lane is reported with its prerequisite and blocks certification.
- Pins are exact; no `>=`, membership-only, or skip-based assertions.
- The roadmap is untouched.
- Only `index.md` holds task checkboxes.

### Requirement Evidence

- Plan Settings "normal verification with explicit complete required-gate
  certification".
- `.ai-factory/ARCHITECTURE.md` requirements 1-7.
- `docs/development.md`.

### Error Handling and Logging

- A failed pin prints the expected and actual values only.
- A failed lane identifies the command and the failing test, with bounded output.
- Never include credentials, DSNs, prompts, or payloads in the receipt.

### Tests

This task runs the final audit; it does not add a new test file.

### Acceptance Criteria

- All 23 tasks are checked only after evidence.
- Every required lane is `executed_passed`; otherwise certification is withheld.
- Pins and docs match the code.
- The roadmap and branch state are untouched.
- The final receipt is complete and honest.

### Verification

- `git status --short`
- `git diff -- .ai-factory/ROADMAP.md` → empty
- `uv run pytest tests/unit/test_formal_rule_*.py tests/architecture/test_formal_rule_boundaries.py -q`
- `uv run pytest tests/unit tests/architecture --cov`
- Expected: green; receipt complete; roadmap untouched.

## Phase Risks and Mitigations

- Risk: docs claim a capability the code does not have.
  Mitigation: count and route assertions read from code; Task 23 cross-checks.
- Risk: historical V3/V4 sections are rewritten incorrectly.
  Mitigation: change only current V4-06 pins and explicitly dated sibling
  sections; leave historical baselines alone.
- Risk: a required lane is unexecuted but the plan is marked done.
  Mitigation: Task 23 blocks certification unless every required lane is
  `executed_passed`.
- Risk: the roadmap is edited by accident.
  Mitigation: `git diff -- .ai-factory/ROADMAP.md` must be empty.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
- Every count and route in docs matches the code.
- The roadmap remains untouched.
- The final receipt is complete, or certification is withheld with a blocker.
