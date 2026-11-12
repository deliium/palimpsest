# Phase 8: Documentation and Verification

Plan: [index.md](index.md)
Tasks: 21-23
Depends on: Phase 7 / Task 20

## Objective

Document the seam through the mandatory `$aif-docs` checkpoint, add positive and
negative documentation parity checks, and certify every required verification
lane explicitly or as `unexecuted` with its prerequisite.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `docs/credit-relationships.md` | feature page | Page template (sections, tokens, non-goals). |
| `docs/architecture.md` | V4-22 narrative 845-859; current pin 861 | Architecture narrative and pin. |
| `docs/configuration.md` | V4-22 activation 585-596; pin 598 | Settings documentation. |
| `docs/analysis-metrics.md` | cardinality 41; V4-22 section 750-761; pin 774 | Metric documentation. |
| `docs/research-api.md` | seven routes 451-462; error codes 464-470; pin 474 | API documentation. |
| `docs/v4-architecture.md` | catalog table 268; pin 455-458 | V4 context documentation. |
| `docs/cognition-runtime.md` | durable records 241-245 | Seam the feature extends. |
| `docs/organizations.md`, `docs/evidence-testimony.md`, `docs/credit-relationships.md` | feature pages | Cross-links. |
| `README.md` | documentation index | Landing-page entry. |
| `.ai-factory/ARCHITECTURE.md` | metric table 184; V4-22 section 1160 | Project architecture record. |
| `.ai-factory/DESCRIPTION.md` | V4-22 676-683 | Project description record. |
| `tests/unit/test_credit_relationships_docs.py` | 20-182 | Docs parity template. |
| `tests/unit/test_market_institutions_docs.py` | 66-101 | Pin token template. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `docs/accounting-ledgers.md` | create | Full feature page. |
| `README.md` | modify | Documentation index entry. |
| `docs/architecture.md` | modify | V4-23 seam narrative and current pin. |
| `docs/configuration.md` | modify | Activation and settings. |
| `docs/analysis-metrics.md` | modify | Four families and cardinality 220. |
| `docs/research-api.md` | modify | Seven routes, codes, pin. |
| `docs/v4-architecture.md` | modify | Context table/pin reference. |
| `docs/cognition-runtime.md` | modify | Cross-link from durable records. |
| `docs/organizations.md`, `docs/evidence-testimony.md`, `docs/credit-relationships.md` | modify | Cross-links. |
| `.ai-factory/ARCHITECTURE.md` | modify | V4-23 seam section, metric table 220. |
| `.ai-factory/DESCRIPTION.md` | modify | V4-23 paragraph and pins. |
| `tests/unit/test_accounting_ledgers_docs.py` | create | Positive and negative parity. |

---

## Task 21: Documentation via aif-docs

### Intent

Produce the durable, contributor-facing record of the accounting seam, including
the belief-vs-truth boundary, the five record kinds, the six record assessments,
the evidence bridge, the analysis semantics, the artifact/store/routes, and the
non-goals.

### Implementation Steps

1. Invoke the mandatory `$aif-docs` checkpoint. It owns README structure and the
   docs directory layout; do not hand-write around it.
2. Create `docs/accounting-ledgers.md` with these sections:
   - **What an accounting ledger is** — owner-scoped interpretation of external
     records; a belief, not a book of record.
   - **Activation** — `organizations` + `durable_records`; optional
     `structured_commitments`, `subjective_valuation`, `evidence_testimony`,
     `collective_projects`.
   - **Record kinds** — `exchange`, `debt`, `inventory`,
     `organizational_resource`, `contribution`, with one example each.
   - **Record assessments** — `unassessed`, `consistent`, `contradicted`,
     `outdated`, `suspected_fraudulent`, `damaged`; explicitly state that
     `consistent` does not mean true and `suspected_fraudulent` does not mean
     proven fraud.
   - **External artifacts** — `acc_v1` relation grammar inside existing
     `Inscribe`/`Amend`/`CopyRecord`; no new genre, kind, or event.
   - **Speech** — `acc_v1` inside existing `Talk`/`Tell`; six acts; one relation.
   - **Evidence use** — the pure candidate bridge into `evidence_testimony`;
     never an automatic write.
   - **Analysis** — committed events only; four families; descriptive counts;
     no balance, solvency, or truth.
   - **Artifact and read surface** — snapshot v1, store v1, seven GET routes,
     both settings, fail-closed codes.
   - **Non-goals** — no double-entry engine, no objective ledger, no tax, no
     audit oracle, no global registry, no Godot overlay. Include the exact
     sentence `No money, currency, interest, bank, or credit score exists.` so
     the parity test can assert it verbatim.
   - **Pins** — 220 families, 43 commands, 73 observer semantic types,
     replay-v27/codec `v25`, Alembic `0017`, `/v1`, `observer-protocol-v1`.
