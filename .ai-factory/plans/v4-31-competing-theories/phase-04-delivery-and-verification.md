# Phase 4: Delivery and verification

Plan: [index.md](index.md)  
Tasks: 7–9  
Depends on: Phase 3 / Tasks 5–6

## Objective

Researchers can inspect contrasting social support and performance in a real completed run. Demonstrate both popularity/accuracy directions without scripting the outcome of autonomous science.

## Current-Code Evidence

| Path | Symbols / contract | Why it matters |
|---|---|---|
| `src/api/routes/scientific_models.py`, `src/api/app.py`, `src/infrastructure/settings.py` | GET-only paired settings, `_authorize`, snapshot-pinned reads | Read-only research surface precedent |
| `clients/research-ui/src/api/scientificModels.ts`, `src/views/ScientificModelsPanel.svelte`, `src/research/selection.ts`, `src/views/RunOverview.svelte` (paths under `clients/research-ui/`) | Run selection and GET-only panel | Typed research client entry points |
| `src/experiments/catalog.py`, `src/experiments/scientific_models_scenario.py`; `tests/integration/test_scientific_models_runner.py`, `test_scientific_models_store_api.py` | `experiment_scientific_models`, `scientific_models_scenario`, actual runner/store/API | Off-gate factory and real end-to-end evidence |
| `docs/development.md` | Locked interpreter, coverage-enabled verification, external lane prerequisites | Verification and release discipline |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/api/routes/competing_theories.py`, `src/api/competing_theories_cursor.py` | Create | Typed response adapters and purpose-separated cursor, following scientific-model route/cursor placement |
| `src/api/app.py`, `src/infrastructure/settings.py` | Modify | Optional reader plus separate cursor purpose and paired settings |
| `clients/research-ui/src/api/competingTheories.ts`, `clients/research-ui/src/views/CompetingTheoriesPanel.svelte`, `clients/research-ui/src/views/CompetingTheoriesPanel.test.ts` | Create | Typed fetch, panel and request lifecycle tests |
| `clients/research-ui/src/research/selection.ts`, `clients/research-ui/src/views/RunOverview.svelte` | Modify | Stable `competing-theories` section and rendering |
| `src/experiments/competing_theories_scenario.py`, `src/experiments/catalog.py`, `src/experiments/__init__.py` | Create/modify | Off-gate experiment |
| `tests/unit/test_competing_theories_routes.py`, `tests/unit/test_competing_theories_scenario.py`, `tests/integration/test_competing_theories_runner.py` | Create | API, off-gate/reproducibility, controlled runner-to-read verification |
| `docs/competing-theories.md`, `docs/scientific-models.md`, `docs/configuration.md`, `docs/development.md`, `docs/research-ui.md`, `README.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/ROADMAP.md` | Add/update through docs and milestone checkpoint | Scope, contracts, named verification and dated landing/pins |

## Task 7: Serve and render read-only theory evidence

### Intent

Expose both axes and provenance independently under an existing research permission; disabled, absent, incomplete and empty data must look different.

### Implementation Steps

1. Add optional paired `PALIMPSEST_COMPETING_THEORIES_ROOT` and `PALIMPSEST_COMPETING_THEORIES_CURSOR_KEY` (≥32 UTF-8 bytes, secret type, hidden repr). Neither means disabled; reject exactly one at startup. Construct only reader and cursor codec in `create_app`, purpose `competing-theories` plus section.
2. Add GET `/v1/simulations/{run_id}/competing-theories` plus GET `/{section}` for the seven closed sections from Phase 3. Check `SUBJECTIVE_DEBUG` before lookup; no cookie/query credentials. Follow V4-30 error mapping: disabled 503, missing run/publication 404, invalid path/filter/limit/cursor or mismatched purpose 400, expired cursor 410, corrupt 500. Anonymous/underprivileged requests do not touch store; writes unsupported. Use initial latest only when no publication ID or cursor supplied; page responses expose publication ID and digest. Limits default 50, valid 1–200; cursor pins run, publication, digest, section, filters, limit and position. No fallback on expired or missing pinned artifacts. Do not expose stack traces or raw paths.
3. Add typed API client and panel. Pin run and publication from summary and keep filters consistent with cursor. Render tabs for support, citations, predictions/failures and transmission, with explicit coverage and rivalry context. Separate **declared support** and **observed predictive performance**, display both denominators, label cited pointers and teaching as testimony. Use stable ordering; no champion/rank/score badge and no mutations or Godot overlay. Cancel or ignore stale responses on run/tab/filter changes; use existing header credentials, never pass in URLs. Provide disabled, missing, known empty, partial and retryable error states.
4. Use the existing purpose-separated cursor implementation as the cryptographic primitive; add a theory-specific purpose and route registration at `create_app`, not a second signing algorithm. Verify the cursor before resolving the snapshot; an explicit publication ID with a cursor must agree with the bound ID. Distinguish `competing_theories_run_not_found` from `competing_theories_publication_not_found` even if both map to 404. A matching cursor for an older retained publication still pages that publication even after a newer one appears; missing old publication is a 404, never a latest fallback. Test settings/reader/cursor wiring through real `create_app(...)`, not only by assigning fake `app.state`.

### Required Interfaces and Contracts

Use Phase 3 rows and paging API, independent from existing scientific-model snapshot and routes. Query names `publication_id`, `window`, `theory_id`, `limit`, `cursor`; filters are exact and unsupported section/filter combinations fail closed.

### Requirement Evidence

`index.md` Original Request: track the requested channels without central selection. `docs/scientific-models.md` “Publication, store and reads”: gating and pinned pagination.

### Error Handling and Logging

Use existing structured error helpers; log route/section and reason counts only, never cursor, credential, speech, claim/citation payload or raw path.

### Tests

`test_competing_theories_routes.py`: authorization before store, optional settings truth table, success/empty/corrupt/disabled/missing, wrong section/run/filter/version, cursor expiry and newer-publication race, no mutations. `CompetingTheoriesPanel.test.ts`: divergent axes, testimony distinction, absence/partial states, pinned page and stale response handling.

### Acceptance Criteria and Verification

`uv run --frozen --python 3.12.14 pytest -q tests/unit/test_competing_theories_routes.py`; `pnpm --dir clients/research-ui test`; `pnpm --dir clients/research-ui check`; `pnpm --dir clients/research-ui build` pass.

## Task 8: Prove disagreement and coexistence in a completed run

### Intent

Prove the mechanism in a controlled lane and keep autonomous outcomes empirical rather than required.

### Implementation Steps

1. Add `competing_theories_scenario` and `experiment_competing_theories` (`competing_theories@1`) as programmatic off-V1-gate exports. Use `scientific_models_scenario(...).conditions` to select `models-season-resource` as the shared config, preserving its dynamics, roster, stochastic identity and ≥96-tick horizon in every arm. `theories-observation` is the unchanged seasonal config; `theories-science-off` only clears `V4CapabilityFlags.science`; `theories-communication` uses the owned deterministic communication strategy for all agents via existing per-agent config. If the shared config already uses it, force just the observation/off arms to the disabled strategy. No preloaded theories or intended result in production configs. Allow null/unobserved or nondiscriminating autonomous runs.
2. Add two distinct real-run lanes. For the representative compatibility lane run the actual unmodified `models-season-resource`/`models-science-off` configs and `models-measurement-coexistence` v57 config from `scientific_models_scenario`. For the controlled lane start with the v56 seasonal config but use a closed, well-lit, colocated runner fixture with no visible resources and no material matching a qualified experiment law; retain the science prerequisites and normal `CognitiveLoop`/`AgentRuntime`/`WorldEngine`. Drive only ordinary legal Wait/Talk/Tell commands using a test-only action strategy, never write the ledgers. With `L = environment.season_length_ticks` (48 in the representative fixture), hold the same location through ticks `L-2`, `L`, `5L-2`, `5L`, then through actual teaching receipt. At `L-2` and `5L-2` require the season hypothesis to be the only eligible V4-30 forecast context (no opportunistic round-robin selection); assert real base case IDs and outcomes from runtime/replay. The case scored at `L` seeds recurrence; the case issued at `5L-2` proves its first planned scoring at the repeat boundary, not retroactive credit. Assert submitted frame bytes, committed recipient observation, and exported stance/teaching rows, including an unmatched echo or denied/replaced negative control. Prove the minimum-three matched comparison separately with the detached fixture. No fixture-only schedule enters production configs.
3. In a controlled owner-policy plus detached analysis fixture, allocate four eligible local supporters to continuity and one to recurrence, score at least three matched cases on which continuity fails and recurrence hits, and keep a window where the majority stays supported after failure. In a separate context or disjoint recipient cohort invert the social distribution independently of outcomes and show support communities remain separate. Include an unanswered/denied teaching attempt and an actual addressed teaching receipt. Assert identical frozen distributions when only later social data changes; changing later social data must not alter the unchanged physical schedule in a matched submitted-command control. The speech-bearing feature run is **not** promised byte-identical to older science-on runs.
4. Export/freeze the real runner result, pass it through the real `assemble_arm_metric_bundle` path and assert nonzero expected families and unchanged existing scientific-model metric schema. Publish at least two windows and two publications via Phase 3, then read through configured Phase 4 factory as an authorized caller; assert same case/stance/receipt attribution, multi-page/window pinning through the older cursor, and no `winner`/truth output at every layer. Include a clean seed twin, a representative unmodified V4-30 science-off scenario and old fixture decode.

### Required Interfaces and Contracts

Scenario is composition only: no flags, schema or stop selector added, no world-oracle state, no scripted “emergence” or statistical generalization. Controlled results demonstrate possibility, not prevalence. Run and speech replay prove delivery independently of any local interpretation.

### Requirement Evidence

`index.md` Original Request: popular inaccurate and accurate minority theories; `.ai-factory/ARCHITECTURE.md` “Requirements for later changes”: reproducibility, gate and compatibility.

### Error Handling and Logging

Missing receipts and autonomous nulls retain their reasons rather than failing qualification. Fixture assertions fail on lineage/denominator mismatch; no raw content in runtime logs.

### Tests

`test_competing_theories_scenario.py` checks real config serialization, legible factor differences, no seeded content, twin scientific manifests and no registry gate changes. `test_competing_theories_runner.py` checks runner→export→publication→authorized GET and compatibility. Policy and detached fixtures from Tasks 3/5 prove explicit endorsement and matched performance matrix.

### Acceptance Criteria and Verification

`uv run --frozen --python 3.12.14 pytest -q tests/unit/test_competing_theories_scenario.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py`; `uv run --frozen --python 3.12.14 pytest -q -m integration tests/integration/test_competing_theories_runner.py`.

## Task 9: Document contracts and execute the compatibility gate

### Intent

Leave an auditable implementation and document exactly what was and was not verified.

### Implementation Steps

1. Route the mandatory docs checkpoint through `$aif-docs`: write the linked feature page with activation, bounded explanatory accounts, same-case forecasts/failures, local support, distinct speech/teaching, independent denominators, quotas, recovery, API and settings. Add the page to the README and neighboring configuration, research UI, development and scientific-model docs. Update dated AI Factory pins and link the implemented bundle under existing M8 without marking M8 complete or claiming any unowned flag.
2. Run default unit/architecture with coverage enabled, Ruff, mypy, import-linter, V4 architecture/pin tests, and Research UI checks. Audit exact 262-family pins and prove first 262 families/version keys stay byte-equivalent while new total is 268. Preserve 45 commands, 73 observer semantics, 17 contexts, 12 flags (9 owned), `v4-context-map-v6`, v4/v2 defaults, latest v57, replay 27/`v25` and 28/`v26`, infrastructure/older pairs, `/v1`, observer protocol and Alembic `0017`.
3. In the implementation summary record command, expected vs actual, coverage, and explicit `unexecuted` status/reason for unavailable PostgreSQL, Compose/browser, Godot, or scale lanes. Do not imply coverage from an unexecuted environment lane, disable coverage to improve speed, or make a scale claim.

### Required Interfaces and Contracts

Docs do not promise a universal winner, causal truth, cross-owner raw exports or full durable subjective restart. Version summary calls out pending v5 as distinct from the world replay codec.

### Requirement Evidence

`AGENTS.md` “Focused exploration”, `.ai-factory/RULES.md` “Coding Standards”, and `.ai-factory/ARCHITECTURE.md` “Versioned Extension Contract”.

### Error Handling and Logging

Preserve failures in verification notes and redact database URLs, environment secrets, patient or personal data (none needed), utterances and state payloads.

### Tests

Full Python baseline plus exact wire, fixture, and UI checks from earlier phases. Run available integration lanes with only disposable `palimpsest_test` database names.

### Acceptance Criteria and Verification

`uv run --frozen --python 3.12.14 pytest`; `uv run --frozen --python 3.12.14 ruff check src tests`; `uv run --frozen --python 3.12.14 mypy src tests`; `uv run --frozen --python 3.12.14 lint-imports`; `git diff --check` pass. Existing externally gated failures or skips are explicitly identified, not silently waived.

## Phase Risks and Mitigations

- A null autonomous run can tempt scripted results: maintain controlled and autonomous lanes separately.
- UI can visually reward a single theory: use key order, separate axes and no winning label.

## Phase Completion Checklist

- Real-run, compatibility, docs and research read checks complete or environment limitations explicitly recorded.
- Update only the Task 7–9 checkboxes in `index.md`.
