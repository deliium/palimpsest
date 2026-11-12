# Phase 1: Contract and Owner-Scoped Accounting Cognition

Plan: [index.md](index.md)
Tasks: 1-4
Depends on: none

## Objective

Produce the complete owner-scoped accounting contract and cognition surface:
a locked policy, closed vocabularies, deterministic identifiers, a bounded
`AccountingLedger`, activation on `organizations` + `durable_records`, carry
through runtime checkpoints, and one `acc_v1` relation attached to an
already-selected `Talk`/`Tell`. No command, event, runner schema, V4 flag, or
V4 context is added.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/simulation/v4_architecture.py` | `V4ContextSpec` 98-106; `organizations` 110-127; `markets_credit` 213-227; `validate_v4_contexts` 367-417 | The context that V4-23 deepens. `organizations` is `OWNER_SCOPED`, `uses_existing_events=True`, prerequisites `()`, and already lists `structured_commitments`/`collective_projects`/`public_goods` as existing mechanisms. |
| `src/simulation/runner_models.py` | `_V4_CAPABILITY_FLAG_NAMES` 307-320; `_V4_OWNED_CAPABILITY_FLAGS` 328-339; `V4CapabilityFlags` 1128-1179; `_DURABLE_RECORD_GENRES` 3552-3563; `DurableRecordsSpec` 3698-3824; `durable_records` field 7860 | Flag count stays 12/8 owned; durable record genres are closed and must not be extended; the spec is the activation input. |
| `src/simulation/runner.py` | `_cognition_config_for` 1024; credit activation 1492-1514; injection 1771-1772; checkpoint read 5077-5106; result wiring 5395-5397; export 5938-5948; call site 7206-7218 | Exact V4-22 twin. V4-23 copies this shape with `organizations_enabled and durable_records_active`. |
| `src/agents/cognition/credit_relationships.py` | policy 84-103; enums 106-177; anchors 272-338; terms/claims/rows 457-779; owner/caps 782-834; `apply_credit_relationship_update` 1071-1082 | Reference for a bounded owner ledger keyed by a symmetric anchor, with deterministic ids and pure fold. |
| `src/agents/cognition/credit_relationships_communication.py` | `_is_expressible` 67-70; selection 77-168; frame build 171-197; `credit_communicate_utterance` 200-268 | Reference for a one-relation `Talk`/`Tell` attachment that never creates or replaces a command. |
| `src/world/credit_relationships.py` | frame subject/chars/relations 40-42; frame 127-207; encode 210-235; parse 238+; relation 298-306; parse relation 309+ | Reference frame codec with strict part count and token validation. |
| `src/agents/cognition/deliberation.py` | 1418-1432 credit attachment; 1470-1492 artifact inscribe path | The only attach point; accounting attaches after credit and never changes the command verb. |
| `src/agents/cognition/configuration.py` | `CognitionCreditMode` 503-512; fields 796-797; normalization 1431-1451; fingerprint 1911-1915 | Mode is cognition-only; no runner key is added. |
| `src/world/artifacts.py` | token grammar 21; caps 22-24; `DurableRecordGenre` 97-108; `RecordIntegrity` 110-116; `ArtifactRelation` 255-274; `ArtifactContent` 277-311; `InformationArtifact` 314-527 | Accounting-like artifacts reuse existing genres and relation tokens; no new genre or artifact kind. |
| `src/world/events.py` | `ArtifactCreated` 1400-1434; `ArtifactModified` 1437-1468; `ArtifactCopied` 1548-1590; `ArtifactAnnotated` 1593-1625; `ArtifactDamaged` 1628-1661; `ArtifactPartiallyLost` 1664-1704; `ArtifactDestroyed` 1507-1545 | Objective record evidence already exists; no event is added. |
| `src/agents/cognition/artifacts.py` | modes 64-73; `ArtifactInterpretation` 136-189; `apply_artifact_interpretation_update` 330-396; `artifact_inscribe_command` 498-535 | Existing owner-scoped reading path; accounting interprets observed metadata, not the existing meaning ledger. |
| `src/simulation/run_control.py` | `AgentRuntimeCheckpoint` fields 618 | Checkpoint carry insertion point. |
| `src/simulation/agent_runtime.py` | field 635; snapshot 2655; restore 3758-3769; export 3969 | Runtime carry points. |
| `src/agents/cognition/loop.py` | prepared field 380/1135; snapshot 1754; fork restore 1814; prepare 3037; apply 3119-3129; call 6256-6260; snapshot emit 6534; commit 6992 | Loop carry points. |
| `src/world/communications.py` | `CommunicationRelation` 98-136; `CommunicationContent` 139-194; `origin_utterance` 346; `retell_utterance` 377; caps 47-54 | Relation transport that `acc_v1` reuses. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/agents/cognition/accounting_ledgers.py` | create | Policy, enums, ids, record parser, entry/revision/claim/ledger dataclasses, caps, pure fold. |
| `src/agents/cognition/accounting_ledgers_communication.py` | create | Deterministic `acc_v1` frame selection and one-relation attachment. |
| `src/world/accounting_ledgers.py` | create | Frame codec, record-content predicate/grammar builder, strict parsers, relation helpers. |
| `src/agents/cognition/configuration.py` | modify | `CognitionAccountingLedgerMode`, fields, normalization, fingerprint, resolved copy. |
| `src/agents/cognition/loop.py` | modify | Prepared field, prepare/apply, snapshot, fork restore. |
| `src/agents/cognition/deliberation.py` | modify | Attach accounting relation after credit. |
| `src/simulation/runner_models.py` | modify | `AccountingLedger` result tuple + validation. |
| `src/simulation/runner.py` | modify | Derive mode/policy, inject, export, wire result. |
| `src/simulation/run_control.py` | modify | Checkpoint field. |
| `src/simulation/agent_runtime.py` | modify | Runtime field, commit, snapshot, checkpoint export/restore. |
| `src/agents/cognition/__init__.py`, `src/world/__init__.py` | modify | Public facade exports only. |

