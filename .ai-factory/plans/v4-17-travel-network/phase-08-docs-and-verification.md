# Phase 8: Documentation and Verification

Plan: [index.md](index.md)
Tasks: 24-25
Depends on: Phase 7 (Tasks 21-23)

## Objective

Land the V4-17 contract, ownership, pins, surfaces, and measured verification in
the project's documentation, then execute the required-gate verification and
record exactly which lanes passed or remain `unexecuted` with prerequisites.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `README.md` | documentation index | Must link the new travel-network page. |
| `docs/infrastructure-networks.md` | 7-17 ownership; 20-28 pins; 41-90 catalog; 107-132 metrics/surfaces | V4-17 deepens this contract; must cross-link and update route surfaces. |
| `docs/v4-architecture.md` | 268 catalog; 271 six GET routes | Update contexts/flags/pins and route count. |
| `docs/configuration.md` | runner v56 and feature gates | Document activation (infrastructure + regions) and no v57. |
| `docs/persistence.md` | accepted events/codecs/checkpoints | Document V27/`v25`, v21/v19 compatibility, and Alembic 0017. |
| `docs/analysis-metrics.md` | catalog 188; append 697-704 | Append four families and 192. |
| `docs/research-api.md` | infrastructure routes | Add the routes route and dual-gate behavior. |
| `docs/research-ui.md` | infrastructure panel | Add the routes section. |
| `docs/observer.md` / Godot docs | objective overlays | Add route status styling. |
| `.ai-factory/ARCHITECTURE.md` | baseline through V4-16; V4-15 seam | Add the V4-17 deepening seam and update the baseline table. |
| `docs/development.md` | verification commands and Godot pin | Source of exact gate commands. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `docs/travel-network.md` | create | Full V4-17 contract, derivation table, beliefs, pins, verification. |
| `README.md` | modify | Add the travel-network documentation link. |
| `docs/infrastructure-networks.md` | modify | Cross-link and note route condition v2. |
| `docs/v4-architecture.md` | modify | Deepening ownership, pair 27/`v25`, 192 metrics, seven routes. |
| `docs/configuration.md` | modify | Activation rule; no new flag/v57. |
| `docs/persistence.md` | modify | V27/`v25` acceptance, v21/v19 compatibility. |
| `docs/analysis-metrics.md` | modify | Four appended families, 192. |
| `docs/research-api.md` | modify | Seven routes, dual gate, paging. |
| `docs/research-ui.md` | modify | Routes section. |
| `docs/observer.md` | modify | Route-status overlay semantics. |
| `.ai-factory/ARCHITECTURE.md` | modify | V4-17 seam, baseline table, ownership note. |
| `.ai-factory/DESCRIPTION.md` | modify | V4-17 shipped state and pins. |
| `.ai-factory/ROADMAP.md` | do not edit | Owned by `$aif-roadmap`. |

## Task 24: Documentation via `$aif-docs`

### Intent

Produce one authoritative travel-network page and update every pinned surface so
later plans and users can discover the contract without reading source.

### Implementation Steps

1. Invoke `$aif-docs` with the V4-17 ownership summary and mandatory
   documentation checkpoint.
2. Create `docs/travel-network.md` with sections:
   - Ownership and authority (deepening `infrastructure_networks` +
     `regions_migration`; no new flag/context).
   - Activation matrix (infra on/off x regions on/off).
   - Locked `travel-network.v1` constants and derivation table.
   - Route status/availability/blockage semantics.
   - Write pair `(27, "v25")`, replay-v27, checkpoint compatibility.
   - Movement rules (closed/restricted/capacity/risk).
   - Observation fields and subjective beliefs (stale/inaccurate legal).
   - Infrastructure quality/capacity/road/bridge semantics.
   - Four metric families and surfaces.
   - Experiment `travel_network@1` (off-gate).
   - Pins: runner v4/v55/v56, result v2/v3, 43 commands, 73 semantics,
     192 metrics, 14 contexts/12 flags/six owned, Alembic 0017, `/v1`,
     `observer-protocol-v1`.
   - Verification receipt.
3. Update `README.md` documentation index.
4. Update `docs/infrastructure-networks.md` with a prominent cross-link and the
   snapshot v2 route rows.
5. Update `docs/v4-architecture.md`:
   - V4-17 deepening section;
   - accepted event 27/codec `v25` only when travel network is active;
   - seven infrastructure GET routes;
   - 192 metrics;
   - reserve 24-26 unchanged.
6. Update `docs/configuration.md` with the activation rule and no v57.
7. Update `docs/persistence.md` with V27/`v25`, checkpoint selection, v21/v19
   compatibility, and Alembic 0017.
8. Update `docs/analysis-metrics.md` with the four appended ids and 192.
9. Update `docs/research-api.md` and `docs/research-ui.md` with the routes route
   and panel section.
10. Update `docs/observer.md` and the Godot docs with route-status styling.
11. Update `.ai-factory/ARCHITECTURE.md`:
    - baseline table through V4-17;
    - V4-17 seam section;
    - owned V4 flags list still six names;
    - no new context/flag;
    - write pair metadata.
12. Update `.ai-factory/DESCRIPTION.md` with the shipped state. Do **not** edit
    `.ai-factory/ROADMAP.md`; `$aif-roadmap` owns it.
