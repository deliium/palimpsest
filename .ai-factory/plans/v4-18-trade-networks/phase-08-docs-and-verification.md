# Phase 8: Documentation and Verification

Plan: [index.md](index.md)
Tasks: 20-22
Depends on: Phase 7 / Task 19

## Objective

Document the trade-network contract and read-only surfaces, prove documentation
parity and negative claims, then certify every required gate or record it as
explicitly `unexecuted` with a prerequisite.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `docs/infrastructure-networks.md` | full page | Prior V4-16 documentation shape. |
| `docs/travel-network.md` | full page | Prior V4-17 deepening documentation shape. |
| `docs/inter-society-relations.md` | full page | Analysis/snapshot/API/UI documentation shape. |
| `README.md` | documentation index | Landing-page link list. |
| `docs/analysis-metrics.md` | metric catalog sections | Catalog count/append documentation. |
| `docs/research-api.md` | route sections | GET-only route documentation. |
| `docs/research-ui.md` | panel sections | UI surface documentation. |
| `docs/observer.md` | overlay sections | Godot overlay documentation. |
| `docs/configuration.md` | settings sections | Root/cursor settings documentation. |
| `docs/v4-architecture.md` | context table 60-75; 408-420 V4-17 | V4 context and seam documentation. |
| `.ai-factory/ARCHITECTURE.md` | baseline 177-207; seam 1020-1039 | Project architecture pins. |
| `.ai-factory/DESCRIPTION.md` | V4-16/V4-17 paragraphs 541-578 | Project description history. |
| `tests/unit/test_travel_network_docs.py` | 20-76 | Docs pin/negative parity pattern. |
| `tests/unit/test_infrastructure_docs.py` | 17-70 | Docs pin pattern. |
| `docs/development.md` | 545-558 | Pinned Godot and verification commands. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `docs/trade-networks.md` | create | Canonical policy, mechanics, taxonomy, derivation, surfaces, configuration, non-goals, verification. |
| `README.md` | modify | Add the trade-network documentation link. |
| `docs/analysis-metrics.md` | modify | Catalog 198 and six new families with value keys. |
| `docs/research-api.md` | modify | Seven GET-only routes and `trade_networks_disabled`. |
| `docs/research-ui.md` | modify | Read-only trade-network panel. |
| `docs/observer.md` | modify | Trade overlay layers and forbidden fields. |
| `docs/configuration.md` | modify | Root/cursor settings and dual-gate semantics. |
| `docs/v4-architecture.md` | modify | V4-18 deepening row/section and 198 families. |
| `.ai-factory/ARCHITECTURE.md` | modify | Baseline through V4-18, 198 families, V4-18 seam. |
| `.ai-factory/DESCRIPTION.md` | modify | V4-18 paragraph with pins and non-goals. |
| `tests/unit/test_trade_networks_docs.py` | create | Positive and negative documentation parity. |
| `tests/unit/test_infrastructure_docs.py` | modify | Update 192 -> 198 and V4-18 baseline wording. |
| `tests/unit/test_travel_network_docs.py` | modify | Update 192 -> 198 and prior-family wording. |

## Task 20: Documentation via `$aif-docs`

### Intent

Publish one canonical page and update every index/pin page so a researcher can
understand the policy, mechanics, surfaces, and non-goals without reading code.

### Implementation Steps

1. Run the mandatory `$aif-docs` checkpoint and create
   `docs/trade-networks.md` with these exact sections:
   - `# Trade Networks`
   - `## Overview` — sustained individual/organizational exchange, no central
     routing.
   - `## Mechanics` — `NegotiateExchange`, `Give`, artifact transfer, inventory
     carrying, journeys, storage, trade-post capacity; organizations never act.
   - `## Flow taxonomy` — food, materials, tools, records, durable exchange
     media, other; media rule and no-money statement.
   - `## Derivation` — 32-tick window, consecutive locations, corridors,
     dependence, major locations, networks, lineage, cross-society.
   - `## Bounds and coverage` — caps, truncation, `complete`/`partial`/`missing`.
   - `## Read-only surfaces` — snapshot version, store version, seven routes,
     Research UI panel, Godot overlay.
   - `## Configuration` — `PALIMPSEST_TRADE_NETWORKS_ROOT` and
     `PALIMPSEST_TRADE_NETWORKS_CURSOR_KEY` (>=32 UTF-8 bytes), 503 disabled.
   - `## Metrics` — six families, the 192 -> 198 append, sustained counts,
     venue counts, and per-family coverage.
   - `## Read-only fields` — network status/predecessor/successor/sustained,
     cross-society anchors, `trade_post_present`, `cross_location_count`, and
     `window_index` filtering.
   - `## Non-goals` — no planner, quota, allocation, price, money, currency,
     global registry, new flag, new command/event, new write pair, migration, or
     V1-gate membership.
   - `## Verification` — exact commands and env-gated prerequisites.