---

## Task 1: Lock the accounting ledger contract, policy, and identifiers

### Intent

Freeze every vocabulary an implementer would otherwise invent: policy version,
entry kinds, directions, record assessments, observed integrity, claim sources,
acts, identifier grammars, forbidden aliases, caps, and the record-content
grammar. Every later task consumes this contract.

### Implementation Steps

1. Create `src/agents/cognition/accounting_ledgers.py` with module docstring and `__all__`.
2. Add policy and identifier constants:
   - `ACCOUNTING_LEDGERS_POLICY_VERSION = "accounting-ledgers.v1"`.
   - `ACCOUNTING_ENTRY_ANCHOR_PREFIX = "acct-"`, `ACCOUNTING_ENTRY_ID_PREFIX = "acce-"`, hex length 16.
   - `ACCOUNTING_RECORD_TOKEN_PREFIX = "accrec-"`, `ACCOUNTING_ORGANIZATION_TOKEN_PREFIX = "accorg-"`, `ACCOUNTING_COUNTERPARTY_TOKEN_PREFIX = "accpeer-"`.
   - `ACCOUNTING_PUBLICATION_PREFIX = "acct-pub-"`.
3. Add closed enums:
   - `AccountingEntryKind`: `exchange`, `debt`, `inventory`, `organizational_resource`, `contribution`.
   - `AccountingDirection`: `inflow`, `outflow`, `holding`, `receivable`, `payable`, `contribution`.
   - `AccountingRecordAssessment`: `unassessed`, `consistent`, `contradicted`, `outdated`, `suspected_fraudulent`, `damaged`.
   - `AccountingRecordIntegrity`: `intact`, `damaged`, `partially_lost`, `unknown`.
   - `AccountingClaimSource`: `direct_record`, `communicated`, `derived`, `unknown`.
   - `AccountingAct`: `declare_entry`, `cite_record`, `affirm_entry`, `dispute_entry`, `correct_entry`, `retract_entry`.
4. Add `AccountingLedgerPolicy` with locked defaults: `max_entries=32`, `max_claims_per_entry=16`, `max_revisions_per_entry=8`, `max_evidence_per_entry=8`, `max_notices=8`, `max_counterparties=8`, `max_quantity=64`, `max_valuation_milli=64_000`, `max_confidence_milli=1_000`, `max_record_age_ticks=128`, `max_due_horizon_ticks=64`, `strong_confidence_milli=750`, `disputed_confidence_milli=500`, `trust_neutral_milli=500`, `communicated_confidence_penalty_milli=200`.
5. Add `_digest16(material: str) -> str` (SHA-256 hex first 16) and determinism helpers:
   - `accounting_record_token(artifact_id: str) -> str`.
   - `accounting_organization_token(concept_id: str) -> str`.
   - `accounting_counterparty_token(actor_id: str) -> str`.
   - `accounting_entry_anchor(*, owner_id, record_token, entry_kind, ordinal) -> str`.
   - `accounting_entry_id(owner_id, anchor) -> str`.
   - `require_accounting_*` validators with the exact regexes.
