# Phase 6: Invariants, Documentation, and Certification

Plan: [index.md](index.md)
Tasks: 18-21
Depends on: Phase 5 (Tasks 15-17)

## Objective

Sweep the science ownership and 244 -> 250 catalog pins through code, tests, and
documentation; add the `docs/scientific-hypotheses.md` page and cross-links; add
positive and negative documentation parity checks; and certify every required
verification lane with an explicit result or an `unexecuted` prerequisite.
Roadmap registration stays owned by `$aif-roadmap`.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `tests/architecture/test_v4_architecture_invariants.py` | owned/unowned pins (174-301), command/semantic/replay pins (137-172) | Primary V4 pin sweep |
| `tests/architecture/test_v4_context_registry.py` | context count, analysis-only set, H3 count (103-205) | Context and docs-heading pins |
| `tests/architecture/test_v3_baseline_inventory.py` | `metric_family_count` 244 (63, 97) | Baseline inventory pin |
| `tests/unit/test_metric_specifications.py` | family count and uniqueness (42-46) | Catalog pin |
| `tests/unit/test_economic_cascades_catalog.py` | first-244 digest (17-30, 50-52) | Append proof |
| `tests/unit/test_accounting_ledgers_pins.py`, `test_supply_chain_pins.py`, `test_credit_relationships_pins.py` | feature pin templates (84-116, 27-68, 36-73) | New pin file template |
| `.ai-factory/ARCHITECTURE.md` | baseline table (177-193), ownership (195-213), seam sections (1225-1275) | Canonical architecture pins |
| `.ai-factory/DESCRIPTION.md` | latest V4 paragraph (758-780) | Implemented-state description |
| `docs/v4-architecture.md` | context table (52-79), version surfaces (317-364), science row (68-79, 174-179) | Science row must stop saying "deferred" |
| `docs/configuration.md` | v56/ownership (307-314) | Configuration pins |
| `docs/analysis-metrics.md` | catalog pin and footer (41, 774-800) | Metrics docs |
| `docs/research-api.md` | route footer (474-492) | API docs |
| `docs/research-ui.md` | panel footer (360-368) | UI docs |
| `docs/v4-versioning.md` | surfaces (10-26), keyset (46-63) | Versioning docs |
| `README.md` | V4 index (71-74), feature index (100-118) | Landing-page links |
| `tests/unit/test_economic_cascades_docs.py` | live pin and cross-link pattern (72-134) | New docs test template |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/simulation/runner_models.py` | modify | Final ownership comment/docstring sweep |
| `src/simulation/compatibility.py` | modify | Final matrix text sweep; no version change |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | Owned 9 / unowned 3; science flag owned; catalog 250 |
| `tests/architecture/test_v4_context_registry.py` | modify | Context count stays 17; science row ownership; no new context |
| `tests/architecture/test_v3_baseline_inventory.py` | modify | `metric_family_count` 250 |
| `tests/unit/test_metric_specifications.py` | modify | 250 count and uniqueness |
| `tests/unit/test_v4_scaffolding_gate.py` | modify | Science owned; three unowned |
| `tests/unit/test_runner_config_v56.py` | modify | Science owned; three unowned |
| `tests/unit/test_accounting_ledgers_pins.py`, `tests/unit/test_supply_chain_pins.py`, `tests/unit/test_credit_relationships_pins.py` | modify | 250 / 9 / 3 pin sweep |
| `tests/unit/test_scientific_hypotheses_pins.py` | create | Feature pins |
| `tests/unit/test_scientific_hypotheses_docs.py` | create | Positive and negative docs parity |
| `docs/scientific-hypotheses.md` | create | Feature page |
| `README.md` | modify | Index and cross-links |
| `.ai-factory/ARCHITECTURE.md` | modify | Baseline, ownership, V4-27 seam |
| `.ai-factory/DESCRIPTION.md` | modify | V4-27 implemented-state paragraph |
| `docs/architecture.md` | modify | Current-state paragraph and pins |
| `docs/configuration.md` | modify | Science ownership and prerequisites |
| `docs/analysis-metrics.md` | modify | Six new families and 250 footer |
| `docs/research-api.md` | modify | Seven routes and 250 footer |
| `docs/v4-architecture.md` | modify | Science row and V4-27 paragraph; keep 17 context H3 headings |
| `docs/research-ui.md` | modify | Read-only panel |
| `docs/v4-versioning.md` | modify | Owned 9 / unowned 3; no v57 |
| `docs/development.md` | modify | Catalog 250 and 17 contexts / `v4-context-map-v5` |
| `docs/cognition-runtime.md` | modify | Intentional test path and hypothesis ledger |
| `docs/experiments.md` | modify | Off-gate `scientific_hypotheses@1` |
| `AGENTS.md` | modify | Add the feature page to the documentation table |

## Task 18: Sweep science ownership, catalog, and documentation pins

### Intent
Make every active pin agree with the implemented state: 17 contexts, 12 flags,
9 owned, 3 unowned, `v4-context-map-v5`, 250 metric families, 43 commands, 73
observer semantic types, replay-v27/codec `v25`, Alembic `0017`, `/v1`, and
`observer-protocol-v1`. No context, schema, version, or write pair is added.

### Implementation Steps
1. In `tests/architecture/test_v4_architecture_invariants.py`:
   - Assert `len(V4_CONTEXTS) == 17`, `len(V4_CAPABILITY_FLAGS) == 12`.
   - Assert `V4_OWNED_CAPABILITY_FLAGS == {organizations, formal_rules,
     legal_disputes, diplomacy, organized_conflict, infrastructure_networks,
     supply_chains, markets_credit, science}`.
   - Assert the unowned set is exactly
     `{epidemics, ecological_feedback, disasters}`.
   - Assert `METRIC_FAMILY_COUNT == 250`, commands 43, observer semantic types
     73, replay 27, codec `v25`, Alembic `0017`, `/v1`,
     `observer-protocol-v1`, `v4-context-map-v5`.
   - Keep the 4 reserved write-pair assertions and the 13 reuse-only contexts
     assertion; `science` is already in the reuse set.
   - Keep the `"runner-config-v57"` absence assertion and the
     `alembic/versions/0018*` absence assertion.
2. In `tests/architecture/test_v4_context_registry.py`:
   - Keep `DECLARED_ORDER` at 17 entries; science is unchanged in position and
     remains `OWNER_SCOPED`, seam `v4_capability_flags.science`, reuse-only,
     prerequisite `formal_rules`.
   - Assert the science spec's capability flag is now owned.
   - Do not add a new context heading; the H3 count stays 17.
3. Update `tests/architecture/test_v3_baseline_inventory.py:63,97` and
   `tests/unit/test_metric_specifications.py:42-46` to 250.
4. Sweep every remaining `244` catalog assertion and docs pin to `250`. Use
   `rg -n "244" tests docs .ai-factory` and change only active pins; leave
   historical landing notes that explicitly describe V4-24/V4-25/V4-26
   landings, and leave the V4-26 first-244 digest guard itself unchanged.
   Also sweep current-state family counts `136/140/...` where a document claims
   them as current, not as a dated landing.
5. Update every `8 owned / 4 unowned`, `eight owned`, `four unowned`, and
   `science remains unowned` current-state statement to `9 owned / 3 unowned`
   and list `epidemics`, `ecological_feedback`, and `disasters` as unowned.
   Do not rewrite historical landing paragraphs that record an earlier count.
   In the same pass, normalize current-state context counts (`14`, `15`, `16`)
   to `17` and current version surfaces (`replay-v22`, `replay-v23`, codec
   `v20`/`v21`, family counts `136`/`140`) to the live pins in
   `docs/development.md`, `docs/v4-versioning.md`, `docs/architecture.md`,
   `docs/configuration.md`, and `docs/v4-architecture.md`. Preserve every dated
   landing narrative that explicitly says it records an earlier state.
6. Create `tests/unit/test_scientific_hypotheses_pins.py` asserting:
   - science is owned; unowned is exactly three flags;
   - contexts 17, flags 12, map `v4-context-map-v5`;
   - `METRIC_FAMILY_COUNT == 250`; the six new ids are last and ordered;
   - commands 43, observer 73, replay 27, codec `v25`, Alembic `0017`, `/v1`,
     `observer-protocol-v1`;
   - no `runner-config-v57`, no `0018`, no `/v2`;
   - `science` has no reserved/deepening write pair and no migration stage.
7. Keep `science=False` legacy configs byte-identical; add one digest parity
   assertion to the new pin file.

### Required Interfaces and Contracts
- Pins are current-state assertions, not historical notes.
- `science` ownership changes no context count, map revision, runner schema,
  command, event, observer semantic type, write pair, or migration.
- The first 244 metric families keep their ids, order, versions, and value keys.
- No active pin still says science is unowned.

### Requirement Evidence
- `.ai-factory/ARCHITECTURE.md:177-213` and `:1225-1275`.
- `src/simulation/runner_models.py:307-339,8232-8244`.
- `src/analysis/specifications.py:53`.
- Original Request "Do not expose objective rules" (pins must not imply a
  truth or rule surface).

### Error Handling and Logging
- WARN `scientific_hypotheses_pin_mismatch` with the pin name only.
- No new production log is required; this task changes tests and documents.
- Never log configuration values, claims, or owner ids.

### Tests
- `uv run pytest tests/architecture/test_v4_architecture_invariants.py tests/architecture/test_v4_context_registry.py tests/architecture/test_v3_baseline_inventory.py tests/unit/test_metric_specifications.py tests/unit/test_v4_scaffolding_gate.py tests/unit/test_runner_config_v56.py tests/unit/test_scientific_hypotheses_pins.py -q`
- Expected result: pass after the sweep.

### Acceptance Criteria
- Every active pin reports 17/12/9/3, 250 families, and unchanged wire pins.
- Science is owned and the three remaining flags are unowned.
- No historical landing note is silently rewritten as a current pin.

### Verification
- `rg -n "244 metric|244 families|METRIC_FAMILY_COUNT = 244|eight owned|8 owned|four unowned|4 unowned|science remains unowned|14 contexts|15 contexts|16 contexts|replay-v22|replay-v23|codec v20|codec v21" tests docs .ai-factory`
- Expected result: only historical landing notes remain, each marked as such.
- The pytest command above passes.

## Task 19: Documentation via `$aif-docs`

### Intent
Document the feature as an owner-scoped, testable-hypothesis seam that never
exposes objective rules, and update every current-state pin and cross-link. This
is the mandatory `$aif-docs` checkpoint.

### Implementation Steps
1. Run the `$aif-docs` workflow with the feature scope
   `v4-27-scientific-hypotheses`. Record the checkpoint in the plan and keep all
   generated prose in English with technical terms preserved.
2. Create `docs/scientific-hypotheses.md` with these sections:
   - Purpose and scope: extending the owned `predictive_world_model` and bounded
     experimentation seams into explicit testable hypotheses. A test may carry a
     `causal_hypothesis_id` link, but the link is lineage, not proof; the
     experiment's own predicted outcome is what the trial scores against.
   - Activation: v56 + `science` + `predictive_world_model` +
     `bounded_experimentation` (including that spec's existing cultural
     history/provenance prerequisites); `science=False` is inert.
   - Owner ledger fields: claim, conditions, predicted result, confidence
     milli, supporting observations, contradictions, creator/source, formulation
     tick, append-only historical revisions with revision ticks, and status.
   - Conditions: the ten closed observation slots and the rule that no
     objective law, rule row, probability, delta, product, or harm band is a
     condition.
   - Predicted result and strict matching: `ExperimentOutcomeClass` equality;
     `unexpected` is always a contradiction.
   - Confidence: integer support ratio, not a probability or calibrated score.
   - Status: `provisional`, `supported`, `contradicted`, `inconclusive`,
     `superseded`, `retired`; hypotheses can be wrong and contradictions are
     retained.
   - Intentional tests: `Wait` -> one `Experiment` when conditions hold and the
     trial budget allows; no meaningful command is overridden.
   - Communication: `hyp_v1` inside `Talk`/`Tell`; adoption is provisional,
     evidence-free testimony.
   - Revisions: bounded append-only history and revision reasons.
   - Analysis: six families, 32-tick windows, 512-window cap, `min_samples=3`,
     descriptive counts/shares only.
   - Artifact: `scientific-hypotheses-snapshot-v1`,
     `scientific-hypotheses-store-v1`, seven GET routes, dual settings, errors.
   - Limits and non-goals: no objective truth registry, no global encyclopedia,
     no scripted discovery, no technology tree, no new command/event/write pair,
     no runner v57, no migration, no Godot overlay.
   - Experiment: `scientific_hypotheses@1`, three arms, off the V1 gate.
   - Pins: 17 contexts / 12 flags / 9 owned / 3 unowned; 250 families; 43
     commands; 73 observer semantics; replay-v27/codec `v25`; Alembic `0017`;
     `/v1`; `observer-protocol-v1`.
3. Update `README.md`: add the page to the V4/feature index and link it from the
   current feature list.
4. Update `.ai-factory/ARCHITECTURE.md`: baseline table to 250 families and nine
   owned flags; ownership list; add a `### V4-27 science-hypotheses seam`
   subsection beside the V4-24/V4-25/V4-26 seams describing the flag, ledger,
   test path, layers, artifact, routes, and unchanged pins.
