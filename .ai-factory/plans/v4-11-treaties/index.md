<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-11 Treaties and Ceasefires

Mode: ultra
Branch: main
Created: 2026-11-05

## Original Request

v4-11 treaties and ceasefires

Naming requirement:

Use `v4-11-treaties`.

Extend contracts into multi-party collective commitments.

Examples:

- ceasefire
    
- access agreement
    
- migration agreement
    
- resource sharing
    
- trade agreement
    
- territorial understanding
    
- mutual aid

Treaties must exist through:

records  
participants  
recognized representatives  
institutional memory  
agent beliefs

WorldEngine does not magically enforce them.

Later generations may:

- remember them
    
- misremember them
    
- reinterpret them
    
- ignore them
    
- renew them

Track versions and lineage.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose/browser, Godot regression, Research UI, benchmark regression, and
  static gates, with coverage enabled for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG flow/counts, INFO milestones,
  WARN unresolved references/truncation, ERROR safe codes.
  `PALIMPSEST_LOG_LEVEL` controls operational verbosity. Never log party
  references, envoy or actor identities, mandate ids, treaty/version/relation
  ids, subject tokens, provision terms, terms digests, record or
  institutional-memory anchors, frame bodies, prompts, credentials, tokens,
  DSNs, memories, embeddings, utterance bodies, labels, or payload surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 24.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-11-treaties`; the ultra bundle directory is
  `.ai-factory/plans/v4-11-treaties/`, phase files use `phase-NN-<slug>.md`,
  and `index.md` is the canonical entrypoint.
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only. No implementation, commit, roadmap edit, or branch
  creation occurs in this invocation.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-11 deepens the already-owned `diplomacy` V4 context on the
accepted `runner-config-v56` seam, adding multi-party treaty commitments,
immutable versions and lineage, recognized-representative acceptance,
later-generation recollections, record/institutional-memory anchors, detached
analysis, `diplomacy-snapshot-v2`, and two read-only routes without adding a
flag, context, runner schema, event, command, observer semantic type, write
pair, `/v2` route, or migration. This plan does not edit or close the roadmap;
`$aif-roadmap` must register V4-11 in M8 and correct the stale roadmap line that
still says nine V4 flags remain unowned beyond three.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Capability ownership", "Important V3 seams", "Versioned
Extension Contract", V4-01 through V4-10 seams) and `.ai-factory/RULES.md`
constrain every edit; `.ai-factory/DESCRIPTION.md` and `.ai-factory/ROADMAP.md`
describe current state; completed V2/V3 contact, migration, commitment,
collective-project, mediation, office, institution, collective-decision,
organization, representation, dispute, and evidence plus V4-01 through V4-10
code and `tests/architecture/test_v4_architecture_invariants.py`,
`test_diplomacy_boundaries.py`, `test_organization_*`,
`test_formal_rule_boundaries`, `test_dispute_boundaries`,
`test_evidence_testimony_boundaries`, and
`test_delegation_representation_boundaries` govern compatibility. V4-11
deepens one owned flag and creates no context.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-11 deepens `diplomacy`; no new V4 flag, `runner-config-v57`, context, runner root field, or per-agent runner key is added | Original Request "Extend contracts"; `.ai-factory/ARCHITECTURE.md` "Capability ownership"; `src/simulation/v4_architecture.py` 150-163; `src/simulation/runner_models.py` 305-325 | Task 3 tests; Task 21 pins; Task 25 `v57` absence |
| Activation remains `runner-config-v56` + `v4_capability_flags.diplomacy`; treaties are active whenever a diplomacy ledger exists | `src/agents/cognition/diplomacy.py` `DIPLOMACY_POLICY_VERSION` 111; V4-10 seam | Task 3/10 tests |
| Parties reuse the five closed V4-10 kinds: `agent`, `organization`, `settlement`, `coalition`, `unknown`; no polity, nation, civilization, border, citizenship, war, or peace object | Original Request; `docs/diplomacy.md` 36-45; `src/agents/cognition/diplomacy.py` 175-191 | Task 1/4/21 tests |
| A treaty is one owner's retained anchor with ordered participants including the owner self-party; every participant resolves locally or remains unresolved | Original Request "multi-party collective commitments"; `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts" | Task 4/8/21 tests |
| Versions are immutable, indexed, parent-linked, and forward-only; `original` starts at 1 and every other change kind has a retained parent | Original Request "Track versions and lineage"; `.ai-factory/ARCHITECTURE.md` "Preserve append-only authoritative history" | Task 4/6/12/15/21 tests |
| `ceasefire`, `access`, `migration`, `resource_sharing`, `trade`, `territorial_understanding`, and `mutual_aid` are closed subject kinds, not permissions or world states | Original Request examples | Task 1/4/21 tests |
| Terms are closed provision kinds plus a canonical `terms_digest`; no free-text ceasefire condition, access rule, quota, price, boundary, or aid text exists | Original Request; `.ai-factory/ARCHITECTURE.md` Key Principle 5 | Task 1/4/15/21 tests |
| Records appear as opaque durable-record anchors; institutional memory appears as opaque owner-local entry anchors; neither ledger is written by diplomacy | Original Request "records ... institutional memory"; `src/world/artifacts.py` 97-170; `src/agents/cognition/institutional_memory.py` 340-352 | Task 4/11/15/21 tests |
| Recognized representatives derive from the owner representation ledger; a principal declaration counts directly, an envoy needs recognized standing and covering scope, and a self-claim never counts | Original Request "recognized representatives"; `src/agents/cognition/delegation_representation.py` 103-122, 1171-1315 | Task 6/7/8/22 tests |
| `apparently_accepted` requires every participant's own declaration, with at least two participants, and binds nobody | Original Request; `.ai-factory/ARCHITECTURE.md` V4-07/V4-09/V4-10 seams | Task 6/22 tests |
| `single_act` and `occasion` mandates never cover a long-running treaty; a named scope subject must match | `src/agents/cognition/diplomacy.py` 461-489; `delegation_representation.py` 115-122 | Task 1/6/22 tests |
| A later accepted, suspended, or terminated version supersedes earlier versions; a rejected or still-proposed later version leaves the earlier accepted version active | Original Request "renew them"; `.ai-factory/ARCHITECTURE.md` append-only history | Task 6/9/22 tests |
| Termination, expiry, suspension, supersession, conflicts, and misrepresentation observations are retained rows; nothing is deleted or reconciled | Original Request; `.ai-factory/ARCHITECTURE.md` "Preserve append-only authoritative history" | Task 5/9/21 tests |
| Later-generation recollections are owner beliefs with closed basis and stance; a recollection never creates a local treaty or version | Original Request "Later generations may remember..." | Task 5/8/22 tests |
| `misremember` is researcher-only alignment (`consistent`, `unresolved`, `inconsistent`, `not_applicable`); no truth, lie, guilt, or `misremembered` field exists in cognition | Original Request "misremember them"; `.ai-factory/ARCHITECTURE.md` "analysis is read-only" | Task 13/21/22 tests |
| `trt_v1` frames travel only inside existing `Talk`/`Ask`/`Tell`; 22 fields bounded at 832 characters and carried as at most four ordered relation chunks; a verified speaker must match the claimed envoy | `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts"; `diplomacy_communication.py` 60-320; `world/communications.py` 50-137 | Task 7/8/21/22 tests |
| Peer-supplied provenance, mandate, record, or institutional-memory refs are claims; provenance is assigned from delivery and mandates resolve locally | V4-10 speech trust rules; `.ai-factory/ARCHITECTURE.md` "anti-patterns" | Task 7/8/21 tests |
| `WorldEngine`, perception, admission, stop selectors, memory, prompts, observer semantics, and Godot never read a treaty or diplomacy ledger | Original Request "WorldEngine does not magically enforce them"; `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime" | Task 21/22 tests |
| No treaty helper constructs, submits, resolves, or executes an `AgentCommand`; every physical effect remains ordinary admission | `.ai-factory/ARCHITECTURE.md` "anti-patterns" | Task 21/22 tests |
| Detached analysis keeps objective counts, owner-token rows, and analytical candidates in three separate types with a hard leakage guard | `.ai-factory/ARCHITECTURE.md` Key Principle 1; `src/analysis/diplomacy_layers.py` 71-100 | Task 11/21 tests |
| Treaty analysis joins `org-`/`msoc-` identities read-only and never mints, renames, splits, merges, or dissolves them | `.ai-factory/ARCHITECTURE.md` "analysis is read-only"; `src/analysis/diplomacy_identity.py` 186-226 | Task 12/21 tests |
| Four metric families append (`treaty_structure@1`, `treaty_version_lineage@1`, `treaty_recollection@1`, `treaty_anchor_coverage@1`), raising the catalog 164 -> 168; the first 164 keep id, order, version, and value keys | Original Request "Track versions and lineage"; `src/analysis/specifications.py` 53, 7380-7762 | Task 14/21/24 tests |
| `diplomacy-snapshot-v2` is canonical and bounded; v2 treaty/version rows carry composer-derived status labels; `diplomacy-snapshot-v1` remains decodable and byte-verifiable; `diplomacy-store-v1` remains the store schema | `.ai-factory/ARCHITECTURE.md` "Use accepted-set and exact-key-set schema evolution"; V4-04/V4-05 snapshot precedent | Task 15/17/18/21 tests |
| Two GET routes (`/diplomacy/treaties`, `/diplomacy/treaties/{treaty_id}`) join the six V4-10 routes for eight total; all require `SUBJECTIVE_DEBUG`, return 503 `diplomacy_disabled`, and 404 for unknown published records | `docs/research-api.md` 242-256; `src/api/routes/diplomacy.py` 180-343 | Task 19/21/22 tests |
| Cursors bind run, publication, digest, purpose, and filters; mismatch is 400 and expiry 410 | `src/simulation/diplomacy_ports.py` 96-156; `src/api/diplomacy_cursor.py` | Task 16/19/22 tests |
| Publication is opt-in, post-completion, atomic, quota-bounded, and isolated from scientific status; v1 and v2 coexist | `src/experiments/diplomacy_publication.py` 327-414; `src/persistence/diplomacy_filesystem.py` 83-202 | Task 17/18/22 tests |
| The treaty E2E runs in-process in the focused/unit lane with real ticks, speech, recognition, publication, and all eight routes; it is never reported as integration-only | Plan Settings; `pyproject.toml` test markers; `tests/unit/test_diplomacy_e2e.py` | Task 22/23 tests |
| No SQL migration, new event, command, observer semantic type, write pair, `/v2` route, or `observer-protocol-v2` is added | `.ai-factory/ARCHITECTURE.md` requirements 4-6; `src/simulation/versioning.py` 39-90 | Task 21/25 pins |
| Every current 164 pin is swept to 168; historical revision statements and the first-154 digest remain unchanged | `src/analysis/specifications.py:53`; 77 `== 164` occurrences in tests plus current doc prose lines measured at plan time | Task 14 sweep and guard; Task 24 re-run |
| The roadmap is owned by `$aif-roadmap` and is not edited here | `.ai-factory/ARCHITECTURE.md` requirement 7 | Task 24/25 `git status` |

