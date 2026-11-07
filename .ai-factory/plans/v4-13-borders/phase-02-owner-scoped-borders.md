# Phase 2: Owner-Scoped Border Beliefs

Plan: [index.md](index.md)
Tasks: 4-10
Depends on: Phase 1 / Tasks 1-3

## Objective

Implement one owner's retained border beliefs: domain claims over logical
location sets, observed boundary edges, boundary recognitions, access
expectations, border agreements, and disputes. Add bounded `bdr_v1` speech, the
ordered update pipeline, runtime carry/checkpoints, deterministic caps, and a
metadata-only export. No border belief grants access, blocks a command, or
mutates world state.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/agents/cognition/territorial.py` | `TerritorialClaimLedger` 313-361; `TerritorialClaim` 252-310; evidence 185-249 | Source of single-location claims and the owner-scoped pattern |
| `src/agents/cognition/territorial.py` | `apply_territorial_update` 975-1072; `_apply_self_actions` 648-711; `_apply_frequent_areas` 714-764; `_apply_testimony` 908-972 | Reusable collection structure for own actions, memory, testimony |
| `src/agents/cognition/loop.py` | `_prepare_territorial_claims` 1716-1785; `_prepare_organized_conflict` 3067-3125; loop result assembly 5450-5620 | Integration point for an ordered border prepare step |
| `src/agents/cognition/contracts.py` | `Perspective` 142-164; territorial validation 335-340; detached copy 609 | Owner-safe carry type |
| `src/agents/cognition/models.py` | `SubjectiveSnapshot` 732-917; `CognitiveLoopProposal` 3967-4064; `CognitiveLoopResult` 4311-4385 | Fields that must carry the new ledger |
| `src/agents/cognition/fork_state.py` | `prepared_organized_conflict` 68 | Prepared-state carry for branch/fork paths |
| `src/simulation/agent_runtime.py` | slots 448-506; init 610-640; `_commit_organized_conflict` 1532-1560; restore 3586; export 3712 | Runtime commit/restore/export pattern |
| `src/simulation/run_control.py` | `AgentRuntimeCheckpoint` 604-640; checkpoint validation 829-840 | Durable owner-state contract |
| `src/simulation/runner_models.py` | result ledger tuple 6394; validation 6764-6785 | Completed-run export contract |
| `src/simulation/runner.py` | `export_organized_conflict_ledgers` 5672-5685; result assembly 5180-5210 | Export function pattern |
| `src/agents/cognition/organized_conflict_communication.py` | frame constants 84-95; encode/parse 632-704; attach 1063-1132 | Newest bounded-frame pattern |
| `src/agents/cognition/diplomacy_communication.py` | `trt_v1` chunks 93-95, 306-330, 632-642; speaker binding 707-721 | Chunked bounded-frame and untrusted-speaker pattern |
| `src/agents/cognition/organization_concepts.py` | `orgc-` ids 30-45; resource anchors 129-137; concept ledger 1483-1549 | Read-only organization anchor resolution |
| `src/agents/cognition/diplomacy.py` | party kinds 241-260; treaty subjects 381-391; provisions 449-459; ledger 1876-2213 | Read-only agreement/treaty anchor resolution |
| `src/world/observations.py` | `Observation.location` 1300-1326; `VisibleExit` 284-330; `ObservedCommunication` | Inputs for local adjacency and delivered frames |
| `tests/unit/test_territorial_claims.py` | 508-760 | Owner-only and no-world tests to mirror |
| `tests/unit/test_organized_conflict_communication.py` | frame malformed/oversize/speaker-mismatch cases | Bounded-frame test pattern |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/agents/cognition/borders.py` | modify | Row families, ledger digest, update pipeline, boundary derivation, caps, export |
| `src/agents/cognition/borders_communication.py` | create | `bdr_v1` encoder, parser, relation adapter, attachment |
| `src/agents/cognition/configuration.py` | modify | Border policy is already in the loop config; no runner key |
| `src/agents/cognition/loop.py` | modify | `_prepare_borders` after territory and organizations; result field |
| `src/agents/cognition/contracts.py` | modify | `Perspective.borders` and owner validation |
| `src/agents/cognition/models.py` | modify | Snapshot, proposal, result fields and validation |
| `src/agents/cognition/fork_state.py` | modify | `prepared_borders` |
| `src/simulation/agent_runtime.py` | modify | slot, init, commit, restore, export |
| `src/simulation/perception.py` | modify | `build_perspective` accepts and forwards `borders` |
| `src/simulation/run_control.py` | modify | checkpoint field and owner validation |
| `src/simulation/runner_models.py` | modify | result `border_ledgers` field and ordered validation |
| `src/simulation/runner.py` | modify | export `border_ledgers` and include in the result |
| `src/simulation/cognition_contracts.py` | modify | Re-export public border symbols |
| `src/agents/cognition/__init__.py` | modify | Public facade exports |
| `tests/unit/test_borders_rows.py` | create | Row contract tests |
| `tests/unit/test_borders_ledger.py` | create | Ledger digest and identity tests |
| `tests/unit/test_borders_update.py` | create | Ordered pipeline tests |
| `tests/unit/test_borders_communication.py` | create | `bdr_v1` frame tests |
| `tests/unit/test_borders_carry.py` | create | Runtime carry/checkpoint/export tests |
| `tests/unit/test_borders_boundaries.py` | create | Boundary-edge derivation tests |
| `tests/unit/test_borders_caps.py` | create | Caps, notices, export tests |

## Task 4: Define domain claims, boundary recognitions, access expectations, agreements, and disputes

### Intent

Give the contract concrete, frozen row families that can be retained, expired,
and published. Every row is a belief held by exactly one owner. A row never
becomes a permission, a title, a country owner, or a world field.

### Implementation Steps

