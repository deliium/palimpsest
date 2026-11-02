# Phase 7: Invariants, End-to-End Evidence, and Regression

Plan: [index.md](index.md)
Tasks: 19-21
Depends on: Phase 6 / Tasks 17-18

## Objective

Prove the V4-05 authority boundary, determinism, owner isolation, and
end-to-end behavior with real commands and real surfaces, then execute the full
V1-V4 regression and qualification lanes. A missing prerequisite is recorded as
`unexecuted`, never as a skip-pass.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `tests/architecture/test_organization_operations_boundaries.py` | exact pins 246-251, 264, 289-309 | Boundary test pattern to mirror |
| `tests/architecture/test_organization_boundaries.py` | pins 232-284; registry 251-271 | Existing pins that must stay green |
| `tests/unit/test_organization_operations_end_to_end.py` | E2E scenario and synthetic-kind caveat 155-167 | Must be improved for V4-05 with real kinds |
| `tests/unit/test_organization_operations_determinism.py` | Determinism pattern | Repeat/shuffle/digest tests |
| `tests/unit/test_organization_operations_isolation.py` | Owner-only isolation pattern | Extend for agency |
| `tests/unit/test_organization_operations_regression.py` | Unit+architecture regression pins 51-103 | Update to six routes/148 families/v3 |
| `tests/unit/test_v1_regression_gate.py`, `tests/unit/test_v2_scientific_invariants.py` | V1/V2 gates | Must stay green |
| `tests/architecture/test_v4_architecture_invariants.py` | 14 contexts/12 flags/pins 120-184 | Must stay green |
| `docs/development.md` | test commands 30-59 | Exact lane commands |
| `tests/compose/acceptance.py` | Compose/browser receipt | Three-state lane behavior |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `tests/architecture/test_organization_agency_boundaries.py` | create | Authority, magic-actor, isolation, and pin tests |
| `tests/unit/test_organization_agency_isolation.py` | create | Owner-only input tests |
| `tests/unit/test_organization_agency_determinism.py` | create | Repeat/shuffle/digest tests |
| `tests/unit/test_organization_agency_end_to_end.py` | create | Real-command E2E |
| `tests/unit/organization_agency_e2e_helpers.py` | create | Bounded real-world fixtures |
| `tests/unit/test_organization_agency_regression.py` | create | Cross-surface pin tests |
| `tests/unit/test_organization_operations_regression.py` | modify | Six routes, 148 families, v3 |
| `tests/unit/test_organization_operations_catalog.py` | modify | 146 → 148 |
| `tests/unit/test_organization_catalog.py` | modify | 146 → 148 |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | Metric pin 146 → 148 only |
| `tests/architecture/test_v3_baseline_inventory.py` | modify | Metric pin 146 → 148 only |
| `tests/unit/test_organization_ports.py` | modify | Six cursor purposes |
| `tests/unit/test_organization_api.py` | modify | Six routes and additive summary |
| `tests/unit/test_organization_operations_docs.py` | modify | v3/six routes/148 families |

## Task 19: Add the collective-agency boundary and determinism suite

### Intent

Make every V4-05 authority claim machine-checked: no super-agent, no objective
organization, no command source, no global OrganizationLLM, no peer read, no
identity creation, no pin weakening.

### Implementation Steps

1. Create `tests/architecture/test_organization_agency_boundaries.py`:
   - **No objective actor/registry:** scan `src/` AST for classes/fields named
     `OrganizationActor`, `OrganizationLLM`, `OrganizationAgent`,
     `Government`, `State`, `Nation`, `Treasury`, `Roster`, `GlobalRegistry`,
     `OrganizationRegistry`, and any `WorldEngine` organization entity. Allow the
     existing belief types only.
   - **No command source:** scan `src/agents/cognition/organization_agency*.py`
     for `AgentCommand(`, `ActionSubmission(`, `resolve_tick(`, `submit(`, and
     imports of `world.actions` command classes except `Talk`/`Tell` type
     checks. Assert no agency helper returns an `AgentCommand` annotation.
   - **No global OrganizationLLM:** scan agency modules for `llm`, `LLMProvider`,
     `LLMRequest`, `prompt`, `generate_text`, `OpenAI`, and shared prompt
     constants. Assert none.
   - **Owner-only inputs:** scan `apply_organization_agency_update` and its
     helpers for `WorldState`, `WorldEvent`, event-store, command, peer-ledger,
     analysis, persistence, API, and observer imports. Assert none.
   - **No objective ownership:** compare world model dataclass field names
     against a frozen V4-04 baseline and assert no new `owner_id`, `ownership`,
     `organization_id`, or `collective_agency` field. Do not fail on a
     pre-existing field; fail on a regression.
   - **No new command/event/observer semantic:** assert
     `len(COMMAND_RULE_MATRIX) == 43`, `EVENT_SCHEMA_REPLAY_V22 == 22`,
     `len(SEMANTIC_EVENT_TYPES) == 73`, no `runner-config-v57`, codec `v20`
     accepted / `v21` rejected, Alembic `0017`, no `0018_*.py`.
   - **Registry unchanged:** 14 contexts, 12 flags, `v4-context-map-v2`,
     `organizations` owner-scoped, analysis-only set unchanged, four write-pair
     reservations unchanged.
   - **V3-31/V4-03/V4-04 unchanged:** assert existing policy versions, id
     prefixes, enum members, and snapshot v1/v2 fixtures are unchanged.
   - **Preparation:** `prepare_parallel is False`.
   - **Observer:** `organization_rows` remains reserved and unadvertised.
   - **Metric assembly:** `analysis.metric_service` and
     `experiments.collectors` consume harvested agency rows through
     `MetricComputationInputs.organization_agency_rows`; neither imports
     `agents.cognition`, and neither passes agency data into command selection
     or world state.
   - **Metrics:** `METRIC_FAMILY_COUNT == 148`; the last two families are the new
     ones; the first 146 ids/order are unchanged.
   - **Routes:** exactly six GET organization routes; no POST/PUT/PATCH/DELETE.
   - **Snapshots:** `SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS == (v1, v2, v3)`.
