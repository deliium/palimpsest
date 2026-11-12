# Phase 8: Documentation and Verification

Plan: [index.md](index.md)
Tasks: 21-23
Depends on: Tasks 1-20

## Objective

Document the implemented credit seam through the mandatory `$aif-docs`
checkpoint, pin the documentation against negative parity claims, and certify
every required verification lane or record it as explicitly `unexecuted` with
its prerequisite.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `docs/emergent-prices.md` | headings 1-223 | Exact page shape to mirror |
| `docs/market-like-institutions.md` | 211 lines | Adjacent V4-20 page and cross-link |
| `README.md` | feature table 61-62, docs table 109-110 | Exact landing-page rows |
| `.ai-factory/ARCHITECTURE.md` | baseline table 177-193, V4-20/V4-21 seams 1098-1140 | Current pins and seam placement |
| `.ai-factory/DESCRIPTION.md` | V4-20/V4-21 paragraphs 620-662 | Current-state narrative |
| `docs/architecture.md` | V4-21 seam 821-842 | Downstream seam placement |
| `docs/configuration.md` | V4-20/V4-21 settings 560-583 | Settings documentation |
| `docs/analysis-metrics.md` | catalog and family sections 1-761 | Metric documentation |
| `docs/research-api.md` | routes 408-451 | Route documentation |
| `tests/unit/test_emergent_prices_docs.py` | docs parity pattern | Exact positive/negative parity test |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `docs/credit-relationships.md` | create | Full feature page |
| `README.md` | modify | Feature and documentation rows; V4-22 mention |
| `.ai-factory/ARCHITECTURE.md` | modify | Pin table 216 and `V4-22 credit-relationship seam` |
| `.ai-factory/DESCRIPTION.md` | modify | V4-22 paragraph |
| `docs/architecture.md` | modify | V4-22 seam section |
| `docs/configuration.md` | modify | `Credit relationships (V4-22)` settings section |
| `docs/analysis-metrics.md` | modify | Four families and catalog 216 |
| `docs/research-api.md` | modify | Seven credit routes |
| `docs/emergent-prices.md` | modify | See-also cross-link to credit |
| `docs/market-like-institutions.md` | modify | See-also cross-link to credit |
| `tests/unit/test_credit_relationships_docs.py` | create | Positive and negative docs parity |

## Task 21: Documentation via aif-docs

### Intent

Record the implemented V4-22 seam at the same depth as V4-20 and V4-21, without
claiming a bank, money, enforceable debt, credit score, or canonical credit.

### Implementation Steps

1. Run the mandatory `$aif-docs` checkpoint for this plan. Treat this task as
   the docs owner; do not edit the roadmap.
2. Create `docs/credit-relationships.md` with these exact headings and content:
   - `# Credit relationships`
   - `## Overview` — owner-scoped beliefs about receive-now/repay-later terms;
     V4-22 deepens `markets_credit`; no bank.
   - `## Non-goals` — no bank, deposit, reserve, loan officer, interest rate,
     money, currency, legal tender, enforceable debt, collection, credit score,
     ranking, allocation, quota, global credit registry, or canonical credit.
   - `## Activation` — `markets_credit` plus V3-17 `structured_commitments`;
     V4-21 price expectations optional; every other combination disabled.
   - `## Owner ledger` — direction, terms, statuses, revisions, willingness,
     confidence, levels, caps, notices.
   - `## crd_v1 frames` — 16 parts, 320 characters, one relation per
     `Talk`/`Tell`, malformed/oversize drop.
   - `## Acts` — propose, accept, decline, repay, default, renegotiate,
     forgive, dispute, withdraw; all are declarations, never enforcement.
   - `## Analysis` — committed claims, `Given` transfers, performances,
     repayment distributions, counterparties, researcher-only alignment,
     coverage and truncation.
   - `## Metrics` — the four families and exact current count 216.
   - `## Snapshot, store, and routes` — `credit-relationships-snapshot-v1`,
     `credit-relationships-store-v1`, seven GET-only routes, dual-gated
     `SUBJECTIVE_DEBUG`, settings names.
   - `## Experiment` — `credit_relationships@1`, four arms, off the V1 gate.
   - `## What this feature does not do` — no command, event, schema, migration,
     Godot overlay, or global registry.
   - `## See also` — market-like institutions, emergent prices, configuration,
     analysis metrics, research API.
3. Update `README.md`:
   - feature table row: `Credit relationships | docs/credit-relationships.md |
     V4-22 owner-scoped credit terms, crd_v1 claims, repayment performance,
     researcher-only alignment, snapshot/store and seven GET routes`;
   - documentation table row with the same link and a concise description.
4. Update `.ai-factory/ARCHITECTURE.md`:
   - baseline table metric families `216` with the V4-22 append;
   - add `### V4-22 credit-relationship seam` after the V4-21 seam:
     activation, ledger, frames, no command, analysis, four families, snapshot/
     store/routes, no bank/enforcement, pins;
   - keep ownership at eight owned / four unowned and `markets_credit` owned.