1. Extend `src/agents/cognition/borders.py` with the row dataclasses declared in
   Task 1 and their exact invariants:
   - `TerritorialDomainClaim`:
     - `domain_id` is a content-addressed `bdc-` id.
     - `location_ids` is 1-8 sorted exact `EntityId`.
     - `boundary_edges` is 0-32 canonical observed pairs.
     - `anchor_kind` is `organization`, `settlement`, `agent`, `unknown`, or
       `None`; `anchor_ref` is required for the first three and bounded to 128.
     - `status` is a `DomainClaimStatus`.
     - `strength` is quantized to 1e-6 in `[0, 1]`.
     - `first_tick <= last_tick`.
   - `BoundaryRecognition`:
     - exactly one row per `(domain_id, basis)` per owner;
     - `boundary_edges` is a subset of the domain's observed edges;
     - `status` is `recognized`, `unresolved`, or `disputed`;
     - a recognition never names another owner as the authority.
   - `AccessExpectation`:
     - one row per `(domain_id, subject_kind, subject_ref)`;
     - `subject_ref` is `None` for `self_agent` and `unknown`; it is required and
       bounded for `other_agent` and `organization`;
     - `mode` is closed;
     - no `granted`, `allowed`, `enforced`, or `permission` field.
   - `BorderAgreement`:
     - one row per `(domain_id, counterparty_kind, counterparty_ref)`;
     - `counterparty_kind` is a `CounterpartyKind`;
     - `counterparty_ref` is `None` only for `unknown`; otherwise it is required
       and bounded;
     - `provisions` is a sorted tuple of 1-5 distinct `AgreementProvision`;
     - `status` is closed;
     - `recognition` is a `BoundaryStatus` belief, not a truth;
     - `effective_tick <= expiry_tick` when both are present.
   - `BorderDispute`:
     - one row per `(domain_id, counterparty_kind, counterparty_ref)`;
     - `counterparty_kind` is a `CounterpartyKind`;
     - `counterparty_ref` is `None` only for `unknown`; otherwise it is required
       and bounded;
     - `contested_location_ids` is 1-8 sorted exact `EntityId` and a subset of
       the referenced domain;
     - no `winner`, `loser`, `guilt`, `verdict`, or `settlement` field.
2. Add `BorderLedger` with:
   - `owner_id: AgentId`
   - `domains: tuple[TerritorialDomainClaim, ...]`
   - `recognitions: tuple[BoundaryRecognition, ...]`
   - `access_expectations: tuple[AccessExpectation, ...]`
   - `agreements: tuple[BorderAgreement, ...]`
   - `disputes: tuple[BorderDispute, ...]`
   - `notices: tuple[str, ...]`
   - `digest: str`
   - `policy_version: str = BORDERS_POLICY_VERSION`
3. Validate in `BorderLedger.__post_init__`:
   - exact owner type; all rows belong to the owner;
   - domain ids unique; recognition domain refs resolve; access/agreement/dispute
     domain refs resolve;
   - all rows sorted by their primary key and then by id;
   - caps from `BordersPolicy`;
   - digest equals `border_ledger_digest(...)`.
4. Add `empty_border_ledger(owner_id)` and
   `require_owner_borders(ledger, owner_id, *, field_name)` mirroring
   `require_owner_territorial_claims` 445-459.
5. Add `border_ledger_digest(ledger)`:
   - canonical material: policy version, owner id, and each row's stable
     content-addressed id and closed fields in sorted order;
   - SHA-256, no UUID, no wall clock, no Python `hash()`;
   - excludes `digest` itself and `notices` order is sorted before hashing.
6. No row type reads `WorldState`, `WorldEvent`, `PhysicalRules`, or
   `AgentBody`; reject them by exact type name as `territorial.py` does at
   462-479.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class BorderLedger:
    owner_id: AgentId
    domains: tuple[TerritorialDomainClaim, ...] = ()
    recognitions: tuple[BoundaryRecognition, ...] = ()
    access_expectations: tuple[AccessExpectation, ...] = ()
    agreements: tuple[BorderAgreement, ...] = ()
    disputes: tuple[BorderDispute, ...] = ()
    notices: tuple[str, ...] = ()
    digest: str = ""
    policy_version: str = BORDERS_POLICY_VERSION

def empty_border_ledger(owner_id: AgentId) -> BorderLedger: ...
def border_ledger_digest(ledger: BorderLedger) -> str: ...
def require_owner_borders(
    ledger: object, owner_id: AgentId, *, field_name: str
) -> None: ...
```

- Two owners may hold identical sets, overlapping sets, or disjoint sets.
- One owner may hold overlapping domains; separate domains are legal.
- A domain row is never a shared claim. The ledger is not consulted by
  `WorldEngine`, admission, perception, memory, prompts, observer semantics, or
  Godot.
- The ledger has no `owner_country`, `country_owner`, `sovereign`, `border_line`,
  `polygon`, `grid_cell`, or `area` field.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — claims, overlapping claims, disputed borders,
  recognized boundaries, access expectations, border agreements.
- Source: `.ai-factory/ARCHITECTURE.md` — "Memory, testimony, and subjective
  concepts" and Key Principle 1.
- Source: `src/agents/cognition/territorial.py` owner-only ledger invariants.
- Supported combinations: one/many domains, overlapping own domains, overlapping
  peer claims, no agreements, one agreement, disputed agreement, expired access
  expectation; Task 4 tests each.

### Error Handling and Logging

- Every invalid row raises `ValueError("<field>: <code>")` and logs
  `ERROR borders_validation_failed field=<field> reason_code=<code>`.
- DEBUG construction log:
  `borders_ledger_constructed owner_id=%s domains=%s agreements=%s disputes=%s`.
- Never log location ids, anchor refs, counterparties, or evidence bodies.

### Tests

- `tests/unit/test_borders_rows.py`
  - `test_domain_claim_requires_sorted_unique_bounded_locations`
  - `test_boundary_recognition_edges_are_a_subset_of_the_domain`
  - `test_access_expectation_subject_matrix`
  - `test_agreement_provisions_are_closed_sorted_and_distinct`
  - `test_dispute_contested_locations_are_a_subset`
  - `test_overlapping_own_domains_are_legal`
  - `test_foreign_owner_rows_are_rejected`
  - `test_no_forbidden_row_field_or_class_exists`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_rows.py -q`