6. Add `_FORBIDDEN_ACCOUNTING_FIELD_NAMES` including at minimum: `truth`, `verified`, `canonical_ledger`, `audited`, `objective_balance`, `book_value`, `solvent`, `credit_score`, `money`, `currency`, `price`, `interest`, `principal_balance`, `reconciled`, `fraud` (the allowed token is `suspected_fraudulent`), `archive`, `institution`, `meaning`.
7. Add the record-content grammar constants used by both cognition and the world builder:
   - `ACCOUNTING_RECORD_PREDICATE = "acc_v1"`.
   - Entry-code map `{"xch": EXCHANGE, "dbt": DEBT, "inv": INVENTORY, "org": ORGANIZATIONAL_RESOURCE, "ctb": CONTRIBUTION}`.
   - Direction-code map `{"in": INFLOW, "out": OUTFLOW, "hold": HOLDING, "recv": RECEIVABLE, "pay": PAYABLE, "ctb": CONTRIBUTION}`.
   - Item-kind set `{"food", "water", "material", "medical", "generic", "tool", "unknown"}`.
   - Subject grammar `"<entry_code>_<item_kind>"`, object grammar `"<direction_code><quantity>"` with quantity 1..64. Both must satisfy `^[a-z][a-z0-9_]{0,31}$` (existing `ArtifactRelation` token rule).
8. Emit bounded DEBUG construction logs with counts only.

### Required Interfaces and Contracts

```python
ACCOUNTING_LEDGERS_POLICY_VERSION: Final[str] = "accounting-ledgers.v1"
ACCOUNTING_RECORD_PREDICATE: Final[str] = "acc_v1"

@dataclass(frozen=True, slots=True)
class AccountingLedgerPolicy:
    max_entries: int = 32
    max_claims_per_entry: int = 16
    max_revisions_per_entry: int = 8
    max_evidence_per_entry: int = 8
    max_notices: int = 8
    max_counterparties: int = 8
    max_quantity: int = 64
    max_valuation_milli: int = 64_000
    max_confidence_milli: int = 1_000
    communicated_confidence_penalty_milli: int = 200

ACCOUNTING_LEDGERS_LOCKED_POLICY: Mapping[str, int]
def default_accounting_ledger_policy() -> AccountingLedgerPolicy: ...
```

Invariants:
- Every enum is a `str, Enum` and closed.
- Identifier validators reject non-canonical values and raise `AccountingLedgerError("accounting_invalid_identifier")`.
- No field named in `_FORBIDDEN_ACCOUNTING_FIELD_NAMES` exists on any accounting dataclass.
- The policy is a frozen singleton; callers cannot widen it.

### Requirement Evidence (when reconciliation applies)

- Original Request bullets "exchanges", "debts", "inventories",
  "organizational resources", "contributions" map one-to-one to
  `AccountingEntryKind`.
- Original Request "correct / wrong / outdated / fraudulent / damaged" maps to
  `AccountingRecordAssessment`; `wrong` becomes `contradicted` and `fraudulent`
  becomes `suspected_fraudulent` because the ledger is a belief, not an oracle.
- `.ai-factory/ARCHITECTURE.md` "Key Principles" 1-2 and "Anti-Patterns" forbid
  collapsing objective and subjective authority.

### Error Handling and Logging

- Invalid policy or identifier: raise `AccountingLedgerError` with a safe code;
  log `WARN accounting_ledger_contract_invalid field=<name>`.
- Construction: `DEBUG accounting_ledger_contract_built entries=%s notices=%s`.
- Never log owner ids, record tokens, item kinds, quantities, assessments,
  counterparty tokens, or payload surrogates.

### Tests

Create `tests/unit/test_accounting_ledgers_contract.py`:
- enum closure and exact string values;
- policy defaults and rejection of booleans/non-ints/out-of-range;
- all identifier grammars accept canonical and reject malformed values;
- record grammar accepts every code combination and rejects unknown
  item/direction/kind codes, quantity 0, quantity 65, and oversize tokens;
- forbidden field names are absent from every accounting dataclass;
- determinism: same inputs produce the same tokens under two `PYTHONHASHSEED`
  values (subprocess-free: assert `_digest16` is a pure function).

Command: `uv run pytest tests/unit/test_accounting_ledgers_contract.py -q`.

### Acceptance Criteria

- The module imports with no banned names and exposes the locked policy.
- Every vocabulary is closed and documented with the belief-vs-truth caveat.
- Record tokens are 32-character-safe and joinable by analysis.

### Verification

- `uv run pytest tests/unit/test_accounting_ledgers_contract.py -q` — expected: pass.
- `uv run ruff check src/agents/cognition/accounting_ledgers.py` — expected: clean.