### Supported combinations and availability transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| Default runner config, all V4 flags off | V4-10-equivalent behavior | No diplomacy or treaty ledger, metric, publication, or route data | Task 3/10/22 tests |
| `diplomacy` enabled on v4 or v55 | Unchanged config | `v4_capability_requires_v56` before construction | Task 3 test |
| `diplomacy` enabled on v56 | Valid run | Diplomacy and treaty beliefs active | Task 3/10 test |
| `organizations` alone | Valid run | No diplomacy or treaty ledger | Task 3 test |
| `formal_rules` or `legal_disputes` alone | Valid run | Diplomacy stays disabled | Task 3 test |
| `diplomacy` with `organizations` off | Valid run | Agent/settlement parties work; organization/coalition anchors stay unresolved | Task 3/8 test |
| `organized_conflict` or another unowned flag | No behavior change | Still fails closed with `capability_unimplemented` | Task 3/21 test |
| Owner proposes a two-party treaty | Treaty anchor + version 1 | `proposed` until every participant declares | Task 4/6/8 test |
| Three-party treaty, all principals accept | Version 1 | `apparently_accepted`; binds nobody | Task 6/22 test |
| One principal missing | Version 1 | Stays `proposed` | Task 6/22 test |
| Recognized envoy with `negotiate`/`until_revoked` accepts | Declaration counts | Party completes | Task 6/22 test |
| Self-claim envoy accepts | Declaration retained | Party does not complete; misrepresentation retained | Task 6/9/22 test |
| `single_act` or `occasion` mandate accepts | Declaration retained | No party completion; `scope_exceeded` | Task 6/9 test |
| One participant rejects | Version 1 | `proposed` status + `rejected` acceptance basis; no acceptance | Task 6/9 test |
| All participants terminate | Version 1 | `terminated`; retained | Task 6/9 test |
| All participants suspend | Version 1 | `suspended`; retained | Task 6/9 test |
| `end_tick` boundary | Expiry | `expired` when `tick >= end_tick`; termination row | Task 9 test |
| Accepted renewal version on the same treaty | Version 2 | Version 1 `superseded`; lineage edge; two versions retained | Task 6/9/22 test |
| Rejected renewal version | Version 2 | Version 1 stays `apparently_accepted` | Task 6/9 test |
| Accession version | Version 2 | Participant added; anchor union retained | Task 6/8 test |
| Withdrawal version | Version 2 | Another participant removed; owner withdrawal creates a termination version; if fewer than two non-owner participants remain, termination | Task 6/8 test |
| Two treaties on the same relation/subject | Two anchors | Both may be accepted; no reconciliation | Task 6/9 test |
| Later-generation record recollection with matching digest | Recollection | `remember`; analysis `consistent` | Task 8/13/22 test |
| Later-generation recollection with different digest | Recollection | `remember`; analysis `inconsistent`; no truth verdict | Task 13/22 test |
| Recollection with absent treaty/version | Recollection | `unresolved`; no invented local treaty | Task 5/13 test |
| Recollection stance `interpret` | Recollection | `reinterpret`; version unchanged | Task 5/13 test |
| Recollection stance `ignore` | Recollection | `ignore`; no enforcement | Task 5/13 test |
| Recollection stance `renew` | Recollection + later version | Renewal proposal; acceptance still required | Task 5/6/22 test |
| Non-participant receives a treaty proposal | Recollection only | No local treaty or version | Task 8/22 test |
| Organization/coalition anchor with owned `orgc-` concept | Resolved participant | Anchor retained; envoy standing independent | Task 8 test |
| Settlement anchor with visible region | Resolved participant | Region anchor retained | Task 8 test |
| Missing anchor | Unresolved participant | `unresolved`; no invented collective/place | Task 8/11 test |
| Durable-record or institutional-memory anchor | Opaque anchor | Counted in analysis; no content published | Task 4/11/15 test |
| Cap exceeded with droppable recollections | Truncation | `diplomacy_truncated:treaty_recollections`; deterministic | Task 9 test |
| Cap exceeded with nothing droppable | Capacity error | `diplomacy_capacity_reached` or `treaty_capacity_reached` | Task 9 test |
| Snapshot exceeds 4 MiB or row caps | No publication | `diplomacy_size_limit` | Task 15/17 test |
| Duplicate publication id with different bytes | Existing artifact untouched | `diplomacy_publication_exists` | Task 18 test |
| `PALIMPSEST_DIPLOMACY_ROOT` unset | API state unset | 503 `diplomacy_disabled`; CLI receipt `disabled` | Task 18/19/22 test |
| Cursor reused with same binding | Same page | 200; digest matches | Task 16/19 test |
| Cursor reused after any binding change | No page served | 400 `diplomacy_cursor_invalid`; expired 410 | Task 16/19 test |
| Run incomplete or publication failed | Scientific result unchanged | Receipt `unavailable`/`failed` only | Task 17/18/22 test |
| In-process treaty E2E without PostgreSQL | No integration prerequisite | Runs in the focused/unit lane with real ticks, speech, recognition, publication, and routes | Task 22/23 test |
| Required Compose/browser/Godot/benchmark/UI lane with a missing prerequisite | No green certification | Recorded `unexecuted` with prerequisite | Task 23/25 |

