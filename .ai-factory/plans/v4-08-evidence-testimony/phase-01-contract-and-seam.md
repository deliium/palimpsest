# Phase 1: Contract and Seam

Plan: [index.md](index.md)
Tasks: 1-3
Depends on: none

## Objective

Freeze the closed evidence-testimony vocabulary and identity grammar, pin the
existing `legal_disputes` context as the only ownership seam, and add the
run-level cognition mode/policy that activates the evidence ledger at
`runner-config-v56` without a new capability flag or runner schema.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/agents/cognition/legal_disputes.py` | `DISPUTE_POLICY_VERSION` 33; prefixes 36-44; `_reject_forbidden_fields` 363-397; `DisputePolicy` 416-469; id minters 578-805; `DisputeLedger` 1750-2068 | Pattern for a locked policy, content-addressed ids, forbidden fields, and an ordered owner ledger |
| `src/agents/cognition/formal_rules.py` | `FORMAL_RULE_POLICY_VERSION` 36; id prefixes 39-54; `FormalRuleEvidence` 864-904 | Evidence anchor and version patterns to reference, not copy |
| `src/agents/cognition/reputation.py` | `ReputationDimension` 49-55; `ReputationChannel` 58-64; `ReputationSourceTrustBand` 67-73; `ReputationEvidenceItem` 243-317 | Owner-relative trust inputs; never a global score |
| `src/social/relationships.py` | `RelationshipDimension` 56-66; `RelationshipConfidence` 176-209; `DirectedRelationshipProfile` 305-386 | Owner trust projection used by evaluation |
| `src/memory/models.py` | `MemoryProvenance` 447-503; `RecallSourceEvidence` 2376-2486; `ReconstructedMemory` 2657-2882 | Remembered-event anchors and opaque objective correlation |
| `src/world/artifacts.py` | `ArtifactKind` 78-94; `DurableRecordGenre` 97-107; `RecordIntegrity` 110-117; `InformationArtifact` 314-527 | Record/artifact source anchors and integrity beliefs |
| `src/world/repositories.py` | `RepositoryStatus` 56-63; `RepositoryAccessMode` 65-70; `KnowledgeRepository` 148-278 | Repository entry and custodian anchors |
| `src/simulation/v4_architecture.py` | `LEGAL_DISPUTES` spec 136-149; `_REQUIRED_CONTEXT_COUNT = 14` 56; `V4_CONTEXT_MAP_VERSION` 38 | The context being deepened |
| `src/simulation/runner_models.py` | V4 flag tuple 305-318; owned set 320-325; `V4CapabilityFlags` 1114-1163; `v4_capability_flags` field 7594 | The flag seam; no new key |
| `src/simulation/runner.py` | `_cognition_config_for` 1014-1050; dispute mode wiring 1328-1406; three call sites 2670/6335/6711 | Where the new internal mode is derived |
| `src/agents/cognition/configuration.py` | `CognitionDisputeMode` 424-432; config fields 638-639; fingerprint material 1530-1534; loop build 1805-1806 | Cognition config shape and fingerprint |
| `src/agents/cognition/loop.py` | `dispute_mode`/`dispute_policy` params 499-500; init 983-1002; slots 319-320, 365 | Loop seam for a new owned ledger |
| `tests/architecture/test_v4_architecture_invariants.py` | 14/12/3 pins and `v57` absence | Existing ownership invariants |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/agents/cognition/evidence_testimony.py` | create | Closed enums, errors, policy, id grammar, validators, `__all__` (records in Task 4) |
| `src/agents/cognition/configuration.py` | modify | `CognitionEvidenceMode`, config fields, fingerprint material, loop construction |
| `src/agents/cognition/loop.py` | modify | Accept and validate `evidence_mode`/`evidence_policy`; disabled path allocates nothing |
| `src/simulation/runner.py` | modify | Derive `evidence_mode`/policy from `v4_capability_flags.legal_disputes` at all three loop-construction sites |
| `tests/unit/test_evidence_testimony_contracts.py` | create | Vocabulary, id, policy, and forbidden-field tests |
| `tests/unit/test_evidence_testimony_config.py` | create | Mode/policy seam, flag gating, disabled passthrough |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | Add an assertion that V4-08 introduces no context/flag/version change (no behavior change) |