5. Update `.ai-factory/DESCRIPTION.md`: add the V4-27 paragraph with the owned
   flag, activation, fields, six families, snapshot/store, seven routes,
   Research UI panel, off-gate experiment, and unchanged pins.
6. Update `docs/architecture.md`: current-state paragraph, 250 families, nine
   owned flags, no v57, no migration.
7. Update `docs/configuration.md`: v56 remains accepted-only; science requires
   predictive world model and bounded experimentation; no new environment
   variable is required for science itself.
8. Update `docs/v4-architecture.md`:
   - Change the science table row from "deferred" to V4-27 owned with its
     existing authority, packages, mechanism, seam, and prerequisites.
   - Add a V4-27 paragraph under the existing version/ownership surface prose,
     not as a new context heading; keep exactly 17 `###` context headings.
9. Update `docs/analysis-metrics.md`: six family rows and the 250 footer.
10. Update `docs/research-api.md`: seven routes, limits, errors, and 250 footer.
11. Update `docs/research-ui.md`: read-only panel sections and the no-truth/no-
    score contract.
12. Update `docs/v4-versioning.md`: 9 owned / 3 unowned, 13 reuse-only contexts,
    max replay-v27/`v25`, 250 families.
13. Update `docs/development.md`: catalog 250, 17 contexts /
    `v4-context-map-v5`, and no v57.
