# Phase 2: Indicators, collapse patterns and recovery

Plan: [index.md](index.md)  
Tasks: 3–4  
Depends on: Task 2

## Objective

Report eight separate observable trajectories on a fixed clock and identify sustained combinations of decline, with hysteresis and explicit uncertainty.

## Current-Code Evidence

| Path | Symbols / contract | Use |
|---|---|---|
| `src/analysis/resilience_windows.py` | `build_shock_windows` | Coverage semantics, not its clock: V4-41 does not require or align to a disaster. |
| `src/analysis/resilience_social.py` | `reduce_social` | Same-owner recognition and knowledge, living technique union, unsupported owner handling. |
| `src/analysis/resilience_physical.py` | Existing separate physical reducers | Keep flows, stock levels and infrastructure identity separate. |
| `src/simulation/agent_runtime.py` | `export_resilience_owner_keys` | `COMPLETE` including known-empty, `OFF`, `UNSUPPORTED`; these keys do not prove consensus or practice. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/analysis/collapse_recovery_indicators.py` | Create | Pure fixed-window measurement, coverage and exact comparison. |
| `src/analysis/collapse_recovery_episodes.py` | Create | Deterministic collapse and recovery episodes; no side effects. |
| `tests/unit/test_collapse_recovery_indicators.py` | Create | Eight axes, denominators, thresholds, geography and missingness. |
| `tests/unit/test_collapse_recovery_episodes.py` | Create | Transition table, hysteresis, prefix and no-gap properties. |

## Task 3: Reduce eight independent indicators

Implement `reduce_collapse_windows(evidence: CollapseEvidence) -> tuple[CollapseWindow, ...]`. Scopes are the whole run and each configured region. Use fixed 32-tick half-open windows from tick 0, never renumber; flows count events in `[start,end)`, exposure is sum of living bodies at start-of-tick boundaries, stocks use boundary `end`. Emit a final nonempty partial interval when available; identify missing range `[P,H)` separately in report metadata. `complete` permits known-zero counts; `unavailable/channel_off`, `partial/{projection_gap,unresolved_attribution}`, and `censored/{run_end,capture_end}` never vote. Value/denominator fields of partial lanes may disclose observed counts only, not use them as totals. Keep denominators, comparison baseline, and supporting lane codes inspectable. No division by zero, no cross-scope normalization.

| Axis (group) | Window measurement and stress trigger against reference window B |
|---|---|
| `population_decline` (people) | Living bodies at end; B ≥4 and current ≤70% of B. Also show deaths where supported. |
| `institutional_failure` (continuity) | **Recognition lapse proxy**, not objective institutional failure: baseline recognized `(body, concept)` pairs among owners still living and in scope at comparison end. With ≥2 eligible B pairs, stress when ≤70% still recognized. Record continuity throughout all boundaries separately, and death/movement exclusions separately; never convert them to recognition lapse. |
| `knowledge_loss` (continuity) | Baseline owner/content pairs among surviving in-scope carriers, same ≥2 and ≤70% rules. Also show baseline living technique union retained/absent/reobserved; do not add a ninth vote. |
| `trade_disruption` (material) | `ExchangeCompleted` per person-tick. Enabled only with structured exchange configured (`resource_exchange_profile`); B ≥4 receipts and positive exposure in both windows; current rate ≤70% of B. |
| `infrastructure_decay` (material) | B ≥2 distinct operational asset IDs in scope; stress if ≤70% of those IDs still operational. Distinguish surviving original assets and replacements; no double counting route assets: regional attribution uses the asset's primary `location_id`, never both endpoints. |
| `migration` (people) | Per region, outbound minus inbound participant arrivals per person-tick; include raw arrivals in both directions. Stress when at least 3 outbound arrivals, positive net outbound, and the rate has increased by ≥50 per 1,000 person-ticks vs B. Run-wide publish gross cross-region arrivals, but never vote there on net outflow. No region spec means unavailable. |
| `conflict` (security) | Count-only committed `Attacked` receipts per person-tick. Stress at ≥3 receipts and an increase of ≥25 per 1,000 person-ticks vs B. Never infer faction membership or operational intent from the receipt. |
| `production_decline` (material) | Count successful harvest/craft completions by verb, then total completions per person-tick, not units of output. Default rule-enabled empty is known-zero; if production rules are absent, unavailable. B ≥4 completions and positive exposure in both windows; current rate ≤70% of B. |

Use exact integer cross-products for thresholds, no floats in comparisons. Report rates as signed milli, integer floor on the absolute ratio and apply sign afterward. Axis comparison returns `stressed`, `not_stressed`, or `not_comparable` with exact denominators; track eligibility separately from physical/source coverage. For social axes, source-off all → unavailable; mixed off/unsupported/missing eligible owners → partial. A baseline owner switching source mode or unmapped cannot be classified as loss. Technique absence needs complete coverage at every boundary in two consecutive complete windows and a nonempty baseline; label `observed_loss`, not extinction. Same-key return after observed loss is `reobserved`, not proven rediscovery. Region union absence can coexist with run-wide retention.

**Logging:** reducers are pure; the composition layer logs window and status counts only. No hidden exceptions-as-zero fallback.

**Tests and acceptance:** `uv run --frozen --python 3.12.14 pytest tests/unit/test_collapse_recovery_indicators.py -q`. Table-test exact threshold and neighboring value for all axes; include exposure change without rate change, sole migration/outflow vs global population, mixed units, infrastructure replacement, regional ambiguity, no baseline, enabled-empty vs off, extinct vs unsupported carriers, uninterrupted retention vs missing middle vs reobservation. A population fall alone or several same-group stresses cannot satisfy Task 4.

## Task 4: Detect episodes with recovery and uncertainty

Implement `derive_collapse_episodes(windows) -> tuple[CollapseEpisode, ...]`. Scan each scope independently in chronological order. A qualifying window has ≥5 comparable axes, ≥3 stressed axes spanning ≥2 of the four named groups, and ≥1 stressed axis outside people. Count distinct axes, not receipts. Record candidate/confirmation boundaries, exact comparison basis, and contributing axes. The algorithm is a descriptive study policy (`collapse-recovery.v1`), not a causal model.

1. Compare first eligible window against the immediately preceding complete window B; if qualifying, freeze B and set pending. Next adjacent full window must qualify against frozen B and share ≥2 stressed axes from ≥2 groups with the pending window. If it does not, clear pending and retest the current window once using its immediate predecessor as B. Do not backdate confirmation: onset and confirmed-at boundary are separate. Insufficient comparable axes never means “no collapse.”
2. Confirmed episode stays open with fixed B. Store the union of the axes stressed in either confirmation window and add newly stressed axes in subsequent assessed windows. For retention/asset axes freeze the exact comparison set on the first stress (including a stress in the pending window); use it for subsequent votes and recovery in this episode. Pairs no longer observable because a carrier died, left scope, or lost usable coverage are not proof of lapse or repair; mark that frozen-axis comparison not comparable. Do not freeze the comparison sets of unstressed axes. A recovery candidate requires ≥5 comparable axes, no stressed axes in the current window, and all previously stressed axes clearing the exit band (decline ratios ≥90% of B, adverse increases ≤20 per 1,000 for migration and ≤10 for conflict). Use exact comparisons; two adjacent candidates confirm `recovered`. Regrowth and replacement can appear in raw panels without reclassifying them as continuity.
3. Use this order for every open episode: if the next window is nonadjacent/right-censored, fewer than five axes are comparable, or any previously stressed axis is not comparable against its episode basis, terminate as `censored` with the last assessed boundary and a closed reason. Otherwise assess: if a comparable window fails the exit band or shows renewed stress, reset only the recovery streak and keep the episode open; if it passes, increment the streak. After censoring, the first subsequent full window may serve as a new baseline but cannot qualify using evidence from before the censor. A healthy run ending at an exact boundary with no recovery confirmation remains `ongoing_at_end`; a sealed prefix or final incomplete window censors already-open episodes. An unconfirmed onset stays only a flagged window, never an episode. No labels feed simulation and no scalar score is generated.

**Logging:** no logs inside transition logic; report composition logs counts by closed disposition at DEBUG. Validation failures use code only.

**Tests and acceptance:** `uv run --frozen --python 3.12.14 pytest tests/unit/test_collapse_recovery_episodes.py -q`. Cover simultaneous stress, flicker, one group only, nonshared consecutive votes, rolling versus frozen baseline, exact and incomplete end, recovery and repeat episodes. Compare three interruptions of a one-window recovery streak: fully comparable relapse (reset), unstressed lane missing while five axes remain comparable (still assess), and stressed frozen carrier exiting scope or source going off (censor even with five other comparable axes). Assert historical window votes do not change when later evidence is appended; only final disposition may be refined.

## Phase Risks and Mitigations

- Sparse activity, growth and population decline can mislead. Publish raw counts, exposures and missingness alongside the locked study thresholds.
- Regional outflow can be circular travel; keep it a direction-specific receipt proxy, not forced migration, motive, or census.

## Phase Completion Checklist

- Verify both pure test suites and update Tasks 3–4 in `index.md`.
