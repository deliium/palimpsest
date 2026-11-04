# Phase 7: Invariants, End-to-End Diplomacy, and Regression

Plan: [index.md](index.md)
Tasks: 22-24
Depends on: Phase 2 / Task 11, Phase 6 / Task 21

## Objective

Prove every authority claim with executable architecture and determinism tests,
exercise the real cognition → speech → recognition → publication → API path end
to end, and run the full V1-V4 regression and qualification lanes with an honest
three-state receipt.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `tests/architecture/test_delegation_representation_boundaries.py` | 80-90, 111-124 | V4 feature boundary-suite shape |
| `tests/architecture/test_v4_architecture_invariants.py` | 156-236, 346-369 | Registry, reservation, and no-v57 pins |
| `tests/architecture/test_evidence_testimony_boundaries.py` | 297-312 | Ledger/world separation precedent |
| `tests/architecture/test_dispute_boundaries.py` | 456 | Command-path and catalog pins |
| `tests/unit/test_v1_regression_gate.py` | A-E gate | Must stay green with V4 flags off |
| `tests/unit/test_v2_scientific_invariants.py` | V2 invariants | Must stay green |
| `tests/integration/test_delegation_representation_e2e.py` | End-to-end shape | E2E precedent |
| `docs/development.md` | Verification command matrix | Lane definitions |
| `tests/compose/acceptance.py` | Compose/browser harness | Acceptance lane entry point |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `tests/architecture/test_diplomacy_boundaries.py` | modify | Extend to the full authority/determinism suite |
| `tests/unit/test_diplomacy_e2e.py` | create | Real in-process end-to-end scenario (no PostgreSQL) |
| `tests/unit/test_diplomacy_physical_distinction.py` | create | World-engine non-interference |
| `tests/unit/test_diplomacy_docs.py` | create | Documentation parity (Task 25) |
| `index.md` | modify | Verification receipt (Task 24) |

## Task 22: Add the diplomacy boundary and determinism suite

### Intent

A future implementer must not be able to claim diplomacy without provable
boundaries. This suite turns every non-goal into a failing test.

### Implementation Steps

1. Extend `tests/architecture/test_diplomacy_boundaries.py` with these cases:
   - `test_v4_10_owns_diplomacy_without_new_schema`: 14 contexts, 12 flags,
     four owned flags, `v4-context-map-v2`, no `runner-config-v57`, no new
     `SimulationRunnerSpec`/`SimulationRunnerConfig` field, no per-agent
     `diplomacy_mode` runner key.
   - `test_diplomacy_has_no_command_path`: AST/source scan proves
     `src/agents/cognition/diplomacy*.py`, `src/analysis/diplomacy*.py`,
     `src/simulation/diplomacy*.py`, `src/experiments/diplomacy*.py`, and
     `src/api/routes/diplomacy.py` never import `AgentCommand`, never call
     `submit`, `resolve`, or `admit`, and never return a command.
   - `test_diplomacy_ledger_is_not_world_read`: `src/world`,
     `src/simulation/engine.py`, admission, rules, stop selectors, `observer`,
     and `src/api` contain no import of `agents.cognition.diplomacy`; the API
     reads only `simulation.diplomacy_ports`/persistence readers.
   - `test_no_peer_ledger_reads`: the cognition update signature accepts only
     owner sidecars; scanning proves no `representation_ledger` from another
     owner and no `organization`/`office`/`rule`/`dispute`/`evidence` peer ledger
     is read.
   - `test_no_score_or_oracle`: no `RelationScore`, `DiplomacyScore`,
     `LegitimacyOracle`, `TruthEngine`, `TreatyStore`, `TreatyAuthority`,
     `EnvoyRegistry`, `Polity`, `Border`, `Citizenship`, `WarState`, or
     `ArmyActor` symbol exists; analysis rows and metric value keys contain no
     `score`, `rank`, `trust`, `valence`, `index`, `composite`, `mean_score`, or
     `overall_relation`.
   - `test_representation_principal_roundness`: party kinds equal the V4-09
     principal value set exactly; no nation/civilization/polity member exists.
   - `test_relation_and_termination_records`: every relation has an ordered
     party set with a self-party; every instrument party set matches; every
     termination target resolves; no row is deleted by expiry/supersession.
   - `test_scope_duration_matrix`: `single_act`/`occasion` never recognize a
     long-running agreement; a mismatched subject yields `scope_exceeded`; the
     same helper is used by Task 9 and Task 14.
   - `test_principal_declaration_and_current_standing`: a principal accept counts
     without an envoy; a revoked/superseded mandate is not current; the stored
     accreditation status is never treated as current.
   - `test_derived_row_pipeline`: one update materializes misrepresentation,
     expiration, supersession, conflict, and termination rows, and a repeated
     update is idempotent.
   - `test_token_domains_interoperate`: the agent token equals V4-09's
     representation token; `orgc-`/region anchors remain unhashed and the
     `org-`/`msoc-` joins resolve; `dip-pub-` is rejected as a candidate id.
   - `test_alignment_stays_researcher_only`: the four alignment statuses never
     appear under `src/agents`, `src/world`, `src/observer`, or `src/api`
     schemas.
   - `test_no_new_wire_surfaces`: events 22, codec `v20`, commands 43, observer
     semantics 73, Alembic `0017` with no `0018`, `/v1` only, no
     `observer-protocol-v2`.
   - `test_snapshot_and_store_schemas`: `diplomacy-snapshot-v1` and
     `diplomacy-store-v1` exist; the organization v1/v2/v3, formal-rule,
     dispute, evidence, and representation snapshots still decode from fixtures.
   - `test_six_routes_and_six_purposes`: exactly six GET diplomacy routes and
     six cursor purposes; route paths are under `/v1/simulations/{run_id}/diplomacy`.
   - `test_existing_pins_unchanged`: 14/12 registry, four owned / eight unowned
     V4 flags, four reservations (events 23-26 / codecs `v21`-`v24`),
     `prepare_parallel=False`, `organization_rows` reserved.
   - `test_no_roadmap_or_client_authority`: no `.ai-factory/ROADMAP.md` edit is
     required by the code; Python never imports either client; Godot files are
     untouched.
