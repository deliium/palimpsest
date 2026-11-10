# Phase 8: Documentation and Verification

Plan: [index.md](index.md)
Tasks: 23-25
Depends on: Task 22

## Objective

Document the capability through the mandatory `$aif-docs` checkpoint across all
documentation surfaces, pin it with positive and negative parity tests, and
certify every required gate as green or explicitly `unexecuted` with its
prerequisite. The roadmap stays untouched; `$aif-roadmap` owns registration.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `docs/trade-networks.md` | Overview … Verification, See Also | Page structure to mirror |
| `README.md` | `## Documentation` 52; table 54+; infra 57; travel 58; trade 59 | Index row |
| `.ai-factory/ARCHITECTURE.md` | baseline table 177-193; V4-17 seam 1020-1039; V4-18 seam 1042-1063 | Baseline and seam sections |
| `.ai-factory/DESCRIPTION.md` | V4-17 560-578; V4-18 580-596 | Description history |
| `docs/architecture.md` | headings end at `## V4-16 infrastructure networks` 766 | Project docs architecture page needs the V4-19 seam |
| `docs/configuration.md` | trade dual gate 539-548 | Settings documentation |
| `docs/infrastructure-networks.md` | 41; 149-152 | States infrastructure does not own `supply_chains` |
| `tests/unit/test_trade_networks_docs.py` | 22-162 | Docs parity shape |
| `tests/unit/test_infrastructure_docs.py` | 17-70 | Sibling docs pin |
| `.ai-factory/ROADMAP.md` | M8 118-162 | Owned by `$aif-roadmap` |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `docs/supply-chains.md` | create | Full reference page |
| `README.md` | modify | Documentation index row |
| `.ai-factory/ARCHITECTURE.md` | modify | Baseline pins + V4-19 seam |
| `.ai-factory/DESCRIPTION.md` | modify | V4-19 paragraph + pins |
| `docs/architecture.md` | modify | V4-19 seam section |
| `docs/configuration.md` | modify | Two new settings + dual gate |
| `docs/infrastructure-networks.md` | modify | Point ownership at V4-19 |
| `tests/unit/test_supply_chain_docs.py` | create | Positive/negative parity |
| `tests/unit/test_infrastructure_docs.py` | modify | New ownership assertion |
| `tests/unit/test_supply_chain_pins.py` | modify | Docs pin assertions in Task 24 |

## Task 23: Documentation via `$aif-docs`

### Intent

Land one authoritative page plus every baseline/configuration surface that
downstream skills and researchers read, using the project's docs command.

### Implementation Steps

1. Invoke `$aif-docs` with scope: `docs/supply-chains.md`, `README.md`,
   `.ai-factory/ARCHITECTURE.md`, `.ai-factory/DESCRIPTION.md`,
   `docs/architecture.md`, `docs/configuration.md`,
   `docs/infrastructure-networks.md`.
2. `docs/supply-chains.md` sections, in order:
   `# Supply Chains`, `## Overview`, `## Mechanics` (chain catalog, tool
   probability bonus, local stage readiness, organization composition),
   `## Non-goals` (no central planner, quota, automatic allocation, price,
   money, optimization, Godot overlay), `## Chain recipe set` (the six locked
   recipes), `## Dependency dimensions` (resources, skills, tools, locations,
   infrastructure, organizations and the ten edge kinds), `## Derivation`
   (events, pairing, window, chains, lineage), `### Bottlenecks` (seven kinds and
   thresholds), `## Bounds and coverage`, `## Read-only surfaces` (seven routes,
   `window_index`, error codes), `## Metrics` (six families), `## Configuration`
   (both settings, `runner-config-v56` flag, and that supply_chains adds no
   write pair — 23/`v21` and 27/`v25` come from other channels),
   `## Read-only fields`, `## Verification`, `## See Also`.
3. README: add `| Supply chains | docs/supply-chains.md | Multi-stage production chains, dependency graph, bottlenecks, read-only surfaces |`
   after the trade row.
4. `.ai-factory/ARCHITECTURE.md`: baseline rows metric families `198 → 204`;
   owned V4 flags "six" → "seven (`supply_chains` added by V4-19)"; add
   `### V4-19 supply-chain seam` after V4-18 covering the world contract,
   legacy catalog immutability, engine activation, `analysis.supply_chain_*`,
   `simulation.supply_chain_*`, `experiments.supply_chain_*`,
   `persistence.supply_chain_filesystem`, seven dual-gated routes, no Godot
   overlay, and pins.
