# Phase 3: Research report, qualification, and docs

Plan: [index.md](index.md)  
Tasks: 6–8  
Depends on: Tasks 1–5.

## Objective

Expose the ten ordered panels as a versioned programmatic artifact, prove them on the actual V4-39 flow, and document the interpretation limits.

## Current-Code Evidence

| Path | Symbols | Why it matters |
|---|---|---|
| `src/experiments/commons_governance_capture.py`, `src/simulation/journal.py` | `_seal_report`, canonical JSON/payload-hash helpers | Separate research siblings and strict identity precedents; never change journal dispatch. |
| `src/experiments/disaster_scenario.py`, `src/experiments/catalog.py` | `disasters_scenario`, `experiment_disasters`, `disasters_arbiter` | Existing paired shock/control design and ordinary runner binding. |
| `tests/unit/test_disaster_experiments.py` | `_stock_base`, `_loss_rule`, existing drought arm | Real v63 executable representative case and existing isolation/restore assertions. |
| `docs/development.md`, `.ai-factory/ARCHITECTURE.md` | Verification commands, baseline through V4-39 | Narrow qualification, coverage and unchanged compatibility. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/analysis/resilience_report.py`, `src/analysis/resilience_report_codec.py` | Create | Pure stable artifact builder and strict canonical bytes. |
| `src/experiments/resilience_capture.py`, `src/experiments/__init__.py` | Modify | Build and return a report after run; expose trusted programmatic entrypoint. |
| `tests/unit/test_resilience_report.py`, `tests/unit/test_resilience_disaster_run.py` | Create | Round-trip, malformed input, and real-run qualification. |
| `tests/architecture/test_resilience_boundaries.py` | Create | Read-only dependency, leak and version-pin gates. |
| `docs/societal-resilience.md`, `README.md`, `docs/development.md`, `docs/architecture.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/ROADMAP.md` | Create / modify at implementation | Documentation and accurate status/pins, never edited as part of this planning invocation. |

## Task 6: Build and encode the detached report

### Intent

Deliver a machine-readable result without changing run output or adding an API, filesystem store, observer view, or global metric.

### Implementation Steps

1. Add frozen `ResilienceReport` and `build_resilience_report(inputs)` to `analysis.resilience_report`. Root exact keys: `schema_version`, `policy_id`, `run_id`, `config_fingerprint`, `finalized_through`, `capture_through`, `capture_status`, `shock_status`, `non_applied_counts`, `schedule`, `episodes`. `schedule` is sorted by `(tick,rule_id)`, at most 32 entries, exact fields `tick`, `rule_id`, `status`, `outcome`, `receipt_event_id` (the latter two are null without a verified matching receipt). Each episode has `shock_tick`, sorted applied `receipts`, `immediate_state`, `windows`, and ten `panels`. `immediate_state` holds `boundary_tick`, `pre_boundary_tick`, and seven state panels in the same dimension order, with no flow panels: each leaf has `dimension`, `status`, `reason`, `owner_coverage`, `measures`. Its deltas compare to `pre_boundary_tick`; the nine regular window cells in each panel instead compare to the full pre window.
2. Serialize windows once per episode; each regular cell has exact keys `window_index`, `status`, `reason`, `expected_ticks`, `observed_ticks`, `owner_coverage`, `measures`. `owner_coverage` is null outside the three owner-based dimensions or at an unverified endpoint; otherwise use exact keys `eligible_owners`, `observed_owners`. Each measure has `metric`, `scope`, `unit`, `value`, `numerator`, `denominator`, `delta_from_baseline`, `reason` and `delta_reason` (validate nullability separately; a raw value can exist with an unavailable baseline). Scope is `null`, tagged region direction or tagged stock kind/unit. Incomplete cells have no numerical measure values; complete sibling measures can coexist with an off contribution submeasure. Receipts expose tick/sequence/event ID/kind/origin/outcome only; schedule matching uses a rule ID internally. Do not include event effect, target or private ledger IDs.
3. Use `schema_version="societal-resilience-report-v1"` and the fixed policy token from Task 1. Shock status: `observed` if an applied episode exists, `no_shock` only if the prefix is complete with no applied receipt and no `receipt_missing` schedule entry, and `unknown` otherwise. `captured` with empty episodes is a valid result; no placeholder episode at the scheduled tick. Disabled, unsupported, aborted or failed before boundary zero returns no report. Under a sealed prefix every emitted episode is based on observed receipts and has censored or partial follow-up as appropriate.
4. Add `encode_resilience_report(report) -> bytes`, `decode_resilience_report(payload) -> ResilienceReport` in the codec. Emit UTF-8 canonical JSON (`sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=True`, `allow_nan=False`, no final newline). Decode with duplicate-key rejection, exact key sets at each node, exact version, enum, integer/null and shape validation, run/cursor ordering and policy invariants, then require canonical byte equality. Cap input and output bytes at 8 MiB, episodes at 32 and each regular panel at exactly 9 cells. Validate `s`/`s+1` for the immediate point, fixed state-only dimensions, `observed_owners <= eligible_owners`, and schedule boundary/status/reference consistency against the verified horizon. Reject invalid unit/scope associations, duplicate measure keys, nonfinite or boolean numeric fields, unknown tags and aggregate-score fields. No write side effect, auto-publication, or reliance on an analysis identifier in an existing codec.
5. `run_with_resilience_capture` produces `ResilienceCaptureResult(result, status, report)`; keep its sealed inputs internal. Build and encode-validate only after completed scientific execution. If report production fails, return the unchanged `result`, status `report_failed`, no report, and log closed reason only. Export capture helper and result via the `experiments` facade; codec/report stay in the documented public analysis submodules.

### Required Interfaces and Contracts

- Use the canonical sibling result programmatically; callers may write bytes themselves. No database, API, observer, client, runner/result schema, metric catalog, or CLI additions. Default behavior is no invocation and no artifact.
- Source evidence: `## Original Request` (multidimensional time series and no universal score), project canonical/strict boundary rules, and the attached version baseline.

