# Phase 4: Report, qualification and documentation

Plan: [index.md](index.md)
Tasks: 7–9
Depends on: Tasks 3–6

## Objective

Deliver the opt-in report with verifiable bytes and a non-interference receipt, without changing protocols, analytics catalog, or world mechanics.

## Current-Code Evidence

| Path | Symbols / contract | Use |
|---|---|---|
| `src/analysis/resilience_report_codec.py` | `encode_resilience_report`, `decode_resilience_report` | Strict canonical sibling artifact, bounded decode and byte round-trip. |
| `src/experiments/disaster_scenario.py` | `disasters_scenario`, `experiment_disasters` | Existing v63 accepted specimen; real runs need not demonstrate collapse. |
| `tests/fakes/resilience_disaster_fixture.py` | `drought_stock_base`, `drought_schedule_entry` | Existing real-world-state simulation fixture, not an input invented to force collapse classification. |
| `tests/architecture/test_resilience_boundaries.py` | Capture boundary assertions | Model for import, wiring and evidence leakage checks. |
| `.ai-factory/ARCHITECTURE.md` | Current baseline through V4-40 | Legacy pins and separated authorities. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/analysis/collapse_recovery_report.py`, `src/analysis/collapse_recovery_report_codec.py` | Create | Compose finalized analysis, strict canonical programmatic contract. |
| `src/experiments/collapse_recovery_capture.py` | Modify | Publish report after the normal finish; encode once to check budget before returning it. |
| `tests/unit/test_collapse_recovery_report.py`, `tests/unit/test_collapse_recovery_runner.py`, `tests/architecture/test_collapse_recovery_boundaries.py` | Create | Schema, actual run parity, positive mechanism and dependency proofs. |
| `docs/collapse-recovery.md`, `README.md`, `docs/development.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/DESCRIPTION.md` | Create first, update others | Describe new research contract and verification. |

## Task 7: Build the canonical programmatic report

1. Implement `build_collapse_recovery_report(evidence: CollapseEvidence) -> CollapseRecoveryReport`, `encode_collapse_recovery_report(report) -> bytes`, and `decode_collapse_recovery_report(payload: bytes) -> CollapseRecoveryReport`. Header exact keys: `schema_version`, `policy_version`, `run_id`, `config_fingerprint`, `window_ticks`, `committed_through`, `captured_through`, `capture_reason`, `windows`, `episodes`, `lineage`. Constants are `collapse-recovery-report-v1`, `collapse-recovery.v1`, 32 ticks. Give nested rows frozen exact typed schemas for the counts, dates, codes, denominators and references specified in Tasks 3–6. Include window scope and bounds, availability, vote and baseline reference, episode onset/confirmed/disposition boundaries, node/edge coverage and continuity, and positive edge-to-episode references. Use run scope before regions, then lexically by region ID and chronologically within scope; measures use the Phase 2 table order. Sort episodes by `(scope, onset_end)`, graph nodes by `(window_start, node_id)`, edges by `(source_window_start, from_id, to_id)` and gap/ambiguity summaries by window/boundary.
2. Validate closed keys/codes, bounds, exact booleans and ints without coercion, unique rows, and resolving in-report references. Check `captured_through <= committed_through`; full windows must end within capture; partial/unknown measures cannot vote. Episode baseline, onset and confirmation must reference full, same-scope, consecutive windows; both confirmation windows must carry the required stress votes; recovery must reference two adjacent passing assessments strictly after confirmation. Distinguish standalone per-window observations from episode-basis assessments when a window is retried against a different baseline; do not silently overwrite the first comparison. Check edge windows are adjacent and known, edge types match component degrees (no one-child `split_successor`), and branch-loss references follow two actual `continuation` edges starting at or descended from the named split child. No need to reconstruct private rosters when decoding: validate only public invariants and counts. Represent missing measures and absent references as null, not zero. Use canonical UTF-8 JSON and decode→encode byte equality; recursively reject duplicate keys, noncanonical payloads and extra fields. Bound bytes to 8 MiB before decoding or returning; never return a clipped artifact with references removed. No raw party/body ID, concept/technique key, item or utterance in public bytes; IDs are scoped report IDs, region IDs, run/config IDs, or graph IDs only.
3. After `finish_run` and final sample, invoke report composition in the experiment adapter. Capture failures may return a sealed truthful prefix report; validation or report size failure returns `report_failed`, unchanged run result, and no partial artifact. No auto-persistence, routes, cursors, CLI exposure, metric registration, or client panel. Caller may explicitly save encoded bytes. Do not re-expose internal capture evidence.

**Logging:** INFO disposition and counts, WARNING for closed validation/encoding failure; DEBUG aggregate coverage and canonical byte count. No raw payloads or exception text.

**Tests and acceptance:** `uv run --frozen --python 3.12.14 pytest tests/unit/test_collapse_recovery_report.py -q`. Canonical golden includes all eight axes, episode, split, continuity/unknown, confirmed branch loss and recovery. Reject extra score/authority fields, boolean-as-int, noncanonical order, duplicate keys, out-of-range bounds, dangling/gap edges and oversize input. Mutate canonical payloads to a one-child split, a censored baseline, recovery with a missing supporting assessment, or branch loss through a merge; reject each on semantics rather than encoding. Verify private fixture strings are not emitted. Require byte repeatability and decode round-trip.

## Task 8: Qualify real-run parity and boundary isolation

1. In `test_collapse_recovery_runner.py`, mirror setup in `tests/unit/test_resilience_disaster_run.py`: construct `disasters_scenario(drought_stock_base(max_ticks=24), treatment_entry=drought_schedule_entry())`, take the scheduled `materialize_assignments` arm, create fresh runners with identical assignment/config/seed/run ID, and apply identical `disasters_arbiter` and `bind_disasters_experiment_runner` on both. The fixture owns the binding; collapse capture installs nothing. Assert identical canonical committed events, stop reason, `objective_state_hash`, serialized config and result; assert finalized terminal coverage and short-window censoring rather than demanding collapse. Test no-disasters/legacy capture and injected projection/report failure parity separately. Add a separate test that patches `WorldEngine.export_events` on the class to raise, then runs capture and encodes the report without history export. Test parity can inspect histories outside that guard.
2. Use two bounded deterministic detached fixtures through the real typed receipt projector and reducers, with no scripted simulation outcome. Episode fixture: `[0,32)` baseline with 12 living bodies, two operational assets, positive exposure and at least four exchanges and harvest/craft completions; `[32,64)` and `[64,96)` with eight living bodies, one of those assets operational, and zero production completions. Keep exchange rate and conflict non-stressed (choose integer counts proportional to measured exposure for exchange), social lanes unavailable, and keep five axes comparable. At `[96,128)` and `[128,160)` restore 12 living bodies, both original assets and baseline production rate. Assert exactly population/infrastructure/production votes on both stress windows, onset at 64, confirmed at 96, recovered at 160, and a cut at 128 never claims recovery. Pin raw counts and denominators. Use the Phase 3 eight-member receipt topology in a separate graph fixture, with sibling retention, same-holder recognition, two continuation windows for branch loss and an unavailable-middle variant; assert no invented episode or lineage over a gap. Exercise the conflict indicator with aggregate synthetic counts only. Label these mechanism tests, not prevalence or causality evidence. A quiet or fully unavailable live run is valid.
3. Add AST checks that only trusted experiments import the capture entry point, none of simulation/world/cognition/memory/observer/API/persistence imports the new analytical modules, and no new registry, config, migration, command, event, codec, or protocol is changed. Keep V1 A–E and V2 scientific invariant tests green. Record commands/results separately from unexecuted environment lanes.

**Logging:** tests use fixture logs or a caplog spy to ensure payload-free reason logging; do not introduce global logging controls.

**Verification and acceptance:**

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_collapse_recovery*.py tests/architecture/test_collapse_recovery_boundaries.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/unit/test_alembic_head_pin.py -q
uv run --frozen --python 3.12.14 pytest tests/unit tests/architecture -q
uv run --frozen --python 3.12.14 ruff check src/analysis src/experiments tests/unit tests/architecture
uv run --frozen --python 3.12.14 mypy src
uv run --frozen --python 3.12.14 lint-imports
```

