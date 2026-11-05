# Phase 7: Invariants, End-to-End Treaty, and Regression

Plan: [index.md](index.md)
Tasks: 21-23
Depends on: Phase 6

## Objective

Prove every treaty authority claim with architecture, determinism, and
end-to-end tests, then run the full V1-V4 regression and qualification lanes.
The end-to-end scenario runs in-process in the focused/unit lane without
PostgreSQL and uses real admission, speech, recognition, publication, and
routes.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `tests/architecture/test_diplomacy_boundaries.py` | 57-201 | Existing ownership, command-path, world-read, score/oracle, representation-roundness, token-domain, and alignment-isolation tests to extend. |
| `tests/unit/test_diplomacy_determinism.py` | 1-80 | Repeated-update/digest determinism pattern. |
| `tests/unit/test_diplomacy_e2e.py` | existing | In-process E2E pattern: real ticks, speech, recognition, publication, routes, no PostgreSQL. |
| `tests/unit/test_diplomacy_acceptance.py` | 215-510 | Principal/envoy acceptance, scope, misrepresentation, and actor-satisfaction cases to mirror. |
| `tests/unit/test_diplomacy_api.py` | 124-240 | Route count, capability, disabled state, 404, and cursor tests to extend. |
| `tests/unit/test_diplomacy_physical_distinction.py` | existing | Physical non-interference precedent: belief changes never alter admission. |
| `tests/integration/test_delegation_representation_e2e.py` | existing | Integration E2E sibling; treaty E2E should stay in the unit lane. |
| `docs/development.md` | test command table | Exact commands for the regression receipt. |
| `tests/compose/acceptance.py` | acceptance harness | Compose/browser lane contract. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `tests/architecture/test_treaty_boundaries.py` | create | Ownership, no-command, no-world-read, no-score/oracle, no-identity-mutation, no-enforcement, frame-trust, pin tests. |
| `tests/architecture/test_diplomacy_boundaries.py` | modify | Include treaty modules in existing scans; keep V4-10 assertions. |
| `tests/unit/test_diplomacy_treaty_determinism.py` | create | Repeated updates, ordering, ID/digest determinism, no hash/UUID/wall clock. |
| `tests/unit/test_diplomacy_treaty_e2e.py` | create | Full in-process ceasefire/access/treaty lifecycle and non-enforcement. |
| `tests/unit/test_diplomacy_treaty_physical_distinction.py` | create | Physically possible command admitted; impossible command rejected; treaty status irrelevant. |
| `index.md` | modify later | Fill the Task 23 verification receipt. |

## Task 21: Add the treaty boundary and determinism suite

### Intent

Make the non-goals executable. If any future change adds a treaty registry,
binding authority, world enforcement, a score, a truth field, a command path,
or a peer-ledger read, this suite must fail.

### Implementation Steps

1. Create `tests/architecture/test_treaty_boundaries.py` with these checks:
   - `diplomacy` remains the only owned flag; registry stays 14 contexts /
     12 flags / four owned / eight unowned; no `runner-config-v57`.
   - No `TreatyStore`, `TreatyAuthority`, `TreatyRegistry`,
     `TreatyExecutor`, `CeasefireState`, `WarState`, `ArmyActor`, `Polity`,
     `Border`, `Citizenship`, `RelationScore`, `DiplomacyScore`,
     `LegitimacyOracle`, or `TruthEngine` class exists in treaty modules.
   - No `binding`, `enforced`, `enforcement`, `legitimate`, `truth`,
     `misremembered`, `false_belief`, `winner`, `score`, `rank`, `trust`,
     `valence`, `composite`, or `overall_relation` field exists on any treaty
     cognition row, snapshot row, analysis row, or API schema.
   - No treaty module contains `AgentCommand`, calls `submit`, `admit`,
     `submit_command`, or `resolve_command`, or imports admission.
   - Snapshot treaty/version `status` and `acceptance_basis` are derived labels,
     not permissions; no API/UI path treats them as authority.
   - `world/`, `simulation/engine.py`, `simulation/perception.py`,
     `observer/`, and the Godot client never import a treaty module or read a
     diplomacy ledger.
   - `analysis/` does not import `experiments`, `persistence`, `api`, or
     `agents.cognition`; treaty analysis is detached.
   - No treaty module calls an `org-`/`msoc-` mint, rename, split, merge, or
     dissolve helper.
   - Peer frames never trust `provenance` or `mandate_ref`; only the
     delivery-assigned provenance and the owner representation ledger count.
   - `trt_v1` is bounded at 22 fields and 832 characters, travels as at most
     four ordered chunk relations, and every relation object stays within the
     world 256-character cap; `dip_v1` remains 15 fields / 320 characters.
   - Metric catalog is 168; the four treaty families are last; no score key.
   - Snapshot schema is v2 with v1 still supported; store schema is v1.
   - Exactly eight GET diplomacy routes exist; no `/v2` route and no
     `observer-protocol-v2`.
