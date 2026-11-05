# Phase 2: Owner-Scoped Treaty Beliefs

Plan: [index.md](index.md)
Tasks: 4-10
Depends on: Phase 1

## Objective

Add retained owner-scoped treaty anchors, immutable versions with forward-only
lineage, participant declarations, later-generation recollections, treaty
misrepresentation observations, and retained termination/conflict rows. Treaties
travel as bounded `trt_v1` frames inside existing `Talk`/`Ask`/`Tell` speech.
The results remain beliefs: no treaty blocks a command, grants access, moves a
resource, enforces a ceasefire, or becomes a global registry.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/agents/cognition/diplomacy.py` | `DiplomaticRelation` 616-635; `DiplomaticParty` 638-659; `DiplomaticInstrument` 768-811; `DiplomaticDeclaration` 815-841; `DiplomaticTermination` 872-894; `DiplomaticConflict` 897-925 | Exact row style: frozen slotted dataclasses, closed enums, bounded tokens, no free-text terms. |
| `src/agents/cognition/diplomacy.py` | `_Builder` 2328-2657; `_process_frame` 2706-2931; `_apply_frames` 2932-2981; `_apply_contact_anchors` 2982-3024 | Deterministic accumulation, local party resolution, frame dedupe, and notice handling to mirror for treaties. |
| `src/agents/cognition/diplomacy.py` | `diplomacy_envoy_status` 1451-1482; `_declaration_counts_for_party` 1485-1521; `diplomacy_instrument_status` 1524-1626 | Current standing and representative acceptance rules to generalize for treaty versions. |
| `src/agents/cognition/diplomacy.py` | `apply_diplomacy_update` 3152-3206; `record_diplomacy_utterance` 3209-3254 | The ordered pipeline and the self-authored speech path. |
| `src/agents/cognition/diplomacy.py` | `enforce_diplomacy_limits` 1999-2247; `diplomacy_ledger_digest` 1371-1425 | Cap enforcement, relation protection, and canonical digest to extend. |
| `src/agents/cognition/diplomacy_communication.py` | `DIPLOMACY_FRAME_FIELD_COUNT` 63; `_FRAME_KEYS` 102-119; `encode_diplomacy_frame` 241-253; `parse_diplomacy_frame` 256-320; `diplomacy_frame_party_matches` 350-365; `diplomacy_frames_from_observation` 367-409 | Existing bounded frame grammar and verified-speaker binding; `trt_v1` must not modify `dip_v1`. |
| `src/agents/cognition/delegation_representation.py` | `RepresentationScopeKind` 103-112; `_derive_mandate` 1233-1305; `representation_status` 1306-1315 | Recognized representative and scope coverage source. |
| `src/agents/cognition/institutional_memory.py` | `institutional_entry_id` 340-352; `InstitutionalMemoryEntry` 655-796; `append_institutional_memory_entry` 1264-1323 | Owner-local institutional-memory entry identity used only as an opaque anchor. |
| `src/world/artifacts.py` | `DurableRecordGenre` 97-155; `DurableRecordsRuleContext` 170+; `record_genre` 330 | Durable records are objective artifacts referenced as opaque anchors, never rewritten by diplomacy. |
| `src/simulation/agent_runtime.py` | 1498-1520 | Existing ledger carry and metadata-only DEBUG counts. |
| `src/simulation/runner_models.py` | 6380-6386, 6739-6755 | `diplomacy_ledgers` ordered tuple and owner validation; no result-document change. |
| `src/agents/cognition/loop.py` | 2994-3009, 5871-5878 | Existing cognition carry of `DiplomacyLedger`. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/agents/cognition/diplomacy.py` | modify | Add treaty rows, ledger groups, status derivation, recollection alignment inputs, termination/conflict kinds, caps, pipeline, and digest coverage. |
| `src/agents/cognition/diplomacy_communication.py` | modify | Add `trt_v1` acts, frame dataclass, parser/encoder, relation helper, utterance helper, and speaker binding. |
| `src/agents/cognition/__init__.py` | modify | Export treaty rows, status helpers, frame types, and policy. |
| `src/simulation/agent_runtime.py` | modify | Add treaty counts to existing DEBUG carry log. |
| `tests/unit/test_diplomacy_treaty_records.py` | create | Row validation, version DAG, anchors, digest. |
| `tests/unit/test_diplomacy_treaty_declarations.py` | create | Declarations, recollections, termination, conflicts. |
| `tests/unit/test_diplomacy_treaty_acceptance.py` | create | Status, multi-party acceptance, renewal, expiry, supersession. |
| `tests/unit/test_diplomacy_treaty_communication.py` | create | `trt_v1` encode/parse/trust. |
| `tests/unit/test_diplomacy_treaty_collection.py` | create | Frame collection, idempotence, participant resolution. |
| `tests/unit/test_diplomacy_treaty_termination.py` | create | Expiry, supersession, conflicts, misrepresentation. |
| `tests/unit/test_diplomacy_treaty_capacity.py` | create | Caps, truncation, protected rows. |
| `tests/unit/test_diplomacy_treaty_runtime.py` | create | Digest, carry, result tuple. |

## Task 4: Define treaty and version records with record and institutional anchors

### Intent

Create the retained treaty anchor and the immutable version DAG. This is the
object that later generations remember and renew, and the object analysis
publishes. It must carry participants, recognized-representative provenance,
record anchors, institutional-memory anchors, and a canonical terms digest
without storing free-text terms.

### Implementation Steps

1. Add `DiplomaticTreaty` to `diplomacy.py` with exactly these fields:
   - `treaty_id: str`
   - `relation_id: str`
   - `participant_party_ids: tuple[str, ...]`
   - `subject_kind: TreatySubjectKind`
   - `current_version_id: str`
   - `opened_tick: int`
   - `last_tick: int`
   - `provenance: DiplomaticProvenance`
   - `revision: int`
   Validate: `dpg-` ID, `dpl-` relation ID, at least two unique participants,
   subject enum, `dpv-` current version ID, ticks non-negative and ordered,
   revision non-negative, no forbidden fields.
