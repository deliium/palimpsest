# Phase 5: Subjective Route Knowledge

Plan: [index.md](index.md)
Tasks: 14-16
Depends on: Phase 4 (Tasks 10-13)

## Objective

Let agents form fallible owner-scoped route-quality beliefs from their own
observations and memories, and plan bounded paths over those beliefs without
reading `WorldState`, the objective route channel, infrastructure assets, or
another owner's knowledge. No new command, ledger, or cognition mode is added:
the existing `regional_migration` destination lane is extended.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/agents/cognition/regional_migration.py` | `destination_memory_trace` 65-198; `known_destination_ids` 201-272; `destination_action_biases` 275-466 | Existing owner-scoped destination evidence, bounded known-route adjacency, and first-hop bias. |
| `src/agents/cognition/memory.py` | destination memory writes 1273-1300; destination recall 231-370 | Direct exits already become memory traces with `direct`/`destination`/`route` tags. |
| `src/agents/cognition/migration_displacement.py` | `RouteBeliefBasis` 119-127; `RouteBeliefStatus` 129-136; `RouteBeliefRow` 706-754; `_update_route_beliefs` 2953-3045; `migration_displacement_action_biases` 3823-3923 | Existing route belief schema and next-hop bias; it consumes `VisibleExit` duration/fatigue automatically. |
| `src/agents/cognition/loop.py` | migration preparation 3258-3329; regional preparation 3258-3329 | Regional biases are prepared from `observation.exits` and passed to selection. |
| `src/agents/cognition/deliberation.py` | regional bias setup 657-712; pairwise selection 2521-2526 | Biases are additive `future_id -> float`; only adjacent `move-N` futures receive them. |
| `src/agents/cognition/contracts.py` | `Perspective` 142-201; ownership checks 316-473 | No new ledger is needed; destination memories already flow through `snapshot.memories`. |
| `src/agents/cognition/prospective.py` | `_reject_objective` 184-192; `rollout_prospective` 879-1099 | Existing no-objective-input discipline must be preserved. |
| `src/world/observations.py` | `PERCEPTION_FIELD_ACCESS` 135-163; `remote_topology` omitted line 160 | Cognition sees adjacent exits only; no global graph. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/agents/cognition/regional_migration.py` | modify | Persist route-quality concepts; parse beliefs; add subjective path costs and first-hop biases. |
| `src/agents/cognition/memory.py` | verify | No schema change expected; destination traces carry the new concepts. |
| `src/agents/cognition/loop.py` | modify | Pass route-quality-aware memories and bounded hop limit; no new mode. |
| `src/agents/cognition/deliberation.py` | verify | Existing regional bias plumbing is sufficient. |
| `tests/unit/test_travel_network_cognition_memory.py` | create | Belief persistence and owner isolation. |
| `tests/unit/test_travel_network_cognition_planning.py` | create | Bounded path planning and fallibility. |
| `tests/architecture/test_travel_network_boundaries.py` | create | No objective access from cognition. |

## Task 14: Persist route-quality beliefs in destination memories

### Intent

Turn the current objective exit facts into owner-scoped, stale-able beliefs.
The memory is evidence, not truth: it may disagree with the current route.

### Implementation Steps

1. In `destination_memory_trace`, extend the concept tuple with:
   - `route_status:<open|restricted|closed>`
   - `route_seasonal_availability:<open|restricted|closed>`
   - `route_blockage_cause:<none|weather|seasonal|hazard>`
   - `route_capacity:<int>`
   - `route_risk:<float>` formatted `.6f`
   - `route_infrastructure_quality:<float>` formatted `.6f`
   Only add them when the corresponding `VisibleExit` fields are present.
2. Add relations for each concept using existing `destination_*` predicates:
   `destination_route_status`, `destination_route_availability`,
   `destination_route_blockage`, `destination_route_capacity`,
   `destination_route_risk`, `destination_route_quality`.
3. Keep mention ids deterministic:
   `c-status`, `c-availability`, `c-blockage`, `c-capacity`, `c-risk`,
   `c-quality`.
4. Do not add route fields to `VisibleExit` parsing here; Task 11 already
   guarantees the values.
5. Do not import `world.travel_network`, `world.infrastructure`, or
   `world._state` in cognition. Accept only `VisibleExit`/`Observation`.