2. Create `tests/unit/test_diplomacy_physical_distinction.py`:
   - a physically possible command from an agent whose diplomatic standing is
     `rejected`/`unresolved` is still admitted;
   - a physically impossible command is still rejected by existing rules;
   - a contested agreement grants no access and moves no item;
   - `WorldEngine` and perception never observe a diplomacy ledger.
3. Create `tests/unit/test_diplomacy_determinism.py` cases if not already
   covered: identical seeds/observations produce identical digests; row order is
   stable; no `hash()`, UUID, or wall clock in diplomacy modules (AST scan).
4. Create `tests/unit/test_diplomacy_docs.py` parity assertions for Task 25
   (counts, route list, schema names, family names).

### Required Interfaces and Contracts

- The suite must fail on any new flag, context, runner schema, command, event,
  observer semantic, write pair, `/v2` route, migration, oracle, registry, or
  score.
- Existing pins are asserted, not weakened.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` Key Principles 1-6 and "Requirements for later
  changes".
- Original Request: "Representatives may misrepresent their society or lack full
  authority"; "Do not create magical bilateral relationship scores".

### Error Handling and Logging

- No runtime logging. Failures name the offending symbol and path.
- Do not add sleeps, retries, or environment-dependent skips.

### Tests

- `uv run pytest tests/architecture/test_diplomacy_boundaries.py tests/unit/test_diplomacy_physical_distinction.py tests/unit/test_diplomacy_determinism.py tests/unit/test_diplomacy_docs.py -q`
- Expected: pass.

### Acceptance Criteria

- Every claim in the Definition of Done has a named test.
- No authority boundary is merely documented.

### Verification

- `uv run pytest tests/architecture/test_diplomacy_boundaries.py -q`
- Expected: pass; `rg -n "AgentCommand" src/agents/cognition/diplomacy*.py src/analysis/diplomacy*.py src/simulation/diplomacy*.py` returns no match.

## Task 23: Add the diplomacy end-to-end scenario

### Intent

Unit tests can pass while the real path is broken. This scenario drives two
owners through contact, accreditation, negotiation, proposal, acceptance,
misrepresentation, publication, and read-only API access.

### Implementation Steps

1. Create `tests/unit/test_diplomacy_e2e.py` with a disposable in-process runner
   (no Docker, no PostgreSQL): `runner-config-v56` + `diplomacy=true` +
   `organizations=true` + the existing `resource_exchange_profile` needed to
   produce a real `ExchangeCompleted`, two agents in two regions, deterministic
   seed. Do not mark it `integration`; the marker is reserved for
   PostgreSQL-dependent tests (`pyproject.toml` 109).
2. Drive objective events through ordinary admitted commands: `Move`/journey to
   create `ContactRecorded` co-presence; `Talk` utterances carrying `dip_v1`
   frames for `dip_contact`, `dip_accredit`, `dip_open_negotiation`,
   `dip_propose`, `dip_accept`, `dip_promise`, `dip_shared_project`.
3. Give the first envoy a recognized representation mandate in the owner's own
   representation ledger via a real `rep_v1` delegation (V4-09 path), then revoke
   it and assert the next diplomatic declaration is recorded with a
   `mandate_unrecognized` misrepresentation row while the prior rows remain.
   Supersede it once and assert the envoy status becomes `SUPERSEDED`.
4. Give the second party's "accept" through a member frame that is not the
   principal and assert the agreement stays `proposed`/`unresolved`, not
   `apparently_accepted`.
5. Then have the actual second party's principal declare acceptance with no envoy
   and assert `apparently_accepted` with `all_parties_declared`, and that no
   objective resource moved.
6. Exercise a `single_act` mandate against a long-running agreement and assert
   `scope_exceeded`; exercise a recall/resignation and assert a retained
   `DiplomaticTermination`.
7. Complete the run, harvest with `entity_to_agent`, compose
   `diplomacy-snapshot-v1`, publish through a temporary filesystem root, and read
   all six routes with `SUBJECTIVE_DEBUG` credentials. Assert the summary,
   relation detail (including terminations), instruments, and lineage are
   populated and contain only tokens/owner-safe anchors.
8. Assert the lane family input has at least one row each for contact, exchange
   (via a real `ExchangeCompleted`, never `Given`), and agreement; conflict and
   narrative lanes may be empty and must remain legal.
9. Assert the scientific result document is byte-identical with publication on
   and off.
10. Add a second run with all V4 flags off and assert no diplomacy ledger,
    metric, or route data exists.

### Required Interfaces and Contracts

- The scenario uses real admission, real speech, real cognition update, real
  representation recognition, real publication, and the real API router.
- No test-only shortcut may write ledger rows directly into the runner result.
- Empty legal lanes stay empty; no zero-filled fabrication.

### Requirement Evidence (when reconciliation applies)

- Original Request: all eight supported interactions plus the misrepresentation
  clause.
- `.ai-factory/ARCHITECTURE.md` V3/V4 seams: every physical effect is an ordinary
  admitted command.

### Error Handling and Logging

- On failure, print safe counts only (relations, instruments, statuses), never
  tokens, ids, subjects, or frames.
- Do not mark the test `integration`; it must run in the focused/unit lane and
  never require PostgreSQL.

### Tests

- `uv run pytest tests/unit/test_diplomacy_e2e.py -q`
- Expected: pass.

### Acceptance Criteria

- The full path works from real ticks to read-only routes.
- Misrepresentation and partial authority are exercised, not simulated.

### Verification

- `uv run pytest tests/unit/test_diplomacy_e2e.py -q`
- Expected: pass; no PostgreSQL or browser prerequisite.

## Task 24: Execute the full V1-V4 regression and qualification lanes

### Intent

Certification must be honest: every required lane is `executed_passed`,
`executed_failed`, or `unexecuted` with a named prerequisite. A missing toolchain
is never a skip-pass.

### Implementation Steps

1. Run and record:
   - `uv run pytest tests/unit tests/architecture -q --cov --cov-report=term`
   - focused V4-10 suite, explicitly including
     `tests/unit/test_diplomacy_e2e.py` and
     `tests/architecture/test_diplomacy_boundaries.py` (no PostgreSQL)
   - V4 + organization + formal-rule + dispute + evidence + representation +
     diplomacy selection
   - documentation parity, including the four-owned/eight-unowned sweep and the
     `test_delegation_representation_catalog.py` stale-pin guard
   - `uv run ruff check src tests`
   - `uv run mypy src tests`
   - `uv run lint-imports`
   - `uv run pytest -m "integration and not scale" -q`
   - integration including scale
   - `docker compose config --quiet`
   - Compose/browser acceptance
   - Godot 4.7.2 regression
   - benchmark/scale lane
   - Research UI test, type/static check, and build
2. Write the Verification Receipt in `index.md` with exactly one state per lane,
   the command, the observed counts, and the named prerequisite for every
   `unexecuted` lane.
3. Do not record a partial run as passed; do not omit a required lane.
4. If any lane fails, keep it `executed_failed` and do not certify.
5. Confirm no `.ai-factory/ROADMAP.md` edit and branch remains `main`.

### Required Interfaces and Contracts

- Receipt schema: `| Lane | State | Evidence |`.
- Allowed states: `executed_passed`, `executed_failed`, `unexecuted`.
- Certification outcome is `certified` only when every required lane is
  `executed_passed`.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` requirements 3 and 6: keep regression gates
  green; preserve `prepare_parallel=False`.
- `docs/development.md`: verification command matrix.

### Error Handling and Logging

- Summarize truncated output; keep full logs outside the plan bundle.
- Never paste secrets, DSNs, tokens, or client payloads into the receipt.

### Tests

- The lanes themselves are the verification.

### Acceptance Criteria

- The receipt is complete and truthful.
- Any uncertified outcome names the blocking prerequisite.

### Verification

- Re-read `index.md` and confirm every row has exactly one allowed state and a
  command or prerequisite.

## Phase Risks and Mitigations

- Risk: the boundary suite documents rather than enforces.
  Mitigation: named failing assertions for every non-goal.
- Risk: the E2E bypasses real admission or recognition.
  Mitigation: explicit prohibition on direct ledger writes and a no-command-path
  scan.
- Risk: an unavailable toolchain is reported as passed.
  Mitigation: three-state receipt and a named prerequisite.

## Phase Completion Checklist

- Every task in this phase satisfies its acceptance criteria.
- Required verification commands pass or are honestly `unexecuted`.
- `index.md` task checkboxes are updated immediately after verified completion.