2. Add `DiplomaticTreatyVersion` with exactly these fields:
   - `version_id: str`
   - `treaty_id: str`
   - `version_index: int`
   - `parent_version_ids: tuple[str, ...]`
   - `change_kind: TreatyChangeKind`
   - `participant_party_ids: tuple[str, ...]`
   - `provision_kinds: tuple[TreatyProvisionKind, ...]`
   - `terms_digest: str`
   - `record_refs: tuple[str, ...]`
   - `institutional_memory_refs: tuple[str, ...]`
   - `effective_tick: int`
   - `end_tick: int | None`
   - `proposer_party_id: str`
   - `proposer_envoy_ref: str | None`
   - `provenance: DiplomaticProvenance`
   - `revision: int`
   Validate: `dpv-`/`dpg-` IDs, `version_index >= 1`, zero to two unique
   `dpv-` parents, closed change kind, at least two participants, one to
   `TreatyPolicy.max_provisions` unique provision kinds, 64 lowercase hex
   `terms_digest`, bounded record refs, bounded 64-hex institutional-memory
   refs, ordered effective/end ticks, proposer in participants, optional
   proposer envoy token, revision.
3. Add `treaty_terms_digest(subject_kind, provision_kinds,
   effective_tick, end_tick) -> str` using SHA-256 over a canonical pipe-joined
   string and returning 64 lowercase hex characters. The digest is
   owner-independent so a later generation in another owner can compare its
   claimed digest to a retained version digest. It never contains free text.
4. Extend `_FORBIDDEN_FIELD_NAMES` use by running `_check_no_forbidden` on both
   new rows. `treaty_id`, `treaty_ref`, `version_id`, and `record_refs` must
   pass; `treaty` and `binding` remain forbidden exact names.
5. Add these ledger fields with empty defaults, after the existing `notices`
   field so no existing positional field order changes:
   - `treaties: tuple[DiplomaticTreaty, ...] = ()`
   - `treaty_versions: tuple[DiplomaticTreatyVersion, ...] = ()`
   - `treaty_declarations: tuple[...] = ()` (defined in Task 5)
   - `treaty_recollections: tuple[...] = ()` (defined in Task 5)
   - `treaty_misrepresentations: tuple[...] = ()` (defined in Task 5)
6. In `DiplomacyLedger.__post_init__`, validate treaty rows in this order:
   - rows are the exact frozen type and sorted by tick then ID;
   - every treaty `relation_id` resolves in `relations`;
   - every treaty participant resolves in `parties`;
   - the owner self-party is first in `participant_party_ids`;
   - every treaty `current_version_id` resolves in `treaty_versions`;
   - version `treaty_id` resolves and `version_index` is unique per treaty;
   - indices for each treaty start at 1 and are contiguous;
   - `original` has index 1 and no parents; every other change kind has at
     least one parent with a lower index in the same treaty;
   - every version participant resolves and includes the owner self-party;
   - every version proposer party is in that version's participants;
   - every proposer envoy (when present) resolves in `envoys` for the same
     relation.
   Foreign or forward references fail with `diplomacy_foreign_reference` or
   `diplomacy_treaty_lineage_invalid`.
7. Add all six treaty groups to `diplomacy_ledger_digest` as sorted `asdict`
   lists. Keep existing groups and key order semantics.
8. Export `DiplomaticTreaty`, `DiplomaticTreatyVersion`, and
   `treaty_terms_digest` from `agents.cognition`.

### Required Interfaces and Contracts

- A treaty anchor always includes the owner self-party first. Its
  `participant_party_ids` is the retained union across versions; the current
  version's participants define current membership. A later version may add
  participants or remove another party, but it never removes the self-party;
  an owner withdrawal creates a `termination` version that retains it.
- `current_version_id` is the highest `version_index`, meaning the latest
  proposed version. It is not automatically the accepted version; acceptance
  and supersession are derived by Task 6.
- `record_refs` are opaque owner-visible durable-record anchors. V4-11 neither
  creates nor mutates a durable record.
- `institutional_memory_refs` are opaque owner-local entry IDs. V4-11 neither
  creates nor mutates an `InstitutionalMemoryLedger`.
- `terms_digest` is content-addressed and safe to publish; it is not a
  substitute for truth and is never logged.
- No row stores a free-text ceasefire condition, access rule, migration quota,
  resource amount, trade price, territorial boundary, or aid description.

### Requirement Evidence (when reconciliation applies)

- Original Request "Treaties must exist through: records, participants,
  recognized representatives, institutional memory, agent beliefs" maps to
  `record_refs`, `participant_party_ids`, `proposer_envoy_ref`/declarations,
  `institutional_memory_refs`, and the ledger itself.
- Original Request "Track versions and lineage" maps to `version_index` and
  `parent_version_ids`.
