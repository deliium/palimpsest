# Phase 8: Documentation and Final Verification

Plan: [index.md](index.md)
Tasks: 23-24
Depends on: Phase 7 / Tasks 20-22

## Objective

Document the verified dispute feature, update every count and seam note, add a
docs parity test, and perform the final V4-07 certification audit.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `README.md` | documentation index 40-95 | Add the disputes page row. |
| `docs/formal-rules.md` | full page structure | Closest documentation template. |
| `docs/mediation.md` | mediation contracts and metrics | Must cross-link disputes and state non-binding semantics. |
| `docs/architecture.md` | authority boundaries and version pins | Add the V4-07 seam and 154-family pin. |
| `docs/configuration.md` | runner/V4 flag and settings tables | Add `legal_disputes` ownership and dispute settings. |
| `docs/analysis-metrics.md` | catalog families and counts | Add three families and 154. |
| `docs/social-communication.md` | `Talk`/`Tell` and bounded frames | Add `dsp_v1`. |
| `docs/cognition-runtime.md` | subjective sidecars and checkpoints | Add the dispute stage/carry. |
| `docs/research-api.md` | route table and cursor errors | Add six dispute routes. |
| `docs/research-ui.md` | panels and read-only policy | Add the Disputes panel. |
| `docs/v4-architecture.md` | V4 context/flag ownership | Mark `legal_disputes` owned. |
| `docs/persistence.md` | filesystem stores and schemas | Add the dispute store. |
| `docs/experiments.md` | publication/CLI bridges | Add the dispute producer. |
| `docs/development.md` | canonical test matrix | Add the dispute suite commands. |
| `.ai-factory/ARCHITECTURE.md` | baseline table, capability ownership, V4-07 seam | Update 3 owned flags and 154 families. |
| `.ai-factory/DESCRIPTION.md` | current state and pins | Add V4-07 state and pins. |
| `tests/unit/test_formal_rule_docs.py` | docs parity pattern | Add `test_dispute_docs.py`. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `docs/disputes.md` | create | Full dispute contract and limitations. |
| `README.md` | modify | Add the documentation index row. |
| `docs/architecture.md` | modify | V4-07 seam, 154 families, 3 owned flags. |
| `docs/configuration.md` | modify | `legal_disputes`, `dispute_root`, cursor key, v56 seam. |
| `docs/analysis-metrics.md` | modify | Three families and 154 count. |
| `docs/social-communication.md` | modify | `dsp_v1` acts and delivery semantics. |
| `docs/cognition-runtime.md` | modify | Dispute stage, carry, checkpoint, disabled passthrough. |
| `docs/mediation.md` | modify | Dispute links, recommendations as beliefs, voluntary undertaking. |
| `docs/research-api.md` | modify | Six routes, auth, `dispute_disabled`, cursor errors. |
| `docs/research-ui.md` | modify | Disputes panel and read-only labels. |
| `docs/v4-architecture.md` | modify | `legal_disputes` implemented/owned; 3 owned / 9 unowned. |
| `docs/persistence.md` | modify | `dispute-resolution-store-v1` layout and quotas. |
| `docs/experiments.md` | modify | Dispute harvest/publication/CLI receipt. |
| `docs/development.md` | modify | Add the focused unit/architecture, integration, and UI dispute commands. |
| `.ai-factory/ARCHITECTURE.md` | modify | V4-07 seam, 154 families, 3 owned flags, no new pins. |
| `.ai-factory/DESCRIPTION.md` | modify | V4-07 state paragraph and pins. |
| `tests/unit/test_dispute_docs.py` | create | Documentation parity assertions. |

## Task 23: Execute the documentation checkpoint

### Intent

Make the documentation match the verified code and explicitly state what a
dispute is and is not. Docs are part of the deliverable, not an afterthought.

### Implementation Steps

1. Invoke the `$aif-docs` checkpoint. Create `docs/disputes.md` with:
   - **What a dispute is**: one owner's belief about attributed claims; not a
     court, verdict, judgment, or shared case file.
   - **Kinds**: contested debt, ownership claim, contract interpretation, injury,
     broken promise, resource appropriation, other.
   - **Claims and counterclaims**: separate attribution, polarity, uncertainty,
     and no reconciliation.
   - **Memory-dependent disagreement**: two owners may retain incompatible
     evidence; no ground-truth correction.
   - **Testimony**: direct vs communicated; shared roots are not independent.
   - **Evidence references**: typed owner-visible anchors; opaque event
     correlation; no payload copies.
   - **Rule references**: owner formal-rule ledger only; orphaned/version
     mismatch behavior; no world law.
   - **Institutional roles**: office/institution/organization/collective-decision
     references; no judge/court/jurisdiction.
   - **Mediation**: linked cases/recommendations/responses/outcomes; not binding;
     only exact `Give` undertaking through the existing mediation compiler.
   - **Resolutions**: proposed, partially accepted, apparently accepted,
     contested, withdrawn, expired, superseded; `apparently_` is deliberate.
   - **No objective justice oracle**: no verdict/guilt/liability/true owner;
     `WorldEngine` never reads the ledger.
   - **Research-only objective alignment**: analysis may classify
     supported/unresolved/inconsistent/not applicable; agents never see it.
   - **Limits and failure behavior**: caps, truncation, disabled state, cursor
     errors.
   - **Metrics**: the three families and what each measures.