- Expected: all pass.

### Acceptance Criteria

- All five row families exist with the documented bounds.
- Overlap is retained, never reconciled.
- No row is a permission, title, country owner, or world field.
- No world authority type is accepted.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_rows.py -q`
- `uv run --frozen --python 3.12.14 ruff check src/agents/cognition/borders.py tests/unit/test_borders_rows.py`
- Expected: pass.

## Task 5: Add content-addressed IDs, ledger digest, and canonical owner ledger

### Intent

Make every row reproducible from its content. IDs are derived, not chosen by an
RNG, a UUID, a clock, or a global counter. The ledger digest is stable across
processes and row insertion order.

### Implementation Steps

1. Add the ID functions:
   - `domain_claim_token_id(owner_id, location_tokens) -> str`:
     `sha256("bdc|" + owner.value + "|" + "|".join(sorted(location_tokens)))`,
     prefixed `bdc-` and truncated to 16 hex characters.
   - `domain_claim_id(owner_id, location_ids) -> str`: validates and orders
     `EntityId` values, then delegates to `domain_claim_token_id` with their
     `.value` strings; no second id grammar exists.
   - `boundary_recognition_id(owner_id, domain_id, basis) -> str`:
     `sha256("bdr|owner|domain|basis")`, prefix `bdr-`.
   - `access_expectation_id(owner_id, domain_id, subject_kind, subject_ref)`:
     prefix `bdx-`.
   - `border_agreement_id(owner_id, domain_id, counterparty_kind, counterparty_ref)`:
     prefix `bda-`.
   - `border_dispute_id(owner_id, domain_id, counterparty_kind, counterparty_ref)`:
     prefix `bdd-`.
2. Each function validates exact types, sorts location ids, rejects duplicates,
   rejects empty/oversize sets, and returns lowercase hex only.
3. Add `border_ledger_digest` as specified in Task 4. Use a canonical string per
   row with a fixed field order:
   - domain: `bdc|domain_id|owner|sorted locations|sorted edges|anchor_kind|anchor_ref|status|strength|first|last`
   - recognition: `bdr|id|domain|sorted edges|basis|status`
   - access: `bdx|id|domain|subject_kind|subject_ref|mode|status`
   - agreement: `bda|id|domain|counterparty_kind|counterparty_ref|sorted provisions|status|recognition|effective|expiry`
   - dispute: `bdd|id|domain|counterparty_kind|counterparty_ref|sorted contested|status`
   - Sort row lines lexicographically, join with `\n`, append one final `\n`,
   and hash the UTF-8 bytes.
4. Add `border_ledger_is_canonical(ledger) -> bool` used by tests and by the
   checkpoint restore path.
5. Do not reuse `oc-`, `dip-`, `orgc-`, `org-`, `msoc-`, `evid-`, `disp-`, or
   `rep-` prefixes.

### Required Interfaces and Contracts

```python
def domain_claim_token_id(owner_id: AgentId, location_tokens: Sequence[str]) -> str: ...
def domain_claim_id(owner_id: AgentId, location_ids: Sequence[EntityId]) -> str: ...
def boundary_recognition_id(owner_id: AgentId, domain_id: str, basis: BoundaryBasis) -> str: ...
def access_expectation_id(
    owner_id: AgentId, domain_id: str, subject_kind: AccessSubjectKind,
    subject_ref: str | None,
) -> str: ...
def border_agreement_id(
    owner_id: AgentId, domain_id: str, counterparty_kind: str,
    counterparty_ref: str,
) -> str: ...
def border_dispute_id(
    owner_id: AgentId, domain_id: str, counterparty_kind: str,
    counterparty_ref: str,
) -> str: ...
def border_ledger_digest(ledger: BorderLedger) -> str: ...
```

- IDs are stable across runs with the same content and differ when any material
  field changes.
- No id function reads the wall clock, RNG, `hash()`, or `uuid`.
- No raw `EntityId` or `AgentId` appears in a publication-facing id.

### Requirement Evidence (when reconciliation applies)

- Source: `.ai-factory/ARCHITECTURE.md` — Key Principle 2 (deterministic seeds,
  namespaced ids, no global RNG/`hash()`/wall clock/UUID).
- Source: `src/agents/cognition/territorial.py` `territorial_claim_id` 146-159
  and `territorial_evidence_id` 162-182.
- Supported combinations: same content/different insertion order produces the
  same digest; one changed location/status/provision changes the digest.

### Error Handling and Logging

- Invalid input raises `ValueError` with a stable code.
- DEBUG only: `borders_id_minted prefix=%s rows=%s`.
- Never log the material string or the ids at INFO.

### Tests

- `tests/unit/test_borders_ledger.py`
  - `test_ids_are_sha256_derived_and_prefix_correct`
  - `test_ids_change_when_any_material_field_changes`
  - `test_digest_is_independent_of_row_insertion_order`
  - `test_digest_covers_domains_recognitions_access_agreements_disputes`
  - `test_no_uuid_hash_or_wall_clock_symbol_is_used`
  - `test_prefixes_do_not_collide_with_existing_ledgers`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_ledger.py -q`
- Expected: all pass.

### Acceptance Criteria