- `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts"
  and "Important V3 seams": durable records and institutional memory remain
  owner/objective anchors, not enforced obligations.

### Error Handling and Logging

- Invalid rows raise stable `DiplomacyError` codes:
  `diplomacy_invalid_treaty`, `diplomacy_treaty_lineage_invalid`,
  `diplomacy_treaty_terms_invalid`, `diplomacy_foreign_reference`.
- Log only `treaty_version_appended versions=%s` and
  `treaty_anchor_updated treaties=%s` at DEBUG. Never log IDs, terms digests,
  record anchors, institutional-memory anchors, or participant tokens.

### Tests

`tests/unit/test_diplomacy_treaty_records.py`:

- Construct a two-party and a four-party treaty anchor; assert self-party
  first and ordered participants.
- Assert fewer than two participants, duplicate participants, foreign
  relation/party/version references, and self-party not first fail.
- Construct original, amendment, renewal, accession, withdrawal, suspension,
  and termination versions; assert valid lineage.
- Assert non-original without parents, parent with equal/higher index, parent
  from another treaty, non-contiguous indices, duplicate versions, and
  forward references fail.
- Assert `treaty_terms_digest` is deterministic, owner-independent, sensitive
  to subject/provision/tick inputs, and exactly 64 lowercase hex characters.
- Assert record and institutional-memory anchors are bounded, sorted, unique,
  and reject free-text or oversize values.
- Use a real `InstitutionalMemoryLedger` entry and a real durable-record anchor
  in one version; assert both round-trip and that neither source ledger is
  mutated.
- Assert `diplomacy_ledger_digest` changes when any treaty row changes and is
  stable for equal rows.

### Acceptance Criteria

- Treaty anchors and versions are immutable, retained, and referenced only
  inside the owner ledger.
- Version indices and parent links form a deterministic forward-only DAG.
- Records and institutional memory appear only as opaque anchors.
- No free-text treaty terms exist.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_records.py tests/unit/test_diplomacy_records.py -q`
- Expected: all tests pass.

## Task 5: Define treaty declarations recollections and terminations

### Intent

Add the acts and observations that make a treaty collective: participant
declarations, later-generation recollections, envoy misrepresentation
observations, retained terminations, and explicit conflicts.

### Implementation Steps

1. Add `DiplomaticTreatyDeclaration` with exactly:
   - `declaration_id: str`
   - `treaty_id: str`
   - `version_id: str`
   - `declarer_party_id: str`
   - `envoy_ref: str | None`
   - `act: TreatyDeclarationAct`
   - `declared_tick: int`
   - `provenance: DiplomaticProvenance`
   - `independence_ref: str | None`
   - `revision: int`
   Validate IDs, resolved version, party in that version's participants,
   optional envoy resolves in the same relation, act enum, tick, optional
   independence ref, revision.
2. Add `DiplomaticTreatyRecollection` with exactly:
   - `recollection_id: str`
   - `treaty_ref: str`
   - `version_ref: str`
   - `subject_kind: TreatySubjectKind`
   - `basis: TreatyRecollectionBasis`
   - `stance: TreatyRecollectionStance`
   - `claimed_terms_digest: str | None`
   - `confidence: float`
   - `first_tick: int`
   - `last_tick: int`
   - `independence_ref: str | None`
   - `provenance: DiplomaticProvenance`
   - `revision: int`
   Validate `dpz-` ID, bounded opaque `treaty_ref`/`version_ref` tokens,
   subject/basis/stance enums, optional 64-hex claimed digest, quantized
   confidence in `[0.0, 1.0]` with the same quantization helper style as
   representation/evidence rows, ordered ticks, optional independence ref,
   provenance, revision. A recollection may reference a treaty or version that
   is not present locally; that is legal and remains unresolved.
3. Add `DiplomaticTreatyMisrepresentation` with exactly:
   - `misrepresentation_id: str`
   - `version_id: str`
   - `kind: DiplomaticMisrepresentationKind`
   - `observed_tick: int`
   - `envoy_ref: str`
   - `declarer_party_id: str`
   - `provenance: DiplomaticProvenance`
   Validate `dpj-` ID, version ID, existing four closed kinds, tick, envoy
   token, declarer party.
4. Extend `DiplomaticTerminationKind` with
   `TREATY_TERMINATED = "treaty_terminated"`. Extend
   `_TERMINATION_KINDS_BY_TARGET` with:
   - `"treaty": {"party_withdrew", "treaty_terminated", "superseded",
     "expired"}`
   - `"treaty_version": {"party_withdrew", "treaty_terminated", "superseded",
     "expired"}`
   Keep every existing target and kind unchanged.
5. Extend `DiplomaticConflictKind` with
   `TREATY_PARTICIPANT_CONFLICT = "treaty_participant_conflict"`,
   `TREATY_RECORD_CONFLICT = "treaty_record_conflict"`, and
   `TREATY_RECOLLECTION_CONFLICT = "treaty_recollection_conflict"`. Reuse
   `DiplomaticConflict`; `instrument_refs` may hold `dpi-`/`dpg-`/`dpv-`
   tokens, and `party_refs` may hold `dpp-` tokens.
6. Add the remaining ledger groups (`treaty_declarations`,
   `treaty_recollections`, `treaty_misrepresentations`) with frozen row types
   and ordered validation. Validate declarations resolve locally; recollections
   do not require local resolution. Version parent links are the only retained
   lineage source; do not add a duplicate owner lineage table.
7. Extend the ledger digest with all remaining treaty groups.

### Required Interfaces and Contracts

- `DiplomaticTreatyDeclaration` is the only way a participant is counted as
  accepting, rejecting, suspending, terminating, interpreting, or ignoring a
  version.
- `DiplomaticTreatyRecollection` is a belief held by the ledger owner. It may
  remember, reinterpret, ignore, or intend to renew. It cannot create a local
  treaty or version.
- `claimed_terms_digest` is a claim. It is never compared to the record in
  cognition; only detached analysis may classify inconsistency.
- There is no `misremembered`, `lie`, `false`, `truth`, `guilty`, `liable`, or
  `bad_faith` field.
- A recollection with an absent `claimed_terms_digest` is legal and remains
  unresolved in analysis; it is never assumed consistent.
- Terminations are appended, never used to delete rows.

### Requirement Evidence (when reconciliation applies)

- Original Request "Later generations may: remember them, misremember them,
  reinterpret them, ignore them, renew them" maps to recollection stance/basis
  and researcher-only alignment.
- `.ai-factory/ARCHITECTURE.md` "Preserve append-only authoritative history"
  and V4-08/V4-09 retained-contradiction precedent.
- V4-10 `DiplomaticMisrepresentation` 844-868 and `DiplomaticTermination`
  871-894 are the exact observation/retention precedents.

### Error Handling and Logging

