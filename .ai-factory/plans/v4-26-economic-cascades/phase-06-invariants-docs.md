# Phase 6: Invariants, Documentation, and Certification

Plan: [index.md](index.md)
Tasks: 18-21
Depends on: Phase 5 (Tasks 15-17)

## Objective

Sweep every shared pin from 16→17 contexts and 236→244 metric families, document
the feature through `$aif-docs`, add positive and negative documentation parity
checks, and record an explicit verification receipt for every required lane.
Roadmap registration stays with `$aif-roadmap`.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `tests/architecture/test_v4_context_registry.py` | order (31), counts (103-110), analysis-only set (113-155), doc headings (195-202) | Context pin sweep |
| `tests/architecture/test_v4_architecture_invariants.py` | 16/12/8/4 (174-226), v57 scan (252-257) | Ownership pin sweep |
| `tests/unit/test_runner_config_v4_flags.py` | 12 fields (25-36), `len(V4_CONTEXTS) == 16` (49), owned set (128-141) | Flag pin sweep |
| `tests/unit/test_metric_specifications.py` | family count | Catalog pin sweep |
| `tests/unit/test_economic_inequality_docs.py` | "15 contexts" (53,65) | Known stale assertion to correct |
| `tests/unit/test_social_mobility_docs.py` | 16 contexts/map v4 (45-79) | Newest docs-pin template |
| `docs/v4-architecture.md` | stale "Fourteen bounded contexts" (54-58) and heading count | Documentation home for the new context |
| `docs/social-mobility.md` | structure to mirror for the new page | Docs template |
| `.ai-factory/ARCHITECTURE.md` | baseline table (177-193), V4-24/V4-25 seams (1202-1247) | Architecture pin and new seam |
| `.ai-factory/DESCRIPTION.md` | V4-25 paragraph (735-756) | Implemented-state description |
| `README.md` | documentation index table | Landing-page entry |
| `docs/analysis-metrics.md`, `docs/research-api.md`, `docs/research-ui.md`, `docs/configuration.md`, `docs/architecture.md` | family/route/settings sections | Cross-surface docs |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `tests/architecture/test_v4_context_registry.py` | modify | 17 contexts, v5 map, order, prereqs, analysis-only set, heading count |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | 17/12/8/4 pins and any remaining 16 literal |
| `tests/unit/test_runner_config_v4_flags.py` | modify | `len(V4_CONTEXTS) == 17` |
| 29 context-count test files (list in the task) | modify | Replace 16 with 17 where the assertion is a context count, not a historical fact |
| `tests/unit/test_metric_specifications.py` and catalog-pin tests | modify | 236→244 |
| `tests/unit/test_economic_inequality_docs.py`, `docs/economic-inequality.md` | modify | Correct stale 15-context current-state wording to 17 |
| `docs/economic-cascades.md` | create | Feature page |
| `README.md` | modify | Documentation index entry |
| `.ai-factory/ARCHITECTURE.md` | modify | Baseline 244/17/v5 and V4-26 seam |
| `.ai-factory/DESCRIPTION.md` | modify | V4-26 implemented-state paragraph |
| `docs/architecture.md`, `docs/configuration.md`, `docs/analysis-metrics.md`, `docs/research-api.md`, `docs/v4-architecture.md`, `docs/research-ui.md` | modify | Context, catalog, routes, settings, UI |
| `docs/supply-chains.md`, `docs/trade-networks.md`, `docs/economic-inequality.md`, `docs/social-mobility.md`, `docs/infrastructure-networks.md` | modify | Cross-links |
| `tests/unit/test_economic_cascades_docs.py` | create | Documentation parity and negatives |
| `tests/architecture/test_economic_cascades_pins.py` | create | Aggregate pin assertions |

## Task 18: Sweep context, catalog, and ownership pins

### Intent
Make the whole repository agree on 17 contexts, `v4-context-map-v5`, 12 flags,
8 owned, 4 unowned, and 244 metric families, without changing accepted legacy
versions.

