# Phase 8: Documentation and Verification

Plan: [index.md](index.md)
Tasks: 23-25
Depends on: Phase 7 / Task 22

## Objective

Document the feature through the mandatory `$aif-docs` checkpoint, pin the
documentation with positive and negative parity tests, and certify every
required gate or record it explicitly `unexecuted` with its missing prerequisite.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `docs/trade-networks.md` | headings, tokens, non-goals | Page structure to mirror |
| `tests/unit/test_trade_networks_docs.py` | sections/tokens/counts/negative parity (22-162) | Docs test pattern |
| `README.md` | docs tables (59-60, 105-106) | Index rows to add |
| `.ai-factory/ARCHITECTURE.md` | baseline pins (177-193), ownership (195-210), V4 seams (1043-1096) | Architecture documentation |
| `.ai-factory/DESCRIPTION.md` | V4 feature paragraphs (598-618) | Project description |
| `docs/architecture.md` | V4 seam sections (785-804) | Contributor architecture |
| `docs/configuration.md` | dual-gate sections (539-558) | Configuration documentation |
| `docs/analysis-metrics.md` | family sections (727-737) | Metric documentation |
| `docs/research-api.md` | route sections (389-399) | API documentation |
| `docs/development.md` | verification commands | Gate commands |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `docs/market-like-institutions.md` | create | Complete feature page |
| `README.md` | modify | Two documentation index rows |
| `.ai-factory/ARCHITECTURE.md` | modify | Baseline pins, ownership, V4-20 seam |
| `.ai-factory/DESCRIPTION.md` | modify | V4-20 paragraph and pins |
| `docs/architecture.md` | modify | V4-20 seam section and cross-link |
| `docs/configuration.md` | modify | Dual-gate settings and publication note |
| `docs/analysis-metrics.md` | modify | Four family sections and count 208 |
| `docs/research-api.md` | modify | Seven routes and failure codes |
| `docs/trade-networks.md` | modify | Cross-link and current catalog pin |
| `tests/unit/test_market_institutions_docs.py` | create | Positive and negative parity |

## Task 23: Documentation via `$aif-docs`

### Intent

Produce one authoritative page and update every current-pin surface so readers
and later plans see the same counts, routes, limits, and non-goals.

### Implementation Steps

1. Invoke the `$aif-docs` workflow and create `docs/market-like-institutions.md`
   with these exact headings:
   `## Overview`, `## Mechanics`, `## Emergence loop`, `## Expectations and
   schedules`, `## Roles and brokers`, `## Exchange records`, `## Derivation`,
   `## Bounds and coverage`, `## Read-only surfaces`, `## Configuration`,
   `## Metrics`, `## Read-only fields`, `## Non-goals`, `## Verification`.
2. The page must state:
   - `market-institutions.v1` policy, owner-scoped beliefs, and the absence of a
     global Market class, price, money, currency, debt, credit limit, score,
     ranking, severity, recommendation, allocation, or quota;
   - `markets_credit` is the inherited V4-01 context name; V4-20 implements
     market-like institutions only, not credit or banking;
   - the emergence loop: repeated own-observed exchange at a location →
     expectation → schedule/role/record beliefs → attendance and persistence;
   - brokers are emergent role claims referencing existing offices or
     organization concepts; no broker actor, fee, or commission exists;
   - exchange records are opaque anchors to existing durable records or
     repositories, never objective market records;
   - schedules are owner-scoped convention-like beliefs communicated in
     `mkt_v1` frames, not world timers;
   - the analysis derives venue recurrence, clusters, lineage, broker-like
     participation, and researcher-only alignment from committed events plus
     detached owner rows;
   - 14 contexts / 12 flags / eight owned / four unowned; 208 metric families;
     43 commands; 73 observer semantic types; replay-v27/codec `v25`; Alembic
     `0017`; `/v1`; `observer-protocol-v1`;
   - seven GET-only routes under `SUBJECTIVE_DEBUG`, default limit 100, maximum
     500, `window_index` 0-511, `market_institutions_disabled` when either
     setting is absent;
   - `market-institutions-snapshot-v1` and `market-institutions-store-v1` are
     siblings, not runner/result/replay/SQL schemas;
   - publication is programmatic and post-completion; no CLI producer exists;
   - no Godot overlay exists;
   - `market_institutions@1` is off the V1 gate;
   - `$aif-roadmap` owns roadmap registration; V4-17, V4-18, V4-19, and V4-20
     are currently unregistered and the owned count must be recorded as eight.
3. Update `README.md` in both documentation tables with a
   `Market-like institutions` row pointing to `docs/market-like-institutions.md`.
4. Update `.ai-factory/ARCHITECTURE.md`:
   - baseline table: metric families 208 and the V4-20 note;
   - capability ownership: add `markets_credit` (V4-20) and state four flags
     remain unowned;
   - add a `### V4-20 market-like institutions seam` section after V4-19 with
     authority, packages, policy, ledger, analysis, snapshot, routes, clients,
     and pins.
