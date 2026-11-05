# Phase 1: Treaty Contract and Seam

Plan: [index.md](index.md)
Tasks: 1-3
Depends on: none

## Objective

Freeze one additive treaty extension to the owner-scoped `diplomacy` context:
closed vocabulary, deterministic identity grammar, a locked `treaty.v1` policy,
and an explicit activation statement proving that V4-11 adds no V4 flag,
context, runner schema, runner root field, per-agent runner key, event, command,
observer semantic type, write pair, `/v2` route, or migration.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/agents/cognition/diplomacy.py` | `DIPLOMACY_POLICY_VERSION` 111; `DIPLOMACY_ID_PREFIXES` 128-139; `_FORBIDDEN_FIELD_NAMES` 150-172; enums 175-341; `DiplomacyPolicy` 346-379; `DiplomacyLedger` 1149-1211 | Existing closed vocabulary, identity prefixes, forbidden-name guard, policy lock, and ledger shape to extend additively. |
| `src/agents/cognition/diplomacy.py` | `diplomacy_scope_covers` 461-489; `LONG_RUNNING_INSTRUMENT_KINDS` 324-326; `DIPLOMACY_SCOPE_COVERAGE` 311-322 | The scope/duration matrix already rejects `single_act`/`occasion` for long-running forms. Treaties must use the same helper. |
| `src/simulation/v4_architecture.py` | `V4ContextId.DIPLOMACY`; `DIPLOMACY` context entry 150-163; `V4_OWNED_CAPABILITY_FLAGS` consumers | `diplomacy` is already owned by V4-10; V4-11 deepens it without a flag change. |
| `src/simulation/runner_models.py` | `V4CapabilityFlags` 305-325; `RUNNER_SCHEMA_VERSION_V56` | The accepted seam has exactly one `v4_capability_flags` sibling. |
| `src/agents/cognition/delegation_representation.py` | `RepresentationScopeKind` 103-112; `RepresentationDurationKind` 115-122 | Treaty authority reuses `negotiate`/`decide` scope beliefs and the long-running duration matrix. |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT` 53 | The current catalog is 164; Phase 3 raises it to 168 and sweeps current pins. |
| `tests/architecture/test_diplomacy_boundaries.py` | 57-201 | The V4-10 boundary suite already forbids `TreatyStore`, `TreatyAuthority`, scores, and command paths; V4-11 extends it. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/agents/cognition/diplomacy.py` | modify | Add treaty enums, ID prefixes, `TREATY_POLICY_VERSION`, `TREATY_CONTRACT_VERSION`, treaty scope mapping, forbidden names, and deterministic ID helpers. |
| `src/agents/cognition/__init__.py` | modify | Export each new public treaty symbol and policy helper. |
| `tests/unit/test_diplomacy_treaty_contracts.py` | create | Closed-vocabulary, ID grammar, scope-matrix, and forbidden-name tests. |
| `tests/unit/test_diplomacy_treaty_config.py` | create | Activation and no-new-schema tests. |

## Task 1: Freeze the treaty vocabulary and identifier grammar

### Intent

Give the implementer one closed treaty vocabulary instead of leaving enum
names, ID prefixes, or scope behavior to guesswork. Every later row, frame,
snapshot, analysis row, API schema, and UI label consumes these exact values.

### Implementation Steps

1. In `src/agents/cognition/diplomacy.py`, immediately after the V4-10 enums,
   add these closed `StrEnum` types with exactly these members:
   - `TreatySubjectKind`: `ceasefire`, `access`, `migration`,
     `resource_sharing`, `trade`, `territorial_understanding`, `mutual_aid`,
     `unknown`.
   - `TreatyChangeKind`: `original`, `amendment`, `renewal`, `accession`,
     `withdrawal`, `suspension`, `termination`, `unknown`.
   - `TreatyStatus`: `proposed`, `apparently_accepted`, `suspended`,
     `terminated`, `expired`, `superseded`, `unknown`.
   - `TreatyAcceptanceBasis`: `all_participants_declared`, `proposer_only`,
     `rejected`, `suspended`, `terminated`, `expired`, `superseded`, `none`,
     `unknown`.
   - `TreatyDeclarationAct`: `propose`, `accept`, `reject`, `accede`,
     `withdraw`, `amend`, `renew`, `suspend`, `terminate`, `interpret`,
     `ignore`.
   - `TreatyProvisionKind`: `non_hostility`, `passage`, `resource_sharing`,
     `exchange`, `territory_acknowledgement`, `mutual_assistance`,
     `procedure`, `unknown`.
   - `TreatyRecollectionBasis`: `durable_record`, `institutional_memory`,
     `communicated_testimony`, `narrative`, `direct_participation`, `unknown`.
   - `TreatyRecollectionStance`: `remember`, `reinterpret`, `ignore`, `renew`,
     `unknown`.
   Do not add a `misremember` stance, `war`, `peace`, `border`, `polity`, or
   `citizenship` member.
2. Add `TREATY_CONTRACT_VERSION: Final[str] = "diplomacy-treaties-v1"` and
   `TREATY_POLICY_VERSION: Final[str] = "treaty.v1"` beside
   `DIPLOMACY_POLICY_VERSION`.
3. Add these ID prefixes and include every one in `DIPLOMACY_ID_PREFIXES`:
   - `DIPLOMACY_TREATY_ID_PREFIX = "dpg-"`
   - `DIPLOMACY_TREATY_VERSION_ID_PREFIX = "dpv-"`
   - `DIPLOMACY_TREATY_DECLARATION_ID_PREFIX = "dpq-"`
   - `DIPLOMACY_TREATY_RECOLLECTION_ID_PREFIX = "dpz-"`
   - `DIPLOMACY_TREATY_MISREPRESENTATION_ID_PREFIX = "dpj-"`
4. Add deterministic helpers using the existing `diplomacy_record_id` and
   `_digest` helpers:
   - `diplomacy_treaty_id(owner_id, relation_id, subject_kind, opened_tick)`
   - `diplomacy_treaty_version_id(owner_id, treaty_id, version_index, change_kind, terms_digest)`
   - `diplomacy_treaty_declaration_id(owner_id, treaty_id, version_id, party_id, act, tick, revision)`
   - `diplomacy_treaty_recollection_id(owner_id, treaty_ref, version_ref, basis, stance, first_tick)`
   - `diplomacy_treaty_misrepresentation_id(owner_id, version_id, envoy_ref, kind, observed_tick)`
   Every helper validates its enum arguments and returns the prefixed 16-hex
   identifier used by `_ID_PATTERNS`.
5. Extend `DIPLOMACY_SCOPE_COVERAGE` with
   `"treaty": frozenset({"negotiate", "decide"})` and add `"treaty"` to
   `LONG_RUNNING_INSTRUMENT_KINDS`. This is an internal mapping; do not change
   `RepresentationScopeKind` or `RepresentationDurationKind`.
6. Extend `_FORBIDDEN_FIELD_NAMES` with `treaty_store`, `treaty_authority`,
   `treaty_registry`, `enforced`, `enforcement`, `war_state`,
   `ceasefire_state`, `misremembered`, `false_belief`, `truth_value`,
   `legitimacy`, and `reliability`. Do not add the exact token `treaty`
   because the contract now legitimately owns treaty records; keep
   `binding`, `authority`, `truth`, `legitimate`, `score`, and the existing
   score-family names forbidden.
7. Export every new enum, constant, and helper from
   `src/agents/cognition/__init__.py` and add each name to that module's
   `__all__`.

### Required Interfaces and Contracts

- Treaty parties are exactly V4-10's `DiplomaticPartyKind` members. Do not
  create a treaty-only party kind.
- Treaty subject kinds are descriptive categories, not capabilities,
  permissions, or objective states.
- A `ceasefire` treaty is a belief about an intended non-hostility
  understanding. It is not a `WarState`, a truce engine, or a command filter.
- ID helpers are pure and deterministic. They must not call `hash()`,
  `uuid`, the wall clock, or global RNG.
- `diplomacy_scope_covers(instrument_kind="treaty", ...)` returns `False` for
  `single_act` and `occasion` duration kinds, `False` for a non-
  `negotiate`/`decide` scope, and `False` when a named scope subject does not
  equal the treaty subject.

### Requirement Evidence (when reconciliation applies)

- Original Request examples (`ceasefire`, `access agreement`, `migration
  agreement`, `resource sharing`, `trade agreement`, `territorial
  understanding`, `mutual aid`) map one-to-one to `TreatySubjectKind`.
- `.ai-factory/ARCHITECTURE.md` "Capability ownership" and the V4-10 seam:
  `diplomacy` is already owned; V4-11 adds no flag.
- `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts":
  a ceasefire or access agreement is an owner belief, never world authority.
