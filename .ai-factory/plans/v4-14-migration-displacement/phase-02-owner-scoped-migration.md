# Phase 2: Owner-Scoped Migration Beliefs

Plan: [index.md](index.md)
Tasks: 4-10
Depends on: Phase 1 / Tasks 1-3

## Objective

Implement one owner's private migration-displacement ledger: six row families,
content-addressed identity, a canonical digest, an ordered update pipeline,
bounded `mdp_v1` speech, a deterministic cause-weighted route bias, runtime
carry, checkpoints, and bounded export. No row grants permission, changes world
state, or constructs a command.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/agents/cognition/borders.py` | `BorderEvidence` 108-116; `BorderLedger` 125-135; IDs 200-260; `apply_borders_update` 1800-2050; caps 2100-2250 | Precedent for owner-scoped rows, digest, ordered update, and caps |
| `src/agents/cognition/borders_communication.py` | `BorderFrame` 55-112; `encode_border_claim` 138-151; `parse_border_claim` 259-304; `attach_border_relation` 332-349; deliveries 442-525 | Precedent for bounded speech and delivery-derived provenance |
| `src/agents/cognition/regional_migration.py` | `destination_lane_id` 43-63; `destination_memory_trace` 65-198; `known_destination_ids` 201-272; `destination_action_biases` 275-466 | Existing destination evidence and bias; V4-14 extends it rather than replacing it |
| `src/agents/cognition/deliberation.py` | regional mode args 170-194; regional bias 655-700; pairwise bias 2440-2472 | Exact insertion point for a second owner-scoped bias |
| `src/agents/cognition/loop.py` | `_prepare_borders` 3149-3205; prepare order 5250-5340; carry 1620-1673 | Precedent for a prepared ledger and carry |
| `src/agents/cognition/contracts.py` | `Perspective` 335-340, `detached_copy` 609 | Owner-safe perspective carrying |
| `src/agents/cognition/models.py` | `SubjectiveSnapshot` 732; `CognitiveLoopProposal` 3967; `CognitiveLoopResult` 4311 | Carry contracts |
| `src/agents/cognition/fork_state.py` | prepared state 68 | Fork carry |
| `src/simulation/agent_runtime.py` | `_commit_borders` pattern 1532-1560; perspective 2468; commit 2981; restore 3586; export 3712 | Runtime carry and checkpoint |
| `src/simulation/perception.py` | `build_perspective` 113, 381 | Perspective projection |
| `src/simulation/run_control.py` | checkpoint field 622; validation 829 | Checkpoint contract |
| `src/simulation/runner_models.py` | ledger export tuple 6394; validation 6764-6785 | Completed-run export |
| `src/simulation/runner.py` | `export_border_ledgers` 5672-5685; result assembly 5180-5210 | Completed-run export pattern |
| `src/world/observations.py` | `VisibleExit` 284-330; location/weather/body facts 1300-1455 | Owner-visible route, cause, and cluster evidence |
| `src/social/relationships.py` | `DirectedRelationshipProfile` 56-87; dimensions 306-502 | Owner-local social-network evidence |
| `src/world/kinship.py` | `KinshipGraph` 51-216; visible kin 347-491 | Objective genealogy available as local cluster evidence |
| `tests/unit/test_borders_carry.py` | carry/restore/export cases | Exact test shape to mirror |
| `tests/unit/test_regional_migration_cognition.py` | bias and hop-bound cases | Existing migration behavior must stay green |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/agents/cognition/migration_displacement.py` | modify | Six row-family semantics, IDs, digest, canonical ledger, update pipeline, route/cause/cluster/integration derivation, bias, caps, notices, owner export |
| `src/agents/cognition/migration_displacement_communication.py` | create | Bounded `mdp_v1` frame encode/parse/attach/delivery |
| `src/agents/cognition/deliberation.py` | modify | Accept and apply the migration-displacement bias to candidate `Move` futures |
| `src/agents/cognition/loop.py` | modify | Prepare the ledger, compute the bias, and carry/restore it |
| `src/agents/cognition/contracts.py` | modify | Carry `migration_displacement` in `Perspective` |
| `src/agents/cognition/models.py` | modify | Carry it in snapshot, proposal, and result |
| `src/agents/cognition/fork_state.py` | modify | Carry prepared migration-displacement state |
| `src/simulation/agent_runtime.py` | modify | Commit, restore, and export the ledger |
| `src/simulation/perception.py` | modify | Project the ledger into the owner-safe perspective |
| `src/simulation/run_control.py` | modify | Checkpoint field and owner validation |
| `src/simulation/runner_models.py` | modify | Completed-run ledger tuple and validation |
| `src/simulation/runner.py` | modify | Export owner-ordered ledgers |
| `src/simulation/migration_displacement_export.py` | create | Token-only owner-row projection for experiments/analysis |
| `tests/unit/test_migration_displacement_rows.py` | create | Six row-family semantics |
| `tests/unit/test_migration_displacement_ledger.py` | create | IDs, digest, canonical order |
| `tests/unit/test_migration_displacement_update.py` | create | Ordered pipeline |
| `tests/unit/test_migration_displacement_communication.py` | create | `mdp_v1` bounds, speaker binding, delivery provenance |
| `tests/unit/test_migration_displacement_cognition.py` | create | Cause-weighted bias, no command path |
| `tests/unit/test_migration_displacement_carry.py` | create | Perspective, snapshot, proposal, result, checkpoint, fork, export |
| `tests/unit/test_migration_displacement_caps.py` | create | Caps, notices, deterministic truncation |

