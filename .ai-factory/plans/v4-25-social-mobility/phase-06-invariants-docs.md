# Phase 6: Invariants, Documentation, and Certification

Plan: [index.md](index.md)
Tasks: 18-21
Depends on: Phase 5 (Tasks 15-17)

## Objective

Sweep every active context/catalog pin from 15→16 contexts and 228→236 metric
families, document the feature through `$aif-docs`, add positive and negative
parity checks, and certify or explicitly mark `unexecuted` every required
verification lane.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `tests/architecture/test_v4_context_registry.py` | `DECLARED_ORDER` (31-47), map assertions (101-108), section count (190) | Context and document-section pins |
| `tests/architecture/test_v4_architecture_invariants.py` | metric pin (146), contexts (215, 392), flags (216, 393) | Architecture pins |
| `tests/architecture/test_v3_baseline_inventory.py` | `"metric_family_count": 228` (63) | Baseline inventory pin |
| `tests/unit/test_metric_specifications.py` | count assertions (44-45) | Catalog count pin |
| `tests/unit/test_economic_inequality_catalog.py` | `_FIRST_220_DIGEST` (15), append discipline (36-40) | Append-discipline pattern for the new first-228 digest |
| `docs/v4-architecture.md` | version pin row (287), per-context `###` sections (81-239) | Context section and catalog pin |
| `docs/*.md` | 50 files carry `Current catalog: 228 metric families; 43 commands; 73 observer semantic types; Alembic \`0017\`.` | Footer sweep |
| `tests/unit/test_economic_inequality_docs.py` | docs pin/parity pattern | New docs parity test shape |
| `.ai-factory/ARCHITECTURE.md` | baseline table (179-193), V4-24 seam (1202-1223) | Architecture documentation update |
| `.ai-factory/DESCRIPTION.md` | V4-24 entry (713-733) | Description update |
| `docs/economic-inequality.md` | section structure (1-160) | New page structure to mirror |
| `docs/generational-runner.md`, `docs/lineage-explorer.md`, `docs/organizations.md`, `docs/economic-inequality.md` | cross-link targets | Genealogy and institution cross-links |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `tests/architecture/test_v4_context_registry.py` | modify | 16 contexts, `v4-context-map-v4` |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | 236 families, 16 contexts |
| `tests/architecture/test_v3_baseline_inventory.py` | modify | 236 families |
| `tests/unit/test_metric_specifications.py` and ~73 other `tests/unit` count pins | modify | 228→236 current pins only |
| ~22 other `tests/architecture` count pins | modify | 228→236 current pins only |
| `docs/*.md` (50 footers) | modify | `Current catalog: 236 metric families` |
| `docs/v4-architecture.md` | modify | Catalog pin, `### social_mobility` section, 16 sections |
| `.ai-factory/ARCHITECTURE.md` | modify | V4-25 seam, 16 contexts, 236 families |
| `.ai-factory/DESCRIPTION.md` | modify | V4-25 entry and pins |
| `README.md` | modify | Documentation index entry |
| `docs/architecture.md`, `docs/configuration.md`, `docs/analysis-metrics.md`, `docs/research-api.md`, `docs/research-ui.md` | modify | Feature surface and counts |
| `docs/generational-runner.md`, `docs/lineage-explorer.md`, `docs/organizations.md`, `docs/economic-inequality.md` | modify | Cross-links to the new page |
| `docs/social-mobility.md` | create | Full feature page |
| `tests/architecture/test_social_mobility_boundaries.py` | create | Import/version boundaries |
| `tests/architecture/test_social_mobility_invariants.py` | create | 16/12/8/4, 236, 43, 73, replay-v27/codec v25, Alembic 0017 |
| `tests/unit/test_social_mobility_docs.py` | create | Docs sections and parity/negative claims |
| `.ai-factory/plans/v4-25-social-mobility/index.md` | modify | Verification receipt only |

## Task 18: Sweep context, catalog, and ownership pins

### Intent
Keep the closed catalog and context registry internally consistent in one
change so no intermediate commit has a half-swept count.

### Implementation Steps
1. Registry pins:
   - `test_v4_context_registry.py`: `DECLARED_ORDER` appends
     `SOCIAL_MOBILITY`; `DECLARED_PREREQUISITES` adds
     `SOCIAL_MOBILITY: frozenset()`; assert `v4-context-map-v4`,
     `len(V4_CONTEXTS) == 16`, flags 12, order equality.
   - `test_v4_architecture_invariants.py`: contexts 16, flags 12, owned 8,
     unowned 4, families 236.
   - Update the `\n### ` document-section assertion to 16 now. The architecture
     suite is expected red on this single assertion until Task 19 writes the
     `### social_mobility` section; do not weaken or skip the assertion.