5. Update `.ai-factory/DESCRIPTION.md` with one V4-22 paragraph after V4-21:
   activation, terms, acts, trust/expectation dependence, no bank, four
   families 212 -> 216, snapshot/store/seven routes, Research UI panel, no Godot
   overlay, off-gate experiment.
6. Update `docs/architecture.md` with the same V4-22 seam and downstream
   boundary notes.
7. Update `docs/configuration.md` with `### Credit relationships (V4-22)`:
   model activation, `PALIMPSEST_CREDIT_RELATIONSHIPS_ROOT`,
   `PALIMPSEST_CREDIT_RELATIONSHIPS_CURSOR_KEY` (>=32 UTF-8 bytes), disabled
   behavior, and no runner key.
8. Update `docs/analysis-metrics.md`: four new families, exact keys, catalog
   216, and the first-212 preservation rule.
9. Update `docs/research-api.md`: seven GET-only routes, capability, response
   families, failure codes, cursors, default/max limits, window range.
10. Add cross-links in `docs/emergent-prices.md` and
    `docs/market-like-institutions.md` See-also sections.
11. Keep `.ai-factory/ROADMAP.md` out of this docs task; `$aif-roadmap`
    owns V4-22 registration as a separate follow-up (completed after
    verification).

### Required Interfaces and Contracts

- Documentation tokens:
  `credit-relationships.v1`, `crd_v1`, `credit-relationships-snapshot-v1`,
  `credit-relationships-store-v1`, `credit_relationships@1`,
  216 metric families.
- No document claims a bank, money, interest, enforceable debt, credit score, or
  canonical credit.
- Every route/settings token in docs matches code exactly.

### Requirement Evidence

- V4-21 page and seam:
  `docs/emergent-prices.md`, `.ai-factory/ARCHITECTURE.md:1116-1140`.
- Docs checkpoint policy: plan `Settings` (`Docs: yes`) and skill-context.
- Roadmap ownership: `.ai-factory/ARCHITECTURE.md` "Requirements for later
  changes" 7.

### Error Handling and Logging

- Documentation-only task; no runtime logging changes.
- If `$aif-docs` cannot run, record the exact reason and treat the docs task as
  incomplete rather than silently substituting prose.

### Tests

- `uv run pytest tests/unit/test_credit_relationships_docs.py -q` after Task 22.
- Manual review: every code token in docs exists in code and vice versa.

### Acceptance Criteria

- Every listed document contains the V4-22 seam and the 216 pin.
- The new page covers activation, ledger, frames, acts, analysis, metrics,
  snapshot/store/routes, experiment, non-goals, and cross-links.
- No document claims a bank, money, enforceable debt, credit score, or canonical
  credit.

### Verification

- `uv run pytest tests/unit/test_credit_relationships_docs.py -q`
- `rg -n "credit_relationships|credit-relationships|crd_v1|216" README.md docs .ai-factory/DESCRIPTION.md .ai-factory/ARCHITECTURE.md`
- Expected: every listed file present; no forbidden claim.

## Task 22: Add documentation pin and negative parity checks

### Intent

Make documentation drift and forbidden-claim drift fail in CI, not in review.

### Implementation Steps

1. Create `tests/unit/test_credit_relationships_docs.py`:
   - assert `docs/credit-relationships.md` exists and contains every required
     heading;
   - assert README, ARCHITECTURE, DESCRIPTION, `docs/architecture.md`,
     `docs/configuration.md`, `docs/analysis-metrics.md`,
     `docs/research-api.md`, `docs/emergent-prices.md`, and
     `docs/market-like-institutions.md` mention V4-22 or credit relationships;
   - assert active docs say 216 and do not say `METRIC_FAMILY_COUNT` 212;
   - assert exact tokens `credit-relationships.v1`, `crd_v1`,
     `credit-relationships-snapshot-v1`, `credit-relationships-store-v1`,
     `credit_relationships@1`;
   - assert seven route suffixes appear in `docs/research-api.md`;
   - assert both settings names appear in `docs/configuration.md`;
   - negative parity: assert no affirmative `"bank account"`, `"interest
     rate"`, `"credit score"`, `"enforceable debt"`, `"canonical credit"`, or
     `"money"` feature claim appears; negated `Non-goals` sentences such as
     "no bank", "no money", or "no enforceable debt" are allowed;
   - assert no `runner-config-v57`, `0018`, `/v2`, or `observer-protocol-v2`.
2. Add a positive/negative pair for the experiment: `credit_relationships@1`
   is listed as off-gate and is absent from the V1 A-E gate list.
3. Add a token-parity scan comparing docs tokens against code constants; fail on
   a token present in one and absent in the other.
4. Ensure historical `(208 -> 212)` strings are not flagged as active pins.

### Required Interfaces and Contracts

- Positive parity: documented tokens, routes, settings, counts, and experiment
  exist in code.