14. Update `docs/cognition-runtime.md` and `docs/experiments.md`: intentional
    test path, ledger fields, and the off-gate experiment.
15. Update `AGENTS.md` documentation table with `docs/scientific-hypotheses.md`.
16. Do not edit `.ai-factory/ROADMAP.md`; V4-23 through V4-27 registration stays
    with `$aif-roadmap`.

### Required Interfaces and Contracts
- Docs state that hypotheses are owner beliefs and can be wrong; they never
  claim truth, proof, verification, accuracy, calibration, or objective rule
  access.
- Docs state that `hyp_v1` is testimony and not evidence.
- Docs state that `ExperimentResolved` rule payload is never copied.
- Docs list the exact family ids, route paths, error codes, and pins.
- Historical landing notes remain historical.

### Requirement Evidence
- `.ai-factory/ARCHITECTURE.md` requirement 7 (docs stay current) and the
  V4-24/V4-25/V4-26 seam format.
- `docs/social-mobility.md` and `docs/economic-cascades.md` as page templates.
- Original Request "Do not expose objective rules" and "Hypotheses can be
  wrong".

### Error Handling and Logging
- `$aif-docs` reports missing or stale links; fix them before closing the task.
- WARN `scientific_hypotheses_docs_gap` with the path only if a mandatory
  surface is missing.

