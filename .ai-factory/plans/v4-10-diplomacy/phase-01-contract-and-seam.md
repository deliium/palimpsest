# Phase 1: Contract and Seam

Plan: [index.md](index.md)
Tasks: 1-3
Depends on: none

## Objective

Freeze the diplomacy vocabulary, party grammar, and locked policy; claim the
already-declared `diplomacy` V4 capability on the accepted `runner-config-v56`
seam without adding a flag slot, context, runner schema, root field, or per-agent
runner key; and install a disabled-by-default cognition mode that activates only
when `v4_capability_flags.diplomacy` is enabled.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/simulation/v4_architecture.py` | `V4_CONTEXT_MAP_VERSION` 38; `_REQUIRED_CONTEXT_COUNT` 56; `V4ContextId` 60-76; `diplomacy` spec 150-163; `V4_CAPABILITY_FLAGS` 324-326; `V4_ANALYSIS_ONLY_CONTEXTS` 320-322 | Registry is closed at 14 contexts / 12 flags; `diplomacy` already declares `OWNER_SCOPED`, owners `agents.cognition`/`social`/`simulation`, prerequisites `(ORGANIZATIONS,)`, `uses_existing_events=True`, and non-goals `no polity, border, or citizenship object` / `no treaty store or treaty authority` |
| `src/simulation/runner_models.py` | `_V4_CAPABILITY_FLAG_NAMES` 305-318 (`diplomacy` at 309); `_V4_OWNED_CAPABILITY_FLAGS` 320-325; `V4CapabilityFlags` 1114-1163; v56 gate 7976-7988 | Wire keys already exist; ownership is a two-string allowlist change (Task 2), not a schema change |
| `src/simulation/compatibility.py` | `V4_OWNED_CAPABILITY_FLAGS` 155-157; V4 bump text 765-775 | Second ownership pin that must move with the runner pin |
| `src/simulation/runner.py` | `from_config` 2189; `v4_unimplemented` 2252; error 2306-2319; `_cognition_config_for` 1023-1621 | Unimplemented-flag rejection disappears automatically when the flag becomes owned |
| `src/agents/cognition/configuration.py` | `CognitionFormalRuleMode` 423-433; `CognitionRepresentationMode`; `CognitionLoopConfig` 670-679; reconciliation 1139-1227 | Mode/policy seam to extend |
| `src/agents/cognition/delegation_representation.py` | policy lock 194-240; id grammar 58-75; `RepresentationPrincipalKind` 92-99 | Locked-policy, id, and principal-roundness precedent |
| `src/agents/cognition/loop.py` | mode install 1035-1055; `_prepare_representation` 2895-2948 | Exact install/prepare shape to mirror |
| `tests/architecture/test_v4_architecture_invariants.py` | 156-200, 346-369 (owned literal 173, 352-354; explicit `diplomacy` unowned 362) | Existing pins must gain `diplomacy` and lose the unowned assertion |
| `tests/unit/test_v4_scaffolding_gate.py` | 118, 138 | Explicit fail-closed `diplomacy` assertion that must flip |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/agents/cognition/diplomacy.py` | create | Closed vocabulary, party grammar, locked policy, token validators |
| `src/agents/cognition/__init__.py` | modify | Export the frozen vocabulary |
| `src/simulation/runner_models.py` | modify | Add `diplomacy` to `_V4_OWNED_CAPABILITY_FLAGS`; update comment |
| `src/simulation/compatibility.py` | modify | Add `diplomacy` to `V4_OWNED_CAPABILITY_FLAGS`; update bump text |
| `src/agents/cognition/configuration.py` | modify | `CognitionDiplomacyMode`; loop-config fields and reconciliation |
| `src/simulation/runner.py` | modify | Derive mode/policy from `diplomacy_enabled`; pass the flag |
| `src/agents/cognition/loop.py` | modify | Install mode/policy and the prepared slot (no behavior yet) |
| `tests/unit/test_diplomacy_contracts.py` | create | Vocabulary/id/policy tests |
| `tests/unit/test_diplomacy_config.py` | create | Mode and seam tests |
| `tests/architecture/test_diplomacy_boundaries.py` | create | Ownership pin, extended in Task 22 |

