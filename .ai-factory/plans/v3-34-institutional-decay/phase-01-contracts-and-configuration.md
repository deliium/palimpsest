# Phase 1: Contracts and configuration

Plan: [index.md](index.md)
Tasks: 1–3
Depends on: none

## Objective

Define a default-off subjective attrition channel, without introducing an objective institution entity, a collapse command, or a new capability flag.

## Current-Code Evidence

| Path | Symbols / sections | Why it matters |
|---|---|---|
| `src/agents/cognition/institution_concepts.py` | `InstitutionConcept`, `InstitutionConceptLedger`, `InstitutionConceptPolicy`, `_freeze` | Six subjective strengths; locked v1 constants; concept ID changes when anchors change, while `group_key` survives. |
| `src/agents/cognition/offices.py` | `OfficeConcept`, `_process_availability` | Stable local office identity, predecessor links, explicit support and succession; absence is not vacancy. |
| `src/agents/cognition/institutional_memory.py` | `InstitutionalMemoryLedger`, `InstitutionalProvenance` | Acquired knowledge survives carrier loss; missing, pruned, and unresolved evidence differ. |
| `src/simulation/runner_models.py` | `AgentCognitionSpec`, institutional-memory validation near 10552 | v53 is currently exclusive to institutional memory; same-owner prerequisites. |
| `src/simulation/runner_serialization.py` | `_COGNITION_KEYS_V53`, `_v53_family_root_keys`, agent/root/wire dispatch | Exact inherited keysets, not optional fields. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/agents/cognition/institutional_decay.py` | create | Immutable owner-local state, signals, locked policy, validators, public update interface. |
| `src/agents/cognition/__init__.py` | modify | Explicit public exports for the new contracts. |
| `src/agents/cognition/configuration.py` | modify | Separate cognition enum, disabled normalization, policy and fingerprint. |
| `src/agents/cognition/loop.py` | modify | Constructor/slots normalization for the new mode and locked policy; no update execution until Phase 2. |
| `src/simulation/runner_models.py` | modify | v54 constant, runner enum, cognition field and validation. |
| `src/simulation/runner_serialization.py` | modify | Exact v54 cognition/root/agent wire dispatch and inherited selectors. |
| `src/simulation/compatibility.py` | modify | Accepted v54, bump trigger and unchanged default write identity. |
| `src/simulation/runner.py` | modify | Runner-to-cognition enum/policy composition. |
| `tests/unit/test_institutional_decay_contracts.py` | create | Strict immutable contracts and policy pins. |
| `tests/unit/test_runner_config_v54.py` | create | Schema/selector/composition matrix. |
| `tests/unit/test_compatibility_matrix.py` | modify | Accepted set and default pins. |

## Task 1: Define owner-local decay contracts and locked policy

### Intent

Keep five measured dimensions distinct from six institution-concept strengths. No single health/reward scalar, world institution ID, authoritative occupant, or institution type is introduced.

### Implementation Steps

1. Introduce `INSTITUTIONAL_DECAY_POLICY_VERSION = "institutional-decay.v1"`, `InstitutionalDecayPolicy`, `InstitutionDecaySignal`, `InstitutionDecayBinding`, `InstitutionDecayRecord`, `InstitutionDecaySample`, `InstitutionDecayLedger`, and `InstitutionDecayUpdate` in the new module. Use frozen/slotted dataclasses and exact enum/type/owner validation, following institutional memory.
2. Define `InstitutionDecayUpdate(concepts: InstitutionConceptLedger, decay: InstitutionDecayLedger)`. Introduce `empty_institution_decay_ledger(owner_id)` and `require_owner_institution_decay(value, owner_id, field_name=...)`. `None` means disabled, a typed empty ledger means enabled without evidence.
3. A binding stores the owner's `group_key`, inception tick, current concept ID, anchor tuple, **separate native structural component digests**, and optional locally evidenced context/location and office ID. Its stable `local_pattern_id` is SHA256 of versioned owner + group key + inception, not the mutable concept ID. Legacy concept anchors often hash a whole sequence into one token; they are not sufficient components for structural split/transform matching. Derive components during native extraction as described in Phase 2, never by reversing a digest. Store no global institution identity. An unresolved association stays unresolved.
4. A signal stores pattern/channel, canonical action/evidence key, observation tick, source tick, immediate channel, independently resolved actor when available, source-root reference when available, and local context. Root references are opaque provenance, never lookup keys. Add `InstitutionDimensionEvidence` for **per-update sufficient statistics**, not rolling ratios: resolved observed-cohort IDs, independently evidenced supporter/root pairs, accepted participant/action keys, performed-procedure keys, eligible/completed succession transition keys, and before/retained acquired-entry keys. Every dimension carries availability (`observed`, `unknown`, `disabled`, `partial`, `not_applicable`) and evidence interval. Do not substitute nearby counts for these quantities.
5. Samples contain owner/local-pattern IDs, observation tick, native source interval, six strengths, recognized flag, the per-update dimension evidence, legacy anchors plus native structural components/context/office-predecessor metadata, and coverage/pruning metadata. They are subjective measurements, not lifecycle classifications. Four-tick ratios are computed **once**, in detached analysis; cognition stores no analytical window state or lifecycle label. Ledger carries records, samples, last update tick, dedup receipts and pruning metadata.
6. Lock constants: quantum `0.000001`; per-unrefreshed-channel loss `0.04` per executed cognitive update; analysis input window 4 consecutive observation/update ticks; maximum local patterns 16, retained samples 256 total per owner, receipts 512 total per owner. Preserve lightweight retired-pattern bindings until the pattern cap is reached. Deterministic overflow never evicts an active pattern to force collapse: ignore a new pattern and mark partial coverage. Samples prune oldest `(tick, local_pattern_id)`; receipts prune oldest `(source_tick, evidence_key)`. Track sample-pruned-through boundaries per pattern and receipt-pruned-through source boundaries separately. A historical pruning counter does not make every later complete window partial forever; completeness is assessed against that window's interval and required sources.
7. Keep hysteresis/lifecycle thresholds analysis-owned in Phase 3, separate from this policy. No automatic forgetting, office vacancy, property transfer, or command generation belongs in these contracts.
8. Records retain factual identity witnesses independently of the sample ring: actual binding inception (not the legacy concept's sometimes synthetic `first_tick=0`), structural signature/revision source key, last native activity tick, and current/previous activity-span start witnesses. Track a bounded covered-inactive streak, saturated at eight updates. The first fresh native practice after eight fully covered inactive updates gets a new span-start witness; an unknown visibility gap does not establish such a boundary. Store only the current and previous witnesses per pattern, plus opaque references to older witnesses as pruned. This is factual interval bookkeeping: it neither classifies collapse nor changes commands. Persist these fields in runtime checkpoints; never derive episode numbering from the retained sample position.

### Required Interfaces and Contracts

- New function signature: `apply_institution_decay_update(*, observation, identity, previous_concepts, previous_decay, norms=None, conventions=None, groups=None, possession=None, memories=(), advice_delta=(), mentorship=None, prior_offices=None, prior_institutional_memory=None, policy=None) -> InstitutionDecayUpdate`.
- Inputs are typed owner-safe observation/identity and same-owner ledgers only. Reject event bodies, engines, repositories, other-owner state, analytical rows/documents, booleans as ticks/counts, nonfinite strengths and mutable unordered collections.
- Mode/policy are non-authoritative cognition configuration. Perceived fading and analytical collapse never grant or remove world permissions.

### Requirement Evidence

User request — track five dimensions and allow weakening; `.ai-factory/ARCHITECTURE.md` — authority, deterministic identity, versioned extensions; `docs/institutional-memory.md` — carrier loss and knowledge retention. These sources agree; the sidecar keeps measurement separate from retained knowledge.

### Error Handling and Logging

Fail closed with safe reason codes on invalid owners/types/policy/constants. DEBUG: owner ID, tick, counts, policy version; WARN: invalid carry or capacity exclusion. Never log anchors, fingerprints, source keys, messages, names, claim content or record facts.

### Tests

`tests/unit/test_institutional_decay_contracts.py`: empty versus disabled; exact enums; forged stable IDs; foreign owners; invalid spans/counts; NaN/inf; defensive detachment; policy override rejection; deterministic cap/pruning behavior; interval-specific pruning boundaries; no rolling-ratio fields in raw samples; factual identity witnesses surviving ring-buffer eviction; no forbidden authority fields.

### Acceptance Criteria

All new values are immutable, owner-validated and deterministic. Pattern identity survives added anchors without conflating different groups. Missing measurements cannot silently become zero.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_decay_contracts.py -q`