### Tests
- No new test in this task; Task 20 adds the parity assertions.
- Manually verify every link added to README, ARCHITECTURE, DESCRIPTION, and
  `docs/` resolves.

### Acceptance Criteria
- The new page and every mandatory cross-link exist.
- Every current pin says 250 families and 9 owned / 3 unowned.
- No page claims objective-rule access or scientific truth.

### Verification
- `rg -n "scientific-hypotheses|scientific_hypotheses|V4-27" README.md docs .ai-factory/ARCHITECTURE.md .ai-factory/DESCRIPTION.md AGENTS.md`
- Expected result: the page, index entries, seam paragraph, and cross-links are
  present.

## Task 20: Add documentation pin and negative parity checks

### Intent
Make documentation drift fail the test suite and prove the negative claims:
science is owned, no v57 exists, no migration exists, hypotheses are not truth,
and no objective rule is exposed.

### Implementation Steps
1. Create `tests/unit/test_scientific_hypotheses_docs.py`:
   - `docs/scientific-hypotheses.md` exists and contains the policy token
     `scientific-hypotheses.v1`, all six family ids, all seven route paths,
     `scientific-hypotheses-snapshot-v1`, `scientific-hypotheses-store-v1`, all
     six status tokens, all six source-kind tokens, the ten condition-slot
     tokens, and the timeline fields `created_tick`/`revision_tick`.
   - Live pins match `V4_CONTEXTS`, `V4_CAPABILITY_FLAGS`,
     `V4_OWNED_CAPABILITY_FLAGS`, `METRIC_FAMILY_COUNT`, command count, observer
     semantic count, replay/codec maxima, and Alembic head.
   - `docs/v4-architecture.md` has exactly `len(V4_CONTEXTS)` `###` context
     headings and its science row says V4-27 owned.
   - README links the page; `docs/architecture.md`, `docs/configuration.md`,
     `docs/analysis-metrics.md`, `docs/research-api.md`,
     `docs/v4-architecture.md`, `docs/research-ui.md`, `docs/v4-versioning.md`,
     `docs/development.md`, `docs/cognition-runtime.md`, and
     `docs/experiments.md` mention the feature and current pins.
   - `.ai-factory/ARCHITECTURE.md` and `.ai-factory/DESCRIPTION.md` mention
     9 owned / 3 unowned, 250 families, and v56-only.
   - Negative assertions: no current-state sentence says science is unowned; no
     page says `runner-config-v57` is accepted; no page says `0018` exists; no
     page claims truth, verified, proven, accuracy, calibration, score, or
     objective-rule access for hypotheses.
