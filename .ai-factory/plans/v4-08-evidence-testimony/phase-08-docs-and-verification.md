# Phase 8: Documentation and Final Verification

Plan: [index.md](index.md)
Tasks: 23-24
Depends on: Phase 7 / Task 22

## Objective

Document exactly what a general evidence belief controls and what it never
controls, align every count with the code, and perform the final V4-08 audit
without touching roadmap ownership.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `docs/disputes.md` | headings 1-267 | Canonical V4 documentation shape |
| `README.md` | documentation table 70-92; Disputes row 88 | Landing-page index |
| `.ai-factory/DESCRIPTION.md` | V4-07 paragraph 317-345 | Feature-state prose and pins |
| `.ai-factory/ARCHITECTURE.md` | baseline table 177-194; ownership 195-208; V4-07 seam 724-770 | Architecture contract to extend |
| `docs/research-api.md` | capability/cursor rules | API contract to extend |
| `docs/configuration.md` | `PALIMPSEST_` settings | Settings documentation |
| `tests/unit/test_dispute_docs.py` | parity tests | Doc-parity test shape |
| `tests/unit/test_organization_docs.py` | pins "metric families 154"/"154 metric families" 39-42 | Count strings updated in Task 13; verify here |
| `tests/unit/test_organization_operations_docs.py` | count pins | Global pin string to update |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `docs/evidence-testimony.md` | create | Canonical contract and behavior |
| `README.md` | modify | Add the Evidence and testimony row |
| `docs/research-api.md` | modify | Six evidence routes and cursor/disabled semantics |
| `docs/analysis-metrics.md` | modify | Evidence families section and denominators |
| `docs/research-ui.md` | modify | Evidence panel section |
| `docs/disputes.md` | modify | See-also cross-link to the evidence contract |
| `docs/configuration.md` | modify | `PALIMPSEST_EVIDENCE_*` settings |
| `docs/architecture.md` | modify | Link the new seam where feature seams are indexed |
| `.ai-factory/DESCRIPTION.md` | modify | V4-08 paragraph and current pins |
| `.ai-factory/ARCHITECTURE.md` | modify | Baseline 157 and V4-08 seam section |
| `tests/unit/test_evidence_testimony_docs.py` | create | Heading, route, env, schema, count, and non-goal parity |
| `tests/unit/test_organization_docs.py` | verify | Count strings were updated to 157 in Task 13; no further edit unless V4-08 prose changes a referenced string |
| `tests/unit/test_organization_operations_docs.py` | verify | Count strings were updated to 157 in Task 13 |

## Task 23: Execute the documentation checkpoint

### Intent

Produce a documentation contract that a later reader can use to understand the
model without inferring truth semantics, and make every documented count match
the code.

### Implementation Steps

1. Create `docs/evidence-testimony.md` with these exact top-level sections:
   - `# Evidence and testimony`
   - `## What evidence can and cannot do`
   - `## Sources`
   - `## Provenance`
   - `## Chain of custody`
   - `## Confidence`
   - `## Agent interpretation`
   - `## Contradictions`
   - `## Witness testimony and independence`
   - `## Evaluation under the owner's own trust models`
   - `## Objective alignment (researcher only)`
   - `## Snapshot, publication, and routes`
   - `## Metrics`
   - `## Configuration`
   - `## Limits and non-goals`
   - `## Non-claims`
   - `## See also`
2. Content requirements:
   - state that evidence is one owner's belief about a source, never truth,
     proof, authenticity, guilt, liability, or a verdict;
   - enumerate the seven requested source kinds plus `unknown`;
   - explain provenance channels, that the reference anchor and the opaque
     correlation token are separate, and that the correlation is never
     dereferenced;
   - explain that custody applies only to artifact, written-record, and
     physical-state sources and that its status is a belief;
   - explain confidence is owner confidence, not probability of truth;
   - explain closed interpretations and that artifacts may be misinterpreted;
   - explain that contradictory memories/records coexist and preferences are
     explicit and revisable;
   - explain direct vs communicated testimony, shared roots, and attributed
     authorship;
   - explain the six trust bases and that no peer ledger or global score is read;
   - explain `consistent`/`unresolved`/`inconsistent`/`not_applicable` as
     researcher-only;
   - document `evidence-testimony-snapshot-v1`,
     `evidence-testimony-store-v1`, the six GET-only routes,
     `PALIMPSEST_EVIDENCE_ROOT`, `PALIMPSEST_EVIDENCE_CURSOR_KEY`, and the
     three metric families with the catalog at 157;
   - list non-goals and non-claims verbatim from the index blocking section.