## Task 1: Freeze the diplomacy vocabulary, party grammar, and locked policy

### Intent

Diplomacy must have a closed, deterministic vocabulary before any record, frame,
analysis row, route, or metric exists. Parties, contacts, envoys, negotiations,
instruments, declarations, misrepresentation, and conflicts are owner beliefs;
none of them is a polity, treaty, authority, or score. Every later phase imports
these names.

### Implementation Steps

1. Create `src/agents/cognition/diplomacy.py` with a module docstring stating that
   diplomacy is one owner's belief about recurring contact and agreements with
   another party, never a polity, treaty authority, bilateral score, or world
   capability.
2. Define `DIPLOMACY_POLICY_VERSION = "diplomacy.v1"`,
   `DIPLOMACY_ID_HEX_LEN = 16`, `DIPLOMACY_SEPARATOR = "\x1f"`, and
   `DIPLOMACY_PUBLICATION_PREFIX = "dip-pub-"`.
3. Define owner-local id prefixes: relation `dpl-`, party `dpp-`, contact `dpc-`,
   envoy `dpe-`, negotiation `dpn-`, instrument `dpi-`, declaration `dpd-`,
   misrepresentation `dps-`, termination `dpt-`, conflict `dpx-`. Analytical
   `dip-`/`dip-edge-` prefixes live only in `analysis/diplomacy_contract.py`
   (Task 12); this module exports no analytical grammar because `analysis` must
   not import `agents`.
4. Define the closed str-enums exactly as listed under Required Interfaces.
5. Define `DiplomacyPolicy` as a frozen slots dataclass whose `__post_init__`
   compares every field to `_DIPLOMACY_POLICY_VALUES` (`MappingProxyType`) and
   raises `DiplomacyError("diplomacy_policy_not_locked")` on mismatch.
6. Define `default_diplomacy_policy()` and token validators:
   `require_diplomacy_id(value, prefix)`, `require_diplomacy_token(value,
   *, max_chars)`, and `require_diplomacy_subject(value)` (lowercase
   `[a-z0-9_.:-]`, 1-32 chars, `none` reserved).
7. Add `DiplomacyError(ValueError)` with a safe `.code` and no payload in the
   message.
8. Add `_FORBIDDEN_FIELD_NAMES` covering `truth`, `verified`, `legitimate`,
   `authority`, `permission`, `allowed`, `winner`, `proxy`, `binding`, `treaty`,
   `border`, `citizenship`, `score`, `relation_score`, `rank`, `trust`, `index`,
   `composite`, and `overall_relation`, and assert it over every policy and record
   dataclass.
9. Export the enums, prefixes, policy, default, and validators from
   `src/agents/cognition/__init__.py` beside the delegation-representation
   block.

### Required Interfaces and Contracts