No blocking open questions: every material decision is fixed below.

## Architecture and Decisions

1. **One owned context, one additive extension.** V4-11 deepens `diplomacy` and
   adds no V4 flag, context, `runner-config-v57`, runner root field, or
   per-agent runner key. Activation is `runner-config-v56` +
   `v4_capability_flags.diplomacy`.
2. **Treaties are beliefs, not instruments.** A `DiplomaticTreaty` anchor groups
   participants and versions; it is not a global treaty store, court, war
   state, or objective agreement.
3. **Parties are representation principals.** The five V4-10 kinds are the
   only kinds; the owner self-party is first. Macro-society `msoc-` identities
   are analysis-only joins and never become treaty parties.
4. **Versions are immutable and parent-linked.** Version indices are contiguous
   from 1; `original` has no parents; every other change kind has at least one
   lower-index parent.
5. **Change kinds are closed.** `original`, `amendment`, `renewal`, `accession`,
   `withdrawal`, `suspension`, `termination`; no free-form amendment.
6. **Acceptance is every participant's own declaration.** A principal counts
   directly; a recognized envoy with covering scope counts for its party; an
   envoy never binds; `apparently_accepted` binds nobody.
7. **Supersession follows collective decision.** A later accepted, suspended,
   or terminated version supersedes earlier versions; a rejected or still-
   proposed later version does not.