## Task 4: Define intents, route beliefs, cause evidence, social-cluster beliefs, integration beliefs, and wave observations

### Intent

Give the six owner row families closed, independently valid semantics. Each row
is one owner's belief; none is a shared migration, refugee category, household,
or truth. The families are deliberately separate so later analysis can keep
objective movement, subjective cause, analytical waves, and integration
outcomes in different layers.

### Implementation Steps

1. Extend the Task 1 dataclasses with full `__post_init__` validation:
   - every owner id is an exact `AgentId`;
   - every location is an exact `EntityId`;
   - every id starts with its family prefix (`mdi-`, `mdr-`, `mdc-`, `mdg-`,
     `mdn-`, `mdw-`);
   - all id tuples are sorted and duplicate-free;
   - all evidence tuples are bounded by `max_evidence_per_row` and sorted by
     `(source_tick, lineage_ref)`;
   - confidence is finite and quantized to six decimals in `[0, 1]`;
   - ticks are non-negative and ordered.
2. Define the status transitions:
   - `MigrationIntentRow`: `considered -> planned -> departed -> arrived`;
     terminal `abandoned`, `expired`, `unknown`.
   - `RouteBeliefRow`: `open -> blocked_belief` or `unresolved`; terminal
     `expired`, `unknown`.
   - `CauseEvidenceRow`: `active -> superseded` or `contradicted`; terminal
     `expired`, `unknown`.
   - `SocialClusterBeliefRow`: `believed -> disputed` or `dissolved`; terminal
     `expired`, `unknown`.
   - `IntegrationBeliefRow`: `settled`, `transient`, `returned`, `onward`,
     `unknown` are terminal observations for a wave participant and destination.
   - `WaveObservationRow`: `observed` or `reported -> disputed`; terminal
     `expired`, `unknown`.
3. Define the family-specific rules:
   - An intent must reference at least one cause id or use `unknown`; it may
     reference zero to two cluster ids.
   - A route belief must have `basis != unresolved` only when the ledger also
     has an observed exit, own journey, or delivered route report supporting
     every consecutive pair; otherwise it stays `unresolved`.
   - A cause row with `cause_kind=unknown` must have `source_kind=unknown` and
     no anchor.
   - A cluster row requires `2 <= len(member_ids) <= max_cluster_members` and
     must include the owner unless `basis=communication`; no row may include a
     member not visible to the owner.
   - An integration row requires `destination_location_id` and a closed
     `IntegrationDomain`; it never contains a numeric wellbeing or assimilation
     value.
   - A wave observation requires `2 <= len(participant_ids) <= 8`, at least one
     cause id or `unknown`, and only participants the owner observed or received
     by `mdp_v1` delivery.
4. Add pure projections used by later layers:
   - `intent_location_tokens(row)`, `route_location_tokens(row)`,
     `cause_kind_token(row)`, `cluster_member_tokens(row)`,
     `integration_domain_token(row)`.
   - Every projection returns strings, never `AgentId`/`EntityId` objects.
5. Add `empty_migration_displacement_ledger(owner_id)` with empty tuples, a
   digest of the empty canonical payload, and the policy version.
6. Add `require_owner_migration_displacement(value, owner_id)` that rejects a
   foreign ledger or a non-ledger value.
7. Add `__all__` entries for every row and helper.

### Required Interfaces and Contracts

```python
PREFIX_BY_FAMILY: Final[Mapping[str, str]] = MappingProxyType(
    {
        "intent": "mdi-",
        "route": "mdr-",
        "cause": "mdc-",
        "cluster": "mdg-",
        "integration": "mdn-",
        "wave": "mdw-",
    }
)
```

- No row field is named `refugee`, `asylum`, `forced`, `displaced`, `threat`,
  `hardship`, `wellbeing`, `assimilation`, `integration_score`, `score`, or
  `composite`.
- A row never stores another owner's raw id in a published projection.
- A row never contains a command, command name, permission, or world state.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — origin, route, destination, cause evidence,
  family/social clusters, integration outcomes, waves without telepathy.
- Source: `.ai-factory/ARCHITECTURE.md` — Key Principle 1; owner-scoped
  subjective state.
- Supported combinations: each status transition; each cause kind; each cluster
  basis; each integration status; each wave status; invalid foreign owner;
  invalid member; oversized evidence; each is tested.

### Error Handling and Logging

- Invalid rows raise `ValueError("<family>: <code>")` and log
  `ERROR migration_displacement_row_rejected family=<family>
  reason_code=<code>`.
- Never log row contents; DEBUG may log counts:
  `migration_displacement_rows intents=%s routes=%s causes=%s clusters=%s
  integrations=%s waves=%s`.
- A foreign owner raises `ValueError("migration_displacement: foreign_owner")`
  without logging the owner id.

### Tests

- `tests/unit/test_migration_displacement_rows.py`
  - `test_six_row_families_have_closed_prefixes`
  - `test_intent_requires_cause_or_unknown_and_bounded_clusters`
  - `test_route_belief_requires_basis_and_contiguous_pairs`
  - `test_unknown_cause_has_no_anchor`
  - `test_cluster_requires_two_members_and_visible_members`
  - `test_integration_has_no_score_or_assimilation_field`
  - `test_wave_observation_requires_two_participants_and_evidence`
  - `test_foreign_owner_is_rejected`
  - `test_public_tokens_never_emit_entity_objects`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_rows.py -q`
- Expected: all pass.

### Acceptance Criteria

- All six families validate independently and reject foreign owners.
- No score, refugee, asylum, or forced field exists.
- Public projections contain tokens only.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_rows.py -q`
- `uv run --frozen --python 3.12.14 ruff check src/agents/cognition/migration_displacement.py tests/unit/test_migration_displacement_rows.py`
- Expected: pass.