### Implementation Steps
1. Context sweep. Replace `16` with `17`, `v4-context-map-v4` with
   `v4-context-map-v5`, and extend ordered/frozenset expectations in:
   - `tests/architecture/test_v4_context_registry.py`
   - `tests/architecture/test_v4_architecture_invariants.py`
   - `tests/unit/test_runner_config_v4_flags.py`
   - `tests/unit/test_social_mobility_docs.py` and
     `tests/architecture/test_social_mobility_invariants.py` (both still pin
     16 contexts and `v4-context-map-v4`)
   - every remaining file found by
     `grep -rln "len(V4_CONTEXTS) == 16\|v4-context-map-v4\|\"16 V4 contexts\"" tests/`
     (the 29-file count sweep reported during planning; re-derive it at
     implementation time with that command).
   - doc-heading count assertions that compare to `len(V4_CONTEXTS)` stay
     derived; the four that hard-code `== 16` become `== 17`.
2. Catalog sweep. Replace `236` with `244` and extend append-range assertions in:
   - `tests/unit/test_metric_specifications.py`
   - `tests/unit/test_economic_cascades_catalog.py` (positions 236-243)
   - every file found by `grep -rln "236" tests/ | xargs grep -l "metric"` where
     the literal is the current family count, not a historical landing count.
   Historical lines such as "220 -> 228" or "228 -> 236" are provenance and stay.
3. Stale current-state correction: `docs/economic-inequality.md` and
   `tests/unit/test_economic_inequality_docs.py` currently say 15 contexts; make
   the current-state wording 17. Do not rewrite historical landing paragraphs in
   other docs.
4. Ownership: assert owned flags remain exactly
   `organizations`, `formal_rules`, `legal_disputes`, `diplomacy`,
   `organized_conflict`, `infrastructure_networks`, `supply_chains`,
   `markets_credit`; unowned remain `science`, `epidemics`,
   `ecological_feedback`, `disasters`.
5. Negative pins: assert no `runner-config-v57` in `src/`, no
   `alembic/versions/0018*`, `EVENT_SCHEMA_REPLAY_V27 == 27` with no V28,
   `"v25"` accepted with `"v26"` absent, 43 commands, 73 observer semantic
   types, `/v1`, and `observer-protocol-v1`.
6. Create `tests/architecture/test_economic_cascades_pins.py` with one assertion
   per pin so a future bump has a single visible failure list.

### Required Interfaces and Contracts
- Only current-state literals change; accepted legacy versions and historical
  landing notes stay.
- No production constant changes other than the ones delivered in Tasks 1 and 8.
- Pin tests read the real registries, not duplicated literals, wherever the
  registry exposes the value.

### Requirement Evidence
- `.ai-factory/ARCHITECTURE.md` requirement 1 and the "dated baseline" note.
- `tests/unit/test_alembic_head_pin.py` and
  `tests/architecture/test_v4_architecture_invariants.py`.

### Error Handling and Logging
- No production logging change.
- Record the exact sweep commands in the verification receipt so the race
  between literals is auditable.

### Tests
- The full unit and architecture lanes (Task 21) are the gate for this task.

### Acceptance Criteria
- A repository-wide search finds no current-state 16-context or 236-family pin.
- All pin tests pass together.
- No accepted version is removed or renamed.

### Verification
- `grep -rn "v4-context-map-v" tests/ src/ docs/ | grep -v "v4-context-map-v5"` → only historical mentions
- `grep -rn "len(V4_CONTEXTS) == 16" tests/` → no matches
- `grep -rn "METRIC_FAMILY_COUNT" src/analysis/specifications.py` → `244`
- Expected result: no stale current-state pin remains.

## Task 19: Documentation via `$aif-docs`

### Intent
Document the contract, evidence model, analytical limits, and read surfaces so a
researcher can use the feature without inferring causality the analysis does not
claim.

### Implementation Steps
1. Invoke `$aif-docs` for the V4-26 change set.
2. Create `docs/economic-cascades.md` with sections:
   - Purpose and non-goals (no cascade engine, no new world rule, no severity).
   - Five disruption classes and their committed event sources.
   - Dependency structure: recipe inputs, tools, infrastructure, transport,
     labor participation; depth 6.
   - Chain semantics: `linked`, `unlinked`, `unresolved`, `unavailable`;
     dependency-conditioned, never proof of cause.
   - Quantitative outputs: shortfall shares, chain counts, depth/lag milli,
     minimum 3 linked chains.
   - Windows: 32 ticks, 512 windows, lag 2 windows.
   - Metric families 236-243 and the 244 total.
   - `economic-cascades-snapshot-v1` and `economic-cascades-store-v1`.
   - Seven routes and both settings.
   - `economic_cascades@1` arms and off-gate status.
   - Interpretation limits: blocked attempts are uncommitted today, so
     shortfalls are inferred from demand/completion gaps; tool shortage is a
     production-decline proxy.
