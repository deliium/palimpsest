# Phase 5: Composition and Durable Publication

Plan: [index.md](index.md)
Tasks: 15-16
Depends on: Phase 4 / Tasks 13-14

## Objective

Compose completed-run collective-agency evidence into canonical
`organization-snapshot-v3` artifacts, record publication receipts, and extend
the atomic filesystem store to serve v1/v2/v3 with correct digests and quotas.
Publication remains opt-in, post-completion, atomic, and isolated from the
scientific result.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/organization_publication.py` | `OrganizationHarvestResult`; `_member_records`; `_structural_rows`; `_FAMILY_DOMAINS`; `_OPERATION_SOURCES`; `_draft_operation`; `_operation_records`; `_candidate_record`; `_trim_snapshot_operations`; `build_organization_harvest_result`; `_finalize`; `publish_organization_snapshot`; `organization_publication_document` | Exact composer to extend |
| `src/experiments/organization_harvest.py` | `OrganizationHarvest`, `build_completed_run_organization_harvest` | Where agency rows enter composition |
| `src/persistence/organization_filesystem.py` | `_STORE_SCHEMA` 48; `_SUPPORTED_SNAPSHOT_SCHEMAS`; `_StoredState` 96-101; `_load` 232-261; `summary` 263-287; reader methods 289-380 | Store schema and read methods |
| `src/research_runner/organization_composition.py` | `OrganizationProducerOptions` 30-48; `publish_organization_harvest` 73-135 | Opt-in CLI producer; no new flag |
| `tests/unit/test_organization_operations_publication.py` | Receipt and v2 publication tests | Test pattern |
| `tests/unit/test_organization_operations_filesystem.py` | v9 unknown-schema test 156-172 | Fail-closed pattern |
| `tests/unit/test_organization_publication.py` | v2 literal 268; duplicate publication behavior | Compatibility tests to update |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/organization_publication.py` | modify | Convert agency rows, mint published ids, trim/cap, v3 snapshot, receipt counts, provenance codes |
| `src/experiments/organization_harvest.py` | modify | Carry agency rows into the harvest result |
| `src/experiments/__init__.py` | modify | Export any new public helper |
| `src/persistence/organization_filesystem.py` | modify | v1/v2/v3 supported set, summary digest, collective-agency read method, v1/v2 empty behavior |
| `tests/unit/test_organization_agency_publication.py` | create | Composition/receipt/trim tests |
| `tests/unit/test_organization_agency_filesystem.py` | create | v1/v2/v3 store tests |

## Task 15: Compose completed-run v3 snapshots and receipts

### Intent

Turn detached agency rows into bounded publication-visible records while
stripping owner-local ids and raw actor ids. A storage/composition failure
changes only the receipt, never the scientific result.

### Implementation Steps

1. Extend `OrganizationHarvestResult` with:
   - `agency_rows: tuple[OrganizationAgencyHarvestRows, ...]`
   - `agency_summary: OrganizationAgencySummary | None`
   - receipt counts: `collective_decision_count`,
     `collective_implementation_count`, `unimplemented_decision_count`,
     `contested_decision_count`, `sabotage_attribution_count`.
2. In `build_organization_harvest_result`:
   - Accept the agency summary and rows from the completed-run harvest.
   - Require the summary to be `None` or a valid `OrganizationAgencySummary`.
   - Do not import `agents.cognition`.
3. Add `_draft_collective_decision(...)`:
   - Mint `orgcpd-` via
     `organization_publication_decision_id(organization_id, proposal_ref,
     revision, decided_tick, content_digest)`.
   - Copy only publication-visible fields: `organization_id`, `proposal_ref`,
     `revision`, `procedure_ref`, `recognition`, `authority_basis`,
     `support_count`, `oppose_count`, `abstain_count`, `contest_count`,
     `implementation_mode`, `effect`, `target_kind`, `target_ref`,
     `decided_tick`, `window_end_tick`, `implementation_status`,
     `provenance_code`, `resolved`.
   - Never copy `proposal_id`, `decision_id` (`orgcd-`), `expected_actors`, or
     raw actor ids.
4. Add `_draft_implementation(...)`:
   - Mint `orgcpi-` from the published decision id, `actor_ref`, status,
     observed tick, and content digest.
   - `actor_ref = organization_agency_ref("actor", actor_id)`; never publish the
     raw agent id.
   - Copy `status`, `effect`, `observed_tick`, `provenance_code`, `resolved`.