---

## Task 2: Add the owner-scoped accounting ledger with record-anchor binding

### Intent

Implement one bounded owner ledger that turns observed external records,
communicated claims, and optional commitment/valuation/contribution inputs into
deterministic accounting entries — without reading world state, peer ledgers, or
another owner's state.

### Implementation Steps

1. In `src/agents/cognition/accounting_ledgers.py`, add frozen dataclasses:
   - `AccountingTerms`: `entry_kind`, `direction`, `item_kind`, `quantity`, `valuation_milli: int | None`.
   - `AccountingEntryRevision`: `tick`, `terms`, `assessment`, `reason_code`.
   - `AccountingRecordObservation`: `record_token`, `record_genre`, `integrity`, `content_revision`, `relations`, `tick`, `ordinal`.
   - `AccountingClaim`: `anchor`, `record_token: str | None`, `organization_token: str | None`, `counterparty_token: str | None`, `terms`, `assessment`, `integrity`, `confidence_milli`, `source`, `act`, `tick`, `ordinal`.
   - `AccountingEntry`: `entry_id`, `anchor`, `record_token`, `record_genre`, `organization_token`, `counterparty_token`, `terms`, `assessment`, `integrity`, `confidence_milli`, `evidence_refs`, `revisions`, `first_tick`, `last_tick`, `source`.
   - `AccountingLedger`: `owner_id`, `entries`, `notices`, `policy_version`.
2. Add `empty_accounting_ledger(owner_id)`, `require_owner_accounting_ledger(...)`, `validate_accounting_ledger_caps(...)`.
3. Add `parse_accounting_record(observation) -> tuple[AccountingTerms, ...]`:
   - Admit only durable-capable artifacts whose `record_genre` is not `None`;
     genre-less artifacts are not accounting records and are ignored.
   - Accept only relations with `predicate == ACCOUNTING_RECORD_PREDICATE`.
   - Validate subject/object against the Task 1 grammar.
   - Ignore unknown triples; increment one bounded invalid-token counter.
   - Map `ObservedArtifact.integrity is None` to `AccountingRecordIntegrity.unknown`;
     never infer `intact` from absence.
   - Never read marks or prose.
4. Add `apply_accounting_ledger_update(*, owner_id, tick, records=(), claims=(), communications=(), prior=None, commitments=None, valuations=None, contributions=(), organizations=None, policy=None) -> AccountingLedger`:
   - Start from `prior` or `empty_accounting_ledger`.
   - Fold record observations first (source `direct_record`), then communicated
     `acc_v1` claims (source `communicated`), then optional commitment rows
     (`debt`, `receivable`/`payable` from `owed_by`), then optional valuation
     rows (`valuation_milli` only when a matching entry exists), then
     contribution rows (`contribution`, `quantity=1`, `contribution_units`),
     then optional organization resource beliefs
     (`organizational_resource`, `holding`, `quantity=1` per referenced anchor,
     with `organization_token` minted from the concept anchor).
   - Deduplicate by `(anchor, source, tick, ordinal, content_digest)`; refolding
     the same inputs leaves bytes identical.
   - Cap revisions and evidence per entry; cap entries; emit one bounded notice
     per cap family.
5. Add deterministic assessment:
   - `damaged` when observed integrity is `damaged` or `partially_lost`;
   - `outdated` when a newer revision of the same record was observed after the
     entry tick;
   - `contradicted` when a folded committed transfer/contribution disagrees on
     direction or quantity;
   - `suspected_fraudulent` when a `dispute_entry` claim from a counterparty
     with confidence >= 500 milli names the entry, or two records with the same
     anchor disagree (apply the disagreement flag only to the later
     `(tick, record_token)` record so the fold is deterministic);
   - `consistent` when intact, current, and no contradiction was observed;
   - `unassessed` otherwise.
6. Add `accounting_evidence_candidates(ledger, *, owner_id, tick, policy=None) -> tuple[object, ...]` returning at most four owner-scoped candidates for `evidence_testimony.apply_evidence_update`:
   - record-backed non-debt entries → `EvidenceObservedReference` with
     `reference_kind=DURABLE_RECORD`/`ORGANIZATION_RECORD`, `integrity` mapped
     from `AccountingRecordIntegrity`, and `reference_id` minted by
     `evidence_source_id(owner_id, source_kind, reference_kind, record_token, ordinal)`;
   - debt entries → `EvidencePriorAgreement(kind="commitment")` with a
     deterministic local ref.
   The helper imports only public `agents.cognition.evidence_testimony` types,
   never writes, and returns `()` when the evidence module is absent.