8. **Records and institutional memory are anchors.** Durable records and
   institutional-memory entries are referenced by opaque, bounded IDs; V4-11
   never writes either ledger.
9. **Terms are closed.** Provision kinds plus a canonical digest; no free-text
   ceasefire condition, access rule, quota, price, boundary, or aid demand.
10. **Recollection is owner-scoped.** Later generations hold recollections with
    basis and stance; a recollection cannot create a local treaty or version.
11. **Misremember is researcher-only.** Alignment compares a claimed digest to
    a retained version digest; no truth/lie/guilt field exists in cognition.
12. **Speech is the only claim channel.** `trt_v1` travels in existing
    `Talk`/`Ask`/`Tell` as at most four ordered chunk relations; the verified
    speaker must match the claimed envoy.
13. **Peer claims are untrusted.** Peer provenance, mandate, record, and
    institutional-memory refs are claims; the receiver assigns provenance and
    resolves mandates locally.
14. **The update pipeline is ordered.** append -> derive -> detect treaty
    misrepresentation -> expire -> supersede -> detect conflicts -> enforce
    limits.
15. **Derived rows are content-addressed and deduplicated.**
16. **Termination is explicit and retained.** Withdrawal, suspension,
    termination, expiry, and supersession append rows; nothing is deleted.
17. **Conflicts coexist.** Duplicate versions, contradictory participants,
    record conflicts, and recollection conflicts are retained and never
    reconciled.
18. **No command path.** No treaty helper constructs, submits, resolves, or
    executes an `AgentCommand`; every physical effect remains ordinary
    admission.
19. **No enforcement anywhere.** Ceasefires do not block attacks; access
    agreements grant no access; trade agreements move nothing; territorial
    understandings change no boundary; mutual aid performs no aid.
20. **Detached analysis keeps three layers.** Objective counts, owner-token
    rows, and analytical candidates are separate; leakage is a hard failure.
21. **Identity joins are read-only.** `org-` and `msoc-` identities are joined,
    never minted, renamed, split, merged, or dissolved.
22. **Four families append.** 164 -> 168; the first 164 keep id, order,
    version, and value keys; no composite or bilateral score exists.
23. **A new snapshot, not a rewrite.** `diplomacy-snapshot-v2` is canonical;
    v1 remains decodable and byte-verifiable; `diplomacy-store-v1` is unchanged.
24. **Two new GET routes.** Eight diplomacy GET routes total; all require
    `SUBJECTIVE_DEBUG`; disabled/404/cursor semantics match V4-10.
25. **Publication is opt-in and non-interfering.** A storage or composition
    failure changes only the receipt, never the scientific result.
26. **The UI is read-only.** It renders tokens, versions, lineage,
    declarations, and recollections; it derives no authority, legitimacy,
    enforcement, score, or winner.
27. **No new wire surface.** No event, codec marker, command, observer semantic
    type, write pair, `/v2` route, `observer-protocol-v2`, or SQL migration.
28. **Deterministic by construction.** Sorted ordering, content-addressed IDs,
    canonical JSON digests, quantized ratios, integer counts, no `hash()`, no
    UUID, and no wall-clock domain values.
29. **Pin sweeps distinguish current from historical.** Current pins move to
    168 and eight diplomacy routes; historical revision statements and the
    first-154 digest keep their original numbers.
30. **No automatic generalization.** V4-11 implements no organized conflict,
    infrastructure, supply chain, market, credit, science, epidemic,
    ecological, disaster, resilience, or macro-society behavior.

### Compatibility pins

Default runner/result `v4`/`v2`; latest feature runner `v55`; accepted runner
adds `v56` only; events `EVENT_SCHEMA_REPLAY_V22` (22); codec `v20`; commands
43; observer semantic types 73; metric families **168 (V4-11 change)**; Alembic
`0017` with no `0018`; `/v1`; `observer-protocol-v1`; observer layout
`observer-layout-v1`; observer capabilities 4 advertised / 6 reserved; four
reserved write pairs (events 23-26 / codecs `v21`-`v24`);
`prepare_parallel=False`; six GET organization, six GET formal-rule, six GET
dispute, six GET evidence, six GET representation, and **eight GET diplomacy**
routes; eight cursor purposes per diplomacy context; snapshots
`organization-snapshot-v1`/`v2`/`v3`, `formal-rule-snapshot-v1`,
`dispute-resolution-snapshot-v1`, `evidence-testimony-snapshot-v1`,
`delegation-representation-snapshot-v1`, `diplomacy-snapshot-v1`/`v2`; stores
`organization-store-v1`, `formal-rule-store-v1`,
`dispute-resolution-store-v1`, `evidence-testimony-store-v1`,
`delegation-representation-store-v1`, and `diplomacy-store-v1`; 14 V4 contexts
/ 12 flags / **4 owned flags** (`organizations`, `formal_rules`,
`legal_disputes`, `diplomacy`) / **8 unowned** (`organized_conflict`,
`infrastructure_networks`, `supply_chains`, `markets_credit`, `science`,
`epidemics`, `ecological_feedback`, `disasters`). The other capability sets
still hold `institutional_economy` and `multi_hop_testimony_tracking` unowned;
they are not part of the 12 V4 flags. `/version` is unchanged;
`organization_rows` remains reserved.