2. Catalog pins:
   - Update every current `METRIC_FAMILY_COUNT == 228` / `len(specs) == 228`
     assertion to 236 across `tests/unit` and `tests/architecture`. Use a
     content search for `228` and change only current-catalog pins; leave
     historical landing counts in feature-history prose untouched.
   - Update metric-service log expectations from `catalog=228` to
     `catalog=236`.
   - Update `test_social_mobility_catalog.py` to pin the first 228 with
     `c8ac976ec9ae568d337835d4b0879850c4864040e4d338e663a3c13a83dc3dff` and
     the appended ids at positions 228-235.
   - Update `tests/architecture/test_v3_baseline_inventory.py` to 236.
3. Docs count sweep (not the feature page; Task 19 writes it):
   - Replace the current-catalog footer in all 50 `docs/*.md` files from 228 to
     236.
   - Leave historical sentences such as "catalog 220 → 228" and "metric
     families 228" inside V4-24 landing history unchanged.
4. Add `tests/architecture/test_social_mobility_boundaries.py`:
   - `analysis/social_mobility_*` imports no `api`, `persistence`,
     `experiments`, `infrastructure`, or `simulation` package;
   - no `world._*` or `WorldState` import;
   - `simulation/social_mobility_*` imports no `analysis`;
   - no `/v2` route and no new command/event/write pair;
   - the module allowlist matches the created files.
5. Add `tests/architecture/test_social_mobility_invariants.py`:
   - 16 contexts / 12 flags / 8 owned / 4 unowned / `v4-context-map-v4`;
   - `METRIC_FAMILY_COUNT == 236`;
   - commands 43, observer semantic types 73, replay `EVENT_SCHEMA_REPLAY_V27`,
     codec `v25`, Alembic `0017`, `/v1`, `observer-protocol-v1`;
   - `social_mobility` has no capability flag and is in the analysis-only and
     event-reusing sets.

### Required Interfaces and Contracts
- No historical count is rewritten as if it were current.
- No new capability flag, command, event, observer semantic type, write pair,
  `/v2` route, migration, runner root field, or per-agent key.
- The only new catalog families are the eight social-mobility ids.

### Requirement Evidence
- `.ai-factory/ARCHITECTURE.md` Versioned Extension Contract requirements 1 and
  5; `METRIC_FAMILY_COUNT` is the closed gate.

### Error Handling and Logging
- No new production logs.
- Test failures must name the mismatched count or token.

### Tests
- The sweep itself is verified by the full architecture suite plus the new
  boundary/invariant tests.

### Acceptance Criteria
- `uv run pytest tests/architecture -q` is green after Task 19 lands the docs
  section.
- Every current pin reads 236 / 16.

### Verification
- `uv run pytest tests/architecture/test_v4_context_registry.py tests/architecture/test_v4_architecture_invariants.py tests/architecture/test_social_mobility_boundaries.py tests/architecture/test_social_mobility_invariants.py -q`
- Expected result: green except the single 16-section document assertion, which
  Task 19 satisfies; record that exception rather than hiding it.

## Task 19: Documentation via `$aif-docs`

### Intent
Produce the mandatory documentation checkpoint and record the seam without
editing the roadmap.

### Implementation Steps
1. Run the `$aif-docs` workflow.
2. Create `docs/social-mobility.md` with these sections, mirroring
   `docs/economic-inequality.md`:
   - `# Social mobility`
   - `## Overview`
   - `## Activation`
   - `## Domains and evidence` (six domains, one measure each, evidence source
     per domain)
   - `## Ancestor and descendant pairing`
   - `## Mobility and persistence statistics` (quantile bins, four statistics,
     persistence labels, minimum pair threshold)
   - `## Generation lags and many-generation studies`
   - `## Coverage and bounds`
   - `## Read-only surfaces` (seven routes, dual gate, cursor binding)
   - `## Non-goals` (no class/caste/stratum labels, no merit/desert/prestige,
     no inheritance right, no composite score, no feedback)
   - `## Pins` (16 contexts / 12 flags / 8 owned / 4 unowned; 236 families; 43
     commands; 73 semantic types; replay-v27/codec `v25`; Alembic `0017`;
     `/v1`; `observer-protocol-v1`)
   - `## Verification`
3. Update `README.md` documentation index; `.ai-factory/ARCHITECTURE.md`
   (V4-25 seam, `v4-context-map-v4`, 16 contexts, 236 families);
   `.ai-factory/DESCRIPTION.md` (V4-25 entry); `docs/architecture.md`,
   `docs/configuration.md`, `docs/analysis-metrics.md`, `docs/research-api.md`,
   `docs/research-ui.md`, and `docs/v4-architecture.md` (also add the
   `### social_mobility` section so the registry document-declaration test can
   pass).
4. Add cross-links in `docs/generational-runner.md`,
   `docs/lineage-explorer.md`, `docs/organizations.md`, and
   `docs/economic-inequality.md`.
5. State explicitly that `.ai-factory/ROADMAP.md` is stale for V4-23, V4-24, and
   V4-25 and is owned by `$aif-roadmap`; do not edit it.

### Required Interfaces and Contracts
- Docs describe analysis only; they never claim a capability flag, new
  command/event, Godot overlay, CLI producer, `/v2` route, or objective
  legitimate-ownership/mobility metric.
