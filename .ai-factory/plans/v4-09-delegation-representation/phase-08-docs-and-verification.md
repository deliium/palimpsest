# Phase 8: Documentation and Final Verification

Plan: [index.md](index.md)
Tasks: 23-24
Depends on: Tasks 2-22

## Objective

Publish the canonical representation contract and update every affected document
so counts, routes, settings, and schemas match the code exactly; then audit the
implementation against the plan and the receipt.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `docs/evidence-testimony.md` | full contract | Canonical-doc template |
| `docs/analysis-metrics.md` | 507-530 evidence families | Metric section template |
| `docs/research-api.md` | 48-56 routes/auth/cursors | API doc template |
| `docs/configuration.md` | 344-359 CLI/env | Config doc template |
| `docs/research-ui.md` | 247-258 panel | UI doc template |
| `README.md` | 89 evidence index entry | Landing-page index |
| `docs/organizations.md` | 225 See also | Collective-context owner page |
| `docs/architecture.md` | V4 seam section | Contributor contract |
| `tests/unit/test_evidence_testimony_docs.py` | parity assertions | Docs parity template |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `docs/delegation-representation.md` | create | Canonical contract |
| `docs/analysis-metrics.md` | modify | Three families and catalog 160 |
| `docs/research-api.md` | modify | Six routes, auth, disabled state, cursors |
| `docs/configuration.md` | modify | Env root, cursor key, CLI flags, receipts |
| `docs/research-ui.md` | modify | Representation panel states |
| `README.md` | modify | Index entry |
| `docs/organizations.md` | modify | See-also link |
| `docs/architecture.md` | modify | V4-09 seam paragraph |
| `.ai-factory/DESCRIPTION.md` | modify | V4-09 state paragraph and pins |
| `.ai-factory/ARCHITECTURE.md` | modify | V4-09 seam and baseline table |
| `tests/unit/test_delegation_representation_docs.py` | create | Docs parity |

## Task 23: Execute the documentation checkpoint

### Intent

Documentation is part of the contract: researchers must know that recognition is
a belief, what it never controls, and how to read the surfaces without inferring
legitimacy.

### Implementation Steps

1. Create `docs/delegation-representation.md` with these headings:
   - `## What representation is` — one owner's belief about standing to act or
     speak for a principal.
   - `## What it is not` — not authority, permission, legitimacy, verdict, or a
     global representative registry.
   - `## Principal kinds` — `agent`, `organization`, `settlement`, `coalition`,
     `unknown`, and the exact anchor each requires.
   - `## Scope and duration` — closed scope kinds, duration rules, expiry.
   - `## Support, opposition, and recognition` — the precedence table, the
     two-independent-root rule, same-root deduplication, self-support exclusion,
     rejection/contestation.
   - `## Revocation, resignation, and conflicts` — authorized revocation,
     contested revocations, supersession, coexistence.
   - `## Speech frames` — `rep_v1` shape, acts, verified-speaker rules.
   - `## Collective decisions and later diplomacy` — decision delegation stays
     decision-scoped; `representation_standing_summary` is read-only; no
     diplomacy/treaty behavior exists.
   - `## Analysis and metrics` — three layers, researcher-only scope alignment,
     the three families, catalog 160.
   - `## Publication and inspection` — snapshot/store schemas, six routes,
     cursors, disabled state.
   - `## Configuration` — `organizations` gate, env root, CLI flags.
   - `## Limits` — 32 mandates, 320 records, 256-character frames (384 policy
     ceiling), snapshot caps.
   - `## Non-claims` — no prevalence, reliability, legitimacy, or diplomatic
     capacity claim.
   - `## See also` — organizations, disputes, evidence, analysis metrics,
     research API, research UI.
2. Update `docs/analysis-metrics.md` with a "Delegation-representation families
   (catalog 160)" section: ids, estimands, denominators, coverage, and the
   explicit note that `not_applicable` is never counted as `consistent`.
3. Update `docs/research-api.md` with the six routes, `SUBJECTIVE_DEBUG`, the
   `representation_disabled` state, cursor TTL/400/410 errors, and the 2 MiB
   payload budget.
4. Update `docs/configuration.md` with `PALIMPSEST_REPRESENTATION_ROOT`,
   `PALIMPSEST_REPRESENTATION_CURSOR_KEY`, the three CLI flags, defaults, bounds,
   and receipt statuses.
5. Update `docs/research-ui.md` with the Representation panel states and the
   "owner belief — not legitimacy" chrome.
6. Add a README index entry and a `docs/organizations.md` See-also link.
7. Update `docs/architecture.md` and `.ai-factory/ARCHITECTURE.md` with the V4-09
   seam paragraph and baseline pins (metric families 160, six representation
   routes, snapshot/store names, 14 contexts / 12 flags / 3 owned).