- All ids are content-addressed and deterministic.
- The digest is canonical and covers every row family.
- No existing ledger prefix is reused.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_ledger.py -q`
- Expected: pass.

## Task 6: Implement the ordered territorial-domain update pipeline

### Intent

Turn one owner's prior ledger, its observed location/exits, its existing
territorial claims, delivered `bdr_v1` frames, organization anchors, and optional
diplomacy anchors into a new ledger in a fixed order. The pipeline never infers a
belief from silence and never reads another owner's ledger.

### Implementation Steps

1. Add `apply_borders_update(...)` with exactly:
   ```python
   def apply_borders_update(
       *,
       owner_id: AgentId,
       tick: int,
       observation: Observation,
       territorial_claims: object | None,
       prior: BorderLedger | None,
       identity: OwnerSafeSocialIdentity | None,
       organization_concepts: object | None,
       diplomacy: object | None,
       policy: BordersPolicy,
       inbox: Sequence[object] | None = None,
       world_state: object = _MISSING,
       world_event: object = _MISSING,
   ) -> BorderLedger: ...
   ```
   `world_state`/`world_event` are forbidden sentinels and raise
   `TypeError("forbidden_input")` if supplied.
2. Fixed order:
   1. **Validate** owner, tick, observation, prior owner, policy, optional ledgers.
   2. **Collect own claims** from `territorial_claims.claims` where
      `target_kind` is `LOCATION` or `FREQUENT_AREA` and `strength >=
      policy.min_claim_strength`. A missing ledger yields no own domains.
   3. **Observe local adjacency** from `observation.location.entity_id` and
      `observation.exits[*].destination_id`. Add only these edges to the
      owner-local observed edge set; merge with prior observed edges.
   4. **Form contiguous domains** from own claimed locations using only observed
      edges. A component of one location is legal. If
      `policy.domain_contiguity_required` is true, a claimed location with no
      observed edge forms its own component and receives `boundary_unobserved`
      notice. Preserve a prior domain when its exact set is unchanged; otherwise
      mint a new id and expire the old row with `status=expired`.
   5. **Collect frames** from `observation.communications` where the recipient is
      the owner and from `inbox` deliveries. Parse `bdr_v1`; malformed or
      oversize frames add `malformed_frame` and are dropped. Never trust a
      frame's declared provenance or party identity. When `identity` is `None`,
      drop every frame with `unresolved_speaker`; never fall back to a raw
      sender id.
   6. **Resolve anchors** locally:
      - organization -> an `orgc-` id in `organization_concepts.concepts`;
      - settlement -> an observed region id from `observation.regional_context`,
        journey origin/destination, or exit destination region;
      - agent -> the owner's `OwnerSafeSocialIdentity` counterpart;
      - diplomacy treaty -> a `dpg-` `DiplomaticTreaty` with
        `territorial_understanding` subject kind, or a `dpv-`
        `DiplomaticTreatyVersion` with a `territory_acknowledgement` provision,
        in the owner's diplomacy ledger. `trt_v1` is the bounded speech frame,
        not an id prefix.
      Missing anchors retain the row with `unresolved` basis and
      `unresolved_anchor` notice.
   7. **Apply acts** in this closed order: `claim_domain`, `propose`, `accept`,
      `reject`, `recognize`, `expect_access`, `withdraw`, `dispute_domain`.
      An `accept` by a party that did not receive the proposal does not create an
      agreement; it remains a testimony row.
   8. **Derive overlaps/disputes** only from retained peer claims and own
      domains. Intersection is exact `EntityId` intersection. A peer claim is
      testimony, never a shared truth. Create/update one dispute per
      `(domain, counterparty)`.
   9. **Derive recognition status**:
      - `own_claim` basis for every own domain;
      - `direct_observation` for observed boundary edges;
      - `testimony` for peer claims;
      - `agreement` for an agreement with `territorial_acknowledgement`;
      - `recognized` only when the owner's own claim plus at least
        `policy.min_recognition_parties - 1` **distinct evidence source owners**
        (`TESTIMONY` or `AGREEMENT` evidence) agree on the same set; repeated
        retellings from one source never count twice; otherwise `unresolved`;
      - `disputed` when a retained peer claim intersects the same set without
        agreement.
   10. **Expire** rows whose `expiry_tick` is before the current tick or whose
       evidence age exceeds the policy. Expiry is a status, not deletion.
   11. **Enforce caps** via Task 10.
   12. **Recompute digest** and return the immutable ledger.
3. Reject any input type named `WorldState`, `WorldEvent`, `PhysicalRules`, or
   `AgentBody`.
4. No branch returns a command. No branch calls `WorldEngine` or an admission
   helper. No branch reads a peer's organization, diplomacy, formal-rule,
   dispute, evidence, representation, conflict, or territorial ledger.
5. Log only counts:
   `DEBUG borders_update owner_id=%s tick=%s domains=%s agreements=%s disputes=%s notices=%s`.

### Required Interfaces and Contracts

```python
def apply_borders_update(
    *,
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    territorial_claims: object | None,
    prior: BorderLedger | None,
    identity: OwnerSafeSocialIdentity | None,
    organization_concepts: object | None,
    diplomacy: object | None,
    policy: BordersPolicy,
    inbox: Sequence[object] | None = None,
) -> BorderLedger: ...
```

- Input ledgers are optional; an absent `organizations` or `diplomacy` ledger
  leaves anchors unresolved.
- A missing `territorial_claims` ledger leaves the domain list empty.
- A peer claim never becomes an own claim.
- Silence never creates an agreement, recognition, dispute, or access
  expectation.
- The pipeline is deterministic for identical inputs.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — overlapping claims, disputed borders, recognized
  boundaries, access expectations, border agreements.
- Source: `.ai-factory/ARCHITECTURE.md` — "Memory, testimony, and subjective
  concepts"; peer reports are testimony, never authority.
- Source: `src/agents/cognition/territorial.py` `apply_territorial_update`
  975-1072 and `src/agents/cognition/organized_conflict.py` update pipeline.
- Supported combinations: own claims only; own + peer claim overlap; agreement
  proposal + acceptance; reject; withdraw; expired access expectation;
  unresolved organization/diplomacy anchor; malformed frame; all tested.

### Error Handling and Logging

- Invalid owner/prior/policy/observation raise `ValueError` or `TypeError` with a
  stable code and log `ERROR borders_update_rejected reason_code=<code>`.
- Unresolved anchors log `WARN borders_anchor_unresolved kind=%s` with no ref.
- Malformed frames log `WARN borders_frame_dropped reason_code=%s` at most once
  per update.
- Caps/truncation log `WARN borders_truncated family=%s dropped=%s`.
- Never log location ids, owner ids, counterparties, frame bodies, or evidence
  refs.

### Tests

- `tests/unit/test_borders_update.py`
  - `test_missing_territorial_ledger_yields_empty_domains`
  - `test_own_claims_form_contiguous_and_isolated_domains`
  - `test_peer_claim_overlap_creates_dispute_without_reconciliation`
  - `test_agreement_requires_proposal_then_counterparty_acceptance`
  - `test_reject_and_withdraw_are_retained`
  - `test_access_expectation_is_only_created_by_explicit_frame`
  - `test_unresolved_organization_and_diplomacy_anchors_are_retained`
  - `test_malformed_frame_is_dropped_with_notice`
  - `test_world_state_and_event_inputs_are_rejected`
  - `test_update_is_deterministic_and_reads_only_owner_inputs`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_update.py -q`