2. Update existing docs tests that assert 244 or 8/4:
   - `tests/unit/test_economic_cascades_docs.py`
   - `tests/unit/test_social_mobility_docs.py`
   - `tests/unit/test_accounting_ledgers_pins.py`
   - `tests/unit/test_supply_chain_pins.py`
   - `tests/unit/test_credit_relationships_pins.py`
   - any other active docs pin found by `rg`.
3. Keep the V4-26 first-244 digest guard and add the same guard for the new
   six-family append in `test_scientific_hypotheses_catalog.py`.

### Required Interfaces and Contracts
- The docs test parses live constants; it does not duplicate them by hand.
- Historical landing notes are excluded by exact sentence or section, not by
  weakening the assertion.
- Negative claims are explicit assertions, not omissions.

### Requirement Evidence
- `tests/unit/test_economic_cascades_docs.py:72-134`.
- `tests/architecture/test_v4_context_registry.py:198-205`.
- `.ai-factory/ARCHITECTURE.md` requirement 7.

### Error Handling and Logging
- Test failures name the file and missing token; they do not print page bodies.
- No production logging change.

### Tests
- `uv run pytest tests/unit/test_scientific_hypotheses_docs.py tests/unit/test_economic_cascades_docs.py tests/unit/test_social_mobility_docs.py -q`
- Expected result: pass.

### Acceptance Criteria
- Docs drift fails closed.
- Negative claims are tested.
- No active `244`, `8-owned`, `14/15/16-context`, or `replay-v22`/`codec v20`
  pin remains in tests or current-state docs.

### Verification
- `uv run pytest tests/unit/test_scientific_hypotheses_docs.py -q`
- `rg -n "runner-config-v57|alembic.*0018|science remains unowned" docs README.md .ai-factory/ARCHITECTURE.md .ai-factory/DESCRIPTION.md`
- Expected result: no positive/current-state match; only explicit negative
  assertions in the docs test may mention these tokens.

## Task 21: Required-gate verification certification

### Intent
Record every required lane with an explicit command, result, and prerequisite.
No lane is green until its command and result are in the receipt. Environment-
gated lanes that cannot run are recorded as `unexecuted` with the missing
prerequisite, never omitted.

