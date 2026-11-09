# Phase 3: Construction bridge

Plan: [index.md](index.md)
Tasks: 5-7
Depends on: Phase 2 / Tasks 3-4

## Objective

Extend collective-project start/contribute/complete (including serialization and
cognition proposers) so eligible completed work registers persistent `infra-`
assets and road Repair anchors without adding AgentCommand types.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/world/actions.py` | `StartCollectiveProject` 777-798 | Allow-list + target field |
| `src/world/_operations.py` | `_StartCollectiveProjectOp` 493-499, 1065-1071 | Op must carry target |
| `src/simulation/serialization.py` | encode/decode 2593-2594, 2923-2925 | Wire compatibility |
| `src/world/collective_projects.py` | `CollectiveProject` 284-301 | Needs `target_location_id` |
| `src/world/_collective_projects.py` | `classify_collective_start` 91-129; `mutate_collective_start` 176+ | Admission + mutate |
| `src/agents/cognition/collective_projects.py` | `_START_KIND` 28-34 | Proposer extension |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/world/actions.py` | modify | New kinds + `target_location_id` |
| `src/world/_operations.py` | modify | Op field + mapping |
| `src/simulation/serialization.py` | modify | Optional `target_location_id` encode/decode |
| `src/world/collective_projects.py` | modify | Catalog rows; `CollectiveProject.target_location_id` |
| `src/world/_collective_projects.py` | modify | Classify/mutate/complete hooks |
| `src/world/_infrastructure.py` | modify | `register_from_completed_project` |
| `src/world/events.py` | modify | Carry target on create where needed |
| `src/agents/cognition/collective_projects.py` | modify | Focus codes + road target selection |
| `src/simulation/engine.py` | modify | Bind `_infrastructure_networks_active` |
| `tests/unit/test_infrastructure_construction.py` | create | Pipeline tests |
| `tests/unit/test_infrastructure_cognition.py` | create | Proposer tests |

## Task 5: Extend kinds and full start pipeline

### Intent
Make edge-capable starts legal through the entire command→op→serialize→mutate
path while preserving legacy payloads.

### Implementation Steps
1. Extend `CollectiveProjectKind` + `StartCollectiveProject` allow-list with
   `road`, `irrigation`, `trade_post`, `large_shelter`.
2. Add `target_location_id: EntityId | None = None` to
   `StartCollectiveProject`, `_StartCollectiveProjectOp`, and
   `CollectiveProject`.
3. Validation: edge kinds require target; node kinds forbid target.
4. Serialization: encode target only when present; decode missing key as `None`
   (legacy clients unbroken).
5. `classify_collective_start`: when infrastructure active, enforce adjacency and
   duplicate-edge rejection; when inactive, reject new kinds with
   `infrastructure_networks_inactive`; preserve well/warning_post
   `public_goods_channel_off` gate.
6. `mutate_collective_start` stores `target_location_id` on the open project.
7. Mirror labor/materials from locked infrastructure catalog into collective
   catalog rows (equality tested in Task 2/5).
8. Assert `len(COMMAND_RULE_MATRIX) == 43`.

### Required Interfaces and Contracts
- Command tag remains `start_collective_project`.
- Well/warning_post still require public_goods to start.
- Infra-only kinds require infrastructure channel + collective_projects only.

### Error Handling and Logging
- Reject reasons: `not_adjacent`, `target_required`, `target_forbidden`,
  `infrastructure_networks_inactive`, `infrastructure_edge_exists`,
  `public_goods_channel_off`, catalog blocked reasons.
- DEBUG open-project counts; INFO accepted start kind only.

### Tests
- Edge/node target matrix; legacy decode without target; kind gating with/without
  flag and public_goods; command count 43.
- `uv run pytest tests/unit/test_infrastructure_construction.py -q`

### Acceptance Criteria
- Full start pipeline works; legacy starts decode; public_goods gate preserved.

### Verification
- Construction tests green.

## Task 6: Cognition proposers for new kinds and roads

### Intent
Deterministic cognition can propose the new starts (including road targets).

### Implementation Steps
1. Extend `_START_KIND` with focus codes for `irrigation`, `trade_post`,
   `large_shelter`, `well`, `warning_post` (if missing), and `road`.
2. For `road`, select a legal adjacent exit from the observation (deterministic
   first sorted adjacent id not blocked) and pass
   `StartCollectiveProject(project_kind="road", target_location_id=…)`.
3. If no legal adjacent target, skip (DEBUG reason) and keep prior command.
4. Do not invent leader/crew fields; never bypass WorldEngine admission.
5. Logging remains metadata-only (owner_id already logged today — keep pattern
   consistent with existing module; do not add payload bodies).

### Required Interfaces and Contracts
- Proposer only replaces command when focus matches and observation permits.
- Road proposals always include `target_location_id` when returned.

### Error Handling and Logging
- DEBUG skip reasons: `no_adjacent_target`, start-block reasons.

### Tests
- Each new focus code proposes the right kind; road includes target; no-adjacent
  skips; channel off passthrough.
- `uv run pytest tests/unit/test_infrastructure_cognition.py -q`

### Acceptance Criteria
- Agents can propose infra starts including roads with targets.

### Verification
- Cognition tests green.

## Task 7: Completion registers assets and ROAD anchors

### Intent
On `ProjectCompleted`, mint operational `infra-` assets and ensure roads have a
Repairable structure anchor.

### Implementation Steps
1. After `_complete_project` structure/store mutation, if infrastructure active
   and kind eligible, call `register_from_completed_project`.
2. Initial asset status `operational`, integrity `1.0`, links project/structure
   ids, normalized edge endpoints.
3. For `road`: always create `StructureKind.ROAD` at anchor `location_id` if not
   already present, and set `linked_structure_id`.
4. Eligible: eight infrastructure kinds; `winter_reserve` / bare `record_site` do
   not register.
5. Cap reached ⇒ WARN `infrastructure_asset_cap`; project still completes;
   scientific run continues.
6. Emit constructed event hook for Task 14.

### Required Interfaces and Contracts
- No owner/crew fields.
- Road without public_goods remains Repair-maintainable via linked ROAD structure.

### Error Handling and Logging
- INFO constructed kind/topology counts; WARN on cap; ERROR on id collision.

### Tests
- Each eligible kind registers; winter_reserve does not; road creates ROAD
  structure; cap behavior.
- `uv run pytest tests/unit/test_infrastructure_construction.py -q`

### Acceptance Criteria
- Completions yield operational assets; roads have Repair anchors.

### Verification
- Construction completion tests green.

## Phase Risks and Mitigations
- Risk: serialize omit breaks cognition round-trip.
  Mitigation: Task 5 encode/decode tests with target present and absent.
- Risk: roads unmaintainable without public_goods.
  Mitigation: ROAD structure anchor (Task 7).

## Phase Completion Checklist
- Tasks 5-7 done; command count 43.