3. `README.md`: add a row after Disputes:
   `| [Evidence and testimony](docs/evidence-testimony.md) | Owner-scoped
   sources, provenance, custody beliefs, confidence, interpretations,
   contradictions, trust evaluation, researcher-only objective alignment,
   evidence-testimony-snapshot-v1, six GET-only routes and the Research UI
   panel |`
4. `docs/research-api.md`: add the six routes, `SUBJECTIVE_DEBUG`,
   `evidence_testimony_disabled`, cursor purposes, TTL 900, 400/410 behavior, and
   the 2 MiB response budget.
5. `docs/configuration.md`: document both env vars, defaults (unset/disabled),
   and validation (non-empty root, ≥32-byte cursor key).
6. `docs/analysis-metrics.md`: add an `## Evidence families (catalog 157)`
   section after the dispute families, with the three family names, their
   denominators, and an explicit statement that objective alignment is
   researcher-only and never a verdict.
7. `docs/research-ui.md`: add an `## Evidence panel` section describing the six
   read-only routes, the available/empty/unavailable states, and that the panel
   renders only server fields.
8. `docs/disputes.md`: add the evidence contract to `## See also`.
9. `.ai-factory/DESCRIPTION.md`: add a V4-08 paragraph after V4-07 stating the
   deepened context, no new flag, evidence ledger, testimony independence,
   trust evaluation, researcher-only alignment, snapshot/store/routes/UI,
   metric families 157, and unchanged pins.
10. `.ai-factory/ARCHITECTURE.md`: update the baseline table to 157 and add a
    `### V4-08 evidence and testimony seam` section stating the ownership,
    non-goals, and pins.
11. The current 157 catalog pins in `.ai-factory/DESCRIPTION.md`,
    `.ai-factory/ARCHITECTURE.md`, `docs/architecture.md`, `docs/disputes.md`,
    and `docs/analysis-metrics.md` were updated in Task 13. Do not change them
    again; if the new V4-08 prose needs a different sentence, edit only the new
    V4-08 paragraphs.
12. Create `tests/unit/test_evidence_testimony_docs.py` asserting:
    - every required heading exists, including the analysis-metrics and
      research-ui sections;
    - all seven source kinds, five custody statuses, six primary trust bases
      (plus `none`/`unknown`), and four alignment values appear;
    - the snapshot/store schema names, six route paths, both env vars, and all
      three family names appear;
    - README links `docs/evidence-testimony.md`;
    - `docs/disputes.md` links the evidence contract;
    - DESCRIPTION and ARCHITECTURE contain the current 157 pin;
    - no doc claims objective truth, proof, authenticity, or a consensus oracle.

### Required Interfaces and Contracts

- `docs/evidence-testimony.md` is canonical; no duplicate document is created.
- Documentation language matches `language.artifacts: en`.
- No roadmap file is edited.

### Requirement Evidence

- Original Request documentation intent; Plan Settings "Docs: yes".
- `.ai-factory/ARCHITECTURE.md` requirement 7 — roadmap ownership.
- `docs/disputes.md` 1-267.

### Error Handling and Logging

- Not applicable; documentation only.

### Tests

- `uv run pytest tests/unit/test_evidence_testimony_docs.py tests/unit/test_dispute_docs.py tests/unit/test_organization_docs.py tests/unit/test_organization_operations_docs.py -q`
- Expected: pass.

### Acceptance Criteria

- The documentation is complete, accurate, and linked from the landing page.
- Every documented count matches the code.

### Verification