```python
DIPLOMACY_POLICY_VERSION: Final[str] = "diplomacy.v1"

class DiplomaticPartyKind(StrEnum):
    AGENT = "agent"
    ORGANIZATION = "organization"
    SETTLEMENT = "settlement"
    COALITION = "coalition"
    UNKNOWN = "unknown"

class DiplomaticPartyResolution(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    UNKNOWN = "unknown"

class DiplomaticContactKind(StrEnum):
    DIRECT_CO_PRESENCE = "direct_co_presence"
    MEDIATED_MESSAGE = "mediated_message"
    WRITTEN_RECORD = "written_record"
    THIRD_PARTY_REPORT = "third_party_report"
    JOURNEY_PRESENCE = "journey_presence"
    UNKNOWN = "unknown"

class DiplomaticEnvoyStatus(StrEnum):
    CLAIMED = "claimed"
    RECOGNIZED = "recognized"
    CONTESTED = "contested"
    REJECTED = "rejected"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"

class DiplomaticNegotiationStatus(StrEnum):
    OPENED = "opened"
    ONGOING = "ongoing"
    STALLED = "stalled"
    CLOSED = "closed"
    ABANDONED = "abandoned"
    UNKNOWN = "unknown"

class DiplomaticInstrumentKind(StrEnum):
    PROPOSAL = "proposal"
    PROMISE = "promise"
    AGREEMENT = "agreement"
    DISPUTE = "dispute"
    SHARED_PROJECT = "shared_project"
    UNKNOWN = "unknown"

class DiplomaticInstrumentStatus(StrEnum):
    PROPOSED = "proposed"
    OPEN = "open"
    APPARENTLY_ACCEPTED = "apparently_accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    UNRESOLVED = "unresolved"
    ACTIVE = "active"
    COMPLETED_CLAIMED = "completed_claimed"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    UNKNOWN = "unknown"

class DiplomaticTermKind(StrEnum):
    MATERIAL_EXCHANGE = "material_exchange"
    SHARED_WORK = "shared_work"
    PASSAGE = "passage"
    RECOGNITION = "recognition"
    PROCEDURE = "procedure"
    UNKNOWN = "unknown"

class DiplomaticProvenance(StrEnum):
    SELF_DECLARED = "self_declared"
    PRINCIPAL_DECLARED = "principal_declared"
    COMMUNICATED = "communicated"
    WITNESSED_CONTACT = "witnessed_contact"
    WRITTEN_RECORD = "written_record"
    REPRESENTATION_BELIEF = "representation_belief"
    COLLECTIVE_DECISION = "collective_decision"
    UNKNOWN = "unknown"

class DiplomaticTerminationKind(StrEnum):
    PARTY_WITHDREW = "party_withdrew"
    ENVOY_RECALLED = "envoy_recalled"
    ENVOY_RESIGNED = "envoy_resigned"
    AGREEMENT_DISPUTED = "agreement_disputed"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    UNKNOWN = "unknown"

class DiplomaticMisrepresentationKind(StrEnum):
    MANDATE_UNRECOGNIZED = "mandate_unrecognized"
    SCOPE_EXCEEDED = "scope_exceeded"
    CONTRADICTED_BY_PRINCIPAL = "contradicted_by_principal"
    CONTESTED_BY_MEMBER = "contested_by_member"
    UNKNOWN = "unknown"

class DiplomaticConflictKind(StrEnum):
    DUPLICATE_ENVOY = "duplicate_envoy"
    CONTRADICTORY_TERMS = "contradictory_terms"
    CONFLICTING_PARTY = "conflicting_party"
    AGREEMENT_DISPUTE = "agreement_dispute"
    UNKNOWN = "unknown"
```

- Locked policy values: `agreement_min_party_declarations=2`,
  `max_relations=24`, `max_parties=32`, `max_contacts_per_relation=16`,
  `max_envoys_per_relation=8`, `max_negotiations_per_relation=8`,
  `max_instruments_per_relation=24`, `max_declarations_per_instrument=16`,
  `max_anchor_refs=8`, `max_total_records=320`, `max_frame_chars=320`.
- Define one closed coverage matrix and one helper, reused by Task 9 and Task 14:

  ```python
  DIPLOMACY_SCOPE_COVERAGE: Final[Mapping[str, frozenset[str]]] = MappingProxyType({
      "contact": frozenset({"speak_for", "carry_message"}),
      "report": frozenset({"speak_for", "carry_message"}),
      "negotiate": frozenset({"negotiate"}),
      "proposal": frozenset({"negotiate", "speak_for"}),
      "agreement": frozenset({"negotiate", "decide"}),
      "promise": frozenset({"speak_for", "negotiate"}),
      "dispute": frozenset({"speak_for", "negotiate"}),
      "shared_project": frozenset({"coordinate_project"}),
  })
  LONG_RUNNING_INSTRUMENT_KINDS: Final[frozenset[str]] = frozenset(
      {"agreement", "promise", "shared_project"}
  )

  def diplomacy_scope_covers(
      *, scope_kind: object, duration_kind: object, instrument_kind: object,
      scope_subject: object, topic_subject: object,
  ) -> bool: ...
  ```

  `single_act` and `occasion` never cover `LONG_RUNNING_INSTRUMENT_KINDS`;
  `until_tick` and `until_revoked` may. A non-`None` `scope_subject` must equal
  `topic_subject`; `None` means the owner believes the mandate is subject-generic.
- `DiplomaticPartyKind` deliberately mirrors the V4-09
  `RepresentationPrincipalKind` value set. Do not import `analysis` here and do
  not add `nation`, `civilization`, `polity`, `tribe`, or `state`.
