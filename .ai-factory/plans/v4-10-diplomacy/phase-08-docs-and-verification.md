# Phase 8: Documentation and Final Verification

Plan: [index.md](index.md)
Tasks: 25-26
Depends on: Phase 7 / Tasks 22-24

## Objective

Produce the canonical diplomacy contract and update every affected document,
then audit the bundle, pins, authority claims, and receipt for final V4-10
certification.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `docs/delegation-representation.md` | 202-line feature-doc shape | Canonical contract template |
| `docs/analysis-metrics.md` | catalog 160; family sections 507, 532 | Metric documentation location |
| `docs/architecture.md` | current pins 565, 596, 654, 659 | Current-pin lines to update |
| `docs/v4-architecture.md` | diplomacy status 64, 133-138 | Context status to update |
| `docs/configuration.md` | runner version and V4 flag tables | Configuration reference |
| `docs/cognition-runtime.md` | mode/carry documentation | Runtime reference |
| `docs/research-api.md` | route documentation | API reference |
| `docs/research-ui.md` | panel documentation | UI reference |
| `docs/organizations.md` | related-contract links | Cross-link target |
| `README.md` | documentation index | Landing-page index |
| `tests/unit/test_delegation_representation_docs.py` | 51, 83 | Docs parity test shape |
| `.ai-factory/ARCHITECTURE.md` | 184, 204-208, 843-847 | Agent-facing current baseline |
| `.ai-factory/DESCRIPTION.md` | 385, 390 | Agent-facing current baseline |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `docs/diplomacy.md` | create | Canonical ownership, authority, records, frames, alignment, metrics, routes |
| `docs/architecture.md` | modify | V4-10 seam, current pins |
| `docs/v4-architecture.md` | modify | Diplomacy status and implementation note |
| `docs/analysis-metrics.md` | modify | Catalog 164 and four family sections |
| `docs/configuration.md` | modify | `runner-config-v56` + `diplomacy`, env vars |
| `docs/cognition-runtime.md` | modify | `CognitionDiplomacyMode`, prepare/carry |
| `docs/research-api.md` | modify | Six routes, disabled state, cursors |
| `docs/research-ui.md` | modify | Diplomacy panel |
| `docs/disputes.md` | modify | Four-owned and catalog-164 current pins |
| `docs/organizations.md` | modify | Link to the diplomacy contract |
| `docs/delegation-representation.md` | modify | Link forward to diplomacy composition |
| `README.md` | modify | Documentation index row |
| `.ai-factory/ARCHITECTURE.md` | modify | V4-10 seam, four owned flags, 164 families |
| `.ai-factory/DESCRIPTION.md` | modify | V4-10 current-state paragraph and pins |
| `tests/unit/test_diplomacy_docs.py` | modify | Parity assertions, including four-owned/eight-unowned |
| `tests/unit/test_formal_rule_docs.py` | modify | Four-owned/eight-unowned ownership parity |
| `tests/unit/test_dispute_docs.py` | modify | Catalog 164 and four-owned parity |
| `tests/unit/test_organization_docs.py` | modify | Catalog 164 parity |
| `tests/unit/test_organization_operations_docs.py` | modify | Catalog 164 parity |
| `tests/unit/test_evidence_testimony_docs.py` | modify | Catalog 164 parity |

## Task 25: Execute the documentation checkpoint

### Intent

Documentation is the contract a future implementer reads. It must state what
diplomacy controls, what it never controls, and every count exactly as the code
implements it.

### Implementation Steps

1. Create `docs/diplomacy.md` with these sections:
   - **Status and ownership**: owned `diplomacy` context, `runner-config-v56`,
     fourth owned V4 flag, prerequisite `organizations` as planning order.
   - **Authority**: owner-scoped belief only; no polity, border, citizenship,
     treaty store, treaty authority, envoy registry, army, war state, or
     bilateral score.
   - **Vocabulary**: party kinds, contact kinds, envoy statuses, negotiation
     statuses, instrument kinds/statuses, terms, provenance, termination,
     misrepresentation, conflicts, acceptance basis.
   - **Long-running relations**: the retained `DiplomaticRelation` row, ordered
     party sets with the owner self-party, episodes, caps, expiry,
     `DiplomaticTermination`, supersession, and retained history.
   - **Envoys and partial authority**: representation mandate composition, self
     claim, contested/rejected/revoked/expired/superseded standing, current
     standing derivation, the closed scope/duration matrix, scope-subject match,
     and the four misrepresentation kinds.
   - **Instruments**: proposals, promises, agreements, disputes, shared projects,
     declarations, the `is_agreement_view` rule, and the rule that
     `apparently_accepted` requires every party's own declaration (a principal
     counts directly; an envoy needs recognized standing) and binds nobody.
   - **Speech**: `dip_v1` acts, 15 fields including `topic_subject`,
     320-character bound, verified-speaker rule, receiver-assigned provenance,
     dropped-frame behavior.
   - **Detached analysis**: harvest, six lanes, `dip-` candidates, read-only
     `org-`/`msoc-` joins, three layers, researcher-only alignment.
   - **Metrics**: four families with populations, denominators, value keys, and
     the explicit absence of a composite score.
   - **Publication and API**: snapshot/store schemas, six GET routes,
     `SUBJECTIVE_DEBUG`, `diplomacy_disabled`, cursor binding.
   - **Research UI**: read-only panel and what it must not derive.
   - **Composition and non-goals**: read-only references to representation,
     decisions, commitments, rules, offices, disputes, and evidence; no command
     path; no automatic generalization.