2. Add the README link under the documentation index.
3. Update `docs/analysis-metrics.md`: count 198; six family ids, algorithm
   versions, value keys, and source `trade_networks_analysis`.
4. Update `docs/research-api.md`: seven GET-only routes, `SUBJECTIVE_DEBUG`,
   cursor TTL, 503 code, 500 corruption code.
5. Update `docs/research-ui.md`: panel sections and disabled/empty behavior.
6. Update `docs/observer.md`: trade overlay layers, presentation-only authority,
   forbidden-field rejection.
7. Update `docs/configuration.md`: settings, validators, enabled flags.
8. Update `docs/v4-architecture.md`: add `V4-18` to the implementation history,
   state that `supply_chains`/`markets_credit` remain unowned, and update the
   catalog to 198.
9. Update `.ai-factory/ARCHITECTURE.md`:
   - heading `### Current baseline through V4-18`;
   - metric row 198;
   - add `### V4-18 trade-network seam` after V4-17 with the policy, no-flag
     posture, event-sourced analysis, snapshot, six families, and pins.
10. Update `.ai-factory/DESCRIPTION.md` with a V4-18 paragraph matching the
    plan's locks. Do not edit `.ai-factory/ROADMAP.md`.
11. Use English; keep technical terms. Do not claim price, money, market score,
    or centralized trade planning.

### Required Interfaces and Contracts

- Documentation is authoritative only for the as-built contract; it may not
  invent behavior.
- Exact stable tokens: `trade-networks.v1`, `trade-networks-snapshot-v1`,
  `trade-networks-store-v1`, `trade_networks@1`, `198`.
- The roadmap remains untouched.
- No source requirement is edited; only documentation and plan-owned artifacts.

### Error Handling and Logging

- Not applicable to docs; `$aif-docs` must report any missing source anchors.

### Tests

- Documentation is validated by Task 21's pin/negative tests; do not mark docs
  complete until those pass.

### Acceptance Criteria

- `docs/trade-networks.md` exists with every required section.
- README, metrics, API, UI, observer, configuration, V4 architecture,
  ARCHITECTURE, and DESCRIPTION are updated.
- The roadmap has no V4-18 edit from this plan.

### Verification

- Manual read-through for accuracy and non-goals.
- `git diff --stat` includes docs and the two architecture/description files;
  `git status --porcelain .ai-factory/ROADMAP.md` is empty.

## Task 21: Add documentation pin and negative parity checks

### Intent

Prevent documentation drift and prevent the new surface from silently claiming a
capability, currency, or central planner it does not have.

### Implementation Steps

1. Create `tests/unit/test_trade_networks_docs.py`:
   - `test_trade_networks_page_exists_and_is_linked_from_readme`
   - `test_required_sections_and_exact_tokens`
   - `test_metric_catalog_is_198_and_six_trade_families_are_documented`
   - `test_seven_routes_and_dual_gate_are_documented`
   - `test_snapshot_store_and_experiment_versions_are_documented`
   - `test_no_new_v4_flag_or_runner_v57_claim`
   - `test_no_central_planner_money_price_or_score_claim`
   - `test_sustained_venue_and_window_filter_are_documented`
   - `test_network_lineage_status_and_society_anchors_are_documented`
   - `test_no_new_command_event_write_pair_or_migration_claim`
   - `test_roadmap_does_not_contain_v4_18_from_this_plan`
2. Pin exact strings: `trade-networks.v1`,
   `trade-networks-snapshot-v1`, `trade-networks-store-v1`,
   `trade_networks@1`, `PALIMPSEST_TRADE_NETWORKS_ROOT`,
   `PALIMPSEST_TRADE_NETWORKS_CURSOR_KEY`, `trade_networks_disabled`,
   `trade_post_present`, `sustained_network_count`, `window_index`, `198`.
3. Negative parity: reject the phrases `new V4 flag`, `runner-config-v57`,
   `money object`, `price index`, `central planner`, `trade score`, `new
   command`, `new event`, and `new write pair` unless they appear in an explicit
   negated sentence (`no ...`, `never ...`, `does not ...`). Use a small
   sentence-level check, not a blunt substring ban that would reject the
   non-goals section.