## Task 5: Add content-addressed IDs, ledger digest, and canonical owner ledger

### Intent

Make every row identity deterministic and every ledger comparable across
processes and runs. IDs and digests must not use `hash()`, UUIDs, wall-clock
time, or unordered mappings.

### Implementation Steps

1. Add `migration_intent_id(...)`, `migration_route_id(...)`,
   `migration_cause_id(...)`, `migration_cluster_id(...)`,
   `migration_integration_id(...)`, and `migration_wave_observation_id(...)`:
   - each hashes a canonical string of owner id, family kind, location tokens,
     status-independent creation fields, and `first_tick`;
   - each returns the family prefix plus 32 hex characters;
   - equal inputs return equal ids; any changed input changes the id.
2. Add `canonical_migration_displacement_payload(ledger)` returning a mapping
   with:
   - `policy_version`, `owner_id` as a token, sorted `intents`, `routes`,
     `causes`, `clusters`, `integrations`, `waves`, `notices`;
   - rows projected through their token helpers;
   - no digest field.
3. Add `canonical_migration_displacement_json(ledger)` using
   `json.dumps(payload, sort_keys=True, separators=(",", ":"),
   ensure_ascii=True)`.
4. Add `migration_displacement_ledger_digest(ledger)` as the SHA-256 of the
   canonical JSON.
5. Add `finalize_migration_displacement_ledger(ledger)` that recomputes the
   digest and returns a replace()d ledger; reject a ledger whose digest does not
   match its payload on validation.
6. Add `merge_migration_displacement_ledger(prior, updated)` only for tests and
   restore; production updates go through Task 6. It must preserve owner
   identity and canonical order.
7. Add `empty_migration_displacement_ledger(owner_id)` with the digest of the
   empty payload.
8. Add `__all__` entries.

### Required Interfaces and Contracts

```python
def migration_displacement_ledger_digest(
    ledger: MigrationDisplacementLedger,
) -> str: ...

def canonical_migration_displacement_json(
    ledger: MigrationDisplacementLedger,
) -> str: ...

def finalize_migration_displacement_ledger(
    ledger: MigrationDisplacementLedger,
) -> MigrationDisplacementLedger: ...
```

- Canonical order is:
  intents by `(first_tick, intent_id)`;
  routes by `(first_tick, route_id)`;
  causes by `(first_tick, cause_id)`;
  clusters by `(first_tick, cluster_id)`;
  integrations by `(first_tick, outcome_id)`;
  waves by `(first_tick, observation_id)`;
  notices as a sorted unique tuple.
- A digest is lower-case hex SHA-256, 64 characters.
- No raw `AgentId` or `EntityId` appears in the canonical payload.

### Requirement Evidence (when reconciliation applies)

- Source: `.ai-factory/ARCHITECTURE.md` — Key Principle 2 (deterministic seeds,
  namespaced ids, no global RNG/hash/UUID/wall clock).
- Source: `src/agents/cognition/borders.py` ledger digest and ID pattern.
- Supported combinations: empty ledger; one row per family; every status; two
  orders of insertion; a changed confidence; a changed route; each is tested.

### Error Handling and Logging

- A digest mismatch raises `ValueError("migration_displacement: digest_mismatch")`
  and logs `ERROR migration_displacement_digest_mismatch`.
- A canonical payload containing a raw id raises
  `ValueError("migration_displacement: raw_identifier")`.
- DEBUG logs `migration_displacement_ledger_finalized rows=%s digest_prefix=%s`
  using only a short digest prefix.

### Tests

- `tests/unit/test_migration_displacement_ledger.py`
  - `test_empty_ledger_digest_is_stable`
  - `test_each_row_family_has_a_content_addressed_id`
  - `test_changed_input_changes_id`
  - `test_canonical_order_is_independent_of_insertion_order`
  - `test_canonical_payload_contains_no_raw_identifiers`
  - `test_digest_mismatch_is_rejected`
  - `test_merge_preserves_owner_and_order`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_ledger.py -q`
- Expected: all pass.

### Acceptance Criteria

- IDs and digests are deterministic across process restarts.
- Canonical order is total and independent of insertion order.
- No raw identity leaks into the canonical payload.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_ledger.py -q`
- `rg -n "hash\(|uuid|datetime\.now|time\.time" src/agents/cognition/migration_displacement.py` — expected: no matches.
- Expected: pass.

## Task 6: Implement the ordered migration-displacement update pipeline

Depends on: Tasks 4, 5, and 7 (`mdp_v1` frame helpers must exist before
`_apply_frames`).

### Intent

Refresh one owner's ledger from visible local inputs in a fixed order. The
pipeline never reads `WorldState`, another owner's ledger, or a command. It
never creates a migration from silence and never treats a peer frame as
trusted.

### Implementation Steps

1. Add:
   ```python
   def apply_migration_displacement_update(
       *,
       owner_id: AgentId,
       tick: int,
       observation: Observation,
       prior: MigrationDisplacementLedger,
       identity: object | None,
       relationships: Sequence[object] = (),
       organization_concepts: object | None = None,
       institution_concepts: object | None = None,
       formal_rules: object | None = None,
       disputes: object | None = None,
       evidence: object | None = None,
       diplomacy: object | None = None,
       organized_conflict: object | None = None,
       borders: object | None = None,
       inbox: object | None = None,
       policy: MigrationDisplacementPolicy,
   ) -> MigrationDisplacementLedger:
   ```