Expected: all contract cases pass with project coverage settings retained.

## Task 2: Add exact runner-config-v54 and supported combinations

### Intent

Enable the new policy without changing any accepted legacy payload or selecting a newer write version merely because analysis was requested.

### Implementation Steps

1. Add `RUNNER_SCHEMA_VERSION_V54`, `InstitutionalDecayMode {DISABLED, DETERMINISTIC}`, and `AgentCognitionSpec.institutional_decay_mode = DISABLED` in `runner_models.py`. v54 requires at least one deterministic decay owner. Every such owner must enable its own deterministic `institution_concept_mode`; office and institutional memory are optional. Cross-owner dependencies are invalid.
2. Set `_COGNITION_KEYS_V54 = _COGNITION_KEYS_V53 | {"institutional_decay_mode"}`. Root shape is exactly the v53 family root, with no new run-level sibling. Decode v54 with this exact keyset for every agent, including disabled agents. Earlier schemas reject the new JSON key and reject an enabled mode in in-memory configs.
3. Update encoder, decoder, root dispatch, nested cognition dispatch, separate wire-agent schema dispatch, and constructor forwarding. Audit each existing `V53` branch in the two runner files individually: add V54 only to inherited feature acceptance lists, never to historical exact-key validation branches.
4. Institutional memory enabled configs accept `{v53, v54}`; v53 still requires some institutional memory, while v54 requires decay but may omit memory. Admit `species_default_institutional_memory_v1` on v54 as well as v53, preserving that profile's empty content and decay-disabled setting. Extend relevant profile exceptions, v3 gates and inherited modes/specs without requiring unrelated optional siblings.
5. Update `simulation.compatibility` accepted runner versions and ownership notes. Preserve default `RUNNER_SCHEMA_VERSION = v4`, all historical selectors, current replay/codec selection, command count 43, observer semantic count 73, `/v1`, `observer-protocol-v1`, and migration head `0017`.
6. Keep public imports consistent with current direct `simulation.runner_models` imports; do not bulk-export old runner versions from `simulation/__init__.py` as cleanup.