- Invalid declarations raise `diplomacy_invalid_treaty_declaration`; invalid
  recollections raise `diplomacy_invalid_recollection`; invalid terminations
  raise `diplomacy_invalid_termination`.
- Log only counts and closed kinds:
  `treaty_recollection_retained stance=<closed> basis=<closed>`.
- Never log treaty/version IDs, claimed digests, record anchors, participant
  identities, or recollection text (there is none).

### Tests

`tests/unit/test_diplomacy_treaty_declarations.py`:

- Accept each declaration act on a valid version; reject a party outside the
  version participant set, a foreign version, and an unknown envoy.
- Assert recollection stance/basis closure, confidence quantization, optional
  claimed digest, absent local treaty/version, and no truth/misremember field.
- Assert a recollection never creates a `DiplomaticTreaty` or version.
- Assert treaty termination targets and kinds; existing termination behavior
  is unchanged.
- Assert new conflict kinds coexist with V4-10 kinds and no row is reconciled.
- Assert `diplomacy_ledger_digest` covers declarations, recollections,
  misrepresentations, and lineage.

### Acceptance Criteria

- Participant declarations, recollections, misrepresentation observations,
  terminations, conflicts, and lineage rows are retained and validated.
- A later-generation recollection is legal without a local treaty/version.
- No truth, lie, guilt, or enforcement field exists.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_declarations.py tests/unit/test_diplomacy_termination.py -q`
- Expected: all tests pass.

## Task 6: Derive treaty version status and representative acceptance

### Intent

Make acceptance and status deterministic, multi-party, and authority-aware.
This is where "recognized representatives" becomes real: a principal can bind
its own belief, a recognized envoy with covering scope can count for its party,
and an unrecognized envoy never completes a party.

### Implementation Steps

1. Add `diplomacy_treaty_version_status(version, declarations, *, tick,
   policy, treaty_policy, representation, envoys) ->
   tuple[TreatyStatus, TreatyAcceptanceBasis]` with this precedence:
   1. `expired` when `end_tick is not None and tick >= end_tick`;
   2. `proposed` with acceptance basis `rejected` when any `reject`
      declaration exists for the version (the closed status vocabulary has no
      separate `rejected` member);
   3. `terminated` when every version participant has a `terminate`
      declaration and at least two participants exist;
   4. `suspended` when every version participant has a `suspend` declaration
      and at least two participants exist;
   5. `apparently_accepted` when every version participant has an `accept`
      declaration that counts, with at least two participants;
   6. `proposed` otherwise.
2. Add `diplomacy_treaty_statuses(treaty, versions, declarations, *, tick,
   policy, treaty_policy, representation, envoys) ->
   tuple[tuple[str, TreatyStatus, TreatyAcceptanceBasis], ...]` returning one
   row per version sorted by `version_index`. After base statuses are computed,
   mark an earlier version `superseded` when any later version of the same
   treaty reaches `apparently_accepted`, `suspended`, or `terminated`. A
   rejected or still-proposed later version does not supersede the earlier
   accepted version.
3. Add `diplomacy_treaty_current_version(treaty, versions) -> version` that
   returns the highest `version_index` row and raises
   `diplomacy_treaty_lineage_invalid` if it is absent.
4. Generalize `_declaration_counts_for_party` into a private helper that
   accepts a target kind string and target ID. For treaties pass
   `"treaty"` so `diplomacy_scope_covers` uses the treaty mapping and the
   long-running duration rule. Keep the existing instrument path byte-
   identical.
5. Add `treaty_participant_union(treaty, versions) -> tuple[str, ...]` and
   use it to update the anchor participant set when a version accedes or
   withdraws. Order is owner self-party first, then sorted unique party IDs.
6. Add `treaty_provision_histogram(versions)` and
   `treaty_change_histogram(versions)` pure helpers for later metrics; they
   return sorted tuples of `(closed_value, count)`.

### Required Interfaces and Contracts

- A principal declaration is a declaration with `envoy_ref is None`; it counts
  directly for its party.
- One actor or envoy cannot satisfy two parties in the same version. If the
  same `envoy_ref` is used for a second party's declaration, that second
  declaration does not count and a retained conflict is appended.
- An envoy declaration counts only when:
  - the envoy belongs to the same relation;
  - current derived standing is `recognized`;
  - the mandate exists in the owner representation ledger;
  - `diplomacy_scope_covers(instrument_kind="treaty", ...)` is true.
- `single_act` and `occasion` mandates never count for a treaty.
- A named mandate subject must equal the treaty's subject token.
- `apparently_accepted` binds nobody and grants no permission.
- `terminate` and `suspend` require every participant to declare; one party's
  declaration is retained but does not terminate or suspend the collective
  belief.
- A later accepted, suspended, or terminated version supersedes earlier
  versions; a later rejected version leaves the earlier accepted version
  active.
- Two different treaties over the same relation and subject may coexist.
- `treaty_status` is a derived read, never a stored authority flag.

### Requirement Evidence (when reconciliation applies)

- Original Request "recognized representatives" and V4-10's "Representatives
  may misrepresent their society or lack full authority".
- `.ai-factory/ARCHITECTURE.md` V4-09 recognition rules and V4-10 acceptance
  rules.
- `src/agents/cognition/delegation_representation.py` 1171-1315.

### Error Handling and Logging

- Missing/foreign mandate yields non-counting standing, not an exception.
- Missing version/treaty raises `diplomacy_treaty_lineage_invalid`.
- Log `treaty_status_derived versions=%s accepted=%s superseded=%s` at DEBUG
  with counts only. Never log party or envoy identities.

### Tests

`tests/unit/test_diplomacy_treaty_acceptance.py`:

- Three-party treaty: principal declarations for all three yield
  `apparently_accepted` / `all_participants_declared`.
- One missing participant stays `proposed`.
- Recognized envoy with `until_revoked` and `negotiate` scope counts; a
  `single_act` or `occasion` mandate does not; a `speak_for` mandate does not.
- Self-claim envoy never counts.
- Reject yields `proposed` with a `rejected` acceptance basis; all-party
  terminate yields `terminated`;
  all-party suspend yields `suspended`.
- Expiry boundary is exclusive.
- Renewal version accepted marks version 1 `superseded` and version 2
  `apparently_accepted`.
- Renewal version rejected leaves version 1 `apparently_accepted`.
- Accession adds a participant in version 2; withdrawal removes a participant
  in version 2 while retaining the anchor union.
- Two treaties with the same participants and subject both remain accepted.
- One envoy cannot satisfy two parties in the same version; the second
  declaration does not count and a conflict is retained.
- Version parent links match change kinds; every non-original version has a
  lower-index parent.

### Acceptance Criteria

- Status and acceptance are deterministic and multi-party.
- Principal and recognized-envoy paths are distinct and test-covered.
- Supersession occurs only after a later version is collectively decided
  (accepted, suspended, or terminated).
- No treaty status is treated as permission or enforcement.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_acceptance.py tests/unit/test_diplomacy_acceptance.py -q`
- Expected: all tests pass.