- Negative parity: forbidden claims, schema bumps, `/v2`, and protocol bumps
  fail.
- The test reads docs only; it never imports a live service.

### Requirement Evidence

- Docs parity precedent: `tests/unit/test_emergent_prices_docs.py`.
- No-schema-bump rule: `.ai-factory/ARCHITECTURE.md` "Requirements for later
  changes" 1.
- Roadmap ownership: `.ai-factory/ARCHITECTURE.md` requirement 7.

### Error Handling and Logging

- Test-only; assertion messages name the document and token only.
- No payload, owner token, or anchor is printed.

### Tests

- `tests/unit/test_credit_relationships_docs.py`

### Acceptance Criteria

- A missing page, missing route, stale 212 pin, or forbidden feature claim fails
  the test.
- A correct V4-22 docs set passes.
- Historical counts do not cause false failures.

### Verification

- `uv run pytest tests/unit/test_credit_relationships_docs.py -q`
- Expected: all pass.

## Task 23: Required-gate verification certification

### Intent

Run the complete required verification strategy and leave an explicit receipt.
Any env-gated lane without its prerequisite is `unexecuted`, never green.

### Implementation Steps

1. Run the Python unit and architecture lanes with coverage:
   - `uv run pytest tests/unit tests/architecture -q`
   - `uv run pytest tests/unit tests/architecture -q --cov=src --cov-report=term`
2. Run the focused credit suites with coverage:
   - `uv run pytest tests/unit/test_credit_relationships_*.py tests/architecture/test_credit_relationships_*.py -q --cov=src --cov-report=term`
3. Run static gates:
   - `uv run ruff check src tests`
   - `uv run mypy src tests`
   - `uv run lint-imports`
4. Run integration lanes:
   - `uv run pytest tests/integration -m "not scale" -q`
   - `uv run pytest tests/integration/test_credit_relationships_store_api.py -q -m integration`
5. Run Compose configuration:
   - `docker compose config`
6. Run Research UI lanes:
   - `cd clients/research-ui && ./node_modules/.bin/vitest run`
   - `cd clients/research-ui && ./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json`
7. Run the existing Godot regression suites only when `GODOT_BIN` or `godot` is
   installed; record `unexecuted` with the missing prerequisite otherwise.
8. Run Compose/browser acceptance only with an attested image and headed
   harness; record `unexecuted` with the missing prerequisite otherwise.
9. Run benchmark regression:
   - `uv run pytest tests/benchmarks -m "not scale" -q`
   - Record `unexecuted` if scale hardware or disposable PostgreSQL is absent.
10. Write the verification receipt into `index.md` with the exact command,
    result count, and prerequisite note for every lane.
11. Confirm `git status` shows the roadmap change limited to the V4-22
    registration and V4-17 through V4-21 re-confirmation, no
    `alembic/versions/0018*`, no `clients/godot-observer/` source change, and
    only the expected V4-22 paths.

### Required Interfaces and Contracts

- Required lanes: unit, architecture, determinism, integration, Compose/browser,
  Godot regression (existing suites only), Research UI, benchmark regression,
  static gates, and coverage for Python lanes.
- A lane without its prerequisite is `unexecuted`, not `pass`.
- The receipt is the only source of certification truth.

### Requirement Evidence

- V4-21 verification receipt structure:
  `.ai-factory/plans/v4-21-emergent-prices/index.md` "Verification Receipt".
- Testing policy: plan `Settings` (`Testing: yes`; full strategy).
- Gate discipline: `.ai-factory/ARCHITECTURE.md` "Requirements for later
  changes" 3.

### Error Handling and Logging

- Test commands only. Do not change production logging to make a gate pass.
- If a gate fails, fix the implementation or report the exact failure; never
  mark it green.

### Tests

- All commands in the steps above.

### Acceptance Criteria

- Every required lane is `pass` or `unexecuted` with a prerequisite.
- No lane is claimed without a command and result.
- The focused credit suite passes with coverage enabled.
- `git status` confirms the roadmap change is limited to V4-22 registration and
  the Godot source tree is untouched.

### Verification

- `git status --porcelain`
- `git diff --stat`
- Expected: only V4-22 implementation, tests, docs, and the roadmap
  registration paths; no migration or Godot source change.

## Phase Risks and Mitigations

- Risk: docs describe an unimplemented token.
  Mitigation: Task 22 token parity against code constants.
- Risk: verification claims green for an unrun env lane.
  Mitigation: explicit `unexecuted` plus prerequisite in the receipt.
- Risk: the roadmap is edited during docs.
  Mitigation: `git status` check and `$aif-roadmap` ownership statement.
- Risk: a docs test rejects a legitimate non-goal sentence.
  Mitigation: allow negated non-goal phrasing and test only affirmative claims.

## Phase Completion Checklist

- Every Task 21-23 in this phase satisfies its acceptance criteria.
- Docs parity and required gates are recorded in `index.md`.
- `index.md` checkboxes are updated only after verified completion.