- `.ai-factory/RULES.md` axioms 1, 4, 5, and the coding standards on frozen
  contracts and boundary rejection.

### Error Handling and Logging

- Invalid enum types, malformed IDs, or unknown prefixes raise
  `DiplomacyError` with a stable code such as `diplomacy_invalid_record`,
  `diplomacy_invalid_treaty`, or `diplomacy_unknown_treaty_kind`. Never include
  the offending value in the exception.
- Log only at DEBUG: `treaty_vocabulary_loaded version=diplomacy-treaties-v1`
  and `treaty_id_minted kind=<closed-kind>` without the ID.
- Never log treaty IDs, subject tokens, participant tokens, terms digests,
  record anchors, institutional-memory anchors, or frame bodies.

### Tests

`tests/unit/test_diplomacy_treaty_contracts.py`:

- Assert exact members and member values for all eight new enums.
- Assert no enum member is `war`, `peace`, `border`, `polity`, `citizenship`,
  `misremembered`, `enforced`, `binding`, or `legitimate`.
- Assert every new prefix is in `DIPLOMACY_ID_PREFIXES` and every helper output
  matches `_ID_PATTERNS`.
- Assert helper determinism across repeated calls and sensitivity to owner,
  treaty, version index, kind, and tick.
- Assert `diplomacy_scope_covers` accepts a `negotiate`/`decide` mandate with
  `until_tick`/`until_revoked`, rejects `single_act`/`occasion`, rejects
  mismatched named subjects, and rejects `speak_for`/`carry_message`.