5. Update `.ai-factory/DESCRIPTION.md` with a V4-20 paragraph in the existing
   V4 sequence, matching the pinned counts and non-goals.
6. Update `docs/architecture.md` with the V4-20 seam and a link to the new page;
   update `docs/configuration.md` with the two settings and the programmatic
   publication note; update `docs/analysis-metrics.md` with the four families
   and current count; update `docs/research-api.md` with the seven routes and
   the four error codes (`market_institutions_disabled`,
   `market_institutions_store_corrupt`, `market_institutions_cursor_invalid`,
   `market_institutions_cursor_expired`).
7. Update `docs/trade-networks.md` only for the current catalog pin (208) and a
   cross-link; do not rewrite its historical statements.
8. Do not edit `.ai-factory/ROADMAP.md`; roadmap ownership is explicitly
   reserved for `$aif-roadmap`.

### Required Interfaces and Contracts

- Documentation counts match source of truth exactly: 208 families, eight owned
  flags, 43 commands, 73 semantic types, replay-v27/codec `v25`, Alembic
  `0017`.
- The page contains no affirmative price/money/score/planner claim; every such
  phrase appears only inside a negation.
- The page names both environment variables exactly:
  `PALIMPSEST_MARKET_INSTITUTIONS_ROOT` and
  `PALIMPSEST_MARKET_INSTITUTIONS_CURSOR_KEY`.
- The page does not claim credit, banking, debt, profit, or a central exchange.

### Requirement Evidence

- Mandatory docs policy from plan Settings.
- `.ai-factory/ARCHITECTURE.md` requirement 7: roadmap registration belongs to
  `$aif-roadmap`.
- `docs/trade-networks.md` and `tests/unit/test_trade_networks_docs.py` — page
  and parity structure.

### Error Handling and Logging

- No runtime behavior.
- `$aif-docs` must report which files it created or updated and stop on a
  missing mandatory section.

### Tests

Documentation content is verified by Task 24. This task's manual check is a
read-through for count and non-goal consistency.

### Acceptance Criteria

- The page exists, is linked from README, and contains every required heading
  and exact token.
- All current-pin surfaces say 208 and eight owned.
- The roadmap file is unchanged.

### Verification

- `git status --short` shows only the files listed in Files to Change, with no
  `.ai-factory/ROADMAP.md` entry.
- Manual read of the new page confirms every non-goal is negated.

## Task 24: Add documentation pin and negative parity checks

### Intent

Prevent silent drift between the page, the code pins, and the API surface, and
prove the page makes no commercial or planner claim.

### Implementation Steps

1. Create `tests/unit/test_market_institutions_docs.py`:
   - page exists and `README.md` links `docs/market-like-institutions.md`;
   - every required heading exists;
   - exact tokens: `market-institutions.v1`,
     `market-institutions-snapshot-v1`, `market-institutions-store-v1`,
     `market_institutions@1`, `PALIMPSEST_MARKET_INSTITUTIONS_ROOT`,
     `PALIMPSEST_MARKET_INSTITUTIONS_CURSOR_KEY`,
     `market_institutions_disabled`, `market_like_persistent`, `window_index`,
     `208`;
   - `METRIC_FAMILY_COUNT == 208` and
     `docs/analysis-metrics.md` contains `**208**` and the four family ids;
   - seven route paths appear in both the page and `docs/research-api.md`;
   - the page contains `14 contexts / 12 flags / eight owned`;
   - `runner-config-v57` is absent;
   - sentence-level negative parity: every sentence containing `central
     planner`, `price index`, `market score`, `money object`, `ranking`,
     `recommendation`, `allocation`, or `quota` also contains a negation marker
     (`no`, `never`, `does not`, `do not`, `not`);
   - every sentence containing `new command`, `new event`, `new write pair`, or
     `migration` is negated;
   - the page contains `$aif-roadmap` and the roadmap file contains `## M8`.
2. Update `tests/unit/test_trade_networks_docs.py` and any sibling docs test
   whose current-pin token is `204` to `208`; leave historical sentences inside
   pages untouched.
3. Add a docs parity assertion that `.ai-factory/ARCHITECTURE.md` and
   `.ai-factory/DESCRIPTION.md` both contain `208`, `markets_credit`, and
   `eight owned`.
4. Add a negative check that no docs page claims a Godot market overlay: search
   `docs/market-like-institutions.md` for `overlay` and require each occurrence
   to be negated.

### Required Interfaces and Contracts

- Tests read files only; they never generate docs.
- Negative parity is sentence-scoped and case-insensitive.
- The docs test does not assert exact prose length or ordering beyond the
  required headings and tokens.

### Requirement Evidence

- `tests/unit/test_trade_networks_docs.py:22-162` — exact pattern.
- Plan Settings: "Docs: yes; mandatory `$aif-docs` checkpoint in Task 23."