8. Update `.ai-factory/DESCRIPTION.md` with a V4-09 paragraph and current pins.
9. Reconcile every current-pin mention: `docs/architecture.md`,
   `docs/analysis-metrics.md`, `docs/disputes.md`, `.ai-factory/ARCHITECTURE.md`,
   and `.ai-factory/DESCRIPTION.md` must say 160. Preserve historical revision
   statements (`154 to 157` in `docs/evidence-testimony.md`, V4-07/V4-08
   sections) and the unrelated `8,157` in `docs/long-horizon-scalability.md`.
10. Create `tests/unit/test_delegation_representation_docs.py` asserting:
    canonical headings, route list, settings names, schema names, catalog count
    160, the `organizations` gate, and the absence of legitimacy/truth claims.
    Re-run the organization, formal-rule, dispute, and evidence docs suites so a
    stale count cannot pass.
11. Do not edit `.ai-factory/ROADMAP.md`; `$aif-roadmap` owns registration.

### Required Interfaces and Contracts

- Every count and path in docs must match code and tests.
- The canonical page states what representation controls (a belief) and what it
  never controls (objective action, permission, or truth).
- Roadmap registration is explicitly out of scope.

### Error Handling and Logging

- Docs parity failures name the missing heading or mismatched count.
- No docs task logs or embeds secrets, tokens, or example DSNs.

### Tests

- `uv run pytest tests/unit/test_delegation_representation_docs.py -q`
- `uv run pytest tests/unit/test_organization_docs.py tests/unit/test_formal_rule_docs.py tests/unit/test_dispute_docs.py tests/unit/test_evidence_testimony_docs.py -q`
- Expected: pass; the four existing docs suites read the current `METRIC_FAMILY_COUNT`, so a stale 157 line fails here.

### Acceptance Criteria

- `docs/delegation-representation.md` is canonical and linked from README and
  `docs/organizations.md`.
- Every count, route, setting, and schema name matches the implementation.

### Verification

- Commands above return pass.
- `rg -n "delegation-representation-snapshot-v1|representation_disabled|160" docs/delegation-representation.md docs/analysis-metrics.md docs/research-api.md` returns the expected anchors.

## Task 24: Perform final V4-09 verification

### Intent

The final audit is a fresh read of every authority claim against code, tests,
docs, and the receipt. It must not accept a green summary that the artifacts do
not support.

### Implementation Steps

1. Verify bundle integrity: `index.md` is the only checkbox source; 24/24 tasks
   checked; eight Phase Index links resolve; each task maps to exactly one phase
   section; no phase file contains a task checkbox; no orphan phase file.
2. Re-read the ownership claim: `organizations` is still the only gate;
   `diplomacy` remains unowned; 14/12/3 unchanged; no `runner-config-v57`, new
   root field, or per-agent runner key.
3. Re-read the negative claims:
   - no `truth`, `verified`, `legitimate`, `permission`, `winner` field;
   - no representation oracle, registry, command construction, world read, or
     peer-ledger read;
   - no new command, event, observer semantic type, write pair, `/v2` route, or
     migration.
4. Verify the positive surface: ledger records, `rep_v1` frames, recognition
   precedence, revocation/conflict retention, six routes, six cursor purposes,
   snapshot/store schemas, three metric families, catalog 160, six UI client
   functions.
5. Verify carry: `Perspective.representation`, `SimulationRunnerResult
   .representation_ledgers`, checkpoint field, runtime commit, export.
6. Verify docs parity and that `.ai-factory/ROADMAP.md` was not edited; record
   the `$aif-roadmap` follow-up.
7. Audit the Task 22 receipt: every lane has exactly one state; every
   `unexecuted` row names a prerequisite; certification matches the states.
8. Record the audit and certification outcome in the `index.md` Verification
   Receipt section; do not weaken a pin to make a lane pass.
9. Confirm `git status --short` shows only V4-09 implementation, docs, tests, and
   the plan bundle (no roadmap edit, no branch change).

### Required Interfaces and Contracts

- The audit cites `path:line` for each material claim.
- A failing claim blocks certification and is fixed in the owning task, not
  papered over in the receipt.

### Error Handling and Logging

- Record safe codes and counts only.
- Never include secrets, DSNs, payloads, principal tokens, or representative ids
  in the audit.

### Tests

- Re-run the focused suite and the boundary suite after any audit fix.
- `uv run pytest tests/architecture/test_delegation_representation_boundaries.py -q`

### Acceptance Criteria

- Every claim is verified or explicitly reported as false.
- Certification is `certified` only when every required lane is
  `executed_passed`; otherwise it is `not certified`.

### Verification

- `git status --short`
- Expected: only planned paths; no `.ai-factory/ROADMAP.md` modification.

## Phase Risks and Mitigations

- Risk: docs drift from code after a late fix.
  Mitigation: Task 23 parity tests run again in Task 24.
- Risk: the audit accepts an `unexecuted` lane as green.
  Mitigation: explicit three-state audit and withheld certification.
- Risk: a late scope addition claims `diplomacy`.
  Mitigation: ownership pin fails on any new flag or context; the audit rechecks
  it.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass or are recorded with a prerequisite.
- `index.md` checkboxes, dependencies, and the receipt match the phase files.