- Expected: all pass.

### Acceptance Criteria

- The pipeline order is exactly the listed order.
- No command is constructed, submitted, resolved, or blocked.
- Peer claims and agreements remain beliefs with local provenance.
- Overlaps and disputes are retained without reconciliation.
- Identical inputs produce identical ledgers and digests.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_update.py -q`
- `uv run --frozen --python 3.12.14 ruff check src/agents/cognition/borders.py`
- Expected: pass.

## Task 7: Add bounded bdr_v1 boundary speech frames

### Intent

Let owners exchange domain claims, proposals, acceptances, rejections,
recognitions, and access expectations inside existing `Talk`/`Ask`/`Tell`
without a new event, command, or wire record. The frame is bounded, untrusted,
and speaker-bound.

### Implementation Steps

1. Create `src/agents/cognition/borders_communication.py`:
   - `BORDER_FRAME_SUBJECT: Final[str] = "bdr_v1"`
   - `BORDER_FRAME_VERSION: Final[str] = "borders-communication.v1"`
   - `BORDER_FRAME_MAX_CHARS: Final[int] = 256`
   - `BORDER_FRAME_MAX_RELATIONS: Final[int] = 8`
2. Define the exact colon-separated relation payload for one location:
   ```text
   bdr_v1:<act>:<domain_id>:<party_kind>:<party_ref>:<index>:<count>:<location_ref>:<expiry_tick>:<access_mode>:<provision>
   ```
   - `act` is one `AgreementAct` value.
   - `domain_id` is `bdc-` + 16 hex and must equal
     `domain_claim_token_id(speaker_owner, locations)`; it is never trusted on
     its own.
   - `party_kind` is `agent`, `organization`, `settlement`, `unknown`.
   - `party_ref` is a bounded token or `-` for `unknown`.
   - `index` is `0..count-1`; `count` is `1..8`.
   - `location_ref` is exactly one location token; every act carries 1-8
     locations so the receiver can verify the domain id and compute overlap.
   - `expiry_tick` is a non-negative integer or `-`.
   - `access_mode` is one `AccessExpectationMode` value or `-`.
   - `provision` is one `AgreementProvision` value or `-`.
3. Add the frozen `BorderFrame` value:
   ```python
   @dataclass(frozen=True, slots=True)
   class BorderFrame:
       act: AgreementAct
       domain_id: str
       party_kind: CounterpartyKind
       party_ref: str | None
       locations: tuple[str, ...]
       expiry_tick: int | None
       access_mode: AccessExpectationMode | None
       provision: AgreementProvision | None
   ```
   `locations` is 1-8 sorted unique tokens for every act. `domain_id` is never
   `None`; it is derived with
   `domain_claim_token_id(speaker_owner, locations)` and verified on parse. The
   frame is immutable and rejects unknown enum values.
4. Add `encode_border_claim(frame)`, `parse_border_claim(text)`,
   `border_claim_relation(frame)`, and `parse_border_claim_relation(relation)`.
5. Add `attach_border_relation(command, frame)`:
   - accepts only `Talk`, `Ask`, or `Tell`;
   - preserves the command type, recipient, and existing relations;
   - appends at most one group of `BORDER_FRAME_MAX_RELATIONS` relations;
   - returns the same command type, never a new command type.
6. Add `border_frames_from_observation(observation)` and
   `border_frames_from_inbox(inbox)`:
   - only delivered `Talk`/`Ask`/`Tell` to the owner;
   - group relations by `(domain_id, count, act, party_ref)`;
   - require contiguous `0..count-1`, unique indices, exact count, and no
     duplicate locations;
   - drop malformed/oversize groups with `malformed_frame`;
   - assign provenance from delivery, never from a declared frame field.
7. Speaker binding:
   - the sender is the speaker;
   - `party_ref` names the counterparty and can never equal the sender token;
   - a frame cannot claim a mandate, recognition, or acceptance on behalf of
     another party;
   - an `accept` is retained only when the speaking party is the named
     counterparty of a prior proposal.
8. No free-text utterance body. The utterance text is exactly `bdr_v1`.

### Required Interfaces and Contracts

```python
BORDER_FRAME_SUBJECT: Final[str] = "bdr_v1"
BORDER_FRAME_MAX_CHARS: Final[int] = 256
BORDER_FRAME_MAX_RELATIONS: Final[int] = 8