### Error Handling and Logging

- Failures name the file, heading, or token; no large text dumps.

### Tests

- `tests/unit/test_market_institutions_docs.py`
- Updated sibling docs tests.

### Acceptance Criteria

- The docs suite passes.
- Deliberately changing a count in the page fails the suite.
- Adding an affirmative price sentence fails the suite.

### Verification

- `uv run pytest tests/unit/test_market_institutions_docs.py tests/unit/test_trade_networks_docs.py tests/unit/test_supply_chain_docs.py -q`
- Expected result: all pass.

## Task 25: Required-gate verification certification

### Intent

Run every required lane, fix failures before certification, and record each
lane's exact command and result. Env-gated lanes that cannot run are recorded as
`unexecuted` with the missing prerequisite; they are never reported green.

### Implementation Steps

1. Run the Python lanes:
   - `uv run pytest tests/unit tests/architecture -q --cov=src --cov-report=term`
   - `uv run pytest tests/unit/test_market_institutions_*.py tests/unit/test_supply_chain_pins.py tests/architecture/test_market_institutions_*.py -q`
   - `uv run pytest tests/unit/test_market_institutions_docs.py -q`
2. Run static lanes:
   - `uv run ruff check src tests`
   - `uv run mypy src tests`
   - `uv run lint-imports`
3. Run integration lanes:
   - `uv run pytest tests/integration -m "not scale" -q`
   - `uv run pytest tests/integration/test_market_institutions_store_api.py -q -m integration`
4. Run packaging and client lanes:
   - `docker compose config`
   - `cd clients/research-ui && npx vitest run`
   - `cd clients/research-ui && npx svelte-check --tsconfig ./tsconfig.app.json`
5. Run the Godot regression suite only if the pinned editor and export templates
   are installed: `cd clients/godot-observer && <pinned-editor> --headless
   --path . -s tests/run_protocol.gd`. If unavailable, record `unexecuted` with
   the missing prerequisite.
6. Run Compose/browser acceptance only with an attested image and a headed
   browser harness; otherwise record `unexecuted`.
7. Run `tests/benchmarks` scale lanes only with scale hardware and a disposable
   PostgreSQL instance; otherwise record `unexecuted`.
8. Append a `## Verification Receipt` section to `index.md` with a table:
   `Lane | Command | Result | Prerequisite / note`. Mark every lane either green
   with its counts or `unexecuted` with the missing prerequisite.
9. Fix all failures before writing the receipt. If a fix changes scope, update
   the affected phase file and task checkbox rather than hiding the change.
10. Confirm `git status --short` shows no `.ai-factory/ROADMAP.md` change and
    no branch creation.

### Required Interfaces and Contracts

- Certification requires every lane green or explicitly `unexecuted`; a skipped
  lane may not be summarized as passing.
- Coverage is enabled for Python unit/architecture lanes.
- No test is marked skip or xfail to manufacture a green lane.
- The receipt records the exact command actually run, not a paraphrase.

### Requirement Evidence

- Plan Settings: testing yes, full strategy; normal verification with explicit
  complete required-gate certification.
- `docs/development.md` — canonical commands.
- V4-19 receipt structure — required lane table shape.

### Error Handling and Logging

- Failures are reported with the failing lane, command, and first actionable
  error; full logs are truncated to the relevant section.
- Never paste secrets, DSNs, tokens, or payload bodies into the receipt.

### Tests

The lanes themselves are the verification. The focused suite must include the
E2E, determinism, leakage, docs, routes, store, and architecture tests.

### Acceptance Criteria

- All local lanes pass.
- The receipt names every required lane and marks env-gated lanes `unexecuted`
  with prerequisites.
- Definition of Done is satisfied except for explicitly unexecuted lanes.
- Roadmap state is unchanged and the follow-up registration is stated.

### Verification

- The receipt table in `index.md` is the final verification artifact.
- `git status --short` matches the planned files plus the plan bundle.

## Phase Risks and Mitigations

- Risk: docs drift from source after the pin sweep. Mitigation: Task 24 asserts
  the exact counts in the page, ARCHITECTURE, and DESCRIPTION.
- Risk: an env-gated lane is silently treated as green. Mitigation: the receipt
  has an explicit `unexecuted` value and a prerequisite column.
- Risk: a late fix invalidates earlier evidence. Mitigation: rerun the affected
  lane and update the receipt row; never carry a stale result forward.

## Phase Completion Checklist

- Every Task 23-25 acceptance criterion is verified.
- docs contain the page, README rows, ARCHITECTURE, DESCRIPTION,
  `docs/architecture.md`, `docs/configuration.md`, `docs/analysis-metrics.md`,
  and `docs/research-api.md` updates.
- The receipt is complete and truthful.
- `index.md` task checkboxes are updated immediately after verified completion.