13. Add a negative docs parity assertion: stale phrases such as
    “six GET routes”, “188 metric families”, “route network is unowned/absent”,
    and “no travel network” must not appear in the current contract pages after
    the update. Positive presence checks alone are not sufficient.

### Required Interfaces and Contracts

- Documentation must not claim a route score, civilization score, omniscient
  planner, new capability flag, or v57.
- Every numeric pin must match code/tests.
- The travel page must state that stale/incorrect beliefs are legal and never
  authoritative.
- The page must state that route condition is objective and derived from
  already-authoritative facts.

### Requirement Evidence

- `docs/travel-network.md`; `.ai-factory/ARCHITECTURE.md` baseline; index settings/docs rows.

### Error Handling and Logging

- `INFO docs_travel_network_written path=docs/travel-network.md`.
- Missing cross-links are a documentation failure, not a warning.
- No route/owner payloads in docs examples beyond safe ids.

### Tests

- Documentation pin sweep in `tests/unit/test_travel_network_docs.py` (create if
  the infrastructure docs test pattern requires it):
  - `docs/travel-network.md` exists and mentions the exact pins;
  - README links it;
  - architecture/configuration/persistence/metrics/API/UI/observer pages
    mention 27/`v25`, 192, seven routes, and activation;
  - no page claims a route score or new flag;
  - negative parity: stale “six GET routes”, “188 metric families”, and
    “travel network unowned/absent” phrases are absent.
- `uv run pytest tests/unit/test_travel_network_docs.py tests/unit/test_infrastructure_docs.py -q`

### Acceptance Criteria

- The new page and all cross-links land.
- Pins are consistent across docs, code, and tests.
- Roadmap remains untouched.

### Verification

- `uv run pytest tests/unit/test_travel_network_docs.py tests/unit/test_infrastructure_docs.py -q`
- `git status --short .ai-factory/ROADMAP.md` must show no V4-17 edit from this
  plan.

## Task 25: Required-gate verification certification

### Intent

Execute the full required-gate strategy and record a truthful certification:
pass, fail, or `unexecuted` with the exact missing prerequisite. No lane may be
silently skipped.

### Implementation Steps

1. Run the full Python unit and architecture lanes with coverage enabled **after
   the final code/docs edits**, not from an intermediate state:
   `uv run pytest tests/unit tests/architecture --cov=src --cov-report=term-missing -q`.
   A focused selection is not sufficient for certification.
2. Run the exact documented static gates:
   `uv run ruff check src tests`,
   `uv run mypy src tests`,
   `uv run lint-imports`.
3. Run non-scale integration:
   `uv run pytest tests/integration -m "not scale" -q`; if PostgreSQL is
   unavailable, record `unexecuted` with `prerequisite=postgresql`.
4. Run Compose config/build/browser gates per `docs/development.md`; record
   `unexecuted` with the exact missing prerequisite if the environment lacks it.
5. Run the pinned Godot suite; record `failed=0` or `unexecuted` with the exact
   Godot version/export prerequisite.
6. Run Research UI install/test/check per `docs/development.md`.
7. Run benchmark/scale regression if the hardware/DB prerequisites exist; record
   `unexecuted` with the exact prerequisite otherwise.
8. Record the receipt in `index.md` or a linked verification section:
   - command, lane, result, duration, and prerequisite for `unexecuted`;
   - no fabricated green status.
9. Update `index.md` Task 25 checkbox only after the receipt is complete.
10. Do not commit, push, or edit the roadmap.

### Required Interfaces and Contracts

- Coverage enabled for Python lanes.
- Static gates green or explicitly `unexecuted`.
- Compose/browser, Godot, integration, and benchmark lanes are either green or
  explicitly `unexecuted` with a prerequisite.
- No secrets, DSNs, prompts, bodies, or payloads in the receipt.

### Requirement Evidence

- index Settings full test strategy; `docs/development.md` commands; index env-gated lane row.

### Error Handling and Logging

- Failures are recorded verbatim as safe codes, not hidden.
- `INFO verification_lane lane=<name> result=<pass|fail|unexecuted>`.
- `ERROR verification_blocked lane=<name> reason_code=<code>` only for a failed
  required gate.

### Tests

- The verification lanes themselves are the test; no new synthetic test task.
- Re-run focused regressions if a lane fails and a fix is made.

### Acceptance Criteria

- The receipt is complete and truthful.
- Every required gate is green or explicitly `unexecuted` with a prerequisite.
- No commit, push, roadmap edit, or branch creation occurs.

### Verification

- The receipt lists the exact commands and outcomes.
- `git status` shows only intended plan/docs/code changes; no roadmap edit.

## Phase Risks and Mitigations

- Risk: documentation pins drift from code.
  Mitigation: docs pin sweep plus architecture pin sweep.
- Risk: env-gated lanes are reported as green without execution.
  Mitigation: explicit `unexecuted` + prerequisite is mandatory.
- Risk: the plan accidentally edits the roadmap.
  Mitigation: `git status` check in Task 24/25.

## Phase Completion Checklist

- Every task above satisfies its acceptance criteria.
- `index.md` checkboxes for Tasks 24-25 are updated after verification.
- No phase file contains task checkboxes.