3. Update `.ai-factory/ARCHITECTURE.md`: baseline metric families 244, contexts
   17, map `v4-context-map-v5`, and a `### V4-26 economic-cascades seam`
   paragraph naming the new context, eight families, snapshot/store, routes,
   and the no-flag/no-event/no-write-pair boundary.
4. Update `.ai-factory/DESCRIPTION.md` with a V4-26 paragraph mirroring V4-25,
   including pins and the five classes.
5. Update `docs/architecture.md` (downstream checklist and analysis boundaries),
   `docs/configuration.md` (both env vars and the dual gate),
   `docs/analysis-metrics.md` (eight families and denominators),
   `docs/research-api.md` (seven GET routes and error codes),
   `docs/v4-architecture.md` (context table row and a `### economic_cascades`
   section; correct the stale "Fourteen bounded contexts / v2" prose),
   `docs/research-ui.md` (panel), and `README.md` (index row).
6. Add cross-links from `docs/supply-chains.md`, `docs/trade-networks.md`,
   `docs/economic-inequality.md`, `docs/social-mobility.md`, and
   `docs/infrastructure-networks.md`.
7. Keep roadmap registration and milestone closure with `$aif-roadmap`.

### Required Interfaces and Contracts
- Every documented route, setting, family id, snapshot version, and store
  version matches the code exactly.
- The page must state the analytical, non-causal semantics and the uncommitted
  rejection limit.
- No documentation may use `class`, `caste`, `stratum`, `elite`, `underclass`,
  `severity`, `impact score`, `cascade score`, `risk score`, `blame`, `fault`,
  `root cause`, `wealth`, or `price` as a claim about the feature.

### Requirement Evidence
- Original Request "Provide dependency/cascade analytics" and "Do not script
  downstream outcomes".
- `.ai-factory/ARCHITECTURE.md` requirement 7 (docs checkpoint) and roadmap
  ownership.

### Error Handling and Logging
- Not applicable; docs only.

### Tests
- Documentation parity is Task 20; this task produces the content.

### Acceptance Criteria
- The page is self-contained and links to code-adjacent docs.
- Every pin stated matches Task 18's values.
- No forbidden vocabulary or causal overclaim exists.

### Verification
- `uv run python -c "from pathlib import Path; t=Path('docs/economic-cascades.md').read_text(); print(all(x in t for x in ['economic-cascades-snapshot-v1','economic-cascades-store-v1','economic_cascades@1','v4-context-map-v5']))"`
- Expected result: `True`.

## Task 20: Add documentation pin and negative parity checks

### Intent
Make documentation drift a test failure, including forbidden vocabulary and
absent-schema claims.

### Implementation Steps
1. Create `tests/unit/test_economic_cascades_docs.py`:
   - `docs/economic-cascades.md` exists and is non-empty.
   - It contains all five class tokens, all four chain states, the snapshot and
     store versions, policy `economic-cascades.v1`, eight family ids, the seven
     route suffixes, both env var names, and `economic_cascades@1`.
   - Pin assertions: 244 families, 17 contexts, `v4-context-map-v5`, 12 flags,
     8 owned, 43 commands, 73 observer semantic types, replay-v27/codec `v25`,
     Alembic `0017`, `/v1`, `observer-protocol-v1`.
   - Negative assertions: no `runner-config-v57`, no `/v2`, no
     `economic_cascades_disabled` documented as a flag, and no forbidden
     vocabulary used as a claim.
   - `docs/v4-architecture.md` contains `### economic_cascades` and its `### `
     heading count equals `len(V4_CONTEXTS)`.
   - README links the new page.
2. Add the same forbidden-vocabulary scan to the panel test fixture text and to
   the snapshot/route response fixtures used in Task 17.
3. Keep the assertions token-based so wording edits do not break them.

### Required Interfaces and Contracts
- Tests fail on a stale count, a missing route, a missing setting, or a
  forbidden claim token.
- Historical provenance sentences are exempt only when they are explicitly
  marked as landed history; do not add blanket substring exemptions.

### Requirement Evidence
- `tests/unit/test_social_mobility_docs.py:45-79`.
- `.ai-factory/ARCHITECTURE.md` requirement 7.

### Error Handling and Logging
- Not applicable.