2. Create `tests/unit/test_organization_agency_isolation.py`:
   - An owner update ignores another owner's communications and ledger.
   - A peer ledger or checkpoint is rejected with
     `organization_agency_foreign_ledger`.
   - The update reads no global event store; pass a fake that raises on
     attribute access and assert it is never touched.
   - `WorldState`, `WorldEngine`, `AgentCommand`, and an event repository are
     rejected.
   - A peer's `orgc-` concept id cannot be used to update the owner's ledger.
   - Analysis harvesting accepts rows, not live ledgers, and never imports
     cognition.
3. Create `tests/unit/test_organization_agency_determinism.py`:
   - Repeated updates with the same observation produce byte-identical ledgers.
   - Shuffled communications/occurrences produce the same sorted ledger.
   - IDs are stable across process runs and independent of `PYTHONHASHSEED`.
   - No `hash()`, `uuid`, `datetime.now`, `time.time`, or global RNG in agency
     modules.
   - Canonical JSON digest is stable for the same ledger and changes when a
     decision or implementation changes.
   - `OrganizationAnalysis.determinism_digest` is stable across repeated
     summaries and changes with agency content.
4. Create `tests/unit/test_organization_agency_regression.py`:
   - Unit+architecture pin summary: 148 families, six routes, v3 snapshot,
     six cursor purposes, 43 commands, 22 events, 73 semantics, Alembic `0017`,
     no v57.
   - Existing V4-03/V4-04 regression tests remain green without edits except
     the intentional pins.
   - A default flags-off run has no agency ledger, no agency metric documents,
     no publication, and no route data.
   - `organizations` on v56 with no evidence has empty ledgers and `ABSENT`
     agency metrics.

### Required Interfaces and Contracts

- Every scan is AST-based or import-based, not a text grep that can be fooled by
  comments.
- The suite must fail on a real violation, not merely skip when a file is
  missing.
- Pins are exact; no `>=`, `in`, or tolerance weakening.
- V3-31 remains unchanged; V4-05 composes with it only as read-only evidence.

### Requirement Evidence

- Original Request: no super-agent, no global OrganizationLLM, agent cognition
  as the source of actions.
- `.ai-factory/ARCHITECTURE.md` "Key Principles", "Capability ownership",
  "Requirements for later changes" 1-7.
- `.ai-factory/RULES.md` axioms 1-10.
- V4-01/V4-03/V4-04 invariant suites.

### Error Handling and Logging

- Test failures report the exact path/symbol and the violated rule; no runtime
  logging is added.
- The boundary suite must not read `.venv`, `node_modules`, caches, or generated
  output.

### Tests

Run:
`uv run --frozen --python 3.12.14 pytest tests/architecture/test_organization_agency_boundaries.py tests/unit/test_organization_agency_isolation.py tests/unit/test_organization_agency_determinism.py tests/unit/test_organization_agency_regression.py -q`

### Acceptance Criteria

- Every authority claim is independently checkable.
- No super-agent, global OrganizationLLM, command source, peer read, objective
  ownership, or identity mutation exists.