- No record or policy field may carry a numeric relationship value, valence,
  ranking, or composite.

### Requirement Evidence (when reconciliation applies)

- Original Request: "Do not create magical bilateral relationship scores between
  civilizations"; "Representatives may misrepresent their society or lack full
  authority".
- `src/simulation/v4_architecture.py` 150-163: owner-scoped authority and
  non-goals `no polity, border, or citizenship object` and `no treaty store or
  treaty authority`.
- `.ai-factory/ARCHITECTURE.md` Key Principle 1: objective state, owner belief,
  and retrospective analysis must never collapse.

### Error Handling and Logging

- Policy mismatch: `DiplomacyError("diplomacy_policy_not_locked")`.
- Invalid id/token/subject: `DiplomacyError("diplomacy_invalid_id")`,
  `("diplomacy_untrusted_token")`, `("diplomacy_invalid_subject")`.
- `DEBUG diplomacy_policy_loaded version=%s` only; never log party refs, envoy
  refs, mandate refs, subject text, or frame bodies.

### Tests

- `tests/unit/test_diplomacy_contracts.py`: exact enum member sets (including
  `DiplomaticEnvoyStatus.SUPERSEDED`); every prefix accepts 16 lowercase hex and
  rejects other shapes; `none` rejected as a subject; locked-policy mutation
  raises; default policy equals the mapping; id minters are deterministic and
  differ across owners/ticks; every record and policy dataclass rejects
  forbidden field names; `str(DiplomacyError)` contains only the code; the
  coverage matrix returns the documented result for every instrument kind,
  every `single_act`/`occasion` long-running case, and matching/mismatching
  subjects.

### Acceptance Criteria

- Every enum, prefix, policy field, and validator exists exactly once and is
  exported.
- The module contains no polity, treaty, border, citizenship, score, rank, or
  truth concept.

### Verification

- `uv run pytest tests/unit/test_diplomacy_contracts.py -q`
- Expected: pass; `rg -n "polity|treaty|border|citizenship|relation_score|rank" src/agents/cognition/diplomacy.py` returns only non-claim docstring prose.

## Task 2: Own the diplomacy flag on the runner-config-v56 seam

### Intent

V4-10 must claim the already-declared `diplomacy` context instead of inventing a
new flag or schema. Ownership is a deliberate two-pin change so a later task
cannot quietly widen the wire contract.

### Implementation Steps

1. In `src/simulation/runner_models.py`, add `"diplomacy"` to
   `_V4_OWNED_CAPABILITY_FLAGS` (320-325) and update the comment to read
   "V4-03/V4-04/V4-05 own `organizations`, V4-06 owns `formal_rules`, V4-07
   owns `legal_disputes`, and V4-10 owns `diplomacy`; the remaining eight V4
   flags stay unowned".
2. In `src/simulation/compatibility.py`, add `"diplomacy"` to
   `V4_OWNED_CAPABILITY_FLAGS` (155-157) and update the V4 bump text
   (765-775) to four owned / eight unowned flags.
3. In `src/simulation/runner.py::_cognition_config_for`, add
   `diplomacy_enabled: bool = False` beside `organizations_enabled` and
   `legal_disputes_enabled` (1029-1031), and pass
   `config.v4_capability_flags.diplomacy` at the three call sites
   (2730-2732, 6427-6431, 6803-6805).
4. Do not change `_V4_CAPABILITY_FLAG_NAMES`, `V4CapabilityFlags`,
   `runner_serialization.py`, `RUNNER_SCHEMA_VERSION_V56`, or the
   `v4_capability_requires_v56` gate (7976-7988).
5. Update the explicit pin sites listed under Tests; do not weaken any existing
   count. Keep 14 contexts, 12 flags, `v4-context-map-v2`, and the four reserved
   write pairs (events 23-26 / codecs `v21`-`v24`) unchanged.
6. Record the planning decision that registry prerequisites are planning-order
   declarations, not runtime gates: `diplomacy` may run with `organizations`
   disabled, and organization/coalition anchors then stay unresolved. This
   matches the shipped `legal_disputes` behavior without `formal_rules`.

### Required Interfaces and Contracts