2. Update `docs/architecture.md` with a V4-10 seam section and every current
   ownership phrase: 565-567 ("Three V4 flags are owned ... nine remain"), 596
   (catalog 160), 659-660 (160 and "`diplomacy` stays unowned"). Leave the
   historical `157 -> 160` revision at 654 unchanged.
3. Update `docs/v4-architecture.md`: the top-of-file ownership statement becomes
   four owned / eight unowned at line 15, and the `diplomacy` row/status at 64
   moves from "deferred" to "V4-10 implementation" with the reuse strategy
   described; keep the V4-01 non-goal sentence scoped to V4-01.
4. Update `docs/analysis-metrics.md`: catalog 164 at line 41, the four family
   sections in append order, empty/absent/unknown behavior, and the
   no-composite rule. Keep the historical `(catalog 160)` section labels at
   507/532.
5. Update `docs/configuration.md`: v56 + `diplomacy`,
   `PALIMPSEST_DIPLOMACY_ROOT`, `PALIMPSEST_DIPLOMACY_CURSOR_KEY`, CLI flags and
   bounds, and the 310-312 ownership paragraph ("Four V4 flags are owned ...
   other eight remain unowned").
6. Update `docs/cognition-runtime.md` with the mode, prepare step, record step,
   perspective, checkpoint, and export.
7. Update `docs/research-api.md` with the six route table, capability, disabled
   state, cursor errors, response fields, and the line-88 ownership statement
   ("Four V4 flags are owned ... other eight remain unowned").
8. Update `docs/research-ui.md` with the panel states and neutral rendering.
9. Add cross-links from `docs/organizations.md` and
   `docs/delegation-representation.md`, and a README documentation-index row.
10. Update `.ai-factory/ARCHITECTURE.md` (current baseline table at 184, ownership
    lists at 205/768-769/813-814/847-848, V4-10 seam) and
    `.ai-factory/DESCRIPTION.md` (V4-10 paragraph and pins at 344-345/370-371/
    391-393, including removing "`diplomacy` stays unowned"). Do not edit
    `.ai-factory/ROADMAP.md`.
11. Update `docs/disputes.md:224-225`: the "3 owned" phrase becomes four owned,
    and the current metric count becomes 164.
12. Sweep the docs parity tests that pin ownership/counts:
    `tests/unit/test_formal_rule_docs.py` (73-95),
    `tests/unit/test_dispute_docs.py` (118-119, 146),
    `tests/unit/test_organization_docs.py` (39, 42),
    `tests/unit/test_organization_operations_docs.py` (52-62), and
    `tests/unit/test_evidence_testimony_docs.py` (108, 168). Rename the
    "three owned / nine unowned" tests to "four owned / eight unowned".
13. Every count must match code: 14 contexts, 12 flags, four owned / eight
    unowned, 164 families, 43 commands, 73 semantic types, event 22, codec v20,
    Alembic 0017. The docs parity test must fail on a stale "diplomacy stays
    unowned", "three owned", or "nine remain" phrase.

### Required Interfaces and Contracts

- Documentation states explicitly that diplomacy is a belief, never permission,
    legitimacy, truth, or a binding agreement.
- Documentation states that a representative may lack authority or misrepresent,
  and that this is retained rather than adjudicated.
- Documentation states that macro-level relation metrics are per-lane counts with
  denominators and no composite score.
- Technical terms are preserved and the UI/artifact language remains English.

### Requirement Evidence (when reconciliation applies)

- Original Request: every requested interaction, the score prohibition, the six
  derivation lanes, and the misrepresentation clause.
- `.ai-factory/ARCHITECTURE.md` requirement 7: roadmap milestones are owned by
  `$aif-roadmap`.

### Error Handling and Logging

- Not applicable; this is a documentation task.
- Do not copy secrets, DSNs, tokens, or payload examples.

### Tests

- `tests/unit/test_diplomacy_docs.py`: `docs/diplomacy.md` exists and contains
  the canonical policy id, schema ids, six route paths, six cursor purposes, four
  family ids, the relation/termination row contract, the scope/duration matrix,
  the 15-field `dip_v1` frame, and the no-composite statement; every current pin
  line matches `METRIC_FAMILY_COUNT`, the registry, and the route list; the
  four-owned/eight-unowned statement appears in every affected doc; README links
  the doc; `docs/analysis-metrics.md` lists the four families last; no doc claims
  a treaty, polity, score, or objective authority; no current doc says
  "`diplomacy` stays unowned", "three owned", or "nine remain".
- `uv run pytest tests/unit/test_diplomacy_docs.py tests/unit/test_delegation_representation_docs.py tests/unit/test_evidence_testimony_docs.py tests/unit/test_formal_rule_docs.py tests/unit/test_dispute_docs.py tests/unit/test_organization_docs.py tests/unit/test_organization_operations_docs.py -q`
- Expected: pass.

### Acceptance Criteria

- The canonical contract is complete and consistent with code.
- Every affected document and agent-facing baseline is updated.
- No roadmap edit.

### Verification

- `uv run pytest tests/unit/test_diplomacy_docs.py -q`
- Expected: pass.
- `git status --short` shows documentation and plan files only; `.ai-factory/ROADMAP.md` is unchanged.

## Task 26: Perform final V4-10 verification

### Intent

The bundle must be internally consistent and the receipt audited before V4-10
can be called certified.

### Implementation Steps

1. Verify bundle integrity:
   - `index.md` contains `<!-- aif:plan-mode:ultra -->` exactly once.
   - All eight Phase Index links exist and are relative.
   - Every Task 1-26 appears exactly once in the index checklist and exactly once
     as a `## Task N:` section in the named phase file.
   - Every dependency references an existing task.
   - No phase file contains task checkboxes or is orphaned.
   - Commit groups cover every task without overlap.
2. Verify registry and pins: 14 contexts, 12 flags, `v4-context-map-v2`, four
   owned flags, eight unowned, four reservations, 164 families, 43 commands, 73
   semantic types, event 22, codec v20, Alembic `0017`, no `0018`, `/v1`,
   `observer-protocol-v1`, `prepare_parallel=False`.
3. Verify authority claims: no diplomacy command path, no world read, no peer
   ledger read, no truth/legitimacy oracle, no registry, no polity/border/
   citizenship/treaty, no score, no `msoc-`/`org-` mutation.
4. Verify the record and standing contracts: relation party sets include a
   self-party; instrument party sets match; terminations are retained;
   `SUPERSEDED` is present; current standing is derived; the scope/duration
   matrix is shared by Task 9 and Task 14; the pipeline materializes every
   derived row family.
5. Verify token interoperability: agent tokens match V4-09's representation
   domain; `orgc-`/region anchors remain owner-safe; `dip-pub-` is rejected as a
   candidate id.
6. Verify surfaces: six GET routes, six cursor purposes,
   `diplomacy-snapshot-v1`, `diplomacy-store-v1`, `DiplomacySnapshot*Row`
   names, `dip-` candidate prefix, four metric families.
7. Verify the pin sweep: 49 test files / 78 current `== 160` occurrences moved to
   164; every four-owned/eight-unowned doc statement updated; historical seam
   pins and the first-154 digest preserved.
8. Audit the Task 24 receipt row by row; confirm every lane is exactly one of the
   three states and the focused in-process E2E lane is present.
9. Record the certification outcome. If any required lane is `unexecuted` or
   `executed_failed`, the outcome is `not certified` with the named blockers.
10. Confirm branch is `main`, no worktree or branch was created, and no roadmap
    edit occurred.

### Required Interfaces and Contracts

- Audit output is recorded in `index.md` under the Verification Receipt.
- No test, pin, or assertion may be weakened to make the audit pass.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` requirements 1-7.
- Plan Settings: "normal verification with explicit complete required-gate
  certification".

### Error Handling and Logging

- Report the exact offending file and symbol for any failed audit.
- Never include tokens, ids, DSNs, or payloads in the audit text.

### Tests

- `uv run pytest tests/architecture/test_diplomacy_boundaries.py tests/unit/test_diplomacy_docs.py -q`
- Expected: pass.

### Acceptance Criteria

- Bundle integrity is 26/26.
- The receipt is complete and the certification outcome is explicit.

### Verification

- Manual bundle audit plus the two commands above.
- Expected: 26 tasks mapped; all pins match; certification outcome recorded.

## Phase Risks and Mitigations

- Risk: docs drift from code counts.
  Mitigation: parity test plus the Task 15 pin sweep and the Task 26 audit.
- Risk: the plan claims certification with unexecuted lanes.
  Mitigation: explicit three-state audit and a recorded blocker list.
- Risk: roadmap is edited as part of documentation.
  Mitigation: `$aif-roadmap` ownership note and a `git status` check.

## Phase Completion Checklist

- Every task in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