4. Update `tests/unit/test_infrastructure_docs.py` and
   `tests/unit/test_travel_network_docs.py` from 192 to 198 and from
   "through V4-17" to "through V4-18" where the baseline pin is asserted.
5. Run:
   `uv run pytest tests/unit/test_trade_networks_docs.py tests/unit/test_infrastructure_docs.py tests/unit/test_travel_network_docs.py -q`.

### Required Interfaces and Contracts

- Docs tests parse Markdown text only; no network or filesystem outside the
  repository.
- Negative checks allow negated non-goal sentences.
- The roadmap is asserted untouched by this plan, not by content forever.

### Error Handling and Logging

- Tests fail with the exact missing token/line; do not print whole documents.

### Tests

- The file itself plus the two updated docs suites.

### Acceptance Criteria

- All documentation pins pass.
- Negative parity passes while the non-goals section still states the negations.
- The roadmap is unchanged by this plan.

### Verification

- `uv run pytest tests/unit/test_trade_networks_docs.py tests/unit/test_infrastructure_docs.py tests/unit/test_travel_network_docs.py -q`
- Expected result: all tests pass.

## Task 22: Required-gate verification certification

### Intent

Produce one truthful receipt. Every required lane is either green with its exact
command or explicitly `unexecuted` with a prerequisite; no silent green claim.

### Implementation Steps

1. Run and record the Python lanes with coverage:
   - `uv run pytest tests/unit tests/architecture --cov=src --cov-report=term -q`
   - `uv run pytest tests/unit/test_trade_networks_*.py -q`
2. Run static lanes:
   - `uv run ruff check src tests`
   - `uv run mypy src tests`
   - `uv run lint-imports`
3. Run integration:
   - `uv run pytest tests/integration -m "not scale" -q`
   - `uv run pytest tests/integration/test_trade_networks_store_api.py -q`
   - PostgreSQL-marked variants only when a disposable `palimpsest_test`
     database is available; otherwise record `skipped`/`unexecuted` with the
     prerequisite.
4. Run Compose configuration:
   - `docker compose config` (exit code only; no secrets in output).
5. Run Research UI:
   - `cd clients/research-ui && npx vitest run`
   - `cd clients/research-ui && npx svelte-check --tsconfig ./tsconfig.app.json`
6. Run the pinned Godot suite when the binary/export templates exist:
   - `"${GODOT_BIN}" --headless --editor --path clients/godot-observer --quit`
   - `"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd`
   - Otherwise record `unexecuted` with the exact prerequisite.
7. Run Compose/browser acceptance only when the image/browser harness is
   attested; otherwise record `unexecuted` with the prerequisite.
8. Run benchmark/scale regression only when scale hardware/database is
   available; otherwise record `unexecuted` with the prerequisite.
9. Run `/aif-docs` completion checks and the docs suite from Task 21.
10. Add or update the `## Verification Receipt` table in `index.md` with lane,
    exact command, result, and prerequisite for every non-green lane.
11. Verify `git status --porcelain` shows the roadmap untouched and no commit
    was created by this plan. Do not commit unless the user explicitly asks.

### Required Interfaces and Contracts

- Coverage stays enabled for Python lanes.
- Env-gated lanes never claim green without execution.
- No secrets, payloads, person sets, or DSNs in the receipt.
- The receipt distinguishes focused suites from full lanes.

### Error Handling and Logging

- A failed lane is recorded as failed, not converted to `unexecuted`.
- A missing binary/image/database is recorded with the exact prerequisite.

### Tests

- The receipt itself is the deliverable; no new test file.
- The full command set above is authoritative.

### Acceptance Criteria

- Every required lane is green or explicitly `unexecuted` with a prerequisite.
- Unit+architecture coverage is recorded.
- The roadmap is untouched and no commit/push/branch/worktree operation occurs.

### Verification

- Execute every command above that the environment supports.
- Expected result: receipt is complete and truthful; focused suites green.

## Phase Risks and Mitigations

- Risk: docs claim a new flag or write pair because the plan is large.
  Mitigation: negative parity tests and exact non-goals.
- Risk: env-gated lanes are assumed green.
  Mitigation: explicit `unexecuted` rows with prerequisites.
- Risk: the receipt drifts from the code after a late edit.
  Mitigation: run the receipt after the final code/docs edit and note the order.

## Phase Completion Checklist

- Every Task 20-22 acceptance criterion is satisfied.
- Required verification commands pass or are explicitly `unexecuted`.
- `index.md` task checkboxes are updated immediately after verified completion.
- The roadmap remains untouched.
