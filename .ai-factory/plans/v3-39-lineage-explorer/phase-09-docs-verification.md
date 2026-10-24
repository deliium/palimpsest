# Phase 9: Documentation and final verification

Plan: [index.md](index.md)  
Tasks: 17–18  
Depends on: Tasks 1–16

## Objective
Deliver an implementable client/operator contract and verify the feature without claiming unrun checks or closing unrelated roadmap work.

## Current-Code Evidence

| Path | Section / purpose | Relevance |
|---|---|---|
| `docs/development.md` | Tests | Pinned Python verification commands and disposable DB rules. |
| `docs/research-causal-debugger.md` | Existing debugger documentation | Clarify old drill-down versus new graph query surface. |
| `README.md`; `AGENTS.md` | Documentation index | Add a discoverable lineage page, keep landing page lean. |
| `.ai-factory/ROADMAP.md` | M7 | In-progress scope indicator, not permission to claim remaining flags. |

## Files to Change
Create `docs/lineage-explorer.md`. Modify relevant sections of `docs/configuration.md`, `docs/development.md`, `docs/research-causal-debugger.md`, `README.md`, and `AGENTS.md`. Through their owning workflows update `.ai-factory/DESCRIPTION.md` / `.ai-factory/ARCHITECTURE.md` only for the shipped query/capture contract; roadmap changes are routed through `/aif-roadmap`, not made by architectural inference. No documentation edits are performed during planning.

## Task 17: Complete the mandatory documentation checkpoint

### Intent / Implementation Steps
1. Invoke `$aif-docs` during implementation for the required docs checkpoint. Write `docs/lineage-explorer.md` as the complete backend contract: eight-family/class matrix, qualified IDs, native edge directions, source activation/coverage, selected-owner privacy, capture-only historical boundaries, pruning/stubs, pagination record semantics and graph limits.
2. Give executable header-authenticated GET examples for all four user questions. Obtain qualified root keys via `/nodes`, using paired `native_kind`/`native_id` for exact lookup; Alice's display name is not accepted as identity. Explain shared analytical actor references versus distinct owner-local entries, agent-level teaching-claim chains versus proven content ancestry, and source/uptake uncertainty. Show `context_only`/`matched_node_keys` for living-descendant output.
3. Explain both-client consumption: same API, no layout fields, cursor reuse with identical parameters, endpoint descriptor deduplication, partial graph selection versus missing evidence, rerooting past traversal limits, strict error/availability codes. No Godot or Research UI feature is promised or implemented by this backend plan.
4. Document `palimpsest-matrix generational --lineage-root ...`, cadence and cap flags, publication tree ownership, capture health and deployment with `PALIMPSEST_LINEAGE_ROOT`. Caps are cumulative per-run scoped publication reservations and encoded artifact bytes, not a resettable session allowance or OS disk quota. Include staging/orphan charges and the conservative 256-KiB control allowance; many owners/families can consume multiple slots at one B. Root setting is reader-only. Existing runs cannot recover uncaptured subjective past from replay; no implicit backfill or full subjective resume.
5. Document optional shared `PALIMPSEST_LINEAGE_CURSOR_KEY`, safe handling, TTL, worker consistency and rotation. Explain distinct snapshot-catalogue, node-catalogue and graph cursor contracts and their pinned generations; cursors are not credentials. Describe operator-trusted roots/no symlinks, `state.json.committed_ref` as the atomic publication point, readers ignoring pending reservations, writer-only bounded recovery, abandoned reservations staying charged, and explicit operator action for stale locks. No GET repairs, deletions or quota resets; no real keys/tokens in examples or query strings.
6. Add test commands and a table of unchanged compatibility surfaces: SQL head `0017`, default runner/result v4/v2, latest feature v55, replay-v22/codec v20 when selected, 43 commands, 73 observer types, 136 metrics, `/v1`, `observer-protocol-v1`; no ownership of remaining flags. Describe lineage artifacts as researcher read models, not world registries.

### Required Interfaces and Contracts
Documentation must match actual OpenAPI/CLI output and tests. State that analytical institution snapshots are published only where detailed source evidence exists, usually at the completed captured boundary; do not advertise arbitrary-time analytical reconstruction.

### Requirement Evidence
User both-client APIs and historical questions; confirmed preference `Docs: yes`; architecture's provenance and compatibility requirements.

### Error Handling and Logging
Examples use only safe placeholders. Include unavailable, partial, expired-cursor and corrupt-source examples without raw source paths/payloads.

### Tests / Acceptance / Verification
Run `uv run --frozen --python 3.12.14 palimpsest-matrix generational --help` and API contract tests from Task 14. Check every documentation link and example parameter against shipped routes; no unbounded traversal or public subjective examples. Acceptance: `$aif-docs` checkpoint recorded as completed and docs distinguish capture/read/query semantics accurately.

## Task 18: Run complete checks and reconcile implementation with this plan

### Intent / Implementation Steps
1. Execute the commands below with coverage enabled. Record actual pass/fail counts and any skipped checks in the implementation summary, not invented success. Fix failures caused by this feature; do not reset unrelated user work.
2. Verify each Task 1–17 criterion and the index tables against code/tests, including all seven approved refinement findings: detailed teaching inputs/identity, actual production/fork installation, physical-read accounting/indexed native lookup, crash commit/quota semantics, strict decoding, purpose-specific cursors and retained-observation merging. Confirm only `index.md` owns task checkboxes; mark a task complete only after verification.
3. Review targeted diffs for accidental payload fields/logs, new write routes, query-side mutation, unbounded reads, legacy schema widening, capability enablement, dependency changes or client changes. No lockfile reads/full diffs.
4. Confirm default-off capture leaves existing behavior intact. Preserve all existing migration/head and scientific gates. If unrelated pre-existing failures prevent full verification, list them explicitly; do not mark the feature fully verified by hiding or skipping those tests.
5. Run `$aif-verify` against this explicit bundle after implementation. M7 remains open for `institutional_economy` and deferred kinship handoff; M6 remains open for `multi_hop_testimony_tracking`. Do not mark either milestone complete because this query backend ships.

### Required Interfaces and Contracts
No implementation is authorized by this planning invocation. During later implementation, docs and verification ownership follow the named skills. Existing SQL integration tests are optional infrastructure-dependent checks; if run, use only disposable `palimpsest_test` databases and explicitly report skips. This feature's historical artifact durability is tested by filesystem restart tests, not claimed as simulation restart.

### Error Handling and Logging
Final reports contain safe summary/error codes, not credentials, logs with payloads or private artifacts. State any remaining blocker rather than silently narrowing scope.

### Tests / Acceptance / Verification

```sh
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src tests
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term-missing
```

Expected: all default unit/architecture tests pass, typing/lint clean, coverage remains enabled; dedicated new family, capture, restart, bounds and authorization cases executed. No PostgreSQL/Godot/browser runtime is required for the default suite. Acceptance: feature reconciles with every supported combination and is implementation-verified, with honest limitations and no unrelated milestone closure.

## Phase Risks and Mitigations
- Documentation overpromises old subjective history: explicitly list missing capture and analytical boundary limitations.
- Large default suite masks skipped gates: final summary lists commands/results and unrun infrastructure checks separately.

## Phase Completion Checklist
- Mandatory docs checkpoint and full verification complete; record final task state only in `index.md`.