2. Update `README.md` with a `Disputes` row linking `docs/disputes.md` and
   describing owner-scoped claims, testimony, rule references, mediation,
   resolutions, `dispute-resolution-snapshot-v1`, six GET routes, and the
   Research UI panel.
3. Update `docs/architecture.md` with the V4-07 seam paragraph and the exact
   pins: 151 → 154 families, 3 owned V4 flags, unchanged replay/codec/Alembic/
   commands/semantics.
4. Update `docs/configuration.md`:
   - `legal_disputes` is owned on `runner-config-v56`;
   - no `runner-config-v57`, root field, or per-agent key;
   - `PALIMPSEST_DISPUTE_ROOT` and `PALIMPSEST_DISPUTE_CURSOR_KEY` semantics;
   - `legal_disputes` may run without `formal_rules`; rule refs are orphaned.
5. Update `docs/analysis-metrics.md` with the three family ids, exact value keys,
   populations, denominators, availability behavior, and the researcher-only
   objective alignment note.
6. Update `docs/social-communication.md` with the ten `dsp_v1` predicates,
   closed payload, delivery-only semantics, and no free-text rule.
7. Update `docs/cognition-runtime.md` with `_prepare_disputes`, owner carry,
   checkpoint, and disabled passthrough.
8. Update `docs/mediation.md` with the dispute link and the exact voluntary
   undertaking delegation.
9. Update `docs/research-api.md` with the six GET routes, `SUBJECTIVE_DEBUG`,
   `503 dispute_disabled`, `400 dispute_cursor_invalid`, `410
   dispute_cursor_expired`, and `400 dispute_size_limit`.
10. Update `docs/research-ui.md` with the Disputes panel, labels, and read-only
    behavior.
11. Update `docs/v4-architecture.md`: `legal_disputes` is implemented and owned;
    three owned flags and nine unowned; context count unchanged.
12. Update `docs/persistence.md` with `dispute-resolution-store-v1`, layout,
    quotas, atomic commit, and digest verification.
13. Update `docs/experiments.md` with the dispute harvest/publication and
    `dispute-publication-{run_id}.json` receipt.
14. Update `docs/development.md` with the focused V4-07 suite, the
    V4/organization/formal-rule regression selection, and the Research UI
    dispute commands so future sessions can reproduce the gates.
15. Update `.ai-factory/ARCHITECTURE.md`:
    - baseline table metric families 154;
    - capability ownership adds `legal_disputes`;
    - add the V4-07 seam subsection;
    - keep 14 contexts, 12 flags, 4 reservations, replay-v22/codec-v20,
      commands 43, semantics 73, Alembic 0017.
16. Update `.ai-factory/DESCRIPTION.md` with a V4-07 state paragraph and pins.
17. Do **not** edit `.ai-factory/ROADMAP.md`; `$aif-roadmap` owns it.
18. Create `tests/unit/test_dispute_docs.py`:
    - assert `docs/disputes.md` exists and contains the required sections;
    - assert the 154-family pin, three owned flags, 14/12 counts, six routes,
      `dispute_disabled`, and `dsp_v1`;
    - assert no `verdict`, `guilty`, `liable`, `winner`, `true owner`, or
      `binding settlement` claim is presented as implemented;
    - assert `legal_disputes` may run without `formal_rules` and that rule refs
      are orphaned;
    - assert the README row, `docs/development.md` command rows, and cross-links
      exist.

### Required Interfaces and Contracts

```text
docs/disputes.md
README.md
docs/architecture.md
docs/configuration.md
docs/analysis-metrics.md
docs/social-communication.md
docs/cognition-runtime.md
docs/mediation.md
docs/research-api.md
docs/research-ui.md
docs/v4-architecture.md
docs/persistence.md
docs/experiments.md
docs/development.md
.ai-factory/ARCHITECTURE.md
.ai-factory/DESCRIPTION.md
tests/unit/test_dispute_docs.py
```

Compatibility invariants:

- No documentation claims a verdict, binding settlement, court, or justice
  oracle.
- Every count matches the code.
- The roadmap remains untouched.

### Requirement Evidence

- Original Request all requirements.
- Plan Settings "Docs: yes; mandatory `$aif-docs` checkpoint."
- `docs/formal-rules.md`, `docs/mediation.md`, `docs/analysis-metrics.md`,
  `docs/research-api.md`.

### Error Handling and Logging

- Docs parity failures list the missing file/section, not private content.
- No docs example includes a real claim body, party name, or evidence id.

### Tests