def attach_border_relation(command: object, frame: BorderFrame) -> object: ...
def border_frames_from_observation(observation: Observation) -> tuple[BorderFrame, ...]: ...
def border_frames_from_inbox(inbox: Sequence[object]) -> tuple[BorderFrame, ...]: ...
```

- A frame is at most 256 characters per relation and at most 8 relations.
- Malformed, oversize, speaker-mismatched, duplicate-index, or non-contiguous
  groups are dropped.
- No frame field is an objective world state, permission, or enforcement flag.
- `bdr_v1` is not a new event, command, observer semantic type, or wire genre.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — border agreements and recognized boundaries.
- Source: `.ai-factory/ARCHITECTURE.md` — "Talk/Ask/Tell prove eligible delivery
  only"; "Reports sharing one root are not independent corroboration".
- Source: `src/agents/cognition/diplomacy_communication.py` 93-95, 306-330,
  632-642, 707-721 and `organized_conflict_communication.py` 84-95.
- Supported combinations: all 8 acts; 1 and 8 locations; oversize; missing
  index; duplicate index; speaker mismatch; unknown party; unknown access mode;
  each has a test.

### Error Handling and Logging

- `parse_border_claim` raises `ValueError("frame: <code>")` for a single frame.
- Group assembly drops the whole group and returns a `malformed_frame` reason.
- Logs: `WARN borders_frame_dropped reason_code=%s count=%s` (count only).
- Never log the relation body, location ref, party ref, or speaker.

### Tests

- `tests/unit/test_borders_communication.py`
  - `test_constants_and_field_order_are_frozen`
  - `test_encode_parse_round_trip_for_all_acts`
  - `test_every_act_requires_one_to_eight_locations`
  - `test_domain_id_must_match_the_speaker_location_set`
  - `test_eight_locations_fit_and_nine_are_rejected`
  - `test_oversize_relation_is_dropped`
  - `test_non_contiguous_missing_and_duplicate_indices_are_dropped`
  - `test_speaker_cannot_accept_for_another_party`
  - `test_unknown_party_and_access_matrix`
  - `test_attaching_preserves_command_type_recipient_and_relations`
  - `test_no_new_wire_event_or_command_is_created`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_communication.py -q`
- Expected: all pass.

### Acceptance Criteria

- `bdr_v1` is exactly bounded at 256 characters and 8 relations.
- Only existing `Talk`/`Ask`/`Tell` carry it.
- Malformed or speaker-mismatched frames are dropped.
- No new event, command, observer semantic type, or write pair exists.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_communication.py -q`
- Expected: pass.

## Task 8: Wire border beliefs through cognition, runtime carry, checkpoints, and export

### Intent

Make the border ledger a first-class owner-scoped value in the cognitive loop,
runtime checkpoints, and completed-run result, without exposing it to world
authority or another owner.

### Implementation Steps

1. In `src/agents/cognition/loop.py`:
   - Add `_prepared_borders` to `__slots__` and initialize to `None`.
   - Add `_prepare_borders(loop_input, territorial_claims, organization_concepts,
     diplomacy)` after `_prepare_organized_conflict` and before mediation.
   - If `_borders_mode` is disabled, set `_prepared_borders=None` and return
     `None`.
   - Read the carried ledger from `snapshot.borders`; default to
     `empty_border_ledger(owner_id)`.
   - Call `apply_borders_update(...)` with the tick, observation, territorial
     ledger, organization concepts, diplomacy, identity, and inbox.
   - Log counts only: `borders_prepare mode=%s domains=%s agreements=%s`.
   - Add `prepared_borders` to `CognitiveLoopState`/snapshot carry and to the
     loop result.
2. In `src/agents/cognition/contracts.py`:
   - Add `borders: object | None = None` to `Perspective`.
   - Validate with `require_owner_borders` at the same point as
     `territorial_claims` (335-340).
   - Include it in `detached_copy` (609).
3. In `src/agents/cognition/models.py`:
   - Add `borders` to `SubjectiveSnapshot` (732), `CognitiveLoopProposal`
     (3967), and `CognitiveLoopResult` (4311).
   - Validate owner identity in each `__post_init__`.
4. In `src/agents/cognition/fork_state.py`, add `prepared_borders` next to
   `prepared_organized_conflict` (68).
5. In `src/simulation/agent_runtime.py`:
   - Add `_borders` to `__slots__` and initialize `None`.
   - Add `_commit_borders(ledger, tick)` mirroring
     `_commit_organized_conflict` 1532-1560:
     - read the mode with `getattr(self._loop, "_borders_mode",
       CognitionBordersMode.DISABLED)`; do not add a second mode field;
     - disabled mode clears;
     - a pending ledger without a mode logs `borders_pending_ledger_missing`;
     - wrong type raises `TypeError("borders must be BorderLedger")`;
     - wrong owner raises `AgentRuntimeError.OWNERSHIP`.
   - In `src/simulation/perception.py`, add `borders: object | None = None` to
     `build_perspective` at line 113 and forward it into `Perspective` at line
     381, next to `organized_conflict`.
   - Pass `borders=self._borders` into `build_perspective` (2468 pattern).
   - Commit from `loop_result.borders` (2981 pattern).
   - Restore from `checkpoint.borders` (3586 pattern).
   - Export `borders=self._borders` (3712 pattern).
6. In `src/simulation/run_control.py`:
   - Add `borders: object | None = None` after `organized_conflict` (622).
   - Validate with `require_owner_borders` after the conflict validation (829).
7. In `src/simulation/runner_models.py`:
   - Add `border_ledgers: tuple[object, ...] = ()` after
     `organized_conflict_ledgers` (6394).
   - Validate exact tuple order, exact `BorderLedger` item type, unique
     owner-order, and owner identity (mirror 6764-6785).
8. In `src/simulation/runner.py`:
   - Add `export_border_ledgers()` mirroring
     `export_organized_conflict_ledgers` (5672-5685).
   - Include `border_ledgers=(self.export_border_ledgers())` in the result
     assembly (5180-5210).
9. In `src/agents/cognition/__init__.py` and
   `src/simulation/cognition_contracts.py`, export the new carry symbols.

### Required Interfaces and Contracts

- `Perspective.borders`, `SubjectiveSnapshot.borders`,
  `CognitiveLoopProposal.borders`, `CognitiveLoopResult.borders`,
  `AgentRuntimeCheckpoint.borders`, and `SimulationRunnerResult.border_ledgers`
  all carry the same owner-scoped `BorderLedger` or `None`.
- A foreign owner ledger is rejected at every boundary.
- Disabled mode produces `None`; enabled mode always produces a ledger, even an
  empty one.
- The ledger is not written to any objective event, observer frame, prompt,
  memory, or analysis input during the tick.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — agents/organizations may believe.
- Source: `.ai-factory/ARCHITECTURE.md` — "Objective authority and runtime";
  owner-safe perspectives; deferred subjective finalization.
- Source: V4-12 `organized_conflict` carry at the cited lines.
- Supported combinations: disabled carry; enabled empty ledger; enabled
  non-empty ledger; checkpoint restore; fork prepared state; export; each tested.

### Error Handling and Logging

- Wrong type/owner raises the stable runtime error and does not partially commit.
- A missing pending ledger while enabled logs `WARN borders_pending_ledger_missing
  tick=%s`.
- Restore/export logs counts only.
- Never log owner ids, domain ids, location ids, anchors, or counterparties.

### Tests

- `tests/unit/test_borders_carry.py`
  - `test_disabled_mode_carries_none`
  - `test_enabled_mode_carries_an_empty_ledger`
  - `test_perspective_rejects_a_foreign_ledger`
  - `test_snapshot_proposal_and_result_require_owner_identity`
  - `test_checkpoint_restore_and_export_round_trip`
  - `test_fork_state_carries_prepared_borders`
  - `test_runner_result_exports_owner_ordered_ledgers`
  - `test_world_and_observer_do_not_receive_border_fields`
- Commands:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_carry.py tests/unit/test_agent_runtime.py -q`
- Expected: all pass.