5. Group implementations under their decision; sort by
   `(observed_tick, actor_ref, implementation_id)`.
6. Candidate projection:
   - Add `collective_decisions` to `OrganizationCandidateRecord`.
   - Add published counts from the agency summary: proposal, amendment, support,
     oppose, abstain, decision, implementation, unimplemented, and contested.
   - Sort decisions by `(decided_tick, decision_id)`.
   - Cap at `MAX_CANDIDATE_COLLECTIVE_DECISIONS` (64) per candidate and
     `MAX_DECISION_IMPLEMENTATIONS` (32) per decision.
7. Snapshot projection:
   - Cap at `MAX_SNAPSHOT_COLLECTIVE_DECISIONS` (4096) and
     `MAX_SNAPSHOT_COLLECTIVE_IMPLEMENTATIONS` (8192).
   - When trimming, set `provenance_code=collective_agency_truncated` and keep
     the newest/deterministic rows; never drop silently.
   - Add decision/implementation counts to windows and objective rows.
8. Use `organization-snapshot-v3` for new publications. `v1`/`v2` inputs remain
   readable; the composer always produces v3.
9. Receipt:
   - Add the five counts above and `collective_agency_truncated` to
     `organization_publication_document`.
   - `status` remains `published`/`failed`/`unavailable`/`disabled`; a
     composition failure does not alter the scientific result.
   - No `run_id`, owner id, actor id, or proposal ref in the receipt.
10. `research_runner/organization_composition.py`:
    - Do not add a CLI flag or environment variable.
    - Pass the agency rows/summary through the existing opt-in producer.
    - Keep `PALIMPSEST_ORGANIZATION_ROOT`, `--organization-root`,
      `--organization-max-publications`, and `--organization-max-bytes`
      semantics unchanged.

### Required Interfaces and Contracts

- Published records contain no `orgc-`, `orgp-`, `orgpm-`, `orgcd-`, `orgci-`,
  `orgcev-`, or raw agent id.
- Published decision/implementation ids are deterministic across identical
  completed runs.
- Publication is opt-in and post-completion; it never runs inside simulation.
- A failed publication returns `failed`/`unavailable`; the scientific result and
  metrics are unchanged.
- Quotas and byte caps are unchanged; v3 records count toward the same
  `max_artifact_bytes` and `max_publications`.

### Requirement Evidence

- V4-02/V3-39/V4-03/V4-04 publication precedent.
- `.ai-factory/ARCHITECTURE.md` "Publication is opt-in and non-interfering".
- Original Request: record provenance, track implementation, no super-agent.

### Error Handling and Logging

- Composition errors raise `OrganizationArtifactError` with a closed code and
  produce a `failed` receipt.
- Log INFO `organization_agency_publication status=%s decisions=%s implementations=%s`
  (counts only); WARN on truncation with `collective_agency_truncated`.
- Never log proposal refs, actor ids, labels, or utterance text.

### Tests

Create `tests/unit/test_organization_agency_publication.py`:
- A completed run with recognized/contested/unrecognized decisions and
  implemented/refused/sabotaged/unimplemented actors produces v3.
- Published records contain no owner-local or raw actor ids.
- Deterministic ids across two identical compositions.
- Candidate/snapshot caps trim with `collective_agency_truncated`.
- Receipt counts match the snapshot.
- A failed composition changes only the receipt; the runner result and metric
  documents are unchanged.
- v1/v2 publication inputs remain readable; new output is v3.
- Duplicate publication id with different bytes leaves the existing publication
  untouched (`organization_publication_exists`).
- No new CLI flag/env var appears in `OrganizationProducerOptions`.

Extend `tests/unit/test_organization_cli.py`:
- The opt-in publication receipt includes the new agency counts.
- `--organization-root`, `--organization-max-publications`,
  `--organization-max-bytes`, `PALIMPSEST_ORGANIZATION_ROOT`, and
  `PALIMPSEST_ORGANIZATION_CURSOR_KEY` are the only organization CLI/settings
  surface; no agency-specific flag or environment variable exists.
- A failed publication receipt changes only the receipt, not the scientific
  result.

Run:
`uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_publication.py tests/unit/test_organization_publication.py tests/unit/test_organization_operations_publication.py tests/unit/test_organization_cli.py -q`

### Acceptance Criteria