## Task 7: Add bounded trt_v1 treaty speech frames

### Intent

Let agents propose, accept, reject, amend, renew, accede, withdraw, suspend,
terminate, recollect, interpret, and ignore treaties through existing speech.
`dip_v1` must remain exactly 15 fields and 320 characters. `trt_v1` is larger
than one `CommunicationRelation.object` can carry, so it travels as a small,
ordered set of bounded relation chunks inside the same utterance.

### Implementation Steps

1. In `diplomacy_communication.py`, add:
   - `TREATY_FRAME_VERSION = "trt_v1"`
   - `TREATY_FRAME_SUBJECT = "trt_v1"`
   - `TREATY_FRAME_MAX_CHARS = 832`
   - `TREATY_FRAME_FIELD_COUNT = 22`
   - `TREATY_CHUNK_MAX_CHARS = 240`
   - `TREATY_MAX_CHUNKS = 4`
   - `TREATY_CHUNK_PREDICATE_PREFIX = "trt_chunk_"`
2. Add `TreatyAct` with exactly:
   `treaty_propose`, `treaty_accept`, `treaty_reject`, `treaty_accede`,
   `treaty_amend`, `treaty_renew`, `treaty_withdraw`, `treaty_suspend`,
   `treaty_terminate`, `treaty_recollect`, `treaty_interpret`,
   `treaty_ignore`.
3. Add `TreatyFrame` with exactly these 22 serialized keys in this order:
   `act`, `treaty_ref`, `version_ref`, `relation_ref`, `participant_refs`,
   `party_kind`, `party_ref`, `envoy_ref`, `mandate_ref`, `subject_kind`,
   `change_kind`, `basis`, `stance`, `confidence`, `provision_kinds`,
   `terms_digest`, `record_refs`, `institutional_memory_refs`,
   `effective_tick`, `end_tick`, `provenance`, `revision`.
   `participant_refs`, `provision_kinds`, `record_refs`, and
   `institutional_memory_refs` are comma-separated bounded lists. A
   participant ref is `<closed-party-kind>:<anchor-token>` where the anchor is
   omitted only for `unknown` and encoded as the empty segment.
4. Add `encode_treaty_frame`, `parse_treaty_frame`,
   `encode_treaty_frame_chunks`, `treaty_frame_relations`,
   `parse_treaty_frame_relations`, `treaty_frame_party_matches`,
   `treaty_frames_from_observation`, `treaty_frames_from_command`, and
   `treaty_communicate_utterance`.
5. Transport contract:
   - `encode_treaty_frame` returns the canonical 22-field string and enforces
     the 832-character cap.
   - `encode_treaty_frame_chunks` splits that string into at most
     `TREATY_MAX_CHUNKS` chunks of at most `TREATY_CHUNK_MAX_CHARS`
     characters. An 832-character frame therefore needs four chunks.
   - `treaty_frame_relations` returns one `CommunicationRelation` per chunk
     with `subject="trt_v1"`, `predicate="trt_chunk_00"`…`"trt_chunk_03"`,
     and `object` equal to the chunk. This stays inside the world
     communication cap (`CommunicationRelation.object` max 256,
     `MAX_COMMUNICATION_RELATIONS=32` in `src/world/communications.py`).
   - `treaty_communicate_utterance` reserves `len(chunks)` relations; if the
     utterance already has fewer than that many free relation slots, it logs
     `treaty_frame_skipped reason=relation_limit` and returns the command
     unchanged.
   - `treaty_frames_from_observation` groups relations by
     `(subject, chunk_index)`, rejects missing/duplicate/out-of-order chunks,
     reassembles the canonical string, and only then parses the frame.
6. Enforce:
   - strict field count, subject, predicate, and max length;
   - no whitespace or control characters;
   - closed enums only;
   - `basis` and `stance` required and closed for `treaty_recollect`;
     `confidence` required for `treaty_recollect` and quantized into `[0,1]`;
   - at least two participants for `propose`, `amend`, `renew`, `accede`,
     `withdraw`, `suspend`, and `terminate`;
   - one to eight provision kinds for version-creating acts;
   - exactly 64 lowercase hex for `terms_digest` when present;
   - a verified speaker must equal `envoy_ref`; mismatched frames are dropped
     with `WARNING treaty_frame_dropped reason=speaker_mismatch`;
   - peer-supplied `provenance` is ignored and replaced by `communicated`;
     the owner's own command frames use `self_declared`;
   - a peer-supplied `mandate_ref` is only a claim and never grants standing.
7. Keep `dip_v1` constants, parsing, field count, and max length unchanged.
   `parse_treaty_frame_relations` must never interpret a `dip_v1` relation.

### Required Interfaces and Contracts

- `trt_v1` is an utterance-body grammar, not an event, command, observer
  semantic type, or write pair.