6. Ensure the memory trace remains within existing mention/concept limits; if
   the limit is reached, drop optional route concepts deterministically from the
   end and log `WARN destination_route_concepts_truncated count=<n>`.
7. Add a policy constant:
   `REGIONAL_ROUTE_QUALITY_POLICY_VERSION = "regional-route-quality.v1"` and
   include it in destination lane identity only if needed; prefer not to change
   existing lane ids to preserve replay compatibility.

### Required Interfaces and Contracts

- Concepts are stable tokens, bounded by existing `MemoryTrace` limits.
- Route values are numeric/closed enum strings only; no free text.
- A trace with no route fields remains valid and unchanged.
- The trace owner is the observing agent; no peer traces are accepted.

### Requirement Evidence

- `src/agents/cognition/regional_migration.py` 65-198; `src/agents/cognition/memory.py` 1273-1300; index belief row.

### Error Handling and Logging

- Missing paired fields raise the existing
  `"visible exit lacks regional travel metadata"` error.
- `DEBUG destination_route_belief_persisted owner_id=<id> destination=<id> status=<s>`.
- No route payload bodies or peer ids.

### Tests

- `tests/unit/test_travel_network_cognition_memory.py`:
  - trace includes all route concepts when present;
  - legacy exit without route fields yields legacy concepts;
  - deterministic mention ids/order;
  - owner mismatch rejection;
  - foreign-owner traces rejected by consumers;
  - concept truncation warning path.
- `uv run pytest tests/unit/test_travel_network_cognition_memory.py tests/unit/test_regional_migration_cognition.py -q`

### Acceptance Criteria

- Route quality is persisted as owner-scoped memory evidence.
- No objective channel is imported or copied.
- Legacy traces remain valid.

### Verification

- `uv run pytest tests/unit/test_travel_network_cognition_memory.py tests/unit/test_regional_migration_cognition.py -q`
- Expected: all pass.

## Task 15: Plan paths from bounded subjective route beliefs

### Intent

Use believed route quality for bounded multi-hop planning while only selecting
the first visible adjacent hop. Stale, closed, and high-risk beliefs must change
the choice without granting objective authority.

### Implementation Steps

1. In `destination_action_biases`, build `route_edges` from memory concepts:
   - duration/fatigue as today;
   - add `status`, `availability`, `capacity`, `risk`, `quality`;
   - default missing fields to unknown/open;
   - confidence decays with age as today and is discounted for communicated
     evidence.
2. Compute believed edge cost:
   `1.0 + duration/20.0 + fatigue/100.0 + risk*3.0 + (1.0 - quality)*0.5 + (1.0 - confidence)*0.5`.
   Add `+10.0` for believed `closed`, `+1.0` for `restricted`.
3. For the current visible exit, use the current observation condition (fresh)
   rather than stale memory; for non-visible hops, use memory beliefs.
4. Keep the existing bounded Dijkstra resource-reachability pass, but skip
   believed `closed` edges and cap hops at `hop_limit`.
5. Add first-hop choice biases for both movement directions:
   - for each `move` future, compute the best believed path to a resource need
     using the extended costs;
   - penalize a first hop whose believed status is `closed` (`-2.0`) or
     `restricted` (`-0.5`);
   - for each `transport` future, additionally penalize (`-2.0`) when the
     believed capacity is less than the 2 participants;
   - keep the final score clamped `[-0.25, 0.75]` as today.
6. If a visible exit has no route fields but a memory belief exists, use the
   fresh duration/fatigue and do not invent status/capacity.
7. If no belief exists, return no bias for that future (unknown is not open).
8. When the agent is travelling, keep the existing wait bias.
9. Never emit a multi-step route command; only bias existing adjacent `move-N`
   futures.

### Required Interfaces and Contracts

- Bias keys are existing future ids; values are finite floats.
- Only adjacent `move` futures receive bias.
- `closed` beliefs are strong penalties, never hard rejections: admission still
  owns the objective truth.
- `restricted` beliefs are mild penalties.
- Communicated evidence remains discounted; same-root retellings are not
  independent corroboration (existing policy).

### Requirement Evidence

- `src/agents/cognition/regional_migration.py` 201-466; `src/agents/cognition/deliberation.py` 657-712/2521-2526; index belief/planning rows.