- Pins must match the code exactly.

### Requirement Evidence
- `workflow.plan_docs: yes`; `.ai-factory/ARCHITECTURE.md` requirement 7
  (roadmap ownership stays with `$aif-roadmap`).

### Error Handling and Logging
- Documentation changes add no runtime logging.

### Tests
- `tests/unit/test_social_mobility_docs.py` is added in Task 20.

### Acceptance Criteria
- The new page exists with all required sections.
- Every updated document states the same 16/236 pins.
- Roadmap is untouched.

### Verification
- `uv run pytest tests/architecture/test_v4_context_registry.py -q`
- Expected result: pass with the new `### social_mobility` section.

## Task 20: Add documentation pin and negative parity checks

### Intent
Prevent documentation drift and ensure no future edit reintroduces class
vocabulary or a capability claim through prose.

### Implementation Steps
1. Create `tests/unit/test_social_mobility_docs.py`:
   - required section headings in `docs/social-mobility.md`;
   - pins: 16 contexts, 236 families, seven route names, dual-gate token
     `social_mobility_disabled`, six domains, eight families, `v4-context-map-v4`;
   - positive absence checks scoped to affirmative claim patterns, excluding
     `## Non-goals` and lines that start with "no "/"never ": reject phrasing
     such as "classifies owners into", "assigns a social class", "identifies
     the elite", "computes a mobility score", "ranks generations", "the best
     generation", "the worst generation", "inheritance right", and "deserved
     status". The page must still be allowed to say "no social class" and
     "no best/worst generation" in its non-goals.
   - negative parity: fail if docs claim a V4 capability flag for
     `social_mobility`, a new command/event, a Godot overlay, a CLI producer, a
     `/v2` route, or objective legitimate-ownership/mobility.
2. Retain and verify the document heading-count assertion here: assert
   `docs/v4-architecture.md` contains exactly 16 `\n### ` sections and a
   `### social_mobility` section; run
   `test_document_declares_every_context_and_required_section` against the page
   Task 19 produced.

### Required Interfaces and Contracts
- Parity checks are literal and fail closed.
- History sections are excluded from negative checks by scoping to the current
  page and current pin lines.

### Requirement Evidence
- `.ai-factory/ARCHITECTURE.md` requirement 7 and docs-ownership rule.
- V4-24 docs parity pattern.

### Error Handling and Logging
- No new production logs.

### Tests
- The named file.

### Acceptance Criteria
- Docs/tests agree on 16/236 and seven routes.
- A hypothetical class label or capability claim fails the suite.

### Verification
- `uv run pytest tests/unit/test_social_mobility_docs.py tests/architecture/test_v4_context_registry.py -q`
- Expected result: pass.

## Task 21: Required-gate verification certification

### Intent
Record evidence for every required lane, and mark env-gated lanes
`unexecuted` with their prerequisite instead of implying success.

### Implementation Steps
1. Run every command in the Verification Receipt in `index.md`; record the
   exact command and result. Do not mark green without both.
2. Confirm `git status` shows:
   - no `.ai-factory/ROADMAP.md` edit from this plan;
   - no `alembic/versions/0018*` file;
   - no `clients/godot-observer/` source change;
   - no `/v2` route;
   - no new V4 capability flag.
3. Confirm pins: 43 commands, 73 observer semantic types, replay-v27/codec
   `v25`, Alembic `0017`, `/v1`, `observer-protocol-v1`, 16 contexts, 236
   families.
4. Write the receipt into `index.md` only. Do not commit unless the user
   explicitly authorizes it.

### Required Interfaces and Contracts
- Each lane row has `command`, `result`, `prerequisite / note`.
- A timed-out or prerequisite-missing lane is `unexecuted`, never `passed`.

### Requirement Evidence
- `workflow.verify_mode: normal`; plan Settings "full strategy".

### Error Handling and Logging
- Collect metadata-safe summaries only; no payloads, tokens, or DSNs.

### Tests
- The verification lanes themselves.

### Acceptance Criteria
- Every lane is green or explicitly `unexecuted` with a prerequisite.
- The receipt matches the actual commands and results.

### Verification
- See the Verification Receipt in `index.md`.

## Phase Risks and Mitigations
- Risk: a global 228→236 replacement rewrites historical counts.
  Mitigation: change only footer/pin patterns and re-read surrounding lines;
  add a test that historical V4-24 sentences still say 220→228.
- Risk: docs claim a capability flag indirectly ("enables social mobility").
  Mitigation: negative parity checks and explicit non-goal wording.
- Risk: certification marks an env-gated lane green without a run.
  Mitigation: the receipt requires command + result and allows `unexecuted`.

## Phase Completion Checklist
- Every Task in this phase satisfies its acceptance criteria.
- Full architecture suite, docs parity, and static gates pass or are recorded
  `unexecuted`.
- `index.md` Task 18-21 checkboxes and the Verification Receipt are updated
  after verification.