7. Emit counts only: `DEBUG accounting_ledger_folded entries=%s claims=%s notices=%s`.

### Required Interfaces and Contracts

```python
def apply_accounting_ledger_update(
    *, owner_id: str | AgentId, tick: int,
    records: Sequence[AccountingRecordObservation] = (),
    claims: Sequence[AccountingClaim] = (),
    communications: Sequence[object] = (),
    prior: AccountingLedger | None = None,
    commitments: Sequence[object] | None = None,
    valuations: Sequence[object] | None = None,
    contributions: Sequence[object] = (),
    organizations: Sequence[object] | None = None,
    policy: AccountingLedgerPolicy | None = None,
) -> AccountingLedger: ...
```

Optional inputs are duck-typed and read-only:
- commitment rows expose `debtor_id`, `creditor_id`, `item_kind`, `quantity`,
  `status`, `due_tick`;
- valuation rows expose `item_kind`, `reservation`, `counterparty_id`;
- contribution rows expose `actor_id`, `labor_delta`, `item_id`, `tick`;
- organization rows expose `concept_id` and `resources`, where each resource
  exposes `anchor_id`, `resource_kind`, `access_belief`.
Missing attributes are treated as an absent input, never as an error.

Locked act transitions (one row per folded `acc_v1` act):

| Act | Transition |
| --- | --- |
| `declare_entry` | Create a new entry for a previously unseen anchor, or append a revision when terms differ. |
| `affirm_entry` | Add 100 confidence milli (cap 1000); `unassessed` becomes `consistent`. |
| `cite_record` | Append one opaque evidence token (cap 8); never changes terms. |
| `dispute_entry` | If sender confidence >= 500 and a matching entry exists, set `suspected_fraudulent`; otherwise append a revision with `reason_code="disputed"`. |
| `correct_entry` | Append a revision (cap 8) and replace terms/assessment while retaining prior terms. |
| `retract_entry` | Append a revision with `reason_code="retracted"`, set confidence to 0, and keep the row as history. |
| any act, source `communicated` | Confidence becomes `max(0, frame_confidence - communicated_confidence_penalty_milli)`. |

Invariants:
- Pure: no `WorldState`, event store, command, token, peer ledger, or adapter read.
- `len(entries) <= 32`; each entry has `<= 16` claims, `<= 8` revisions,
  `<= 8` evidence refs; quantities 1..64; confidence 0..1000.
- An entry never stores a raw `artifact_id`, owner id, item id, inventory count,
  structure quantity, or world state.
- Assessment is an owner belief; no field asserts truth, authenticity, or fraud.
- Re-folding the same inputs is byte-identical.

### Requirement Evidence (when reconciliation applies)

- Original Request "Records may be correct / wrong / outdated / fraudulent /
  damaged" and "Do not make ledger content objective truth".
- `src/world/artifacts.py` 255-311 — relation tokens are opaque objective marks.
- `src/agents/cognition/evidence_testimony.py` 1643-1706, 1768-1778 — pure
  candidate DTOs are the only supported bridge.

### Error Handling and Logging

- Invalid claim/entry: drop it, increment `malformed_claims`, and continue.
- Cap overflow: keep the deterministic prefix, set `coverage="partial"` on the
  analysis projection later, and emit one `accounting_ledger_truncated` notice.
- `WARN accounting_ledger_invalid_claim reason=<safe_code>` (no payload).
- `WARN accounting_ledger_record_invalid reason=<safe_code>`.
- Never log record tokens, item kinds, quantities, assessments, counterparties,
  evidence refs, or owner ids.

### Tests

Create `tests/unit/test_accounting_ledgers_ledger.py` and
`tests/unit/test_accounting_ledgers_evidence_bridge.py`:
- record parsing accepts valid `acc_v1` triples and ignores others;
- all five entry kinds are produced from records, communications, commitments,
  valuations, contributions, and organization resource beliefs;
- assessment precedence (`damaged` > `outdated` > `contradicted` >
  `suspected_fraudulent` > `consistent` > `unassessed`);
- cap behavior (entries, claims, revisions, evidence, counterparties, notices);
- double fold is byte-identical;
- evidence candidates never write and return `()` without the evidence module;
- Hypothesis: arbitrary relation tokens never raise and never exceed caps.

Command: `uv run pytest tests/unit/test_accounting_ledgers_ledger.py tests/unit/test_accounting_ledgers_evidence_bridge.py -q`.

### Acceptance Criteria