2. Execute exactly this order:
   1. `_update_own_intents` — from own needs, goals, visible exits, active
      intents, and own journey state. A new intent requires
      `confidence >= min_intent_confidence` and at least one cause id or
      `unknown`.
   2. `_update_route_beliefs` — from visible exits (`VisibleExit`), own current
      journey, and delivered route reports. Each consecutive pair must be an
      observed exit or an own-journey edge; otherwise the route is
      `unresolved`.
   3. `_update_cause_evidence` — from own need deficits, visible weather/hazard/
      exposure, own journey, relationships, visible kin, organization concepts,
      institution concepts, formal rules, disputes, evidence, diplomacy,
      organized conflict, and borders. Each reference resolves only against the
      owner's own ledger; missing anchors produce `unresolved_anchor`.
   4. `_update_cluster_beliefs` — from visible kinship, owner relationships,
      organization concepts, and observed co-movement. A cluster requires at
      least two visible members and at least one basis.
   5. `_apply_frames` — only delivered `mdp_v1` frames from
      `migration_displacement_frames_from_observation` and
      `migration_displacement_frames_from_inbox`; replace declared provenance
      with `source_kind=testimony`, `source_owner_id=<sender>`,
      `source_tick=<delivery tick>`.
   6. `_resolve_anchors` — resolve only local opaque anchors; a missing,
      version-mismatched, or foreign anchor stays `unresolved` and emits a
      notice.
   7. `_update_integration_beliefs` — after arrival, from own residence,
      needs, visible access, organization/institution participation, and
      relationships. No row is created before arrival.
   8. `_update_wave_observations` — only from participants the owner directly
      observed moving or received by delivered frames; never from another
      owner's ledger.
   9. `_expire_rows` — terminal rows older than their policy age become
      `expired`; non-terminal rows are retained until their age cap.
   10. `_enforce_caps` — apply Task 10 caps in canonical order.
   11. `_finalize_digest`.
3. Ensure no helper accepts a `WorldState`, `WorldEvent` body, `AgentCommand`,
   command factory, or peer ledger. The only inputs are the owner-safe
   observation, prior ledger, owner-local ledgers, and delivered inbox.
4. Ensure a frame cannot create an intent, route, or cluster with a subject,
   origin, destination, cause, or member not visible to the receiver. A frame
   may only inform a belief; the receiver decides whether to store it.
5. Add `migration_displacement_update_summary(ledger)` returning counts only.
6. Add `__all__` entries.

### Required Interfaces and Contracts

- The pipeline is pure with respect to world state: the same `(owner_id, tick,
  observation, prior, identity, owner ledgers, inbox, policy)` produces the
  same ledger.
- `owner_id == prior.owner_id`; a mismatch raises
  `ValueError("migration_displacement: foreign_owner")`.
- Speaker binding is mandatory: a delivered frame whose `speaker_ref` does not
  equal the verified sender is dropped with `malformed_frame`.
- `subject_ref` may name the sender or another participant visible to the
  receiver; a different subject alone is not a drop reason. Delivery provenance
  still attributes the testimony to the verified sender (Task 7).
- Silence never creates an intent, cause, cluster, integration belief, or wave.
- Co-movement never creates a cause or an intent.
- No helper constructs a command.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — six causes, waves without telepathy, integration
  outcomes.
- Source: `.ai-factory/ARCHITECTURE.md` — "Objective authority and runtime";
  "Memory, testimony, and subjective concepts".
- Source: `src/agents/cognition/borders.py` `apply_borders_update` for ordered
  updates and local anchor resolution.
- Supported combinations: every order step; missing anchor; malformed frame;
  same-root testimony; no cause; no route; post-arrival integration; each is
  tested.

### Error Handling and Logging

- Missing required owner ledgers are not errors; references stay unresolved.
- Wrong types raise `TypeError` or `ValueError` with stable codes.
- Log `DEBUG migration_displacement_prepare intents=%s routes=%s causes=%s
  clusters=%s integrations=%s waves=%s notices=%s`.
- Never log ids, locations, routes, causes, members, or frame bodies.

### Tests

- `tests/unit/test_migration_displacement_update.py`
  - `test_update_order_is_own_then_frames_then_integration_then_waves`
  - `test_silence_creates_no_intent_route_cause_or_wave`
  - `test_unobserved_route_stays_unresolved`
  - `test_own_ledgers_supply_local_anchors`
  - `test_missing_anchor_is_retained_and_noticed`
  - `test_delivered_frame_is_testimony_not_truth`
  - `test_other_subject_is_allowed_when_speaker_matches`
  - `test_speaker_mismatch_is_dropped`
  - `test_foreign_owner_ledger_is_rejected`
  - `test_pipeline_is_deterministic_under_permutation`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_update.py -q`
- Expected: all pass.

### Acceptance Criteria

- The pipeline follows the exact order and is deterministic.
- No world state, event body, peer ledger, or command is read or created.
- Silence and co-movement create no beliefs.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_update.py -q`
- `rg -n "WorldState|WorldEvent|AgentCommand|ActionSubmission|from world._|import world._" src/agents/cognition/migration_displacement.py` — expected: no matches.
- Expected: pass.

## Task 7: Add bounded mdp_v1 migration speech frames

### Intent