- Assert every forbidden field name is rejected by
  `assert_diplomacy_no_forbidden_fields`.
- Assert treaty records may use fields named `treaty_id`, `treaty_ref`,
  `version_id`, and `record_refs` without tripping the forbidden-name guard.

### Acceptance Criteria

- One closed treaty vocabulary exists and is exported.
- Treaty identity helpers are deterministic and content-addressed.
- The scope/duration matrix covers `treaty` exactly once and rejects
  single-act and occasion mandates.
- No war, peace, border, polity, citizenship, truth, enforcement, or
  misremembering member exists.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_contracts.py -q`
- Expected: all tests pass; `ruff` and `mypy` report no new issues.

## Task 2: Add the locked treaty policy

### Intent

Bound every treaty row with one immutable policy so a later implementation
cannot silently choose different caps, truncation rules, or frame limits.

### Implementation Steps

1. In `src/agents/cognition/diplomacy.py`, add `TREATY_POLICY_VALUES` as a
   `MappingProxyType` with exactly:
   - `max_treaties_per_relation = 8`
   - `max_versions_per_treaty = 16`
   - `max_treaty_declarations_per_version = 32`
   - `max_treaty_recollections = 64`
   - `max_participants_per_treaty = 32`
   - `max_provisions = 8`
   - `max_record_refs = 8`
   - `max_institutional_memory_refs = 8`
   - `max_treaty_frame_chars = 832`
2. Add `@dataclass(frozen=True, slots=True) class TreatyPolicy` with those
   exact fields and a `__post_init__` mirroring `DiplomacyPolicy`: reject
   forbidden field names, type/value drift, and any deviation from
   `TREATY_POLICY_VALUES` with `diplomacy_policy_not_locked`.
3. Add `default_treaty_policy() -> TreatyPolicy` that returns the single
   locked value and logs only
   `treaty_policy_loaded version=treaty.v1` at DEBUG.
4. Add `TREATY_POLICY_VERSION` to the module facade and to
   `agents.cognition.__all__`.
5. Do not add treaty fields to `DiplomacyPolicy`. The V4-10 policy remains
   byte-identical so existing ledgers and snapshot-v1 documents stay valid.

### Required Interfaces and Contracts

- `TreatyPolicy` is a cognition-owned, run-independent constant. It is never
  read from settings, runner JSON, environment variables, or per-agent config.
- Caps are absolute per owner ledger:
  - treaties per relation;
  - versions per treaty;
  - declarations per version;
  - recollections per owner ledger;
  - participants per treaty/version;
  - provisions per version;
  - durable-record anchors per version;
  - institutional-memory anchors per version;
  - bounded `trt_v1` frame characters.
- No cap field may be named `score`, `rank`, `trust`, `binding`, `authority`,
  `enforced`, or `legitimacy`.

### Requirement Evidence (when reconciliation applies)

- Original Request "Treaties must exist through records" requires bounded
  record and institutional-memory anchor caps.
- `.ai-factory/ARCHITECTURE.md` "Key Principles" 2 and 3: deterministic
  identity and fail-closed locked policy.
- V4-10 `DiplomacyPolicy` precedent at 346-379: one locked value, no runtime
  tuning.

### Error Handling and Logging

- Any altered value raises `DiplomacyError("diplomacy_policy_not_locked")`.
- Log only `treaty_policy_loaded version=treaty.v1` at DEBUG. Do not log cap
  values per treaty or per owner.

### Tests

`tests/unit/test_diplomacy_treaty_contracts.py` additions:

- Assert `default_treaty_policy()` equals the locked values.
- Assert every field drift raises `diplomacy_policy_not_locked`.
- Assert a forbidden field added by a subclass or replacement fails.
- Assert `DiplomacyPolicy` field set and values are unchanged from V4-10.
- Assert the treaty policy is not present in `Settings` or runner models.

### Acceptance Criteria

- One locked `treaty.v1` policy exists.
- The V4-10 `diplomacy.v1` policy is unchanged.
- No settings or runner key can alter treaty caps.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_contracts.py -q`
- Expected: all tests pass.