Run:

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_docs.py -q`

Assertions:

- `test_disputes_doc_exists_and_covers_required_sections`
- `test_metric_family_count_is_154`
- `test_v4_owned_flag_split_is_three_and_nine`
- `test_six_routes_and_dispute_disabled_are_documented`
- `test_dsp_v1_acts_are_documented`
- `test_no_verdict_or_binding_settlement_is_claimed`
- `test_formal_rules_optional_behavior_is_documented`
- `test_readme_and_cross_links_exist`
- `test_development_matrix_lists_dispute_commands`

### Acceptance Criteria

- Documentation covers every requested capability and every limitation.
- Counts and pins match the code.
- No objective justice oracle is claimed.
- Docs parity tests pass.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_docs.py -q`
- Expected result: all tests pass.

## Task 24: Perform final V4-07 verification

### Intent

Audit the complete bundle, code, pins, receipt, and repository state before
declaring the plan implementation-ready or certified.

### Implementation Steps

1. Confirm every one of the 24 tasks is checked in `index.md` and has verified
   evidence in its phase file.
2. Re-run the focused suite, docs parity, static gates, and the required lanes
   from Task 22 if any source changed since the last run.
3. Audit exact pins:
   - `legal_disputes` owned; three owned flags; nine unowned;
   - 14 V4 contexts, 12 capability flags, `v4-context-map-v2`;
   - four write-pair reservations (events 23-26 / codecs `v21`-`v24`);
   - no `runner-config-v57` outside a negative assertion;
   - no Alembic `0018`; head `0017`;
   - replay `EVENT_SCHEMA_REPLAY_V22`, codec `v20`;
   - commands 43; observer semantic types 73; metric families 154;
   - `/v1`; `observer-protocol-v1`; no `observer-protocol-v2` serving;
   - six organization, six formal-rule, and six dispute GET routes;
   - six cursor purposes for disputes;
   - `dispute-resolution-snapshot-v1` and `dispute-resolution-store-v1`.
4. Audit the Verification Receipt: every lane is exactly one of
   `executed_passed`, `executed_failed`, `unexecuted`; any `unexecuted` carries a
   prerequisite and blocks certification.
5. Run `git status --short` and confirm:
   - no `.ai-factory/ROADMAP.md` change;
   - no branch or worktree creation;
   - only intended implementation, test, docs, and plan files are modified.
6. Run `git diff --stat` and inspect that no existing pin, test, or contract was
   weakened. The only intentional pin changes are:
   - 151 → 154 metric families;
   - six dispute routes added;
   - owned V4 flags 2 → 3.
7. Run `grep -rn "151" tests` and justify every remaining occurrence as a
   non-catalog literal (seed, tick, port, or unchanged historical text) or as a
   deliberately preserved "first 151" assertion. Every catalog count must be
   154.
8. Run `grep -rn "DisputeReadSession\|DisputeSummaryView" src tests` and confirm
   no parallel session-based read API remains; the port is run-id/filter based,
   and `DisputeSummary` is the only read summary name.
9. If implementation is complete and all required lanes pass, update the index
   Status to `implementation complete and verified` and record the certification
   outcome. If any required lane is unexecuted or failed, leave the plan
   uncertified and record the blocker.
10. Do not edit the roadmap or close M8.

### Required Interfaces and Contracts

```text
Certification outcome: certified | not certified
```

Compatibility invariants:

- No pin is weakened to obtain certification.
- No required lane is converted from skip to pass.
- The roadmap and clients remain untouched except the Research UI panel.

### Requirement Evidence

- Plan Settings and Definition of Done.
- `.ai-factory/ARCHITECTURE.md` versioned extension contract.
- `docs/development.md` lanes.

### Error Handling and Logging

- A failed audit lists the exact pin/file mismatch.
- An unexecuted lane lists its prerequisite.
- No private content is written to the receipt.

### Tests

Run the final audit commands:

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_*.py tests/architecture/test_dispute_boundaries.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_docs.py -q`
- `uv run --frozen --python 3.12.14 ruff check src tests`
- `uv run --frozen --python 3.12.14 mypy src tests`
- `uv run --frozen --python 3.12.14 lint-imports`
- `grep -rn "151" tests`
- `grep -rn "DisputeReadSession\|DisputeSummaryView" src tests`
- `git status --short`
- `git diff --stat`

Plus every required lane recorded in the Verification Receipt.

### Acceptance Criteria

- All 24 tasks are checked with evidence.
- Every pin is exact.
- The roadmap is unchanged.
- The certification outcome is truthful.
- If any required lane is unexecuted, the plan is not certified.

### Verification

- The `index.md` Verification Receipt and Status match the audit.
- Expected result: `certified` only when every required lane is
  `executed_passed`; otherwise `not certified` with a named blocker.

## Phase Risks and Mitigations

- Risk: Documentation drifts from the code.
  Mitigation: Task 23 docs parity test.
- Risk: A stale count remains in an older section.
  Mitigation: Task 23 updates every listed file and Task 24 audits the pins.
- Risk: Certification is claimed with an unexecuted lane.
  Mitigation: Task 24 three-state audit.
- Risk: The roadmap is edited by the implementation.
  Mitigation: Task 24 `git status` check.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass or are recorded with blockers.
- `index.md` task checkboxes and Verification Receipt are updated immediately
  after verified completion.