### Error Handling and Logging

Pure report/codec errors have a closed reason code. The experiment adapter emits one metadata-only warning if the report cannot be produced, never raw JSON, owner keys, underlying exception text, or payload-derived values. Over-limit outputs fail closed; no silent truncation presented as complete.

### Tests / Acceptance / Verification

`tests/unit/test_resilience_report.py`: exact golden minimal and ten-lane documents (including immediate point); byte-stable twins; no-shock vs unknown; each schedule status, a spontaneous receipt not satisfying a schedule and invalid status/coverage cross-fields; partial owner coverage round-trip without leaking keys; strict wrong-schema, wrong scope/unit, boolean, duplicate key, unknown key, noncanonical and extra score rejection; malformed windows and aggregate ordering; over-limit rejection; no forbidden payload fields.

Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_resilience_report.py tests/unit/test_resilience_capture.py -q`; valid reports round-trip canonically and corrupt documents are rejected.

## Task 7: Qualify against V4-39 and keep compatibility pinned

### Intent

Prove that the planned time series are connected to a real committed shock path and do not change it.

### Implementation Steps

1. In `tests/unit/test_resilience_disaster_run.py` reuse the existing test-only `_stock_base`/drought rule fixture: extract the named drought case factory to `tests/fakes/resilience_disaster_fixture.py` and point the existing V4-39 drought case at the same factory without changing its input bytes. Execute the unchanged seed-34 eight-tick v63 drought/control design with `disasters_scenario`, `materialize_assignments`, the normal `SimulationRunner.from_config`, and the existing V4-39 arbiter binding. Invoke resilience capture instead of the coordinator's terminal-only `run_all` for each assignment. Assert no control episode and a v63 committed `APPLIED` treatment episode at tick 2 with neither a complete eight-tick baseline nor follow-up. Verify the report's immediate WATER change from boundary 2 to 3 against an independent physical witness.
2. Extend that same fixture in a separate test to 24 ticks and schedule tick 8, keeping decisions arm-matched. Verify `[0,8)`, `[8,16)`, `[16,24)` and subsequent right-censored slots; compare published WATER measures with independently captured physical checkpoints/witnesses at boundaries 8, 9, 16 and 24. A return is legal but not required. Compare enabled/disabled runs using same run identity, seed, and normalized event/state/counter/stop parity.
3. For the no-episode contrast, execute the existing V4-39 `test_skipped_scheduled_intervention_recorded` configuration through capture (`not_applied` with its committed outcome and event ID). Then reuse the drought fixture with a legal tick-2 schedule and eight-tick horizon, `MortalityMode.ENABLED`, `stop_on_all_agents_terminal=True`, and the sole founder at `Health(1)` and `Thirst(100)`. Keep the normal runner and existing drought Wait arbiter. Default physical thirst damage makes tick 0 terminal; assert `ALL_AGENTS_TERMINAL` at boundary 1 before examining the report. Require `not_reached` with null outcome and event ID, no non-applied receipt increment, and no fabricated episode in either case. Do not schedule at `max_ticks`, which the runner validates against `max_ticks - 1`.
4. Add `test_resilience_boundaries.py`: assert `societal_resilience` remains detached/flagless, analysis modules have no runner, private world or cognition import, and no live world/cognition/observer/API/client path imports a report, decoder, experiment bridge, or reducers. Allow only the isolated inspect-only neutral runner export, not a tick-path read. Reassert 45 commands, 73 semantic types, 275 metrics, 17 contexts/12 owned flags, default v4/v2, latest v63, disaster 26/`v24` and prior physical pairs, pending v1 default/v7 latest, `/v1`, `observer-protocol-v1`, Alembic `0017`. Do not change V1 experiment gates or route counts.

### Required Interfaces and Contracts

- Real runner test must use a pre-existing V4-39 design, not only fabricated events; no production import from tests. Synthetic tests remain responsible for exhaustive coverage of optional dimensions and masked baselines.
- Requirement evidence: V4-39 baseline in `.ai-factory/ARCHITECTURE.md`; accepted-set/exact-key rules; no scientist-facing claim based only on synthetic fixtures.

### Error Handling and Logging

Tests assert truthful coverage distinctions and metadata-only diagnostics, not lack of diagnostic logging. Record test failures as failures rather than converting them to skipped qualifications.

### Tests / Acceptance / Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_resilience*.py tests/architecture/test_resilience_boundaries.py tests/unit/test_disaster_experiments.py tests/unit/test_disaster_replay.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/unit/test_alembic_head_pin.py -q`
- `uv run --frozen --python 3.12.14 pytest` (retain coverage); `uv run --frozen --python 3.12.14 ruff check src tests`; `uv run --frozen --python 3.12.14 mypy src tests`; `uv run --frozen --python 3.12.14 lint-imports`; `git diff --check`.
- Expected: real-arm windows/physics agree; baseline and flags-off gates pass; no authority leaks. Record PostgreSQL, Compose, Godot, browser and scale as out of changed surface or unexecuted with reason, not as passed.