2. Extend `tests/architecture/test_diplomacy_boundaries.py` to include
   `agents/cognition/diplomacy*.py`, `analysis/diplomacy*.py`,
   `simulation/diplomacy*.py`, `experiments/diplomacy*.py`,
   `persistence/diplomacy*.py`, `research_runner/diplomacy*.py`, and
   `api/routes/diplomacy.py` in its scans.
3. Create `tests/unit/test_diplomacy_treaty_determinism.py`:
   - apply the same treaty frames twice and assert identical ledger/digest;
   - assert treaty/version/declaration/recollection/lineage IDs are
     content-addressed and stable;
   - assert row order is deterministic regardless of input frame order;
   - assert no `hash()`, `uuid`, `datetime.now`, or `time.time` appears in
     treaty modules;
   - assert two equal ledgers produce equal digests and a one-field change
     changes the digest.
4. Add the physical-distinction test:
   - a ceasefire or access treaty does not make a physically impossible
     command admissible;
   - a treaty rejection/termination does not block a physically possible
     command;
   - `WorldEngine` admission behaves exactly as if the treaty ledger were
     absent;
   - no witness, observer, or prompt receives treaty enforcement.

### Required Interfaces and Contracts

- The suite is executable with `pytest` and no external services.
- Every forbidden symbol/field is checked by exact name and by AST where a
  call path matters.
- Determinism checks run with an explicit seed and no wall clock.
- The physical-distinction test uses the existing engine/admission test
  helpers, not a fake admission shortcut.

### Requirement Evidence (when reconciliation applies)

- Original Request "WorldEngine does not magically enforce them".
- `.ai-factory/ARCHITECTURE.md` "Anti-Patterns" and Key Principles 1-5.
- V4-10 boundary suite 57-201 and physical-distinction precedent.

### Error Handling and Logging

- Test failures name the forbidden symbol/field/path.
- No application logging is added by tests.

### Tests

The two new test files plus the extended diplomacy boundary suite, as
specified above.

### Acceptance Criteria

- A treaty cannot acquire world authority, enforcement, a score, a truth
  field, a registry, or a command path without failing the suite.