### Acceptance Criteria

- The ledger survives snapshot, proposal, result, checkpoint, restore, fork, and
  completed-run export.
- A foreign ledger is rejected everywhere.
- No world or observer contract gains a border field.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_carry.py -q`
- `uv run --frozen --python 3.12.14 python -c "import simulation.agent_runtime, simulation.run_control, simulation.runner_models"` (via `uv run`)
- Expected: pass.

## Task 9: Derive deterministic boundary edges from the logical location graph

### Intent

A border is the set of observed adjacency pairs where exactly one endpoint is in
the owner's domain. It is not a polygon, a grid line, or a world field. The owner
records only edges it has observed; an unobserved edge is an explicit
`unresolved` boundary, never an invented one.

### Implementation Steps

1. In `src/agents/cognition/borders.py`, add:
   - `observe_local_edges(observation) -> tuple[tuple[EntityId, EntityId], ...]`
     from `observation.location.entity_id` and
     `observation.exits[*].destination_id`.
   - `boundary_edges_for_domain(location_ids, observed_edges) -> tuple[tuple[str, str], ...]`
     returning canonical pairs with exactly one endpoint in the set.
   - `unobserved_domain_locations(location_ids, observed_edges) -> tuple[EntityId, ...]`
     returning in-set locations with no observed incident edge.
2. No function reads `WorldState`, `RegionDefinition`, `LocationRegion`,
   `RouteSpec`, or world adjacency directly. Only the owner's observation and
   prior observed edges are inputs.
3. Merge prior observed edges from `BorderEvidence` with `BoundaryBasis.
   DIRECT_OBSERVATION`; deduplicate by canonical pair.
4. If a domain has no observed edge, set `BoundaryRecognition.status =
   UNRESOLVED` and add `boundary_unobserved` notice.
5. If an agreement or peer testimony covers the same edge pair, set the
   recognition basis to `AGREEMENT` or `TESTIMONY`; if both a dispute and a
   recognition exist for the same edge, `DISPUTED` wins.
6. Add `boundary_summary(ledger)` returning counts only: domains, observed
   edges, unresolved domains, disputed edges, recognized edges.
7. No region membership is converted into a border. A region is a logical label;
   a domain is an owner belief over locations.

### Required Interfaces and Contracts

```python
def observe_local_edges(observation: Observation) -> tuple[tuple[EntityId, EntityId], ...]: ...
def boundary_edges_for_domain(
    location_ids: Sequence[EntityId],
    observed_edges: Sequence[tuple[EntityId, EntityId]],
) -> tuple[tuple[str, str], ...]: ...
def unobserved_domain_locations(
    location_ids: Sequence[EntityId],
    observed_edges: Sequence[tuple[EntityId, EntityId]],
) -> tuple[EntityId, ...]: ...
```

- Edges are canonical sorted pairs and deduplicated.
- A self-edge is rejected.
- A location with no observed edge is unresolved, not a closed border.
- No grid, coordinate, polygon, area, or region-to-border conversion exists.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — "WorldEngine knows only locations and occupancy",
  "No grid conversion", "recognized boundaries".
- Source: `src/world/models.py` `Location.adjacent`; `src/world/observations.py`
  `VisibleExit`; `src/world/regions.py` `RegionDefinition` is a label only.
- Supported combinations: one isolated location; two adjacent locations; a
  domain with an unobserved side; a domain touching a region edge; an agreement
  covering one edge; each tested.

### Error Handling and Logging

- Invalid edge input raises `ValueError("boundary_edge: <code>")`.
- Unobserved domains log `WARN borders_boundary_unobserved domain_count=%s` with
  counts only.
- Never log location ids or edge pairs.

### Tests

- `tests/unit/test_borders_boundaries.py`
  - `test_isolated_domain_has_no_edges_and_is_unresolved`
  - `test_two_adjacent_locations_produce_one_canonical_boundary_edge`
  - `test_edges_are_boundary_only_when_one_endpoint_is_in_the_set`
  - `test_prior_observed_edges_are_merged_and_deduplicated`
  - `test_dispute_wins_over_recognition_for_the_same_edge`
  - `test_region_membership_is_never_converted_to_a_border`
  - `test_no_grid_coordinate_or_polygon_symbol_is_used`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_boundaries.py -q`