## Task 3: Confirm treaty activation on the owned diplomacy flag

### Intent

Prove that V4-11 activates only through the already-owned `diplomacy` flag and
does not create a second capability seam. This is the explicit no-new-schema
gate for the whole plan.

### Implementation Steps

1. Add `TREATY_CONTRACT_VERSION` to the `DiplomacyLedger`-adjacent exports and
   document in the module docstring that treaty rows exist whenever a
   diplomacy ledger exists.
2. Add a tiny pure helper
   `treaty_extension_enabled(ledger: DiplomacyLedger | None) -> bool` that
   returns `ledger is not None and ledger.policy_version ==
   DIPLOMACY_POLICY_VERSION`. It performs no allocation and logs nothing.
3. Do not modify `V4CapabilityFlags`, `V4ContextId`, `V4_CONTEXTS`,
   `runner_models.py`, `compatibility.py`, or `v4_architecture.py`. The
   context entry, ownership, prerequisites, and `uses_existing_events` value
   stay exactly as V4-10 shipped them.
4. Add tests that construct the base V4-01 config on `runner-config-v56`:
   - `diplomacy=True` constructs and yields an active diplomacy ledger;
   - `organizations=True` alone yields no diplomacy ledger and no treaty rows;
   - `formal_rules=True` or `legal_disputes=True` alone leaves diplomacy
     disabled;
   - `diplomacy=True` with `organizations=False` still allows agent and
     settlement parties while organization/coalition anchors stay unresolved;
   - `organized_conflict=True` still fails with
     `capability_unimplemented` at `stage="v4_capability_flags"`;
   - no source file contains `runner-config-v57`;
   - no runner model or per-agent spec has a `treaty_mode`, `treaties`, or
     `treaty` field.