### Implementation Steps
1. Fill the `## Verification Receipt` table in `index.md` by running, in order:
   - `uv run pytest tests/unit tests/architecture -q`
   - `uv run pytest tests/unit/test_scientific_hypotheses_*.py tests/architecture/test_scientific_hypotheses_*.py tests/integration/test_scientific_hypotheses_store_api.py -q`
   - the focused coverage command with `--cov=src --cov-report=term`
   - the full unit+architecture coverage command with `--cov=src --cov-report=term`
   - `uv run ruff check src tests`
   - `uv run mypy src tests`
   - `uv run lint-imports`
   - `uv run pytest tests/integration -m "not scale" -q`
   - `uv run pytest tests/integration/test_scientific_hypotheses_store_api.py -q -m integration`
   - `docker compose config`
   - `cd clients/research-ui && ./node_modules/.bin/vitest run`
   - `cd clients/research-ui && ./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json`
   - the existing Godot protocol suite with `GODOT_BIN=...`
   - `PALIMPSEST_API_IMAGE=<matched> PALIMPSEST_V3_ACCEPTANCE_REQUIRED=1 uv run pytest -m compose -q` when an attested image is available
   - `PALIMPSEST_V4_SCALE_IDS=100000 uv run pytest tests/benchmarks -m "not scale" -q`
2. Record the Compose/browser acceptance lane as `unexecuted` with the exact
   command above and the attested-image prerequisite if no attested image is
   available; do not mark it green.
3. Record any lane whose prerequisite is absent as `unexecuted` with the exact
   environment variable or credential, not as a failure of the feature.
4. Run the `git status` audit:
   - no `.ai-factory/ROADMAP.md` edit from this plan;
   - no `alembic/versions/0018*`;
   - no `clients/godot-observer/` source change;
   - no `/v2` route;
   - no `runner-config-v57`;
   - no new V4 context; the only ownership change is `science` 8 -> 9 owned.
5. Record the final counts and any residual risk (for example an unexecuted
   Compose/browser lane) in the receipt note column.
6. Do not edit the roadmap, close M8, or create a commit unless the user
   explicitly authorizes it.

### Required Interfaces and Contracts
- Every required lane has a row: command, result, prerequisite/note.
- `unexecuted` is acceptable only with a prerequisite and is never reported as
  green.
- No lane is certified from a previous plan's receipt.
- The receipt is the only certification source.

### Requirement Evidence
- The selected settings: full test strategy, verbose metadata-only logging,
  mandatory docs, normal verification with explicit complete certification.
- `.ai-factory/ARCHITECTURE.md` requirement 7 and the project verification
  commands in `docs/development.md`.

### Error Handling and Logging
- Record failures verbatim by command and short result; do not paste full logs.
- If a gate fails, fix the feature or record the blocker; never mark it green.
- Never include secrets, DSNs, tokens, or payloads in the receipt.

### Tests
- The receipt commands themselves. No additional test file.

### Acceptance Criteria
- Every required lane is green or `unexecuted` with a prerequisite.
- The `git status` audit is clean for the forbidden surfaces.
- The final counts are 17/12/9/3, 250 families, 43 commands, 73 observer
  semantics, replay-v27/`v25`, Alembic `0017`, `/v1`, and
  `observer-protocol-v1`.

### Verification
- Re-run any failed focused command after the fix.
- Confirm `git status` output contains only the intended science surfaces,
  analysis/artifact modules, routes, UI panel, tests, and docs.

## Phase Risks and Mitigations
- Risk: a broad 244 -> 250 sweep rewrites historical landing notes.
  Mitigation: target active pins and current-state sentences; leave dated
  paragraphs intact.
- Risk: `docs/v4-architecture.md` gains a context heading and breaks the 17-H3
  invariant.
  Mitigation: add a V4-27 paragraph, not a new context heading.
- Risk: an env-gated lane is silently skipped.
  Mitigation: every skipped lane is `unexecuted` with an explicit prerequisite.
- Risk: certification hides a real failure behind "pre-existing".
  Mitigation: record command and result; fix feature-caused failures.

## Phase Completion Checklist
- Every active pin says 17/12/9/3 and 250 families.
- The feature page and all mandatory cross-links exist.
- Positive and negative docs parity tests pass.
- Every required verification lane is green or explicitly `unexecuted`.
- The roadmap remains unedited and owned by `$aif-roadmap`.
- `index.md` Tasks 18-21 checkboxes are updated after verification.