- One pure owner ledger produces all five requested record kinds.
- Record content is treated as a claim, never as truth.
- The ledger never stores objective quantities or identifiers beyond tokens.

### Verification

- `uv run pytest tests/unit/test_accounting_ledgers_ledger.py tests/unit/test_accounting_ledgers_evidence_bridge.py -q` — expected: pass.
- `uv run mypy src/agents/cognition/accounting_ledgers.py` — expected: clean.

---

## Task 3: Activate and carry accounting ledgers under organizations and durable records

### Intent

Wire the ledger into the deterministic runtime so it is allocated only when the
owned `organizations` V4 flag and the V3-11 `durable_records` spec are both
present, survives checkpoint/fork paths, and exports as a token-only result
tuple. No runner schema, flag, context, or per-agent runner key is added.

### Implementation Steps

1. `src/agents/cognition/configuration.py`:
   - add `CognitionAccountingLedgerMode(str, Enum)` with `DISABLED`, `DETERMINISTIC` near `CognitionCreditMode` 503-512;
   - add `accounting_ledger_mode` and `accounting_ledger_policy` fields near 796-797;
   - normalize/type-check near 1431-1451; include the policy version in the
     fingerprint only when deterministic (near 1911-1915); add the resolved copy
     near 2232-2233.
2. `src/simulation/runner.py`:
   - `_cognition_config_for` already has `organizations_enabled: bool = False` (1030); add only `durable_records_active: bool = False` beside it;
   - add `accounting_enabled = organizations_enabled and durable_records_active` beside the credit block (1492-1514);
   - build `CognitionAccountingLedgerMode.DETERMINISTIC` and
     `default_accounting_ledger_policy()` only when enabled, else `DISABLED`/`None`;
   - inject at 1771-1772;
   - pass `durable_records_active=config.durable_records is not None` at all three
     `_cognition_config_for` call sites: 2934 (initial runtime), 6806 (adopted
     fork runtime), and 7206 (primary composition), using `self._config` in the
     runtime path;
   - read/validate the checkpoint at 5077-5106 (type, `owner_id`);
   - wire `accounting_ledgers=(self.export_accounting_ledgers())` at 5395-5397;
   - add `export_accounting_ledgers()` after 5948.
3. `src/simulation/runner_models.py`:
   - add `accounting_ledgers: tuple[object, ...] = ()` after `credit_relationship_ledgers` (6401);
   - add the validation block after 6960 using `require_owner_accounting_ledger`,
     `validate_accounting_ledger_caps`, unique/sorted `owner_id.value`.
4. `src/simulation/run_control.py`: add `accounting_ledger: object | None = None` beside 618.
5. `src/simulation/agent_runtime.py`: add the field beside 635; commit beside
   the credit commit 1440-1458; snapshot beside 2655; restore beside
   3758-3769; export beside 3969.
6. `src/agents/cognition/loop.py`: prepared field beside 380/1135; snapshot
   message 1754; fork restore 1814; `_prepare_accounting_ledgers` beside 3037
   (reads `snapshot.accounting_ledger` as `prior`, then passes observed
   artifacts, committed contributions, the prepared commitment/valuation
   ledgers, and the prepared organization concept ledger when each is present);
   `apply_accounting_ledger_update` call beside 3119-3129 and 6256-6260;
   snapshot emission 6534; deferred commit 6992.
   Ordering is fixed: `_prepare_accounting_ledgers` runs **after**
   `_prepare_organization_concepts` (6079) and **before** `_prepare_evidence`
   (6106). Extend `_prepare_evidence(loop_input, memory, accounting_candidates=())`
   and append the candidates to the existing `observed` tuple at the
   `apply_evidence_update` call (3683). When the evidence mode is not
   `DETERMINISTIC`, the candidates are ignored and no evidence row is written.
7. Log activation once per run: `INFO accounting_ledger_mode mode=%s policy_version=%s`
   and `DEBUG accounting_ledger_disabled` otherwise.

### Required Interfaces and Contracts

- Activation truth table:
  - `organizations off` → `DISABLED`, empty ledger, no carry, legacy bytes unchanged.
  - `organizations on`, `durable_records` absent → `DISABLED`, empty ledger.
  - both present → `DETERMINISTIC`, ledger allocated per owner.
- The durable-records channel keeps its existing prerequisites
  (`cultural_historical_memory` + `cultural_feature_provenance` + an accepted
  v33..v56 schema). Accounting does not re-validate or relax them; a config that
  fails those gates fails before accounting is considered.
- `SimulationRunnerResult.accounting_ledgers` is ordered by `owner_id.value`,
  unique, and contains only `AccountingLedger` values.