Let owners explicitly communicate migration intents, routes, causes, clusters,
and outcomes inside existing `Talk`/`Ask`/`Tell` without a new event, message
genre, or shared knowledge. Frames are bounded, untrusted, and delivery-scoped.

### Implementation Steps

1. Create `src/agents/cognition/migration_displacement_communication.py` with:
   - `MIGRATION_FRAME_SUBJECT = "mdp_v1"`;
   - `MIGRATION_FRAME_VERSION = "migration-displacement-communication.v1"`;
   - `MIGRATION_FRAME_MAX_CHARS = 256`;
   - `MIGRATION_FRAME_MAX_RELATIONS = 4`;
   - `MIGRATION_FRAME_FIELD_COUNT = 14` (subject marker plus 13 semantic
     fields);
   - `MigrationFrameError`.
2. Define `MigrationFrame` with exactly:
   - `act: MigrationFrameAct` (`report_intent`, `report_route`,
     `report_cause`, `report_cluster`, `report_outcome`, `ask_route`,
     `unknown`);
   - `speaker_ref: str` (must equal the verified sender);
   - `subject_ref: str` (may be the sender or another visible participant);
   - `origin_ref: str`;
   - `route_refs: tuple[str, ...]` (ordered; act-specific bounds below);
   - `destination_ref: str`;
   - `cause_kind: MigrationCauseKind`;
   - `source_kind: MigrationCauseSource`;
   - `cluster_ref: str | None`;
   - `confidence_q: int` (0-100);
   - `as_of_tick: int`;
   - `evidence_ref: str | None`;
   - `declared_provenance_ref: str | None`.
3. Encode one relation as 14 colon-separated parts:
   `mdp_v1:act:speaker:subject:origin:route:destination:cause:source:cluster:confidence:as_of:evidence:provenance`.
   Use `-` for absent optional values and `~` between route tokens. Reject any
   part containing `:`, newline, or more than 256 characters.