- v3 composition is canonical, bounded, deterministic, and owner-local-free.
- Receipts are truthful and isolated from scientific status.
- No new CLI or environment surface exists.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_publication.py -q`
- Expected: all tests pass.

## Task 16: Extend the atomic filesystem store for v1/v2/v3

### Intent

Serve committed v1/v2/v3 publications without repair, mutation, or partial
reads; expose the publication digest for cursor binding; add the collective
agency read method.

### Implementation Steps

1. In `src/persistence/organization_filesystem.py`:
   - `_SUPPORTED_SNAPSHOT_SCHEMAS = SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS`
     (v1, v2, v3).
   - `_load` returns `(snapshot, digest)` or add `_load_with_digest`; preserve
     the existing digest verification against `state.json` and reject a
     mismatch with `organization_digest_mismatch`.
   - `summary` passes `snapshot_digest=digest`, plus the published
     proposal/amendment/support/oppose/abstain/decision/implementation/
     unimplemented counts.
2. Add `collective_agency(run_id, publication_id, offset, limit, recognition=None,
   organization_id=None)`:
   - Load the committed snapshot.
   - Reject a publication mismatch with `organization_publication_missing`.
   - Flatten decisions across candidates, filter by `recognition` and
     `organization_id`, sort by `(decided_tick, decision_id)`, and select with
     the paging helper.
   - v1/v2 snapshots have no decisions and return an empty page.
3. Keep `candidates`, `candidate`, `lineage`, and `operations` behavior
   unchanged; they now read v3 candidates with empty agency fields when absent.
4. Keep the single atomic `state.json` commit point, writer lock, quotas,
   manifest size, and child-first artifact layout unchanged.
5. Verify v1/v2 publications remain byte-verifiable and readable:
   - `summary.schema_version` is the stored version.
   - `operation_count=0` for v1, as before.
   - `collective_decision_count=0` for v1/v2.
6. In `src/simulation/organization_ports.py`, ensure the protocol signature
   exactly matches the reader method.

### Required Interfaces and Contracts

- The store never rewrites a publication to add v3 fields.
- v1/v2/v3 are all accepted; unknown versions fail closed with
  `organization_store_corrupt` or `organization_invalid_value`.
- The digest in `summary` is the SHA-256 of the exact committed snapshot bytes.
- Quotas, locks, and atomic write semantics are unchanged.
- The store imports no analysis or cognition types.

### Requirement Evidence

- V4-04 filesystem store contract.
- `.ai-factory/ARCHITECTURE.md` "Keep append-only authoritative history and
  evidence high-water boundaries".
- `src/persistence/organization_filesystem.py` 96-287.

### Error Handling and Logging

- Corrupt state/manifest → `organization_store_corrupt`.
- Digest mismatch → `organization_digest_mismatch`.
- Publication missing → `organization_publication_missing`.
- Log INFO `organization_loaded run_id=%s schema=%s decisions=%s implementations=%s`
  (counts only); never ids or payloads.

### Tests

Create `tests/unit/test_organization_agency_filesystem.py`:
- Publish a v3 snapshot; read summary/candidates/candidate/lineage/operations/
  collective-agency; counts and digest match.
- Publish v1 and v2 fixtures; they remain readable with zero agency counts and
  empty agency pages.
- Unknown `v9` fails closed.
- Tampered snapshot bytes fail with `organization_digest_mismatch`.
- Duplicate publication id with identical bytes is idempotent; different bytes
  fail with `organization_publication_exists`.
- Quota and lock behavior is unchanged.
- A v3 decision page is bounded and never splits implementations.
- `summary.snapshot_digest` round-trips to a valid cursor.

Run:
`uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_filesystem.py tests/unit/test_organization_operations_filesystem.py tests/unit/test_organization_filesystem.py -q`

### Acceptance Criteria

- The store serves v1/v2/v3 atomically and truthfully.
- The digest is available to the API for cursor binding.
- No publication is repaired or rewritten.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_filesystem.py -q`
- Expected: all tests pass.

## Phase Risks and Mitigations

- Risk: v3 publication changes existing v2 tests.
  Mitigation: v2 remains supported; tests use version-specific fixtures and
  assert v1/v2 byte stability.
- Risk: receipt fields expose owner/actor data.
  Mitigation: receipt contains counts and status only; tests scan for forbidden
  prefixes.
- Risk: the agency read method bypasses the byte budget.
  Mitigation: it uses the shared paging helper and `MAX_RESPONSE_BYTES` guard.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