- Treaty frames travel only in existing `Talk`/`Ask`/`Tell` relations.
- A frame never contains free text, a ceasefire condition, an access rule, a
  price, a quota, or a boundary description.
- A recollection frame carries an opaque `treaty_ref`, `version_ref`,
  `subject_kind`, `basis`, `stance`, `confidence`, optional `terms_digest`,
  and `provenance`; it creates no local treaty.
- The canonical frame bound is 832 characters. A single relation object is
  capped at 240 characters so the full frame always fits the existing world
  communication contract. Oversize frames are dropped, not truncated.
- Chunk relations are ordered and complete. A missing, duplicate, or
  out-of-order chunk is a malformed frame and is dropped with a notice.

### Requirement Evidence (when reconciliation applies)

- Original Request "Treaties must exist through ... agent beliefs" and
  "Later generations may remember ... reinterpret ... ignore ... renew".
- `.ai-factory/ARCHITECTURE.md` "Speech is the only claim channel" and V4-10
  `dip_v1` seam.
- `src/agents/cognition/diplomacy_communication.py` 60-320;
- `src/world/communications.py` `MAX_COMMUNICATION_RELATIONS` 50,
  `_MAX_CONCEPT_CHARS` 53, and `CommunicationRelation` 99-137.

### Error Handling and Logging

- Malformed frames return `None` from `parse_treaty_frame` and log only
  `treaty_frame_dropped reason=oversize|invalid|unknown_subject|speaker_mismatch|chunk_missing|chunk_duplicate|chunk_order`.
- Never log frame text, chunks, refs, digests, participant anchors, envoy
  identities, or mandate references.

### Tests

`tests/unit/test_diplomacy_treaty_communication.py`:

- Round-trip every `TreatyAct` with all 22 fields.
- Assert exact field count, subject, max length, and comma-list grammar.
- Assert an 832-character frame becomes four ordered chunk relations and
  reassembles byte-for-byte.
- Assert a frame with more than four chunks or a chunk over 240 characters
  fails closed.
- Assert missing, duplicate, and out-of-order chunk relations are dropped with
  the expected reason.
- Assert malformed count, unknown subject/predicate, whitespace, control
  characters, oversize text, bad digest, bad confidence, and unknown enum fail
  closed.
- Assert fewer than two participants fails for version-creating acts.
- Assert a speaker mismatch is dropped and a matching speaker is parsed.
- Assert peer provenance is replaced with `communicated` and a peer mandate is
  not trusted.
- Assert `dip_v1` still has 15 fields and 320 characters, and its parser never
  accepts `trt_v1` chunks.
- Assert no `AgentCommand` appears in the communication module.

### Acceptance Criteria

- `trt_v1` is bounded, chunked, strict, and speaker-bound.
- No chunk relation object exceeds 240 characters; the full frame spans at
  most four relations.
- `dip_v1` is unchanged.
- No frame carries free-text terms or becomes an event/command.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_communication.py tests/unit/test_diplomacy_communication.py -q`
- Expected: all tests pass.

## Task 8: Collect treaty frames and reconcile local treaty state

### Intent

Fold `trt_v1` frames and owner-visible anchors into the ledger deterministically,
including participant resolution, local versus observer behavior, idempotence,
and notices for unresolved references.

### Implementation Steps

1. Extend `_Builder` with dictionaries for treaties, versions, declarations,
   recollections, and misrepresentations, plus `add_treaty`,
   `add_treaty_version`, `add_treaty_declaration`,
   `add_treaty_recollection`, and `add_treaty_misrepresentation`.
2. Extend `_apply_frames`/`_process_frame` with a `_process_treaty_frame`
   branch. First reassemble chunk relations through
   `treaty_frames_from_observation`; an incomplete, duplicated, or
   out-of-order chunk group appends `treaty_malformed_chunks` to notices and is
   dropped without creating a row. Then resolve `participant_refs` with the
   existing party resolver: `agent` anchors resolve to agent parties;
   organization/coalition anchors resolve only against owner `orgc-` concepts;
   settlement anchors resolve only against visible regions; missing anchors
   stay `unresolved`.
3. Apply these rules:
   - A `treaty_propose` frame creates a treaty anchor and original version only
     when the owner is a participant and at least two participants resolve
     (including the owner self-party). If the owner is not a participant,
     retain only a recollection.
   - `treaty_amend`, `treaty_renew`, `treaty_accede`, `treaty_withdraw`,
     `treaty_suspend`, and `treaty_terminate` create the next version only
     when the referenced treaty resolves and the proposer is a participant.
     `version_ref` must be the current version or a retained ancestor; unknown
     refs append a bounded notice and change nothing.
   - `treaty_accept`, `treaty_reject`, `treaty_interpret`, and `treaty_ignore`
     append declarations only when the version resolves and the declaring
     party is a participant.
   - `treaty_recollect` appends a recollection and never creates a treaty or
     version. It accepts absent local refs.
   - A `treaty_withdraw` version removes the withdrawing party from that
     version's participants when that party is not the owner self-party. If the
     owner withdraws, create a `termination` version that retains the
     participant set and derives `terminated`; never remove the self-party from
     a version. If fewer than two non-owner participants remain, create a
     `termination` version and retain both rows.
   - A `treaty_terminate` or `treaty_suspend` version keeps the participant
     set and requires all-party declarations in Task 6 for status.
4. After appending a version, replace the treaty anchor
   `participant_party_ids` and `current_version_id` with the Task 6 derived
   union and highest version. Keep the anchor's `last_tick` current.
5. Deduplicate every derived row by its content-addressed ID. Repeating the
   same frame at the same tick must produce no new row.
6. Add anchor ingestion: owner-visible durable-record anchors and
   institutional-memory entry IDs are attached to a version only when the
   owner explicitly selects them in the frame or the call's `anchor_refs`.
   Never infer an anchor from a peer-supplied list alone; peer anchors are
   retained as claims but marked unresolved in analysis.
7. Update `apply_diplomacy_update` and `record_diplomacy_utterance` to accept
   an optional `treaty_policy: TreatyPolicy | None = None`, defaulting to
   `default_treaty_policy()`. Do not change existing positional arguments.
8. Keep the pipeline order in Task 9; Task 8 ends with `builder.build()`.

### Required Interfaces and Contracts

- Received speech is a claim channel. It can create a local treaty belief only
  when the owner is a participant and the speaker is the claimed envoy.
- A non-participant owner can hold a recollection but never a local treaty
  anchor or version.
- Unknown treaty/version references are notices, not exceptions. They never
  invent a treaty.
- Participant resolution never invents a collective, settlement, or
  organization. Unresolved anchors stay unresolved.
- Replaying the same frame or update is idempotent.
- No treaty helper constructs, submits, resolves, or executes an
  `AgentCommand`.

### Requirement Evidence (when reconciliation applies)

- Original Request "Treaties must exist through ... participants ...
  recognized representatives".
- `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts"
  and V4-03/V4-10 anchor-resolution rules.