## Task 1: Freeze the evidence-testimony vocabulary and identity grammar

### Intent

Create the single closed vocabulary that every later record, frame, row,
snapshot, route, and metric uses. Later tasks must not invent enum values or id
shapes.

### Implementation Steps

1. Create `src/agents/cognition/evidence_testimony.py` with module docstring
   stating: owner-scoped belief, never truth, no proof engine, no registry.
2. Add constants:
   - `EVIDENCE_TESTIMONY_POLICY_VERSION = "evidence-testimony.v1"`
   - `EVIDENCE_ID_HEX_LEN = 16`
   - `EVIDENCE_SEPARATOR = "\x1f"`
   - owner-local prefixes: `evs-` (source), `evw-` (witness statement), `evi-`
     (interpreted item), `evc-` (custody link), `evx-` (contradiction), `eva-`
     (evaluation).
3. Add closed enums:
   - `EvidenceSourceKind`: `witness_testimony`, `written_record`, `artifact`,
     `physical_state`, `prior_agreement`, `reputation`, `remembered_event`,
     `unknown`.
   - `EvidenceProvenanceChannel`: `direct_observation`, `communicated`,
     `remembered`, `recorded`, `derived`, `inferred`, `unknown`.
   - `EvidenceReferenceKind`: `observed_occurrence`,
     `observed_communication`, `memory_trace`, `reconstructed_memory`,
     `artifact`, `durable_record`, `repository_entry`, `commitment`,
     `reputation_record`, `relationship_record`, `office_record`,
     `institution_record`, `organization_record`, `rule_record`,
     `mediation_record`, `dispute_record`, `unknown`.
   - `EvidenceTestimonyChannel`: `direct`, `communicated`.
   - `EvidenceIntegrityBelief`: `intact`, `damaged`, `partially_lost`,
     `destroyed_belief`, `uncertain`.
   - `EvidenceInterpretationKind`: `supports`, `contradicts`, `ambiguous`,
     `insufficient`, `irrelevant`, `unknown`.
   - `EvidenceItemStatus`: `active`, `retracted`, `superseded`.
   - `EvidenceCustodyRole`: `holder`, `repository_custodian`, `location`,
     `observer`.
   - `EvidenceCustodyStatus`: `not_applicable`, `complete_belief`,
     `incomplete_belief`, `conflicting_belief`, `unknown`.
   - `EvidenceContradictionKind`: `testimony_conflict`, `memory_conflict`,
     `record_conflict`, `artifact_conflict`, `custody_conflict`,
     `temporal_conflict`, `interpretation_conflict`, `provenance_conflict`.
   - `EvidenceContradictionStatus`: `unresolved`, `owner_prefers_first`,
     `owner_prefers_second`, `withdrawn`.
   - `EvidenceTrustBasis`: `direct_experience`, `relationship_trust`,
     `reputation`, `role_authority`, `rule_authority`,
     `institution_membership`, `none`, `unknown`.
   - `EvidenceEvaluationKind`: `corroborated`, `contested`, `uncorroborated`,
     `excluded_by_owner`, `unknown`.
   - `EvidenceReportKind`: `summary`, `candidate`, `item`, `contradiction`,
     `custody`, `lineage`.
4. Add `EVIDENCE_ERROR_CODES` (exact frozenset): `evidence_invalid_input`,
   `evidence_invalid_id`, `evidence_invalid_record`, `evidence_owner_mismatch`,
   `evidence_tick_mismatch`, `evidence_unknown_reference`,
   `evidence_duplicate_id`, `evidence_limit_exceeded`,
   `evidence_policy_not_locked`, `evidence_forbidden_field`,
   `evidence_untrusted_frame`, `evidence_invalid_confidence`,
   `evidence_chain_conflict`.
5. Add `EVIDENCE_FORBIDDEN_FIELD_NAMES` (exact frozenset): `truth`, `verified`,
   `authenticated`, `authentic`, `forged`, `fake`, `proof`, `certainty`,
   `verdict`, `guilt`, `guilty`, `liable`, `liability`, `true_owner`, `winner`.
6. Add `EVIDENCE_NOTICE_REASONS`: `evidence_truncated`,
   `evidence_chain_incomplete`, `evidence_reference_unknown`,
   `evidence_contradiction_retained`, `evidence_trust_basis_missing`,
   `evidence_testimony_root_shared`, `evidence_item_retracted`.