- All pins are exact and green.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_organization_agency_boundaries.py tests/unit/test_organization_agency_isolation.py tests/unit/test_organization_agency_determinism.py -q`
- Expected: all tests pass.

## Task 20: Add the collective-agency end-to-end scenario

### Intent

Exercise the full pipeline with a real `WorldEngine`, real commands, real
observation kinds, real publication, and the API: proposal → discussion →
support/opposition/abstention → amendment → recognized procedure → collective
decision → individual implementation/compliance/refusal/sabotage →
unimplemented decision.

### Implementation Steps

1. Create `tests/unit/organization_agency_e2e_helpers.py`:
   - Build a small world with four agents, a shared item, a repository, a
     collective project, a commitment, and a recognized procedure belief.
   - Use `urandom`-free deterministic seeds.
   - Provide a helper to run ticks and collect owner observations.
   - Provide a helper to construct `org_ca_v1` claims through existing
     `Talk`/`Tell` commands.
2. Create `tests/unit/test_organization_agency_end_to_end.py`:
   - Enable `organizations` on `runner-config-v56` with the required V3 evidence.
   - Tick 1: the owner generates a proposal to `give` a specific item to a
     member using a recognized procedure.
   - Tick 2: peers deliver `support`, `oppose`, `abstain`, and `amend` claims
     through `Talk`/`Tell`; the owner records positions and the amendment.
   - Tick 3: the owner recognizes the amended proposal; a decision `orgcd-` is
     recorded with support/oppose/abstain counts and `recognition=contested` or
     `recognized` as the evidence dictates.
   - Implementation window:
     - actor A submits a real `Give` for the target item → `implemented`;
     - actor B submits a `Talk`/`Tell` refusal → `refused`;
     - actor C opposes then submits a real `Attack`/`Erase` against the target →
       `sabotaged` (owner attribution);
     - actor D is observed idle → `unimplemented`;
     - a second decision with no observed actor → `unknown` (censored).
   - Assert:
     - the decision-level status aggregates correctly;
     - `compliance_count`, `refusal_count`, `sabotage_count`,
       `contrary_count`, `censored_actor_count` match;
     - objective possession (`holder_id`, `location_id`,
       `custodian_repository_id`, `stored_quantity`) is unchanged except for the
       real `Give`/`Attack` effects;
     - no organization object constructed or submitted a command;
     - the command count remains 43 and no new event kind appears;
     - the decision that no one implements stays `unimplemented`, not
       `satisfied`;
     - the decision with no visibility stays `unknown`.
3. Metric assembly:
   - Run the completed arm through `experiments.collectors` so
     `MetricComputationInputs.organization_agency_rows` is populated from
     `runner_result.organization_agency_ledgers`.
   - Call `analysis.metric_service.assemble_metric_documents` and assert both
     `organization_collective_agency` and
     `organization_collective_implementation` documents are present with the
     scenario's counts.
   - Assert the agency rows never feed cognition or command selection.
4. Publication:
   - Build the completed-run harvest and publish a v3 snapshot through the
     filesystem store.
   - Read summary, candidate detail, and the collective-agency route.
   - Assert no owner-local/raw actor ids; counts match.
   - Force a publication failure (quota or duplicate) and assert the scientific
     result and metric documents are unchanged.
5. API/UI:
   - The API test reads the sixth route and validates the response.
   - The UI test (Task 18) renders the same fixture.
6. Add a negative test: a proposal with an out-of-order amendment or an
   unrecognized procedure is still recorded, but not `recognized`; the
   organization still operates.

### Required Interfaces and Contracts

- Use only real observation kinds (`give`, `item_stored`, `artifact_created`,
  `attack`, `artifact_destroyed`, etc.); never `given`/`taken`/`dropped`.
- A real `Give` exposes `public_facts["give_item_ids"]` and `success=None`; the
  E2E must prove the matcher uses the tuple, not a synthetic `item_id` field.
- Every physical effect is an ordinary `AgentCommand` submitted by an agent.
- The organization does not teleport, grant permission, or execute.
- Refusal/sabotage require explicit evidence; silence is `unimplemented` or
  `unknown` per the observation rule.
- Publication failure is non-interfering.

### Requirement Evidence

- Original Request: "Collective decisions may fail because members do not act";
  "Track whether organization-level actions were actually implemented"; "Do not
  add a global OrganizationLLM."
- `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime".
- V4-04 E2E pattern, with the synthetic-kind bug corrected.

### Error Handling and Logging

- The scenario asserts no ERROR logs for expected censoring/truncation.
- WARN is allowed for `unimplemented`/`unknown` only if the plan's logging policy
  requires it; prefer INFO/DEBUG counts.
- No actor sets, labels, or utterance bodies in logs.

### Tests

Run:
`uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_end_to_end.py tests/unit/test_organization_agency_publication.py tests/unit/test_organization_agency_api.py tests/unit/test_metric_service.py tests/unit/test_experiment_collectors.py -q`