3. Update:
   - `docs/architecture.md` — V4-23 seam narrative and current pin;
   - `docs/configuration.md` — activation truth table and both settings;
   - `docs/analysis-metrics.md` — four family descriptions and cardinality 220;
   - `docs/research-api.md` — seven routes, error codes, pagination;
   - `docs/v4-architecture.md` — context table reference and pin;
   - `docs/cognition-runtime.md` — one cross-link sentence from durable records;
   - `docs/organizations.md`, `docs/evidence-testimony.md`,
     `docs/credit-relationships.md` — cross-links.
4. Update `.ai-factory/ARCHITECTURE.md` with a "V4-23 accounting-ledger seam"
   section and change the metric table to 220; update
   `.ai-factory/DESCRIPTION.md` with a V4-23 paragraph and pins.
5. Add a README documentation-index entry pointing at
   `docs/accounting-ledgers.md`.

### Required Interfaces and Contracts

- English prose; technical terms preserved.
- No claim that accounting content is truth.
- No claim of a new V4 flag, context, command, event, observer semantic, write
  pair, migration, `/v2` route, or Godot overlay.
- Every count matches the executable catalog.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` "Requirements for later changes" 7 — roadmap and
  documentation ownership.
- Original Request bullets.

### Error Handling and Logging

- Not applicable.

### Tests

Documentation is verified in Task 22; Task 21 completes when every listed file
is updated and the page renders in the docs index.

### Acceptance Criteria

- The page covers every requested record kind and assessment.
- The belief-vs-truth boundary is explicit and repeated at the evidence bridge.
- Cross-links exist from the four related pages.

### Verification

- `test -f docs/accounting-ledgers.md`
- `rg -n "accounting-ledgers.md" README.md docs/*.md` — expected: at least one
  index entry and the cross-links.

---

## Task 22: Add documentation pin and negative parity checks

### Intent

Prevent documentation drift and prohibit truth/money/authority language with
executable checks.

### Implementation Steps

1. Create `tests/unit/test_accounting_ledgers_docs.py`:
   - required headings and tokens in `docs/accounting-ledgers.md`;
   - all five entry kinds and six assessments named;
   - `consistent` is documented as "not truth" and `suspected_fraudulent` as
     "not proven";
   - `220` metric families and no `Current catalog: 216` line;
   - seven route paths and both env settings;
   - pins: 43 commands, 73 observer semantic types, replay-v27/codec `v25`,
     Alembic `0017`, `/v1`, `observer-protocol-v1`;
   - forbidden claims: assert the page does not claim `money`, `currency`,
     `interest`, or `bank` as implemented features, and that it contains the
     exact non-goal sentence
     `No money, currency, interest, bank, or credit score exists.`; assert the
     page does not contain `objective ledger`, `source of truth`,
     `verified balance`, or `fraud detected`;
   - no `runner-config-v57`, no `0018`, no `/v2`, no Godot overlay claim;
   - off-gate experiment named;
   - cross-links present in the four related pages;
   - historical counts may appear only in clearly dated historical sections.
2. Add a positive parity check that the four accounting family ids appear in
   `docs/analysis-metrics.md` and resolve in `MetricFamilyId`, and that the
   accounting section contains no unknown family id. Do not require every one of
   the 220 ids to be listed in that page.
3. Add a negative check that `docs/accounting-ledgers.md` does not contain
   `objective ledger`, `source of truth`, `verified balance`, or
   `fraud detected`.
4. Run `$aif-docs` verification output into the test expectations only where the
   docs skill defines stable tokens.

### Required Interfaces and Contracts

- The test is a pure text/AST check; no network.
- Negative checks fail on prose drift, not on code comments.

### Requirement Evidence (when reconciliation applies)

- Original Request "Do not make ledger content objective truth".
- `tests/unit/test_credit_relationships_docs.py` and
  `tests/unit/test_emergent_prices_docs.py`.

### Error Handling and Logging

- Not applicable.

### Tests

Command: `uv run pytest tests/unit/test_accounting_ledgers_docs.py -q`.

### Acceptance Criteria

- Positive and negative parity checks pass.
- No forbidden truth/money language is present.

### Verification

- The command above — expected: pass.
- `rg -n "source of truth|verified balance|fraud detected" docs/accounting-ledgers.md` — expected: no output.

---

## Task 23: Required-gate verification certification

### Intent

Run every required lane, record the exact command and result, and mark any lane
that cannot run as `unexecuted` with its prerequisite. No lane is green without
evidence.

### Implementation Steps

1. Run and record:
   - `uv run pytest tests/unit tests/architecture -q`
   - `uv run pytest tests/unit/test_accounting_ledgers_*.py tests/architecture/test_accounting_ledgers_*.py -q`
   - the focused coverage lane with `--cov=src --cov-report=term`
   - `uv run ruff check src tests`
   - `uv run mypy src tests`
   - `uv run lint-imports`
   - `uv run pytest tests/integration -m "not scale" -q`
   - `uv run pytest tests/integration/test_accounting_ledgers_store_api.py -q -m integration`
   - `docker compose config`
   - `cd clients/research-ui && ./node_modules/.bin/vitest run`
   - `cd clients/research-ui && ./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json`
   - `GODOT_BIN=~/.cache/palimpsest-godot/Godot_v4.7.2-stable_linux.x86_64 "$GODOT_BIN" --headless --path clients/godot-observer --script res://tests/run_protocol.gd`
   - `PALIMPSEST_V4_SCALE_IDS=100000 uv run pytest tests/benchmarks -m "not scale" -q`
2. For Compose/browser acceptance, attempt only with an attested image. If the
   image reports `revision=unknown` or `source-clean=false`, record
   `unexecuted` with `source_revision_missing`.
3. For full-lane Python coverage, use the same policy as the previous plan: if
   the lane cannot finish inside a dedicated budget, record `unexecuted` and the
   focused coverage result instead of claiming green.
4. Fill the Verification Receipt in `index.md` with the lane, exact command,
   result, and prerequisite/note.
5. Record the roadmap handoff: `$aif-roadmap` owns the V4-23 registration and
   the V4-17 through V4-22 re-confirmation. Do not edit `ROADMAP.md` here.
6. Confirm with `git status` that no `alembic/versions/0018*`, no
   `clients/godot-observer/` source change, no `/v2` route, and no runner schema
   file changed.

### Required Interfaces and Contracts

- Every required lane is either green with a command/result or `unexecuted` with
  a prerequisite.
- No partial result is described as passing.
- The receipt is the only certification source.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` "Code Organization Note" — coverage enabled and
  test commands.
- `docs/development.md` — verification commands.

### Error Handling and Logging

- A failing lane blocks certification; do not mark the plan complete.
- Record the failure and the safe error code.

### Tests

- The lanes above are the tests.

### Acceptance Criteria

- Every required lane is recorded.
- The Definition of Done in `index.md` is satisfied or explicitly deferred.
- The verification receipt is complete.

### Verification

- `git status --short` — expected: only V4-23 plan, source, tests, docs, and
  client changes.
- `rg -n "runner-config-v57|alembic/versions/0018|observer-protocol-v2" src tests docs` — expected: no output.

## Phase Risks and Mitigations

- Risk: documentation claims a behavior the code does not implement.
  Mitigation: docs parity checks run in the same task as the docs.
- Risk: an environment-gated lane is reported as green without an attested
  image.
  Mitigation: the receipt records `unexecuted` with the exact prerequisite.
- Risk: the roadmap is edited by the plan rather than `$aif-roadmap`.
  Mitigation: `git status` check and an explicit ownership note.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