- Determinism and physical non-interference are proven.
- Existing V4-10 boundary assertions remain green.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_treaty_boundaries.py tests/architecture/test_diplomacy_boundaries.py tests/unit/test_diplomacy_treaty_determinism.py tests/unit/test_diplomacy_treaty_physical_distinction.py -q`
- Expected: all tests pass.

## Task 22: Add the treaty end-to-end scenario

### Intent

Exercise the whole feature in-process with real engine ticks, real speech
delivery, real representation recognition, real publication, and real read
routes. The scenario must show multi-party treaty formation, renewal/lineage,
later-generation recollection, researcher-only misremember alignment, and
physical non-enforcement.

### Implementation Steps

1. Create `tests/unit/test_diplomacy_treaty_e2e.py` with a seeded,
   in-process scenario:
   - three agents A, B, C and one owner-visible settlement/region anchor
     (organization/coalition anchor resolution is covered by Task 8 unit
     tests);
   - a real durable-record anchor and a real owner-local
     `InstitutionalMemoryLedger` entry, not synthetic token strings;
   - a real `RepresentationLedger` for at least one recognized envoy;
   - a `runner-config-v56` config with `diplomacy=True` and no PostgreSQL.
2. Scenario sequence:
   1. A proposes a `ceasefire` treaty with participants A, B, C via a
      `trt_v1` `treaty_propose` frame inside existing `Talk`.
   2. B and C accept as principals; A accepts. Assert version 1 is
      `apparently_accepted` for all three owners and binds nobody.
   3. A physically possible attack/command is still admitted while the
      ceasefire is apparently accepted.
   4. A proposes a `renewal` version with a later end tick; B and C accept.
      Assert version 2 is accepted, version 1 is `superseded`, and one
      lineage edge exists.
   5. A later agent D reads the durable record/institutional memory and sends
      a `treaty_recollect` frame with the correct digest; D's ledger holds a
      recollection and no local treaty/version.
   6. D sends another recollection with a different claimed digest; analysis
      classifies it `inconsistent`; D's cognition still exposes only the
      recollection stance, never a truth verdict.
   7. A non-participant cannot create a local treaty or version.
   8. Publish the completed run through `build_completed_run_diplomacy_harvest`
      and `publish_diplomacy_snapshot`; assert v2 snapshot.
   9. Read all eight diplomacy routes through the real route handlers:
      summary, relations page, relation detail, instruments page, instrument
      detail, lineage page, treaties page, and treaty detail. Assert
      tokens/versions/lineage/recollections and cursor behavior.
   10. Assert the scientific result, stop reason, and metric status are
       unchanged by publication.
3. Use real `Talk`/`Tell` delivery and existing speech helpers. Do not bypass
   the communication relation or the frame parser.
4. Use the existing representation ledger to recognize at least one envoy
   with `negotiate` and `until_revoked`; assert its acceptance counts. Use a
   second envoy with `single_act` and assert its acceptance does not count.
5. Assert no `AgentCommand` is constructed by any treaty helper; the attack
   command is built by ordinary cognition/admission.

### Required Interfaces and Contracts

- Runs in `tests/unit` without PostgreSQL, Docker, or the network.
- Uses real ticks and real speech, not synthetic row injection only.
- Uses real recognition and real publication/routes.
- Asserts both acceptance and non-enforcement.
- Never reports the scenario as integration-only.

### Requirement Evidence (when reconciliation applies)

- Original Request examples and "WorldEngine does not magically enforce them".
- Original Request "Later generations may remember them, misremember them,
  reinterpret them, ignore them, renew them".
- `.ai-factory/ARCHITECTURE.md` V3/V4 seams and in-process E2E precedent.

### Error Handling and Logging

- Failing assertions identify the stage (propose, accept, renew, recollect,
  publish, read, physical).
- No production code is changed for the test beyond Task 1-20 contracts.

### Tests

The scenario above is the test; include at least:

- `test_three_party_ceasefire_is_believed_but_not_enforced`
- `test_renewal_creates_version_two_and_linear_lineage`
- `test_later_generation_recalls_without_creating_a_local_treaty`
- `test_researcher_alignment_distinguishes_consistent_and_inconsistent_recall`
- `test_non_participant_cannot_create_a_treaty`
- `test_single_act_envoy_never_completes_a_party`
- `test_real_durable_record_and_institutional_memory_anchors_round_trip`
- `test_publication_and_all_eight_routes_expose_v2_without_changing_science`

### Acceptance Criteria

- The full lifecycle runs in-process without PostgreSQL.
- Multi-party acceptance, renewal, lineage, later-generation recollection, and
  misremember alignment are proven.
- Ceasefire/access beliefs never block or grant a command.
- Publication and routes expose v2 without changing the scientific result.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_e2e.py -q`
- Expected: all tests pass and no PostgreSQL marker is required.

## Task 23: Execute the full V1-V4 regression and qualification lanes

### Intent

Run every required lane after the invariant and E2E gates, record exact
evidence, and fill the verification receipt. An unexecuted lane keeps its
missing prerequisite and blocks certification; it is never a skip-pass.

### Implementation Steps

1. Run the full Python unit + architecture lane with coverage:
   `uv run --frozen --python 3.12.14 pytest tests/unit tests/architecture -q --cov --cov-report=term`.
2. Run the focused V4-11 suite:
   `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_*.py tests/architecture/test_treaty_boundaries.py -q`.
3. Run the focused in-process E2E:
   `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_e2e.py -q`.