- `uv run pytest tests/unit/test_evidence_testimony_docs.py -q`
- `rg -n "evidence-testimony-snapshot-v1|PALIMPSEST_EVIDENCE_ROOT|evidence_source_structure" docs README.md .ai-factory/DESCRIPTION.md .ai-factory/ARCHITECTURE.md`
- Expected: tests pass and all identifiers are present.

## Task 24: Perform final V4-08 verification

### Intent

Audit the completed bundle against every authority claim and the recorded
receipt, without claiming certification when a required lane is unexecuted.

### Implementation Steps

1. Verify `index.md` is the only checkbox source and that 24/24 tasks are
   checked; every Phase Index link resolves to one phase file and every task
   maps to exactly one `## Task N:` section.
2. Verify `legal_disputes` remains the third owned V4 flag;
   `V4_CONTEXTS` is 14, `V4_CAPABILITY_FLAGS` is 12,
   `V4_OWNED_CAPABILITY_FLAGS` is exactly three; no `runner-config-v57`, new
   flag, context, root field, or per-agent runner key exists.
3. Verify no new event, command, observer semantic type, write pair, `/v2`
   route, or migration: replay `EVENT_SCHEMA_REPLAY_V22` (22), codec `v20`,
   commands 43, observer semantics 73, Alembic `0017`, no `0018`.
4. Verify six GET-only `/v1/.../evidence` routes, six cursor purposes, and that
   the organization/formal-rule/dispute route sets are unchanged.
5. Verify `evidence-testimony-snapshot-v1` and
   `evidence-testimony-store-v1` are independent; dispute, organization v1/v2/v3,
   and `formal-rule-snapshot-v1` fixtures remain decodable and byte-verifiable.
6. Verify `WorldEngine` and admission never read an evidence ledger, and that
   the E2E proves a contested-but-possible command is admitted while a possible
   impossible command is rejected.
7. Verify metric families 157, the first 154 unchanged, and real completed-run
   assembly emits all three evidence documents.
8. Verify `docs/evidence-testimony.md` is canonical, README links it, and every
   documented count matches.
9. Verify `.ai-factory/RULES.md` was not edited and `.ai-factory/ROADMAP.md`
   was not edited. Record that `$aif-roadmap` must register V4-08 in M8 after
   verification.
10. Audit the Task 22 receipt: every required lane is exactly one of the three
    states; each `unexecuted` row has a prerequisite; no lane is a skip-pass.
    Set the certification outcome to **certified** only when every required lane
    is `executed_passed`; otherwise **not certified** with the blocker list.
11. Record the audit in `index.md` under a `### Task 24 audit` subsection.

### Required Interfaces and Contracts

- No implementation or test weakening occurs during the audit.
- Certification is a strict function of the receipt.
- The roadmap remains owned by `$aif-roadmap`.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Versioned Extension Contract"; requirement 7.
- Plan Settings "Testing: yes; full strategy" and Definition of Done.

### Error Handling and Logging

- Report blockers by lane name and prerequisite; do not hide an unexecuted lane.

### Tests

- Re-run the focused V4-08 suite and the pin suite:
  `uv run pytest tests/unit/test_evidence_testimony_*.py tests/architecture/test_evidence_testimony_boundaries.py -q`
- `uv run pytest tests/unit/test_metric_specifications.py tests/architecture/test_v4_architecture_invariants.py -q`

### Acceptance Criteria

- The audit is complete, reproducible, and consistent with the receipt.
- `git status` shows no roadmap or rules edit.

### Verification

- `git status --short`
- Expected: only V4-08 implementation, tests, and documentation paths (plus the
  plan bundle); no `.ai-factory/ROADMAP.md`, no `.ai-factory/RULES.md`, no
  unrelated files.

## Phase Risks and Mitigations

- Risk: documentation drifts from code counts.
  Mitigation: parity tests read the artifacts and assert exact strings.
- Risk: certification is claimed despite an unexecuted lane.
  Mitigation: Task 24 is a strict audit of the three-state receipt.
- Risk: roadmap is edited during implementation.
  Mitigation: explicit `git status` check and `$aif-roadmap` ownership note.

## Phase Completion Checklist

- Every Task 23-24 in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
- The verification receipt and audit reflect actual command results.
