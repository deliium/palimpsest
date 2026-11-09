# Phase 6: Write pair, replay, observation

Plan: [index.md](index.md)
Tasks: 14-17
Depends on: Phases 3-5

## Objective

Activate reserved write pair `(EVENT_SCHEMA_REPLAY_V23, "v21")` with
effect-complete events, semantic aliases (pin 73), structure-kind codec gates,
runner snapshot branches, replay projection, and colocated observation.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/simulation/versioning.py` | reservation 39-49 | Claim target |
| `src/simulation/persistence.py` | `ACCEPTED_PERSISTENCE_CODEC_VERSIONS` 139-161; structure gates 1128-1144 | Accept v21; gate new kinds |
| `src/simulation/persistence.py` | `checkpoint_schema_for_production` 254+ | Priority branch |
| `src/simulation/runner.py` | codec `v20` branches ~7165-7316 | Must extend for v21 + infrastructure rows |
| `src/observer/version.py` | `SEMANTIC_EVENT_TYPES` / `SEMANTIC_TYPE_BY_KIND` | Alias without new semantics |
| `src/world/observations.py` | `ObservedCollectiveProject` | Observation precedent |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/world/events.py` | modify | `EVENT_SCHEMA_REPLAY_V23`; five event types |
| `src/observer/version.py` | modify | `SEMANTIC_TYPE_BY_KIND` aliases only |
| `src/simulation/persistence.py` | modify | Accept `v21`; checkpoint priority; structure gates; encode/decode infra |
| `src/simulation/runner.py` | modify | Thread active flag; v21 snapshot branches |
| `src/world/_replay.py` | modify | Project infrastructure events |
| `src/world/observations.py` + `_perception.py` | modify | `ObservedInfrastructure` |
| `tests/unit/test_infrastructure_replay.py` | create | Pair + round-trip |
| `tests/unit/test_infrastructure_observation.py` | create | Perception tests |
| Architecture pins | modify | v23/v21 accepted; semantics 73 |

## Task 14: Event schema replay-v23 and semantic aliases

### Intent
Define effect-complete events and map them onto existing observer semantics.

### Implementation Steps
1. Add `EVENT_SCHEMA_REPLAY_V23 = 23` and include in accepted schema sets.
2. Add events: `InfrastructureConstructed`, `InfrastructureDamaged`,
   `InfrastructureRepaired`, `InfrastructureDecayed`,
   `InfrastructureDestroyed` with asset summary fields (ids, kind, topology,
   locations, integrity, status, links, tick).
3. Wire emission from Tasks 7-9.
4. Add `SEMANTIC_TYPE_BY_KIND` aliases exactly as in `index.md` (constructed →
   `STRUCTURE_BUILT`, repaired → `STRUCTURE_REPAIRED`, damaged →
   `PUBLIC_GOOD_OPPOSED`, decayed → `ARTIFACT_DAMAGED`, destroyed →
   `ARTIFACT_DESTROYED`).
5. Do **not** append to `SEMANTIC_EVENT_TYPES` (remain length 73).
6. Forbid score fields on event details.

### Required Interfaces and Contracts
- Downstream checklist: claim reserved pair with effect-complete details.
- Semantics pin stays 73.

### Error Handling and Logging
- DEBUG emit counts by event type name.

### Tests
- Event validation; schema membership; semantic map; `len(SEMANTIC_EVENT_TYPES)==73`.
- `uv run pytest tests/unit/test_infrastructure_replay.py -k event -q`

### Acceptance Criteria
- Five events under schema 23; aliases only; no new semantic strings.

### Verification
- Event/semantic tests green.

## Task 15: Codec v21, gates, and checkpoint selection

### Intent
Select/encode `(23, v21)` when active and reject new structure kinds on older
codecs.

### Implementation Steps
1. Add `"v21"` to `ACCEPTED_PERSISTENCE_CODEC_VERSIONS`.
2. `checkpoint_schema_for_production(..., infrastructure_networks_active=False)`:
   if active, return `(EVENT_SCHEMA_REPLAY_V23, "v21")` **before**
   cultural_contact.
3. Structure-kind gates (mirror well/warning_post pattern):
   `ROAD` / `IRRIGATION` / `TRADE_POST` require codec `v21+`; reject earlier with
   safe ValueError + WARN.
4. Encode/decode `WorldState.infrastructure` rows on v21 snapshots; pre-v21
   payloads must not carry infra rows.
5. Extend `runner.py` persistence codec branch lists that currently top out at
   `"v20"` so v21 selects the correct snapshot fields (including infrastructure).
6. Do not create Alembic `0018`.
7. Log INFO `checkpoint_schema_selected … reason=infrastructure_networks_active`.

### Required Interfaces and Contracts
- Flag off never writes v23/v21.
- Epidemic reservation codec string `v22` remains unaccepted.

### Error Handling and Logging
- Fail closed on codec/schema mismatch and premature structure kinds.

### Tests
- Pair selection matrix; kind gates; infra absent on v20 restore; no 0018 file.
- `uv run pytest tests/unit/test_infrastructure_replay.py -k schema -q`

### Acceptance Criteria
- Active ⇒ (23,v21); new kinds gated; Alembic 0017 unchanged.

### Verification
- Schema/gate tests + `ALEMBIC_HEAD_REVISION == "0017"`.

## Task 16: Replay projection for infrastructure events

### Intent
Live/restored infrastructure parity.

### Implementation Steps
1. Implement `_project_infrastructure_*` helpers; share mutators with live path.
2. Round-trip digest equality for construct/damage/repair/decay/destroy and edge
   normalization.
3. Tombstones project as destroyed integrity 0.

### Required Interfaces and Contracts
- No UUID/`hash()`/wall-clock in projection.

### Error Handling and Logging
- Projection errors raise typed codes only.

### Tests
- Twin digests; full lifecycle sequence.
- `uv run pytest tests/unit/test_infrastructure_replay.py -q`

### Acceptance Criteria
- Replay restores exact asset set/status/integrity.

### Verification
- Replay module green.

## Task 17: Observation projection for colocated assets

### Intent
Agents perceive colocated/endpoint-visible infrastructure facts without scores;
cognition (Task 6) can act on them.

### Implementation Steps
1. Add `ObservedInfrastructure` DTO: kind, status, integrity, topology, optional
   endpoint-present boolean — no effect score fields.
2. Include assets at observer location or either edge endpoint.
3. Channel off ⇒ no infra observations.
4. Confirm proposers from Task 6 still compile against observation shapes.

### Required Interfaces and Contracts
- Forbidden fields absent; location-based only.

### Error Handling and Logging
- DEBUG observed_count.

### Tests
- Colocation/edge visibility; forbid-list; channel off empty.
- `uv run pytest tests/unit/test_infrastructure_observation.py -q`

### Acceptance Criteria
- Safe observation supports cognition starts without score leakage.

### Verification
- Observation tests green.

## Phase Risks and Mitigations
- Risk: adding new SEMANTIC_EVENT_TYPES.
  Mitigation: aliases only + length pin.
- Risk: missing runner v21 branch leaves infra out of checkpoints.
  Mitigation: explicit runner encode/decode steps + restore test.

## Phase Completion Checklist
- Tasks 14-17 done.