7. Add `_digest(*parts) -> str` using sha256 over
   `EVIDENCE_SEPARATOR.join(parts)`; no `hash()`, no wall clock, no UUID.
8. Add id minters and `require_*` validators:
   - `evidence_source_id(owner_id, source_kind, reference_kind, reference_id, ordinal)`
   - `evidence_testimony_id(owner_id, speaker_id, channel, root_ref, ordinal)`
   - `evidence_item_id(owner_id, source_id, interpretation, ordinal)`
   - `evidence_custody_id(owner_id, source_id, link_index, role, subject_token, tick)`
   - `evidence_contradiction_id(owner_id, first_ref, second_ref, kind, ordinal)`
   - `evidence_evaluation_id(owner_id, item_id, basis_csv, ordinal)`
   Each returns `<prefix>-<16 lowercase hex>`; validators enforce the regex and
   that the id is stable for the same inputs.
9. Add `EvidencePolicy` frozen slots dataclass with exact locked values via
   `_LOCKED_POLICY_VALUES` and `evidence_policy_not_locked`:
   `max_sources=64`, `max_testimony=64`, `max_items=128`,
   `max_custody_links_per_source=16`, `max_contradictions=64`,
   `max_evaluations=128`, `max_total_records=640`, `max_notices=16`,
   `max_frame_chars=768`, `max_frame_relations=32`, `max_subject_token=128`,
   `trust_weight_direct_experience=5000`, `trust_weight_relationship=2500`,
   `trust_weight_reputation=2000`, `trust_weight_role_authority=500`,
   `neutral_confidence=0.5`, `confidence_quantum=0.000001`.
   Add `default_evidence_policy()` and `require_evidence_policy(value)`.
10. Add `EvidenceError(reason_code)` with only safe codes; add `__all__`.

### Required Interfaces and Contracts

- All enums are `StrEnum` and closed; unknown values fail at construction.
- No text/payload fields are introduced anywhere in the contract.
- Confidence values are floats in `[0.0, 1.0]`, quantized to
  `confidence_quantum` by record constructors in Task 4.
- Trust weights are integers in basis points; no float weighting.
- `evidence_source_id` and friends are pure functions; deterministic across
  processes and Python versions.

### Requirement Evidence

- Original Request "Potential evidence sources" and "Evidence != truth" —
  source kinds and forbidden truth fields.
- `.ai-factory/ARCHITECTURE.md` "Key Principles" 1-2 — three authorities,
  deterministic identity.
- `src/agents/cognition/legal_disputes.py` 33-469 — policy and id precedent.

### Error Handling and Logging

- Invalid vocabulary or id inputs raise `EvidenceError` with a safe code.
- Log at DEBUG: `evidence_contract_initialized policy_version=%s` only. Never log
  ids, tokens, owner ids, or confidence values at INFO or above.

### Tests

- Create `tests/unit/test_evidence_testimony_contracts.py`:
  - every enum value is in the declared frozenset and no duplicates exist;
  - id minters are stable across repeated calls and differ across owner/source;
  - validators reject `evs-`, `evs-xyz`, uppercase hex, and 15/17 hex lengths;
  - `EvidencePolicy()` default equals locked values and mutation attempts fail;
  - `EvidenceError` exposes only a reason code;
  - forbidden field set contains exactly the declared names.
- Command: `uv run pytest tests/unit/test_evidence_testimony_contracts.py -q`.

### Acceptance Criteria

- The module imports without importing `analysis`, `experiments`,
  `persistence`, `api`, `infrastructure`, `observer`, or `world`.
- Every later task can reference exactly one source-kind, provenance,
  interpretation, contradiction, custody, and trust-basis vocabulary.

### Verification

- `uv run pytest tests/unit/test_evidence_testimony_contracts.py -q`
- Expected: all tests pass; no network, Docker, or database.

## Task 2: Pin the legal_disputes deepening seam

### Intent

Prove that V4-08 deepens the existing context and cannot silently become a new
flag or schema. This task changes no registry value; it adds the internal
derivation and the assertions that lock the seam.

### Implementation Steps