### Required Interfaces and Contracts

- Activation is exactly `runner-config-v56` plus
  `v4_capability_flags.diplomacy = true`.
- There is no `TreatyMode`, no per-agent mode, no run-level treaty spec, and
  no treaty settings object.
- The `diplomacy` context remains owner-scoped with owners
  `agents.cognition`, `social`, `simulation` and prerequisite `organizations`.
- The registry remains 14 contexts / 12 flags / four owned / eight unowned.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` "Capability ownership" explicitly lists
  `diplomacy` as owned and the other eight V4 flags as unowned.
- `.ai-factory/ARCHITECTURE.md` V4-10 seam: no `runner-config-v57`, root field,
  or per-agent runner key.
- `src/simulation/v4_architecture.py` 150-163 and 324-326 are the authority for
  the context declaration.
- `docs/configuration.md` 455-465 documents the existing diplomacy activation.

### Error Handling and Logging

- A disabled flag path logs nothing new. An enabled path logs at INFO once:
  `treaty_extension_active contract=diplomacy-treaties-v1` with no owner,
  party, treaty, or version identifiers.
- A `v57` or runner-field drift is a test failure, not a runtime fallback.

### Tests

`tests/unit/test_diplomacy_treaty_config.py`:

- Base config on v56 with `diplomacy=True` constructs and the exported ledger
  satisfies `treaty_extension_enabled`.
- Each other owned flag alone does not activate diplomacy.
- `diplomacy=True` without `organizations` still works and unresolved
  organization parties remain legal.
- `organized_conflict=True` fails closed with the exact code and stage.
- Scan `src/` for `runner-config-v57` and assert no match.
- Assert `{field.name for field in fields(SimulationRunnerConfig)}` and all
  agent specs contain no `treaty` key.

### Acceptance Criteria

- Treaties activate only through the owned diplomacy flag.
- No new capability flag, context, runner schema, root field, or per-agent key
  exists.
- The V4-01 invariant suite still proves 14 contexts / 12 flags / four owned.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_config.py tests/architecture/test_v4_architecture_invariants.py -q`
- Expected: all tests pass; no `v57` occurrence.

## Phase Risks and Mitigations

- Risk: Adding treaty enums to `diplomacy.py` accidentally changes V4-10
  snapshot or frame behavior.
  Mitigation: keep `dip_v1` field count and `diplomacy.v1` policy untouched;
  add new prefixes and new enums only; run the V4-10 focused suite in this
  phase.
- Risk: The forbidden-name guard rejects legitimate `treaty_id` fields.
  Mitigation: the guard matches exact field names, not substrings; tests prove
  `treaty_id`, `treaty_ref`, and `version_id` are accepted while `treaty` and
  `binding` remain rejected.
- Risk: A new treaty scope silently widens representation authority.
  Mitigation: treat `treaty` as a string key in the existing diplomacy scope
  mapping only; do not add a `RepresentationScopeKind` member and do not grant
  world permission.

## Phase Completion Checklist

- Every Task 1-3 acceptance criterion is met.
- `dip_v1` remains 15 fields and 320 characters; `diplomacy.v1` remains
  unchanged.
- No `runner-config-v57`, new flag, context, runner field, or per-agent key
  exists.
- `index.md` checkboxes are updated only after verification passes.