- The tuple is runtime-only. `SimulationRunnerResultDocument`,
  `build_runner_result_document`, and `encode_runner_result_document` stay
  unchanged: no ledger objects, no result-v2/v3 field, and no new document key.
- `runner-config-v56` remains the only write for V4 runs; no v57, no new root or
  per-agent runner key.
- Checkpoint/fork restore rejects a ledger whose `owner_id` differs from the
  runtime owner and clears it when the mode is disabled.

### Requirement Evidence (when reconciliation applies)

- Original Request "extend external records" and "agents/institutions use
  ledgers as evidence".
- `.ai-factory/ARCHITECTURE.md` "Versioned Extension Contract" — V4 counts and
  accepted-set discipline.
- `src/simulation/v4_architecture.py:110-127` — `organizations` stays the owning
  context; `uses_existing_events=True`.

### Error Handling and Logging

- Type/owner mismatch in a checkpoint: raise `ValueError` with a safe code and
  log `ERROR accounting_ledger_checkpoint_invalid`.
- Disabled mode clears the runtime ledger, mirroring credit.
- Never log owner ids, entry counts per owner, or payload fields.

### Tests

Create `tests/unit/test_accounting_ledgers_activation.py` and
`tests/unit/test_accounting_ledgers_carry.py`:
- all three activation combinations;
- mode/policy injection into `CognitionLoopConfig`;
- result tuple ordering/validation and rejection of a foreign-owner ledger;
- checkpoint export → restore round-trip; fork snapshot restore;
- runner schema stays `runner-config-v56` and no v57 constant is introduced;
- `markets_credit`-only and `durable_records`-only runs produce an empty tuple.

Command: `uv run pytest tests/unit/test_accounting_ledgers_activation.py tests/unit/test_accounting_ledgers_carry.py -q`.

### Acceptance Criteria

- Accounting activates only for `organizations` + `durable_records`.
- The ledger survives supported runtime checkpoints and forks.
- No runner schema or capability count changes.

### Verification

- `uv run pytest tests/unit/test_accounting_ledgers_activation.py tests/unit/test_accounting_ledgers_carry.py -q` — expected: pass.
- `rg -n "runner-config-v57" src/ tests/` — expected: no output.

---

## Task 4: Add acc_v1 frames with bounded record-sensitive attachment

### Intent

Let one owner's accounting belief travel as a bounded `acc_v1` relation inside an
already-selected `Talk`/`Tell`, and let one accounting content bundle be attached
to an already-selected `Inscribe`. No command is created, replaced, or biased.

### Implementation Steps

1. Create `src/world/accounting_ledgers.py`:
   - `ACCOUNTING_FRAME_SUBJECT = "acc_v1"`, `ACCOUNTING_FRAME_MAX_CHARS = 320`,
     `ACCOUNTING_FRAME_MAX_RELATIONS = 32`, `ACCOUNTING_FRAME_FIELD_COUNT = 16`.
   - `AccountingEntryFrame` with exactly 16 fields:
     `act`, `entry_anchor`, `record_token`, `entry_kind`, `direction`,
     `item_kind`, `quantity`, `organization_token`, `counterparty_token`,
     `assessment`, `integrity`, `confidence_milli`, `tick`, `revision`,
     `evidence_token`, `record_genre`.
   - `encode_accounting_entry_frame`, `parse_accounting_entry_frame`,
     `accounting_entry_relation`, `parse_accounting_entry_relation`.
   - `accounting_record_content(lines: Sequence[tuple[str, str]]) -> ArtifactContent`
     building validated `acc_v1` relations; reject unknown codes with
     `accounting_record_invalid`.
   - `accounting_record_genre(entry_kind) -> str` mapping `exchange`/`debt` to
     `agreement` and `inventory`/`organizational_resource`/`contribution` to
     `inventory_record`. No new genre is introduced; these are existing
     `DurableRecordGenre` values.
   - Strict rules: no whitespace/control chars, exact part count, token regex,
     quantity 1..64, confidence 0..1000, unknown enum values rejected.