## Phase Index

1. [Phase 1: Treaty Contract and Seam](phase-01-treaty-contract-and-seam.md) — Tasks 1-3
2. [Phase 2: Owner-Scoped Treaty Beliefs](phase-02-treaty-beliefs.md) — Tasks 4-10
3. [Phase 3: Detached Analysis, Candidates, and Metrics](phase-03-detached-analysis.md) — Tasks 11-14
4. [Phase 4: Diplomacy Snapshot v2](phase-04-snapshot-v2.md) — Tasks 15-16
5. [Phase 5: Composition and Durable Publication](phase-05-composition-publication.md) — Tasks 17-18
6. [Phase 6: Read-Only API and Research UI](phase-06-read-only-surfaces.md) — Tasks 19-20
7. [Phase 7: Invariants, End-to-End Treaty, and Regression](phase-07-invariants-and-regression.md) — Tasks 21-23
8. [Phase 8: Documentation and Final Verification](phase-08-docs-and-verification.md) — Tasks 24-25

## Cross-Phase Dependencies

- All phases assume the completed V2/V3 contact, migration, commitment,
  collective-project, mediation, office, institution, collective-decision, and
  organization stacks plus V4-01 through V4-10; V4-11 does not rewrite them, but
  Tasks 21/23 must keep their suites green.
- Task 2 depends on Task 1: the locked policy uses the frozen vocabulary.
- Task 3 depends on Tasks 1-2: activation tests consume the contract and policy.
- Task 4 depends on Tasks 2-3: rows use the policy, IDs, and ledger seam.
- Task 5 depends on Task 4: declarations/recollections extend the same ledger.
- Task 6 depends on Tasks 4-5: status derives from versions and declarations.
- Task 7 depends on Task 5: `trt_v1` encodes the record vocabulary.
- Task 8 depends on Tasks 6-7: collection consumes frames, status, and anchors.
- Task 9 depends on Task 8: expiry/supersession/conflicts/caps consume collected
  state.
- Task 10 depends on Tasks 4-9: carry needs the complete ledger.
- Task 11 depends on Task 10: harvest reads exported ledgers.
- Task 12 depends on Task 11: candidates/lineage consume harvested rows.
- Task 13 depends on Tasks 11-12: alignment consumes rows and versions.
- Task 14 depends on Tasks 11-13: metrics consume rows, lineage, and alignment.
- Task 15 depends on Tasks 9 and 11-14: snapshot mirrors derived state and
  metric provenance.
- Task 16 depends on Task 15: paging and ports select typed rows.
- Task 17 depends on Tasks 9, 10, 14, and 16: the composer derives statuses and
  analysis at publication time.
- Task 18 depends on Tasks 15-17: the store serves v1/v2 and the CLI calls the
  composer.
- Task 19 depends on Task 18: the API reads the committed store.
- Task 20 depends on Task 19: the panel consumes the new routes.
- Task 21 depends on Tasks 2-20: the suite asserts every authority claim.
- Task 22 depends on Tasks 8-20: the E2E uses real ticks, speech, recognition,
  publication, and routes.
- Task 23 depends on Tasks 21-22: regression runs after invariant/E2E gates.
- Task 24 depends on Tasks 2-23: documentation describes verified surfaces.
- Task 25 depends on Tasks 23-24: final certification needs receipts and docs.

## Tasks