Expected: capture-off/on/failure parity, no boundary regression, no new static failures, coverage enabled. Record any baseline or environmental failure truthfully. DB, client and scale certification are out of scope, not silently passed.

## Task 9: Document the evidence and limits

1. Run the mandatory `$aif-docs` checkpoint. Add `docs/collapse-recovery.md` and link from `README.md`; document opt-in example, policy thresholds, effect of flags and gaps, canonical programmatic report, interpretation, caps and test commands. Include one worked split with continuing institutions in one successor and a technique missing from another. Describe region presence vs residence, report proxies vs institutions, and local observed technique loss vs extinction.
2. Add focused commands to `docs/development.md` and a short detached composition entry to `.ai-factory/ARCHITECTURE.md` and `.ai-factory/DESCRIPTION.md`. Keep current numerical pins unchanged. Roadmap milestone remains open; update landing status only through the owning roadmap workflow with verified evidence and no claim that V4-41 closes M8.

**Logging:** document closed capture/report reason codes without data-bearing examples. No runtime changes.

**Tests and acceptance:** visually check relative Markdown links and example calls against actual exports; run `git diff --check`. Document bounded/quiet cases as valid outcomes and state that no `CivilizationCollapsed` flag, score, root-cause diagnosis, authority, or agent input exists.

## Phase Risks and Mitigations

- A canonical report can be mistaken for an authoritative state change. Keep it apart from runner, persistence and API schemas and document the interpretation explicitly.
- An engineered fixture can be mistaken for qualified emergence. Publish real-run parity and synthetic mechanism verification separately.

## Phase Completion Checklist

- Verify artifact round-trip, real runner parity, static/boundary checks, and documentation.
- Update Tasks 7–9 only in `index.md`; record the actual lanes exercised.