### Acceptance Criteria

- The full pipeline works with real commands and real observation kinds.
- Collective failure, compliance, refusal, and sabotage are distinguishable.
- Publication and API reads are truthful and owner-safe.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_end_to_end.py -q`
- Expected: all tests pass; no synthetic event kinds appear in the test or
  production mapping.

## Task 21: Execute the full V1-V4 regression and qualification lanes

### Intent

Run every required lane and record a truthful three-state receipt. A missing
prerequisite leaves the lane `unexecuted` with the prerequisite; it never
becomes a pass.

### Implementation Steps

1. Run and record each lane with coverage enabled on Python lanes:
   - `uv run --frozen --python 3.12.14 pytest tests/unit tests/architecture --cov=src --cov-report=term`
   - Focused V4-05 lane:
     `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_*.py tests/unit/test_organization_agency_config.py tests/unit/test_organization_agency_end_to_end.py tests/unit/test_metric_service.py tests/unit/test_experiment_collectors.py tests/unit/test_organization_cli.py tests/architecture/test_organization_agency_boundaries.py -q`
   - `uv run --frozen --python 3.12.14 ruff check src tests`
   - `uv run --frozen --python 3.12.14 mypy src tests`
   - `uv run --frozen --python 3.12.14 lint-imports`
   - Integration, non-scale, with a disposable `palimpsest_test` pgvector:
     `PALIMPSEST_TEST_DATABASE_URL=... uv run --frozen --python 3.12.14 pytest -m "integration and not scale" -q`
   - Integration selection including scale tests:
     `PALIMPSEST_TEST_DATABASE_URL=... uv run --frozen --python 3.12.14 pytest -m integration -q`
     (record the exact selection).
   - `docker compose config --quiet`
   - Compose/browser acceptance:
     `PALIMPSEST_API_IMAGE=... uv run --frozen --python 3.12.14 pytest -m compose -q`
     (or `tests/compose/acceptance.py` as documented).
   - Godot 4.7.2:
     `"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd`
   - Benchmark/scale:
     `PALIMPSEST_TEST_DATABASE_URL=... uv run --frozen --python 3.12.14 pytest -m "integration and scale" tests/benchmarks/ -q`
   - Research UI:
     `cd clients/research-ui && pnpm test -- --run`
     `cd clients/research-ui && pnpm check`
     `cd clients/research-ui && pnpm build`
2. Record for each lane: `executed_passed`, `executed_failed`, or `unexecuted`
   with the missing prerequisite. Include command, duration, counts, and
   coverage where applicable.
3. If a lane fails:
   - fix a V4-05 regression and rerun;
   - if the failure is pre-existing and outside the V4-05 diff, record it
     explicitly with the failing test and do not claim a green lane.
4. Verify pins directly:
   - 148 metric families with the two new families last;
   - 14 contexts / 12 flags / `v4-context-map-v2`;
   - events 22; codec `v20` accepted and `v21` not;
   - 43 commands; 73 observer semantic types;
   - Alembic `0017` and no `0018_*.py`;
   - no `runner-config-v57`;
   - six GET organization routes;
   - snapshot v1/v2/v3;
   - six cursor purposes;
   - roadmap untouched.
5. Write the receipt into `index.md` under `## Verification Receipt`.

### Required Interfaces and Contracts

- Python lanes use coverage.
- Compose/browser, Godot, benchmark, and integration lanes are required for full
  certification; a missing prerequisite is `unexecuted`, not `skipped`.
- The receipt records exact counts, not estimates.
- No test skip is silently converted to a pass.

### Requirement Evidence

- Plan Settings "Testing: yes; full strategy".
- `docs/development.md` commands.
- V4-04 verification receipt format.

### Error Handling and Logging

- Capture redacted logs on failure; never include credentials, DSNs, prompts,
  memories, embeddings, or actor sets.
- Record safe reason codes for unexecuted lanes.

### Tests

This task executes the suites above; it does not add a new test file.

### Acceptance Criteria

- Every required lane is executed or truthfully recorded `unexecuted`.
- All executed lanes pass except explicitly documented pre-existing failures.
- Pins are verified directly.

### Verification

- The receipt table in `index.md` is complete and matches the commands run.
- A lane with a missing prerequisite has a named prerequisite.

## Phase Risks and Mitigations

- Risk: the full suite is long and times out.
  Mitigation: run unit+architecture with coverage once, then focused suites; keep
  output bounded and summarize counts.
- Risk: integration/Compose/Godot prerequisites are absent.
  Mitigation: record `unexecuted` with the prerequisite; do not certify those
  lanes.
- Risk: a boundary scan misses a dynamic import.
  Mitigation: combine AST scans with import-linter and runtime import tests.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