1. In `src/agents/cognition/evidence_testimony.py`, add:
   - `EVIDENCE_TESTIMONY_CONTEXT_ID = "legal_disputes"`
   - `EVIDENCE_TESTIMONY_REQUIRED_RUNNER_SCHEMA = "runner-config-v56"`
   - `EVIDENCE_TESTIMONY_IS_CAPABILITY_FLAG = False`
2. In `src/simulation/runner.py`, add a private helper
   `_evidence_testimony_enabled(config: SimulationRunnerConfig) -> bool` that
   returns `config.v4_capability_flags.legal_disputes` and logs
   `evidence_testimony_seam enabled=%s runner_schema=%s` at DEBUG. Do not add a
   config field.
3. Confirm `SimulationRunner.from_config` still rejects `legal_disputes` on
   v4/v55 with `v4_capability_requires_v56` before any loop construction, and
   still allows v56 with `legal_disputes` on/off `formal_rules`.
4. Do not edit `V4_CONTEXTS`, `V4ContextId`, `V4CapabilityFlags`,
   `V4_CONTEXT_MAP_VERSION`, `SUPPORTED_RUNNER_SCHEMA_VERSIONS`,
   `runner_serialization.py`, or `compatibility.py`.
5. Add a focused assertion to
   `tests/architecture/test_v4_architecture_invariants.py` that the registry is
   still 14 contexts / 12 flags / 3 owned and that no `runner-config-v57`
   identifier appears in `src/`.

### Required Interfaces and Contracts

- `EVIDENCE_TESTIMONY_CONTEXT_ID` is the only context identifier V4-08 claims.
- No new capability-flag name is accepted by `V4CapabilityFlags`.
- The evidence ledger has no independent runner flag; its activation is a pure
  function of the existing flag.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Capability ownership" — owned V4 flags are
  `organizations`, `formal_rules`, `legal_disputes`; others fail closed.
- `src/simulation/v4_architecture.py` 136-149 — `legal_disputes` is
  owner-scoped with `formal_rules` prerequisite and existing events.
- `src/simulation/runner_models.py` 7950-7962 — `v4_capability_requires_v56`.

### Error Handling and Logging

- Invalid combinations keep the existing `EngineError`/`SimulationError` codes;
  V4-08 adds no new configuration error.
- DEBUG flow logs only booleans, schema names, and counts.

### Tests

- Create `tests/unit/test_evidence_testimony_config.py` with:
  - `legal_disputes` on v4 and v55 raises `v4_capability_requires_v56`;
  - v56 without `formal_rules` validates and derives evidence enabled;
  - v56 with `formal_rules` validates and derives evidence enabled;
  - all V4 flags off derives evidence disabled;
  - `V4_CONTEXTS` length is 14, `V4_CAPABILITY_FLAGS` length is 12,
    `V4_OWNED_CAPABILITY_FLAGS` is exactly
    `{"organizations", "formal_rules", "legal_disputes"}`.
- Add to `tests/architecture/test_v4_architecture_invariants.py`:
  `assert "runner-config-v57" not in <concatenated src text>`.
- Command: `uv run pytest tests/unit/test_evidence_testimony_config.py tests/architecture/test_v4_architecture_invariants.py -q`.

### Acceptance Criteria

- No registry, flag, or runner-schema source file is modified by this task.
- Enabling `legal_disputes` on v56 activates the seam; every other path is
  unchanged.

### Verification

- `git diff --stat` shows no changes to `src/simulation/v4_architecture.py`,
  `src/simulation/runner_models.py`, `src/simulation/compatibility.py`, or
  `src/simulation/runner_serialization.py`.
- `uv run pytest tests/unit/test_evidence_testimony_config.py tests/architecture/test_v4_architecture_invariants.py -q`
- Expected: pass.

## Task 3: Add the cognition evidence mode and policy seam

### Intent

Give cognition one run-level mode and a locked policy, derived lockstep from
`legal_disputes`, so the ledger can be prepared without a per-agent runner key.
Disabled must allocate nothing and must not change existing behavior.

### Implementation Steps