### Phase 1: Treaty Contract and Seam
- [x] Task 1: Freeze the treaty vocabulary and identifier grammar ([details](phase-01-treaty-contract-and-seam.md#task-1-freeze-the-treaty-vocabulary-and-identifier-grammar))
- [x] Task 2: Add the locked treaty policy ([details](phase-01-treaty-contract-and-seam.md#task-2-add-the-locked-treaty-policy)) (depends on 1)
- [x] Task 3: Confirm treaty activation on the owned diplomacy flag ([details](phase-01-treaty-contract-and-seam.md#task-3-confirm-treaty-activation-on-the-owned-diplomacy-flag)) (depends on 1, 2)

### Phase 2: Owner-Scoped Treaty Beliefs
- [x] Task 4: Define treaty and version records with record and institutional anchors ([details](phase-02-treaty-beliefs.md#task-4-define-treaty-and-version-records-with-record-and-institutional-anchors)) (depends on 2, 3)
- [x] Task 5: Define treaty declarations recollections and terminations ([details](phase-02-treaty-beliefs.md#task-5-define-treaty-declarations-recollections-and-terminations)) (depends on 4)
- [x] Task 6: Derive treaty version status and representative acceptance ([details](phase-02-treaty-beliefs.md#task-6-derive-treaty-version-status-and-representative-acceptance)) (depends on 4, 5)
- [x] Task 7: Add bounded trt_v1 treaty speech frames ([details](phase-02-treaty-beliefs.md#task-7-add-bounded-trt_v1-treaty-speech-frames)) (depends on 5)
- [x] Task 8: Collect treaty frames and reconcile local treaty state ([details](phase-02-treaty-beliefs.md#task-8-collect-treaty-frames-and-reconcile-local-treaty-state)) (depends on 6, 7)
- [x] Task 9: Detect recollection conflicts expiry supersession and caps ([details](phase-02-treaty-beliefs.md#task-9-detect-recollection-conflicts-expiry-supersession-and-caps)) (depends on 8)
- [x] Task 10: Carry treaty rows through the ledger digest and runtime ([details](phase-02-treaty-beliefs.md#task-10-carry-treaty-rows-through-the-ledger-digest-and-runtime)) (depends on 4-9)

### Phase 3: Detached Analysis, Candidates, and Metrics
- [x] Task 11: Harvest treaty rows and keep three layers separate ([details](phase-03-detached-analysis.md#task-11-harvest-treaty-rows-and-keep-three-layers-separate)) (depends on 10)
- [x] Task 12: Extend candidates lineage and read-only identity joins ([details](phase-03-detached-analysis.md#task-12-extend-candidates-lineage-and-read-only-identity-joins)) (depends on 11)
- [x] Task 13: Classify researcher-only treaty recollection alignment ([details](phase-03-detached-analysis.md#task-13-classify-researcher-only-treaty-recollection-alignment)) (depends on 11, 12)
- [x] Task 14: Add four metric families and raise the catalog to 168 ([details](phase-03-detached-analysis.md#task-14-add-four-metric-families-and-raise-the-catalog-to-168)) (depends on 11-13)

### Phase 4: Diplomacy Snapshot v2
- [x] Task 15: Define diplomacy-snapshot-v2 and preserve v1 decoding ([details](phase-04-snapshot-v2.md#task-15-define-diplomacy-snapshot-v2-and-preserve-v1-decoding)) (depends on 9, 11-14)
- [x] Task 16: Add treaty paging ports and cursor purposes ([details](phase-04-snapshot-v2.md#task-16-add-treaty-paging-ports-and-cursor-purposes)) (depends on 15)

### Phase 5: Composition and Durable Publication
- [x] Task 17: Compose completed-run treaty views and receipts ([details](phase-05-composition-publication.md#task-17-compose-completed-run-treaty-views-and-receipts)) (depends on 9, 10, 14, 16)
- [x] Task 18: Extend the filesystem store and CLI producer ([details](phase-05-composition-publication.md#task-18-extend-the-filesystem-store-and-cli-producer)) (depends on 15-17)

### Phase 6: Read-Only API and Research UI
- [x] Task 19: Add GET treaty routes schemas and app wiring ([details](phase-06-read-only-surfaces.md#task-19-add-get-treaty-routes-schemas-and-app-wiring)) (depends on 18)
- [x] Task 20: Add the read-only Research UI treaties view ([details](phase-06-read-only-surfaces.md#task-20-add-the-read-only-research-ui-treaties-view)) (depends on 19)

### Phase 7: Invariants, End-to-End Treaty, and Regression
- [x] Task 21: Add the treaty boundary and determinism suite ([details](phase-07-invariants-and-regression.md#task-21-add-the-treaty-boundary-and-determinism-suite)) (depends on 2-20)
- [x] Task 22: Add the treaty end-to-end scenario ([details](phase-07-invariants-and-regression.md#task-22-add-the-treaty-end-to-end-scenario)) (depends on 8-20)
- [x] Task 23: Execute the full V1-V4 regression and qualification lanes ([details](phase-07-invariants-and-regression.md#task-23-execute-the-full-v1-v4-regression-and-qualification-lanes)) (depends on 21, 22)

### Phase 8: Documentation and Final Verification
- [x] Task 24: Execute the documentation checkpoint ([details](phase-08-docs-and-verification.md#task-24-execute-the-documentation-checkpoint)) (depends on 2-23)
- [x] Task 25: Perform final V4-11 verification ([details](phase-08-docs-and-verification.md#task-25-perform-final-v4-11-verification)) (depends on 23, 24)

## Verification Receipt (Tasks 23 and 25)

To be completed by Task 23 and audited by Task 25. Every required lane must be
recorded as exactly one of `executed_passed`, `executed_failed`, or
`unexecuted`. An `unexecuted` lane carries its missing prerequisite and blocks
certification; it is never a skip-pass. Initial planning state is `unexecuted`
for every lane because nothing has run yet.

| Lane | State | Evidence |
| --- | --- | --- |
| Python unit + architecture with coverage | unexecuted | Full coverage run stopped at 31% after ~12 minutes; the same suite without coverage passed (9,040 passed). |
| Focused V4-11 suite | executed_passed | `pytest tests/unit/test_diplomacy_treaty_*.py tests/architecture/test_treaty_boundaries.py tests/architecture/test_diplomacy_boundaries.py -q` — 239 passed; the last test additions passed in a focused 26-test run. |
| Focused in-process treaty E2E | executed_passed | `pytest tests/unit/test_diplomacy_treaty_e2e.py -q` — 8 passed in the focused lane without PostgreSQL; real engine ticks, `Talk` delivery of chunked `trt_v1`, recognized representative, real durable-record and institutional-memory anchors, publication, and all eight GET routes. |
| V1/V2/V3/V4 regression selection | executed_passed | Included in the full unit+architecture run (9,040 passed), including V1 gate, V2 invariants, V4 registry, organization, formal-rule, dispute, evidence, representation, and diplomacy suites. |
| Documentation parity | executed_passed | `pytest tests/unit/test_diplomacy_docs.py tests/unit/test_treaty_docs.py tests/unit/test_diplomacy_treaty_catalog.py -q` — 17 passed; current pins 168, eight routes, v2/v1 documented. |
| Ruff | executed_passed | `uv run ruff check src tests` — all checks passed. |
| Mypy | executed_passed | `uv run mypy src tests` — success, 2,077 files checked. |
| Import-linter | executed_passed | `uv run lint-imports` — 25 contracts kept, 0 broken. |
| Integration (`-m "integration and not scale"`) | executed_passed | 106 passed against disposable `pgvector/pgvector:pg17` with `PALIMPSEST_TEST_DATABASE_URL=.../palimpsest_test`. |
| Integration including scale | unexecuted | Requires a disposable PostgreSQL/pgvector instance and the long-run harness. |
| Docker Compose config | executed_passed | `docker compose config --quiet` — exit 0. |
| Compose/browser acceptance | unexecuted | Attempted with a source-built image; generational browser setup requires a source-attested image (`source_assertion_missing`), and the dirty working tree cannot honestly attest a clean source. |
| Godot 4.7.2 regression | executed_passed | Pinned Godot 4.7.2 headless protocol suite — `godot_protocol_tests failed=0`. |
| Benchmark/scale lane | unexecuted | Requires the multi-hour harness. |
| Research UI tests | executed_passed | `pnpm test` (10.34.9 via npx) — 275 passed across 54 files. |
| Research UI type/static checks | executed_passed | `pnpm check` — 0 errors, 0 warnings. |
| Research UI build | executed_passed | `pnpm build` — production build complete; `research_ui_build_ok file_count=5`. |

Certification outcome: **not certified** — coverage, integration-scale, Compose/browser, and benchmark/scale lanes remain `unexecuted` with their prerequisites. All executed lanes passed.

## Commit Plan

Proposed implementation checkpoints; no commit is made by planning.

1. After Tasks 1-3: `feat(v4): freeze the treaty contract and policy`
2. After Tasks 4-7: `feat(v4): define owner-scoped treaty records and frames`
3. After Tasks 8-10: `feat(v4): collect and recognize treaties without authority`
4. After Tasks 11-14: `feat(v4): analyze treaty versions and recollection`
5. After Tasks 15-18: `feat(v4): publish diplomacy-snapshot-v2`
6. After Tasks 19-20: `feat(v4): serve read-only treaty surfaces`
7. After Tasks 21-25: `test(v4): enforce treaty invariants and certify`

## Blocking Conditions and Non-Goals

- Adding a new V4 flag, `runner-config-v57`, a new context, a runner root field,
  or a per-agent runner key to make this plan work is a blocking scope
  violation. Stop and re-plan.
- Claiming `organized_conflict`, `infrastructure_networks`, `supply_chains`,
  `markets_credit`, `science`, `epidemics`, `ecological_feedback`, `disasters`,
  `institutional_economy`, or `multi_hop_testimony_tracking` is forbidden.
- Creating a `TreatyStore`, `TreatyAuthority`, `TreatyRegistry`,
  `TreatyExecutor`, `CeasefireState`, `WarState`, `ArmyActor`, `Polity`,
  `Border`, `Citizenship`, `LegitimacyOracle`, `TruthEngine`, `RelationScore`,
  or binding agreement is forbidden.
- Computing, storing, publishing, or rendering a bilateral relationship score,
  valence, rank, trust value, composite index, legitimacy score, or "overall
  relation" is forbidden.
- Letting `WorldEngine`, perception, admission, stop selectors, memory, prompts,
  observer semantics, or the Godot client read a treaty or diplomacy ledger is
  forbidden.
- Letting a treaty helper return, construct, submit, or resolve an
  `AgentCommand`, move a resource, execute a physical action, block a command,
  or grant access is forbidden.
- Treating treaty acceptance, recognized representation, or scope as
  permission, prohibition, legitimacy, authenticity, truth, guilt, liability,
  enforcement, or a binding finding is forbidden.
- Inferring a treaty, participant, declaration, recollection, or acceptance
  from silence, an unobserved act, or another owner's ledger is forbidden.
- Treating a peer-supplied frame `provenance`, `mandate_ref`, `record_ref`, or
  institutional-memory ref as trusted is forbidden.
- Publishing raw agent IDs, free-text subjects, provision terms, frame bodies,
  record content, or institutional-memory content instead of hashed tokens,
  content-addressed IDs, and opaque anchors is forbidden.
- Reading a peer owner's relationship, reputation, commitment, rule, office,
  institution, organization, decision, dispute, evidence, representation, or
  institutional-memory ledger to evaluate a treaty is forbidden.
- Reconciling conflicting versions, participants, records, recollections, or
  treaties into one authoritative treaty is forbidden. Analysis may classify
  recollection alignment for researchers only.
- Minting, renaming, splitting, merging, or dissolving `org-` or `msoc-`
  identities from treaty analysis is forbidden.
- Adding a new event, command, observer semantic type, write pair, artifact
  kind, wire record genre, `/v2` route, `observer-protocol-v2` serving, or SQL
  migration is forbidden. Treaty rows are owner beliefs inside the existing
  snapshot/persistence seam, not new wire genres.
- Rewriting the V4-10 diplomacy contract, `dip_v1` frame, `diplomacy.v1`
  policy, `diplomacy-snapshot-v1`, or `diplomacy-store-v1` is forbidden; v2 is
  additive.
- Weakening an existing pin or assertion (catalog counts, Alembic `0017`,
  replay v22, codec v20, command count, observer semantic count, context count)
  is forbidden. The only intentional pin changes are 164 -> 168 metric families,
  the four treaty families, the two additional diplomacy GET routes, and the
  new v2 snapshot schema.
- Claiming prevalence, emergence probability, predictive power, accuracy,
  reliability of treaties in general, moral correctness, or a composite
  legitimacy score is forbidden.
- Editing `.ai-factory/ROADMAP.md` or closing M8 is out of scope;
  `$aif-roadmap` owns that.
- Changing the Godot client, observer protocol, observer capabilities, or
  `/version` is out of scope; the Research UI is the only client change.
- Enabling V4 flags in matrix lanes is out of scope; `experiments.matrix_schema`
  keeps its rejection gate.
- V4-11 does not add a command selector, prompt, or speech-generation bias.
  Treaties are beliefs; a later plan that lets them bias behavior must be
  separately owned.
- Full qualification requires a disposable PostgreSQL/pgvector instance,
  Docker, a real browser driver, and the pinned Node/pnpm and Godot toolchains.
  A missing prerequisite leaves the lane unexecuted and blocks certification;
  it never becomes a skip-pass.
- Do not implement any other V4 context in this plan.

## Definition of Done

- All 25 indexed tasks have verified completion evidence; only this index holds
  task progress checkboxes.
- `diplomacy` remains the only relevant owned flag; no `v57`, new flag,
  context, root field, or per-agent runner key exists; `organized_conflict`
  remains unowned and fail-closed.
- The context registry validates at 14 contexts, 12 flags,
  `v4-context-map-v2`, and four owned flags.
- A multi-party treaty contract exists with seven requested subject kinds plus
  closed `unknown`, seven requested change kinds plus closed `unknown`, closed
  statuses/acts/provisions/recollection bases/stances, ordered participants with
  the owner self-party, immutable versions, parent-linked lineage, retained
  declarations, recollections, misrepresentation observations, terminations,
  conflicts, and bounded caps.
- Every treaty/version/declaration/parent-link reference resolves inside the
  ledger; recollections may reference absent records but never invent one.
- `ceasefire`, access, migration, resource sharing, trade, territorial
  understanding, and mutual aid are owner beliefs, not world states or
  permissions.
- Records and institutional memory appear only as opaque anchors; diplomacy
  never writes either ledger.
- Recognized representatives are derived from the owner representation ledger;
  principals count directly, recognized envoys need covering scope, self-claims
  never count, one actor cannot satisfy two parties, and
  `apparently_accepted` binds nobody.
- `single_act` and `occasion` mandates never complete a treaty party; a named
  scope subject must match.
- Later accepted, suspended, or terminated versions supersede earlier versions;
  rejected or still-proposed renewals leave the earlier version active; two
  treaties may coexist.
- Recollections support remember, reinterpret, ignore, and renew; misremember
  is researcher-only `consistent`/`unresolved`/`inconsistent`/
  `not_applicable`; no truth/lie/guilt/enforcement field exists.
- `trt_v1` is bounded at 22 fields and 832 characters, carried as at most four
  ordered chunk relations; `dip_v1` remains 15 fields and 320 characters;
  peer provenance and mandates are untrusted.
- The ordered pipeline is append -> derive -> detect misrepresentation -> expire
  -> supersede -> detect conflicts -> enforce limits, with content-addressed
  dedupe.
- Caps retain treaties/versions/accepted declarations/parent links; only
  recollections are age-droppable; otherwise fail closed.
- Detached analysis harvests token-only treaty rows, keeps three layers
  separate, derives version lineage, joins `org-`/`msoc-` read-only, and
  classifies recollection alignment for researchers only.
- The metric catalog is exactly 168 with four appended families; the first 164
  are unchanged; real completed-run assembly emits all four documents.
- No test file or current-pin doc line still asserts 164; the stale-pin guard
  passes while historical revision statements and the first-154 digest remain.
- `diplomacy-snapshot-v2` and `diplomacy-store-v1` are canonical, bounded,
  atomic, and immutable after publication; v2 treaty/version rows carry
  composer-derived status labels; v1 snapshots remain decodable and
  byte-verifiable.
- Snapshot rows and API responses contain only hashed tokens, content-addressed
  record IDs, opaque anchors, and composer-derived status labels; no raw agent
  id, free-text subject, terms, record content, or frame body is published.
- Eight GET-only diplomacy routes require `SUBJECTIVE_DEBUG`, have an explicit
  `diplomacy_disabled` state, return 404 for unknown published records, and are
  consumed by a read-only Research UI view that derives no authority,
  legitimacy, enforcement, score, or winner.
- Cursor reuse works on treaty pages; a changed run/publication/digest/purpose/
  filter fails with 400 and expiry with 410.
- `WorldEngine` never reads a treaty ledger; a ceasefire or access treaty does
  not block a physically possible command, and a physically impossible command
  is still rejected by existing world rules.
- The boundary suite proves owner-only authority, the absence of
  score/legitimacy/treaty-registry/enforcement/war-state objects, no command
  construction, no peer-ledger reads, no world-ledger reads, and no
  `org-`/`msoc-` mutation; no new commands/events/migrations are added;
  observer and migration pins are unchanged.
- The focused in-process treaty E2E runs without PostgreSQL in the focused/unit
  lane and is never reported as an integration-only prerequisite.
- The full V1-V4 regression lanes and static gates execute and pass; any
  unexecuted required lane is reported with its blocker and is not certified.
- Documentation states what treaties control (a belief), what they never
  control (objective action, permission, truth, enforcement, or a binding
  agreement), how participants, recognized representatives, records,
  institutional memory, versions, lineage, recollections, and `trt_v1` frames
  work, and every count matches the code. The docs sweep updates every current
  164 pin and leaves historical seam pins intact.
- `docs/diplomacy.md` is the canonical contract; `docs/analysis-metrics.md`
  documents the four families, `docs/research-api.md` documents the eight
  routes, `docs/research-ui.md` documents the view, `docs/v4-architecture.md`
  records the V4-11 seam, and README plus `docs/organizations.md` and
  `docs/delegation-representation.md` link the contract.