- `src/agents/cognition/diplomacy.py` 2328-3024.

### Error Handling and Logging

- Unknown refs add notices such as `treaty_unknown_treaty` and
  `treaty_unknown_version`.
- Unresolved anchors add `treaty_unresolved_participant` at WARNING with only
  a count; never the anchor or party.
- Log `treaty_frames_applied proposed=%s accepted=%s recollected=%s` at DEBUG.
- Never log participant anchors, treaty refs, version refs, digests, or terms.

### Tests

`tests/unit/test_diplomacy_treaty_collection.py`:

- Propose a three-party treaty from the owner; all participants resolve.
- A peer proposal to an owner participant creates a local belief; a peer
  proposal to a non-participant creates only a recollection.
- Organization/coalition parties resolve only with owned `orgc-` concepts;
  settlement parties only with visible regions; missing anchors stay
  unresolved.
- Accept/reject/interpret/ignore declarations require local version and
  participant.
- Amend/renew/accede/withdraw/suspend/terminate create the next version with
  a retained parent link.
- Unknown treaty/version refs append notices and no row.
- An incomplete, duplicated, or out-of-order chunk group appends
  `treaty_malformed_chunks` and creates no row.
- Repeating identical frames is idempotent.
- No `AgentCommand` is constructed.

### Acceptance Criteria

- Treaty frames reconcile into deterministic local beliefs.
- Observers hold recollections only.
- Participant resolution never invents a collective or place.
- Replay is idempotent.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_collection.py tests/unit/test_diplomacy_collection.py -q`
- Expected: all tests pass.

## Task 9: Detect recollection conflicts expiry supersession and caps

### Intent

Close the ordered update pipeline and bound the ledger. This task owns treaty
misrepresentation observations, expiry, supersession, conflicts, and
deterministic cap enforcement so earlier tasks never forward-reference later
ones.

### Implementation Steps

1. Add `detect_treaty_misrepresentation(ledger, representation, *, tick,
   policy, treaty_policy)` mirroring V4-10:
   - an envoy declaration with no mandate, non-recognized standing, or
     non-covering scope appends a `DiplomaticTreatyMisrepresentation` using the
     existing closed kinds;
   - rows are content-addressed and deduplicated;
   - principal declarations never produce envoy misrepresentation rows.
2. Add `expire_treaty_records(ledger, *, tick, policy, treaty_policy)`:
   - versions with `end_tick <= tick` derive `expired`;
   - append a retained `DiplomaticTermination` with target `treaty_version`,
     kind `expired`, when a version first expires;
   - an expired version remains addressable and its rows are never deleted.
3. Add `supersede_treaty_records(ledger, *, tick, policy, treaty_policy)`:
   - compute statuses in one ascending pass;
   - append a retained `DiplomaticTermination` with target `treaty_version`,
     kind `superseded`, when an accepted version is superseded;
   - never supersede an earlier version merely because a later version was
     proposed, rejected, suspended, or terminated.
4. Add `detect_treaty_conflicts(ledger, *, tick, policy, treaty_policy)`:
   - duplicate version index for a treaty;
   - contradictory participant sets for the same version index;
   - a version with no resolvable parent after cap pruning;
   - a recollection claiming a different subject kind than its referenced
     version when both are local;
   - a record anchor conflict where two versions claim the same record ref
     with different terms digests.
   Append `DiplomaticConflict` rows using the three new treaty conflict kinds.
   Conflicts coexist and are never reconciled.
5. Extend `enforce_diplomacy_limits` with a treaty pass before the final total:
   - group treaties per relation and enforce
     `max_treaties_per_relation`;
   - group versions per treaty and enforce `max_versions_per_treaty`;
   - group declarations per version and enforce
     `max_treaty_declarations_per_version`;
   - enforce `max_treaty_recollections` by dropping the oldest recollections
     first and adding `diplomacy_truncated:treaty_recollections`;
   - enforce `max_participants_per_treaty` and `max_provisions` at append
     time, failing closed with `treaty_capacity_reached`.
   Never drop a treaty anchor, an accepted version, the current version, a
   declaration that supports an accepted version, or a parent link needed by a
   retained version. If no droppable row remains, fail with
   `diplomacy_capacity_reached`.
6. Extend total-record accounting and `referenced_parties` with treaty
   participants and declarers. Do not drop a relation that has a retained
   treaty; add that relation to the protected set.
7. Extend the ordered pipeline in `apply_diplomacy_update` to exactly:
   `append -> derive -> detect treaty misrepresentation -> expire ->
   supersede -> detect conflicts -> enforce limits`. Keep V4-10 stages in
   their existing relative order.
8. Recompute the digest after every `_bump`; keep row ordering by
   `(tick, id)`.

### Required Interfaces and Contracts

- `treaty_capacity_reached` is distinct from `diplomacy_capacity_reached` and
  identifies the table by code only.
- Truncation never edits an immutable version in place and never rewrites a
  parent link.
- Recollection rows are the only treaty rows that may be dropped for age.
- An accepted treaty protects its relation from relation-level truncation.
- Repeated detection appends no duplicate termination, conflict,
  misrepresentation, or lineage row.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` "Preserve append-only authoritative history"
  and V4-10 ordered-pipeline precedent.