- Expected: all pass.

### Acceptance Criteria

- Boundary edges are observed adjacency only.
- No grid/geometry/region-to-border conversion exists.
- Unobserved boundaries are explicit and never invented.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_boundaries.py -q`
- Expected: pass.

## Task 10: Enforce border caps, notices, and owner export

### Intent

Keep the ledger bounded and deterministic under pressure without silently
dropping an active claim or turning overflow into a truth. Export only the
detached, metadata-safe rows that analysis needs.

### Implementation Steps

1. Add `enforce_borders_limits(ledger, policy)`:
   - Drop expired evidence older than `max_domain_evidence_age_ticks` first and
     recompute each affected domain's strength/recognition from remaining
     evidence.
   - Drop terminal disputes (`withdrawn`, `expired`) oldest first.
   - Drop terminal agreements (`withdrawn`, `expired`, `superseded`) oldest
     first.
   - Drop `expired` domains oldest first.
   - Never drop an active `claimed`, `recognized`, or `disputed` domain; never
     drop an `apparent_acceptance`/`recognized` agreement; never drop a
     non-terminal dispute.
   - If a family is still over cap and no droppable row exists, raise
     `ValueError("borders_capacity_reached")` and keep the prior ledger.
   - Add `borders_truncated:<family>` notice for each pruned family and
     `borders_capacity_reached` only on failure.
2. Apply the same caps in `BorderLedger.__post_init__` and after every update.
3. Add `export_border_rows(ledger) -> tuple[BorderExportRow, ...]`:
   - one row per domain, recognition, access expectation, agreement, dispute;
   - owner token is a stable hash of the owner id, not the raw id;
   - location tokens are stable hashes or already-public opaque tokens, never
     raw `EntityId`;
   - anchors are opaque bounded tokens;
   - no evidence bodies, frame bodies, or free text.
4. Add `border_export_digest(rows)` canonical SHA-256.
5. Ensure export order is `(row_kind, row_id)` and stable.
6. Add `borders_notice_counts(ledger)` returning a sorted tuple of
   `(code, count)` for logs and publication.

### Required Interfaces and Contracts

```python
def enforce_borders_limits(ledger: BorderLedger, policy: BordersPolicy) -> BorderLedger: ...
def export_border_rows(ledger: BorderLedger) -> tuple[BorderExportRow, ...]: ...
def border_export_digest(rows: Sequence[BorderExportRow]) -> str: ...
```

- Caps are cognition policy, not runner configuration.
- Active domains and active agreements are never silently dropped.
- Overflow with nothing droppable fails closed.
- The export is metadata-only and deterministic.

### Requirement Evidence (when reconciliation applies)

- Source: `.ai-factory/ARCHITECTURE.md` — bounded optional channels and
  metadata-only logs.
- Source: V4-12 `organized_conflict` caps/export precedent.
- Supported combinations: over-cap observations droppable; over-cap active rows
  not droppable; expired rows pruned; duplicate export digest stable; each
  tested.

### Error Handling and Logging

- Capacity failure raises `ValueError("borders_capacity_reached")` and logs
  `ERROR borders_capacity_reached family=%s`.
- Truncation logs `WARN borders_truncated family=%s dropped=%s`.
- Never log row ids, owner ids, locations, anchors, or evidence.
- A failed update leaves the prior ledger untouched.

### Tests

- `tests/unit/test_borders_caps.py`
  - `test_evidence_cap_prunes_oldest_first`
  - `test_terminal_disputes_and_agreements_are_dropped_before_domains`
  - `test_active_domains_and_agreements_are_never_dropped`
  - `test_overflow_with_nothing_droppable_fails_closed`
  - `test_notice_counts_are_sorted_and_deterministic`
  - `test_export_rows_are_metadata_only_and_digest_stable`
  - `test_export_never_contains_raw_owner_or_entity_ids`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_caps.py -q`
- Expected: all pass.

### Acceptance Criteria

- Caps are enforced deterministically and never drop active authority-shaped
  beliefs silently.
- Overflow with nothing droppable fails closed.
- Export contains only hashed/opaque tokens and closed labels.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_caps.py -q`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: a peer claim is treated as a shared claim or an obligation.
  Mitigation: every peer row is `testimony` with local provenance; Task 6 tests
  assert no reconciliation and no command effect.
- Risk: an agreement or access expectation blocks a command.
  Mitigation: no command path exists; Task 6/23 tests assert a physically
  possible command still passes admission.
- Risk: boundary edges become a hidden world topology.
  Mitigation: only observed local edges; unobserved is explicit; Task 9 tests
  reject region/grid conversion.
- Risk: runtime carry breaks snapshots or checkpoints.
  Mitigation: Task 8 mirrors the proven V4-12 carry and adds restore/export
  round trips.
- Risk: cap handling drops an active claim.
  Mitigation: Task 10 forbids dropping active domains/agreements and fails closed
  instead.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