5. `.ai-factory/DESCRIPTION.md`: V4-19 paragraph after V4-18 with ownership,
   six recipes, six dimensions/ten edge kinds, seven bottleneck kinds, six
   metric families (198 → 204), snapshot/store versions, seven routes, off-gate
   experiment, and pins (43/73/replay-v27/`v25`/`0017`/`/v1`/
   `observer-protocol-v1`/14/12/seven).
6. `docs/architecture.md`: add a `## V4-19 supply chains` seam section after
   V4-16 (the page currently stops there) describing the same boundaries and
   pointing to `docs/supply-chains.md`.
7. `docs/configuration.md`: add `PALIMPSEST_SUPPLY_CHAINS_ROOT` and
   `PALIMPSEST_SUPPLY_CHAINS_CURSOR_KEY` as a dual gate (≥32 UTF-8 bytes,
   reader attached only when both are set, otherwise 503), and state that
   supply_chains itself activates no write pair.
8. `docs/infrastructure-networks.md`: replace the "Does **not** own
   `supply_chains`" claim with a sentence stating infrastructure supplies
   venue/capacity evidence while V4-19 owns `supply_chains`.
9. Preserve `## Original Request`, `## Research Context` (absent), and
   `## Requirements Reconciliation`; do not edit `ROADMAP.md`.

### Required Interfaces and Contracts

- Documentation states actual pins and never claims a planner, optimizer, price,
  quota, or central allocation.
- Every path, version constant, route, setting, metric id, edge kind, and cap
  matches code.
- The page names `trade-networks.v1` as a sibling, not a dependency.

### Requirement Evidence

- `docs/trade-networks.md` structure; README 52-59; ARCHITECTURE 177-193 and
  1042-1063; DESCRIPTION 580-596; `docs/architecture.md` 766+;
  `docs/configuration.md` 539-548; `test_trade_networks_docs.py`.
- Supported combinations: correct docs, stale count (fails Task 24),
  prohibited claim (fails Task 24).

### Error Handling and Logging

- Documentation emits no runtime logs; the `Docs: yes` checkpoint is mandatory.

### Tests

- No new tests here; Task 24 pins the result.
- Manual check: `grep -n "supply" README.md docs/supply-chains.md` shows the page
  and index row.

### Acceptance Criteria

- All seven documentation files are updated and consistent with code pins.
- No claim implies centralized planning, optimization, price, or quota.
- `ROADMAP.md` is unchanged.

### Verification

- `git status --porcelain .ai-factory/ROADMAP.md` → empty.
- `grep -c "supply-chains.md" README.md` → 1.

## Task 24: Add documentation pin and negative parity checks

### Intent

Prevent documentation drift and prohibited claims from returning.

### Implementation Steps

1. `tests/unit/test_supply_chain_docs.py` asserts:
   - `docs/supply-chains.md` exists and README links it exactly once;
   - all required headings exist in order;
   - the page names the six recipes, six dimensions, ten edge kinds, seven
     bottleneck kinds, six metric ids, seven routes, both settings, and both
     artifact versions;
   - pins appear exactly: `43`, `73`, `204`, `0017`, `14 contexts`,
     `12 flags`, `seven owned`, `EVENT_SCHEMA_REPLAY_V27`, `v25`, `/v1`,
     `observer-protocol-v1`;
   - `.ai-factory/ARCHITECTURE.md` contains a `V4-19 supply-chain seam` heading
     and a `204` baseline row;
   - `docs/architecture.md` contains a `V4-19 supply chains` heading;
   - `docs/configuration.md` names both settings and the dual gate;
   - `.ai-factory/DESCRIPTION.md` contains the V4-19 paragraph tokens.
2. Negative assertions (absent):
   - `runner-config-v57`, `0018`, `/v2`, `observer-protocol-v2`;
   - `planner`, `optimizer`, `price`, `money`, `currency`, `quota`,
     `allocation`, `score`, `rank`, `severity`, `recommendation` as capability
     claims (allowed only inside explicit "no …" non-goal sentences);
   - a claim of a new Godot overlay kind;
   - a claim that supply_chains activates a write pair.
3. `tests/unit/test_infrastructure_docs.py`: expect the V4-19 ownership sentence
   instead of "does not own `supply_chains`"; keep the rest.
4. Extend `tests/unit/test_supply_chain_pins.py` with
   `test_docs_match_metric_catalog` (reads `METRIC_FAMILY_COUNT` and asserts the
   number appears in the page and ARCHITECTURE).

### Required Interfaces and Contracts