## Task 8: Document use, comparability, and limits

### Intent

Make it practical to produce and interpret the report without turning a vector into a ranking.

### Implementation Steps

1. Run the mandatory `$aif-docs` checkpoint. Write `docs/societal-resilience.md`: runnable v63 programmatic capture and codec use, dimension definitions/units/denominators, a worked example where the immediate state dip is gone by the first full window, the schedule-state table, overlap/right-censoring, enabled-empty/disabled/partial distinctions with owner coverage counts, caps, and evidence sources.
2. Document why the no-shock arm has no fabricated clock, why single-run deltas are descriptive, why stock/asset replacement and same-key reacquisition are not continuous persistence, and why observed technology absence and living-cohort inequality do not establish extinction or welfare. Do not claim the runner supports durable subjective resume or that absent evidence means collapse.
3. Link the guide in `README.md`, add focused verification to `docs/development.md`, link the detached research seam in `docs/architecture.md`, and apply the V4-40 factual pin/status update to `.ai-factory/{DESCRIPTION,ARCHITECTURE,ROADMAP}.md` after verification. Do not close all of M8 or rewrite historical pin counts. Record actual verification outcomes in a receipt section of the plan index if claimed.

### Required Interfaces and Contracts

- Docs describe exactly the public programmatic helper, schema and opt-in/default policy; no nonexistent CLI command or endpoint. Source evidence: project docs policy and M8's remaining detached analysis direction.

### Error Handling and Logging

Examples must show `report is None` and sealed coverage how-to; never dump private evidence or add credentials, payload fingerprints, or prompts to logs.

### Tests / Acceptance / Verification

Add a docs-contract test in `tests/unit/test_resilience_report.py` checking the real callable, documented schema string, no-score caveat and all ten dimension IDs. Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_resilience_report.py -q` and `git diff --check`, and compare the example to the real-run test.

## Phase Risks and Mitigations

- A timestamped/different-run artifact is not byte-identical by default. Byte comparisons pin run ID, config, policy and input order.
- No positive recovery in an unassisted run is a legal result. Optional disabled lanes stay visible on the shared axis with null values.

## Phase Completion Checklist

- Tasks 6–8 satisfy acceptance, gates and actual documentation checkpoint; update checkboxes only in `index.md`.