- Ownership is expressed only by `runner-config-v56` +
  `v4_capability_flags.diplomacy = true`.
- `diplomacy` is the fourth owned V4 flag; `organized_conflict`,
  `infrastructure_networks`, `supply_chains`, `markets_credit`, `science`,
  `epidemics`, `ecological_feedback`, `disasters` remain unowned and fail closed.
- `institutional_economy`, `multi_hop_testimony_tracking`, and
  `organized_conflict` remain unowned.
- No `runner-config-v57`, root config field, per-agent runner key, new context,
  new event, new codec, or migration.

### Requirement Evidence (when reconciliation applies)

- Original Request: "Implement long-running relationships between macro-society
  candidates and organizations"; "Do not create magical bilateral relationship
  scores".
- `src/simulation/v4_architecture.py` 150-163 declares the context, authority,
  owners, prerequisites, and non-goals.
- `.ai-factory/ARCHITECTURE.md` "Capability ownership": V4 flags are closed and
  ownership is explicit.

### Error Handling and Logging

- Enabling `diplomacy` on `runner-config-v4` or `v55` must raise
  `v4_capability_requires_v56` before construction.
- Enabling any still-unowned V4 flag must keep raising `capability_unimplemented`
  with `stage="v4_capability_flags"`.
- `INFO runner_v4_owned_flags count=4`; never log flag combinations that reveal
  configuration of a specific run beyond counts.

### Tests

- `tests/architecture/test_diplomacy_boundaries.py`:
  `test_v4_10_owns_diplomacy_without_new_schema` asserts the registry revision,
  14/12 counts, the four-owned set, `diplomacy` authority `OWNER_SCOPED` and
  prerequisite `organizations`, no `runner-config-v57` literal under `src/`,
  no `diplomacy_mode` field on `AgentCognitionSpec`/`SimulationRunnerSpec`/
  `SimulationRunnerConfig`, and that `organized_conflict` still fails closed.
- `tests/unit/test_diplomacy_config.py`: v4/v55 + `diplomacy` raises
  `v4_capability_requires_v56`; v56 + `diplomacy` constructs; all-flags-off
  config is byte-identical in behavior to V4-09.
- Update every pinned owned-set literal. The measured set is:
  `tests/architecture/test_v4_architecture_invariants.py` (187, 352-354),
  `tests/architecture/test_delegation_representation_boundaries.py` (90,
  111-124), `tests/architecture/test_evidence_testimony_boundaries.py` (311-312),
  `tests/architecture/test_organization_boundaries.py` (270),
  `tests/unit/test_runner_config_v4_flags.py` (111, 120-121),
  `tests/unit/test_v4_scaffolding_gate.py` (118, 138),
  `tests/unit/test_runner_config_v56.py` (253, 285),
  `tests/unit/test_evidence_testimony_config.py` (101),
  `tests/unit/test_organization_gate.py` (89), and
  `tests/unit/test_formal_rule_regression.py` (82). Replace the "diplomacy
  unowned" assertion with "organized_conflict unowned" and rename the
  formal-rule regression test from "...nine flags remain unowned" to "...eight
  flags remain unowned". The docs parity tests and ownership prose are Task 25.
- Add a V4-10 assertion that `V4_OWNED_CAPABILITY_FLAGS` has exactly four
  members and that `V4CapabilityFlags(diplomacy=True).owned_enabled_names() ==
  ("diplomacy",)` on the v56 seam.

### Acceptance Criteria

- `diplomacy` is owned and constructible only on v56.
- No pin regresses other than the intentional four-owned set and new V4-10
  surfaces introduced later.

### Verification

- `uv run pytest tests/unit/test_diplomacy_config.py tests/architecture/test_diplomacy_boundaries.py tests/architecture/test_v4_architecture_invariants.py -q`
- Expected: pass.
- `rg -n "runner-config-v57" src tests docs` returns no match.

## Task 3: Add the cognition diplomacy mode and policy seam

### Intent

The ledger must activate only when the owned `diplomacy` flag is on, using the
same run-wide, flag-derived activation as organization concepts and
representation. No per-agent mode and no new wire field.

### Implementation Steps

