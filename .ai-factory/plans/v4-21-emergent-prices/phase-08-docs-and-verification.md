# Phase 8: Documentation and Verification

Plan: [index.md](index.md)
Tasks: 23-25
Depends on: Phase 7 / Task 22

## Objective

Document the feature through the mandatory `$aif-docs` checkpoint, add positive
and negative documentation parity checks, and certify the required gates with an
explicit receipt. The roadmap is not edited; V4-21 registration remains with
`$aif-roadmap`.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `docs/trade-networks.md` | page structure, pins 191 | Closest analytical-network doc template |
| `docs/market-like-institutions.md` | page structure, pins 159/193 | Direct V4-20 predecessor doc |
| `docs/analysis-metrics.md` | 41, 741-750 | Metric catalog page and market section |
| `docs/architecture.md` | 568, 662, 714, 733, 821 | Seam sections and downstream checklist |
| `docs/configuration.md` | V4 settings/versions | Settings and activation docs |
| `docs/research-api.md` | route tables | GET route documentation |
| `README.md` | documentation index | Landing-page link |
| `tests/unit/test_market_institutions_docs.py` | 84-118 | Positive/negative doc parity pattern |
| `tests/unit/test_trade_networks_docs.py` | 75-81 | Catalog pin doc test |
| `.ai-factory/ARCHITECTURE.md` | 184, 1098-1117 | Baseline table and seam section |
| `.ai-factory/DESCRIPTION.md` | 620-640 | Current feature summary |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `docs/emergent-prices.md` | create | Full feature page |
| `README.md` | modify | Add documentation index entry |
| `docs/architecture.md` | modify | V4-21 seam and boundaries |
| `docs/configuration.md` | modify | Activation, settings, experiment |
| `docs/analysis-metrics.md` | modify | Four families and 212 catalog |
| `docs/research-api.md` | modify | Seven GET routes |
| `docs/market-like-institutions.md` | modify | Cross-link V4-21 and state that prices are separate expectations, not V4-20 venue status |
| `.ai-factory/ARCHITECTURE.md` | modify | V4-21 seam section and baseline table |
| `.ai-factory/DESCRIPTION.md` | modify | V4-21 summary paragraph |
| `tests/unit/test_emergent_prices_docs.py` | create | Positive/negative parity |

## Task 23: Documentation via `$aif-docs`

### Intent

Run the mandatory documentation checkpoint and write the complete, bounded
feature documentation with no claim of a canonical price.

### Implementation Steps

1. Invoke `$aif-docs` for V4-21 and use the resolved `paths.docs` directory.
2. Create `docs/emergent-prices.md` with these sections:
   - purpose and non-goals (no global price table, no money, no credit/debt, no
     planner/quota/allocation);
   - activation: `markets_credit` **and** `subjective_valuation`; V3-19
     `resource_exchange_profile` as the medium/acceptance evidence seam;
   - owner ledger: rows, unit sources, expectation, confidence formula, caps,
     notices, carry/checkpoints;
   - `prc_v1` frames: acts, nine fields, one relation maximum, malformed
     handling;
   - analysis: paired evidence, pairing classes, completed and quoted
     distributions kept separate, five bin shares, market distributions,
     convergence/divergence overlap, four layers, caps;
   - metrics: four family ids and value keys;
   - snapshot/store/routes/settings: exact tokens, purposes, limits, error codes;
   - experiment `emergent_prices@1` and the off-gate statement;
   - what the feature does **not** do: no command-producing path, no exchange
     admission change, no Godot overlay, no canonical price.
3. Update `README.md` documentation index with the new page.
4. `docs/architecture.md`: add a V4-21 seam section after V4-20 describing owner
   authority, detached analysis, and the unchanged pins.
5. `docs/configuration.md`: document activation preconditions, both env vars, the
   experiment, and that no runner schema/root/per-agent key is added.
6. `docs/analysis-metrics.md`: add the four families and update the catalog to
   **212**; state that distributions are descriptive and no single price exists.
7. `docs/research-api.md`: add the seven GET routes, dual gate, cursor binding,
   and error codes.
8. `.ai-factory/ARCHITECTURE.md`: add the V4-21 seam under V4-20 and update the
   baseline table to 212 while preserving historical counts.
9. `docs/market-like-institutions.md`: add a short “Emergent prices (V4-21)”
   cross-link stating that price expectations and distributions are a separate
   deepening of the same `markets_credit` context, do not change venue status,
   and never publish a canonical price.
10. `.ai-factory/DESCRIPTION.md`: add the V4-21 paragraph after V4-20, naming
    `markets_credit`, `prc_v1`, four families (208 → 212), snapshot/store tokens,
    seven routes, and the off-gate experiment.
11. Register V4-21 in `.ai-factory/ROADMAP.md` M8 alongside V4-17 through V4-20,
    and record that eight V4 flags are owned and four remain unowned.

### Required Interfaces and Contracts

- Human-readable text is English; technical terms preserved.
- No doc says "the price of X is Y" or implies a canonical market price.
- Route/setting/token literals match code exactly.
- The page states explicitly that expectations never alter exchange admission.

### Requirement Evidence

- Docs policy: plan settings (`Docs: yes`, mandatory `$aif-docs`).
- `.ai-factory/ARCHITECTURE.md` requirement 7; roadmap ownership boundary.