4. Act-specific `route_refs` bounds (aligned with Task 1's 2-4 route contract):
   - `report_intent` and `report_route` require an ordered sequence of **2-4**
     location tokens;
   - `ask_route` may carry **0-4** tokens as a probe (empty/`-` allowed);
   - other acts that omit a route use `-` / empty and must not invent a path;
   - undersize/oversize for the act is `malformed_frame`.
5. Implement:
   - `encode_migration_displacement_claim(frame) -> str`;
   - `parse_migration_displacement_relation(relation) -> str`;
   - `parse_migration_displacement_claim(text) -> MigrationFrame`;
   - `migration_displacement_claim_relation(frame) -> tuple[CommunicationRelation, ...]`;
   - `attach_migration_displacement_relation(command, frame) -> object`;
   - `migration_displacement_frame_deliveries(communications, identity)`;
   - `migration_displacement_frames_from_observation(observation, identity)`;
   - `migration_displacement_frames_from_inbox(inbox, identity)`.
6. Parse at most 4 relations per group; reject more than 4, field-count
   mismatch, unknown subject, unknown enum, invalid confidence, negative tick,
   oversized relation, act-specific route-length violations, or a `speaker_ref`
   that does not match the verified sender. `subject_ref` may name another
   participant visible to the receiver, but the receiver still assigns delivery
   provenance to the sender.
7. Attach at most one `mdp_v1` group to an existing `Talk`, `Ask`, or `Tell`.
   Reject any other command type with `malformed_frame`.
8. Delivery sets:
   - `source_kind=testimony`;
   - `source_owner_id=sender`;
   - `source_tick=delivery tick`;
   - `lineage_ref` from delivery, never from `declared_provenance_ref`.
9. A receiver may store a cause, route, cluster, or wave observation only after
   local anchor resolution. A frame never creates an intent by itself.

### Required Interfaces and Contracts

```python
MIGRATION_FRAME_SUBJECT: Final[str] = "mdp_v1"
MIGRATION_FRAME_MAX_CHARS: Final[int] = 256
MIGRATION_FRAME_MAX_RELATIONS: Final[int] = 4
MIGRATION_FRAME_FIELD_COUNT: Final[int] = 14
```

- The frame is **not** a new event, command, observer semantic type, or wire
  genre.
- `declared_provenance_ref` is displayed only as an untrusted claim; it is never
  used for lookup or independence.
- Same-root relations are not independent corroboration.
- At most one group per speech command.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — "Support migration waves without agents sharing
  collective telepathy".
- Source: `.ai-factory/ARCHITECTURE.md` — "Talk/Ask/Tell prove eligible delivery
  only"; declared lineage is testimony.
- Source: `src/agents/cognition/borders_communication.py` for bounded frame and
  delivery patterns.
- Supported combinations: each act; each cause/source; absent optional fields;
  `report_route` with 2-4 tokens; `report_route` with 1 token rejected;
  `ask_route` with empty/partial route; 4 relations; 5 relations; 257
  characters; speaker mismatch; other subject allowed; non-speech command; each
  is tested.

### Error Handling and Logging

- Every violation raises `MigrationFrameError("<stable_code>")`.
- The update pipeline catches it, appends `malformed_frame`, and drops the
  frame.
- Log `WARN migration_displacement_frame_dropped reason_code=%s count=%s`; never
  log frame bodies, subject, origins, routes, or cause text.
- A valid group logs `DEBUG migration_displacement_frame_delivered count=%s`.

### Tests

- `tests/unit/test_migration_displacement_communication.py`
  - `test_frame_has_thirteen_semantic_fields_and_fourteen_parts`
  - `test_round_trip_for_every_act_and_cause`
  - `test_report_route_requires_two_to_four_ordered_locations`
  - `test_ask_route_allows_empty_or_partial_probe`
  - `test_route_is_ordered_and_bounded`
  - `test_oversize_and_bad_enum_are_rejected`
  - `test_speaker_mismatch_is_rejected_but_other_subject_is_allowed`
  - `test_declared_provenance_is_replaced_from_delivery`
  - `test_same_root_is_not_independent`
  - `test_only_talk_ask_tell_accept_a_frame`
  - `test_at_most_one_group_per_command`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_communication.py -q`
- Expected: all pass.

### Acceptance Criteria

- `mdp_v1` is exactly bounded and only travels inside existing speech.
- Speaker binding and delivery provenance are mandatory.
- No frame creates a command, event, or shared belief.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_communication.py -q`
- `rg -n "mdp_v1" src/world/events.py src/observer src/simulation` — expected:
  no event/observer/simulation wire additions.
- Expected: pass.

## Task 8: Extend deterministic route and destination cognition with cause-weighted multi-hop plans

### Intent

Use the owner's own migration ledger to bias ordinary `Move` candidates toward
destinations supported by the owner's causes, routes, and clusters. Physical
movement is still one adjacent `Move` at a time; a multi-hop route is a belief,
not a teleport or a new command.

### Implementation Steps

1. In `src/agents/cognition/migration_displacement.py`, add:
   ```python
   def migration_displacement_action_biases(
       ledger: MigrationDisplacementLedger,
       *,
       observation: Observation,
       known_destinations: Sequence[EntityId],
       base_biases: Mapping[str, float] | None = None,
       policy: MigrationDisplacementPolicy,
   ) -> Mapping[str, float]:
   ```
   - Return a mapping from future id (`str`) to a bounded additive bias in
     `[-max_destination_bias, max_destination_bias]`, matching the existing
     `regional_migration_bias` key shape used by `_pairwise_select`.
   - Only active intents (`planned`, `departed`) and `open` route beliefs
     contribute.
   - A destination supported by an active cause and a route gets a positive
     bias; an unresolved route or unknown cause contributes zero.
   - No base bias is mutated; compose by addition and clamp.
2. In `src/agents/cognition/loop.py`:
   - Add `_prepare_migration_displacement` after `_prepare_borders` and before
     mediation.
   - If the mode is disabled, set `_prepared_migration_displacement = None` and
     return `None`.
   - Read `snapshot.migration_displacement`; default to
     `empty_migration_displacement_ledger(owner_id)`.
   - Call `apply_migration_displacement_update(...)` with the owner-safe
     inputs listed in Task 6.
   - Compute `migration_displacement_biases` from the prepared ledger and the
     visible destinations.
   - Store `_prepared_migration_displacement` and
     `_prepared_migration_displacement_biases`.
   - Log counts only.
3. In `src/agents/cognition/deliberation.py`:
   - Add `migration_displacement_bias: Mapping[str, float] | None = None` to
     the deliberation method after `regional_migration_hop_limit`.
   - Pass it to `_pairwise_select` as a new final bias argument.
   - In `_pairwise_select`, apply `total += bias.get(left.future_id, 0.0)` and
     `total -= bias.get(right.future_id, 0.0)` exactly once.
   - Reject a bias mapping containing a non-finite value.
4. Do not call `Move`, `Transport`, or `Flee` constructors from the bias helper.
   The existing deliberation path still compiles one ordinary command.
5. Test that with the mode disabled the candidate order, tie-break, and command
   are byte-identical to the pre-V4-14 deterministic regional behavior.
6. Test that the bias can favor a route only when the owner has an active
   cause/route belief; co-movement alone adds no bias.

### Required Interfaces and Contracts

- The helper is a pure scoring projection; it never returns an `AgentCommand`,
  command name, action direction, or world mutation.
- `max_destination_bias` is locked at `0.25`; no runner field configures it.
- The bias applies only to existing candidate `Move` futures; it cannot create a
  candidate, bypass capacity, ignore fatigue, or cross a non-adjacent edge.
- Existing `regional_migration_cognition_mode` behavior is unchanged when the
  new mode is disabled.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — six causes and population-scale movement.
- Source: `.ai-factory/ARCHITECTURE.md` — cognition returns one closed
  `AgentCommand`; ordinary admission still applies.
- Source: `src/agents/cognition/regional_migration.py`
  `destination_action_biases`; `src/agents/cognition/deliberation.py` 655-700.
- Supported combinations: disabled mode; enabled no intent; enabled planned
  intent; unresolved route; unknown cause; multi-hop route; each is tested.

### Error Handling and Logging

- A non-finite bias raises `ValueError("migration_displacement: bias")`.
- A bias for a non-candidate key is ignored.
- Log `DEBUG migration_displacement_bias candidates=%s active_intents=%s
  applied=%s`; never log destination ids or route contents.

### Tests

- `tests/unit/test_migration_displacement_cognition.py`
  - `test_disabled_mode_preserves_regional_candidate_order`
  - `test_planned_intent_with_cause_and_route_adds_bounded_bias`
  - `test_unresolved_route_adds_no_bias`
  - `test_unknown_cause_adds_no_bias`
  - `test_multi_hop_route_biases_only_the_next_adjacent_step`
  - `test_bias_never_constructs_a_command`
  - `test_bias_does_not_bypass_capacity_or_fatigue`
  - `test_permutation_of_causes_does_not_change_selection`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_cognition.py tests/unit/test_regional_migration_cognition.py -q`
- Expected: all pass; legacy regional tests unchanged.

### Acceptance Criteria

- The bias consumes only the owner ledger and visible candidates.
- It applies to one adjacent `Move` step and never constructs a command.
- Disabled mode is byte-identical to the existing regional behavior.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_cognition.py -q`
- `rg -n "Move\(|Transport\(|Flee\(|AgentCommand\(" src/agents/cognition/migration_displacement.py` — expected: no matches.
- Expected: pass.

## Task 9: Wire migration beliefs through cognition, runtime carry, checkpoints, and export

### Intent

Make the migration-displacement ledger a first-class owner-scoped value in the
cognitive loop, runtime checkpoints, and completed-run result, without exposing
it to world authority or another owner.

### Implementation Steps

1. In `src/agents/cognition/contracts.py`:
   - Add `migration_displacement: object | None = None` to `Perspective`.
   - Validate with `require_owner_migration_displacement` at the same point as
     `borders`.
   - Include it in `detached_copy`.
2. In `src/agents/cognition/models.py`:
   - Add `migration_displacement` to `SubjectiveSnapshot` (732),
     `CognitiveLoopProposal` (3967), and `CognitiveLoopResult` (4311).
   - Validate owner identity in each `__post_init__`.
3. In `src/agents/cognition/fork_state.py`, add
   `prepared_migration_displacement` and
   `prepared_migration_displacement_biases` next to `prepared_borders`.
4. In `src/simulation/agent_runtime.py`:
   - Add `_migration_displacement` to `__slots__` and initialize `None`.
   - Add `_commit_migration_displacement(ledger, tick)` mirroring
     `_commit_borders`:
     - read the mode with `getattr(self._loop,
       "_migration_displacement_mode",
       CognitionMigrationDisplacementMode.DISABLED)`;
     - disabled mode clears;
     - a pending ledger without a mode logs
       `migration_displacement_pending_ledger_missing`;
     - wrong type raises `TypeError("migration_displacement must be
       MigrationDisplacementLedger")`;
     - wrong owner raises `AgentRuntimeError.OWNERSHIP`.
   - In `src/simulation/perception.py`, add
     `migration_displacement: object | None = None` to `build_perspective` at
     line 113 and forward it into `Perspective` at line 381, next to `borders`.
   - Pass `migration_displacement=self._migration_displacement` into
     `build_perspective`.
   - Commit from `loop_result.migration_displacement`.
   - Restore from `checkpoint.migration_displacement`.
   - Export `migration_displacement=self._migration_displacement`.
5. In `src/simulation/run_control.py`:
   - Add `migration_displacement: object | None = None` after `borders`.
   - Validate with `require_owner_migration_displacement` after the border
     validation.
6. In `src/simulation/runner_models.py`:
   - Add `migration_displacement_ledgers: tuple[object, ...] = ()` after
     `border_ledgers`.
   - Validate exact tuple order, exact `MigrationDisplacementLedger` item type,
     unique owner order, and owner identity.
7. In `src/simulation/runner.py`:
   - Add `export_migration_displacement_ledgers()` mirroring
     `export_border_ledgers`.
   - Include `migration_displacement_ledgers=(
     self.export_migration_displacement_ledgers())` in the result assembly.
8. In `src/agents/cognition/__init__.py` and
   `src/simulation/cognition_contracts.py`, export the new carry symbols.

### Required Interfaces and Contracts

- `Perspective.migration_displacement`,
  `SubjectiveSnapshot.migration_displacement`,
  `CognitiveLoopProposal.migration_displacement`,
  `CognitiveLoopResult.migration_displacement`,
  `AgentRuntimeCheckpoint.migration_displacement`, and
  `SimulationRunnerResult.migration_displacement_ledgers` all carry the same
  owner-scoped `MigrationDisplacementLedger` or `None`.
- A foreign owner ledger is rejected at every boundary.
- Disabled mode produces `None`; enabled mode always produces a ledger, even an
  empty one.
- The ledger is not written to any objective event, observer frame, prompt,
  memory, or analysis input during the tick.

### Requirement Evidence (when reconciliation applies)

- Source: `.ai-factory/ARCHITECTURE.md` — "Objective authority and runtime";
  owner-safe perspectives; deferred subjective finalization.
- Source: V4-13 border carry at the cited lines.
- Supported combinations: disabled carry; enabled empty ledger; enabled
  non-empty ledger; checkpoint restore; fork prepared state; export; each tested.

### Error Handling and Logging

- Wrong type/owner raises the stable runtime error and does not partially commit.
- A missing pending ledger while enabled logs `WARN
  migration_displacement_pending_ledger_missing tick=%s`.
- Restore/export logs counts only.
- Never log owner ids, intent ids, locations, routes, causes, clusters, or
  participants.

### Tests

- `tests/unit/test_migration_displacement_carry.py`
  - `test_disabled_mode_carries_none`
  - `test_enabled_mode_carries_an_empty_ledger`
  - `test_perspective_rejects_a_foreign_ledger`
  - `test_snapshot_proposal_and_result_require_owner_identity`
  - `test_checkpoint_restore_and_export_round_trip`
  - `test_fork_state_carries_prepared_migration_displacement`
  - `test_runner_result_exports_owner_ordered_ledgers`
  - `test_world_and_observer_do_not_receive_migration_fields`
- Commands:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_carry.py tests/unit/test_agent_runtime.py -q`
- Expected: all pass.

### Acceptance Criteria

- The ledger survives snapshot, proposal, result, checkpoint, restore, fork, and
  completed-run export.
- A foreign ledger is rejected everywhere.
- No world or observer contract gains a migration field.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_carry.py -q`
- `uv run --frozen --python 3.12.14 python -c "import simulation.agent_runtime, simulation.run_control, simulation.runner_models"` (via `uv run`)
- Expected: pass.

## Task 10: Enforce migration-displacement caps, notices, and owner export

### Intent

Keep the ledger bounded and publishable without deleting terminal history
silently. Export produces token-only owner rows so experiments and analysis can
consume the ledger without importing cognition or exposing raw identities.

### Implementation Steps

1. In `src/agents/cognition/migration_displacement.py`, implement
   `_enforce_caps(ledger, policy)`:
   - cap intents at 8, routes at 16, causes at 32, clusters at 8, integrations at
     8, wave observations at 8, total rows at 96;
   - drop terminal rows first in canonical order: `expired`, `abandoned`,
     `dissolved`, `superseded`, `contradicted`, `unknown`;
   - never drop an active `planned`/`departed` intent while a non-terminal row
     exists;
   - if no droppable row exists, return the prior ledger and append
     `migration_displacement_capacity_reached`;
   - when a row is dropped, append
     `migration_displacement_truncated:<family>` for that family.
2. Implement `_expire_rows(ledger, tick, policy)`:
   - non-terminal rows older than their family age cap become `expired`;
   - terminal rows remain until cap pressure;
   - expiry never invents a cause, route, cluster, integration, or wave.
3. Add `migration_displacement_owner_export(ledger)` in
   `src/simulation/migration_displacement_export.py`:
   - accepts a sequence of owner ledgers;
   - returns token-only `MigrationOwnerExportRow` values for each family;
   - sorts by `(owner_token, family, first_tick, row_token)`;
   - rejects a foreign or duplicate owner;
   - contains no `AgentId`, `EntityId`, raw route, cause text, frame body, or
     evidence content.
4. Add `migration_displacement_export_notices(rows)` returning sorted unique
   notices from the exported rows.
5. Add `migration_displacement_export_digest(rows)` for publication provenance.
6. Ensure the export is the only bridge from cognition ledgers to
   `experiments`/`analysis`; those packages must not import
   `agents.cognition.migration_displacement`.
7. Add `__all__` entries.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class MigrationOwnerExportRow:
    owner_token: str
    family: str
    row_token: str
    origin_token: str
    destination_token: str
    route_tokens: tuple[str, ...]
    cause_tokens: tuple[str, ...]
    cluster_tokens: tuple[str, ...]
    status: str
    confidence: float
    first_tick: int
    last_tick: int
    coverage: str
```

- Every token is lowercase `[a-z0-9][a-z0-9-]{0,63}`.
- No raw ids or free text are exported.
- Caps are deterministic; insertion order never changes the retained set.
- A capacity notice is a `notices` entry, not a row deletion of active state.

### Requirement Evidence (when reconciliation applies)

- Source: `.ai-factory/ARCHITECTURE.md` — bounded state, owner-scoped export,
  analysis isolation.
- Source: `src/agents/cognition/borders.py` caps and export patterns.
- Supported combinations: each family cap; total cap; droppable vs
  non-droppable; terminal vs active; duplicate owner; empty ledger; each is
  tested.

### Error Handling and Logging

- A cap overflow logs `WARN migration_displacement_truncated family=%s count=%s`
  with counts only.
- A non-droppable overflow logs `WARN
  migration_displacement_capacity_reached rows=%s`.
- Export rejects a duplicate owner with
  `ValueError("migration_displacement_export: duplicate_owner")`.
- Never log owner tokens, row tokens, locations, routes, causes, or clusters.

### Tests

- `tests/unit/test_migration_displacement_caps.py`
  - `test_each_family_cap_is_enforced`
  - `test_total_ledger_cap_is_enforced`
  - `test_terminal_rows_are_dropped_before_active_rows`
  - `test_no_droppable_row_keeps_prior_ledger_and_notice`
  - `test_truncation_notice_is_family_specific`
  - `test_expiry_does_not_invent_a_row`
  - `test_owner_export_is_token_only_and_sorted`
  - `test_export_rejects_duplicate_or_foreign_owner`
  - `test_export_digest_is_stable`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_caps.py -q`
- Expected: all pass.

### Acceptance Criteria

- The ledger never exceeds its family or total caps.
- Active intents are preserved when any droppable row exists.
- Export contains tokens only and is deterministic.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_caps.py -q`
- `rg -n "AgentId|EntityId|WorldEvent|AgentCommand" src/simulation/migration_displacement_export.py` — expected: no raw-identity or command exposure in export rows.
- Expected: pass.

## Phase Risks and Mitigations

- Risk: a migration intent becomes a hidden command path.
  Mitigation: Task 8 tests assert the bias never constructs a command and cannot
  bypass capacity or fatigue; Task 23 scans constructors.
- Risk: co-movement is mistaken for shared intent.
  Mitigation: Task 6 creates no cause from movement; Task 13 groups only
  independent committed movements; Task 23 asserts no shared ledger.
- Risk: a peer frame creates an unobserved route or cause.
  Mitigation: Task 7 requires delivery and local anchor resolution; Task 6
  drops a frame that names an unobserved subject or member.
- Risk: caps delete active plans.
  Mitigation: Task 10 drops terminal rows first and preserves active intents
  when any droppable row exists.
- Risk: raw identities leak into the export.
  Mitigation: Task 10 exports tokens only; Task 23 scans for raw fields.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
