# Phase 8: Documentation and final compatibility gate

Plan: [index.md](index.md)
Tasks: 14
Depends on: Tasks 1–13

## Objective
Document precise guarantees and verify the complete implementation without changing unrelated historical artifacts or claiming unfinished capability ownership.

## Current-Code Evidence

| Path | Symbols / sections | Why it matters |
|---|---|---|
| `.ai-factory/ARCHITECTURE.md` | Current baseline through V3-32; extension requirements | Existing pins and non-authoritative cognition boundary. |
| `docs/configuration.md` | versioned runner configuration | New exact mode/schema and prerequisite combinations. |
| `docs/mediation.md` | owner-scoped mode, examples and limitations | Documentation style for adjacent subjective mechanism. |
| `docs/development.md` | Tests | Frozen Python 3.12.14 commands and infrastructure-free default suite. |
| `README.md` | documentation index | Lean landing-page link, not a long feature manual. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `docs/institutional-memory.md` | create | Mechanisms, provenance, successor learning, limitations and reproduction. |
| `docs/configuration.md` | modify | v53 exact keys/dependencies and off-path behavior. |
| `docs/architecture.md` | modify | New seam and no new objective authority/write pair. |
| `docs/experiments.md` | modify | BJ arms, opportunity contrasts and non-success acceptance. |
| `README.md` | modify | Add new documentation index link only. |
| `.ai-factory/DESCRIPTION.md` | modify during implementation docs checkpoint | Append/update current V3-33 state without overwriting unrelated edits. |
| `.ai-factory/ARCHITECTURE.md` | modify during implementation docs checkpoint | Current feature version v53, metric families 126, institutional-memory seam. |
| affected catalog/version tests | modify | Intentional current pins only, with existing legacy fixtures retained. |

## Task 14: Complete docs checkpoint and run full gates

### Intent
Communicate what actually persists and how learners obtain it. Do not overclaim privacy, correctness, durable subjective restart or institution authority.

### Implementation Steps
1. Invoke `$aif-docs` as the mandatory implementation checkpoint, scoped to these pages. Show the user the documentation checkpoint. Document role/procedure channels, local binding, frames, read/teach/transmit flow, ignored/partial/conflicting states, caps/pruning and attributed/native/declared provenance.
2. Illustrate trade ledger, archive, project record, decision record and succession history as uses of ordinary artifacts/public claims, not five new institution types. Give a concrete A→record→B→teaching→C path and a no-access failure path. Reading is observation+interpretation, not a new world action; learning is not accession.
3. Explicit limitations: repository retrieval permissions are not reading confidentiality; no office-derived access grants; public frame syntax is not truth; copying can preserve wrong claims; damaged facts are not reconstructed from lineage; a surviving record can be ignored; runtime object continuation is not durable restoration of all subjective ledgers; objective physical records do persist/replay using existing codecs. Existing newborn profiles remain new-mode off. Document explicit `species_default_institutional_memory_v1` as a v53-only modes-on/content-empty opt-in, not inheritance, and show an admitted learner acquiring later. Distinguish the preserved outer utterance envelope from institutional frame parent/root testimony.
4. Document v53 per-agent exact key, same-owner office/procedure prerequisite, explicit learner-profile gate, optional artifact/teaching gates, independent institutional teaching selection, owner-local ignore/unignore decisions, v52 mediation composition, mixed owners, default v4, accepted legacy versions and invalid examples. Keep both unowned flags fail-closed. Pins: commands 43, semantics 73, latest available replay V22/codec v20 but channel-selected, Alembic 0017, `/v1`, `observer-protocol-v1`, `prepare_parallel=False`; metric families 126.
5. Execute focused new tests, adjacent regressions, full default suite with coverage, Ruff, strict mypy and import-linter. Fix only regressions introduced by this plan; report unrelated baseline failures separately with exact command and code evidence. Do not disable coverage, weaken contracts, delete legacy fixtures or change generated lockfiles/dependencies to make gates pass.
6. Review the targeted diff for payload logging, private/analysis imports, hidden state fetches and unrelated edits. Preserve preexisting user changes. Record actual verification outcomes in the implementation summary; mark Task 14 complete only after all plan-owned acceptance checks pass. Milestone M7 remains open; roadmap updates belong to `$aif-roadmap`, not this task's authority.

### Required Interfaces and Contracts
No new API route/client schema, SQL migration, world command/event or objective codec version. No claiming `institutional_economy`. Source docs must say 'claimed', 'observed', 'learned', and 'analytically aligned' distinctly. This planning invocation itself changes only the plan bundle; these docs edits are future implementation work.

### Requirement Evidence
All index reconciliation rules, user's illustrative uses, architecture version-extension contract and configured mandatory docs/testing preference.

### Error Handling and Logging
Documentation includes code-only diagnostics and safe counts. Never paste real credentials, DSNs, record bodies or memory payloads into logs/examples. Report unresolved gates honestly; no fabricated successful test run.

### Tests
Run full default suite and tools below. New feature tests must include actual engine/runner/collector/replay integration, not only constructed DTOs. Integration/Compose remain opt-in and unnecessary because no persistence adapter/schema change is planned.

### Acceptance Criteria
All new mechanisms and negative guarantees have passing tests; docs describe precise limitations; existing off-path outputs and pins remain unchanged except intentional v53/two-family additions. No blocking open implementation choice remains.

### Verification
```bash
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term -q
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src tests
uv run --frozen --python 3.12.14 lint-imports
```

Run each command independently. Expected: default unit/architecture suite, existing regression gates, lint, typing and import boundaries pass without live infrastructure. Verify docs links and configuration examples against actual encoded v53 output. Tests are planned here, not executed by the planning command.

## Phase Risks and Mitigations
- Existing docs/context have historical counts and pending user edits. Mitigation: scoped current-state additions and targeted diffs; do not normalize all history or overwrite existing changes.
- Misleading persistence claims undermine the experiment. Mitigation: separate objective external-memory durability, supported runtime continuation and deferred full subjective durable restart explicitly.

## Phase Completion Checklist
- Verify Task 14 and mark index only.
- Commit checkpoint 4 follows Tasks 12–14; no auto-push.