### Tests
- `tests/unit/test_economic_cascades_docs.py`.

### Acceptance Criteria
- A deliberate pin edit or vocabulary edit fails the test with a readable
  message.
- No false positive on the documented non-goals.

### Verification
- `uv run pytest tests/unit/test_economic_cascades_docs.py -q`
- Expected result: pass.

## Task 21: Required-gate verification certification

### Intent
Record every lane's command and result honestly, including unexecuted lanes and
their prerequisites. No lane is green without a recorded command and result.

### Implementation Steps
1. Add a `## Verification Receipt` table to `index.md` with rows for:
   unit+architecture, focused cascade suites, Python coverage (focused and full),
   Ruff, mypy, import-linter, non-scale integration, cascade store/API
   integration, Compose config, Research UI vitest, Research UI svelte-check,
   Godot regression (existing suite only), Compose/browser acceptance, and
   benchmark regression.
2. Run each lane with the exact commands:
   - `uv run pytest tests/unit tests/architecture -q`
   - `uv run pytest tests/unit/test_economic_cascades_*.py tests/architecture/test_economic_cascades_*.py tests/integration/test_economic_cascades_store_api.py -q`
   - `uv run pytest tests/unit/test_economic_cascades_*.py tests/architecture/test_economic_cascades_*.py -q --cov=src --cov-report=term`
   - `uv run pytest tests/unit tests/architecture -q --cov=src --cov-report=term`
   - `uv run ruff check src tests`
   - `uv run mypy src tests`
   - `uv run lint-imports`
   - `uv run pytest tests/integration -m "not scale" -q`
   - `uv run pytest tests/integration/test_economic_cascades_store_api.py -q -m integration`
   - `docker compose config`
   - `cd clients/research-ui && ./node_modules/.bin/vitest run`
   - `cd clients/research-ui && ./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json`
   - `GODOT_BIN=~/.cache/palimpsest-godot/Godot_v4.7.2-stable_linux.x86_64 "$GODOT_BIN" --headless --path clients/godot-observer --script res://tests/run_protocol.gd`
   - attested image + headed browser harness (may be `unexecuted`)
   - `PALIMPSEST_V4_SCALE_IDS=100000 uv run pytest tests/benchmarks -m "not scale" -q`
3. Record `unexecuted` with the missing prerequisite when a lane cannot run; do
   not claim certification.
4. Run `git status --short` and confirm: no `.ai-factory/ROADMAP.md` edit, no
   `alembic/versions/0018*`, no `clients/godot-observer/` source change, no
   `runner-config-v57`, no new V4 flag, no `/v2` route.
5. Note the expected-red window between Task 1 and Task 18 only if the receipt
   is recorded incrementally; the final receipt must show the full suite green.

### Required Interfaces and Contracts
- The receipt is the only certification source; prose claims without a command
  are invalid.
- Coverage is lane-scoped and labeled as such.
- Unattested Compose/browser lanes stay `unexecuted`.

### Requirement Evidence
- Project `verify_mode: normal` plus the user's explicit complete-gate
  certification request.
- `.ai-factory/ARCHITECTURE.md` requirement 3 (V1/V2 gates stay green).

### Error Handling and Logging
- If a lane fails, fix the cause or record it as failed with the exact error;
  never mark it passed.
- Long lanes may run in the background; record wall time only if useful.

### Tests
- Not applicable; this task records results.

### Acceptance Criteria
- Every required lane has a command, result, and prerequisite note.
- The final unit+architecture lane is green at 244 families and 17 contexts.
- `git status` confirms the scoped change set.

### Verification
- `uv run pytest tests/unit tests/architecture -q` expected: all pass.
- `git status --short` expected: only V4-26 scoped paths.

## Phase Risks and Mitigations
- Risk: a blanket 236→244 replacement corrupts historical landing notes.
  Mitigation: only current-state literals; provenance lines are explicitly
  identified and left unchanged.
- Risk: docs overclaim causality.
  Mitigation: task 20's token scan plus explicit non-goals.
- Risk: an env-gated lane is reported green without execution.
  Mitigation: `unexecuted` plus prerequisite is mandatory and verified by the
  receipt review.

## Phase Completion Checklist
- Context, catalog, and ownership sweeps are complete and consistent.
- The docs page and cross-links exist with positive and negative parity tests.
- The verification receipt has one row per required lane.
- `index.md` Tasks 18-21 checkboxes are updated after verification.