- Original Request "Track versions and lineage" requires pruning never to
  orphan a retained version.
- V4-10 `enforce_diplomacy_limits` 1999-2247.

### Error Handling and Logging

- `treaty_capacity_reached` and `diplomacy_capacity_reached` are stable codes.
- Log `treaty_truncated table=<closed-table> dropped=<count>` at WARNING.
- Log `treaty_capacity_reached table=<closed-table>` at ERROR.
- Never log treaty/version IDs, participants, terms, or record anchors.

### Tests

`tests/unit/test_diplomacy_treaty_termination.py` and
`tests/unit/test_diplomacy_treaty_capacity.py`:

- Envoy misrepresentation for missing, revoked, expired, superseded, and
  scope-exceeded standing; each retained once.
- Principal declarations never create misrepresentation rows.
- Expiry boundary is exclusive and appends one termination row.
- Supersession appends one termination row and is idempotent.
- Rejected renewal does not supersede the accepted version.
- Duplicate index, contradictory participants, missing parent, subject
  mismatch, and record conflict each append one retained conflict.
- Cap truncation drops only recollections; protected treaties/versions survive.
- Relation truncation never drops a relation with an accepted treaty.
- Repeating the update does not duplicate derived rows.

### Acceptance Criteria

- The ordered pipeline materializes every treaty-derived row family.
- Expiry, supersession, conflicts, and truncation are retained and
  deterministic.
- Caps never orphan a retained version or delete accepted history.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_termination.py tests/unit/test_diplomacy_treaty_capacity.py tests/unit/test_diplomacy_termination.py -q`
- Expected: all tests pass.

## Task 10: Carry treaty rows through the ledger digest and runtime

### Intent

Prove the new treaty rows travel with the owner's `DiplomacyLedger` through
cognition, runtime carry, and the ordered `SimulationRunnerResult` without
adding a result-document field or changing the carry path.

### Implementation Steps

1. Keep `DiplomacyLedger` as the single carry object. Do not add a
   `TreatyLedger`, `TreatySnapshot`, or per-agent treaty field.
2. Extend `diplomacy_ledger_digest` to include every treaty group (Task 4-5)
   and assert equal ledgers with equal treaty rows have equal digests.
3. In `src/simulation/agent_runtime.py` around 1498-1520, keep the existing
   type and owner validation and extend the DEBUG metadata:
   `diplomacy_ledger_carried relations=%s instruments=%s treaties=%s
   versions=%s recollections=%s tick=%s`.
4. Confirm `src/simulation/runner_models.py` 6380-6386 and 6739-6755 remain
   unchanged: `diplomacy_ledgers` is still an ordered tuple of
   `DiplomacyLedger`, validated by owner and order. No `runner-result-v4`.
5. Confirm `src/agents/cognition/loop.py` 2994-3009 and 5871-5878 need no
   structural change; the new fields travel inside the ledger.
6. Confirm `src/simulation/perception.py` and `Perspective` need no new field;
   the ledger is carried as the existing diplomacy object.
7. Add a test that a run with treaty rows exports the same `DiplomacyLedger`
   object shape and that the result document field set is unchanged.

### Required Interfaces and Contracts

- `SimulationRunnerResult.diplomacy_ledgers` remains the only result field.
- No result schema version changes.
- No raw treaty data enters `Perspective` beyond the owner's own ledger.
- Runtime logs are metadata-only.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime" and V4-10
  carry path.
- `src/simulation/runner_models.py` 6380-6386, 6739-6755.

### Error Handling and Logging

- Foreign owner or wrong type still fails with the existing
  `diplomacy_owner_mismatch` / `TypeError`.
- Log only counts at DEBUG; never IDs or terms.

### Tests

`tests/unit/test_diplomacy_treaty_runtime.py`:

- Build a ledger with treaties/versions/declarations/recollections and assert
  digest stability.
- Assert owner mismatch is rejected.
- Assert runtime carry preserves row counts and the same ledger object.
- Assert runner result field set is unchanged and `diplomacy_ledgers` remains
  an ordered tuple.
- Assert no result schema constant changed.

### Acceptance Criteria

- Treaty rows travel through the existing ledger and result tuple.
- No new result field, schema, or carry path exists.
- Logs remain metadata-only.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_runtime.py tests/unit/test_diplomacy_runtime.py -q`
- Expected: all tests pass.

## Phase Risks and Mitigations

- Risk: A treaty version is created from untrusted peer speech and treated as
  local authority.
  Mitigation: require the owner to be a participant and the speaker to be the
  claimed envoy; non-participants retain only recollections; no command path.
- Risk: Renewal supersedes an active treaty before acceptance.
  Mitigation: supersession is computed only after a later version reaches
  `apparently_accepted`, `suspended`, or `terminated`.
- Risk: Cap enforcement orphans a parent version.
  Mitigation: versions, accepted declarations, and parent links are protected;
  only recollections are age-droppable; otherwise fail closed.
- Risk: Treaties become enforcement through a helper name or field.
  Mitigation: forbidden-name guard, boundary AST test, and E2E physical
  non-interference test.

## Phase Completion Checklist

- Every Task 4-10 acceptance criterion is met.
- Treaty rows are retained, ordered, and digest-covered.
- `trt_v1` is bounded and `dip_v1` is unchanged.
- The update pipeline order is exact and idempotent.
- No treaty row grants permission, enforces a ceasefire, or constructs a
  command.
- `index.md` checkboxes are updated only after verification passes.