### Error Handling and Logging

- Foreign-owner memory raises `ValueError`.
- `DEBUG route_quality_bias owner_id=<id> tick=<t> known_edges=<n> closed_edges=<n> biases=<n>`.
- Never log memory bodies, concepts, or paths at INFO.

### Tests

- `tests/unit/test_travel_network_cognition_planning.py`:
  - open direct exit chosen over closed believed alternative;
  - restricted believed route penalized but not rejected;
  - high-risk believed route avoided;
  - low-capacity belief penalizes a transport future but not a move future;
  - stale belief loses influence over time;
  - communicated belief discounted;
  - no belief → no bias;
  - only first hop biased;
  - owner isolation;
  - no `WorldState`/asset import.
- `uv run pytest tests/unit/test_travel_network_cognition_planning.py tests/unit/test_migration_displacement_cognition.py -q`

### Acceptance Criteria

- Planning uses bounded owner beliefs and current adjacent facts only.
- Inaccurate beliefs are legal and produce different choices.
- No new command or omniscient planner.

### Verification

- `uv run pytest tests/unit/test_travel_network_cognition_planning.py tests/unit/test_migration_displacement_cognition.py -q`
- Expected: all pass.

## Task 16: Guard subjective route knowledge against objective leakage

### Intent

Prove the boundary mechanically: cognition never imports objective route state,
and the migration-displacement ledger continues to consume only owner-visible
facts.

### Implementation Steps

1. Add `tests/architecture/test_travel_network_boundaries.py` with AST/import
   checks:
   - `agents.cognition.regional_migration` does not import
     `world._state`, `world._infrastructure`, `world._travel_network`,
     `world.travel_network`, or `simulation`.
   - `agents.cognition.migration_displacement` remains free of objective route
     imports.
   - No cognition module reads `state.travel_network` or
     `RouteCondition`.
2. Extend the existing migration-displacement cognition tests to assert that
   route beliefs see the adjusted `VisibleExit` duration/fatigue after a
   condition change, without importing `RouteStatus`.
3. Add a test that a stale memory belief contradicts a fresh observation and
   the fresh adjacent exit wins for the first hop, while the stale belief still
   influences a non-visible multi-hop cost.
4. Confirm `prospective._reject_objective` still rejects objective inputs.
5. If any existing import is already permitted by a documented facade, record
   the exception in the test allowlist with a reason; do not widen it silently.

### Required Interfaces and Contracts

- No new owner ledger, per-agent mode, or checkpoint schema.
- `migration_displacement.RouteBeliefRow` is unchanged; it already consumes
  `VisibleExit` duration/fatigue, which now include condition adjustments.
- Boundary tests fail closed on new objective imports.

### Requirement Evidence

- `src/agents/cognition/regional_migration.py` imports; `src/agents/cognition/prospective.py` 184-192; index belief row.

### Error Handling and Logging

- Architecture test failures report file/line/import only.
- `INFO route_quality_boundary_checks modules=<n>` at test collection only.

### Tests

- `tests/architecture/test_travel_network_boundaries.py`
- `tests/unit/test_migration_displacement_cognition.py` extension
- `uv run pytest tests/architecture/test_travel_network_boundaries.py tests/unit/test_migration_displacement_cognition.py -q`

### Acceptance Criteria

- Cognition has no objective route access.
- Fresh local observation outranks stale belief for the first hop.
- Migration-displacement behavior remains valid and owner-scoped.

### Verification

- `uv run pytest tests/architecture/test_travel_network_boundaries.py tests/unit/test_migration_displacement_cognition.py -q`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: adding concepts exceeds memory mention limits.
  Mitigation: deterministic optional-concept truncation with a WARN.
- Risk: stale beliefs accidentally become objective truth.
  Mitigation: admission remains authoritative; tests require a closed belief to
  be penalized, not enforced.
- Risk: duplicated route ledgers with V4-14.
  Mitigation: reuse `RouteBeliefRow` only as-is; route-quality evidence lives in
  destination memories, not a new ledger.

## Phase Completion Checklist

- Every task above satisfies its acceptance criteria.
- `index.md` checkboxes for Tasks 14-16 are updated after verification.
- No phase file contains task checkboxes.