- Pins are read from code where possible (`METRIC_FAMILY_COUNT`,
   `SUPPLY_CHAIN_ROUTE_COUNT`, snapshot/store versions,
   `V4_OWNED_CAPABILITY_FLAGS`) and compared to literal documentation tokens.
- Negative checks allow explicit non-goal phrasing only.

### Requirement Evidence

- `test_trade_networks_docs.py` 22-162; `test_infrastructure_docs.py` 17-70.
- Supported combinations: correct docs, stale count, prohibited claim, missing
  README row, missing configuration entry.

### Error Handling and Logging

- Tests only; failures name the stale token and its source of truth.

### Tests

- `uv run pytest tests/unit/test_supply_chain_docs.py tests/unit/test_infrastructure_docs.py tests/unit/test_trade_networks_docs.py tests/unit/test_travel_network_docs.py tests/unit/test_supply_chain_pins.py -q`.

### Acceptance Criteria

- Positive and negative pins pass; mutating a pinned count fails.
- Infrastructure docs no longer claim non-ownership.

### Verification

- `uv run pytest tests/unit/test_supply_chain_docs.py tests/unit/test_infrastructure_docs.py tests/unit/test_trade_networks_docs.py tests/unit/test_travel_network_docs.py tests/unit/test_supply_chain_pins.py -q` → all pass.

## Task 25: Required-gate verification certification

### Intent

Record truthful evidence for every lane. An unavailable lane is `unexecuted`
with its prerequisite, never silently green.

### Implementation Steps

1. Run and record, in order:
   - `uv run pytest tests/unit tests/architecture --cov=src --cov-report=term -q`;
   - `uv run pytest tests/unit/test_supply_chain_*.py tests/architecture/test_supply_chain_*.py -q`;
   - `uv run pytest tests/unit/test_supply_chain_docs.py tests/unit/test_trade_networks_docs.py tests/unit/test_infrastructure_docs.py tests/unit/test_travel_network_docs.py -q`;
   - `uv run ruff check src tests`;
   - `uv run mypy src tests`;
   - `uv run lint-imports`;
   - `uv run pytest tests/integration -m "not scale" -q`;
   - `uv run pytest tests/integration/test_supply_chain_store_api.py -q -m integration`;
   - `docker compose config`;
   - `cd clients/research-ui && npx vitest run`;
   - `cd clients/research-ui && npx svelte-check --tsconfig ./tsconfig.app.json`;
   - Godot: pinned editor + `tests/run_protocol.gd` (existing suites only).
2. Record `unexecuted` with the exact prerequisite for any lane that cannot run
   (Godot editor/export templates; attested image + browser harness; scale
   hardware + disposable PostgreSQL).
3. Confirm `git status --porcelain .ai-factory/ROADMAP.md` is empty and record
   the full changed-file list.
4. Write the Verification Receipt into `index.md` with one row per lane,
   command, result, and prerequisite.
5. Do not commit. Note that `$aif-roadmap` must register V4-17, V4-18, and
   V4-19 in M8 and record the seven-owned count.

### Required Interfaces and Contracts

- Every row is green with exact command/counts, `unexecuted` with prerequisite,
  or failed with the failing test id (failure blocks certification).
- Coverage is enabled for Python lanes.
- The roadmap is never edited.

### Requirement Evidence

- Plan Settings; ARCHITECTURE requirement 7; prior V4-18 receipt format.
- Supported combinations: all local lanes available; env lane missing
  prerequisite; a lane failing.

### Error Handling and Logging

- Certification logs contain commands, counts, and safe codes only.
- Never paste DSNs, tokens, cursor keys, payloads, or secrets.

### Tests

- The certification is the gate; no new tests.

### Acceptance Criteria

- `index.md` contains a complete Verification Receipt.
- No lane is green without its command and result.
- `ROADMAP.md` is untouched and the roadmap follow-up is stated.

### Verification

- Re-run any uncertain lane.
- `git status --porcelain .ai-factory/ROADMAP.md` → empty.

## Phase Risks and Mitigations

- Risk: docs drift after a late code change. Mitigation: pins read from code.
- Risk: an env lane is claimed green without evidence. Mitigation: `unexecuted`
  plus prerequisite is mandatory.
- Risk: roadmap is edited during implementation. Mitigation: explicit
  checkpoint and `git status`.

## Phase Completion Checklist

- Tasks 23-25 satisfy their acceptance criteria.
- Required verification commands pass or are `unexecuted` with prerequisites.
- `index.md` checkboxes and Verification Receipt are updated.
- `ROADMAP.md` is unchanged.