1. In `src/agents/cognition/configuration.py`:
   - Add `CognitionEvidenceMode(StrEnum)` with `DISABLED` and `DETERMINISTIC`,
     docstring: lockstep with `V4CapabilityFlags.legal_disputes`, run-level
     cognition mode, not a capability flag.
   - Add `evidence_mode: CognitionEvidenceMode = CognitionEvidenceMode.DISABLED`
     and `evidence_policy: EvidencePolicy | None = None` next to
     `dispute_mode`/`dispute_policy` (638-639).
   - Mirror the dispute policy normalization at 1192-1198: disabled clears the
     policy to `None`; deterministic defaults it; a wrong type fails closed.
   - Add evidence entries to the fingerprint material at 1530-1534 only inside
     the `DETERMINISTIC` branch, exactly like the dispute branch: include
     `evidence_mode.value` and `evidence_policy.version` only when the mode is
     deterministic. Disabled configurations must keep their previous
     fingerprint.
   - Pass the new fields through the `CognitionLoop` construction at 1805-1806.
2. In `src/agents/cognition/loop.py`:
   - Add `evidence_mode` and `evidence_policy` keyword parameters after
     `dispute_mode`/`dispute_policy` (499-500), defaulting to disabled/None.
   - Store `_evidence_mode`, `_evidence_policy`, and `_prepared_evidence = None`
     alongside the dispute slots (319-320, 365).
   - Validate in `__init__`: deterministic mode requires a policy; disabled mode
     requires `None`; policy version must equal
     `EVIDENCE_TESTIMONY_POLICY_VERSION`; otherwise raise `ValueError` (same
     style as the dispute validation at 983-1002).
3. In `src/simulation/runner.py` `_cognition_config_for`:
   - Import `CognitionEvidenceMode` and `default_evidence_policy`.
   - Compute `evidence_mode = DETERMINISTIC if legal_disputes_enabled else
     DISABLED` and `evidence_policy = default_evidence_policy()` only when
     enabled.
   - Add INFO `cognition_evidence_mode mode=%s policy_version=%s`.
   - Pass both values at the three call sites that already pass dispute mode
     (2670, 6335, 6711 area).
4. Ensure disabled mode keeps `evidence_ledgers` empty, allocates no rows or
   notices, and leaves the config fingerprint unchanged.

### Required Interfaces and Contracts

- `CognitionLoopConfig.evidence_mode` and `.evidence_policy` exist but are not
  serialized to runner JSON and are not read by `runner_serialization.py`.
- `CognitionEvidenceMode.DETERMINISTIC` implies `EvidencePolicy` with version
  `evidence-testimony.v1`.
- The mode is a pure function of `v4_capability_flags.legal_disputes`.

### Requirement Evidence

- `src/agents/cognition/configuration.py` 424-432 — dispute mode precedent.
- `src/agents/cognition/loop.py` 983-1002 — mode/policy validation precedent.
- `src/simulation/runner.py` 1328-1406 — dispute mode derivation.

### Error Handling and Logging

- Invalid mode/policy pairing raises `ValueError` before any tick executes.
- INFO: one line per cognition config with mode and policy version only.
- DEBUG: `cognition_evidence_mode_source flag=%s` boolean; never log policy
  object contents or owner ids.

### Tests

- Extend `tests/unit/test_evidence_testimony_config.py`:
  - disabled mode allocates no `_prepared_evidence` and produces an empty
    `evidence_ledgers` tuple after a runner result;
  - deterministic mode requires a policy and rejects a wrong version;
  - config fingerprint changes when only a deterministic `evidence_mode`
    changes, and an all-disabled config keeps its V4-07 fingerprint;
  - runner serialization does not gain an `evidence_mode` key.
- Command: `uv run pytest tests/unit/test_evidence_testimony_config.py tests/unit/test_runner_serialization.py -q`.

### Acceptance Criteria

- Flags-off runs are byte-identical to V4-07 behavior in existing regression
  tests.
- No runner JSON key, schema version, or serialization branch is added.

### Verification

- `uv run pytest tests/unit/test_evidence_testimony_config.py tests/unit/test_runner_serialization.py tests/unit/test_v1_regression_gate.py -q`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: a new enum name drifts between modules or wire/snapshot layers.
  Mitigation: Task 1 is the only definition source; later tasks import it and
  tests assert exact frozensets.
- Risk: the seam silently gains a flag or runner key.
  Mitigation: Task 2 edits no registry/serialization file and Task 20 scans for
  `runner-config-v57` and per-agent evidence keys.
- Risk: the disabled path allocates or mutates state.
  Mitigation: Task 3 tests assert empty allocations and fingerprint-only changes.

## Phase Completion Checklist

- Every Task 1-3 in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