### Error Handling and Logging

- Documentation only; no runtime logging.

### Tests

- `tests/unit/test_emergent_prices_docs.py` is created in Task 24.
- Manual check: `docs/emergent-prices.md` links resolve.

### Acceptance Criteria

- Every required doc page is updated.
- The page answers activation, representation, analysis, and non-goals without
  inventing behavior.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_docs.py -q` (after Task 24)
- Expected: all pass.

## Task 24: Add documentation pin and negative parity checks

### Intent

Prevent docs drift and prevent a future edit from reintroducing canonical-price
language or stale counts.

### Implementation Steps

1. Create `tests/unit/test_emergent_prices_docs.py`:
   - positive: `docs/emergent-prices.md` exists and contains
     `emergent-prices.v1`, `prc_v1`, `emergent-prices-snapshot-v1`,
     `emergent-prices-store-v1`, `PALIMPSEST_EMERGENT_PRICES_ROOT`,
     `PALIMPSEST_EMERGENT_PRICES_CURSOR_KEY`, the four family ids,
     `emergent_prices@1`, `emergent_prices_disabled`, and `212`;
   - positive: `README.md`, `docs/architecture.md`, `docs/configuration.md`,
     `docs/analysis-metrics.md`, `docs/research-api.md`, and
     `docs/market-like-institutions.md` each link/mention the page or the
     feature;
   - negative: no page contains `canonical price`, `global price table`,
     `price index`, `clearing price`, `money object`, `credit limit`, or a
     claim that exchange admission reads expectations, except inside an explicit
     "does not" sentence list;
   - negative: no stale current-state `208 metric families` or
     `catalog 208` outside historical sections;
   - negative: no `runner-config-v57`, no `0018`, no `/v2` route mention.
2. Update the shared docs pin helper used by existing docs tests to expect 212.
3. Keep historical archive/plan counts untouched.

### Required Interfaces and Contracts

- Negative checks allow explicitly negated statements ("no canonical price")
  and reject only affirmative claims.
- The test reads only the named docs, never the whole repository.

### Requirement Evidence

- Existing docs parity pattern: `tests/unit/test_market_institutions_docs.py:84-118`,
  `tests/unit/test_trade_networks_docs.py:75-81`.

### Error Handling and Logging

- Assertion messages name the offending file and token.

### Tests

- `uv run pytest tests/unit/test_emergent_prices_docs.py -q`

### Acceptance Criteria

- Docs pins and parity pass.
- A stale count or canonical-price claim fails the test.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_docs.py -q`
- Expected: all pass.

## Task 25: Required-gate verification certification

### Intent

Run the full required gate matrix and record a truthful receipt, marking
env-gated lanes `unexecuted` rather than green.

### Implementation Steps

1. Run the Python unit + architecture lane with coverage:
   `uv run pytest tests/unit tests/architecture -q --cov=src --cov-report=term`.
2. Run focused price suites:
   `uv run pytest tests/unit/test_emergent_prices_*.py tests/architecture/test_emergent_prices_*.py -q`.
3. Run static gates: `uv run ruff check src tests`, `uv run mypy src tests`,
   `uv run lint-imports`.
4. Run integration non-scale:
   `uv run pytest tests/integration -m "not scale" -q`; run the price store/API
   integration case explicitly.
5. Run Compose config: `docker compose config`.
6. Run Research UI tests and types.
7. Run Godot regression with `${GODOT_BIN}` when available; otherwise record
   `unexecuted` with the missing prerequisite.
8. Run Compose/browser acceptance only when an attested image and headed browser
   harness exist; otherwise `unexecuted`.
9. Run benchmark regression with
   `uv run pytest tests/benchmarks -m "not scale" -q`; run scale lanes only when
   scale hardware and a disposable PostgreSQL are available, otherwise record
   `unexecuted`.
10. Write a `## Verification Receipt` table into `index.md` with command, result,
    and prerequisite/note per lane. Do not skip, xfail, or downgrade a required
    gate to manufacture green.
11. State the roadmap registration: V4-21 is recorded in M8 and V4-17 through
    V4-20 are re-confirmed; eight V4 flags remain owned and four remain unowned.

### Required Interfaces and Contracts

- Coverage stays enabled for Python lanes.
- Env-gated lanes are `unexecuted`, not passed.
- No test or gate is removed.

### Requirement Evidence

- Plan settings: full testing strategy; normal verification with explicit
  complete required-gate certification.
- `docs/development.md` verification commands.

### Error Handling and Logging

- Record exact commands and results; do not paste test payloads or secrets.

### Tests

- The full gate matrix above.

### Acceptance Criteria

- Every required gate is either passing or explicitly `unexecuted` with a
  prerequisite and a remediation note.
- No source requirement artifact is edited during verification.

### Verification

- The receipt itself is the verification artifact; all commands are re-runnable.

## Phase Risks and Mitigations

- Risk: docs drift from code tokens.
  Mitigation: exact literals asserted by parity tests.
- Risk: env-gated lanes look green because they were skipped silently.
  Mitigation: explicit `unexecuted` rows and a no-skip rule.
- Risk: roadmap gets edited out of habit.
  Mitigation: Task 23/25 state the ownership boundary and check `git status`.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass or are explicitly `unexecuted`.
- `index.md` task checkboxes and the Verification Receipt are updated after
  verified completion.