1. In `src/agents/cognition/configuration.py`, add
   `CognitionDiplomacyMode` (`DISABLED`, `DETERMINISTIC`) beside
   `CognitionRepresentationMode`.
2. Add `diplomacy_mode: CognitionDiplomacyMode = DISABLED` and
   `diplomacy_policy: DiplomacyPolicy | None = None` to `CognitionLoopConfig`
   after the representation policy field (670-679).
3. Extend `CognitionLoopConfig.__post_init__` reconciliation (1139-1227),
   mirroring the V4-09 representation block exactly: DETERMINISTIC with `None`
   fills `default_diplomacy_policy()`; DISABLED clears a supplied policy; any
   wrong type raises `TypeError`, and any other inconsistent pairing raises
   `diplomacy_mode_policy_mismatch`.
4. Extend `condition_fingerprint_material` (1609-1611) with
   `diplomacy_mode` and `diplomacy_policy_version` only when DETERMINISTIC, so a
   changed mode/policy changes the condition fingerprint.
5. In `src/simulation/runner.py::_cognition_config_for`, inside the
   `diplomacy_enabled` branch, derive `diplomacy_mode =
   CognitionDiplomacyMode.DETERMINISTIC` and
   `diplomacy_policy = default_diplomacy_policy()`.
6. Pass both into `CognitionLoopConfig(...)` beside the representation fields.
7. In `src/agents/cognition/loop.py`, add the install block beside the
   representation block (1035-1055): store `_diplomacy_mode`,
   `_diplomacy_policy`, and allocate `_prepared_diplomacy = None`. Add the
   matching slots (380-390) and the constructor arguments (509-510). Do not call
   a ledger function yet.
8. Log `INFO cognition_diplomacy_mode mode=%s policy_version=%s` when
   DETERMINISTIC and `DEBUG` when DISABLED.
9. Import `default_diplomacy_policy` lazily inside `_cognition_config_for`,
   matching the existing local-import style.

### Required Interfaces and Contracts

- Activation derives solely from `config.v4_capability_flags.diplomacy`.
- `organizations`, `formal_rules`, and `legal_disputes` must not enable it.
- Disabled mode is a passthrough: no ledger, no notices, no metrics, no
  publication, no API state.
- `runner-config-v56` stays the only accepted V4 schema.

### Requirement Evidence (when reconciliation applies)

- Original Request: "using agent-mediated interaction"; "Representatives may
  misrepresent their society or lack full authority".
- `src/simulation/runner.py` 1023-1621: existing flag-derived mode pattern.
- `src/agents/cognition/loop.py` 1035-1055, 2895-2948: install and prepare
  pattern to mirror in Task 7.

### Error Handling and Logging

- `diplomacy_mode_policy_mismatch` on an inconsistent pairing.
- `TypeError("diplomacy_mode must be CognitionDiplomacyMode")` on a wrong type.
- Log mode and policy version only; never log policy values.

### Tests

- `tests/unit/test_diplomacy_config.py`: default DISABLED/None;
  `diplomacy=True` yields DETERMINISTIC with the locked policy; each of the
  other eleven V4 flags alone yields DISABLED; mismatched policy raises; runner
  schema stays `runner-config-v56`; enabling `diplomacy` with `organizations`
  off is accepted; the condition fingerprint includes `diplomacy_mode` and
  `diplomacy_policy_version` only when enabled.
- Parameterize over all 12 flags so a later flag cannot silently activate
  diplomacy.

### Acceptance Criteria

- Exactly one flag activates the seam.
- Off-path configuration is behaviorally identical to V4-09.

### Verification

- `uv run pytest tests/unit/test_diplomacy_config.py tests/unit/test_runner_config_v56.py -q`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: ownership changes accidentally widen the wire schema.
  Mitigation: Task 2 asserts no new spec/config field and no v57; serialization
  files are untouched.
- Risk: diplomacy activates through the wrong flag or bypasses the v56 gate.
  Mitigation: parameterized 12-flag test plus the unchanged
  `v4_capability_requires_v56` gate.
- Risk: prerequisites get enforced at runtime and break existing runs.
  Mitigation: record the planning-order decision and test that `diplomacy` runs
  with `organizations` off, leaving anchors unresolved.

## Phase Completion Checklist

- Every task in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