2. Create `src/agents/cognition/accounting_ledgers_communication.py`:
   - `ACCOUNTING_COMMUNICATION_POLICY_VERSION = "accounting-ledgers-communication.v1"`.
   - `_is_expressible` accepts only `Talk`/`Tell`.
   - Deterministic selection: choose at most one entry with
     `assessment != unassessed` or a revision newer than the last shared tick;
     order by `(last_tick, entry_id)` descending, first eligible.
   - `accounting_communicate_utterance(command, *, owner_id, ledger, tick, policy=None)`:
     skip when a relation with subject `acc_v1` already exists, when
     `len(relations) >= 32`, or when the encoded frame exceeds 320 chars; attach
     with `replace(content, relations=(*relations, relation))` and return the same
     command class.
   - `accounting_inscribe_content(ledger, *, owner_id, tick, existing: ArtifactContent) -> ArtifactContent | None`
     returns the **merged** content for an already-selected `Inscribe`: preserve
     every existing mark and relation, append accounting relations only while
     the total relation count stays `<= 8` (the artifact cap), and return
     `None` when nothing fits. Never builds or submits a command.
3. `src/agents/cognition/deliberation.py`: after the credit attachment
   (1418-1432) add the accounting speech attachment; in the artifact inscribe
   path run the accounting content merge **immediately after**
   `artifact_inscribe_command` (1470-1492) and **before** the institutional
   memory hook (1493+), so later marks compose instead of overwriting. Apply the
   merge only when the command presented at that point is already `Inscribe`
   (including the pre-existing artifact-inscription replacement).
4. Record-attachment guard: the inscribe path must keep the same `Inscribe` verb,
   kind, and recipient semantics; if the command presented at the hook is not
   `Inscribe`, do nothing. Accounting never selects `Inscribe` and never replaces
   a non-`Inscribe` command.
5. Log `DEBUG accounting_frame_attached kind=speech|record chars=%s` and
   `WARN accounting_frame_dropped reason=oversize|malformed` once per tick.

### Required Interfaces and Contracts

- One relation per utterance; the command class and recipient are unchanged.
- `acc_v1` is carried only inside existing `Talk`/`Tell`; no new command.
- Record content uses only existing `ArtifactRelation` tokens, the existing
  `Inscribe` command, and an existing `DurableRecordGenre` selected by
  `accounting_record_genre`; no genre, kind, or event is added.
- Malformed or oversize frames are dropped; simulation continues.
- A receiver folds a frame as `source=communicated` with confidence
  `max(0, frame_confidence - communicated_confidence_penalty_milli)`; it never
  copies the sender ledger.

### Requirement Evidence (when reconciliation applies)

- Original Request "Allow agents/institutions to use ledgers as evidence" and
  "Extend external records with accounting-like artifacts".
- `src/agents/cognition/credit_relationships_communication.py:200-268` and
  `src/agents/cognition/evidence_testimony_communication.py:464-488` — attach
  pattern.
- `.ai-factory/ARCHITECTURE.md` "Anti-Patterns" — no structured output shortcut
  and no command authority.

### Error Handling and Logging

- Parse failure: return `None`; never raise into deliberation.
- Oversize: drop the relation and increment one bounded warning count.
- Never log anchors, tokens, item kinds, quantities, or assessments.

### Tests

Create `tests/unit/test_accounting_ledgers_communication.py` and
`tests/unit/test_accounting_ledgers_deliberation.py`:
- 16-part round-trip and strict rejection (15/17 parts, whitespace, unknown
  enums, oversize, confidence/quantity bounds);
- attachment only to `Talk`/`Tell`; no duplicate subject; 32-relation cap;
- `Inscribe` content extension keeps the same command class, preserves every
  existing mark/relation, never exceeds 8 total relations, maps the genre per
  entry kind, and never appears for another command type;
- all other selected commands are returned unchanged (identity);
- a foreign or malformed frame is ignored without error.

Command: `uv run pytest tests/unit/test_accounting_ledgers_communication.py tests/unit/test_accounting_ledgers_deliberation.py -q`.

### Acceptance Criteria

- Accounting claims travel without a new command or event.
- Record artifacts can carry accounting-like content through existing commands.
- Malformed frames never affect the selected command.

### Verification

- `uv run pytest tests/unit/test_accounting_ledgers_communication.py tests/unit/test_accounting_ledgers_deliberation.py -q` — expected: pass.
- `rg -n "class .*Accounting.*\\(.*AgentCommand" src/world/actions.py` — expected: no output.

## Phase Risks and Mitigations

- Risk: `organizations` + `durable_records` is an accidental third activation
  axis that silently changes legacy runs.
  Mitigation: the truth table is tested in both directions; disabled mode clears
  the ledger and leaves event bytes untouched.
- Risk: record-content parsing accidentally reads prose or meaning.
  Mitigation: only `acc_v1` relation triples with closed code vocabularies are
  accepted; marks are ignored.
- Risk: the `Inscribe` extension is mistaken for a new command path.
  Mitigation: the verb, kind, and class are preserved and asserted by identity.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