### Required Interfaces and Contracts

Supported: decay + concepts alone; decay + concepts + offices; decay + concepts + memory; all three, with optional mediation/collective decisions and existing family siblings. Mixed owners may enable different allowed modes. No owned capability flag is required solely for decay; `institutional_economy` stays unowned/fail-closed. v54 is selected only for a genuinely enabled decay mode; all-disabled configurations continue using their existing valid schema.

### Requirement Evidence

Index reconciliation matrix; `runner_models.py` existing v53 same-owner validation; `runner_serialization.py` exact key recurrence; architecture accepted-set/exact-key-set rule. v54 refines, rather than widens, v53.

### Error Handling and Logging

Use safe codes `institutional_decay_requires_v54`, `v54_requires_institutional_decay`, and `institutional_decay_requires_local_concepts`. Preserve legacy reason codes for legacy invalid inputs. Log field path/schema/mode only.

### Tests

`test_runner_config_v54.py`: every supported combination, mixed owners, missing/extra/invalid mode keys, old-schema rejection, disabled v54 rejection, wrong-owner prerequisite, exact roundtrip bytes, v53 memory/profile preservation, v54 profile admission without decay content, all inherited root shapes already represented by v53 tests. Extend `test_compatibility_matrix.py`; do not rewrite historical goldens to v54.

### Acceptance Criteria

The supported-combination matrix roundtrips, unsupported combinations fail closed, and v4/v49–v53 behavior remains unchanged.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_runner_config_v54.py tests/unit/test_runner_config_v53.py tests/unit/test_compatibility_matrix.py -q`

Expected: all tests pass; no implicit new world feature requirements.

## Task 3: Compose cognition mode, policy and fingerprints

### Intent

Ensure disabled owners allocate no decay state and keep existing cognition fingerprints; enabled owners identify the exact locked policy.

### Implementation Steps

1. Add `CognitionInstitutionalDecayMode` and optional policy to `configuration.py`, with exact enum/type validation and disabled-policy normalization matching institutional memory. Add enabled-only fingerprint material: mode plus `institutional-decay.v1` and locked constants. Do not add absent/disabled keys to legacy fingerprint payloads.
2. Extend `CognitiveLoop` constructor/slots with the mode/policy, default disabled. Normalize and validate without creating ledgers or opening resources. The construction seam must reject decay without local institution concepts, even when a caller bypasses runner configuration.
3. Extend runner cognition composition near the current institutional-memory mapping to translate runner mode to cognition mode, allocate a locked policy only when enabled, and forward both. Export only deliberate public symbols from cognition.
4. Add fingerprint/construction tests to `test_institutional_decay_contracts.py` and runner composition cases to `test_runner_config_v54.py`.

### Required Interfaces and Contracts

No provider, API, settings environment variable, new V3 flag, or LLM schema is introduced. Logging remains metadata-only despite the verbose preference.

### Requirement Evidence

`configuration.py` enabled-only institutional-memory fingerprint pattern; user-selected tests/logging/docs defaults; architecture optional-channel parity.

### Error Handling and Logging

Reject wrong enum/policy and local prerequisite with safe messages. DEBUG constructor/composition logs include mode/policy version, not configuration fingerprints or source content.

### Tests

Disabled policy normalization; disabled fingerprint equality to pre-feature configuration; enabled fingerprint distinction; locked constant validation; direct-construction prerequisite; runner mapping; mixed owners.

### Acceptance Criteria

Default-off has no allocation or fingerprint change. Enabled construction is explicit and rejects ambiguous policy selection.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_decay_contracts.py tests/unit/test_runner_config_v54.py -q`

Expected: construction and identity checks pass.

## Phase Risks and Mitigations

- Numerous explicit version allowlists: audit V53 references, test both root and wire-agent dispatch, and preserve exact legacy keysets.
- Five requested measurements do not equal six existing strengths: name and test the mapping, never synthesize a scalar or turn disabled evidence into failure.
- A mutable concept ID cannot identify lineage: retain a separate owner-local binding based on group/inception.

## Phase Completion Checklist

- Tasks 1–3 satisfy their acceptance criteria and commands pass.
- Only `index.md` task checkboxes are updated after verification.
