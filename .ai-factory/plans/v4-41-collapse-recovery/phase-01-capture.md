# Phase 1: Finalized collapse evidence

Plan: [index.md](index.md)  
Tasks: 1–2  
Depends on: none

## Objective

Obtain a bounded contiguous prefix of finalized characteristics and committed receipts, without making a simulation run conditional on the reporter.

## Current-Code Evidence

| Path | Symbols / contract | Use |
|---|---|---|
| `src/simulation/runner.py` | `initialize_finalized_boundary`, `export_resilience_boundary`, `run_tick`, `run`, `finish_run` | Body/key/asset projection already checks finalized boundary and objective hash; reuse without inheriting the disasters-only eligibility rule. |
| `src/simulation/resilience_evidence.py` | `ResilienceBoundaryFacts`, `OwnerLaneState`, `project_resilience_batch_events` | Detached body ↔ agent IDs, location region, owner-local keys, asset slots, migration receipts and exchange venue extraction. |
| `src/experiments/resilience_capture.py` | `run_with_resilience_capture` | Reference for terminal sampling after `finish_run`; do not consume the shock-aligned report. |
| `src/world/events.py` | `WorldEvent`, `OccurrenceContext`, `JourneyArrived`, `ExchangeCompleted`, `ResourceHarvested`, `ItemCrafted`, `Attacked` | Typed receipt allowlist. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/experiments/collapse_recovery_capture.py` | Create | Opt-in lifecycle adapter, immutable sealed input, receipt projection. |
| `src/analysis/collapse_recovery_evidence.py` | Create | Frozen narrow input models and validation independent of runner orchestration. |
| `tests/unit/test_collapse_recovery_capture.py` | Create | Prefix, attribution inputs, budgets, terminal and default-off tests. |

## Task 1: Define the detached evidence

1. Define `CollapseFrame` (the projection below plus `tick`, revision and run identity), `CollapseBatch` (tick and ordered normalized receipts), and `CollapseEvidence` (run/config IDs, captured and committed horizons, optional closed seal reason, region keys, source coverage, frames and batches) in `analysis.collapse_recovery_evidence`. The analysis model imports no experiments module. Retain the resilience body, infrastructure and scoped owner-key rows; drop stock amounts and held-item counts. Select availability from the accepted spec and finalized source flags, not the presence of events: migration requires `regions_migration`, exchange requires `resource_exchange_profile`, production checks `config.agents[0].cognition.production_catalog.recipe_count > 0` as in `SimulationRunner.from_config`, infrastructure reads the frame source flag. Population and the objective conflict receipt lane are not conditional on V4 flags.
2. Project latest `TickResult.events` only in the experiment adapter. Normalize to frozen rows with `event_id`, tick, sequence, closed receipt kind and only applicable body/region/location references. Keep typed death and cross-region journey arrivals, one `ExchangeCompleted` per receipt, successful `ResourceHarvested`, `ItemCrafted`, and committed `Attacked` (count only; no damage, tactical context or planning data). Retain bounded contact rows for Task 5 from delivered `Talk`/`Ask`/`Tell`, successful `Help`/`Feed`, and completed exchange parties. Normalize to registered **body** IDs; ambiguous identity is an attribution gap, never a distinct person. For speech, require actual addressed delivery, not attempts; retain parties only. Do not include content, item IDs, diagnoses, or private state.
3. Resolve regions through exact immutable `regions_migration.location_regions`; read `JourneyArrived.origin_location_id` and `destination_location_id` from the typed receipt (V4-40's normalized batch drops them). For exchange, production, conflict and optional regional death proximity use only `occurrence.origin_location_id` (the exchange venue/supply event precedent); if destination is present and differs, site is unassigned. No final-actor-location backfill. Missing region leaves the run-level count intact and makes the relevant regional lane partial rather than spreading the count. Do not multiply exchange count by bundle size. Static region set comes from config, not observed motion. Treat regional population as bodies at projected locations, not residence or membership; unmapped bodies make regional stock/rate exposure partial.
4. Validate exact clock integers, closed kinds, tuple ordering, unique IDs/slots, revision continuity and run identity. Receipts are ordered by `(sequence,event_id,kind,participant_id-or-empty)`; one event may emit separate measurement and lineage receipts and one arrival per unique participant. Frames cover `0..P`, batches `0..P-1`; an initial capture failure has `P=0` and no retained boundary (distinct from an observed boundary 0). Reject input above the caps before analysis. An unmapped reference affects its own lane/reason; inconsistent clock/run identity seals the prefix.

**Logging:** projection emits one DEBUG count summary per accepted window, not per row. On invalid input use bounded reason codes; never log raw event details, labels, owner/key identifiers or exception messages.

**Tests and acceptance:** `uv run --frozen --python 3.12.14 pytest tests/unit/test_collapse_recovery_capture.py -q`. Fixtures cover empty tick, malformed/incomplete locations, conflicting IDs, 1 completed multi-item exchange = 1 count, failed craft/harvest excluded, delivered vs undelivered speech, and journeys by participant with equal-region arrivals excluded.

## Task 2: Capture and seal a run once

1. Add `async run_with_collapse_recovery_capture(runner: SimulationRunner, *, capture: bool = False) -> CollapseCaptureResult`. Result holds the original runner result, `disabled | unsupported | captured | sealed | aborted | report_failed`, closed reason or `None`, and report or `None` (attach report in Task 7; keep evidence internal). Exact boolean only. When off, call `runner.run()` once without inspecting evidence. For opt-in support fresh tick-zero, empty-history runners with finite `1..512` tick horizon and max 128 registered bodies. There is no required shock, V4 flag, or specific schema beyond being accepted by `SimulationRunner`; missing channels are lane-local.
2. Follow `SimulationRunner.run` stop ordering exactly. Initialize and export boundary 0; sample each non-terminal committed tick after finalization and the terminal tick only after `finish_run`. Never sample an aborted tick. Require `frame.tick == last_tick_result.tick.value + 1 == runner.ticks_committed`, `frame.revision == last_tick_result.resulting_revision.value`, and `frame.history_length - previous.history_length == len(last_tick_result.events)`. Validate each raw event's run/tick/resulting revision and distinct event ID before normalization, and use `export_resilience_boundary()` for the objective hash check. Append the verified batch+frame atomically. Only exporter/projection/validation failures seal capture; initialization, runner execution and cancellation errors retain ordinary semantics. Do not retry capture after a seal.
3. Caps are 512 ticks, 128 bodies, 64 configured regions, 512 assets/frame, 4,096 normalized rows/frame, 262,144 cumulative normalized frame rows (including keys), 50,000 cumulative raw event occurrences before projection, and 100,000 cumulative normalized receipt rows. Check the normalized receipt budget incrementally as multi-participant arrivals expand; on overflow discard the whole current pair. Reusing `export_resilience_boundary()` inherits its 256 managed-stock cap and its frame cap **before** discarding stock rows; treat exporter overflow as `capture_cap`, with no exporter change. Report finalized prefix P and committed horizon H separately. Configure no sinks, arbiter, callbacks, stop selectors or auto-publication. On scientific abort return `aborted` with no report; healthy prefix with no full windows still yields a structured report after Task 7, not a false negative.

**Logging:** DEBUG tick/revision and row counts at completed windows; INFO disabled/unsupported/final disposition; WARNING first seal with stage and code only. Use stdlib logging configured by existing project settings.

**Tests and acceptance:** run the Task 1 command. Assert default-off runner invoked once; non-disasters opt-in accepted; initial and terminal sampled once; empty batches preserved; failure after the initial frame does not change output or stop reason. Cover a stale batch with matching revision but wrong tick, mismatched event identity, separate raw and normalized overflow, inherited stock overflow, projection error, abort and cancellation. Use side-effect spies; real-run parity is Task 8.

## Phase Risks and Mitigations

- Snapshot gaps could look like absence. Commit frames and batches together; stop retaining evidence at the first invalid boundary and leave the run untouched.
- A location key is not a polity and a travel arrival is not a residence change. Preserve that distinction at the source.

## Phase Completion Checklist

- Run focused tests; confirm no analysis logic entered the runner.
- Update Tasks 1–2 only in `index.md`.