4. Run V1/V2/V3/V4 regression selections:
   `tests/unit/test_v1_regression_gate.py`,
   `tests/unit/test_v2_scientific_invariants.py`,
   `tests/architecture/test_v4_architecture_invariants.py`,
   `tests/architecture/test_v4_context_registry.py`, and the existing
   organization/formal-rule/dispute/evidence/representation/diplomacy suites.
5. Run static gates after all implementation and test changes:
   `uv run ruff check src tests`, `uv run mypy src tests`,
   `uv run lint-imports`, and `uv run pytest tests/unit/test_packaging.py -q`.
   Before running mypy, narrow every `tuple[object, ...]` paging/runner-result
   field and every `getattr` value with `typing.cast` or `isinstance` at the
   first read. Re-run mypy after the final documentation/test commit; do not
   copy an earlier receipt.
6. Run `docker compose config --quiet`.
7. Run integration lanes only when a disposable PostgreSQL/pgvector instance
   is available:
   `uv run pytest -m "integration and not scale"` and the integration/scale
   lane. Otherwise record `unexecuted` with the missing prerequisite.
8. Run Compose/browser acceptance when Docker, the pinned API image,
   Playwright, and the acceptance harness are available. Otherwise record
   `unexecuted`.
9. Run the pinned Godot 4.7.2 suite when `GODOT_BIN` is available:
   `"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd`.
   Otherwise record `unexecuted`.
10. Run the benchmark/scale lane when the multi-hour harness is available.
    Otherwise record `unexecuted`.
11. Run Research UI tests/type/build when `pnpm` is available:
    `cd clients/research-ui && pnpm test && pnpm check && pnpm build`.
    Otherwise record `unexecuted`.
12. Fill the `## Verification Receipt` table in `index.md` with exactly one of
    `executed_passed`, `executed_failed`, or `unexecuted`, plus exact evidence
    or the missing prerequisite. Do not mark a lane passed from a skip.
13. Record the certification outcome. Any `unexecuted` required lane means
    `not certified`.
14. Do not edit `.ai-factory/ROADMAP.md`; `$aif-roadmap` owns it.

### Required Interfaces and Contracts

- Every lane is recorded exactly once.
- Python coverage remains enabled for unit/architecture.
- No lane is silently omitted.
- A missing prerequisite is named, not generalized.
- The receipt is the durable evidence for Task 24/25.
- `mypy src tests` passes on the final tree; tests narrow `object` payloads
  with `cast`/`isinstance` rather than reading fields directly.

### Requirement Evidence (when reconciliation applies)

- Plan Settings "Testing: yes; full strategy".
- `docs/development.md` command table.
- `tests/compose/acceptance.py` and the project's unexecuted-lane policy.

### Error Handling and Logging

- Test/lint output is summarized; failures keep the exact failing command and
  a bounded excerpt.
- Never log DSNs, credentials, or environment secrets.

### Tests

This task executes tests; it creates no new tests except the receipt.

### Acceptance Criteria

- All available lanes execute and pass.
- Every unavailable lane is `unexecuted` with its prerequisite.
- The receipt matches the actual commands and outcomes.
- Certification is withheld if any required lane is unexecuted.

### Verification

- The receipt itself plus `git status` showing no roadmap edit.
- Expected: Python/static/docs/Compose-config lanes pass; unavailable lanes
  are truthful and block certification.

## Phase Risks and Mitigations

- Risk: The boundary suite is too name-based and misses a new enforcement
  path.
  Mitigation: combine exact-name checks, field scans, import scans, AST call
  checks, and the physical-distinction/E2E tests.
- Risk: The E2E accidentally requires PostgreSQL or Docker.
  Mitigation: keep it in `tests/unit`, use in-process engine helpers, and run
  it explicitly in the focused lane.
- Risk: A regression lane is marked passed from a skip.
  Mitigation: the receipt distinguishes `unexecuted` and names the
  prerequisite; Task 25 audits it.
- Risk: The UI/Godot lanes are unavailable and the plan claims certification.
  Mitigation: certification is explicitly withheld until they execute.

## Phase Completion Checklist

- Every Task 21-23 acceptance criterion is met.
- Treaty boundaries, determinism, and physical non-interference are proven.
- The in-process E2E covers multi-party acceptance, renewal, lineage,
  recollection, publication, and routes.
- The receipt is complete and truthful.
- `index.md` checkboxes are updated only after verification passes.
